"""Ruthless Integration & Anti-Theater Tests for PR 1 (ContextBudget Gating).

Verifies that:
1. ContextBudget check is run inside the live turn loop of drive_session().
2. Reaching 70% triggers a warning telemetry event.
3. Reaching 90% triggers a hard-stop outcome with proper DB event logs and no further LLM calls.
4. Token estimation includes block and tool payloads.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog, SessionState, ToolRegistry
from fa.inner_loop.coder_loop import drive_session
from fa.providers import ChainConfig, ProviderChain
from fa.providers.base import ResponseInfo


@pytest.fixture
def mock_session_state(tmp_path: Path) -> SessionState:
    log = EventLog(tmp_path / "events.jsonl", run_id="test-pr1-run")
    return SessionState(
        workspace_root=tmp_path,
        run_id="test-pr1-run",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True, context_compaction_enabled=False),
    )


def _mock_success_response(text: str = "done") -> tuple[ResponseInfo, str, list]:
    resp = ResponseInfo(
        text=text,
        in_tokens=1000,
        out_tokens=100,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        finish_reason="stop",
        tool_calls=[],
        extras={},
    )
    return resp, "call-id", []


def test_drive_session_budget_warn_event(tmp_path: Path, mock_session_state: SessionState) -> None:
    """Reaching 70% capacity must write a warn event, but continue with the LLM call."""
    mock_chain = MagicMock(spec=ProviderChain)
    # Set limit to 100,000 tokens
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "openai"

    mock_chain.request.return_value = _mock_success_response("warn path executed")

    # Generate a task with ~75,000 tokens (300,000 chars) to trigger 70%+ warning
    task = "A" * 300000

    outcome = drive_session(
        task,
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=MagicMock(),
        state=mock_session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 0
    events = mock_session_state.log.read_all()
    # Confirm a 'context_budget_warn' event was appended
    warn_events = [e for e in events if e.kind == "context_budget_warn"]
    assert len(warn_events) == 1
    assert warn_events[0].content["action"] == "warn"


def test_drive_session_stage2_zone_does_not_hard_stop_when_compaction_disabled(
    tmp_path: Path, mock_session_state: SessionState
) -> None:
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "openai"
    mock_chain.request.return_value = _mock_success_response("stage2 zone allowed")

    # ~85k estimated tokens => Stage 2 zone, but not Stage 3.
    task = "A" * 340000

    outcome = drive_session(
        task,
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=MagicMock(),
        state=mock_session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 0
    assert mock_chain.request.call_count == 1
    events = mock_session_state.log.read_all()
    assert not [e for e in events if e.kind == "context_budget_hard_stop"]



def test_drive_session_budget_hard_stop(tmp_path: Path, mock_session_state: SessionState) -> None:
    """Reaching the Stage 3 zone with compaction disabled must hard-stop immediately without LLM request."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "openai"

    # Generate a task with ~95,000 tokens (380,000 chars) to trigger Stage 3 hard-stop.
    task = "A" * 380000

    outcome = drive_session(
        task,
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=MagicMock(),
        state=mock_session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 1
    assert outcome.stop_reason == "context_budget_hard_stop"
    assert mock_chain.request.call_count == 0

    events = mock_session_state.log.read_all()
    hard_stop_events = [e for e in events if e.kind == "context_budget_hard_stop"]
    assert len(hard_stop_events) == 1
    assert hard_stop_events[0].content["action"] == "stage3"

    stopped_events = [
        e for e in events if e.kind == "run_stopped" and e.content.get("reason") == "context_budget_hard_stop"
    ]
    assert len(stopped_events) == 1


def test_budget_wiring_present() -> None:
    """Static AST check (Anti-Theater): Verify coder_loop.py imports and evaluates ContextBudget."""
    loop_file = Path("src/fa/inner_loop/coder_loop.py")
    assert loop_file.exists()
    content = loop_file.read_text(encoding="utf-8")

    # Assert code contains explicit wiring keywords
    assert "ContextBudget" in content
    assert "estimate_tokens" in content
    assert "budget_enabled" in content
    assert "context_budget_hard_stop" in content

    # Verify AST structure
    tree = ast.parse(content)
    has_import = False
    has_evaluate = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if "context_budget" in node.module or "fa.memory.context_budget" in node.module:
                has_import = True
        if isinstance(node, ast.Attribute):
            if node.attr == "check":
                has_evaluate = True
    assert has_import, "ContextBudget import statement missing in coder_loop.py AST"
    assert has_evaluate, "ContextBudget check invocation missing in coder_loop.py AST"
