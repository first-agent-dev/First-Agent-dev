"""Simulate each Q17 option's LOOP behaviour using the real controller."""
import argparse, json, subprocess, tempfile
from pathlib import Path
from typing import Any
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.workflow_controller import run_workflow, workflow_artifact_paths, workflow_exit_code

def setup():
    tmp=Path(tempfile.mkdtemp())
    subprocess.run(["git","init","-q","."],cwd=tmp,check=True)
    subprocess.run(["git","-c","user.email=t@t","-c","user.name=t","commit","-q","--allow-empty","-m","i"],cwd=tmp,check=True)
    (tmp/"PLAN.md").write_text("# P Plan-ID: X\n### Step S1: a\n### Step S2: b\n")
    (tmp/"models.yaml").write_text("providers: {}\n")
    return tmp

def run(label, eval_text, rid):
    tmp=setup(); calls={"coder":0,"eval":0}
    def stage(a: argparse.Namespace, **kw: Any) -> int:
        calls[a.role]=calls.get(a.role,0)+1
        s=kw.get("outcome_sink")
        if a.role=="eval" and s is not None:
            s.append(SessionOutcome(exit_code=0,stop_reason="stopped_by_llm",turns=1,final_text=eval_text))
        return 0
    rc,st=run_workflow(roles=["coder","eval"],task="t",per_role_task={},mode="adaptive",
      max_repairs=2,max_replans=0,run_id=rid,config=tmp/"models.yaml",workspace=tmp,
      max_turns=1,output_mode="quiet",run_stage_fn=stage,plan_path=tmp/"PLAN.md")
    print(f"{label:34s} status={st.status:16s} exit={workflow_exit_code(rc,st)} "
          f"coder_runs={calls.get('coder',0)} eval_runs={calls.get('eval',0)}")

# (c) warn-only == today: PASS survives
run("(c) warn only  -> PASS","### Verdict\nPASS\n### Step results\n- S1: PASS - ok\n","opt_c")
# (a) REPAIR_REQUIRED: what the loop does
run("(a) REPAIR_REQUIRED","### Verdict\nREPAIR_REQUIRED\n### Route decision\nreturn_to_coder\n","opt_a")
# (b) BLOCKED: what the loop does
run("(b) BLOCKED","### Verdict\nBLOCKED\n### Route decision\nblocked\n","opt_b")
