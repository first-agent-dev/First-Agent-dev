"""Shared thin factories for composition-root wiring tests — per tests-writing skill.

Extracted after third duplication of mock ProviderChain + EventLog + SessionState helpers.

Keep factories thin; still call real `drive_session` root. Use tmp_path for FS.

Gold patterns:
- hooks=HookRegistry() real type
- tool_calls=() tuple
- _require_log narrowing Optional
- ResponseInfo with tool_calls tuple
- Thresholds from ContextBudget source when needed (not here)

This file is NOT a test file itself; it is imported by tests/test_*_wiring.py suites.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog, SessionState
from fa.providers import ChainConfig, ProviderChain
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


def make_mock_chain(
    context_limit: int = 150000,
    compaction_threshold: int | None = None,
    model: str = "test-model",
    family: str = "openai",
) -> MagicMock:
    """Create mock ProviderChain with ChainConfig fields — type-honest."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = context_limit
    mock_chain.config.compaction_threshold = compaction_threshold
    mock_chain.config.model = model
    mock_chain.config.family = family
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
