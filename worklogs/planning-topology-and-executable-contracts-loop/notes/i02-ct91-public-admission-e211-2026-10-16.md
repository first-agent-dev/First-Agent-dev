# E211 — public explicit admission checkpoint, 2026-10-16

**Partial retained I02 implementation, not SLICE6 acceptance or SHIPPED.**
Parent: `e56ace2b56997dafe655b6c43962c4549e07e762`. Own branch:
`arena/86633f17-first-agent-dev`. Q67(a) and Q68(a) explicitly selected by the operator.
No I03 managed acquisition, OS boundary, nested success, all-16-kill, independent/operator DoD,
or full-repository `d9109f4` comparison claim. No STEP checkbox changed.

## Declaration, source review and mechanism

Source-verified before integration: `run_workflow` read an explicit snapshot but did not invoke
admission; adaptive replans used ordinary planner dispatch. Admission helpers/publication from
E208/E209 existed but lacked their mandatory public producer. T0 capture depended on the repair
counter and the context could reread plan text independently. Q67 was a blocking lifecycle
ambiguity; implementation resumed only after explicit (a). Source review later identified an
unratified blanket tool-error rule; Q68 was asked and (a) selected before checkpointing.

Intent: wire CT87/CT91/Q57 repair and CT92/93/94/Q58 through the real public controller, sharing
credits with eval-only replanning, then bind CT71–77/CT86/CT95 verification/eval/T0 to the admitted
snapshot. Supports GAP-06/10/12/15; does not close them or GAP-04/05/I03 foundation.

Exact allowed implementation files: `workflow_controller.py`, `coder_loop.py`,
`tests/test_verify_gate_live.py` under their repository directories. The three additional test
files in the hash table were declared for the precise compatibility migrations below. Decision
and evidence edits are this note, open questions, explicit-admission spec, register and ledger.
No dependency, new backend, generic transaction engine, guessed PlanRef or bootstrap stub.

Production construction:
- One run-local admission authority pins the exact snapshot, baseline state, admitted version,
  shared reserved attempt counter, failure and last actual eval. Initial configured planner is
  free; reserve each scoped attempt before seed/provider, including failed attempts.
- `_run_stage -> _admit_plan` gates coder. Actual FAIL may repair; exception/unexplained zero
  slices is indeterminate. Revalidate every revision and seed from the latest rejected draft.
- Mandatory `_run_admission_repair -> _promote_validated_plan` now exists. Use real scoped CLI
  registry/session writer, immutable validated buffer, existing canonical flock/CAS publication,
  mode/durability checks and owned-candidate cleanup. Cleanup uncertainty blocks publication.
- Reuse existing private descriptor IO/flock/fsync primitives for durable admission barriers,
  verification/eval persistence and immutable T0. Do not infer persistence from best-effort flow.
- Q67 keeps canonical ADMITTED during first eval-only revision; unchanged durable history before
  provider, actual candidate outcome afterward, RETRY only for actual FAIL. No coder until final
  validated/promoted/durably admitted snapshot. No schema weakening or fabricated diagnostics.
- T0 state is independent of repair/replan counters. Capture after admission, once; symmetric
  slice/TESTS topology and exact identity/type checks reject incompatible reuse.
- Verifier and eval use pinned IDs/bytes. Verification attempts contain their PlanRef. Source
  mismatch or missing required artifacts cannot yield DONE in either mode. A successful coder
  still reaches real eval while deadline permits; retain actual judgment, never synthesize it.
- Session loop projects trusted paired tool names before/after result handling. Q68 consumes
  only `fs_write_file`/`pr_prepare` errors for scoped attempts, even if recovered. Read errors may
  recover. Missing/nonzero outcome remains failed; ordinary planner exit behavior is unchanged.
- Admission now respects preexisting deadline checks before gate/initial lock and propagates
  stage deadline exit 124/marker without generic overwrite. Determinate planner-unavailable/
  budget rejection retains runtime exit 1; infrastructure/admission failures remain nonzero.
  Admitted version survives later budget rejection; `workflow_exit_code(0, None)` is nonzero.

DoD/negative proof for this chunk: actual public repair/replan and same-path bytes, no coder/T0
on pre-coder failures, shared credit and rejected-draft progress, immutable T0 across coders and
replan, durable barriers, real eval on post-coder integrity failures, and sensitivity to removing
mandatory producers. `/tests-writing` INJECT/SKILL was read. C1 normal cases mock only provider
IO; faults inject storage/FS effects without replacing roots. C0 covers schema/topology/exit
helpers; C2 preserves CLI dispatch/budget/version oracles; C3 covers real guarded writers and
integrity failures. Normative whole-path acceptance remains explicitly incomplete below.

## Frozen inputs

| File | SHA-256 |
| --- | --- |
| `src/fa/inner_loop/workflow_controller.py` | `9896ba84bfd87bc1760139a0194634e6db66910ca64501647463edaf8fe47778` |
| `src/fa/inner_loop/coder_loop.py` | `fc7cfbdd2de9f063620eb9088c620ca3b1618e7215f41290241f2150a6de935f` |
| `tests/test_verify_gate_live.py` | `21ba17cb182dd02665fc9852a13f46bd4c97d5766b77d64572122e8c60614b78` |
| `tests/test_cli_ergonomics.py` | `aa4377aaf8a63cb70ca888735012bcac5fa18f3988375bd0bdf74147b0261378` |
| `tests/test_plan_reference.py` | `f44bd3658b4ad1768245a0383c0a8f6d66e1ddac151d70c264307232b069d4d4` |
| `tests/test_s8_workflow_controller.py` | `6e835c49f1113597755f1dd7177bd3c6a88d7d1dad22625a0b19b8c25a7da147` |

AST comparison against HEAD: only preexisting live-module definition changed is
`test_ct93_real_stage_dispatch_controls_candidate_writes`. Every other original test/fixture/
class definition there is unchanged. Hashes were rechecked after all 15 mutations.

## TEST-EDITS and compatibility correction

51 new parametrized cases in 22 definitions: 45 public-root cases plus five T0 identity/topology
unit cases and one terminal-exit unit case. Observe/enforce and linear/adaptive are covered where
applicable. The public cases include initial PASS, repair/rejected drafts, Q67/eval retries/shared
credits, storage/fsync/cleanup uncertainty, repeated coders, WARN/structural near-miss,
indeterminate/budget/no-planner/provider/denial/collection failures, pinned actual eval under
integrity failures, nonincrement publication refusal, and both Q68 directions.

Only these old test definitions changed:
1. CT93 real scoped dispatch: expected scoped failure exit 2 for deliberate guarded write errors;
   ordinary exit 0 and every schema/FS/event oracle retained.
2. Plan-path tracking: use the existing valid disposable explicit-plan fixture instead of a
   legacy zero-slice body. Both returned/on-disk path assertions unchanged. Other `_PLAN_BODY`
   tests remain untouched.
3. Three CLI replan tests: terminal FAILED/BLOCKED and exact planner-unavailable/planner-budget
   reasons under Q57, instead of a still-pending REPLAN_REQUIRED. Original exit 1, provider counts,
   no-spin, repair/replan counters and active version assertions preserved.
4. S8 scoped-provider failure: exact `admission/promotion/prepare-failed` replaces free-text
   `exited 2`; add reserved-credit assertion. Exit 2, FAILED and prior eval assertions retained.

An initial broader run had 15 failures (1125 passed/1 deselected, 144.03s): six standing identities
plus nine additional failures. Four deadline cases exposed real gate-before-deadline ordering;
plan-path recording needed a valid fixture; three replan cases needed the approved blocked
state plus retained exit/version semantics; S8 needed the scoped closed reason. These nine were
resolved, not hidden by loosening dispatch/counter oracles. Deadline test source was untouched.
Intermediate correction run: 93 passed/2 standing deadline failures, 43.68s.

## Actual final checks

- Focused live module: **480 passed, 1 deselected, 55.83s; rc 0**. Deselects only the old recursive
  `test_real_workflow_writes_verification_and_supplies_it_to_eval`.
- Focused compatibility: **1031 passed, 6 failed, 2 deselected, 285.86s; rc 1**. Selection below.
  `TestRealWorkflowsSmoke::test_all_real_workflows_clean` was incidentally deselected by the same
  substring; separately ran it unchanged: **1 passed, 0.09s; rc 0**.
- Ruff and Mypy: all six implementation/test files above clean. `git diff --check` clean.
- Pylint production two files: **10/10, rc 0**.
- Production Pyrefly with explicit `--min-severity warn`: **6 warnings, no errors, rc 1**.
  Test-inclusive three-file Pyrefly: **59 errors + 6 warnings, rc 1**. All 59 error-message
  multiplicities exactly match archived E209 baseline; AST verifies old definitions unchanged.
  This is existing unwaived fixture debt, not all-static-green. No suppression added.

Commands (use repository compatible uv, Python 3.13.16):

```bash
uv run --frozen pytest tests/test_verify_gate_live.py -k 'not real_workflow' -q --tb=short
uv run --frozen pytest tests/test_workflow*.py tests/test_s8_workflow_controller.py tests/test_s10c_workflow_exit_contract.py tests/test_cli_ergonomics.py tests/test_plan_reference.py tests/test_plan_precheck.py tests/test_plan_grammar_live_chain.py tests/test_planner_emits_schema4.py tests/test_plan_ids.py tests/test_verify_gate_live.py tests/test_verify_slice.py tests/test_invoke_workflow_tool.py tests/test_coder_loop.py -k 'not real_workflow' -q --tb=short
uv run --frozen pytest tests/test_workflow_hygiene.py::TestRealWorkflowsSmoke::test_all_real_workflows_clean -q
uv run --frozen ruff check src/fa/inner_loop/workflow_controller.py src/fa/inner_loop/coder_loop.py tests/test_verify_gate_live.py tests/test_cli_ergonomics.py tests/test_plan_reference.py tests/test_s8_workflow_controller.py
uv run --frozen mypy src/fa/inner_loop/workflow_controller.py src/fa/inner_loop/coder_loop.py tests/test_verify_gate_live.py tests/test_cli_ergonomics.py tests/test_plan_reference.py tests/test_s8_workflow_controller.py
uv run --frozen pylint src/fa/inner_loop/workflow_controller.py src/fa/inner_loop/coder_loop.py
uv run --frozen pyrefly check --min-severity warn src/fa/inner_loop/workflow_controller.py src/fa/inner_loop/coder_loop.py
uv run --frozen pyrefly check --min-severity warn src/fa/inner_loop/workflow_controller.py src/fa/inner_loop/coder_loop.py tests/test_verify_gate_live.py
```

Six standing failures, none waived (same identities as E208/E209):
- `test_workflow_deadline.py::test_no_deadline_runs_the_full_pipeline`
- `test_workflow_deadline.py::test_generous_deadline_runs_the_full_pipeline`
- `test_workflow_global_history.py::test_nested_workflow_produces_two_rows`
- `test_workflow_no_eval_terminal.py::test_eval_requested_but_no_verdict_fails[linear]`
- `test_workflow_no_eval_terminal.py::test_scratch_pipeline_succeeds_but_is_marked_unjudged`
- `test_workflow_no_eval_terminal.py::test_planner_coder_without_eval_is_also_unjudged`

The first two and two unjudged cases retain old no-automatic-eval expectations; the no-verdict
case differs on `no usable verdict` wording; nested success lacks explicit acquisition/PlanRef.
Fixtures are already valid explicit plans, so invalid-plan assertions are not an explanation.
The command covers a different module inventory from the initial 1125-pass run: compare failure
identities, not totals as if this were the same/full-repo suite. Full-repo baseline still open.

## Supplemental mutation sensitivity — NOT the 16 normative contract×path runs

Each check uses an exact overlay, actual child-import provenance probe, unchanged tests and
fresh JUnit. Required rc 1, nonzero failures, zero runner errors/skips, identical 33 selected
cases. **15/15 detected; harness rc 0**. The helper body replacements supplement producer removals,
not pretend to be their normative directives. No ERROR/timeout/collection failure counted.

| Mutation | Symbol | Cases | Failures | Errors | Skips | rc | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| producer-precheck | `_validate_plan_admission` | 33 | 17 | 0 | 0 | 1 | detected |
| producer-kill-validator | `_validate_plan_admission` | 33 | 17 | 0 | 0 | 1 | detected |
| producer-public-gate | `_run_stage` | 33 | 20 | 0 | 0 | 1 | detected |
| producer-public-publication | `_run_admission_repair` | 33 | 7 | 0 | 0 | 1 | detected |
| producer-durable-barrier | `_record_admission_attempt` | 33 | 21 | 0 | 0 | 1 | detected |
| failed-tool-projection | `_failed_tool_names` | 33 | 7 | 0 | 0 | 1 | detected |
| reserve-shared-credit | `_admit_plan` | 33 | 9 | 0 | 0 | 1 | detected |
| bounded-shared-credit | `_admit_plan` | 33 | 2 | 0 | 0 | 1 | detected |
| source-hash-guard | `_check_admission_source` | 33 | 2 | 0 | 0 | 1 | detected |
| baseline-independent-counter | `_needs_baseline` | 33 | 1 | 0 | 0 | 1 | detected |
| control-integrity-floor | `_mark_integrity_failure` | 33 | 2 | 0 | 0 | 1 | detected |
| owned-candidate-cleanup | `_run_admission_repair` | 33 | 8 | 0 | 0 | 1 | detected |
| publication-prepare-error | `_scoped_stage_failed` | 33 | 2 | 0 | 0 | 1 | detected |
| blanket-tool-error | `_scoped_stage_failed` | 33 | 2 | 0 | 0 | 1 | detected |
| pinned-context-authority | `plan_text` | 33 | 1 | 0 | 0 | 1 | detected |

Reproduction harness, run as `uv run --frozen python /path/to/audit.py` from repository root:

```python
"""Supplemental selected-case audit, not whole-declared-path contract acceptance."""
import ast,hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from fa.inner_loop.slice_verification import CommandOutcome,KillDirective,KillOperator,apply_kill,mutation_overlay,_assert_overlay_wins,_overlay_env
ROOT=Path.cwd();OUT=Path('/home/user/.cache/i02-ct91-mutations');OUT.mkdir(exist_ok=True)
C='src/fa/inner_loop/workflow_controller.py';L='src/fa/inner_loop/coder_loop.py'
SELECT='q68 or (ct91_public_repair_retries_latest_draft_then_promotes and enforce and linear) or (ct91_public_q67_eval_replan and observe) or ct91_public_block_never or ct93_real_stage_dispatch or ct91_terminal_none or (ct91_public_post_coder_integrity and observe) or ct91_public_initial_repair_spends or ct91_t0_reuse_rejects or ct91_public_admission_storage or ct91_public_post_replace_fsync'
CASES=[
('producer-precheck',C,'_validate_plan_admission','KILL','precheck'),
('producer-kill-validator',C,'_validate_plan_admission','KILL','validate_kill_directives'),
('producer-public-gate',C,'_run_stage','KILL','_admit_plan'),
('producer-public-publication',C,'_run_admission_repair','KILL','_promote_validated_plan'),
('producer-durable-barrier',C,'_record_admission_attempt','KILL','write_admission_record'),
('failed-tool-projection',L,'_failed_tool_names',None,'return set()'),
('reserve-shared-credit',C,'_admit_plan','state.planner_calls += 1','state.planner_calls += 0'),
('bounded-shared-credit',C,'_admit_plan','state.planner_calls < state.planner_limit','True'),
('source-hash-guard',C,'_check_admission_source',None,'return None'),
('baseline-independent-counter',C,'_needs_baseline',None,'return progress.repair_round == 0'),
('control-integrity-floor',C,'_mark_integrity_failure',None,'return None'),
('owned-candidate-cleanup',C,'_run_admission_repair','os.unlink(target.name, dir_fd=parent)','None'),
('publication-prepare-error',C,'_scoped_stage_failed','{"fs_write_file", "pr_prepare"}','{"fs_write_file"}'),
('blanket-tool-error',C,'_scoped_stage_failed','not {"fs_write_file", "pr_prepare"}.isdisjoint(sink[-1].failed_tools)','bool(sink[-1].failed_tools)'),
('pinned-context-authority',C,'plan_text','return self.admission.snapshot.text','return self.plan_path.read_text(encoding="utf-8")'),
]
results=[]
for name,rel,symbol,before,after in CASES:
 source=(ROOT/rel).read_text()
 if before=='KILL':
  change=apply_kill(source,KillDirective(KillOperator.REMOVE_CALL,rel,symbol,after,0));assert change.targets==change.edits==1 and change.source
  mutated=change.source
 else:
  nodes=[n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name==symbol];assert len(nodes)==1
  node=nodes[0];lines=source.splitlines(keepends=True);start=node.lineno-1;end=node.end_lineno
  original=''.join(lines[start:end])
  if before is None:
   body_start=node.body[0].lineno-node.lineno
   changed=''.join(original.splitlines(keepends=True)[:body_start])+'    '+after+'\n'
  else:
   assert original.count(before)==1,(name,original.count(before));changed=original.replace(before,after)
  mutated=''.join(lines[:start])+changed+''.join(lines[end:])
 ast.parse(mutated);testhash=hashlib.sha256((ROOT/'tests/test_verify_gate_live.py').read_bytes()).hexdigest()
 with mutation_overlay(ROOT,rel,mutated) as overlay:
  env=_overlay_env(ROOT,overlay);probe=_assert_overlay_wins(rel[4:-3].replace('/','.'),overlay,env,workspace=ROOT)
  assert probe.outcome is CommandOutcome.PASS,probe
  xml=OUT/(name+'.xml');xml.unlink(missing_ok=True)
  run=subprocess.run([sys.executable,'-m','pytest','tests/test_verify_gate_live.py','-k',SELECT,'-q','--tb=short','--junitxml='+str(xml)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
  (OUT/(name+'.log')).write_text(run.stdout+run.stderr)
  assert testhash==hashlib.sha256((ROOT/'tests/test_verify_gate_live.py').read_bytes()).hexdigest()
  tree=ET.parse(xml).getroot();stats={k:sum(int(n.get(k,0)) for n in tree.findall('testsuite')) for k in ['tests','failures','errors','skipped']}
  if results:assert stats['tests']==results[0]['tests'],stats
  r=dict(name=name,path=rel,symbol=symbol,source_sha256=hashlib.sha256(source.encode()).hexdigest(),tests_sha256=testhash,rc=run.returncode,**stats)
  r['killed']=r['rc']==1 and r['failures']>0 and r['errors']==r['skipped']==0
  results.append(r);print(json.dumps(r),flush=True);(OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
assert len(results)==15 and all(r['killed'] for r in results),results

```

This selected-case sensitivity is not Q53(c) whole-path acceptance. The prior CT94 whole-path
attempt and earlier selected audits were stopped after regression discovery, then superseded
again after Q68 changed source; no final verdict from those attempts is claimed. The frozen
unfiltered baseline `uv run --frozen pytest tests/test_verify_gate_live.py -q --tb=short` was also
intentionally stopped after >10 minutes without a result. Observed process tree: outer live
pytest -> kill-check pytest -> verify pytest -> fixture pytest. The old C1 contains nine internal
whole-path kills; at depth-one kill children it can boot another C1, which runs its own declared
checks. Do not call this incomplete baseline PASS, ERROR-free or a mutation proof. The process-tool stop initially left its child group alive; the exact verified baseline group
was subsequently SIGKILLed and a process listing confirmed no remaining pytest children. No completed
normative CT94 whole-path result exists for this frozen source. Do not change depth markers,
narrow TESTS or skip the C1 to manufacture the required evidence.

## Remaining implementation/acceptance and concrete handoff

1. **Next implementation:** CT95 unsupported managed acquisition. Actual
   `src/fa/inner_loop/tools/workflow_tool.py` still constructs a child and calls the controller
   without a PlanRef; it has no acquisition-unavailable guard. Add the specified unavailable
   result before child provider/coder dispatch, no guessed path/glob/context-field bootstrap.
   Test the real invoke_workflow registry/session path with zero child provider calls and no
   false child-start/history claim. This E211 checkpoint does not implement that route.
2. Disposition the six compatibility failures individually under existing Q55/Q57/I03 scope;
   preserve strong stage/count/status/history oracles. Do not weaken production to restore old
   unjudged success or present missing nested acquisition as nested success.
3. Finish the retained SLICE6 clause-by-clause matrix and whole declared-path baseline, then all
   **16** named producer kills, unchanged TESTS path. Budget/report the actual recursive C1 cost;
   no selected subset, manufactured PROVEN or per-contract attribution map. A timeout/error is
   not proof. Discuss any proposed acceptance/fixture-topology policy change explicitly first.
4. Full-repository `d9109f4` test/static comparison, old E174 reporter failure, nine repo-wide Mypy
   diagnostics and 59 local Pyrefly fixture errors remain unwaived. Independent and operator DoD
   remain open. This is a durable major-chunk checkpoint, not acceptance of the slice.
5. I03 owns mandatory execution foundation, managed acquisition, publication/recovery and live-
   host acceptance. Local flock/no-follow/hash checks do not isolate arbitrary PTY/host writers.
   Linux/Docker and PTY stay. Preserve credential redaction and ordinary allowed logging (Q66).

Additional **planned, not executed** host cases (extend E209 ADM-H14–H19; require I03 foundation):
- ADM-H20: real public linear/adaptive × observe/enforce repair, latest draft progress, same-path
  publication, final durable admission before coder; verify actual managed writer identity.
- ADM-H21: initial repair plus eval replan share reserved credits, failed attempts consume credit,
  no reset across phases, one immutable T0 for unchanged topology; no pending/fake-FAIL evidence.
- ADM-H22: held process lock and fsync/storage faults at pre-provider and irreversible post-replace
  barriers, canonical bytes retained and no coder; readers remain permitted, competing managed
  writers blocked. Do not infer whole-host exclusion from local flock.
- ADM-H23: real boundary denies unauthorized mutation; pinned evidence/integrity fail-closed on
  controlled separate publication-target mismatch. Never mutate a mounted overlay's backing
  filesystem; I03 must provide immutable/stable base and exclusive publication protocol first.
- ADM-H24: real read failure recovered versus publication-tool error recovered, actual registry
  outcomes and credit/terminal state under both modes, without changing ordinary planner policy.
- ADM-H25: deadline at admission/scoped-stage/eval boundaries, correct terminal no-eval marker,
  existing/resumed/new session lifecycle and unsupported acquisition refusing child dispatch.

## Captured final focused output

```text
........................................................................ [ 15%]
........................................................................ [ 30%]
........................................................................ [ 45%]
........................................................................ [ 60%]
........................................................................ [ 75%]
........................................................................ [ 90%]
................................................                         [100%]
480 passed, 1 deselected in 55.83s

```

## Captured final compatibility output

```text
................FF........F...................................F.FF...... [  6%]
........................................................................ [ 13%]
........................................................................ [ 20%]
........................................................................ [ 27%]
........................................................................ [ 34%]
........................................................................ [ 41%]
........................................................................ [ 48%]
........................................................................ [ 55%]
........................................................................ [ 62%]
........................................................................ [ 69%]
........................................................................ [ 76%]
........................................................................ [ 83%]
........................................................................ [ 90%]
........................................................................ [ 97%]
.............................                                            [100%]
=================================== FAILURES ===================================
___________________ test_no_deadline_runs_the_full_pipeline ____________________
tests/test_workflow_deadline.py:194: in test_no_deadline_runs_the_full_pipeline
    assert stage.roles == roles, "the whole pipeline must still run without a deadline"
E   AssertionError: the whole pipeline must still run without a deadline
E   assert ['planner', 'coder', 'eval'] == ['planner', 'coder']
E
E     Left contains one more item: 'eval'
E     Use -v to get more diff
----------------------------- Captured stderr call -----------------------------
fa workflow: run_id=dl-none mode=linear roles=planner→coder→eval

fa workflow ─ stage 1/3: planner

fa workflow ─ stage 2/3: coder
fa workflow: verify gate mode=observe blocking=False persisted=True artifact=/tmp/pytest-of-user/pytest-4992/fa-state16/session-log/dl-none/verification.json

fa workflow ─ stage 3/3: eval

fa workflow: 3 stage(s) ran (run_id=dl-none); verification route=blocked — not accepted.
------------------------------ Captured log call -------------------------------
WARNING  fa.inner_loop.workflow_controller:workflow_controller.py:2746 workflow global_history export failed for dl-none: role 'providers': empty chain — no providers configured for this role. Fix: add at least one chain entry under the 'chain:' key for role 'providers' in ~/.fa/models.yaml.
________________ test_generous_deadline_runs_the_full_pipeline _________________
tests/test_workflow_deadline.py:211: in test_generous_deadline_runs_the_full_pipeline
    assert stage.roles == roles
E   AssertionError: assert ['planner', 'coder', 'eval'] == ['planner', 'coder']
E
E     Left contains one more item: 'eval'
E     Use -v to get more diff
----------------------------- Captured stderr call -----------------------------
fa workflow: run_id=dl-generous mode=linear roles=planner→coder→eval

fa workflow ─ stage 1/3: planner

fa workflow ─ stage 2/3: coder
fa workflow: verify gate mode=observe blocking=False persisted=True artifact=/tmp/pytest-of-user/pytest-4992/fa-state17/session-log/dl-generous/verification.json

fa workflow ─ stage 3/3: eval

fa workflow: 3 stage(s) ran (run_id=dl-generous); verification route=blocked — not accepted.
------------------------------ Captured log call -------------------------------
WARNING  fa.inner_loop.workflow_controller:workflow_controller.py:2746 workflow global_history export failed for dl-generous: role 'providers': empty chain — no providers configured for this role. Fix: add at least one chain entry under the 'chain:' key for role 'providers' in ~/.fa/models.yaml.
____________________ test_nested_workflow_produces_two_rows ____________________
tests/test_workflow_global_history.py:280: in test_nested_workflow_produces_two_rows
    assert child_row is not None, f"nested workflow wrote no row for {child_run_id}"
E   AssertionError: nested workflow wrote no row for chat-parent-wf1
E   assert None is not None
----------------------------- Captured stderr call -----------------------------
fa workflow: invalid plan reference: missing
_______________ test_eval_requested_but_no_verdict_fails[linear] _______________
tests/test_workflow_no_eval_terminal.py:141: in test_eval_requested_but_no_verdict_fails
    assert "no verdict" in payload["blocked_reason"].lower()
E   AssertionError: assert 'no verdict' in 'workflow blocked after eval: eval stage produced no usable verdict'
E    +  where 'workflow blocked after eval: eval stage produced no usable verdict' = <built-in method lower of str object at 0x7f1db49fa1e0>()
E    +    where <built-in method lower of str object at 0x7f1db49fa1e0> = 'workflow blocked after eval: eval stage produced no usable verdict'.lower
----------------------------- Captured stderr call -----------------------------
fa workflow: run_id=r-linear mode=linear roles=planner→coder→eval

fa workflow ─ stage 1/3: planner

fa workflow ─ stage 2/3: coder
fa workflow: verify gate mode=observe blocking=False persisted=True artifact=/tmp/pytest-of-user/pytest-4992/fa-state62/session-log/r-linear/verification.json

fa workflow ─ stage 3/3: eval

fa workflow: 3 stage(s) ran (run_id=r-linear); verification route=blocked — not accepted.
------------------------------ Captured log call -------------------------------
WARNING  fa.inner_loop.workflow_controller:workflow_controller.py:2746 workflow global_history export failed for r-linear: role 'providers': empty chain — no providers configured for this role. Fix: add at least one chain entry under the 'chain:' key for role 'providers' in ~/.fa/models.yaml.
____________ test_scratch_pipeline_succeeds_but_is_marked_unjudged _____________
tests/test_workflow_no_eval_terminal.py:156: in test_scratch_pipeline_succeeds_but_is_marked_unjudged
    assert exit_code == 0, "a scratch pipeline must still succeed"
E   AssertionError: a scratch pipeline must still succeed
E   assert 1 == 0
----------------------------- Captured stderr call -----------------------------
fa workflow: run_id=r-scratch mode=linear roles=coder→eval

fa workflow ─ stage 1/2: coder
fa workflow: verify gate mode=observe blocking=False persisted=True artifact=/tmp/pytest-of-user/pytest-4992/fa-state64/session-log/r-scratch/verification.json

fa workflow ─ stage 2/2: eval

fa workflow: 2 stage(s) ran (run_id=r-scratch); verification route=blocked — not accepted.
------------------------------ Captured log call -------------------------------
WARNING  fa.inner_loop.workflow_controller:workflow_controller.py:2746 workflow global_history export failed for r-scratch: role 'providers': empty chain — no providers configured for this role. Fix: add at least one chain entry under the 'chain:' key for role 'providers' in ~/.fa/models.yaml.
_______________ test_planner_coder_without_eval_is_also_unjudged _______________
tests/test_workflow_no_eval_terminal.py:166: in test_planner_coder_without_eval_is_also_unjudged
    assert exit_code == 0
E   assert 1 == 0
----------------------------- Captured stderr call -----------------------------
fa workflow: run_id=r-pc mode=linear roles=planner→coder→eval

fa workflow ─ stage 1/3: planner

fa workflow ─ stage 2/3: coder
fa workflow: verify gate mode=observe blocking=False persisted=True artifact=/tmp/pytest-of-user/pytest-4992/fa-state65/session-log/r-pc/verification.json

fa workflow ─ stage 3/3: eval

fa workflow: 3 stage(s) ran (run_id=r-pc); verification route=blocked — not accepted.
------------------------------ Captured log call -------------------------------
WARNING  fa.inner_loop.workflow_controller:workflow_controller.py:2746 workflow global_history export failed for r-pc: role 'providers': empty chain — no providers configured for this role. Fix: add at least one chain entry under the 'chain:' key for role 'providers' in ~/.fa/models.yaml.
=========================== short test summary info ============================
FAILED tests/test_workflow_deadline.py::test_no_deadline_runs_the_full_pipeline
FAILED tests/test_workflow_deadline.py::test_generous_deadline_runs_the_full_pipeline
FAILED tests/test_workflow_global_history.py::test_nested_workflow_produces_two_rows
FAILED tests/test_workflow_no_eval_terminal.py::test_eval_requested_but_no_verdict_fails[linear]
FAILED tests/test_workflow_no_eval_terminal.py::test_scratch_pipeline_succeeds_but_is_marked_unjudged
FAILED tests/test_workflow_no_eval_terminal.py::test_planner_coder_without_eval_is_also_unjudged
6 failed, 1031 passed, 2 deselected in 285.86s (0:04:45)

```
