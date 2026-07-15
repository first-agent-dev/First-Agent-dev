"""Ruthless Integration & Anti-Theater Tests for PR 3 (PromptComposer Wiring).

Verifies that:
1. PromptComposer is the sole authority for prompt payload generation.
2. Named segment cache breakpoints are correctly attached.
3. Cache-control headers are cleanly stripped if prompt_caching is False.
4. Static AST check ensures no parallel, manual system-assembly paths exist.
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
    log = EventLog(tmp_path / "events.jsonl", run_id="test-pr3-run")
    return SessionState(
        workspace_root=tmp_path,
        run_id="test-pr3-run",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True, prompt_caching=True),
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


def test_drive_session_uses_prompt_composer(tmp_path: Path, mock_session_state: SessionState) -> None:
    """Verifies PromptComposer is called to construct payloads and caching controls."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "anthropic"  # Use anthropic to test cache breakpoints

    mock_chain.request.return_value = _mock_success_response("caching completed")

    from fa.inner_loop.hooks import HookRegistry

    outcome = drive_session(
        "Test task",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=mock_session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 0
    assert mock_chain.request.call_count == 1

    # Verify cache breakpoints exist in the request message payload
    request_info = mock_chain.request.call_args[0][0]
    messages = request_info.messages

    # Anthropic segments should have cache_control on system prompt (index 0)
    # and tool specifications (index 2)
    assert messages[0].get("cache_control") == {"type": "ephemeral"}
    assert messages[2].get("cache_control") == {"type": "ephemeral"}


def test_openai_prompt_cache_key_forwarded_into_request_extras(
    tmp_path: Path, mock_session_state: SessionState
) -> None:
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "openai"

    mock_chain.request.return_value = _mock_success_response("cache-key forwarded")

    from fa.inner_loop.hooks import HookRegistry

    outcome = drive_session(
        "Test task",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=mock_session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 0
    request_info = mock_chain.request.call_args[0][0]
    assert "prompt_cache_key" in request_info.extras
    assert request_info.extras["prompt_cache_retention"] == "1h"



def test_cache_headers_stripped_when_disabled(tmp_path: Path) -> None:
    """If prompt_caching feature flag is disabled, cache_control headers must be stripped."""
    log = EventLog(tmp_path / "events.jsonl", run_id="test-pr3-disabled")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="test-pr3-disabled",
        log=log,
        feature_flags=FeatureFlags(prompt_caching=False),  # Disabled
    )

    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100000
    mock_chain.config.compaction_threshold = 80000
    mock_chain.config.model = "test-model"
    mock_chain.config.family = "anthropic"

    mock_chain.request.return_value = _mock_success_response("no-cache completed")

    from fa.inner_loop.hooks import HookRegistry

    outcome = drive_session(
        "Test task",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
    )

    assert outcome.exit_code == 0
    request_info = mock_chain.request.call_args[0][0]
    messages = request_info.messages

    # Verify no cache_control headers are present anywhere in the requested messages
    for msg in messages:
        assert "cache_control" not in msg
    assert request_info.extras == {}


def test_prompt_composer_ast_invariants() -> None:
    """Static AST check (Anti-Theater): Verify coder_loop has no parallel manual system prompts assembly."""
    loop_file = Path("src/fa/inner_loop/coder_loop.py")
    assert loop_file.exists()
    content = loop_file.read_text(encoding="utf-8")

    # Verify imports
    assert "build_prompt_parts_v2" in content
    assert "to_anthropic_request_v2" in content
    assert "to_openai_request_v2" in content

    # Assert old "messages.append" or manual list setups have been deleted or migrated
    # "messages: list" is no longer defined or initialized directly
    assert "messages: list" not in content

    # Verify AST
    tree = ast.parse(content)
    has_composer_call = False
    has_request_call = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id == "build_prompt_parts_v2":
                    has_composer_call = True
                if node.func.id in ("to_anthropic_request_v2", "to_openai_request_v2"):
                    has_request_call = True

    assert has_composer_call, "build_prompt_parts_v2 call missing in coder_loop.py AST"
    assert has_request_call, "to_*_request_v2 conversion call missing in coder_loop.py AST"
