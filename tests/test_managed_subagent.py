"""Producer and caller-edge tests for the managed R13 child capability.

These tests exercise the production child tool factory and the CLI registration
seam. The fake EXEC denial is a producer/edge kill check only; the S4P1 R13
negative oracle still requires the real local supervisor/backend and its counters.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar, override
from unittest.mock import patch

import pytest

from fa.cli import _ManagedStageLease, _register_managed_subagent_tool
from fa.execution.client import ExecutionClient, ExecutionRejectedError, ManagedBashExecutor, ManagedProjectToolExecutor
from fa.execution.composition import ExecutionBinding, ManagedExecution
from fa.execution.tool_port import ClientWorkspacePort
from fa.execution.types import Access, GrantReply, NamespaceRef, Operation, ViewPurpose, ViewRef
from fa.feature_flags import FeatureFlags, load_feature_flags
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.hooks.base import HookPayload, LifecyclePoint
from fa.inner_loop.registry import ToolCall, ToolRegistry, ToolResult, ToolSpec
from fa.inner_loop.runtime_limits import RuntimeLimits
from fa.inner_loop.session_db import SessionDatabase
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.tools import managed_subagent
from fa.observability.redaction import SecretRedactor
from fa.providers import ProviderChain
from fa.providers.chain import ChainConfig, ChainEntry
from tests.test_execution_views import native_profile, read_only_profile


class _ParentState(SessionState):
    def __init__(self, db: SessionDatabase, flags: FeatureFlags, *, role_run_id: str = "run-parent") -> None:
        flags = replace(flags, blackboard_enabled=False, telemetry_enabled=False)
        super().__init__(
            workspace_root=db.path.parent,
            session_id="session-1",
            run_id=role_run_id,
            session_db=db,
            log=EventLog(db.path.parent / "events.jsonl", session_db=db, session_id="session-1", run_id=role_run_id),
            feature_flags=flags,
        )

    @property
    def spawn_count(self) -> int:
        return self.get_subagent_spawns()

    @property
    def active_count(self) -> int:
        return self.get_active_subagents()


class _FakeClient(ExecutionClient):
    def __init__(self, tmp_path: Path) -> None:
        super().__init__(tmp_path / "supervisor.sock", server_uid=os.getuid(), rpc_timeout_ms=100)
        self.pin_calls: list[tuple[ExecutionBinding, str, Any]] = []
        self.stop_calls: list[tuple[NamespaceRef, ViewRef]] = []
        self.report_root: Path | None = None

    @override
    def pin_reader(
        self,
        binding: object,
        revision_id: str,
        *,
        plan_ref: Any = None,
        deadline: float | None = None,
    ) -> GrantReply:
        assert isinstance(binding, ExecutionBinding)
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

    @override
    def stop_view(
        self,
        namespace: NamespaceRef,
        *,
        view: ViewRef,
        grant: GrantReply,
        deadline: float | None = None,
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


class _ParentWriter(ManagedExecution):
    def __init__(self, tmp_path: Path) -> None:
        binding = ExecutionBinding(NamespaceRef("session-1", "run-writer"), "ws-" + "1" * 32)
        grant = GrantReply(Operation.ACQUIRE_WRITER, "c" * 64, None, 1, "rev-" + "3" * 32)
        super().__init__(
            _FakeClient(tmp_path), binding, grant, view_profile=native_profile(), read_only_profile=read_only_profile()
        )

    @property
    def fake_client(self) -> _FakeClient:
        assert isinstance(self.client, _FakeClient)
        return self.client


def _parent(tmp_path: Path, *, role: str = "chat", enabled: bool = True) -> tuple[_ParentState, _ParentWriter]:
    db = SessionDatabase(tmp_path / "session.db", session_id="session-1")
    flags = FeatureFlags(
        subagent_spawning_enabled=enabled,
        subagent_chat_enabled=role == "chat",
        subagent_planner_enabled=role == "planner",
        subagent_coder_enabled=role == "coder",
        max_subagent_spawns_per_session=2,
    )
    return _ParentState(db, flags), _ParentWriter(tmp_path)


def _build_tool(
    tmp_path: Path, parent: _ParentState, writer: _ParentWriter, *, role: str = "chat", with_provider: bool = True
) -> ToolSpec:
    def no_network(_entry: ChainEntry) -> Any:
        raise AssertionError("provider IO is not permitted in this fixture")

    chain = ProviderChain(
        ChainConfig(
            role="chat",
            name="fake-chat",
            family="openai",
            chain=(ChainEntry("openrouter", "test/model", "https://example.invalid/v1", "K"),),
        ),
        provider_factory=no_network,
        env={"K": "sk-test-live"},
    )
    workspace = tmp_path / "project"
    workspace.mkdir(exist_ok=True)
    log_dir = tmp_path / "session-log"
    log_dir.mkdir(exist_ok=True)
    writer.fake_client.report_root = log_dir / "subagents"
    return managed_subagent.build_managed_subagent_tool(
        workspace_root=workspace,
        run_log_dir=log_dir,
        managed=writer,
        parent_state=parent,
        parent_role=role,
        chat_chain=chain if with_provider else None,
        chat_compactor=None,
        limits=RuntimeLimits(bash_timeout_seconds=17),
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
    assert result.result is not None
    assert result.result["exit_code"] == 0
    assert result.result["files_changed"] == [] and result.result["patch_diff"] == ""
    assert captured["task"] == "Inspect the import path"
    assert captured["role"] == "subagent"
    assert isinstance(captured["provider_chain"], ProviderChain)
    assert captured["provider_chain"].config.name == "fake-chat"
    assert captured["acting_family"] == "openai"
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
    assert writer.fake_client.pin_calls[0][0].namespace.parent_run_id == writer.binding.namespace.run_id
    assert writer.fake_client.pin_calls[0][1] == writer.current_revision_id
    assert writer.fake_client.stop_calls[0][0] == writer.fake_client.pin_calls[0][0].namespace
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
    assert writer.fake_client.pin_calls == []
    assert parent.spawn_count == parent.active_count == 0

    parent, writer = _parent(tmp_path, enabled=True)
    writer.read_only_profile = replace(read_only_profile(), interactive=True)
    tool = _build_tool(tmp_path, parent, writer)
    with patch.object(managed_subagent, "get_current_session", return_value=parent):
        result = tool.handler({"task": "read"})
    assert result.error is not None and result.error.code == "subagent_profile_unavailable"
    assert writer.fake_client.pin_calls == []
    assert parent.spawn_count == parent.active_count == 0


def test_missing_managed_child_provider_refuses_before_pin_or_reservation(tmp_path: Path) -> None:
    parent, writer = _parent(tmp_path)
    tool = _build_tool(tmp_path, parent, writer, with_provider=False)
    with patch.object(managed_subagent, "get_current_session", return_value=parent):
        result = tool.handler({"task": "read"})
    assert result.error is not None and result.error.code == "subagent_provider_unavailable"
    assert writer.fake_client.pin_calls == [] and writer.fake_client.stop_calls == []
    assert parent.spawn_count == parent.active_count == 0


@pytest.mark.parametrize("role", ["chat", "planner", "coder"])
def test_production_caller_registers_managed_child_only_for_managed_stages(tmp_path: Path, role: str) -> None:
    """Caller-edge kill check for _cmd_run's managed registry registration seam."""
    parent, writer = _parent(tmp_path, role=role)
    workspace = tmp_path / "project"
    workspace.mkdir()
    run_log_dir = tmp_path / "logs"
    registry = ToolRegistry()
    namespace = writer.binding.namespace
    view = ViewRef(
        writer.binding.workspace_id,
        "view-" + "4" * 32,
        writer.current_revision_id,
        namespace.run_id,
        1,
        Access.WRITE,
        ViewPurpose.PROJECT,
    )
    grant = GrantReply(Operation.CREATE_VIEW, "d" * 64, view, None, None, "e" * 64)
    port = ClientWorkspacePort(writer.client, namespace=namespace, view=view, grant=grant)
    profile = native_profile()
    bash = ManagedBashExecutor(
        writer.client,
        namespace=namespace,
        view=view,
        grant=grant,
        profile=profile,
        input_tree_sha256="e" * 64,
        plan_sha256=None,
        original_revision_id=writer.current_revision_id,
        controller_root=workspace,
    )
    tools = ManagedProjectToolExecutor(
        writer.client,
        namespace=namespace,
        view=view,
        grant=grant,
        profile=profile,
        input_tree_sha256="e" * 64,
        plan_sha256=None,
        original_revision_id=writer.current_revision_id,
    )
    stage_lease = _ManagedStageLease(
        managed=writer,
        namespace=namespace,
        view_grant=grant,
        workspace_io=port,
        managed_executor=bash,
        project_tool_executor=tools,
        plan_ref=None,
        allow_nested_handoff=False,
    )
    wired = _register_managed_subagent_tool(
        registry,
        role=role,
        workspace_root=workspace,
        run_log_dir=run_log_dir,
        workspace_io=port,
        stage_lease=stage_lease,
        parent_state=parent,
        chat_chain=None,
        chat_compactor=None,
        limits=RuntimeLimits(bash_timeout_seconds=10),
        redactor=None,
    )
    from fa.inner_loop.registry import validate_tool_schema_portability

    spec = wired.lookup("fs_spawn_subagent")
    assert spec.name == "fs_spawn_subagent"
    validate_tool_schema_portability(spec.name, spec.input_schema)
    assert spec.max_context_bytes == 16_384
    assert spec.input_schema["required"] == ["task"]
    properties = spec.input_schema["properties"]
    assert isinstance(properties, dict)
    assert set(properties) == {"task"}


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
    assert result.result is not None
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
    assert writer.fake_client.stop_calls, "the reader must be stopped even after EXEC denial"
    assert parent.active_count == 0
    # The child namespace differs from the writer namespace; this local double
    # does not by itself prove the absence of a supervisor-side handoff.
    assert writer.fake_client.pin_calls[0][0].namespace != writer.binding.namespace


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


@pytest.mark.parametrize("role", ["chat", "planner", "coder"])
@pytest.mark.parametrize("master,role_enabled", [(False, False), (False, True), (True, False), (True, True)])
def test_managed_child_handler_requires_master_and_its_own_role_flag(
    tmp_path: Path, role: str, master: bool, role_enabled: bool
) -> None:
    parent, writer = _parent(tmp_path, role=role)
    assert parent.feature_flags is not None
    parent.feature_flags = replace(
        parent.feature_flags,
        subagent_spawning_enabled=master,
        subagent_chat_enabled=role == "chat" and role_enabled,
        subagent_planner_enabled=role == "planner" and role_enabled,
        subagent_coder_enabled=role == "coder" and role_enabled,
    )
    tool = _build_tool(tmp_path, parent, writer, role=role)
    with (
        patch.object(managed_subagent, "get_current_session", return_value=parent),
        patch.object(managed_subagent, "ClientWorkspacePort", _FakePort),
        patch.object(managed_subagent, "ReadOnlyManagedBashExecutor", _FakeExecutor),
        patch.object(
            managed_subagent,
            "drive_session",
            return_value=SessionOutcome(0, "stopped_by_llm", 1, "Done."),
        ),
    ):
        result = tool.handler({"task": "Inspect the project"})
    if master and role_enabled:
        assert result.error is None
        assert len(writer.fake_client.pin_calls) == len(writer.fake_client.stop_calls) == 1
    else:
        assert result.error is not None and result.error.code == "disabled"
        assert writer.fake_client.pin_calls == [] and writer.fake_client.stop_calls == []
    assert parent.active_count == 0


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


def test_managed_report_redaction_masks_and_withholds_on_error() -> None:
    secret = "sk-test-secret-value"
    redactor = SecretRedactor({"TOKEN": secret}, ["TOKEN"])
    assert secret not in managed_subagent._redact(redactor, f"found {secret}")
    with patch.object(redactor, "redact", side_effect=RuntimeError("mask failure")):
        assert managed_subagent._redact(redactor, secret) == "[output withheld: redaction failed]"


def test_managed_child_rejects_inherited_host_store_before_authority_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C3/R13: reject host-backed child dependencies before opening any authority."""
    from fa.inner_loop.artifacts import ArtifactStore

    host_store = ArtifactStore(tmp_path / "host-artifacts")
    authority_root = tmp_path / "forbidden-authority"
    roots_requested: list[Path] = []

    def state_root() -> Path:
        roots_requested.append(authority_root)
        return authority_root

    monkeypatch.setattr("fa.inner_loop.state.default_state_root", state_root)
    with pytest.raises(ValueError, match="managed child state cannot inherit host-backed"):
        SessionState(
            workspace_root=tmp_path,
            run_id="child-guard",
            managed_child=True,
            artifact_store=host_store,
        )
    assert roots_requested == []
    assert not authority_root.exists()


@pytest.mark.parametrize(
    "params",
    [{}, {"task": 42}, {"task": " \n"}, {"task": "\ud800"}, {"task": "é" * 8001}],
)
def test_managed_child_rejects_invalid_task_before_reservation_and_pin(
    params: dict[str, object], tmp_path: Path
) -> None:
    """C1/C3 R13: malformed or oversized UTF-8 tasks never reach child authority."""
    parent, writer = _parent(tmp_path)
    tool = _build_tool(tmp_path, parent, writer)
    with patch.object(managed_subagent, "get_current_session", return_value=parent):
        result = tool.handler(params)
    assert result.error is not None and result.error.code == "invalid_params"
    assert writer.fake_client.pin_calls == [] and writer.fake_client.stop_calls == []
    assert parent.spawn_count == parent.active_count == 0


def test_managed_child_accepts_exact_utf8_byte_limit_before_supervisor_refusal(tmp_path: Path) -> None:
    """C1 boundary: 16,000 encoded bytes reach PIN, whose refusal remains fail-closed."""
    parent, writer = _parent(tmp_path)
    tool = _build_tool(tmp_path, parent, writer)
    with (
        patch.object(managed_subagent, "get_current_session", return_value=parent),
        patch.object(
            writer.fake_client, "pin_reader", side_effect=ExecutionRejectedError("ADMISSION_CLOSED", None)
        ) as pin,
    ):
        result = tool.handler({"task": "é" * 8000})
    assert result.error is not None and result.error.code == "subagent_denied"
    assert pin.call_count == 1
    assert parent.spawn_count == 1 and parent.active_count == 0
    assert writer.fake_client.stop_calls == []
