---
Increment-ID: RM-planning-topology-I02
Roadmap-ID: RM-planning-topology
status: IN PROGRESS
slices: 7
shipped: —
---

# INCREMENT I02: Executable contracts & the verify gate

**Shippable when:** explicit-plan CLI/library workflows validate a controller-owned PlanRef before
coder, perform bounded Q57 admission repair/Q58 same-path promotion, capture T0 once, run the
slice-scoped command/kill gate after successful coder, and preserve real eval plus Q55/Q56 routing.
Retained local contracts, composition/mutation proofs, honest local/full-suite result records and
plan-versus-diff review satisfy the DoD below **without waiting for foundation I03 or deployed-host E2E**.
E223 moves deployed functional/source-to-behaviour verification, environment/readiness and inherited
baseline acceptance review, broad independent implementation/evidence review, and integrated E2E/
deployment signoff to final I03 SLICE6, explicitly incomplete. No separate broad review or per-case
inherited-baseline acceptance ceremony is an I02 closeout prerequisite.
This is delivery of the scoped local gate, not OS isolation or safe integrated chat→workflow acceptance.

**Scope migration, 2026-10-15 (E200):** this plan ends at SLICE6. Seven actual sections remain:
SLICE1, SLICE2, SLICE2b, SLICE3, SLICE4, SLICE5, SLICE6. The former eight-slice exception is no
longer needed; the global seven-slice ceiling is unchanged. CT96/CT97, managed-acquisition clauses
of CT90/CT92–CT95 and mixed STEP proofs, and all former SLICE7 CT88/CT89 obligations belong to
[foundation I03](increment-03-execution-workspace-foundation.md). Nothing moved is marked delivered.

The [migration bank](../notes/i02-to-i03-scope-migration-2026-10-15.md) identifies every CT/STEP/GAP
owner, preserves the old SLICE7 body and removed DoD, and separates original recommendations
from current directions. Rationale/reuse lives in the
[decision note](../notes/execution-workspace-and-i02-i03-scope-decisions-2026-10-15.md) and
[reuse audit](../notes/execution-foundation-scope-reduction-and-reuse-audit-2026-10-15.md).
Existing gate design: [verification design](../notes/i02-slice-verification-design.md).
Normative retained implementation details: [explicit admission specification](../notes/i02-explicit-admission-spec-2026-10-15.md).
Adversarial findings and source evidence: [review](../notes/i02-i03-adversarial-review-2026-10-15.md).

**Grounding (product source unchanged at d9109f4; 2026-10-15):**
- `_run_stage` already calls `verify_plan` after successful coder; existing direct C1 proves the
  verifier/eval composition, not admission. `precheck`/`validate_kill_directives` have no production
  admission caller. Artifact paths lack `admission.json`; the candidate/promotion channel is absent.
- CLI `--plan` remains optional and its existence check precedes selected-workspace resolution.
  Direct `run_workflow` lacks the required input/run-ID/budget guards. Missing/empty plans must not
  become an empty passing `PlanIds`; a non-empty structural near-miss is repairable under Q57.
- Baseline creation currently depends on `repair_round`; eval replan can attempt a second T0.
  Stored/current slice→TESTS maps need exact symmetric equality, not intersection comparison.
- Ordinary planner writes cover `.fa/`, not canonical worklogs. Exact-target Q58 capability must
  thread through `_run_stage` → `_cmd_run` → role registry builders → profiles/write handler.
  Reserve admission state from ordinary writes; descriptor-rooted no-follow IO is required.
- Current `invoke_workflow` supplies no plan. In reduced I02, unsupported managed acquisition
  must return unavailable before child provider/coder dispatch, with no guessed plan/bootstrap.
- Current local subprocess/PTY fallback is **not** an OS execution boundary. Hash/path checks
  in this plan do not protect against malicious shell descendants or controller-secret reads.
  Host supervision, fail-closed cell routing, private views and process-tree sealing are I03 work.
- Existing JUnit bool projection loses failure/skip/error distinctions. SLICE5 CT66/STEP7 retains
  detailed local classification; supervised job/revision evidence binding is I03.

**Retained implementation guardrails:**
- Keep `plan_ids.py` pure and the Q45-B position surface approved by Q65; no duplicated locator.
- Keep `neutralise`/`remove-call`, Q54 `src/` + explicitly allowed `scripts/`, tests outside
  mutation roots, import provenance, and unchanged mutmut global `source_paths`.
- Q53(c) runs every declared slice TESTS path per FUNCTIONAL contract; no per-contract mapping.
  Genuine unrelated test failures can still weaken attribution; collection/infra errors cannot.
- Admission is blocking independently of observe/enforce. Q57 repair is pre-coder in linear and
  adaptive; linear does not gain adaptive eval semantics. No rejected attempt dispatches eval.
- Q58 canonical same-path replacement remains implemented/proved here. Ordinary planner permissions
  do not expand to worklogs. Bootstrap no-clobber is a distinct I03 obligation.
- No new increment status, safety-mode CLI, fake bootstrap/cell, standalone FastAPI deployment gate,
  calibration corpus or ≥95% gate. Q64 stays I06. No status ticks from this plan revision.

## Shipping order — E130 history and current status

E130/E164 sequencing below is historical. Current closure is the retained SLICE6 explicit-plan
admission/composition contract and this plan's revised local DoD. Former SLICE7/deployed-host
acceptance is an incomplete I03 obligation, not an I02 shipping prerequisite (E200).

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
  CT66 [FUNCTIONAL]: a kill-check is PROVEN only when mutation provenance passed, the current
    harness-issued report records at least one actually executed test failure, and the runner/report
    agree with no collection/setup/runner/timeout/infrastructure error. All executed tests passing
    is VACUOUS. Missing/stale/malformed/contradictory reports, testcase or suite errors, zero executed
    and all-skipped runs are ERROR, never PROVEN. Reuse one detailed JUnit parser with the existing
    baseline-compatible bool projection; do not infer a kill from exit!=0 or a false bool row.
    Preserve slice-level Q53(c): a genuine unrelated test failure can still prove a kill; no
    per-contract nodeid mapping or newly adopted clean-control baseline gate.
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

- [x] STEP7: strengthen `_run_kill_check` and shared JUnit parsing for amended CT66: issue a fresh report per operation; bind it locally to that invocation; distinguish executed failures, skips and testcase errors, checking runner outcome/counters consistently. Preserve existing baseline projection and provenance. Prove timeout/collection/setup/error/zero/all-skipped/stale negatives plus real failure and all-pass cases; rerun CT66's full-path kill without new baseline policy (exit: `uv run pytest tests/test_verify_slice.py tests/test_slice_verification_runner.py -q` exits 0; amended CT66 producer kill is PROVEN)

E204 evidence: [CT66 implementation, actual exits and mutation results](../notes/i02-slice-verification-design.md#6-ct66-implementation-evidence-2026-10-15). Local C0 only; SLICE6 and I03 acceptance remain open.

## SLICE6: Explicit-plan admission and live-path gate composition
STEPS: prescriptive
DEPS: SLICE5
INTENT: validate/repair an explicit PlanRef before coder in either mode; prove the real local
  controller→session→verifier→eval path. Nested acquisition and OS-enforced execution are I03.
CONTRACTS:
  CT71 [FUNCTIONAL]: after successful coder, `_run_stage` calls `verify_plan` for every declared
    slice at the shared stage choke point and attaches typed PlanVerification to StageResult.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> verify_plan
  CT72 [FUNCTIONAL]: after real eval, reconcile enforce-mode verifier evidence as a floor:
    eval complete + determinate block → return_to_coder; complete + indeterminate → blocked;
    no blocked enforce run is DONE/exit 0. Observe preserves eval routing; non-complete eval
    routes keep Q56 precedence. Integrity/missing-evidence failures hard-block both modes after eval.
    Preserve model eval_report; effective route goes to flow_state.
    kill: neutralise src/fa/inner_loop/workflow_controller.py::_effective_controller_route
  CT73 [FUNCTIONAL]: every successful coder is followed by real eval with that attempt's evidence,
    even if eval was omitted/misordered or verification blocks. Pre-coder rejection runs no eval.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::run_workflow -> _ensure_eval_after_coder
  CT74 [CONSTRAINT]: validate/type-check/clamp max_repairs/max_replans once at public entry;
    None uses defaults, bool/string/non-int rejects. Keep configured ceilings, bounded coder repair,
    and one planner counter for admission repairs/adaptive eval replans, reserved before dispatch
    including failures. Initial configured planner is free. Zero budget admits valid input but
    blocks required repair/replan. Linear retains one-pass eval semantics.
  CT75 [FUNCTIONAL]: C1 boots run_workflow→_cmd_run→drive_session, mocking only ProviderChain.request;
    assert actual roles/requests, persisted verification/admission/terminal artifacts, and real eval.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> run_stage_fn
  CT76 [FUNCTIONAL]: C1 proves per-slice command ownership and commands_for(None) exactly once.
    kill: remove-call src/fa/inner_loop/slice_verification.py::verify_plan -> commands_for
  CT77c [FUNCTIONAL]: load observe/enforce from operator feature flags and record it in verification;
    observe is the deployment default, but neither mode makes pre-coder admission advisory.
    kill: neutralise src/fa/inner_loop/slice_verification.py::_gate_mode
  CT77b [FUNCTIONAL]: persist verification beside actual eval_report on every successful coder,
    including blocked attempts: commands, real exits/tails, verdicts/kills/errors/durations.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> write_verification
  CT77 [FUNCTIONAL]: real eval request receives this attempt's typed mode/round/plan/slice/kill/
    regression/error evidence; do not synthesize or overwrite the model-authored eval report.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_eval_evidence_block -> _verification_evidence_lines
  CT86 [FUNCTIONAL]: admission/repair precedes write-once T0 before first coder. Reuse T0 across
    coder repair, repeated configured coders and eval replan, independently of repair_round. Failed
    capture/storage blocks before coder in both modes; never recapture a changed tree. Require symmetric equality of
    complete slice-ID→normalized TESTS-path maps; additions/removals/path edits are indeterminate.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> capture_baseline
  CT87 [FUNCTIONAL]: one shared pre-coder helper calls precheck and validate_kill_directives on
    exact active/candidate bytes in initial/linear/adaptive dispatches. Send sanitized determinate
    FAILs through bounded Q57 planner repair; revalidate every revision, preserving rejected-draft
    progress. Missing/failed planner, write/promotion failure, indeterminate validation or budget
    exhaustion blocks with no coder/eval. Distinguish ordinary planning/repair/replan in evidence.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_validate_plan_admission -> validate_kill_directives
  CT90 [FUNCTIONAL]: CLI roles containing coder require --plan before run/session/artifact creation;
    resolve supplied relative paths against the selected workspace, not process CWD. Update help/
    examples; preserve E19 guards and Q72’s narrow operator-approved repairs. No managed-acquisition exception is delivered in I02.
    kill: remove-call src/fa/cli.py::_cmd_workflow -> _require_plan_for_coder
  CT91 [FUNCTIONAL]: precheck FAIL joins kill diagnostics in Q57 repair; WARN alone does not block.
    Non-empty structural near-miss can repair before a slice parses. Exceptions, empty input or
    zero slices without determinate diagnostics are indeterminate; final zero-slice plans block.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_validate_plan_admission -> precheck
  CT92 [FUNCTIONAL]: create admission.json before first provider stage, append sanitized attempts
    with schema/run ID/PlanRef hashes/dispatch/validation/routes, and schema-check complete writes.
    Use private no-follow process-shared flock, atomic replace, file+directory fsync; each append
    is a pre-provider barrier. No .message/source snippets/raw plan/absolute paths/secrets. On
    write failure stop before next pre-coder provider; best-effort blocked flow_state is not proof
    admission persisted. Failure after promotion preserves canonical bytes, blocks before coder.
    Do not suppress Q55 eval with a later admission write. Freeze Q62 closed per-validator rules
    using the normative explicit-admission spec §3: EXPLICIT_INPUT is distinct from reserved I03
    ACQUISITION; bool is not a JSON integer. Migration bank §4 is historical schema provenance.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_record_admission_attempt -> write_admission_record
  CT93 [FUNCTIONAL]: thread typed dispatch_kind/controller target through stage→CLI→role registry→
    profiles/write handler. Repair/eval-replan gets only its exact fresh candidate writer; reject
    active plan, siblings, absolute/escaping/symlink paths with descriptor-rooted no-follow IO.
    Ordinary planner writer denies .fa/admission/ and active PlanRef; do not broaden worklogs permissions. Selection/
    bootstrap tools are I03, not added here. C3 uses the actual _cmd_run registry/handler.
    kill: remove-call src/fa/inner_loop/profiles.py::_build_tool_builders -> build_scoped_write_file_tool
  CT94 [FUNCTIONAL]: Q58 repair/eval-replan seeds fresh .fa/admission/<run_id>/ candidates from the
    admitted plan/latest rejected draft; strictly decode/hash/validate one exact snapshot. Under
    process-shared canonical-target lock, reject nonregular/symlink/hard-link targets and stale source hash.
    Stage validated bytes in a unique hidden sibling, preserve mode, fsync, replace same canonical
    increment path, directory-fsync/verify promoted hash/update PlanRef/clean temps. Before replace,
    failure leaves original bytes unchanged; after irreversible replace, never rollback: preserve
    bytes and block if verification/fsync/final append fails. Valid explicit non-increment plans
    may admit but cannot promote outside Q58 scope. Bootstrap no-clobber belongs to I03.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_admission_repair -> _promote_validated_plan
  CT95 [FUNCTIONAL]: public entry validates nonempty normalized planner|coder|eval roles, mode, budgets
    and run/context identity before artifact paths. Preserve non-eval order; Q55 deliberately
    relocates/inserts eval after each coder. Reject ordinary planner after coder or duplicate
    ordinary planner; adaptive replan remains bounded. Malformed identity/config returns typed
    input error without artifacts; only safely addressed PlanRef failures create blocked state. For
    coder workflows require explicit controller-owned PlanRef before any provider: readable regular
    nonsymlink file inside workspace via rooted no-follow walk, strict UTF-8, nonempty, ≤1 MiB.
    Missing/invalid/outside/oversized PlanRef with valid request identity blocks with structured
    terminal/admission state unless storage itself fails (nonzero, no false persistence claim). Recheck
    hash before coder; detected post-coder PlanRef mismatch is indeterminate evidence, never stale
    success in either mode, and still reaches Q55 eval using the pinned admitted snapshot. Deadline
    exhaustion records no eval and fails, never fakes a report. This detects mismatch, not OS isolation. Unsupported
    coder-containing invoke_workflow managed acquisition returns unavailable before child provider/coder dispatch (Q70);
    no guessed path, globbing, fake bundle or public context field. C1/C3 proves these limits.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::run_workflow -> _require_plan_for_coder
TESTS: tests/test_verify_gate_live.py   (EXISTING — extend direct explicit-plan C1/C2/C3)
```verify
uv run pytest tests/test_verify_gate_live.py -q
uv run ruff check src/fa/inner_loop/workflow_controller.py src/fa/inner_loop/workflow_artifacts.py src/fa/inner_loop/profiles.py src/fa/inner_loop/tools/write_file.py src/fa/cli.py src/fa/feature_flags.py src/fa/session/manager.py tests/test_verify_gate_live.py
```
- [ ] STEP1: implement/verify `verify_plan(plan_ids, *, root, …) -> PlanVerification`, preserving plan-level and per-slice command ownership (exit: `uv run pytest tests/test_verify_slice.py -q -k verify_plan` exits 0)
- [ ] STEP2: call `verify_plan` from `_run_stage` only after a successful coder stage, capture T0 before that dispatch, and persist the result (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "coder_stage or baseline"` exits 0)
- [ ] STEP3: reconcile the actual eval route with typed verifier evidence through `_effective_controller_route` per Q56; preserve `eval_report.json` (exit: `uv run pytest tests/test_verify_gate_live.py -q -k reconciliation` exits 0)
- [ ] STEP4: make successful coder dispatch always reach eval, pass typed verification evidence, and prove the route matrix plus repair cap (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "role_loops or repair or indeterminate"` exits 0)
- [ ] STEP5: boot the real C1 composition root with only `ProviderChain.request` mocked; assert a verifier false-pass cannot finish DONE (exit: `uv run pytest tests/test_verify_gate_live.py -q -k real_workflow` exits 0)
- [ ] STEP6: assert plan-level and per-slice command attribution and the once-only plan-level command (exit: `uv run pytest tests/test_verify_gate_live.py -q -k real_workflow` exits 0)
- [ ] STEP7: assert eval received the same attempt's typed evidence and the persisted actual eval report remains unmodified (exit: `uv run pytest tests/test_verify_gate_live.py -q -k real_workflow` exits 0)
- [x] STEP8: record the operator-resolved Q58 interface in the open-question/design record: controller-owned candidate, exact-target planner writer, revalidation, then physical replacement of the original canonical increments file at the same `--plan` path. This decision step is complete; runtime implementation and its proofs remain in the following steps (exit: explicit operator decision recorded; no inferred approval)
- [ ] STEP9: implement CT92–CT94 explicit-plan history/candidate/scoped-writer/promotion with private durable IO, canonical-target flock and source-hash CAS; preserve Q58 irreversible failure policy and rejected-draft progress (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "candidate or admission_artifact"` exits 0)
- [ ] STEP10: implement shared exact-byte PlanRef admission with precheck+kill validators, WARN advisory and Q57 determinate repair; prove indeterminate/empty/zero-slice blocks (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "admission or precheck"` exits 0)
- [ ] STEP12: implement spec §§1–2 shared pure request validator/budget normalizer and pre-coder admission; retain non-eval order with explicit Q55 eval relocation, reject unsafe ordinary-planner ordering, preserve linear semantics and shared repair/replan counter (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "linear_admission or adaptive_admission or role_order or direct_budget"` exits 0)
- [ ] STEP13: implement read-only SessionManager.resolve_workflow_workspace; validate plan/task/inject before lifecycle, recheck allocated workspace, and enforce spec §1 failure/evidence classes. Update help without fixing E19. Unsupported coder-containing managed acquisition blocks before child provider; preserve verified non-coder delegation (Q70). Contain the SD-C fixture plan inside its fixture workspace; repair/promotion uses a disposable workspace at the same canonical relative path (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "plan_preflight or direct_api_plan_guard or plan_help or acquisition_unavailable"` exits 0)
- [ ] STEP14: implement spec §5 baseline state independent of counters; capture once after admission, reject capture/storage uncertainty before coder, reuse across repeated coder/repair/replan, and check symmetric slice→TESTS topology equality (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "baseline or t0 or repeated_configured_coders or eval_replan"` exits 0)
- [ ] STEP16: prove direct explicit-plan C1/C2/C3: actual controller→_cmd_run→drive_session with only provider mocked; valid/invalid-first-valid-later admission, no/failed planner, budget/indeterminate/UTF8/size/path/run-ID blocks, actual registry symlink denial, stale source-hash contention, write failure before retry/after promotion, Q58 same-path bytes, T0 reuse, actual eval/evidence and stage ordering. Add negative unsupported invoke_workflow test (zero child provider), not nested success proof. Preserve tracked source bytes. Detected post-coder PlanRef mismatch and persistence failure still reach eval using pinned IDs and cannot succeed in either mode (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "ct91_public or acquisition_unavailable or plan_ref_mismatch"` exits 0)
- [x] STEP17: after Q69 fixture factoring and a completed unmutated whole-path baseline, run the full declared tests/test_verify_gate_live.py path once per retained FUNCTIONAL contract: CT71, CT72, CT73, CT75, CT76, CT77b, CT77c, CT77, CT86, CT87, CT90, CT91, CT92, CT93, CT94, CT95. Report all 16 contract×path runs, cost/provenance and Q53(c) attribution risk; do not replace kills with -k subsets. Keep tests outside mutation roots and restore source (exit: every retained named producer mutation is killed)

**Scope/progress:** STEP IDs 11 and 15 move entirely to I03; mixed STEPs retain the IDs above and
have clause-level successors in the migration bank. STEP8 remains checked only for the historical
operator Q58 decision. STEP17 is now complete at E220: a completed877-pass/no-skip
unmutated baseline preceded all16 normative+2supplemental exact487-case runs; all PROVEN
with fresh native UUIDs, import provenance and unchanged source/status. The whole retained
bank's40 FUNCTIONAL+CT79 also passed actual producer sensitivity, including amended SLICE5
CT66 (110pass5fail). E218's concurrent699/18 and E212's older486 results remain historical,
not substitutes. See [blocked local acceptance/evidence record](../notes/i02-local-acceptance.md).
Q72 dispositions only the two repaired E19 documentation causes. No shipped or overall DoD
status is assigned: actual just check/test remain red on inherited readiness/Go prewarm;
E223 carries environment/inherited-baseline acceptance and broad independent review to I03.
The retained I02 plan-versus-diff review has not started. SLICE6 has **16 FUNCTIONAL** kills,
not18; older9-kill/12-test/308-test records are not current admission proof.
E174’s reporter/no-summary is historical: E220 has actual terminal summaries and exact
baseline/candidate nodeid comparison. Eight recorded configured-Mypy diagnostics are now clean
with individual proposed fixes; E194’s ninth/test_inject_condensates context is not reproduced
by d910 and stays unresolved for I03 final baseline acceptance review. Intentional I02 changes
and replacement-test intent remain subjects of the local plan-versus-diff review.
Neither scope migration nor existing green verifier
proof closes admission, full-suite comparison or review. Nested success/OS integrity/live-host
acceptance are incomplete I03 obligations, not suppressed failures or I02 evidence.

**E223 operator-approved closeout boundary, 2026-10-16:** final I03 SLICE6 owns all four
acceptance obligations listed above; [migration bank §9](../notes/i02-to-i03-scope-migration-2026-10-15.md#9-e223-closeout-acceptance-transfer--2026-10-16)
records their exact successors and unfinished status. This supersedes E222's requirement for
operator-reviewed inherited-baseline dispositions and broad independent review before I02 closure.
Local C1/C2/C3 and producer-sensitivity checks remain I02 requirements, not deployed verification.
No failure is relabeled PASS, no guard is disabled, and no new I02 regression may be hidden by
calling it deferred acceptance. This documentation update does not start the diff review.

## Increment definition of done

- [ ] Every retained CT in the seven sections satisfies its local verify/C1/C2/C3 and declared
      producer-kill oracle. Reprove amended SLICE5 CT66/STEP7; errors/skip-only/stale reports never
      PROVEN. Q53(c) full-path attribution/cost and Q54 mutation restrictions remain.
- [ ] Real direct C1 boots run_workflow→_cmd_run→drive_session with only ProviderChain.request
      mocked; proves explicit admission/repair/promotion/T0/verification/actual eval/terminal route.
      CLI missing --plan creates no run/session artifacts; direct invalid PlanRef creates specified
      blocked evidence but zero provider stages; rejected repair creates no coder/eval/T0 artifacts.
- [ ] Explicit-plan acceptance matrix proves both modes, role ordering, bounds, exact schema/no
      raw diagnostic bytes, no-follow candidate/target paths, source-hash contention, and Q58
      failure points before/after replacement. Deleting each retained producer breaks its oracle;
      all 16 SLICE6 FUNCTIONAL full-path kills are recorded with elapsed/provenance/limitations.
      The spec §6 matrix is complete; every required selector collects tests, no all-skip proof.
      Exact v1 schema checks old and new attempts, concurrent appends and bool-integer rejection.
- [ ] T0 is write-once after admission, survives repair/replan, rejects changed slice→TESTS maps;
      successful coder reaches real eval with pinned attempt evidence, including indeterminate verifier/
      detected PlanRef mismatch. Integrity/storage/missing-evidence failures cannot finish DONE in
      either mode; observe is advisory only for determinate gate judgment. Shared deadline
      exhaustion is explicitly unsuccessful, not a synthesized eval.
- [ ] Unsupported coder-containing managed acquisition is explicitly unavailable before any child provider/coder;
      no fake bootstrap, guessed PlanRef, public context field or unsafe fallback is introduced.
      General planner permissions stay narrow. I02 makes no OS isolation/secret-read protection claim.
- [ ] Demonstrate VACUOUS, PRODUCER_ABSENT, REGRESSION and error negatives on constructed slices;
      prove overlay import provenance (disabled probe exposes VACUOUS; enabled mismatch is ERROR).
      Operator tree/source bytes and git status are unchanged by gate tests; no leftover worktrees.
- [x] Reconcile I02-owned D1/D2/D3/D4-readers/D5/D8 with actual named evidence in deferred register.
      D2 now has the real caller+ordered kill (E220); pending successor coder-brief
      reader is not falsely closed. No register tick is assigned by this plan edit.
- [ ] Finalize `notes/i02-local-acceptance.md` as the local implementation/closeout record:
      code SHA, commands, actual outcomes, local proof and mutation references, limitations and
      plan-versus-diff review result. Preserve usable isolated d9109f4/candidate full-suite manifests,
      terminal summaries and exact failure identity/phase comparisons already recorded. Retain actual
      just test/just check and blocking subgate results; red remains red. Formal environment/readiness
      and inherited baseline/Mypy acceptance review belongs to I03 SLICE6, not a new I02 Go/live-host gate.
- [ ] Complete plan-versus-diff review of actual I02 changes against d9109f4 and this retained plan,
      in this or a new session. Confirm intended local logic, meaningful local tests, replacement-test
      intent, no unintended changes, strict extractor/Q45-B source-position preservation and scoped
      mutation findings. Pure extractor tests pass; no non-equivalent survivor remains in the retained
      scoped runtime mutation audit. Use available d9109f4, not absent 3c0caad or an inferred clean diff.
      Resolve findings and refresh affected local checks/proofs. New I02 defects are not deferred as
      inherited infrastructure. No separate broad independent review required here.
- [ ] Record the four transferred acceptance obligations and their incomplete I03 SLICE6 successors
      consistently in the migration bank, I03 plan/spec and local record; do not mark them VERIFIED
      or fulfilled merely because ownership moved. Close I02 locally only after retained local checks
      and the plan-versus-diff review, with findings resolved and the local closeout record finalized.

After the retained local checks and plan-versus-diff review, I02 may receive existing SHIPPED
status **before I03**. No tick/status is assigned by this documentation change; wait for the
operator's next command before starting that review. SHIPPED means the retained local explicit-plan
gate is implemented and diff-reviewed, **not deployment-validated** or a safe integrated product.
Broad independent implementation/evidence review and all deployed functional/source-to-behaviour,
environment/inherited-baseline, integrated E2E and deployment acceptance remain unfinished I03 work.
Intentional test changes are checked during the local diff review; their final acceptance treatment
is recorded in I03. Existing evidence/results, historical E19 and Q72's narrow repair approval remain
intact; no blanket passing result or hook/test bypass is authorized.

Q59/Q60 exact nested route/bundle and CT97 runtime decisions, Q66 propagation, Q63 final live-result
schema, cell deployment and the former SLICE7 host package are not retained I02 blockers.
Q62's implementation table is supplied in spec §3; historical question status is not silently closed.
Preserve strict parser accessor behavior and extractor-origin IDs; no Q43 leniency adoption is
authorized. Changed accessor semantics still need explicit disposition. Q64 calibration stays I06.

## Out of scope (moved, not dropped)

- Foundation I03 owns CT96/CT97 and managed-acquisition clauses/real nested success, Q66 initial
  context, trusted imports, all project-code cell routing (including readiness), PTY descendants/
  uncertain outcomes, workspace lease/views/fencing/sealing/publication/recovery.
- I03 final group owns former SLICE7 CT88/CT89 and STEPs1–10: producer index/run sheets/fixtures,
  independent manual checklist, skill E2E obligations and reviewed main-host acceptance for I02+I03.
  E223 also explicitly transfers deployed functional/source-to-behaviour verification, environment/
  readiness and inherited baseline acceptance review, broad independent implementation/evidence
  review, and integrated E2E/deployment signoff. All remain incomplete under I03 SLICE6.
- Old I03 loop/tracker/three-level eval, TEST-DEFECT, CT10b/tests_note and VERIFIED L2 conditions
  follow the named deferred successor capability on the roadmap, not foundation I03's number.
- Generated-mutant sweep and nonessential verification-integrity follow-ups remain deferred;
  calibration/≥95% is I06. Do not add CAS/overlay framework, parallel scheduler or advanced privacy.

## Hand-off to I03 (conditional concrete briefs, not delivery)

Use [conditional six-slice foundation plan](increment-03-execution-workspace-foundation.md) and
[migration bank](../notes/i02-to-i03-scope-migration-2026-10-15.md) for exact clause/case ownership.
Keep existing SliceVerification/actual eval evidence facades and strengthened local parser; I03
adds supervised execution/revision binding. Existing FastAPI PTY server is an optional cell-internal
transport seam, **not** the host supervisor and not a standalone I02 shipping requirement.
