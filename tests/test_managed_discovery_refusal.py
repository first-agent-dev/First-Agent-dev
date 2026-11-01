"""Q97: real managed registries never index the controller's host project."""

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
from fa.inner_loop.tools import fs_reach, fs_search
from tests.test_execution_client_port import _plan_ref, _served, _socket_client
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site


@pytest.mark.parametrize("access", [Access.WRITE, Access.READ])
@pytest.mark.parametrize("name", ["fs_search", "fs_reach"])
def test_real_session_and_registry_refuse_discovery_without_host_index(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, access: Access, name: str
) -> None:
    """C1: actual UDS-granted view, paired event log, host-only sentinel and spies."""
    (site.source / "chain.py").write_text("def view_sentinel():\n    return 1\n")
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=access,
            purpose=ViewPurpose.PROJECT if access is Access.WRITE else ViewPurpose.VERIFICATION,
            base_revision=managed.grant.revision_id if access is Access.WRITE else None,
            plan_ref=plan,
        )
        assert grant.view_ref is not None
        client = _socket_client(site, tmp_path)
        port = ClientWorkspacePort(client, namespace=managed.binding.namespace, view=grant.view_ref, grant=grant)
        # Producer precondition: the selected view really is reachable over UDS.
        assert "view_sentinel" in port.read_file("chain.py").content
        assert client.sent == [Operation.READ_FILE]
        client.sent.clear()
        (site.source / "chain.py").write_text("def host_only_sentinel():\n    return 2\n")

        calls: list[str] = []
        search_holder, reach_holder = fs_search._IndexHolder, fs_reach._ReachHolder
        search_handle, reach_handle = fs_search._handle, fs_reach._handle

        def index(*args: Any, **kwargs: Any) -> Any:
            calls.append("search holder")
            return search_holder(*args, **kwargs)

        def structural(*args: Any, **kwargs: Any) -> Any:
            calls.append("reach holder")
            return reach_holder(*args, **kwargs)

        def search(*args: Any, **kwargs: Any) -> Any:
            calls.append("search indexer")
            return search_handle(*args, **kwargs)

        def reach(*args: Any, **kwargs: Any) -> Any:
            calls.append("reach indexer")
            return reach_handle(*args, **kwargs)

        monkeypatch.setattr(fs_search, "_IndexHolder", index)
        monkeypatch.setattr(fs_reach, "_ReachHolder", structural)
        monkeypatch.setattr(fs_search, "_handle", search)
        monkeypatch.setattr(fs_reach, "_handle", reach)
        registry = cli._build_role_registry("coder", site.source, bash_timeout_seconds=2, workspace_io=port)
        assert registry.lookup(name) is not None
        log = EventLog(tmp_path / "logs" / "events.jsonl", run_id="discovery")
        state = SessionState(
            workspace_root=site.source,
            run_id="discovery",
            log=log,
            feature_flags=FeatureFlags(blackboard_enabled=False),
            workspace_io=port,
        )
        params = (
            {"query": "host_only_sentinel", "output_mode": "files"}
            if name == "fs_search"
            else {"symbol": "host_only_sentinel"}
        )
        result = run_session(
            [ToolCall(name=name, params=params, call_id="discover-1")],
            registry=registry,
            hooks=HookRegistry(),
            state=state,
        )[0]
        assert result.error is not None
        assert result.error.code == ("search_failed" if name == "fs_search" else "reach_failed")
        assert result.error.retryable is False and result.result is None
        assert result.error.message == (
            "managed cell-local search index is unavailable"
            if name == "fs_search"
            else "managed cell-local reach index is unavailable"
        )
        assert "host_only_sentinel" not in result.error.message and str(site.source) not in result.error.message
        assert calls == [] and client.sent == []
        assert not (site.source / ".fa" / "fts.db").exists()
        assert not (site.source / ".fa" / "structural.db").exists()
        assert (site.source / "chain.py").read_text() == "def host_only_sentinel():\n    return 2\n"
        events = [event for event in log.read_all() if event.tool_call_id == "discover-1"]
        assert sum(event.kind == "tool_call" for event in events) == 1
        assert sum(event.kind == "tool_result" for event in events) == 1


@pytest.mark.parametrize("name", ["fs_search", "fs_reach"])
def test_falsey_port_is_still_a_managed_binding(tmp_path: Path, name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """C0 EDGE: truthiness must not turn a bound port into host authority."""
    from tests.test_execution_tool_index import _CachePort

    class FalseyPort(_CachePort):
        def __bool__(self) -> bool:
            return False

    root = tmp_path / "host"
    root.mkdir()
    (root / "chain.py").write_text("def host_only_sentinel():\n    return 1\n")
    port = FalseyPort(tmp_path / "cache")
    holders: list[str] = []
    search_holder, reach_holder = fs_search._IndexHolder, fs_reach._ReachHolder

    def search(*args: Any, **kwargs: Any) -> Any:
        holders.append("search")
        return search_holder(*args, **kwargs)

    def reach(*args: Any, **kwargs: Any) -> Any:
        holders.append("reach")
        return reach_holder(*args, **kwargs)

    monkeypatch.setattr(fs_search, "_IndexHolder", search)
    monkeypatch.setattr(fs_reach, "_ReachHolder", reach)
    if name == "fs_search":
        spec = fs_search.build_fs_search_tool(root / ".fa" / "fts.db", root, workspace_io=port)
        result = spec.handler({"query": "host_only_sentinel"})
    else:
        spec = fs_reach.build_fs_reach_tool(root, workspace_io=port)
        result = spec.handler({"symbol": "host_only_sentinel"})
    assert result.error is not None
    assert result.error.code == ("search_failed" if name == "fs_search" else "reach_failed")
    assert result.error.retryable is False and result.result is None
    assert result.error.message == (
        "managed cell-local search index is unavailable"
        if name == "fs_search"
        else "managed cell-local reach index is unavailable"
    )
    assert holders == []
    assert not (root / ".fa").exists() and not (tmp_path / "cache").exists()


def test_extra_registry_path_retains_managed_port(tmp_path: Path) -> None:
    """C3: optional-tool composition must not drop the binding on an empty registry."""
    from fa.inner_loop.registry import ToolRegistry
    from fa.inner_loop.tools import _register_extra_tools
    from tests.test_execution_tool_index import _CachePort

    root = tmp_path / "host"
    root.mkdir()
    (root / "chain.py").write_text("def host_only_sentinel():\n    return 1\n")
    registry = ToolRegistry()
    _register_extra_tools(
        registry, root, include_pair=False, include_observability=False, workspace_io=_CachePort(tmp_path / "cache")
    )
    result = registry.dispatch(ToolCall(name="fs_search", params={"query": "host_only_sentinel"}, call_id="extra-1"))
    assert result.error is not None and result.error.code == "search_failed"
    assert result.error.message == "managed cell-local search index is unavailable"
    assert result.error.retryable is False and result.result is None
    assert not (root / ".fa").exists() and not (tmp_path / "cache").exists()


@pytest.mark.parametrize(
    ("role", "name"),
    [
        ("coder", "fs_search"),
        ("coder", "fs_reach"),
        ("chat", "fs_search"),
        ("chat", "fs_reach"),
        ("planner", "fs_search"),
        ("planner", "fs_reach"),
        ("eval", "fs_search"),
    ],
)
def test_all_registered_managed_roles_refuse_host_discovery(tmp_path: Path, role: str, name: str) -> None:
    """C1: each role's real composition retains the safety boundary."""
    from tests.test_execution_tool_index import _CachePort

    root = tmp_path / "host"
    root.mkdir()
    (root / "chain.py").write_text("def host_only_sentinel():\n    return 1\n")
    registry = cli._build_role_registry(role, root, bash_timeout_seconds=2, workspace_io=_CachePort(tmp_path / "cache"))
    assert registry.lookup(name) is not None
    params = {"query": "host_only_sentinel"} if name == "fs_search" else {"symbol": "host_only_sentinel"}
    result = registry.dispatch(ToolCall(name=name, params=params, call_id="role-1"))
    assert result.error is not None and result.error.code == (
        "search_failed" if name == "fs_search" else "reach_failed"
    )
    assert result.error.retryable is False and result.result is None
    assert not (root / ".fa").exists() and not (tmp_path / "cache").exists()


def test_parallel_managed_discovery_refusals_keep_per_call_events(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C2: real parallel tool dispatch cannot race into either host indexer."""
    import threading

    from fa.inner_loop.loop import _should_parallelize_tool_batch

    (site.source / "chain.py").write_text("def alpha():\n    return 1\n")
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=Access.WRITE, purpose=ViewPurpose.PROJECT, base_revision=managed.grant.revision_id, plan_ref=plan
        )
        assert grant.view_ref is not None
        client = _socket_client(site, tmp_path)
        port = ClientWorkspacePort(client, namespace=managed.binding.namespace, view=grant.view_ref, grant=grant)
        assert "alpha" in port.read_file("chain.py").content
        client.sent.clear()
        registry = cli._build_role_registry("coder", site.source, bash_timeout_seconds=2, workspace_io=port)
        calls = [
            ToolCall(name="fs_search", params={"query": "alpha"}, call_id="parallel-search"),
            ToolCall(name="fs_reach", params={"symbol": "alpha"}, call_id="parallel-reach"),
        ]
        assert _should_parallelize_tool_batch(calls, registry)
        barrier = threading.Barrier(2)
        threads: list[int] = []
        original_dispatch = registry.dispatch

        def synchronized(call: ToolCall) -> Any:
            threads.append(threading.get_ident())
            barrier.wait(timeout=5)
            return original_dispatch(call)

        monkeypatch.setattr(registry, "dispatch", synchronized)
        log = EventLog(tmp_path / "parallel" / "events.jsonl", run_id="parallel")
        state = SessionState(
            workspace_root=site.source,
            run_id="parallel",
            log=log,
            feature_flags=FeatureFlags(blackboard_enabled=False),
            workspace_io=port,
        )
        results = run_session(calls, registry=registry, hooks=HookRegistry(), state=state)
        assert len(set(threads)) == 2 and len(threads) == 2
        assert [r.error.code if r.error else None for r in results] == ["search_failed", "reach_failed"]
        assert all(r.error is not None and not r.error.retryable and r.result is None for r in results)
        assert client.sent == [] and not (site.source / ".fa" / "fts.db").exists()
        assert not (site.source / ".fa" / "structural.db").exists()
        for call in calls:
            events = [e for e in log.read_all() if e.tool_call_id == call.call_id]
            assert sum(e.kind == "tool_call" for e in events) == 1
            assert sum(e.kind == "tool_result" for e in events) == 1
