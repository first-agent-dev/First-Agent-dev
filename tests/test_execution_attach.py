"""C0/C3 native Unix upgrade/mux + actual local worker/PTY, NOT Docker/C1."""

from __future__ import annotations

import socket
import struct
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from fa.execution.cell_protocol import decode_cell_reply, encode_cell_request
from fa.execution.cell_worker import CellWorker, serve, serve_once
from fa.execution.docker import DockerUnavailableError
from fa.execution.protocol import MAX_FRAME_BYTES, MAX_TAIL_BYTES, _loads, encode_json, read_frame
from fa.execution.types import ExecutionContractError
from fa.execution.worker_client import WorkerClient, WorkerUnavailableError
from fa.runtime.pty_pool import PtyPool
from tests.test_execution_client import profile
from tests.test_execution_docker import Case, Endpoint, Reply, observation
from tests.test_execution_journal import CID

UPGRADE = (
    b"HTTP/1.1 101 UPGRADED\r\nContent-Type: application/vnd.docker.raw-stream\r\n"
    b"Connection: Upgrade\r\nUpgrade: tcp\r\n\r\n"
)


@pytest.fixture
def endpoint(tmp_path: Path) -> Iterator[Endpoint]:
    private = tmp_path / "attach-private"
    private.mkdir(mode=0o700)
    peer = Endpoint(private / "engine.sock")
    try:
        yield peer
    finally:
        peer.close()


def until(seconds: float = 2) -> float:
    return time.monotonic() + seconds


def message(action: str = "LIST", payload: dict[str, Any] | None = None, rid: str = "1" * 32) -> bytes:
    return encode_cell_request(request_id=rid, action=action, payload={} if payload is None else payload)


def run(command: str, rid: str = "1" * 32, *, timeout: int = 1000) -> bytes:
    return message("RUN", {"command": command, "cwd": ".", "timeout_ms": timeout, "session_id": "main"}, rid)


def reply(rid: str = "1" * 32, result: dict[str, Any] | None = None) -> bytes:
    return encode_json(
        {
            "version": 1,
            "request_id": rid,
            "result": {"sessions": [], "message": ""} if result is None else result,
            "error": None,
        }
    )


def framed(raw: bytes) -> bytes:
    return struct.pack("!I", len(raw)) + raw


def mux(raw: bytes, kind: int = 1) -> bytes:
    return bytes([kind, 0, 0, 0]) + struct.pack("!I", len(raw)) + raw


def test_upgrade_preserves_coalesced_stream_and_demuxes_fragments(endpoint: Endpoint) -> None:
    raw = reply()
    wire = framed(raw)
    endpoint.replies.append(Reply(raw=UPGRADE + mux(b"diagnostic", 2) + mux(wire[:2], 0) + mux(wire[2:])))
    stream = endpoint.engine().attach(CID, deadline=until())
    try:
        assert stream.read_frame(deadline=until()) == raw
        assert stream.stderr_tail == b"diagnostic"
        assert len(endpoint.seen) == 1
        seen = endpoint.seen[0]
        assert seen["method"] == "POST" and seen["body"] is None
        assert seen["path"] == (f"/v1.45/containers/{CID}/attach?stream=1&stdin=1&stdout=1&stderr=1&logs=0&detachKeys=")
    finally:
        stream.close()


@pytest.mark.parametrize(
    "bad",
    [
        UPGRADE.replace(b"101 UPGRADED", b"200 OK"),
        UPGRADE.replace(b"Upgrade: tcp", b"Upgrade: websocket"),
        UPGRADE.replace(b"Connection: Upgrade", b"Connection: close"),
        UPGRADE.replace(b"Connection: Upgrade", b"Connection: Upgrade\r\nConnection: Upgrade"),
        UPGRADE.replace(b"\r\n\r\n", b"\r\nContent-Length: 10\r\n\r\n"),
        UPGRADE.replace(b"\r\n\r\n", b"\r\nTransfer-Encoding: chunked\r\n\r\n"),
        b"HTTP/1.1 500 private-daemon-diagnostic\r\n\r\nprivate-body",
    ],
)
def test_failed_upgrade_is_sanitized_without_fallback_or_retry(endpoint: Endpoint, bad: bytes) -> None:
    endpoint.replies.append(Reply(raw=bad))
    returned = None
    try:
        with pytest.raises(DockerUnavailableError) as caught:
            returned = endpoint.engine().attach(CID, deadline=until())
    finally:
        if returned is not None:
            returned.close()
    assert str(caught.value) == "execution_engine_unavailable" and len(endpoint.seen) == 1


@pytest.mark.parametrize(
    "data",
    [
        bytes([3, 0, 0, 0]) + struct.pack("!I", len(framed(reply()))) + framed(reply()),
        bytes([1, 1, 0, 0]) + struct.pack("!I", len(framed(reply()))) + framed(reply()),
        bytes([1, 0, 0, 0]) + struct.pack("!I", MAX_FRAME_BYTES + 5),
        mux(b"\0\0\0\0"),
        mux(struct.pack("!I", MAX_FRAME_BYTES + 1)),
        mux(struct.pack("!I", 10) + b"{}"),
    ],
)
def test_malformed_mux_or_nested_frame_is_unavailable(endpoint: Endpoint, data: bytes) -> None:
    endpoint.replies.append(Reply(raw=UPGRADE + data))
    stream = endpoint.engine().attach(CID, deadline=until())
    try:
        with pytest.raises(DockerUnavailableError):
            stream.read_frame(deadline=until())
    finally:
        stream.close()
    assert len(endpoint.seen) == 1


def test_stderr_memory_is_tail_bounded(endpoint: Endpoint) -> None:
    endpoint.replies.append(Reply(raw=UPGRADE + mux(b"a" * (MAX_TAIL_BYTES + 20), 2) + mux(framed(reply()))))
    stream = endpoint.engine().attach(CID, deadline=until())
    try:
        assert stream.read_frame(deadline=until()) == reply()
        assert stream.stderr_tail == b"a" * MAX_TAIL_BYTES
    finally:
        stream.close()


def test_owned_journal_gate_and_inspection_precede_attach(endpoint: Endpoint, tmp_path: Path) -> None:
    case = Case(endpoint, tmp_path)
    endpoint.replies.extend([Reply(200, observation()), Reply(raw=UPGRADE + mux(framed(reply())))])
    stream = case.cells.attach_created(case.req, profile=profile(), deadline=until())
    try:
        assert stream.read_frame(deadline=until()) == reply()
        assert len(endpoint.seen) == 2 and endpoint.seen[0]["path"].endswith("/json")
        assert "/attach?" in endpoint.seen[1]["path"]
    finally:
        stream.close()


@pytest.mark.parametrize("status", ["created", "exited", "paused", "dead", "restarting"])
def test_nonrunning_cell_is_never_attached(endpoint: Endpoint, tmp_path: Path, status: str) -> None:
    case = Case(endpoint, tmp_path)
    endpoint.replies.extend([Reply(200, observation(status)), Reply(raw=UPGRADE)])
    returned = None
    try:
        with pytest.raises(DockerUnavailableError):
            returned = case.cells.attach_created(case.req, profile=profile(), deadline=until())
    finally:
        if returned is not None:
            returned.close()
    assert len(endpoint.seen) == 1


@pytest.fixture
def local_worker(tmp_path: Path) -> Iterator[CellWorker]:
    pool = PtyPool(base_cwd=tmp_path, run_id="attach-unit")
    worker = CellWorker(pool, workspace=tmp_path, max_command_ms=3000)
    # Must precede HTTP fixture threads (also on the test process main thread).
    assert worker.handle(run("true"))["exit_code"] == 0
    try:
        yield worker
    finally:
        worker.close()


@pytest.fixture
def worker_endpoint(local_worker: CellWorker, tmp_path: Path) -> Iterator[Endpoint]:
    private = tmp_path / "worker-private"
    private.mkdir(mode=0o700)
    peer = Endpoint(private / "engine.sock")
    try:
        yield peer
    finally:
        peer.close()


def test_real_worker_pty_state_and_controls_share_one_owned_attach(
    local_worker: CellWorker,
    worker_endpoint: Endpoint,
    tmp_path: Path,
) -> None:
    worker, endpoint = local_worker, worker_endpoint
    finished = threading.Event()

    class MuxWorker:
        def __init__(self, peer: socket.socket) -> None:
            self.peer = peer
            self.writes = threading.Lock()

        def recv(self, size: int, /) -> bytes:
            return self.peer.recv(size)

        def sendall(self, raw: bytes, /) -> None:
            with self.writes:
                self.peer.sendall(mux(raw))

    def bridge(peer: socket.socket) -> None:
        peer.settimeout(4)
        try:
            serve(worker, MuxWorker(peer))
        except (ExecutionContractError, OSError):
            pass  # Expected EOF after client close; never a terminality oracle.
        finally:
            finished.set()

    case = Case(endpoint, tmp_path)
    endpoint.replies.extend([Reply(200, observation()), Reply(raw=UPGRADE, upgraded=bridge)])
    client = WorkerClient(case.cells.attach_created(case.req, profile=profile(), deadline=until()))
    try:
        assert client.request(run("export FA_ATTACH_CHECK=kept"), deadline=until())["exit_code"] == 0
        observed = client.request(run('printf "%s" "$FA_ATTACH_CHECK"', "2" * 32), deadline=until())
        assert observed["exit_code"] == 0 and "kept" in observed["stdout"] and not observed["timed_out"]
        assert client.request(message(rid="3" * 32), deadline=until())["sessions"] == ["main"]
        with ThreadPoolExecutor(max_workers=1) as executor:
            busy = executor.submit(client.request, run("sleep 1", "4" * 32, timeout=2000), deadline=until(3))
            control = client.request(message("LIST", rid="5" * 32), deadline=until(0.5))
            assert control["sessions"] == ["main"] and not busy.done()
            assert busy.result(3)["exit_code"] == 0
        interrupted = client.request(message("INTERRUPT", {"session_id": "main"}, "6" * 32), deadline=until(0.5))
        assert "message" in interrupted  # Idle Ctrl-C ACK, NOT process terminality.
        assert client.request(message("CLOSE", {"session_id": "main"}, "7" * 32), deadline=until())["sessions"] == []
        assert client.request(message("STOP", rid="8" * 32), deadline=until())["sessions"] == []
        assert len(endpoint.seen) == 2  # No per-command create/start/reattach.
    finally:
        client.close(deadline=until())
        assert finished.wait(3)
        worker.close()


def test_out_of_order_control_and_run_are_correlated(endpoint: Endpoint) -> None:
    seen: list[dict[str, Any]] = []
    first = threading.Event()

    def bridge(peer: socket.socket) -> None:
        peer.settimeout(3)
        seen.append(_loads(read_frame(peer)))
        first.set()
        seen.append(_loads(read_frame(peer)))
        peer.sendall(mux(framed(reply("2" * 32))))
        peer.sendall(
            mux(
                framed(
                    reply(
                        result={
                            "stdout": "ok",
                            "exit_code": 7,
                            "truncated": False,
                            "session_id": "main",
                            "timed_out": False,
                        }
                    )
                )
            )
        )

    endpoint.replies.append(Reply(raw=UPGRADE, upgraded=bridge))
    client = WorkerClient(endpoint.engine().attach(CID, deadline=until()))
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(client.request, run("literal, not executed"), deadline=until())
            assert first.wait(1)
            assert (
                client.request(message("INTERRUPT", {"session_id": "main"}, "2" * 32), deadline=until())["sessions"]
                == []
            )
            outcome = future.result(2)
        assert outcome["stdout"] == "ok" and outcome["exit_code"] == 7
        assert [request["action"] for request in seen] == ["RUN", "INTERRUPT"]
    finally:
        client.close(deadline=until())


@pytest.mark.parametrize("fault", ["eof", "wrong-id", "wrong-fields", "worker-error", "timeout"])
def test_uncertain_exchange_poisoned_without_resend(endpoint: Endpoint, fault: str) -> None:
    seen: list[dict[str, Any]] = []

    def bridge(peer: socket.socket) -> None:
        peer.settimeout(1)
        seen.append(_loads(read_frame(peer)))
        if fault == "timeout":
            # Wait for the actual client deadline/close, no polling or fixed sleep.
            assert peer.recv(1) == b""
        elif fault != "eof":
            body = _loads(reply("9" * 32 if fault == "wrong-id" else "1" * 32))
            if fault == "wrong-fields":
                body["result"]["authority"] = "forged"
            if fault == "worker-error":
                body.update(result=None, error="WORKER_UNAVAILABLE")
            peer.sendall(mux(framed(encode_json(body))))

    endpoint.replies.append(Reply(raw=UPGRADE, upgraded=bridge))
    client = WorkerClient(endpoint.engine().attach(CID, deadline=until()))
    try:
        with pytest.raises(WorkerUnavailableError, match=r"^execution_worker_unavailable$"):
            client.request(message(), deadline=until(0.08))
        with pytest.raises(WorkerUnavailableError):
            client.request(message(rid="2" * 32), deadline=until())
        assert len(seen) == len(endpoint.seen) == 1
    finally:
        client.close(deadline=until())


@pytest.mark.parametrize(
    "mutation", ["bool-exit", "missing-timeout", "foreign-session", "extra", "provisional", "large"]
)
def test_worker_result_codec_is_closed_and_preserves_unknown(mutation: str) -> None:
    body = _loads(
        reply(result={"stdout": "x", "exit_code": 7, "truncated": False, "session_id": "main", "timed_out": False})
    )
    if mutation == "bool-exit":
        body["result"]["exit_code"] = True
    elif mutation == "missing-timeout":
        del body["result"]["timed_out"]
    elif mutation == "foreign-session":
        body["result"]["session_id"] = "other"
    elif mutation == "extra":
        body["result"]["terminal_barrier"] = True
    elif mutation == "provisional":
        body["result"]["exit_code"] = -1
    else:
        body["result"]["stdout"] = "é" * MAX_TAIL_BYTES
    with pytest.raises(ExecutionContractError):
        decode_cell_reply(encode_json(body), request_id="1" * 32, action="RUN", session_id="main")


def test_worker_timeout_fields_are_not_rewritten() -> None:
    result = {"stdout": "partial", "exit_code": -1, "truncated": True, "session_id": "main", "timed_out": True}
    assert decode_cell_reply(reply(result=result), request_id="1" * 32, action="RUN", session_id="main") == result


def test_one_shot_status_survives_actual_worker_and_native_attach(
    local_worker: CellWorker,
    worker_endpoint: Endpoint,
) -> None:
    exited: list[int] = []
    done = threading.Event()

    class MuxWorker:
        def __init__(self, peer: socket.socket) -> None:
            self.peer = peer

        def recv(self, size: int, /) -> bytes:
            return self.peer.recv(size)

        def sendall(self, raw: bytes, /) -> None:
            self.peer.sendall(mux(raw))

    def bridge(peer: socket.socket) -> None:
        peer.settimeout(2)
        try:
            exited.append(serve_once(local_worker, MuxWorker(peer)))
        finally:
            done.set()

    worker_endpoint.replies.append(Reply(raw=UPGRADE, upgraded=bridge))
    client = WorkerClient(worker_endpoint.engine().attach(CID, deadline=until()))
    try:
        outcome = client.request(run("printf one-shot; exit 7"), deadline=until())
        assert outcome["exit_code"] == 7 and not outcome["timed_out"]
        assert "one-shot" in outcome["stdout"] and "terminal_barrier" not in outcome
        assert done.wait(2) and exited == [7]  # Local function status, NOT actual container exit.
        assert len(worker_endpoint.seen) == 1
    finally:
        client.close(deadline=until())


def test_lifetime_is_not_capped_at_one_response_frame(endpoint: Endpoint) -> None:
    raw = b"x" * (512 * 1024)
    endpoint.replies.append(Reply(raw=UPGRADE + mux(framed(raw) * 2) * 5))
    stream = endpoint.engine().attach(CID, deadline=until())
    try:
        for _ in range(10):
            assert stream.read_frame(deadline=until()) == raw
    finally:
        stream.close()


def test_backpressured_stdin_uses_absolute_write_budget(endpoint: Endpoint) -> None:
    release = threading.Event()

    def bridge(peer: socket.socket) -> None:
        assert release.wait(2), "test failed to release deliberately nonreading peer"

    endpoint.replies.append(Reply(raw=UPGRADE, upgraded=bridge))
    stream = endpoint.engine().attach(CID, deadline=until())
    try:
        with pytest.raises(DockerUnavailableError):
            stream.write_frame(b"x" * MAX_FRAME_BYTES, deadline=until(0.05))
    finally:
        release.set()
        stream.close()


def test_slow_mux_payload_cannot_reset_read_budget(endpoint: Endpoint) -> None:
    data = mux(framed(reply()))
    endpoint.replies.append(Reply(chunks=[UPGRADE, *[data[i : i + 2] for i in range(0, len(data), 2)]]))
    stream = endpoint.engine().attach(CID, deadline=until())
    started = time.monotonic()
    try:
        with pytest.raises(DockerUnavailableError):
            stream.read_frame(deadline=until(0.07))
        assert time.monotonic() - started < 0.5  # Generous ceiling, drip would take >1s.
    finally:
        stream.close()


def test_attach_kernel_peer_gate_precedes_any_http(endpoint: Endpoint, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    endpoint.replies.append(Reply(raw=UPGRADE))
    monkeypatch.setattr(
        socket.socket, "getsockopt", lambda *args: struct.pack("3i", os.getpid(), os.getuid() + 1, os.getgid())
    )
    returned = None
    try:
        with pytest.raises(DockerUnavailableError):
            returned = endpoint.engine().attach(CID, deadline=until())
    finally:
        if returned is not None:
            returned.close()
    assert endpoint.seen == []


def test_bad_ownership_binding_never_observes_or_attaches(endpoint: Endpoint, tmp_path: Path) -> None:
    from fa.execution.journal import JournalError

    case = Case(endpoint, tmp_path)
    case.req["payload"]["command"] = "different command"
    with pytest.raises(JournalError):
        case.cells.attach_created(case.req, profile=profile(), deadline=until())
    assert endpoint.seen == []


def test_queued_run_timeout_and_duplicate_pending_id_do_not_send_or_poison_original(endpoint: Endpoint) -> None:
    seen: list[dict[str, Any]] = []
    first = threading.Event()

    def bridge(peer: socket.socket) -> None:
        peer.settimeout(2)
        seen.append(_loads(read_frame(peer)))
        first.set()
        seen.append(_loads(read_frame(peer)))
        peer.sendall(mux(framed(reply("3" * 32))))
        peer.sendall(
            mux(
                framed(
                    reply(
                        result={
                            "stdout": "kept",
                            "exit_code": 0,
                            "truncated": False,
                            "session_id": "main",
                            "timed_out": False,
                        }
                    )
                )
            )
        )

    endpoint.replies.append(Reply(raw=UPGRADE, upgraded=bridge))
    client = WorkerClient(endpoint.engine().attach(CID, deadline=until()))
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            active = executor.submit(client.request, run("not executed"), deadline=until())
            assert first.wait(1)
            with pytest.raises(WorkerUnavailableError):
                client.request(run("not sent", "2" * 32), deadline=until(0.03))
            with pytest.raises(WorkerUnavailableError):
                client.request(message(), deadline=until())  # Duplicate outstanding request_id.
            assert client.request(message(rid="3" * 32), deadline=until())["sessions"] == []
            assert active.result(2)["stdout"] == "kept"
        assert [req["request_id"] for req in seen] == ["1" * 32, "3" * 32]
        assert len(endpoint.seen) == 1
    finally:
        client.close(deadline=until())


@pytest.mark.parametrize("cwd", ["../x", "x/../y", "x/./y", "x//y", "/absolute"])
def test_closed_cell_cwd_is_rejected_before_write(endpoint: Endpoint, cwd: str) -> None:
    with pytest.raises(ExecutionContractError):
        encode_cell_request(
            request_id="1" * 32,
            action="RUN",
            payload={"command": "not sent", "cwd": cwd, "timeout_ms": 1, "session_id": "main"},
        )
    assert endpoint.seen == []


def test_reply_codec_rejects_mismatched_request_id() -> None:
    with pytest.raises(ExecutionContractError):
        decode_cell_reply(reply("2" * 32), request_id="1" * 32, action="LIST", session_id=None)


def test_lost_stream_wakes_all_pending_without_reconnect(endpoint: Endpoint) -> None:
    seen: list[dict[str, Any]] = []
    first = threading.Event()

    def bridge(peer: socket.socket) -> None:
        peer.settimeout(2)
        seen.append(_loads(read_frame(peer)))
        first.set()
        seen.append(_loads(read_frame(peer)))
        # Literal EOF with both requests outstanding.

    endpoint.replies.append(Reply(raw=UPGRADE, upgraded=bridge))
    client = WorkerClient(endpoint.engine().attach(CID, deadline=until()))
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            active = executor.submit(client.request, run("not executed"), deadline=until())
            assert first.wait(1)
            with pytest.raises(WorkerUnavailableError):
                client.request(message(rid="2" * 32), deadline=until())
            with pytest.raises(WorkerUnavailableError):
                active.result(2)
        assert len(seen) == 2 and len(endpoint.seen) == 1
    finally:
        client.close(deadline=until())


@pytest.mark.parametrize("deadline", [float("inf"), float("nan"), True])
def test_invalid_attach_deadline_is_rejected_before_contact(endpoint: Endpoint, deadline: float) -> None:
    with pytest.raises(ExecutionContractError):
        endpoint.engine().attach(CID, deadline=deadline)
    assert endpoint.seen == []
