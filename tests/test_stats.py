"""Tests for fa.stats — session analytics."""

from __future__ import annotations

import json
from pathlib import Path

from fa.stats import (
    SessionAnalytics,
    aggregate_sessions,
    efficiency_warnings,
    find_dead_zones,
    parse_session,
    render_session_json,
)


def _write_events(path: Path, events: list[dict[str, object]]) -> None:
    """Write synthetic events.jsonl."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for i, event in enumerate(events, 1):
            row = {
                "event_id": f"ev-{i:06d}",
                "ts": "2026-06-21T14:00:00Z",
                "run_id": "test-run",
                "harness_id": "fa-inner-loop@0.1.0",
                "actor": event.get("actor", "runtime"),
                "kind": event.get("kind", ""),
                "content": event.get("content", {}),
                "tool_name": event.get("tool_name", ""),
                "tool_call_id": event.get("tool_call_id", ""),
                "parent_event_id": "",
            }
            f.write(json.dumps(row) + "\n")


def _minimal_session_events() -> list[dict[str, object]]:
    """Minimal set of events for a complete session."""
    return [
        {"kind": "run_started", "content": {"role": "planner", "max_turns": 16}},
        {
            "kind": "tool_call",
            "actor": "coder",
            "tool_name": "fs.read_file",
            "tool_call_id": "tc-1",
            "content": {"params": {"path": "src/fa/cli.py"}},
        },
        {
            "kind": "tool_result",
            "actor": "tool",
            "tool_name": "fs.read_file",
            "tool_call_id": "tc-1",
            "content": {"summary": "505 lines", "ok": True},
        },
        {
            "kind": "tool_call",
            "actor": "coder",
            "tool_name": "fs.read_file",
            "tool_call_id": "tc-2",
            "content": {"params": {"path": "src/fa/cli.py"}},
        },
        {
            "kind": "tool_result",
            "actor": "tool",
            "tool_name": "fs.read_file",
            "tool_call_id": "tc-2",
            "content": {"summary": "505 lines", "ok": True},
        },
        {
            "kind": "tool_call",
            "actor": "coder",
            "tool_name": "fs.run_bash",
            "tool_call_id": "tc-3",
            "content": {"params": {"command": "ruff check src/fa/cli.py"}},
        },
        {
            "kind": "tool_result",
            "actor": "tool",
            "tool_name": "fs.run_bash",
            "tool_call_id": "tc-3",
            "content": {"summary": "exit=0", "ok": True},
        },
        {
            "kind": "tool_call",
            "actor": "coder",
            "tool_name": "fs.write_file",
            "tool_call_id": "tc-4",
            "content": {"params": {"path": "src/fa/output.py", "content": "..."}},
        },
        {
            "kind": "tool_result",
            "actor": "tool",
            "tool_name": "fs.write_file",
            "tool_call_id": "tc-4",
            "content": {"summary": "wrote file", "ok": True},
        },
        {
            "kind": "usage",
            "content": {
                "input_tokens": 3200,
                "output_tokens": 400,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 200,
            },
        },
        {
            "kind": "usage",
            "content": {
                "input_tokens": 5100,
                "output_tokens": 800,
                "cache_read_input_tokens": 3000,
                "cache_creation_input_tokens": 0,
            },
        },
        {
            "kind": "provider_attempt",
            "actor": "provider",
            "content": {
                "provider": "fireworks",
                "slug": "glm-5p2",
                "status": 200,
                "ms": 1847,
                "error": None,
            },
        },
        {
            "kind": "session_summary",
            "content": {
                "n_turns": 2,
                "input_tokens": 8300,
                "output_tokens": 1200,
                "cache_read_input_tokens": 3000,
                "cache_creation_input_tokens": 200,
                "uncached_input_tokens": 5100,
                "cache_hit_ratio": 0.36,
            },
        },
        {"kind": "run_stopped", "content": {"reason": "stopped_by_llm"}},
    ]


# ── parse_session ─────────────────────────────────────────────────────────


def test_parse_session_basic(tmp_path: Path) -> None:
    events_path = tmp_path / "test-run" / "events.jsonl"
    _write_events(events_path, _minimal_session_events())

    result = parse_session(events_path)

    assert result is not None
    assert result.run_id == "test-run"
    assert result.role == "planner"
    assert result.turns == 2
    assert result.ok is True
    assert result.stop_reason == "stopped_by_llm"


def test_parse_session_tool_counts(tmp_path: Path) -> None:
    events_path = tmp_path / "test-run" / "events.jsonl"
    _write_events(events_path, _minimal_session_events())

    result = parse_session(events_path)
    assert result is not None

    tool_dict = {t.name: t.count for t in result.tool_usage}
    assert tool_dict["fs.read_file"] == 2
    assert tool_dict["fs.run_bash"] == 1
    assert tool_dict["fs.write_file"] == 1


def test_parse_session_file_access(tmp_path: Path) -> None:
    events_path = tmp_path / "test-run" / "events.jsonl"
    _write_events(events_path, _minimal_session_events())

    result = parse_session(events_path)
    assert result is not None

    file_dict = {f.path: f for f in result.file_access}
    assert file_dict["src/fa/cli.py"].reads == 2
    assert file_dict["src/fa/output.py"].writes == 1


def test_parse_session_bash_commands(tmp_path: Path) -> None:
    events_path = tmp_path / "test-run" / "events.jsonl"
    _write_events(events_path, _minimal_session_events())

    result = parse_session(events_path)
    assert result is not None

    bash_dict = {b.command: b.count for b in result.bash_commands}
    assert bash_dict["ruff check src/fa/cli.py"] == 1


def test_parse_session_token_timeline(tmp_path: Path) -> None:
    events_path = tmp_path / "test-run" / "events.jsonl"
    _write_events(events_path, _minimal_session_events())

    result = parse_session(events_path)
    assert result is not None

    assert len(result.token_timeline) == 2
    assert result.token_timeline[0].in_tokens == 3200
    assert result.token_timeline[0].cache_hit_ratio == 0.0
    assert result.token_timeline[1].cache_read == 3000


def test_parse_session_provider_health(tmp_path: Path) -> None:
    events_path = tmp_path / "test-run" / "events.jsonl"
    _write_events(events_path, _minimal_session_events())

    result = parse_session(events_path)
    assert result is not None

    assert len(result.provider_health) == 1
    p = result.provider_health[0]
    assert p.provider == "fireworks"
    assert p.ok == 1
    assert p.avg_ms == 1847


def test_parse_session_totals(tmp_path: Path) -> None:
    events_path = tmp_path / "test-run" / "events.jsonl"
    _write_events(events_path, _minimal_session_events())

    result = parse_session(events_path)
    assert result is not None

    assert result.total_in == 8300
    assert result.total_out == 1200
    assert result.cache_hit_ratio == 0.36


def test_parse_session_redundant_reads(tmp_path: Path) -> None:
    events_path = tmp_path / "test-run" / "events.jsonl"
    _write_events(events_path, _minimal_session_events())

    result = parse_session(events_path)
    assert result is not None

    # cli.py read 2x → 1 redundant
    assert result.redundant_reads == 1


def test_parse_session_nonexistent(tmp_path: Path) -> None:
    result = parse_session(tmp_path / "nope" / "events.jsonl")
    assert result is None


def test_parse_session_corrupt_lines(tmp_path: Path) -> None:
    """Corrupt JSONL lines are skipped, not fatal."""
    events_path = tmp_path / "test-run" / "events.jsonl"
    events_path.parent.mkdir(parents=True)
    events_path.write_text(
        '{"event_id":"ev-1","ts":"x","run_id":"t","harness_id":"fa","actor":"r","kind":"run_started","content":{"role":"c"}}\n'
        "this is not json\n"
        '{"event_id":"ev-2","ts":"x","run_id":"t","harness_id":"fa","actor":"r","kind":"run_stopped","content":{"reason":"ok"}}\n',
        encoding="utf-8",
    )
    # Should not raise
    result = parse_session(events_path)
    # May return analytics from partial data or None — just verify no crash
    assert result is None or isinstance(result, SessionAnalytics)


# ── efficiency_warnings ───────────────────────────────────────────────────


def test_efficiency_redundant_reads(tmp_path: Path) -> None:
    events_path = tmp_path / "test-run" / "events.jsonl"
    _write_events(events_path, _minimal_session_events())
    result = parse_session(events_path)
    assert result is not None

    warnings = efficiency_warnings(result)
    assert any("redundant" in w.lower() for w in warnings)


# ── aggregate_sessions ────────────────────────────────────────────────────


def test_aggregate_two_sessions(tmp_path: Path) -> None:
    for run_id in ("run-1", "run-2"):
        events_path = tmp_path / run_id / "events.jsonl"
        _write_events(events_path, _minimal_session_events())

    sessions = []
    for run_id in ("run-1", "run-2"):
        result = parse_session(tmp_path / run_id / "events.jsonl")
        if result:
            sessions.append(result)

    agg = aggregate_sessions(sessions)
    assert agg["sessions"] == 2
    assert agg["total_in"] == 8300 * 2


# ── find_dead_zones ───────────────────────────────────────────────────────


def test_dead_zones(tmp_path: Path) -> None:
    # Create fake src/ tree
    (tmp_path / "src" / "fa").mkdir(parents=True)
    (tmp_path / "src" / "fa" / "cli.py").write_text("# code", encoding="utf-8")
    (tmp_path / "src" / "fa" / "unused.py").write_text("# code", encoding="utf-8")

    events_path = tmp_path / "test-run" / "events.jsonl"
    _write_events(events_path, _minimal_session_events())
    result = parse_session(events_path)
    assert result is not None

    dead = find_dead_zones(tmp_path, [result])
    # cli.py was accessed, unused.py was not
    assert "src/fa/unused.py" in dead
    assert "src/fa/cli.py" not in dead


# ── render_session_json ───────────────────────────────────────────────────


def test_render_json_serializable(tmp_path: Path) -> None:
    events_path = tmp_path / "test-run" / "events.jsonl"
    _write_events(events_path, _minimal_session_events())
    result = parse_session(events_path)
    assert result is not None

    data = render_session_json(result)
    # Must be JSON-serializable
    serialized = json.dumps(data, default=str)
    parsed = json.loads(serialized)
    assert parsed["run_id"] == "test-run"
    assert parsed["role"] == "planner"
    assert len(parsed["tool_usage"]) >= 3
