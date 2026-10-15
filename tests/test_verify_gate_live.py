"""SLICE6 live proof: the workflow gate is reached through the production session path.

Test class: C1 for ``run_workflow`` -> ``_cmd_run`` -> ``drive_session``. The
only provider seam replaced in the live test is ``ProviderChain.request``; the
transport and stage dispatcher are real. The artifact and eval request are the
observable oracle, not a fake stage result.

Producer kill-check: remove-call
``src/fa/inner_loop/workflow_controller.py::_run_stage -> verify_plan``.
The live assertion that ``verification.json`` contains both slices then fails.
The module is also the plan's declared TESTS path, so the kill runner exercises
the same live oracle while keeping nested gate-owned pytest runs bounded by the
private depth marker.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from fa.feature_flags import FAIL_OPEN_FLAGS, FeatureFlags
from fa.inner_loop import workflow_controller as workflow
from fa.inner_loop.plan_ids import extract_plan_ids
from fa.inner_loop.slice_verification import (
    CommandOutcome,
    CommandResult,
    PlanVerification,
    _gate_mode,
)
from fa.inner_loop.workflow_artifacts import EvalReport, EvalVerdict, RouteDecision, load_eval_report, load_flow_state
from fa.inner_loop.workflow_controller import (
    BaselineCapture,
    StageResult,
    WorkflowContext,
    WorkflowProgress,
    _effective_controller_route,
    _ensure_eval_after_coder,
    _run_adaptive,
    _run_initial_roles,
    _run_linear,
    _run_stage,
    run_workflow,
    workflow_artifact_paths,
)
from fa.providers import ProviderChain, SecretStore
from fa.providers.base import RequestInfo, ResponseInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
_EVAL_FINAL_TEXT = "## Verification Summary\n\n### Verdict\n\nPASS\n"
_ROLE_YAML = """\
{role}:
  name: "m"
  family: "openai"
  chain:
    - provider: openrouter
      model: "t/m"
      base_url: "https://example.invalid/v1"
      api_key_env: K
"""


def _skip_nested_live_test() -> bool:
    """Skip the live test in nodeid/ordinary verify children, but not one kill oracle."""
    try:
        depth = max(0, int(os.environ.get("FA_VERIFY_GATE_TEST_DEPTH", "0")))
    except ValueError:
        depth = 99
    is_kill_check = os.environ.get("FA_VERIFY_GATE_KILL_CHECK") == "1"
    return depth > 1 or (depth == 1 and not is_kill_check)


def _eval_report(
    run_id: str = "gate-test",
    *,
    route: RouteDecision = "complete",
) -> EvalReport:
    verdicts: dict[RouteDecision, EvalVerdict] = {
        "complete": "PASS",
        "return_to_coder": "REPAIR_REQUIRED",
        "return_to_planner": "REPLAN_REQUIRED",
        "blocked": "BLOCKED",
    }
    verdict = verdicts[route]
    return EvalReport(
        run_id=run_id,
        plan_id="PLAN-gate-test",
        plan_version=1,
        evaluation_id=f"eval-{run_id}",
        verdict=verdict,
        route_decision=route,
        summary="independent evaluator decision",
    )


def _context(tmp_path: Path, *, run_id: str, mode: str = "observe") -> WorkflowContext:
    config = tmp_path / "models.yaml"
    config.write_text("providers: {}\n", encoding="utf-8")
    return WorkflowContext(
        run_id=run_id,
        base_task="test verify gate",
        per_role_task={},
        artifact_paths=workflow_artifact_paths(run_id, base_dir=tmp_path / "logs" / run_id),
        config=config,
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        verify_gate_mode=mode,
    )


def _plan_text(marker: Path, *, fail_plan_command: bool = False) -> str:
    append_code = f"from pathlib import Path; Path({str(marker)!r}).open('a', encoding='utf-8').write('global\\n')"
    if fail_plan_command:
        append_code += "; raise SystemExit(7)"
    plan_command = f"python -c {shlex.quote(append_code)}"
    return f"""Plan-ID: PLAN-i02-live-gate

```verify
{plan_command}
```

## SLICE1: the first command owner
CONTRACTS:
  CT71 [FUNCTIONAL]: a successful coder stage reaches the harness verify gate.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> verify_plan
  CT72 [FUNCTIONAL]: a blocking or missing enforce result reconciles after eval and prevents PASS.
    kill: neutralise src/fa/inner_loop/workflow_controller.py::_effective_controller_route
  CT73 [FUNCTIONAL]: every successful coder stage is followed by an eval stage.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::run_workflow -> _ensure_eval_after_coder
  CT75 [FUNCTIONAL]: the composition root dispatches real roles through drive_session.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> run_stage_fn
  CT76 [FUNCTIONAL]: commands remain attributed to the slice that declares them.
    kill: remove-call src/fa/inner_loop/slice_verification.py::verify_plan -> commands_for
  CT77c [FUNCTIONAL]: the operator-selected enforce mode is honored and recorded.
    kill: neutralise src/fa/inner_loop/slice_verification.py::_gate_mode
  CT77b [FUNCTIONAL]: the controller persists the verification attempt artifact.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> write_verification
  CT77 [FUNCTIONAL]: the eval request carries the actual verifier evidence.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_eval_evidence_block -> _verification_evidence_lines
  CT86 [FUNCTIONAL]: the baseline is captured before coder dispatch.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> capture_baseline
TESTS: tests/test_verify_gate_live.py
```verify
python -c "print('slice-one')"
```

## SLICE2: the second command owner
CONTRACTS:
  CT90 [CONSTRAINT]: the second slice owns its own command result.
TESTS: tests/test_verify_gate_live.py
```verify
python -c "print('slice-two')"
```
"""


def test_eval_role_is_relocated_after_every_coder_dispatch() -> None:
    """Q55: omitted, early, and duplicate eval entries cannot skip a coder judgement."""
    assert _ensure_eval_after_coder(["eval", "planner", "coder"]) == ["planner", "coder", "eval"]
    assert _ensure_eval_after_coder(["coder", "eval", "coder", "eval"]) == [
        "coder",
        "eval",
        "coder",
        "eval",
    ]


def test_t0_baseline_is_write_once_and_survives_repair_loads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CT85/86: the T0 writer refuses a second capture rather than adopting a repair as baseline."""
    plan_ids = extract_plan_ids(_plan_text(tmp_path / "marker.txt"))
    baseline_path = tmp_path / "verify_baseline.json"
    captured = BaselineCapture(
        nodeids_by_slice={
            "SLICE1": {"tests/test_verify_gate_live.py::test_existing": True},
            "SLICE2": {},
        }
    )
    monkeypatch.setattr(workflow, "_capture_nodeids_by_slice", lambda *_args, **_kwargs: captured)

    first = workflow.capture_baseline(baseline_path, plan_ids, root=tmp_path, run_id="baseline-once")
    original_bytes = baseline_path.read_bytes()
    refused = workflow.capture_baseline(baseline_path, plan_ids, root=tmp_path, run_id="baseline-once")
    reloaded = workflow.load_verify_baseline(baseline_path, plan_ids, run_id="baseline-once")

    assert first.nodeids_by_slice == captured.nodeids_by_slice
    assert refused.errors and "File exists" in refused.errors[-1]
    assert refused.nodeids_by_slice == {"SLICE1": None, "SLICE2": None}
    assert baseline_path.read_bytes() == original_bytes
    assert reloaded.nodeids_by_slice == captured.nodeids_by_slice


def test_verification_artifact_keeps_repair_attempt_history_and_latest_eval_lines(tmp_path: Path) -> None:
    """CT77b/77: later verification is appended without erasing earlier evidence."""
    path = tmp_path / "verification.json"
    verification = PlanVerification(plan_command_results=(), slice_verifications=())
    workflow.write_verification(path, verification, run_id="history", mode="observe", repair_round=0)
    workflow.write_verification(path, verification, run_id="history", mode="enforce", repair_round=1)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert [item["repair_round"] for item in payload["attempts"]] == [0, 1]
    assert workflow._verification_lines(path) == ("Harness verify gate (mode=enforce, repair_round=1):",)


def test_gate_mode_uses_the_existing_feature_flag_surface_and_defaults_to_observe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT77c: the rollout mode is operator-configurable through FeatureFlags."""
    assert FeatureFlags().workflow_verify_gate_mode == "observe"
    assert FeatureFlags().as_dict()["workflow.verify_gate.mode"] == "observe"
    assert "workflow_verify_gate_mode" in FAIL_OPEN_FLAGS

    config = tmp_path / "config.yaml"
    config.write_text("feature_flags:\n  workflow:\n    verify_gate:\n      mode: enforce\n", encoding="utf-8")
    from fa import feature_flags

    monkeypatch.setattr(feature_flags, "DEFAULT_CONFIG_PATH", config)
    assert _gate_mode() == "enforce"
    assert _gate_mode("OBSERVE") == "observe"
    assert _gate_mode("not-a-mode") == "observe"


def test_reconciliation_keeps_eval_negative_authority_and_never_promotes_a_gate_failure() -> None:
    """CT72: the gate is a no-PASS floor; eval's own non-complete route is preserved."""
    deterministic_failure = _blocking_verification()
    indeterminate_failure = PlanVerification(
        plan_command_results=(),
        slice_verifications=(),
        errors=("kill-check subprocess could not start",),
    )
    passing_verification = PlanVerification(plan_command_results=(), slice_verifications=())
    assert (
        _effective_controller_route(
            _eval_report("observe-block"), deterministic_failure, gate_mode="observe", eval_requested=True
        )
        == "complete"
    )
    assert (
        _effective_controller_route(
            _eval_report("enforce-fail"), deterministic_failure, gate_mode="enforce", eval_requested=True
        )
        == "return_to_coder"
    )
    assert (
        _effective_controller_route(
            _eval_report("enforce-error"), indeterminate_failure, gate_mode="enforce", eval_requested=True
        )
        == "blocked"
    )
    assert (
        _effective_controller_route(
            _eval_report("enforce-pass"), passing_verification, gate_mode="enforce", eval_requested=True
        )
        == "complete"
    )
    assert (
        _effective_controller_route(
            _eval_report("missing-verification"),
            None,
            gate_mode="enforce",
            eval_requested=True,
            verification_required=True,
        )
        == "blocked"
    )
    for negative_route in ("return_to_coder", "return_to_planner", "blocked"):
        assert (
            _effective_controller_route(
                _eval_report(f"eval-{negative_route}", route=negative_route),
                indeterminate_failure,
                gate_mode="enforce",
                eval_requested=True,
            )
            == negative_route
        )


def test_missing_plan_is_indeterminate_and_blocks_an_eval_false_pass(tmp_path: Path) -> None:
    """Q56: a successful coder with no plan has missing evidence, not an empty pass."""
    context = _context(tmp_path, run_id="missing-plan-enforce", mode="enforce")
    result = _run_stage(
        context,
        "coder",
        fresh=True,
        progress=WorkflowProgress(),
        transition_reason="test coder with missing plan",
        run_stage_fn=lambda *_args, **_kwargs: 0,
    )

    assert result.verification is not None
    assert result.verification.blocking
    assert result.verification.errors == ("plan artifact was not supplied before coder dispatch",)
    assert (
        _effective_controller_route(
            _eval_report("missing-plan-enforce"),
            result.verification,
            gate_mode="enforce",
            eval_requested=True,
            verification_required=True,
        )
        == "blocked"
    )
    artifact = json.loads(context.artifact_paths.verification.read_text(encoding="utf-8"))
    assert artifact["attempts"][0]["blocking"] is True
    assert artifact["attempts"][0]["errors"] == ["plan artifact was not supplied before coder dispatch"]


def test_coder_stage_records_enforce_verification_without_replacing_eval_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C0 wiring oracle for CT71/72/77b: preserve actual eval as a later stage."""
    context = _context(tmp_path, run_id="enforce-wiring", mode="enforce")
    blocked = _blocking_verification()
    monkeypatch.setattr(workflow, "verify_plan", lambda *_args, **_kwargs: blocked)

    result = _run_stage(
        context,
        "coder",
        fresh=True,
        progress=WorkflowProgress(),
        transition_reason="test coder",
        run_stage_fn=lambda *_args, **_kwargs: 0,
    )

    assert result.verification is not None
    assert result.verification.plan_command_results == blocked.plan_command_results
    assert result.verification.blocking
    assert result.verification.errors == ("plan artifact was not supplied before coder dispatch",)
    assert result.eval_report is None, "a coder result must not impersonate the evaluator"
    assert not context.artifact_paths.eval_report.exists()
    artifact = json.loads(context.artifact_paths.verification.read_text(encoding="utf-8"))
    assert artifact["attempts"][0]["mode"] == "enforce"
    assert artifact["attempts"][0]["blocking"] is True


def test_observe_mode_records_blocking_evidence_without_routing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path, run_id="observe-wiring", mode="observe")
    monkeypatch.setattr(workflow, "verify_plan", lambda *_args, **_kwargs: _blocking_verification())

    result = _run_stage(
        context,
        "coder",
        fresh=True,
        progress=WorkflowProgress(),
        transition_reason="test coder observe",
        run_stage_fn=lambda *_args, **_kwargs: 0,
    )

    assert result.verification is not None and result.verification.blocking
    assert result.eval_report is None
    artifact = json.loads(context.artifact_paths.verification.read_text(encoding="utf-8"))
    assert artifact["attempts"][0]["mode"] == "observe"
    assert artifact["attempts"][0]["blocking"] is True
    assert not context.artifact_paths.eval_report.exists()


def _blocking_verification() -> PlanVerification:
    return PlanVerification(
        plan_command_results=(
            CommandResult(
                command="python -c failure",
                outcome=CommandOutcome.FAIL,
                exit_code=1,
                stdout_tail="",
                stderr_tail="failed",
                duration_s=0.01,
            ),
        ),
        slice_verifications=(),
    )


def test_both_role_loops_run_eval_after_blocking_coder_and_reconcile_afterward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """CT73: eval is dispatched with verifier facts before a non-PASS terminal route."""
    verification = _blocking_verification()
    report = _eval_report("loop-reconciliation")
    context = _context(tmp_path, run_id="loop-reconciliation", mode="enforce")
    dispatched: list[str] = []
    eval_inputs: list[PlanVerification | None] = []

    def fake_stage(
        _ctx: WorkflowContext,
        role: str,
        **kwargs: Any,
    ) -> StageResult:
        dispatched.append(role)
        if role == "coder":
            return StageResult(role=role, exit_code=0, verification=verification)
        if role == "eval":
            eval_inputs.append(kwargs.get("prior_verification"))
            return StageResult(role=role, exit_code=0, eval_report=report)
        return StageResult(role=role, exit_code=0)

    monkeypatch.setattr(workflow, "_run_stage", fake_stage)
    code, stage_count, final_report, final_verification = _run_initial_roles(
        context,
        ["planner", "coder", "eval"],
        run_stage_fn=lambda *_args, **_kwargs: 0,
    )
    assert code == 0
    assert stage_count == 3
    assert dispatched == ["planner", "coder", "eval"]
    assert final_report is report
    assert final_verification is verification
    assert eval_inputs == [verification]

    dispatched.clear()
    linear_context = _context(tmp_path, run_id="linear-reconciliation", mode="enforce")
    assert (
        _run_linear(
            linear_context,
            ["planner", "coder", "eval"],
            run_stage_fn=lambda *_args, **_kwargs: 0,
        )
        == 0
    )
    assert dispatched == ["planner", "coder", "eval"]
    final_state = load_flow_state(linear_context.artifact_paths.flow_state)
    assert final_state.status == "REPAIR_REQUIRED"
    assert final_state.last_route_decision == "return_to_coder"
    assert final_state.judged is True
    assert workflow.workflow_exit_code(0, final_state) == 1
    captured = capsys.readouterr().err
    assert "not accepted" in captured
    assert "accepted (verdict=PASS)" not in captured


def test_adaptive_verification_repairs_remain_bounded_by_the_existing_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT74: determinate gate failures get eval, then stop at the existing repair cap."""
    verification = _blocking_verification()
    report = _eval_report("adaptive-repair-cap")
    context = _context(tmp_path, run_id="adaptive-repair-cap", mode="enforce")
    dispatched: list[str] = []

    def fake_stage(
        _ctx: WorkflowContext,
        role: str,
        **_kwargs: Any,
    ) -> StageResult:
        dispatched.append(role)
        if role == "coder":
            return StageResult(role=role, exit_code=0, verification=verification)
        if role == "eval":
            return StageResult(role=role, exit_code=0, eval_report=report)
        return StageResult(role=role, exit_code=0)

    monkeypatch.setattr(workflow, "_run_stage", fake_stage)
    assert (
        _run_adaptive(
            context,
            ["coder", "eval"],
            max_repairs=1,
            max_replans=0,
            run_stage_fn=lambda *_args, **_kwargs: 0,
        )
        == 0
    )
    assert dispatched == ["coder", "eval", "coder", "eval"]
    state = load_flow_state(context.artifact_paths.flow_state)
    assert state.status == "REPAIR_REQUIRED"
    assert state.last_route_decision == "return_to_coder"
    assert state.repair_round == 1
    assert workflow.workflow_exit_code(0, state) == 1


def test_indeterminate_enforce_verification_blocks_without_gate_driven_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT72: harness uncertainty blocks an eval false-pass without starting a repair loop."""
    verification = PlanVerification(
        plan_command_results=(),
        slice_verifications=(),
        errors=("verify subprocess could not start",),
    )
    context = _context(tmp_path, run_id="indeterminate-no-repair", mode="enforce")
    dispatched: list[str] = []

    def fake_stage(
        _ctx: WorkflowContext,
        role: str,
        **_kwargs: Any,
    ) -> StageResult:
        dispatched.append(role)
        if role == "coder":
            return StageResult(role=role, exit_code=0, verification=verification)
        if role == "eval":
            return StageResult(role=role, exit_code=0, eval_report=_eval_report("indeterminate-no-repair"))
        return StageResult(role=role, exit_code=0)

    monkeypatch.setattr(workflow, "_run_stage", fake_stage)
    assert (
        _run_adaptive(
            context,
            ["coder", "eval"],
            max_repairs=3,
            max_replans=0,
            run_stage_fn=lambda *_args, **_kwargs: 0,
        )
        == 0
    )
    assert dispatched == ["coder", "eval"]
    state = load_flow_state(context.artifact_paths.flow_state)
    assert state.status == "FAILED"
    assert state.last_route_decision == "blocked"
    assert state.repair_round == 0
    assert "verify subprocess could not start" in state.blocked_reason


@pytest.mark.skipif(
    _skip_nested_live_test(),
    reason="gate-owned pytest runs must not recursively boot the live workflow",
)
def test_real_workflow_writes_verification_and_supplies_it_to_eval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1 / SD-C: real run_workflow -> _cmd_run -> drive_session, one provider seam only."""
    from fa import feature_flags
    from fa.cli import _cmd_run

    home = tmp_path / "home"
    flag_path = home / ".fa" / "config.yaml"
    flag_path.parent.mkdir(parents=True)
    flag_path.write_text("feature_flags:\n  workflow:\n    verify_gate:\n      mode: enforce\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    # The main test process imported FeatureFlags before HOME changed; direct
    # the real loader at the same temporary file the child processes discover.
    monkeypatch.setattr(feature_flags, "DEFAULT_CONFIG_PATH", flag_path)

    state_root = tmp_path / "state"
    state_root.mkdir()
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)

    config = tmp_path / "models.yaml"
    config.write_text("".join(_ROLE_YAML.format(role=role) for role in ("planner", "coder", "eval")), encoding="utf-8")
    plan_marker = tmp_path / "plan-level-command-runs.txt"
    plan_path = tmp_path / "implementation-plan.md"
    plan_path.write_text(_plan_text(plan_marker, fail_plan_command=True), encoding="utf-8")

    provider_roles: list[str] = []
    request_text_by_role: dict[str, list[str]] = {"planner": [], "coder": [], "eval": []}

    def fake_provider_request(
        chain: ProviderChain,
        request: RequestInfo,
        *,
        logical_call_id: str | None = None,
    ) -> tuple[ResponseInfo, str, list[Any]]:
        role = chain.config.role
        provider_roles.append(role)
        request_text_by_role[role].append(
            "\n".join(
                content if isinstance(content := message.get("content"), str) else str(content)
                for message in request.messages
            )
        )
        text = _EVAL_FINAL_TEXT if role == "eval" else f"{role} stage complete"
        response = ResponseInfo(text=text, in_tokens=1, out_tokens=2, finish_reason="stop")
        return response, logical_call_id or f"mock-{role}", []

    # This is the only mocked production boundary in the C1 composition test.
    monkeypatch.setattr(ProviderChain, "request", fake_provider_request)
    run_id = "i02-live-verification"
    exit_code, terminal = run_workflow(
        # Q55: even a caller omitting eval gets a real evaluator after coder.
        roles=["planner", "coder"],
        task="exercise the live verification gate",
        per_role_task={},
        mode="linear",
        max_repairs=0,
        max_replans=0,
        run_id=run_id,
        config=config,
        workspace=REPO_ROOT,
        max_turns=2,
        output_mode="quiet",
        run_stage_fn=_cmd_run,
        transport=None,
        secrets=SecretStore({"K": "sk-test-live"}),
        plan_path=plan_path,
    )

    assert exit_code == 1, "an enforce-mode verifier failure must not yield a successful workflow"
    assert terminal is not None and terminal.status == "REPAIR_REQUIRED"
    assert terminal.last_route_decision == "return_to_coder"
    assert terminal.judged is True
    assert provider_roles == ["planner", "coder", "eval"], "_cmd_run did not reach real drive_session for each role"

    artifacts = workflow_artifact_paths(run_id)
    verification_path = artifacts.verification
    assert verification_path.is_file(), "the production verify_plan call produced no verification.json"
    payload = json.loads(verification_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == run_id
    assert len(payload["attempts"]) == 1
    attempt = payload["attempts"][0]
    assert attempt["mode"] == "enforce"
    assert attempt["blocking"] is True
    assert len(attempt["plan_commands"]) == 1
    assert attempt["plan_commands"][0]["outcome"] == "fail"
    assert attempt["plan_commands"][0]["exit_code"] == 7
    assert [item["slice_id"] for item in attempt["slices"]] == ["SLICE1", "SLICE2"]

    slice_one = next(item for item in attempt["slices"] if item["slice_id"] == "SLICE1")
    slice_two = next(item for item in attempt["slices"] if item["slice_id"] == "SLICE2")
    assert len(slice_one["commands"]) == 1
    assert "slice-one" in slice_one["commands"][0]["stdout_tail"]
    kill_checks = {item["contract_id"]: item for item in slice_one["kill_checks"]}
    expected_kills = {"CT71", "CT72", "CT73", "CT75", "CT76", "CT77c", "CT77b", "CT77", "CT86"}
    assert set(kill_checks) == expected_kills
    assert all(item["verdict"] == "proven" and item["detail"] == "" for item in kill_checks.values())
    assert kill_checks["CT71"]["operator"] == "remove-call"
    assert kill_checks["CT71"]["callee"] == "verify_plan"
    assert kill_checks["CT72"]["operator"] == "neutralise"
    assert kill_checks["CT72"]["symbol"] == "_effective_controller_route"
    assert kill_checks["CT76"]["callee"] == "commands_for"
    assert len(slice_two["commands"]) == 1
    assert "slice-two" in slice_two["commands"][0]["stdout_tail"]
    assert "slice-two" not in " ".join(item["command"] for item in slice_one["commands"])
    assert "slice-one" not in " ".join(item["command"] for item in slice_two["commands"])

    assert plan_marker.read_text(encoding="utf-8") == "global\n", "commands_for(None) did not run exactly once"
    baseline_path = artifacts.verify_baseline
    assert baseline_path.is_file(), "the T0 baseline was not captured before the coder stage"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline["run_id"] == run_id
    assert set(baseline["slices"]) == {"SLICE1", "SLICE2"}

    # The actual evaluator's report is preserved even though controller routing
    # rejects its false-pass on the deterministic command failure.
    eval_report = load_eval_report(artifacts.eval_report)
    assert eval_report is not None
    assert eval_report.verdict == "PASS"
    assert eval_report.route_decision == "complete"
    assert not eval_report.evaluation_id.startswith("harness-verify-")

    eval_request = "\n".join(request_text_by_role["eval"])
    assert "Harness verify gate (mode=enforce" in eval_request
    assert "Plan command: outcome=fail, exit_code=7" in eval_request
    assert "SLICE1: proven" in eval_request
    assert "SLICE2: proven" in eval_request


# Retained SLICE6, CT74/95: the pure request boundary, before admission IO.
# C0 policy plus C2 real CLI rejection; these do not claim admitted C1 delivery.


def _request_input() -> dict[str, Any]:
    return {
        "roles": ["planner", "coder", "eval"],
        "mode": "linear",
        "max_repairs": None,
        "max_replans": None,
        "run_id": "request-valid",
        "task": "implement the declared plan",
        "per_role_task": {},
    }


@pytest.mark.parametrize(
    ("roles", "mode", "expected"),
    [
        ([" coder "], "adaptive", ("coder", "eval")),
        (["eval", "coder", "coder"], "linear", ("coder", "eval", "coder", "eval")),
        (["eval", "planner", "coder"], "linear", ("planner", "coder", "eval")),
        (["planner"], "linear", ("planner",)),
    ],
)
def test_role_order_request_normalization_preserves_non_eval_stages(
    roles: list[str], mode: str, expected: tuple[str, ...]
) -> None:
    values = _request_input() | {"roles": roles, "mode": mode}
    request = workflow._validate_workflow_request(**values)

    assert request.roles == tuple(role.strip() for role in roles)
    assert workflow._ensure_eval_after_coder(list(request.roles)) == list(expected)
    assert values["roles"] == roles
    assert request.max_repairs == workflow.DEFAULT_MAX_REPAIRS
    assert request.max_replans == workflow.DEFAULT_MAX_REPLANS


@pytest.mark.parametrize(("repairs", "replans", "expected"), [(-10, -1, (0, 0)), (0, 0, (0, 0)), (99, 99, (3, 2))])
def test_direct_budget_request_clamps_real_integers(repairs: int, replans: int, expected: tuple[int, int]) -> None:
    request = workflow._validate_workflow_request(
        **(_request_input() | {"max_repairs": repairs, "max_replans": replans})
    )

    assert (request.max_repairs, request.max_replans) == expected


_INVALID_REQUESTS = [
    ("roles", [], "roles"),
    ("roles", "coder", "roles"),
    ("roles", ["coder", ""], "roles"),
    ("roles", ["private-secret-value"], "roles"),
    ("roles", [True], "roles"),
    ("roles", ["coder", "planner"], "role-order"),
    ("roles", ["planner", "planner", "coder"], "role-order"),
    ("mode", "private-secret-mode", "mode"),
    ("max_repairs", True, "max-repairs"),
    ("max_repairs", "1", "max-repairs"),
    ("max_repairs", 1.0, "max-repairs"),
    ("max_replans", False, "max-replans"),
    ("max_replans", "1", "max-replans"),
    ("max_replans", 1.0, "max-replans"),
    ("run_id", "../private-secret", "run-id"),
    ("run_id", ".hidden", "run-id"),
    ("run_id", "", "run-id"),
    ("run_id", "x" * 129, "run-id"),
    ("task", " ", "task"),
    ("task", None, "task"),
    ("task", 7, "task"),
    ("inject_overrides", {"private-secret-injection": "off"}, "injection"),
    ("inject_overrides", {"coder_slice_ceremony": "private-secret-mode"}, "injection"),
    ("inject_overrides", {"coder_slice_ceremony": True}, "injection"),
]


@pytest.mark.parametrize(("field", "value", "code"), _INVALID_REQUESTS)
def test_direct_budget_invalid_request_has_no_artifacts_or_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
    value: object,
    code: str,
) -> None:
    from fa.cli import _cmd_run

    home, state, workspace = tmp_path / "home", tmp_path / "state", tmp_path / "workspace"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("FA_STATE_ROOT", str(state))
    values = _request_input() | {field: value}

    result = run_workflow(
        **values,
        config=tmp_path / "missing-models.yaml",
        workspace=workspace,
        max_turns=1,
        run_stage_fn=_cmd_run,
    )

    assert result == (2, None)
    assert capsys.readouterr().err == f"fa workflow: invalid workflow request: {code}\n"
    assert not home.exists()
    assert not state.exists()
    assert not workspace.exists()


@pytest.mark.parametrize(("field", "value", "code"), [row for row in _INVALID_REQUESTS if row[0] != "inject_overrides"])
def test_plan_preflight_cli_rejects_malformed_request_before_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
    value: object,
    code: str,
) -> None:
    import argparse

    from fa.cli import _cmd_workflow

    home, state, workspace = tmp_path / "home", tmp_path / "state", tmp_path / "workspace"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("FA_STATE_ROOT", str(state))
    values = _request_input() | {field: value}
    roles = values["roles"]
    # Actual argv delivers one comma-separated string, including empty entries.
    cli_roles = ",".join(roles) if isinstance(roles, list) and all(isinstance(role, str) for role in roles) else roles
    if field == "roles" and value == "coder":
        cli_roles = "private-secret-value"
    args = argparse.Namespace(
        **{key: val for key, val in values.items() if key not in {"roles", "per_role_task"}},
        roles=cli_roles,
        session_id="preflight-session",
        workspace=workspace,
        config=tmp_path / "missing-models.yaml",
        max_turns=1,
        inject=None,
    )

    assert _cmd_workflow(args) == 2
    expected_error = f"fa workflow: invalid workflow request: {code}\n"
    if code == "roles" and cli_roles == "private-secret-value":
        expected_error = (
            "fa workflow: unsupported stage role(s): 'private-secret-value'. "
            "--roles must be drawn from: coder, eval, planner\n"
        )
    assert capsys.readouterr().err == expected_error
    assert not home.exists()
    assert not state.exists()
    assert not workspace.exists()


@pytest.mark.parametrize("inject", [["unknown=off"], ["coder_slice_ceremony=invalid"], ["bad"], [True]])
def test_plan_preflight_invalid_inject_cannot_claim_a_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], inject: list[object]
) -> None:
    import argparse

    from fa.cli import _cmd_workflow

    home, state, workspace = tmp_path / "home", tmp_path / "state", tmp_path / "workspace"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("FA_STATE_ROOT", str(state))
    args = argparse.Namespace(
        roles="coder",
        task="implement",
        run_id="request-valid",
        mode="adaptive",
        max_repairs=0,
        max_replans=0,
        config=tmp_path / "models.yaml",
        workspace=workspace,
        max_turns=1,
        session_id="preflight-session",
        inject=inject,
    )

    assert _cmd_workflow(args) == 2
    assert capsys.readouterr().err == "fa workflow: invalid workflow request: injection\n"
    assert not home.exists()
    assert not state.exists()
    assert not workspace.exists()


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("run_id", None, "run-id"),
        ("run_id", True, "run-id"),
        ("run_id", 7, "run-id"),
        ("mode", None, "mode"),
        ("per_role_task", None, "task"),
        ("per_role_task", {"unknown": "text"}, "task"),
        ("per_role_task", {"coder": True}, "task"),
        ("inject_overrides", [], "injection"),
        ("inject_overrides", {7: "off"}, "injection"),
        ("inject_overrides", {"coder_slice_ceremony": []}, "injection"),
    ],
)
def test_direct_budget_pure_request_rejects_wrong_shapes(field: str, value: object, code: str) -> None:
    with pytest.raises(workflow.WorkflowRequestError) as failure:
        workflow._validate_workflow_request(**(_request_input() | {field: value}))

    assert failure.value.code == code
    assert str(failure.value) == f"invalid workflow request: {code}"


@pytest.mark.parametrize("run_id", ["a", "0", "a" * 128, "A.b_C-9"])
@pytest.mark.parametrize("mode", ["off", "observe", "enforce"])
def test_direct_budget_valid_identity_and_injection_controls(run_id: str, mode: str) -> None:
    request = workflow._validate_workflow_request(
        **(_request_input() | {"run_id": run_id, "inject_overrides": {"coder_slice_ceremony": mode}})
    )

    assert request.roles == ("planner", "coder", "eval")
    assert (request.max_repairs, request.max_replans) == (workflow.DEFAULT_MAX_REPAIRS, workflow.DEFAULT_MAX_REPLANS)


def test_plan_preflight_requested_id_can_be_absent_only_at_cli_generation_boundary() -> None:
    values = _request_input() | {"run_id": None}
    request = workflow._validate_workflow_request(**values, allow_missing_run_id=True)

    assert request.roles == ("planner", "coder", "eval")
    with pytest.raises(workflow.WorkflowRequestError, match=r"^invalid workflow request: run-id$"):
        workflow._validate_workflow_request(**values)


@pytest.mark.parametrize(("context_id", "context_workspace"), [("different", "workspace"), ("request-valid", "other")])
def test_direct_budget_context_identity_mismatch_has_no_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    context_id: str,
    context_workspace: str,
) -> None:
    from fa.cli import _cmd_run
    from fa.session.manager import RunContext

    home, state, workspace = tmp_path / "home", tmp_path / "state", tmp_path / "workspace"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("FA_STATE_ROOT", str(state))
    context = RunContext(
        run_id=context_id,
        session_id="request-session",
        workspace_path=tmp_path / context_workspace,
        session_db_path=state / "session.db",
        run_log_dir=state / "run",
    )

    result = run_workflow(
        **_request_input(),
        config=tmp_path / "models.yaml",
        workspace=workspace,
        max_turns=1,
        run_stage_fn=_cmd_run,
        run_context=context,
    )

    assert result == (2, None)
    assert capsys.readouterr().err == "fa workflow: invalid workflow request: context-binding\n"
    assert not home.exists()
    assert not state.exists()
    assert not workspace.exists()


def test_direct_budget_matching_context_and_per_role_tasks_are_accepted(tmp_path: Path) -> None:
    from fa.session.manager import RunContext

    workspace = tmp_path / "workspace"
    context = RunContext(
        run_id="request-valid",
        session_id="request-session",
        workspace_path=workspace,
        session_db_path=tmp_path / "session.db",
        run_log_dir=tmp_path / "run",
    )
    request = workflow._validate_workflow_request(
        **(
            _request_input()
            | {"task": None, "per_role_task": dict.fromkeys(("planner", "coder", "eval"), "implement")}
        ),
        workspace=workspace,
        run_context=context,
    )

    assert request.roles == ("planner", "coder", "eval")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "values,code",
    [
        ({"roles": ["planner"], "mode": "adaptive"}, "adaptive-roles"),
        ({"roles": ["coder"], "task": None, "per_role_task": {"coder": "implement"}}, "task"),
        ({"per_role_task": {"coder": " "}}, "task"),
    ],
)
def test_direct_budget_request_cross_field_rejections(values: dict[str, object], code: str) -> None:
    with pytest.raises(workflow.WorkflowRequestError) as failure:
        workflow._validate_workflow_request(**(_request_input() | values))

    assert failure.value.code == code


@pytest.mark.parametrize("context", [{}, [], "not-a-context", SimpleNamespace(run_id="request-valid")])
def test_direct_budget_malformed_context_is_a_typed_rejection(context: object) -> None:
    with pytest.raises(workflow.WorkflowRequestError) as failure:
        workflow._validate_workflow_request(
            **(_request_input() | {"run_context": context}), workspace=Path("workspace")
        )

    assert failure.value.code == "context-binding"


# CT90/95 STEP13: C0 exact-byte reader, C2 CLI preflight, adversarial paths.
# No new claim about admitted direct C1, promotion or OS execution isolation.


def test_plan_preflight_snapshot_owns_exact_bytes_and_relative_identity(tmp_path: Path) -> None:
    import hashlib
    from dataclasses import FrozenInstanceError

    from fa.inner_loop.plan_admission import PlanRef, read_plan_snapshot

    raw = b"Plan-ID: PLAN-reference\r\n\r\n## SLICE1: same bytes\r\nTESTS: tests/test_x.py\r\n"
    target = tmp_path / "plans" / "p.md"
    target.parent.mkdir()
    target.write_bytes(raw)
    snapshot = read_plan_snapshot(tmp_path, Path("plans/p.md"))

    assert snapshot.ref == PlanRef("plans/p.md", "EXPLICIT", hashlib.sha256(raw).hexdigest())
    assert snapshot.utf8_bytes == raw
    assert snapshot.text == raw.decode("utf-8")
    assert snapshot.ids == extract_plan_ids(snapshot.text)
    assert read_plan_snapshot(tmp_path, target) == snapshot
    target.write_text("changed", encoding="utf-8")
    assert snapshot.utf8_bytes == raw
    with pytest.raises(FrozenInstanceError):
        snapshot.ref.__setattr__("sha256", "changed")


@pytest.mark.parametrize(
    "kind,rule",
    [
        ("absent", "unreadable"),
        ("directory", "not-regular"),
        ("empty", "empty"),
        ("whitespace", "empty"),
        ("invalid-utf8", "invalid-utf8"),
        ("too-large", "too-large"),
        ("terminal-link", "symlink"),
        ("ancestor-link", "symlink"),
        ("dangling-link", "symlink"),
        ("escape", "path-escape"),
        ("outside", "path-escape"),
        ("root", "path-escape"),
        ("nul", "unreadable"),
    ],
)
def test_plan_preflight_reader_rejects_bad_reference(tmp_path: Path, kind: str, rule: str) -> None:
    from fa.inner_loop.plan_admission import MAX_PLAN_BYTES, PlanRefError, read_plan_snapshot

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("secret fixture bytes", encoding="utf-8")
    target = workspace / "plan.md"
    if kind == "directory":
        target.mkdir()
    elif kind in {"empty", "whitespace", "invalid-utf8", "too-large"}:
        target.write_bytes(
            {"empty": b"", "whitespace": b" \t\r\n", "invalid-utf8": b"\xff", "too-large": b"x" * (MAX_PLAN_BYTES + 1)}[
                kind
            ]
        )
    elif kind == "terminal-link":
        target.symlink_to(outside)
    elif kind == "ancestor-link":
        (workspace / "linked").symlink_to(tmp_path, target_is_directory=True)
        target = workspace / "linked" / "outside.md"
    elif kind == "dangling-link":
        target.symlink_to(workspace / "absent.md")
    elif kind == "escape":
        target = Path("../outside.md")
    elif kind == "outside":
        target = outside
    elif kind == "root":
        target = Path(".")
    elif kind == "nul":
        target = Path("bad\x00name")

    with pytest.raises(PlanRefError) as failure:
        read_plan_snapshot(workspace, target)

    assert failure.value.rule == rule
    assert str(failure.value) == f"invalid plan reference: {rule}"
    assert outside.read_text(encoding="utf-8") == "secret fixture bytes"


def test_plan_preflight_size_limit_is_inclusive(tmp_path: Path) -> None:
    from fa.inner_loop.plan_admission import MAX_PLAN_BYTES, read_plan_snapshot

    target = tmp_path / "limit.md"
    target.write_bytes(b"x" * MAX_PLAN_BYTES)
    assert len(read_plan_snapshot(tmp_path, target).utf8_bytes) == MAX_PLAN_BYTES


def test_plan_preflight_fifo_cannot_hang_reader(tmp_path: Path) -> None:
    import subprocess
    import sys

    target = tmp_path / "pipe"
    os.mkfifo(target)
    code = (
        "from pathlib import Path; "
        "from fa.inner_loop.plan_admission import read_plan_snapshot, PlanRefError; "
        "import sys\n"
        "try: read_plan_snapshot(Path(sys.argv[1]), Path('pipe'))\n"
        "except PlanRefError as e: print(e.rule)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True, timeout=5, check=False
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, "not-regular\n", "")


def test_plan_preflight_detects_concurrent_source_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop import plan_admission as admission

    target = tmp_path / "plan.md"
    target.write_bytes(b"before")
    original_read = os.read
    changed = False

    def read_and_change(fd: int, count: int) -> bytes:
        nonlocal changed
        raw = original_read(fd, count)
        if not changed:
            changed = True
            target.write_bytes(b"after-and-longer")
        return raw

    monkeypatch.setattr(os, "read", read_and_change)
    with pytest.raises(admission.PlanRefError) as failure:
        admission.read_plan_snapshot(tmp_path, target)
    assert failure.value.rule == "source-changed"


@pytest.mark.parametrize("mode", ["linear", "adaptive"])
@pytest.mark.parametrize("kind", ["missing", "unreadable", "outside", "symlink", "invalid-utf8", "too-large"])
def test_plan_preflight_cli_plan_rejection_precedes_allocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], mode: str, kind: str
) -> None:
    from fa.cli import _cmd_workflow, build_parser
    from fa.inner_loop.plan_admission import MAX_PLAN_BYTES

    home, state, workspace = tmp_path / "home", tmp_path / "state", tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("FA_STATE_ROOT", str(state))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.chdir(workspace)
    target = workspace / "plan.md"
    argv = ["workflow", "coder", "implement", "--mode", mode, "--run-id", "plan-reject", "--workspace", str(workspace)]
    if kind == "outside":
        target = tmp_path / "private-sentinel.md"
        target.write_text("do not expose fixture", encoding="utf-8")
    elif kind == "symlink":
        target.symlink_to(workspace / "missing.md")
    elif kind == "invalid-utf8":
        target.write_bytes(b"\xff")
    elif kind == "too-large":
        target.write_bytes(b"x" * (MAX_PLAN_BYTES + 1))
    if kind != "missing":
        argv.extend(["--plan", str(target)])
    args = build_parser().parse_args(argv)
    before = sorted(p.name for p in workspace.iterdir())

    assert _cmd_workflow(args) == 2

    err = capsys.readouterr().err
    rule = "path-escape" if kind == "outside" else kind
    assert err.startswith(f"fa workflow: invalid plan reference: {rule} (")
    assert str(target) not in err
    assert "do not expose" not in err
    assert not state.exists()
    assert not home.exists()
    assert sorted(p.name for p in workspace.iterdir()) == before


def test_plan_preflight_workspace_resolution_is_read_only(tmp_path: Path) -> None:
    from fa.session.manager import SessionManager, SessionManagerError

    state, root = tmp_path / "state", tmp_path / "workspaces"
    manager = SessionManager(state_root=state, workspace_root=root)
    assert not state.exists()
    assert not root.exists()
    assert (
        manager.resolve_workflow_workspace(session_id=None, workspace_override=root / "selected") == root / "selected"
    )
    assert not state.exists()
    assert not root.exists()
    with pytest.raises(SessionManagerError) as failure:
        manager.resolve_workflow_workspace(session_id=None, workspace_override=None)
    assert failure.value.code == "workspace_required"
    assert str(failure.value) == "workspace_required: create or choose an existing workspace with --workspace first"


def test_plan_preflight_resumed_session_does_not_touch_manifest_or_db(tmp_path: Path) -> None:
    from fa.session.manager import SessionManager, SessionManagerError

    manager = SessionManager(state_root=tmp_path / "state", workspace_root=tmp_path / "workspaces")
    session = manager.provision_entrypoint_session(
        session_id="existing", workspace_override=tmp_path / "workspaces" / "one"
    )
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
    assert manager.resolve_workflow_workspace(session_id="existing", workspace_override=None) == session.workspace_path
    assert (
        manager.resolve_workflow_workspace(session_id="existing", workspace_override=session.workspace_path)
        == session.workspace_path
    )
    with pytest.raises(SessionManagerError) as failure:
        manager.resolve_workflow_workspace(session_id="existing", workspace_override=tmp_path / "workspaces" / "two")
    assert failure.value.code == "workspace_mismatch"
    assert str(failure.value) == "workspace_mismatch: workspace disagrees with session"
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files} == before
    assert {p for p in tmp_path.rglob("*") if p.is_file()} == set(files)


def test_plan_help_describes_required_workspace_relative_plan(capsys: pytest.CaptureFixture[str]) -> None:
    from fa.cli import build_parser

    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["workflow", "--help"])
    assert exit_info.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "Explicit plan required when roles contain coder" in help_text
    assert "selected workspace, not the process CWD" in help_text
    assert "automatic bootstrap is not available" in help_text


@pytest.mark.parametrize("resumed", [False, True])
def test_plan_preflight_real_cli_uses_selected_workspace_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, resumed: bool
) -> None:
    """C2 positive control: real factories/session/provider loop; only provider mocked."""
    from fa.cli import _cmd_workflow, build_parser
    from fa.session.manager import SessionManager

    state, workspace, cwd = tmp_path / "state", tmp_path / "workspaces" / "selected", tmp_path / "cwd"
    workspace.mkdir(parents=True)
    cwd.mkdir()
    (workspace / "plan.md").write_text("Plan-ID: PLAN-selected\n", encoding="utf-8")
    # A same-named invalid CWD file must neither authorize nor veto selection.
    (cwd / "plan.md").write_bytes(b"\xff")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FA_STATE_ROOT", str(state))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(workspace.parent))
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
    monkeypatch.chdir(cwd)
    config = tmp_path / "models.yaml"
    config.write_text(_ROLE_YAML.format(role="planner"), encoding="utf-8")
    if resumed:
        manager = SessionManager(state_root=state, workspace_root=workspace.parent)
        manager.provision_entrypoint_session(session_id="selected-session", workspace_override=workspace)
    calls: list[str] = []

    def provider(
        chain: ProviderChain, request: RequestInfo, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        calls.append(chain.config.role)
        return ResponseInfo(text="planning finished", in_tokens=1, out_tokens=1, finish_reason="stop"), "p", []

    monkeypatch.setattr(ProviderChain, "request", provider)
    argv = [
        "workflow",
        "planner",
        "inspect explicit plan",
        "--run-id",
        "workspace-plan",
        "--plan",
        "plan.md",
        "--config",
        str(config),
    ]
    argv += ["--session-id", "selected-session"] if resumed else ["--workspace", str(workspace)]
    args = build_parser().parse_args(argv)

    assert _cmd_workflow(args, secrets=SecretStore({"K": "fixture-key"})) == 0
    assert calls == ["planner"]
    final = load_flow_state(state / "session-log" / "workspace-plan" / "flow_state.json")
    assert final.plan_path == str(workspace / "plan.md")
    assert (cwd / "plan.md").read_bytes() == b"\xff"


@pytest.mark.parametrize(
    "change,code",
    [
        ("unknown", "unknown_session"),
        ("missing-workspace", "workspace_missing"),
        ("corrupt", "manifest_corrupt"),
        ("inactive", "session_not_active"),
        ("escape", "path_escape"),
    ],
)
def test_plan_preflight_resolver_rejects_invalid_session_without_writes(tmp_path: Path, change: str, code: str) -> None:
    from fa.session.manager import SessionManager, SessionManagerError

    manager = SessionManager(state_root=tmp_path / "state", workspace_root=tmp_path / "workspaces")
    selected = tmp_path / "workspaces" / "selected"
    session = manager.provision_entrypoint_session(session_id="known", workspace_override=selected)
    if change == "missing-workspace":
        selected.rmdir()
    elif change == "corrupt":
        session.manifest_path.write_text("{bad", encoding="utf-8")
    elif change in {"inactive", "escape"}:
        data = json.loads(session.manifest_path.read_text(encoding="utf-8"))
        data["status" if change == "inactive" else "workspace_path"] = (
            "archived" if change == "inactive" else str(tmp_path / "outside")
        )
        session.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
    with pytest.raises(SessionManagerError) as failure:
        manager.resolve_workflow_workspace(
            session_id="absent" if change == "unknown" else "known", workspace_override=None
        )
    assert failure.value.code == code
    if change == "unknown":
        assert str(failure.value) == "unknown_session: session does not exist"
    if change == "missing-workspace":
        assert str(failure.value) == "workspace_missing: session workspace is missing"
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files} == before
    assert {p for p in tmp_path.rglob("*") if p.is_file()} == set(files)


@pytest.mark.parametrize("workspace_kind", ["missing", "regular-file"])
def test_plan_preflight_unusable_root_is_sanitized(tmp_path: Path, workspace_kind: str) -> None:
    from fa.inner_loop.plan_admission import PlanRefError, read_plan_snapshot

    root = tmp_path / "root"
    if workspace_kind == "regular-file":
        root.write_bytes(b"not a directory")
    # Missing root dominates even an absolute outside target, before path walk.
    target = tmp_path / "outside.md" if workspace_kind == "missing" else Path("plan.md")
    with pytest.raises(PlanRefError) as failure:
        read_plan_snapshot(root, target)
    assert (failure.value.rule, str(failure.value)) == ("unreadable", "invalid plan reference: unreadable")


def test_plan_preflight_short_reads_preserve_exact_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib

    from fa.inner_loop.plan_admission import read_plan_snapshot

    raw = "Plan-ID: PLAN-bytes\n\u041f\u0440\u0438\u043c\u0435\u0440\n".encode()
    target = tmp_path / "plan.md"
    target.write_bytes(raw)
    original_read = os.read
    monkeypatch.setattr(os, "read", lambda fd, count: original_read(fd, min(count, 3)))
    snapshot = read_plan_snapshot(tmp_path, target)
    assert snapshot.utf8_bytes == raw
    assert snapshot.ref.sha256 == hashlib.sha256(raw).hexdigest()


def test_plan_preflight_growth_never_reads_beyond_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.plan_admission import MAX_PLAN_BYTES, PlanRefError, read_plan_snapshot

    target = tmp_path / "plan.md"
    target.write_bytes(b"initial")
    original_read = os.read
    changed = False
    received: list[int] = []

    def grow_and_read(fd: int, count: int) -> bytes:
        nonlocal changed
        if not changed:
            changed = True
            target.write_bytes(b"x" * (3 * MAX_PLAN_BYTES))
        raw = original_read(fd, min(count, 64 * 1024))
        received.append(len(raw))
        return raw

    monkeypatch.setattr(os, "read", grow_and_read)
    with pytest.raises(PlanRefError) as failure:
        read_plan_snapshot(tmp_path, target)
    assert (failure.value.rule, str(failure.value)) == ("too-large", "invalid plan reference: too-large")
    assert sum(received) == MAX_PLAN_BYTES + 1


def test_plan_preflight_descriptors_are_nofollow_nonblocking_and_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C0 mechanism supplement to the actual symlink/FIFO tests, not OS-isolation proof."""
    from fa.inner_loop.plan_admission import read_plan_snapshot

    directory = tmp_path / "plans"
    directory.mkdir()
    (directory / "plan.md").write_bytes(b"plan bytes")
    original_open = os.open
    opened: list[tuple[object, int, int]] = []

    def record_open(path: Any, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
        fd = original_open(path, flags, mode, dir_fd=dir_fd)
        opened.append((path, flags, fd))
        return fd

    monkeypatch.setattr(os, "open", record_open)
    assert read_plan_snapshot(tmp_path, directory / "plan.md").utf8_bytes == b"plan bytes"
    assert len(opened) == 3
    for index, (_path, flags, _fd) in enumerate(opened):
        assert flags & os.O_NOFOLLOW
        assert flags & os.O_CLOEXEC
        if index < 2:
            assert flags & os.O_DIRECTORY
        if index > 0:
            assert flags & os.O_NONBLOCK
    for fd in {item[2] for item in opened}:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_plan_preflight_new_workspace_cannot_bypass_existing_owner(tmp_path: Path) -> None:
    from fa.session.manager import SessionManager, SessionManagerError

    manager = SessionManager(state_root=tmp_path / "state", workspace_root=tmp_path / "workspaces")
    session = manager.provision_entrypoint_session(
        session_id="owner", workspace_override=tmp_path / "workspaces" / "owned"
    )
    before = session.manifest_path.read_bytes()
    with pytest.raises(SessionManagerError) as failure:
        manager.resolve_workflow_workspace(session_id=None, workspace_override=session.workspace_path)
    assert failure.value.code == "workspace_already_owned"
    assert session.manifest_path.read_bytes() == before


@pytest.mark.parametrize("failure_point", ["ancestor", "terminal"])
def test_plan_preflight_close_failure_still_releases_owned_descriptors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_point: str
) -> None:
    """C0 fault injection: simulate Linux closing a descriptor but reporting EIO."""
    import errno

    from fa.inner_loop.plan_admission import PlanRefError, read_plan_snapshot

    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / "plan.md").write_bytes(b"plan")
    original_open, original_close = os.open, os.close
    names: dict[int, object] = {}
    owned: list[int] = []
    failed = False

    def record_open(path: Any, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
        fd = original_open(path, flags, mode, dir_fd=dir_fd)
        names[fd] = path
        owned.append(fd)
        return fd

    def close_with_fault(fd: int) -> None:
        nonlocal failed
        name = names.pop(fd, None)
        original_close(fd)
        if not failed and name == (tmp_path if failure_point == "ancestor" else "plan.md"):
            failed = True
            raise OSError(errno.EIO, "injected close failure")

    monkeypatch.setattr(os, "open", record_open)
    monkeypatch.setattr(os, "close", close_with_fault)
    with pytest.raises(PlanRefError) as failure:
        read_plan_snapshot(tmp_path, tmp_path / "plans" / "plan.md")
    assert failed
    assert failure.value.rule == "unreadable"
    for fd in set(owned):
        with pytest.raises(OSError):
            os.fstat(fd)


def test_plan_help_registry_and_examples_carry_explicit_workspace_plan() -> None:
    from fa.cli import build_parser
    from fa.cli_help import COMMANDS

    help_args = COMMANDS["workflow"]["args"]["--plan"]
    assert "Explicit plan required" in help_args["en"]
    assert "bootstrap" in help_args["ru"]
    examples = COMMANDS["workflow"]["examples"]
    assert len(examples) == 5
    for example in examples:
        args = build_parser().parse_args(shlex.split(example)[1:])
        assert args.workspace == Path("/sessions/demo")
        assert args.plan == Path(
            "worklogs/planning-topology-and-executable-contracts-loop/increments/"
            "increment-02-verify-gate-and-kill-checks.md"
        )
        assert "coder" in args.roles.split(",")


def test_plan_preflight_allocated_workspace_mismatch_blocks_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLI fault supplement: change the real manifest after the snapshot read."""
    from fa import cli
    from fa.inner_loop.plan_admission import PlanSnapshot, read_plan_snapshot
    from fa.session.manager import SessionManager

    state, root = tmp_path / "state", tmp_path / "workspaces"
    first, second = root / "first", root / "second"
    first.mkdir(parents=True)
    second.mkdir()
    (first / "plan.md").write_text("Plan-ID: PLAN-first\n", encoding="utf-8")
    manager = SessionManager(state_root=state, workspace_root=root)
    session = manager.provision_entrypoint_session(session_id="switch", workspace_override=first)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FA_STATE_ROOT", str(state))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(root))
    original_reader = read_plan_snapshot

    def read_then_switch(workspace: Path, target: Path) -> PlanSnapshot:
        snapshot = original_reader(workspace, target)
        manifest = json.loads(session.manifest_path.read_text(encoding="utf-8"))
        manifest["workspace_path"] = str(second)
        session.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return snapshot

    # Fault injection changes only fixture environment, not lifecycle behavior.
    monkeypatch.setattr(cli, "read_plan_snapshot", read_then_switch)
    providers: list[str] = []

    def provider(
        chain: ProviderChain, request: RequestInfo, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        providers.append(chain.config.role)
        return ResponseInfo(text="done", in_tokens=1, out_tokens=1, finish_reason="stop"), "p", []

    monkeypatch.setattr(ProviderChain, "request", provider)
    args = cli.build_parser().parse_args(
        ["workflow", "planner", "inspect", "--session-id", "switch", "--plan", "plan.md", "--run-id", "mismatch"]
    )
    assert cli._cmd_workflow(args) == 2
    assert providers == []
    assert "fa workflow: workspace preflight: workspace-mismatch\n" in capsys.readouterr().err
    assert (state / "session-log" / "mismatch").is_dir(), "the fault must actually pass through lifecycle"
    assert not (state / "session-log" / "mismatch" / "flow_state.json").exists()
