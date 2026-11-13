"""S5P1 STEP2 — acquisition admits the coder, and refuses before it.

The run-level contract, with the real `run_workflow` composition and only the stage
dispatcher injected:

  * a planner that selects an existing increment admits the coder against *that*
    plan, proven by the admission record's `plan_ref` and by the coder stage seeing
    a plan path it never received from the caller;
  * a planner that asks for clarification, or wants a new project, or emits no
    usable choice, stops the run **before the coder is dispatched** — proven with a
    poison dispatcher that raises if any role after the planner is called;
  * the entry check still refuses a coder with no plan when no acquisition
    substrate is bound.

Classes (knowledge/skills/tests-writing):
  C1 — the admitted lifecycle: planner → bound snapshot → coder.
  C0 — every non-selection outcome is a closed refusal, none of them a coder run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

from fa.execution.publication import render_bundle
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.plan_admission import PlanRef, PlanSnapshot
from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
from fa.inner_loop.tools.workspace_port import PortDirectoryEntry, PortProjectArtifactListing
from fa.inner_loop.workflow_controller import (
    AcquisitionSubstrate,
    run_workflow,
    workflow_artifact_paths,
)

from .test_plan_reference import _config
from .test_s5p1_acquisition_resolution import _Port, _port

SELECTION = json.dumps({"kind": "SELECT_EXISTING", "project_slug": "demo-project", "increment_id": "I01"})
CLARIFICATION = json.dumps({"kind": "NEEDS_CLARIFICATION", "reason": "AMBIGUOUS_PROJECT"})
BOOTSTRAP = json.dumps(
    {
        "kind": "BOOTSTRAP_NEW_PROJECT",
        "project_slug": "new-project",
        "increment_slug": "foundation",
        "roadmap_body": "## Intent\n\nNew.\n\n## Out of scope\n\nNone.\n",
        "increment_body": "## SLICE1: Build\n\nDo it.\n",
    }
)


class _PlannerThen:
    """Dispatch the planner with `message`, and record/veto every later role."""

    def __init__(self, message: str, *, forbid_after_planner: bool) -> None:
        self.message = message
        self.forbid_after_planner = forbid_after_planner
        self.roles: list[str] = []

    def __call__(self, args: argparse.Namespace, **kwargs: Any) -> int:
        role = str(getattr(args, "role", "?"))
        self.roles.append(role)
        if role == "planner":
            sink = kwargs.get("outcome_sink")
            if isinstance(sink, list):
                sink.append(SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text=self.message))
            return 0
        if self.forbid_after_planner:
            raise AssertionError(f"role {role!r} was dispatched after a refused acquisition")
        return 0


def _run(
    tmp_path: Path, *, run_id: str, stage: Any, roles: list[str], mode: str = "linear", **kwargs: Any
) -> tuple[int, Any]:
    return run_workflow(
        roles=roles,
        task="do the thing",
        per_role_task={},
        mode=mode,
        max_repairs=kwargs.pop("max_repairs", 0),
        max_replans=kwargs.pop("max_replans", 0),
        run_id=run_id,
        config=_config(tmp_path),
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        run_stage_fn=stage,
        **kwargs,
    )


def _substrate(port: Any = None, *, project_names: tuple[str, ...] = ("demo-project",)) -> AcquisitionSubstrate:
    return AcquisitionSubstrate(port=port or _port(), project_names=project_names)


def _record(run_id: str) -> dict[str, Any]:
    path = workflow_artifact_paths(run_id).admission
    assert path.exists(), f"no admission record for {run_id}"
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


# ── C1: the admitted lifecycle ───────────────────────────────────────────────


@pytest.mark.parametrize("mode", ["linear", "adaptive"])
def test_a_selection_admits_the_coder_against_the_selected_plan(tmp_path: Path, mode: str) -> None:
    """The S5P1 target behaviour, end to end through the real controller."""
    stage = _PlannerThen(SELECTION, forbid_after_planner=False)
    run_id = f"acq-ok-{mode}"
    code, state = _run(
        tmp_path,
        run_id=run_id,
        stage=stage,
        roles=["planner", "coder"],
        mode=mode,
        acquisition=_substrate(),
    )

    assert "coder" in stage.roles, "the coder never ran, so nothing was admitted"
    assert state is not None
    # The plan is the one the planner selected, not one the caller supplied.
    record = _record(run_id)
    assert record["plan_ref"] is not None
    assert record["plan_ref"]["source_kind"] == "EXISTING_SELECTION"
    assert record["plan_ref"]["workspace_relative_path"].endswith("increment-01-foundation.md")
    # Not asserted as 0: the injected stage writes no tests, so the verify gate
    # blocks the run afterwards. That is the gate doing its job, not this step's
    # subject -- what matters here is that the coder ran against an admitted plan.
    assert code != 2 or state.blocked_reason.startswith("plan-ref/") is False


@pytest.mark.parametrize("mode", ["linear", "adaptive"])
def test_the_selected_plan_reaches_the_coder_stage(tmp_path: Path, mode: str) -> None:
    """The coder runs against a plan path the caller never passed."""
    seen: list[str] = []

    class _Recorder(_PlannerThen):
        def __call__(self, args: argparse.Namespace, **kwargs: Any) -> int:
            # The stage boundary carries the plan as `_managed_plan_ref`, not as a
            # host `plan_path`: a coder stage is handed an identity, never a path it
            # could be asked to read outside the pinned view.
            ref = getattr(args, "_managed_plan_ref", None)
            if getattr(args, "role", "") == "coder":
                seen.append("" if ref is None else ref.workspace_relative_path)
            return super().__call__(args, **kwargs)

    _run(
        tmp_path,
        run_id=f"acq-plan-path-{mode}",
        stage=_Recorder(SELECTION, forbid_after_planner=False),
        roles=["planner", "coder"],
        mode=mode,
        acquisition=_substrate(),
    )

    assert seen and seen[0].endswith("increment-01-foundation.md"), seen


# ── C0: every other outcome refuses before the coder ────────────────────────


@pytest.mark.parametrize("mode", ["linear", "adaptive"])
def test_a_clarification_stops_the_run_before_the_coder(tmp_path: Path, mode: str) -> None:
    stage = _PlannerThen(CLARIFICATION, forbid_after_planner=True)
    code, state = _run(
        tmp_path,
        run_id=f"acq-clarify-{mode}",
        stage=stage,
        roles=["planner", "coder"],
        mode=mode,
        acquisition=_substrate(),
    )

    assert code != 0
    assert "coder" not in stage.roles
    assert "eval" not in stage.roles
    assert state is not None and "clarification" in state.blocked_reason


@pytest.mark.parametrize("mode", ["linear", "adaptive"])
def test_a_bootstrap_request_without_a_managed_authority_stops_before_the_coder(tmp_path: Path, mode: str) -> None:
    """Bootstrap needs the authority: rendering and installing are its operations.

    `_substrate()` is a port only, so this run has no `managed_execution` and there is
    nothing that could install a project. The refusal must name that, and must happen
    before the coder — a coder admitted here would be coding against prose the
    workspace never received.
    """
    stage = _PlannerThen(BOOTSTRAP, forbid_after_planner=True)
    code, state = _run(
        tmp_path,
        run_id=f"acq-bootstrap-{mode}",
        stage=stage,
        roles=["planner", "coder"],
        mode=mode,
        acquisition=_substrate(),
    )

    assert code == 2
    assert "coder" not in stage.roles
    assert "eval" not in stage.roles
    assert state is not None and state.blocked_reason == "plan-ref/bootstrap-unavailable"


@pytest.mark.parametrize("mode", ["linear", "adaptive"])
def test_an_unparseable_choice_stops_the_run_before_the_coder(tmp_path: Path, mode: str) -> None:
    stage = _PlannerThen("I will now write a plan.", forbid_after_planner=True)
    code, _state = _run(
        tmp_path,
        run_id=f"acq-garbage-{mode}",
        stage=stage,
        roles=["planner", "coder"],
        mode=mode,
        acquisition=_substrate(),
    )

    assert code == 2
    assert "coder" not in stage.roles
    assert "eval" not in stage.roles


def test_adaptive_repair_round_preserves_the_acquired_plan_and_never_reacquires(tmp_path: Path) -> None:
    """D6 + shared-loop C1: adaptive keeps the bound admission across repair rounds.

    Proves two invariants across the shared stage loop:
      * the initial loop returns the updated `WorkflowContext` back into `_run_adaptive`,
        so both the initial coder and the repair-round coder receive the acquired
        `_managed_plan_ref`;
      * the planner runs only once (no spurious re-acquisition during repair).
    """
    coder_refs: list[PlanRef | None] = []
    eval_verdicts = iter(
        [
            (
                "## Verification Summary\n\n### Step results\n- SLICE1: FAIL\n\n"
                "### Verdict\nREPAIR_REQUIRED\n\n### Route decision\nreturn_to_coder\n"
            ),
            (
                "## Verification Summary\n\n### Step results\n- SLICE1: PASS\n\n"
                "### Verdict\nPASS\n\n### Route decision\ncomplete\n"
            ),
        ]
    )

    class _AdaptiveStage:
        def __init__(self) -> None:
            self.roles: list[str] = []

        def __call__(self, args: argparse.Namespace, **kwargs: Any) -> int:
            role = str(getattr(args, "role", "?"))
            self.roles.append(role)
            sink = kwargs.get("outcome_sink")
            if role == "planner":
                assert len(self.roles) == 1, "repair round must not re-run acquisition planner"
                if isinstance(sink, list):
                    sink.append(
                        SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text=SELECTION)
                    )
                return 0
            if role == "coder":
                coder_refs.append(getattr(args, "_managed_plan_ref", None))
                return 0
            if role == "eval":
                if isinstance(sink, list):
                    sink.append(
                        SessionOutcome(
                            exit_code=0,
                            stop_reason="stopped_by_llm",
                            turns=1,
                            final_text=next(eval_verdicts),
                        )
                    )
                return 0
            return 0

    stage = _AdaptiveStage()
    code, state = _run(
        tmp_path,
        run_id="acq-adaptive-repair",
        stage=stage,
        roles=["planner", "coder", "eval"],
        mode="adaptive",
        max_repairs=1,
        acquisition=_substrate(),
    )

    assert code == 0
    assert state is not None and state.status == "DONE"
    assert state.repair_round == 1
    assert stage.roles == ["planner", "coder", "eval", "coder", "eval"]
    assert len(coder_refs) == 2
    assert all(ref is not None and ref.source_kind == "EXISTING_SELECTION" for ref in coder_refs), coder_refs
    assert coder_refs[0] == coder_refs[1]
    record = _record("acq-adaptive-repair")
    assert record["status"] == "ADMITTED"
    assert record["plan_ref"]["source_kind"] == "EXISTING_SELECTION"


def test_eval_replan_after_selection_is_not_misread_as_a_second_acquisition(tmp_path: Path) -> None:
    """§7.0 choice consumed once: subsequent EVAL_REPLAN planner writes prose, not JSON.

    If `ctx.acquisition` stayed active across admission binding, the scoped replan
    planner stage would fail with `choice-malformed` in `_stage_acquisition_choice`.
    """
    slug = "planning-topology-and-executable-contracts-loop"
    files = render_bundle(
        slug,
        "foundation",
        "## Intent\n\nA project.\n\n## Out of scope\n\nOther work.\n",
        (
            "## SLICE1: Foundation\n"
            "CONTRACTS:\n"
            "  CT1 [CONSTRAINT]: initial.\n"
            "TESTS: tests/test_s5p1_acquisition_lifecycle.py\n"
        ),
        created="2026-11-02",
    )
    listing = PortProjectArtifactListing(
        "directory",
        "file",
        "directory",
        (PortDirectoryEntry("increment-01-foundation.md", "file"),),
    )
    port = _Port(files, listing=listing)
    selection = json.dumps({"kind": "SELECT_EXISTING", "project_slug": slug, "increment_id": "I01"})
    revised_body = (
        files[f"worklogs/{slug}/increments/increment-01-foundation.md"]
        .decode("utf-8")
        .replace("initial.", "revised after eval.")
    )

    class _Publisher:
        def publish_candidate(
            self, source: PlanSnapshot, candidate: PlanSnapshot, *, deadline: float | None = None
        ) -> PlanRef:
            return PlanRef(
                source.ref.workspace_relative_path,
                source.ref.source_kind,
                candidate.ref.sha256,
            )

    coder_refs: list[PlanRef | None] = []
    dispatches: list[PlannerDispatchKind] = []
    eval_verdicts = iter(
        [
            (
                "## Verification Summary\n\n### Step results\n- SLICE1: FAIL\n\n"
                "### Verdict\nREPLAN_REQUIRED\n\n### Route decision\nreturn_to_planner\n"
            ),
            (
                "## Verification Summary\n\n### Step results\n- SLICE1: PASS\n\n"
                "### Verdict\nPASS\n\n### Route decision\ncomplete\n"
            ),
        ]
    )

    class _ReplanStage:
        def __init__(self) -> None:
            self.roles: list[str] = []

        def __call__(self, args: argparse.Namespace, **kwargs: Any) -> int:
            role = str(getattr(args, "role", "?"))
            self.roles.append(role)
            sink = kwargs.get("outcome_sink")
            if role == "planner":
                dispatch: PlannerDispatch | None = kwargs.get("planner_dispatch")
                assert dispatch is not None
                dispatches.append(dispatch.kind)
                if dispatch.kind == PlannerDispatchKind.EVAL_REPLAN:
                    assert dispatch.candidate_target is not None
                    target = tmp_path / dispatch.candidate_target
                    target.write_text(revised_body, encoding="utf-8")
                    if isinstance(sink, list):
                        sink.append(
                            SessionOutcome(
                                exit_code=0,
                                stop_reason="stopped_by_llm",
                                turns=1,
                                final_text="Revised the candidate increment after eval.",
                            )
                        )
                    return 0
                if isinstance(sink, list):
                    sink.append(
                        SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text=selection)
                    )
                return 0
            if role == "coder":
                coder_refs.append(getattr(args, "_managed_plan_ref", None))
                return 0
            if role == "eval":
                if isinstance(sink, list):
                    sink.append(
                        SessionOutcome(
                            exit_code=0,
                            stop_reason="stopped_by_llm",
                            turns=1,
                            final_text=next(eval_verdicts),
                        )
                    )
                return 0
            return 0

    stage = _ReplanStage()
    code, state = _run(
        tmp_path,
        run_id="acq-eval-replan",
        stage=stage,
        roles=["planner", "coder", "eval"],
        mode="adaptive",
        max_replans=1,
        acquisition=_substrate(port, project_names=(slug,)),
        plan_publisher=_Publisher(),
    )

    assert code == 0
    assert state is not None and state.status == "DONE"
    assert state.replan_round == 1
    assert stage.roles == ["planner", "coder", "eval", "planner", "coder", "eval"]
    assert dispatches[-1] == PlannerDispatchKind.EVAL_REPLAN
    assert len(coder_refs) == 2
    assert coder_refs[0] is not None and coder_refs[1] is not None
    assert coder_refs[0].sha256 != coder_refs[1].sha256
    assert coder_refs[1].source_kind == "EXISTING_SELECTION"
    record = _record("acq-eval-replan")
    assert [attempt["dispatch_kind"] for attempt in record["attempts"]] == ["EXPLICIT_INPUT", "EVAL_REPLAN"]


@pytest.mark.parametrize("mode", ["linear", "adaptive"])
def test_q57_admission_repair_after_selection_runs_in_both_modes_without_reacquiring(tmp_path: Path, mode: str) -> None:
    """Q57 + D6: pre-coder admission repair works identically after acquisition in both modes."""
    slug = "planning-topology-and-executable-contracts-loop"
    files = render_bundle(
        slug,
        "foundation",
        "## Intent\n\nA project.\n\n## Out of scope\n\nOther work.\n",
        "## SLICE1: Foundation\nCONTRACTS:\n  CT1 [CONSTRAINT]: initial.\n",
        created="2026-11-02",
    )
    listing = PortProjectArtifactListing(
        "directory",
        "file",
        "directory",
        (PortDirectoryEntry("increment-01-foundation.md", "file"),),
    )
    port = _Port(files, listing=listing)
    selection = json.dumps({"kind": "SELECT_EXISTING", "project_slug": slug, "increment_id": "I01"})
    repaired_body = (
        files[f"worklogs/{slug}/increments/increment-01-foundation.md"].decode("utf-8")
        + "TESTS: tests/test_s5p1_acquisition_lifecycle.py\n"
    )

    class _Publisher:
        def publish_candidate(
            self, source: PlanSnapshot, candidate: PlanSnapshot, *, deadline: float | None = None
        ) -> PlanRef:
            return PlanRef(
                source.ref.workspace_relative_path,
                source.ref.source_kind,
                candidate.ref.sha256,
            )

    coder_refs: list[PlanRef | None] = []
    dispatches: list[PlannerDispatchKind] = []

    class _AdmissionRepairStage:
        def __init__(self) -> None:
            self.roles: list[str] = []

        def __call__(self, args: argparse.Namespace, **kwargs: Any) -> int:
            role = str(getattr(args, "role", "?"))
            self.roles.append(role)
            sink = kwargs.get("outcome_sink")
            if role == "planner":
                dispatch: PlannerDispatch | None = kwargs.get("planner_dispatch")
                assert dispatch is not None
                dispatches.append(dispatch.kind)
                if dispatch.kind == PlannerDispatchKind.ADMISSION_REPAIR:
                    assert dispatch.candidate_target is not None
                    (tmp_path / dispatch.candidate_target).write_text(repaired_body, encoding="utf-8")
                    if isinstance(sink, list):
                        sink.append(
                            SessionOutcome(
                                exit_code=0,
                                stop_reason="stopped_by_llm",
                                turns=1,
                                final_text="Added missing TESTS line to candidate increment.",
                            )
                        )
                    return 0
                if isinstance(sink, list):
                    sink.append(
                        SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text=selection)
                    )
                return 0
            if role == "coder":
                coder_refs.append(getattr(args, "_managed_plan_ref", None))
                return 0
            if role == "eval":
                if isinstance(sink, list):
                    sink.append(
                        SessionOutcome(
                            exit_code=0,
                            stop_reason="stopped_by_llm",
                            turns=1,
                            final_text=(
                                "## Verification Summary\n\n### Step results\n- SLICE1: PASS\n\n"
                                "### Verdict\nPASS\n\n### Route decision\ncomplete\n"
                            ),
                        )
                    )
                return 0
            return 0

    run_id = f"acq-admission-repair-{mode}"
    stage = _AdmissionRepairStage()
    code, state = _run(
        tmp_path,
        run_id=run_id,
        stage=stage,
        roles=["planner", "coder", "eval"],
        mode=mode,
        max_replans=1,
        acquisition=_substrate(port, project_names=(slug,)),
        plan_publisher=_Publisher(),
    )

    assert code == 0
    assert state is not None and state.status == "DONE"
    assert state.replan_round == 1
    assert stage.roles == ["planner", "planner", "coder", "eval"]
    assert dispatches[-1] == PlannerDispatchKind.ADMISSION_REPAIR
    assert len(coder_refs) == 1 and coder_refs[0] is not None
    assert coder_refs[0].source_kind == "EXISTING_SELECTION"
    record = _record(run_id)
    assert [attempt["dispatch_kind"] for attempt in record["attempts"]] == ["EXPLICIT_INPUT", "ADMISSION_REPAIR"]
    assert [attempt["route"] for attempt in record["attempts"]] == ["RETRY", "ADMITTED"]


def test_a_coder_with_no_plan_and_no_substrate_is_still_refused(tmp_path: Path) -> None:
    """No weakening by adjacency: the plain refusal is unchanged."""
    stage = _PlannerThen(SELECTION, forbid_after_planner=True)
    code, state = _run(tmp_path, run_id="acq-none", stage=stage, roles=["coder"])

    assert code == 2
    assert stage.roles == []
    assert state is not None and state.blocked_reason == "plan-ref/missing"


def test_an_acquisition_substrate_cannot_admit_a_coder_without_a_lead_planner(tmp_path: Path) -> None:
    """An acquired plan needs an owner: the planner must run first.

    Without this refusal, `roles=["coder"]` plus a substrate would bypass the plan
    check entirely — the run would have an admission with nobody who produced it.
    """
    stage = _PlannerThen(SELECTION, forbid_after_planner=True)
    code, state = _run(tmp_path, run_id="acq-no-planner", stage=stage, roles=["coder"], acquisition=_substrate())

    assert code == 2
    assert stage.roles == [], "no role may run when the acquisition shape is invalid"
    assert state is not None and state.blocked_reason == "plan-ref/admission-without-planner"
