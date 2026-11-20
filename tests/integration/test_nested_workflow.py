"""C1: production nested-invocation ownership lifecycle with a real Docker child cell.

The injected workflow callback is deliberately controlled, not a provider witness;
this suite exercises the actual invoke_workflow handler, session child allocation,
HANDOFF/return, managed mutation view and Docker/cgroup-backed settlement. It is
not the separate W4 §9.1 real-provider acceptance case.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from fa.execution.cgroup import descendants_empty
from fa.execution.client import ExecutionRejectedError, ManagedProjectToolExecutor
from fa.execution.composition import ManagedExecution
from fa.execution.types import Access, NamespaceRef, Operation, ViewPurpose, ViewRef
from fa.inner_loop.plan_admission import read_plan_snapshot
from fa.inner_loop.session_db import SessionDatabase
from fa.inner_loop.tools.workflow_tool import WorkflowInvocationContext, build_invoke_workflow_tool
from fa.inner_loop.tools.workspace_port import WorkspacePortError
from fa.inner_loop.workflow_artifacts import FlowState
from tests.integration._host import ExecutionHostRuntime

pytestmark = pytest.mark.execution_host


def _cell_for_view(runtime: ExecutionHostRuntime, view: ViewRef) -> str:
    records = [
        record
        for record in runtime._owned_cell_records()
        if record.get("view_ref") == view.to_dict() and isinstance(record.get("container_id"), str)
    ]
    assert records, "each parent/child managed EXEC must be owned by its real view"
    container_ids = {
        container_id for record in records if isinstance((container_id := record.get("container_id")), str)
    }
    assert len(container_ids) == 1
    return next(iter(container_ids))


def _assert_view_populated(runtime: ExecutionHostRuntime, view: ViewRef, container_id: str) -> None:
    assert (
        descendants_empty(
            runtime.service_config.cgroup_root,
            runtime.readiness.write_profile.cgroup_parent,
            container_id,
        )
        is False
    ), f"view {view.view_id} must have a live cell before settlement"


def _assert_view_empty(runtime: ExecutionHostRuntime, view: ViewRef, container_id: str) -> None:
    assert (
        descendants_empty(
            runtime.service_config.cgroup_root,
            runtime.readiness.write_profile.cgroup_parent,
            container_id,
        )
        is True
    ), f"view {view.view_id} must have cgroup-empty evidence after settlement"


def _make_session_context(
    tmp_path: Path,
    workspace_root: Path,
    namespace: NamespaceRef,
) -> tuple[Any, Any, Any, SessionDatabase]:
    """Create real SessionManager identities; only readiness provisioning is scaffolded."""
    from fa.session.manager import SessionManager
    from fa.session.provisioning import ProvisionedWorkspace
    from fa.workspace_bootstrap import ReadyState, ReadyStatus

    state_root = tmp_path / "session-state"

    def provision(_request: Any) -> ProvisionedWorkspace:
        return ProvisionedWorkspace(True, "ws-" + uuid4().hex, "rev-" + uuid4().hex, None)

    def ready(workspace: Path, _run: Any) -> ReadyState:
        return ReadyState(ReadyStatus.READY, None, "ready_fast_path", workspace / "ready.log", False, 0)

    manager = SessionManager(
        state_root=state_root,
        workspace_root=workspace_root.parent,
        source_workspace=workspace_root,
        workspace_preparer=ready,
        workspace_provisioner=provision,
    )
    session = manager.provision_entrypoint_session(
        session_id=namespace.session_id,
        workspace_override=workspace_root,
    )
    parent_run = manager.begin_run(session, requested_run_id=namespace.run_id)
    session_db = SessionDatabase.open_existing(session.session_db_path, session_id=session.session_id)
    return manager, session, parent_run, session_db


def test_invoke_workflow_hands_one_real_writer_to_a_mutation_cell_and_returns_it_to_parent(
    host_runtime: ExecutionHostRuntime,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = "i03-nested-" + uuid4().hex[:12]
    parent_run_id = "run-parent-" + uuid4().hex[:12]
    parent_namespace = NamespaceRef(session_id, parent_run_id)
    workspace = host_runtime.register_workspace(
        namespace=parent_namespace,
        files={
            "plan.md": b"# Canonical plan\n\nKeep the plan immutable during nested coding.\n",
            "src/keep.py": b"KEEP = True\n",
        },
    )
    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path / "session-state"))
    _manager, session, parent_run, session_db = _make_session_context(
        tmp_path,
        workspace.root,
        parent_namespace,
    )
    assert parent_run.run_id == parent_namespace.run_id

    initial_writer = workspace.acquire_writer()
    managed = ManagedExecution(
        host_runtime.client,
        workspace.binding,
        initial_writer,
        view_profile=host_runtime.readiness.write_profile,
        read_only_profile=host_runtime.readiness.read_only_profile,
    )
    parent_view = workspace.open_write_view()
    parent_port = workspace.port(parent_view)
    parent_executor = workspace.managed_bash(parent_view)
    parent_command = parent_executor.run(
        "set -eu\nprintf 'PARENT_BEFORE_CHILD\\n' > src/parent-before-child.txt\n",
        timeout=30,
    )
    assert parent_command.exit_code == 0, parent_command.stdout
    parent_cell = _cell_for_view(host_runtime, parent_view.view_ref)
    _assert_view_populated(host_runtime, parent_view.view_ref, parent_cell)

    assert parent_view.grant.input_tree_sha256 is not None
    parent_project_executor = ManagedProjectToolExecutor(
        host_runtime.client,
        namespace=parent_namespace,
        view=parent_view.view_ref,
        grant=parent_view.grant,
        profile=host_runtime.readiness.write_profile,
        input_tree_sha256=parent_view.grant.input_tree_sha256,
        plan_sha256=None,
        original_revision_id=parent_view.view_ref.base_revision,
    )
    from fa.cli import _ManagedStageLease

    parent_lease = _ManagedStageLease(
        managed=managed,
        namespace=parent_namespace,
        view_grant=parent_view.grant,
        workspace_io=parent_port,
        managed_executor=parent_executor,
        project_tool_executor=parent_project_executor,
        plan_ref=None,
        allow_nested_handoff=True,
    )
    plan = read_plan_snapshot(workspace.root, Path("plan.md"))
    child_evidence: dict[str, Any] = {}

    def controlled_child_workflow(**kwargs: Any) -> tuple[int, FlowState | None]:
        assert parent_lease.state == "suspended"
        parent_view.lifecycle = "published"
        workspace.revision_id = managed.current_revision_id
        child_run = kwargs["run_context"]
        child_namespace = managed.binding.namespace
        assert child_namespace.session_id == session.session_id
        assert child_namespace.run_id == kwargs["run_id"] == child_run.run_id
        assert child_namespace.parent_run_id == parent_namespace.run_id
        assert child_namespace != parent_namespace
        assert kwargs["acquisition"] is not None
        assert kwargs["plan_publisher"]._binding == managed.binding

        # A request carrying the revoked parent proof cannot reopen or retarget a
        # view after HANDOFF; the single writer remains owned by this child.
        with pytest.raises(ExecutionRejectedError) as old_owner:
            host_runtime.client.open_view(
                workspace.binding,
                access=Access.WRITE,
                purpose=ViewPurpose.PROJECT,
                base_revision=managed.current_revision_id,
                grant=initial_writer,
            )
        assert old_owner.value.code == "UNAUTHORIZED"

        competing_namespace = NamespaceRef(session_id, "run-competing-writer")
        with pytest.raises(ExecutionRejectedError) as competing_writer:
            host_runtime.request(
                Operation.ACQUIRE_WRITER,
                namespace=competing_namespace,
                payload={"workspace_id": workspace.workspace_id},
            )
        assert competing_writer.value.code == "WORKSPACE_BUSY"

        child_view = managed.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.MUTATION,
            base_revision=managed.current_revision_id,
            plan_ref=plan.ref,
        )
        assert child_view.view_ref is not None
        tracked_child_view = workspace.track_view(child_view, child_namespace)
        child_port = workspace.port(tracked_child_view)
        with pytest.raises(WorkspacePortError) as protected_plan:
            child_port.write_file("plan.md", "# Tampered by nested coder\n")
        assert protected_plan.value.code in {"denied", "input_policy"}
        assert child_port.read_file("plan.md").content == plan.text

        child_executor = workspace.managed_bash(tracked_child_view, plan_ref=plan.ref)
        child_result = child_executor.run(
            "set -eu\n"
            f'test "$(id -u)" = {host_runtime.readiness.write_profile.uid}\n'
            "test ! -S /var/run/docker.sock\n"
            "printf 'NESTED_CHILD_CELL_WRITE\\n' > src/nested-child.py\n",
            timeout=30,
        )
        assert child_result.exit_code == 0, child_result.stdout
        assert child_port.read_file("src/nested-child.py").content == "NESTED_CHILD_CELL_WRITE\n"
        child_cell = _cell_for_view(host_runtime, tracked_child_view.view_ref)
        _assert_view_populated(host_runtime, tracked_child_view.view_ref, child_cell)

        publication = managed.publish_stage(tracked_child_view.grant)
        tracked_child_view.lifecycle = "published"
        workspace.revision_id = publication.revision_id
        child_evidence.update(
            {
                "namespace": child_namespace,
                "view": tracked_child_view.view_ref,
                "container_id": child_cell,
                "revision_id": publication.revision_id,
                "capability": managed.grant.capability,
            }
        )
        _assert_view_empty(host_runtime, tracked_child_view.view_ref, child_cell)
        return 0, FlowState(
            run_id=child_run.run_id,
            task=str(kwargs["task"]),
            status="DONE",
            active_role="eval",
            active_plan_id="nested-host-control",
            active_plan_version=1,
            last_route_decision="complete",
            last_transition_reason="accepted",
        )

    invocation = build_invoke_workflow_tool(
        controlled_child_workflow,
        lambda: WorkflowInvocationContext(
            parent_run_id=parent_run.run_id,
            config=tmp_path / "models.yaml",
            workspace=workspace.root,
            max_turns=2,
            run_stage_fn=lambda *_args, **_kwargs: 0,
            workflow_timeout_seconds=120,
            session_context=session,
            run_context=parent_run,
            session_db=session_db,
            managed_execution=managed,
            parent_stage_lease=parent_lease,
        ),
    )
    result = invocation.handler({"task": "make one nested source change", "roles": "planner,coder,eval"})

    # The outer handler returned the same grant to the exact parent and resumed
    # its controller objects on a fresh WRITE view at the child's revision.
    assert result.error is None, result.error
    if result.result is None:
        raise AssertionError("successful nested invocation must return structured workflow fields")
    tool_result = result.result
    assert tool_result["exit_code"] == 0
    assert tool_result["parent_view_refreshed"] is True
    assert managed.binding.namespace == parent_namespace
    assert parent_lease.state == "active"
    assert managed.current_revision_id == child_evidence["revision_id"]
    resumed_grant = parent_lease._view_grant
    assert resumed_grant is not None
    resumed_view = workspace.track_view(resumed_grant, parent_namespace)
    resumed_port = parent_lease.workspace_io
    assert resumed_port.read_file("src/nested-child.py").content == "NESTED_CHILD_CELL_WRITE\n"
    assert resumed_port.read_file("src/parent-before-child.txt").content == "PARENT_BEFORE_CHILD\n"
    assert resumed_port.read_file("plan.md").content == plan.text

    parent_after_child = parent_lease.managed_executor.run(
        "set -eu\nprintf 'PARENT_AFTER_CHILD\\n' > src/parent-after-child.txt\n",
        timeout=30,
    )
    assert parent_after_child.exit_code == 0, parent_after_child.stdout
    resumed_cell = _cell_for_view(host_runtime, resumed_view.view_ref)
    _assert_view_populated(host_runtime, resumed_view.view_ref, resumed_cell)
    parent_lease.finish(accepted=True)
    resumed_view.lifecycle = "published"
    _assert_view_empty(host_runtime, resumed_view.view_ref, resumed_cell)

    workspace.writer_grant = managed.grant
    workspace.revision_id = managed.current_revision_id
    assert workspace.root.joinpath("plan.md").read_text(encoding="utf-8") == plan.text
    assert workspace.root.joinpath("src/keep.py").read_text(encoding="utf-8") == "KEEP = True\n"
    assert workspace.root.joinpath("src/parent-before-child.txt").read_text(encoding="utf-8") == "PARENT_BEFORE_CHILD\n"
    assert workspace.root.joinpath("src/nested-child.py").read_text(encoding="utf-8") == "NESTED_CHILD_CELL_WRITE\n"
    assert workspace.root.joinpath("src/parent-after-child.txt").read_text(encoding="utf-8") == "PARENT_AFTER_CHILD\n"

    child_namespace = child_evidence["namespace"]
    assert isinstance(child_namespace, NamespaceRef)
    child_binding = session_db.get_run_binding(child_namespace.run_id)
    assert child_binding is not None
    assert child_binding["session_id"] == session.session_id

    handoffs = [
        event
        for event in host_runtime.events
        if event.get("operation") == Operation.HANDOFF.value and event.get("outcome") == "OK"
    ]
    assert len(handoffs) == 2
    assert handoffs[0]["namespace"] == parent_namespace.to_dict()
    assert handoffs[0]["payload"]["target_namespace"] == child_namespace.to_dict()
    assert handoffs[1]["namespace"] == child_namespace.to_dict()
    assert handoffs[1]["payload"]["target_namespace"] == parent_namespace.to_dict()

    assert host_runtime.assert_owned_cells_terminal() >= 3
    trace = json.dumps(host_runtime.events, sort_keys=True)
    assert initial_writer.capability not in trace
    assert child_evidence["capability"] not in trace
    assert managed.grant.capability not in trace
