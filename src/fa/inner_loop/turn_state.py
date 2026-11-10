"""The conversation state a session carries from one turn to the next.

Companion to :class:`fa.inner_loop.usage_ledger.UsageLedger`. That one holds
what *was spent*; this one holds *what is being said*: the running history, the
summary the compactor produced, the last budget ratio the exit will report, and
the session-level chain-exhaustion counter.

Why these four and not the loop's other locals: each is written by a phase and
read by a *later* one, so they cannot be produced and consumed inside a single
turn.

=========================================  ==============  ===============
field                                      written by      read by
=========================================  ==============  ===============
``conversation_history`` / ``summary``     compaction      next request
``last_budget_ratio``                      budget          ``finish``
``chain_exhaustion_count``                 provider fail   retry guard
=========================================  ==============  ===============

``last_budget_ratio`` is the one that looks removable and is not: ``finish``
reads it to report ``context_used_pct``, and Q#4 was exactly the bug of
reporting a stale one (a stop at 92% printed as 99%). Keeping it as a field of
this object rather than a bare local gives it one writer per exit and a name
that says "this is the number the summary will show".

Deliberately not here: ``collected_results`` and ``failed_tools``. They are the
outcome accumulator that ``finish_at`` closes over, and moving them would move
the exit — which the plan explicitly does not do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnState:
    """Running conversation and the counters the exit reports."""

    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    memory_summary: str = ""
    #: Q#4: the ratio the *summary* will report. Written by the budget phase
    #: after any re-classification, never read before it.
    last_budget_ratio: float = 0.0
    #: S22: session-level chain exhaustion count, distinct from the per-turn
    #: retry counter inside the request seam. ``max_chain_retries`` compares
    #: against this one.
    chain_exhaustion_count: int = 0

    @classmethod
    def from_restored(cls, restored: tuple[str, list[dict[str, Any]]]) -> TurnState:
        """Build from ``restore_conversation_history``'s ``(summary, history)``.

        Worth a method because the tuple is in the opposite order to the fields:
        unpacking it inline is one silent swap away from a session that starts
        with its history in the summary slot. Here the swap happens once, in a
        named place, and is covered by a test.
        """
        summary, history = restored
        return cls(conversation_history=history, memory_summary=summary)

    def adopt_compaction(
        self,
        *,
        history: list[dict[str, Any]],
        ratio: float,
        summary: str | None = None,
    ) -> None:
        """Take a compaction stage's result in one step.

        Stage 2 and stage 3 both produce (history, ratio); only stage 3 produces
        a new summary, which is why ``summary`` is optional — masking does not
        summarize, and passing the current value back would be a no-op that
        reads like a decision.

        Assigning the fields one by one is three chances to update two of three,
        the failure mode ``ScopeState.adopt`` exists to prevent, repeated here.
        """
        self.conversation_history = history
        if summary is not None:
            self.memory_summary = summary
        self.last_budget_ratio = ratio

    def note_budget_ratio(self, ratio: float) -> None:
        """Record the ratio without adopting new history (warn and stage-3-stop paths)."""
        self.last_budget_ratio = ratio


__all__ = ["TurnState"]
