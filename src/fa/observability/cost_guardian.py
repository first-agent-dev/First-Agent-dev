"""Cost guardian observer + guard (Wave-3 R-45).

A single :class:`GuardMiddleware` that mirrors the
:class:`fa.inner_loop.hooks.blockers.BlockerMiddleware` shape:

- ``AFTER_TOOL_EXEC`` — observe-in-handle. The guardian invokes
  the injected ``CostExtractor`` against ``payload.tool_result``;
  if the extractor returns a :class:`CostObservation` it is added
  to the rolling :class:`CostRollup` and (optionally) one
  ``kind="cost_observation"`` row lands in the audit log. The
  decision is always ``Decision.allow()``.
- ``BEFORE_TOOL_EXEC`` — gate. When the configured ``budget_usd``
  is positive and the rolling ``usd`` total has already exceeded
  it, the guardian denies the next call with a budget-quote
  reason; otherwise allows.

``budget_usd`` semantics mirror ``*_suppression_seconds`` on
:class:`fa.inner_loop.runtime_limits.RuntimeLimits`:

- ``None`` — unbounded (the default; no gating, no observation
  emission rate-limiting).
- ``0.0`` — **observe-only**; the extractor still runs and the
  rollup still accumulates, but ``_gate`` never denies. Useful
  during the T-2 LLM-driver landing for collecting a real-world
  usd baseline before tightening a real budget.
- ``> 0`` — hard cap; the next tool call after the rollup crosses
  the budget is denied. There is **no per-call extrapolation** —
  the gate compares the *recorded* total to the budget, not a
  predicted "next call would push past" estimate. Rationale:
  predictions need a cost model the M-1 substrate does not
  carry; the observed-total check is enough to stop runaway
  loops, and the LLM driver can layer a predictive gate on top
  later if the observed-total check proves insufficient.

**Dormant on baseline M-1 tools** — the
:func:`default_cost_extractor` looks for a ``cost=...`` artifact
in :attr:`ToolResult.artifacts` (the artifact shape the T-2 LLM
driver will produce when wrapping provider calls). Baseline
``fs.read_file`` / ``fs.write_file`` / ``fs.run_bash`` results
do not emit such an artifact, so ``_observe`` exits cleanly and
no rollup row lands. Wiring the guardian into the inner-loop
smoke entrypoint now keeps the chain stable for T-2 without
churning the registry shape — same posture as
:class:`fa.inner_loop.hooks.blockers.BlockerMiddleware` per its
module docstring.

References:
- ``knowledge/research/borrow-roadmap-2026-05.md`` §R-45
- YT-4 ``cost-tracker`` per-call rollup pattern
- Aperant ``pause-handler.ts:30-80`` (prod-tuned cost-tracking
  cadence; same source as :class:`RateLimitBlocker`)
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from fa.inner_loop.hooks.base import (
    Decision,
    GuardMiddleware,
    HookPayload,
    LifecyclePoint,
)
from fa.inner_loop.registry import ToolResult
from fa.inner_loop.state import EventLog

# Marker prefix the default extractor recognises in
# ``ToolResult.artifacts``. The artifact shape is
# ``"cost=tokens_in=<int>,tokens_out=<int>,usd=<float>"``; one entry
# per call. The T-2 LLM driver emits one of these per provider call.
# Tests can construct synthetic ``ToolResult`` instances with this
# artifact to drive the guardian without an LLM provider.
COST_ARTIFACT_PREFIX = "cost="


@dataclass(frozen=True)
class CostObservation:
    """One per-call cost sample: tokens-in / tokens-out / usd.

    ``usd`` must be a finite, non-negative number. NaN / +Inf / -Inf
    are rejected early because they silently poison the rollup
    (``x + NaN == NaN`` is permanent; ``NaN > budget`` is always
    ``False`` so the guardian gate stops denying any call for the
    rest of the session, +Inf flips that to permanent-deny). The
    extractor must catch the parse error and observe-only-fail
    rather than constructing a bad observation.
    """

    tokens_in: int
    tokens_out: int
    usd: float

    def __post_init__(self) -> None:
        if self.tokens_in < 0:
            raise ValueError("tokens_in must be >= 0")
        if self.tokens_out < 0:
            raise ValueError("tokens_out must be >= 0")
        if math.isnan(self.usd) or math.isinf(self.usd):
            raise ValueError("usd must be a finite number (not NaN/Inf)")
        if self.usd < 0:
            raise ValueError("usd must be >= 0")


@dataclass(frozen=True)
class CostRollup:
    """Rolling totals across a session — pure value, no I/O."""

    tokens_in: int = 0
    tokens_out: int = 0
    usd: float = 0.0
    samples: int = 0

    def add(self, observation: CostObservation) -> CostRollup:
        return CostRollup(
            tokens_in=self.tokens_in + observation.tokens_in,
            tokens_out=self.tokens_out + observation.tokens_out,
            usd=self.usd + observation.usd,
            samples=self.samples + 1,
        )


CostExtractor = Callable[[ToolResult], list[CostObservation]]


def default_cost_extractor(result: ToolResult) -> list[CostObservation]:
    """Read every ``cost=...`` artifact from ``result.artifacts``.

    Returns one :class:`CostObservation` per artifact starting with
    :data:`COST_ARTIFACT_PREFIX`, in source order. Returns an empty
    list when no such artifact is present (the baseline-tool case);
    malformed artifacts are skipped rather than aborting the parse
    (observe-only-fail — a parse error must never block tool
    execution, and one bad row must not drop the good rows from the
    same call).

    ADR-7 §Sub-amendment 2026-05-21 mandates «one row per recognised
    `cost=…` artifact» so the contract is plural by construction:
    a single tool call may emit several artifacts (retry chain,
    router fan-out, batch call) and each one is a separate sample
    in the rollup.

    Recognised keys: ``tokens_in``, ``tokens_out``, ``usd``. Missing
    keys default to ``0``. The order of the pairs is not significant.
    """

    observations: list[CostObservation] = []
    for raw in result.artifacts:
        if not raw.startswith(COST_ARTIFACT_PREFIX):
            continue
        body = raw[len(COST_ARTIFACT_PREFIX) :]
        fields: dict[str, str] = {}
        for pair in body.split(","):
            if "=" not in pair:
                continue
            key, _, value = pair.partition("=")
            fields[key.strip()] = value.strip()
        try:
            observations.append(
                CostObservation(
                    tokens_in=int(fields.get("tokens_in", "0")),
                    tokens_out=int(fields.get("tokens_out", "0")),
                    usd=float(fields.get("usd", "0")),
                )
            )
        except (ValueError, TypeError):
            # Malformed artifact — observe-only-fail, skip but keep
            # parsing the rest of ``result.artifacts``.
            continue
    return observations


class CostGuardian(GuardMiddleware):
    """R-45 cost guardian — accumulate per-call cost, deny over budget.

    Single :class:`GuardMiddleware` that attaches to both
    ``BEFORE_TOOL_EXEC`` (gate) and ``AFTER_TOOL_EXEC`` (observe).
    Mirrors :class:`fa.inner_loop.hooks.blockers.BlockerMiddleware`
    shape — see module docstring for the observe-in-handle rationale
    (one class, both lifecycle points, no separate Observer subclass).

    State is per-instance: :attr:`rollup` lives on ``self``. Tests
    build a fresh registry per case; the smoke CLI builds a fresh
    registry per ``fa`` invocation. No cross-run leakage.
    """

    name = "CostGuardian"
    attaches_to = (LifecyclePoint.BEFORE_TOOL_EXEC, LifecyclePoint.AFTER_TOOL_EXEC)

    def __init__(
        self,
        *,
        budget_usd: float | None = None,
        extractor: CostExtractor | None = None,
        event_log: EventLog | None = None,
    ) -> None:
        if budget_usd is not None and (math.isnan(budget_usd) or math.isinf(budget_usd)):
            raise ValueError("budget_usd must be a finite number (not NaN/Inf)")
        if budget_usd is not None and budget_usd < 0:
            raise ValueError("budget_usd must be None or >= 0 (0 = observe-only)")
        self.budget_usd = budget_usd
        self._extractor: CostExtractor = (
            extractor if extractor is not None else default_cost_extractor
        )
        self._event_log = event_log
        self.rollup = CostRollup()

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        if point is LifecyclePoint.BEFORE_TOOL_EXEC:
            return self._gate(payload)
        if point is LifecyclePoint.AFTER_TOOL_EXEC:
            self._observe(payload)
            return Decision.allow()
        return Decision.allow()

    def _gate(self, payload: HookPayload) -> Decision:
        # ``None`` => unbounded; ``0.0`` => observe-only. Either way
        # the gate allows. A budget breach denies on the *next* call
        # after the rollup crosses the line — no per-call prediction
        # (see module docstring §3 for rationale).
        if self.budget_usd is None or self.budget_usd <= 0:
            return Decision.allow()
        if self.rollup.usd > self.budget_usd:
            tool_name = payload.tool_call.name if payload.tool_call is not None else ""
            reason = (
                f"CostGuardian: session usd {self.rollup.usd:.6f} "
                f"exceeds budget {self.budget_usd:.6f} "
                f"(samples={self.rollup.samples}; next call to {tool_name!r} denied)"
            )
            return Decision.deny(reason)
        return Decision.allow()

    def _observe(self, payload: HookPayload) -> None:
        result = payload.tool_result
        if result is None:
            return
        # ADR-7 §Sub-amendment 2026-05-21: «one row per recognised
        # `cost=…` artifact». The extractor returns a list (possibly
        # empty); iterate in source order so the rollup snapshot in
        # each event-log row reflects the post-add total at that point.
        observations = self._extractor(result)
        if not observations:
            return
        call = payload.tool_call
        for observation in observations:
            self.rollup = self.rollup.add(observation)
            if self._event_log is None:
                continue
            self._event_log.append(
                actor="hook",
                kind="cost_observation",
                content={
                    "tokens_in": observation.tokens_in,
                    "tokens_out": observation.tokens_out,
                    "usd": observation.usd,
                    "rollup_tokens_in": self.rollup.tokens_in,
                    "rollup_tokens_out": self.rollup.tokens_out,
                    "rollup_usd": self.rollup.usd,
                    "rollup_samples": self.rollup.samples,
                },
                tool_name="" if call is None else call.name,
                tool_call_id="" if call is None else call.call_id,
            )


__all__ = [
    "COST_ARTIFACT_PREFIX",
    "CostExtractor",
    "CostGuardian",
    "CostObservation",
    "CostRollup",
    "default_cost_extractor",
]
