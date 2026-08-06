from __future__ import annotations

from pathlib import Path
from typing import Any

from fa.inner_loop.context import reset_current_session, set_current_session
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.tools.observability import build_chronicle_search_tool, build_usage_tool
from tests._capabilities import requires_posix_paths


def test_usage_defaults_to_current_run_authority(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "events.jsonl", run_id="current-run")
    state = SessionState(workspace_root=tmp_path, run_id="current-run", log=log)
    log.append(
        actor="coder",
        kind="tool_call",
        content={"params": {}},
        tool_name="fs_read_file",
        tool_call_id="tc-1",
    )
    log.append(
        actor="runtime",
        kind="usage",
        content={
            "input_tokens": 120,
            "output_tokens": 30,
            "cache_read_input_tokens": 20,
            "cache_creation_input_tokens": 5,
        },
    )

    token = set_current_session(state)
    try:
        tool = build_usage_tool()
        result = tool.handler({})
    finally:
        reset_current_session(token)

    assert result.error is None
    assert result.result is not None
    assert result.result["run_id"] == "current-run"
    assert result.result["input_tokens"] == 120
    assert result.result["output_tokens"] == 30
    assert result.result["cache_read_input_tokens"] == 20
    assert result.result["tool_calls_breakdown"] == {"fs_read_file": 1}


def test_chronicle_search_defaults_to_current_run_authority(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "events.jsonl", run_id="current-run")
    state = SessionState(workspace_root=tmp_path, run_id="current-run", log=log)
    log.append(actor="runtime", kind="context_budget_warn", content={"message": "budget warning"})

    token = set_current_session(state)
    try:
        tool = build_chronicle_search_tool()
        result = tool.handler({"query": "budget warning"})
    finally:
        reset_current_session(token)

    assert result.error is None
    assert result.result is not None
    assert result.result["run_id"] == "current-run"
    assert len(result.result["entries"]) == 1
    assert result.result["entries"][0]["kind"] == "context_budget_warn"


def test_usage_requires_explicit_target_without_active_session() -> None:
    token = set_current_session(None)
    try:
        tool = build_usage_tool()
        result = tool.handler({})
    finally:
        reset_current_session(token)

    assert result.error is not None
    assert result.error.code == "no_active_session"


def test_chronicle_search_requires_explicit_target_without_active_session() -> None:
    token = set_current_session(None)
    try:
        tool = build_chronicle_search_tool()
        result = tool.handler({"query": "anything"})
    finally:
        reset_current_session(token)

    assert result.error is not None
    assert result.error.code == "no_active_session"


@requires_posix_paths
def test_usage_explicit_run_id_reads_run_authority(tmp_path: Path, monkeypatch: Any) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    run_dir = home / ".fa" / "session-log" / "run-42"
    log = EventLog(run_dir / "events.jsonl", run_id="run-42")
    log.append(
        actor="coder",
        kind="tool_call",
        content={"params": {}},
        tool_name="fs_grep",
        tool_call_id="tc-1",
    )
    log.append(
        actor="runtime",
        kind="usage",
        content={
            "input_tokens": 500,
            "output_tokens": 70,
            "cache_read_input_tokens": 100,
            "cache_creation_input_tokens": 0,
        },
    )

    token = set_current_session(None)
    try:
        tool = build_usage_tool()
        result = tool.handler({"run_id": "run-42"})
    finally:
        reset_current_session(token)

    assert result.error is None
    assert result.result is not None
    assert result.result["run_id"] == "run-42"
    assert result.result["input_tokens"] == 500
    assert result.result["tool_calls_breakdown"] == {"fs_grep": 1}


def test_chronicle_search_does_not_guess_workspace_events_path(tmp_path: Path) -> None:
    misleading = tmp_path / ".fa"
    misleading.mkdir(parents=True)
    (misleading / "events.jsonl").write_text('{"kind":"misleading"}\n', encoding="utf-8")

    token = set_current_session(None)
    try:
        tool = build_chronicle_search_tool()
        result = tool.handler({"query": "misleading"})
    finally:
        reset_current_session(token)

    assert result.error is not None
    assert result.error.code == "no_active_session"
