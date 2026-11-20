"""The context-budget *decision*, separated from what the driver does about it.

Why this module exists
----------------------
The session driver used to answer three questions in one 380-line block:

1. **what did the budget decide?** — ``action``, ``ratio``, ``message``;
2. **what does the operator need to see?** — ``log.append`` + ``output.emit``;
3. **may the session continue?** — the five session exits inside that block.

The middle question is where the S6-F5 and Q#4 defects lived: both were
"the displayed number/state disagrees with the one the decision used", and both
survived review because the answer was buried between effects. Splitting (1)
into a typed value does not move a single effect and does not change any
behaviour — it makes (1) testable as a table, so (2) and (3) can be checked
against something explicit.

Relationship to ``fa.memory.context_budget.ContextBudget``
----------------------------------------------------------
``ContextBudget.check()`` remains the single authority for the thresholds and
for the durable row's shape: this module calls it and never recomputes a
threshold or a ratio of its own. ``raw`` keeps the exact mapping that reaches
``log.append`` today, because ``fa stats`` reads ``action``, ``ratio`` and
``message`` from it (``stats._parse_events``) and nine keys of it are stored
verbatim in the trace. Re-deriving the payload from the fields below would be a
second source of truth for the same event.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

#: Actions ``ContextBudget.check`` can return. A closed set on purpose: an
#: unrecognised action means the budget module grew a state the driver does not
#: handle, and continuing as if nothing happened would hide exactly the kind of
#: pressure signal this gate exists to surface.
BUDGET_ACTIONS: frozenset[str] = frozenset({"allow", "warn", "stage2", "stage3"})


@dataclass(frozen=True)
class BudgetVerdict:
    """What the context budget decided for one turn, as a value.

    ``raw`` is the mapping ``ContextBudget.check`` produced — the same object
    that is appended to the durable log. It is carried, not reconstructed: see
    the module docstring.
    """

    action: str
    ratio: float
    threshold: int
    message: str
    raw: Mapping[str, Any]

    @property
    def wants_compaction(self) -> bool:
        """True when the budget asked for a compaction stage."""
        return self.action in {"stage2", "stage3"}

    @property
    def may_stop(self) -> bool:
        """True when this verdict can end the session (stage-3 pressure)."""
        return self.action == "stage3"

    def hard_stop_row(self, *, message: str) -> dict[str, Any]:
        """The ``context_budget_hard_stop`` payload for this verdict.

        Derived from ``raw``, not from a second ``budget.check()``: the row and
        the console mirror then describe the *same* measurement by
        construction, so they cannot drift (Q#4 was a stale percent reaching the
        console while the row carried the fresh one). ``raw`` is exactly what
        ``ContextBudget.check()`` returned for this usage, so this is byte-equal
        to ``ContextBudget.hard_stop_row(usage, message=...)`` — asserted by a
        test, because "byte-equal" is a claim that will rot.

        ``message`` is replaced: the breaker explains itself, while ``action``,
        ``ratio`` and the thresholds stay the budget's own words.
        """
        return {**dict(self.raw), "message": message}


def classify_budget(
    decision: Mapping[str, Any],
    *,
    stage2_threshold: int,
    stage3_threshold: int,
) -> BudgetVerdict:
    """Turn ``ContextBudget.check()``'s mapping into a ``BudgetVerdict``.

    The two threshold arguments come from the same ``ContextBudget`` instance
    that produced ``decision``; they are passed rather than fetched so the call
    site stays explicit about which budget object is authoritative when more
    than one exists (the compactor chain has its own).

    Raises:
        ValueError: ``action`` is outside :data:`BUDGET_ACTIONS`. Fail-closed:
            a budget state the driver does not understand must not be treated
            as "allow".
    """
    action = str(decision.get("action", ""))
    if action not in BUDGET_ACTIONS:
        raise ValueError(f"unknown context-budget action {action!r}; expected one of {sorted(BUDGET_ACTIONS)}")

    # Exactly the rule the ``compaction_warning`` row has always used: stage-2
    # pressure names the stage-2 threshold, everything else names stage 3. Kept
    # verbatim because that value is durable (``stats`` reads ``threshold`` from
    # the row), so "cleaning it up" here would silently change trace content.
    threshold = stage2_threshold if action == "stage2" else stage3_threshold

    return BudgetVerdict(
        action=action,
        ratio=float(decision.get("ratio", 0.0)),
        threshold=threshold,
        message=str(decision.get("message", "")),
        raw=dict(decision),
    )


__all__ = ["BUDGET_ACTIONS", "BudgetVerdict", "classify_budget"]
