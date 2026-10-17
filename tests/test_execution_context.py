"""C0/C3 real UDS/journal seam, explicit fixture callbacks and simulated results.

NOT WorkspaceAuthority/CellBackend composition, Docker, kernel or live acceptance.
"""

from __future__ import annotations

import copy
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from fa.execution.journal import OperationJournal
from fa.execution.plans import ProtectedPlanContext
from fa.execution.protocol import DeadlineConnection, decode_reply, decode_request, encode_json, read_frame, write_frame
from fa.execution.supervisor import CompletedReplyCache, PeerIdentity, SupervisorDispatcher
from fa.execution.types import GRANT_OPERATIONS, Access, GrantReply, NamespaceRef, Operation, ViewPurpose, ViewRef
from tests.test_execution_dispatch import profile
from tests.test_execution_protocol import RESULTS, RID, request


class Probe:
    """Records invocation facts; never claims to be a production authority."""

    def __init__(self, tmp_path: Path, clock: list[float]) -> None:
        self.clock = clock
        self.context = ProtectedPlanContext(tmp_path, None, False)
        self.auth: list[tuple[PeerIdentity, float]] = []
        self.handled: list[tuple[PeerIdentity, float]] = []
        self.expire_in_auth = False
        self.journal = OperationJournal(tmp_path / "operations", lock_timeout_ms=1000)
        self.service = SupervisorDispatcher(
            client_uids=frozenset({os.getuid()}),
            rpc_timeout_ms=2000,
            profiles=(profile(),),
            journal=self.journal,
            replies=CompletedReplyCache(max_entries=32),
            authorize=self.authorize,
            handle=self.handle,
        )

    def authorize(self, peer: PeerIdentity, req: dict[str, Any], *, deadline: float) -> ProtectedPlanContext | None:
        self.auth.append((peer, deadline))
        self.clock[0] += 0.25
        if self.expire_in_auth:
            self.clock[0] = deadline + 0.01
        return self.context if req["op"] in {"exec", "pin_reader", "create_view"} else None

    def handle(self, peer: PeerIdentity, req: dict[str, Any], *, deadline: float) -> GrantReply | dict[str, Any]:
        self.handled.append((peer, deadline))
        op = Operation(req["op"])
        value = copy.deepcopy(RESULTS[op])
        if op is Operation.EXEC:
            self.journal.record_container("op-" + req["request_id"], NamespaceRef(**req["namespace"]), "a" * 64)
            value["receipt"].update(plan_sha256=None, profile_id="interactive", image_digest=profile().image_digest)
        if op not in GRANT_OPERATIONS:
            return value
        raw_view = value["view_ref"]
        view = None
        if raw_view is not None:
            view = ViewRef(
                workspace_id=raw_view["workspace_id"],
                view_id=raw_view["view_id"],
                base_revision=raw_view["base_revision"],
                owner_run_id=raw_view["owner_run_id"],
                generation=raw_view["generation"],
                access=Access(raw_view["access"]),
                purpose=ViewPurpose(raw_view["purpose"]),
            )
        return GrantReply(op, "e" * 64, view, value.get("generation"), value.get("revision_id"))

    def exchange(self, req: dict[str, Any]) -> dict[str, Any] | None:
        controller, accepted = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        with ThreadPoolExecutor(max_workers=1) as workers:
            pending = workers.submit(self.service.serve_connection, accepted)
            with controller:
                controller.settimeout(2)
                write_frame(controller, encode_json(req))
                try:
                    raw = read_frame(controller)
                except (OSError, ValueError):
                    raw = None
            pending.result(timeout=3)
        return None if raw is None else decode_reply(raw, operation=Operation(req["op"]), request_id=req["request_id"])


def execution_request(op: Operation) -> dict[str, Any]:
    req = request(op)
    if op is Operation.EXEC:
        req["payload"].update(profile_id="interactive", timeout_ms=1000, session_id="main")
    return req


def test_absolute_deadline_accessor_is_readonly_and_does_not_reset_with_elapsed_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [10.0]
    monkeypatch.setattr("fa.execution.protocol.time.monotonic", lambda: clock[0])
    left, right = socket.socketpair()
    with left, right:
        framed = DeadlineConnection(left, timeout_ms=2000)
        assert framed.started_at == 10.0 and framed.deadline == 12.0
        clock[0] = 10.5
        assert framed.deadline == 12.0 and framed.remaining() == 1.5
        framed.add_execution_budget(1000)
        assert framed.deadline == 13.0 and framed.remaining() == 2.5
        for field in ["deadline", "started_at"]:
            with pytest.raises(AttributeError):
                object.__setattr__(framed, field, 1000.0)
        clock[0] = 13.01
        with pytest.raises(TimeoutError):
            framed.remaining()
        assert framed.deadline == 13.0


@pytest.mark.parametrize("op", list(Operation))
def test_all_closed_operations_forward_kernel_peer_and_original_absolute_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, op: Operation
) -> None:
    clock = [0.0]
    monkeypatch.setattr("fa.execution.protocol.time.monotonic", lambda: clock[0])
    case = Probe(tmp_path, clock)
    req = execution_request(op)
    reply = case.exchange(req)
    assert reply is not None and reply["status"] == "OK"
    expected = (PeerIdentity(os.getpid(), os.getuid(), os.getgid()), 1.0 if op is Operation.EXEC else 2.0)
    assert case.auth == case.handled == [expected]
    assert clock[0] == 0.25  # Authorization elapsed time never becomes a fresh budget.
    readonly = op in {Operation.HEALTH, Operation.READ_FILE, Operation.INSPECT, Operation.PTY_CONTROL}
    if readonly:
        assert not (tmp_path / "operations").exists()
    else:
        record = case.journal.lookup("op-" + RID, NamespaceRef(**req["namespace"]))
        assert record is not None and record["state"] == "DONE"
        assert case.exchange(req) == reply
        assert case.auth == case.handled == [expected]  # Q75 replay invokes neither callback.


@pytest.mark.parametrize("action", ["INTERRUPT", "CLOSE"])
def test_mutating_pty_controls_forward_context_and_replay_without_new_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    clock = [0.0]
    monkeypatch.setattr("fa.execution.protocol.time.monotonic", lambda: clock[0])
    case = Probe(tmp_path, clock)
    req = request(Operation.PTY_CONTROL)
    req["payload"] = {"action": action, "session_id": "main"}
    reply = case.exchange(req)
    assert reply is not None and reply["status"] == "OK" and case.exchange(req) == reply
    assert case.auth == case.handled == [(PeerIdentity(os.getpid(), os.getuid(), os.getgid()), 2.0)]


@pytest.mark.parametrize("op", [Operation.HEALTH, Operation.RELEASE, Operation.EXEC])
@pytest.mark.parametrize("deadline", [0.0, -1.0, float("nan"), float("inf"), True])
def test_expired_or_invalid_fresh_context_never_invokes_authority_or_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, op: Operation, deadline: float
) -> None:
    clock = [0.0]
    monkeypatch.setattr("fa.execution.protocol.time.monotonic", lambda: clock[0])
    case = Probe(tmp_path, clock)
    req = decode_request(encode_json(execution_request(op)))
    reply = case.service._dispatch(PeerIdentity(os.getpid(), os.getuid(), os.getgid()), req, deadline=deadline)
    assert reply["status"] == "ERROR" and reply["error"]["code"] == "BACKEND_UNAVAILABLE"
    assert case.auth == case.handled == []
    if op is not Operation.HEALTH:
        assert case.journal.lookup("op-" + RID, NamespaceRef(**req["namespace"])) is None


@pytest.mark.parametrize("op", [Operation.HEALTH, Operation.RELEASE, Operation.EXEC])
def test_authorization_consuming_deadline_cannot_begin_or_dispatch_fresh_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, op: Operation
) -> None:
    clock = [0.0]
    monkeypatch.setattr("fa.execution.protocol.time.monotonic", lambda: clock[0])
    case = Probe(tmp_path, clock)
    case.expire_in_auth = True
    begun: list[str] = []
    original = case.journal.begin

    def begin(oid: str, namespace: NamespaceRef) -> None:
        begun.append(oid)
        original(oid, namespace)

    monkeypatch.setattr(case.journal, "begin", begin)
    reply = case.exchange(execution_request(op))
    if op is Operation.EXEC:
        assert reply is not None and reply["error"]["code"] == "EXECUTION_UNKNOWN"
    else:
        assert reply is None  # Control execution and reply share the short deadline.
    assert len(case.auth) == 1 and case.handled == [] and begun == []
    if op is not Operation.HEALTH:
        record = case.journal.lookup("op-" + RID, NamespaceRef(**request(op)["namespace"]))
        assert record is not None and record["state"] == "UNKNOWN" and record["result"] is None


@pytest.mark.parametrize("op", [Operation.RELEASE, Operation.EXEC])
def test_durable_begin_consuming_deadline_cannot_invoke_backend_or_reclaim_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, op: Operation
) -> None:
    clock = [0.0]
    monkeypatch.setattr("fa.execution.protocol.time.monotonic", lambda: clock[0])
    case = Probe(tmp_path, clock)
    original = case.journal.begin

    def begin(oid: str, namespace: NamespaceRef) -> None:
        original(oid, namespace)
        clock[0] = 4.0

    monkeypatch.setattr(case.journal, "begin", begin)
    req = execution_request(op)
    assert case.exchange(req) is None
    record = case.journal.lookup("op-" + RID, NamespaceRef(**req["namespace"]))
    assert record is not None and record["state"] == "UNKNOWN" and record["result"] is None
    assert len(case.auth) == 1 and case.handled == []
    reply = case.exchange(req)
    assert reply is not None and reply["error"]["code"] == "EXECUTION_UNKNOWN"
    assert len(case.auth) == 1 and case.handled == []


@pytest.mark.parametrize("op", [Operation.HEALTH, Operation.RELEASE, Operation.EXEC])
@pytest.mark.parametrize("frame_elapsed", [0.4, 1.1])
def test_valid_frame_consumes_original_command_budget_not_reply_allowance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, op: Operation, frame_elapsed: float
) -> None:
    import fa.execution.supervisor as supervisor

    clock = [0.0]
    monkeypatch.setattr("fa.execution.protocol.time.monotonic", lambda: clock[0])
    original = decode_request

    def decode(raw: bytes) -> dict[str, Any]:
        parsed = original(raw)
        clock[0] = frame_elapsed
        return parsed

    monkeypatch.setattr(supervisor, "decode_request", decode)
    case = Probe(tmp_path, clock)
    req = execution_request(op)
    reply = case.exchange(req)
    assert reply is not None
    if op is Operation.EXEC and frame_elapsed > 1:
        assert reply["status"] == "ERROR" and reply["error"]["code"] == "BACKEND_UNAVAILABLE"
        assert case.auth == case.handled == []
        assert case.journal.lookup("op-" + RID, NamespaceRef(**req["namespace"])) is None
    else:
        assert reply["status"] == "OK"
        expected = (PeerIdentity(os.getpid(), os.getuid(), os.getgid()), 1.0 if op is Operation.EXEC else 2.0)
        assert case.auth == case.handled == [expected]
