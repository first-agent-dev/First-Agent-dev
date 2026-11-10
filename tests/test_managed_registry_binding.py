"""STEP2b registry binding: real supervisor view, no legacy bash or host writes."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from fa import cli
from fa.execution.client import ManagedBashExecutor
from fa.execution.tool_port import ClientWorkspacePort
from fa.execution.types import Access, Operation, ViewPurpose
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.registry import ToolResult
from fa.inner_loop.tools import run_bash
from tests.test_execution_client import SHA
from tests.test_execution_client_port import _plan_ref, _served
from tests.test_execution_tool_port import _call
from tests.test_execution_views import native_profile
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site


@pytest.mark.parametrize("role", ["coder", "chat", "planner", "eval"])
def test_real_registry_role_binds_view_and_bash_without_host_effects(
    role: str, site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan_ref(site)
    host_calls: list[object] = []

    def forbidden(*args: Any, **kwargs: Any) -> None:
        host_calls.append((args, kwargs))
        raise AssertionError("host subprocess executed")

    monkeypatch.setattr(subprocess, "run", forbidden)
    with _served(site, tmp_path) as managed:
        operations: list[object] = []
        request = managed.client.request

        def recorded(operation: Any, **kwargs: Any) -> dict[str, Any]:
            operations.append(operation)
            return request(operation, **kwargs)

        monkeypatch.setattr(managed.client, "request", recorded)
        grant = managed.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.PROJECT,
            base_revision=managed.grant.revision_id,
            plan_ref=plan,
        )
        assert grant.view_ref is not None
        port = ClientWorkspacePort(
            managed.client, namespace=managed.binding.namespace, view=grant.view_ref, grant=grant
        )
        executor = ManagedBashExecutor(
            managed.client,
            namespace=managed.binding.namespace,
            view=grant.view_ref,
            grant=grant,
            profile=native_profile(),
            input_tree_sha256=SHA,
            plan_sha256=plan.sha256,
            original_revision_id=grant.view_ref.base_revision,
            controller_root=site.source,
        )
        registry = cli._build_run_tool_registry(
            role,
            site.source,
            bash_timeout_seconds=2,
            draft_store=PrDraftStore(tmp_path / "draft"),
            workspace_io=port,
            managed_executor=executor,
        )
        assert "fs_spawn_subagent" not in registry.names()
        assert not {"fs_checkpoint", "fs_undo", "fs_diff"}.intersection(registry.names())
        if role != "eval":
            name = "knowledge/research/stage.md" if role == "planner" else "src/stage.py"
            write = registry.lookup("fs_write_file")
            assert write is not None
            written = _call(write, {"path": name, "content": "from managed view\n"})
            assert written.error is None, written.error
            assert not (site.source / name).exists()
            assert port.read_file(name).content == "from managed view\n"
            read = registry.lookup("fs_read_file")
            observed = _call(read, {"path": name})
            assert observed.error is None and "from managed view" in str(observed.result)
            if role == "planner":
                denied = _call(write, {"path": "src/forbidden.py", "content": "forbidden"})
                assert denied.error is not None
                assert not (site.source / "src/forbidden.py").exists()
            if role in {"coder", "chat"}:
                edit = registry.lookup("fs_edit_file")
                changed = _call(edit, {"path": name, "old_string": "managed", "new_string": "isolated"})
                assert changed.error is None
                assert port.read_file(name).content == "from isolated view\n"
        if role != "planner":
            bash = registry.lookup("fs_run_bash")
            assert bash is not None
            answer = _call(bash, {"command": "touch host"})
            assert answer.error is not None and answer.error.code == "execution_unavailable"
            assert not answer.error.retryable
            assert operations.count(Operation.EXEC) == 1
        assert host_calls == [] and not (site.source / "host").exists()


@pytest.mark.parametrize("role", ["coder", "chat", "planner", "eval"])
def test_managed_profile_build_failure_is_not_replaced_by_host_fallback(
    role: str, site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop import profiles

    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.PROJECT,
            base_revision=managed.grant.revision_id,
            plan_ref=plan,
        )
        assert grant.view_ref is not None
        port = ClientWorkspacePort(
            managed.client, namespace=managed.binding.namespace, view=grant.view_ref, grant=grant
        )

        def broken(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("profile assembly failed")

        monkeypatch.setattr(profiles, "build_registry_for_role", broken)
        with pytest.raises(RuntimeError, match="profile assembly failed"):
            cli._build_role_registry(role, site.source, bash_timeout_seconds=2, workspace_io=port)


def test_missing_managed_bash_never_becomes_host_bash(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan_ref(site)
    host_calls: list[object] = []

    def forbidden(*args: Any, **kwargs: Any) -> None:
        host_calls.append((args, kwargs))
        raise AssertionError("host subprocess executed")

    monkeypatch.setattr(subprocess, "run", forbidden)
    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.PROJECT,
            base_revision=managed.grant.revision_id,
            plan_ref=plan,
        )
        assert grant.view_ref is not None
        port = ClientWorkspacePort(
            managed.client, namespace=managed.binding.namespace, view=grant.view_ref, grant=grant
        )
        registry = cli._build_role_registry("coder", site.source, bash_timeout_seconds=2, workspace_io=port)
        bash = registry.lookup("fs_run_bash")
        assert bash is not None
        answer = _call(bash, {"command": "touch host"})
        assert answer.error is not None and answer.error.code == "execution_unavailable"
        assert not answer.error.retryable
        assert host_calls == [] and not (site.source / "host").exists()


def test_missing_planner_limit_never_falls_back_to_full_write(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop import profiles

    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=Access.WRITE, purpose=ViewPurpose.PROJECT, base_revision=managed.grant.revision_id, plan_ref=plan
        )
        assert grant.view_ref is not None
        port = ClientWorkspacePort(
            managed.client, namespace=managed.binding.namespace, view=grant.view_ref, grant=grant
        )
        real_builders = profiles._build_tool_builders

        def without_limit(*args: Any, **kwargs: Any) -> Any:
            builders = real_builders(*args, **kwargs)
            assert "fs_write_file" in builders
            del builders["fs_write_file_limited"]
            return builders

        monkeypatch.setattr(profiles, "_build_tool_builders", without_limit)
        with pytest.raises(RuntimeError, match="managed tool unavailable: fs_write_file"):
            cli._build_role_registry("planner", site.source, bash_timeout_seconds=2, workspace_io=port)


@pytest.mark.parametrize("role", ["chat", "planner", "coder", "eval"])
def test_unmanaged_product_run_registries_omit_legacy_host_subagent(
    role: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Q126-A EDGE oracle: ordinary role registries cannot dispatch the old host runner."""
    from fa.inner_loop.subagent_runner import SubagentRunner

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runner_calls: list[object] = []

    def forbidden_runner(self: Any, *args: Any, **kwargs: Any) -> Any:
        runner_calls.append((self, args, kwargs))
        raise AssertionError("legacy host SubagentRunner reached from a product registry")

    monkeypatch.setattr(SubagentRunner, "run_stateless", forbidden_runner)
    registry = cli._build_run_tool_registry(
        role,
        workspace,
        bash_timeout_seconds=2,
        draft_store=PrDraftStore(tmp_path / "draft"),
    )

    assert "fs_spawn_subagent" not in registry.names()
    assert runner_calls == []
    assert not (workspace / ".fa" / "subagents").exists()


def test_session_state_rejects_isolated_worktree_without_git_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Q126-A producer oracle: the actual SessionState caller never creates a Git worktree."""
    from fa.feature_flags import FeatureFlags
    from fa.inner_loop.state import SessionState

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    git_calls: list[object] = []

    def record_git(*args: Any, **kwargs: Any) -> Any:
        git_calls.append((args, kwargs))
        raise AssertionError("isolated host-Git producer reached from SessionState")

    monkeypatch.setattr(subprocess, "run", record_git)
    state = SessionState(
        workspace_root=workspace,
        run_id="q126-isolated-refusal",
        feature_flags=FeatureFlags(worktree_mode="isolated"),
    )

    assert state.worktree_manager is None
    assert git_calls == []
    assert not (workspace / ".fa" / "worktrees").exists()
    log = state.log
    assert log is not None
    assert any(
        event.kind == "config_warning" and event.content.get("key") == "worktree.mode" for event in log.read_all()
    )


def test_missing_explicit_executor_fails_closed_through_production_chat_session(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R11 C1 oracle: a live managed view with no Bash executor never becomes host Bash."""
    import json

    from fa.feature_flags import FeatureFlags
    from fa.inner_loop.artifacts import ArtifactStore
    from fa.inner_loop.coder_loop import drive_session
    from fa.inner_loop.runtime_limits import RuntimeLimits
    from fa.inner_loop.session_db import SessionDatabase
    from fa.inner_loop.state import EventLog, SessionState
    from fa.providers.base import ResponseInfo
    from fa.providers.chain import ChainConfig, ChainEntry, ProviderChain

    plan = _plan_ref(site)
    fallback_calls: list[tuple[Any, ...]] = []
    host_process_calls: list[tuple[Any, ...]] = []

    def trapped_fallback(*args: Any, **_kwargs: Any) -> Any:
        fallback_calls.append(args)
        return ToolResult.fail("mutant_host_fallback", "host fallback tripwire", retryable=False)

    def trapped_subprocess(*args: Any, **_kwargs: Any) -> Any:
        host_process_calls.append(args)
        raise AssertionError("host subprocess tripwire reached")

    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.PROJECT,
            base_revision=managed.grant.revision_id,
            plan_ref=plan,
        )
        assert grant.view_ref is not None
        port = ClientWorkspacePort(
            managed.client, namespace=managed.binding.namespace, view=grant.view_ref, grant=grant
        )
        operations: list[Operation] = []
        original_request = managed.client.request

        def record_request(operation: Operation, **kwargs: Any) -> dict[str, Any]:
            operations.append(operation)
            return original_request(operation, **kwargs)

        monkeypatch.setattr(managed.client, "request", record_request)
        monkeypatch.setattr(run_bash, "_run_subprocess_fallback", trapped_fallback)
        monkeypatch.setattr(subprocess, "run", trapped_subprocess)

        run_id = managed.binding.namespace.run_id
        session_id = managed.binding.namespace.session_id
        session_db = SessionDatabase(tmp_path / "r11-session.db", session_id=session_id)
        log = EventLog(
            tmp_path / "r11-run" / "events.jsonl",
            run_id=run_id,
            session_db=session_db,
            session_id=session_id,
        )
        monkeypatch.setattr("fa.runtime.PtyPool", lambda **_kwargs: None)
        state = SessionState(
            workspace_root=site.source,
            session_id=session_id,
            run_id=run_id,
            log=log,
            session_db=session_db,
            feature_flags=FeatureFlags(blackboard_enabled=False, telemetry_enabled=False),
            artifact_store=ArtifactStore(tmp_path / "r11-artifacts"),
            workspace_io=port,
        )
        limits = RuntimeLimits.anchored_defaults()
        registry = cli._build_run_tool_registry(
            "chat",
            site.source,
            bash_timeout_seconds=limits.bash_timeout_seconds,
            draft_store=PrDraftStore(tmp_path / "r11-draft.md"),
            workspace_io=port,
            managed_executor=None,
        )
        output_bus_ref: list[Any] = []
        hooks = cli._build_run_hook_registry(
            workspace=site.source,
            log=log,
            limits=limits,
            redactor=None,
            run_log_dir=tmp_path / "r11-run",
            output_bus_ref=output_bus_ref,
            managed_workspace=True,
        )

        class ScriptedProvider:
            name = "scripted"

            def __init__(self) -> None:
                self.calls: list[Any] = []

            def request(self, request: Any, **_kwargs: Any) -> ResponseInfo:
                self.calls.append(request)
                if len(self.calls) == 1:
                    offered = {
                        str(tool.get("function", {}).get("name", ""))
                        for tool in request.tools
                        if isinstance(tool.get("function"), dict)
                    }
                    assert "fs_run_bash" in offered, "production chat registry lost its role-assigned Bash tool"
                    call = {
                        "id": "r11-managed-bash",
                        "type": "function",
                        "function": {
                            "name": "fs_run_bash",
                            "arguments": json.dumps({"command": "touch r11-host-marker"}),
                        },
                    }
                    return ResponseInfo("", 1, 1, "tool_calls", (call,))
                assert len(self.calls) == 2
                return ResponseInfo("managed refusal recorded", 1, 1, "stop")

        scripted = ScriptedProvider()
        chain_config = ChainConfig(
            role="chat",
            name="r11-test-model",
            family="openai",
            chain=(
                ChainEntry(
                    provider="openrouter",
                    model="test/model",
                    base_url="https://example.invalid/v1",
                    api_key_env="K",
                ),
            ),
        )
        chain = ProviderChain(chain_config, provider_factory=lambda _entry: scripted, env={"K": "sk-test-live"})
        outcome = drive_session(
            "probe missing managed executor",
            provider_chain=chain,
            registry=registry,
            hooks=hooks,
            state=state,
            role="chat",
            acting_family="openai",
            limits=limits,
            max_turns=2,
        )
        rows = session_db.read_event_rows(run_id=run_id)
        bash_results = [
            row["content"] for row in rows if row["kind"] == "tool_result" and row["tool_name"] == "fs_run_bash"
        ]
        assert outcome.exit_code == 0 and len(scripted.calls) == 2
        assert len(bash_results) == 1
        assert fallback_calls == [] and host_process_calls == []
        assert bash_results[0]["ok"] is False
        assert bash_results[0]["error"]["code"] == "execution_unavailable"
        assert bash_results[0]["error"]["retryable"] is False
        assert operations.count(Operation.EXEC) == 0
        assert not (site.source / "r11-host-marker").exists()
        port.suspend()
        # The local no-backend fixture ends with this test; release is not part
        # of R11, and a stopped WRITE view is not a settled publication.
        assert managed.stop_view(grant)
