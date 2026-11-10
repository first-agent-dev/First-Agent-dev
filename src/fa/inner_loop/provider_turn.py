"""The durable and console record of one provider call.

Split out of ``_drive_session_inner`` because it decides nothing: given a
response and the attempt records that produced it, it writes the same rows and
emits the same event as before. Every value it needs comes through arguments, so
there is no driver state to capture and no hidden channel back into the loop.

Two rows, one event, in this order (order is the contract — ``fa stats`` and the
console both read the sequence):

1. one ``provider_attempt`` row per attempt, each carrying the logical call id;
2. one ``llm_call`` rollup row embedding the same attempts;
3. one ``llm_response`` console event.

``cost_usd`` is intentionally absent from the rollup (BACKLOG I-33): no wired
cost source exists, and a ``None``/``0.0`` placeholder is worse than absence
because a consumer can mistake it for "free".
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from fa.inner_loop.state import EventLog
from fa.output import EventBus, OutputEvent
from fa.providers.base import ResponseInfo
from fa.providers.errors import ProviderChainExhaustedError, ProviderRequestShapeError
from fa.providers.types import ChainAttemptRecord

logger = logging.getLogger(__name__)

#: Attempt fields that appear on both the per-attempt row and the rollup entry.
#: Kept together so the two shapes cannot drift: a field added to one and not the
#: other is a silent hole in the rollup.
_ATTEMPT_FIELDS: tuple[str, ...] = ("provider", "slug", "status", "ms", "error")


def _attempt_entry(attempt: ChainAttemptRecord) -> dict[str, Any]:
    """The rollup's compact view of one attempt (no logical id — the row has it)."""
    return {name: getattr(attempt, name) for name in _ATTEMPT_FIELDS}


def record_provider_call(
    *,
    log: EventLog,
    output: EventBus | None,
    response: ResponseInfo,
    attempts: Sequence[ChainAttemptRecord],
    logical_call_id: str,
    role: str,
    model: str,
    family: str,
    turn: int,
    max_turns: int,
) -> None:
    """Write the attempts, the rollup, and the console line for one call.

    ``log`` is not optional: a session without a durable log cannot produce a
    trace at all, and the driver asserts that invariant before the loop starts.
    ``output`` is optional — a headless run still writes rows.
    """
    for attempt in attempts:
        log.append(
            actor="provider",
            kind="provider_attempt",
            content={**_attempt_entry(attempt), "logical_call_id": logical_call_id},
        )

    log.append(
        actor="provider",
        kind="llm_call",
        content={
            "logical_call_id": logical_call_id,
            "role": role,
            "model": model,
            "family": family,
            "chain": [_attempt_entry(attempt) for attempt in attempts],
            "in_tokens": response.in_tokens,
            "out_tokens": response.out_tokens,
            "wallclock_ms": sum(attempt.ms for attempt in attempts),
        },
    )

    if output is None:
        return
    elapsed = int(attempts[-1].ms if attempts else 0)
    output.emit(
        OutputEvent(
            type="llm_response",
            turn=turn,
            max_turns=max_turns,
            data={
                "ms": elapsed,
                "in_tokens": response.in_tokens,
                "out_tokens": response.out_tokens,
                "cache_read": response.cache_read_input_tokens,
                "cache_creation": response.cache_creation_input_tokens,
                "tool_call_count": len(response.tool_calls),
                "text": response.text if response.text else None,
            },
        )
    )


# ── Failures: what the turn should do, expressed as a value ──────────────
#
# The three handlers around the provider call were the last 64-line block in the
# driver, and they were unreadable for one reason: each one *decided* something
# (retry the turn, stop with this code) and then *performed* it with a `return`
# or a `continue`. The decision could not be tested without driving a session,
# and the `continue` could not be reviewed next to the two `return`s it mirrors.
#
# Same rule as the budget ladder: values out, exits stay with the driver.


@dataclass(frozen=True)
class ProviderTurnStop:
    """A stop the driver performs with `finish_at`."""

    exit_code: int
    reason: str
    final_text: str = ""


@dataclass(frozen=True)
class ProviderRetry:
    """Retry the whole turn: re-enter the loop with this exhaustion counter."""

    exhaustion_count: int
    max_retries: int


@dataclass(frozen=True)
class ProviderFailure:
    """Exactly one of ``stop`` / ``retry``; ``exhaustion_count`` is post-update.

    ``exhaustion_count`` travels even on the stop path because the counter is
    session state that advanced here: returning only the decision would leave
    the driver guessing whether to increment.
    """

    stop: ProviderTurnStop | None
    retry: ProviderRetry | None
    exhaustion_count: int


def _retry_event(attempt: ChainAttemptRecord, *, turn: int, max_turns: int) -> OutputEvent:
    """One ``api_retry`` line for one failed attempt.

    Built in one place because the retry path and both stop paths emit it, and a
    field added to two of the three would be a silent hole in the console.
    """
    return OutputEvent(
        type="api_retry",
        turn=turn,
        max_turns=max_turns,
        data={
            "provider": attempt.provider,
            "status": attempt.status,
            "retry_after_s": 0,
            "reason": attempt.error or "unknown",
        },
    )


def _emit_attempts_failed(
    attempts: Sequence[ChainAttemptRecord], *, output: EventBus | None, turn: int, max_turns: int
) -> None:
    if output is None:
        return
    for attempt in attempts:
        output.emit(_retry_event(attempt, turn=turn, max_turns=max_turns))


def handle_provider_failure(
    exc: BaseException,
    *,
    exhaustion_count: int,
    max_retries: int,
    log: EventLog,
    output: EventBus | None,
    turn: int,
    max_turns: int,
) -> ProviderFailure:
    """Turn a provider exception into the driver's next move, writing what it decides.

    ``exhaustion_count`` is the count *before* this failure; the value returned is
    the count after it. The increment happens for every exhaustion, retried or
    not — it is a count of events, not of retries, and `fa stats` reports it as
    ``chain_exhaustion_events`` at session end.

    Order of effects is part of the contract and differs by path:
    ``run_stopped`` precedes ``api_retry`` on both stop paths, and on the retry
    path the log line precedes the console lines. Callers reused the previous
    inline order; the tests pin it.
    """
    if isinstance(exc, KeyboardInterrupt):
        log.append(actor="runtime", kind="run_stopped", content={"reason": "abnormal_stop:interrupt"})
        return ProviderFailure(
            stop=ProviderTurnStop(exit_code=130, reason="abnormal_stop:interrupt"),
            retry=None,
            exhaustion_count=exhaustion_count,
        )

    if isinstance(exc, ProviderRequestShapeError):
        # CT5 / I-50 / I-51: a shape failure is FA's own construction bug, reported
        # the same way whether it was raised locally before HTTP or returned as
        # 400/422 by the provider.
        log.append(actor="runtime", kind="run_stopped", content={"reason": "request_shape", "detail": str(exc)})
        if output is not None:
            output.emit(
                OutputEvent(
                    type="api_retry",
                    turn=turn,
                    max_turns=max_turns,
                    data={
                        "provider": getattr(exc, "provider", None) or "unknown",
                        "status": exc.status,
                        "retry_after_s": 0,
                        "reason": f"request_shape_error: {exc}",
                    },
                )
            )
        return ProviderFailure(
            stop=ProviderTurnStop(exit_code=2, reason="request_shape"),
            retry=None,
            exhaustion_count=exhaustion_count,
        )

    if not isinstance(exc, ProviderChainExhaustedError):
        # Loud rather than silent: an unhandled exception type here would mean the
        # driver's `except` list and this table disagree, which is a wiring bug.
        raise TypeError(f"handle_provider_failure does not handle {type(exc).__name__}")

    # The per-turn retry seam already persisted this exception's attempts;
    # re-emitting them here would count the final attempt twice in stats.
    updated = exhaustion_count + 1
    log.chain_exhaustion_count += 1

    if updated <= max_retries:
        # Session-level retry (CT13): run the WHOLE turn again. Distinct from the
        # per-turn cooldown retries inside `_request_with_cooldown_retries`.
        logger.info("Provider chain exhausted, session-level retry (%d/%d)", updated, max_retries)
        _emit_attempts_failed(exc.attempts, output=output, turn=turn, max_turns=max_turns)
        return ProviderFailure(
            stop=None,
            retry=ProviderRetry(exhaustion_count=updated, max_retries=max_retries),
            exhaustion_count=updated,
        )

    log.append(actor="runtime", kind="run_stopped", content={"reason": "chain_exhausted", "detail": str(exc)})
    _emit_attempts_failed(exc.attempts, output=output, turn=turn, max_turns=max_turns)
    return ProviderFailure(
        stop=ProviderTurnStop(exit_code=2, reason="chain_exhausted"),
        retry=None,
        exhaustion_count=updated,
    )


__all__ = [
    "ProviderFailure",
    "ProviderRetry",
    "ProviderTurnStop",
    "handle_provider_failure",
    "record_provider_call",
]
