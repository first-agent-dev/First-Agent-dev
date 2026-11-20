"""The budget ladder, tested without a session.

Why this file can exist at all
------------------------------
Before the ladder was extracted, every one of these cases could only be checked
by driving a whole session and catching the ``SessionOutcome``, because each
terminal branch ended in ``return finish_at(...)``. That is also why the two
budget defects (S6-F5's reason, Q#4's stale ratio) survived review: the exit was
the only observable.

Now a stop is a value. The tests below assert on it directly — and, crucially,
assert on its *absence* for the paths that must carry on, which is the check a
"returns something" test cannot make.

The rows are asserted too, not just the outcome: the durable sequence is what
`fa stats` and the trace oracle read, and it is produced here now. Each test
therefore pins both halves of the contract — what the operator sees, and what
the session does.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from fa.inner_loop import budget_ladder
from fa.inner_loop.budget_ladder import BudgetOutcome, BudgetStop, run_budget_ladder
from fa.inner_loop.compaction.compaction_turn import Stage2Result, Stage3Result
from fa.inner_loop.state import EventLog
from fa.inner_loop.turn_state import TurnState
from fa.memory.context_budget import ContextBudget

_LADDER_ARGS: dict[str, Any] = {
    "compactor_chain": None,
    "artifact_store": None,
    "compose_request": None,
}


def _log(tmp_path: Path, name: str = "ladder") -> EventLog:
    return EventLog(tmp_path / f"{name}.jsonl", run_id=name)


def _budget(*, limit: int = 100_000) -> ContextBudget:
    # Real object: thresholds come from the source, never re-derived here.
    return ContextBudget(limit_tokens=limit)


def _ladder(
    *,
    log: EventLog,
    budget: ContextBudget,
    tokens: int,
    threshold: int | None,
    turn_state: TurnState | None = None,
    output: Any = None,
) -> BudgetOutcome:
    return run_budget_ladder(
        usage=tokens,
        budget=budget,
        turn=1,
        max_turns=3,
        log=log,
        output=output,
        turn_state=turn_state or TurnState(),
        tool_payload=(),
        compaction_threshold=threshold,
        **_LADDER_ARGS,
    )


def _verdict(action: str, ratio: float, message: str = "m") -> Any:
    return budget_ladder.classify_budget(
        {"action": action, "ratio": ratio, "message": message},
        stage2_threshold=90_000,
        stage3_threshold=95_000,
    )


def _kinds(log: EventLog) -> list[str]:
    return [e.kind for e in log.read_all()]


def test_warn_rung_records_and_carries_on(tmp_path: Path) -> None:
    """A warning has no consequence for the session's fate — and says so."""
    log = _log(tmp_path)
    outcome = _ladder(log=log, budget=_budget(), tokens=75_000, threshold=None)
    assert outcome.stop is None
    assert outcome.verdict.action == "warn"
    assert _kinds(log) == ["context_budget_warn"]


def test_stage2_with_compaction_disabled_records_pressure_and_carries_on(tmp_path: Path) -> None:
    """Nothing to compact: the pressure is real, the exit is not."""
    log = _log(tmp_path)
    outcome = _ladder(log=log, budget=_budget(), tokens=85_000, threshold=None)
    assert outcome.stop is None
    # The ordering is the contract: detection first, then the pressure row.
    assert _kinds(log) == ["compaction_warning", "context_budget_warn"]


def test_stage3_with_compaction_disabled_writes_the_stop_and_reports_it(tmp_path: Path) -> None:
    """The stop's rows are written here; the exit is not taken here."""
    log = _log(tmp_path)
    outcome = _ladder(log=log, budget=_budget(), tokens=95_000, threshold=None)
    assert outcome.stop == BudgetStop(
        exit_code=1,
        reason="context_budget_hard_stop",
        final_text=outcome.verdict.message,
    )
    assert _kinds(log) == ["compaction_warning", "context_budget_hard_stop", "run_stopped"]


def test_the_outcome_carries_the_ratio_it_decided_on(tmp_path: Path) -> None:
    """Q#4, as an assertion on the value rather than on a printed percentage.

    The session-level writer is `TurnState`; a ladder that computed a ratio and
    forgot to hand it over would report the previous turn's number at exit.
    """
    turn_state = TurnState(last_budget_ratio=0.10)
    _ladder(log=_log(tmp_path), budget=_budget(), tokens=95_000, threshold=None, turn_state=turn_state)
    assert turn_state.last_budget_ratio == pytest.approx(0.95)


def test_carrying_on_returns_no_stop_but_the_last_verdict(tmp_path: Path) -> None:
    """`stop is None` is the contract for "continue"; nothing else encodes it."""
    outcome = _ladder(log=_log(tmp_path), budget=_budget(), tokens=50_000, threshold=None)
    assert outcome.stop is None
    assert outcome.verdict.action == "allow"
    assert _kinds(_log(tmp_path, "empty")) == []


class _Spy:
    """Records the calls the ladder makes, in order."""

    def __init__(self) -> None:
        self.calls: list[str] = []


def _scripted(*values: int) -> Any:
    tail = itertools.chain(values, itertools.repeat(values[-1]))

    def estimate(*_a: Any, **_k: Any) -> int:
        return next(tail)

    return estimate


def _fake_stage2(*, history: list[Any], **_: Any) -> Stage2Result:
    return Stage2Result(
        applied=True,
        decision={"action": "stage3", "ratio": 0.99, "message": "over"},
        verdict=_verdict("stage3", 0.99, "over"),
        history=history,
        messages_payload=[{"role": "user", "content": "masked"}],
        request_extras={"k": "v"},
        usage=92_000,
    )


def _fake_stage3_stopped(**_: Any) -> Stage3Result:
    return Stage3Result(
        stopped=True,
        applied=False,
        decision={"action": "stage3", "ratio": 0.92, "message": "over"},
        verdict=_verdict("stage3", 0.92, "over"),
        stop_message="stop-here",
        history=[],
        memory_summary="",
        messages_payload=[],
        request_extras={},
        usage=0,
    )


def test_masking_then_compaction_stop_reports_the_post_compaction_ratio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The full ladder in one test: mask, re-classify, compact, stop.

    Two properties at once, because they broke together before: the ratio at the
    stop is the one compaction ended with (not the pre-mask 0.95), and the masked
    payload is discarded — the run is over, so handing the driver a prompt it
    must not send would be a trap.
    """
    monkeypatch.setattr(budget_ladder, "run_stage2_masking", _fake_stage2)
    monkeypatch.setattr(budget_ladder, "run_stage3_compaction", _fake_stage3_stopped)
    turn_state = TurnState(conversation_history=[{"role": "user", "content": "hi"}])
    log = _log(tmp_path)

    outcome = _ladder(log=log, budget=_budget(), tokens=95_000, threshold=80_000, turn_state=turn_state)

    assert outcome.stop is not None and outcome.stop.final_text == "stop-here"
    assert turn_state.last_budget_ratio == pytest.approx(0.92)
    assert outcome.messages_payload is None
    assert _kinds(log) == ["compaction_warning"]


def test_masking_that_resolves_the_pressure_carries_the_masked_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stage-2 path that does NOT reach stage-3 — the majority case, unpinned until now.

    Distinct numbers on purpose: masking reports 0.75 where the pre-mask check saw
    0.95, so a ladder that forgot to adopt the masking result would still report
    the old ratio and send the old prompt. Stage-3 raising means "reached
    compaction" is a failure here, not an alternative path.
    """
    monkeypatch.setattr(
        budget_ladder,
        "run_stage2_masking",
        lambda *, history, **_: Stage2Result(
            applied=True,
            decision={"action": "allow", "ratio": 0.75, "message": "ok"},
            verdict=_verdict("allow", 0.75, "ok"),
            history=[*history, {"role": "system", "content": "masked"}],
            messages_payload=[{"role": "user", "content": "masked"}],
            request_extras={"k": "v"},
            usage=92_000,
        ),
    )

    def _must_not_compact(**_: Any) -> Any:
        raise AssertionError("stage-3 ran although masking left the prompt under the threshold")

    monkeypatch.setattr(budget_ladder, "run_stage3_compaction", _must_not_compact)
    turn_state = TurnState()
    outcome = _ladder(log=_log(tmp_path), budget=_budget(), tokens=95_000, threshold=80_000, turn_state=turn_state)

    assert outcome.stop is None
    assert outcome.messages_payload == ({"role": "user", "content": "masked"},)
    assert outcome.request_extras == {"k": "v"}
    assert outcome.usage == 92_000
    assert turn_state.last_budget_ratio == pytest.approx(0.75)


def test_compaction_that_succeeds_hands_back_the_new_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stopped=True is not the only way stage-3 ends: success must carry values."""
    monkeypatch.setattr(
        budget_ladder,
        "run_stage2_masking",
        lambda **_: Stage2Result(
            applied=False,
            decision={"action": "stage3", "ratio": 0.95, "message": "over"},
            verdict=_verdict("stage3", 0.95, "over"),
            history=[],
            messages_payload=[],
            request_extras={},
            usage=0,
        ),
    )
    monkeypatch.setattr(
        budget_ladder,
        "run_stage3_compaction",
        lambda **_: Stage3Result(
            stopped=False,
            applied=True,
            decision={"action": "allow", "ratio": 0.4, "message": "ok"},
            verdict=_verdict("allow", 0.4, "ok"),
            stop_message="",
            history=[{"role": "user", "content": "compacted"}],
            memory_summary="the summary",
            messages_payload=[{"role": "user", "content": "compacted"}],
            request_extras={"x": 1},
            usage=40_000,
        ),
    )
    turn_state = TurnState()
    outcome = _ladder(log=_log(tmp_path), budget=_budget(), tokens=95_000, threshold=80_000, turn_state=turn_state)

    assert outcome.stop is None
    assert outcome.usage == 40_000
    assert outcome.messages_payload == ({"role": "user", "content": "compacted"},)
    assert outcome.request_extras == {"x": 1}
    # The conversation state is the other half of the outcome, and it is why the
    # driver keeps it: both fields move together or neither does.
    assert turn_state.memory_summary == "the summary"
    assert turn_state.last_budget_ratio == pytest.approx(0.4)


def test_ladder_never_calls_finish_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The split's whole point: the module may not end a session.

    A `finish_at` called from here would need the driver's `collected_results`,
    which is the thing the plan says stays put. Asserting the import does not
    exist keeps a future edit from reintroducing it quietly.
    """
    assert "finish_at" not in dir(budget_ladder)
    outcome = _ladder(log=_log(tmp_path), budget=_budget(), tokens=95_000, threshold=None)
    assert isinstance(outcome.stop, BudgetStop)


def test_unrecognised_action_is_loud_not_silent(tmp_path: Path) -> None:
    """`classify_budget` raises on an unknown action; the ladder must not swallow it."""
    budget = MagicMock()
    budget.check.return_value = {"action": "banana", "ratio": 0.5, "message": "?"}
    budget.stage2_threshold = 90_000
    budget.stage3_threshold = 95_000
    with pytest.raises(ValueError):
        _ladder(log=_log(tmp_path), budget=budget, tokens=96_000, threshold=80_000)
