"""Producer and caller-edge tests for the managed R13 child capability.

These tests exercise the production child tool factory and the CLI registration
seam. The fake EXEC denial is a producer/edge kill check only; the S4P1 R13
negative oracle still requires the real local supervisor/backend and its counters.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import patch

import pytest

from fa.cli import _register_managed_subagent_tool
from fa.execution.client import ExecutionRejectedError
from fa.execution.composition import ExecutionBinding
from fa.execution.types import Access, GrantReply, NamespaceRef, Operation, ViewPurpose, ViewRef
from fa.feature_flags import FeatureFlags, load_feature_flags
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.hooks.base import HookPayload, LifecyclePoint
from fa.inner_loop.registry import ToolCall, ToolRegistry, ToolResult
from fa.inner_loop.session_db import SessionDatabase
from fa.inner_loop.tools import managed_subagent
from tests.test_execution_views import read_only_profile


class _ParentState:
    def __init__(self, db: SessionDatabase, flags: FeatureFlags, *, role_run_id: str = "run-parent") -> None:
        self.managed_child = False
        self.session_id = "session-1"
        self.run_id = role_run_id
        self.session_db = db
        self.feature_flags = flags
        self.spawn_count = 0
        self.active_count = 0

    def try_reserve_subagent_spawn(self, maximum: int) -> bool:
        if self.spawn_count >= maximum:
            return False
        self.spawn_count += 1
        return True

    def try_reserve_active_subagent(self, max_active: int = 1) -> bool:
        if self.active_count >= max_active:
            return False
        self.active_count += 1
        return True

    def release_active_subagent(self) -> None:
        assert self.active_count == 1
        self.active_count -= 1


class _FakeClient:
    def __init__(self) -> None:
        self.pin_calls: list[tuple[ExecutionBinding, str, Any]] = []
        self.stop_calls: list[tuple[NamespaceRef, ViewRef]] = []
        self.report_root: Path | None = None

    def pin_reader(
        self,
        binding: ExecutionBinding,
        *,
        revision_id: str,
        plan_ref: Any,
        deadline: float,
    ) -> GrantReply:
        self.pin_calls.append((binding, revision_id, plan_ref))
        view = ViewRef(
            binding.workspace_id,
            "view-" + "2" * 32,
            revision_id,
            binding.namespace.run_id,
            1,
            Access.READ,
            ViewPurpose.PROJECT,
        )
        return GrantReply(
            Operation.PIN_READER,
            "a" * 64,
            view,
            None,
            None,
            input_tree_sha256="b" * 64,
        )

    def stop_view(
        self,
        namespace: NamespaceRef,
        *,
        view: ViewRef,
        grant: GrantReply,
        deadline: float,
    ) -> bool:
        assert grant.operation is Operation.PIN_READER
        self.stop_calls.append((namespace, view))
        if self.report_root is not None:
            assert not (self.report_root / namespace.run_id / "report.json").exists(), (
                "report must not be persisted before terminality is confirmed"
            )
        return True


class _FakePort:
    instances: ClassVar[list[_FakePort]] = []

    def __init__(
        self,
        client: Any,
        *,
        namespace: NamespaceRef,
        view: ViewRef,
        grant: GrantReply,
        cache_dir: Path,
    ) -> None:
        self.namespace = namespace
        self.view = view
        self.grant = grant
        self.cache_dir = cache_dir
        self.suspended = False
        self.instances.append(self)

    def suspend(self) -> None:
        self.suspended = True


class _FakeExecutor:
    interactive = False
    instances: ClassVar[list[_FakeExecutor]] = []
    reject_exec: ClassVar[bool] = False
    counters: ClassVar[dict[str, int]] = {}

    def __init__(
        self,
        client: Any,
        *,
        namespace: NamespaceRef,
        view: ViewRef,
        grant: GrantReply,
        profile: Any,
        plan_ref: Any,
        controller_root: Path,
    ) -> None:
        self.namespace = namespace
        self.view = view
        self.grant = grant
        self.profile = profile
        self.plan_ref = plan_ref
        self.controller_root = controller_root
        self.suspended = False
        self.instances.append(self)

    def run(self, command: str, *, timeout: int, workdir: Path, session_id: str | None) -> Any:
        self.counters["exec_requests"] = self.counters.get("exec_requests", 0) + 1
        assert session_id is None, "READ child Bash must never reuse an interactive session"
        if self.reject_exec:
            self.counters["exec_allowed"] = 0
            self.counters["cell_launches"] = 0
            raise ExecutionRejectedError("ADMISSION_CLOSED", None)
        raise AssertionError("test executor is only used for the explicit refusal case")

    def suspend(self) -> None:
        self.suspended = True


class _ParentWriter:
    def __init__(self) -> None:
        self.binding = ExecutionBinding(NamespaceRef("session-1", "run-writer"), "ws-" + "1" * 32)
        self.current_revision_id = "rev-" + "3" * 32
        self.read_only_profile = read_only_profile()
        self.client = _FakeClient()


def _parent(tmp_path: Path, *, role: str = "chat", enabled: bool = True) -> tuple[_ParentState, _ParentWriter]:
    db = SessionDatabase(tmp_path / "session.db", session_id="session-1")
    flags = FeatureFlags(
        subagent_spawning_enabled=enabled,
        subagent_chat_enabled=role == "chat",
        subagent_planner_enabled=role == "planner",
        subagent_coder_enabled=role == "coder",
        max_subagent_spawns_per_session=2,
    )
    return _ParentState(db, flags), _ParentWriter()


def _build_tool(tmp_path: Path, parent: _ParentState, writer: _ParentWriter, *, role: str = "chat"):
    workspace = tmp_path / "project"
    workspace.mkdir(exist_ok=True)
    log_dir = tmp_path / "session-log"
    log_dir.mkdir(exist_ok=True)
    writer.client.report_root = log_dir / "subagents"
    return managed_subagent.build_managed_subagent_tool(
        workspace_root=workspace,
        run_log_dir=log_dir,
        managed=writer,
        parent_state=parent,
        parent_role=role,
        chat_chain=SimpleNamespace(config=SimpleNamespace(family="fake-chat")),
        chat_compactor=None,
        limits=SimpleNamespace(bash_timeout_seconds=17),
        plan_ref=None,
        redactor=None,
    )


def test_managed_subagent_producer_uses_child_binding_and_releases_before_report(tmp_path: Path) -> None:
    """Producer kill check: remove child PIN/STOP or task-only drive wiring and this fails."""
    parent, writer = _parent(tmp_path)
    tool = _build_tool(tmp_path, parent, writer)
    captured: dict[str, Any] = {}
    _FakePort.instances.clear()
    _FakeExecutor.instances.clear()

    def fake_drive(task: str, **kwargs: Any) -> SessionOutcome:
        captured.update(kwargs)
        captured["task"] = task
        return SessionOutcome(0, "stopped_by_llm", 1, "Inspected only the requested task.")

    with (
        patch.object(managed_subagent, "get_current_session", return_value=parent),
        patch.object(managed_subagent, "ClientWorkspacePort", _FakePort),
        patch.object(managed_subagent, "ReadOnlyManagedBashExecutor", _FakeExecutor),
        patch.object(managed_subagent, "drive_session", side_effect=fake_drive),
    ):
        result = tool.handler({"task": "Inspect the import path"})

    assert result.error is None
    assert result.result["exit_code"] == 0
    assert result.result["files_changed"] == [] and result.result["patch_diff"] == ""
    assert captured["task"] == "Inspect the import path"
    assert captured["role"] == "subagent"
    assert captured["initial_memory_summary"] == ""
    assert captured["system_prompt_extra"] == ""
    assert captured["pinned_buffer"] is None
    assert captured["output"] is None
    child_state = captured["state"]
    assert child_state.managed_child is True
    assert child_state.workspace_io is _FakePort.instances[0]
    assert child_state.artifact_store is child_state.blackboard is child_state.telemetry is None
    assert child_state.pty_pool is child_state.worktree_manager is None
    assert set(captured["registry"].names()) == {"fs_read_file", "fs_run_bash"}
    assert writer.client.pin_calls[0][0].namespace.parent_run_id == writer.binding.namespace.run_id
    assert writer.client.pin_calls[0][1] == writer.current_revision_id
    assert writer.client.stop_calls[0][0] == writer.client.pin_calls[0][0].namespace
    assert _FakePort.instances[0].suspended and _FakeExecutor.instances[0].suspended
    assert parent.spawn_count == 1 and parent.active_count == 0

    report_path = tmp_path / "session-log" / "subagents" / result.result["task_id"] / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["notes"] == ["Inspected only the requested task."]
    assert report["token_usage"] == {}
    assert report["artifact_refs"] == []
    assert report["files_changed"] == []
    assert report_path.is_relative_to(tmp_path / "session-log")
    assert not report_path.is_relative_to(tmp_path / "project")
    assert os.stat(report_path).st_mode & 0o777 == 0o600


def test_managed_subagent_flag_and_profile_gates_happen_before_pin(tmp_path: Path) -> None:
    """Edge kill check: the default-off role flag and interactive profile never reach PIN_READER."""
    parent, writer = _parent(tmp_path, enabled=False)
    tool = _build_tool(tmp_path, parent, writer)
    with patch.object(managed_subagent, "get_current_session", return_value=parent):
        result = tool.handler({"task": "read"})
    assert result.error is not None and result.error.code == "disabled"
    assert writer.client.pin_calls == []
    assert parent.spawn_count == parent.active_count == 0

    parent, writer = _parent(tmp_path, enabled=True)
    writer.read_only_profile = SimpleNamespace(interactive=True)
    tool = _build_tool(tmp_path, parent, writer)
    with patch.object(managed_subagent, "get_current_session", return_value=parent):
        result = tool.handler({"task": "read"})
    assert result.error is not None and result.error.code == "subagent_profile_unavailable"
    assert writer.client.pin_calls == []
    assert parent.spawn_count == parent.active_count == 0


@pytest.mark.parametrize("role", ["chat", "planner", "coder"])
def test_production_caller_registers_managed_child_only_for_managed_stages(tmp_path: Path, role: str) -> None:
    """Caller-edge kill check for _cmd_run's managed registry registration seam."""
    parent, writer = _parent(tmp_path, role=role)
    workspace = tmp_path / "project"
    workspace.mkdir()
    run_log_dir = tmp_path / "logs"
    registry = ToolRegistry()
    stage_lease = SimpleNamespace(managed=writer, plan_ref=None)
    wired = _register_managed_subagent_tool(
        registry,
        role=role,
        workspace_root=workspace,
        run_log_dir=run_log_dir,
        workspace_io=object(),
        stage_lease=stage_lease,
        parent_state=parent,
        chat_chain=None,
        chat_compactor=None,
        limits=SimpleNamespace(bash_timeout_seconds=10),
        redactor=None,
    )
    assert wired.lookup("fs_spawn_subagent").name == "fs_spawn_subagent"
    assert wired.lookup("fs_spawn_subagent").input_schema["required"] == ["task"]
    assert set(wired.lookup("fs_spawn_subagent").input_schema["properties"]) == {"task"}


def test_subagent_child_exec_refusal_has_no_host_subprocess_or_writer_handoff(tmp_path: Path) -> None:
    """Producer negative probe: one managed EXEC refusal, then terminal cleanup, with zero host fallback."""
    parent, writer = _parent(tmp_path)
    tool = _build_tool(tmp_path, parent, writer)
    _FakeExecutor.reject_exec = True
    _FakeExecutor.counters = {
        "exec_allowed": 0,
        "cell_launches": 0,
        "host_subprocesses": 0,
        "proxy_credentials": 0,
        "project_writes": 0,
    }
    child_registry: ToolRegistry | None = None

    def fake_drive(task: str, **kwargs: Any) -> SessionOutcome:
        nonlocal child_registry
        child_registry = kwargs["registry"]
        # Q130: the managed child has no runtime IntentGuard seat. The READ
        # mount remains the authority for project writes.
        from fa.inner_loop.hooks.intent_guard import IntentGuard

        assert not any(isinstance(hook, IntentGuard) for chain in kwargs["hooks"]._chains.values() for hook in chain)
        kwargs["hooks"].dispatch(
            LifecyclePoint.BEFORE_TOOL_EXEC,
            HookPayload(
                tool_call=ToolCall("fs_run_bash", {"command": "printf note > /scratch/note.txt"}),
                role="subagent",
            ),
        )
        # The production fs_run_bash builder receives the child's read-only
        # managed executor. Its refusal must be returned directly, not retried
        # through the legacy subprocess fallback.
        tool_result = child_registry.lookup("fs_run_bash").handler({"command": "printf read-only-probe"})
        return SessionOutcome(0, "stopped_by_llm", 1, "The managed command was refused.", (tool_result,))

    with (
        patch.object(managed_subagent, "get_current_session", return_value=parent),
        patch.object(managed_subagent, "ClientWorkspacePort", _FakePort),
        patch.object(managed_subagent, "ReadOnlyManagedBashExecutor", _FakeExecutor),
        patch.object(managed_subagent, "drive_session", side_effect=fake_drive),
        patch("fa.inner_loop.tools.run_bash.subprocess.run") as host_run,
    ):
        result = tool.handler({"task": "Probe managed Bash admission"})

    _FakeExecutor.reject_exec = False
    assert result.error is None
    assert result.result["exit_code"] == 0
    assert any("execution_rejected" in item for item in result.result["evidence"])
    assert _FakeExecutor.counters == {
        "exec_requests": 1,
        "exec_allowed": 0,
        "cell_launches": 0,
        "host_subprocesses": 0,
        "proxy_credentials": 0,
        "project_writes": 0,
    }
    host_run.assert_not_called()
    assert child_registry is not None
    assert writer.client.stop_calls, "the reader must be stopped even after EXEC denial"
    assert parent.active_count == 0
    # No handoff API exists on the fake writer binding, and the child namespace
    # is the only namespace used by the pinned reader.
    assert writer.client.pin_calls[0][0].namespace != writer.binding.namespace


def test_subagent_role_flags_are_independent_and_master_gated() -> None:
    """Default-off and per-role gates remain independent for all production callers."""
    defaults = load_feature_flags("feature_flags: {}\n").flags
    assert not defaults.subagent_spawning_enabled
    assert not any(defaults.subagent_enabled_for(role) for role in ("chat", "planner", "coder"))
    configured = load_feature_flags(
        "feature_flags:\n"
        "  subagent_spawning_enabled: true\n"
        "  subagent:\n"
        "    chat:\n"
        "      enabled: true\n"
        "    planner:\n"
        "      enabled: false\n"
        "    coder:\n"
        "      enabled: true\n"
    ).flags
    assert configured.subagent_enabled_for("chat")
    assert not configured.subagent_enabled_for("planner")
    assert configured.subagent_enabled_for("coder")

    flags = FeatureFlags()
    assert not any(flags.subagent_enabled_for(role) for role in ("chat", "planner", "coder"))
    flags = FeatureFlags(
        subagent_spawning_enabled=True,
        subagent_chat_enabled=True,
        subagent_planner_enabled=False,
        subagent_coder_enabled=True,
    )
    assert flags.subagent_enabled_for("chat")
    assert not flags.subagent_enabled_for("planner")
    assert flags.subagent_enabled_for("coder")
    assert not flags.subagent_enabled_for("eval")


def test_managed_subagent_report_is_schema_valid_and_bounded() -> None:
    """Report output is capped, records child failure, and cannot claim project mutations."""
    outcome = SessionOutcome(
        1,
        "iteration_cap",
        4,
        "final note " * 2_000,
        tuple(ToolResult.fail("denied", "bounded evidence " * 100) for _ in range(20)),
    )
    report = managed_subagent._make_report(
        outcome,
        child_run_id="run-child",
        parent_run_id="run-parent",
        parent_role="coder",
        duration_ms=123,
        redactor=None,
    )
    encoded = report.to_json()
    assert len(encoded) <= 8_000
    payload = json.loads(encoded)
    assert payload["exit_code"] == 1
    assert payload["terminal_state"] == "iteration_cap"
    assert payload["next_action"] == "needs-human"
    assert payload["files_changed"] == []
    assert payload["patch_diff"] == ""
    assert payload["token_usage"] == {}
    assert payload["evidence"]
