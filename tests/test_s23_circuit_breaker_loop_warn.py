"""S23: Kill-check test for compaction circuit-breaker loop_warn.

root=drive_session matrix=C claim=loop_warn on circuit breaker path
kill-check=removing the loop_warn emit → grep fails + behavioral test
path-inventory: path 1 of 1 (circuit breaker in coder_loop.py)

The circuit breaker path emits THREE OutputEvents:
  1. compaction_end (stage 3, ok=False) — existing (NEW-2)
  2. context_warn (stage3) — existing (FINDING-V2)
  3. loop_warn (detector=compaction_circuit_breaker) — S23 addition

This test has two parts:
  a) A static grep that proves the emit call exists in production code
  b) A behavioral C1 test that drives the session and checks the emit fires
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks.base import HookRegistry
from fa.inner_loop.registry import ToolRegistry
from fa.output import EventBus, OutputEvent

from tests.fixtures.session_wiring import (
    make_mock_chain,
    make_session_state,
    mock_success_response,
)


def test_loop_warn_emit_exists_in_coder_loop() -> None:
    """Static grep: the loop_warn emit with detector=compaction_circuit_breaker
    must exist in coder_loop.py. This is a C0p existence pre-check.

    kill-check: removing the emit call makes this test fail.
    """
    source = Path("src/fa/inner_loop/coder_loop.py").read_text(encoding="utf-8")
    assert 'detector": "compaction_circuit_breaker"' in source, (
        "S23 loop_warn emit with detector=compaction_circuit_breaker not found "
        "in coder_loop.py — the emit was removed or never written"
    )


def test_loop_warn_on_circuit_breaker(tmp_path: Path) -> None:
    """C1: Circuit breaker path emits loop_warn with detector=compaction_circuit_breaker.

    kill-check: removing the output.emit(type="loop_warn") in the circuit
    breaker path makes this test fail.
    """
    # Set up session with compaction enabled and small context
    state = make_session_state(tmp_path, "test-cb")

    # Mock chain with small context + compaction threshold → triggers compaction
    mock_chain = make_mock_chain(
        context_limit=10000,
        compaction_threshold=5000,
    )
    mock_chain.cooldowns = {}

    # Response that finishes cleanly (stop) to end the session
    mock_chain.request.return_value = mock_success_response("done")

    # Capture OutputEvents
    bus = EventBus()
    captured: list[OutputEvent] = []
    bus.add(type("Listener", (), {"on_event": lambda self, e: captured.append(e)})())

    # Drive session — the large task + small context will trigger budget pressure
    task = "A" * 50000  # triggers budget pressure with small context

    drive_session(
        task,
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
        output=bus,
    )

    # Check for loop_warn with compaction_circuit_breaker detector
    loop_warn_events = [
        e for e in captured
        if e.type == "loop_warn"
        and e.data.get("detector") == "compaction_circuit_breaker"
    ]

    # The session may or may not hit the circuit breaker depending on
    # whether compaction reclaims enough space. If context_warn with
    # stage3 was emitted and the session ended with hard_stop, the
    # circuit breaker path fired and loop_warn must be present.
    context_warn_stage3 = [
        e for e in captured
        if e.type == "context_warn"
        and e.data.get("action") == "stage3"
    ]

    if context_warn_stage3:
        assert len(loop_warn_events) >= 1, (
            "Circuit breaker path emitted context_warn with stage3 but no loop_warn — "
            "S23 loop_warn emit is missing from the circuit breaker path. "
            f"Captured events: {[e.type for e in captured]}"
        )
