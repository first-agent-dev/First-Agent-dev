"""Effects of a context-budget verdict that do not change the session's fate.

Why this module exists
----------------------
``budget_turn`` answers "what did the budget decide". This module answers the
next question for the two verdicts whose answer is the same every time:

* ``warn`` — one durable row plus one console mirror, and the turn continues;
* ``stage2`` while compaction is disabled — the same, because the pressure is
  real but there is nothing to compact.

Those two paths had no session-level consequences, yet they lived in the middle
of a 399-line block whose other paths *do* end the run. That is how the two
budget-side defects happened (S6-F5's misleading reason, Q#4's stale ratio):
the harmless branches were indistinguishable from the fatal ones at the point of
reading.

Deliberately **not** here: the paths that can stop the session (stage-3 without
compaction, the circuit breaker, the post-compaction re-check) and the actual
compaction work. Moving those means deciding where ``finish_at`` lives and
guaranteeing the ``try``/mask ordering survives; that is its own slice, and
folding it in here would make this one impossible to review.

Behaviour is unchanged. The durable row is ``verdict.raw`` — the identical
mapping the driver appended before — and the percentage comes from
``verdict.ratio``, so a local variable cannot drift from the decision again.
"""

from __future__ import annotations

from fa.inner_loop.budget_turn import BudgetVerdict
from fa.inner_loop.state import EventLog
from fa.output import EventBus, OutputEvent


def record_budget_pressure(
    verdict: BudgetVerdict,
    *,
    turn: int,
    max_turns: int,
    log: EventLog,
    output: EventBus | None,
    compaction_enabled: bool,
) -> None:
    """Persist and mirror a non-terminal budget verdict.

    Ordering is part of the contract and is asserted by tests: the durable row
    is written first, then the console mirror.
    """
    if verdict.action == "warn":
        log.append(actor="runtime", kind="context_budget_warn", content=dict(verdict.raw))
        emit_context_warn(verdict, turn=turn, max_turns=max_turns, output=output, action="warn")
        return

    if verdict.action == "stage2" and not compaction_enabled:
        log.append(actor="runtime", kind="context_budget_warn", content=dict(verdict.raw))
        emit_context_warn(verdict, turn=turn, max_turns=max_turns, output=output, action="stage2")
        return

    raise ValueError(
        f"record_budget_pressure does not handle action={verdict.action!r} with "
        f"compaction_enabled={compaction_enabled}; that path can end the session and "
        "must stay in the driver until the stop slice moves it"
    )


def record_compaction_pressure(
    verdict: BudgetVerdict,
    *,
    turn: int,
    max_turns: int,
    log: EventLog,
    output: EventBus | None,
    compaction_enabled: bool,
) -> None:
    """Persist and mirror the ``compaction_warning`` row for stage-2/3 pressure.

    This fires in BOTH the enabled and the disabled case — the operator must see
    that pressure was detected regardless of whether anything will be done about
    it (S6). The ``threshold`` in the payload comes from the verdict, which took
    it from the budget object that produced the decision.
    """
    if not verdict.wants_compaction:
        raise ValueError(f"compaction pressure is only defined for stage2/stage3, got {verdict.action!r}")

    warning_data = {
        "action": verdict.action,
        "compaction_enabled": compaction_enabled,
        "ratio": verdict.ratio,
        "threshold": verdict.threshold,
    }
    log.append(actor="runtime", kind="compaction_warning", content=warning_data)
    if output is not None:
        output.emit(
            OutputEvent(
                type="compaction_warning",
                turn=turn,
                max_turns=max_turns,
                data=warning_data,
            )
        )


def emit_context_warn(
    verdict: BudgetVerdict,
    *,
    turn: int,
    max_turns: int,
    output: EventBus | None,
    action: str,
    message: str | None = None,
) -> None:
    """Console mirror for a context-budget row (FIX-1).

    Moved here from the driver so there is exactly one implementation shared by
    the branches that stay in the driver and the branches that moved out. ``pct``
    is derived from the verdict, never from a caller-local variable — Q#4 was
    precisely that drift, one level up.

    ``action`` stays a parameter rather than ``verdict.action``: the
    stage-2-without-compaction path reports the literal ``"stage2"`` while the
    other sites report the verdict's own action. Keeping it explicit means a
    future caller cannot silently change the console's ``action`` field by
    passing a different verdict.

    ``message`` overrides the verdict's text only where the driver already had a
    different one to show — the compaction circuit breaker replaces the budget
    message with its own explanation. Defaulting to the verdict keeps the
    ordinary sites honest.
    """
    if output is None:
        return
    output.emit(
        OutputEvent(
            type="context_warn",
            turn=turn,
            max_turns=max_turns,
            data={
                "pct": round(verdict.ratio * 100),
                "action": action,
                "message": verdict.message if message is None else message,
            },
        )
    )


__all__ = ["emit_context_warn", "record_budget_pressure", "record_compaction_pressure"]
