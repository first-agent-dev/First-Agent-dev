"""Q97: an active/broken guard cannot derive managed metadata from the host."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fa import cli
from fa.execution.tool_port import ClientWorkspacePort
from fa.execution.types import Access, Operation, ViewPurpose
from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.tools import mutation_guard
from tests.test_execution_client_port import _plan_ref, _served, _socket_client
from tests.test_execution_views import source as view_source
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site


@pytest.mark.parametrize("tool", ["write", "edit"])
@pytest.mark.parametrize("board", ["active", "unavailable", "disabled"])
def test_managed_guard_does_not_read_host_metadata_or_silently_drop_enabled_board(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool: str, board: str
) -> None:
    """C1: real role registry + session + UDS; both mutation tools share policy."""
    original = "BEFORE\n"
    (site.source / "f.txt").write_text(original)
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=Access.WRITE, purpose=ViewPurpose.PROJECT, base_revision=managed.grant.revision_id, plan_ref=plan
        )
        assert grant.view_ref is not None
        client = _socket_client(site, tmp_path)
        port = ClientWorkspacePort(client, namespace=managed.binding.namespace, view=grant.view_ref, grant=grant)
        registry = cli._build_role_registry("coder", site.source, bash_timeout_seconds=2, workspace_io=port)
        flags = FeatureFlags(blackboard_enabled=board != "disabled")
        state = SessionState(
            workspace_root=site.source,
            run_id="guard-test",
            log=EventLog(tmp_path / "logs" / "events.jsonl", run_id="guard-test"),
            feature_flags=flags,
            workspace_io=port,
        )
        assert (state.blackboard is not None) is (board != "disabled")
        if board == "unavailable":
            state.blackboard = None  # model an enabled board whose initialization failed
        host_lookups: list[str] = []

        def forbidden(*args: Any, **kwargs: Any) -> Any:
            host_lookups.append("metadata")
            raise AssertionError("host metadata must not be consulted")

        monkeypatch.setattr(mutation_guard, "_entry_for", forbidden)
        monkeypatch.setattr(mutation_guard, "belongs_to_workspace", forbidden)
        path = "new.txt" if tool == "write" else "f.txt"
        params = (
            {"path": path, "content": "AFTER\n"}
            if tool == "write"
            else {
                "path": path,
                "old_string": "BEFORE",
                "new_string": "AFTER",
            }
        )
        call = ToolCall(name=f"fs_{tool}_file", params=params, call_id="guard-1")
        result = run_session([call], registry=registry, hooks=HookRegistry(), state=state)[0]
        assert host_lookups == []
        private = view_source(site, grant) / path
        if board == "disabled":
            assert result.error is None
            assert client.sent.count(Operation.WRITE_FILE) == 1
            assert private.read_text() == "AFTER\n"
        else:
            assert result.error is not None and result.error.code == "blackboard_unavailable"
            assert result.error.retryable is False
            assert client.sent.count(Operation.WRITE_FILE) == 0
            assert private.read_text() == original if tool == "edit" else not private.exists()
        assert (site.source / "f.txt").read_text() == original
        assert not (site.source / "new.txt").exists()


@pytest.mark.parametrize("tool", ["write", "edit"])
def test_managed_context_failure_never_becomes_permission(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool: str
) -> None:
    """C3: unexpected context lookup failure is not an absent/disabled board."""
    (site.source / "f.txt").write_text("BEFORE\n")
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=Access.WRITE, purpose=ViewPurpose.PROJECT, base_revision=managed.grant.revision_id, plan_ref=plan
        )
        assert grant.view_ref is not None
        client = _socket_client(site, tmp_path)
        port = ClientWorkspacePort(client, namespace=managed.binding.namespace, view=grant.view_ref, grant=grant)
        registry = cli._build_role_registry("coder", site.source, bash_timeout_seconds=2, workspace_io=port)
        import fa.inner_loop.context as context

        def broken() -> Any:
            raise RuntimeError("context failure")

        monkeypatch.setattr(context, "get_current_session", broken)
        spec = registry.lookup(f"fs_{tool}_file")
        assert spec is not None
        params = (
            {"path": "new.txt", "content": "AFTER\n"}
            if tool == "write"
            else {
                "path": "f.txt",
                "old_string": "BEFORE",
                "new_string": "AFTER",
            }
        )
        result = spec.handler(params)
        assert result.error is not None and result.error.code == "blackboard_unavailable"
        assert result.error.retryable is False and Operation.WRITE_FILE not in client.sent
        assert (view_source(site, grant) / "f.txt").read_text() == "BEFORE\n"
        assert not (view_source(site, grant) / "new.txt").exists()


def test_managed_post_record_never_uses_host_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        calls.append("access")
        raise AssertionError("metadata lookup")

    monkeypatch.setattr(mutation_guard, "belongs_to_workspace", forbidden)
    monkeypatch.setattr(mutation_guard, "_entry_for", forbidden)
    mutation_guard.record_mutation(object(), read_set=[], write_set=["f"], root=tmp_path, managed=True)
    assert calls == []


def test_managed_foreign_or_unbound_board_is_not_host_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("board or host metadata was consulted")

    monkeypatch.setattr(mutation_guard, "belongs_to_workspace", forbidden)
    monkeypatch.setattr(mutation_guard, "_entry_for", forbidden)
    denial = mutation_guard.check_mutation_allowed(object(), read_set=[], write_set=["f"], root=tmp_path, managed=True)
    assert denial is not None and denial.error is not None
    assert denial.error.code == "blackboard_unavailable" and not denial.error.retryable
