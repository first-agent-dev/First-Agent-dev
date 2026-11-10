"""Stage-2 compaction: deterministic observation masking, extracted from the driver.

Why this exists
---------------
The budget block in ``coder_loop._drive_session_inner`` was 405 lines and 29 of
the function's 68 branches. Stage-2 alone owned 3 durable rows, 3 console events
and a broad ``try`` whose ``except`` is the only place in the loop where an
exception is swallowed on purpose. Sitting in the middle of a block that can
also end the session, that ``except`` was one edit away from losing the
"continue with the verbatim prompt" promise it exists to keep.

Deliberately narrow: this returns a result, it does not end the session. The
stage-3 hard stops and the circuit breaker stay in the driver for now, because
they call ``finish_at`` and moving them means deciding where that lives.
Stage-2 runs before them and never terminates, so it can move first — the seam
gets proven before anything is allowed to return an outcome.

Ordering is the contract, and it is asserted by tests: ``compaction_stage2_start``
row, ``compaction_start`` event, the work, ``compaction_stage2_done`` row, the
``compaction_end`` event. On failure the error row and the ``ok=False`` event
replace the done pair, and the caller keeps the prompt it already had.

The non-obvious part kept from the driver is the re-check after masking:
``usage``, ``decision`` and ``verdict`` are re-derived from the masked prompt,
because the verdict is a snapshot of the *before* state while everything
downstream — the stage-3 trigger, Q#4's reported percentage — reads the *after*
state. Returning them together is what stops a caller from forgetting: that
forgetting is exactly Q#4.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fa.inner_loop.budget_effects import emit_context_warn as _emit_context_warn
from fa.inner_loop.budget_turn import BudgetVerdict, classify_budget
from fa.inner_loop.state import EventLog
from fa.output import EventBus, OutputEvent

if TYPE_CHECKING:
    from fa.memory.context_budget import ContextBudget

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Stage2Result:
    """What masking produced.

    On failure ``applied`` is False and the history/usage fields describe the
    unmasked state — but the caller must not adopt them: the inline version left
    its existing prompt variables untouched, and adopting a re-derived decision
    here would compute one from the pre-masking prompt for a second time. The
    only fields meaningful on failure are ``applied`` and the two rows already
    written to the log.
    """

    applied: bool
    history: list[dict[str, Any]]
    messages_payload: list[dict[str, Any]]
    request_extras: Mapping[str, Any]
    usage: int
    decision: dict[str, Any]
    verdict: BudgetVerdict


def _mask_observation_history(
    history: list[dict[str, Any]],
    *,
    artifact_store: Any | None,
    recent_turns_to_keep: int,
) -> list[dict[str, Any]]:
    """Indirection so a test can patch one name and get a real failure path."""
    from fa.inner_loop.compaction.compactor import project_messages_after_mask

    return project_messages_after_mask(
        messages=history,
        artifact_store=artifact_store,
        recent_turns_to_keep=recent_turns_to_keep,
    )


def run_stage2_masking(
    *,
    turn: int,
    max_turns: int,
    history: list[dict[str, Any]],
    memory_summary: str,
    usage: int,
    budget: ContextBudget,
    log: EventLog,
    output: EventBus | None,
    tool_payload: Sequence[Mapping[str, Any]],
    compose_request: Any,
    artifact_store: Any | None = None,
    recent_turns_to_keep: int = 4,
) -> Stage2Result:
    """Mask older observations, then re-derive the decision from the result.

    ``compose_request`` is the driver's per-turn ``_compose_request_payload``
    closure: it captures the session-constant prompt inputs, so passing it in
    keeps this function from needing the eleven arguments it would only forward.

    ``estimate_tokens`` is imported at call time, not bound at module import:
    callers inject it by patching ``fa.memory.context_budget.estimate_tokens``
    (eight test modules do), and a module-level binding would silently ignore
    those patches — measured: the probe's scenarios all collapsed to the real
    estimator and every session settled at ~2% instead of stopping.
    """
    from fa.memory.context_budget import estimate_tokens

    logger.info("ContextBudget Stage 2 reached. Triggering deterministic observation masking first...")
    log.append(
        actor="runtime",
        kind="compaction_stage2_start",
        content={"tokens_before": usage, "threshold": budget.stage2_threshold},
    )
    if output is not None:
        output.emit(
            OutputEvent(
                type="compaction_start",
                turn=turn,
                max_turns=max_turns,
                data={"stage": 2, "tokens_before": usage},
            )
        )

    try:
        masked_history = _mask_observation_history(
            history,
            artifact_store=artifact_store,
            recent_turns_to_keep=recent_turns_to_keep,
        )
        _request_body, messages_payload, request_extras = compose_request(
            active_summary=memory_summary,
            observations=masked_history,
        )
        post_mask_usage = estimate_tokens(messages_payload, tool_payload)
        log.append(
            actor="runtime",
            kind="compaction_stage2_done",
            content={"tokens_before": usage, "tokens_after": post_mask_usage},
        )
        if output is not None:
            output.emit(
                OutputEvent(
                    type="compaction_end",
                    turn=turn,
                    max_turns=max_turns,
                    data={
                        "stage": 2,
                        "tokens_before": usage,
                        "tokens_after": post_mask_usage,
                        "ok": True,
                    },
                )
            )
        logger.info(
            "Stage 2 Compaction successful. Reclaimed tokens: %d -> %d",
            usage,
            post_mask_usage,
        )
    except Exception as exc:  # noqa: BLE001 # graceful degradation, keep the verbatim prompt
        logger.warning("Stage 2 Compaction failed: %s, continuing with verbatim prompt", exc)
        log.append(
            actor="runtime",
            kind="compaction_stage2_error",
            content={"error": str(exc)},
        )
        if output is not None:
            output.emit(
                OutputEvent(
                    type="compaction_end",
                    turn=turn,
                    max_turns=max_turns,
                    data={"stage": 2, "ok": False, "error": str(exc)},
                )
            )
        return Stage2Result(
            applied=False,
            history=history,
            messages_payload=[],
            request_extras={},
            usage=usage,
            decision={},
            verdict=classify_budget(
                budget.check(usage),
                stage2_threshold=budget.stage2_threshold,
                stage3_threshold=budget.stage3_threshold,
            ),
        )

    decision = budget.check(post_mask_usage)
    verdict = classify_budget(
        decision,
        stage2_threshold=budget.stage2_threshold,
        stage3_threshold=budget.stage3_threshold,
    )
    return Stage2Result(
        applied=True,
        history=masked_history,
        messages_payload=list(messages_payload),
        request_extras=request_extras,
        usage=post_mask_usage,
        decision=decision,
        verdict=verdict,
    )


# ---------------------------------------------------------------------------
# Stage 3 — LLM compaction, the circuit breaker, and the "stop" decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage3Result:
    """The outcome of stage-3, including whether the session has to end.

    ``stopped`` is a *report*, not an action: this module writes the rows and
    the console events that describe the stop, but the driver performs it. That
    split is the point of the move — ``finish_at`` closes over eight driver
    locals (turn, results, summary, usage totals), so calling it from here would
    mean handing those over as parameters, which is a bigger seam than the one
    being removed. The driver keeps "how a session ends"; this module owns
    "why it ended".

    On failure (``applied=False``) ``stopped`` still reflects the post-failure
    re-check: a failed compaction can leave the prompt over the stage-3
    threshold, and the driver must still stop in that case.
    """

    applied: bool
    stopped: bool
    stop_message: str
    history: list[dict[str, Any]]
    memory_summary: str
    messages_payload: list[dict[str, Any]]
    request_extras: Mapping[str, Any]
    usage: int
    decision: dict[str, Any]
    verdict: BudgetVerdict


def _older_history_text(older_history: list[dict[str, Any]], memory_summary: str) -> str:
    """Flatten the pre-boundary turns into the compactor's input text."""
    text = ""
    if memory_summary:
        text += f"PREVIOUS COMPACTION SUMMARY:\n{memory_summary}\n\nNEW CONVERSATION TO ADD:\n"
    if not older_history:
        return text
    lines = []
    for msg in older_history:
        msg_role = msg.get("role", "unknown").upper()
        msg_content = msg.get("content") or msg.get("text") or ""
        lines.append(f"{msg_role}: {msg_content}")
        if "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                lines.append(f"CALL TOOL: {fn.get('name')} with arguments {fn.get('arguments')}")
    return text + "\n".join(lines)


def _record_stage3_stop(
    *,
    turn: int,
    max_turns: int,
    log: EventLog,
    output: EventBus | None,
    budget: ContextBudget,
    usage_for_row: int,
    message: str,
    verdict_for_console: BudgetVerdict,
    extra_event: str | None = None,
) -> None:
    """Write the two rows and the console mirrors that precede a hard stop.

    Shared by both stage-3 exits so the pair cannot drift: the durable row is
    ``hard_stop_row`` (Q#5 — one schema for every exit), and the console gets
    the same verdict the row was built from, with the exit's own wording.
    """
    log.append(
        actor="runtime",
        kind="context_budget_hard_stop",
        content=budget.hard_stop_row(usage_for_row, message=message),
    )
    _emit_context_warn(
        verdict_for_console,
        output=output,
        turn=turn,
        max_turns=max_turns,
        action="stage3",
        message=message,
    )
    if output is not None and extra_event == "loop_warn":
        output.emit(
            OutputEvent(
                type="loop_warn",
                turn=turn,
                max_turns=max_turns,
                data={
                    "detector": "compaction_circuit_breaker",
                    "message": (
                        "Compaction circuit breaker triggered — context budget exceeded after compaction attempts"
                    ),
                },
            )
        )
    log.append(
        actor="runtime",
        kind="run_stopped",
        content={"reason": "context_budget_hard_stop", "turns": turn},
    )


def run_stage3_compaction(
    *,
    turn: int,
    max_turns: int,
    history: list[dict[str, Any]],
    memory_summary: str,
    usage: int,
    budget: ContextBudget,
    log: EventLog,
    output: EventBus | None,
    tool_payload: Sequence[Mapping[str, Any]],
    compose_request: Any,
    compactor_chain: Any,
    verdict_for_console: BudgetVerdict,
    recent_turns_to_keep: int = 4,
) -> Stage3Result:
    """Compact via the LLM compactor, then decide whether the session can go on.

    ``verdict_for_console`` is passed in rather than re-derived at entry because
    the caller already holds the verdict the *entry* decision produced; this
    module only re-derives it when the prompt actually changes (after masking's
    result, or after compaction). Recomputing it here would spend a second
    ``estimate_tokens`` call on an unchanged prompt and, in the broken case,
    disagree with the caller.

    Returns:

    * ``stopped=True`` when the breaker fired or the prompt is still over the
      stage-3 threshold — the rows and events for that exit are already written,
      so the caller only has to end the session;
    * ``stopped=False`` with the post-compaction history, summary, payload and a
      freshly re-classified decision otherwise.
    """
    from fa.inner_loop.compaction.compactor import FullLLMCompactor, find_turn_boundary_backward
    from fa.memory.context_budget import estimate_tokens

    log.append(
        actor="runtime",
        kind="compaction_stage3_start",
        content={"tokens_before": usage, "threshold": budget.stage3_threshold},
    )
    if output is not None:
        output.emit(
            OutputEvent(
                type="compaction_start",
                turn=turn,
                max_turns=max_turns,
                data={"stage": 3, "tokens_before": usage},
            )
        )

    post_compaction_usage = usage
    updated_summary = memory_summary
    protected_window = history
    # Bound before the try: the failure path leaves them empty, and naming them
    # here is what the inline version got from its enclosing scope. Without it a
    # raising compactor surfaced as UnboundLocalError instead of degrading
    # (measured in two edge-case tests).
    messages_payload: list[dict[str, Any]] = []
    request_extras: Mapping[str, Any] = {}
    compacted = False
    try:
        cutoff_idx = find_turn_boundary_backward(history, recent_turns_to_keep=recent_turns_to_keep)
        older_history = history[:cutoff_idx]
        protected_window = history[cutoff_idx:]
        older_history_text = _older_history_text(older_history, memory_summary)

        if not older_history_text:
            # Nothing to compact — the prompt is unchanged, so the re-check below
            # runs on the same usage. It must still run: falling through to the
            # driver without it silently skipped the hard stop this branch used
            # to reach through the second `if decision == stage3` block
            # (measured: a stage-3 session continued to the provider instead of
            # exiting 1).
            logger.warning("No older history to compact for Stage 3")
            return _finish_stage3(
                applied=False,
                did_compact=False,
                history=history,
                memory_summary=memory_summary,
                messages_payload=[],
                request_extras={},
                post_compaction_usage=usage,
                turn=turn,
                max_turns=max_turns,
                log=log,
                output=output,
                budget=budget,
            )

        compactor = FullLLMCompactor(compactor_chain=compactor_chain)
        updated_summary = compactor.compact(older_history_text)
        _request_body, messages_payload, request_extras = compose_request(
            active_summary=updated_summary,
            observations=protected_window,
        )
        post_compaction_usage = estimate_tokens(messages_payload, tool_payload)
        log.append(
            actor="runtime",
            kind="compaction_stage3_done",
            content={
                "tokens_before": usage,
                "tokens_after": post_compaction_usage,
                "summary": updated_summary,
            },
        )
        if output is not None:
            output.emit(
                OutputEvent(
                    type="compaction_end",
                    turn=turn,
                    max_turns=max_turns,
                    data={
                        "stage": 3,
                        "tokens_before": usage,
                        "tokens_after": post_compaction_usage,
                        "ok": True,
                    },
                )
            )
        logger.info(
            "Stage 3 LLM Compaction done. Reclaimed tokens: %d -> %d",
            usage,
            post_compaction_usage,
        )
        compacted = True

        is_ok = budget.record_compaction_attempt(tokens_before=usage, tokens_after=post_compaction_usage)
        if not is_ok:
            return _circuit_breaker_exit(
                turn=turn,
                max_turns=max_turns,
                log=log,
                output=output,
                budget=budget,
                post_compaction_usage=post_compaction_usage,
            )
    except Exception as exc:  # noqa: BLE001 # graceful degradation, the re-check decides
        logger.warning("Stage 3 Compaction failed: %s", exc)
        log.append(actor="runtime", kind="compaction_stage3_error", content={"error": str(exc)})
        if output is not None:
            output.emit(
                OutputEvent(
                    type="compaction_end",
                    turn=turn,
                    max_turns=max_turns,
                    data={"stage": 3, "ok": False, "error": str(exc)},
                )
            )
        # The prompt did not change: keep the caller's history and summary, and
        # let the re-check below run on the pre-call usage. `compacted` stays
        # False so the caller does not adopt an empty payload as the new
        # request — "applied" means "there is a new prompt to send".
        post_compaction_usage = usage

    return _finish_stage3(
        applied=compacted,
        did_compact=compacted,
        history=protected_window,
        memory_summary=updated_summary,
        messages_payload=list(messages_payload),
        request_extras=request_extras,
        post_compaction_usage=post_compaction_usage,
        turn=turn,
        max_turns=max_turns,
        log=log,
        output=output,
        budget=budget,
    )


def _circuit_breaker_exit(
    *,
    turn: int,
    max_turns: int,
    log: EventLog,
    output: EventBus | None,
    budget: ContextBudget,
    post_compaction_usage: int,
) -> Stage3Result:
    """The anti-thrashing lock: three compaction attempts that reclaimed nothing.

    The console order here is not the same as the plain hard stop — the
    `compaction_end` with `ok=False` precedes the `context_warn`, and the
    operator gets one extra `loop_warn` naming the detector. Both are
    deliberate (NEW-2, FINDING-V2, S23) and are asserted as a sequence.
    """
    circuit_breaker_message = "Compaction circuit breaker triggered: anti-thrashing loop locked."
    logger.error(
        "Compaction circuit breaker triggered: less than 10%% space reclaimed 3 consecutive times. "
        "Anti-thrashing loop locked. Consider increasing context_limit or reducing conversation "
        "complexity in ~/.fa/models.yaml."
    )
    log.append(
        actor="runtime",
        kind="compaction_circuit_breaker",
        content={"message": circuit_breaker_message},
    )
    if output is not None:
        output.emit(
            OutputEvent(
                type="compaction_end",
                turn=turn,
                max_turns=max_turns,
                data={"stage": 3, "ok": False, "error": f"circuit_breaker: {circuit_breaker_message}"},
            )
        )
    verdict = classify_budget(
        budget.check(post_compaction_usage),
        stage2_threshold=budget.stage2_threshold,
        stage3_threshold=budget.stage3_threshold,
    )
    _record_stage3_stop(
        turn=turn,
        max_turns=max_turns,
        log=log,
        output=output,
        budget=budget,
        usage_for_row=post_compaction_usage,
        message=circuit_breaker_message,
        verdict_for_console=verdict,
        extra_event="loop_warn",
    )
    return Stage3Result(
        applied=True,
        stopped=True,
        stop_message=circuit_breaker_message,
        history=[],
        memory_summary="",
        messages_payload=[],
        request_extras={},
        usage=post_compaction_usage,
        decision={},
        verdict=verdict,
    )


def _finish_stage3(
    *,
    applied: bool,
    did_compact: bool,
    history: list[dict[str, Any]],
    memory_summary: str,
    messages_payload: list[dict[str, Any]],
    request_extras: Mapping[str, Any],
    post_compaction_usage: int,
    turn: int,
    max_turns: int,
    log: EventLog,
    output: EventBus | None,
    budget: ContextBudget,
) -> Stage3Result:
    """Re-check after stage-3 and report whether the session has to end.

    Single exit point for all three ways stage-3 can end its work — compacted,
    nothing to compact, or the compaction raised. Keeping them on one path is
    what preserves the original structure: the driver used to run this check
    unconditionally after the `try`, which is why a *failed* compaction still
    produced a hard stop when the prompt stayed over the threshold.
    """
    decision = budget.check(post_compaction_usage)
    verdict = classify_budget(
        decision,
        stage2_threshold=budget.stage2_threshold,
        stage3_threshold=budget.stage3_threshold,
    )
    if verdict.action == "stage3":
        logger.warning(
            "ContextBudget Gate Breach: Stage 3 still exceeds budget! %s",
            decision["message"],
        )
        _record_stage3_stop(
            turn=turn,
            max_turns=max_turns,
            log=log,
            output=output,
            budget=budget,
            usage_for_row=post_compaction_usage,
            message=decision["message"],
            verdict_for_console=verdict,
        )
        return Stage3Result(
            applied=applied,
            stopped=True,
            stop_message=decision["message"],
            history=history,
            memory_summary=memory_summary,
            messages_payload=[],
            request_extras={},
            usage=post_compaction_usage,
            decision=decision,
            verdict=verdict,
        )

    return Stage3Result(
        applied=applied and did_compact,
        stopped=False,
        stop_message="",
        history=history,
        memory_summary=memory_summary,
        messages_payload=messages_payload,
        request_extras=request_extras,
        usage=post_compaction_usage,
        decision=decision,
        verdict=verdict,
    )
