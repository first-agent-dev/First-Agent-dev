"""S12a — the workflow's reference to the plan it executes against.

**The gap this closes.** The harness had no plan concept at all. Worse,
``emit_eval_report`` was called with ``plan_id=ctx.run_id`` and ``FlowState``
recorded ``active_plan_id=ctx.run_id``: a field whose name promised a plan
reference while holding a run identifier. Nothing could check a run against
its contract because nothing knew what the contract was.

S12a is deliberately plumbing, not enforcement. It supplies ``plan_path`` and a
real ``plan_id``; **S12** (validate slice IDs) and **S13** (give eval the plan
and diff) are the consumers. Shipping the reference first keeps each step
falsifiable on its own.

**Why ``--plan`` is optional.** Most runs, and every pre-S12a caller, have no
plan artifact. An absent plan must degrade silently -- no warnings about a
contract the operator never supplied. The standing rule that legacy plans
failing extraction is expected, and is not a kill signal, applies here.

Classes: **C0** for the extractor and the identity fallback, **C1** for the
composition root (real ``run_workflow``, only the stage dispatcher injected),
**C2** for the CLI boundary.

Kill-check target: the ``plan_path=`` assignment in ``_write_terminal_state``'s
``FlowState`` and ``plan_id=ctx.plan_identity()`` in ``_run_stage``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fa.cli import build_parser
from fa.inner_loop.plan_ids import extract_plan_id
from fa.inner_loop.workflow_controller import (
    WorkflowContext,
    build_eval_report,
    run_workflow,
    workflow_artifact_paths,
)

_PLAN_BODY = """# PLAN: A worked example    Plan-ID: PLAN-example-contract
Status: READY

### Step S1: do the thing
"""


class _SilentStage:
    """Real ``run_stage_fn`` shape; returns 0 without an outcome."""

    def __init__(self) -> None:
        self.roles: list[str] = []

    def __call__(self, args: argparse.Namespace, **_kwargs: Any) -> int:
        self.roles.append(str(getattr(args, "role", "?")))
        return 0


def _config(tmp_path: Path) -> Path:
    config = tmp_path / "models.yaml"
    config.write_text("providers: {}\n", encoding="utf-8")
    return config


def _run(tmp_path: Path, *, run_id: str, plan_path: Path | None) -> tuple[int, Any]:
    return run_workflow(
        roles=["coder"],
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
        run_stage_fn=_SilentStage(),
        plan_path=plan_path,
    )


def _flow_state(run_id: str) -> dict[str, Any]:
    path = workflow_artifact_paths(run_id).flow_state
    assert path.is_file(), f"no flow_state.json at {path}"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


# ── C0: the extractor ──────────────────────────────────────────────────────


def test_extracts_all_three_declaration_shapes_used_in_this_repo() -> None:
    """C0 — the three real formats, not an invented canonical one.

    Sampled from the repo's own plans: backticked, bolded label, and this
    plan's own inline-at-end-of-H1 form. A parser that handled only the tidy
    case would silently return None for most real plans.
    """
    assert extract_plan_id("Plan-ID: `PLAN-ble001-waiver-reduction`") == "PLAN-ble001-waiver-reduction"
    assert extract_plan_id("**Plan-ID:** PLAN-deterministic-routing-S7-S9") == "PLAN-deterministic-routing-S7-S9"
    assert extract_plan_id("# PLAN: Title    Plan-ID: PLAN-slice-ceremony") == "PLAN-slice-ceremony"


def test_missing_or_empty_declaration_is_none_not_an_error() -> None:
    """C0 — absence is a valid answer; a plan without a header must not raise."""
    assert extract_plan_id("") is None
    assert extract_plan_id("a plan with no header at all\n\n## Steps\n") is None


def test_first_declaration_wins() -> None:
    """C0 — a later prose mention cannot displace the header."""
    doc = "# T   Plan-ID: PLAN-real\n\nlater we mention Plan-ID: PLAN-decoy in prose\n"
    assert extract_plan_id(doc) == "PLAN-real"


def test_real_repo_plan_resolves() -> None:
    """C0 — run against the actual artifact, not only synthetic strings."""
    plan = Path(__file__).resolve().parents[1] / "worklogs" / "implementation-plans"
    plan = plan / "PLAN-slice-ceremony-harness-enforcement.md"
    if not plan.is_file():
        return
    assert extract_plan_id(plan.read_text(encoding="utf-8")) == "PLAN-slice-ceremony-harness-enforcement"


# ── C0: identity fallback on the context ───────────────────────────────────


def _ctx(tmp_path: Path, plan_path: Path | None) -> WorkflowContext:
    return WorkflowContext(
        run_id="run-xyz",
        base_task="t",
        per_role_task={},
        artifact_paths=workflow_artifact_paths("run-xyz", base_dir=tmp_path / "art"),
        config=_config(tmp_path),
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        plan_path=plan_path,
    )


def test_plan_identity_prefers_the_declared_id(tmp_path: Path) -> None:
    """C0 — with a plan, records carry the plan's ID, not the run ID."""
    plan = tmp_path / "P.md"
    plan.write_text(_PLAN_BODY, encoding="utf-8")
    assert _ctx(tmp_path, plan).plan_identity() == "PLAN-example-contract"


def test_plan_identity_falls_back_to_run_id(tmp_path: Path) -> None:
    """C0 — no plan, or a plan with no header, keeps the historical value."""
    assert _ctx(tmp_path, None).plan_identity() == "run-xyz"
    headerless = tmp_path / "H.md"
    headerless.write_text("# no id here\n", encoding="utf-8")
    assert _ctx(tmp_path, headerless).plan_identity() == "run-xyz"


def test_unreadable_plan_does_not_take_the_run_down(tmp_path: Path) -> None:
    """C0 — a plan deleted mid-run degrades to the fallback, never raises.

    The plan is advisory input, not a dependency: losing it must not be able
    to fail a pipeline that is otherwise healthy.
    """
    ctx = _ctx(tmp_path, tmp_path / "vanished.md")
    assert ctx.plan_text() is None
    assert ctx.plan_identity() == "run-xyz"


# ── C1: T20 / T20b — the composition root ──────────────────────────────────


def test_plan_path_is_recorded_in_flow_state(tmp_path: Path) -> None:
    """T20 (KILL-CHECK) — a supplied plan is traceable from the artifact.

    Removing the ``plan_path=`` assignment in ``_write_terminal_state`` fails
    here, which is exactly what leaves S12/S13 with no input.
    """
    plan = tmp_path / "P.md"
    plan.write_text(_PLAN_BODY, encoding="utf-8")

    exit_code, state = _run(tmp_path, run_id="pp-1", plan_path=plan)

    assert exit_code == 0
    assert state is not None
    assert state.plan_path == str(plan)
    assert _flow_state("pp-1")["plan_path"] == str(plan)


def test_absent_plan_degrades_silently(tmp_path: Path) -> None:
    """T20b — no ``--plan`` means empty, no warning, behaviour unchanged."""
    exit_code, state = _run(tmp_path, run_id="pp-2", plan_path=None)

    assert exit_code == 0
    assert state is not None
    assert state.plan_path == "", "no plan supplied must record empty, not a guess"


# ── C2: T20c — the CLI boundary ────────────────────────────────────────────


def test_cli_accepts_plan_as_a_path() -> None:
    """C2 — argv wiring: ``--plan`` reaches the namespace typed as a Path."""
    args = build_parser().parse_args(["workflow", "planner,coder", "t", "--plan", "/tmp/P.md"])
    assert args.plan == Path("/tmp/P.md")
    assert build_parser().parse_args(["workflow", "planner,coder", "t"]).plan is None


def test_missing_plan_file_is_rejected_before_anything_runs(tmp_path: Path, capsys: Any) -> None:
    """T20c — a mistyped path fails fast, leaving no artifacts behind.

    Oracle is the exit code AND the absence of a session directory: rejecting
    late would still have written flow_state for a run that never had a
    contract.
    """
    from fa.cli import _cmd_workflow

    run_id = "pp-missing"
    args = build_parser().parse_args(
        [
            "workflow",
            "coder",
            "t",
            "--plan",
            str(tmp_path / "nope.md"),
            "--run-id",
            run_id,
            "--workspace",
            str(tmp_path),
            "--config",
            str(_config(tmp_path)),
        ]
    )

    assert _cmd_workflow(args) == 2
    assert "not found" in capsys.readouterr().err
    assert not workflow_artifact_paths(run_id).flow_state.exists(), "a rejected invocation must leave nothing on disk"


# ── §24 D-1: the build/write seam S12, S13 and S11b all depend on ──────────


def test_build_eval_report_does_not_write_anything(tmp_path: Path) -> None:
    """C0 — parsing must be separable from persisting.

    ``emit_eval_report`` fused parse-and-write, so S12 (drop invented slice
    IDs), S13 (record the ID list) and S11b (override the verdict against
    harness observation) would each have had to rewrite ``eval_report.json``
    after the fact: three writes of one file, a window in which the artifact
    on disk contradicts the routing decision, and a last-writer-wins ordering
    dependency between otherwise independent steps.

    This pins the seam. If ``build_eval_report`` ever starts writing, the
    ``build -> adjust -> write`` pipeline those steps rely on is gone.
    """
    # Watch the WHOLE filesystem surface this call could plausibly touch, not
    # just tmp_path: a regression that writes to the process CWD (the most
    # likely accidental target) would be invisible to a tmp_path-only oracle.
    # Verified by mutation -- the first version of this test missed exactly
    # that mutant.
    monkeyed: list[str] = []
    real_open = open

    def _tracking_open(file, mode="r", *args, **kwargs):  # type: ignore[no-untyped-def]
        if any(flag in str(mode) for flag in ("w", "a", "x", "+")):
            monkeyed.append(str(file))
        return real_open(file, mode, *args, **kwargs)

    cwd_before = set(os.listdir("."))
    with patch("builtins.open", _tracking_open):
        report = build_eval_report(
            "### Verdict\nPASS\n",
            run_id="seam-1",
            plan_id="PLAN-x",
            plan_version=1,
        )

    assert report.verdict == "PASS"
    assert report.plan_id == "PLAN-x"
    assert monkeyed == [], f"build_eval_report must not open anything for writing; got {monkeyed}"
    assert set(os.listdir(".")) == cwd_before, "build_eval_report must not create files"


def test_emit_still_writes_for_callers_that_need_no_adjustment(tmp_path: Path) -> None:
    """C0 — the split must not break the one-call convenience path."""
    from fa.inner_loop.workflow_controller import emit_eval_report

    path = tmp_path / "eval_report.json"
    report = emit_eval_report(
        report_path=path,
        final_text="### Verdict\nREPAIR_REQUIRED\n",
        run_id="seam-2",
        plan_id="PLAN-y",
        plan_version=1,
    )

    assert path.is_file(), "emit_eval_report must still persist the artifact"
    assert json.loads(path.read_text(encoding="utf-8"))["verdict"] == "REPAIR_REQUIRED"
    assert report.route_decision == "return_to_coder"
