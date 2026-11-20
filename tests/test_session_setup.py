"""Preconditions of a session, and the one ordering trap inside them.

The block that became `prepare_session` was pure assignment with a single `if`,
which is exactly the kind of code that looks untestable and stays untested — yet
it hid a real coupling: the budget's stage thresholds are percentages *of the
limit it is handed*, so a budget built from an unclamped limit puts every
threshold below the floor while every test that never trips the floor stays
green. The clamp test below therefore asserts on the budget's derived
thresholds, not just on the returned integer.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from fa.inner_loop.session_setup import MIN_CONTEXT_LIMIT, SessionSetup, prepare_session
from fa.inner_loop.state import EventLog
from fa.inner_loop.usage_ledger import UsageLedger
from fa.memory.context_budget import ContextBudget


def _log(tmp_path: Path) -> EventLog:
    return EventLog(tmp_path / "setup.jsonl", run_id="setup")


def _prepare(log: EventLog, **overrides: object) -> SessionSetup:
    args: dict[str, object] = {
        "log": log,
        "context_limit": 100_000,
        "compaction_threshold": None,
        "pinned_buffer": None,
        "tool_payload": [{"name": "fs_read_file"}],
    }
    args.update(overrides)
    return prepare_session(**args)  # type: ignore[arg-type]


def test_healthy_limit_is_used_as_given_and_records_nothing(tmp_path: Path) -> None:
    """No clamp, no row: a telemetry line appears only when something was fixed."""
    log = _log(tmp_path)
    setup = _prepare(log)
    assert setup.context_limit == 100_000
    assert setup.budget.limit_tokens == 100_000
    assert [e.kind for e in log.read_all()] == []


def test_below_floor_is_clamped_and_the_clamp_is_recorded(tmp_path: Path) -> None:
    """The operator-visible row is part of the contract, not a debugging aid."""
    log = _log(tmp_path)
    setup = _prepare(log, context_limit=100)

    assert setup.context_limit == MIN_CONTEXT_LIMIT
    rows = log.read_all()
    assert [r.kind for r in rows] == ["telemetry"]
    assert rows[0].content == {"message": "context_limit=100 below floor 32000, clamped"}


def test_budget_is_built_from_the_clamped_limit_not_the_configured_one(tmp_path: Path) -> None:
    """The ordering that this module exists to make testable.

    100 is a typo for 100000. Built from 100, stage 2 would sit at 80 tokens and
    every real turn would be a stage-3 stop; built from the floor, it sits at
    25 600. Asserting the derived numbers pins the order, which asserting
    `context_limit == 32_000` alone would not: a later refactor could clamp the
    field and construct the budget from the argument.
    """
    setup = _prepare(_log(tmp_path), context_limit=100)
    assert setup.budget.stage2_threshold == min(int(MIN_CONTEXT_LIMIT * 0.80), 150_000)
    assert setup.budget.stage2_threshold > 100
    assert setup.budget.limit_tokens == MIN_CONTEXT_LIMIT


def test_exact_floor_is_not_a_clamp(tmp_path: Path) -> None:
    """`<` not `<=`: a limit of exactly 32 000 is usable and must not warn."""
    log = _log(tmp_path)
    setup = _prepare(log, context_limit=MIN_CONTEXT_LIMIT)
    assert setup.context_limit == MIN_CONTEXT_LIMIT
    assert [e.kind for e in log.read_all()] == []


def test_compaction_threshold_reaches_the_budget_unchanged(tmp_path: Path) -> None:
    """Threshold presence is the compaction toggle (S14); it must survive intact."""
    setup = _prepare(_log(tmp_path), compaction_threshold=80_000)
    assert setup.compaction_threshold == 80_000
    assert setup.budget.stage2_threshold == 80_000


def test_prompt_tool_definitions_are_a_copy_not_the_shared_payload(tmp_path: Path) -> None:
    """The loop mutates nothing today; a shared list would make that a matter of luck."""
    payload = [{"name": "fs_read_file", "params": {"path": "a"}}]
    setup = _prepare(_log(tmp_path), tool_payload=payload)
    assert setup.tool_defs_for_prompt == payload
    assert setup.tool_defs_for_prompt is not payload
    assert setup.tool_defs_for_prompt[0] is not payload[0]


def test_ledger_is_fresh_and_the_setup_is_frozen(tmp_path: Path) -> None:
    """One ledger per session; and a frozen value cannot be half-rebound later."""
    first = _prepare(_log(tmp_path))
    second = _prepare(_log(tmp_path))
    assert isinstance(first.ledger, UsageLedger)
    assert first.ledger is not second.ledger
    with pytest.raises(FrozenInstanceError):
        first.budget = ContextBudget(limit_tokens=1)  # type: ignore[misc]


def test_pinned_buffer_is_passed_through_untouched(tmp_path: Path) -> None:
    """The assembler does not decide *whether* there is a buffer — the caller does."""
    sentinel = object()
    assert _prepare(_log(tmp_path), pinned_buffer=sentinel).pinned_buffer is sentinel
    assert _prepare(_log(tmp_path), pinned_buffer=None).pinned_buffer is None
