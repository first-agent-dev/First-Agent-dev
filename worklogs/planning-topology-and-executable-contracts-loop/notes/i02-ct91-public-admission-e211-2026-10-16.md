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

import ast, hashlib, json, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path
from fa.inner_loop.slice_verification import (
    CommandOutcome,
    KillDirective,
    KillOperator,
    apply_kill,
    mutation_overlay,
    _assert_overlay_wins,
    _overlay_env,
)

ROOT = Path.cwd()
OUT = Path("/home/user/.cache/i02-ct91-mutations")
OUT.mkdir(exist_ok=True)
C = "src/fa/inner_loop/workflow_controller.py"
L = "src/fa/inner_loop/coder_loop.py"
SELECT = "q68 or (ct91_public_repair_retries_latest_draft_then_promotes and enforce and linear) or (ct91_public_q67_eval_replan and observe) or ct91_public_block_never or ct93_real_stage_dispatch or ct91_terminal_none or (ct91_public_post_coder_integrity and observe) or ct91_public_initial_repair_spends or ct91_t0_reuse_rejects or ct91_public_admission_storage or ct91_public_post_replace_fsync"
CASES = [
    ("producer-precheck", C, "_validate_plan_admission", "KILL", "precheck"),
    ("producer-kill-validator", C, "_validate_plan_admission", "KILL", "validate_kill_directives"),
    ("producer-public-gate", C, "_run_stage", "KILL", "_admit_plan"),
    ("producer-public-publication", C, "_run_admission_repair", "KILL", "_promote_validated_plan"),
    ("producer-durable-barrier", C, "_record_admission_attempt", "KILL", "write_admission_record"),
    ("failed-tool-projection", L, "_failed_tool_names", None, "return set()"),
    ("reserve-shared-credit", C, "_admit_plan", "state.planner_calls += 1", "state.planner_calls += 0"),
    ("bounded-shared-credit", C, "_admit_plan", "state.planner_calls < state.planner_limit", "True"),
    ("source-hash-guard", C, "_check_admission_source", None, "return None"),
    ("baseline-independent-counter", C, "_needs_baseline", None, "return progress.repair_round == 0"),
    ("control-integrity-floor", C, "_mark_integrity_failure", None, "return None"),
    ("owned-candidate-cleanup", C, "_run_admission_repair", "os.unlink(target.name, dir_fd=parent)", "None"),
    ("publication-prepare-error", C, "_scoped_stage_failed", '{"fs_write_file", "pr_prepare"}', '{"fs_write_file"}'),
    (
        "blanket-tool-error",
        C,
        "_scoped_stage_failed",
        'not {"fs_write_file", "pr_prepare"}.isdisjoint(sink[-1].failed_tools)',
        "bool(sink[-1].failed_tools)",
    ),
    (
        "pinned-context-authority",
        C,
        "plan_text",
        "return self.admission.snapshot.text",
        'return self.plan_path.read_text(encoding="utf-8")',
    ),
]
results = []
for name, rel, symbol, before, after in CASES:
    source = (ROOT / rel).read_text()
    if before == "KILL":
        change = apply_kill(source, KillDirective(KillOperator.REMOVE_CALL, rel, symbol, after, 0))
        assert change.targets == change.edits == 1 and change.source
        mutated = change.source
    else:
        nodes = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == symbol]
        assert len(nodes) == 1
        node = nodes[0]
        lines = source.splitlines(keepends=True)
        start = node.lineno - 1
        end = node.end_lineno
        original = "".join(lines[start:end])
        if before is None:
            body_start = node.body[0].lineno - node.lineno
            changed = "".join(original.splitlines(keepends=True)[:body_start]) + "    " + after + "\n"
        else:
            assert original.count(before) == 1, (name, original.count(before))
            changed = original.replace(before, after)
        mutated = "".join(lines[:start]) + changed + "".join(lines[end:])
    ast.parse(mutated)
    testhash = hashlib.sha256((ROOT / "tests/test_verify_gate_live.py").read_bytes()).hexdigest()
    with mutation_overlay(ROOT, rel, mutated) as overlay:
        env = _overlay_env(ROOT, overlay)
        probe = _assert_overlay_wins(rel[4:-3].replace("/", "."), overlay, env, workspace=ROOT)
        assert probe.outcome is CommandOutcome.PASS, probe
        xml = OUT / (name + ".xml")
        xml.unlink(missing_ok=True)
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_verify_gate_live.py",
                "-k",
                SELECT,
                "-q",
                "--tb=short",
                "--junitxml=" + str(xml),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        (OUT / (name + ".log")).write_text(run.stdout + run.stderr)
        assert testhash == hashlib.sha256((ROOT / "tests/test_verify_gate_live.py").read_bytes()).hexdigest()
        tree = ET.parse(xml).getroot()
        stats = {
            k: sum(int(n.get(k, 0)) for n in tree.findall("testsuite"))
            for k in ["tests", "failures", "errors", "skipped"]
        }
        if results:
            assert stats["tests"] == results[0]["tests"], stats
        r = dict(
            name=name,
            path=rel,
            symbol=symbol,
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            tests_sha256=testhash,
            rc=run.returncode,
            **stats,
        )
        r["killed"] = r["rc"] == 1 and r["failures"] > 0 and r["errors"] == r["skipped"] == 0
        results.append(r)
        print(json.dumps(r), flush=True)
        (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
assert len(results) == 15 and all(r["killed"] for r in results), results
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


## E212 continuation — remaining-plan architecture/readiness review and Q69/Q70

Review base: `e94b62b6dcc3db27022feca823eb863693834de8`. This section supersedes E211's
remaining-work statements only where actual results below say so. It is **not** independent
review, operator acceptance, I02 SHIPPED or I03 completion. No STEP checkbox is newly checked.

### Pre-edit scope and architectural findings

Declared CT95, STEP13/16, Q69/Q70, GAP-06/10/15; supporting STEP5–7/14/17 evidence. Reviewed
`workflow_tool`, real CLI context injection, SessionManager.begin_run and CLI private-context checks,
verification overlays/JUnit classification, all 16 normative targets, current explicit spec,
retained DoD and `/tests-writing`. The remaining architecture is sound for **local explicit-plan
SLICE6**, not managed deployment. Found three executable-plan defects: STEP16's empty selector,
STEP14's incomplete selector, and C1's recursive verification cost. Corrected selectors and
required the unmutated whole-bank baseline before STEP17; fixed the duplicate spec section 6.

| Remaining work | Existing mechanism / proof ground | Reachability / still required |
|---|---|---|
| STEP9/10/12 | Shared pure request/admission validators, actual scoped planner, durable admission and exact-buffer same-path publication; E211 real-root matrix | Implementation exists; full-file and producer evidence, full-repo comparison/dispositions and review still required. No helper-only acceptance. |
| STEP13 | Read-only workspace resolution and preflight; new coder-only tool guard, genuine child session authority for supported noncoders | Q70 resolves the prior overbroad blocking ambiguity. Successful managed acquisition remains I03, not a retained I02 requirement. |
| STEP14 | Independent T0 state and symmetric identity; repeated configured coder/eval-replan tests | Selector now includes those actual test names. Whole-file proof must retain the once-only T0 and uncertainty barriers. |
| STEP5–7/16 | Actual controller→CLI→drive_session; provider IO seam; real guarded filesystem/session/eval artifacts | Q69 removes recursive fixture cost without deleting the public C1 or narrowing normative TESTS. Measured full-file baseline is finite. |
| STEP17 | 16 unique named producer directives, original production overlay/provenance/JUnit classifier, complete declared path | No test mapping or selected mutants. All 16 individual valid reports and source restoration required; errors/timeout cannot pass. |
| Local DoD | Isolated archive d9109f4 comparison, same locked dependencies/Python, just test/check, exact manifests and failure dispositions | Reachable but not discharged by these focused results. Baseline contamination, absent terminal summary or unexplained failure blocks. |
| Review/signoff | Independent revised-plan/source/evidence review and operator-reviewed local DoD | Still explicitly open; this author's source review cannot substitute. I03 migration is ownership, not delivered proof. |

Q69 and Q70 were blocking choices; the operator approved fixture factoring and explicitly selected
coder-containing-only refusal. Decisions are recorded in open questions and spec §7. No runtime
recursion-marker change, guessed plan, public PlanRef schema extension, acquisition stub, new
admission state, role-wide delegation ban or normative-bank reduction was introduced.

Exact allowed code/tests: `src/fa/inner_loop/tools/workflow_tool.py`,
`tests/test_invoke_workflow_tool.py`, `tests/test_verify_gate_live.py`,
`tests/test_workflow_global_history.py`, `tests/_chat_registry_fixture.py`; the two separately
predeclared new fixture files `tests/fixtures/i02_gate_probe.py` and `i02_gate_subject.py`.
The later precise Q55 compatibility declaration additionally allowed `tests/test_workflow_deadline.py`
and `tests/test_workflow_no_eval_terminal.py`. Evidence/authority: current plan, explicit spec,
open questions, this existing note, register and ledger. No controller/coder-loop/verifier runtime
code changed in this chunk. Source branch remains arena/86633f17-first-agent-dev.

Current→target/mechanism: coder/default invocation formerly reached an unsupported path; now the
named `_requires_acquisition` guard refuses before candidate identity, handoff, artifacts/provider.
For noncoders, forwarding the parent's RunContext would fail actual run binding validation; now
`_child_run_context` checks trusted parent/session field consistency and uses existing SessionManager.begin_run to allocate the
child's own authority. Pure request validation precedes allocation for supported noncoder input;
structured validation/context failure does not consume invocation credit. Retain existing budget,
reentrancy, deadline, handoff, exception isolation and legacy unbound behavior. No new backend.

### TEST-EDITS and test classes

- **Q69 C1:** only the original constructed plan selects the whole nonrecursive leaf; its default
  helper TESTS path is unchanged. Copy the two leaf fixtures into that temporary workspace.
  The leaf exercises real workflow/CLI/session with provider IO only, two independently owned
  slice commands, one failing global command with once marker, independent baseline and actual
  typed eval/Harness evidence. All nine original internal mutations remain in the outer C1.
- **Q70 C0:** supported forwarding cases use planner/eval, preserving parameter/exception/deadline
  oracles. Five refusal variants assert no controller/handoff and no consumed child identity.
  Three invalid noncoder request cases prove pre-allocation validation and next successful wf1.
- **Q70 C1:** five normal `_cmd_run` chat→actual registry→invoke_workflow compositions. Provider IO
  alone is mocked. Default/coder refusal asserts error, zero child provider/binding/directory/
  history; planner, planner/eval and eval assert actual sequence, one session with distinct child
  binding/event streams, DONE, separate parent+child history rows and no admission fabrication.
- **Q55 compatibility:** successful deadline fixtures now return typed PASS for the automatically
  inserted real eval obligation; retain exact deadline marker/exit and stage-count assertions.
  Planner-only unjudged success remains positive. Coder omission now requires inserted eval and
  missing-judgment fail-closed negative pairs; preserve exact mode-specific refusal reason.
  Historical global-history delegation uses supported planner/eval with real transport/secrets.
- **Typing only:** move raw malformed-request overrides inside `_request_input(**overrides)` with
  its existing `dict[str, Any]` boundary. All invalid values, root calls and assertions remain;
  no ignores, weakened runtime annotations or diagnostic suppression. Remove an unnecessary str
  conversion on an already-str path. Shared chat fixture accepts typed transport/secrets.

C2 deadline/argument migrations and existing C3 filesystem oracles remain in the bank. New policy
failure behavior is observable through real provider/context/artifact producers; no fake gate
verdict, substituted composition root or assertion reduction. Supplemental guard/context removals
are additional to, not replacements for, the 16 normative contract×path runs.

### Actual results before normative audit finalization

Environment: locally compiled CPython 3.13.16, frozen uv.lock/all extras, uv 0.13.1. SSL manually
built against installed OpenSSL 3.0.20; ssl/sqlite3/zlib/ctypes imported successfully. This runtime
lacks optional bz2/lzma/readline modules; do not describe it as an identical complete stock build.
No dependency/lock change. Commands below use the supported uv launcher so verification child
`python` resolves the project interpreter. Direct `.venv/bin/pytest` without that PATH activation
caused one broad run to fail closed at baseline-unavailable (30failed/568passed/1deselected31.44s);
that environment-misconfigured run is NOT mutation/acceptance evidence.

- Standalone whole leaf: **1passed3.04s**.
- Four compatibility/delegation modules after exact Q55 reason fix: **110passed14.92s**.
- New normal CLI/chat `-k acquisition_unavailable`: **5passed481deselected2.05s**.
- `uv run --frozen --no-sync pytest tests/test_verify_gate_live.py -q --tb=short
  --junitxml=/home/user/.cache/fa-runtime/ct95-whole.xml`: **486passed106.92s**, rc0,
  no deselection/skips. This includes the original whole C1 and all nine internal kills.
- Ruff check, Mypy nine changed implementation/test files: clean; Pyrefly with min-severity warn:
  **0 diagnostics (1 pre-existing suppressed)**, rc0. No new suppression added. Production
  Pylint: **10/10**. `git diff --check`: clean. Three raw-fixture formatting deltas remain to be
  canonicalized before final candidate proof; no claim that full format/full-repo checks passed.
- Current plan precheck: PASS, eight WARN, zero FAIL; strict extractor/IDs unchanged. A first
  diagnostic-print command incorrectly iterated PrecheckReport and raised TypeError; rerun used
  its real `.diagnostics`/`.ok` API. That tooling mistake is not a validator result or proof.

Normative audit and final source/version results follow below when complete. Full-repository
baseline/candidate manifests, just test/check, broad static dispositions, independent/operator
review remain open. Do not infer them from the whole live-gate file or Q69/Q70 approval.


### Final-byte baseline and broader gate execution

Canonicalized the three raw-input fixture formatting deltas; added three C0 actual-session-API
cases for missing session, missing run and mismatched parent run fields, all refusing before child
allocation/provider. Initial construction of those three C0 fixtures exposed an invalid workspace
override and then an incorrect begin_run keyword; these were test-setup failures, corrected using
the real approved workspace root and requested_run_id API. No fake SessionContext/manager added.
The final unmutated combined invocation includes the **entire** public file, four compatibility/
delegation modules and both leaf files: **604passed117.09s**, rc0, no deselection/skips. Final
changed-file Ruff check/format, Mypy and Pyrefly are clean (nine files, zero new suppressions).
The final public-file/producer inputs are frozen for the repeated 16+2 full-path audit.

`just check` and an isolated archived d9109f4 `just test` have been started with separate tree-local
environments, identical uv.lock/Python/dependencies and verified fa module origins. Their outcomes
must be recorded below; starting a command is not a completed gate. Full-tree lint reports older
formatting debt beyond this chunk, Mypy currently reports eight diagnostics in four files, and
current authoring-check remains red. `_lint` short-circuited at format, so deptry/Pylint are also
run individually rather than silently counting unexecuted subgates as passed. Deptry passed; the
first separate Pylint batch timed out at the tool boundary after 60s and its continuation status
was not usable, so only that subgate is repeated under process tracking with a durable rc file.

The read-only workspace readiness check returned rc75 / degraded_environment / hook_seat_collision:
Arena's existing foreign commit-msg hook is not the FA-managed hook. Preserved it without changing
hook ownership/configuration; no bootstrap-ready or hook-bypass claim. Normal git uses that actual
Arena hook. This is an environment blocker, not a green DoD disposition.


### E212 reproducible full-path audit

The production execution/classification path is reused, not a replacement verifier: apply_kill →
mutation_overlay → actual import provenance → production run_commands → fresh UUID-bound JUnit →
production _kill_check_result. The declaration is parsed from SLICE6, not hand-mapped to test IDs.
Each normative invocation runs the complete TESTS path; four isolated overlays run concurrently,
with the production timeout unchanged. A separately collected complete manifest is compared with
every result's exact nodeids. Root source/test bytes are hashed before and after every invocation.
Fresh artifact paths and UUIDs prohibit stale reports. Failed collection/setup/teardown reports,
runner/timeout errors or skips cannot satisfy the final assertions. Q53(c) attribution risk remains:
a slice-wide failure proves sensitivity, not which individual assertion establishes a contract.
No contract→nodeid mapping or new clean-control policy is introduced.

Artifacts stay outside Git under `/home/user/.cache/fa-runtime/slice6-final-audit/` (inputs,
baseline-collection, per-contract JSON/XML, combined results); the retained table/hashes below
survive independently of that cache. Reproduce from the repository root after frozen all-extra
setup with `uv run --frozen --no-sync python <audit-script>`:

```python
"""E212: full declared-path audit using production overlay/provenance/runner/JUnit classifier."""

import concurrent.futures, dataclasses, hashlib, json, shlex, subprocess, sys, time, uuid
from pathlib import Path
from fa.inner_loop.plan_ids import extract_plan_ids
from fa.inner_loop import slice_verification as v

ROOT = Path.cwd()
OUT = Path("/home/user/.cache/fa-runtime/slice6-final-audit")
OUT.mkdir(exist_ok=True)
PLAN = (
    ROOT
    / "worklogs/planning-topology-and-executable-contracts-loop/increments/increment-02-verify-gate-and-kill-checks.md"
)
record = next(r for r in extract_plan_ids(PLAN.read_text()).slice_records if r.slice_id == "SLICE6")
assert record.test_paths == ("tests/test_verify_gate_live.py",)
cases = list(v.parse_kill_directives(record).items())
assert len(cases) == 16
cases += [
    (
        "SUP-GUARD",
        v.KillDirective(
            v.KillOperator.REMOVE_CALL,
            "src/fa/inner_loop/tools/workflow_tool.py",
            "build_invoke_workflow_tool.handler",
            "_requires_acquisition",
            0,
        ),
    ),
    (
        "SUP-CONTEXT",
        v.KillDirective(
            v.KillOperator.REMOVE_CALL, "src/fa/inner_loop/tools/workflow_tool.py", "_child_run_context", "begin_run", 0
        ),
    ),
]
watched = sorted(
    set(
        [d.path for _, d in cases]
        + ["tests/test_verify_gate_live.py", "tests/fixtures/i02_gate_probe.py", "tests/fixtures/i02_gate_subject.py"]
    )
)


def hashes():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in watched}


frozen = hashes()
(OUT / "inputs.json").write_text(json.dumps(frozen, indent=2) + "\n")
col = subprocess.run(
    [sys.executable, "-m", "pytest", *record.test_paths, "--collect-only", "-q"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=True,
)
manifest = sorted(l for l in col.stdout.splitlines() if l.startswith("tests/test_verify_gate_live.py::"))
assert len(manifest) == 486, len(manifest)
(OUT / "baseline-collection.json").write_text(json.dumps(manifest, indent=2) + "\n")


def run(case):
    name, d = case
    started = time.monotonic()
    source = (ROOT / d.path).read_text()
    a = v.apply_kill(source, d)
    assert a.targets == a.edits == 1 and a.source is not None, (name, a)
    report_path = OUT / (name + ".xml")
    report_path.unlink(missing_ok=True)
    with v.mutation_overlay(ROOT, d.path, a.source) as overlay:
        env = v._overlay_env(ROOT, overlay)
        probe = v._assert_overlay_wins(v._module_name(d.path), overlay, env, workspace=ROOT)
        assert probe.outcome is v.CommandOutcome.PASS, (name, probe)
        run_id = uuid.uuid4().hex
        env = v._gate_subprocess_env(ROOT, base_env=env, kill_check=True)
        env[v.JUNIT_RUN_ID_ENV] = run_id
        command = (
            v.KILL_CHECK_COMMAND.format(path=shlex.join(record.test_paths))
            + " -p fa.inner_loop.junit_nodeid_plugin --junitxml="
            + shlex.quote(str(report_path))
        )
        (result,) = v.run_commands((command,), workspace=ROOT, env=env)
        report, detail = v._parse_junit_report(report_path, run_id=run_id)
    verdict = v._kill_check_result(d, ", ".join(record.test_paths), started, result, report, detail)
    summary = {
        "name": name,
        "directive": dataclasses.asdict(d),
        "targets": a.targets,
        "edits": a.edits,
        "command": command,
        "probe": dataclasses.asdict(probe),
        "runner": dataclasses.asdict(result),
        "check": dataclasses.asdict(verdict),
        "run_id": run_id,
        "report_detail": detail,
        "nodeids_match": report is not None and sorted(report.outcomes) == manifest,
        "outcomes": dict(report.outcomes) if report else None,
    }
    if report:
        summary["counts"] = {
            k: sum(x.value == k for x in report.outcomes.values()) for k in ["passed", "failed", "skipped"]
        }
    (OUT / (name + ".json")).write_text(json.dumps(summary, indent=2, default=str) + "\n")
    assert hashes() == frozen, (name, "source/test input changed")
    print(
        json.dumps(
            {
                "name": name,
                "verdict": verdict.verdict.value,
                "rc": result.exit_code,
                "duration": round(verdict.duration_s, 2),
                "counts": summary.get("counts"),
                "nodeids_match": summary["nodeids_match"],
                "detail": verdict.detail,
            }
        ),
        flush=True,
    )
    return summary


results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for done in concurrent.futures.as_completed([pool.submit(run, c) for c in cases]):
        results.append(done.result())
        (OUT / "results.json").write_text(json.dumps(results, indent=2, default=str) + "\n")
assert len(results) == 18
assert all(
    r["check"]["verdict"] is v.SliceVerdict.PROVEN and r["nodeids_match"] and r["counts"]["skipped"] == 0
    for r in results
), [(r["name"], r["check"]) for r in results]
assert hashes() == frozen
print("ALL_16_NORMATIVE_PLUS_2_SUPPLEMENTAL_PROVEN; unchanged inputs; exact whole-path manifests", flush=True)
```


### Additional measured gate identities and handoff scope

After source review and a pre-edit declaration, the session-close mirror `worklogs/HANDOFF.md`
is updated only to route the next agent to E212/current plan/spec/decisions and exact unfinished
work; unrelated old S18/doc-hygiene instructions remain historical. Doc-maintenance skill read.
No new knowledge/worklog file, ADR, term, index entry, branch or public schema was introduced.

- Final tool module tests: **91passed2.11s**, rc0 after canonical formatting.
- Separate full-tree deptry: PASS. Process-tracked Pylint src/fa: rc0, **10/10**.
- Isolated d9109f4 Mypy: **8 errors/4 files/443 files checked**, rc1. Candidate: **8 errors/4
  files/450 checked**, rc1. Same path/code/message identities (two mutation-overlay line numbers
  shift by one); not a reviewed waiver. Exact diagnostics: plan_ids.py:877 var-annotated inside;
  test_skill_grammar_emit.py:70 no-any-return; test_slice_verification_runner.py:88,89,321
  comparison-overlap and :150 var-annotated; test_mutation_overlay.py:144/145 attr-defined shutil
  and :555/556 comparison-overlap. Retain all eight for operator-reviewed disposition.
- Candidate Pyrefly full project: rc0, **0 errors (139 suppressed, 52 warnings not shown)** by
  existing config. No new suppression. This is not a warning-free whole-project claim.
- Authoring baseline: rc1, **5** existing export-completeness blocks: BaselineCapture,
  capture_baseline, load_verify_baseline, write_verification, EVAL_VERIFICATION_MAX_CHARS.
  Candidate: rc1, those five plus **3 new** public symbols absent from __all__:
  WorkflowAdmission, AdmissionDiagnostic, PlanAdmissionValidation. These three are new blocking
  work, not a baseline disposition or accepted API expansion. Correct intended visibility and
  repeat affected static/runtime proof before local acceptance.
- Candidate lock, four contract guards and shell syntax passed. Full lint stops at broader
  formatting debt; no blanket whole-tree formatting/legacy-test rewrite in this chunk.

Candidate full suite collected5027; baseline4477, verified separate editable module origins.
Both existing just test commands are still running at this checkpoint until explicit final status
is appended. Do not compare totals alone, claim no new failures, or create local-acceptance.md
from partial output. The old WindowsPath reporter problem remains a risk, not a waived gate.


### Final E212 normative results — completed, rc0

Final formatted-source audit completed with **all16 normative +2 supplemental PROVEN**.
Each invocation executed the entire exact486-nodeid public bank, rc1 with actual call-phase
failures, zero errors/skips and valid fresh UUID-bound JUnit. Every producer resolved uniquely
(one target/one edit), actual overlay import probe passed, and every frozen input hash below
remained unchanged after every invocation. No collector/runner/timeout/infra error was accepted.
Four-way concurrency; unchanged production600s budget. Sum of measured invocation durations: **3850.30s** (overlapping, not wall time).

| Contract | Producer removed / neutralised | Passed | Failed | Errors / skipped | Elapsed s | Invocation UUID | XML SHA256 |
|---|---|---:|---:|---|---:|---|---|
| CT71 | `_run_stage → verify_plan` | 452 | 34 | 0 / 0 | 224.90 | `aa38910bafb141778dca1816cd94e9ed` | `b51b84c1dcbe113c635e0bdde7f3ee1bae5f00cfe0de47f2d63415eec243c314` |
| CT72 | `_effective_controller_route (neutralise)` | 473 | 13 | 0 / 0 | 319.43 | `37f44c0a93a54794b4ba6e440f46db75` | `8d513cdaf42c08a1a1f849f66edd3feef9b7a77fd68f5e58de4004bd74a31fc4` |
| CT73 | `run_workflow → _ensure_eval_after_coder` | 415 | 71 | 0 / 0 | 45.22 | `e83a099831044fa6add283802a31e7c3` | `82fbe9c99ab8c5fba0126ad637a5f75b31f6a6298f932e2bcc93d5ee42758696` |
| CT75 | `_run_stage → run_stage_fn` | 424 | 62 | 0 / 0 | 42.13 | `7659d79432744e2f88383dc0da268b78` | `7eb59965ecf008fe387362a504bbcd9c77646624077ce750980aa91988321cb5` |
| CT76 | `verify_plan → commands_for` | 478 | 8 | 0 / 0 | 223.24 | `636f9448781c4bf2b13abd8ac6ce3938` | `ae3d6a40e4d6a0c51195f759a741cbce23d9ec56b45b8d24d5a59ffa5582eaf3` |
| CT77b | `_run_stage → write_verification` | 472 | 14 | 0 / 0 | 326.34 | `d60b29e5475447b8af611a2c793e1a5f` | `84f72f690a3b3316027a020542fd304806e7258c225fd629ed1f6cfd8e2809c6` |
| CT77c | `_gate_mode (neutralise)` | 478 | 8 | 0 / 0 | 332.32 | `eee028754654460fad6e34dc74556a33` | `eaf212b3916b543f6ad5a49293b8e87a78cfb52a7ed91f8c87138bba86f4b455` |
| CT77 | `_eval_evidence_block → _verification_evidence_lines` | 455 | 31 | 0 / 0 | 323.85 | `c88176a7ad4c4a76a8e9ccbd90a345a9` | `4d7373ba6019b3c1c6a4740bdc3dbcb35d63acb471def43b1f2f574e00c5e4ae` |
| CT86 | `_run_stage → capture_baseline` | 454 | 32 | 0 / 0 | 55.92 | `2ecea2730d9b4004b7bf98eb28e890c1` | `f24e15f5ffa3c08d36a89e11857e326a07f75671652ed92d8913c8d38100d1c2` |
| CT87 | `_validate_plan_admission → validate_kill_directives` | 415 | 71 | 0 / 0 | 52.20 | `415c5ba44306410dac17a72d4a924516` | `cc59a0cd93ff88d2331c450733a61f9d962f9eb3581965dfb2d56943d688a6c9` |
| CT90 | `_cmd_workflow → _require_plan_for_coder` | 484 | 2 | 0 / 0 | 296.76 | `1491be1b12384cb7b277afede0f4fb07` | `d6c3e006a6226db06e40ea1650c6fef91fe3978b0cbf95a47ce32169501876b4` |
| CT91 | `_validate_plan_admission → precheck` | 414 | 72 | 0 / 0 | 44.96 | `f139aec9e9b242fa8397fea445471955` | `451c0fca88f6b4c14022e69c6c472cccdf19f8e5e125e3b6c9d6d983cdfb7f02` |
| CT92 | `_record_admission_attempt → write_admission_record` | 420 | 66 | 0 / 0 | 200.11 | `36de85f340b349f0b87dbb0e3c146e0d` | `38c2c81a8be9beaa50f6cad0eb4428cd4c406eae473468c1d883856b5a15f3b9` |
| CT93 | `_build_tool_builders → build_scoped_write_file_tool` | 464 | 22 | 0 / 0 | 273.87 | `3c80954107c5444b983efec7880d96bc` | `0f036aeb171f2f4e5b4e403dbbbf480f349fa5d1bd70332af4689ba5c28aa6fb` |
| CT94 | `_run_admission_repair → _promote_validated_plan` | 473 | 13 | 0 / 0 | 288.60 | `47c2944faa744816bdf8906508af6cbc` | `4fde595cc48631ea855a9c18c9b5e3f937d6dbfed59bd12a08907a681428fe3e` |
| CT95 | `run_workflow → _require_plan_for_coder` | 478 | 8 | 0 / 0 | 302.06 | `d4181a117d1241939773ac31329795a5` | `cdf0081a2ae8870c6b047e13e2b760e5fa14960503402e2984e2c88605c32283` |
| SUP-GUARD | `build_invoke_workflow_tool.handler → _requires_acquisition` | 484 | 2 | 0 / 0 | 297.63 | `541296ea3e1c46ee9a9ac0c5a0ce3a79` | `bc09b94b1313f7754f4d1a4c2a683dd9e12f4a90aab450b5922d1411733c7875` |
| SUP-CONTEXT | `_child_run_context → begin_run` | 483 | 3 | 0 / 0 | 200.77 | `7a84bcd8f44046f29efcb5ec0b84e604` | `d2eaa9351c6d72f53bba62f496bb12f12fbef56923852fe33028773262e8e193` |

SUP-GUARD and SUP-CONTEXT are additional real producer removals in workflow_tool, not extra
SLICE6 contracts. Normative count remains16. The guard removal kills both default/coder normal
chat cases; child begin_run removal kills all three supported noncoder normal chat cases. The
pre-format16+2 batch also completed, but this final table supersedes it for candidate-byte proof.
The source/provenance/slice-sensitivity limitations above still apply. STEP17 alone may now be
checked for these exact frozen versions; no SLICE6/local-DoD/independent/operator acceptance.

Frozen normative/fixture inputs (SHA256; canonical root unchanged by all18 overlays):

```text
732ca6bb3e0ac9acf42e1aef200ee50ec21e9693464886f0a278142012650e89  src/fa/cli.py
9dc2780947286c753926fef845b00760df5c813e398f5ecf3ee45f16aa09b2da  src/fa/inner_loop/profiles.py
96021dbf5c05ad9fd2ec7e200d70b651dc5170f057e97e1bd163ecb925d9e2c5  src/fa/inner_loop/slice_verification.py
137cc8f80709b63748c68692b9f4e7ba25c0c210281ce88ddd312a7d61978f3f  src/fa/inner_loop/tools/workflow_tool.py
9896ba84bfd87bc1760139a0194634e6db66910ca64501647463edaf8fe47778  src/fa/inner_loop/workflow_controller.py
0da233bef7e76bb2db461c8c1b093835174a11b4f275dba753f1e341a5cdec52  tests/fixtures/i02_gate_probe.py
96b72e3b13d8c3fd7597afac21bf679b5ff9acc986ff961669ef45490b119f2e  tests/fixtures/i02_gate_subject.py
efe1674c7cdd614c5c7c7e0a58b1916646b1f5abcc047e672563f0c819e207b1  tests/test_verify_gate_live.py
```

Complete486-nodeid collection manifest SHA256: `3c8e96d2e7467a703909e1c3d1f5169d68b59341da7b9a971c6d71fb6d57bf02`.
Whole-repo doc-links command: rc1,46 pre-existing broken archived links; the five changed
Markdown files checked separately: rc0/no broken links. No link waiver or archive rewrite.


### Complete preliminary full-suite reports — not local acceptance

Both commands completed normally, no WindowsPath reporter abort. Candidate `just check` rc1:
**4994passed20failed12skipped1xfailed2warnings1053.50s**, coverage83.19% (80% total floor met).
Baseline `just test` rc1: **4451passed11failed14skipped1xfailed2warnings902.76s**. JUnit carries
exact collector nodeids for all5027 candidate/all4477 baseline cases, zero setup/teardown errors;
all failures are call-phase. Xfail is serialized as one additional skipped case. The candidate
full-run UUID env name was initially misspelled, so its report has exact IDs but no run-UUID
property; it was a fresh absent-at-start report path, not reused evidence. Normative16+2 reports
above all have the correct fresh UUID binding. This preliminary comparison does not waive the
version/final-manifest requirements for the eventual local-acceptance report.

`just _cli-cov-floor` was run separately after pytest prevented the normal chained invocation:
rc0,27 cli.py function floors met,78 functions scanned. Individual deptry/Pylint are separately
recorded above. Full `just check` remains red, not partially blessed.

Exact failure identity sets from the two completed XML reports (no count-only waiver):

**Common (4):**

```text
tests/test_deploy_scripts.py::test_historical_workspace_docs_have_top_level_superseded_banner
tests/test_doc_links.py::test_repo_has_no_broken_internal_file_links
tests/test_s10a_cli_coverage.py::test_s10a_authoring_check_runs_on_a_real_workspace
tests/test_workspace_readiness_integration.py::test_clean_candidate_real_readiness_commit_and_local_publication
```

**Candidate-only (16):**

```text
tests/test_deploy_scripts.py::test_workspace_stale_claims_are_confined_to_historical_evidence
tests/test_handoff_payload.py::test_blackboard_writer_called_with_handoff
tests/test_handoff_payload.py::test_facts_provider_exception_does_not_kill_chat
tests/test_handoff_payload.py::test_handoff_reaches_run_workflow_task
tests/test_handoff_payload.py::test_k_budget_third_call_denied_k2
tests/test_handoff_payload.py::test_malformed_risk_config_degrades_to_goal_only
tests/test_handoff_payload.py::test_missing_facts_provider_degrades_goal_only
tests/test_prompt_registry_coherence.py::test_wire_name_error_is_not_swallowed_by_the_fallback[build_baseline_registry-fs_read_file]
tests/test_prompt_registry_coherence.py::test_wire_name_error_is_not_swallowed_by_the_fallback[build_chat_registry-fs_read_file]
tests/test_prompt_registry_coherence.py::test_wire_name_error_is_not_swallowed_by_the_fallback[build_eval_registry-fs_run_bash]
tests/test_prompt_registry_coherence.py::test_wire_name_error_is_not_swallowed_by_the_fallback[build_planner_registry-fs_read_file]
tests/test_quality_slice_coverage.py::test_profile_registry_propagates_schema_contract_failure
tests/test_s127_outline.py::test_s127_fold_cli_py_matches_ast_truth
tests/test_s13_10_tool_names.py::test_composition_root_accepts_a_non_fs_pr_prefixed_name
tests/test_s13_10_tool_names.py::test_composition_root_rejects_non_portable_name
tests/test_s4_log_kind.py::test_log_kind_member_count_matches_source
```

**Baseline-only (7):**

```text
tests/test_deploy_scripts.py::test_executable_script_modes_are_pinned
tests/test_mutation_overlay.py::test_the_overlay_leaves_the_real_checkout_untouched
tests/test_workflow_deadline.py::test_generous_deadline_runs_the_full_pipeline
tests/test_workflow_deadline.py::test_no_deadline_runs_the_full_pipeline
tests/test_workflow_no_eval_terminal.py::test_eval_requested_but_no_verdict_fails[linear]
tests/test_workflow_no_eval_terminal.py::test_planner_coder_without_eval_is_also_unjudged
tests/test_workflow_no_eval_terminal.py::test_scratch_pipeline_succeeds_but_is_marked_unjudged
```

Some archived-baseline fixture failures are Git/archive-context sensitive (script mode and
checkout-untouched checks), not automatically product improvements. The reports need case-by-case
classification and operator review. No new/missing/unclassified=0 or acceptance claim.

**Additional declared Q70 compatibility edit:** `tests/test_handoff_payload.py` only. Six old
handoff/K-budget fixtures still requested default coder roles and were correctly refused. Set
supported planner/eval roles in the shared handler fixture and two direct positive calls; preserve
all handoff/goal/error-recovery/blackboard/K-counter oracles, and leave no-live-context refusal
unchanged. Handler-seam tests are C0, not claimed as real-session proof. Final handoff+invoke:
**112passed0.78s**, rc0; Ruff/check-format/Pyrefly clean; Mypy clean with the real source module
included (single-test-only Mypy first produced five import-untyped context diagnostics, not
suppressed). Production and frozen public/leaf audit inputs are unchanged; the completed normative
proof remains source/hash-identical. A fresh full suite is still required after these migrations.

Root doc-links remains rc1/46 archived links, changed-file docs rc0; no archive rewrite or waiver.
The other candidate-only failures and new authoring exports remain explicit next repair work.
Full candidate JUnit SHA256: `0b08b31a5135d177f8195eb507983e26bab653e07c80f049d821fa2278475f26`.
Full baseline JUnit SHA256: `55eb4f1963c7fd47d5ae1475131f5721ce74e6d039c61c53c3db48faec4c9492`.


## E215 — Q71 production-grade repair and repository quality cleanup, 2026-10-16

Q71 custom direction: “implement suiting production-grade wise design. robust and maintainable policy”.
Adopted deterministic retired-recipe/lifecycle detection, no new path exemptions; ordinary security
and denial evidence can name alias mechanisms anywhere. This is not a language-understanding
classifier, permission waiver, or execution-isolation proof. Historical ledger entries are unchanged.

**Scope and mechanism.** CT87/91/95; STEP12/13/16/17; GAP06/10/15 and retained local DoD quality
gates. Only existing controller implementation types become private; existing verification facade
exports are completed. Production routing, acquisition, deadline, isolation and retry policy are
unchanged. Registry C0 fixtures typed-forward the new dispatch argument, preserving actual invalid
name/schema exceptions and optional-builder fallback. CLI78 is the addition of `_valid_planner_dispatch`;
AST-derived truth is still independently asserted. LogKind C0 uses the canonical append-kind AST
scanner and its existing dormant-event explanations; a two-sided fixture distinguishes admission/
provider namespaces, actual literal/conditional producers and an unresolved producer.

**Quality corrections, no waivers.** Annotate an integer set and empty results; validate expected
JSON object shape; use direct shutil dependency; express enum exclusion as membership after a
positive identity assertion (same oracle, no comparison-overlap); move the empty-tuple assertion
after the error generator to avoid narrowing its element to Never. No assertions deleted.
Formatter-only profile/runner/overlay/plugin fixtures retain identical ASTs. Archive edits only
relocate broken Markdown link targets, preserving labels/fragments and historical bodies; destinations
are existing canonical documents or moved archives, not fabricated stubs.

**Actual checks so far:** targeted152passed12skipped2.52s (missing shellcheck); standalone typing-fixture
regressions100passed4.48s; configured `mypy`450files clean (explicit `mypy .` is a different480-file
selection and reports legacy archived demos/scripts; it is not the configured gate). Ruff check
whole tree clean; format901files clean; whole doclinks308files clean; authoring0diagnostics.
Pre-format public-bank487passed111.85s is diagnostic only. Invalid baseline invocation with a
nonexistent invoke-test filename returned rc4/no tests; not counted. Final corrected baseline and
16+2 audit pending. All live normative mutations must retain the entire487-case bank; no per-contract
test map. STEP17 reopened because source/test bytes changed. No local DoD/SHIPPED or I03 acceptance.

**Allowed existing-file inventory for this batch** (decision/evidence files are included; no new
source/test module or path-whitelist component):

- `src/fa/inner_loop/overlay_pytest_plugin.py`
- `src/fa/inner_loop/plan_ids.py`
- `src/fa/inner_loop/profiles.py`
- `src/fa/inner_loop/slice_verification.py`
- `src/fa/inner_loop/workflow_controller.py`
- `tests/test_deploy_scripts.py`
- `tests/test_mutation_overlay.py`
- `tests/test_planner_emits_schema4.py`
- `tests/test_prompt_registry_coherence.py`
- `tests/test_quality_slice_coverage.py`
- `tests/test_s127_outline.py`
- `tests/test_s13_10_tool_names.py`
- `tests/test_s4_log_kind.py`
- `tests/test_skill_grammar_emit.py`
- `tests/test_slice_verification_runner.py`
- `tests/test_verify_gate_live.py`
- `tests/test_verify_slice.py`
- `tests/workflow_fixtures.py`
- `worklogs/HANDOFF.md`
- `worklogs/archive/HANDOFF-S14-era-20260825.md`
- `worklogs/archive/PLAN-cli-trace-S10a-cli-coverage.md`
- `worklogs/archive/PLAN-cli-trace-S10b-cli-decomposition.md`
- `worklogs/archive/PLAN-cli-trace-S10c-contract-and-posture-fixes.md`
- `worklogs/archive/PLAN-cli-trace-S11-controlled-deployment.md`
- `worklogs/archive/PLAN-cli-trace-S5-authority-correctness.md`
- `worklogs/archive/PLAN-cli-trace-S6.6-mutation-gap-closure.md`
- `worklogs/archive/PLAN-cli-trace-S7-container-verification.md`
- `worklogs/archive/PLAN-cli-trace-S7-direct-run-vertical-slice.md`
- `worklogs/archive/PLAN-cli-trace-S8-workflow-controller-surface.md`
- `worklogs/archive/PLAN-cli-trace-S9-stats-projections.md`
- `worklogs/archive/knowledge-pr-notes-20260825/PR_NOTE_SANDBOX_MUTATION_CLOSURE.md`
- `worklogs/archive/knowledge-pr-notes-20260825/PR_NOTE_substrate_gap_closure.md`
- `worklogs/archive/knowledge-pr-notes-20260825/README.md`
- `worklogs/archive/knowledge-pr-notes-20260825/workspace-isolation.md`
- `worklogs/planning-topology-and-executable-contracts-loop/increments/increment-02-verify-gate-and-kill-checks.md`
- `worklogs/planning-topology-and-executable-contracts-loop/ledger.md`
- `worklogs/planning-topology-and-executable-contracts-loop/notes/e2e-live-verification-register.md`
- `worklogs/planning-topology-and-executable-contracts-loop/notes/i02-ct91-public-admission-e211-2026-10-16.md`
- `worklogs/planning-topology-and-executable-contracts-loop/notes/i02-slice-verification-design.md`
- `worklogs/planning-topology-and-executable-contracts-loop/notes/open-questions-2026-10-07.md`
