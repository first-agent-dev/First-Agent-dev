"""S5P1 STEP2 — the planner's choice reaches admission from inside the same run.

`i03-execution-workspace-spec:1356` forbids the shape this bank could so easily
have encoded: run a planner, read its choice, then re-enter `run_workflow` with a
coder. So the choice is read from the stage that produced it — the `outcome_sink`
list `_run_stage` already builds for every role — and resolved against the same
pinned view the planner read through.

Classes (knowledge/skills/tests-writing):
  C0 — the seam refuses when there is nothing to read.
  C1 — a real planner message plus a real inventory becomes a real snapshot.

What must stay true (each test names the producer it kills):
  * the snapshot is the resolver's, with its own `source_kind` — not a rebuilt one;
  * no settled planner message is an error, never an empty selection;
  * a clarification passes through as a clarification and never as a snapshot;
  * the substrate's name list is the only thing consulted, so a name outside the
    pinned revision cannot become an IO probe.
"""

from __future__ import annotations

import json

import pytest

from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.managed_acquisition import AcquisitionChoiceError
from fa.inner_loop.workflow_controller import (
    AcquisitionSubstrate,
    StageResult,
    _read_acquisition_choice,
)
from fa.inner_loop.workflow_controller import (
    _run_linear as linear,
)

from .test_s5p1_acquisition_resolution import _port, _rendered_files

SELECTION_JSON = json.dumps({"kind": "SELECT_EXISTING", "project_slug": "demo-project", "increment_id": "I01"})
CLARIFICATION_JSON = json.dumps({"kind": "NEEDS_CLARIFICATION", "reason": "AMBIGUOUS_PROJECT"})


def _outcome(text: str) -> SessionOutcome:
    return SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text=text)


def _substrate(port=None) -> AcquisitionSubstrate:  # type: ignore[no-untyped-def]
    return AcquisitionSubstrate(port=port or _port(), project_names=("demo-project",))


# ── C1: a real message becomes a real snapshot ────────────────────────────────


def test_a_settled_planner_message_becomes_the_admitted_snapshot() -> None:
    outcome = _read_acquisition_choice([_outcome(SELECTION_JSON)], _substrate())

    assert outcome.snapshot is not None
    assert outcome.snapshot.ref.source_kind == "EXISTING_SELECTION"
    assert outcome.clarification is None and outcome.bootstrap is None
    assert outcome.roadmap is not None and outcome.increment is not None


def test_the_last_settled_message_is_the_one_read() -> None:
    """`sink` may hold earlier outcomes; only the terminal one is the choice."""
    earlier = _outcome("not json at all")
    outcome = _read_acquisition_choice([earlier, _outcome(SELECTION_JSON)], _substrate())

    assert outcome.snapshot is not None


def test_a_clarification_is_a_clarification_and_not_a_snapshot() -> None:
    outcome = _read_acquisition_choice([_outcome(CLARIFICATION_JSON)], _substrate())

    assert outcome.clarification is not None
    assert outcome.snapshot is None


def test_a_name_outside_the_pinned_revision_is_never_read() -> None:
    port = _port()
    substrate = AcquisitionSubstrate(port=port, project_names=("demo-project",))
    message = json.dumps({"kind": "SELECT_EXISTING", "project_slug": "other-project", "increment_id": "I01"})

    outcome = _read_acquisition_choice([_outcome(message)], substrate)

    assert outcome.clarification is not None
    assert port.list_calls == [] and port.read_calls == []


# ── C0: nothing to read is an error, not an empty selection ──────────────────


def test_no_settled_outcome_is_refused() -> None:
    with pytest.raises(AcquisitionChoiceError):
        _read_acquisition_choice([], _substrate())


def test_a_message_with_no_choice_is_refused() -> None:
    with pytest.raises(AcquisitionChoiceError):
        _read_acquisition_choice([_outcome("I have read the roadmap and will now plan.")], _substrate())


def test_an_empty_final_text_is_refused() -> None:
    with pytest.raises(AcquisitionChoiceError):
        _read_acquisition_choice([_outcome("")], _substrate())


# ── the stage carries it exactly once ────────────────────────────────────────


def test_a_stage_result_can_carry_an_acquisition_choice() -> None:
    """The field exists so `_run_stage` can hand the choice back to the controller."""
    outcome = _read_acquisition_choice([_outcome(SELECTION_JSON)], _substrate())
    result = StageResult(role="planner", exit_code=0, acquisition=outcome)

    assert result.acquisition is outcome
    assert StageResult(role="coder", exit_code=0).acquisition is None


def test_the_seam_is_not_reachable_from_the_linear_loop_signature() -> None:
    """Guard against the forbidden two-phase shape.

    `_run_linear` takes exactly (ctx, roles, run_stage_fn). A seam threaded in as a
    fourth parameter would mean the caller could inject a pre-run planner, which is
    the design `i03-execution-workspace-spec:1356` explicitly forbids.
    """
    import inspect

    assert list(inspect.signature(linear).parameters) == ["ctx", "roles", "run_stage_fn"]


def test_the_inventory_fixture_is_the_real_renderer() -> None:
    """`_rendered_files` is shared with the resolver bank; keep it the real one."""
    files = _rendered_files()
    assert any(path.endswith("roadmap.md") for path in files)
    assert any("increments/increment-01-foundation.md" in path for path in files)
