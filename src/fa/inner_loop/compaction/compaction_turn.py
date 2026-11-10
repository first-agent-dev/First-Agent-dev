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
