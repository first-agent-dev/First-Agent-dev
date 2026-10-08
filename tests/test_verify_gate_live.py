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
