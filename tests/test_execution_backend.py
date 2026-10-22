"""C0/C3 real episode owner over the native attach transport, NOT Docker/C1.

The Docker engine is a literal HTTP peer and the cell worker is the real local
PTY worker. No container, cgroup, descendant barrier or receipt is proven here.

Cancel path inventory (I03 SLICE1 STEP2, spec §2.2 + E262 note):
  G1 interactive episode cancel: episode map -> intent -> original creation cell.
  G2 one-shot cancel of a RUNNING operation: journal record -> intent -> that CID.
  G3 one-shot cancel from another view: UNAUTHORIZED, no journal write, no request.
  G4 one-shot cancel of an unknown operation: EXECUTION_UNKNOWN, no request.
  G5 one-shot cancel before any cell exists: durable intent, `not_created`, and
     the refused operation can never create/start afterwards.
  G6 one-shot cancel with a fresh backend: no in-memory episode map is required.
"""

from __future__ import annotations

import os
import queue
import socket
import struct
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any, override

import pytest

from fa.execution.backend import CellBackend, CommandOutcome, _EpisodeKey
from fa.execution.cell_protocol import decode_cell_request, encode_cell_request
from fa.execution.cell_worker import CellWorker, serve
from fa.execution.docker import DockerEngine, DockerUnavailableError
from fa.execution.journal import JournalError
from fa.execution.protocol import encode_json
from fa.execution.supervisor import SupervisorError
from fa.execution.types import ExecutionContractError, NamespaceRef
from fa.execution.workspace import WorkspaceAuthority
from fa.runtime.pty_pool import PtyPool
from tests.test_execution_admission import claim, close
from tests.test_execution_admission import request as admission_request
from tests.test_execution_dispatch import profile
from tests.test_execution_docker import Endpoint, Reply
from tests.test_execution_views import create as create_view
from tests.test_execution_workspace import ACTOR, OTHER, PEER, Site, ok, until
from tests.test_execution_workspace import site as site

UPGRADE = (
    b"HTTP/1.1 101 UPGRADED\r\nContent-Type: application/vnd.docker.raw-stream\r\n"
    b"Connection: Upgrade\r\nUpgrade: tcp\r\nContent-Length: 0\r\n\r\n"
)
CID = "b" * 64


def native_profile() -> Any:
    # Real chown/IO needs the actual service UID; this is NOT deployed UID proof.
    # The command budget exceeds the journal lock timeout so a cancel issued
    # while a command runs really contends for the journal lock.
    return replace(profile(), uid=os.getuid() or 1000, gid=os.getgid() or 1000, max_command_ms=5000)


def observation(operation_id: str, view_id: str, *, status: str = "running") -> dict[str, Any]:
    running = status in {"running", "paused"}
    return {
        "Id": CID,
        "Name": "/fa-job-" + operation_id.removeprefix("op-"),
        "Image": native_profile().image_digest,
        "Config": {
            "Image": native_profile().image,
            "Labels": {"fa.execution.operation_id": operation_id, "fa.execution.view_id": view_id},
        },
        "State": {
            "Status": status,
            "Running": running,
            "Paused": status == "paused",
            "Restarting": status == "restarting",
            "Dead": status == "dead",
            "OOMKilled": False,
            "Pid": 123 if running else 0,
            "ExitCode": 7 if status == "exited" else 0,
        },
    }


class CountingWorker(CellWorker):
    """Real worker that counts the RUN frames it actually receives."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.runs = 0
        self.broken = False

    @override
    def handle(self, raw: bytes) -> dict[str, Any]:
        record = decode_cell_request(raw)
        if record["action"] == "RUN":
            self.runs += 1
        if self.broken:
            raise ExecutionContractError
        return super().handle(raw)


class MuxWorker:
    """Docker multiplexed framing over the real upgraded socket."""

    def __init__(self, peer: socket.socket) -> None:
        self._peer = peer

    def recv(self, size: int, /) -> bytes:
        return self._peer.recv(size)

    def sendall(self, data: bytes, /) -> None:
        self._peer.sendall(mux(data))


class FakeWorkerStream:
    """Private protocol peer for backend lifecycle tests, not worker proof."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self._replies: queue.Queue[bytes | None] = queue.Queue()
        self.closed = False

    def write_frame(self, raw: bytes, *, deadline: float) -> None:
        if time.monotonic() >= deadline:
            raise OSError("fake_worker_deadline")
        request = decode_cell_request(raw)
        self.requests.append(request)
        result = {
            "stdout": "fake one-shot result",
            "exit_code": 0,
            "truncated": False,
            "session_id": request["payload"]["session_id"],
            "timed_out": False,
        }
        self._replies.put(
            encode_json(
                {
                    "version": 1,
                    "request_id": request["request_id"],
                    "result": result,
                    "error": None,
                }
            )
        )

    def read_frame(self, *, deadline: float) -> bytes:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OSError("fake_worker_deadline")
        try:
            reply = self._replies.get(timeout=remaining)
        except queue.Empty:
            raise OSError("fake_worker_deadline") from None
        if reply is None:
            raise OSError("fake_worker_closed")
        return reply

    def close(self) -> None:
        self.closed = True
        self._replies.put(None)


def mux(raw: bytes, kind: int = 1) -> bytes:
    return bytes([kind, 0, 0, 0]) + struct.pack("!I", len(raw)) + raw


class ObservedEngine(DockerEngine):
    """The real engine, plus a hook that runs while a daemon request completes.

    The hook observes the durable state at the exact moment a request reaches
    the daemon, so ordering (cancel intent BEFORE the stop) is observable and
    not inferred from a later read.
    """

    def __init__(self, path: Path, **kwargs: Any) -> None:
        super().__init__(path, **kwargs)
        self.observer: Callable[[str], None] | None = None

    @override
    def _request(self, method: str, path: str, *, body: dict[str, Any] | None, status: int, deadline: float) -> bytes:
        content = super()._request(method, path, body=body, status=status, deadline=deadline)
        if self.observer is not None:
            self.observer(f"{method} {path}")
        return content


class Backend:
    """Real authority + journal + literal HTTP Docker peer + real local worker."""

    def __init__(self, site: Site, tmp_path: Path, *, profile_override: Any | None = None) -> None:
        self.profile = native_profile() if profile_override is None else profile_override
        self.cache = tmp_path / "approved-cache"
        self.cache.mkdir(mode=0o755)
        self.authority = WorkspaceAuthority(
            site.state,
            approved_roots={"projects": site.roots},
            controller_uids=frozenset({PEER.uid}),
            lock_timeout_ms=1000,
            view_profile=self.profile,
            approved_cache=self.cache,
        )
        self.authority.__enter__()
        ids = ok(lambda: site.register(self.authority))
        lease = ok(lambda: site.claim(self.authority, ids))
        self.grant = ok(lambda: create_view(self.authority, ids, lease))
        self.worker = CountingWorker(
            PtyPool(base_cwd=tmp_path, run_id="backend-cell"),
            workspace=tmp_path,
            max_command_ms=self.profile.max_command_ms,
        )
        self.backend: CellBackend | None = None
        self.engine: DockerEngine | None = None
        # Must precede the HTTP fixture thread: the real PTY is forked on the
        # main thread, matching the production main-thread acquisition rule.
        self.worker.handle(
            encode_cell_request(
                request_id="0" * 32,
                action="RUN",
                payload={"command": "true", "cwd": ".", "timeout_ms": 2000, "session_id": "main"},
            )
        )
        self.worker.runs = 0  # The warm-up is not an episode command.

    def close(self) -> None:
        if self.backend is not None:
            self.backend.close(deadline=until())
        self.worker.close()
        self.authority.__exit__(None, None, None)

    def serve_worker(self, peer: socket.socket) -> None:
        peer.settimeout(5)
        try:
            serve(self.worker, MuxWorker(peer))
        except (OSError, ValueError):
            pass  # Expected EOF after the client closes; never a terminality oracle.

    @property
    def view(self) -> Any:
        assert self.grant.view_ref is not None
        return self.grant.view_ref

    peer: Endpoint

    def owner(self) -> CellBackend:
        assert self.backend is not None
        return self.backend

    def docker(self) -> DockerEngine:
        assert self.engine is not None
        return self.engine

    def episode_replies(self, operation_id: str, view_id: str | None = None) -> list[Reply]:
        view = self.view.view_id if view_id is None else view_id
        return [
            Reply(201, {"Id": CID, "Warnings": []}),
            Reply(204),
            Reply(200, observation(operation_id, view)),
            Reply(raw=UPGRADE, upgraded=self.serve_worker),
        ]

    def observe(self, callback: Callable[[str], None]) -> None:
        """Watch the daemon requests of this case without changing its behaviour."""
        engine = self.engine
        assert isinstance(engine, ObservedEngine)
        engine.observer = callback


@pytest.fixture
def backend(site: Site, tmp_path: Path) -> Iterator[Backend]:
    case = Backend(site, tmp_path)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    peer = Endpoint(private / "engine.sock")
    case.peer = peer
    case.engine = ObservedEngine(peer.path, daemon_uid=os.getuid(), api_version="1.45", rpc_timeout_ms=1000)
    case.backend = CellBackend(case.authority, case.engine, case.authority.journal)
    try:
        yield case
    finally:
        case.close()
        peer.close()


def exec_request(grant: Any, rid: str, command: str) -> dict[str, Any]:
    req = admission_request(grant)
    req["request_id"] = rid
    req["payload"]["operation_id"] = "op-" + rid
    req["payload"]["command"] = command
    req["payload"]["cwd"] = "."
    return req


def denied(code: str, call: Any) -> None:
    """A denial must be an ASSERTION about the closed code, never a leaked type."""
    try:
        call()
    except SupervisorError as error:
        assert error.code == code, f"expected {code}; observed {error.code}"
        return
    except (JournalError, DockerUnavailableError, ExecutionContractError, OSError) as error:
        raise AssertionError(f"expected {code}; observed {type(error).__name__}") from None
    raise AssertionError(f"expected {code}; observed success")


def ok_backend[T](call: Callable[[], T]) -> T:
    """A domain failure is a failed ASSERTION, never a leaked error type.

    The oracle still fails when the behavior is wrong; it only reports the
    failure as an assertion, so a producer mutation cannot earn credit from an
    unrelated exception class.
    """
    try:
        return call()
    except (SupervisorError, DockerUnavailableError, JournalError) as error:
        raise AssertionError(f"expected a successful backend outcome; observed {type(error).__name__}") from None


# The closed error surface of the backend. A thread records only these; any
# other exception escapes the thread and is reported by pytest as a warning,
# which is never kill credit.
DOMAIN_ERRORS = (SupervisorError, JournalError, DockerUnavailableError, ExecutionContractError, OSError)


def command_thread(backend: Backend, request: dict[str, Any], failures: list[Exception]) -> threading.Thread:
    """Run one command off the main thread and RECORD its outcome.

    A thread failure is never raised out of the thread: an unhandled thread
    exception is a pytest warning, and a warning is never kill credit. The
    oracle below decides whether the recorded outcome is a legal one.
    """

    def run() -> None:
        try:
            backend.owner().execute(PEER, request, deadline=until())
        except DOMAIN_ERRORS as error:  # Recorded for the oracle; never swallowed.
            failures.append(error)

    thread = threading.Thread(target=run)
    thread.start()
    return thread


def assert_cancelled_command_outcome(failures: list[Exception]) -> None:
    """A stopped owned cell may only end its command in a closed outcome."""
    for error in failures:
        assert isinstance(error, SupervisorError), f"unexpected thread failure: {type(error).__name__}"
        assert error.code in {"EXECUTION_UNKNOWN", "BACKEND_UNAVAILABLE"}, f"unexpected code: {error.code}"


def prepare(backend: Backend, rid: str, command: str) -> dict[str, Any]:
    req = exec_request(backend.grant, rid, command)
    claim(backend.authority, req)
    return req


def running(backend: Backend, rid: str, command: str) -> dict[str, Any]:
    """A claimed command whose budget outlives the journal lock timeout.

    The budget is set BEFORE the claim: the operation input digest covers the
    whole payload, so a later edit would not be the claimed operation.
    """
    req = exec_request(backend.grant, rid, command)
    req["payload"]["timeout_ms"] = 3000
    claim(backend.authority, req)
    return req


def complete_execution(backend: Backend, request: dict[str, Any]) -> None:
    view = request["view_ref"]
    receipt = {
        "schema_version": 1,
        "operation_id": request["payload"]["operation_id"],
        "namespace": request["namespace"],
        "workspace_id": view["workspace_id"],
        "view_id": view["view_id"],
        "owner_run_id": view["owner_run_id"],
        "generation": view["generation"],
        "revision_id": view["base_revision"],
        "original_revision_id": view["base_revision"],
        "input_tree_sha256": "c" * 64,
        "plan_sha256": None,
        "profile_id": request["payload"]["profile_id"],
        "image_digest": backend.profile.image_digest,
        "state": "EXITED",
        "exit_code": 0,
        "timed_out": False,
        "stdout_tail": "fixture result",
        "stderr_tail": "",
        "truncated": False,
        "duration_ms": 1,
        "terminal_barrier": False,
    }
    backend.authority.journal.complete(
        request["payload"]["operation_id"],
        NamespaceRef(**request["namespace"]),
        {"receipt": receipt},
        original_proof=request["capability"],
    )


def test_two_commands_share_one_cell_and_two_durable_records(backend: Backend) -> None:
    first = prepare(backend, "1" * 32, "export FA_BACKEND=kept")
    second = prepare(backend, "2" * 32, 'printf "%s" "$FA_BACKEND"')
    backend.peer.replies.extend(backend.episode_replies("op-" + "1" * 32))
    outcome = ok_backend(lambda: backend.owner().execute(PEER, first, deadline=until()))
    assert outcome.exit_code == 0 and outcome.container_id == CID
    assert outcome.terminal_barrier is False
    reused = ok_backend(lambda: backend.owner().execute(PEER, second, deadline=until()))
    assert reused.exit_code == 0 and "kept" in reused.stdout
    assert reused.container_id == CID and backend.worker.runs == 2
    paths = [seen["path"] for seen in backend.peer.seen]
    assert sum(1 for path in paths if "/containers/create" in path) == 1
    assert sum(1 for path in paths if path.endswith("/start")) == 1
    assert sum(1 for path in paths if "/attach" in path) == 1
    first_record = backend.authority.journal.lookup("op-" + "1" * 32, ACTOR)
    second_record = backend.authority.journal.lookup("op-" + "2" * 32, ACTOR)
    assert first_record is not None and second_record is not None
    assert first_record["container_id"] == CID and second_record["container_id"] == CID
    assert second_record["view_ref"] == first_record["view_ref"]


def test_noninteractive_commands_use_null_sessions_and_fresh_one_shot_cells(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = replace(native_profile(), profile_id="verification", interactive=False)
    case = Backend(site, tmp_path, profile_override=profile)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    peer = Endpoint(private / "engine.sock")
    case.peer = peer
    case.engine = ObservedEngine(peer.path, daemon_uid=os.getuid(), api_version="1.45", rpc_timeout_ms=1000)
    case.backend = CellBackend(case.authority, case.engine, case.authority.journal)
    streams: list[FakeWorkerStream] = []

    def attach(container_id: str, *, deadline: float) -> FakeWorkerStream:
        stream = FakeWorkerStream()
        streams.append(stream)
        return stream

    monkeypatch.setattr(case.engine, "attach", attach)
    try:
        for rid in ("2" * 32, "3" * 32):
            request = exec_request(case.grant, rid, "printf noninteractive")
            request["payload"].update(profile_id=profile.profile_id, session_id=None)
            claim(case.authority, request)
            peer.replies.extend(
                [
                    Reply(201, {"Id": CID, "Warnings": []}),
                    Reply(204),
                    Reply(200, observation(request["payload"]["operation_id"], case.view.view_id)),
                ]
            )
            execute: Callable[[], CommandOutcome] = partial(case.owner().execute, PEER, request, deadline=until())
            outcome = ok_backend(execute)
            assert outcome.exit_code == 0 and outcome.session_id is None and outcome.terminal_barrier is False
        assert case.owner().episode_count() == 0
        assert len(streams) == 2 and all(stream.closed for stream in streams)
        for stream in streams:
            assert len(stream.requests) == 1
            sent = stream.requests[0]
            assert sent["action"] == "RUN"
            assert sent["payload"] == {
                "command": "printf noninteractive",
                "cwd": ".",
                "timeout_ms": 500,
                "session_id": None,
            }
        paths = [seen["path"] for seen in peer.seen]
        assert sum("/containers/create" in path for path in paths) == 2
        assert sum(path.endswith("/start") for path in paths) == 2
    finally:
        case.close()
        peer.close()


def test_duplicate_operation_id_is_denied_without_a_second_send(backend: Backend) -> None:
    request = prepare(backend, "3" * 32, "printf once")
    backend.peer.replies.extend(backend.episode_replies("op-" + "3" * 32))
    assert ok_backend(lambda: backend.owner().execute(PEER, request, deadline=until())).exit_code == 0
    denied("EXECUTION_UNKNOWN", lambda: backend.owner().execute(PEER, request, deadline=until()))
    assert backend.worker.runs == 1


def test_cancel_before_send_produces_no_run_frame(backend: Backend) -> None:
    request = prepare(backend, "4" * 32, "printf cancelled")
    backend.authority.journal.request_cancel("op-" + "4" * 32, ACTOR, view=backend.view)
    denied("EXECUTION_UNKNOWN", lambda: backend.owner().execute(PEER, request, deadline=until()))
    assert backend.worker.runs == 0


def test_unusable_reply_is_unknown_with_exactly_one_frame(backend: Backend) -> None:
    request = prepare(backend, "5" * 32, "printf lost")
    backend.worker.broken = True
    backend.peer.replies.extend(backend.episode_replies("op-" + "5" * 32))
    denied("EXECUTION_UNKNOWN", lambda: backend.owner().execute(PEER, request, deadline=until()))
    assert backend.worker.runs == 1


def test_cancel_during_a_running_command_persists_intent_and_never_replays(backend: Backend) -> None:
    request = running(backend, "6" * 32, "sleep 2")
    backend.peer.replies.extend(backend.episode_replies("op-" + "6" * 32))
    started = threading.Event()
    failure: list[Exception] = []

    worker = backend.worker
    original = worker.handle

    def counted(raw: bytes) -> dict[str, Any]:
        started.set()  # The cell is busy from here until the command returns.
        return original(raw)

    worker.handle = counted  # type: ignore[method-assign]
    thread = command_thread(backend, request, failure)
    try:
        assert started.wait(3), "the command never reached the cell worker"
        cancel = {
            "protocol_version": 1,
            "request_id": "7" * 32,
            "op": "cancel",
            "namespace": ACTOR.to_dict(),
            "view_ref": backend.view.to_dict(),
            "capability": backend.grant.capability,
            "payload": {"operation_id": "op-" + "6" * 32},
        }
        backend.peer.replies.extend(
            [
                Reply(200, observation("op-" + "6" * 32, backend.view.view_id)),
                Reply(204),
                Reply(200, observation("op-" + "6" * 32, backend.view.view_id, status="exited")),
            ]
        )
        stopped = ok_backend(lambda: backend.owner().cancel(PEER, cancel, deadline=until()))
        assert stopped["container_id"] == CID
        assert any(seen["path"].endswith("/kill?signal=SIGKILL") for seen in backend.peer.seen)
        record = backend.authority.journal.lookup("op-" + "6" * 32, ACTOR)
        assert record is not None and record["cancel_requested"] is True
    finally:
        thread.join(5)
    assert worker.runs == 1
    assert_cancelled_command_outcome(failure)


def test_second_view_gets_its_own_cell_and_never_reuses_the_first_shell(backend: Backend) -> None:
    first = prepare(backend, "e" * 32, "export FA_FIRST=one")
    backend.peer.replies.extend(backend.episode_replies("op-" + "e" * 32))
    assert ok_backend(lambda: backend.owner().execute(PEER, first, deadline=until())).exit_code == 0
    second_view = ok(
        lambda: backend.authority.pin_reader(
            PEER,
            ACTOR,
            workspace_id=backend.view.workspace_id,
            revision_id=backend.view.base_revision,
            plan_ref=None,
            formal_evidence=False,
            deadline=until(),
        )
    )
    second = exec_request(second_view, "f" * 32, "printf second")
    claim(backend.authority, second)
    assert second_view.view_ref is not None
    backend.peer.replies.extend(backend.episode_replies("op-" + "f" * 32, second_view.view_ref.view_id))
    assert ok_backend(lambda: backend.owner().execute(PEER, second, deadline=until())).exit_code == 0
    paths = [seen["path"] for seen in backend.peer.seen]
    assert sum(1 for path in paths if "/containers/create" in path) == 2
    assert sum(1 for path in paths if "/attach" in path) == 2


def test_cancel_cannot_name_an_operation_from_another_view_in_same_namespace(backend: Backend) -> None:
    first = prepare(backend, "a3" * 16, "export FA_VIEW=A")
    backend.peer.replies.extend(backend.episode_replies(first["payload"]["operation_id"]))
    ok_backend(lambda: backend.owner().execute(PEER, first, deadline=until()))

    second_view = ok(
        lambda: backend.authority.pin_reader(
            PEER,
            ACTOR,
            workspace_id=backend.view.workspace_id,
            revision_id=backend.view.base_revision,
            plan_ref=None,
            formal_evidence=False,
            deadline=until(),
        )
    )
    assert second_view.view_ref is not None
    second = exec_request(second_view, "a4" * 16, "export FA_VIEW=B")
    claim(backend.authority, second)
    backend.peer.replies.extend(
        backend.episode_replies(second["payload"]["operation_id"], second_view.view_ref.view_id)
    )
    ok_backend(lambda: backend.owner().execute(PEER, second, deadline=until()))
    before = backend.authority.journal.lookup(second["payload"]["operation_id"], ACTOR)
    assert before is not None and before["cancel_requested"] is False
    seen_before = len(backend.peer.seen)
    cancel = {
        "protocol_version": 1,
        "request_id": "a5" * 16,
        "op": "cancel",
        "namespace": ACTOR.to_dict(),
        "view_ref": backend.view.to_dict(),
        "capability": backend.grant.capability,
        "payload": {"operation_id": second["payload"]["operation_id"]},
    }
    denied("UNAUTHORIZED", lambda: backend.owner().cancel(PEER, cancel, deadline=until()))
    after = backend.authority.journal.lookup(second["payload"]["operation_id"], ACTOR)
    assert after == before and len(backend.peer.seen) == seen_before


def test_cancel_of_a_later_command_cancels_that_command_not_the_creation(backend: Backend) -> None:
    first = prepare(backend, "4a" * 16, "export FA_SIDE=one")
    backend.peer.replies.extend(backend.episode_replies("op-" + "4a" * 16))
    assert ok_backend(lambda: backend.owner().execute(PEER, first, deadline=until())).exit_code == 0
    second = running(backend, "4b" * 16, "sleep 2")
    started = threading.Event()
    worker = backend.worker
    original = worker.handle

    def counted(raw: bytes) -> dict[str, Any]:
        started.set()  # The cell is busy from here until the command returns.
        return original(raw)

    worker.handle = counted  # type: ignore[method-assign]
    failures: list[Exception] = []
    thread = command_thread(backend, second, failures)
    try:
        assert started.wait(3), "the second command never reached the cell worker"
        cancel = {
            "protocol_version": 1,
            "request_id": "4c" * 16,
            "op": "cancel",
            "namespace": ACTOR.to_dict(),
            "view_ref": backend.view.to_dict(),
            "capability": backend.grant.capability,
            "payload": {"operation_id": "op-" + "4b" * 16},
        }
        backend.peer.replies.extend(
            [
                Reply(200, observation("op-" + "4a" * 16, backend.view.view_id)),
                Reply(204),
                Reply(200, observation("op-" + "4a" * 16, backend.view.view_id, status="exited")),
            ]
        )
        ok_backend(lambda: backend.owner().cancel(PEER, cancel, deadline=until()))
        second_record = backend.authority.journal.lookup("op-" + "4b" * 16, ACTOR)
        assert second_record is not None and second_record["cancel_requested"] is True
    finally:
        thread.join(5)
    assert_cancelled_command_outcome(failures)


def test_reconcile_stops_a_surviving_owned_cell_without_creating_another(backend: Backend) -> None:
    request = prepare(backend, "8" * 32, "printf reconcile")
    backend.peer.replies.extend(backend.episode_replies("op-" + "8" * 32))
    ok_backend(lambda: backend.owner().execute(PEER, request, deadline=until()))
    backend.peer.replies.extend(
        [
            Reply(200, observation("op-" + "8" * 32, backend.view.view_id)),
            Reply(204),
            Reply(200, observation("op-" + "8" * 32, backend.view.view_id, status="exited")),
        ]
    )
    results = ok_backend(lambda: backend.owner().reconcile(deadline=until()))
    assert results and results[0]["status"] in {"running", "exited", "dead"}
    paths = [seen["path"] for seen in backend.peer.seen]
    assert sum(1 for path in paths if "/containers/create" in path) == 1
    assert any(path.endswith("/kill?signal=SIGKILL") for path in paths)


def test_reconcile_inspects_done_owned_cell_after_backend_restart(backend: Backend) -> None:
    request = prepare(backend, "8a" * 16, "printf completed-but-cell-survives")
    backend.peer.replies.extend(backend.episode_replies(request["payload"]["operation_id"]))
    ok_backend(lambda: backend.owner().execute(PEER, request, deadline=until()))
    complete_execution(backend, request)
    record = backend.authority.journal.lookup(request["payload"]["operation_id"], ACTOR)
    assert record is not None and record["state"] == "DONE" and record["container_id"] == CID

    backend.owner().close(deadline=until())
    engine = backend.engine
    assert engine is not None
    backend.backend = CellBackend(backend.authority, engine, backend.authority.journal)
    backend.peer.replies.extend(
        [
            Reply(200, observation(request["payload"]["operation_id"], backend.view.view_id)),
            Reply(204),
            Reply(200, observation(request["payload"]["operation_id"], backend.view.view_id, status="exited")),
        ]
    )
    results = ok_backend(lambda: backend.owner().reconcile(deadline=until()))
    assert results == [{"operation_id": request["payload"]["operation_id"], "status": "exited"}]
    paths = [seen["path"] for seen in backend.peer.seen]
    assert not any("/containers/create" in path or path.endswith("/start") or "/attach" in path for path in paths[4:])
    assert any(path.endswith("/kill?signal=SIGKILL") for path in paths)
    assert backend.authority.journal.lookup(request["payload"]["operation_id"], ACTOR) == record


def test_episode_lookup_is_bound_to_principal_namespace_and_view(backend: Backend) -> None:
    request = prepare(backend, "1a" * 16, "export FA_BIND=one")
    backend.peer.replies.extend(backend.episode_replies("op-" + "1a" * 16))
    assert ok_backend(lambda: backend.owner().execute(PEER, request, deadline=until())).exit_code == 0
    owner = backend.owner()
    assert owner.episode_container(PEER, ACTOR, backend.view) == CID
    assert owner.episode_container(replace(PEER, gid=PEER.gid + 1), ACTOR, backend.view) is None
    assert owner.episode_container(PEER, OTHER, backend.view) is None
    same_session = NamespaceRef(ACTOR.session_id, "run-other")
    assert owner.episode_container(PEER, same_session, backend.view) is None
    other_view = replace(backend.view, view_id="view-" + "9" * 32)
    assert owner.episode_container(PEER, ACTOR, other_view) is None


def test_foreign_namespace_cannot_reuse_the_episode_shell(backend: Backend) -> None:
    request = prepare(backend, "9" * 32, "export FA_OWNER=mine")
    backend.peer.replies.extend(backend.episode_replies("op-" + "9" * 32))
    assert ok_backend(lambda: backend.owner().execute(PEER, request, deadline=until())).exit_code == 0
    other = exec_request(backend.grant, "a" * 32, "printf other")
    other["namespace"] = OTHER.to_dict()
    backend.authority.journal.reserve(other)
    backend.authority.journal.begin("op-" + "a" * 32, OTHER)
    denied("UNAUTHORIZED", lambda: backend.owner().execute(PEER, other, deadline=until()))
    assert backend.worker.runs == 1


def test_forged_capability_never_obtains_an_episode(backend: Backend) -> None:
    request = prepare(backend, "b" * 32, "printf forged")
    request["capability"] = "f" * 64
    denied("UNAUTHORIZED", lambda: backend.owner().execute(PEER, request, deadline=until()))
    assert backend.worker.runs == 0
    assert backend.owner().episode_count() == 0


def test_unapproved_profile_does_not_reach_docker(backend: Backend) -> None:
    request = prepare(backend, "c" * 32, "printf profile")
    request["payload"]["profile_id"] = "other-profile"
    denied("UNAPPROVED_PROFILE", lambda: backend.owner().execute(PEER, request, deadline=until()))
    assert not backend.peer.seen


def test_expired_budget_never_starts_a_cell(backend: Backend) -> None:
    request = prepare(backend, "d" * 32, "printf expired")
    denied("BACKEND_UNAVAILABLE", lambda: backend.owner().execute(PEER, request, deadline=time.monotonic() - 1))
    assert not backend.peer.seen
    assert backend.worker.runs == 0


def test_episode_creation_lock_uses_the_absolute_request_deadline(backend: Backend) -> None:
    request = prepare(backend, "d4" * 16, "printf lock-timeout")
    owner = backend.owner()
    namespace = NamespaceRef(**request["namespace"])
    view = owner._view_of(request["view_ref"])
    key = _EpisodeKey.build(PEER, namespace, view, backend.profile.profile_id)
    attempted, lock = threading.Event(), threading.Lock()
    assert lock.acquire(blocking=False)

    class ContendedLock:
        timeout: float | None = None
        attempted_at: float | None = None
        acquired = False

        def acquire(self, *, timeout: float) -> bool:
            self.timeout = timeout
            self.attempted_at = time.monotonic()
            attempted.set()
            self.acquired = lock.acquire(timeout=timeout)
            return self.acquired

        def release(self) -> None:
            if not self.acquired:
                raise AssertionError("a lock that was not acquired must not be released")
            lock.release()

    contended = ContendedLock()
    owner._creations[key] = contended  # type: ignore[assignment]
    started_at = time.monotonic()
    deadline = started_at + 1
    failures: list[Exception] = []
    finished = threading.Event()
    finished_at: list[float] = []

    def execute() -> None:
        try:
            owner.execute(PEER, request, deadline=deadline)
        except DOMAIN_ERRORS as error:
            failures.append(error)
        finally:
            finished_at.append(time.monotonic())
            finished.set()

    thread = threading.Thread(target=execute)
    thread.start()
    try:
        assert attempted.wait(3), "request never reached the contended episode lock"
        thread.join(3)
        assert not thread.is_alive() and finished.is_set()
        assert len(failures) == 1 and isinstance(failures[0], SupervisorError)
        assert failures[0].code == "BACKEND_UNAVAILABLE"
        assert contended.timeout is not None and contended.attempted_at is not None
        assert finished_at[0] >= contended.attempted_at + contended.timeout - 0.05
        assert backend.peer.seen == [] and backend.worker.runs == 0
    finally:
        lock.release()
        thread.join(3)


def test_close_admission_that_wins_before_effect_prevents_create_start_attach_and_run(
    backend: Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = prepare(backend, "d2" * 16, "printf closed")
    entered, resume = threading.Event(), threading.Event()
    failures: list[Exception] = []
    owner = backend.owner()
    original = owner._live_episode

    def pause_before_effect(scope: Any, req: dict[str, Any], key: Any, *, deadline: float) -> Any:
        entered.set()
        assert resume.wait(5), "the deterministic admission race was not released"
        return original(scope, req, key, deadline=deadline)

    monkeypatch.setattr(owner, "_live_episode", pause_before_effect)
    thread = command_thread(backend, request, failures)
    try:
        assert entered.wait(3), "the request never reached the pre-effect pause"
        close(backend.authority, backend.grant)
        resume.set()
        thread.join(5)
    finally:
        resume.set()
        thread.join(5)
    assert not thread.is_alive()
    assert len(failures) == 1 and isinstance(failures[0], SupervisorError)
    assert failures[0].code == "VIEW_CLOSED"
    assert backend.peer.seen == [] and backend.worker.runs == 0


def test_effect_that_wins_blocks_close_until_create_attach_finish_then_drain_completes(
    backend: Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = prepare(backend, "d3" * 16, "printf closed-after-create")
    backend.peer.replies.extend(backend.episode_replies(request["payload"]["operation_id"]))
    entered, resume, effect_finished, closed = (threading.Event() for _ in range(4))
    failures: list[Exception] = []
    owner = backend.owner()
    original_launch = owner._cells.launch_new
    original_live = owner._live_episode

    def pause_launch(*args: Any, **kwargs: Any) -> str:
        entered.set()
        assert resume.wait(5), "the deterministic effect race was not released"
        return original_launch(*args, **kwargs)

    def wait_after_effect(scope: Any, req: dict[str, Any], key: Any, *, deadline: float) -> Any:
        episode = original_live(scope, req, key, deadline=deadline)
        effect_finished.set()
        assert closed.wait(5), "close did not follow the completed admitted effect"
        return episode

    def close_thread() -> None:
        close(backend.authority, backend.grant)
        closed.set()

    monkeypatch.setattr(owner._cells, "launch_new", pause_launch)
    monkeypatch.setattr(owner, "_live_episode", wait_after_effect)
    thread = command_thread(backend, request, failures)
    closer: threading.Thread | None = None
    try:
        assert entered.wait(3), "the create effect was not reached"
        closer = threading.Thread(target=close_thread)
        closer.start()
        assert not closed.wait(0.1), "close passed an effect that already owned the authority gate"
        resume.set()
        assert effect_finished.wait(5), "create/start/attach did not finish under the effect guard"
        assert closed.wait(5), "close did not finish after the effect guard retired"
        thread.join(5)
    finally:
        resume.set()
        thread.join(5)
        if closer is not None:
            closer.join(5)
    assert not thread.is_alive() and (closer is None or not closer.is_alive())
    assert len(failures) == 1 and isinstance(failures[0], SupervisorError)
    assert failures[0].code == "VIEW_CLOSED"
    paths = [seen["path"] for seen in backend.peer.seen]
    assert any("/containers/create" in path for path in paths)
    assert any(path.endswith("/start") for path in paths)
    assert any("/attach" in path for path in paths)
    assert backend.worker.runs == 0
    ok(
        lambda: backend.authority.drain(
            PEER, ACTOR, view_ref=backend.view, capability=backend.grant.capability, deadline=until()
        )
    )


def test_created_cell_binds_only_the_authority_trusted_paths(backend: Backend) -> None:
    request = prepare(backend, "a1" * 16, "printf bound")
    backend.peer.replies.extend(backend.episode_replies("op-" + "a1" * 16))
    ok_backend(lambda: backend.owner().execute(PEER, request, deadline=until()))
    creates = [seen for seen in backend.peer.seen if "/containers/create" in seen["path"]]
    assert len(creates) == 1
    body = creates[0]["body"]
    assert isinstance(body, dict)
    assert body["Labels"] == {
        "fa.execution.operation_id": "op-" + "a1" * 16,
        "fa.execution.view_id": backend.view.view_id,
    }
    # Independent oracle: the authority's own layout, not its accessor.
    view_root = backend.authority._state / "workspaces" / backend.view.workspace_id / "views" / backend.view.view_id
    mounts = {mount["Target"]: mount["Source"] for mount in body["HostConfig"]["Mounts"]}
    assert mounts == {
        "/workspace": str(view_root / "source"),
        "/scratch": str(view_root / "scratch"),
        "/opt/toolchain-cache": str(backend.cache),
    }
    assert body["HostConfig"]["Mounts"][0]["ReadOnly"] is False


def test_cancel_persists_the_exact_intent_before_the_cell_is_stopped(backend: Backend) -> None:
    # The creation command owns the cell; a LATER command is the one cancelled,
    # so the durable intent under test is not the creation's own cancel intent.
    creation = prepare(backend, "b1" * 16, "export FA_ORDER=one")
    backend.peer.replies.extend(backend.episode_replies("op-" + "b1" * 16))
    ok_backend(lambda: backend.owner().execute(PEER, creation, deadline=until()))
    request = running(backend, "b2" * 16, "sleep 2")
    started = threading.Event()
    worker = backend.worker
    original = worker.handle

    def counted(raw: bytes) -> dict[str, Any]:
        started.set()  # The cell is busy from here until the command returns.
        return original(raw)

    worker.handle = counted  # type: ignore[method-assign]
    failures: list[Exception] = []
    thread = command_thread(backend, request, failures)
    observed: list[tuple[str, bool]] = []

    def watch(path: str) -> None:
        record = backend.authority.journal.lookup("op-" + "b2" * 16, ACTOR)
        observed.append((path, bool(record and record["cancel_requested"])))

    try:
        assert started.wait(3), "the command never reached the cell worker"
        backend.observe(watch)
        cancel = {
            "protocol_version": 1,
            "request_id": "b3" * 16,
            "op": "cancel",
            "namespace": ACTOR.to_dict(),
            "view_ref": backend.view.to_dict(),
            "capability": backend.grant.capability,
            "payload": {"operation_id": "op-" + "b2" * 16},
        }
        backend.peer.replies.extend(
            [
                Reply(200, observation("op-" + "b1" * 16, backend.view.view_id)),
                Reply(204),
                Reply(200, observation("op-" + "b1" * 16, backend.view.view_id, status="exited")),
            ]
        )
        ok_backend(lambda: backend.owner().cancel(PEER, cancel, deadline=until()))
    finally:
        backend.observe(lambda path: None)
        thread.join(5)
    kills = [entry for entry in observed if "/kill?signal=SIGKILL" in entry[0]]
    assert kills, "the owned cell was never stopped"
    assert all(intent for _, intent in kills), f"cancel intent was not durable before the stop: {observed}"
    assert_cancelled_command_outcome(failures)


def test_cancel_refuses_a_cell_that_is_not_the_owned_one(backend: Backend) -> None:
    request = running(backend, "c1" * 16, "sleep 2")
    backend.peer.replies.extend(backend.episode_replies("op-" + "c1" * 16))
    started = threading.Event()
    worker = backend.worker
    original = worker.handle

    def counted(raw: bytes) -> dict[str, Any]:
        started.set()  # The cell is busy from here until the command returns.
        return original(raw)

    worker.handle = counted  # type: ignore[method-assign]
    failures: list[Exception] = []
    thread = command_thread(backend, request, failures)
    try:
        assert started.wait(3), "the command never reached the cell worker"
        cancel = {
            "protocol_version": 1,
            "request_id": "c2" * 16,
            "op": "cancel",
            "namespace": ACTOR.to_dict(),
            "view_ref": backend.view.to_dict(),
            "capability": backend.grant.capability,
            "payload": {"operation_id": "op-" + "c1" * 16},
        }
        foreign = observation("op-" + "c1" * 16, backend.view.view_id)
        foreign["Name"] = "/fa-job-" + "f" * 32
        backend.peer.replies.extend([Reply(200, foreign)])
        denied("PATH_DENIED", lambda: backend.owner().cancel(PEER, cancel, deadline=until()))
        labelled = observation("op-" + "f" * 32, backend.view.view_id)
        labelled["Name"] = "/fa-job-" + "c1" * 16
        backend.peer.replies.extend([Reply(200, labelled)])
        denied("PATH_DENIED", lambda: backend.owner().cancel(PEER, cancel, deadline=until()))
        assert not any(seen["path"].endswith("/kill?signal=SIGKILL") for seen in backend.peer.seen)
    finally:
        thread.join(5)
    assert_cancelled_command_outcome(failures)


def test_completed_command_leaves_no_admitted_work_behind(backend: Backend) -> None:
    request = prepare(backend, "e1" * 16, "printf done")
    backend.peer.replies.extend(backend.episode_replies("op-" + "e1" * 16))
    ok_backend(lambda: backend.owner().execute(PEER, request, deadline=until()))
    close(backend.authority, backend.grant)
    ok(
        lambda: backend.authority.drain(
            PEER, ACTOR, view_ref=backend.view, capability=backend.grant.capability, deadline=until()
        )
    )


def test_drain_waits_for_a_running_command_and_returns_when_it_retires(backend: Backend) -> None:
    request = running(backend, "f1" * 16, "sleep 2")
    backend.peer.replies.extend(backend.episode_replies("op-" + "f1" * 16))
    started = threading.Event()
    worker = backend.worker
    original = worker.handle

    def counted(raw: bytes) -> dict[str, Any]:
        started.set()  # The cell is busy from here until the command returns.
        return original(raw)

    worker.handle = counted  # type: ignore[method-assign]
    failures: list[Exception] = []
    thread = command_thread(backend, request, failures)
    drained = threading.Event()

    def drain() -> None:
        try:
            ok(
                lambda: backend.authority.drain(
                    PEER, ACTOR, view_ref=backend.view, capability=backend.grant.capability, deadline=until()
                )
            )
        except DOMAIN_ERRORS as error:  # Recorded for the oracle; never swallowed.
            failures.append(error)
        finally:
            drained.set()

    drainer = threading.Thread(target=drain)
    drainer_started = False
    try:
        assert started.wait(3), "the command never reached the cell worker"
        close(backend.authority, backend.grant)
        drainer.start()
        drainer_started = True
        assert not drained.wait(0.5), "the drain returned while a command was still running"
        thread.join(15)
        assert drained.wait(15), "the drain never returned after the command finished"
    finally:
        thread.join(15)
        if drainer_started:
            drainer.join(15)
    assert not failures, f"unexpected failure: {failures!r}"


def test_failing_command_reports_its_own_exit_code(backend: Backend) -> None:
    request = prepare(backend, "d1" * 16, "exit 3")
    backend.peer.replies.extend(backend.episode_replies("op-" + "d1" * 16))
    outcome = ok_backend(lambda: backend.owner().execute(PEER, request, deadline=until()))
    assert outcome.exit_code == 3
    assert outcome.terminal_barrier is False
    assert outcome.container_id == CID
    assert outcome.session_id == "main"


# ---------------------------------------------------------------------------
# G2-G6: one-shot cancellation ownership (SLICE1 STEP2, spec §2.2 / E262).
# A noninteractive cell is created for ONE operation and is never in the
# persistent episode map, so its cancel must resolve the durable journal CID.
# ---------------------------------------------------------------------------

NONINTERACTIVE = replace(native_profile(), profile_id="verification", interactive=False)


class InFlightWorkerStream:
    """A one-shot attach whose RUN stays in flight until the test releases it.

    It is not a worker: it makes the cancel window observable and deterministic,
    so "cancel while the command runs" is a real state, not a race.
    """

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.received = threading.Event()
        self.release = threading.Event()
        self.closed = False

    def write_frame(self, raw: bytes, *, deadline: float) -> None:
        if time.monotonic() >= deadline:
            raise OSError("fake_worker_deadline")
        self.requests.append(decode_cell_request(raw))
        self.received.set()

    def read_frame(self, *, deadline: float) -> bytes:
        if not self.release.wait(max(0.0, deadline - time.monotonic())):
            raise OSError("fake_worker_deadline")
        raise OSError("fake_worker_closed")  # A stopped cell never answers.

    def close(self) -> None:
        self.closed = True
        self.release.set()


@dataclass
class OneShot:
    """A noninteractive backend over the SAME real authority/journal/daemon peer."""

    case: Backend
    streams: list[InFlightWorkerStream]


def one_shot(site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> OneShot:
    case = Backend(site, tmp_path, profile_override=NONINTERACTIVE)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    peer = Endpoint(private / "engine.sock")
    case.peer = peer
    case.engine = ObservedEngine(peer.path, daemon_uid=os.getuid(), api_version="1.45", rpc_timeout_ms=1000)
    case.backend = CellBackend(case.authority, case.engine, case.authority.journal)
    streams: list[InFlightWorkerStream] = []

    def attach(container_id: str, *, deadline: float) -> InFlightWorkerStream:
        stream = InFlightWorkerStream()
        streams.append(stream)
        return stream

    monkeypatch.setattr(case.engine, "attach", attach)
    return OneShot(case, streams)


@pytest.fixture
def one_shot_case(site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[OneShot]:
    """A noninteractive backend that is always torn down, even on failure."""
    one = one_shot(site, tmp_path, monkeypatch)
    try:
        yield one
    finally:
        try:
            one.case.close()  # The real authority/journal/worker teardown, never a leak.
        finally:
            one.case.peer.close()


def one_shot_request(case: Backend, rid: str, command: str) -> dict[str, Any]:
    request = exec_request(case.grant, rid, command)
    request["payload"].update(profile_id=NONINTERACTIVE.profile_id, session_id=None)
    claim(case.authority, request)
    return request


def one_shot_replies(case: Backend, operation_id: str) -> list[Reply]:
    return [
        Reply(201, {"Id": CID, "Warnings": []}),
        Reply(204),
        Reply(200, observation(operation_id, case.view.view_id)),
    ]


def cancel_replies(operation_id: str, view_id: str) -> list[Reply]:
    return [
        Reply(200, observation(operation_id, view_id)),
        Reply(204),
        Reply(200, observation(operation_id, view_id, status="exited")),
    ]


def cancel_request(case: Backend, operation_id: str, *, view: Any = None, rid: str = "c" * 32) -> dict[str, Any]:
    return {
        "protocol_version": 1,
        "request_id": rid,
        "op": "cancel",
        "namespace": ACTOR.to_dict(),
        "view_ref": (case.view if view is None else view).to_dict(),
        "capability": case.grant.capability,
        "payload": {"operation_id": operation_id},
    }


def eventually(predicate: Callable[[], bool], *, timeout: float = 5.0) -> bool:
    """Poll a cross-thread condition; a fixed sleep is never the oracle."""
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def start_one_shot(
    one: OneShot, rid: str, command: str
) -> tuple[dict[str, Any], str, list[Exception], threading.Thread]:
    """Claim and launch one noninteractive command; return its in-flight state."""
    operation_id = "op-" + rid
    request = one_shot_request(one.case, rid, command)
    one.case.peer.replies.extend(one_shot_replies(one.case, operation_id))
    failures: list[Exception] = []
    thread = command_thread(one.case, request, failures)
    return request, operation_id, failures, thread


def test_running_one_shot_cancel_stops_the_journal_bound_cid(one_shot_case: OneShot) -> None:
    """G2 / C3: a running one-shot is stopped by its own durable CID.

    kill-check: removing the noninteractive branch of CellBackend.cancel (or the
    journal-derived CID) leaves this cancel at EXECUTION_UNKNOWN.
    """
    one = one_shot_case
    _, operation_id, failures, thread = start_one_shot(one, "a" * 32, "sleep 5")
    try:
        assert eventually(lambda: bool(one.streams) and one.streams[0].received.is_set()), (
            f"the RUN never reached the one-shot cell: {failures}"
        )
        one.case.peer.replies.extend(cancel_replies(operation_id, one.case.view.view_id))
        cancelled = ok_backend(
            lambda: one.case.owner().cancel(PEER, cancel_request(one.case, operation_id), deadline=until())
        )
        assert cancelled == {"container_id": CID, "status": "exited"}
        paths = [seen["path"] for seen in one.case.peer.seen]
        assert sum(1 for path in paths if "/containers/create" in path) == 1
        assert sum(1 for path in paths if path.endswith("/start")) == 1
        assert sum(1 for path in paths if path.endswith("/kill?signal=SIGKILL")) == 1
        record = one.case.authority.journal.lookup(operation_id, ACTOR)
        assert record is not None and record["cancel_requested"] is True
        assert len(one.streams) == 1
        assert len(one.streams[0].requests) == 1, "a cancelled command must never be re-sent"
    finally:
        for stream in one.streams:
            stream.release.set()
        thread.join(5)
    assert len(failures) == 1, f"the command must end in exactly one closed outcome: {failures}"
    assert_cancelled_command_outcome(failures)


def test_one_shot_cancel_from_another_view_is_unauthorized_without_effect(one_shot_case: OneShot) -> None:
    """G3 / C3: the exact ViewRef gate runs BEFORE any intent write or daemon stop."""
    one = one_shot_case
    _, operation_id, failures, thread = start_one_shot(one, "b" * 32, "sleep 5")
    try:
        assert eventually(lambda: bool(one.streams) and one.streams[0].received.is_set()), (
            f"the RUN never reached the one-shot cell: {failures}"
        )
        other = ok(
            lambda: one.case.authority.pin_reader(
                PEER,
                ACTOR,
                workspace_id=one.case.view.workspace_id,
                revision_id=one.case.view.base_revision,
                plan_ref=None,
                formal_evidence=False,
                deadline=until(),
            )
        )
        assert other.view_ref is not None
        before = one.case.authority.journal.lookup(operation_id, ACTOR)
        seen_before = len(one.case.peer.seen)
        denied(
            "UNAUTHORIZED",
            lambda: one.case.owner().cancel(
                PEER, cancel_request(one.case, operation_id, view=other.view_ref), deadline=until()
            ),
        )
        after = one.case.authority.journal.lookup(operation_id, ACTOR)
        assert after == before and before is not None and before["cancel_requested"] is False
        assert len(one.case.peer.seen) == seen_before, "a foreign-view cancel must reach no daemon"
    finally:
        for stream in one.streams:
            stream.release.set()
        thread.join(5)
    assert_cancelled_command_outcome(failures)


def test_one_shot_cancel_of_an_unknown_operation_touches_no_cell(one_shot_case: OneShot) -> None:
    """G4 / C0-C3: an unknown operation is refused without any daemon contact."""
    one = one_shot_case
    seen_before = len(one.case.peer.seen)
    denied(
        "EXECUTION_UNKNOWN",
        lambda: one.case.owner().cancel(PEER, cancel_request(one.case, "op-" + "d" * 32), deadline=until()),
    )
    assert len(one.case.peer.seen) == seen_before
    assert one.case.authority.journal.lookup("op-" + "d" * 32, ACTOR) is None


def test_one_shot_cancel_before_creation_persists_intent_and_blocks_the_cell(one_shot_case: OneShot) -> None:
    """G5 / C3: with no CID the durable intent is the outcome, and no cell appears.

    kill-check: returning a fake "exited"/stopped observation (or skipping the
    intent write) breaks the guarantee that create/start can never follow.
    """
    one = one_shot_case
    operation_id = "op-" + "e" * 32
    request = one_shot_request(one.case, "e" * 32, "sleep 5")
    cancelled = ok_backend(
        lambda: one.case.owner().cancel(PEER, cancel_request(one.case, operation_id), deadline=until())
    )
    assert cancelled == {"container_id": None, "status": "not_created"}
    record = one.case.authority.journal.lookup(operation_id, ACTOR)
    assert record is not None and record["cancel_requested"] is True and record["container_id"] is None
    seen_before = len(one.case.peer.seen)
    denied("EXECUTION_UNKNOWN", lambda: one.case.owner().execute(PEER, request, deadline=until()))
    assert len(one.case.peer.seen) == seen_before, "a cancelled operation must never create or start a cell"
    assert one.streams == []


def test_one_shot_cancel_does_not_depend_on_the_interactive_episode_map(one_shot_case: OneShot) -> None:
    """G6 / C3: a restart-fresh backend (no episodes) still stops the live cell."""
    one = one_shot_case
    _, operation_id, failures, thread = start_one_shot(one, "f" * 32, "sleep 5")
    try:
        assert eventually(lambda: bool(one.streams) and one.streams[0].received.is_set()), (
            f"the RUN never reached the one-shot cell: {failures}"
        )
        engine = one.case.engine
        assert engine is not None
        restarted = CellBackend(one.case.authority, engine, one.case.authority.journal)
        assert restarted.episode_count() == 0
        one.case.peer.replies.extend(cancel_replies(operation_id, one.case.view.view_id))
        cancelled = ok_backend(lambda: restarted.cancel(PEER, cancel_request(one.case, operation_id), deadline=until()))
        assert cancelled == {"container_id": CID, "status": "exited"}
        assert any(seen["path"].endswith("/kill?signal=SIGKILL") for seen in one.case.peer.seen)
    finally:
        for stream in one.streams:
            stream.release.set()
        thread.join(5)
    assert_cancelled_command_outcome(failures)
