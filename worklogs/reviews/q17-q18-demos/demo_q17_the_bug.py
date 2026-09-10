"""Produce REAL transcript output for each Q17 option, for the report."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.workflow_controller import run_workflow, workflow_artifact_paths, workflow_exit_code


def setup():
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q", "."], cwd=tmp, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"],
        cwd=tmp,
        check=True,
    )
    plan = "# P  Plan-ID: PLAN-demo\n" + "".join(f"### Step S{i}: task {i}\n" for i in range(1, 6))
    (tmp / "PLAN.md").write_text(plan)
    (tmp / "models.yaml").write_text("providers: {}\n")
    return tmp


# Scenario: plan has S1..S5. The judge only reports on S1.
tmp = setup()
coder_calls = {"n": 0}


def stage(a: argparse.Namespace, **kw: Any) -> int:
    if a.role == "coder":
        coder_calls["n"] += 1
    s = kw.get("outcome_sink")
    if a.role == "eval" and s is not None:
        s.append(
            SessionOutcome(
                exit_code=0,
                stop_reason="stopped_by_llm",
                turns=1,
                final_text="### Verdict\nPASS\n### Step results\n- S1: PASS - looks good to me\n",
            )
        )
    return 0


rc, state = run_workflow(
    roles=["coder", "eval"],
    task="implement the plan",
    per_role_task={},
    mode="adaptive",
    max_repairs=2,
    max_replans=0,
    run_id="q17demo",
    config=tmp / "models.yaml",
    workspace=tmp,
    max_turns=1,
    output_mode="quiet",
    run_stage_fn=stage,
    plan_path=tmp / "PLAN.md",
)
d = json.loads(Path(workflow_artifact_paths("q17demo").eval_report).read_text())
print("PLAN DECLARES : S1 S2 S3 S4 S5")
print("JUDGE REPORTED:", [s["step_id"] for s in d["step_results"]])
print("unreported_slices in artifact:", d["unreported_slices"])
print("verdict:", d["verdict"], "| terminal status:", state.status)
print("EXIT CODE:", workflow_exit_code(rc, state), " <- 0 means 'success' to CI/operator")
print("coder stages run:", coder_calls["n"])
