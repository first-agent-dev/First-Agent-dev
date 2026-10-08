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
- `.venv/` is git-ignored (`.gitignore:4`), so it is absent from any copied tree.
- **Deployment (`worklogs/DEPLOYMENT-ANATOMY.md`), which decides every path here.** In
  production FA runs in a container: the harness's own code is baked at
  `/opt/first-agent/src` with its venv at `/opt/fa-venv` (`Dockerfile.fa:89-96`), the repo is
  bind-mounted **read-only** at `/repo` and is *not* used for runtime import, and the code the
  coder edits lives in a per-session workspace clone under `/sessions/<id>/`, passed as
  `run_workflow(workspace=…)`. Therefore **every path in a kill directive is relative to the
  workspace root, never to the harness's own source tree**, and `/repo` being read-only is an
  independent reason the git-worktree sandbox could not have worked.
- **The workspace wins over the baked image by `PYTHONPATH` precedence, and nothing else.**
  `scripts/fa-entrypoint.sh:237` does
  `export PYTHONPATH="${WORKSPACE%/}/src${PYTHONPATH:+:$PYTHONPATH}"`, and
  `docker-compose.fa.yml:220` deliberately withholds it from the proxy so that container runs
  the immutable image. This is the proven idiom the overlay must mirror, not reinvent.
- **The session workspace already arrives with a built `.venv`.** `workspace_bootstrap.py`
  (`check_workspace_ready:691`, `ensure_workspace_ready:730`) prepares it, and the agent is told
  so verbatim in `_READINESS_PROMPT_EXTRA` (`cli.py:165-170`): *"the project venv is at ./.venv —
  run tests with `uv run pytest ...` (or `.venv/bin/pytest`); never reinstall or rebuild the
  environment."* The comment above it records why (`cli.py:160-164`): a session once burned 12 of
  20 turns on `find / -name pytest`. **Consequence: verify commands run verbatim.** The planner
  emits what the agent was told to emit, the env is already correct, and normalising the command
  would make the plan text and the executed fact diverge for no gain.
- **`UV_PROJECT_ENVIRONMENT` is pinned by the bootstrap (`workspace_bootstrap.py:243-259`) but is
  not on the scrubber allowlist** (`tools/bash_env.py:29-50`, which carries `UV_CACHE_DIR` and not
  this). The fix is **not** to widen the allowlist. The allowlist passes ambient state through, so
  inheriting this name would import whatever the parent happened to hold — including a stale pin
  from a *different* session's workspace, which is worse than no pin because `uv run` would then
  silently use another session's venv. It would also widen a security boundary globally, for the
  agent's shell too, to obtain a value the gate can compute exactly.
  **The house pattern is already compute-and-inject**: `run_bash.py:233-236` scrubs, then sets
  `env["PATH"]` to the workspace's `.venv/bin` prepended. The gate does the same for
  `UV_PROJECT_ENVIRONMENT` and `UV_NO_SYNC`. An allowlist is for what you cannot know; a computed
  value is for what you can.
- **`DEFAULT_BASH_TIMEOUT_SECONDS = 30`** (`runtime_limits.py:71`). The planner is told to emit
  `uv run pytest …` (`prompt.py:205-207`), and `uv` is on the image PATH (`Dockerfile.fa:59-67`).
  A real test file, or a `uv run` that first syncs a venv in the session workspace, exceeds 30 s
  easily. A timed-out command is `ERROR`, and `ERROR` blocks — so inheriting the bash default
  would block every slice on the first live run for purely environmental reasons.
- **`--plan` is optional and defaults to `None`** (`cli.py:758-763`). With `plan_path=None`,
  `plan_text()` returns `None` and `extract_plan_ids` cannot identify slices, so there is no
  positive command/contract coverage. SLICE6 now records an explicit missing-plan verification
  error after a successful coder: observe mode leaves routing to eval but persists the error;
  enforce mode routes eval `complete` to `blocked` (CT72). Normal gate runs therefore still pass
  an explicit plan file. The flag's help states the original reason it is never inferred:
  *"guessing the contract is worse than having none."* That argument is against **heuristic
  discovery** (globbing for a likely `.md`), and it stands. Deterministic planner-output capture
  remains a separate proposed scope (E134); I02 does not add that third behavior.
- Artifacts land in `~/.fa/session-log/<run_id>/` as `eval_report.json` and `flow_state.json`
  (`workflow_controller.py:212-219`), reachable on the host under
  `/srv/first-agent/state/session-log/<run_id>/`.
- **`PYTHONPATH` is on the scrubber's allowlist** (`tools/bash_env.py:41`), so commands run
  through `build_scrubbed_env` inherit it. This is why the plain command gate tests the
  coder's edits rather than the baked image — load-bearing, and currently unprotected.
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
- A successful coder stage is **always followed by the real eval stage**, even when verification
  is blocking. Pass that attempt's typed evidence to eval; do not short-circuit or synthesize an
  `EvalReport` in the coder stage.
- Preserve the model-authored `EvalReport` and its negative routing authority. Reconcile only
  after eval: observe mode uses the eval route; enforce mode with a complete eval route sends a
  determinate blocking result to the bounded coder-repair route, and an indeterminate result to
  `blocked`. An eval non-complete route remains authoritative in either case (Q55/Q56).
- Controller reconciliation changes the effective `FlowState` route/status, not the contents or
  provenance of `eval_report.json`. `ERROR` is never `PASS`; a missing or unclassifiable verifier
  result cannot produce `DONE` in enforce mode.
- Q10(a)'s bounded repair budget remains in force, but its synthetic-report mechanism is
  superseded here by always-eval-then-reconcile. Do not add a provenance field to `EvalReport`.

---

## Shipping order — E130 history and current status

The Phase A/Phase B split below records E130's original sequencing and sizing decision. Its
"do not start Phase B" stop condition was later explicitly superseded by the operator in E164;
SLICE2–SLICE5 are now implemented. The Phase A/B distinction remains useful as a risk map, not
as an unfinished prerequisite. D1b/D3 were closed in E147, and SLICE5 STEP5–STEP6 were closed
in E190–E191. The current closure gate is SLICE6's real composition-root proof plus the remaining
verification and operator-owned progress synchronization.

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

## SLICE2: Kill directives — strict parse, loud failure
STEPS: prescriptive
DEPS: —
INTENT: a contract's declared kill-check is read from the slice's raw text and validated
  before the coder starts, so that a missing or malformed directive blocks loudly instead of
  disabling the non-vacuity gate in silence.
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
INTENT: the gate becomes reachable from a real workflow run — the first production consumer of
  `commands_for` — and the composition-root test proves verification, real eval, and terminal
  reconciliation through `run_workflow` → `_cmd_run` → `drive_session` (SD-C).
CONTRACTS:
  CT71 [FUNCTIONAL]: after a `coder` stage returns exit 0, `_run_stage`
    (`workflow_controller.py`) verifies **every slice** the plan declares and attaches a
    `PlanVerification` to its `StageResult`. It is at the shared dispatch choke point, not in
    either pipeline loop, so linear, adaptive, and repair dispatches all reach it.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> verify_plan
  CT72 [FUNCTIONAL]: after the actual eval report is built, controller reconciliation prevents
    an enforce-mode blocking verification result from yielding effective route `complete`,
    terminal status `DONE`, or process exit 0. For eval route `complete`, a determinate block
    routes to `return_to_coder`; an indeterminate result — including a missing plan/verification
    artifact — routes to `blocked`. Observe mode keeps eval routing. Any eval non-complete route
    remains authoritative even when verifier evidence is indeterminate. `eval_report.json`
    remains the model-authored report; only `flow_state.json` records the effective route.
    kill: neutralise src/fa/inner_loop/workflow_controller.py::_effective_controller_route
  CT73 [FUNCTIONAL]: every successful coder stage is followed by one real eval stage, including
    when the caller omits `eval` or supplies it before `coder`. Eval receives the typed
    verification result from that coder attempt. A blocking gate never suppresses eval.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::run_workflow -> _ensure_eval_after_coder
  CT74 [CONSTRAINT]: verification-driven repairs are governed by the existing
    `WorkflowProgress.repair_round` cap; a determinate blocking result cannot start an
    unbounded coder/eval loop. When eval says `complete`, indeterminate gate evidence routes to
    `blocked` and cannot initiate repair; an eval-authored non-complete repair route still follows
    Q56 and the same bounded cap.
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
  CT86 [FUNCTIONAL]: before the first `coder` stage — `progress.repair_round == 0` — the run
    captures the T0 baseline from the plan's existing `TESTS:` paths and writes
    `verify_baseline.json` once. Repair rounds load that same baseline rather than overwriting
    it.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> capture_baseline
TESTS: tests/test_verify_gate_live.py   (NEW — author it)
```verify
uv run pytest tests/test_verify_gate_live.py -q
uv run ruff check src/fa/inner_loop/workflow_controller.py src/fa/feature_flags.py tests/test_verify_gate_live.py
```
- [ ] STEP1: implement/verify `verify_plan(plan_ids, *, root, …) -> PlanVerification`, preserving plan-level and per-slice command ownership (exit: `uv run pytest tests/test_verify_slice.py -q -k verify_plan` exits 0)
- [ ] STEP2: call `verify_plan` from `_run_stage` only after a successful coder stage, capture T0 before that dispatch, and persist the result (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "coder_stage or baseline"` exits 0)
- [ ] STEP3: reconcile the actual eval route with typed verifier evidence through `_effective_controller_route` per Q56; preserve `eval_report.json` (exit: `uv run pytest tests/test_verify_gate_live.py -q -k reconciliation` exits 0)
- [ ] STEP4: make successful coder dispatch always reach eval, pass typed verification evidence, and prove the route matrix plus repair cap (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "role_loops or repair or indeterminate"` exits 0)
- [ ] STEP5: boot the real C1 composition root with only `ProviderChain.request` mocked; assert a verifier false-pass cannot finish DONE (exit: `uv run pytest tests/test_verify_gate_live.py -q -k real_workflow` exits 0)
- [ ] STEP6: assert plan-level and per-slice command attribution and the once-only plan-level command (exit: `uv run pytest tests/test_verify_gate_live.py -q -k real_workflow` exits 0)
- [ ] STEP7: assert eval received the same attempt's typed evidence and the persisted actual eval report remains unmodified (exit: `uv run pytest tests/test_verify_gate_live.py -q -k real_workflow` exits 0)
- [ ] STEP8: prove the write-once baseline is captured before coder and reused across repair rounds (exit: `uv run pytest tests/test_verify_gate_live.py -q -k baseline` exits 0)

**SLICE6 policy/progress (Q55/Q56, 2026-10-08; E193–E194):** eval always runs after a
successful coder stage, then enforce-mode reconciliation applies the gate-as-a-floor precedence
above. The real C1 composition-root test passes (12 tests; its nine Q53(c) contract kills all
return PROVEN). The combined I02 slice-path run passed 308 tests, with related feature-flag and
plan-reference checks also green. I02 is not marked complete: the latest full-suite run ended in
the E174 `WindowsPath` reporter INTERNALERROR near 96% with no final failure summary, full-repo
Mypy still reports nine diagnostics outside SLICE6, and live-host register rows remain planned.
Per E51, the STEP checkboxes and `shipped:` field remain operator-owned until I03; this plan does
not tick or ship itself.

## Increment definition of done

- [ ] Every `CT#` satisfied: each slice's `verify` block exits 0.
- [ ] The gate runs in a real workflow: `tests/test_verify_gate_live.py` calls `run_workflow`
      with `run_stage_fn=_cmd_run`; only `ProviderChain.request` is mocked. The observable
      oracle includes the persisted verification artifact and terminal route, and deleting the
      `_run_stage -> verify_plan` call makes the test fail. A kill-check aimed only at
      `extract_plan_ids` does not count.
- [ ] The provenance probe is demonstrated: with it disabled, a mutation of an installed
      module is provably NOT observed and the gate reports `VACUOUS`; with it enabled the same
      run reports `ERROR`. Without this the gate is inverted rather than broken.
- [ ] Every successful coder stage is shown to reach eval, even with a blocking verifier
      result; the eval request carries that attempt's evidence, and terminal reconciliation
      prevents enforce-mode `DONE`/PASS without replacing `eval_report.json`.
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
- [ ] Full-suite comparison remains open. The latest `pytest -q` retry ended near 96% in the
      known E174 `WindowsPath` reporter `INTERNALERROR` and emitted no final summary, so the
      visible failures cannot be attributed test-by-test. Compare against E192 and rerun with a
      way to preserve failure identities before closing this item; do not fix E19. The
      comparison is test-by-test, not a raw count, because the suite grows as slices land.
- [ ] `plan_ids.py` changed **only** by the position surface Q45-B sanctioned —
      `SliceRecord.start_line`, `SliceRecord.contract_lines`, `PlanIds.contract_line` — with
      `git diff 3c0caad -- src/fa/inner_loop/plan_ids.py` read line by line against that list
      (exit: `uv run pytest tests/test_plan_ids.py -q` exits 0). This item demanded an empty
      diff until Q45-B overruled it: a parser that discards where it found things is
      defective by design, and making the consumer re-read with its own regex breaks Single
      Source of Truth (E170).
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
