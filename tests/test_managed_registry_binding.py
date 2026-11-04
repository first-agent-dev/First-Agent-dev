"""STEP2b registry binding: real supervisor view, no legacy bash or host writes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fa import cli
from fa.execution.client import ManagedBashExecutor
from fa.execution.tool_port import ClientWorkspacePort
from fa.execution.types import Access, Operation, ViewPurpose
from fa.inner_loop.pr_draft import PrDraftStore
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

    monkeypatch.setattr(run_bash.subprocess, "run", forbidden)
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

    monkeypatch.setattr(run_bash.subprocess, "run", forbidden)
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
