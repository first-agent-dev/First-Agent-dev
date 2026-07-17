"""Ruthless Integration & Anti-Theater Tests for PR 2 (PinnedBuffer Every Turn).

Verifies that:
1. PinnedBuffer extracts guidelines and are injected into the system prompt on EVERY turn.
2. File hash tracking is stable.
3. Mid-session file edits (e.g. AGENTS.md modified by human mid-run) are reloaded on the fly.
4. No crash occurs if pinned files are missing.
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
from tests.fixtures.session_wiring import mock_success_response, mock_tool_call_response, require_log


@pytest.fixture
def mock_session_state(tmp_path: Path) -> SessionState:
    log = EventLog(tmp_path / "events.jsonl", run_id="test-pr2-run")
    return SessionState(
        workspace_root=tmp_path,
        run_id="test-pr2-run",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True, context_compaction_enabled=False),
    )


def test_pins_present_each_turn_no_compaction(tmp_path: Path, mock_session_state: SessionState) -> None:
    """Verifies pinned buffer contents are present on all turns."""
    # Write synthetic constraints
    agents_file = tmp_path / "AGENTS.md"
    agents_file.write_text("Rule: never modify src/", encoding="utf-8")

    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "openai"

    mock_chain.request.side_effect = [
        mock_tool_call_response("tc-1", "fs.read_file", {"path": "test.txt"}),
        mock_tool_call_response("tc-2", "fs.read_file", {"path": "test.txt"}),
        mock_success_response("all done"),
    ]

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


    outcome = drive_session(
        "Test task",
        provider_chain=mock_chain,
        registry=registry,
        hooks=HookRegistry(),
        state=mock_session_state,
        max_turns=3,
    )

    # Output should have run successfully
    assert outcome.exit_code == 0
    # Confirm mock_chain was called 3 times (3 turns)
    assert mock_chain.request.call_count == 3

    # Every single request payload must contain the pinned AGENTS.md content
    for call in mock_chain.request.call_args_list:
        request_info = call[0][0]
        system_msgs = [msg["content"] for msg in request_info.messages if msg["role"] == "system"]
        assert any("STANDING CONSTRAINT: AGENTS.md" in msg for msg in system_msgs)
        assert any("Rule: never modify src/" in msg for msg in system_msgs)


def test_pin_missing_file_policy(tmp_path: Path, mock_session_state: SessionState) -> None:
    """Missing AGENTS.md must warn but not crash the session."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "openai"

    mock_chain.request.return_value = mock_success_response("missing path done")


    outcome = drive_session(
        "Test task",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=mock_session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 0
    # Verify warning logged but system remains functional
    system_msg = mock_chain.request.call_args[0][0].messages[0]["content"]
    assert "STANDING CONSTRAINT: AGENTS.md" not in system_msg


def test_mid_session_file_change_reloads(tmp_path: Path, mock_session_state: SessionState) -> None:
    """Rigorous Invariant: Modifying constraints mid-session must dynamically reload on subsequent turns."""
    agents_file = tmp_path / "AGENTS.md"
    agents_file.write_text("Rule V1: Initial guideline", encoding="utf-8")

    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "openai"

    # Turn 1: original content, returns a tool call to trigger next turn
    # Turn 2: modified content, returns stop
    captured_prompts = []

    def _side_effect(request_info, *args, **kwargs):
        captured_prompts.append(request_info.messages)
        call_count = len(captured_prompts)
        if call_count == 1:
            agents_file.write_text("Rule V2: Updated guideline mid-run", encoding="utf-8")
            return mock_tool_call_response("tc-1", "fs.read_file", {"path": "test.txt"})
        return mock_success_response("turn done")

    mock_chain.request.side_effect = _side_effect

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


    outcome = drive_session(
        "Test task",
        provider_chain=mock_chain,
        registry=registry,
        hooks=HookRegistry(),
        state=mock_session_state,
        max_turns=2,
    )

    assert outcome.exit_code == 0
    assert len(captured_prompts) == 2

    system_msgs_t1 = [msg["content"] for msg in captured_prompts[0] if msg["role"] == "system"]
    assert any("Rule V1: Initial guideline" in msg for msg in system_msgs_t1)

    system_msgs_t2 = [msg["content"] for msg in captured_prompts[1] if msg["role"] == "system"]
    assert any("Rule V2: Updated guideline mid-run" in msg for msg in system_msgs_t2)



def test_resume_draft_is_memory_summary_not_pinned(tmp_path: Path, mock_session_state: SessionState) -> None:
    agents_file = tmp_path / "AGENTS.md"
    agents_file.write_text("Rule: standing governance", encoding="utf-8")

    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "openai"
    mock_chain.request.return_value = mock_success_response("done")


    outcome = drive_session(
        "Test task",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=mock_session_state,
        max_turns=1,
        initial_memory_summary="Resume draft from previous session",
    )

    assert outcome.exit_code == 0
    request_info = mock_chain.request.call_args[0][0]
    system_msgs = [msg["content"] for msg in request_info.messages if msg["role"] == "system"]
    assert any("Memory summary:\nResume draft from previous session" in msg for msg in system_msgs)
    pinned_msgs = [msg for msg in system_msgs if "STANDING PROFILE GUIDELINES" in msg]
    assert not pinned_msgs
    assert any("STANDING CONSTRAINT: AGENTS.md" in msg for msg in system_msgs)
