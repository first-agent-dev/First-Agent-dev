"""S12.7 (CT1) — LoopGuard ping-pong detector, reason-prefix contract, scoped
terminality, and the l2 replay regression.

Conventions per knowledge/skills/tests-writing: pyramid A (offline, mocked
provider I/O only); C0 = guard-unit; C1 = drive_session live path.

Path inventory (emit sites for the LoopGuard stop signal):
  Path 1: identical-repeat deny (Detector 1) — loop_guard.py `_scan`
  Path 2: ping-pong deny (Detector 3) — loop_guard.py `_scan`
  Path 3: warn emissions (both detectors) — allow + continue, never a stop
  Path 4: non-LoopGuard BETWEEN_ROUNDS stops (PauseGuard shape) — continue
"""

from __future__ import annotations

from pathlib import Path
from typing import override

import pytest

from fa.inner_loop import EventLog, SessionState, ToolCall
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import (
    Decision,
    GuardMiddleware,
    HookPayload,
    HookRegistry,
    LifecyclePoint,
    LoopGuard,
)
from fa.inner_loop.hooks.loop_guard import LOOP_GUARD_REASON_PREFIX
from fa.inner_loop.registry import ToolRegistry, ToolResult, ToolSpec
from fa.inner_loop.runtime_limits import load_runtime_limits
from fa.output import EventBus, OutputEvent
from tests.fixtures.session_wiring import make_mock_chain, mock_success_response, mock_tool_call_response

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _read(path: str, start: int, end: int, call_id: str) -> ToolCall:
    return ToolCall(
        name="t.read",
        params={"path": path, "start_line": start, "end_line": end},
        call_id=call_id,
    )


def _registry_with_read_tool(tmp_path: Path) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="t.read",
            description="Read a window",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
            },
            permission="read",
            handler=lambda params: ToolResult.ok(f"lines {params.get('start_line')}-{params.get('end_line')}"),
        )
    )
    return registry


class _CaptureListener:
    """p4 pattern: EventBus listeners need ``on_event`` — bare callables are
    swallowed by the bus's fail-open try/except."""

    def __init__(self) -> None:
        self.events: list[OutputEvent] = []

    def on_event(self, event: OutputEvent) -> None:
        self.events.append(event)


def _capture_bus() -> tuple[EventBus, _CaptureListener]:
    bus = EventBus()
    capture = _CaptureListener()
    bus.add(capture)
    return bus, capture


# ---------------------------------------------------------------------------
# C0 — Detector 3 (ping-pong) unit behavior
# ---------------------------------------------------------------------------


def test_s127_pingpong_warns_at_3_cycles_and_denies_at_4() -> None:
    """root=LoopGuard.handle matrix=A claim=Detector 3 warn/deny progression.

    producer-kill-check: removing the Detector 3 branch in `_scan` fails this test.
    """
    warns: list[tuple[str, str]] = []
    # repeat threshold 6 keeps Detector 1 silent in this test (counts reach
    # only 4), isolating Detector 3's progression.
    guard = LoopGuard(
        repeat_warn=6,
        circuit_breaker=7,
        window=8,
        pingpong_warn_cycles=3,
        pingpong_break_cycles=4,
        warn_sink=lambda d, m: warns.append((d, m)),
    )
    call_a = ToolCall(name="t.read", params={"path": "a", "start_line": 1, "end_line": 10}, call_id="a")
    call_b = ToolCall(name="t.read", params={"path": "a", "start_line": 99, "end_line": 110}, call_id="b")

    # 3 full A-B cycles (6 calls) → warn (k=3), decision still allow.
    for a, b in [(call_a, call_b)] * 3:
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=a))
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=b))
    decision = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert decision.action == "allow", f"k=3 must warn-and-allow, got {decision.action}: {decision.reason}"
    assert len(warns) == 1 and warns[0][0] == "pingpong_oscillation"
    assert "3 cycles" in warns[0][1]

    # 4th full cycle (8 calls = full window) → deny with the prefix.
    guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call_a))
    guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call_b))
    decision = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert decision.action == "deny"
    assert decision.reason.startswith(LOOP_GUARD_REASON_PREFIX)
    assert "ping-pong" in decision.reason
    assert "4 cycles" in decision.reason


def test_s127_pingpong_pure_repeats_belong_to_detector_1() -> None:
    """A one-sig 'alternation' (pure repeat) must deny via Detector 1, never D3."""
    guard = LoopGuard(repeat_warn=3, circuit_breaker=5, window=8)
    call = ToolCall(name="t.read", params={"path": "a", "start_line": 1, "end_line": 10}, call_id="a")
    for _ in range(8):
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    decision = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert decision.action == "deny"
    assert "identical call" in decision.reason
    assert "ping-pong" not in decision.reason

    # Scenario (b) — mutation-hardened (M2 sweep): pure repeats with Detector 1
    # SILENCED (rw=6/cb=7) and ping-pong thresholds low (1/2). sig[j]==sig[j-2]
    # holds trivially for one sig, so ONLY the exactly-two-distinct-sigs check
    # keeps this ALLOW. Dropping that check (len(set(tail)) != 2) turns four
    # repeats into a spurious "ping-pong" deny.
    warns: list[tuple[str, str]] = []
    guard_b = LoopGuard(
        repeat_warn=6,
        circuit_breaker=7,
        window=8,
        pingpong_warn_cycles=1,
        pingpong_break_cycles=2,
        warn_sink=lambda d, m: warns.append((d, m)),
    )
    for _ in range(4):
        guard_b.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    decision_b = guard_b.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert decision_b.action == "allow", (
        f"pure repeats must stay Detector 1's domain even when D1 is quiet; got {decision_b.reason}"
    )
    assert not [w for w in warns if w[0] == "pingpong_oscillation"], warns


def test_s127_pingpong_ignores_period_3_and_longer() -> None:
    """A,B,C rotation (3 distinct sigs) never matches the two-sig predicate."""
    guard = LoopGuard(repeat_warn=3, circuit_breaker=5, window=8)
    calls = [
        ToolCall(name="t.read", params={"path": "a", "start_line": i, "end_line": i + 10}, call_id=f"c{i}")
        for i in range(8)
    ]
    for call in calls:
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    decision = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert decision.action == "allow"


def test_s127_legit_edit_read_alternation_is_allowed() -> None:
    """T-pp-legit: edit→read→edit→read with ADVANCING params each cycle is
    progress (hashes differ per cycle), not a period-2 repeat — never denied."""
    guard = LoopGuard(repeat_warn=3, circuit_breaker=5, window=8)
    for i in range(4):
        edit = ToolCall(name="t.edit", params={"path": "a", "new": f"v{i}"}, call_id=f"e{i}")
        read = _read("a", 100 * i, 100 * i + 50, f"r{i}")
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=edit))
        gate = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
        assert gate.action == "allow", f"legit alternation denied: {gate.reason}"
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=read))
        gate = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
        assert gate.action == "allow", f"legit alternation denied: {gate.reason}"


# ---------------------------------------------------------------------------
# C0 — reason-prefix contract (producer + consumer pins)
# ---------------------------------------------------------------------------


def test_s127_every_deny_reason_carries_the_prefix() -> None:
    """Producer pin: both deny paths construct reasons from the single-sourced
    LOOP_GUARD_REASON_PREFIX. Kill-check: hardcoding/dropping the prefix on
    either path fails this test."""
    # identical-repeat path
    guard = LoopGuard(repeat_warn=3, circuit_breaker=5, window=8)
    call = ToolCall(name="t.read", params={"path": "a", "start_line": 1, "end_line": 10}, call_id="a")
    for _ in range(8):
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    d1 = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert d1.action == "deny" and d1.reason.startswith(LOOP_GUARD_REASON_PREFIX)
    # ping-pong path
    guard2 = LoopGuard(repeat_warn=3, circuit_breaker=5, window=8)
    a = ToolCall(name="t.read", params={"path": "a", "start_line": 1, "end_line": 10}, call_id="a")
    b = ToolCall(name="t.read", params={"path": "a", "start_line": 99, "end_line": 110}, call_id="b")
    for _ in range(4):
        guard2.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=a))
        guard2.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=b))
    d3 = guard2.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert d3.action == "deny" and d3.reason.startswith(LOOP_GUARD_REASON_PREFIX)


def test_s127_coder_loop_uses_the_imported_prefix_constant() -> None:
    """Consumer pin: coder_loop scopes terminality on the IMPORTED constant —
    the module attribute IS loop_guard's object (no local literal drift)."""
    import fa.inner_loop.coder_loop as coder_loop_module

    assert coder_loop_module.LOOP_GUARD_REASON_PREFIX is LOOP_GUARD_REASON_PREFIX


# ---------------------------------------------------------------------------
# C0 — constructor validation + config keys
# ---------------------------------------------------------------------------


def test_s127_ctor_validates_pingpong_thresholds() -> None:
    with pytest.raises(ValueError, match="pingpong_warn_cycles"):
        LoopGuard(repeat_warn=3, circuit_breaker=5, window=8, pingpong_warn_cycles=0)
    with pytest.raises(ValueError, match="pingpong_break_cycles"):
        LoopGuard(repeat_warn=3, circuit_breaker=5, window=8, pingpong_warn_cycles=3, pingpong_break_cycles=2)
    with pytest.raises(ValueError, match="window"):
        LoopGuard(repeat_warn=3, circuit_breaker=5, window=8, pingpong_warn_cycles=3, pingpong_break_cycles=5)


def test_s127_runtime_limits_parse_pingpong_keys() -> None:
    """Kill-check: dropping either key from _KNOWN_KEYS/parse makes this fail."""
    text = """\
capabilities:
  ENABLE_DYNAMIC_TOOLS: false

runtime_limits:
  loop_guard_pingpong_warn_cycles: 2
  loop_guard_pingpong_break_cycles: 3
"""
    result = load_runtime_limits(text)
    assert result.limits.loop_guard_pingpong_warn_cycles == 2
    assert result.limits.loop_guard_pingpong_break_cycles == 3
    assert not result.warnings


# ---------------------------------------------------------------------------
# C1 — live path (drive_session, mocked provider I/O)
# ---------------------------------------------------------------------------


def test_s127_l2_replay_distinct_window_reads_never_denied(tmp_path: Path) -> None:
    """T-l2-replay: the committed l2 shape — five DISTINCT-window reads of one
    file — must complete without any LoopGuard stop (the removed Detector 2
    denied exactly this; re-adding any path-counting detector fails here).

    root=drive_session matrix=A oracle=event kinds + call_count + trajectory.
    """
    log = EventLog(tmp_path / "events.jsonl", run_id="s127-l2-replay")
    state = SessionState(workspace_root=tmp_path, run_id="s127-l2-replay", log=log)
    hooks = HookRegistry()
    hooks.register(LoopGuard())  # production defaults 3/5/8 + pp 3/4
    registry = _registry_with_read_tool(tmp_path)

    windows = [(3300, 3400), (3400, 3500), (3500, 3600), (3440, 3451), (3331, 3431)]
    chain = make_mock_chain(context_limit=150_000)
    chain.request.side_effect = [
        mock_tool_call_response(f"c{i}", "t.read", {"path": "src/fa/cli.py", "start_line": a, "end_line": b})
        for i, (a, b) in enumerate(windows)
    ] + [mock_success_response("done")]

    outcome = drive_session(
        "l2 replay",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=8,
    )
    assert chain.request.call_count == 6, "all five reads + final answer must run"
    assert len([r for r in outcome.tool_results if r.error is None]) == 5
    events = log.read_all()
    guard_stops = [e for e in events if e.kind == "run_stopped" and "LoopGuard" in str(e.content.get("reason", ""))]
    assert not guard_stops, f"advancing reads were denied: {[e.content for e in guard_stops]}"


def test_s127_trip_terminates_in_band_with_dual_write(tmp_path: Path) -> None:
    """T-zombie (defaults matrix): the trip ends the session in-band — no
    further provider calls, no synthetic run_stopped results, and the
    hook_deny OutputEvent reaches the bus (dual-write contract)."""
    log = EventLog(tmp_path / "events.jsonl", run_id="s127-trip")
    state = SessionState(workspace_root=tmp_path, run_id="s127-trip", log=log)
    hooks = HookRegistry()
    hooks.register(LoopGuard())  # defaults: warn 3 / breaker 5 / window 8
    registry = _registry_with_read_tool(tmp_path)
    bus, capture = _capture_bus()

    same = {"path": "src/fa/cli.py", "start_line": 1, "end_line": 10}
    chain = make_mock_chain(context_limit=150_000)
    chain.request.side_effect = [mock_tool_call_response(f"c{i}", "t.read", same) for i in range(6)]

    drive_session(
        "trip test",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=8,
        output=bus,
    )
    # Breaker (5) fires at turn 6's gate → exactly 6 model calls, never 7+.
    assert chain.request.call_count == 6
    # Dual-write: the operator saw it too.
    denies = [e for e in capture.events if e.type == "hook_deny"]
    assert len(denies) >= 1
    assert str(denies[-1].data.get("reason", "")).startswith(LOOP_GUARD_REASON_PREFIX)
    # In-band termination durable in the log.
    stopped = [e for e in log.read_all() if e.kind == "run_stopped" and "LoopGuard" in str(e.content.get("reason", ""))]
    assert len(stopped) == 1


def test_s127_non_loopguard_between_rounds_stop_continues(tmp_path: Path) -> None:
    """T-pauseguard-untouched: a BETWEEN_ROUNDS denial WITHOUT the LoopGuard
    prefix (PauseGuard shape: "pause sentinel active: …") keeps the
    continue-by-design semantics — session iterates, synthetic padding
    present, no terminal break. Kill-check: dropping the prefix gate in
    coder_loop (making all BETWEEN_ROUNDS stops terminal) fails here."""

    class PauseSentinelShape(GuardMiddleware):
        name = "PauseSentinelShape"
        attaches_to = (LifecyclePoint.BETWEEN_ROUNDS,)

        @override
        def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
            return Decision.deny("pause sentinel active: manual")

    log = EventLog(tmp_path / "events.jsonl", run_id="s127-pause")
    state = SessionState(workspace_root=tmp_path, run_id="s127-pause", log=log)
    hooks = HookRegistry()
    hooks.register(PauseSentinelShape())
    registry = _registry_with_read_tool(tmp_path)

    chain = make_mock_chain(context_limit=150_000)
    chain.request.side_effect = [
        mock_tool_call_response(f"c{i}", "t.read", {"path": "a", "start_line": i, "end_line": i + 5}) for i in range(3)
    ]
    outcome = drive_session(
        "pause test",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=3,
    )
    assert chain.request.call_count == 3, "non-LoopGuard BETWEEN_ROUNDS stops must keep iterating"
    synthetics = [r for r in outcome.tool_results if r.error is not None and "pause sentinel active" in r.error.message]
    assert len(synthetics) == 3, "padding path must still produce the synthetic results (continue-by-design)"
