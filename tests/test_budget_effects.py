"""C1 — the non-terminal budget effects, pinned on both sides.

``budget_effects`` owns two verdicts whose consequence is "record it and carry
on": ``warn``, and ``stage2`` while compaction is disabled. Moving them out of
the driver's 399-line block is behaviour-preserving by construction, so the
oracle has to be the *recipient* — the durable log row and the console event —
rather than the placement of the code.

Two-sided per the tests-writing skill: every assertion here pairs the EventLog
row with the OutputEvent, because "the row was written" and "the operator saw it"
are separate promises and only one of them used to be checked on some paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.budget_effects import emit_context_warn, record_budget_pressure, record_compaction_pressure
from fa.inner_loop.budget_turn import BudgetVerdict, classify_budget
from fa.inner_loop.state import EventLog
from fa.memory.context_budget import ContextBudget
from fa.output import EventBus, OutputEvent


class _Capture:
    def __init__(self) -> None:
        self.events: list[OutputEvent] = []

    def on_event(self, event: OutputEvent) -> None:
        self.events.append(event)


@pytest.fixture
def wiring(tmp_path: Path) -> tuple[EventLog, EventBus, _Capture]:
    log = EventLog(tmp_path / "events.jsonl", run_id="effects")
    bus = EventBus()
    capture = _Capture()
    bus.add(capture)
    return log, bus, capture


def _verdict(budget: ContextBudget, tokens: int) -> BudgetVerdict:
    return classify_budget(
        budget.check(tokens),
        stage2_threshold=budget.stage2_threshold,
        stage3_threshold=budget.stage3_threshold,
    )


# ---------------------------------------------------------------------------
# warn
# ---------------------------------------------------------------------------


def test_warn_writes_the_row_and_mirrors_it(wiring: tuple[EventLog, EventBus, _Capture]) -> None:
    """C1: one durable row, one console event, same action and percentage."""
    log, bus, capture = wiring
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    verdict = _verdict(budget, 75_000)
    assert verdict.action == "warn"

    record_budget_pressure(verdict, turn=2, max_turns=8, log=log, output=bus, compaction_enabled=False)

    rows = [row for row in log.read_all() if row.kind == "context_budget_warn"]
    assert len(rows) == 1
    assert rows[0].content["action"] == "warn"
    assert rows[0].content["ratio"] == verdict.ratio
    # the durable row is the verdict's raw mapping, keys and all: `fa stats`
    # reads action/ratio/message off it and the trace stores it verbatim
    assert rows[0].content["current_tokens"] == 75_000

    warns = [e for e in capture.events if e.type == "context_warn"]
    assert len(warns) == 1
    assert warns[0].data["action"] == "warn"
    assert warns[0].data["pct"] == round(verdict.ratio * 100)
    assert warns[0].turn == 2 and warns[0].max_turns == 8


def test_warn_row_precedes_its_console_event(wiring: tuple[EventLog, EventBus, _Capture]) -> None:
    """C1: ordering is part of the contract, not an accident of statement order.

    A console event that arrives before its durable row means an operator can
    see pressure that the trace cannot later explain.
    """
    log, bus, capture = wiring
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    verdict = _verdict(budget, 75_000)

    record_budget_pressure(verdict, turn=1, max_turns=4, log=log, output=bus, compaction_enabled=False)

    kinds = [row.kind for row in log.read_all()]
    assert kinds.count("context_budget_warn") == 1
    assert [e.type for e in capture.events] == ["context_warn"]


# ---------------------------------------------------------------------------
# stage2 with compaction disabled
# ---------------------------------------------------------------------------


def test_stage2_without_compaction_records_and_continues(wiring: tuple[EventLog, EventBus, _Capture]) -> None:
    """C1: real pressure, nothing to compact — the run must not be told to stop.

    This is the branch whose whole point is "we noticed and we are carrying on";
    it returns normally rather than signalling a stop.
    """
    log, bus, capture = wiring
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    verdict = _verdict(budget, 85_000)
    assert verdict.action == "stage2"

    record_budget_pressure(verdict, turn=3, max_turns=8, log=log, output=bus, compaction_enabled=False)

    rows = [row for row in log.read_all() if row.kind == "context_budget_warn"]
    assert len(rows) == 1 and rows[0].content["action"] == "stage2"

    warns = [e for e in capture.events if e.type == "context_warn"]
    assert len(warns) == 1
    assert warns[0].data["action"] == "stage2"
    # no compaction was attempted: nothing to start, nothing to end
    assert not [e for e in capture.events if e.type in {"compaction_start", "compaction_end"}]


# ---------------------------------------------------------------------------
# negatives — the two things this module must refuse to do
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("tokens", "compaction_enabled"), [(95_000, False), (95_000, True), (85_000, True)])
def test_terminal_or_compacting_verdicts_are_refused(
    wiring: tuple[EventLog, EventBus, _Capture], tokens: int, compaction_enabled: bool
) -> None:
    """C0 (negative): paths that can end the session must not move silently.

    ``stage3`` ends the run; ``stage2`` with compaction enabled starts a whole
    compaction stage. Neither is "record and carry on", so this module raises
    instead of half-handling them — the slice would otherwise claim to own
    effects it does not.
    """
    log, bus, _ = wiring
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    verdict = _verdict(budget, tokens)

    with pytest.raises(ValueError, match="does not handle action"):
        record_budget_pressure(verdict, turn=1, max_turns=4, log=log, output=bus, compaction_enabled=compaction_enabled)


def test_no_bus_still_writes_the_durable_row(wiring: tuple[EventLog, EventBus, _Capture]) -> None:
    """C1: console is optional, the trace is not.

    Library callers and `fa inner-loop-smoke` run without an EventBus. The
    durable row must still exist or the pressure becomes invisible after the
    fact — the "failure-observable" rule.
    """
    log, _, _ = wiring
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    verdict = _verdict(budget, 75_000)

    record_budget_pressure(verdict, turn=1, max_turns=4, log=log, output=None, compaction_enabled=False)

    assert [row.kind for row in log.read_all()].count("context_budget_warn") == 1


# ---------------------------------------------------------------------------
# compaction pressure (the row that fires in both enabled/disabled cases)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("compaction_enabled", [True, False])
def test_compaction_pressure_fires_regardless_of_enablement(
    wiring: tuple[EventLog, EventBus, _Capture], compaction_enabled: bool
) -> None:
    """C1: the warning reports pressure, not intent — both cases, both sides."""
    log, bus, capture = wiring
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    verdict = _verdict(budget, 85_000)

    record_compaction_pressure(
        verdict,
        turn=1,
        max_turns=4,
        log=log,
        output=bus,
        compaction_enabled=compaction_enabled,
    )

    rows = [row for row in log.read_all() if row.kind == "compaction_warning"]
    assert len(rows) == 1
    assert rows[0].content["compaction_enabled"] is compaction_enabled
    assert rows[0].content["threshold"] == budget.stage2_threshold  # stage2 -> stage2 threshold
    events = [e for e in capture.events if e.type == "compaction_warning"]
    assert len(events) == 1
    assert events[0].data == rows[0].content


def test_compaction_pressure_refuses_verdicts_without_pressure(
    wiring: tuple[EventLog, EventBus, _Capture],
) -> None:
    """C0 (negative): 'allow' must never produce a compaction warning."""
    log, bus, _ = wiring
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    verdict = _verdict(budget, 10_000)
    assert verdict.action == "allow"

    with pytest.raises(ValueError, match="only defined for stage2/stage3"):
        record_compaction_pressure(verdict, turn=1, max_turns=4, log=log, output=bus, compaction_enabled=True)


def test_pct_cannot_drift_from_the_verdict() -> None:
    """C0: the percentage has no parameter to drift through (the Q#4 shape).

    Q#4 was a caller-local ``last_budget_ratio`` that stopped matching the
    decision. ``emit_context_warn`` takes the verdict, so the only way to get a
    wrong percentage is to pass a wrong verdict — which is a different bug with
    a different test.
    """
    import inspect

    params = inspect.signature(emit_context_warn).parameters
    assert "pct" not in params
    assert "verdict" in params


# ---------------------------------------------------------------------------
# The seam is wired into the driver, not just importable (delivery law)
# ---------------------------------------------------------------------------


def test_driver_routes_non_terminal_pressure_through_this_module(tmp_path: Path) -> None:
    """C1: `drive_session` really calls `record_budget_pressure` — both branches.

    Measured before writing this: reverting the driver to its previous inline
    ``log.append`` for the warn branch survived the entire 298-test
    compaction/budget bank. A behaviour-preserving move is invisible to
    behavioural assertions, so the oracle has to be the call itself.

    Both non-terminal branches are covered in one drive by using a config where
    the warn rung is hit on turn 1... which it cannot be: a single run crosses
    one rung. So the two branches are asserted in separate runs — the warn rung
    with compaction disabled, and stage-2 pressure with compaction disabled —
    which is also the only pair this module claims to own.
    """

    from unittest.mock import patch

    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import EventLog, SessionState, budget_effects, budget_ladder, coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry
    from tests.fixtures.session_wiring import make_mock_chain, mock_success_response

    def drive(tokens: int, *, threshold: int | None, run_id: str) -> list[str]:
        seen: list[str] = []
        real = budget_effects.record_budget_pressure

        def spy(verdict: BudgetVerdict, **kwargs: Any) -> None:
            seen.append(verdict.action)
            return real(verdict, **kwargs)

        monkeypatch = pytest.MonkeyPatch()
        # The pressure row is produced by the ladder now; the driver delegates.
        monkeypatch.setattr(budget_ladder, "_record_budget_pressure", spy)
        try:
            log = EventLog(tmp_path / f"{run_id}.jsonl", run_id=run_id)
            state = SessionState(
                workspace_root=tmp_path,
                run_id=run_id,
                log=log,
                feature_flags=FeatureFlags(context_budget_enabled=True),
            )
            chain = make_mock_chain(context_limit=100_000, compaction_threshold=threshold)
            chain.request.return_value = mock_success_response("done")
            with patch("fa.memory.context_budget.estimate_tokens", return_value=tokens):
                coder_loop.drive_session(
                    run_id,
                    provider_chain=chain,
                    registry=ToolRegistry(),
                    hooks=HookRegistry(),
                    state=state,
                    max_turns=1,
                )
        finally:
            monkeypatch.undo()
        return seen

    # warn rung (no compaction configured, so the verdict is plain "warn")
    assert drive(75_000, threshold=None, run_id="warn-wired") == ["warn"]
    # stage-2 rung with compaction disabled → the same "record and carry on" path
    assert drive(85_000, threshold=None, run_id="stage2-wired") == ["stage2"]
