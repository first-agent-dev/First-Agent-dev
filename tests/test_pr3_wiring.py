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
from fa.inner_loop.hooks import HookRegistry
from fa.providers import ProviderChain
from tests.fixtures.session_wiring import make_test_chain_config, mock_success_response


@pytest.fixture
def mock_session_state(tmp_path: Path) -> SessionState:
    log = EventLog(tmp_path / "events.jsonl", run_id="test-pr3-run")
    return SessionState(
        workspace_root=tmp_path,
        run_id="test-pr3-run",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True, prompt_caching=True),
    )


def test_drive_session_uses_prompt_composer(tmp_path: Path, mock_session_state: SessionState) -> None:
    """Verifies PromptComposer is called to construct payloads and caching controls."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = make_test_chain_config(
        compaction_threshold=80000,
        context_limit=100000,
        family="anthropic",  # Use anthropic to test cache breakpoints,
    )

    mock_chain.request.return_value = mock_success_response("caching completed")

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
    mock_chain.config = make_test_chain_config(
        compaction_threshold=80000,
        context_limit=100000,
    )

    mock_chain.request.return_value = mock_success_response("cache-key forwarded")

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
    mock_chain.config = make_test_chain_config(
        compaction_threshold=80000,
        context_limit=100000,
        family="anthropic",
    )

    mock_chain.request.return_value = mock_success_response("no-cache completed")

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
    """C0: the driver delegates all three paths to the sole assembly owner."""
    loop_source = Path("src/fa/inner_loop/coder_loop.py").read_text(encoding="utf-8")
    composer_source = Path("src/fa/inner_loop/prompt_composer.py").read_text(encoding="utf-8")
    loop_tree = ast.parse(loop_source)
    composer_tree = ast.parse(composer_source)
    driver = next(n for n in loop_tree.body if isinstance(n, ast.FunctionDef) and n.name == "_drive_session_inner")
    closure = next(
        n for n in ast.walk(driver) if isinstance(n, ast.FunctionDef) and n.name == "_compose_request_payload"
    )
    owner = next(n for n in composer_tree.body if isinstance(n, ast.FunctionDef) and n.name == "compose_turn_request")

    def calls(node: ast.AST, name: str) -> int:
        return sum(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name for n in ast.walk(node)
        )

    # The driver owns assembly for all three paths. Since the compaction slice
    # the two compaction paths get the composer as a *callback* (the stage
    # functions live in another module and cannot close over the driver's
    # locals), so the invariant is "one call and two hand-offs", not "three
    # calls". Counting references, not `Call` nodes, keeps the check honest:
    # a stage that started assembling its own request would drop the reference
    # and fail here.
    assert calls(driver, "_compose_request_payload") == 1  # current turn
    handled = sum(
        isinstance(n, ast.keyword)
        and n.arg == "compose_request"
        and getattr(n.value, "id", None) == "_compose_request_payload"
        for n in ast.walk(driver)
    )
    assert handled == 2  # stage 2, stage 3
    assert calls(closure, "compose_turn_request") == 1
    assert calls(owner, "build_prompt_parts_v2") == 1
    assert calls(owner, "to_anthropic_request_v2") == 1
    assert calls(owner, "to_openai_request_v2") == 1
    assert calls(driver, "build_prompt_parts_v2") == 0
    assert "messages: list" not in loop_source  # forbid the old parallel assembly path


def test_composer_final_role_assertion_for_both_families() -> None:
    """C0: a malformed formatter output still fails before the provider."""
    from unittest.mock import patch

    from fa.inner_loop.prompt_composer import compose_turn_request

    for family, formatter in (("anthropic", "to_anthropic_request_v2"), ("openai", "to_openai_request_v2")):
        with patch(f"fa.inner_loop.prompt_composer.{formatter}", return_value={"messages": [{"role": "assistant"}]}):
            with pytest.raises(AssertionError, match="final provider-visible role"):
                compose_turn_request(
                    family=family,
                    base_system="base",
                    pinned_text="",
                    tool_defs=[],
                    role="coder",
                    task="task",
                    active_summary="",
                    observations=[],
                    turn_context="",
                    skills_conditional=None,
                )
