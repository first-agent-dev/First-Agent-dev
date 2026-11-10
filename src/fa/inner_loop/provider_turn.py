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

from collections.abc import Sequence
from typing import Any

from fa.inner_loop.state import EventLog
from fa.output import EventBus, OutputEvent
from fa.providers.base import ResponseInfo
from fa.providers.types import ChainAttemptRecord

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


__all__ = ["record_provider_call"]
