"""Tests for fa.output — EventBus + ConsoleRenderer + QuietRenderer."""

from __future__ import annotations

import os
from io import StringIO
from unittest.mock import patch

from fa.output import ConsoleRenderer, EventBus, OutputEvent, QuietRenderer


def _event(type: str, **data: object) -> OutputEvent:
    return OutputEvent(type=type, turn=1, max_turns=16, data=dict(data))  # type: ignore[arg-type]


class _CollectingListener:
    def __init__(self) -> None:
        self.events: list[OutputEvent] = []

    def on_event(self, event: OutputEvent) -> None:
        self.events.append(event)


class _CrashingListener:
    def on_event(self, event: OutputEvent) -> None:
        raise RuntimeError("boom")


# ── EventBus ──────────────────────────────────────────────────────────────


def test_event_bus_fanout() -> None:
    bus = EventBus()
    a = _CollectingListener()
    b = _CollectingListener()
    bus.add(a)
    bus.add(b)
    bus.emit(_event("session_start"))
    assert len(a.events) == 1
    assert len(b.events) == 1


def test_event_bus_crash_isolation() -> None:
    """A crashing listener does not prevent others from receiving events."""
    bus = EventBus()
    crasher = _CrashingListener()
    collector = _CollectingListener()
    bus.add(crasher)
    bus.add(collector)
    bus.emit(_event("session_start"))
    assert len(collector.events) == 1


# ── ConsoleRenderer ───────────────────────────────────────────────────────


def test_console_session_start() -> None:
    buf = StringIO()
    r = ConsoleRenderer(detail="standard")
    with patch.object(r, "_write", side_effect=lambda t: buf.write(t + "\n")):
        r.on_event(_event("session_start", model="glm-5p2", role="planner"))
    assert "glm-5p2" in buf.getvalue()
    assert "planner" in buf.getvalue()


def test_console_turn_start_minimal_suppressed() -> None:
    """Minimal detail: turn headers are suppressed."""
    buf = StringIO()
    r = ConsoleRenderer(detail="minimal")
    with patch.object(r, "_write", side_effect=lambda t: buf.write(t + "\n")):
        r.on_event(_event("turn_start"))
    assert buf.getvalue() == ""


def test_console_llm_response() -> None:
    buf = StringIO()
    r = ConsoleRenderer(detail="standard")
    with patch.object(r, "_write", side_effect=lambda t: buf.write(t + "\n")):
        r.on_event(
            _event(
                "llm_response",
                ms=1847,
                in_tokens=2100,
                out_tokens=312,
                cache_read=1830,
            )
        )
    out = buf.getvalue()
    assert "1847ms" in out
    assert "2.1k" in out
    assert "cache=" in out


def test_console_tool_call_success() -> None:
    buf = StringIO()
    r = ConsoleRenderer(detail="standard")
    with patch.object(r, "_write", side_effect=lambda t: buf.write(t + "\n")):
        r.on_event(
            _event(
                "tool_call",
                tool="fs.read_file",
                params={"path": "src/fa/cli.py"},
                summary="505 lines",
                ok=True,
            )
        )
    out = buf.getvalue()
    assert "Read" in out
    assert "cli.py" in out
    assert "505 lines" in out


def test_console_tool_call_failure() -> None:
    buf = StringIO()
    r = ConsoleRenderer(detail="standard")
    with patch.object(r, "_write", side_effect=lambda t: buf.write(t + "\n")):
        r.on_event(
            _event(
                "tool_call",
                tool="fs.run_bash",
                params={"command": "sudo rm -rf /"},
                summary="",
                ok=False,
                error="bash command blocked",
            )
        )
    out = buf.getvalue()
    assert "blocked" in out


def test_console_no_color() -> None:
    """NO_COLOR=1 disables ANSI escape codes."""
    with patch.dict(os.environ, {"NO_COLOR": "1"}):
        r = ConsoleRenderer(detail="standard")
    assert not r._use_color
    assert r._c("31", "red") == "red"


def test_console_session_end() -> None:
    buf = StringIO()
    r = ConsoleRenderer(detail="standard")
    with patch.object(r, "_write", side_effect=lambda t: buf.write(t + "\n")):
        r.on_event(
            _event(
                "session_end",
                ok=True,
                stop_reason="stopped_by_llm",
                turns=3,
                wall_s=5.2,
                total_in=6900,
                total_out=1200,
                cache_hit_ratio=0.89,
            )
        )
    out = buf.getvalue()
    assert "stopped_by_llm" in out
    assert "turns=3" in out
    assert "6.9k" in out
    assert "89%" in out


# ── QuietRenderer ─────────────────────────────────────────────────────────


def test_quiet_does_nothing() -> None:
    """QuietRenderer swallows all events."""
    q = QuietRenderer()
    q.on_event(_event("session_start"))
    q.on_event(_event("llm_response", ms=100, in_tokens=50, out_tokens=10))
    q.on_event(_event("session_end", ok=True, stop_reason="done", turns=1))
    # No assertion needed — just verify it doesn't raise.
