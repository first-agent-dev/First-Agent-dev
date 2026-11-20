"""The per-session usage ledger: the object the driver's closures were faking.

Before this module, three pieces of state lived as plain locals in
``_drive_session_inner`` and two closures mutated them through ``nonlocal``:
``usage_totals``, ``usage_turns`` and ``summary_written``. That made an object
without a name, and it is why the driver's exits could not be moved: ``finish``
wrote ``summary_written`` into the loop's scope, so the summary could only be
emitted from inside the loop body.

Naming it changes no behaviour — the same numbers, in the same order, appended
by the same caller — but it removes the hidden channel. A closure may now take
the ledger as an argument instead of capturing it.

Deliberately small and dumb:

* it does **not** write to the event log. The caller owns the log, and a ledger
  that logged would be a second place that decides what a usage row looks like;
* it does **not** know about ``SessionOutcome``. ``summary_written`` is a
  one-shot guard, and the caller asks about it.

``summary_written`` is a field rather than a bool returned by
``mark_summary_written()`` because the guard must survive several exit paths
reaching ``finish`` — an exception path and a normal path can both call it, and
only the first may write the row.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

#: The counters every session reports. Fixed set, in a fixed order: the summary
#: row's shape is durable (``fa stats`` reads it), so a ledger that accepted
#: arbitrary keys could widen the schema by accident.
USAGE_KEYS: tuple[str, ...] = (
    "input_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "output_tokens",
)


@dataclass
class UsageLedger:
    """Running usage totals, the turn count, and the one-shot summary guard."""

    totals: dict[str, int] = field(default_factory=lambda: dict.fromkeys(USAGE_KEYS, 0))
    turns: int = 0
    summary_written: bool = False

    def record(self, row: Mapping[str, int]) -> None:
        """Fold one complete usage row into the totals.

        The row must name **every** declared counter. An unknown key is an error
        rather than silently ignored — a provider reporting a new counter should
        fail loudly here instead of having its tokens dropped from every summary
        from now on. A *missing* key is an error for the opposite reason: the old
        inline loop added only what it saw, so an omitted counter left its total
        untouched and the summary could not distinguish "reported 0" from "not
        reported". ``_usage_event_content`` always emits the full set, so a
        partial row means a producer changed, not a legitimate partial.
        """
        unknown = set(row) - set(self.totals)
        if unknown:
            raise KeyError(f"usage row has unknown keys {sorted(unknown)}; add them to USAGE_KEYS deliberately")
        missing = set(self.totals) - set(row)
        if missing:
            raise KeyError(f"usage row is missing {sorted(missing)}; a partial row would under-report the summary")
        for key, value in row.items():
            self.totals[key] += value
        self.turns += 1

    def claim_summary(self) -> bool:
        """True the first time, False afterwards — the caller writes the row once.

        This is the whole ``summary_written`` protocol, named: the first exit to
        reach ``finish`` writes ``session_summary`` and ``session_end``, and a
        later exit (an exception unwinding through the same handler) must not
        duplicate them.
        """
        if self.summary_written:
            return False
        self.summary_written = True
        return True


__all__ = ["USAGE_KEYS", "UsageLedger"]
