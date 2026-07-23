"""C1 producer tests for EventTypes missing C1 coverage.

These tests verify that drive_session actually EMITS each EventType via the
output bus. This is the PRODUCER proof required by the two-sided contract
(I-TW-14, I-TW-10). Consumer-only tests (C0) prove handlers work GIVEN an
event, but do NOT prove the event is ever produced.

Path inventory:
  - session_start: emitted once per session at start
  - turn_start: emitted per turn iteration
  - llm_response: emitted per model response
  - tool_call: emitted per tool invocation
  - hook_deny: emitted when a hook denies an action
  - subagent_start: emitted when subagent spawning begins
  - subagent_end: emitted when subagent spawning completes

Kill-check: removing the output.emit() call from the production code path
makes each test fail.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, override
from unittest.mock import MagicMock, patch

from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog, SessionState
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.registry import ToolRegistry, ToolResult, ToolSpec
from fa.output import EventBus, OutputEvent
from fa.providers.base import ResponseInfo
from tests.fixtures.session_wiring import make_mock_chain, mock_success_response


class _Capture:
    """Capture OutputEvents for test assertions."""

    def __init__(self) -> None:
        self.events: list[OutputEvent] = []

    def on_event(self, event: OutputEvent) -> None:
        self.events.append(event)


def _make_session_with_output(
    tmp_path: Path,
    *,
    budget_enabled: bool = True,
) -> tuple[SessionState, EventBus, _Capture]:
    """Create session state + output bus with capture listener."""
    flags = FeatureFlags(
        context_budget_enabled=budget_enabled,
    )
    log = EventLog(tmp_path / "events.jsonl", run_id="test-c1")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="test-c1",
        log=log,
        feature_flags=flags,
    )
    bus = EventBus()
    capture = _Capture()
    bus.add(capture)
    return state, bus, capture


def _mock_response_with_tools(tool_calls: list[dict[str, Any]]) -> tuple[ResponseInfo, str, list[Any]]:
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


# ── session_start ────────────────────────────────────────────────────────


def test_session_start_emitted(tmp_path: Path) -> None:
    """C1 producer: drive_session emits session_start OutputEvent.

    root=drive_session matrix=C claim=session_start emitted at session start
    kill-check=removing the session_start emit from coder_loop.py makes test fail.
    """
    state, bus, capture = _make_session_with_output(tmp_path, budget_enabled=False)
    mock_chain = make_mock_chain(context_limit=150000)
    mock_chain.request.return_value = mock_success_response("done")

    drive_session(
        "test session start",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
        output=bus,
    )

    start_events = [e for e in capture.events if e.type == "session_start"]
    assert len(start_events) >= 1, f"Expected session_start event. Types: {[e.type for e in capture.events]}"


# ── turn_start ───────────────────────────────────────────────────────────


def test_turn_start_emitted(tmp_path: Path) -> None:
    """C1 producer: drive_session emits turn_start per turn.

    root=drive_session matrix=C claim=turn_start emitted each turn
    kill-check=removing the turn_start emit from coder_loop.py makes test fail.
    """
    state, bus, capture = _make_session_with_output(tmp_path, budget_enabled=False)
    mock_chain = make_mock_chain(context_limit=150000)
    mock_chain.request.return_value = mock_success_response("done")

    drive_session(
        "test turn start",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
        output=bus,
    )

    turn_events = [e for e in capture.events if e.type == "turn_start"]
    assert len(turn_events) >= 1, f"Expected turn_start event. Types: {[e.type for e in capture.events]}"


# ── llm_response ─────────────────────────────────────────────────────────


def test_llm_response_emitted(tmp_path: Path) -> None:
    """C1 producer: drive_session emits llm_response on model response.

    root=drive_session matrix=C claim=llm_response emitted after provider call
    kill-check=removing the llm_response emit from coder_loop.py makes test fail.
    """
    state, bus, capture = _make_session_with_output(tmp_path, budget_enabled=False)
    mock_chain = make_mock_chain(context_limit=150000)
    mock_chain.request.return_value = mock_success_response("model says hello")

    drive_session(
        "test llm response",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
        output=bus,
    )

    llm_events = [e for e in capture.events if e.type == "llm_response"]
    assert len(llm_events) >= 1, f"Expected llm_response event. Types: {[e.type for e in capture.events]}"


# ── tool_call ────────────────────────────────────────────────────────────


def test_tool_call_emitted(tmp_path: Path) -> None:
    """C1 producer: drive_session emits tool_call when model invokes a tool.

    root=drive_session matrix=C claim=tool_call emitted on tool invocation
    kill-check=removing the tool_call emit from coder_loop.py makes test fail.
    """
    state, bus, capture = _make_session_with_output(tmp_path, budget_enabled=False)

    # Register a test tool
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
    tool_call = {
        "id": "tc-001",
        "type": "function",
        "function": {"name": "test.echo", "arguments": json.dumps({"text": "hello"})},
    }
    mock_chain.request.side_effect = [
        _mock_response_with_tools([tool_call]),
        mock_success_response("done after tool"),
    ]

    drive_session(
        "test tool call event",
        provider_chain=mock_chain,
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        max_turns=3,
        output=bus,
    )

    tc_events = [e for e in capture.events if e.type == "tool_call"]
    assert len(tc_events) >= 1, f"Expected tool_call event. Types: {[e.type for e in capture.events]}"


# ── hook_deny ────────────────────────────────────────────────────────────


def test_hook_deny_emitted(tmp_path: Path) -> None:
    """C1 producer: drive_session emits hook_deny when a guard denies.

    root=drive_session matrix=C claim=hook_deny emitted on guard deny
    kill-check=removing the hook_deny emit from coder_loop.py makes test fail.
    path-inventory: path 1 of 2 (BEFORE_LLM_CALL deny)
    """
    from fa.inner_loop.hooks import GuardMiddleware, HookPayload, LifecyclePoint
    from fa.inner_loop.hooks.base import Decision

    state, bus, capture = _make_session_with_output(tmp_path, budget_enabled=False)

    # Register a guard that denies at BEFORE_LLM_CALL
    class _DenyGuard(GuardMiddleware):
        name = "deny_test"
        attaches_to = (LifecyclePoint.BEFORE_LLM_CALL,)

        @override
        def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
            return Decision.deny("test deny")

    hooks = HookRegistry()
    hooks.register(_DenyGuard())

    mock_chain = make_mock_chain(context_limit=150000)
    mock_chain.request.return_value = mock_success_response("never reached")

    drive_session(
        "test hook deny event",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=hooks,
        state=state,
        max_turns=1,
        output=bus,
    )

    deny_events = [e for e in capture.events if e.type == "hook_deny"]
    assert len(deny_events) >= 1, f"Expected hook_deny event. Types: {[e.type for e in capture.events]}"


# ── subagent_start / subagent_end ────────────────────────────────────────


def test_subagent_events_emitted_via_output_bus(tmp_path: Path) -> None:
    """C1 producer: spawn_subagent emits subagent_start/subagent_end via output_bus.

    root=build_spawn_subagent_tool handler matrix=C claim=subagent_start/end
    OutputEvent emitted via state.output_bus
    kill-check=removing the output_bus.emit() calls from spawn_subagent.py
    makes this test fail.

    Tests the FIX-3 wiring: subagent_start and subagent_end must be emitted
    on the output_bus, not just logged to EventLog.
    """
    from fa.inner_loop.context import set_current_session
    from fa.inner_loop.tools.spawn_subagent import build_spawn_subagent_tool

    log = EventLog(tmp_path / "events.jsonl", run_id="test-sub-c1")
    bus = EventBus()
    capture = _Capture()
    bus.add(capture)

    state = SessionState(
        workspace_root=tmp_path,
        run_id="test-sub-c1",
        log=log,
        feature_flags=FeatureFlags(
            context_budget_enabled=False,
            subagent_spawning_enabled=True,
        ),
        output_bus=bus,
    )

    # Set session context so spawn_subagent can find it
    set_current_session(state)

    # Mock SubagentRunner to avoid needing a real one
    # It's imported locally inside the handler, so patch at the source module
    with patch("fa.inner_loop.subagent_runner.SubagentRunner") as mock_runner_class:
        from fa.inner_loop.subagent_envelope import SubagentEnvelope

        mock_runner = MagicMock()
        mock_envelope = SubagentEnvelope.from_verifier(
            task_id="task-1",
            exit_code=0,
            stdout="verification passed",
            duration_ms=150,
            role="verifier",
        )
        mock_runner.run_stateless.return_value = mock_envelope
        mock_runner_class.return_value = mock_runner

        tool = build_spawn_subagent_tool(tmp_path)
        result = tool.handler(
            {
                "task_id": "task-1",
                "command": "echo hello",
                "role": "verifier",
            }
        )

    assert result.error is None, f"Subagent tool should succeed: {result}"

    # Verify subagent_start was emitted
    start_events = [e for e in capture.events if e.type == "subagent_start"]
    assert len(start_events) >= 1, f"Expected subagent_start event. Types: {[e.type for e in capture.events]}"
    assert start_events[0].data["task_id"] == "task-1"

    # Verify subagent_end was emitted
    end_events = [e for e in capture.events if e.type == "subagent_end"]
    assert len(end_events) >= 1, f"Expected subagent_end event. Types: {[e.type for e in capture.events]}"
    assert end_events[0].data["task_id"] == "task-1"
    assert end_events[0].data["ok"] is True
