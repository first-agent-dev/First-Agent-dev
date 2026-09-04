"""LoopGuard (Wave-2 R-2): non-progress circuit breaker.

A :class:`GuardMiddleware` that detects two non-progress patterns
in the recent tool-call history and denies the run when a hard
threshold is crossed. The thresholds come from
:class:`fa.inner_loop.runtime_limits.RuntimeLimits` (config-bounded
per ADR-7 §Amendment 2026-05-20 rule 1) — never magic constants in
the guard code.

Detectors (Kronos ``kronos/security/loop_detector.py`` shape; see
``borrow-roadmap-2026-05.md`` §R-2). The Kronos no-op-observation
detector remains deferred (it needs observation-content
fingerprinting, which the inner loop does not yet record):

1. **Identical-call repeat.** Same ``(tool_name, params_hash)`` shows
   up ``>= loop_guard_repeat_warn`` times in the trailing window
   → emit a ``kind="loop_guard_warn"`` event (allow). If the same
   sig hits ``loop_guard_circuit_breaker`` → deny.
2. **Ping-pong oscillation** (S12.7 CT1). The trailing window ends
   with ``2k`` calls alternating between exactly TWO distinct
   ``(tool_name, params_hash)`` sigs (A,B,A,B,…) → warn at
   ``loop_guard_pingpong_warn_cycles`` full cycles (default 3),
   deny at ``loop_guard_pingpong_break_cycles`` (default 4 = the
   default window). A one-sig "alternation" (pure repeat) never
   matches — that is Detector 1's domain — and advancing reads
   (all-distinct windows) are aperiodic and never match.

REMOVED in S12.7 (CT1): the former same-path thrash detector counted
distinct params-hashes per path and therefore denied *advancing* work
— five distinct-window reads of one file counted as thrash. Committed
live evidence (kimi l2 row 1788088035) shows it vetoing a correct
edit. Distinct params are progress, not thrash.

Every deny reason starts with ``LOOP_GUARD_REASON_PREFIX``; the loop
driver scopes session-terminal handling on that prefix (CT1).

Deny at the ``BETWEEN_ROUNDS`` lifecycle point so the runtime catches
the ``PermissionError`` in the same code path that already handles
``PauseGuard`` denials (see ``loop.py`` BETWEEN_ROUNDS try/except).

LoopGuard is **stateful per instance**: the trailing window lives on
``self``. Tests build a fresh registry per case; the smoke CLI builds
a fresh registry per ``fa run`` invocation. There is no cross-run
leakage.

The ``_warned`` set is never cleared during a single session: once a
warn fires for a given detector/key combo it will not fire again,
even if the pattern disappears and re-emerges later. This is
intentional log-spam reduction, not a bug.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from fa.inner_loop.hooks.base import (
    Decision,
    GuardMiddleware,
    HookPayload,
    LifecyclePoint,
)
from fa.inner_loop.recovery.attempt_history import canonical_params_hash
from fa.inner_loop.runtime_limits import (
    DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER,
    DEFAULT_LOOP_GUARD_PINGPONG_BREAK_CYCLES,
    DEFAULT_LOOP_GUARD_PINGPONG_WARN_CYCLES,
    DEFAULT_LOOP_GUARD_REPEAT_WARN,
    DEFAULT_LOOP_GUARD_WINDOW,
)

# Type alias for the optional warn-emitter the loop driver wires up.
# The caller passes a function that writes a ``kind="loop_guard_warn"``
# row to ``events.jsonl``; we keep the guard decoupled from EventLog
# so unit tests can pass a list-appender.
WarnSink = Callable[[str, str], None]

# S12.7 (CT1): single source of the guard-identity contract. Every
# LoopGuard deny reason starts with this prefix; ``coder_loop`` scopes
# session-terminal stop handling on it (point == BETWEEN_ROUNDS AND
# reason.startswith(this)). Consumer must IMPORT the constant — never
# re-type the literal. The prefix is already operator-load-bearing:
# the live-trial postmortem recipe greps it in events.jsonl.
LOOP_GUARD_REASON_PREFIX = "LoopGuard: "


@dataclass(frozen=True)
class _Observation:
    """One trailing-window row: a single tool-call signature."""

    tool_name: str
    params_hash: str


class LoopGuard(GuardMiddleware):
    """Non-progress detector — denies on identical repeats / ping-pong oscillation."""

    name = "LoopGuard"
    attaches_to = (LifecyclePoint.BEFORE_TOOL_EXEC, LifecyclePoint.BETWEEN_ROUNDS)

    def __init__(
        self,
        *,
        repeat_warn: int = DEFAULT_LOOP_GUARD_REPEAT_WARN,
        circuit_breaker: int = DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER,
        window: int = DEFAULT_LOOP_GUARD_WINDOW,
        pingpong_warn_cycles: int = DEFAULT_LOOP_GUARD_PINGPONG_WARN_CYCLES,
        pingpong_break_cycles: int = DEFAULT_LOOP_GUARD_PINGPONG_BREAK_CYCLES,
        warn_sink: WarnSink | None = None,
    ) -> None:
        if repeat_warn < 1:
            raise ValueError("repeat_warn must be >= 1")
        if circuit_breaker < repeat_warn:
            raise ValueError("circuit_breaker must be >= repeat_warn")
        if window < circuit_breaker:
            raise ValueError("window must be >= circuit_breaker")
        if pingpong_warn_cycles < 1:
            raise ValueError("pingpong_warn_cycles must be >= 1")
        if pingpong_break_cycles < pingpong_warn_cycles:
            raise ValueError("pingpong_break_cycles must be >= pingpong_warn_cycles")
        if 2 * pingpong_break_cycles > window:
            raise ValueError("window must be >= 2 * pingpong_break_cycles (a full alternation must fit)")
        self.repeat_warn = repeat_warn
        self.circuit_breaker = circuit_breaker
        self.window = window
        self.pingpong_warn_cycles = pingpong_warn_cycles
        self.pingpong_break_cycles = pingpong_break_cycles
        self._warn_sink = warn_sink
        self._observations: deque[_Observation] = deque(maxlen=window)
        # Tracks which detector/threshold combos already produced a
        # warn during the current window so each warn fires exactly
        # once per crossing rather than on every BETWEEN_ROUNDS tick.
        self._warned: set[tuple[str, str]] = set()

    def _record(self, payload: HookPayload) -> None:
        """Snapshot the current tool_call into the trailing window."""

        if payload.tool_call is None:
            return
        # ADR-7 §1 typing: ``ToolCall.params`` is ``Mapping[str, object]``,
        # not specifically ``dict``. ``canonical_params_hash`` consumes any
        # Mapping (MappingProxyType included) — no dict isinstance guard.
        params = payload.tool_call.params
        observation = _Observation(
            tool_name=payload.tool_call.name,
            params_hash=canonical_params_hash(payload.tool_call.name, params),
        )
        self._observations.append(observation)

    def _scan(self) -> Decision:
        """Run the detectors over the trailing window."""

        if not self._observations:
            return Decision.allow()

        # Detector 1: identical (tool, params_hash) repeats.
        sig_counts: dict[tuple[str, str], int] = {}
        for obs in self._observations:
            key = (obs.tool_name, obs.params_hash)
            sig_counts[key] = sig_counts.get(key, 0) + 1
        for (tool_name, params_hash), count in sig_counts.items():
            warn_key = ("identical", f"{tool_name}|{params_hash}")
            if count >= self.circuit_breaker:
                reason = (
                    f"{LOOP_GUARD_REASON_PREFIX}identical call {tool_name} "
                    f"({params_hash}) repeated {count} times "
                    f"(threshold {self.circuit_breaker})"
                )
                return Decision.deny(reason)
            if count >= self.repeat_warn and warn_key not in self._warned:
                self._warned.add(warn_key)
                self._emit_warn(
                    "identical_call_repeat",
                    f"{tool_name} repeated {count} times (warn threshold {self.repeat_warn})",
                )

        # Detector 3 (S12.7 CT1): period-2 ping-pong oscillation. The
        # predicate — the last 2k sigs satisfy sig[j] == sig[j-2] for all
        # j AND span exactly two distinct sigs — is monotone from the
        # back (if the last 2k alternate, so do the last 2(k-1)), so the
        # scan stops at the first k that fails. Pure repeats (one sig)
        # never match; advancing reads (all-distinct windows) never match.
        sigs = [(obs.tool_name, obs.params_hash) for obs in self._observations]
        cycles = 0
        for k in range(1, len(sigs) // 2 + 1):
            tail = sigs[-2 * k :]
            if len(set(tail)) != 2:
                break
            if any(tail[j] != tail[j - 2] for j in range(2, 2 * k)):
                break
            cycles = k
        if cycles >= self.pingpong_break_cycles:
            pair = sorted(set(sigs[-2 * self.pingpong_break_cycles :]))
            return Decision.deny(
                f"{LOOP_GUARD_REASON_PREFIX}ping-pong oscillation between "
                f"{pair[0][0]} and {pair[1][0]} "
                f"({cycles} cycles, threshold {self.pingpong_break_cycles})"
            )
        if cycles >= self.pingpong_warn_cycles:
            pair = sorted(set(sigs[-2 * cycles :]))
            warn_key = ("pingpong", f"{pair[0]}|{pair[1]}")
            if warn_key not in self._warned:
                self._warned.add(warn_key)
                self._emit_warn(
                    "pingpong_oscillation",
                    f"alternation between {pair[0][0]} and {pair[1][0]} reached {cycles} cycles "
                    f"(warn threshold {self.pingpong_warn_cycles})",
                )

        return Decision.allow()

    def _emit_warn(self, detector: str, message: str) -> None:
        """Best-effort warn emit — swallow errors so they never block."""

        if self._warn_sink is None:
            return
        try:
            self._warn_sink(detector, message)
        # Waiver: observer boundary — a failing warn sink must never block
        # tool execution.
        except Exception:  # noqa: BLE001, S110
            # Observers must never block tool execution; swallow any
            # error from the warn sink and move on.
            pass

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        if point is LifecyclePoint.BEFORE_TOOL_EXEC:
            self._record(payload)
            return Decision.allow()
        if point is LifecyclePoint.BETWEEN_ROUNDS:
            return self._scan()
        return Decision.allow()
