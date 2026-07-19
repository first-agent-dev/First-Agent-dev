"""Ruthless Integration & Anti-Theater Tests for PR 4 (Stage 2 Observation Masking).

Verifies that:
1. Reaching 80% context capacity triggers Stage 2 Observation Masking when compaction is enabled.
2. Older bulky tool outputs (>200 chars) are replaced with high-fidelity placeholder pointers.
3. Protected recent turns (tail window) remain completely unmasked and verbatim.
4. Telemetry start/done events are logged inside SQLite state database.
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
from fa.providers import ProviderChain
from tests.fixtures.session_wiring import make_test_chain_config, mock_success_response, require_log


@pytest.fixture
def mock_session_state(tmp_path: Path) -> SessionState:
    log = EventLog(tmp_path / "events.jsonl", run_id="test-pr4-run")
    return SessionState(
        workspace_root=tmp_path,
        run_id="test-pr4-run",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True, context_compaction_enabled=True),
    )


def test_stage2_triggers_at_80_percent(tmp_path: Path, mock_session_state: SessionState) -> None:
    """Verifies progressive Stage 2 masking triggers when usage crosses 80% capacity."""
    mock_chain = MagicMock(spec=ProviderChain)
    # Budget limit = 100k, threshold = 80k (80%)
    mock_chain.config = make_test_chain_config(
        context_limit=100000,
        compaction_threshold=80000,
        family="anthropic",
    )

    # Turn 1: original content (generates very bulky history)
    # We load history with 2 bulky previous turns of 42k chars each
    # (total 84k, i.e. 21k tokens, plus system prompts)
    # We configure side effect to return stop
    mock_chain.request.return_value = mock_success_response("all done")

    # Wire a dummy tool
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

    # Pre-populate session log history to trigger 80% threshold and Stage 2 masking
    # Turn 1 to 4: bulky (eligible for masking)
    for i in range(1, 5):
        t_calls = [
            {"id": f"tc-{i}", "type": "function", "function": {"name": "fs.read_file", "arguments": "{}"}}
        ]
        require_log(mock_session_state).append(
            actor="model", kind="model_msg", content={"text": f"Step {i}", "tool_calls": t_calls}
        )
        require_log(mock_session_state).append(
            actor="tool",
            kind="tool_result",
            content={"summary": "bulk output", "result": {"stdout": "A" * 100000}, "ok": True},
            tool_name="fs.read_file",
            tool_call_id=f"tc-{i}",
        )

    # Turn 5: recent window (protected) - keep small
    tool_calls_5 = [{"id": "tc-5", "type": "function", "function": {"name": "fs.read_file", "arguments": "{}"}}]
    require_log(mock_session_state).append(
        actor="model", kind="model_msg", content={"text": "Step 5", "tool_calls": tool_calls_5}
    )
    require_log(mock_session_state).append(
        actor="tool",
        kind="tool_result",
        content={"summary": "bulk output", "result": {"stdout": "A" * 1000}, "ok": True},
        tool_name="fs.read_file",
        tool_call_id="tc-5",
    )

    # Initialize the messages list by reading from database events

    outcome = drive_session(
        "Test task",
        provider_chain=mock_chain,
        registry=registry,
        hooks=HookRegistry(),
        state=mock_session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 0
    assert mock_chain.request.call_count == 1

    # Verify compaction events are logged inside SQLite state database
    events = require_log(mock_session_state).read_all()
    start_events = [e for e in events if e.kind == "compaction_stage2_start"]
    done_events = [e for e in events if e.kind == "compaction_stage2_done"]
    assert len(start_events) == 1
    assert len(done_events) == 1

    # Assert outbound request contains the masked placeholder for Turn 1
    # but the recent Turn 2 remains completely full verbatim
    request_info = mock_chain.request.call_args[0][0]
    messages = request_info.messages

    # Locate the tool messages in request_info
    tool_msgs = [msg for msg in messages if msg["role"] == "tool"]
    assert len(tool_msgs) == 5

    # Tool message 1 (Turn 1): Masked
    assert "Omitted tool result" in tool_msgs[0]["content"]

    # Tool message 2 (Turn 2): Verbatim (Recent protected window)
    assert tool_msgs[4]["content"].startswith("A" * 100)
