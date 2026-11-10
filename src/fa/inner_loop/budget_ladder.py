"""The budget ladder: the driver's budget block, minus its exits.

Why this module exists
----------------------
``budget_turn`` answers "what did the budget decide" and ``budget_effects``
covers the two verdicts that never stop a run. What was left in the driver was
the 146-line block that decides whether the session *continues* — masking,
stage-3 compaction, the circuit breaker — and it could not move because every
terminal branch ended with ``return finish_at(...)``, which closes over
``collected_results`` and ``turn``.

This module moves the **decision**, not the exit. ``run_budget_ladder`` returns
a :class:`BudgetOutcome` that says "stop like this" or "carry on with these
values"; the driver performs the stop with the one function that owns it. The
plan's rule — ``finish_at`` stays with the state it captures — holds: nothing
here calls it.

What this buys, beyond fewer lines:

* the block can be exercised without a session. A stop is now an *assertion* on
  a returned value rather than a captured ``SessionOutcome``;
* the three exits are described once, in ``BudgetStop``, instead of being
  spelled out at three different indentation levels;
* the driver's body becomes one call plus one ``if``, which is what makes the
  remaining nesting fall from 7 to 5.

Behaviour is meant to be identical, and is asserted so rather than argued: the
golden trace oracle and both probes compare the full run before and after.

What is deliberately **not** here: ``run_stage2_masking`` and
``run_stage3_compaction``. They own their own rows and events and are already
separately tested; this module calls them and folds their results, so the
durable order (``compaction_warning`` → stage rows → ``run_stopped``) stays
produced by the same functions that produced it before.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from fa.inner_loop.budget_effects import (
    emit_context_warn as _emit_context_warn,
)
from fa.inner_loop.budget_effects import (
    record_budget_pressure as _record_budget_pressure,
)
from fa.inner_loop.budget_effects import (
    record_compaction_pressure as _record_compaction_pressure,
)
from fa.inner_loop.budget_turn import BudgetVerdict, classify_budget
from fa.inner_loop.compaction.compaction_turn import run_stage2_masking, run_stage3_compaction
from fa.inner_loop.state import EventLog
from fa.inner_loop.turn_state import TurnState
from fa.memory.context_budget import ContextBudget
from fa.output import EventBus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BudgetStop:
    """A stop the ladder decided on; the driver performs it.

    ``exit_code`` and ``reason`` are what ``finish_at`` needs, ``final_text`` is
    what the operator sees. Nothing else: a stop that carried the rows it had
    already written would duplicate the ownership this split is about — the
    rows are written here, the exit is taken there.
    """

    exit_code: int
    reason: str
    final_text: str


@dataclass(frozen=True)
class BudgetOutcome:
    """Either a stop, or the values the turn should continue with.

    Exactly one of ``stop`` / ``carry`` is meaningful, and ``stop`` is None on
    the continuing path — a caller cannot mistake "allow" for "stop quietly"
    because the stop carries its own reason string.
    """

    stop: BudgetStop | None
    verdict: BudgetVerdict
    usage: int
    #: Only populated when compaction changed the prompt; the driver keeps its
    #: own payload when this is None.
    messages_payload: tuple[dict[str, Any], ...] | None = None
    request_extras: Mapping[str, Any] | None = None


def run_budget_ladder(
    *,
    usage: int,
    budget: ContextBudget,
    turn: int,
    max_turns: int,
    log: EventLog,
    output: EventBus | None,
    turn_state: TurnState,
    tool_payload: Sequence[Mapping[str, Any]],
    compose_request: Any,
    compactor_chain: Any,
    artifact_store: Any,
    compaction_threshold: int | None,
) -> BudgetOutcome:
    """Apply the budget for one turn; return what the driver must do next.

    The order of operations is the contract and is unchanged from the driver's
    block: warn → compaction warning → (disabled) stop or continue →
    (enabled) mask → maybe compact → maybe stop.

    ``verdict`` is re-derived after masking and again after compaction, and the
    value returned is always the last one — Q#4 was a caller reading the
    pre-compaction ratio after a successful compaction, so the outcome carries
    the ratio it decided on, not the one it started with.
    """
    decision = budget.check(usage)
    verdict = classify_budget(
        decision,
        stage2_threshold=budget.stage2_threshold,
        stage3_threshold=budget.stage3_threshold,
    )
    turn_state.note_budget_ratio(verdict.ratio)

    if verdict.action == "warn":
        logger.warning("ContextBudget Gating Warning: %s", verdict.message)
        _record_budget_pressure(
            verdict,
            turn=turn,
            max_turns=max_turns,
            log=log,
            output=output,
            compaction_enabled=False,
        )
        return BudgetOutcome(stop=None, verdict=verdict, usage=usage)

    if verdict.action not in {"stage2", "stage3"}:
        return BudgetOutcome(stop=None, verdict=verdict, usage=usage)

    # S6: one observation point for compaction-level pressure, fired in BOTH the
    # enabled and disabled cases so the operator always sees the detection.
    compaction_enabled = compaction_threshold is not None
    _record_compaction_pressure(
        verdict,
        turn=turn,
        max_turns=max_turns,
        log=log,
        output=output,
        compaction_enabled=compaction_enabled,
    )
    logger.warning("compaction_enabled: %s", compaction_enabled)

    if not compaction_enabled:
        return _without_compaction(
            verdict=verdict,
            usage=usage,
            turn=turn,
            max_turns=max_turns,
            log=log,
            output=output,
        )

    return _with_compaction(
        verdict=verdict,
        usage=usage,
        budget=budget,
        turn=turn,
        max_turns=max_turns,
        log=log,
        output=output,
        turn_state=turn_state,
        tool_payload=tool_payload,
        compose_request=compose_request,
        compactor_chain=compactor_chain,
        artifact_store=artifact_store,
    )


def _without_compaction(
    *,
    verdict: BudgetVerdict,
    usage: int,
    turn: int,
    max_turns: int,
    log: EventLog,
    output: EventBus | None,
) -> BudgetOutcome:
    """Stage-2 continues with a warning; stage-3 stops here (nothing to compact)."""
    if verdict.action == "stage2":
        logger.warning("ContextBudget Stage 2 reached but compaction is disabled: %s", verdict.message)
        _record_budget_pressure(
            verdict,
            turn=turn,
            max_turns=max_turns,
            log=log,
            output=output,
            compaction_enabled=False,
        )
        return BudgetOutcome(stop=None, verdict=verdict, usage=usage)

    logger.warning("ContextBudget Gate Breach: Stage 3 reached! %s", verdict.message)
    log.append(
        actor="runtime",
        kind="context_budget_hard_stop",
        content=verdict.hard_stop_row(message=verdict.message),
    )
    _emit_context_warn(verdict, output=output, turn=turn, max_turns=max_turns, action="stage3")
    log.append(actor="runtime", kind="run_stopped", content={"reason": "context_budget_hard_stop", "turns": turn})
    return BudgetOutcome(
        stop=BudgetStop(exit_code=1, reason="context_budget_hard_stop", final_text=verdict.message),
        verdict=verdict,
        usage=usage,
    )


def _with_compaction(
    *,
    verdict: BudgetVerdict,
    usage: int,
    budget: ContextBudget,
    turn: int,
    max_turns: int,
    log: EventLog,
    output: EventBus | None,
    turn_state: TurnState,
    tool_payload: Sequence[Mapping[str, Any]],
    compose_request: Any,
    compactor_chain: Any,
    artifact_store: Any,
) -> BudgetOutcome:
    """Mask first, then compact only if masking left the prompt over interval-3."""
    stage2 = run_stage2_masking(
        turn=turn,
        max_turns=max_turns,
        history=turn_state.conversation_history,
        memory_summary=turn_state.memory_summary,
        usage=usage,
        budget=budget,
        log=log,
        output=output,
        tool_payload=tool_payload,
        compose_request=compose_request,
        artifact_store=artifact_store,
        recent_turns_to_keep=4,
    )

    messages_payload: tuple[dict[str, Any], ...] | None = None
    request_extras: Mapping[str, Any] | None = None
    if stage2.applied:
        verdict = stage2.verdict
        turn_state.adopt_compaction(history=stage2.history, ratio=verdict.ratio)
        messages_payload = tuple(stage2.messages_payload)
        request_extras = dict(stage2.request_extras)
        usage = stage2.usage

    if verdict.action != "stage3":
        return BudgetOutcome(
            stop=None,
            verdict=verdict,
            usage=usage,
            messages_payload=messages_payload,
            request_extras=request_extras,
        )

    stage3 = run_stage3_compaction(
        turn=turn,
        max_turns=max_turns,
        history=turn_state.conversation_history,
        memory_summary=turn_state.memory_summary,
        usage=usage,
        budget=budget,
        log=log,
        output=output,
        tool_payload=tool_payload,
        compose_request=compose_request,
        compactor_chain=compactor_chain,
    )
    if stage3.stopped:
        # Q#4 at the exit itself: the ratio the session reports must describe the
        # state the stop was decided on (measured: 99% where the run died at 92%).
        turn_state.note_budget_ratio(stage3.verdict.ratio)
        return BudgetOutcome(
            stop=BudgetStop(exit_code=1, reason="context_budget_hard_stop", final_text=stage3.stop_message),
            verdict=stage3.verdict,
            usage=usage,
        )

    if not stage3.applied:
        return BudgetOutcome(
            stop=None,
            verdict=stage3.verdict,
            usage=usage,
            messages_payload=messages_payload,
            request_extras=request_extras,
        )

    turn_state.adopt_compaction(history=stage3.history, summary=stage3.memory_summary, ratio=stage3.verdict.ratio)
    return BudgetOutcome(
        stop=None,
        verdict=stage3.verdict,
        usage=stage3.usage,
        messages_payload=tuple(stage3.messages_payload),
        request_extras=dict(stage3.request_extras),
    )


__all__ = ["BudgetOutcome", "BudgetStop", "classify_budget", "run_budget_ladder"]
