"""Kill-check tests for S1: Fix `or 150000` logic trap + MIN_CONTEXT_LIMIT floor.

Verifies:
1. Direct access: provider_chain.config.context_limit is used (no getattr, no `or`)
2. context_limit=0 is rejected upstream by ChainConfig.validate()
3. context_limit=100 (below MIN_CONTEXT_LIMIT) is clamped to 32000 with telemetry event
4. context_limit=150000 passes through unchanged (normal path)
5. compaction_threshold direct access works (no getattr fallback)
6. No `or 150000` code pattern remains in the source
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fa.inner_loop import EventLog, SessionState, ToolRegistry
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from fa.providers import ChainConfig, ProviderChain
from fa.providers.errors import ConfigurationError
from tests.fixtures.session_wiring import (
    make_test_chain_config,
    mock_success_response,
    require_log,
)

# ── Constants ────────────────────────────────────────────────────────

MIN_CONTEXT_LIMIT = 32_000
CODER_LOOP_PATH = Path("src/fa/inner_loop/coder_loop.py")


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def session_state(tmp_path: Path) -> SessionState:
    log = EventLog(tmp_path / "events.jsonl", run_id="test-s1-run")
    return SessionState(
        workspace_root=tmp_path,
        run_id="test-s1-run",
        log=log,
    )


# ── Kill-check 1: context_limit=0 is rejected upstream ───────────────


def test_context_limit_zero_rejected_by_chain_config() -> None:
    """ChainConfig.validate() rejects context_limit=0 with ConfigurationError.
    The `or 150000` trap that would silently convert 0→150000 is now removed,
    so the upstream validation is the sole defense against zero."""
    from fa.providers.chain import ChainEntry

    entry = ChainEntry(
        provider="test",
        model="test/model",
        base_url="https://api.example.com/v1",
        api_key_env="TEST_KEY",
    )
    cfg = ChainConfig(
        role="coder",
        name="test-model",
        family="test",
        chain=(entry,),
        context_limit=0,
    )
    with pytest.raises(ConfigurationError, match="context_limit must be a positive integer"):
        cfg.validate(require_api_keys=False)


# ── Kill-check 2: context_limit below floor is clamped ───────────────


def test_context_limit_below_floor_clamped(tmp_path: Path, session_state: SessionState) -> None:
    """context_limit=100 (a likely typo) should be clamped to MIN_CONTEXT_LIMIT=32000
    and a telemetry event should be emitted."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = make_test_chain_config(
        context_limit=100,  # Below MIN_CONTEXT_LIMIT — likely typo
    )
    mock_chain.request.return_value = mock_success_response("clamped path")

    # Small task — we're just testing the clamping, not budget behavior
    outcome = drive_session(
        "test task",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=session_state,
        max_turns=1,
    )

    # Session should succeed (clamping doesn't fail the session)
    assert outcome.exit_code == 0

    # Telemetry event should be logged
    events = require_log(session_state).read_all()
    telemetry_events = [e for e in events if e.kind == "telemetry"]
    clamp_events = [e for e in telemetry_events if "below floor" in str(e.content.get("message", ""))]
    assert len(clamp_events) == 1, f"Expected 1 clamp telemetry event, got {len(clamp_events)}"
    assert "context_limit=100" in str(clamp_events[0].content["message"])
    assert str(MIN_CONTEXT_LIMIT) in str(clamp_events[0].content["message"])


# ── Kill-check 3: normal context_limit passes through unchanged ──────


def test_context_limit_normal_passthrough(tmp_path: Path, session_state: SessionState) -> None:
    """context_limit=150000 (normal value) passes through without clamping
    and without telemetry events."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = make_test_chain_config(
        context_limit=150000,
    )
    mock_chain.request.return_value = mock_success_response("normal path")

    outcome = drive_session(
        "test task",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 0

    # No clamp telemetry events
    events = require_log(session_state).read_all()
    telemetry_events = [e for e in events if e.kind == "telemetry"]
    clamp_events = [e for e in telemetry_events if "below floor" in str(e.content.get("message", ""))]
    assert len(clamp_events) == 0, "No clamp event expected for normal context_limit"


# ── Kill-check 4: context_limit exactly at floor is NOT clamped ──────


def test_context_limit_at_floor_not_clamped(tmp_path: Path, session_state: SessionState) -> None:
    """context_limit=32000 (exactly at MIN_CONTEXT_LIMIT) should NOT be clamped."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = make_test_chain_config(
        context_limit=MIN_CONTEXT_LIMIT,  # Exactly at floor
    )
    mock_chain.request.return_value = mock_success_response("floor boundary")

    outcome = drive_session(
        "test task",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=session_state,
        max_turns=1,
    )

    assert outcome.exit_code == 0

    # No clamp telemetry events — 32000 is exactly at floor, not below
    events = require_log(session_state).read_all()
    telemetry_events = [e for e in events if e.kind == "telemetry"]
    clamp_events = [e for e in telemetry_events if "below floor" in str(e.content.get("message", ""))]
    assert len(clamp_events) == 0, "No clamp event for context_limit at floor"


# ── Static checks: no `or 150000` and no getattr on context_limit ───


def test_no_or_150000_code_pattern() -> None:
    """Source code must not contain `or 150000` as a code pattern (comments are OK)."""
    content = CODER_LOOP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            for val in node.values:
                if isinstance(val, ast.Constant) and val.value == 150000:
                    pytest.fail(
                        f"Found `or 150000` code pattern at line {node.lineno}. "
                        "The getattr+or fallback was a logic trap (swallowed 0)."
                    )


def test_no_getattr_context_limit_or_compaction_threshold() -> None:
    """Source code must not use getattr for context_limit or compaction_threshold
    on provider_chain.config — direct attribute access is now required."""
    content = CODER_LOOP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "getattr":
                # Check if any string arg is context_limit or compaction_threshold
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value in ("context_limit", "compaction_threshold"):
                            pytest.fail(
                                f"Found getattr(..., '{arg.value}', ...) at line {node.lineno}. "
                                f"ChainConfig always has this field — use direct access instead."
                            )


def test_direct_context_limit_access_exists() -> None:
    """Source code must access context_limit via direct attribute: provider_chain.config.context_limit"""
    content = CODER_LOOP_PATH.read_text(encoding="utf-8")
    assert "provider_chain.config.context_limit" in content, (
        "Expected direct access pattern `provider_chain.config.context_limit` not found"
    )
    assert "provider_chain.config.compaction_threshold" in content, (
        "Expected direct access pattern `provider_chain.config.compaction_threshold` not found"
    )


def test_min_context_limit_constant_exists() -> None:
    """Source code must define MIN_CONTEXT_LIMIT = 32_000."""
    content = CODER_LOOP_PATH.read_text(encoding="utf-8")
    assert "MIN_CONTEXT_LIMIT" in content, "MIN_CONTEXT_LIMIT constant not found"
    assert "32_000" in content or "32000" in content, "MIN_CONTEXT_LIMIT value not 32000"
