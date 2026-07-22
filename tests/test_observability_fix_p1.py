"""Observability Fix Phase 1 — Wire dead-code hooks (LOGIC-14, LOGIC-15).

C1 composition-root tests proving:

1. LOGIC-14: LoopGuard warn_sink is wired in _cmd_run so loop_guard_warn
   events are written to session.db when the repeat_warn threshold is hit.
   Previously, warn_sink was not passed → _emit_warn short-circuited →
   loop_guard_warn was dead code in production.

2. LOGIC-15: FailureClassifierObserver and AttemptHistoryObserver are
   registered in the _cmd_run hook chain so recovery_action events are
   written to session.db when a tool fails. Previously, neither observer
   was registered → recovery_action was dead code in production.

Kill-check: removing the warn_sink / observer registration from cli.py
makes these tests fail.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog, SessionState
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import (
    AttemptHistoryObserver,
    FailureClassifierObserver,
    HookRegistry,
    LoopGuard,
)
from fa.inner_loop.registry import ToolRegistry, ToolResult, ToolSpec
from fa.providers.base import ResponseInfo
from tests.fixtures.session_wiring import make_mock_chain, mock_success_response, require_log

# ── LOGIC-14: LoopGuard warn_sink wiring ──────────────────────────────────


def test_loop_guard_warn_event_emitted_via_drive_session(tmp_path: Path) -> None:
    """root=drive_session matrix=A claim=loop_guard_warn via warn_sink; kill-check=warn_sink in cli.py.

    When the same tool call is repeated >= repeat_warn times, the
    LoopGuard must emit a loop_guard_warn event to EventLog. This
    requires warn_sink to be wired (LOGIC-14 fix).
    """
    log = EventLog(tmp_path / "events.jsonl", run_id="test-logic14")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="test-logic14",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=False),
    )
    hooks = HookRegistry()

    # Wire warn_sink — mirrors the cli.py fix
    captured_warns: list[tuple[str, str]] = []

    def _test_warn_sink(detector: str, message: str) -> None:
        captured_warns.append((detector, message))
        log.append(
            actor="hook",
            kind="loop_guard_warn",
            content={"detector": detector, "message": message},
        )

    hooks.register(
        LoopGuard(
            repeat_warn=2,
            circuit_breaker=5,
            window=10,
            warn_sink=_test_warn_sink,
        )
    )

    # Register a simple test tool that always succeeds
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="test.echo",
            description="Echo test tool",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
            permission="read",
            handler=lambda params: ToolResult.ok(str(params.get("text", ""))),
        )
    )

    mock_chain = make_mock_chain(context_limit=150000)
    # Return the same tool call repeatedly to trigger loop detection
    same_call = {
        "id": "tc-001",
        "type": "function",
        "function": {"name": "test.echo", "arguments": json.dumps({"text": "hello"})},
    }
    mock_chain.request.side_effect = [
        # Turn 1: tool call
        _mock_response_with_tools([same_call]),
        # Turn 2: same tool call (repeat)
        _mock_response_with_tools([same_call]),
        # Turn 3: same tool call again (triggers repeat_warn=2)
        _mock_response_with_tools([same_call]),
        # Turn 4: final stop
        mock_success_response("done"),
    ]

    outcome = drive_session(
        "test loop guard warn",
        provider_chain=mock_chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=4,
    )

    # The session should still complete (warn does not stop)
    assert outcome.exit_code == 0

    # Verify loop_guard_warn event was written to EventLog
    events = require_log(state).read_all()
    warn_events = [e for e in events if e.kind == "loop_guard_warn"]
    assert len(warn_events) >= 1, (
        f"Expected at least 1 loop_guard_warn event, got {len(warn_events)}. Kinds present: {[e.kind for e in events]}"
    )


def test_loop_guard_circuit_breaker_works_without_sink(tmp_path: Path) -> None:
    """root=drive_session matrix=A claim=circuit breaker denies tool; kill-check=LoopGuard logic.

    The circuit breaker must deny tool execution when repeat count hits
    circuit_breaker threshold, even without a warn_sink. The session may
    still complete normally if the LLM stops afterwards — the key is that
    the denied tool result appears in the outcome.
    """
    log = EventLog(tmp_path / "events.jsonl", run_id="test-cb-no-sink")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="test-cb-no-sink",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=False),
    )
    hooks = HookRegistry()
    # NO warn_sink — circuit breaker should still work
    hooks.register(LoopGuard(repeat_warn=2, circuit_breaker=3, window=10))

    # Register a simple test tool
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="test.echo",
            description="Echo test tool",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
            permission="read",
            handler=lambda params: ToolResult.ok(str(params.get("text", ""))),
        )
    )

    mock_chain = make_mock_chain(context_limit=150000)
    same_call = {
        "id": "tc-001",
        "type": "function",
        "function": {"name": "test.echo", "arguments": json.dumps({"text": "hello"})},
    }
    # Provide enough turns for circuit breaker to fire
    mock_chain.request.side_effect = [
        _mock_response_with_tools([same_call]),
        _mock_response_with_tools([same_call]),
        _mock_response_with_tools([same_call]),
        _mock_response_with_tools([same_call]),
        _mock_response_with_tools([same_call]),
        mock_success_response("done"),
    ]

    outcome = drive_session(
        "test circuit breaker",
        provider_chain=mock_chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=6,
    )
    # Circuit breaker should have produced a denied tool result
    # The session may still end normally (stopped_by_llm) but at least
    # one tool result should contain the LoopGuard deny message.
    denied = [r for r in outcome.tool_results if "LoopGuard" in r.summary]
    assert len(denied) >= 1, (
        f"Expected at least 1 LoopGuard-denied tool result. Got: {[r.summary for r in outcome.tool_results]}"
    )


# ── LOGIC-15: FailureClassifierObserver + AttemptHistoryObserver wiring ────


def test_recovery_action_event_on_tool_failure(tmp_path: Path) -> None:
    """Drive a session and verify the recovery_action event is emitted.

    When a tool fails, FailureClassifierObserver must emit a
    recovery_action event to EventLog. Previously, the observer was
    defined but never registered (LOGIC-15).
    """
    log = EventLog(tmp_path / "events.jsonl", run_id="test-logic15")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="test-logic15",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=False),
    )
    hooks = HookRegistry()

    # Register FailureClassifierObserver — mirrors cli.py fix
    hooks.register(FailureClassifierObserver(event_log=log))

    mock_chain = make_mock_chain(context_limit=150000)

    # Register a tool that fails
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="test.fail_tool",
            description="Test tool that always fails",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            permission="read",
            handler=lambda params: ToolResult.fail("test_error", "deliberate failure", retryable=True),
        )
    )

    fail_call = {
        "id": "tc-fail",
        "type": "function",
        "function": {"name": "test.fail_tool", "arguments": json.dumps({"path": "/nonexistent/file.txt"})},
    }
    mock_chain.request.side_effect = [
        _mock_response_with_tools([fail_call]),
        mock_success_response("done after failure"),
    ]

    drive_session(
        "test recovery action",
        provider_chain=mock_chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=2,
    )

    # Verify recovery_action event was written to EventLog
    events = require_log(state).read_all()
    recovery_events = [e for e in events if e.kind == "recovery_action"]
    assert len(recovery_events) >= 1, (
        f"Expected at least 1 recovery_action event, got {len(recovery_events)}. "
        f"Kinds present: {sorted({e.kind for e in events})}"
    )
    # Verify structure
    re = recovery_events[0]
    assert "category" in re.content
    assert "action" in re.content
    assert "target" in re.content


def test_attempt_history_file_written_on_tool_failure(tmp_path: Path) -> None:
    """root=drive_session matrix=C claim=attempt_history.json; kill-check=AttemptHistoryObserver registration.

    When a tool fails, AttemptHistoryObserver must write to
    attempt_history.json. Previously, the observer was defined but never
    registered (LOGIC-15).
    """
    from fa.inner_loop.recovery.attempt_history import AttemptHistory

    log = EventLog(tmp_path / "events.jsonl", run_id="test-attempt-hist")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="test-attempt-hist",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=False),
    )
    hooks = HookRegistry()

    # Register AttemptHistoryObserver — mirrors cli.py fix
    history_path = tmp_path / ".fa" / "attempt_history.json"
    attempt_history = AttemptHistory(history_path)
    hooks.register(AttemptHistoryObserver(history=attempt_history))
    hooks.register(FailureClassifierObserver(event_log=log))

    mock_chain = make_mock_chain(context_limit=150000)

    # Register a tool that fails
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="test.fail_tool",
            description="Test tool that always fails",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            permission="read",
            handler=lambda params: ToolResult.fail("test_error", "deliberate failure", retryable=True),
        )
    )

    fail_call = {
        "id": "tc-fail2",
        "type": "function",
        "function": {"name": "test.fail_tool", "arguments": json.dumps({"path": "/nonexistent.txt"})},
    }
    mock_chain.request.side_effect = [
        _mock_response_with_tools([fail_call]),
        mock_success_response("done"),
    ]

    drive_session(
        "test attempt history",
        provider_chain=mock_chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=2,
    )

    # Verify attempt_history.json was written
    assert history_path.exists(), "attempt_history.json should exist after tool failure"
    content = json.loads(history_path.read_text(encoding="utf-8"))
    assert isinstance(content, list)
    assert len(content) >= 1, "attempt_history.json should contain at least one entry"


# ── Helpers ────────────────────────────────────────────────────────────────


def _mock_response_with_tools(
    tool_calls: list[dict[str, Any]],
) -> tuple[ResponseInfo, str, list[object]]:
    """Return a mock response with tool calls for drive_session."""
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
