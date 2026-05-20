"""LoopGuard (Wave-2 R-2): non-progress circuit breaker.

A :class:`GuardMiddleware` that detects three non-progress patterns
in the recent tool-call history and denies the run when a hard
threshold is crossed. The thresholds come from
:class:`fa.inner_loop.runtime_limits.RuntimeLimits` (config-bounded
per ADR-7 §Amendment 2026-05-20 rule 1) — never magic constants in
the guard code.

Detectors (ported from Kronos
``kronos/security/loop_detector.py`` 3-detector shape; see
``borrow-roadmap-2026-05.md`` §R-2):

1. **Identical-call repeat.** Same ``(tool_name, params_hash)`` shows
   up ``>= loop_guard_repeat_warn`` times in the trailing window
   → emit a ``kind="loop_guard_warn"`` event (allow). If the same
   sig hits ``loop_guard_circuit_breaker`` → deny.
2. **Same-path thrash.** Same workspace-relative ``path`` parameter
   appears across multiple call sigs in the window
   → same warn/deny progression as (1).

Deny at the ``BETWEEN_ROUNDS`` lifecycle point so the runtime catches
the ``PermissionError`` in the same code path that already handles
``PauseGuard`` denials (see ``loop.py`` BETWEEN_ROUNDS try/except).

LoopGuard is **stateful per instance**: the trailing window lives on
``self``. Tests build a fresh registry per case; the smoke CLI builds
a fresh registry per ``fa run`` invocation. There is no cross-run
leakage.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from fa.inner_loop.hooks.base import (
    Decision,
    GuardMiddleware,
    HookPayload,
    LifecyclePoint,
)
from fa.inner_loop.recovery.attempt_history import canonical_params_hash
from fa.inner_loop.runtime_limits import (
    DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER,
    DEFAULT_LOOP_GUARD_REPEAT_WARN,
    DEFAULT_LOOP_GUARD_WINDOW,
)

# Type alias for the optional warn-emitter the loop driver wires up.
# The caller passes a function that writes a ``kind="loop_guard_warn"``
# row to ``events.jsonl``; we keep the guard decoupled from EventLog
# so unit tests can pass a list-appender.
WarnSink = Callable[[str, str], None]


@dataclass(frozen=True)
class _Observation:
    """One trailing-window row: a single tool-call signature."""

    tool_name: str
    params_hash: str
    path_hint: str


class LoopGuard(GuardMiddleware):
    """Non-progress detector — denies on repeated identical / thrash patterns."""

    name = "LoopGuard"
    attaches_to = (LifecyclePoint.BEFORE_TOOL_EXEC, LifecyclePoint.BETWEEN_ROUNDS)

    def __init__(
        self,
        *,
        repeat_warn: int = DEFAULT_LOOP_GUARD_REPEAT_WARN,
        circuit_breaker: int = DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER,
        window: int = DEFAULT_LOOP_GUARD_WINDOW,
        warn_sink: WarnSink | None = None,
    ) -> None:
        if repeat_warn < 1:
            raise ValueError("repeat_warn must be >= 1")
        if circuit_breaker < repeat_warn:
            raise ValueError("circuit_breaker must be >= repeat_warn")
        if window < circuit_breaker:
            raise ValueError("window must be >= circuit_breaker")
        self.repeat_warn = repeat_warn
        self.circuit_breaker = circuit_breaker
        self.window = window
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
        params = payload.tool_call.params
        path_hint = str(params.get("path", "")) if isinstance(params, dict) else ""
        observation = _Observation(
            tool_name=payload.tool_call.name,
            params_hash=canonical_params_hash(payload.tool_call.name, params),
            path_hint=path_hint,
        )
        self._observations.append(observation)

    def _scan(self) -> Decision:
        """Run the two detectors over the trailing window."""

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
                    f"LoopGuard: identical call {tool_name} "
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

        # Detector 2: same-path thrash. Count rows by ``path_hint``
        # across DIFFERENT params_hashes — same file, different
        # attempts (typical fix-edit-fix-edit churn). Pure-repeat
        # (same params_hash) is already captured by Detector 1.
        path_sigs: dict[str, set[str]] = {}
        for obs in self._observations:
            if not obs.path_hint:
                continue
            path_sigs.setdefault(obs.path_hint, set()).add(obs.params_hash)
        for path, distinct_sigs in path_sigs.items():
            distinct = len(distinct_sigs)
            warn_key = ("thrash", path)
            if distinct >= self.circuit_breaker:
                reason = (
                    f"LoopGuard: path {path!r} thrashed across "
                    f"{distinct} distinct attempts "
                    f"(threshold {self.circuit_breaker})"
                )
                return Decision.deny(reason)
            if distinct >= self.repeat_warn and warn_key not in self._warned:
                self._warned.add(warn_key)
                self._emit_warn(
                    "same_path_thrash",
                    f"path {path!r} hit by {distinct} distinct attempts "
                    f"(warn threshold {self.repeat_warn})",
                )

        return Decision.allow()

    def _emit_warn(self, detector: str, message: str) -> None:
        """Best-effort warn emit — swallow errors so they never block."""

        if self._warn_sink is None:
            return
        try:
            self._warn_sink(detector, message)
        except Exception:
            # Observers must never block tool execution; swallow any
            # error from the warn sink and move on.
            pass

    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        if point is LifecyclePoint.BEFORE_TOOL_EXEC:
            self._record(payload)
            return Decision.allow()
        if point is LifecyclePoint.BETWEEN_ROUNDS:
            return self._scan()
        return Decision.allow()
