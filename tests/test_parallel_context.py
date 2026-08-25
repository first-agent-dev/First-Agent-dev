"""I-63: contextvar propagation to parallel tool workers.

Verifies that get_current_session() returns the SessionState inside
ThreadPoolExecutor workers used by run_session's parallel batch path.

This is a C1 live-path test: real ToolRegistry, real SessionState,
real blackboard, real EventLog, parallel batch of 2+ read tools.

Kill-check: removing contextvars.copy_context().run wrapper in
loop.py::_execute_batch_parallel makes test_parallel_blackboard_query_in_parallel_batch
fail with blackboard_unavailable.
"""

from __future__ import annotations

from pathlib import Path

from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.runtime_limits import RuntimeLimits
from fa.inner_loop.tools.blackboard_query import build_blackboard_query_tool
from fa.inner_loop.tools.fs_search import build_fs_search_tool


def test_parallel_blackboard_query_in_parallel_batch(tmp_path: Path) -> None:
    """Parallel batch [fs_search, fs_blackboard_query] must both succeed first try."""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / ".fa").mkdir()
    # seed repo files so search finds something and artifact index has content
    (ws / "a.txt").write_text("iteration_cap needle\n")
    (ws / "knowledge").mkdir()
    (ws / "knowledge" / "test.md").write_text("# Skill\ncontent")

    log = EventLog(ws / "ev.jsonl", run_id="par-bb")
    state = SessionState(workspace_root=ws, run_id="par-bb", log=log)
    # Blackboard must exist (source-verified: SessionState creates it when session_db present)
    assert state.blackboard is not None

    # Ensure artifact index has at least 1 row for the query to return
    from fa.blackboard.artifact_index import ensure_artifacts_indexed

    stats = ensure_artifacts_indexed(state.blackboard, ws)
    # In this tiny fixture, scanned may be 1, but we at least have a DB
    assert stats is not None

    registry = ToolRegistry()
    registry.register(build_fs_search_tool(ws / ".fa" / "fts.db", ws))
    registry.register(build_blackboard_query_tool())

    calls = (
        ToolCall(name="fs_search", params={"query": "iteration_cap"}, call_id="t1"),
        ToolCall(name="fs_blackboard_query", params={"type": "skill", "limit": 5}, call_id="t2"),
    )

    results = run_session(
        calls,
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
        limits=RuntimeLimits(max_iterations=10),
    )

    assert len(results) == 2
    # Both must succeed — the bug made second fail with blackboard_unavailable
    assert results[0].error is None, f"fs_search failed: {results[0].error}"
    assert results[1].error is None, f"fs_blackboard_query failed in parallel batch: {results[1].error} — I-63 regress"
    assert results[1].result is not None


def test_parallel_search_telemetry_propagated(tmp_path: Path) -> None:
    """fs_search in parallel batch must record _pending_search_paths for S15 surfaced_by."""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / ".fa").mkdir()
    (ws / "a.txt").write_text("needle content\n")

    log = EventLog(ws / "ev.jsonl", run_id="par-search")
    state = SessionState(workspace_root=ws, run_id="par-search", log=log)

    registry = ToolRegistry()
    registry.register(build_fs_search_tool(ws / ".fa" / "fts.db", ws))

    # Parallel batch: two searches (both parallel-safe)
    calls = (
        ToolCall(name="fs_search", params={"query": "needle"}, call_id="t1"),
        ToolCall(name="fs_search", params={"query": "needle"}, call_id="t2"),
    )

    results = run_session(
        calls,
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
        limits=RuntimeLimits(max_iterations=10),
    )

    assert len(results) == 2
    assert all(r.error is None for r in results)
    # After batch, pending paths should have been committed (loop.py commits after each batch)
    # So last_search_paths should contain a.txt (from search)
    # Note: commit_search_paths is called after batch, so last_search_paths should be non-empty
    assert "a.txt" in state.last_search_paths or len(state.last_search_paths) > 0
