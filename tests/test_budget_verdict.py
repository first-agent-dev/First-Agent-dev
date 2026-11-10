"""C0 — the budget verdict, pinned as a transition table.

This slice has no behaviour of its own: it names the decision the driver already
takes. So the oracle is a table over the real ``ContextBudget`` ladder rather
than a mock of it — if the ladder moves, these tests move with it and the driver
call site is checked against a value instead of a dict lookup.

Why the table matters (measured, not stylistic): both budget-side defects in
this area were "the displayed state disagreed with the state the decision used"
— a guard stop reported as ``iteration_cap`` (S6-F5) and a hard-stop printing
the pre-compaction percentage after a successful compaction (Q#4). A typed
verdict with an exhaustive action table is what lets the follow-up slice check
"what was decided" separately from "what was emitted".
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.budget_turn import BUDGET_ACTIONS, BudgetVerdict, classify_budget
from fa.memory.context_budget import ContextBudget


def _verdict(budget: ContextBudget, tokens: int) -> BudgetVerdict:
    return classify_budget(
        budget.check(tokens),
        stage2_threshold=budget.stage2_threshold,
        stage3_threshold=budget.stage3_threshold,
    )


# ---------------------------------------------------------------------------
# The ladder, end to end: 100k limit, explicit 80k stage-2 threshold
# ---------------------------------------------------------------------------

#: (tokens, action, want_compaction, may_stop) — the whole ladder in one place.
#: 70k is the warn floor for this configuration, 80k stage 2, 90k stage 3.
_LADDER = [
    (10_000, "allow", False, False),
    (69_999, "allow", False, False),
    (70_000, "warn", False, False),
    (79_999, "warn", False, False),
    (80_000, "stage2", True, False),
    (89_999, "stage2", True, False),
    (90_000, "stage3", True, True),
    (100_001, "stage3", True, True),
]


@pytest.mark.parametrize(("tokens", "action", "wants_compaction", "may_stop"), _LADDER)
def test_ladder_transitions(tokens: int, action: str, wants_compaction: bool, may_stop: bool) -> None:
    """C0: each rung keeps its action, and the two derived predicates follow.

    The boundaries are the point: 69,999/70,000 and 79,999/80,000 are where a
    ``>=`` turned into a ``>`` would move the whole gate by one token without
    any other test noticing.
    """
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    verdict = _verdict(budget, tokens)

    assert verdict.action == action
    assert verdict.wants_compaction is wants_compaction
    assert verdict.may_stop is may_stop


def test_threshold_names_the_stage_the_verdict_is_about() -> None:
    """C0: ``threshold`` reproduces the ``compaction_warning`` rule exactly.

    The value is durable — ``stats`` reads it off the ``compaction_warning`` row
    — so stage-2 pressure must name the stage-2 threshold and stage-3 pressure
    the stage-3 one. A tidy-up that made this "the threshold we are over" would
    silently rewrite the trace.
    """
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)

    assert _verdict(budget, 85_000).threshold == 80_000  # stage2 -> stage2_threshold
    assert _verdict(budget, 95_000).threshold == 90_000  # stage3 -> stage3_threshold
    # allow/warn keep the historical stage-3 naming (see classify_budget).
    assert _verdict(budget, 10_000).threshold == 90_000


def test_ratio_is_the_one_the_budget_reported() -> None:
    """C0: the verdict must not recompute the ratio — Q#4 was a ratio defect."""
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    decision = budget.check(92_000)

    verdict = classify_budget(
        decision,
        stage2_threshold=budget.stage2_threshold,
        stage3_threshold=budget.stage3_threshold,
    )

    assert verdict.ratio == decision["ratio"]
    assert verdict.ratio == pytest.approx(0.92)


def test_raw_is_the_mapping_the_trace_stores() -> None:
    """C0: the durable row is carried, not rebuilt.

    ``stats._parse_events`` reads ``action``/``ratio``/``message`` straight off
    this mapping, and nine keys of it are written verbatim into the trace. If the
    verdict re-derived the payload, one event would have two sources of truth.
    """
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    decision = budget.check(85_000)

    verdict = classify_budget(
        decision,
        stage2_threshold=budget.stage2_threshold,
        stage3_threshold=budget.stage3_threshold,
    )

    assert dict(verdict.raw) == decision
    assert verdict.raw["action"] == "stage2"
    assert {"current_tokens", "limit_tokens", "warning_threshold"} <= set(verdict.raw)


def test_default_threshold_ladder_is_covered_too() -> None:
    """C0: the dynamic fallback (no configured threshold) uses the same rules.

    ``configured_threshold=None`` makes stage 2 ``min(80%, 150k)`` and stage 3
    ``min(stage2+1, 90%)``; the verdict must not assume an explicit threshold.
    """
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=None)
    assert budget.stage2_threshold == 80_000

    assert _verdict(budget, 85_000).action == "stage2"
    assert _verdict(budget, 95_000).action == "stage3"
    assert _verdict(budget, 95_000).threshold == budget.stage3_threshold


def test_unknown_action_fails_closed() -> None:
    """C0 (negative): a budget state the driver cannot classify is an error.

    The alternative — defaulting to ``allow`` — would mean a future
    ``ContextBudget`` state silently disables the gate. This is the one place
    where "unexpected input" must be loud.
    """
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    rogue = dict(budget.check(85_000))
    rogue["action"] = "panic"

    with pytest.raises(ValueError, match="unknown context-budget action"):
        classify_budget(rogue, stage2_threshold=80_000, stage3_threshold=90_000)


def test_action_vocabulary_is_closed_and_small() -> None:
    """C0: the set is the budget's own vocabulary, not an open string.

    Pinning it here means adding a state to ``ContextBudget`` forces a decision
    in ``classify_budget`` instead of producing a value nothing handles.
    """
    assert BUDGET_ACTIONS == {"allow", "warn", "stage2", "stage3"}

    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    produced = {budget.check(tokens)["action"] for tokens in (0, 70_000, 80_000, 90_000)}
    assert produced <= BUDGET_ACTIONS


# ---------------------------------------------------------------------------
# The seam is wired, not just defined (delivery law: edge mutant)
# ---------------------------------------------------------------------------


def test_driver_calls_the_verdict_on_the_real_budget_path(tmp_path: Path) -> None:
    """C1: `drive_session` really goes through `classify_budget`.

    Without this, the module could be imported and never called: every test
    above would stay green while the driver kept reading the raw dict. That is
    the "works if called" vs "is called" gap the tests-writing skill calls the
    edge mutant — measured here before writing it: reverting the driver to
    ``last_budget_ratio = decision.get("ratio", 0.0)`` survived the whole
    compaction/budget bank, because a value-preserving hop is invisible to
    behavioural assertions by construction.

    So the oracle is the call itself: a spy over the module attribute, plus the
    thresholds it was handed (they must be the *driver's* budget object, not a
    default).
    """
    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import EventLog, SessionState, coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry
    from tests.fixtures.session_wiring import make_mock_chain, mock_success_response

    seen: list[tuple[str, int, int]] = []
    real = coder_loop.classify_budget

    def spy(decision: Mapping[str, Any], *, stage2_threshold: int, stage3_threshold: int) -> BudgetVerdict:
        verdict = real(decision, stage2_threshold=stage2_threshold, stage3_threshold=stage3_threshold)
        seen.append((verdict.action, stage2_threshold, stage3_threshold))
        return verdict

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(coder_loop, "classify_budget", spy)
    try:
        log = EventLog(tmp_path / "events.jsonl", run_id="verdict-wired")
        state = SessionState(
            workspace_root=tmp_path,
            run_id="verdict-wired",
            log=log,
            feature_flags=FeatureFlags(context_budget_enabled=True),
        )
        chain = make_mock_chain(context_limit=100_000, compaction_threshold=80_000)
        chain.request.return_value = mock_success_response("done")

        with pytest.MonkeyPatch.context() as _:
            from unittest.mock import patch

            with patch("fa.memory.context_budget.estimate_tokens", return_value=85_000):
                coder_loop.drive_session(
                    "verdict wiring",
                    provider_chain=chain,
                    registry=ToolRegistry(),
                    hooks=HookRegistry(),
                    state=state,
                    max_turns=1,
                )
    finally:
        monkeypatch.undo()

    assert seen, "drive_session never called classify_budget — the seam is dormant"
    assert seen[0][0] == "stage2", f"unexpected verdict action: {seen[0][0]}"
    assert seen[0][1] == 80_000, "stage2_threshold must come from the driver's budget"


# ---------------------------------------------------------------------------
# hard_stop_row — the durable row must come from the verdict, not a second check
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tokens", [95_000, 94_000, 85_000, 72_000, 10_000])
def test_hard_stop_row_is_byte_equal_to_the_budgets_own_row(tokens: int) -> None:
    """C1: deriving the row from the verdict changes nothing observable.

    ``StageThreeStop`` builds the ``context_budget_hard_stop`` payload from
    ``verdict.raw`` instead of calling ``budget.check()`` a second time. That is
    only safe if the two are the same mapping, so it is asserted rather than
    argued: if the ladder or the row shape moves, this fails instead of
    ``fa stats`` quietly reading a different key set.

    The two message variants are the two call sites — the budget's own sentence
    and the circuit breaker's.
    """
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    verdict = _verdict(budget, tokens)

    for message in (budget.check(tokens)["message"], "Compaction circuit breaker triggered: locked."):
        assert verdict.hard_stop_row(message=message) == budget.hard_stop_row(tokens, message=message)


def test_hard_stop_row_overrides_only_the_message() -> None:
    """C1: the breaker's wording must not drag the numbers with it.

    Q#5's whole point was one schema for every exit. Overriding ``message`` is
    allowed; letting a caller change ``action`` or ``ratio`` by accident is not,
    so the override is proven to be surgical.
    """
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    verdict = _verdict(budget, 94_000)

    row = verdict.hard_stop_row(message="breaker wording")

    assert row["message"] == "breaker wording"
    assert row["action"] == verdict.action == "stage3"
    assert row["ratio"] == pytest.approx(0.94)
    assert row["current_tokens"] == 94_000
    assert row["stage3_threshold"] == budget.stage3_threshold
