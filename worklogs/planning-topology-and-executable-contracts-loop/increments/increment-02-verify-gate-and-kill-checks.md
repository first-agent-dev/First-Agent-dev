---
Increment-ID: RM-planning-topology-I02
Roadmap-ID: RM-planning-topology
status: PLANNED
slices: 6
shipped: —
---

# INCREMENT I02: Executable contracts & the verify gate

**Shippable when:** after a coder stage, the harness itself runs that slice's `verify`
commands, records the real exit code, and proves each `FUNCTIONAL` contract's test is bound
to production code by executing the contract's declared kill-check. A non-zero exit or a
surviving kill-check routes the run back to the coder instead of passing.

Rationale lives in [`../notes/i02-slice-verification-design.md`](../notes/i02-slice-verification-design.md)
and [`../notes/i02-handoff-verify-gate.md`](../notes/i02-handoff-verify-gate.md). Do not
restate it here.

**Ground truth (verified @ `9ec70ce`, 2026-10-07 — read before editing):**
- `src/fa/inner_loop/slice_verification.py` does **not exist**.
- `src/fa/inner_loop/plan_ids.py` exposes `commands_for`, `section`, `tests_for`,
  `contract_class`, `SliceRecord.test_paths`, `.tests_note`, `.contracts`; all executed and
  live. `commands_for(None)` returns `()` on increment-01.
- `commands_for` has **zero** production call sites. This increment creates the first.
- `build_scrubbed_env` is at `src/fa/inner_loop/tools/bash_env.py:70`. The env + venv-PATH +
  timeout + binary-decode policy to copy is `src/fa/inner_loop/tools/run_bash.py:233-250`.
- `_run_subprocess_fallback` is at `src/fa/inner_loop/tools/run_bash.py:219` and is private,
  tool-shaped, and performs `transaction.add_write` and artifact offload.
- `_run_stage` is at `src/fa/inner_loop/workflow_controller.py:511` and takes
  `(ctx, role, *, fresh, progress, transition_reason, run_stage_fn) -> StageResult`. **It has
  no slice parameter and there is no per-slice loop**: one coder stage covers the whole plan.
  The per-slice loop is I03's. `StageResult` is `(role, exit_code, eval_report=None)` at `:193`.
- `_deadline_exceeded` is at `:536` and is already called at the top of `_run_stage`.
- The governing repair counter is `WorkflowProgress.repair_round` at `:188`; the cap is applied
  at `:944-957`, triggered by `eval_report.route_decision == "return_to_coder"`.
  `workflow_artifacts.py:277` is `FlowState.repair_round`, a mirror — do not key on it.
- `_run_initial_roles` (`:886`) overwrites `eval_report` from any later stage (`:908-909`), so a
  report attached to a coder stage is **discarded** unless the role loop stops there.
- `EvalReport` (`workflow_artifacts.py:201`) has fields
  `run_id, plan_id, plan_version, evaluation_id, verdict, route_decision, summary, step_results,
  findings, …`. `EvalVerdict` includes `REPAIR_REQUIRED`; `RouteDecision` includes
  `return_to_coder`. **There is no provenance field** — nothing marks a report harness-authored.
- The composition root for a workflow is `run_workflow(... run_stage_fn=_cmd_run, transport=…)`;
  `_cmd_run` (`cli.py:1460`) is what calls `drive_session` (`cli.py:2408`). `drive_session` sits
  **below** the controller and cannot exercise `_run_stage`. The only existing end-to-end
  precedent is `tests/test_workflow_global_history.py:123-141`, which stubs the **transport**.
- `.venv/` is git-ignored (`.gitignore:4`), so it is absent from any copied or worktree'd tree.
- **Measured 2026-10-07: a mutated copy of the tree is invisible to the import system.** With
  `fa` installed (an absolute path on `sys.path`), running a test with `cwd` set to a copy still
  imports the original module. `PYTHONPATH=<copy>/src` does win. Without a guard, every
  kill-check would run against unmutated code, every test would pass, and the gate would report
  `VACUOUS` for every contract — inverted, not merely broken.
- `_git_output` (`workflow_controller.py:401`) collapses OSError/SubprocessError to `None`.
  Do not reuse it; "couldn't run" must never read as "passed".
- A `kill:` line indented under a contract passes the shipped `precheck` with `ok=True` and
  zero diagnostics, and is reachable with line structure intact via `section()`.

**Decisions (do exactly):**
- Module is `src/fa/inner_loop/slice_verification.py`. Do not add to `plan_ids.py`; it is
  pure, stdlib-only and total by contract, and a subprocess runner breaks all three.
- The kill directive is read from **`section()`**, never from the joined contract body.
- Exactly two kill operators: `neutralise` and `remove-call`. Do not add a third.
- `VACUOUS` and `PRODUCER_ABSENT` block with **no appeal** (operator, F3).
- Kill-checks run on **`FUNCTIONAL` contracts only** (operator, F4).
- Mutation is applied to a **throwaway copy of `src/` only** (2.4 MB, ~10 ms), never a git
  worktree. Tests are read from the operator's tree and are therefore structurally immune to
  mutation. The operator's tree is never written to.
- **Every kill-check run must first prove the mutated module is the one imported.** A kill-check
  whose provenance probe fails is `ERROR`, never a verdict.
- A blocking verdict **stops the role loop** before the eval stage runs; otherwise the eval
  report overwrites the synthetic one (`:908-909`) and the route is silently lost.
- Harness origin is carried in `evaluation_id`, prefixed `harness-verify-`, plus a
  `FindingClass="implementation"` finding. Do not add a field to `EvalReport`.
- Routing reuses Q10(a): synthesise a harness-origin eval report with
  `route_decision="return_to_coder"`. Do not introduce a second routing concept.
- `ERROR` is never `PASS`. A thing that could not be determined did not pass.

---

## SLICE1: The command runner (three-state, scrubbed, bounded)
STEPS: prescriptive
DEPS: —
INTENT: the harness, not the model, executes a slice's verify commands and records the real
  exit code, with a result type that cannot express "couldn't run" as "passed".
CONTRACTS:
  CT44 [FUNCTIONAL]: `run_commands(commands, *, root, timeout_s, deadline)` returns a
    `tuple[CommandResult, ...]`, one per input command in order, each carrying the verbatim
    command, the real integer `exit_code`, and `stdout_tail`/`stderr_tail`.
    kill: neutralise src/fa/inner_loop/slice_verification.py::run_commands
  CT45 [FUNCTIONAL]: a command exceeding `timeout_s` yields `outcome=ERROR` with
    `exit_code=None`; it is never `PASS` and never silently `FAIL`.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_run_one -> TimeoutExpired
  CT46 [CONSTRAINT]: the subprocess environment is built by
    `tools.bash_env.build_scrubbed_env` with the repo's `.venv/bin` prepended to `PATH`,
    mirroring `tools/run_bash.py:233-250`. `_run_subprocess_fallback` is not imported,
    called, or copied. Catches: a verifier that inherits the operator's secrets, or that
    acquires `transaction.add_write` side effects a read-only gate must not have.
  CT47 [CONSTRAINT]: the run deadline is checked **between** commands; once exceeded the
    remaining commands are returned as `ERROR` without being started. Catches: one hung
    verification consuming the whole run budget.
  CT48 [FUNCTIONAL]: an empty command tuple returns an empty result tuple and the caller
    records `skipped`; it is not an error and does not block.
    kill: remove-call src/fa/inner_loop/slice_verification.py::run_commands -> _empty_result
  CT49 [PRESERVATION]: `src/fa/inner_loop/plan_ids.py` is not modified by this slice; it
    imports no subprocess, os.environ or pathlib-write facility.
TESTS: tests/test_slice_verification_runner.py   (NEW — author it)
```verify
uv run pytest tests/test_slice_verification_runner.py -q
uv run ruff check src/fa/inner_loop/slice_verification.py tests/test_slice_verification_runner.py
```
- [ ] STEP1: create `src/fa/inner_loop/slice_verification.py` with `CommandOutcome` (PASS/FAIL/ERROR) and a frozen `CommandResult` dataclass (exit: `uv run python -c "from fa.inner_loop.slice_verification import CommandResult, CommandOutcome"` exits 0)
- [ ] STEP2: implement `_run_one` using `subprocess.run(..., shell=True, capture_output=True, text=False, timeout=timeout_s, env=env)`, decoding with `errors="ignore"`, copying the policy at `tools/run_bash.py:233-250` (exit: `grep -c "_run_subprocess_fallback" src/fa/inner_loop/slice_verification.py` prints 0)
- [ ] STEP3: implement `run_commands` with the between-command deadline check (exit: `uv run pytest tests/test_slice_verification_runner.py -q -k "deadline or timeout"` exits 0)
- [ ] STEP4: write the oracles for CT44–CT49, including a seeded `sleep` command for CT45 (exit: `uv run pytest tests/test_slice_verification_runner.py -q` exits 0)

## SLICE2: Kill directives — strict parse, loud failure
STEPS: prescriptive
DEPS: —
INTENT: a contract's declared kill-check is read from the slice's raw text and validated
  before the coder starts, so that a missing or malformed directive blocks loudly instead of
  disabling the non-vacuity gate in silence.
CONTRACTS:
  CT50 [FUNCTIONAL]: `parse_kill_directives(section)` reads `section()` output line by line
    and returns `dict[contract_id, KillDirective]`, attributing each directive to the `CT<n>`
    entry it is indented under. Trailing prose after the directive does not affect parsing.
    kill: neutralise src/fa/inner_loop/slice_verification.py::parse_kill_directives
  CT51 [FUNCTIONAL]: a near-miss line — `kil:`, `Kill :`, `kill-check:` — is reported as
    `kill-directive-near-miss` naming `file:line`, in the manner of `heading-near-miss`
    (CT26) and `step-near-miss` (CT37). Catches: a typo that would otherwise present as
    "the planner declared none".
    kill: remove-call src/fa/inner_loop/slice_verification.py::validate_kill_directives -> _NEAR_MISS_RE
  CT52 [FUNCTIONAL]: `validate_kill_directives` emits `kill-directive-missing` for a
    `FUNCTIONAL` contract with no directive, `kill-directive-malformed` for a line matching
    the soft pattern but not the strict one, and `kill-directive-ambiguous` for two or more
    directives on one contract. Each names `file:line` and each is a FAIL.
    kill: neutralise src/fa/inner_loop/slice_verification.py::validate_kill_directives
  CT53 [CONSTRAINT]: parsing and validation are pure — stdlib only, no filesystem read, no
    subprocess — so they can run at admission, before any coder stage. Catches: a gate that
    can only report a malformed directive after the coder has already done the work.
  CT54 [CONSTRAINT]: `CONSTRAINT` and `PRESERVATION` contracts without a directive produce no
    diagnostic. Catches: a validator that forces a meaningless kill-check onto a contract
    whose test is an existing one.
TESTS: tests/test_kill_directives.py   (NEW — author it)
```verify
uv run pytest tests/test_kill_directives.py -q
uv run ruff check src/fa/inner_loop/slice_verification.py tests/test_kill_directives.py
```
- [ ] STEP1: add `KillOperator` (NEUTRALISE/REMOVE_CALL) and a frozen `KillDirective` carrying operator, path, symbol, callee, line (exit: `uv run python -c "from fa.inner_loop.slice_verification import KillDirective"` exits 0)
- [ ] STEP2: implement `parse_kill_directives` over raw section text with the strict pattern `^\s*kill:\s*(neutralise|remove-call)\s+(\S+)::(\S+?)(?:\s*->\s*(\S+))?\s*$` (exit: `uv run pytest tests/test_kill_directives.py -q -k parse` exits 0)
- [ ] STEP3: implement `validate_kill_directives` with the soft, strict and near-miss patterns (exit: `uv run pytest tests/test_kill_directives.py -q -k validate` exits 0)
- [ ] STEP4: add the six-case corpus from the design note §F1 as a table-driven oracle (exit: `uv run pytest tests/test_kill_directives.py -q` exits 0)

## SLICE3: The mutation operators (AST, pure)
STEPS: prescriptive
DEPS: —
INTENT: apply a declared kill-check to source text by symbol rather than by line, and report
  how many targets matched, so that "the producer is missing" is distinguishable from "the
  test is weak".
CONTRACTS:
  CT55 [FUNCTIONAL]: `apply_kill(source, directive)` with `neutralise` replaces the body of the
    named function with `return None`, and every other definition is unchanged **relative to
    `ast.unparse(ast.parse(source))`**, not to `source`. Measured: `ast.unparse` discards
    comments and layout, so a comparison against the original text fails for reasons unrelated
    to the mutation.
    kill: neutralise src/fa/inner_loop/slice_verification.py::apply_kill
  CT56 [FUNCTIONAL]: with `remove-call`, **every `ast.Call` to `<callee>` inside the enclosing
    symbol is replaced by the constant `None`** — not only bare expression statements. Measured
    on a four-call sample (`a = emit(x)`, `emit(x)`, `if emit(x):`, a comprehension): deleting
    only `ast.Expr` statements sees **1 of 4**, which silently reports `PRODUCER_ABSENT` when the
    producer is assigned, and partially removes it otherwise. Replacement handles all four forms
    uniformly and is a truer simulation of "the producer never ran".
    kill: remove-call src/fa/inner_loop/slice_verification.py::_Silence -> visit_Call
  CT57 [FUNCTIONAL]: `apply_kill` returns `(mutated_source, hits)`. `hits == 0` means the
    target is absent and the caller raises `PRODUCER_ABSENT`; `hits > 1` is an ambiguous
    target and the caller raises `ERROR`, never a guess.
    kill: remove-call src/fa/inner_loop/slice_verification.py::apply_kill -> _count_hits
  CT58 [CONSTRAINT]: `apply_kill` takes source text and returns source text. It performs no
    filesystem read or write and no subprocess call. Catches: a mutation helper that is
    convenient to call directly on the working tree.
  CT59 [CONSTRAINT]: exactly two operators are implemented and `KillOperator` has exactly two
    members. Catches: the slow growth of a mutation DSL, which `i02-handoff-verify-gate.md`
    §5 forbids.
TESTS: tests/test_kill_operators.py   (NEW — author it)
```verify
uv run pytest tests/test_kill_operators.py -q
uv run ruff check src/fa/inner_loop/slice_verification.py tests/test_kill_operators.py
```
- [ ] STEP1: implement `_Neutralise(ast.NodeTransformer)` counting hits on `visit_FunctionDef` and `visit_AsyncFunctionDef` (exit: `uv run pytest tests/test_kill_operators.py -q -k neutralise` exits 0)
- [ ] STEP2: implement `_Silence(ast.NodeTransformer)` replacing every `ast.Call` to the callee inside the enclosing symbol with `ast.Constant(None)`, resolving both `Name` and `Attribute` callees, and counting each (exit: `uv run pytest tests/test_kill_operators.py -q -k remove_call` exits 0)
- [ ] STEP2b: assert the four-call-form sample yields `hits == 4` (exit: `uv run pytest tests/test_kill_operators.py -q -k call_forms` exits 0)
- [ ] STEP3: implement `apply_kill` dispatching on the operator and returning `(source, hits)` (exit: `uv run pytest tests/test_kill_operators.py -q -k hits` exits 0)
- [ ] STEP4: assert the closed operator set with `len(KillOperator) == 2` (exit: `uv run pytest tests/test_kill_operators.py -q` exits 0)

## SLICE4: The mutation sandbox — a `src` overlay with a provenance guard
STEPS: prescriptive
DEPS: —
INTENT: run a mutated copy of production code without writing to the operator's tree, and
  refuse to return a verdict unless the mutated module is provably the one that was imported.
CONTRACTS:
  CT60 [FUNCTIONAL]: `mutation_overlay(root, rel_path, mutated_source)` yields a temporary
    directory containing a copy of `root/src` with `rel_path` replaced by `mutated_source`,
    and removes it on normal exit **and** on exception.
    kill: remove-call src/fa/inner_loop/slice_verification.py::mutation_overlay -> _copy_src
  CT61 [FUNCTIONAL]: a command run against the overlay receives `PYTHONPATH=<overlay>/src`
    prepended to any inherited value, and `cwd` stays the operator's root so the tests under
    test are the real ones.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_overlay_env -> _prepend_pythonpath
  CT62 [FUNCTIONAL]: before any kill-check result is trusted, a provenance probe runs in the
    same environment and asserts the target module resolves **inside the overlay**; if it does
    not, the outcome is `ERROR` and no verdict is produced. Catches the measured defect that
    an installed package resolves to an absolute path, so a mutated copy is simply never
    imported and every kill-check reports a false `VACUOUS`.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_run_kill_check -> _assert_overlay_wins
  CT63 [CONSTRAINT]: only `src/` is copied. Test files are read from the operator's tree and
    are therefore structurally impossible for a kill-check to mutate. Catches: a sandbox built
    by copying the whole tree, in which a mutation could silently rewrite the oracle.
  CT64 [CONSTRAINT]: after any `mutation_overlay` use, `git status --porcelain` in the
    operator's root is byte-identical to its value before, and no `git worktree` command is
    invoked. Catches: a mutation reaching the real checkout.
TESTS: tests/test_mutation_overlay.py   (NEW — author it)
```verify
uv run pytest tests/test_mutation_overlay.py -q
uv run ruff check src/fa/inner_loop/slice_verification.py tests/test_mutation_overlay.py
```
- [ ] STEP1: implement `mutation_overlay` as a `@contextmanager` using `tempfile.mkdtemp()` + `shutil.copytree(root/"src")`, writing `mutated_source` over `rel_path`, removing the tree in `finally` (exit: `uv run pytest tests/test_mutation_overlay.py -q -k overlay` exits 0)
- [ ] STEP2: implement `_overlay_env` prepending `<overlay>/src` to `PYTHONPATH` over the scrubbed env from SLICE1 (exit: `uv run pytest tests/test_mutation_overlay.py -q -k pythonpath` exits 0)
- [ ] STEP3: implement `_assert_overlay_wins(module, overlay, env)` running `python -c "import <module>, pathlib, sys; sys.exit(0 if str(pathlib.Path(<module>.__file__).resolve()).startswith(sys.argv[1]) else 3)"` and mapping a non-zero exit to `ERROR` (exit: `uv run pytest tests/test_mutation_overlay.py -q -k provenance` exits 0)
- [ ] STEP4: add the negative oracle — with the probe disabled, a mutation of an installed module is NOT observed; with it enabled, the run is `ERROR` not `VACUOUS` (exit: `uv run pytest tests/test_mutation_overlay.py -q` exits 0)

## SLICE5: Verdict assembly
STEPS: prescriptive
DEPS: SLICE1, SLICE2, SLICE3, SLICE4
INTENT: compose the phases into one verdict per slice, keeping "the test is weak" and "the
  feature was never wired" as separate, separately-repairable outcomes.
CONTRACTS:
  CT65 [FUNCTIONAL]: `verify_slice(record, *, root, ...)` returns a frozen `SliceVerification`
    carrying a `SliceVerdict`, the per-command results, and the per-contract kill-check
    outcomes. `verify_plan` (SLICE6) maps it over every slice; neither function takes a
    "current slice" from the controller, because no per-slice dispatch exists in I02.
    kill: neutralise src/fa/inner_loop/slice_verification.py::verify_slice
  CT66 [FUNCTIONAL]: when the slice's commands pass but a contract's test **still passes**
    under its kill-check, the verdict is `VACUOUS` and names the contract id.
    kill: remove-call src/fa/inner_loop/slice_verification.py::verify_slice -> _run_kill_check
  CT67 [FUNCTIONAL]: when a kill directive's target yields `hits == 0`, the verdict is
    `PRODUCER_ABSENT` and names the contract and the target. It is a distinct member of
    `SliceVerdict`, not folded into `VACUOUS`.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_classify -> _producer_absent
  CT68 [FUNCTIONAL]: a test green at baseline and red after the change yields `REGRESSION`;
    red-to-red is advisory and does not block.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_classify -> _compare_baseline
  CT69 [CONSTRAINT]: the baseline runs only the slice's own `TESTS:` paths, never the whole
    suite, and the kill-check phase runs only the contract's own test. Catches: an
    O(slices × suite-time) gate that will not survive a real increment (§6.2).
  CT70 [CONSTRAINT]: `VACUOUS` and `PRODUCER_ABSENT` expose no dismissal or appeal parameter.
    Catches: an appeal path quietly reintroduced from E63, which granted it to generated
    mutants only.
TESTS: tests/test_verify_slice.py   (NEW — author it)
```verify
uv run pytest tests/test_verify_slice.py -q
uv run ruff check src/fa/inner_loop/slice_verification.py tests/test_verify_slice.py
```
- [ ] STEP1: add `SliceVerdict` with exactly the seven members in the design note §3.2 (exit: `uv run python -c "from fa.inner_loop.slice_verification import SliceVerdict; assert len(SliceVerdict)==7"` exits 0)
- [ ] STEP2: implement `_run_kill_check(directive, test_path, root)` using `apply_kill` + `mutation_overlay` + `_assert_overlay_wins` + `run_commands`, in that order; the provenance probe gates the result (exit: `uv run pytest tests/test_verify_slice.py -q -k kill_check` exits 0)
- [ ] STEP3: implement `_classify` mapping phase outputs to a verdict, with `ERROR` dominating (exit: `uv run pytest tests/test_verify_slice.py -q -k classify` exits 0)
- [ ] STEP4: build the three-row oracle from the design note §3.6 — PROVEN, PRODUCER_ABSENT, VACUOUS — as the slice's primary test (exit: `uv run pytest tests/test_verify_slice.py -q` exits 0)

## SLICE6: Wire the gate into the controller, and prove it live
STEPS: prescriptive
DEPS: SLICE5
INTENT: the gate becomes reachable from a real workflow run — the first production consumer of
  `commands_for` — and one test boots the real composition root to prove it, discharging SD-C
  and register rows D1, D3, D4 and D5.
CONTRACTS:
  CT71 [FUNCTIONAL]: after a `coder` stage returns exit 0, `_run_stage`
    (`workflow_controller.py:511`) verifies **every slice** the plan declares and attaches a
    `PlanVerification` to its `StageResult`. There is no per-slice dispatch in I02; one coder
    stage covers the whole plan, and the per-slice loop belongs to I03.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> verify_plan
  CT72 [FUNCTIONAL]: a blocking verdict makes `_run_stage` return a synthetic `EvalReport` with
    `verdict="REPAIR_REQUIRED"`, `route_decision="return_to_coder"`,
    `evaluation_id` prefixed `harness-verify-`, and a finding carrying the failing command and
    its real stderr text. No new routing constant and no new `EvalReport` field.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> _synthesise_verify_report
  CT73 [FUNCTIONAL]: `_run_initial_roles` (`:886`) **stops the role loop** when a coder stage
    returns a blocking report, so the eval stage never runs. Catches two defects at once: an
    LLM call paid for on work already known to be broken, and — the real one — the eval stage
    overwriting `eval_report` at `:908-909`, which would discard the synthetic route entirely
    and let the run finish green.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_initial_roles -> _is_blocking
  CT74 [CONSTRAINT]: verification-driven repairs are governed by the existing
    `WorkflowProgress.repair_round` cap at `:944-957`; a permanently failing command terminates
    the run non-`DONE` instead of looping. Catches: an infinite repair loop on an unsatisfiable
    command.
  CT75 [FUNCTIONAL]: a live test calls `run_workflow(roles=["planner","coder","eval"], …,
    run_stage_fn=_cmd_run, transport=<stub>)`, following
    `tests/test_workflow_global_history.py:123-141`, and asserts the plan's commands ran with
    their real exit codes recorded. `drive_session` is **not** the harness: it sits below
    `_cmd_run` and cannot exercise `_run_stage`.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> verify_plan
  CT76 [FUNCTIONAL]: in that same live test, commands are attributed to the slice that declares
    them — a command declared only by SLICE2 is not recorded under SLICE1 — and
    `commands_for(None)` runs exactly once at plan level. Catches: a gate that concatenates
    every command and reports one undifferentiated result, which a naive per-plan assertion
    would pass.
    kill: remove-call src/fa/inner_loop/slice_verification.py::verify_plan -> commands_for
TESTS: tests/test_verify_gate_live.py   (NEW — author it)
```verify
uv run pytest tests/test_verify_gate_live.py -q
uv run ruff check src/fa/inner_loop/workflow_controller.py tests/test_verify_gate_live.py
```
- [ ] STEP1: add `verify_plan(plan_ids, *, root, …) -> PlanVerification` to `slice_verification.py`, iterating `slice_records` plus `commands_for(None)` (exit: `uv run pytest tests/test_verify_slice.py -q -k verify_plan` exits 0)
- [ ] STEP2: call `verify_plan` from `_run_stage` guarded by `role == "coder" and code == 0` (exit: `grep -n "verify_plan" src/fa/inner_loop/workflow_controller.py` prints at least one line)
- [ ] STEP3: implement `_synthesise_verify_report` per CT72 (exit: `uv run pytest tests/test_verify_gate_live.py -q -k route` exits 0)
- [ ] STEP4: stop the role loop in `_run_initial_roles` on a blocking coder report (exit: `uv run pytest tests/test_verify_gate_live.py -q -k short_circuit` exits 0)
- [ ] STEP5: write the live test on the `test_workflow_global_history.py:123-141` template (exit: `uv run pytest tests/test_verify_gate_live.py -q -k live` exits 0)
- [ ] STEP6: add the per-slice attribution assertion of CT76 (exit: `uv run pytest tests/test_verify_gate_live.py -q` exits 0)

## Increment definition of done

- [ ] Every `CT#` satisfied: each slice's `verify` block exits 0.
- [ ] The gate runs in a real workflow: `tests/test_verify_gate_live.py` calls `run_workflow`
      with `run_stage_fn=_cmd_run` and a stub transport, and deleting the `verify_plan` call
      site in `workflow_controller.py:511` makes it fail. A kill-check aimed at
      `extract_plan_ids` does not count — it stays green with the gate unwired, which is the
      condition this exists to detect.
- [ ] The provenance probe is demonstrated: with it disabled, a mutation of an installed
      module is provably NOT observed and the gate reports `VACUOUS`; with it enabled the same
      run reports `ERROR`. Without this the gate is inverted rather than broken.
- [ ] A blocking coder verdict is shown to stop the role loop before the eval stage runs,
      asserted on the stage count, not on a log line.
- [ ] `VACUOUS`, `PRODUCER_ABSENT` and `REGRESSION` each demonstrated on a constructed slice,
      not merely representable in the enum.
- [ ] The operator's working tree is byte-identical before and after a full gate run (CT64),
      verified with `git status --porcelain` captured on both sides, and `git worktree list`
      shows no leftover entry.
- [ ] Register rows **D1, D3, D4, D5** are ticked in
      [`../notes/deferred-verification-register.md`](../notes/deferred-verification-register.md),
      each citing the test that closed it.
- [ ] Full suite shows no regression against the 4156P / 3F / 12S / 1X baseline, with the
      three expected-red re-run by name.
- [ ] `plan_ids.py` is unmodified: `git diff --stat src/fa/inner_loop/plan_ids.py` is empty.
- [ ] A scoped mutation run over `slice_verification.py` has no non-equivalent survivors, per
      the protocol in `../notes/i01-dod-walk-2026-10-07.md`.

## Out of scope (moved, not dropped)

- **Generated-mutant sweep per slice (E63 / handoff §6.4).** A declared kill-check is not the
  same mechanism; see the design note §1. Deferred to its own increment.
- **`TEST-DEFECT` as a first-class verdict (§6.3).** Needs the eval loop; I03.
- **`VERIFIED` status.** Requires I03's eval L2 on top (schema §6).
- **Verification-integrity controls (§6.7).** Four of five are assertions over
  `BlackboardEntry.write_set`; audit before building, and not here.
- **The 20-slice calibration corpus and the ≥95% exit criterion (§6.1).** It measures the
  gate; it cannot be built in the increment that builds the gate.
- **CT10b path-existence rule (Q39).** Lands with the `tests_note` semantics in I03.

## Hand-off to I03 (banked context, not a plan)

- `SliceVerification` is the record the eval stage should read instead of re-deriving
  completion from prose. It already carries real exit codes and per-contract kill-check
  outcomes.
- The judge keeps the questions a command cannot answer: is this a good implementation, did
  it break something adjacent, is the test honest beyond its declared kill-check.
- `steps_mode` is still unread (schema §7 marks it PENDING with I03 as consumer).
