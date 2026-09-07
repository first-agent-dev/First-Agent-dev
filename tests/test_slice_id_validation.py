"""S12 + Q16 — the harness checks the evaluator's slice claims against the plan.

**Three defects this closes**, all probed at the tip before the fix:

1. ``_STEP_LINE_RE`` accepts any ``S<digits>`` token, so ``- S404: PASS``
   parsed as a real slice and counted toward apparent coverage.
2. Nothing noticed **omission**. Dropping ``S7`` from the eval's list produced
   a clean ``PASS`` over work nobody examined. This is the one that matters:
   invention is cosmetic, omission is silent.
3. ``step_results`` was inert (§19 F1). A run could terminate ``DONE`` while
   carrying ``S7: FAIL``. **Q16** makes a per-slice ``fail`` route to
   ``REPAIR_REQUIRED``.

**Why the adjuster is pure.** ``validate_slice_ids`` neither logs nor writes,
so the decision is testable without booting a workflow, and the caller keeps a
single write of ``eval_report.json`` (§24 D-1: ``build -> adjust -> write``,
never ``emit -> rewrite``). A second write would leave a window in which the
persisted artifact contradicts the routing decision.

Classes: **C0** for the adjuster, **C1** for the composition root (real
``run_workflow``, only the stage dispatcher injected).

Kill-check target: the ``validate_slice_ids`` call in ``_run_stage``'s eval
branch. Removing it fails ``test_invented_slice_id_is_dropped`` and
``test_per_slice_failure_forces_repair``.
"""

from __future__ import annotations

from fa.inner_loop.workflow_artifacts import parse_eval_report
from fa.inner_loop.workflow_controller import validate_slice_ids

_PLAN = """# PLAN: worked example    Plan-ID: PLAN-example

### Step S1: first
### Step S5: second
### Step S5a: third
"""


def _report(final_text: str):  # type: ignore[no-untyped-def]
    return parse_eval_report(final_text, run_id="r", plan_id="p", evaluation_id="e")


# ── C0: invention ──────────────────────────────────────────────────────────


def test_invented_slice_id_is_dropped() -> None:
    """T16 (KILL-CHECK) — an ID absent from the plan is noise, not evidence."""
    report = _report("### Verdict\nPASS\n### Step results\n- S1: PASS - ok\n- S404: PASS - invented\n")
    adjusted, warnings = validate_slice_ids(report, _PLAN)

    assert [step.step_id for step in adjusted.step_results] == ["S1"]
    assert any("S404" in w for w in warnings)
    assert not any("S1" in w and "absent" in w for w in warnings)


# ── C0: omission (the one that matters) ────────────────────────────────────


def test_omitted_plan_slices_are_recorded() -> None:
    """T16b — a slice the evaluator never mentioned must not vanish silently."""
    report = _report("### Verdict\nPASS\n### Step results\n- S1: PASS - ok\n")
    adjusted, warnings = validate_slice_ids(report, _PLAN)

    assert adjusted.unreported_slices == ("S5", "S5a")
    assert any("no eval verdict" in w for w in warnings)


def test_full_coverage_produces_no_warnings() -> None:
    """T16b (negative) — a complete report must stay silent, or the signal is noise."""
    report = _report("### Verdict\nPASS\n### Step results\n- S1: PASS - a\n- S5: PASS - b\n- S5a: PASS - c\n")
    adjusted, warnings = validate_slice_ids(report, _PLAN)

    assert adjusted.unreported_slices == ()
    assert warnings == ()


# ── C0: exact matching ─────────────────────────────────────────────────────


def test_s5_and_s5a_are_never_conflated() -> None:
    """T16d — suffixed slices are distinct in BOTH directions.

    Normalising case or stripping the suffix would report a real omission as
    covered, which is precisely the failure this step exists to prevent.
    """
    report = _report("### Verdict\nPASS\n### Step results\n- S5a: PASS - only the suffixed one\n")
    adjusted, _ = validate_slice_ids(report, _PLAN)

    assert adjusted.unreported_slices == ("S1", "S5"), "S5a must not satisfy S5"
    assert [step.step_id for step in adjusted.step_results] == ["S5a"]


# ── C0: degradation ────────────────────────────────────────────────────────


def test_absent_plan_is_a_no_op() -> None:
    """T16c — no plan means no contract to check; never manufacture warnings."""
    report = _report("### Verdict\nPASS\n### Step results\n- S404: PASS - x\n")
    adjusted, warnings = validate_slice_ids(report, None)

    assert adjusted.step_results == report.step_results, "nothing may be dropped without a plan"
    assert adjusted.unreported_slices == ()
    assert warnings == ()


def test_plan_declaring_no_slices_is_a_no_op() -> None:
    """T16c — an unparseable/legacy plan must not flag every claim as invented.

    Legacy plans failing extraction is expected and is not a kill signal.
    """
    report = _report("### Verdict\nPASS\n### Step results\n- S1: PASS - x\n")
    adjusted, warnings = validate_slice_ids(report, "# a plan with prose but no step headings\n")

    assert [step.step_id for step in adjusted.step_results] == ["S1"]
    assert warnings == ()


# ── C0: Q16 routing ────────────────────────────────────────────────────────


def test_per_slice_failure_forces_repair() -> None:
    """Q16 (KILL-CHECK) — PASS cannot coexist with a reported per-slice failure."""
    report = _report("### Verdict\nPASS\n### Step results\n- S1: FAIL - broken\n")
    assert report.verdict == "PASS", "precondition: the parser accepts the model's PASS"

    adjusted, warnings = validate_slice_ids(report, _PLAN)

    assert adjusted.verdict == "REPAIR_REQUIRED"
    assert adjusted.route_decision == "return_to_coder"
    assert "S1" in adjusted.summary
    assert any("Q16" in w for w in warnings)


def test_partial_does_not_force_repair() -> None:
    """Q16 scope — only a literal ``fail`` blocks.

    ``StepVerdict`` also allows ``partial`` and ``not_evaluated``; neither
    asserts the slice is broken, and routing on them would turn "the evaluator
    was unsure" into a hard repair loop.
    """
    for token in ("PARTIAL", "NOT_EVALUATED"):
        report = _report(f"### Verdict\nPASS\n### Step results\n- S1: {token} - unsure\n")
        adjusted, _ = validate_slice_ids(report, _PLAN)
        assert adjusted.verdict == "PASS", f"{token} must not force a repair"


def test_q16_never_upgrades_a_non_pass_verdict() -> None:
    """Q16 invariant — the adjuster may only ever be MORE conservative.

    A BLOCKED run carrying a failure stays BLOCKED; rewriting it to
    REPAIR_REQUIRED would discard the evaluator's stronger signal.
    """
    for verdict in ("BLOCKED", "REPLAN_REQUIRED"):
        report = _report(f"### Verdict\n{verdict}\n### Step results\n- S1: FAIL - x\n")
        adjusted, _ = validate_slice_ids(report, _PLAN)
        assert adjusted.verdict == verdict


def test_q16_applies_without_a_plan() -> None:
    """Q16 is independent of plan availability.

    A reported failure is a fact about the work; whether the harness can see
    the contract does not change it.
    """
    report = _report("### Verdict\nPASS\n### Step results\n- S1: FAIL - broken\n")
    adjusted, warnings = validate_slice_ids(report, None)

    assert adjusted.verdict == "REPAIR_REQUIRED"
    assert any("Q16" in w for w in warnings)


# ── C0: schema ─────────────────────────────────────────────────────────────


def test_unreported_slices_round_trips_and_defaults() -> None:
    """The new field must survive JSON and must not break pre-S12 artifacts."""
    from fa.inner_loop.workflow_artifacts import EvalReport

    report = _report("### Verdict\nPASS\n### Step results\n- S1: PASS - ok\n")
    adjusted, _ = validate_slice_ids(report, _PLAN)
    payload = adjusted.to_json_dict()

    assert payload["unreported_slices"] == ["S5", "S5a"]
    assert EvalReport.from_json_dict(payload).unreported_slices == ("S5", "S5a")

    legacy = {k: v for k, v in payload.items() if k != "unreported_slices"}
    assert EvalReport.from_json_dict(legacy).unreported_slices == (), (
        "a pre-S12 artifact has no such key and must default to empty"
    )


# ── C1: the live path ──────────────────────────────────────────────────────


def test_live_workflow_persists_the_adjusted_report(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """C1 (live-path proof) — the adjustment reaches ``eval_report.json``.

    A C0 test of the pure function proves only the decision. This boots the
    real ``run_workflow`` with a stage that returns a genuine ``SessionOutcome``
    and asserts on the PERSISTED artifact -- the same file the repair loop and
    the operator read.

    It also pins §24 D-1: the report is written ONCE, already adjusted. If the
    wiring reverted to ``emit -> rewrite`` the file would briefly hold the
    unadjusted verdict, and any reader racing that window would route wrong.
    """
    import argparse
    import json
    from pathlib import Path
    from typing import Any

    from fa.inner_loop.coder_loop import SessionOutcome
    from fa.inner_loop.workflow_controller import run_workflow, workflow_artifact_paths

    plan = tmp_path / "PLAN.md"
    plan.write_text(_PLAN, encoding="utf-8")
    config = tmp_path / "models.yaml"
    config.write_text("providers: {}\n", encoding="utf-8")

    def stage(args: argparse.Namespace, **kwargs: Any) -> int:
        sink = kwargs.get("outcome_sink")
        if getattr(args, "role", "") == "eval" and sink is not None:
            sink.append(
                SessionOutcome(
                    exit_code=0,
                    stop_reason="stopped_by_llm",
                    turns=1,
                    final_text=("### Verdict\nPASS\n### Step results\n- S1: PASS - ok\n- S404: PASS - invented\n"),
                )
            )
        return 0

    run_id = "s12-live"
    exit_code, state = run_workflow(
        roles=["coder", "eval"],
        task="t",
        per_role_task={},
        mode="linear",
        max_repairs=0,
        max_replans=0,
        run_id=run_id,
        config=config,
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        run_stage_fn=stage,
        plan_path=plan,
    )

    payload = json.loads(Path(workflow_artifact_paths(run_id).eval_report).read_text(encoding="utf-8"))
    assert [s["step_id"] for s in payload["step_results"]] == ["S1"], "S404 must not reach disk"
    assert payload["unreported_slices"] == ["S5", "S5a"]
    assert state is not None and exit_code == 0
