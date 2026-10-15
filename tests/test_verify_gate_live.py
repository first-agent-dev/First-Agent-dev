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
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

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
from fa.inner_loop.workflow_artifacts import (
    EvalReport,
    EvalVerdict,
    FlowState,
    RouteDecision,
    load_eval_report,
    load_flow_state,
)
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

if TYPE_CHECKING:
    from fa.inner_loop.plan_admission import PlanSnapshot

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
    # STEP13: real source/test overlay in a disposable workspace; the explicit
    # plan must not live outside it. No operator source or metadata is mutated.
    import shutil

    workspace = tmp_path / "workspace"
    for relative in ("src/fa", "scripts"):
        shutil.copytree(REPO_ROOT / relative, workspace / relative, ignore=shutil.ignore_patterns("__pycache__"))
    (workspace / "tests").mkdir()
    for filename in ("conftest.py", "__init__.py", "test_verify_gate_live.py"):
        shutil.copy2(REPO_ROOT / "tests" / filename, workspace / "tests" / filename)
    for filename in ("pyproject.toml", "uv.lock"):
        shutil.copy2(REPO_ROOT / filename, workspace / filename)
    (workspace / ".venv").symlink_to(REPO_ROOT / ".venv", target_is_directory=True)
    plan_marker = workspace / "plan-level-command-runs.txt"
    plan_path = workspace / "implementation-plan.md"
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
        workspace=workspace,
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
    from fa.inner_loop.plan_admission import read_plan_snapshot
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


# CT92/95: closed records, durable locked append and safely addressed rejection.


def _admission_attempt(**changes: Any) -> dict[str, Any]:
    return {
        "dispatch_kind": "EXPLICIT_INPUT",
        "validation": "INDETERMINATE",
        "diagnostics": [{"validator": "plan-ref", "rule": "missing", "severity": "ERROR", "line": None}],
        "source_sha256": None,
        "candidate_sha256": None,
        "promoted_sha256": None,
        "route": "BLOCKED",
    } | changes


def _admission_fixture() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": "admission-test",
        "status": "ADMITTED",
        "plan_ref": {"workspace_relative_path": "plans/p.md", "source_kind": "EXPLICIT", "sha256": "a" * 64},
        "attempts": [
            _admission_attempt(
                attempt=1,
                validation="PASS",
                route="ADMITTED",
                source_sha256="a" * 64,
                diagnostics=[
                    {
                        "validator": "precheck",
                        "rule": "step-near-miss",
                        "severity": "WARN",
                        "line": 7,
                        "contract_id": "CT12a",
                    }
                ],
            )
        ],
    }


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), True),
        (("schema_version",), 2),
        (("run_id",), "different"),
        (("status",), "unknown"),
        (("attempts",), []),
        (("attempts",), {}),
        (("extra",), "raw secret"),
        (("plan_ref", "extra"), "raw secret"),
        (("plan_ref", "workspace_relative_path"), "../outside"),
        (("plan_ref", "workspace_relative_path"), "/outside"),
        (("plan_ref", "workspace_relative_path"), "a//b"),
        (("plan_ref", "workspace_relative_path"), "a/./b"),
        (("plan_ref", "workspace_relative_path"), ""),
        (("plan_ref", "workspace_relative_path"), "a\x00b"),
        (("plan_ref", "sha256"), None),
        (("plan_ref", "sha256"), "A" * 64),
        (("plan_ref", "source_kind"), "guessed"),
        (("attempts", 0, "attempt"), True),
        (("attempts", 0, "attempt"), 0),
        (("attempts", 0, "dispatch_kind"), "PLANNER"),
        (("attempts", 0, "validation"), "unknown"),
        (("attempts", 0, "route"), "unknown"),
        (("attempts", 0, "route"), "RETRY"),
        (("attempts", 0, "source_sha256"), None),
        (("attempts", 0, "source_sha256"), "x"),
        (("attempts", 0, "candidate_sha256"), "b" * 64),
        (("attempts", 0, "promoted_sha256"), "a" * 64),
        (("attempts", 0, "diagnostics"), {}),
        (("attempts", 0, "diagnostics", 0, "validator"), "unknown"),
        (("attempts", 0, "diagnostics", 0, "rule"), "kill-directive-missing"),
        (("attempts", 0, "diagnostics", 0, "severity"), "unknown"),
        (("attempts", 0, "diagnostics", 0, "severity"), "ERROR"),
        (("attempts", 0, "diagnostics", 0, "severity"), "FAIL"),
        (("attempts", 0, "diagnostics", 0, "line"), True),
        (("attempts", 0, "diagnostics", 0, "line"), 0),
        (("attempts", 0, "diagnostics", 0, "contract_id"), "CT12\n"),
        (("attempts", 0, "diagnostics", 0, "message"), "raw secret"),
    ],
)
def test_admission_artifact_schema_rejects_invalid_fields(path: tuple[Any, ...], value: object) -> None:
    from fa.inner_loop.admission_schema import AdmissionRecordError, validate_admission_record

    record = _admission_fixture()
    parent = record
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    with pytest.raises(AdmissionRecordError, match=r"^invalid admission record$"):
        validate_admission_record(record, run_id="admission-test")


@pytest.mark.parametrize("level", ["record", "reference", "attempt", "diagnostic"])
def test_admission_artifact_schema_requires_every_key(level: str) -> None:
    from fa.inner_loop.admission_schema import AdmissionRecordError, validate_admission_record

    base = _admission_fixture()
    keys = {
        "record": set(base),
        "reference": set(base["plan_ref"]),
        "attempt": set(base["attempts"][0]),
        "diagnostic": {"validator", "rule", "severity", "line"},
    }[level]
    for missing in keys:
        record = _admission_fixture()
        target = {
            "record": record,
            "reference": record["plan_ref"],
            "attempt": record["attempts"][0],
            "diagnostic": record["attempts"][0]["diagnostics"][0],
        }[level]
        del target[missing]
        with pytest.raises(AdmissionRecordError):
            validate_admission_record(record, run_id="admission-test")


def test_admission_artifact_valid_history_preserves_old_admission_and_cas_chain() -> None:
    from fa.inner_loop.admission_schema import validate_admission_record

    record = _admission_fixture()
    record["attempts"].extend(
        [
            _admission_attempt(
                attempt=2,
                dispatch_kind="EVAL_REPLAN",
                validation="DIAGNOSTICS",
                route="RETRY",
                source_sha256="a" * 64,
                candidate_sha256="b" * 64,
                diagnostics=[
                    {"validator": "precheck", "rule": "slice-without-tests", "severity": "FAIL", "line": None}
                ],
            ),
            _admission_attempt(
                attempt=3,
                dispatch_kind="EVAL_REPLAN",
                validation="PASS",
                route="ADMITTED",
                source_sha256="a" * 64,
                candidate_sha256="c" * 64,
                promoted_sha256="c" * 64,
                diagnostics=[],
            ),
        ]
    )
    record["plan_ref"]["sha256"] = "c" * 64
    assert validate_admission_record(record, run_id="admission-test") == record
    record["attempts"][1]["source_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="invalid admission record"):
        validate_admission_record(record, run_id="admission-test")


def test_admission_artifact_initialization_append_and_modes(tmp_path: Path) -> None:
    from fa.inner_loop.workflow_artifacts import write_admission_record

    path = tmp_path / "private" / "admission.json"
    initial = write_admission_record(path, run_id="admission-test", plan_ref=None)
    assert initial == {
        "schema_version": 1,
        "run_id": "admission-test",
        "status": "ACQUIRING",
        "plan_ref": None,
        "attempts": [],
    }
    first = write_admission_record(
        path, run_id="admission-test", plan_ref=None, attempt=_admission_attempt(), status="BLOCKED"
    )
    second = write_admission_record(
        path, run_id="admission-test", plan_ref=None, attempt=_admission_attempt(), status="BLOCKED"
    )
    assert second["attempts"] == first["attempts"] + [_admission_attempt(attempt=2)]
    assert json.loads(path.read_bytes()) == second
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert (path.parent / ".admission.lock").stat().st_mode & 0o777 == 0o600
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.parametrize("bad", ["{broken", '{"schema_version":true}', '{"schema_version":1,"schema_version":2}'])
def test_admission_artifact_old_corruption_is_never_reset(tmp_path: Path, bad: str) -> None:
    from fa.inner_loop.workflow_artifacts import AdmissionIOError, write_admission_record

    path = tmp_path / "admission.json"
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(AdmissionIOError) as failure:
        write_admission_record(
            path, run_id="admission-test", plan_ref=None, attempt=_admission_attempt(), status="BLOCKED"
        )
    assert failure.value.rule == "corrupt-record"
    assert path.read_text(encoding="utf-8") == bad


@pytest.mark.parametrize("phase", ["file-fsync", "replace", "directory-fsync", "zero-write"])
def test_admission_artifact_publication_faults_preserve_irreversible_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str, bounded_admission_test: None
) -> None:
    import stat

    from fa.inner_loop.workflow_artifacts import AdmissionIOError, write_admission_record

    path = tmp_path / "admission.json"
    write_admission_record(path, run_id="admission-test", plan_ref=None)
    old = path.read_bytes()
    original_sync, original_replace = os.fsync, os.replace
    published = False

    def sync(fd: int) -> None:
        if phase == "file-fsync" and stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("injected file fsync")
        if phase == "directory-fsync" and published and stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("injected directory fsync")
        original_sync(fd)

    def replace(source: Any, target: Any, **kwargs: Any) -> None:
        nonlocal published
        if phase == "replace":
            raise OSError("injected replace")
        original_replace(source, target, **kwargs)
        published = True

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "replace", replace)
    if phase == "zero-write":
        monkeypatch.setattr(os, "write", lambda *_args: 0)
    with pytest.raises(AdmissionIOError) as failure:
        write_admission_record(
            path, run_id="admission-test", plan_ref=None, attempt=_admission_attempt(), status="BLOCKED"
        )
    assert failure.value.rule == ("durability-unknown" if phase == "directory-fsync" else "append-failed")
    if phase == "directory-fsync":
        assert json.loads(path.read_bytes())["attempts"] == [_admission_attempt(attempt=1)]
    else:
        assert path.read_bytes() == old
    assert not list(tmp_path.glob("*.tmp"))


def test_admission_artifact_lock_wait_is_bounded_and_does_not_modify_record(
    tmp_path: Path, bounded_admission_test: None
) -> None:
    import fcntl
    import time

    from fa.inner_loop.workflow_artifacts import AdmissionIOError, write_admission_record

    path = tmp_path / "admission.json"
    write_admission_record(path, run_id="admission-test", plan_ref=None)
    before = path.read_bytes()
    with (tmp_path / ".admission.lock").open("rb") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        started = time.monotonic()
        with pytest.raises(AdmissionIOError) as failure:
            write_admission_record(
                path,
                run_id="admission-test",
                plan_ref=None,
                attempt=_admission_attempt(),
                status="BLOCKED",
                deadline=started + 0.04,
            )
        assert failure.value.rule == "lock-failed"
        assert time.monotonic() - started < 1
    assert path.read_bytes() == before


def test_admission_artifact_concurrent_subprocess_appends_do_not_lose_attempts(tmp_path: Path) -> None:
    import subprocess
    import sys

    from fa.inner_loop import workflow_artifacts as artifacts
    from fa.inner_loop.admission_schema import validate_admission_record

    path = tmp_path / "admission.json"
    source_root = str(Path(artifacts.__file__).resolve().parents[2])
    child_env = os.environ | {"PYTHONPATH": os.pathsep.join((source_root, os.environ.get("PYTHONPATH", "")))}
    script = (
        "from pathlib import Path; import sys\n"
        "from fa.inner_loop import workflow_artifacts as artifacts\n"
        "from fa.inner_loop.workflow_artifacts import write_admission_record\n"
        "assert Path(artifacts.__file__).resolve().is_relative_to(Path(sys.argv[2]).resolve())\n"
        f"attempt = {_admission_attempt()!r}\n"
        "for _ in range(4):\n"
        "    write_admission_record(Path(sys.argv[1]), run_id='admission-test', "
        "plan_ref=None, attempt=attempt, status='BLOCKED')\n"
    )
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(path), source_root],
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(4)
    ]
    try:
        for process in processes:
            out, err = process.communicate(timeout=15)
            assert (process.returncode, out, err) == (0, b"", b"")
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait()
    record = validate_admission_record(json.loads(path.read_bytes()), run_id="admission-test")
    assert [item["attempt"] for item in record["attempts"]] == list(range(1, 17))


@pytest.mark.parametrize(
    "kind,rule",
    [("missing", "missing"), ("outside", "path-escape"), ("invalid-utf8", "invalid-utf8"), ("symlink", "symlink")],
)
@pytest.mark.parametrize("mode", ["linear", "adaptive"])
@pytest.mark.parametrize("gate_mode", ["observe", "enforce"])
def test_direct_api_plan_guard_persists_blocked_before_real_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    rule: str,
    mode: str,
    gate_mode: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from fa import feature_flags
    from fa.cli import _cmd_run

    flag_path = tmp_path / "flags.yaml"
    flag_path.write_text(f"feature_flags:\n  workflow:\n    verify_gate:\n      mode: {gate_mode}\n", encoding="utf-8")
    monkeypatch.setattr(feature_flags, "DEFAULT_CONFIG_PATH", flag_path)

    state, workspace = tmp_path / "state", tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("FA_STATE_ROOT", str(state))
    config = tmp_path / "models.yaml"
    config.write_text("".join(_ROLE_YAML.format(role=r) for r in ("planner", "coder", "eval")), encoding="utf-8")
    target: Path | None = None
    if kind == "outside":
        target = tmp_path / "private-sentinel.md"
        target.write_text("fixture private bytes", encoding="utf-8")
    elif kind == "invalid-utf8":
        target = workspace / "plan.md"
        target.write_bytes(b"\xff")
    elif kind == "symlink":
        target = workspace / "plan.md"
        target.symlink_to(workspace / "absent.md")
    calls: list[str] = []

    def provider(
        chain: ProviderChain, request: RequestInfo, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        calls.append(chain.config.role)
        return ResponseInfo(text=_EVAL_FINAL_TEXT, in_tokens=1, out_tokens=1, finish_reason="stop"), "p", []

    monkeypatch.setattr(ProviderChain, "request", provider)
    result, flow = run_workflow(
        **(_request_input() | {"mode": mode}),
        config=config,
        workspace=workspace,
        max_turns=1,
        run_stage_fn=_cmd_run,
        plan_path=target,
        secrets=SecretStore({"K": "fixture-key"}),
    )
    assert result == 2
    assert flow is not None and flow.status == "FAILED" and flow.last_route_decision == "blocked"
    assert flow.blocked_reason == f"plan-ref/{rule}"
    assert flow == FlowState(
        run_id="request-valid",
        task="implement the declared plan",
        status="FAILED",
        active_role="workflow",
        active_plan_id="request-valid",
        active_plan_version=1,
        last_actor="workflow",
        last_transition_reason="explicit plan admission blocked",
        last_route_decision="blocked",
        blocked_reason=f"plan-ref/{rule}",
        judged=False,
    )
    assert calls == []
    directory = state / "session-log" / "request-valid"
    record = json.loads((directory / "admission.json").read_bytes())
    assert record == {
        "schema_version": 1,
        "run_id": "request-valid",
        "status": "BLOCKED",
        "plan_ref": None,
        "attempts": [
            _admission_attempt(
                attempt=1, diagnostics=[{"validator": "plan-ref", "rule": rule, "severity": "ERROR", "line": None}]
            )
        ],
    }
    assert load_flow_state(directory / "flow_state.json") == flow
    assert not (directory / "verification.json").exists()
    assert not (directory / "verify_baseline.json").exists()
    assert not (directory / "eval_report.json").exists()
    assert "private-sentinel" not in (directory / "admission.json").read_text()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"fa workflow: invalid plan reference: {rule}\n"


@pytest.mark.parametrize(
    "kind",
    ["ancestor", "record-link", "lock-link", "record-hardlink", "lock-hardlink", "record-directory", "lock-fifo"],
)
def test_admission_artifact_hostile_paths_never_touch_outside(tmp_path: Path, kind: str) -> None:
    from fa.inner_loop.workflow_artifacts import AdmissionIOError, write_admission_record

    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text(
        json.dumps(
            {"schema_version": 1, "run_id": "admission-test", "status": "ACQUIRING", "plan_ref": None, "attempts": []}
        ),
        encoding="utf-8",
    )
    sentinel.chmod(0o640)
    parent = tmp_path / "record"
    if kind == "ancestor":
        parent.symlink_to(outside, target_is_directory=True)
    else:
        parent.mkdir()
        target = parent / (".admission.lock" if kind.startswith("lock") else "admission.json")
        if kind.endswith("link") and "hardlink" not in kind:
            target.symlink_to(sentinel)
        elif kind.endswith("hardlink"):
            os.link(sentinel, target)
        elif kind == "record-directory":
            target.mkdir()
        else:
            os.mkfifo(target)
    before = {p.name: (p.read_bytes(), p.stat().st_mode) for p in outside.iterdir()}
    with pytest.raises(AdmissionIOError) as failure:
        write_admission_record(
            parent / "admission.json",
            run_id="admission-test",
            plan_ref=None,
            attempt=_admission_attempt(),
            status="BLOCKED",
        )
    expected_rule = (
        "lock-failed"
        if kind.startswith("lock")
        else "corrupt-record"
        if kind in {"record-directory", "record-hardlink"}
        else "append-failed"
    )
    assert failure.value.rule == expected_rule
    assert {p.name: (p.read_bytes(), p.stat().st_mode) for p in outside.iterdir()} == before


def test_admission_artifact_temp_collision_is_not_owned_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop import workflow_artifacts as artifacts

    path = tmp_path / "admission.json"
    artifacts.write_admission_record(path, run_id="admission-test", plan_ref=None)
    before = path.read_bytes()
    collision = tmp_path / ".admission.json.collision.tmp"
    collision.write_bytes(b"someone else's file")
    monkeypatch.setattr(artifacts, "uuid4", lambda: SimpleNamespace(hex="collision"))
    with pytest.raises(artifacts.AdmissionIOError) as failure:
        artifacts.write_admission_record(
            path, run_id="admission-test", plan_ref=None, attempt=_admission_attempt(), status="BLOCKED"
        )
    assert failure.value.rule == "append-failed"
    assert collision.read_bytes() == b"someone else's file"
    assert path.read_bytes() == before


def test_admission_artifact_short_writes_and_unchanged_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import copy

    from fa.inner_loop.workflow_artifacts import write_admission_record

    original_write = os.write
    monkeypatch.setattr(os, "write", lambda fd, raw: original_write(fd, raw[:3]))
    proposal = _admission_attempt()
    before = copy.deepcopy(proposal)
    path = tmp_path / "admission.json"
    value = write_admission_record(path, run_id="admission-test", plan_ref=None, attempt=proposal, status="BLOCKED")
    assert value["attempts"] == [proposal | {"attempt": 1}]
    assert json.loads(path.read_bytes()) == value
    assert proposal == before


@pytest.mark.parametrize("run_id", ["", "../outside", "a" * 129, "a\n"])
def test_admission_artifact_invalid_identity_precedes_directory_creation(tmp_path: Path, run_id: str) -> None:
    from fa.inner_loop.admission_schema import AdmissionRecordError
    from fa.inner_loop.workflow_artifacts import write_admission_record

    directory = tmp_path / "not-created"
    with pytest.raises(AdmissionRecordError):
        write_admission_record(directory / "admission.json", run_id=run_id, plan_ref=None)
    assert not directory.exists()


def test_admission_artifact_valid_diagnostic_vocabulary_and_reserved_values() -> None:
    from fa.inner_loop.admission_schema import ADMISSION_RULES, validate_admission_record

    expected = {
        "precheck": {
            "heading-near-miss",
            "step-marker-unknown",
            "step-near-miss",
            "slice-count-at-ceiling",
            "orphaned-slice-field",
            "slice-without-tests",
            "step-without-exit",
            "deps-undefined-slice",
            "deps-cycle",
            "contract-reference-undeclared",
            "contract-declared-twice",
            "contract-declaration-lost",
        },
        "kill-directives": {
            "kill-directive-near-miss",
            "kill-directive-malformed",
            "kill-directive-ambiguous",
            "kill-directive-missing",
        },
        "plan-ref": {
            "missing",
            "path-escape",
            "symlink",
            "not-regular",
            "unreadable",
            "invalid-utf8",
            "empty",
            "too-large",
            "zero-slices",
            "source-changed",
            "validator-error",
        },
        "promotion": {
            "scope-denied",
            "symlink",
            "not-regular",
            "source-changed",
            "prepare-failed",
            "replace-failed",
            "durability-unknown",
            "hash-mismatch",
        },
        "artifact-io": {"corrupt-record", "lock-failed", "append-failed", "durability-unknown"},
        "bootstrap": {"unavailable"},
    }
    assert ADMISSION_RULES == expected
    for validator, rules in expected.items():
        for rule in rules:
            record = _admission_fixture()
            record["status"] = "BLOCKED"
            record["attempts"][0].update(
                validation="INDETERMINATE",
                route="BLOCKED",
                diagnostics=[
                    {"validator": validator, "rule": rule, "severity": "ERROR", "line": None},
                ],
            )
            assert validate_admission_record(record, run_id="admission-test") == record


@pytest.mark.parametrize("fault", ["admission-only", "unsafe-directory"])
def test_direct_api_plan_guard_storage_failure_is_explicit_and_never_dispatches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    from fa.cli import _cmd_run
    from fa.inner_loop import workflow_artifacts as artifacts

    state = tmp_path / "state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state))
    outside = tmp_path / "outside"
    outside.mkdir()
    if fault == "unsafe-directory":
        (state / "session-log").mkdir(parents=True)
        (state / "session-log" / "request-valid").symlink_to(outside, target_is_directory=True)
    else:
        original = artifacts._replace_private_json

        def reject_admission(directory_fd: int, name: str, payload: dict[str, Any]) -> None:
            if name == "admission.json":
                raise artifacts.AdmissionIOError("append-failed")
            original(directory_fd, name, payload)

        monkeypatch.setattr(artifacts, "_replace_private_json", reject_admission)
    code, flow = run_workflow(
        **_request_input(), config=tmp_path / "models.yaml", workspace=tmp_path, max_turns=1, run_stage_fn=_cmd_run
    )
    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    expected_error = (
        "fa workflow: invalid plan reference: missing\nfa workflow: admission storage error: append-failed\n"
    )
    if fault == "unsafe-directory":
        expected_error += "fa workflow: blocked flow storage error: append-failed\n"
    assert captured.err == expected_error
    assert (flow is not None) == (fault == "admission-only")
    assert not list(outside.iterdir())
    assert not (state / "session-log" / "request-valid" / "admission.json").exists()


@pytest.fixture()
def bounded_admission_test() -> Iterator[None]:
    """Make a wedged storage operation a test failure, not mutation-runner evidence."""
    import signal

    def expired(_signum: int, _frame: object) -> None:
        raise AssertionError("admission storage test exceeded its bounded operation window")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 2)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@pytest.mark.parametrize("validation", ["PASS", "DIAGNOSTICS", "INDETERMINATE"])
@pytest.mark.parametrize("route", ["ADMITTED", "RETRY", "BLOCKED"])
@pytest.mark.parametrize(
    "severities", [(), ("WARN",), ("FAIL",), ("ERROR",), ("FAIL", "WARN"), ("ERROR", "WARN"), ("FAIL", "ERROR", "WARN")]
)
def test_admission_artifact_validation_route_truth_table(
    validation: str, route: str, severities: tuple[str, ...]
) -> None:
    from fa.inner_loop.admission_schema import AdmissionRecordError, validate_admission_record

    allowed = {
        ("PASS", "ADMITTED", ()),
        ("PASS", "ADMITTED", ("WARN",)),
        ("PASS", "BLOCKED", ()),
        ("PASS", "BLOCKED", ("WARN",)),
        ("DIAGNOSTICS", "RETRY", ("FAIL",)),
        ("DIAGNOSTICS", "RETRY", ("FAIL", "WARN")),
        ("DIAGNOSTICS", "BLOCKED", ("FAIL",)),
        ("DIAGNOSTICS", "BLOCKED", ("FAIL", "WARN")),
        *(
            ("INDETERMINATE", "BLOCKED", values)
            for values in [
                (),
                ("WARN",),
                ("FAIL",),
                ("ERROR",),
                ("FAIL", "WARN"),
                ("ERROR", "WARN"),
                ("FAIL", "ERROR", "WARN"),
            ]
        ),
    }
    record = _admission_fixture()
    record["status"] = {"ADMITTED": "ADMITTED", "RETRY": "ACQUIRING", "BLOCKED": "BLOCKED"}[route]
    record["attempts"][0].update(
        validation=validation,
        route=route,
        diagnostics=[
            {"validator": "precheck", "rule": "step-near-miss", "severity": severity, "line": 1}
            for severity in severities
        ],
    )
    if (validation, route, severities) in allowed:
        assert validate_admission_record(record, run_id="admission-test") == record
    else:
        with pytest.raises(AdmissionRecordError):
            validate_admission_record(record, run_id="admission-test")


@pytest.mark.parametrize("source_kind", ["EXPLICIT", "EXISTING_SELECTION", "BOOTSTRAP"])
def test_admission_artifact_initial_ref_is_checked_without_history(source_kind: str) -> None:
    from fa.inner_loop.admission_schema import AdmissionRecordError, validate_admission_record

    record = _admission_fixture()
    record.update(run_id="Run-1", status="ACQUIRING", attempts=[])
    record["plan_ref"]["source_kind"] = source_kind
    assert validate_admission_record(record, run_id="Run-1") == record
    for malformed in ["A" * 64, "a" * 63, True, 4, "a" * 65, []]:
        record["plan_ref"]["sha256"] = malformed
        with pytest.raises(AdmissionRecordError):
            validate_admission_record(record, run_id="Run-1")


@pytest.mark.parametrize("kind", ["ADMISSION_REPAIR", "EVAL_REPLAN"])
@pytest.mark.parametrize(
    "fault", ["none", "bad-source", "bad-candidate", "bad-promoted", "unpromoted", "failed-promotion"]
)
def test_admission_artifact_promotion_hash_coherence(kind: str, fault: str) -> None:
    from fa.inner_loop.admission_schema import AdmissionRecordError, validate_admission_record

    record = _admission_fixture()
    record["plan_ref"]["sha256"] = "b" * 64
    item = _admission_attempt(
        attempt=2,
        dispatch_kind=kind,
        source_sha256="a" * 64,
        candidate_sha256="b" * 64,
        promoted_sha256="b" * 64,
        validation="PASS",
        route="ADMITTED",
        diagnostics=[],
    )
    record["attempts"].append(item)
    if fault == "bad-source":
        item["source_sha256"] = "c" * 64
    elif fault == "bad-candidate":
        item["candidate_sha256"] = "c" * 64
    elif fault == "bad-promoted":
        item["candidate_sha256"] = item["promoted_sha256"] = record["plan_ref"]["sha256"] = "invalid"
    elif fault == "unpromoted":
        item["promoted_sha256"] = None
        record["plan_ref"]["sha256"] = "a" * 64
    elif fault == "failed-promotion":
        item.update(
            validation="DIAGNOSTICS",
            route="BLOCKED",
            diagnostics=[{"validator": "precheck", "rule": "step-near-miss", "severity": "FAIL", "line": 1}],
        )
        record["status"] = "BLOCKED"
    if fault == "none":
        assert validate_admission_record(record, run_id="admission-test") == record
    else:
        with pytest.raises(AdmissionRecordError):
            validate_admission_record(record, run_id="admission-test")


def test_admission_artifact_explicit_history_cannot_forget_canonical_or_admit_null() -> None:
    from fa.inner_loop.admission_schema import AdmissionRecordError, validate_admission_record

    record = _admission_fixture()
    record["attempts"].append(record["attempts"][0] | {"attempt": 2})
    assert validate_admission_record(record, run_id="admission-test") == record
    record["attempts"][1]["source_sha256"] = record["plan_ref"]["sha256"] = "b" * 64
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="admission-test")
    record = _admission_fixture()
    record["plan_ref"] = None
    record["attempts"][0]["source_sha256"] = None
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="admission-test")
    record = {
        "schema_version": 1,
        "run_id": "admission-test",
        "status": "BLOCKED",
        "plan_ref": None,
        "attempts": [_admission_attempt(attempt=1, dispatch_kind="ACQUISITION")],
    }
    assert validate_admission_record(record, run_id="admission-test") == record


def test_admission_artifact_duplicate_valid_record_is_not_last_key_wins(tmp_path: Path) -> None:
    from fa.inner_loop.workflow_artifacts import AdmissionIOError, write_admission_record

    path = tmp_path / "admission.json"
    record = write_admission_record(path, run_id="admission-test", plan_ref=None)
    bad = '{"schema_version":2,' + json.dumps(record)[1:]
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(AdmissionIOError) as failure:
        write_admission_record(
            path, run_id="admission-test", plan_ref=None, attempt=_admission_attempt(), status="BLOCKED"
        )
    assert failure.value.rule == "corrupt-record"
    assert str(failure.value) == "admission storage error: corrupt-record"
    assert path.read_text(encoding="utf-8") == bad


def test_admission_artifact_requests_safe_descriptor_flags_and_private_create_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop.workflow_artifacts import write_admission_record

    path = tmp_path / "admission.json"
    write_admission_record(path, run_id="admission-test", plan_ref=None)
    original = os.open
    seen: list[tuple[str, int, int]] = []

    def opened(name: Any, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
        seen.append((str(name), flags, mode))
        return original(name, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", opened)
    write_admission_record(path, run_id="admission-test", plan_ref=None, attempt=_admission_attempt(), status="BLOCKED")
    reads = [flags for name, flags, _ in seen if name == "admission.json"]
    assert reads and all(
        flags & (os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK) == os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        for flags in reads
    )
    creates = [(flags, mode) for name, flags, mode in seen if name.endswith(".tmp")]
    assert creates and all(
        mode == 0o600
        and flags & (os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC)
        == os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
        for flags, mode in creates
    )


def test_admission_artifact_controller_barrier_preserves_reference_and_deadline(
    tmp_path: Path, bounded_admission_test: None
) -> None:
    import fcntl
    import time
    from dataclasses import asdict

    from fa.inner_loop.plan_admission import PlanRef
    from fa.inner_loop.workflow_artifacts import AdmissionIOError, write_admission_record

    paths = workflow_artifact_paths("admission-test", base_dir=tmp_path)
    ref = PlanRef("планы/p.md", "EXPLICIT", "a" * 64)
    write_admission_record(paths.admission, run_id="admission-test", plan_ref=ref)
    proposal = _admission_attempt(validation="PASS", route="ADMITTED", source_sha256="a" * 64, diagnostics=[])
    workflow._record_admission_attempt(
        paths, run_id="admission-test", plan_ref=ref, attempt=proposal, status="ADMITTED", deadline=time.monotonic() + 1
    )
    record = json.loads(paths.admission.read_bytes())
    assert record["plan_ref"] == asdict(ref)
    assert record["attempts"] == [proposal | {"attempt": 1}]
    before = paths.admission.read_bytes()
    with (tmp_path / ".admission.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with pytest.raises(AdmissionIOError) as failure:
            workflow._record_admission_attempt(
                paths,
                run_id="admission-test",
                plan_ref=ref,
                attempt=proposal,
                status="ADMITTED",
                deadline=time.monotonic() - 1,
            )
        assert failure.value.rule == "lock-failed"
    assert paths.admission.read_bytes() == before


@pytest.mark.parametrize(
    "change", [{"attempt": 55}, {"extra": "source body"}, {"diagnostics": [{"message": "source body"}]}]
)
def test_admission_artifact_bad_proposal_does_not_overwrite_history(tmp_path: Path, change: dict[str, Any]) -> None:
    from fa.inner_loop.workflow_artifacts import AdmissionIOError, write_admission_record

    path = tmp_path / "admission.json"
    write_admission_record(path, run_id="admission-test", plan_ref=None)
    before = path.read_bytes()
    with pytest.raises(AdmissionIOError) as failure:
        write_admission_record(
            path, run_id="admission-test", plan_ref=None, attempt=_admission_attempt(**change), status="BLOCKED"
        )
    assert failure.value.rule == "corrupt-record"
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory"])
def test_admission_artifact_shared_flow_writer_rejects_aliased_controls(tmp_path: Path, kind: str) -> None:
    from fa.inner_loop.workflow_artifacts import AdmissionIOError, FlowState, write_flow_state

    outside = tmp_path / "outside"
    outside.write_bytes(b"private bytes")
    parent = tmp_path / "records"
    parent.mkdir()
    target = parent / "flow_state.json"
    if kind == "symlink":
        target.symlink_to(outside)
    elif kind == "hardlink":
        os.link(outside, target)
    else:
        target.mkdir()
    with pytest.raises(AdmissionIOError) as failure:
        write_flow_state(
            target,
            FlowState(
                run_id="admission-test",
                task="blocked",
                status="FAILED",
                active_role="workflow",
                active_plan_id="admission-test",
                active_plan_version=1,
            ),
        )
    assert failure.value.rule == "append-failed"
    assert outside.read_bytes() == b"private bytes"


@pytest.mark.parametrize("location", ["directory", "record", "record-kind"])
def test_admission_artifact_foreign_owner_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, location: str
) -> None:
    import stat

    from fa.inner_loop.workflow_artifacts import AdmissionIOError, write_admission_record

    path = tmp_path / "admission.json"
    write_admission_record(path, run_id="admission-test", plan_ref=None)
    before = path.read_bytes()
    original = os.fstat

    def metadata(fd: int) -> Any:
        result = original(fd)
        wanted = (
            stat.S_ISDIR(result.st_mode) if location == "directory" else os.readlink(f"/proc/self/fd/{fd}") == str(path)
        )
        if wanted:
            return SimpleNamespace(
                st_mode=stat.S_IFIFO | 0o600 if location == "record-kind" else result.st_mode,
                st_uid=os.getuid() if location == "record-kind" else os.getuid() + 1,
                st_nlink=result.st_nlink,
            )
        return result

    monkeypatch.setattr(os, "fstat", metadata)
    with pytest.raises(AdmissionIOError) as failure:
        write_admission_record(
            path, run_id="admission-test", plan_ref=None, attempt=_admission_attempt(), status="BLOCKED"
        )
    assert failure.value.rule == ("append-failed" if location == "directory" else "corrupt-record")
    assert path.read_bytes() == before


def test_admission_artifact_rejected_candidate_digest_is_still_checked() -> None:
    from fa.inner_loop.admission_schema import AdmissionRecordError, validate_admission_record

    record = _admission_fixture()
    record["status"] = "ACQUIRING"
    record["attempts"].append(
        _admission_attempt(
            attempt=2,
            dispatch_kind="ADMISSION_REPAIR",
            source_sha256="a" * 64,
            candidate_sha256="invalid",
            validation="DIAGNOSTICS",
            route="RETRY",
            diagnostics=[{"validator": "precheck", "rule": "step-near-miss", "severity": "FAIL", "line": 1}],
        )
    )
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="admission-test")


def test_direct_api_plan_guard_context_directory_and_expired_admission_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import time

    from fa.cli import _cmd_run
    from fa.session.manager import RunContext

    state = tmp_path / "state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state))
    context = RunContext(
        run_id="request-valid",
        session_id="request-session",
        workspace_path=tmp_path,
        session_db_path=tmp_path / "session.db",
        run_log_dir=tmp_path / "private-run",
    )
    code, flow = run_workflow(
        **(
            _request_input()
            | {
                "task": None,
                "per_role_task": dict.fromkeys(["planner", "coder", "eval"], "role task"),
            }
        ),
        config=tmp_path / "models.yaml",
        workspace=tmp_path,
        max_turns=1,
        run_stage_fn=_cmd_run,
        run_context=context,
        deadline_mono=time.monotonic() - 1,
    )
    assert code == 2
    assert flow is not None and flow.task == "" and flow.blocked_reason == "plan-ref/missing"
    assert load_flow_state(context.run_log_dir / "flow_state.json") == flow
    assert not (context.run_log_dir / "admission.json").exists()
    assert not state.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        captured.err
        == "fa workflow: invalid plan reference: missing\nfa workflow: admission storage error: lock-failed\n"
    )


def test_direct_api_plan_guard_schema_storage_error_has_sanitized_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from fa.cli import _cmd_run
    from fa.inner_loop.admission_schema import AdmissionRecordError

    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path / "state"))

    def rejected(*_args: Any, **_kwargs: Any) -> Any:
        raise AdmissionRecordError

    # C0 injected storage-schema failure, supplementing the real-writer root cases.
    monkeypatch.setattr(workflow, "write_admission_record", rejected)
    code, flow = run_workflow(
        **_request_input(), config=tmp_path / "models.yaml", workspace=tmp_path, max_turns=1, run_stage_fn=_cmd_run
    )
    assert code == 2 and flow is not None and flow.status == "FAILED"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        captured.err
        == "fa workflow: invalid plan reference: missing\nfa workflow: admission storage error: append-failed\n"
    )


def test_admission_artifact_utf8_read_is_independent_of_process_locale(tmp_path: Path) -> None:
    import subprocess
    import sys

    from fa.inner_loop import workflow_artifacts as artifacts
    from fa.inner_loop.plan_admission import PlanRef
    from fa.inner_loop.workflow_artifacts import write_admission_record

    path = tmp_path / "admission.json"
    source_root = str(Path(artifacts.__file__).resolve().parents[2])
    ref = PlanRef("планы/p.md", "EXPLICIT", "a" * 64)
    write_admission_record(path, run_id="admission-test", plan_ref=ref)
    script = (
        "import sys, locale; from pathlib import Path\n"
        "from fa.inner_loop.plan_admission import PlanRef\n"
        "from fa.inner_loop import workflow_artifacts as artifacts\n"
        "from fa.inner_loop.workflow_artifacts import write_admission_record\n"
        "assert Path(artifacts.__file__).resolve().is_relative_to(Path(sys.argv[2]).resolve())\n"
        "assert locale.getencoding().lower() not in ('utf-8', 'utf8')\n"
        f"ref=PlanRef({ref.workspace_relative_path!a}, 'EXPLICIT', 'a'*64)\n"
        f"attempt={_admission_attempt(validation='PASS', route='ADMITTED', source_sha256='a' * 64, diagnostics=[])!r}\n"
        "write_admission_record(Path(sys.argv[1]), run_id='admission-test', "
        "plan_ref=ref, attempt=attempt, status='ADMITTED')\n"
    )
    child = subprocess.run(
        [sys.executable, "-c", script, str(path), source_root],
        env=os.environ
        | {
            "LC_ALL": "C",
            "PYTHONUTF8": "0",
            "PYTHONCOERCECLOCALE": "0",
            "PYTHONPATH": os.pathsep.join((source_root, os.environ.get("PYTHONPATH", ""))),
        },
        capture_output=True,
        timeout=10,
    )
    assert (child.returncode, child.stdout, child.stderr) == (0, b"", b"")
    assert json.loads(path.read_bytes())["attempts"][0]["route"] == "ADMITTED"


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_admission_artifact_shared_eval_writer_rejects_non_json_numbers(tmp_path: Path, value: float) -> None:
    from dataclasses import replace

    from fa.inner_loop.workflow_artifacts import write_eval_report

    path = tmp_path / "eval_report.json"
    report = _eval_report()
    write_eval_report(path, report)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        write_eval_report(path, replace(report, eval_independence={"disjoint": True, "invalid_number": value}))
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


# CT93 prerequisite: C0 capability/descriptor negatives and C1/C3 real-session
# consumer proof. No admission/repair orchestration claim is made by these tests.
@pytest.mark.parametrize("kind", ["ADMISSION_REPAIR", "EVAL_REPLAN"])
@pytest.mark.parametrize(
    "target",
    [
        "",
        "/.fa/admission/ct93/p.md",
        ".fa//admission/ct93/p.md",
        ".fa/admission/other/p.md",
        ".fa/admission/ct93",
        ".fa/admission/ct93/../p.md",
        ".fa/admission/ct93/./p.md",
        ".fa/admission/ct93/p.md/",
        ".fa/admission/ct93/p\x00.md",
    ],
)
def test_ct93_rejects_noncanonical_capabilities(kind: str, target: str) -> None:
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchError, PlannerDispatchKind

    with pytest.raises(PlannerDispatchError, match=r"^invalid planner dispatch$"):
        PlannerDispatch(PlannerDispatchKind(kind), "ct93", candidate_target=target)


@pytest.mark.parametrize("obstacle", ["ancestor", "terminal", "hardlink", "fifo", "directory"])
def test_ct93_descriptor_writer_preserves_unsafe_targets(tmp_path: Path, obstacle: str) -> None:
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.tools.write_file import build_scoped_write_file_tool

    target = ".fa/admission/ct93/candidate.md"
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(b"unchanged")
    candidate = tmp_path / target
    candidate.parent.mkdir(parents=True)
    if obstacle == "ancestor":
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "candidate.md").write_bytes(b"unchanged")
        candidate.parent.rmdir()
        candidate.parent.symlink_to(elsewhere, target_is_directory=True)
    elif obstacle == "terminal":
        candidate.symlink_to(sentinel)
    elif obstacle == "hardlink":
        os.link(sentinel, candidate)
    elif obstacle == "fifo":
        os.mkfifo(candidate)
    else:
        candidate.mkdir()
    tool = build_scoped_write_file_tool(
        tmp_path, PlannerDispatch(PlannerDispatchKind.ADMISSION_REPAIR, "ct93", candidate_target=target)
    )
    result = tool.handler({"path": target, "content": "replaced"})
    assert result.error is not None and result.error.retryable is False
    assert sentinel.read_bytes() == b"unchanged"
    if obstacle == "ancestor":
        assert (tmp_path / "elsewhere/candidate.md").read_bytes() == b"unchanged"
    elif obstacle in {"terminal", "hardlink"}:
        assert candidate.read_bytes() == b"unchanged"
    assert not list(candidate.parent.glob(".*.tmp"))


def test_ct93_scoped_handler_rejects_wrong_path_and_content(tmp_path: Path) -> None:
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.tools.write_file import build_scoped_write_file_tool

    target = ".fa/admission/ct93/candidate.md"
    tool = build_scoped_write_file_tool(
        tmp_path, PlannerDispatch(PlannerDispatchKind.EVAL_REPLAN, "ct93", candidate_target=target)
    )
    for path in [target + ".other", ".fa/note.md", "src/x.py", ".fa/admission/ct93/./candidate.md"]:
        result = tool.handler({"path": path, "content": "bad"})
        assert result.error is not None and result.error.code == "scope_denied"
    for content in [None, 1, "\ud800"]:
        result = tool.handler({"path": target, "content": content})
        assert result.error is not None and result.error.code == "write_failed"
    assert not (tmp_path / ".fa").exists()
    assert tool.handler({"path": target, "content": "первая\n"}).error is None
    assert tool.handler({"path": target, "content": "second\n"}).error is None
    assert (tmp_path / target).read_bytes() == b"second\n"
    assert (tmp_path / target).stat().st_mode & 0o777 == 0o600
    assert (tmp_path / target).parent.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize(
    "kind,obstacle",
    [
        ("ORDINARY_PLANNING", "none"),
        ("ADMISSION_REPAIR", "none"),
        ("EVAL_REPLAN", "none"),
        ("ADMISSION_REPAIR", "ancestor"),
        ("ADMISSION_REPAIR", "terminal"),
        ("EVAL_REPLAN", "hardlink"),
    ],
)
def test_ct93_real_stage_dispatch_controls_candidate_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, obstacle: str
) -> None:
    """C1/C3: only provider IO replaced; real stage/CLI/registry/session/hooks/FS.

    CT93 producer kill: profiles._build_tool_builders -> build_scoped_write_file_tool.
    Removing that producer leaves the ordinary limited tool, so the candidate
    effect and provider-visible exact-target schema fail this same live oracle.
    """
    from dataclasses import replace

    from fa.cli import _cmd_run
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind

    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
    ctx = _context(tmp_path, run_id="ct93")
    ctx.config.write_text(_ROLE_YAML.format(role="planner"), encoding="utf-8")
    active = ".fa/active.md"
    target = ".fa/admission/ct93/candidate.md"
    (tmp_path / active).parent.mkdir()
    (tmp_path / active).write_bytes(b"Plan-ID: PLAN-ct93\nprotected\n")
    (tmp_path / ".fa/active-alias.md").symlink_to(tmp_path / active)
    os.link(tmp_path / active, tmp_path / ".fa/active-hardlink.md")
    (tmp_path / target).parent.mkdir(parents=True)
    (tmp_path / target).write_bytes(b"old candidate")
    (tmp_path / ".fa/admission-alias").symlink_to(tmp_path / ".fa/admission", target_is_directory=True)
    # Reserved lexical paths must also stay denied when a symlink exits storage.
    (tmp_path / ".fa/admission/escape").symlink_to(tmp_path / ".fa", target_is_directory=True)
    if obstacle == "ancestor":
        (tmp_path / target).parent.rename(tmp_path / "elsewhere")
        (tmp_path / target).parent.symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    elif obstacle in {"terminal", "hardlink"}:
        (tmp_path / target).unlink()
        if obstacle == "terminal":
            (tmp_path / target).symlink_to(tmp_path / active)
        else:
            os.link(tmp_path / active, tmp_path / target)
    protected = [active, ".fa/active-alias.md", ".fa/active-hardlink.md"]
    paths = [
        *protected,
        target,
        ".fa/admission-alias/ct93/candidate.md",
        ".fa/admission/escape/escaped.md",
        ".fa/note.md",
        "knowledge/research/note.md",
        "src/forbidden.py",
        "worklogs/forbidden.md",
    ]
    requests: list[RequestInfo] = []

    def provider_request(
        _chain: ProviderChain, request: RequestInfo, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        requests.append(request)
        calls: tuple[dict[str, Any], ...] = ()
        if len(requests) == 1:
            calls = (
                {
                    "id": "prepare-ct93",
                    "type": "function",
                    "function": {
                        "name": "pr_prepare",
                        "arguments": json.dumps(
                            {"intent": "IMPLEMENT", "invariant": "Implements: CT93 exact-target writer"}
                        ),
                    },
                },
            )
        elif len(requests) == 2:
            calls = tuple(
                {
                    "id": f"ct93-{i}",
                    "type": "function",
                    "function": {
                        "name": "fs_write_file",
                        "arguments": json.dumps({"path": path, "content": "new bytes\n"}),
                    },
                }
                for i, path in enumerate(paths)
            )
        return (
            ResponseInfo("done" if not calls else "", 1, 1, "tool_calls" if calls else "stop", calls),
            logical_call_id or "ct93",
            [],
        )

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    ordinary = kind == "ORDINARY_PLANNING"
    dispatch = None if ordinary else PlannerDispatch(PlannerDispatchKind(kind), "ct93", active, target)
    ctx = replace(ctx, max_turns=20, plan_path=tmp_path / active, secrets=SecretStore({"K": "sk-test-live"}))
    outcome = _run_stage(
        ctx,
        "planner",
        fresh=True,
        transition_reason="ct93-test",
        progress=WorkflowProgress(),
        run_stage_fn=_cmd_run,
        planner_dispatch=dispatch,
    )
    assert outcome.exit_code == 0
    assert len(requests) == 3
    schemas = [item["function"] for item in requests[0].tools if item["function"]["name"] == "fs_write_file"]
    assert len(schemas) == 1
    if not ordinary:
        assert schemas[0]["parameters"]["properties"]["path"]["enum"] == [target]
        assert schemas[0]["parameters"]["additionalProperties"] is False
    expected = b"old candidate" if ordinary or obstacle == "ancestor" else b"new bytes\n"
    if obstacle in {"terminal", "hardlink"}:
        expected = b"Plan-ID: PLAN-ct93\nprotected\n"
    assert (tmp_path / target).read_bytes() == expected
    events = [json.loads(line) for line in (tmp_path / "state/session-log/ct93/events.jsonl").read_text().splitlines()]
    results = {event["tool_call_id"]: event["content"] for event in events if event["kind"] == "tool_result"}
    assert results["prepare-ct93"]["ok"] is True
    if obstacle != "none":
        assert results["ct93-3"]["error"]["code"] == "write_failed", (
            "descriptor rejection must not be attributed to hooks"
        )
        assert results["ct93-3"]["error"]["retryable"] is False
    elif not ordinary:
        assert results["ct93-3"]["ok"] is True
    else:
        assert results["ct93-3"]["error"]["code"] == "path_denied"
        assert results["ct93-6"]["ok"] is True and results["ct93-7"]["ok"] is True

    for path in protected:
        assert (tmp_path / path).read_bytes() == b"Plan-ID: PLAN-ct93\nprotected\n"
    for path in [".fa/note.md", "knowledge/research/note.md"]:
        assert (tmp_path / path).exists() is ordinary
        if ordinary:
            assert (tmp_path / path).read_bytes() == b"new bytes\n"
    for path in ["src/forbidden.py", "worklogs/forbidden.md", ".fa/escaped.md"]:
        assert not (tmp_path / path).exists()


@pytest.mark.parametrize("role,run_id", [("coder", "ct93"), ("planner", "other"), ("eval", "ct93")])
def test_ct93_misbound_dispatch_has_zero_provider_and_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str, run_id: str
) -> None:
    from fa.cli import _cmd_run, build_parser
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind

    calls: list[object] = []

    def provider_request(*_args: object, **_kwargs: object) -> tuple[ResponseInfo, str, list[Any]]:
        calls.append(role)
        return ResponseInfo("done", 1, 1, "stop"), "ct93", []

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    config = tmp_path.parent / f"ct93-{role}-{run_id}.yaml"
    config.write_text("".join(_ROLE_YAML.format(role=item) for item in ("planner", "coder", "eval")), encoding="utf-8")
    state = tmp_path.parent / f"ct93-state-{role}-{run_id}"
    monkeypatch.setenv("FA_STATE_ROOT", str(state))
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
    args = build_parser().parse_args(
        [
            "run",
            "--workspace",
            str(tmp_path),
            "--role",
            role,
            "--run-id",
            run_id,
            "--config",
            str(config),
            "--max-turns",
            "1",
            "ct93 task",
        ]
    )
    dispatch = PlannerDispatch(PlannerDispatchKind.ADMISSION_REPAIR, "ct93", candidate_target=".fa/admission/ct93/p.md")
    assert _cmd_run(args, planner_dispatch=dispatch, secrets=SecretStore({"K": "sk-test-live"})) == 2
    assert calls == []
    assert list(tmp_path.iterdir()) == []
    assert not state.exists()


@pytest.mark.parametrize("failure", ["raises", "absent"])
def test_ct93_required_builder_failure_never_falls_back_or_calls_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from dataclasses import replace

    from fa.cli import _cmd_run
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchError, PlannerDispatchKind
    from fa.inner_loop.tools import write_file

    ctx = _context(tmp_path, run_id="ct93")
    ctx.config.write_text(_ROLE_YAML.format(role="planner"), encoding="utf-8")
    ctx = replace(ctx, secrets=SecretStore({"K": "sk-test-live"}))
    calls: list[object] = []
    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
    monkeypatch.setattr(ProviderChain, "request", lambda *a, **kw: calls.append(a))

    def unavailable(*_args: object, **_kwargs: object) -> Any:
        if failure == "raises":
            raise OSError("scope backend unavailable")
        return None

    monkeypatch.setattr(write_file, "build_scoped_write_file_tool", unavailable)
    dispatch = PlannerDispatch(PlannerDispatchKind.ADMISSION_REPAIR, "ct93", candidate_target=".fa/admission/ct93/p.md")
    with pytest.raises(PlannerDispatchError, match=r"^invalid planner dispatch$"):
        _run_stage(
            ctx,
            "planner",
            fresh=True,
            transition_reason="ct93-fault",
            progress=WorkflowProgress(),
            run_stage_fn=_cmd_run,
            planner_dispatch=dispatch,
        )
    assert calls == []
    assert not (tmp_path / ".fa/admission").exists()


@pytest.mark.parametrize("fault", ["guard", "replace", "fsync"])
def test_ct93_scoped_failure_preserves_candidate_and_reports_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.registry import ToolResult
    from fa.inner_loop.tools import write_file

    target = ".fa/admission/ct93/candidate.md"
    path = tmp_path / target
    path.parent.mkdir(parents=True)
    path.write_bytes(b"old bytes")
    tool = write_file.build_scoped_write_file_tool(
        tmp_path, PlannerDispatch(PlannerDispatchKind.ADMISSION_REPAIR, "ct93", candidate_target=target)
    )
    if fault == "guard":
        monkeypatch.setattr(
            write_file, "check_mutation_allowed", lambda *a, **kw: ToolResult.fail("test_conflict", "blocked")
        )
    else:

        def unavailable(*_args: object, **_kwargs: object) -> None:
            raise OSError("injected publication fault")

        monkeypatch.setattr(os, fault, unavailable)
    result = tool.handler({"path": target, "content": "replacement"})
    assert result.error is not None
    assert result.error.code == ("test_conflict" if fault == "guard" else "write_failed")
    assert result.error.retryable is False
    assert path.read_bytes() == b"old bytes"
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "ORDINARY_PLANNING"},
        {"kind": "ADMISSION_REPAIR"},
        {"run_id": ""},
        {"run_id": "../other"},
        {"run_id": "x" * 129},
        {"active_plan": "/outside.md"},
        {"active_plan": "a/../p.md"},
        {"candidate_target": ".fa/admission/ct93/p.md"},
    ],
)
def test_ct93_invalid_dispatch_fields_cannot_construct_an_ordinary_scope(changes: dict[str, Any]) -> None:
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchError, PlannerDispatchKind

    fields: dict[str, Any] = {"kind": PlannerDispatchKind.ORDINARY_PLANNING, "run_id": "ct93"}
    with pytest.raises(PlannerDispatchError):
        PlannerDispatch(**(fields | changes))


def test_ct93_scope_is_frozen_and_cannot_target_its_active_plan() -> None:
    from dataclasses import FrozenInstanceError

    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchError, PlannerDispatchKind

    target = ".fa/admission/ct93/p.md"
    with pytest.raises(PlannerDispatchError):
        PlannerDispatch(PlannerDispatchKind.ADMISSION_REPAIR, "ct93", target, target)
    dispatch = PlannerDispatch(PlannerDispatchKind.ADMISSION_REPAIR, "ct93", candidate_target=target)
    from dataclasses import fields

    for field in fields(dispatch):
        with pytest.raises(FrozenInstanceError):
            setattr(dispatch, field.name, ".fa/active.md")


# CT94 IO prerequisite; local session composition is not run_workflow admission.
_CT94_PATH = "worklogs/planning-topology-and-executable-contracts-loop/increments/fixture.md"


def _ct94_plan(label: str = "original") -> bytes:
    return (
        f"Plan-ID: PLAN-ct94\n\n## SLICE1: {label}\nCONTRACTS:\n"
        "  CT1 [CONSTRAINT]: exact plan bytes remain authoritative.\n"
        "TESTS: tests/test_candidate.py\n"
    ).encode()


def _ct94_source(tmp_path: Path) -> PlanSnapshot:
    from fa.inner_loop.plan_admission import read_plan_snapshot

    path = tmp_path / _CT94_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(_ct94_plan())
    path.chmod(0o640)
    path.parent.chmod(0o750)
    return read_plan_snapshot(tmp_path, path)


@pytest.mark.parametrize(
    "case,outcome,rule",
    [
        ("valid", "PASS", None),
        ("precheck", "DIAGNOSTICS", "slice-without-tests"),
        ("kill", "DIAGNOSTICS", "kill-directive-missing"),
        ("near-miss", "DIAGNOSTICS", "heading-near-miss"),
        ("prose", "INDETERMINATE", "zero-slices"),
    ],
)
def test_ct94_validation_joins_both_validators(case: str, outcome: str, rule: str | None) -> None:
    from fa.inner_loop.plan_admission import snapshot_from_bytes

    raw = _ct94_plan()
    if case == "precheck":
        raw = raw.replace(b"TESTS: tests/test_candidate.py\n", b"")
    elif case == "kill":
        raw = raw.replace(b"[CONSTRAINT]", b"[FUNCTIONAL]")
    elif case == "near-miss":
        raw = b"## SLICE 1: almost\n"
    elif case == "prose":
        raw = b"not a plan yet\n"
    snapshot = snapshot_from_bytes("draft.md", raw)
    result = workflow._validate_plan_admission(snapshot)
    assert result.snapshot is snapshot
    assert result.outcome == outcome
    if rule is not None:
        assert rule in {d.rule for d in result.diagnostics}
    else:
        assert result.diagnostics == ()


@pytest.mark.parametrize("fault", ["precheck", "kill", "unknown-rule", "unknown-severity"])
def test_ct94_validation_faults_are_sanitized_indeterminate(monkeypatch: pytest.MonkeyPatch, fault: str) -> None:
    from dataclasses import asdict

    from fa.inner_loop.plan_admission import snapshot_from_bytes
    from fa.inner_loop.plan_ids import PlanDiagnostic, PrecheckReport

    def broken(*_args: object, **_kwargs: object) -> Any:
        if fault in {"precheck", "kill"}:
            raise RuntimeError("PRIVATE-EXCEPTION-BODY /outside/private/path")
        return PrecheckReport(
            "/outside/private/path",
            (
                PlanDiagnostic(
                    "future-rule" if fault == "unknown-rule" else "slice-without-tests",
                    "FUTURE" if fault == "unknown-severity" else "FAIL",
                    "/outside/private/path",
                    1,
                    "PRIVATE-SOURCE-BODY",
                ),
            ),
        )

    monkeypatch.setattr(workflow, "validate_kill_directives" if fault == "kill" else "precheck", broken)
    # Kill-validator failure must not erase an already known precheck failure.
    snapshot = snapshot_from_bytes("draft.md", _ct94_plan().replace(b"TESTS: tests/test_candidate.py\n", b""))
    result = workflow._validate_plan_admission(snapshot)
    assert result.outcome == "INDETERMINATE"
    assert "validator-error" in {d.rule for d in result.diagnostics}
    if fault == "kill":
        assert "slice-without-tests" in {d.rule for d in result.diagnostics}
    assert "PRIVATE" not in json.dumps([asdict(d) for d in result.diagnostics])
    assert "/outside" not in json.dumps([asdict(d) for d in result.diagnostics])


def test_ct94_warn_only_passes_and_empty_or_unexplained_zero_slices_do_not() -> None:
    from dataclasses import replace

    from fa.inner_loop.plan_admission import snapshot_from_bytes
    from fa.inner_loop.plan_ids import PlanIds

    raw = b"Plan-ID: PLAN-ct94\n" + b"".join(
        f"\n## SLICE{i}: unit\nCONTRACTS:\n  CT{i} [CONSTRAINT]: invariant.\nTESTS: tests/test_candidate.py\n".encode()
        for i in range(1, 8)
    )
    snapshot = snapshot_from_bytes("draft.md", raw)
    result = workflow._validate_plan_admission(snapshot)
    assert result.outcome == "PASS" and {d.severity for d in result.diagnostics} == {"WARN"}
    empty = workflow._validate_plan_admission(replace(snapshot, text=" ", ids=PlanIds()))
    assert empty.outcome == "INDETERMINATE" and empty.diagnostics[0].rule == "empty"
    missing_ids = workflow._validate_plan_admission(replace(snapshot, ids=PlanIds()))
    assert missing_ids.outcome == "INDETERMINATE" and missing_ids.diagnostics[-1].rule == "zero-slices"


@pytest.mark.parametrize("kind", ["ADMISSION_REPAIR", "EVAL_REPLAN"])
def test_ct94_seed_is_fresh_and_retains_rejected_draft_progress(tmp_path: Path, kind: str) -> None:
    from fa.inner_loop.plan_admission import snapshot_from_bytes
    from fa.inner_loop.plan_promotion import seed_plan_candidate
    from fa.inner_loop.planner_dispatch import PlannerDispatchKind

    source = _ct94_source(tmp_path)
    rejected = snapshot_from_bytes("draft.md", b"## SLICE 1: a structural near miss worth preserving\n")
    first = seed_plan_candidate(tmp_path, source, run_id="ct94", kind=PlannerDispatchKind(kind))
    second = seed_plan_candidate(tmp_path, source, run_id="ct94", kind=PlannerDispatchKind(kind), draft=rejected)
    assert first.candidate_target is not None and second.candidate_target is not None
    assert first.candidate_target != second.candidate_target
    assert (tmp_path / first.candidate_target).read_bytes() == source.utf8_bytes
    assert (tmp_path / second.candidate_target).read_bytes() == rejected.utf8_bytes
    assert first.active_plan == second.active_plan == _CT94_PATH
    assert (tmp_path / second.candidate_target).stat().st_mode & 0o777 == 0o600
    assert (tmp_path / second.candidate_target).parent.stat().st_mode & 0o777 == 0o700
    assert (tmp_path / _CT94_PATH).read_bytes() == source.utf8_bytes
    assert (tmp_path / _CT94_PATH).parent.stat().st_mode & 0o777 == 0o750


@pytest.mark.parametrize(
    "path",
    [
        "notes.md",
        "worklogs/other/increments/p.md",
        "worklogs/planning-topology-and-executable-contracts-loop/increments/../p.md",
    ],
)
def test_ct94_scope_denial_precedes_allocation(tmp_path: Path, path: str) -> None:
    from dataclasses import replace

    from fa.inner_loop.plan_admission import PlanRef
    from fa.inner_loop.plan_promotion import PlanPromotionError, publish_plan_buffer, seed_plan_candidate
    from fa.inner_loop.planner_dispatch import PlannerDispatchKind

    source = _ct94_source(tmp_path)
    outside = replace(source, ref=PlanRef(path, "EXPLICIT", source.ref.sha256))
    actions: list[Callable[[], object]] = [
        lambda: seed_plan_candidate(tmp_path, outside, run_id="ct94", kind=PlannerDispatchKind.ADMISSION_REPAIR),
        lambda: publish_plan_buffer(tmp_path, outside, _ct94_plan("new")),
    ]
    for action in actions:
        with pytest.raises(PlanPromotionError) as error:
            action()
        assert error.value.rule == "scope-denied" and error.value.replaced is False
    assert not (tmp_path / ".fa").exists()
    assert (tmp_path / _CT94_PATH).read_bytes() == source.utf8_bytes


def test_ct94_promotion_uses_validated_buffer_not_changed_draft(tmp_path: Path) -> None:
    from fa.inner_loop.plan_admission import read_plan_snapshot

    source = _ct94_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_bytes(_ct94_plan("validated revision"))
    snapshot = read_plan_snapshot(tmp_path, draft)
    validated = workflow._validate_plan_admission(snapshot)
    assert validated.outcome == "PASS"
    draft.write_bytes(b"invalid bytes after validation\xff")
    promoted = workflow._promote_validated_plan(tmp_path, source, validated)
    assert (tmp_path / _CT94_PATH).read_bytes() == snapshot.utf8_bytes
    assert promoted.ref.workspace_relative_path == _CT94_PATH
    assert promoted.ref.sha256 == snapshot.ref.sha256
    assert promoted.ids is snapshot.ids and promoted.text == snapshot.text
    assert (tmp_path / _CT94_PATH).stat().st_mode & 0o777 == 0o640
    assert (tmp_path / _CT94_PATH).parent.stat().st_mode & 0o777 == 0o750
    assert list((tmp_path / _CT94_PATH).parent.iterdir()) == [tmp_path / _CT94_PATH]


@pytest.mark.parametrize("obstacle", ["stale", "terminal", "ancestor", "hardlink", "fifo", "directory"])
def test_ct94_promotion_rejects_unsafe_source_without_clobbering(
    tmp_path: Path, obstacle: str, bounded_admission_test: None
) -> None:
    from fa.inner_loop.plan_admission import snapshot_from_bytes
    from fa.inner_loop.plan_promotion import PlanPromotionError

    source = _ct94_source(tmp_path)
    target = tmp_path / _CT94_PATH
    sentinel = tmp_path / "outside"
    sentinel.write_bytes(source.utf8_bytes)
    if obstacle == "stale":
        target.write_bytes(_ct94_plan("external edit"))
    elif obstacle == "ancestor":
        target.parent.rename(tmp_path / "elsewhere")
        target.parent.symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    else:
        target.unlink()
        if obstacle == "terminal":
            target.symlink_to(sentinel)
        elif obstacle == "hardlink":
            os.link(sentinel, target)
        elif obstacle == "fifo":
            os.mkfifo(target)
        else:
            target.mkdir()
    validated = workflow._validate_plan_admission(snapshot_from_bytes("draft.md", _ct94_plan("new")))
    with pytest.raises(PlanPromotionError) as error:
        workflow._promote_validated_plan(tmp_path, source, validated)
    expected_rule = (
        "source-changed"
        if obstacle == "stale"
        else "symlink"
        if obstacle in {"terminal", "ancestor"}
        else "not-regular"
    )
    assert error.value.rule == expected_rule and error.value.replaced is False
    assert sentinel.read_bytes() == source.utf8_bytes
    if obstacle == "stale":
        assert target.read_bytes() == _ct94_plan("external edit")
    elif obstacle not in {"fifo", "directory"}:
        assert target.read_bytes() == source.utf8_bytes
    assert not list(target.parent.glob(".*.tmp"))


@pytest.mark.parametrize("fault", ["write", "file-fsync", "replace", "directory-fsync", "post-hash"])
def test_ct94_promotion_failure_boundary_never_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    import stat

    from fa.inner_loop import plan_promotion as publication
    from fa.inner_loop.plan_admission import snapshot_from_bytes

    source = _ct94_source(tmp_path)
    raw = _ct94_plan("new")
    validated = workflow._validate_plan_admission(snapshot_from_bytes("draft.md", raw))
    real_fsync = os.fsync
    real_write = os.write
    target = tmp_path / _CT94_PATH
    # Pre-create lock directories so directory-fsync fault is precisely post-replace.
    import hashlib

    lock_key = hashlib.sha256(_CT94_PATH.encode()).hexdigest()
    (tmp_path / ".fa/admission/.locks" / lock_key).mkdir(parents=True)

    def fsync(fd: int) -> None:
        regular = stat.S_ISREG(os.fstat(fd).st_mode)
        if (fault == "file-fsync" and regular) or (fault == "directory-fsync" and not regular):
            raise OSError("PRIVATE-FSYNC-FAILURE")
        real_fsync(fd)

    def write(fd: int, data: Any) -> int:
        if fault == "write":
            return 0
        return real_write(fd, data)

    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(os, "write", write)
    if fault == "replace":

        def rejected(*_args: object, **_kwargs: object) -> None:
            raise OSError("PRIVATE-REPLACE-FAILURE")

        monkeypatch.setattr(os, "replace", rejected)
    elif fault == "post-hash":
        from fa.inner_loop.plan_admission import read_plan_snapshot as original_reader

        def changed(*args: Any, **kwargs: Any) -> Any:
            target.write_bytes(_ct94_plan("host changed after replace"))
            return original_reader(*args, **kwargs)

        monkeypatch.setattr(publication, "read_plan_snapshot", changed)
    with pytest.raises(publication.PlanPromotionError) as error:
        workflow._promote_validated_plan(tmp_path, source, validated)
    after = fault in {"directory-fsync", "post-hash"}
    assert error.value.replaced is after
    expected = {
        "write": "prepare-failed",
        "file-fsync": "prepare-failed",
        "replace": "replace-failed",
        "directory-fsync": "durability-unknown",
        "post-hash": "hash-mismatch",
    }
    assert error.value.rule == expected[fault]
    assert "PRIVATE" not in str(error.value)
    actual = _ct94_plan("host changed after replace") if fault == "post-hash" else raw if after else source.utf8_bytes
    assert target.read_bytes() == actual
    assert target.stat().st_mode & 0o777 == 0o640
    assert list(target.parent.iterdir()) == [target]


@pytest.mark.parametrize("fault", ["collision", "zero-write", "file-fsync", "directory-fsync"])
def test_ct94_seed_failure_never_clobbers_existing_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from fa.inner_loop import plan_promotion as publication
    from fa.inner_loop.planner_dispatch import PlannerDispatchKind

    source = _ct94_source(tmp_path)
    monkeypatch.setattr(publication, "uuid4", lambda: SimpleNamespace(hex="fixed"))
    path = tmp_path / ".fa/admission/ct94/candidate-fixed.md"
    path.parent.mkdir(parents=True)
    if fault == "collision":
        path.write_bytes(b"existing owned by someone else")
    elif fault == "zero-write":
        monkeypatch.setattr(os, "write", lambda *_args: 0)
    else:
        import stat

        real_fsync = os.fsync

        def unavailable(fd: int) -> None:
            regular = stat.S_ISREG(os.fstat(fd).st_mode)
            if regular is (fault == "file-fsync"):
                raise OSError("private seed failure")
            real_fsync(fd)

        monkeypatch.setattr(os, "fsync", unavailable)
    with pytest.raises(publication.PlanPromotionError) as error:
        publication.seed_plan_candidate(tmp_path, source, run_id="ct94", kind=PlannerDispatchKind.ADMISSION_REPAIR)
    assert error.value.rule == "prepare-failed" and error.value.replaced is False
    assert path.exists() is (fault == "collision")
    if fault == "collision":
        assert path.read_bytes() == b"existing owned by someone else"
    assert (tmp_path / _CT94_PATH).read_bytes() == source.utf8_bytes


@pytest.mark.parametrize("race", ["bytes", "inode", "symlink", "hardlink", "mode"])
def test_ct94_final_cas_detects_mutation_during_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, race: str
) -> None:
    from fa.inner_loop import plan_promotion as publication
    from fa.inner_loop.plan_admission import snapshot_from_bytes

    source = _ct94_source(tmp_path)
    target = tmp_path / _CT94_PATH
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(source.utf8_bytes)
    stage = publication._stage_replacement

    def changed(*args: Any, **kwargs: Any) -> None:
        stage(*args, **kwargs)
        if race == "bytes":
            target.write_bytes(_ct94_plan("host edit"))
        elif race == "mode":
            target.chmod(0o600)
        else:
            target.unlink()
            if race == "inode":
                target.write_bytes(source.utf8_bytes)
            elif race == "symlink":
                target.symlink_to(sentinel)
            else:
                os.link(sentinel, target)

    monkeypatch.setattr(publication, "_stage_replacement", changed)
    validation = workflow._validate_plan_admission(snapshot_from_bytes("draft.md", _ct94_plan("revision")))
    with pytest.raises(publication.PlanPromotionError) as error:
        workflow._promote_validated_plan(tmp_path, source, validation)
    assert error.value.replaced is False
    expected_rule = "symlink" if race == "symlink" else "not-regular" if race == "hardlink" else "source-changed"
    assert error.value.rule == expected_rule
    assert target.read_bytes() == (_ct94_plan("host edit") if race == "bytes" else source.utf8_bytes)
    assert sentinel.read_bytes() == source.utf8_bytes
    assert not list(target.parent.glob(".*.tmp"))


@pytest.mark.parametrize("case", ["structural", "zero-slices", "validator-error"])
def test_ct94_nonpassing_validation_never_publishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    from fa.inner_loop.plan_admission import snapshot_from_bytes
    from fa.inner_loop.plan_promotion import PlanPromotionError

    source = _ct94_source(tmp_path)
    raw = b"## SLICE 1: bad heading\n" if case == "structural" else b"only prose\n"
    if case == "validator-error":

        def broken(*_args: object, **_kwargs: object) -> Any:
            raise RuntimeError("not admissible")

        monkeypatch.setattr(workflow, "precheck", broken)
    validated = workflow._validate_plan_admission(snapshot_from_bytes("draft.md", raw))
    with pytest.raises(PlanPromotionError) as error:
        workflow._promote_validated_plan(tmp_path, source, validated)
    assert error.value.rule == "prepare-failed" and error.value.replaced is False
    assert (tmp_path / _CT94_PATH).read_bytes() == source.utf8_bytes
    assert not (tmp_path / ".fa").exists()


@pytest.mark.parametrize("kind", ["ADMISSION_REPAIR", "EVAL_REPLAN"])
def test_ct94_real_session_edits_fresh_candidate_before_validated_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """C1 session + local IO composition, NOT full public repair/budget admission."""
    from dataclasses import replace

    from fa.cli import _cmd_run
    from fa.inner_loop.plan_admission import read_plan_snapshot
    from fa.inner_loop.plan_promotion import seed_plan_candidate
    from fa.inner_loop.planner_dispatch import PlannerDispatchKind

    source = _ct94_source(tmp_path)
    if kind == "ADMISSION_REPAIR":
        (tmp_path / _CT94_PATH).write_bytes(source.utf8_bytes.replace(b"[CONSTRAINT]", b"[FUNCTIONAL]"))
        source = read_plan_snapshot(tmp_path, Path(_CT94_PATH))
        assert workflow._validate_plan_admission(source).outcome == "DIAGNOSTICS"
    dispatch = seed_plan_candidate(tmp_path, source, run_id="ct94", kind=PlannerDispatchKind(kind))
    assert dispatch.candidate_target is not None
    target = dispatch.candidate_target
    raw = _ct94_plan("repaired by real scoped writer")
    ctx = _context(tmp_path, run_id="ct94")
    ctx.config.write_text(_ROLE_YAML.format(role="planner"), encoding="utf-8")
    ctx = replace(ctx, plan_path=tmp_path / _CT94_PATH, max_turns=5, secrets=SecretStore({"K": "sk-test-live"}))
    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
    requests: list[RequestInfo] = []

    def provider_request(
        _chain: ProviderChain, request: RequestInfo, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        requests.append(request)
        assert (tmp_path / _CT94_PATH).read_bytes() == source.utf8_bytes
        if len(requests) == 1:
            tool, params = "pr_prepare", {"intent": "IMPLEMENT", "invariant": "Implements: CT94 candidate revision"}
            assert (tmp_path / target).read_bytes() == source.utf8_bytes
        elif len(requests) == 2:
            tool, params = "fs_write_file", {"path": target, "content": raw.decode()}
        else:
            return ResponseInfo("done", 1, 1, "stop"), logical_call_id or "ct94", []
        call = {
            "id": f"ct94-{len(requests)}",
            "type": "function",
            "function": {"name": tool, "arguments": json.dumps(params)},
        }
        return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "ct94", []

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    stage = _run_stage(
        ctx,
        "planner",
        fresh=True,
        progress=WorkflowProgress(),
        transition_reason="ct94 candidate",
        run_stage_fn=_cmd_run,
        planner_dispatch=dispatch,
    )
    assert stage.exit_code == 0 and len(requests) == 3
    (schema,) = [item["function"] for item in requests[0].tools if item["function"]["name"] == "fs_write_file"]
    assert schema["parameters"]["properties"]["path"]["enum"] == [target]
    candidate = read_plan_snapshot(tmp_path, Path(target))
    validated = workflow._validate_plan_admission(candidate)
    assert validated.outcome == "PASS"
    promoted = workflow._promote_validated_plan(tmp_path, source, validated)
    assert (tmp_path / _CT94_PATH).read_bytes() == raw
    assert promoted.ref.workspace_relative_path == _CT94_PATH
    assert promoted.ref.sha256 == candidate.ref.sha256 and promoted.ids is candidate.ids
    assert (tmp_path / _CT94_PATH).stat().st_mode & 0o777 == 0o640
    assert (tmp_path / _CT94_PATH).parent.stat().st_mode & 0o777 == 0o750
    events = [json.loads(line) for line in (tmp_path / "state/session-log/ct94/events.jsonl").read_text().splitlines()]
    results = {event["tool_call_id"]: event["content"] for event in events if event["kind"] == "tool_result"}
    assert results["ct94-1"]["ok"] is True and results["ct94-2"]["ok"] is True


_CT94_PUBLISH_CHILD = r"""
import json, pathlib, sys, time
from fa.inner_loop import plan_promotion as publication
from fa.inner_loop.plan_admission import snapshot_from_bytes
from fa.inner_loop.workflow_artifacts import AdmissionIOError
from fa.inner_loop.workflow_controller import _validate_plan_admission, _promote_validated_plan
assert pathlib.Path(publication.__file__).resolve() == pathlib.Path(sys.argv[5]).resolve()
root = pathlib.Path(sys.argv[1])
source = snapshot_from_bytes(sys.argv[2], bytes.fromhex(sys.argv[3]))
candidate = snapshot_from_bytes("candidate.md", bytes.fromhex(sys.argv[4]))
validation = _validate_plan_admission(candidate)
assert validation.outcome == "PASS"
print("READY", flush=True)
try:
    result = _promote_validated_plan(root, source, validation, deadline=time.monotonic() + float(sys.argv[6]))
    print(json.dumps({"status": "promoted", "hash": result.ref.sha256}), flush=True)
except (publication.PlanPromotionError, AdmissionIOError) as error:
    print(json.dumps({"status": error.rule, "replaced": getattr(error, "replaced", False)}), flush=True)
"""


@pytest.mark.parametrize("held_until_timeout", [False, True])
def test_ct94_process_shared_target_lock_and_hash_cas(tmp_path: Path, held_until_timeout: bool) -> None:
    """C3 actual competing processes, exact import provenance and finite child deadlines."""
    import hashlib
    import select
    import subprocess
    import sys

    from fa.inner_loop import plan_promotion as publication
    from fa.inner_loop.workflow_artifacts import _admission_lock, _private_artifact_directory

    source = _ct94_source(tmp_path)
    children: list[subprocess.Popen[str]] = []
    lock_key = hashlib.sha256(_CT94_PATH.encode()).hexdigest()
    try:
        with (
            _private_artifact_directory(tmp_path / ".fa/admission/.locks" / lock_key) as lock_fd,
            _admission_lock(lock_fd, deadline=None),
        ):
            for i in range(1 if held_until_timeout else 2):
                child = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        _CT94_PUBLISH_CHILD,
                        str(tmp_path),
                        _CT94_PATH,
                        source.utf8_bytes.hex(),
                        _ct94_plan(f"publisher-{i}").hex(),
                        str(Path(publication.__file__).resolve()),
                        "0.2" if held_until_timeout else "15",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=REPO_ROOT,
                )
                children.append(child)
                assert child.stdout is not None
                assert select.select([child.stdout], [], [], 10)[0], "child did not reach publication"
                assert child.stdout.readline() == "READY\n"
            if held_until_timeout:
                out, err = children[0].communicate(timeout=10)
                assert children[0].returncode == 0, err
                assert json.loads(out) == {"status": "lock-failed", "replaced": False}
                assert (tmp_path / _CT94_PATH).read_bytes() == source.utf8_bytes
                return
        outcomes = []
        for child in children:
            out, err = child.communicate(timeout=20)
            assert child.returncode == 0, err
            outcomes.append(json.loads(out))
        assert sorted(item["status"] for item in outcomes) == ["promoted", "source-changed"]
        assert (tmp_path / _CT94_PATH).read_bytes() in {_ct94_plan("publisher-0"), _ct94_plan("publisher-1")}
        assert (tmp_path / _CT94_PATH).stat().st_mode & 0o777 == 0o640
        assert list((tmp_path / _CT94_PATH).parent.iterdir()) == [tmp_path / _CT94_PATH]
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)


def test_ct94_collision_retains_foreign_temp_and_short_writes_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop import plan_promotion as publication
    from fa.inner_loop.plan_admission import snapshot_from_bytes

    source = _ct94_source(tmp_path)
    raw = _ct94_plan("первая revision")
    validated = workflow._validate_plan_admission(snapshot_from_bytes("draft.md", raw))
    monkeypatch.setattr(publication, "uuid4", lambda: SimpleNamespace(hex="fixed"))
    collision = (tmp_path / _CT94_PATH).parent / ".fixture.md.fixed.tmp"
    collision.write_bytes(b"unrelated temporary")
    with pytest.raises(publication.PlanPromotionError) as error:
        workflow._promote_validated_plan(tmp_path, source, validated)
    assert error.value.rule == "prepare-failed" and error.value.replaced is False
    assert collision.read_bytes() == b"unrelated temporary"
    assert (tmp_path / _CT94_PATH).read_bytes() == source.utf8_bytes
    collision.unlink()
    real_write = os.write
    calls: list[int] = []

    def short(fd: int, data: Any) -> int:
        calls.append(len(data))
        return real_write(fd, data[:3])

    monkeypatch.setattr(os, "write", short)
    result = workflow._promote_validated_plan(tmp_path, source, validated)
    assert len(calls) > 1
    assert result.ref.sha256 == validated.snapshot.ref.sha256
    assert (tmp_path / _CT94_PATH).read_bytes() == raw
    assert not collision.exists()


@pytest.mark.parametrize(
    "raw,rule", [(b"", "empty"), (b"\xff", "invalid-utf8"), (b"a" * (1024 * 1024 + 1), "too-large")]
)
def test_ct94_invalid_buffer_cannot_allocate_or_publish(tmp_path: Path, raw: bytes, rule: str) -> None:
    from fa.inner_loop.plan_admission import PlanRefError
    from fa.inner_loop.plan_promotion import publish_plan_buffer

    source = _ct94_source(tmp_path)
    with pytest.raises(PlanRefError) as error:
        publish_plan_buffer(tmp_path, source, raw)
    assert error.value.rule == rule
    assert (tmp_path / _CT94_PATH).read_bytes() == source.utf8_bytes
    assert not (tmp_path / ".fa").exists()


def test_ct94_projection_is_accepted_by_actual_admission_schema(tmp_path: Path) -> None:
    from dataclasses import asdict

    from fa.inner_loop.plan_admission import snapshot_from_bytes
    from fa.inner_loop.workflow_artifacts import write_admission_record

    snapshot = snapshot_from_bytes("draft.md", _ct94_plan().replace(b"[CONSTRAINT]", b"[FUNCTIONAL]"))
    validated = workflow._validate_plan_admission(snapshot)
    assert validated.outcome == "DIAGNOSTICS"
    attempt = {
        "dispatch_kind": "EXPLICIT_INPUT",
        "validation": validated.outcome,
        "diagnostics": [asdict(d) for d in validated.diagnostics],
        "source_sha256": snapshot.ref.sha256,
        "candidate_sha256": None,
        "promoted_sha256": None,
        "route": "BLOCKED",
    }
    path = tmp_path / "record/admission.json"
    write_admission_record(path, run_id="ct94", plan_ref=snapshot.ref, attempt=attempt, status="BLOCKED")
    stored = json.loads(path.read_bytes())
    assert stored["attempts"][0]["diagnostics"] == [
        {"validator": "kill-directives", "rule": "kill-directive-missing", "severity": "FAIL", "line": 5}
    ]
    assert stored["status"] == "BLOCKED"


def test_ct94_post_replace_mode_tamper_fails_without_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.plan_admission import snapshot_from_bytes
    from fa.inner_loop.plan_promotion import PlanPromotionError

    source = _ct94_source(tmp_path)
    target = tmp_path / _CT94_PATH
    raw = _ct94_plan("revision")
    validated = workflow._validate_plan_admission(snapshot_from_bytes("draft.md", raw))
    real_replace = os.replace

    def tampered(*args: Any, **kwargs: Any) -> None:
        real_replace(*args, **kwargs)
        target.chmod(0o600)

    monkeypatch.setattr(os, "replace", tampered)
    with pytest.raises(PlanPromotionError) as error:
        workflow._promote_validated_plan(tmp_path, source, validated)
    assert error.value.rule == "hash-mismatch" and error.value.replaced is True
    assert target.read_bytes() == raw and target.stat().st_mode & 0o777 == 0o600


def test_ct94_open_descriptor_source_change_is_not_generic_io_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop import plan_promotion as publication
    from fa.inner_loop.plan_admission import PlanRefError, snapshot_from_bytes

    source = _ct94_source(tmp_path)
    validated = workflow._validate_plan_admission(snapshot_from_bytes("draft.md", _ct94_plan("new")))

    def changed(_fd: int) -> bytes:
        raise PlanRefError("source-changed")

    monkeypatch.setattr(publication, "_read_open_plan_bytes", changed)
    with pytest.raises(publication.PlanPromotionError) as error:
        workflow._promote_validated_plan(tmp_path, source, validated)
    assert error.value.rule == "source-changed" and error.value.replaced is False
    assert (tmp_path / _CT94_PATH).read_bytes() == source.utf8_bytes
    assert list((tmp_path / _CT94_PATH).parent.iterdir()) == [tmp_path / _CT94_PATH]


def test_ct94_ordinary_dispatch_cannot_seed_a_candidate(tmp_path: Path) -> None:
    from fa.inner_loop.plan_promotion import PlanPromotionError, seed_plan_candidate
    from fa.inner_loop.planner_dispatch import PlannerDispatchKind

    source = _ct94_source(tmp_path)
    with pytest.raises(PlanPromotionError) as error:
        seed_plan_candidate(tmp_path, source, run_id="ct94", kind=PlannerDispatchKind.ORDINARY_PLANNING)
    assert error.value.rule == "scope-denied" and error.value.replaced is False
    assert not (tmp_path / ".fa").exists()
    assert (tmp_path / _CT94_PATH).read_bytes() == source.utf8_bytes


def test_ct94_canonical_namespace_allows_normalized_descendants(tmp_path: Path) -> None:
    from fa.inner_loop.plan_admission import read_plan_snapshot, snapshot_from_bytes

    source = _ct94_source(tmp_path)
    nested = (tmp_path / _CT94_PATH).parent / "nested" / "increment.md"
    nested.parent.mkdir()
    nested.write_bytes(source.utf8_bytes)
    nested.chmod(0o640)
    source = read_plan_snapshot(tmp_path, nested)
    validation = workflow._validate_plan_admission(snapshot_from_bytes("draft.md", _ct94_plan("nested revision")))
    promoted = workflow._promote_validated_plan(tmp_path, source, validation)
    assert promoted.ref.workspace_relative_path == nested.relative_to(tmp_path).as_posix()
    assert nested.read_bytes() == validation.snapshot.utf8_bytes
    assert nested.stat().st_mode & 0o777 == 0o640
    assert (tmp_path / _CT94_PATH).read_bytes() == _ct94_plan()
