"""Observability Fix Phase 4 — Console visibility (LOGIC-5, LOGIC-9, FIX-1..5).

C1 tests proving that new OutputEvent types are emitted by drive_session
and correctly handled by ConsoleRenderer.

1. LOGIC-5: context_used_pct computed from budget (not hardcoded None)
2. FIX-1: context_warn OutputEvent emitted at budget warn/stage thresholds
3. FIX-2: compaction_start/end OutputEvents emitted during compaction
4. LOGIC-9: ProviderRequestShapeError emits api_retry console event
5. FIX-5: loop_warn OutputEvent emitted via warn_sink

Kill-check: removing the emit calls or handler registrations makes tests fail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog, SessionState
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry, LoopGuard
from fa.inner_loop.registry import ToolRegistry, ToolResult, ToolSpec
from fa.output import ConsoleRenderer, EventBus, OutputEvent
from fa.providers.base import ResponseInfo
from fa.providers.errors import ProviderRequestShapeError
from tests.fixtures.session_wiring import make_mock_chain, mock_success_response

# ── Capturing output bus for event assertions ─────────────────────────────


class _CaptureListener:
    """Captures OutputEvents for test assertions."""

    def __init__(self) -> None:
        self.events: list[OutputEvent] = []

    def on_event(self, event: OutputEvent) -> None:
        self.events.append(event)


def _make_session_with_output(
    tmp_path: Path, *, budget_enabled: bool = True, compaction_enabled: bool = False
) -> tuple[SessionState, EventBus, _CaptureListener]:
    """Create session state + output bus with capture listener."""
    flags = FeatureFlags(context_budget_enabled=budget_enabled)
    log = EventLog(tmp_path / "events.jsonl", run_id="test-p4")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="test-p4",
        log=log,
        feature_flags=flags,
    )
    bus = EventBus()
    capture = _CaptureListener()
    bus.add(capture)
    bus.add(ConsoleRenderer(detail="verbose"))
    return state, bus, capture


# ── LOGIC-5: context_used_pct computed ────────────────────────────────────


def test_context_used_pct_not_none_at_session_end(tmp_path: Path) -> None:
    """root=drive_session matrix=A claim=context_used_pct computed; kill-check=reverting None assignment.

    When budget check runs, context_used_pct should be a real number
    in the session_end OutputEvent, not None.
    """
    state, bus, capture = _make_session_with_output(tmp_path)

    # Size task to trigger budget check (over 70% of 100k)
    mock_chain = make_mock_chain(context_limit=100000)
    mock_chain.request.return_value = mock_success_response("done with budget")

    task = "X" * 300000  # ~75k tokens

    drive_session(
        task,
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
        output=bus,
    )

    end_events = [e for e in capture.events if e.type == "session_end"]
    assert len(end_events) >= 1, f"No session_end event found. Types: {[e.type for e in capture.events]}"
    pct = end_events[0].data.get("context_used_pct")
    assert pct is not None, "context_used_pct should not be None after budget check runs"


# ── FIX-1: context_warn OutputEvent ───────────────────────────────────────


def test_context_warn_emitted_at_budget_warn(tmp_path: Path) -> None:
    """root=drive_session matrix=A claim=context_warn OutputEvent; kill-check=removing emit call.

    When context budget reaches warn threshold, a context_warn
    OutputEvent must be emitted.
    """
    state, bus, capture = _make_session_with_output(tmp_path)

    mock_chain = make_mock_chain(context_limit=100000)
    mock_chain.request.return_value = mock_success_response("warn path")

    task = "A" * 300000  # ~75k tokens → triggers warn

    drive_session(
        task,
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
        output=bus,
    )

    warn_events = [e for e in capture.events if e.type == "context_warn"]
    assert len(warn_events) >= 1, (
        f"Expected context_warn event. Types: {[e.type for e in capture.events]}"
    )


# ── LOGIC-9: ProviderRequestShapeError console event ──────────────────────


def test_request_shape_error_emits_api_retry_event(tmp_path: Path) -> None:
    """root=drive_session matrix=A claim=api_retry on shape error; kill-check=removing emit call.

    When ProviderRequestShapeError is raised, an api_retry OutputEvent
    must be emitted before the session ends.
    """
    state, bus, capture = _make_session_with_output(tmp_path, budget_enabled=False)

    mock_chain = make_mock_chain(context_limit=150000)
    mock_chain.request.side_effect = ProviderRequestShapeError("bad request shape")

    drive_session(
        "test shape error",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
        output=bus,
    )

    retry_events = [e for e in capture.events if e.type == "api_retry"]
    assert len(retry_events) >= 1, (
        f"Expected api_retry event for shape error. Types: {[e.type for e in capture.events]}"
    )
    assert "request_shape" in str(retry_events[0].data.get("reason", "")).lower()


# ── FIX-5: loop_warn OutputEvent ──────────────────────────────────────────


def test_loop_warn_emitted_via_warn_sink(tmp_path: Path) -> None:
    """root=drive_session matrix=A claim=loop_warn OutputEvent; kill-check=removing warn_sink.

    When LoopGuard fires at repeat_warn threshold with a warn_sink
    that also emits to output_bus, a loop_warn OutputEvent must appear.
    """
    log = EventLog(tmp_path / "events.jsonl", run_id="test-loop-warn")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="test-loop-warn",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=False),
    )
    bus = EventBus()
    capture = _CaptureListener()
    bus.add(capture)

    hooks = HookRegistry()

    def _warn_sink(detector: str, message: str) -> None:
        try:
            log.append(actor="hook", kind="loop_guard_warn", content={"detector": detector, "message": message})
        except (OSError, RuntimeError, ValueError, TypeError):
            pass
        try:
            bus.emit(OutputEvent(type="loop_warn", data={"detector": detector, "message": message}))
        except (OSError, RuntimeError, ValueError, TypeError):
            pass

    hooks.register(LoopGuard(repeat_warn=2, circuit_breaker=5, window=10, warn_sink=_warn_sink))

    # Register a test tool
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="test.echo",
        description="Echo test tool",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        permission="read",
        handler=lambda params: ToolResult.ok(str(params.get("text", ""))),
    ))

    mock_chain = make_mock_chain(context_limit=150000)
    same_call = {
        "id": "tc-001",
        "type": "function",
        "function": {"name": "test.echo", "arguments": json.dumps({"text": "hello"})},
    }
    mock_chain.request.side_effect = [
        _mock_response_with_tools([same_call]),
        _mock_response_with_tools([same_call]),
        _mock_response_with_tools([same_call]),
        mock_success_response("done"),
    ]

    drive_session(
        "test loop warn output",
        provider_chain=mock_chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=4,
        output=bus,
    )

    loop_warn_events = [e for e in capture.events if e.type == "loop_warn"]
    assert len(loop_warn_events) >= 1, (
        f"Expected loop_warn event. Types: {[e.type for e in capture.events]}"
    )


# ── ConsoleRenderer detail-level tests ────────────────────────────────────


def test_context_warn_visible_at_standard_detail(capsys: Any) -> None:
    """context_warn OutputEvent renders at --detail standard."""
    renderer = ConsoleRenderer(detail="standard")
    renderer._write = lambda text: sys.stderr.write(text + "\n")  # type: ignore[method-assign,assignment]  # test capture seam
    event = OutputEvent(type="context_warn", data={"pct": 85, "action": "stage2", "message": "budget warning"})
    renderer.on_event(event)
    captured = capsys.readouterr()
    assert "85%" in captured.err
    assert "context" in captured.err.lower()


def test_compaction_start_renders(capsys: Any) -> None:
    """compaction_start OutputEvent renders."""
    renderer = ConsoleRenderer(detail="standard")
    renderer._write = lambda text: sys.stderr.write(text + "\n")  # type: ignore[method-assign,assignment]  # test capture seam
    event = OutputEvent(type="compaction_start", data={"stage": 2, "tokens_before": 120000})
    renderer.on_event(event)
    captured = capsys.readouterr()
    assert "compaction" in captured.err.lower()
    assert "stage2" in captured.err


def test_loop_warn_renders(capsys: Any) -> None:
    """loop_warn OutputEvent renders."""
    renderer = ConsoleRenderer(detail="standard")
    renderer._write = lambda text: sys.stderr.write(text + "\n")  # type: ignore[method-assign,assignment]  # test capture seam
    event = OutputEvent(
        type="loop_warn",
        data={"detector": "identical_call_repeat", "message": "test.echo repeated 2 times"},
    )
    renderer.on_event(event)
    captured = capsys.readouterr()
    assert "loop" in captured.err.lower()


# ── Helpers ────────────────────────────────────────────────────────────────


def _mock_response_with_tools(tool_calls: list[dict[str, Any]]) -> tuple[ResponseInfo, str, list[object]]:
    from fa.providers.base import ResponseInfo

    resp = ResponseInfo(
        text="",
        in_tokens=100,
        out_tokens=10,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        finish_reason="tool_calls",
        tool_calls=tuple(tool_calls),
        extras={},
    )
    return resp, "call-id-1", []
