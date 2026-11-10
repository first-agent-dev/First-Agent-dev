"""C1 — the conversation state the driver used to carry as four locals.

`TurnState` holds what a session *says* (history, summary) and the two numbers
its exit reports (last budget ratio, chain exhaustion count). Each is written by
one phase and read by a later one, which is why none can be consumed inside the
turn that produced it.

The three behaviours worth pinning are the three ways this goes wrong:

* the restored tuple is ``(summary, history)`` while the fields are the other
  way round — a silent swap starts a session with its summary in the history;
* stage 2 adopts new history but no summary (masking does not summarize);
* ``last_budget_ratio`` must describe the state the stop was decided on, not the
  one before compaction (Q#4).
"""

from __future__ import annotations

import pytest

from fa.inner_loop.turn_state import TurnState


def test_defaults_are_an_empty_session() -> None:
    state = TurnState()

    assert state.conversation_history == []
    assert state.memory_summary == ""
    assert state.last_budget_ratio == 0.0
    assert state.chain_exhaustion_count == 0


def test_from_restored_unswaps_the_tuple() -> None:
    """C1: ``restore_conversation_history`` returns ``(summary, history)``.

    Unpacking it inline is one silent swap away from a session whose summary is
    its history. The order is pinned here so a refactor cannot quietly flip it.
    """
    history = [{"role": "assistant", "content": "hi"}]

    state = TurnState.from_restored(("the summary", history))

    assert state.memory_summary == "the summary"
    assert state.conversation_history == history


def test_adopt_compaction_takes_history_and_ratio() -> None:
    """Stage-2 shape: new history, no summary change."""
    state = TurnState(memory_summary="keep me")
    new_history = [{"role": "user", "content": "masked"}]

    state.adopt_compaction(history=new_history, ratio=0.42)

    assert state.conversation_history == new_history
    assert state.last_budget_ratio == 0.42
    assert state.memory_summary == "keep me", "masking must not clear the summary"


def test_adopt_compaction_updates_the_summary_when_given_one() -> None:
    """Stage-3 shape: compaction also summarizes."""
    state = TurnState(memory_summary="old")

    state.adopt_compaction(history=[], summary="new", ratio=0.9)

    assert state.memory_summary == "new"
    assert state.last_budget_ratio == 0.9


def test_stage2_adoption_is_not_a_mutation_of_the_callers_list() -> None:
    """The field is a reference, not a copy — so the caller must hand a fresh list.

    Documented here because the opposite assumption (defensive copy) would make
    ``adopt`` quietly disagree with what the rest of the loop sees.
    """
    history = [{"role": "user", "content": "a"}]
    state = TurnState()
    state.adopt_compaction(history=history, ratio=0.1)

    history.append({"role": "assistant", "content": "b"})

    assert len(state.conversation_history) == 2


@pytest.mark.parametrize(("ratio", "expected"), [(0.0, 0.0), (0.92, 0.92), (0.99, 0.99)])
def test_last_budget_ratio_is_whatever_was_last_recorded(ratio: float, expected: float) -> None:
    """Q#4's contract, at the smallest possible scale.

    The exit reports this number as ``context_used_pct``. The bug was reporting
    the pre-compaction value after a compaction succeeded, so "last write wins"
    is the whole rule and it is worth stating explicitly.
    """
    state = TurnState()

    state.adopt_compaction(history=[], ratio=0.99)
    state.note_budget_ratio(ratio)

    assert state.last_budget_ratio == expected


def test_note_budget_ratio_leaves_history_alone() -> None:
    """The warn and stage-3-stop paths record a percentage, not a new history."""
    state = TurnState(conversation_history=[{"role": "user", "content": "a"}])
    before = state.conversation_history

    state.note_budget_ratio(0.95)

    assert state.conversation_history is before
    assert state.last_budget_ratio == 0.95
