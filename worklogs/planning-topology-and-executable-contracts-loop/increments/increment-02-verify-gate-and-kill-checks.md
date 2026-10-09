---
Increment-ID: RM-planning-topology-I02
Roadmap-ID: RM-planning-topology
status: IN PROGRESS
slices: 8
shipped: —
---

# INCREMENT I02: Executable contracts & the verify gate

**Shippable when:** every coder workflow admits a supplied, usable plan before baseline capture or coder dispatch; determinate schema/kill-directive diagnostics receive bounded planner repair in the same invocation in both modes; and no rejected pre-coder attempt reaches coder or eval. After a successful coder stage, the harness runs each slice's `verify` commands, records real exit codes, and proves every `FUNCTIONAL` contract against production through its declared kill-check. Post-coder verification/eval routing remains governed by Q55/Q56.

Rationale lives in [`../notes/i02-slice-verification-design.md`](../notes/i02-slice-verification-design.md),
[`../notes/i02-handoff-verify-gate.md`](../notes/i02-handoff-verify-gate.md), and the operator-E2E
ownership/design record [`../notes/e2e-handoff-and-plan-review-design.md`](../notes/e2e-handoff-and-plan-review-design.md).
Do not restate rationale here.

**Current code snapshot (rechecked 2026-10-09; line references are this checkout):**
- `src/fa/inner_loop/slice_verification.py` exists. `verify_plan` is now called from
  `_run_stage` after a successful coder (`workflow_controller.py:1098`), but
  `validate_kill_directives` (`slice_verification.py:679`) still has no production caller.
  CT87 is specifically the missing admission producer, not the verify-command runner.
- `plan_ids.py` exposes `extract_plan_ids`, `precheck`, `PlanIds`, and `SliceRecord`.
  A direct stdlib-only probe confirmed `precheck("")` returns `ok=True` with no slices and
  `validate_kill_directives("", extract_plan_ids(""))` returns `[]`. Admission must therefore
  reject missing/unreadable/empty input and must not accept a final candidate with no parsed
  slice. First collect any determinate non-empty structural `FAIL` diagnostic (for example,
  a near-miss slice heading) for bounded repair; if no such diagnostic explains a no-slice parse,
  block as indeterminate. Neither pure validator proves an empty plan is valid. `precheck` is
  advisory by design in I01; I02 routes only its determinate `FAIL` diagnostics through Q57,
  while `WARN` is not a block.
- `WorkflowArtifactPaths` (`workflow_controller.py:123-129`) has `eval_report`, `flow_state`,
  `verification`, and `verify_baseline`, but no admission history. `StageResult` (`:212-219`)
  carries `role`, `exit_code`, `eval_report`, and `verification`; it has no admission outcome.
- `_run_stage` is at `workflow_controller.py:952`. It takes the stage task from
  `ctx.task_for(role)` and appends evidence only for eval (`:997-1006`). It captures the
  baseline before dispatching coder (`:1053-1081`), but currently has no pre-coder admission.
  `WorkflowContext.plan_text()` returns `None` on missing/unreadable input (`:171-183`), and
  the current coder path can extract an empty `PlanIds` and continue.
- `_run_initial_roles` (`workflow_controller.py:1448-1477`) runs configured roles and returns
  on a nonzero stage. Adaptive planner/coder/eval dispatches are eval-report-driven
  (`:1597-1654`); there is no pre-coder repair route. `_run_linear` (`:1774-1837`) is a
  one-pass role loop. The CLI defaults to `linear` (`cli.py:723-728`) and passes
  `max_replans`, but only `_run_adaptive` currently consumes that budget; admission must thread
  it into the linear path without adding linear eval-repair semantics.
- `_run_adaptive_replan` increments `replan_round` but preserves `repair_round`
  (`workflow_controller.py:1635-1638`). `_run_stage` uses `repair_round == 0` to choose
  exclusive baseline creation (`:1067-1081`); `_write_json_exclusive` uses `O_EXCL`
  (`:318-358`). Thus a later coder after an eval-driven planner route can hit a second-create
  error. `load_verify_baseline` checks run/schema/nodeid shape (`:362-391`) but does not compare
  the stored `TESTS:` path map to the current plan revision.
- The CLI `--plan` option is optional (`cli.py:758-767`) and currently checks existence only
  when supplied (`:1369-1372`). E137 requires a plan for coder workflows. The controller must
  also defend direct `run_workflow` callers; an empty parse must not silently pass admission.
  `tests/test_verify_gate_live.py::test_missing_plan_is_indeterminate_and_blocks_an_eval_false_pass`
  currently exercises the too-late `_run_stage` behavior; migrate it to assert pre-coder rejection
  through the CLI/controller while retaining a separate post-coder indeterminate-verification case.
- The planner write allowlist is `knowledge/research/` and `.fa/`
  (`profiles.py:132-145`), not canonical `worklogs/...` paths. Any repair channel must be
  controller-bounded and must not expand general planner writes. `verify_baseline.json`,
  `verification.json`, `eval_report.json`, and `flow_state.json` currently land in the run log
  (`workflow_controller.py:233-249`); the proposed `admission.json` belongs beside them.
- `tests/test_verify_gate_live.py` already contains the real `run_workflow` → `_cmd_run` →
  `drive_session` C1 composition-root test; the old “NEW — author it” label is stale. Keep the
  provider request as the only mocked boundary. The workflow verify gate defaults to `observe`
  (`feature_flags.py:58-61`, key `workflow.verify_gate.mode`); pre-coder plan admission is a
  separate safety check and is not made advisory by that flag.
- Production workflow calls run inside the `first-agent` container. Host environment variables
  are not automatically forwarded through `docker compose exec`; the sessions mount is
  `/sessions`, and persistent artifacts mount to `/home/fa/.fa` (see
  `worklogs/DEPLOYMENT-ANATOMY.md:12-37`). `scripts/fa update` uses the main-only update path;
  `scripts/fa-update.sh:1093-1110` deploys, waits for health, runs tests, reports the deployed
  HEAD/health/test rc, and exits with the test rc. A nonzero rc is not by itself proof that the
  deployment did not happen.
- The session workspace has its own `.venv`; verify commands run against the workspace tree,
  not the baked image. The production runner uses `build_scrubbed_env` and computes the
  workspace venv paths (`tools/run_bash.py:233-250`); do not widen the ambient environment
  allowlist. Mutation remains narrowly scoped to `src/` plus explicitly allowed `scripts/`,
  with `tests/` outside the overlay and import-provenance checks required (Q54).

**Decisions and implementation guardrails (carry forward):**
- `src/fa/inner_loop/slice_verification.py` owns subprocess execution and kill-check behavior;
  keep `plan_ids.py` pure. The kill directive is read from `section()`, never the joined
  contract body. Keep exactly the two existing operators: `neutralise` and `remove-call`.
- `VACUOUS` and `PRODUCER_ABSENT` block with no appeal; kill-check only `FUNCTIONAL` contracts.
  Every kill-check proves that the mutated module is the one imported. A failed provenance probe
  is `ERROR`, never a verdict.
- Mutation uses the throwaway, explicitly allowlisted `src/` plus `scripts/` roots; tests remain
  outside. Do not widen mutmut's global `source_paths`, write the operator's tree, or mutate the
  repository under test (Q54). Preserve the Q53(c) cost and unrelated-failing-test attribution
  risk: each functional contract runs each declared slice test path.
- **Q57 (operator-resolved):** determinate admission diagnostics are sent to the planner through
  bounded repair in the same workflow invocation; revalidate every revision; no coder while any
  blocking diagnostic remains; budget exhaustion or indeterminate validation fails `blocked`.
  A rejected pre-coder attempt does not run eval. Once coder succeeds, normal Q55/Q56 applies.
- Apply the same pre-coder admission helper to `linear` and `adaptive`; this does **not** make
  linear mode eval-adaptive. Preserve linear's one-pass eval semantics and the caller's normal
  role order. The admission planner call is only an additional bounded repair dispatch before
  coder when needed. Count these attempts against `max_replans` in both modes.
- E137: a workflow containing `coder` requires an explicit `--plan`. Missing, unreadable,
  empty/unparseable/no-slice, or indeterminate plan input is never equivalent to a valid empty
  contract set. CLI rejects missing `--plan` before run/session artifact creation; the public
  controller path independently fails closed before coder. If diagnostics need repair but no
  planner is configured, block without coder/eval.
- `precheck` contributes only determinate `FAIL` diagnostics to repair; `WARN` is recorded but
  does not hold admission. Repair non-empty, diagnosable near-miss structure even when no slice
  parses yet; after revalidation, require at least one parsed slice. Empty input or zero parsed
  slices with no determinate repair diagnostic is indeterminate and blocks. A validator or
  file-read exception is indeterminate and blocks.
- Capture the write-once T0 baseline only after admission accepts the active plan and before the
  first coder. Never key T0 creation only to `repair_round`; later planner/coder rounds reuse the
  same baseline. If a post-coder plan revision changes a slice's `TESTS:` path set, baseline
  comparison is indeterminate and blocks rather than comparing mismatched maps.
- **Q58 — RESOLVED by operator, 2026-10-09:** use a controller-owned candidate under the
  run's workspace-local `.fa/admission/<run_id>/` area and grant the repair stage a single-target
  writer only. The planner never writes the active `--plan` or receives a broader `worklogs/`
  allowlist. For an increment workflow, the authoritative plan is the exact supplied file under
  `worklogs/planning-topology-and-executable-contracts-loop/increments/`; that same path remains
  canonical before and after repair. After re-reading and passing both validators, the controller
  serializes promotions for that target, rechecks the original-plan hash, writes the candidate to
  a hidden, uniquely named non-plan temporary sibling of the canonical file, flushes it, and atomically replaces the original at
  the **same path**; clean the temporary sibling on failure. No `.fa` candidate becomes an alternate active plan; remove the candidate after promotion and retain its hash/route in `admission.json`. A failed validation,
  read/write, hash check, or replacement blocks before coder and leaves the original plan bytes
  unchanged; attempt diagnostics, target/source/candidate/promoted hashes, and routes go in
  `admission.json`. The source hash and promotion lock protect against competing updates only;
  neither is a review approval marker. E2E uses a disposable copy at the same relative increments
  path and never edits the tracked source plan.
- A successful coder stage is always followed by the real eval stage, even when verification is
  blocking. Preserve the model-authored `EvalReport`: observe mode leaves eval routing intact;
  enforce mode applies Q56 only after eval, and a blocking non-complete eval route remains
  authoritative. Do not synthesize an eval report in the coder stage.
- The plan-revision/admission history is a separate persisted `admission.json`; do not overload
  `eval_report.json` or assert that the harness assigned a live-E2E result. `flow_state.json`
  remains the controller's terminal route/status artifact.

---

## Shipping order — E130 history and current status

The Phase A/Phase B split below records E130's original sequencing and sizing decision. Its
"do not start Phase B" stop condition was later explicitly superseded by the operator in E164;
SLICE2–SLICE5 are now implemented. The Phase A/B distinction remains useful as a risk map, not
as an unfinished prerequisite. D1b/D3 were closed in E147, and SLICE5 STEP5–STEP6 were closed
in E190–E191. The earlier verify/eval composition-root path is proven; current closure requires
Q57 admission wiring in both workflow modes, the missing E137 `--plan` contract, write-once
baseline reuse across eval replans, the admission C1/C3 and mutation proof, then SLICE7's
reviewed host package. Post-merge live evidence remains increment-level, operator-reviewed work.

**Phase A, the command gate.** SLICE1 (runner) + SLICE5 restricted to a command-only verdict +
SLICE6 wiring. It reads the commands a slice declares and routes only after the real eval stage;
it is the independently valuable system exercised on the live host. The verified C1 path now
boots `run_workflow` → `_cmd_run` → `drive_session`.

**Corrected 2026-10-08 (E145). Phase A does not close D1; it closes D4.** The earlier claim was
wrong on a checkable fact. D1's live half (D1a — the coverage gate observes a non-empty slice
set inside a real `run_workflow`) is **already closed** by
`tests/test_slice_id_validation.py:199`, verified by executing D1's own kill-check: neutralising
`extract_plan_ids` at `workflow_controller.py:332` reddens that live test. What Phase A really
retires is **D4** — `commands_for` gains its first production reader, ending the SD-B violation
I01 left standing.

**Phase A0, the precondition.** The live plan-emission assumption was a genuine blocker: a plan
*the model actually writes*, following the injected skill skeleton, had to parse into slices
carrying `verify` fences. D1b/D3 were closed with the live chain in E147, before SLICE5/SLICE6.

**Phase B, the kill-check.** SLICE2 (directive parse) + SLICE3 (AST operators) + SLICE4
(overlay) + the kill-check columns of SLICE5 and the kill-related contracts of SLICE6. It holds
two thirds of the complexity and much of the unmeasured risk. E130 originally held Phase B for
a live Phase A cost measurement; the operator explicitly directed crossing that gate in E164,
with its O(contracts × test paths) cost and unrelated-red-test attribution risk recorded there
and in Q53(c).

The original Phase A command-only verdict used `PASS`, `FAILING`, `ERROR` and `SKIPPED`;
`PROVEN`, `VACUOUS` and `PRODUCER_ABSENT` became reachable only after Phase B's kill-check
runner shipped. This is historical sequencing, not the current verdict surface.

## SLICE1: The command runner (three-state, scrubbed, bounded)
STEPS: prescriptive
DEPS: —
INTENT: the harness, not the model, executes a slice's verify commands and records the real
  exit code, with a result type that cannot express "couldn't run" as "passed".
CONTRACTS:
  CT44 [FUNCTIONAL]: `run_commands(commands, *, workspace, timeout_s, deadline)` returns a
    `tuple[CommandResult, ...]`, one per input command in order, each carrying the verbatim
    command, the real integer `exit_code`, and `stdout_tail`/`stderr_tail`.
    kill: neutralise src/fa/inner_loop/slice_verification.py::run_commands
  CT45 [FUNCTIONAL]: a command exceeding `timeout_s` yields `outcome=ERROR` with
    `exit_code=None`; it is never `PASS` and never silently `FAIL`.
    kill: neutralise src/fa/inner_loop/slice_verification.py::_timeout_result
  CT46 [CONSTRAINT]: the subprocess environment is built by
    `tools.bash_env.build_scrubbed_env` with the **workspace's** `.venv/bin` prepended to
    `PATH`, mirroring `tools/run_bash.py:233-246`. `_run_subprocess_fallback` is not imported,
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
  CT49b [PRESERVATION]: `PYTHONPATH` survives `build_scrubbed_env`
    (`tools/bash_env.py:41`) and reaches the verified command. Catches the highest-impact
    silent inversion available in this system: with `PYTHONPATH` dropped, every verify command
    would import the image-baked `/opt/first-agent/src` instead of the coder's workspace edits,
    so the gate would pass no matter what the coder did — or did not — write. The allowlist is
    one line in an unrelated module; this contract is what stops a future tightening of it from
    silently disabling the whole increment.
  CT49c [FUNCTIONAL]: every command runs with `cwd` set to the **session workspace**, matching
    what the agent's own shell already does (`run_bash.py:240`, `cwd=root`). This is conformance
    with existing behaviour, not a new architectural requirement — no change to the workspace
    model is needed or proposed. Catches: a gate that invents its own working directory and so
    verifies the tree FA was installed from instead of the one the coder edited.
    kill: remove-call src/fa/inner_loop/slice_verification.py::run_commands -> _workspace_cwd
  CT49d [FUNCTIONAL]: the runner takes its **own** per-command timeout, defaulting to 600 s and
    operator-overridable; it does not inherit `DEFAULT_BASH_TIMEOUT_SECONDS`
    (`runtime_limits.py:71`, currently 30). A timeout yields `ERROR` carrying the elapsed
    seconds and the command text. Catches the first live run blocking every slice because a
    real `uv run pytest` exceeded a 30 s budget meant for interactive shell calls.
    kill: neutralise src/fa/inner_loop/slice_verification.py::_command_timeout
  CT49e [FUNCTIONAL]: after scrubbing, the runner **sets** `UV_PROJECT_ENVIRONMENT` to
    `<workspace>/.venv` and `UV_NO_SYNC=1`, following `run_bash.py:233-236`, rather than
    inheriting them. Catches two things: `uv run` resolving a different session's venv from an
    inherited stale pin, and an implicit lockfile sync reaching for a network the container
    does not have.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_build_env -> _pin_uv_environment
TESTS: tests/test_slice_verification_runner.py   (NEW — author it)
```verify
uv run pytest tests/test_slice_verification_runner.py -q
uv run ruff check src/fa/inner_loop/slice_verification.py tests/test_slice_verification_runner.py
```
- [x] STEP1: create `src/fa/inner_loop/slice_verification.py` with `CommandOutcome` (PASS/FAIL/ERROR) and a frozen `CommandResult` dataclass (exit: `uv run python -c "from fa.inner_loop.slice_verification import CommandResult, CommandOutcome"` exits 0)
- [x] STEP2: implement `_run_one` using `subprocess.run(..., shell=True, capture_output=True, text=False, timeout=timeout_s, env=env)`, decoding with `errors="ignore"`, copying the policy at `tools/run_bash.py:233-250` (exit: `! grep -q "_run_subprocess_fallback" src/fa/inner_loop/slice_verification.py` exits 0)
- [x] STEP3: implement `run_commands` with the between-command deadline check (exit: `uv run pytest tests/test_slice_verification_runner.py -q -k "deadline or timeout"` exits 0)
- [x] STEP4: write the oracles for CT44–CT49, including a seeded `sleep` command for CT45 (exit: `uv run pytest tests/test_slice_verification_runner.py -q` exits 0)

## SLICE2: Kill directives — strict parse, determinate diagnostics
STEPS: prescriptive
DEPS: —
INTENT: a contract's declared kill-check is read from the slice's raw text and validated before
  coder dispatch, so a missing or malformed directive cannot silently disable the non-vacuity
  gate. I02/SLICE6 routes determinate diagnostics through bounded planner repair; it blocks only
  when the input/validator is indeterminate, no planner is available, or the retry budget ends.
CONTRACTS:
  CT50b [FUNCTIONAL]: `<symbol>` accepts a bare name **or** a dotted `Class.method`, and the
    operators resolve both. Catches a gap found while auditing this plan's own directives:
    three of its contracts name a method (`_Silence.visit_Call`), which a bare-name grammar
    cannot express — the directive would resolve to nothing and report `PRODUCER_ABSENT`
    against working code.
    The half SLICE2 owns is the grammar and `_split_dotted`. The half that resolves a dotted
    symbol against real source is CT81 (SLICE3), declared there because that is the slice
    that builds it — see §4 "Producer ownership". This directive originally named
    `_resolve_symbol`, a guess at a name SLICE3 had not chosen yet (Q48).
    kill: neutralise src/fa/inner_loop/slice_verification.py::_split_dotted
  CT50 [FUNCTIONAL]: `parse_kill_directives(record)` reads `record.section` line by line
    and returns `dict[contract_id, KillDirective]`, attributing each directive to the `CT<n>`
    entry it is indented under. Trailing prose after the directive does not affect parsing.
    kill: neutralise src/fa/inner_loop/slice_verification.py::parse_kill_directives
  CT51 [FUNCTIONAL]: a near-miss line — `kil:`, `Kill :`, `kill-check:` — is reported as
    `kill-directive-near-miss` naming `file:line`, in the manner of `heading-near-miss`
    (CT26) and `step-near-miss` (CT37). Catches: a typo that would otherwise present as
    "the planner declared none".
    kill: remove-call src/fa/inner_loop/slice_verification.py::validate_kill_directives -> _near_miss
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
- [x] STEP1: add `KillOperator` (NEUTRALISE/REMOVE_CALL) and a frozen `KillDirective` carrying operator, path, symbol, callee, line (exit: `uv run python -c "from fa.inner_loop.slice_verification import KillDirective"` exits 0)
- [x] STEP2: implement `parse_kill_directives` over raw section text with the strict pattern `^\s*kill:\s*(neutralise|remove-call)\s+(\S+)::(\S+?)(?:\s*->\s*(\S+))?\s*$` (exit: `uv run pytest tests/test_kill_directives.py -q -k parse` exits 0)
- [x] STEP3: implement `validate_kill_directives` with the soft, strict and near-miss patterns (exit: `uv run pytest tests/test_kill_directives.py -q -k "near_miss or malformed or ambiguous or missing"` exits 0)
- [x] STEP4: add the six-case corpus from the design note §F1 as a table-driven oracle (exit: `uv run pytest tests/test_kill_directives.py -q` exits 0)

## SLICE2b: Source positions move into the parser that reads the source

INTENT: retire I02's private copy of the contract grammar; I01 reports where it read each
contract, and I02 does arithmetic on that answer instead of re-deriving it.
DEPS: SLICE2
STEPS-MODE: prescriptive
CONTRACTS:
  CT78 [FUNCTIONAL]: `SliceRecord` carries `start_line` (1-based document line of the slice
    heading) and `contract_lines` (`(contract id, 1-based document line)` per declared
    contract), and `PlanIds.contract_line(id)` returns that line, or `0` when the id was
    never declared in this parse. Catches: a parser that returns structure without source
    positions, which forces every consumer to re-derive them.
    kill: neutralise src/fa/inner_loop/plan_ids.py::_build_record
  CT79 [CONSTRAINT]: `slice_verification` contains no pattern matching a contract entry.
    Attribution asks `_owner_at` which declaration most recently preceded a line, using the
    positions I01 supplied. Catches: the duplicated grammar coming back.
    kill: neutralise src/fa/inner_loop/slice_verification.py::_owner_at
  CT80 [CONSTRAINT]: `0` is the only "line unknown" answer; no code path guesses a line.
    Catches: a diagnostic pointing confidently at the wrong place, which is worse than one
    that admits it does not know.
TESTS: tests/test_plan_ids.py, tests/test_kill_directives.py
```verify
uv run pytest tests/test_plan_ids.py tests/test_kill_directives.py -q
uv run ruff check src/fa/inner_loop/plan_ids.py src/fa/inner_loop/slice_verification.py
```
- [x] STEP1: add `start_line` and `contract_lines` to `SliceRecord`, populated in `_build_record` from the existing `_contract_declaration_sites` (exit: `uv run pytest tests/test_plan_ids.py -q -k positions` exits 0)
- [x] STEP2: add `PlanIds.contract_line` beside `contract_class` (exit: `uv run pytest tests/test_plan_ids.py -q -k "contract_line or ContractSourcePositions"` exits 0)
- [x] STEP3: delete `slice_verification._CONTRACT_ENTRY_RE`, add `_owner_at`, and take `SliceRecord` in `parse_kill_directives` (exit: `grep -c _CONTRACT_ENTRY_RE src/fa/inner_loop/slice_verification.py` prints 0)
- [x] STEP4: tighten the accessors to strict slice ids (Q43(ii)) (exit: `uv run pytest tests/test_plan_ids.py -q -k accessors` exits 0)

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
    kill: neutralise src/fa/inner_loop/slice_verification.py::_Silence.visit_Call
  CT57 [FUNCTIONAL]: `apply_kill` returns a `KillApplication` carrying **two** counts, because
    the caller asks two questions. `targets` is a question of *search* — how many definitions
    carry the qualified name the directive wrote — and must be exactly 1: `0` is
    `PRODUCER_ABSENT`, `>1` is `ERROR`, never a guess. `edits` is a question of
    *transformation* — how many nodes changed — always 1 for `neutralise`, legitimately `0..n`
    for `remove-call`, since one method may call the emitter four times. Symbols resolve by
    **exact qualified name anchored at the module root**. `source` is `None` whenever
    `targets != 1 or edits == 0`, so unmutated source cannot be run and misreported as
    `VACUOUS`. Collapsing the two counts into one `hits` was a design defect: it made the
    four-call sample of CT56 report `4` and be rejected by this contract as ambiguous (Q47).
    kill: remove-call src/fa/inner_loop/slice_verification.py::apply_kill -> _resolve_targets
  CT58 [CONSTRAINT]: `apply_kill` takes source text and returns source text. It performs no
    filesystem read or write and no subprocess call. Catches: a mutation helper that is
    convenient to call directly on the working tree.
  CT59 [CONSTRAINT]: exactly two operators are implemented and `KillOperator` has exactly two
    members. Catches: the slow growth of a mutation DSL, which `i02-handoff-verify-gate.md`
    §5 forbids.
  CT81 [FUNCTIONAL]: the operators resolve a dotted `Class.method` symbol, by **exact**
    qualified name anchored at the module root. The half of CT50b that lives here, because
    this is the slice that builds the resolver (Q48). A bare `visit_Call` resolves to
    nothing rather than to some same-named method: under exactness a mis-spelled or
    under-qualified symbol lands on `PRODUCER_ABSENT`, which is loud and accurate, and
    `targets > 1` stays reachable only through a genuine double definition.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_resolve_targets -> _split_dotted
TESTS: tests/test_kill_operators.py   (NEW — author it)
```verify
uv run pytest tests/test_kill_operators.py -q
uv run ruff check src/fa/inner_loop/slice_verification.py tests/test_kill_operators.py
```
- [x] STEP1: implement `_resolve_targets(tree, symbol)` returning every definition whose qualified name is exactly `symbol`, and `_neutralise_body(node)` replacing the body with `return None` (exit: `uv run pytest tests/test_kill_operators.py -q -k neutralise` exits 0)
- [x] STEP2: implement `_Silence(ast.NodeTransformer)` replacing every `ast.Call` to the callee inside the enclosing symbol with `ast.Constant(None)`, resolving both `Name` and `Attribute` callees, and counting each (exit: `uv run pytest tests/test_kill_operators.py -q -k remove_call` exits 0)
- [x] STEP2b: assert the four-call-form sample yields `edits == 4` (exit: `uv run pytest tests/test_kill_operators.py -q -k call_forms` exits 0)
- [x] STEP3: implement `apply_kill` dispatching on the operator and returning a `KillApplication`, and `KillApplication.__post_init__` refusing any state where `source` and the counts disagree (exit: `uv run pytest tests/test_kill_operators.py -q -k counts` exits 0)
- [x] STEP4: assert the closed operator set with `len(KillOperator) == 2` (exit: `uv run pytest tests/test_kill_operators.py -q` exits 0)

## SLICE4: The narrow `src`/`scripts` mutation overlay with a provenance guard
STEPS: prescriptive
DEPS: —
INTENT: run a mutated copy of production code without writing to the operator's tree, and
  refuse to return a verdict unless the mutated module is provably the one that was imported.
  Expectation on a later slice, stated as prose and not as a directive (§4 "Producer
  ownership"): **SLICE5 must provide `_run_kill_check`, and it must call
  `_assert_overlay_wins` before any kill-check outcome is trusted.** The contract and the kill
  directive for that call live in SLICE5, which builds it.
CONTRACTS:
  CT60 [FUNCTIONAL]: `mutation_overlay(workspace, rel_path, mutated_source)` yields a
    temporary directory containing a copy of the allowlisted `workspace/src` and, when present,
    `workspace/scripts` roots. `rel_path` must target one copied root and only its overlay copy is
    replaced by `mutated_source`; the overlay is removed on normal exit **and** on exception.
    `workspace` is the session workspace (`run_workflow(workspace=…)`), never the harness tree.
    kill: remove-call src/fa/inner_loop/slice_verification.py::mutation_overlay -> _copy_src
  CT61 [FUNCTIONAL]: every overlay command receives `<overlay>/src` **prepended** to the
    inherited `PYTHONPATH`, preserving `<workspace>/src` behind it as
    `scripts/fa-entrypoint.sh:237` does. For a `scripts/` target, the overlay parent is also an
    import root and a pytest bootstrap inserts it ahead of the workspace-root `scripts/` package
    before test collection; `cwd` stays the workspace root and tests remain the real ones.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_overlay_env -> _prepend_pythonpath
  CT62 [FUNCTIONAL]: `_assert_overlay_wins(module, overlay_root, env, *, workspace)` runs a
    root-aware provenance probe and reports `PASS` only when the target module resolves inside
    its exact overlay source tree (`src/` or `scripts/`); anything else is `ERROR`, never `FAIL`
    and never `PASS`. The scripts-root pytest bootstrap separately checks the exact module before
    tests execute, so a workspace import cannot masquerade as a killed mutation.
    Catches the measured defect that an installed package resolves to an absolute path, so a
    mutated copy is simply never imported and every kill-check reports a false `VACUOUS`.
    The *wiring* claim — that no verdict is trusted until this has run — is CT82 (SLICE5),
    because SLICE5 builds the runner that must call it. This directive named `_run_kill_check`
    until Q48; a slice cannot kill a producer it does not build (§4 "Producer ownership").
    kill: neutralise src/fa/inner_loop/slice_verification.py::_assert_overlay_wins
  CT63 [CONSTRAINT]: only the explicit `src/` and `scripts/` roots may be copied, each target
    is contained beneath its selected root, and `tests/` is never copied. Test files are read
    from the operator's tree and are structurally impossible for a kill-check to mutate. Catches:
    broad repository copying or cross-root/symlink writes that could rewrite the oracle.
  CT64 [CONSTRAINT]: after any `mutation_overlay` use, `git status --porcelain` in the
    operator's root is byte-identical to its value before, and no `git worktree` command is
    invoked. Catches: a mutation reaching the real checkout.
TESTS: tests/test_mutation_overlay.py   (NEW — author it)
```verify
uv run pytest tests/test_mutation_overlay.py -q
uv run ruff check src/fa/inner_loop/slice_verification.py tests/test_mutation_overlay.py
```
- [x] STEP1: implement `mutation_overlay` as a `@contextmanager` copying required `src/` and optional `scripts/` roots separately, writing only beneath the selected root, and removing the tree in `finally` (exit: `uv run pytest tests/test_mutation_overlay.py -q -k overlay` exits 0)
- [x] STEP2: implement `_overlay_env` preserving the scrubbed SLICE1 environment, prepending `<overlay>/src`, and adding the scripts import root plus pre-collection bootstrap only for `scripts/` targets (exit: `uv run pytest tests/test_mutation_overlay.py -q -k pythonpath` exits 0)
- [x] STEP3: implement `_assert_overlay_wins` with exact, root-specific containment for `src/` and `scripts/`, and map any failed probe to `ERROR` (exit: `uv run pytest tests/test_mutation_overlay.py -q -k provenance` exits 0)
- [x] STEP4: add the negative oracle — with the probe disabled, a mutation of an installed module is NOT observed; with it enabled, the run is `ERROR` not `VACUOUS` (exit: `uv run pytest tests/test_mutation_overlay.py -q` exits 0)

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
  CT66 [FUNCTIONAL]: when the slice's commands pass and every test path in the slice's
    `TESTS:` list still passes under one contract's kill-check, that contract is `VACUOUS`
    and the slice verdict names the contract id. Under Q53(c), any failing test among those
    paths makes that contract's kill-check `PROVEN`; attribution may therefore be weaker than
    one contract to one test.
    kill: remove-call src/fa/inner_loop/slice_verification.py::verify_slice -> _run_kill_check
  CT67 [FUNCTIONAL]: when `apply_kill` reports `targets == 0` — or `targets == 1` with
    `edits == 0`, the call site a `remove-call` names not being there — the verdict is
    `PRODUCER_ABSENT` and names the contract and the target. `targets > 1` is `ERROR`, never a
    guess at which definition was meant (CT57). It is a distinct member of
    `SliceVerdict`, not folded into `VACUOUS`.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_classify -> _producer_absent
  CT68 [FUNCTIONAL]: a test **green at the T0 baseline and red now** yields `REGRESSION`;
    red-to-red is advisory and does not block. The baseline is keyed by **pytest nodeid**
    (`tests/test_x.py::test_case`), never by file. A file-keyed baseline turns one
    newly-added failing test into a red file and reports `REGRESSION` where the truth is
    `FAILING` — the agent adding a deliberately-red test is the common case, not the rare
    one. A nodeid absent at T0 — a new test, a renamed one — can never be `REGRESSION`, and
    an absent row is not `False` (Q49).
    kill: remove-call src/fa/inner_loop/slice_verification.py::_classify -> _compare_baseline
  CT69 [CONSTRAINT]: the baseline and current nodeid capture run only the slice's own
    `TESTS:` paths, never the whole repository suite; the kill-check phase runs every declared
    slice test path for each `FUNCTIONAL` contract (Q53(c)), not a guessed contract-to-test
    mapping. This costs O(functional contracts × slice test paths) and may attribute an
    unrelated path's failure to a contract; the operator explicitly accepts that risk. The
    baseline and "now" side are **harness-issued and instrumented** (`--junitxml`), distinct
    from the planner's `verify` commands, which run verbatim (`cli.py:165-170`) and yield only
    an exit code and a truncated tail — no nodeid is recoverable from them. Catches an
    O(slices × repository suite-time) gate that will not survive a real increment (§6.2).
  CT85 [CONSTRAINT]: the baseline is captured **once per run, at T0**, before the first coder
    stage; a repair round never recaptures it, and `verify_slice` takes it as an argument and
    never gathers one. Catches: a repair round laundering a regression into the baseline —
    round 1 breaks an adjacent test, round 2 recaptures, and the breakage becomes the new
    normal with nothing ever reported.
  CT70 [CONSTRAINT]: `VACUOUS` and `PRODUCER_ABSENT` expose no dismissal or appeal parameter.
    Catches: an appeal path quietly reintroduced from E63, which granted it to generated
    mutants only.
  CT82 [FUNCTIONAL]: `_run_kill_check` calls `_assert_overlay_wins` and refuses to produce a
    verdict unless the probe passed; a failed probe is `ERROR`. The wiring half of CT62, moved
    here because this slice builds the runner (Q48).
    kill: remove-call src/fa/inner_loop/slice_verification.py::_run_kill_check -> _assert_overlay_wins
  CT83 [FUNCTIONAL]: `scripts/check_kill_directive_ownership.py` exits non-zero when a slice
    whose `STEP` boxes are **all ticked** declares a kill directive that does not resolve to
    exactly one definition in the file it names. Measured on the plans as they stand: 14 of 30
    directives cannot fire, of which 12 name producers of slices not yet built — legitimate,
    the plan being ahead of the code — and 2 were the category error this rule forbids (E168,
    E169). The tick is the trigger because an unfinished slice is *expected* to point at code
    that does not exist; a finished one pointing at nothing is a plan defect.
    kill: remove-call scripts/check_kill_directive_ownership.py::main -> _unresolved_directives
  CT84 [CONSTRAINT]: no `kill:` directive names a producer built by a different slice. A
    cross-slice expectation is `INTENT:` prose plus a contract in the slice that builds the
    producer. Catches the category error directly: a directive is an instrument for hardening a
    test suite, and cannot specify an interface for code that does not exist yet — it can only
    guess a private name (measured: `_resolve_symbol` vs `_resolve_targets`) or mutate code the
    declaring slice's tests never execute (measured: 36 passed, fully green).
TESTS: tests/test_verify_slice.py   (NEW — author it)
```verify
uv run pytest tests/test_verify_slice.py -q
uv run ruff check src/fa/inner_loop/slice_verification.py tests/test_verify_slice.py
```
- [x] STEP1: add `SliceVerdict` with exactly the seven members in the design note §3.2 (exit: `uv run python -c "from fa.inner_loop.slice_verification import SliceVerdict; assert len(SliceVerdict)==7"` exits 0)
- [x] STEP2: implement `_run_kill_check(directive, test_paths, root)` using `apply_kill` + `mutation_overlay` + `_assert_overlay_wins` + `run_commands`, in that order; execute every declared slice test path (Q53(c)), and let the provenance probe gate the result (exit: `uv run pytest tests/test_verify_slice.py -q -k kill_check` exits 0)
- [x] STEP3: implement `_classify` mapping phase outputs to a verdict, with `ERROR` dominating, and `_compare_baseline(baseline, now)` comparing nodeid maps where an absent T0 row never yields `REGRESSION` (exit: `uv run pytest tests/test_verify_slice.py -q -k classify` exits 0)
- [x] STEP4: build the three-row oracle from the design note §3.6 — PROVEN, PRODUCER_ABSENT, VACUOUS — as the slice's primary test (exit: `uv run pytest tests/test_verify_slice.py -q` exits 0)
- [x] STEP5: implement `scripts/check_kill_directive_ownership.py` reading every plan under `worklogs/planning-topology-and-executable-contracts-loop/increments/` with `extract_plan_ids` + `parse_kill_directives` + `_resolve_targets`, reporting one line per unfirable directive of a fully-ticked slice (exit: `uv run python scripts/check_kill_directive_ownership.py` exits 0)
- [x] STEP6: add the ownership oracle — a fixture plan with one ticked slice naming an absent producer and one unticked slice naming the same, asserting the first is reported and the second is not (exit: `uv run pytest tests/test_verify_slice.py -q -k ownership` exits 0)

## SLICE6: Wire the gate into the controller, and prove it live
STEPS: prescriptive
DEPS: SLICE5
INTENT: the command gate remains reachable from a real workflow run through `commands_for`,
  while the new shared admission loop validates/repairs the supplied plan before coder in both
  modes. The composition-root test proves admission, verification, real eval, and terminal
  reconciliation through `run_workflow` → `_cmd_run` → `drive_session` (SD-C).
CONTRACTS:
  CT71 [FUNCTIONAL]: after a `coder` stage returns exit 0, `_run_stage`
    (`workflow_controller.py`) verifies **every slice** the plan declares and attaches a
    `PlanVerification` to its `StageResult`. It is at the shared dispatch choke point, not in
    either pipeline loop, so linear, adaptive, and repair dispatches all reach it.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> verify_plan
  CT72 [FUNCTIONAL]: after the actual eval report is built, controller reconciliation prevents
    an enforce-mode blocking verification result from yielding effective route `complete`,
    terminal status `DONE`, or process exit 0. For eval route `complete`, a determinate post-coder
    verification block routes to `return_to_coder`; an indeterminate post-coder verification
    result routes to `blocked`. Missing, unreadable, or empty input is rejected before coder;
    a no-slice parse is repaired first only when `precheck` supplies a determinate diagnostic,
    otherwise it blocks. These are admission outcomes under CT90/CT91, not post-coder evidence.
    Observe mode keeps
    eval routing. Any eval non-complete route remains authoritative even when verifier evidence
    is indeterminate. `eval_report.json` remains the model-authored report; only `flow_state.json`
    records the effective route.
    kill: neutralise src/fa/inner_loop/workflow_controller.py::_effective_controller_route
  CT73 [FUNCTIONAL]: every successful coder stage is followed by one real eval stage, including
    when the caller omits `eval` or supplies it before `coder`. Eval receives the typed
    verification result from that coder attempt. A blocking gate never suppresses eval.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::run_workflow -> _ensure_eval_after_coder
  CT74 [CONSTRAINT]: post-coder verification repair remains governed by the existing
    `WorkflowProgress.repair_round` cap; a determinate blocking result cannot start an unbounded
    coder/eval loop. Pre-coder admission repairs use the separate shared `replan_round` budget
    (`max_replans`) in both modes; admission does not invoke eval while the plan is rejected.
    Linear remains one-pass for eval-driven outcomes. When eval says `complete`, indeterminate
    post-coder gate evidence routes to `blocked` and cannot initiate repair; an eval-authored
    non-complete repair route still follows Q56 and the same bounded cap.
  CT75 [FUNCTIONAL]: the C1 test boots `run_workflow` with `run_stage_fn=_cmd_run`, which reaches
    real `drive_session`; only `ProviderChain.request` is mocked. It observes all provider roles,
    persisted verification evidence, the eval request, and the terminal artifacts. Removing
    `_run_stage`'s `run_stage_fn` call breaks the live oracle.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> run_stage_fn
  CT76 [FUNCTIONAL]: in that same C1 test, commands are attributed to the slice that declares
    them — a command declared only by SLICE2 is not recorded under SLICE1 — and
    `commands_for(None)` runs exactly once at plan level.
    kill: remove-call src/fa/inner_loop/slice_verification.py::verify_plan -> commands_for
  CT77c [FUNCTIONAL]: the gate has two modes. In **observe** mode — default on first deployment
    — it computes and records the result but never changes routing. In **enforce** mode eval
    still runs and the result is reconciled per CT72. The mode is loaded from the operator's
    feature-flag config and recorded in `verification.json`.
    kill: neutralise src/fa/inner_loop/slice_verification.py::_gate_mode
  CT77b [FUNCTIONAL]: the run writes `verification.json` beside `eval_report.json` through
    `WorkflowArtifactPaths`, carrying plan/slice commands, real exit codes, truncated output,
    per-slice verdicts, kill-checks, errors, and elapsed seconds. Written on every successful
    coder stage, blocking or not.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> write_verification
  CT77 [FUNCTIONAL]: the eval request receives the current typed verification evidence,
    including mode, repair round, plan commands, slice results, kill-checks, regressions and
    errors. The actual report is not replaced with a synthetic harness report.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_eval_evidence_block -> _verification_evidence_lines
  CT86 [FUNCTIONAL]: after plan admission succeeds and before the first `coder` stage, the run
    captures T0 from the admitted plan's `TESTS:` paths and writes `verify_baseline.json` once.
    Baseline creation is write-once across admission repair, coder repair, and eval-driven planner
    replan; it is not keyed only to `repair_round`. Later stages load the same T0. The loader
    verifies that the current plan's per-slice `TESTS:` path map matches the stored map; a changed
    map is indeterminate and blocks rather than comparing incomparable snapshots.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> capture_baseline
  CT87 [FUNCTIONAL]: every coder dispatch in initial, linear, adaptive-repair, or adaptive-replan
    flow passes through one shared admission helper before T0 capture or coder-stage dispatch.
    The helper calls `validate_kill_directives` on the current active plan. Any missing,
    malformed, duplicate, or near-miss functional kill directive is a determinate diagnostic:
    persist it in the per-attempt `admission.json` history, supply the full diagnostic bundle and
    active-plan reference to a configured planner repair dispatch, then re-read and revalidate the
    candidate. Promote no invalid candidate. A valid repair continues in the same invocation;
    no coder is dispatched while any blocking diagnostic remains and no eval runs for a rejected
    pre-coder attempt. The same `max_replans` budget bounds admission and eval-driven planner
    replan in both modes; linear's eval outcome remains one-pass. Missing planner when repair is
    needed, failed/unavailable planner, candidate-write/promotion failure, indeterminate
    validation, or budget exhaustion records a final `blocked` route. An accepted coder proceeds
    through normal Q55/Q56 behavior. The C1 oracle observes provider-role order and persisted
    attempts through the real workflow (Q57).
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_validate_plan_admission -> validate_kill_directives
  CT90 [FUNCTIONAL]: any workflow whose normalized roles contain `coder` requires explicit
    `--plan` at the CLI boundary before run-id/session/artifact creation (E137). Direct
    `run_workflow` callers are guarded too: missing, unreadable, and empty input is indeterminate
    and blocks before planner/coder/eval. A no-slice parse is never accepted as a valid empty
    contract set: if non-empty text has a determinate structural `precheck` diagnostic, route it
    to bounded planner repair; if not, block as indeterminate. Require at least one parsed slice
    before coder. A supplied plan must resolve inside the session workspace before it can be
    revised. For an increment, `--plan` names the canonical file under
    `worklogs/planning-topology-and-executable-contracts-loop/increments/`; admission may replace
    that exact file only after validation and never makes a `.fa` candidate an alternate active
    plan. CLI errors are actionable; controller rejection persists a structured `blocked`
    admission result.
    kill: remove-call src/fa/cli.py::_cmd_workflow -> _require_plan_for_coder
  CT91 [FUNCTIONAL]: admission runs `precheck` on the active plan and includes its determinate
    `FAIL` diagnostics in the same bounded repair batch as kill-directive diagnostics; `WARN`
    alone does not block. Revalidate all structural diagnostics on every candidate. An exception
    from reading/parsing/precheck is indeterminate and blocks. Empty input, or a no-slice parse
    without any determinate structural diagnostic, is indeterminate and blocks; a non-empty
    near-miss heading with a reported `FAIL` is repairable before the final parsed-slice check.
    The real composition-root test proves a structural diagnostic reaches planner before coder.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_validate_plan_admission -> precheck
  CT92 [FUNCTIONAL]: controller appends every admission attempt and its diagnostics, plan hashes,
    validator outcome, planner/coder/eval dispatch facts, and final admission route to the
    versioned `admission.json` artifact beside the other run artifacts. Writes are atomic and
    schema-checked; no raw plan body, credentials, or provider secret is copied into this report.
    The real C1 test reads the persisted file, not an in-memory report.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_record_admission_attempt -> write_admission_record
  CT93 [FUNCTIONAL]: during a planner-repair dispatch, the planner's write capability is scoped
    to the exact controller-generated candidate path. The active `--plan`, sibling candidate,
    traversal path, absolute path, and symlink escape are denied; no broader `worklogs/` or
    `.fa/` write permission is introduced for this repair call. The C3 oracle proves both the
    allowed candidate write and denied escapes through the real registry/tool handler.
    kill: remove-call src/fa/inner_loop/profiles.py::_build_tool_builders -> build_scoped_write_file_tool
  CT94 [FUNCTIONAL]: only a fully revalidated candidate whose source hash still matches the
    active plan may be promoted. The controller serializes promotions for that target, rechecks
    the source hash, writes to a hidden, uniquely named non-plan temporary sibling of the exact
    canonical `--plan` file under `worklogs/.../increments/`, flushes it, then atomically replaces
    the original at the same path and cleans temporary/staging drafts. The `.fa` candidate is never an alternate active plan; subsequent coder/verification
    reads use the promoted canonical path. Invalid, stale, unreadable, symlinked, or failed
    candidates/replacements leave the original byte-identical and route `blocked`. The C1 oracle
    asserts in-place replacement after validation and unchanged original bytes on rejection.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_admission_repair -> _promote_validated_plan
TESTS: tests/test_verify_gate_live.py   (EXISTING — extend; C1/C3 admission proofs are new)
```verify
uv run pytest tests/test_verify_gate_live.py -q
uv run ruff check src/fa/inner_loop/workflow_controller.py src/fa/inner_loop/workflow_artifacts.py src/fa/inner_loop/profiles.py src/fa/inner_loop/tools/write_file.py src/fa/cli.py src/fa/feature_flags.py tests/test_verify_gate_live.py
```
- [ ] STEP1: implement/verify `verify_plan(plan_ids, *, root, …) -> PlanVerification`, preserving plan-level and per-slice command ownership (exit: `uv run pytest tests/test_verify_slice.py -q -k verify_plan` exits 0)
- [ ] STEP2: call `verify_plan` from `_run_stage` only after a successful coder stage, capture T0 before that dispatch, and persist the result (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "coder_stage or baseline"` exits 0)
- [ ] STEP3: reconcile the actual eval route with typed verifier evidence through `_effective_controller_route` per Q56; preserve `eval_report.json` (exit: `uv run pytest tests/test_verify_gate_live.py -q -k reconciliation` exits 0)
- [ ] STEP4: make successful coder dispatch always reach eval, pass typed verification evidence, and prove the route matrix plus repair cap (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "role_loops or repair or indeterminate"` exits 0)
- [ ] STEP5: boot the real C1 composition root with only `ProviderChain.request` mocked; assert a verifier false-pass cannot finish DONE (exit: `uv run pytest tests/test_verify_gate_live.py -q -k real_workflow` exits 0)
- [ ] STEP6: assert plan-level and per-slice command attribution and the once-only plan-level command (exit: `uv run pytest tests/test_verify_gate_live.py -q -k real_workflow` exits 0)
- [ ] STEP7: assert eval received the same attempt's typed evidence and the persisted actual eval report remains unmodified (exit: `uv run pytest tests/test_verify_gate_live.py -q -k real_workflow` exits 0)
- [x] STEP8: record the operator-resolved Q58 interface in the open-question/design record: controller-owned candidate, exact-target planner writer, revalidation, then physical replacement of the original canonical increments file at the same `--plan` path. This decision step is complete; runtime implementation and its proofs remain in the following steps (exit: explicit operator decision recorded; no inferred approval)
- [ ] STEP9: repair T0 lifecycle: capture only after the active plan passes admission and before first coder; create once independent of `repair_round`; prove adaptive eval replans reuse it; make `load_verify_baseline` reject a changed per-slice `TESTS:` path map as indeterminate (exit: `uv run pytest tests/test_verify_gate_live.py -q -k baseline` exits 0)
- [ ] STEP10: implement the accepted bounded plan-revision channel across `workflow_controller.py`, `workflow_artifacts.py`, `profiles.py`, and the scoped writer in `tools/write_file.py`: candidate separate from active `--plan`; stage-scoped exact-target write boundary and path/symlink containment; after both validators and source-hash recheck, write a temporary sibling and atomically replace the original canonical increments file at the same `--plan` path; persist per-attempt diagnostics, target/source/candidate/promoted hashes, and final route in `admission.json`. A `.fa` candidate is never the active plan (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "candidate or admission_artifact"` exits 0; C3 traversal/symlink cases deny writes outside the exact candidate target; C1 proves same-path promotion and unchanged source on rejection)
- [ ] STEP11: call `precheck` and `validate_kill_directives` from the shared pre-coder admission helper; pass the combined structured `FAIL` diagnostics to the planner, ignore `WARN` for blocking, and re-run both validators on every candidate. Repair non-empty near-miss schema diagnostics before the final parsed-slice check; empty input or no parsed slice without a determinate diagnostic is indeterminate, not an empty pass (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "admission or precheck"` exits 0)
- [ ] STEP12: route every coder dispatch through that helper in both `_run_linear` and adaptive dispatch/replan, threading the same bounded `max_replans` budget through linear without adding eval-driven repair or reordering normal linear roles; no eval on a rejected attempt, and successful coder still gets Q55 eval (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "linear_admission or adaptive_admission or role_order"` exits 0)
- [ ] STEP13: enforce E137 at `_cmd_workflow` before run/session/artifact setup when coder is requested and `--plan` is absent; keep a defensive `run_workflow` guard for missing, unreadable, outside-workspace, or empty input, plus no-slice input with no determinate structural repair diagnostic or still no slice after repair (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "plan_preflight or no_plan or empty_plan"` exits 0)
- [ ] STEP14: boot the real `run_workflow` → `_cmd_run` → `drive_session` C1 path with only `ProviderChain.request` mocked. Prove a malformed kill directive and a `precheck` near-miss slice heading with zero parsed slices each invoke planner repair before coder; prove a valid candidate physically replaces the exact canonical `--plan` file in place before coder then eval; assert no alternate `.fa` path becomes active and the test's original plan bytes remain unchanged for invalid/stale/failed promotion. Prove no-planner, planner failure, exhausted budget, unreadable/indeterminate validation, and failed candidate promotion end `blocked` without coder/eval. Assert provider-role order, `admission.json`, `verify_baseline.json`, `verification.json`, actual `eval_report.json`, and terminal `flow_state.json`; a linear-mode case proves eval routing stays one-pass (exit: `uv run pytest tests/test_verify_gate_live.py -q -k real_workflow_admission` exits 0)
- [ ] STEP15: run targeted mutation checks for functional producers CT86, CT87, and CT90–CT94 with tests outside mutation roots; removing baseline capture, validator, CLI preflight, precheck, admission writer, scoped candidate writer, or atomic promotion makes its named test fail. Keep mutmut's global `source_paths` unchanged and report all functional-contract × test-path executions and unrelated-failure false-proof risk (exit: each named producer mutation is killed; restore source and confirm clean diff)

**SLICE6 policy/progress (Q55/Q56, 2026-10-08; E193–E194):** eval always runs after a
successful coder stage, then enforce-mode reconciliation applies the gate-as-a-floor precedence
above. The recorded C1 composition-root run passed (12 tests; its nine Q53(c) contract kills all
returned PROVEN), and the combined I02 slice-path run recorded 308 passing tests, with related
feature-flag and plan-reference checks also green. These are prior recorded results, not freshly
reproduced in this planning edit; the existing C1 proves the verify/eval path, **not** Q57
admission repair. SLICE6 now declares 15 functional contracts against one `TESTS:` path, so the
planned full kill pass is O(15 × 1), up from the historical 9 × 1 / 99.72 s measurement; remeasure
rather than assume linear per-contract cost. The Q53(c) unrelated-red-path false-proof risk remains. The 2026-10-09 source audit confirms `verify_plan` is wired after coder but
`validate_kill_directives` has no production caller; there is no admission-history artifact, and
adaptive eval replans can revisit exclusive T0 creation. The shared linear/adaptive admission
path, baseline correction, CLI `--plan` requirement, C1/C3 proof, and the operator-resolved Q58
interface are still pending implementation. I02 is not complete: the latest recorded full-suite run ended in the E174
`WindowsPath` reporter INTERNALERROR near 96% with no final failure summary, full-repo Mypy
still has nine diagnostics outside SLICE6, and live-host E2E has not run. SLICE7's E2E package
and the post-merge host run remain pending. Per E51, only STEP8 is ticked to record the operator's explicit Q58 resolution; all other STEP checkboxes and the `shipped:` field remain operator-owned until I03. This review does not ship I02 or assign a live result.

## SLICE7: Live E2E handoff and operator package
STEPS: prescriptive
DEPS: SLICE6
INTENT: prepare a tracked, independently reviewed I02 live-acceptance package outside the
  harness verdict path. Preserve every producer oracle, give the operator safe copy/paste steps
  for the actual main-only deploy path, and keep local proof separate from live-host judgment.
CONTRACTS:
  CT88 [CONSTRAINT]: every I02 producer maps to a unique, non-duplicated E2E case ID and CT
    owner, with separate local-proof and live-result fields, fixture/run-sheet path, expected
    observable host effect, and evidence location. Recommended live-result vocabulary is
    `NOT RUN | PASS | FAIL | BLOCKED` (confirm in STEP1's schema review); attempts append run ID,
    deployed-main SHA, date, command, artifact paths, observed effect, exit code, and reviewer
    note. Only the operator or an LLM evaluating collected run evidence may assign a live result.
    A shared host scenario may cover multiple producer rows only when
    each unique case row names its own producer and explicitly maps to the shared evidence.
    `e2e/README.md` has no exact duplicate producer/case rows.
  CT89 [CONSTRAINT]: the planner owns the acceptance oracle and operator run sheet; the coder
    appends source-backed implementation seams and labels proposed checks as proposals. An
    independent reviewer completes a manual checklist before fixture/helper implementation;
    material changes to oracle, commands, or fixtures require a new checklist entry. This is a
    human record only, not a hash-bound or machine-enforced approval marker. Coder-created
    fixtures/helpers stay within the reviewed plan. Live cases assert useful persisted
    behavior/artifacts, not only private helper calls.
TESTS: tests/test_e2e_artifact_contract.py, tests/test_skill_conformance.py   (NEW — author artifact test; update skill test)
```verify
uv run pytest tests/test_e2e_artifact_contract.py tests/test_skill_conformance.py -q
uv run ruff check tests/test_e2e_artifact_contract.py tests/test_skill_conformance.py
```
- [ ] STEP1: update `notes/artifact-schema-and-grammar.md` with roadmap lifecycle `IN PROGRESS | DONE`, increment lifecycle `OUTLINED | IN PROGRESS | SHIPPED`, CT lifecycle, `e2e/` ownership/result fields, and the checklist-only review record. Keep generic plan-authoring `DRAFT | READY | BLOCKED` distinct; do not globally delete `READY`. Keep `roadmap.md`'s `active-increment: I01` and I02 `IN PROGRESS`; no live result is assigned in this branch (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k schema` exits 0)
- [ ] STEP2: create `worklogs/planning-topology-and-executable-contracts-loop/e2e/README.md` as the planner-owned case index and `e2e/I02/live-verification.md` as the operator sheet. Index stable case IDs for every old and new producer, CT, local proof, fixture, command block, expected observable, and persisted evidence; keep local status distinct from `NOT RUN | PASS | FAIL | BLOCKED` live status and append each attempt rather than overwriting it (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k "index or status"` exits 0)
- [ ] STEP3: migrate `notes/e2e-live-verification-register.md` without losing any unique producer. Replace the stale CT52 expectation “malformed admission blocks immediately” with bounded planner repair + revalidation and explicit exhausted/indeterminate/no-planner blocks; remove exact duplicate `_producer_absent` and `_classify` rows; retain the Q53(c) attribution caveat and separate local proof from live outcome (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k coverage` exits 0)
- [ ] STEP4: make the run sheet executable from current host facts, not assumed paths. Include copy/paste preflight and stop conditions; confirm current main SHA, `fa status`, active `/sessions/<id>/` workspace, feature-flag config, artifact mount, provider readiness without printing secrets, and the correct `--plan`/run-ID paths. Include explicit `fa update` from the host repo root, then verify deployed SHA and container health before workflow runs. Provide complete copy/paste commands with defined shell variables and required task text (the CLI rejects roles without a shared or per-role task): `fa workflow planner,coder "$TASK" --task-planner "$PLANNER_TASK" --task-coder "$CODER_TASK" --mode linear --max-replans 2 --run-id "$RUN_ID" --workspace "$WORKSPACE" --plan "$PLAN"` for repair; also a bounded blocked case, an adaptive-mode admission case, and the E137 missing-plan preflight. Each command must use a unique run ID and a disposable scratch workspace containing a plan copy at the same relative canonical path, `worklogs/planning-topology-and-executable-contracts-loop/increments/<increment-file>.md`. That copy is the run's exact `--plan` target; the C1/live oracle proves successful repair replaces that path in place, while the tracked source plan is never mutated by a live test. Normal authoring runs pass the actual canonical increment file. State that admission is blocking regardless of verify-gate `observe`/`enforce`; start the verify gate in observe. Record `admission.json`, `verify_baseline.json`, `verification.json`, actual `eval_report.json`, and terminal `flow_state.json` from `/srv/first-agent/state/session-log/<run_id>/`. If `fa update` returns nonzero, capture its printed HEAD/health/test rc and stop to inspect: deployment may already have occurred; do not blindly retry or label the deploy failed. Do not assume host environment variables cross `docker compose exec`; use the deployed config path or explicit approved container configuration. No credentials or raw host logs in Git (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k run_sheet` exits 0)
- [ ] STEP5: add `e2e/I02/implementation-handoffs.md`; coder appends contract/producer IDs, current source call sites, observable artifacts, host prerequisites, candidate commands/fixtures, and limitations. Separate source-backed facts from proposals; coder cannot modify the acceptance oracle or live result (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k handoff` exits 0)
- [ ] STEP6: update `plan-authoring/SKILL.md`, `feature-planning/{SKILL.md,INJECT.md}`, and `tests-writing/{SKILL.md,INJECT.md}` so the planner records E2E obligations before coding, coder provides only an evidence-backed handoff, planner finalizes the run sheet, an independent reviewer uses the manual checklist, and no harness/eval/coder assigns live `PASS`. Preserve generic `READY` semantics where unrelated (exit: `uv run pytest tests/test_skill_conformance.py -q -k e2e` exits 0)
- [ ] STEP7: before any fixture/helper implementation, an independent reviewer completes the checklist in `e2e/I02/live-verification.md`: every producer has a unique case; local-vs-live oracles are distinct; commands use current deployment/workspace paths; no secrets or unbounded/destructive actions; run IDs/artifact paths and no-coder/no-eval blocked outcomes are observable; `fa update` nonzero-test behavior has a safe stop path; observe/enforce ordering is clear. Record reviewer, date, checked boxes, and prose notes only—no hash-bound approval marker or machine gate. Material oracle/command/fixture changes get a fresh manual checklist entry. The local test checks the checklist's shape, never claims that human approval happened (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k review_checklist` exits 0)
- [ ] STEP8: only after STEP7, add planned fixture/helper files under `e2e/I02/fixtures/`. Keep live-host commands out of default pytest discovery; copy fixtures into a unique scratch area in the session workspace, never edit tracked `src/` or canonical worklogs during a live run, and preserve artifacts until evidence is returned (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k fixtures` exits 0)
- [ ] STEP9: update the case index so every new producer has a future live-host case: shared-loop linear and adaptive admission; structural `precheck` and kill-directive repair; E137 CLI/direct-API missing-plan rejection; `admission.json` writer; exact-target candidate writer; atomic in-place promotion to the exact canonical increment path with no alternate active plan; bounded/no-planner/exhausted blocking; and T0 reuse across adaptive replan. Give each producer a distinct stable case ID even when a host scenario supplies shared evidence; a skipped/unobservable row is not PASS (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k producer_coverage` exits 0)
- [ ] STEP10: run local artifact/skill conformance tests; inspect all required producer mappings, duplicates, command syntax, file paths, and exact review-before-fixture ordering. Mark the package locally complete only; do not set live results, change I02 to `SHIPPED`, or claim host readiness before merge/update (exit: `uv run pytest tests/test_e2e_artifact_contract.py tests/test_skill_conformance.py -q` exits 0)

## Increment definition of done

- [ ] Every `CT#` satisfied: each slice's local `verify` block exits 0; the C1/C3 and declared
      producer mutation proofs pass.
- [ ] Pre-deploy readiness is explicit and closed: Q58 is resolved; SLICE6/SLICE7 local proof
      is complete; the independent checklist-only review is recorded; and the E174 full-suite
      comparison below has a test-by-test disposition. Until then, this branch may be reviewed,
      but it is **not declared ready for merge/deploy or host testing**. No unrecorded waiver is
      inferred.
- [ ] Every required I02 producer case in `e2e/README.md` has a reviewed live-host result from
      the deployed `main` image, with deployed SHA, unique run ID, exact command, exit code,
      observed effect, and persisted-artifact references recorded. There is no separate staging:
      merge to `main`, use the normal host `fa update` path, verify the deployed SHA and health,
      then run the sheet. The first workflow verify-gate run is observe mode; admission remains
      blocking independent of that flag; enforce-mode runs begin only after operator review.
      If `fa update` returns nonzero, read its printed HEAD/health/test rc because deployment may
      already have occurred; stop, preserve outputs, and do not blindly retry. The harness/eval
      never assigns live status. I02 is not `SHIPPED` while an explicit E2E result is unproven.
- [ ] The gate and admission both run in the real workflow: `tests/test_verify_gate_live.py`
      calls `run_workflow` with `run_stage_fn=_cmd_run` and reaches `drive_session`; only
      `ProviderChain.request` is mocked. Assert persisted verification and admission artifacts,
      actual eval input/report, terminal route, and observable provider-stage order. Deleting the
      `_run_stage -> verify_plan`, `_validate_plan_admission -> validate_kill_directives`,
      `_validate_plan_admission -> precheck`, CLI `_cmd_workflow -> _require_plan_for_coder`,
      `_record_admission_attempt -> write_admission_record`, scoped
      `_build_tool_builders -> build_scoped_write_file_tool`, or
      `_run_admission_repair -> _promote_validated_plan` producer makes its named oracle fail.
      A test aimed only at `extract_plan_ids` does not count.
- [ ] The admission matrix proves both `linear` and `adaptive` use the shared bounded pre-coder
      loop; no rejected attempt reaches coder/eval; successful repair reaches coder then eval;
      missing/unreadable/empty input, no-slice input without a determinate repair diagnostic or
      after repair exhaustion, planner absence/failure, candidate containment/promotion failure,
      indeterminate validation, and exhausted budget all fail closed. A diagnosable structural
      near-miss is repaired before the final parsed-slice check. Linear keeps one-pass eval
      semantics and requested normal role order.
- [ ] The provenance probe is demonstrated: with it disabled, a mutation of an installed
      module is provably NOT observed and the gate reports `VACUOUS`; with it enabled the same
      run reports `ERROR`. Without this the gate is inverted rather than broken.
- [ ] Every successful coder stage reaches eval even with a blocking post-coder verifier result;
      eval receives that attempt's evidence, terminal reconciliation prevents enforce-mode
      `DONE`/PASS without replacing `eval_report.json`, and pre-coder rejection does not synthesize
      or dispatch eval.
- [ ] T0 is captured once after admission and before first coder, remains write-once through
      coder repair/adaptive replan, and rejects a changed `TESTS:` path map rather than comparing
      mismatched baselines.
- [ ] `VACUOUS`, `PRODUCER_ABSENT` and `REGRESSION` each demonstrated on a constructed slice,
      not merely representable in the enum.
- [ ] The operator's working tree is byte-identical before and after a full gate run (CT64),
      verified with `git status --porcelain` captured on both sides, and `git worktree list`
      shows no leftover entry.
- [ ] Register rows **D1, D3, D4, D5, D8** are ticked in
      [`../notes/deferred-verification-register.md`](../notes/deferred-verification-register.md),
      each citing the test that closed it. D8 was added to the register after this list was
      written and is owned by I02; the standing rule admits no increment that still owns an
      unticked row.
- [ ] Full-suite comparison remains open until closed by evidence. The latest recorded
      `pytest -q` retry ended near 96% in the known E174 `WindowsPath` reporter `INTERNALERROR`
      and emitted no final summary, so visible failures cannot be attributed test-by-test.
      Compare against E192 and rerun with a way to preserve failure identities before closing
      this item; do not fix E19. The comparison is test-by-test, not a raw count, because the
      suite grows as slices land. This is part of the pre-deploy readiness gate above.
- [ ] `plan_ids.py` changed **only** by the position surface Q45-B sanctioned —
      `SliceRecord.start_line`, `SliceRecord.contract_lines`, `PlanIds.contract_line` — with
      `git diff 3c0caad -- src/fa/inner_loop/plan_ids.py` read line by line against that list
      (exit: `uv run pytest tests/test_plan_ids.py -q` exits 0). This item demanded an empty
      diff until Q45-B overruled it: a parser that discards where it found things is
      defective by design, and making the consumer re-read with its own regex breaks Single
      Source of Truth (E170).
- [ ] A scoped mutation run over the changed runtime producers in `src/` and explicitly
      allowed `scripts/` has no non-equivalent survivors; `tests/` stay outside mutation roots
      and mutmut's global `source_paths` remains unchanged (Q54).

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
