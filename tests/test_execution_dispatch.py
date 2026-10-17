"""C0/C3 dispatcher transport/order. Authority/backend are explicit unit fixtures.

Kernel AF_UNIX peer credentials and real operation files, NOT real workspace
ownership, issuer, daemon activation, Docker jobs or descendant terminality.
"""

from __future__ import annotations

import os
import socket
import struct
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from fa.execution.journal import OperationJournal
from fa.execution.plans import ProtectedPlanContext
from fa.execution.profiles import ExecutionProfile
from fa.execution.protocol import DeadlineConnection, decode_reply, decode_request, encode_json, read_frame, write_frame
from fa.execution.supervisor import CompletedReplyCache, PeerIdentity, SupervisorDispatcher, SupervisorError
from fa.execution.types import GrantReply, NamespaceRef, Operation

RID = "1" * 32
CAP = "2" * 64
ISSUED = "3" * 64
NS = NamespaceRef("session-1", "run-1")


def request() -> dict[str, Any]:
    return {
        "protocol_version": 1,
        "request_id": RID,
        "op": "handoff",
        "namespace": NS.to_dict(),
        "view_ref": None,
        "capability": CAP,
        "payload": {"target_namespace": NamespaceRef("session-1", "child", "run-1").to_dict()},
    }


def profile() -> ExecutionProfile:
    return ExecutionProfile(
        "interactive",
        "unit.invalid/cell@sha256:" + "4" * 64,
        1000,
        1000,
        1_000_000_000,
        128 * 1024**2,
        64,
        1000,
        True,
        "fa-exec.slice",
        '{"defaultAction":"SCMP_ACT_ERRNO","syscalls":[]}',
    )


class Fixture:
    """Side-effect counter + fixture revocation, not a production authority."""

    def __init__(self, tmp_path: Path) -> None:
        self.journal = OperationJournal(tmp_path / "operations", lock_timeout_ms=1000)
        self.auth_calls = self.handler_calls = 0
        self.proof_alive = True
        self.break_backend = False
        self.service = self.make_service()

    def authorize(self, peer: PeerIdentity, req: dict[str, Any]) -> ProtectedPlanContext | None:
        self.auth_calls += 1
        assert peer.uid == os.getuid() and peer.pid == os.getpid()
        if req["op"] != "health" and (
            not self.proof_alive or req["capability"] != CAP or req["namespace"] != NS.to_dict()
        ):
            raise SupervisorError("UNAUTHORIZED")
        return None

    def handle(self, req: dict[str, Any]) -> GrantReply | dict[str, Any]:
        self.handler_calls += 1
        if req["op"] == "health":
            return {"ready": False, "protocol_version": 1, "profile_set_sha256": "4" * 64}
        observed = self.journal.lookup("op-" + req["request_id"], NS)
        assert observed is not None and observed["state"] == "EXECUTING"
        if self.break_backend:
            raise RuntimeError(CAP + " private host diagnostic")
        self.proof_alive = False
        if req["op"] == "release":
            return {"released": True}
        return GrantReply(Operation.HANDOFF, ISSUED, None, 2, "rev-" + "5" * 32)

    def make_service(
        self, *, uid: int | None = None, configured_profile: ExecutionProfile | None = None
    ) -> SupervisorDispatcher:
        return SupervisorDispatcher(
            client_uids=frozenset({os.getuid() if uid is None else uid}),
            rpc_timeout_ms=2000,
            profiles=(profile() if configured_profile is None else configured_profile,),
            journal=self.journal,
            replies=CompletedReplyCache(max_entries=32),
            authorize=self.authorize,
            handle=self.handle,
        )


def exchange(service: SupervisorDispatcher, raw: bytes) -> dict[str, Any] | None:
    controller, accepted = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(service.serve_connection, accepted)
        with controller:
            controller.settimeout(3)
            try:
                write_frame(controller, raw)
                response = read_frame(controller)
            except (ConnectionError, OSError, ValueError):
                response = None
        future.result(timeout=4)
    return None if response is None else decode_reply(response, operation=Operation.HANDOFF, request_id=RID)


def test_authenticated_framed_handoff_has_durable_done_before_ack_and_exact_cached_replay(tmp_path: Path) -> None:
    case = Fixture(tmp_path)
    first = exchange(case.service, encode_json(request()))
    assert first is not None and first["status"] == "OK"
    assert first["result"]["capability"] == ISSUED
    record = case.journal.lookup("op-" + RID, NS)
    assert record is not None and record["state"] == "DONE"
    assert "capability" not in record["result"]
    raw = (tmp_path / "operations" / ("op-" + RID + ".json")).read_bytes()
    assert CAP.encode() not in raw and ISSUED.encode() not in raw
    # Fixture has revoked the proof. There is no new authority/handler call.
    assert case.proof_alive is False
    assert exchange(case.service, encode_json(request())) == first
    assert case.auth_calls == case.handler_calls == 1


def test_absent_authority_denies_before_reservation_or_handler(tmp_path: Path) -> None:
    case = Fixture(tmp_path)
    denied = exchange(case.service, encode_json({**request(), "capability": "a" * 64}))
    assert denied is not None and denied["error"]["code"] == "UNAUTHORIZED"
    assert case.auth_calls == 1 and case.handler_calls == 0
    assert case.journal.lookup("op-" + RID, NS) is None


def test_peer_uid_is_rejected_before_frame_or_authority(tmp_path: Path) -> None:
    case = Fixture(tmp_path)
    assert exchange(case.make_service(uid=os.getuid() + 1), encode_json(request())) is None
    assert case.auth_calls == case.handler_calls == 0
    assert not (tmp_path / "operations").exists()


def test_closed_schema_extra_docker_authority_is_denied_before_calls(tmp_path: Path) -> None:
    case = Fixture(tmp_path)
    response = exchange(case.service, encode_json({**request(), "image": "attacker-selected"}))
    assert response is not None and response["error"]["code"] == "INVALID_REQUEST"
    assert case.auth_calls == case.handler_calls == 0
    assert not (tmp_path / "operations").exists()


def test_changed_input_and_proof_never_reinvoke_completed_handler(tmp_path: Path) -> None:
    case = Fixture(tmp_path)
    assert exchange(case.service, encode_json(request())) is not None
    changed = {**request(), "payload": {"target_namespace": NamespaceRef("session-1", "other", "run-1").to_dict()}}
    for req, code in [(changed, "COLLISION"), ({**request(), "capability": "a" * 64}, "UNAUTHORIZED")]:
        response = exchange(case.service, encode_json(req))
        assert response is not None and response["error"]["code"] == code
    assert case.auth_calls == case.handler_calls == 1


def test_cache_loss_blocks_without_fresh_authority_or_reissuing_grant(tmp_path: Path) -> None:
    case = Fixture(tmp_path)
    first = exchange(case.service, encode_json(request()))
    assert first is not None and first["status"] == "OK"
    response = exchange(case.make_service(), encode_json(request()))
    assert response is not None and response["error"]["code"] == "EXECUTION_UNKNOWN"
    assert case.auth_calls == case.handler_calls == 1


def test_backend_exception_is_secret_free_uncertain_and_not_replayed(tmp_path: Path) -> None:
    case = Fixture(tmp_path)
    case.break_backend = True
    response = exchange(case.service, encode_json(request()))
    assert response is not None and response["error"]["code"] == "EXECUTION_UNKNOWN"
    assert response["error"]["operation_id"] == "op-" + RID
    assert CAP.encode() not in encode_json(response) and b"diagnostic" not in encode_json(response)
    record = case.journal.lookup("op-" + RID, NS)
    assert record is not None and record["state"] == "UNKNOWN" and record["result"] is None
    again = exchange(case.service, encode_json(request()))
    assert again is not None and again["error"]["code"] == "EXECUTION_UNKNOWN"
    assert case.auth_calls == case.handler_calls == 1


@pytest.mark.parametrize(
    "profile_id,timeout,session,interactive,code",
    [
        ("not-approved", 1000, "main", True, "UNAPPROVED_PROFILE"),
        ("interactive", 1001, "main", True, "INPUT_POLICY"),
        ("interactive", 1000, None, True, "INPUT_POLICY"),
        ("verification", 1000, "main", False, "INPUT_POLICY"),
    ],
)
def test_profile_and_configured_limit_deny_before_authority_or_handler(
    tmp_path: Path, profile_id: str, timeout: int, session: str | None, interactive: bool, code: str
) -> None:
    case = Fixture(tmp_path)
    if not interactive:
        case.service = case.make_service(
            configured_profile=replace(profile(), profile_id="verification", interactive=False)
        )
    req = {
        **request(),
        "op": "exec",
        "view_ref": {
            "workspace_id": "ws-" + "6" * 32,
            "view_id": "view-" + "7" * 32,
            "base_revision": "rev-" + "8" * 32,
            "owner_run_id": "run-1",
            "generation": 1,
            "access": "WRITE",
            "purpose": "PROJECT",
        },
        "payload": {
            "operation_id": "op-" + RID,
            "profile_id": profile_id,
            "timeout_ms": timeout,
            "cwd": ".",
            "command": "fixture",
            "session_id": session,
        },
    }
    parsed = decode_request(encode_json(req))
    response = case.service._dispatch(PeerIdentity(os.getpid(), os.getuid(), os.getgid()), parsed)
    assert case.auth_calls == case.handler_calls == 0
    assert response["error"]["code"] == code
    assert case.journal.lookup("op-" + RID, NS) is None


def test_absolute_deadline_does_not_reset_for_partial_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [0.0]
    monkeypatch.setattr("fa.execution.protocol.time.monotonic", lambda: clock[0])
    client, server = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    with client, server:
        # Use actual socket API; changing only the clock is deterministic C0,
        # not a test-runner timeout or claimed live slowloris/kernel proof.
        framed = DeadlineConnection(client, timeout_ms=1000)
        assert framed.remaining() == 1.0
        server.sendall(b"ab")
        clock[0] = 0.5
        assert framed.recv(1) == b"a"
        clock[0] = 0.75
        assert framed.recv(1) == b"b"
        assert framed.remaining() == 0.25
        server.sendall(b"c")  # A removed guard reads this immediately, not via timeout.
        clock[0] = 1.01
        with pytest.raises(TimeoutError):
            framed.recv(1)
        with pytest.raises(TimeoutError):
            framed.sendall(struct.pack("!I", 1))


def test_non_grant_release_replays_only_original_public_reply_without_new_handler(tmp_path: Path) -> None:
    case = Fixture(tmp_path)
    req = {**request(), "op": "release", "payload": {}}
    peer = PeerIdentity(os.getpid(), os.getuid(), os.getgid())
    first = case.service._dispatch(peer, decode_request(encode_json(req)))
    assert first["status"] == "OK" and first["result"] == {"released": True}
    assert case.proof_alive is False
    assert case.service._dispatch(peer, req) == first
    assert case.auth_calls == case.handler_calls == 1
    record = case.journal.lookup("op-" + RID, NS)
    assert record is not None and record["state"] == "DONE" and record["result"] == {"released": True}


def test_readonly_health_reports_fixture_not_ready_without_operation_reservation(tmp_path: Path) -> None:
    case = Fixture(tmp_path)
    req = {**request(), "op": "health", "namespace": None, "view_ref": None, "capability": None, "payload": {}}
    response = case.service._dispatch(
        PeerIdentity(os.getpid(), os.getuid(), os.getgid()), decode_request(encode_json(req))
    )
    assert response["status"] == "OK"
    assert response["result"] == {"ready": False, "protocol_version": 1, "profile_set_sha256": "4" * 64}
    assert case.auth_calls == case.handler_calls == 1
    assert not (tmp_path / "operations").exists()


def test_lost_ack_does_not_roll_back_done_or_repeat_handoff(tmp_path: Path) -> None:
    case = Fixture(tmp_path)
    controller, accepted = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(case.service.serve_connection, accepted)
        with controller:
            write_frame(controller, encode_json(request()))
            # Deliberately discard the reply. Whether send failed or was queued,
            # the next request can only retrieve the original completed value.
        future.result(timeout=4)
    assert case.handler_calls == 1
    record = case.journal.lookup("op-" + RID, NS)
    assert record is not None and record["state"] == "DONE"
    reply = exchange(case.service, encode_json(request()))
    assert reply is not None and reply["status"] == "OK" and reply["result"]["capability"] == ISSUED
    assert case.auth_calls == case.handler_calls == 1


def test_callback_mutation_cannot_retarget_original_key_or_replay_proof(tmp_path: Path) -> None:
    class MutatingFixture(Fixture):
        def authorize(self, peer: PeerIdentity, req: dict[str, Any]) -> None:
            super().authorize(peer, req)
            req["capability"] = "a" * 64

        def handle(self, req: dict[str, Any]) -> GrantReply | dict[str, Any]:
            value = super().handle(req)
            req["request_id"] = "a" * 32
            return value

    case = MutatingFixture(tmp_path)
    peer = PeerIdentity(os.getpid(), os.getuid(), os.getgid())
    original = request()
    response = case.service._dispatch(peer, original)
    assert response["status"] == "OK" and response["request_id"] == RID
    assert original == request()
    assert case.service._dispatch(peer, request()) == response
    assert case.auth_calls == case.handler_calls == 1
    assert case.journal.lookup("op-" + "a" * 32, NS) is None
