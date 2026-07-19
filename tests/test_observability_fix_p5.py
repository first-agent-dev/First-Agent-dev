"""Observability Fix Phase 5 — fa stats retrieval gaps (LOGIC-7, FIX-6..9).

C0 unit tests proving that parse_session and render_session handle
the new PR #53 event kinds: tool_result errors, compaction, subagent,
and context budget.

Kill-check: removing the parsing handlers makes the corresponding
SessionAnalytics fields empty.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from fa.inner_loop.state import EventLog
from fa.stats import (
    CompactionRecord,
    ContextBudgetEvent,
    SessionAnalytics,
    SubagentRecord,
    ToolError,
    parse_session,
    render_session,
)


def _write_events(tmp_path: Path, events: list[tuple[str, str, dict, str, str]]) -> Path:
    """Write events to an EventLog and return the path.

    Each event tuple: (actor, kind, content_dict, tool_name, tool_call_id)
    """
    jsonl_path = tmp_path / "events.jsonl"
    log = EventLog(jsonl_path, run_id="test-stats-p5")
    for actor, kind, content, tool_name, tool_call_id in events:
        log.append(actor=actor, kind=kind, content=content, tool_name=tool_name, tool_call_id=tool_call_id)
    return jsonl_path


# ── LOGIC-7: tool_result error extraction ──────────────────────────────────


def test_stats_parses_tool_result_errors(tmp_path: Path) -> None:
    """parse_session extracts tool errors from tool_result events."""
    jsonl_path = _write_events(tmp_path, [
        ("runtime", "run_started", {"role": "coder"}, "", ""),
        ("coder", "tool_call", {"params": {"path": "/tmp/a.txt"}}, "fs.read_file", "tc-1"),
        ("tool", "tool_result", {"summary": "failed", "ok": False, "error": {"code": "file_not_found", "message": "No such file"}}, "fs.read_file", "tc-1"),
        ("runtime", "session_summary", {"n_turns": 1, "input_tokens": 100, "output_tokens": 10, "cache_hit_ratio": 0.0}, "", ""),
    ])
    result = parse_session(jsonl_path)
    assert result is not None
    assert len(result.tool_errors) == 1
    assert result.tool_errors[0].tool == "fs.read_file"
    assert result.tool_errors[0].code == "file_not_found"


def test_stats_tool_result_ok_not_in_errors(tmp_path: Path) -> None:
    """Successful tool_result events don't appear in tool_errors."""
    jsonl_path = _write_events(tmp_path, [
        ("runtime", "run_started", {"role": "coder"}, "", ""),
        ("coder", "tool_call", {"params": {"path": "/tmp/a.txt"}}, "fs.read_file", "tc-1"),
        ("tool", "tool_result", {"summary": "ok", "ok": True}, "fs.read_file", "tc-1"),
        ("runtime", "session_summary", {"n_turns": 1, "input_tokens": 100, "output_tokens": 10, "cache_hit_ratio": 0.0}, "", ""),
    ])
    result = parse_session(jsonl_path)
    assert result is not None
    assert len(result.tool_errors) == 0


# ── FIX-6: Compaction events ──────────────────────────────────────────────


def test_stats_parses_compaction_events(tmp_path: Path) -> None:
    """parse_session extracts compaction records from stage2/3 done/error events."""
    jsonl_path = _write_events(tmp_path, [
        ("runtime", "run_started", {"role": "coder"}, "", ""),
        ("runtime", "compaction_stage2_done", {"tokens_before": 120000, "tokens_after": 80000}, "", ""),
        ("runtime", "compaction_stage3_done", {"tokens_before": 80000, "tokens_after": 50000}, "", ""),
        ("runtime", "session_summary", {"n_turns": 1, "input_tokens": 100, "output_tokens": 10, "cache_hit_ratio": 0.0}, "", ""),
    ])
    result = parse_session(jsonl_path)
    assert result is not None
    assert len(result.compaction_records) == 2
    assert result.compaction_records[0].stage == 2
    assert result.compaction_records[0].ok is True
    assert result.compaction_records[0].tokens_before == 120000
    assert result.compaction_records[1].stage == 3


def test_stats_parses_compaction_error(tmp_path: Path) -> None:
    """parse_session extracts compaction error records."""
    jsonl_path = _write_events(tmp_path, [
        ("runtime", "run_started", {"role": "coder"}, "", ""),
        ("runtime", "compaction_stage2_error", {"error": "masking failed"}, "", ""),
        ("runtime", "session_summary", {"n_turns": 1, "input_tokens": 100, "output_tokens": 10, "cache_hit_ratio": 0.0}, "", ""),
    ])
    result = parse_session(jsonl_path)
    assert result is not None
    assert len(result.compaction_records) == 1
    assert result.compaction_records[0].ok is False
    assert "masking failed" in result.compaction_records[0].error


# ── FIX-7: Subagent events ────────────────────────────────────────────────


def test_stats_parses_subagent_events(tmp_path: Path) -> None:
    """parse_session extracts subagent spawn results."""
    jsonl_path = _write_events(tmp_path, [
        ("runtime", "run_started", {"role": "coder"}, "", ""),
        ("tool", "subagent_spawn_done", {"ok": True}, "", ""),
        ("tool", "subagent_spawn_fail", {"error": "chain exhausted"}, "", ""),
        ("runtime", "session_summary", {"n_turns": 1, "input_tokens": 100, "output_tokens": 10, "cache_hit_ratio": 0.0}, "", ""),
    ])
    result = parse_session(jsonl_path)
    assert result is not None
    assert len(result.subagent_records) == 2
    assert result.subagent_records[0].ok is True
    assert result.subagent_records[1].ok is False
    assert "chain exhausted" in result.subagent_records[1].error


# ── FIX-8/9: Context budget events ────────────────────────────────────────


def test_stats_parses_context_budget_events(tmp_path: Path) -> None:
    """parse_session extracts context budget warn and hard-stop events."""
    jsonl_path = _write_events(tmp_path, [
        ("runtime", "run_started", {"role": "coder"}, "", ""),
        ("runtime", "context_budget_warn", {"action": "warn", "ratio": 0.72, "message": "context at 72%"}, "", ""),
        ("runtime", "context_budget_hard_stop", {"action": "stage3", "ratio": 0.92, "message": "context at 92%"}, "", ""),
        ("runtime", "session_summary", {"n_turns": 1, "input_tokens": 100, "output_tokens": 10, "cache_hit_ratio": 0.0}, "", ""),
    ])
    result = parse_session(jsonl_path)
    assert result is not None
    assert len(result.context_budget_events) == 2
    assert result.context_budget_events[0].action == "warn"
    assert abs(result.context_budget_events[0].pct - 72.0) < 1.0
    assert result.context_budget_events[1].action == "hard_stop"


# ── Rendering tests ────────────────────────────────────────────────────────


def test_stats_renders_tool_errors_section(tmp_path: Path) -> None:
    """render_session shows Tool errors section when tool errors exist."""
    analytics = SessionAnalytics(
        run_id="test",
        role="coder",
        start_ts="2026-01-01",
        stop_reason="stopped_by_llm",
        ok=True,
        turns=1,
        tool_errors=[ToolError(tool="fs.read_file", code="not_found", message="No such file")],
    )
    stream = io.StringIO()
    render_session(analytics, stream=stream)
    output = stream.getvalue()
    assert "Tool errors" in output
    assert "fs.read_file" in output


def test_stats_renders_compaction_section(tmp_path: Path) -> None:
    """render_session shows Compaction section when records exist."""
    analytics = SessionAnalytics(
        run_id="test",
        role="coder",
        start_ts="2026-01-01",
        stop_reason="stopped_by_llm",
        ok=True,
        turns=1,
        compaction_records=[CompactionRecord(stage=2, ok=True, tokens_before=120000, tokens_after=80000)],
    )
    stream = io.StringIO()
    render_session(analytics, stream=stream)
    output = stream.getvalue()
    assert "Compaction" in output
    assert "stage2" in output


def test_stats_renders_context_budget_section(tmp_path: Path) -> None:
    """render_session shows Context budget section when events exist."""
    analytics = SessionAnalytics(
        run_id="test",
        role="coder",
        start_ts="2026-01-01",
        stop_reason="stopped_by_llm",
        ok=True,
        turns=1,
        context_budget_events=[ContextBudgetEvent(action="warn", pct=72.0, message="context at 72%")],
    )
    stream = io.StringIO()
    render_session(analytics, stream=stream)
    output = stream.getvalue()
    assert "Context budget" in output
    assert "72%" in output
