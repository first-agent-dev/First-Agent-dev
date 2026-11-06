"""C0/C1/C3: private frame budgets, not EXEC or daemon acceptance."""

from __future__ import annotations

import socket
import struct
import threading
import time
from collections.abc import Iterator
from typing import Any, override

import pytest

from fa.execution.cell_protocol import decode_cell_reply, encode_cell_request
from fa.execution.docker import DockerAttachStream
from fa.execution.protocol import MAX_EXTENDED_FRAME_BYTES, MAX_FRAME_BYTES, MAX_TAIL_BYTES, encode_json, read_frame
from fa.execution.types import ExecutionContractError
from fa.execution.worker_client import WorkerClient, WorkerUnavailableError


class ObservedStream(DockerAttachStream):
    def __init__(self, connection: socket.socket) -> None:
        super().__init__(connection)
        self.read_started = threading.Event()

    @override
    def read_frame(self, *, deadline: float, max_bytes: int = MAX_FRAME_BYTES) -> bytes:
        self.read_started.set()
        return super().read_frame(deadline=deadline, max_bytes=max_bytes)


@pytest.fixture
def transport() -> Iterator[tuple[ObservedStream, socket.socket]]:
    left, right = socket.socketpair()
    right.settimeout(10)
    stream = ObservedStream(left)
    try:
        yield stream, right
    finally:
        stream.close()
        right.close()


def deadline() -> float:
    return time.monotonic() + 10


def req(action: str, request_id: str) -> bytes:
    payload: dict[str, Any] = (
        {} if action == "LIST" else {"command": "not executed", "cwd": ".", "timeout_ms": 1000, "session_id": "main"}
    )
    return encode_cell_request(request_id=request_id, action=action, payload=payload)


def reply(action: str, request_id: str) -> bytes:
    result: dict[str, Any] = (
        {"sessions": [], "message": ""}
        if action == "LIST"
        else {"stdout": "ok", "exit_code": 0, "truncated": False, "session_id": "main", "timed_out": False}
    )
    return encode_json({"version": 1, "request_id": request_id, "result": result, "error": None})


def padded(raw: bytes, size: int) -> bytes:
    assert size >= len(raw)
    return raw + b" " * (size - len(raw))


def send(peer: socket.socket, raw: bytes) -> None:
    frame = struct.pack("!I", len(raw)) + raw
    peer.sendall(b"\x01\0\0\0" + struct.pack("!I", len(frame)) + frame)


def assert_sent(peer: socket.socket, request_id: str) -> None:
    # Client -> worker is the existing unmultiplexed private frame.
    from fa.execution.protocol import _loads

    assert _loads(read_frame(peer))["request_id"] == request_id


@pytest.mark.parametrize("run_first", [True, False])
def test_pending_control_then_extended_run_is_bound_even_if_read_already_blocked(
    transport: tuple[ObservedStream, socket.socket], run_first: bool
) -> None:
    stream, peer = transport
    limit = MAX_FRAME_BYTES + 256
    client = WorkerClient(stream, max_reply_bytes=limit)
    try:
        control = client.begin(req("LIST", "1" * 32), deadline=deadline())
        assert_sent(peer, "1" * 32)
        assert stream.read_started.wait(2)  # Reader selected its budget before RUN registration.
        run = client.begin(req("RUN", "2" * 32), deadline=deadline(), max_reply_bytes=limit)
        assert_sent(peer, "2" * 32)
        big = padded(reply("RUN", "2" * 32), limit)
        if run_first:
            send(peer, big)
            assert client.await_reply(run, deadline=deadline())["stdout"] == "ok"
            send(peer, reply("LIST", "1" * 32))
            assert client.await_reply(control, deadline=deadline())["sessions"] == []
        else:
            send(peer, reply("LIST", "1" * 32))
            assert client.await_reply(control, deadline=deadline())["sessions"] == []
            send(peer, big)
            assert client.await_reply(run, deadline=deadline())["stdout"] == "ok"
    finally:
        client.close(deadline=deadline())


def test_large_control_cannot_borrow_pending_run_budget(transport: tuple[ObservedStream, socket.socket]) -> None:
    stream, peer = transport
    limit = MAX_FRAME_BYTES + 256
    client = WorkerClient(stream, max_reply_bytes=limit)
    try:
        control = client.begin(req("LIST", "1" * 32), deadline=deadline())
        assert_sent(peer, "1" * 32)
        assert stream.read_started.wait(2)
        run = client.begin(req("RUN", "2" * 32), deadline=deadline(), max_reply_bytes=limit)
        assert_sent(peer, "2" * 32)
        send(peer, padded(reply("LIST", "1" * 32), MAX_FRAME_BYTES + 1))
        assert control.pending.event.wait(2) and run.pending.event.wait(2)
        with pytest.raises(WorkerUnavailableError):
            client.await_reply(control, deadline=deadline())
        with pytest.raises(WorkerUnavailableError):
            client.await_reply(run, deadline=deadline())
        with pytest.raises(WorkerUnavailableError):
            client.begin(req("LIST", "3" * 32), deadline=deadline())
        assert peer.recv(1) == b""  # The poisoned stream closed, with no retry frame.
    finally:
        client.close(deadline=deadline())


@pytest.mark.parametrize("over", [False, True])
def test_request_budget_is_exact_byte_boundary(transport: tuple[ObservedStream, socket.socket], over: bool) -> None:
    stream, peer = transport
    client = WorkerClient(stream)
    try:
        exchange = client.begin(req("LIST", "1" * 32), deadline=deadline(), max_reply_bytes=512)
        assert_sent(peer, "1" * 32)
        send(peer, padded(reply("LIST", "1" * 32), 512 + int(over)))
        if over:
            with pytest.raises(WorkerUnavailableError):
                client.await_reply(exchange, deadline=deadline())
        else:
            assert client.await_reply(exchange, deadline=deadline())["sessions"] == []
    finally:
        client.close(deadline=deadline())


@pytest.mark.parametrize("bad", [0, True, -1, MAX_EXTENDED_FRAME_BYTES + 1])
def test_invalid_channel_budget_refused_before_reader_starts(
    transport: tuple[ObservedStream, socket.socket], bad: int
) -> None:
    stream, _peer = transport
    with pytest.raises(ExecutionContractError):
        WorkerClient(stream, max_reply_bytes=bad)
    assert not stream.read_started.is_set()


@pytest.mark.parametrize("action,budget", [("RUN", MAX_FRAME_BYTES + 1), ("LIST", MAX_FRAME_BYTES + 1), ("RUN", True)])
def test_invalid_request_budget_fails_before_write_and_keeps_channel_usable(
    transport: tuple[ObservedStream, socket.socket], action: str, budget: int
) -> None:
    stream, peer = transport
    # LIST cannot use extended budget even on a channel that supports it.
    client = WorkerClient(stream, max_reply_bytes=MAX_EXTENDED_FRAME_BYTES if action == "LIST" else MAX_FRAME_BYTES)
    try:
        with pytest.raises(ExecutionContractError):
            client.begin(req(action, "1" * 32), deadline=deadline(), max_reply_bytes=budget)
        peer.settimeout(0.05)
        with pytest.raises(TimeoutError):
            peer.recv(1)
        peer.settimeout(10)
        control = client.begin(req("LIST", "2" * 32), deadline=deadline())
        assert_sent(peer, "2" * 32)
        send(peer, reply("LIST", "2" * 32))
        assert client.await_reply(control, deadline=deadline())["sessions"] == []
    finally:
        client.close(deadline=deadline())


def test_extended_frame_does_not_expand_stdout_tail_or_default_codec() -> None:
    body = {
        "version": 1,
        "request_id": "1" * 32,
        "result": {
            "stdout": "x" * (MAX_TAIL_BYTES + 1),
            "exit_code": 0,
            "truncated": False,
            "session_id": "main",
            "timed_out": False,
        },
        "error": None,
    }
    raw = padded(encode_json(body), MAX_FRAME_BYTES + 1)
    with pytest.raises(ExecutionContractError):
        decode_cell_reply(raw, request_id="1" * 32, action="RUN", session_id="main")
    with pytest.raises(ExecutionContractError):
        decode_cell_reply(raw, request_id="1" * 32, action="RUN", session_id="main", max_bytes=len(raw))


def test_big_run_without_explicit_request_budget_poisoned(transport: tuple[ObservedStream, socket.socket]) -> None:
    stream, peer = transport
    client = WorkerClient(stream, max_reply_bytes=MAX_FRAME_BYTES + 100)
    try:
        exchange = client.begin(req("RUN", "1" * 32), deadline=deadline())
        assert_sent(peer, "1" * 32)
        send(peer, padded(reply("RUN", "1" * 32), MAX_FRAME_BYTES + 1))
        with pytest.raises(WorkerUnavailableError):
            client.await_reply(exchange, deadline=deadline())
    finally:
        client.close(deadline=deadline())


def test_extended_unknown_id_poisons_both_pending(transport: tuple[ObservedStream, socket.socket]) -> None:
    stream, peer = transport
    limit = MAX_FRAME_BYTES + 10
    client = WorkerClient(stream, max_reply_bytes=limit)
    try:
        control = client.begin(req("LIST", "1" * 32), deadline=deadline())
        assert_sent(peer, "1" * 32)
        run = client.begin(req("RUN", "2" * 32), deadline=deadline(), max_reply_bytes=limit)
        assert_sent(peer, "2" * 32)
        send(peer, padded(reply("RUN", "3" * 32), limit))
        with pytest.raises(WorkerUnavailableError):
            client.await_reply(control, deadline=deadline())
        with pytest.raises(WorkerUnavailableError):
            client.await_reply(run, deadline=deadline())
    finally:
        client.close(deadline=deadline())


def test_channel_ceiling_rejects_declared_size_before_body(transport: tuple[ObservedStream, socket.socket]) -> None:
    stream, peer = transport
    limit = MAX_FRAME_BYTES + 10
    client = WorkerClient(stream, max_reply_bytes=limit)
    try:
        run = client.begin(req("RUN", "1" * 32), deadline=deadline(), max_reply_bytes=limit)
        assert_sent(peer, "1" * 32)
        # Two headers only: neither a declared oversized frame nor its body is accepted.
        peer.sendall(b"\x01\0\0\0" + struct.pack("!I", 4) + struct.pack("!I", limit + 1))
        with pytest.raises(WorkerUnavailableError):
            client.await_reply(run, deadline=deadline())
    finally:
        client.close(deadline=deadline())


def test_oversized_reply_is_refused_before_cell_result_decode(
    transport: tuple[ObservedStream, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.execution import worker_client

    original = worker_client.decode_cell_reply
    decoded: list[bytes] = []

    def observe(raw: bytes, **kwargs: Any) -> dict[str, Any] | None:
        decoded.append(raw)
        return original(raw, **kwargs)

    monkeypatch.setattr(worker_client, "decode_cell_reply", observe)
    stream, peer = transport
    client = WorkerClient(stream)
    try:
        exchange = client.begin(req("LIST", "1" * 32), deadline=deadline(), max_reply_bytes=512)
        assert_sent(peer, "1" * 32)
        send(peer, padded(reply("LIST", "1" * 32), 513))
        with pytest.raises(WorkerUnavailableError):
            client.await_reply(exchange, deadline=deadline())
        assert decoded == []
    finally:
        client.close(deadline=deadline())


def test_request_forwards_opt_in_to_begin(transport: tuple[ObservedStream, socket.socket]) -> None:
    stream, peer = transport
    limit = MAX_FRAME_BYTES + 128
    client = WorkerClient(stream, max_reply_bytes=limit)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            assert_sent(peer, "1" * 32)
            send(peer, padded(reply("RUN", "1" * 32), limit))
        except (OSError, AssertionError) as error:
            errors.append(error)

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        assert client.request(req("RUN", "1" * 32), deadline=deadline(), max_reply_bytes=limit)["stdout"] == "ok"
    finally:
        client.close(deadline=deadline())
        thread.join(10)
    assert not thread.is_alive() and errors == []
