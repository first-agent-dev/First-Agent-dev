"""S5P1 seam: the acquisition stage exists, and nothing grants it a candidate.

The stage kind is one half of this; the other half is that five call sites used to
ask "is this kind *not* ordinary planning?" and treat the answer as "owns the
staged-candidate buffer". That was true only while every non-ordinary kind happened
to own one. ``ACQUISITION`` runs before any plan is admitted, so it can neither
label a buffer (CT120 needs an admitted ``plan_ref``) nor satisfy a promotion.

These are C0/C1 unit oracles over the real types: no authority, no provider.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop.plan_admission import snapshot_from_bytes
from fa.inner_loop.plan_promotion import PlanPromotionError, seed_plan_candidate
from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchError, PlannerDispatchKind
from fa.inner_loop.profiles import _candidate_dispatch
from fa.inner_loop.tools.write_file import build_scoped_write_file_tool

_RUN = "s5p1-run"
# The canonical parent is project-specific, so a made-up slug would make the
# path check the thing under test rather than the acquisition refusal.
_PLAN = "worklogs/planning-topology-and-executable-contracts-loop/increments/increment-03-demo.md"
_CANDIDATE = f".fa/admission/{_RUN}/candidate-{'a' * 32}.md"


def _acquisition() -> PlannerDispatch:
    return PlannerDispatch(PlannerDispatchKind.ACQUISITION, _RUN)


def test_acquisition_exists_and_owns_no_candidate() -> None:
    """C0 — the kind is representable, and says plainly that it owns no buffer."""
    assert PlannerDispatchKind.ACQUISITION.value == "ACQUISITION"
    assert _acquisition().owns_candidate is False


def test_only_the_two_repair_kinds_own_a_candidate() -> None:
    """C0 — ownership is a positive fact per kind, not the absence of a negation.

    Written as an exhaustive table so adding a fourth kind without deciding whether
    it owns a buffer fails here rather than silently granting one.
    """
    expected = {
        PlannerDispatchKind.ORDINARY_PLANNING: False,
        PlannerDispatchKind.ADMISSION_REPAIR: True,
        PlannerDispatchKind.EVAL_REPLAN: True,
        PlannerDispatchKind.ACQUISITION: False,
    }
    assert expected.keys() == set(PlannerDispatchKind)
    for kind, owns in expected.items():
        dispatch = PlannerDispatch(kind, _RUN, candidate_target=_CANDIDATE if owns else None)
        assert dispatch.owns_candidate is owns, kind


def test_acquisition_cannot_carry_a_candidate_or_an_active_plan() -> None:
    """C1 (negative) — a half-built acquisition capability is refused at construction.

    Both fields are refusals, not ignored values: a target would be a buffer the
    stage cannot label, and an active plan would be a claim about a target the
    model has not selected yet.
    """
    with pytest.raises(PlannerDispatchError):
        PlannerDispatch(PlannerDispatchKind.ACQUISITION, _RUN, candidate_target=_CANDIDATE)
    with pytest.raises(PlannerDispatchError):
        PlannerDispatch(PlannerDispatchKind.ACQUISITION, _RUN, active_plan=_PLAN)


def test_no_candidate_tool_is_built_for_an_acquisition_stage() -> None:
    """C1 (negative) — the writer capability is withheld, in every call site.

    ``_candidate_dispatch`` feeds the per-profile builder table; the scoped writer
    refuses the kind directly. Either path granting a buffer to acquisition would
    give a pre-plan stage a write capability it cannot legally use.
    """
    dispatch = _acquisition()
    assert _candidate_dispatch(dispatch) is None
    with pytest.raises(PlannerDispatchError):
        build_scoped_write_file_tool(Path("/tmp"), dispatch)


def test_acquisition_cannot_seed_a_repair_candidate(tmp_path: Path) -> None:
    """C1 (negative) — promotion refuses acquisition, so no seed is written.

    The refusal must land before any filesystem effect: a stage that cannot own a
    candidate must not leave a directory behind that a later repair could adopt.
    """
    source = snapshot_from_bytes(_PLAN, b"# plan\n")
    with pytest.raises(PlanPromotionError) as refused:
        seed_plan_candidate(tmp_path, source, run_id=_RUN, kind=PlannerDispatchKind.ACQUISITION)
    assert refused.value.rule == "scope-denied"
    assert not (tmp_path / ".fa" / "admission" / _RUN).exists()
