"""Shared thin factories for composition-root wiring tests — per tests-writing skill.

Extracted after third duplication of mock ProviderChain + EventLog + SessionState helpers.

Keep factories thin; still call real `drive_session` root. Use tmp_path for FS.

Gold patterns:
- hooks=HookRegistry() real type
- tool_calls=() tuple
- _require_log narrowing Optional
- ResponseInfo with tool_calls tuple
- Thresholds from ContextBudget source when needed (not here)

## Design principle: never mock dataclasses

Frozen dataclasses are pure data — no behavior, no side effects. Mocking them
with ``MagicMock(spec=...)`` creates latent regression bugs: when a new field
is added to the dataclass, the mock doesn't inherit it, so any production code
that accesses the new field raises ``AttributeError`` at runtime.

Instead, use real instances. Benefits:

- New fields with defaults just work (no test changes needed).
- New required fields break at import time with a clear TypeError
  (not at runtime in a specific test).
- Removed/renamed fields break at import time, not silently.
- The dataclass definition is the single source of truth.

Only mock objects with *behavior* (methods, side effects, state).
For ProviderChain we mock it because we need to control ``request()`` return
values. But its ``config`` attribute should be a real ``ChainConfig``.

This file is NOT a test file itself; it is imported by tests/test_*_wiring.py suites.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog, SessionState
from fa.providers import ChainConfig, ChainEntry, ProviderChain
from fa.providers.base import ResponseInfo


def require_log(state: SessionState) -> EventLog:
    """Narrow Optional log for type checkers — gold pattern."""
    assert state.log is not None
    return state.log


def mock_success_response(text: str = "done") -> tuple[ResponseInfo, str, list[Any]]:
    resp = ResponseInfo(
        text=text,
        in_tokens=100,
        out_tokens=10,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        finish_reason="stop",
        tool_calls=(),
        extras={},
    )
    return resp, "call-id-final", []


def mock_response_with_tools(
    tool_calls: list[dict[str, Any]], text: str = ""
) -> tuple[ResponseInfo, str, list[Any]]:
    resp = ResponseInfo(
        text=text,
        in_tokens=100,
        out_tokens=10,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        finish_reason="tool_calls",
        tool_calls=tuple(tool_calls),
        extras={},
    )
    return resp, "call-id-1", []


def make_tool_call(name: str, params: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(params)},
    }


def mock_tool_call_response(
    call_id: str, name: str, params: dict[str, Any]
) -> tuple[ResponseInfo, str, list[Any]]:
    """Convenience: create a ResponseInfo containing a single tool call.

    Used by pr2/pr4 wiring tests where a single tool call is returned per turn.
    Equivalent to ``mock_response_with_tools([make_tool_call(name, params, call_id)])``
    but with ``text="Executing tool"`` for parity with the original local defs.
    """
    return mock_response_with_tools(
        [make_tool_call(name, params, call_id)],
        text="Executing tool",
    )


# ── Real value-object factories ─────────────────────────────────────
# These replace MagicMock(spec=ChainConfig) with real ChainConfig instances.
# When a new field is added to ChainConfig with a default value, these
# factories inherit it automatically — zero test breakage.
# When a new required field is added, the factory's constructor call raises
# TypeError at import time with a clear message — not at runtime.


def make_test_chain_entry(
    provider: str = "openrouter",
    slug: str = "test/test-model",
    base_url: str = "https://openrouter.ai/api/v1",
    api_key_env: str = "TEST_API_KEY",
    **overrides: Any,
) -> ChainEntry:
    """Create a real ChainEntry with test defaults.

    Extra keyword arguments override any field on ChainEntry.
    """
    return ChainEntry(
        provider=provider,
        slug=slug,
        base_url=base_url,
        api_key_env=api_key_env,
        **overrides,
    )


def make_test_chain_config(
    role: str = "coder",
    model: str = "test-model",
    family: str = "openai",
    context_limit: int = 150000,
    compaction_threshold: int | None = None,
    extras: dict[str, Any] | None = None,
    **overrides: Any,
) -> ChainConfig:
    """Create a real ChainConfig with test defaults.

    Uses an empty chain tuple by default (no chain entries needed for most
    tests — the ProviderChain mock controls request() behavior directly).

    Extra keyword arguments override any field on ChainConfig. This is safe
    because ChainConfig is a frozen dataclass — unknown keys raise TypeError.

    **Why real ChainConfig, not MagicMock(spec=ChainConfig)?**

    Real instances automatically inherit new fields with defaults.
    MagicMock(spec=...) does not — it creates a latent regression bug where
    every new field on ChainConfig must be manually added to every mock site.
    """
    return ChainConfig(
        role=role,
        model=model,
        family=family,
        chain=(),
        context_limit=context_limit,
        compaction_threshold=compaction_threshold,
        extras=extras if extras is not None else {},
        **overrides,
    )


def make_mock_chain(
    context_limit: int = 150000,
    compaction_threshold: int | None = None,
    model: str = "test-model",
    family: str = "openai",
    extras: dict[str, Any] | None = None,
    **config_overrides: Any,
) -> MagicMock:
    """Create mock ProviderChain with a **real** ChainConfig.

    The ProviderChain itself is mocked (we control ``request()`` return
    values), but its ``config`` attribute is a real ``ChainConfig`` instance.
    This eliminates the entire class of "new field on dataclass breaks mocks"
    regressions.

    Extra keyword arguments are forwarded to ``make_test_chain_config()``.
    """
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = make_test_chain_config(
        context_limit=context_limit,
        compaction_threshold=compaction_threshold,
        model=model,
        family=family,
        extras=extras,
        **config_overrides,
    )
    return mock_chain


def make_session_state(
    tmp_path: Path,
    run_id: str,
    feature_flags: FeatureFlags | None = None,
    log_path: Path | None = None,
) -> SessionState:
    """Create SessionState with EventLog attached — for C1 tests."""
    lp = log_path or (tmp_path / "events.jsonl")
    log = EventLog(lp, run_id=run_id)
    flags = feature_flags if feature_flags is not None else FeatureFlags()
    return SessionState(
        workspace_root=tmp_path,
        run_id=run_id,
        log=log,
        feature_flags=flags,
    )
