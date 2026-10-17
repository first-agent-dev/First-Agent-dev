"""C0/C3 PlanRef joins through the real dispatcher/journal, injected test authority.

NOT the production protected-metadata loader, Docker, or C1 service composition.
"""

from __future__ import annotations

import copy
import os
from dataclasses import FrozenInstanceError, asdict, replace
from pathlib import Path
from typing import Any

import pytest

from fa.execution.plans import ProtectedPlanContext
from fa.execution.protocol import decode_request, encode_json
from fa.execution.supervisor import PeerIdentity
from fa.execution.types import Access, ExecutionContractError, GrantReply, Operation, ViewPurpose, ViewRef
from fa.inner_loop.plan_admission import MAX_PLAN_BYTES, read_plan_snapshot
from tests.test_execution_dispatch import NS, Fixture, profile
from tests.test_execution_protocol import RECEIPT, RID, SHA, VIEW, request


def admitted(tmp_path: Path, *, formal: bool = True) -> ProtectedPlanContext:
    (tmp_path / "plan.md").write_bytes(b"# Admitted plan\n")
    ref = read_plan_snapshot(tmp_path, Path("plan.md")).ref
    return ProtectedPlanContext(tmp_path, ref, formal)


@pytest.mark.parametrize("kind", ["EXPLICIT", "EXISTING_SELECTION", "BOOTSTRAP"])
def test_actual_source_recheck_preserves_existing_admitted_plan_identity(tmp_path: Path, kind: str) -> None:
    ctx = admitted(tmp_path)
    assert ctx.plan_ref is not None
    ctx = replace(ctx, plan_ref=replace(ctx.plan_ref, source_kind=kind))
    ctx.recheck()
    assert ctx.plan_ref is not None
    assert ctx.to_plan_ref() == asdict(ctx.plan_ref)
    public = ctx.to_plan_ref()
    assert public is not None
    public["sha256"] = "f" * 64
    retained = ctx.to_plan_ref()
    assert retained is not None and retained["sha256"] != public["sha256"]
    with pytest.raises(FrozenInstanceError):
        ctx.formal_evidence = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        ctx.plan_ref.sha256 = "f" * 64  # type: ignore[misc]


def test_ordinary_null_is_explicit_but_never_formal_evidence(tmp_path: Path) -> None:
    ctx = ProtectedPlanContext(tmp_path, None, False)
    ctx.recheck()
    assert ctx.to_plan_ref() is None
    ctx.check_receipt_plan(None)
    with pytest.raises(ExecutionContractError):
        ctx.check_receipt_plan(SHA)
    with pytest.raises(ExecutionContractError):
        ProtectedPlanContext(tmp_path, None, True)


@pytest.mark.parametrize(
    "field,value",
    [
        ("workspace_relative_path", "../outside"),
        ("workspace_relative_path", "/absolute"),
        ("workspace_relative_path", "a/./b"),
        ("sha256", "f" * 63),
        ("sha256", "F" * 64),
        ("source_kind", "WORKER"),
    ],
)
def test_trusted_context_still_validates_plan_shape(tmp_path: Path, field: str, value: str) -> None:
    ctx = admitted(tmp_path)
    assert ctx.plan_ref is not None
    with pytest.raises(ExecutionContractError):
        replace(ctx, plan_ref=replace(ctx.plan_ref, **{field: value}))


@pytest.mark.parametrize(
    "bad", ["changed", "missing", "file-link", "parent-link", "directory", "utf8", "empty", "large"]
)
def test_actual_recheck_denies_mutable_or_non_regular_sources(tmp_path: Path, bad: str) -> None:
    ctx = admitted(tmp_path)
    path = tmp_path / "plan.md"
    if bad == "changed":
        path.write_bytes(b"different admitted-source bytes")
    elif bad == "missing":
        path.unlink()
    elif bad in {"file-link", "parent-link"}:
        directory = tmp_path / "real"
        directory.mkdir()
        path.rename(directory / "plan.md")
        if bad == "file-link":
            path.symlink_to(directory / "plan.md")
        else:
            (tmp_path / "link").symlink_to(directory, target_is_directory=True)
            assert ctx.plan_ref is not None
            ctx = replace(ctx, plan_ref=replace(ctx.plan_ref, workspace_relative_path="link/plan.md"))
    elif bad == "directory":
        path.unlink()
        path.mkdir()
    else:
        path.write_bytes({"utf8": b"\xff", "empty": b" ", "large": b"x" * (MAX_PLAN_BYTES + 1)}[bad])
    with pytest.raises(ExecutionContractError):
        ctx.recheck()


class PlanFixture(Fixture):
    """Explicit fixture callbacks and simulated receipts; no resource authority claim."""

    def __init__(self, tmp_path: Path, context: ProtectedPlanContext | None) -> None:
        super().__init__(tmp_path)
        self.context = context
        self.receipt_plan = None if context is None or context.plan_ref is None else context.plan_ref.sha256

    def authorize(self, peer: PeerIdentity, req: dict[str, Any]) -> ProtectedPlanContext | None:
        self.auth_calls += 1
        assert peer.pid == os.getpid() and peer.uid == os.getuid() and req["namespace"] == NS.to_dict()
        return self.context

    def handle(self, req: dict[str, Any]) -> GrantReply | dict[str, Any]:
        self.handler_calls += 1
        record = self.journal.lookup("op-" + req["request_id"], NS)
        assert record is not None and record["state"] == "EXECUTING"
        if req["op"] == "exec":
            self.journal.record_container(record["operation_id"], NS, "a" * 64)  # Simulated C0 witness only.
            return {
                "receipt": {
                    **copy.deepcopy(RECEIPT),
                    "plan_sha256": self.receipt_plan,
                    "profile_id": "interactive",
                    "image_digest": profile().image_digest,
                }
            }
        view = ViewRef(
            workspace_id=str(VIEW["workspace_id"]),
            view_id=str(VIEW["view_id"]),
            base_revision=str(VIEW["base_revision"]),
            owner_run_id="run-1",
            generation=1,
            access=Access.READ if req["op"] == "pin_reader" else Access.WRITE,
            purpose=ViewPurpose.PROJECT,
        )
        return GrantReply(Operation(req["op"]), "b" * 64, view, None, None)

    def dispatch(self, req: dict[str, Any]) -> dict[str, Any]:
        parsed = decode_request(encode_json(req))
        return self.service._dispatch(PeerIdentity(os.getpid(), os.getuid(), os.getgid()), parsed)


def operation_request(op: Operation) -> dict[str, Any]:
    req = request(op)
    if op is Operation.EXEC:
        req["payload"].update(profile_id="interactive", timeout_ms=1000, session_id="main")
    return req


@pytest.mark.parametrize("op", [Operation.PIN_READER, Operation.CREATE_VIEW, Operation.EXEC])
@pytest.mark.parametrize("planned", [False, True])
def test_admission_and_execution_use_actual_context_before_durable_done(
    tmp_path: Path, op: Operation, planned: bool
) -> None:
    ctx = admitted(tmp_path) if planned else ProtectedPlanContext(tmp_path, None, False)
    case = PlanFixture(tmp_path, ctx)
    req = operation_request(op)
    if op is not Operation.EXEC:
        req["payload"]["plan_ref"] = ctx.to_plan_ref()
    result = case.dispatch(req)
    assert result["status"] == "OK"
    record = case.journal.lookup("op-" + RID, NS)
    assert record is not None and record["state"] == "DONE"
    if op is Operation.EXEC:
        assert result["result"]["receipt"]["plan_sha256"] == case.receipt_plan
    else:
        assert result["result"]["capability"] == "b" * 64
    assert case.auth_calls == case.handler_calls == 1
    # Q75 reads original memory-cached completion even after source disappearance.
    if planned:
        (tmp_path / "plan.md").unlink()
    assert case.dispatch(req) == result
    assert case.auth_calls == case.handler_calls == 1


@pytest.mark.parametrize("op", [Operation.PIN_READER, Operation.CREATE_VIEW, Operation.EXEC])
@pytest.mark.parametrize("bad", ["missing-context", "stale-source"])
def test_plan_failure_precedes_reservation_and_backend(tmp_path: Path, op: Operation, bad: str) -> None:
    ctx = admitted(tmp_path)
    case = PlanFixture(tmp_path, None if bad == "missing-context" else ctx)
    req = operation_request(op)
    if op is not Operation.EXEC:
        req["payload"]["plan_ref"] = ctx.to_plan_ref()
    if bad == "stale-source":
        (tmp_path / "plan.md").write_bytes(b"not the admitted plan")
    result = case.dispatch(req)
    assert result["status"] == "ERROR"
    assert result["error"]["code"] == ("UNAUTHORIZED" if bad == "missing-context" else "INPUT_POLICY")
    assert case.auth_calls == 1 and case.handler_calls == 0
    assert case.journal.lookup("op-" + RID, NS) is None


@pytest.mark.parametrize("op", [Operation.PIN_READER, Operation.CREATE_VIEW])
@pytest.mark.parametrize(
    "field,value", [("sha256", "f" * 64), ("source_kind", "BOOTSTRAP"), ("workspace_relative_path", "different.md")]
)
def test_admission_cannot_replace_any_admitted_plan_component(
    tmp_path: Path, op: Operation, field: str, value: str
) -> None:
    ctx = admitted(tmp_path)
    case = PlanFixture(tmp_path, ctx)
    req = operation_request(op)
    ref = ctx.to_plan_ref()
    assert ref is not None
    ref[field] = value
    req["payload"]["plan_ref"] = ref
    result = case.dispatch(req)
    assert result["status"] == "ERROR" and result["error"] is not None
    assert result["error"]["code"] == "INPUT_POLICY"
    assert case.handler_calls == 0 and case.journal.lookup("op-" + RID, NS) is None


@pytest.mark.parametrize("planned,bad_hash", [(True, None), (True, SHA), (False, SHA)])
def test_receipt_cannot_erase_replace_or_fabricate_plan_binding(
    tmp_path: Path, planned: bool, bad_hash: str | None
) -> None:
    ctx = admitted(tmp_path) if planned else ProtectedPlanContext(tmp_path, None, False)
    case = PlanFixture(tmp_path, ctx)
    case.receipt_plan = bad_hash
    req = operation_request(Operation.EXEC)
    result = case.dispatch(req)
    assert result["status"] == "ERROR" and result["error"] is not None
    assert result["error"]["code"] == "EXECUTION_UNKNOWN"
    record = case.journal.lookup("op-" + RID, NS)
    assert record is not None and record["state"] == "UNKNOWN" and record["result"] is None
    assert case.auth_calls == case.handler_calls == 1
    assert case.dispatch(req)["error"]["code"] == "EXECUTION_UNKNOWN"
    assert case.auth_calls == case.handler_calls == 1


@pytest.mark.parametrize("purpose", ["VERIFICATION", "MUTATION", "CANDIDATE"])
def test_formal_view_cannot_use_ordinary_null_context(tmp_path: Path, purpose: str) -> None:
    case = PlanFixture(tmp_path, ProtectedPlanContext(tmp_path, None, False))
    req = operation_request(Operation.EXEC)
    req["view_ref"]["purpose"] = purpose
    assert case.dispatch(req)["error"]["code"] == "INPUT_POLICY"
    assert case.handler_calls == 0 and case.journal.lookup("op-" + RID, NS) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_root", Path("relative")),
        ("source_root", "/host/string"),
        ("formal_evidence", None),
        ("formal_evidence", 1),
        ("plan_ref", {}),
    ],
)
def test_context_does_not_default_indeterminate_authority_policy(tmp_path: Path, field: str, value: Any) -> None:
    ctx = admitted(tmp_path)
    with pytest.raises(ExecutionContractError):
        replace(ctx, **{field: value})


def test_framed_fresh_exec_rechecks_source_before_reservation(tmp_path: Path) -> None:
    import socket
    from concurrent.futures import ThreadPoolExecutor

    from fa.execution.protocol import decode_reply, read_frame, write_frame

    case = PlanFixture(tmp_path, admitted(tmp_path))
    (tmp_path / "plan.md").write_bytes(b"changed after admission")
    controller, accepted = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    req = operation_request(Operation.EXEC)
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(case.service.serve_connection, accepted)
        with controller:
            controller.settimeout(3)
            write_frame(controller, encode_json(req))
            response = decode_reply(read_frame(controller), operation=Operation.EXEC, request_id=RID)
        future.result(timeout=4)
    assert response["status"] == "ERROR" and response["error"] is not None
    assert response["error"]["code"] == "INPUT_POLICY"
    assert case.auth_calls == 1 and case.handler_calls == 0
    assert case.journal.lookup("op-" + RID, NS) is None
