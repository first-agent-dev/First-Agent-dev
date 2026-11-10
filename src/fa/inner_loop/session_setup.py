"""What a session needs before its first turn: assembled once, named.

Why this module exists
----------------------
The driver opened with ~30 lines that had nothing to do with driving: read two
config fields, clamp a floor, build the budget, pick a pinned buffer, allocate
the ledger and the artifact store, take a monotonic timestamp, and derive the
tool-definition payload. Every one of those is a *precondition* of the loop, not
a step of it, yet they sat in the same body as the loop — which is why the
driver kept looking like a grab-bag to whoever read it next.

The behavioural risk in this block is ordering, not logic. `ContextBudget` must
be built from the *clamped* limit, and the clamp must be visible in the trace
(``context_limit=... below floor ..., clamped``). An assembler that returns the
budget without recording the clamp would keep every test green and silently drop
an operator-visible row.

What is deliberately **not** here: `tool_payload`. It is the rendered spec list
the turn loop and the prompt both read, and it belongs to the loop's own
wiring; only the prompt-facing copy is derived. Moving it would drag the
`registry` seam in behind it for no gain.

Also not here: the `user_msg` / `run_started` rows. They are trace ordering, not
setup — the golden trace oracle pins them, and their position relative to
`session_start` is a fact about the session's beginning that reads better where
the session is started.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from fa.inner_loop.state import EventLog
from fa.inner_loop.usage_ledger import UsageLedger
from fa.memory.context_budget import ContextBudget


class PinnedContentSource(Protocol):
    """What the loop asks of a pinned buffer: one extraction, no state of ours.

    A Protocol rather than the concrete `PinnedBuffer` so a test can hand over a
    stand-in — and so this module does not import the memory package just to name
    a type it never calls.
    """

    def extract_pinned_content(self, extra_instructions: str | None = None) -> str: ...


#: Below this, a context budget is meaningless. Catches typos like
#: `context_limit=100` (meant 100000) before they turn every turn into a
#: stage-3 stop.
MIN_CONTEXT_LIMIT = 32_000


@dataclass(frozen=True)
class SessionSetup:
    """The session's fixed preconditions — built once, never reassigned.

    Frozen on purpose: if a later turn wants a different budget or a different
    buffer, that is a different session, and the attempt should fail here rather
    than half-rebind a value the exit reads.
    """

    budget: ContextBudget
    context_limit: int
    compaction_threshold: int | None
    pinned_buffer: object | None
    ledger: UsageLedger
    started_at: float
    tool_defs_for_prompt: list[dict[str, Any]]


def prepare_session(
    *,
    log: EventLog,
    context_limit: int,
    compaction_threshold: int | None,
    pinned_buffer: PinnedContentSource | None,
    tool_payload: Sequence[Mapping[str, Any]],
) -> SessionSetup:
    """Assemble the preconditions, recording the clamp if it fires.

    The clamp is applied *before* the budget is constructed — the budget's
    stage thresholds are percentages of the limit it is handed, so building it
    from an unclamped value would put every threshold below the floor.
    """
    clamped = max(context_limit, MIN_CONTEXT_LIMIT)
    if clamped != context_limit:
        log.append(
            actor="runtime",
            kind="telemetry",
            content={"message": f"context_limit={context_limit} below floor {MIN_CONTEXT_LIMIT}, clamped"},
        )

    # TODO: Adaptive context sizing — eventually derive the limit from API
    # response metadata (the model's actual context_window). ADR-17 §Option B
    # point 5 describes the target architecture; today it is static config from
    # models.yaml. See knowledge/adr/ADR-17-context-management-and-compaction.md
    return SessionSetup(
        budget=ContextBudget(limit_tokens=clamped, configured_threshold=compaction_threshold),
        context_limit=clamped,
        compaction_threshold=compaction_threshold,
        pinned_buffer=pinned_buffer,
        ledger=UsageLedger(),
        started_at=time.monotonic(),
        # `dict()` because the composer's contract is plain dicts, and the
        # rendered specs are Mappings — this list is the one place that boundary is crossed.
        tool_defs_for_prompt=[dict(tool) for tool in tool_payload],
    )


__all__ = ["MIN_CONTEXT_LIMIT", "SessionSetup", "prepare_session"]
