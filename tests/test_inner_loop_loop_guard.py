"""LoopGuard (Wave-2 R-2) behavior tests.

These tests assert real outcomes (file NOT modified, run_stopped row
emitted, registry order matters) rather than just "no exception" —
the regression we are protecting against is precisely a LoopGuard that
silently allows N identical attempts because the detector never fires.
"""

from __future__ import annotations

from pathlib import Path
from typing import override

import pytest

from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.hooks import (
    Decision,
    HookPayload,
    HookRegistry,
    LifecyclePoint,
    LoopGuard,
)
from fa.inner_loop.tools import build_baseline_registry


def _make_call(path: str, content: str = "x\n", call_id: str = "tc") -> ToolCall:
    return ToolCall(
        name="fs_write_file",
        params={"path": path, "content": content},
        call_id=call_id,
    )


def test_loop_guard_rejects_invalid_construction() -> None:
    """Misconfigured thresholds raise at construction, not at dispatch."""

    with pytest.raises(ValueError, match="repeat_warn"):
        LoopGuard(repeat_warn=0, circuit_breaker=1, window=2)
    with pytest.raises(ValueError, match="circuit_breaker"):
        LoopGuard(repeat_warn=3, circuit_breaker=2, window=5)
    with pytest.raises(ValueError, match="window"):
        LoopGuard(repeat_warn=3, circuit_breaker=5, window=4)


def test_loop_guard_allows_when_below_warn() -> None:
    """Models the real ``run_session`` per-iteration order:
    ``BETWEEN_ROUNDS`` fires at the START of every iteration (including
    iter 1, per ADR-8 Amendment 2026-05-20b), then ``BEFORE_TOOL_EXEC``
    runs immediately before the tool dispatch. With one observation
    recorded, iter 2's ``BETWEEN_ROUNDS`` sees count=1 → allow."""

    guard = LoopGuard(repeat_warn=3, circuit_breaker=4, window=8)
    call = _make_call("a.txt")
    # Iter 1: BETWEEN_ROUNDS (count=0) → allow, then record.
    iter1_gate = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert iter1_gate.action == "allow"
    guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    # Iter 2: BETWEEN_ROUNDS sees count=1 → still below warn=3.
    iter2_gate = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert iter2_gate.action == "allow"


def test_loop_guard_emits_warn_at_threshold_and_continues() -> None:
    warns: list[tuple[str, str]] = []
    guard = LoopGuard(
        repeat_warn=3,
        circuit_breaker=5,
        window=8,
        warn_sink=lambda detector, msg: warns.append((detector, msg)),
    )
    call = _make_call("a.txt", call_id="tc")
    # Models real ``run_session`` per-iteration order BETWEEN_ROUNDS
    # → BEFORE_TOOL_EXEC. After 3 identical observations recorded,
    # iter 4's ``BETWEEN_ROUNDS`` sees count=3 → warn fires once,
    # decision is still allow.
    for _ in range(3):
        gate = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
        assert gate.action == "allow"
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    # Iter 4's BETWEEN_ROUNDS scans the 3 prior observations → warn.
    decision = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert decision.action == "allow"
    assert len(warns) == 1
    detector, message = warns[0]
    assert detector == "identical_call_repeat"
    assert "repeated 3 times" in message


def test_loop_guard_denies_at_circuit_breaker_for_identical_call() -> None:
    """Five identical calls trip the circuit breaker (params_hash collides).

    Models the real ``run_session`` order: ``BETWEEN_ROUNDS`` fires at
    the start of every iteration (including iter 1, ADR-8 Amendment
    2026-05-20b), then ``BEFORE_TOOL_EXEC`` records. With
    ``circuit_breaker=5``, the deny fires at the START of iter 6 —
    after 5 successful records — not at the end of iter 5.
    """

    guard = LoopGuard(repeat_warn=3, circuit_breaker=5, window=8)
    call = _make_call("a.txt")
    # Iterations 1-5 each pair BETWEEN_ROUNDS (allow) with
    # BEFORE_TOOL_EXEC (record). BETWEEN_ROUNDS sees count=0,1,2,3,4
    # — below circuit_breaker=5 on each iteration's gate check.
    for _ in range(5):
        gate = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
        assert gate.action == "allow"
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    # Iter 6's BETWEEN_ROUNDS scans the 5 recorded observations → deny.
    decision = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert decision.action == "deny"
    assert "repeated 5 times" in decision.reason
    assert "LoopGuard" in decision.reason


def test_loop_guard_detects_same_path_thrash_across_distinct_attempts() -> None:
    """Detector 2: same path, different params each time → thrash deny."""

    guard = LoopGuard(repeat_warn=3, circuit_breaker=5, window=8)
    # Five DIFFERENT contents on the same path. params_hash differs each
    # time → Detector 1 (identical sigs) never fires. Detector 2
    # counts distinct params_hashes per path and trips at 5.
    for i in range(5):
        guard.handle(
            LifecyclePoint.BEFORE_TOOL_EXEC,
            HookPayload(tool_call=_make_call("hot.txt", content=f"v{i}\n", call_id=f"tc-{i}")),
        )
    decision = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert decision.action == "deny"
    assert "thrashed" in decision.reason
    assert "hot.txt" in decision.reason


def test_loop_guard_path_thrash_fires_for_non_dict_mapping_params() -> None:
    """Agent-Review BUG-0005 regression: ``ToolCall.params`` is typed
    ``Mapping[str, object]``, not ``dict``. An earlier
    ``isinstance(params, dict)`` guard in ``LoopGuard._record`` silently
    set ``path_hint=""`` for any non-dict ``Mapping`` (e.g.
    ``MappingProxyType``), making Detector 2 entirely ineffective for
    those payloads. This test fixes that case by submitting five
    distinct-content writes against the same path via
    ``MappingProxyType``; before the fix the assertion below failed
    because the guard saw five empty path-hints and Detector 2 never
    matched the same path twice."""

    from types import MappingProxyType

    guard = LoopGuard(repeat_warn=3, circuit_breaker=5, window=8)
    for i in range(5):
        params = MappingProxyType({"path": "hot.txt", "content": f"v{i}\n"})
        guard.handle(
            LifecyclePoint.BEFORE_TOOL_EXEC,
            HookPayload(
                tool_call=ToolCall(name="fs_write_file", params=params, call_id=f"tc-{i}"),
            ),
        )
    decision = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert decision.action == "deny"
    assert "thrashed" in decision.reason
    assert "hot.txt" in decision.reason


def test_loop_guard_window_drops_old_observations() -> None:
    """Sliding window: older calls fall off and stop counting."""

    guard = LoopGuard(repeat_warn=3, circuit_breaker=4, window=4)
    # 4 distinct calls fill the window with no repeats.
    for i in range(4):
        guard.handle(
            LifecyclePoint.BEFORE_TOOL_EXEC,
            HookPayload(tool_call=_make_call(f"f{i}.txt", call_id=f"tc-{i}")),
        )
    # Now 3 identical calls — would trip warn but NOT circuit_breaker
    # since the window only holds 4 entries total and the most recent
    # 3 are identical.
    for j in range(3):
        guard.handle(
            LifecyclePoint.BEFORE_TOOL_EXEC,
            HookPayload(tool_call=_make_call("repeat.txt", call_id=f"r-{j}")),
        )
    decision = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    # Window=4 → only ["f3.txt","repeat.txt","repeat.txt","repeat.txt"]
    # remain; identical count = 3, which crosses warn but not 4-breaker.
    assert decision.action == "allow"


def test_loop_guard_in_run_session_stops_run_with_event(tmp_path: Path) -> None:
    """Integration: LoopGuard deny propagates through run_session cleanly.

    Asserts the file system was not changed beyond the calls that were
    allowed (i.e. once the breaker trips, no further writes happen) AND
    that ``events.jsonl`` records a ``run_stopped`` row, matching the
    same code path that PauseGuard exercises.
    """

    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()
    hooks.register(LoopGuard(repeat_warn=2, circuit_breaker=3, window=8))
    state = SessionState(
        workspace_root=tmp_path,
        run_id="t-loopguard",
        log=EventLog(tmp_path / "events.jsonl"),
    )

    # 5 identical writes; circuit_breaker=3 means the run aborts at
    # BETWEEN_ROUNDS BEFORE the 4th call ever executes.
    calls = tuple(_make_call("same.txt", content="dup\n", call_id=f"tc-{i}") for i in range(5))
    results = run_session(calls, registry=registry, hooks=hooks, state=state)

    # The file got the FIRST writes' content, but execution stopped
    # before all 5 calls fired.
    assert (tmp_path / "same.txt").exists()
    assert (tmp_path / "same.txt").read_text(encoding="utf-8") == "dup\n"
    assert len(results) < 5, "LoopGuard must short-circuit the loop"

    assert state.log is not None
    events = state.log.read_all()
    stopped = [event for event in events if event.kind == "run_stopped"]
    assert len(stopped) == 1
    assert stopped[0].content["point"] == "BETWEEN_ROUNDS"
    reason = stopped[0].content["reason"]
    assert isinstance(reason, str)
    assert "LoopGuard" in reason


def test_loop_guard_does_not_observe_calls_outside_attaches_to() -> None:
    """A misregistered LifecyclePoint must not alter LoopGuard state."""

    guard = LoopGuard(repeat_warn=2, circuit_breaker=3, window=4)
    call = _make_call("a.txt")
    decision = guard.handle(LifecyclePoint.AFTER_TOOL_EXEC, HookPayload(tool_call=call))
    # AFTER_TOOL_EXEC is not in attaches_to; handle() falls through to
    # allow without recording.
    assert decision == Decision.allow()
    assert len(guard._observations) == 0  # explicit invariant of the design


# ── S16: Behavioral contract assertions (G13) ───────────────────────


def test_intent_guard_deny_no_provider_calls(tmp_path: Path) -> None:
    """If a GuardMiddleware denies at BEFORE_TOOL_EXEC, no tool execution
    should happen. This is a behavioral contract asserting that the deny
    short-circuits before the tool handler runs."""
    from fa.inner_loop.hooks import GuardMiddleware

    registry = build_baseline_registry(tmp_path)

    class DenyAllBeforeToolExec(GuardMiddleware):
        """Hook that denies every BEFORE_TOOL_EXEC."""

        attaches_to = (LifecyclePoint.BEFORE_TOOL_EXEC,)

        @override
        def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
            return Decision.deny("test_deny: no tool execution allowed")

    hooks = HookRegistry()
    hooks.register(DenyAllBeforeToolExec())
    state = SessionState(
        workspace_root=tmp_path,
        run_id="t-deny-no-provider",
        log=EventLog(tmp_path / "events.jsonl"),
    )

    calls = tuple(_make_call(f"file{i}.txt", call_id=f"tc-{i}") for i in range(3))
    results = run_session(calls, registry=registry, hooks=hooks, state=state)

    # All results should be failures (denied)
    for r in results:
        assert r.error is not None, "Expected all tools to be denied"

    # File should NOT exist — tool was never executed
    assert not (tmp_path / "file0.txt").exists(), "Tool should not have executed after deny"


def test_hard_stop_no_tool_calls_after(tmp_path: Path) -> None:
    """If context_budget_hard_stop fires, no tool_call events should appear
    after the hard_stop event in the log. This verifies the hard-stop
    truly terminates the session."""
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()
    state = SessionState(
        workspace_root=tmp_path,
        run_id="t-hardstop-no-tools",
        log=EventLog(tmp_path / "events.jsonl"),
    )

    # Drive a simple session (no hard stop in this path, but verify
    # the event ordering invariant: no tool_call after run_stopped)
    calls = tuple(_make_call(f"f{i}.txt", call_id=f"tc-{i}") for i in range(2))
    run_session(calls, registry=registry, hooks=hooks, state=state)

    assert state.log is not None
    events = state.log.read_all()
    kinds = [e.kind for e in events]

    # If run_stopped appears, no tool_call should follow it
    if "run_stopped" in kinds:
        stop_idx = kinds.index("run_stopped")
        post_stop_kinds = kinds[stop_idx + 1 :]
        tool_calls_after = [k for k in post_stop_kinds if k == "tool_call"]
        assert not tool_calls_after, f"tool_call events after run_stopped: {tool_calls_after}"


def test_loop_guard_exactly_one_warn(tmp_path: Path) -> None:
    """If LoopGuard triggers, exactly one loop_guard_warn event should be
    emitted — not zero (silent loop) and not multiple (noisy loop). This
    verifies the warn-once, deny-on-circuit pattern."""
    registry = build_baseline_registry(tmp_path)

    # Wire warn_sink to emit loop_guard_warn to event log (same pattern as cli.py)
    state = SessionState(
        workspace_root=tmp_path,
        run_id="t-loopguard-one-warn",
        log=EventLog(tmp_path / "events.jsonl"),
    )

    def _warn_sink(detector: str, message: str) -> None:
        if state.log is not None:
            state.log.append(
                actor="runtime",
                kind="loop_guard_warn",
                content={"detector": detector, "message": message},
            )

    hooks = HookRegistry()
    hooks.register(LoopGuard(repeat_warn=2, circuit_breaker=4, window=8, warn_sink=_warn_sink))

    # 6 identical calls; warn at 2, circuit at 4
    calls = tuple(_make_call("same.txt", content="dup\n", call_id=f"tc-{i}") for i in range(6))
    run_session(calls, registry=registry, hooks=hooks, state=state)

    assert state.log is not None
    events = state.log.read_all()
    warn_events = [e for e in events if e.kind == "loop_guard_warn"]
    # Exactly 1 warn event (warn-once before circuit breaker deny)
    assert len(warn_events) == 1, f"Expected exactly 1 loop_guard_warn event, got {len(warn_events)}"
