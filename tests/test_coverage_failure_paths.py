"""High-signal coverage tests for runtime failure and analytics paths."""

from __future__ import annotations

import builtins
import io
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from fa.feature_flags import FeatureFlags
from fa.inner_loop.profiles import build_registry_for_role
from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.session_db import SessionDatabase
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.tools.spawn_subagent import build_spawn_subagent_tool
from fa.stats import (
    FileAccess,
    SessionAnalytics,
    ToolUsage,
    TurnTokens,
    aggregate_sessions,
    efficiency_warnings,
    find_dead_zones,
    render_aggregate,
    render_session,
)


def test_profile_builder_optional_import_failure_is_observable(caplog: Any, tmp_path: Path) -> None:
    """C2: one optional builder failure does not collapse the role registry."""
    real_import = builtins.__import__

    def fail_glob(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "fa.inner_loop.tools.glob":
            raise ImportError("simulated glob backend unavailable")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fail_glob):
        registry = build_registry_for_role("researcher", tmp_path)

    names = {spec.name for spec in registry.specs()}
    assert "fs.read_file" in names
    assert "fs.grep" in names
    assert "fs.glob" not in names
    assert any("glob" in record.message.lower() for record in caplog.records)


def test_subagent_runner_exception_returns_failure_and_cleans_workspace(tmp_path: Path) -> None:
    """C1: runner exception produces failure event and cleanup."""
    from fa.inner_loop.context import reset_current_session, set_current_session

    log = EventLog(tmp_path / "events.jsonl", run_id="subagent-error")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="subagent-error",
        log=log,
        feature_flags=FeatureFlags(subagent_spawning_enabled=True),
    )
    token = set_current_session(state)
    workspace = tmp_path / "subagent-workspace"
    workspace.mkdir()
    try:
        tool = build_spawn_subagent_tool(tmp_path)
        with patch.object(state, "create_subagent_workspace", return_value=workspace) as create_workspace:
            with patch.object(state, "cleanup_subagent_workspace") as cleanup_workspace:
                with patch(
                    "fa.inner_loop.subagent_runner.SubagentRunner.run_stateless",
                    side_effect=RuntimeError("runner boom"),
                ):
                    result = tool.handler({"task_id": "failure-1", "command": "false", "role": "verifier"})
    finally:
        reset_current_session(token)

    assert result.error is not None
    assert result.error.code == "runner_failed"
    create_workspace.assert_called_once_with("failure-1")
    cleanup_workspace.assert_called_once_with(workspace)
    failure_events = [event for event in log.read_all() if event.kind == "subagent_spawn_fail"]
    assert len(failure_events) == 1
    assert "runner boom" in str(failure_events[0].content["error"])


def test_stats_aggregate_and_render_edge_paths(tmp_path: Path) -> None:
    """C2: aggregate/render paths expose status, tokens, files, and warnings."""
    first = SessionAnalytics(
        run_id="run-1",
        role="coder",
        start_ts="2026-01-01T00:00:00Z",
        stop_reason="stopped_by_llm",
        ok=True,
        turns=3,
        tool_usage=[ToolUsage(name="fs.read_file", count=3)],
        file_access=[FileAccess(path="src/fa/cli.py", reads=3)],
        token_timeline=[
            TurnTokens(turn=i, in_tokens=100, out_tokens=20, cache_read=0, cache_creation=0) for i in range(1, 5)
        ],
        total_in=400,
        total_out=80,
        redundant_reads=2,
        repeated_commands=1,
    )
    second = SessionAnalytics(
        run_id="run-2",
        role="verifier",
        start_ts="2026-01-02T00:00:00Z",
        stop_reason="context_budget_hard_stop",
        ok=False,
        turns=1,
        total_in=50,
        total_out=10,
    )

    aggregate = aggregate_sessions([first, second])
    assert aggregate["sessions"] == 2
    assert aggregate["ok"] == 1
    assert aggregate["failed"] == 1
    assert aggregate["total_turns"] == 4
    assert aggregate["most_read_files"]

    session_stream = io.StringIO()
    render_session(first, stream=session_stream)
    rendered = session_stream.getvalue()
    assert "run-1" in rendered
    assert "fs.read_file" in rendered
    assert "redundant" in rendered.lower()

    aggregate_stream = io.StringIO()
    render_aggregate([first, second], stream=aggregate_stream)
    aggregate_text = aggregate_stream.getvalue()
    assert "2 sessions" in aggregate_text
    assert "context_budget_hard_stop" in aggregate_text

    warnings = efficiency_warnings(first)
    assert any("redundant" in warning for warning in warnings)
    assert any("repeated bash" in warning for warning in warnings)
    assert any("cache miss" in warning.lower() for warning in warnings)


def test_stats_dead_zone_detection_handles_missing_and_unread_files(tmp_path: Path) -> None:
    """C2: dead-zone projection is deterministic and excludes cache files."""
    (tmp_path / "src" / "fa").mkdir(parents=True)
    (tmp_path / "src" / "fa" / "used.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "src" / "fa" / "dead.py").write_text("x = 2\n", encoding="utf-8")
    (tmp_path / "src" / "fa" / "__pycache__").mkdir()
    (tmp_path / "src" / "fa" / "__pycache__" / "ignored.py").write_text("", encoding="utf-8")

    analytics = SessionAnalytics(
        run_id="run-1",
        role="coder",
        start_ts="",
        stop_reason="done",
        ok=True,
        turns=1,
        file_access=[FileAccess(path="src/fa/used.py", reads=1)],
    )
    assert find_dead_zones(tmp_path, [analytics]) == ["src/fa/dead.py"]
    assert find_dead_zones(tmp_path / "missing", [analytics]) == []


def test_session_db_read_failure_falls_back_to_jsonl_without_inventing_rows(tmp_path: Path) -> None:
    """C3: authoritative read failure uses the existing mirror deterministically."""
    log = EventLog(tmp_path / "events.jsonl", run_id="read-fallback")
    log.append(actor="runtime", kind="tool_call", content={"command": "pwd"})
    assert log.session_db is not None

    with patch.object(log.session_db, "read_event_rows", side_effect=RuntimeError("db unavailable")):
        events = log.read_all()

    assert len(events) == 1
    assert events[0].kind == "tool_call"
    assert events[0].content["command"] == "pwd"


def test_session_db_initialization_failure_is_explicit(tmp_path: Path) -> None:
    """C3: authority initialization failure cannot silently create split brain."""
    with patch.object(SessionDatabase, "_connect", side_effect=OSError("disk unavailable")):
        with pytest.raises(RuntimeError, match="session_db_init_failed"):
            SessionDatabase(tmp_path / "broken" / "session.db")


def test_profile_optional_builders_all_missing_are_skipped(caplog: Any, tmp_path: Path) -> None:
    """C2: missing optional builders never make registry construction crash."""
    import fa.inner_loop.tools as tools

    names = (
        "build_glob_tool",
        "build_grep_tool",
        "build_chronicle_search_tool",
        "build_usage_tool",
        "build_list_tasks_tool",
        "build_checkpoint_tool",
        "build_diff_tool",
        "build_send_ctrl_c_tool",
        "build_undo_tool",
        "build_instant_grep_tool",
        "build_spawn_subagent_tool",
    )
    original = {name: getattr(tools, name) for name in names}
    try:
        for name in names:
            setattr(tools, name, None)
        registry = ToolRegistry()
        tools._register_extra_tools(
            registry,
            tmp_path,
            include_pair=True,
            include_observability=True,
            include_instant_grep=True,
            include_glob_grep=True,
        )
    finally:
        for name, value in original.items():
            setattr(tools, name, value)
    assert registry.names() == ()


def test_subagent_invalid_secret_environment_is_denied(tmp_path: Path) -> None:
    """C3: secret-looking subagent environment keys fail closed."""
    from fa.inner_loop.context import reset_current_session, set_current_session

    state = SessionState(
        workspace_root=tmp_path,
        run_id="subagent-secret",
        log=EventLog(tmp_path / "events.jsonl", run_id="subagent-secret"),
        feature_flags=FeatureFlags(subagent_spawning_enabled=True),
    )
    token = set_current_session(state)
    try:
        result = build_spawn_subagent_tool(tmp_path).handler(
            {"task_id": "secret-env", "command": "echo safe", "env": {"OPENAI_API_KEY": "blocked"}}
        )
    finally:
        reset_current_session(token)
    assert result.error is not None
    assert result.error.code == "invalid_params"
    assert "secret" in result.error.message.lower()


def test_subagent_missing_required_input_is_structured(tmp_path: Path) -> None:
    """C2: malformed subagent calls fail before workspace creation."""
    from fa.inner_loop.context import reset_current_session, set_current_session

    state = SessionState(
        workspace_root=tmp_path,
        run_id="subagent-invalid",
        log=EventLog(tmp_path / "events.jsonl", run_id="subagent-invalid"),
        feature_flags=FeatureFlags(subagent_spawning_enabled=True),
    )
    token = set_current_session(state)
    try:
        result = build_spawn_subagent_tool(tmp_path).handler({"task_id": "missing-command"})
    finally:
        reset_current_session(token)
    assert result.error is not None
    assert result.error.code == "invalid_params"


def test_pty_pool_rejects_invalid_workdir_and_exhaustion(tmp_path: Path) -> None:
    """C3: PTY resource admission fails explicitly and preserves main pinning."""
    from fa.runtime.pty_pool import PoolExhaustedError, PtyPool

    pool = PtyPool(max_size=1, base_cwd=tmp_path, run_id="coverage-pool")
    with pytest.raises(RuntimeError, match="not exists"):
        pool.acquire("missing", workdir=str(tmp_path / "missing"))
    assert pool.acquire("main").session_id == "main"
    with pytest.raises(PoolExhaustedError):
        pool.acquire("worker")
    pool.kill("main")
    assert pool.list_sessions() == []
