"""S19: Kill-check tests for missing log-kind parsers in fa stats.

root=parse_session matrix=C claim=all LogKinds visible to fa stats
kill-check=removing an elif branch for a new kind → UNPARSED_KINDS contract
  check or missing field in SessionAnalytics makes test fail
path-inventory: 6 new elif paths in parse_session

Covers:
- compaction_warning → CompactionWarningRecord
- compaction_circuit_breaker → CircuitBreakerRecord
- compaction_stage2_start / compaction_stage3_start → CompactionStartRecord
- model_msg → model_msg_count
- user_msg → user_msg_count
- UNPARSED_KINDS completeness: all LogKinds accounted for
"""

from __future__ import annotations

import json
from pathlib import Path

from fa.output import LogKind
from fa.stats import (
    UNPARSED_KINDS,
    CircuitBreakerRecord,
    CompactionStartRecord,
    CompactionWarningRecord,
    SessionAnalytics,
    parse_session,
)
import typing


def _write_events_jsonl(path: Path, events: list[dict]) -> None:
    """Write synthetic events.jsonl for stats parsing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def _base_event(run_id: str = "test-run", kind: str = "run_started", **extra: object) -> dict:
    return {
        "event_id": "ev-000001",
        "ts": "2026-07-20T00:00:00Z",
        "run_id": run_id,
        "harness_id": "fa-inner-loop@0.1.0",
        "actor": "runtime",
        "kind": kind,
        "content": extra,
        "tool_name": "",
        "tool_call_id": "",
        "parent_event_id": "",
    }


# ── Kill-check: compaction_warning parsed ──────────────────────────────


def test_compaction_warning_parsed(tmp_path: Path) -> None:
    """kill-check: removing compaction_warning elif → record not in analytics."""
    events_path = tmp_path / "events.jsonl"
    _write_events_jsonl(events_path, [
        _base_event(kind="run_started", role="coder"),
        _base_event(kind="compaction_warning", action="stage2", compaction_enabled=True, ratio=0.75, threshold=0.7),
        _base_event(kind="session_summary", n_turns=1, input_tokens=100, output_tokens=50, cache_hit_ratio=0.5, output_tokens_total=50),
    ])
    result = parse_session(events_path)
    assert result is not None
    assert len(result.compaction_warnings) == 1
    assert result.compaction_warnings[0].action == "stage2"
    assert result.compaction_warnings[0].compaction_enabled is True
    assert result.compaction_warnings[0].ratio == 0.75


# ── Kill-check: compaction_circuit_breaker parsed ──────────────────────


def test_circuit_breaker_parsed(tmp_path: Path) -> None:
    """kill-check: removing circuit_breaker elif → record not in analytics."""
    events_path = tmp_path / "events.jsonl"
    _write_events_jsonl(events_path, [
        _base_event(kind="run_started", role="coder"),
        _base_event(kind="compaction_circuit_breaker", message="anti-thrashing loop locked"),
        _base_event(kind="session_summary", n_turns=1, input_tokens=100, output_tokens=50, cache_hit_ratio=0.5),
    ])
    result = parse_session(events_path)
    assert result is not None
    assert len(result.circuit_breaker_events) == 1
    assert "anti-thrashing" in result.circuit_breaker_events[0].message


# ── Kill-check: compaction_stage*_start parsed ─────────────────────────


def test_compaction_start_parsed(tmp_path: Path) -> None:
    """kill-check: removing stage2/3 start elif → record not in analytics."""
    events_path = tmp_path / "events.jsonl"
    _write_events_jsonl(events_path, [
        _base_event(kind="run_started", role="coder"),
        _base_event(kind="compaction_stage2_start", tokens_before=120000, threshold=0.7),
        _base_event(kind="compaction_stage3_start", tokens_before=130000, threshold=0.85),
        _base_event(kind="session_summary", n_turns=1, input_tokens=100, output_tokens=50, cache_hit_ratio=0.5),
    ])
    result = parse_session(events_path)
    assert result is not None
    assert len(result.compaction_starts) == 2
    assert result.compaction_starts[0].stage == 2
    assert result.compaction_starts[0].tokens_before == 120000
    assert result.compaction_starts[1].stage == 3


# ── Kill-check: model_msg / user_msg counted ───────────────────────────


def test_model_user_msg_counted(tmp_path: Path) -> None:
    """kill-check: removing model_msg/user_msg elif → counts stay 0."""
    events_path = tmp_path / "events.jsonl"
    _write_events_jsonl(events_path, [
        _base_event(kind="run_started", role="coder"),
        _base_event(kind="user_msg", text="hello"),
        _base_event(kind="model_msg", text="world", tool_calls=[], finish_reason="stop"),
        _base_event(kind="user_msg", text="hello2"),
        _base_event(kind="model_msg", text="world2", tool_calls=[], finish_reason="stop"),
        _base_event(kind="session_summary", n_turns=2, input_tokens=200, output_tokens=100, cache_hit_ratio=0.5),
    ])
    result = parse_session(events_path)
    assert result is not None
    assert result.user_msg_count == 2
    assert result.model_msg_count == 2


# ── Kill-check: UNPARSED_KINDS completeness ────────────────────────────


def test_unparsed_kinds_complete() -> None:
    """All LogKinds must be either parsed or in UNPARSED_KINDS.

    This is a contract check: if a new LogKind is added to output.py
    without a parser here, this test fails.
    """
    all_kinds = set(typing.get_args(LogKind))

    # Kinds that have elif branches in parse_session
    parsed_kinds = {
        "run_started", "tool_call", "usage", "provider_attempt", "hook_decision",
        "loop_guard_warn", "tool_result", "compaction_stage2_done", "compaction_stage2_error",
        "compaction_stage3_done", "compaction_stage3_error", "subagent_spawn_done",
        "subagent_spawn_fail", "context_budget_warn", "context_budget_hard_stop",
        "session_summary", "run_stopped",
        "compaction_warning", "compaction_circuit_breaker", "compaction_stage2_start",
        "compaction_stage3_start", "model_msg", "user_msg",
    }

    unparsed = set(UNPARSED_KINDS)
    accounted = parsed_kinds | unparsed
    missing = all_kinds - accounted
    assert not missing, (
        f"LogKinds not accounted for in stats.py: {sorted(missing)}. "
        f"Either add an elif parser or add to UNPARSED_KINDS."
    )


# ── Kill-check: UNPARSED_KINDS are valid LogKind members ───────────────


def test_unparsed_kinds_are_valid_logkinds() -> None:
    """Every member of UNPARSED_KINDS must be a valid LogKind."""
    valid = set(typing.get_args(LogKind))
    invalid = set(UNPARSED_KINDS) - valid
    assert not invalid, f"UNPARSED_KINDS contains invalid LogKind values: {sorted(invalid)}"
