from __future__ import annotations

import json
from pathlib import Path

import pytest

from fa.inner_loop.workflow_artifacts import (
    EvalFinding,
    EvalReport,
    FlowState,
    StepResult,
    default_route_for_verdict,
    load_eval_report,
    load_flow_state,
    parse_eval_report,
    write_eval_report,
    write_flow_state,
)

_EVAL_OUTPUT_REPAIR = """## Verification Summary

### Step results
- S1: PASS — predicate matched in src/fa/x.py
- S2: FAIL — pytest exited 1

### Integration checks
- Focused: FAIL — pytest tests/test_x.py → 1 failed
- Regression: PASS — just check → ok

### Blocking findings
- F-1: missing branch in src/fa/x.py:42

### Non-blocking observations
- none

### Verdict
REPAIR_REQUIRED

### Route decision
return_to_coder
"""

_EVAL_OUTPUT_PASS = """## Verification Summary

### Step results
- S1: PASS — landed as specified

### Verdict
PASS

### Route decision
complete
"""


def test_eval_report_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "eval_report.json"
    report = EvalReport(
        run_id="run-1",
        plan_id="plan-a",
        plan_version=2,
        evaluation_id="eval-1",
        verdict="REPAIR_REQUIRED",
        route_decision="return_to_coder",
        summary="step S2 failed focused verification",
        step_results=(
            StepResult(
                step_id="S1",
                verdict="pass",
                acceptance_matched=True,
                evidence="predicate matched",
            ),
            StepResult(
                step_id="S2",
                verdict="fail",
                acceptance_matched=False,
                evidence="pytest exited 1",
                notes="missing edge case",
            ),
        ),
        findings=(
            EvalFinding(
                finding_id="F-1",
                severity="major",
                finding_class="implementation",
                blocking=True,
                route="coder",
                step_id="S2",
                location="src/fa/x.py:42",
                claim="missing branch",
                evidence="pytest failure in tests/test_x.py",
                expected="test passes",
                actual="IndexError raised",
                required_action="handle empty input",
                suggested_check="python -m pytest tests/test_x.py -k empty -q",
            ),
        ),
        integration_checks=("focused: fail",),
        regression_checks=("regression: not run",),
        confidence="high",
    )

    write_eval_report(path, report)
    loaded = load_eval_report(path)

    assert loaded == report


def test_flow_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "flow_state.json"
    state = FlowState(
        run_id="run-1",
        task="implement feature X",
        status="REPAIR_REQUIRED",
        active_role="coder",
        active_plan_id="plan-a",
        active_plan_version=2,
        repair_round=1,
        replan_round=0,
        last_actor="eval",
        last_transition_reason="blocking implementation finding",
        last_route_decision="return_to_coder",
        blocked_reason="",
        completed_steps=("S1",),
        invalidated_steps=(),
    )

    write_flow_state(path, state)
    loaded = load_flow_state(path)

    assert loaded == state


def test_atomic_json_writer_overwrites_cleanly(tmp_path: Path) -> None:
    path = tmp_path / "flow_state.json"
    first = FlowState(
        run_id="run-1",
        task="task",
        status="PLANNING",
        active_role="planner",
        active_plan_id="plan-a",
        active_plan_version=1,
    )
    second = FlowState(
        run_id="run-1",
        task="task",
        status="EVALUATING",
        active_role="eval",
        active_plan_id="plan-a",
        active_plan_version=2,
        repair_round=1,
        last_actor="coder",
        last_transition_reason="coding round finished",
    )

    write_flow_state(path, first)
    write_flow_state(path, second)

    loaded = load_flow_state(path)
    assert loaded == second
    assert "EVALUATING" in path.read_text(encoding="utf-8")


# ── parse_eval_report (deterministic eval-output translation) ───────────────


def test_default_route_for_verdict_matches_documented_mapping() -> None:
    assert default_route_for_verdict("PASS") == "complete"
    assert default_route_for_verdict("REPAIR_REQUIRED") == "return_to_coder"
    assert default_route_for_verdict("REPLAN_REQUIRED") == "return_to_planner"
    assert default_route_for_verdict("BLOCKED") == "blocked"


def test_parse_eval_report_extracts_verdict_route_and_steps() -> None:
    report = parse_eval_report(
        _EVAL_OUTPUT_REPAIR,
        run_id="wf-1",
        plan_id="wf-1",
        evaluation_id="wf-1-eval",
    )
    assert report.verdict == "REPAIR_REQUIRED"
    assert report.route_decision == "return_to_coder"
    assert report.confidence == "parsed:contract"
    by_id = {s.step_id: s for s in report.step_results}
    assert by_id["S1"].verdict == "pass"
    assert by_id["S1"].acceptance_matched is True
    assert by_id["S2"].verdict == "fail"
    assert by_id["S2"].acceptance_matched is False


def test_parse_eval_report_pass_routes_to_complete() -> None:
    report = parse_eval_report(_EVAL_OUTPUT_PASS, run_id="r", plan_id="r", evaluation_id="r-eval")
    assert report.verdict == "PASS"
    assert report.route_decision == "complete"


def test_parse_eval_report_is_fail_closed_on_missing_verdict() -> None:
    report = parse_eval_report(
        "no recognizable verdict here", run_id="r", plan_id="r", evaluation_id="r-eval"
    )
    assert report.verdict == "BLOCKED"
    assert report.route_decision == "blocked"
    assert report.confidence == "parsed:none"


def test_parse_eval_report_verdict_overrides_contradictory_route() -> None:
    # Route is a routing consequence of the verdict; a route that contradicts
    # the verdict is overridden by the verdict-derived default (fail-safe).
    text = "### Verdict\nPASS\n### Route decision\nreturn_to_coder\n"
    report = parse_eval_report(text, run_id="r", plan_id="r", evaluation_id="r-eval")
    assert report.verdict == "PASS"
    assert report.route_decision == "complete"


def test_parse_eval_report_round_trips_through_persistence(tmp_path: Path) -> None:
    report = parse_eval_report(
        _EVAL_OUTPUT_REPAIR, run_id="wf-1", plan_id="wf-1", evaluation_id="wf-1-eval"
    )
    path = tmp_path / "eval_report.json"
    write_eval_report(path, report)
    assert load_eval_report(path) == report


# ── boundary validation on load (fail-closed JSON parsing) ──────────────────


def test_load_eval_report_rejects_unknown_verdict(tmp_path: Path) -> None:
    path = tmp_path / "eval_report.json"
    payload = {
        "run_id": "r",
        "plan_id": "p",
        "plan_version": 1,
        "evaluation_id": "e",
        "verdict": "TOTALLY_BOGUS",
        "route_decision": "complete",
        "summary": "x",
        "step_results": [],
        "findings": [],
        "integration_checks": [],
        "regression_checks": [],
        "confidence": "",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="verdict"):
        load_eval_report(path)


def test_load_flow_state_rejects_non_integer_plan_version(tmp_path: Path) -> None:
    path = tmp_path / "flow_state.json"
    payload = {
        "run_id": "r",
        "task": "t",
        "status": "PLANNING",
        "active_role": "planner",
        "active_plan_id": "p",
        "active_plan_version": "not-an-int",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="integer"):
        load_flow_state(path)
