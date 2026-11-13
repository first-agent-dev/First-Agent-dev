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

from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.workflow_controller import (
    AcquisitionSubstrate,
    run_workflow,
    workflow_artifact_paths,
)

from .test_plan_reference import _config
from .test_s5p1_acquisition_resolution import _port

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


def _run(tmp_path: Path, *, run_id: str, stage: Any, roles: list[str], **kwargs: Any) -> tuple[int, Any]:
    return run_workflow(
        roles=roles,
        task="do the thing",
        per_role_task={},
        mode="linear",
        max_repairs=0,
        max_replans=0,
        run_id=run_id,
        config=_config(tmp_path),
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        run_stage_fn=stage,
        **kwargs,
    )


def _substrate(port: Any = None) -> AcquisitionSubstrate:
    return AcquisitionSubstrate(port=port or _port(), project_names=("demo-project",))


def _record(run_id: str) -> dict[str, Any]:
    path = workflow_artifact_paths(run_id).admission
    assert path.exists(), f"no admission record for {run_id}"
    return json.loads(path.read_text(encoding="utf-8"))


# ── C1: the admitted lifecycle ───────────────────────────────────────────────


def test_a_selection_admits_the_coder_against_the_selected_plan(tmp_path: Path) -> None:
    """The S5P1 target behaviour, end to end through the real controller."""
    stage = _PlannerThen(SELECTION, forbid_after_planner=False)
    code, state = _run(
        tmp_path,
        run_id="acq-ok",
        stage=stage,
        roles=["planner", "coder"],
        acquisition=_substrate(),
    )

    assert "coder" in stage.roles, "the coder never ran, so nothing was admitted"
    assert state is not None
    # The plan is the one the planner selected, not one the caller supplied.
    record = _record("acq-ok")
    assert record["plan_ref"] is not None
    assert record["plan_ref"]["source_kind"] == "EXISTING_SELECTION"
    assert record["plan_ref"]["workspace_relative_path"].endswith("increment-01-foundation.md")
    # Not asserted as 0: the injected stage writes no tests, so the verify gate
    # blocks the run afterwards. That is the gate doing its job, not this step's
    # subject -- what matters here is that the coder ran against an admitted plan.
    assert code != 2 or state.blocked_reason.startswith("plan-ref/") is False


def test_the_selected_plan_reaches_the_coder_stage(tmp_path: Path) -> None:
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
        run_id="acq-plan-path",
        stage=_Recorder(SELECTION, forbid_after_planner=False),
        roles=["planner", "coder"],
        acquisition=_substrate(),
    )

    assert seen and seen[0].endswith("increment-01-foundation.md"), seen


# ── C0: every other outcome refuses before the coder ────────────────────────


def test_a_clarification_stops_the_run_before_the_coder(tmp_path: Path) -> None:
    stage = _PlannerThen(CLARIFICATION, forbid_after_planner=True)
    code, state = _run(
        tmp_path, run_id="acq-clarify", stage=stage, roles=["planner", "coder"], acquisition=_substrate()
    )

    assert code != 0
    assert "coder" not in stage.roles
    assert state is not None and "clarification" in state.blocked_reason


def test_a_bootstrap_request_stops_the_run_before_the_coder(tmp_path: Path) -> None:
    stage = _PlannerThen(BOOTSTRAP, forbid_after_planner=True)
    code, _state = _run(
        tmp_path, run_id="acq-bootstrap", stage=stage, roles=["planner", "coder"], acquisition=_substrate()
    )

    assert code != 0
    assert "coder" not in stage.roles
    record = _record("acq-bootstrap")
    assert record["status"] == "BLOCKED"


def test_an_unparseable_choice_stops_the_run_before_the_coder(tmp_path: Path) -> None:
    stage = _PlannerThen("I will now write a plan.", forbid_after_planner=True)
    code, _state = _run(
        tmp_path, run_id="acq-garbage", stage=stage, roles=["planner", "coder"], acquisition=_substrate()
    )

    assert code == 2
    assert "coder" not in stage.roles


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
