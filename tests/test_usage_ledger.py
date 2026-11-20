"""C1 — the usage ledger that replaced two `nonlocal` writes.

Why this module exists: the numbers it holds are durable (the ``session_summary``
row and the ``session_end`` event carry them, and ``fa stats`` reads them back),
and until now they were three locals mutated from two closures. A local cannot
be tested; a field can. These tests pin the three behaviours the closures had —
fold a row, count a turn, write the summary once — plus the one the closures did
*not* have: an unknown counter is now an error instead of silently dropped.

The one-shot guard is the interesting one. ``finish`` is reachable from both a
normal exit and an exception path; before, a second call re-entered the block
and checked a bool. Now ``claim_summary()`` both decides and records, so callers
cannot forget to set the flag.
"""

from __future__ import annotations

import pytest

from fa.inner_loop.usage_ledger import USAGE_KEYS, UsageLedger


def test_starts_at_zero_for_every_declared_key() -> None:
    """The summary row's shape is fixed, so the initial totals must be too."""
    ledger = UsageLedger()

    assert set(ledger.totals) == set(USAGE_KEYS)
    assert all(value == 0 for value in ledger.totals.values())
    assert ledger.turns == 0
    assert ledger.summary_written is False


def test_record_folds_a_row_and_counts_a_turn() -> None:
    """C1: the accumulation the old `record_usage` closure performed inline."""
    ledger = UsageLedger()

    ledger.record(
        {"input_tokens": 10, "output_tokens": 3, "cache_read_input_tokens": 1, "cache_creation_input_tokens": 0}
    )
    ledger.record(
        {"input_tokens": 5, "output_tokens": 7, "cache_read_input_tokens": 2, "cache_creation_input_tokens": 0}
    )

    assert ledger.totals == {
        "input_tokens": 15,
        "cache_read_input_tokens": 3,
        "cache_creation_input_tokens": 0,
        "output_tokens": 10,
    }
    assert ledger.turns == 2


def test_partial_row_is_rejected_rather_than_zero_filled() -> None:
    """A provider that omits a counter must not silently report zero for it.

    The old code iterated ``row.items()`` and added only what was present, so a
    missing key left its total untouched — indistinguishable, in the summary,
    from "this provider reported 0". Failing here makes the difference visible
    at the only place that can fix it.
    """
    ledger = UsageLedger()

    with pytest.raises(KeyError, match="missing"):
        ledger.record({"input_tokens": 1})


def test_unknown_counter_is_an_error_not_a_silent_drop() -> None:
    """Adding a counter is a schema decision, so it cannot happen by accident."""
    ledger = UsageLedger()
    row = dict.fromkeys(USAGE_KEYS, 0) | {"reasoning_tokens": 42}

    with pytest.raises(KeyError, match="reasoning_tokens"):
        ledger.record(row)

    assert ledger.turns == 0, "a rejected row must not count as a turn"


def test_claim_summary_is_true_exactly_once() -> None:
    """C1: the guard that replaced `nonlocal summary_written`.

    Both the normal exit and the exception path can reach ``finish``; the row
    and the ``session_end`` event may be emitted once. This is that contract.
    """
    ledger = UsageLedger()

    assert ledger.claim_summary() is True
    assert ledger.claim_summary() is False
    assert ledger.claim_summary() is False
    assert ledger.summary_written is True


def test_claim_summary_does_not_touch_usage() -> None:
    """Writing the summary must not perturb the numbers it is about to report."""
    ledger = UsageLedger()
    ledger.record(dict.fromkeys(USAGE_KEYS, 4))

    before = dict(ledger.totals), ledger.turns
    ledger.claim_summary()

    assert (ledger.totals, ledger.turns) == before
