"""What the judge actually receives, with and without the evidence block."""
import subprocess, tempfile
from pathlib import Path
from fa.inner_loop.workflow_controller import _eval_evidence_block, WorkflowContext, workflow_artifact_paths
tmp=Path(tempfile.mkdtemp())
def g(*a): subprocess.run(["git",*a],cwd=tmp,check=True,capture_output=True)
g("init","-q","."); g("config","user.email","t@t"); g("config","user.name","t")
(tmp/"login.py").write_text("def check_password(p): return verify(p)\n")
g("add","-A"); g("commit","-q","-m","base")
(tmp/"login.py").write_text("def check_password(p): return True  # TODO fix\n")
(tmp/"PLAN.md").write_text("# P Plan-ID: PLAN-login\n### Step S1: harden password check\n")
ctx=WorkflowContext(run_id="r",base_task="Judge whether the coder completed the plan.",
  per_role_task={},artifact_paths=workflow_artifact_paths("r"),config=tmp/"c",
  workspace=tmp,max_turns=1,output_mode="quiet",plan_path=tmp/"PLAN.md")
block=_eval_evidence_block(ctx)
print("========== MODE off  : what the judge receives ==========")
print("Judge whether the coder completed the plan.")
print()
print("========== MODE enforce : what the judge receives ==========")
print("Judge whether the coder completed the plan.")
print()
print(block)
