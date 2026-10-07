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
- `_deadline_exceeded` is at `src/fa/inner_loop/workflow_controller.py:536`;
  `repair_round` is at `src/fa/inner_loop/workflow_artifacts.py:277`.
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
- Mutation is applied in a throwaway git worktree. The operator's tree is never written to.
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
  CT55 [FUNCTIONAL]: `apply_kill(source, directive)` with `neutralise` replaces the body of
    the named function with `return None` and leaves every other definition byte-identical
    after `ast.unparse` round-trip.
    kill: neutralise src/fa/inner_loop/slice_verification.py::apply_kill
  CT56 [FUNCTIONAL]: with `remove-call`, every statement inside the enclosing symbol whose
    expression is a call to `<callee>` is deleted; if the body empties it becomes `pass`.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_RemoveCall -> visit_FunctionDef
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
- [ ] STEP2: implement `_RemoveCall(ast.NodeTransformer)` deleting `ast.Expr` statements whose `value` is an `ast.Call` to the callee, resolving both `Name` and `Attribute` callees (exit: `uv run pytest tests/test_kill_operators.py -q -k remove_call` exits 0)
- [ ] STEP3: implement `apply_kill` dispatching on the operator and returning `(source, hits)` (exit: `uv run pytest tests/test_kill_operators.py -q -k hits` exits 0)
- [ ] STEP4: assert the closed operator set with `len(KillOperator) == 2` (exit: `uv run pytest tests/test_kill_operators.py -q` exits 0)

## SLICE4: Worktree isolation
STEPS: prescriptive
DEPS: —
INTENT: a kill-check runs against a disposable copy of the working tree, including the
  coder's uncommitted and untracked files, so production code is mutated without the
  operator's checkout ever being written to.
CONTRACTS:
  CT60 [FUNCTIONAL]: `scratch_tree(root)` yields a path whose content equals the working tree
    — tracked modifications **and untracked, non-ignored files**. Catches: a worktree built
    from `HEAD` plus `git diff HEAD`, which omits the planner-authored test file because it is
    new and untracked, so the kill-check would run where the test does not exist.
    kill: remove-call src/fa/inner_loop/slice_verification.py::scratch_tree -> _copy_untracked
  CT61 [FUNCTIONAL]: the scratch tree is removed on normal exit **and** on exception; the
    context manager is exception-safe.
    kill: remove-call src/fa/inner_loop/slice_verification.py::scratch_tree -> _remove_worktree
  CT62 [CONSTRAINT]: after any `scratch_tree` use, `git status --porcelain` in the operator's
    root is byte-identical to its value before. Catches: a mutation written to the real tree.
  CT63 [CONSTRAINT]: the scratch path is created outside the repository root and is never
    added to the coder's writable set. Catches: §6.7's requirement that verification run
    where the coder cannot write.
  CT64 [FUNCTIONAL]: if the worktree cannot be created, the result is `ERROR`; it is never
    reported as a passing or failing kill-check.
    kill: remove-call src/fa/inner_loop/slice_verification.py::scratch_tree -> _raise_scratch_error
TESTS: tests/test_scratch_tree.py   (NEW — author it)
```verify
uv run pytest tests/test_scratch_tree.py -q
uv run ruff check src/fa/inner_loop/slice_verification.py tests/test_scratch_tree.py
```
- [ ] STEP1: implement `scratch_tree` as a `@contextmanager` using `git worktree add --detach` into a `tempfile.mkdtemp()` path (exit: `uv run pytest tests/test_scratch_tree.py -q -k creates` exits 0)
- [ ] STEP2: copy tracked modifications with `git diff HEAD` piped to `git -C <scratch> apply`, tolerating an empty diff (exit: `uv run pytest tests/test_scratch_tree.py -q -k tracked` exits 0)
- [ ] STEP3: copy untracked non-ignored files listed by `git ls-files --others --exclude-standard` (exit: `uv run pytest tests/test_scratch_tree.py -q -k untracked` exits 0)
- [ ] STEP4: remove the worktree in a `finally` block with `git worktree remove --force` and assert the CT62 porcelain equality (exit: `uv run pytest tests/test_scratch_tree.py -q` exits 0)

## SLICE5: Verdict assembly
STEPS: prescriptive
DEPS: SLICE1, SLICE2, SLICE3, SLICE4
INTENT: compose the phases into one verdict per slice, keeping "the test is weak" and "the
  feature was never wired" as separate, separately-repairable outcomes.
CONTRACTS:
  CT65 [FUNCTIONAL]: `verify_slice(record, *, root, ...)` returns a frozen `SliceVerification`
    carrying a `SliceVerdict`, the per-command results, and the per-contract kill-check
    outcomes.
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
- [ ] STEP2: implement `_run_kill_check(directive, test_path, root)` using `scratch_tree` + `apply_kill` + `run_commands` (exit: `uv run pytest tests/test_verify_slice.py -q -k kill_check` exits 0)
- [ ] STEP3: implement `_classify` mapping phase outputs to a verdict, with `ERROR` dominating (exit: `uv run pytest tests/test_verify_slice.py -q -k classify` exits 0)
- [ ] STEP4: build the three-row oracle from the design note §3.6 — PROVEN, PRODUCER_ABSENT, VACUOUS — as the slice's primary test (exit: `uv run pytest tests/test_verify_slice.py -q` exits 0)

## SLICE6: Wire the gate into the controller, and prove it live
STEPS: prescriptive
DEPS: SLICE5
INTENT: the gate becomes reachable from a real run — the first production consumer of
  `commands_for` — and one test boots the real composition root to prove it, discharging
  SD-C and register rows D1, D3, D4 and D5.
CONTRACTS:
  CT71 [FUNCTIONAL]: after a `coder` stage returns, `_run_stage` calls `verify_slice` for that
    slice and attaches the result to the stage outcome.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> verify_slice
  CT72 [FUNCTIONAL]: a blocking verdict causes the controller to synthesise a harness-origin
    eval report with `route_decision="return_to_coder"`, carrying the failing command and its
    real stderr text. No new routing constant is introduced.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> _synthesise_repair_report
  CT73 [CONSTRAINT]: verification-driven repairs are governed by the existing `repair_round`
    cap (`workflow_artifacts.py:277`); a permanently failing command terminates the run
    non-`DONE` instead of looping. Catches: an infinite repair loop on an unsatisfiable
    command.
  CT74 [FUNCTIONAL]: a test boots `drive_session` with the shipped factories, a real
    workspace in `tmp_path` and `hooks=HookRegistry()`, mocking **only**
    `ProviderChain.request`, and asserts the slice's own commands ran.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> verify_slice
  CT75 [FUNCTIONAL]: in that same live test, a command belonging to a **different** slice does
    not run, and `commands_for(None)` runs exactly once at plan level. Catches: a gate that
    runs everything, which a naive per-slice assertion would pass.
    kill: remove-call src/fa/inner_loop/slice_verification.py::verify_slice -> commands_for
  CT76 [CONSTRAINT]: `plan_ids.commands_for` has at least one production call site after this
    slice, closing register row D4. Catches: the S16 proposal to delete `.commands` for having
    no consumers.
TESTS: tests/test_verify_gate_live.py   (NEW — author it)
```verify
uv run pytest tests/test_verify_gate_live.py -q
uv run ruff check src/fa/inner_loop/workflow_controller.py tests/test_verify_gate_live.py
```
- [ ] STEP1: call `verify_slice` from `_run_stage` after a coder stage, guarded by `role == "coder"` (exit: `grep -n "verify_slice" src/fa/inner_loop/workflow_controller.py` prints at least one line)
- [ ] STEP2: implement `_synthesise_repair_report` building the harness-origin eval report per Q10(a) (exit: `uv run pytest tests/test_verify_gate_live.py -q -k route` exits 0)
- [ ] STEP3: write the SD-C live test on `tests/fixtures/session_wiring.py`, mocking only `ProviderChain.request` and returning a plan authored from the SLICE1b skill text (exit: `uv run pytest tests/test_verify_gate_live.py -q -k live` exits 0)
- [ ] STEP4: add the negative assertion that another slice's command did not run (exit: `uv run pytest tests/test_verify_gate_live.py -q` exits 0)
- [ ] STEP5: run each slice's kill-check by hand and record the result in the ledger (exit: `uv run pytest tests/test_verify_gate_live.py tests/test_verify_slice.py -q` exits 0)

## Increment definition of done

- [ ] Every `CT#` satisfied: each slice's `verify` block exits 0.
- [ ] The gate runs in a real session: `tests/test_verify_gate_live.py` boots `drive_session`
      with only `ProviderChain.request` mocked, and deleting the `verify_slice` call site in
      `workflow_controller.py` makes it fail. A kill-check aimed at `extract_plan_ids`
      instead does not count.
- [ ] `VACUOUS`, `PRODUCER_ABSENT` and `REGRESSION` each demonstrated on a constructed slice,
      not merely representable in the enum.
- [ ] The operator's working tree is byte-identical before and after a full gate run
      (CT62), verified with `git status --porcelain` captured on both sides.
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
