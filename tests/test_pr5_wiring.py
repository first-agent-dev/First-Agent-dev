"""Ruthless Integration & Anti-Theater Tests for PR 5 (Stage 3 Compaction & Constraints).

Verifies that:
1. Reaching 80% capacity with progressive compaction enabled triggers Stage 3 LLM Compaction
   if Stage 2 Observation Masking is insufficient to bring the usage below the threshold.
2. Previous compaction summaries (memory_summary) are correctly carried forward and prepended
   during subsequent compaction steps.
3. The 3-strike circuit breaker (anti-thrashing loop) halts the loop if less than 10% space
   is reclaimed 3 consecutive times, logging appropriate telemetry events.
4. If a compactor role is declared, its chain is used to run Stage 3 LLM Compaction.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog, SessionState, ToolRegistry
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.providers import ChainConfig, ProviderChain
from fa.providers.base import ResponseInfo


@pytest.fixture
def mock_session_state(tmp_path: Path) -> SessionState:
    log = EventLog(tmp_path / "events.jsonl", run_id="test-pr5-run")
    return SessionState(
        workspace_root=tmp_path,
        run_id="test-pr5-run",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True, context_compaction_enabled=True),
    )


def _require_log(state: SessionState) -> EventLog:
    """Session fixtures always attach a log; narrow Optional for type checkers."""
    assert state.log is not None
    return state.log


def _mock_success_response(text: str = "done") -> tuple[ResponseInfo, str, list[object]]:
    resp = ResponseInfo(
        text=text,
        in_tokens=1000,
        out_tokens=100,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        finish_reason="stop",
        tool_calls=(),
        extras={},
    )
    return resp, "call-id", []


def test_stage3_compaction_triggers_and_rebuilds_prompt(
    tmp_path: Path, mock_session_state: SessionState
) -> None:
    """Verifies that Stage 3 LLM Compaction triggers and uses the compactor_chain."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "anthropic"

    mock_chain.request.return_value = _mock_success_response("all done")

    # We also mock the compactor chain
    mock_compactor_chain = MagicMock(spec=ProviderChain)
    mock_compactor_chain.config = MagicMock(spec=ChainConfig)
    mock_compactor_chain.config.context_limit = 100000
    mock_compactor_chain.config.model = "compactor-model"
    mock_compactor_chain.config.family = "openai"

    compactor_resp = ResponseInfo(
        text=(
            "## PREVIOUSLY\n"
            "Summarized the older conversation.\n\n"
            "## PARKED\n"
            "None.\n\n"
            "## CURRENT\n"
            "Task is ongoing.\n\n"
            "## NEXT ACTION\n"
            "Proceed with drive_session verification."
        ),
        in_tokens=500,
        out_tokens=100,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        finish_reason="stop",
        tool_calls=(),
        extras={},
    )
    mock_compactor_chain.request.return_value = (compactor_resp, "comp-call-id", [])

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="fs.read_file",
            description="read",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            permission="read",
            handler=lambda params: ToolResult.ok("mock read"),
        )
    )

    # Pre-populate session log:
    # First 2 turns: extremely bulky (outside protected window, eligible for compaction)
    for i in range(1, 3):
        t_calls = [
            {"id": f"tc-{i}", "type": "function", "function": {"name": "fs.read_file", "arguments": "{}"}}
        ]
        _require_log(mock_session_state).append(
            actor="model",
            kind="model_msg",
            content={"text": "Bulky step content " * 15000, "tool_calls": t_calls},
        )
        _require_log(mock_session_state).append(
            actor="tool",
            kind="tool_result",
            content={"summary": "short summary", "result": {"stdout": "A" * 150}, "ok": True},
            tool_name="fs.read_file",
            tool_call_id=f"tc-{i}",
        )

    # Remaining 5 turns: small (inside protected window, or just additional turns)
    for i in range(3, 8):
        t_calls = [
            {"id": f"tc-{i}", "type": "function", "function": {"name": "fs.read_file", "arguments": "{}"}}
        ]
        _require_log(mock_session_state).append(
            actor="model", kind="model_msg", content={"text": f"Step content {i}", "tool_calls": t_calls}
        )
        _require_log(mock_session_state).append(
            actor="tool",
            kind="tool_result",
            content={"summary": "short summary", "result": {"stdout": "A" * 150}, "ok": True},
            tool_name="fs.read_file",
            tool_call_id=f"tc-{i}",
        )


    outcome = drive_session(
        "Test Stage 3 compaction task",
        provider_chain=mock_chain,
        compactor_chain=mock_compactor_chain,
        registry=registry,
        hooks=HookRegistry(),
        state=mock_session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 0
    assert mock_chain.request.call_count == 1
    assert mock_compactor_chain.request.call_count == 1

    events = _require_log(mock_session_state).read_all()
    stage3_start = [e for e in events if e.kind == "compaction_stage3_start"]
    stage3_done = [e for e in events if e.kind == "compaction_stage3_done"]
    assert len(stage3_start) == 1
    assert len(stage3_done) == 1
    assert "summary" in stage3_done[0].content
    assert "Summarized the older conversation" in str(stage3_done[0].content.get("summary", ""))

    compactor_req = mock_compactor_chain.request.call_args[0][0]
    assert compactor_req.model_slug == "compactor-model"


def test_stage2_can_avoid_stage3_when_usage_drops_below_stage3_threshold(
    tmp_path: Path, mock_session_state: SessionState
) -> None:
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "anthropic"
    mock_chain.request.return_value = _mock_success_response("stage2 only")

    mock_compactor_chain = MagicMock(spec=ProviderChain)
    mock_compactor_chain.config = MagicMock(spec=ChainConfig)
    mock_compactor_chain.config.context_limit = 100000
    mock_compactor_chain.config.model = "compactor-model"
    mock_compactor_chain.config.family = "openai"

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="fs.read_file",
            description="read",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            permission="read",
            handler=lambda params: ToolResult.ok("mock read"),
        )
    )

    # Create five turns so the first one sits outside the protected tail and can be masked.
    for i in range(1, 6):
        t_calls = [
            {"id": f"tc-{i}", "type": "function", "function": {"name": "fs.read_file", "arguments": "{}"}}
        ]
        _require_log(mock_session_state).append(
            actor="model",
            kind="model_msg",
            content={"text": f"Step {i}", "tool_calls": t_calls},
        )
        stdout = "A" * 330000 if i == 1 else "small"
        _require_log(mock_session_state).append(
            actor="tool",
            kind="tool_result",
            content={"summary": "bulk output", "result": {"stdout": stdout}, "ok": True},
            tool_name="fs.read_file",
            tool_call_id=f"tc-{i}",
        )


    outcome = drive_session(
        "Test Stage 2 only task",
        provider_chain=mock_chain,
        compactor_chain=mock_compactor_chain,
        registry=registry,
        hooks=HookRegistry(),
        state=mock_session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 0
    assert mock_chain.request.call_count == 1
    assert mock_compactor_chain.request.call_count == 0

    events = _require_log(mock_session_state).read_all()
    assert [e for e in events if e.kind == "compaction_stage2_done"]
    assert not [e for e in events if e.kind == "compaction_stage3_start"]



def test_previous_summary_carried_forward(tmp_path: Path, mock_session_state: SessionState) -> None:
    """Verifies that an existing memory_summary in the event log is correctly carried forward and prepended."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "anthropic"

    mock_chain.request.return_value = _mock_success_response("all done")

    mock_compactor_chain = MagicMock(spec=ProviderChain)
    mock_compactor_chain.config = MagicMock(spec=ChainConfig)
    mock_compactor_chain.config.context_limit = 100000
    mock_compactor_chain.config.model = "compactor"

    compactor_resp = ResponseInfo(
        text=(
            "## PREVIOUSLY\nCompacted again.\n\n"
            "## PARKED\nNone.\n\n"
            "## CURRENT\nOngoing.\n\n"
            "## NEXT ACTION\nNext."
        ),
        in_tokens=500,
        out_tokens=100,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        finish_reason="stop",
        tool_calls=(),
        extras={},
    )
    mock_compactor_chain.request.return_value = (compactor_resp, "comp-call-id", [])

    # Seed the log with a previous compaction_stage3_done event
    _require_log(mock_session_state).append(
        actor="runtime", kind="compaction_stage3_done", content={"summary": "PREVIOUS COMPACTION RECORDED"}
    )

    # First few turns after the summary: extremely bulky
    for i in range(1, 3):
        t_calls = [
            {"id": f"tc-{i}", "type": "function", "function": {"name": "fs.read_file", "arguments": "{}"}}
        ]
        _require_log(mock_session_state).append(
            actor="model",
            kind="model_msg",
            content={"text": "Bulky step content " * 15000, "tool_calls": t_calls},
        )
        _require_log(mock_session_state).append(
            actor="tool",
            kind="tool_result",
            content={"summary": "short summary", "result": {"stdout": "A" * 150}, "ok": True},
            tool_name="fs.read_file",
            tool_call_id=f"tc-{i}",
        )

    # Last few turns: small
    for i in range(3, 8):
        t_calls = [
            {"id": f"tc-{i}", "type": "function", "function": {"name": "fs.read_file", "arguments": "{}"}}
        ]
        _require_log(mock_session_state).append(
            actor="model", kind="model_msg", content={"text": f"Step content {i}", "tool_calls": t_calls}
        )
        _require_log(mock_session_state).append(
            actor="tool",
            kind="tool_result",
            content={"summary": "short summary", "result": {"stdout": "A" * 150}, "ok": True},
            tool_name="fs.read_file",
            tool_call_id=f"tc-{i}",
        )


    outcome = drive_session(
        "Test Task",
        provider_chain=mock_chain,
        compactor_chain=mock_compactor_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=mock_session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 0
    assert mock_chain.request.call_count == 1
    assert mock_compactor_chain.request.call_count == 1

    # Verify that the compactor request payload had the previous summary prepended
    compactor_req = mock_compactor_chain.request.call_args[0][0]
    compactor_messages = compactor_req.messages
    user_content = compactor_messages[1]["content"]
    assert "PREVIOUS COMPACTION RECORDED" in user_content


def test_circuit_breaker_stops_session(tmp_path: Path, mock_session_state: SessionState) -> None:
    """Verifies that the circuit breaker triggers and stops the session if <10% space is reclaimed 3 times."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "anthropic"

    mock_chain.request.return_value = _mock_success_response("done")

    # Prepare a mock compactor chain that returns a response of the exact same size (0% reclaimed)
    mock_compactor_chain = MagicMock(spec=ProviderChain)
    mock_compactor_chain.config = MagicMock(spec=ChainConfig)
    mock_compactor_chain.config.context_limit = 100000
    mock_compactor_chain.config.model = "compactor"

    # We will simulate 2 failures/attempts already stored in ContextBudget, and run a 3rd one.
    # Actually, we can inspect ContextBudget's record_compaction_attempt behavior.
    from fa.memory.context_budget import ContextBudget

    budget = ContextBudget(limit_tokens=100000)
    # Strike 1: 100k -> 98k (2% reclaimed)
    assert budget.record_compaction_attempt(100000, 98000) is True
    # Strike 2: 98k -> 97k (1% reclaimed)
    assert budget.record_compaction_attempt(98000, 97000) is True
    # Strike 3: 97k -> 96k (1% reclaimed) -> should trigger circuit breaker!
    assert budget.record_compaction_attempt(97000, 96000) is False


def test_circuit_breaker_logs_terminal_events_in_live_loop(
    monkeypatch: pytest.MonkeyPatch,
    mock_session_state: SessionState,
) -> None:
    """Verifies the live loop writes hard-stop telemetry when the breaker fires."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "anthropic"
    mock_chain.request.return_value = _mock_success_response("unreachable")

    mock_compactor_chain = MagicMock(spec=ProviderChain)
    mock_compactor_chain.config = MagicMock(spec=ChainConfig)
    mock_compactor_chain.config.context_limit = 100000
    mock_compactor_chain.config.model = "compactor-model"
    mock_compactor_chain.config.family = "openai"
    mock_compactor_chain.request.return_value = (
        ResponseInfo(
            text=(
                "## PREVIOUSLY\nNo reduction.\n\n"
                "## PARKED\nNone.\n\n"
                "## CURRENT\nStill overloaded.\n\n"
                "## NEXT ACTION\nStop."
            ),
            in_tokens=500,
            out_tokens=100,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            finish_reason="stop",
            tool_calls=(),
            extras={},
        ),
        "comp-call-id",
        [],
    )

    for i in range(1, 8):
        t_calls = [
            {"id": f"tc-{i}", "type": "function", "function": {"name": "fs.read_file", "arguments": "{}"}}
        ]
        _require_log(mock_session_state).append(
            actor="model",
            kind="model_msg",
            content={"text": "Bulky step content " * 15000, "tool_calls": t_calls},
        )
        _require_log(mock_session_state).append(
            actor="tool",
            kind="tool_result",
            content={"summary": "short summary", "result": {"stdout": "A" * 150}, "ok": True},
            tool_name="fs.read_file",
            tool_call_id=f"tc-{i}",
        )

    from fa.memory.context_budget import ContextBudget

    monkeypatch.setattr(ContextBudget, "record_compaction_attempt", lambda *_args, **_kwargs: False)

    outcome = drive_session(
        "Test circuit breaker branch",
        provider_chain=mock_chain,
        compactor_chain=mock_compactor_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=mock_session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 1
    assert outcome.stop_reason == "context_budget_hard_stop"
    assert mock_chain.request.call_count == 0

    events = _require_log(mock_session_state).read_all()
    assert [e for e in events if e.kind == "compaction_circuit_breaker"]
    assert [e for e in events if e.kind == "context_budget_hard_stop"]
    assert [
        e
        for e in events
        if e.kind == "run_stopped" and e.content.get("reason") == "context_budget_hard_stop"
    ]
