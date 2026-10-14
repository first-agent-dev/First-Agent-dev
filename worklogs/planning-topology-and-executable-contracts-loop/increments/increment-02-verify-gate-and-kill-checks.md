---
Increment-ID: RM-planning-topology-I02
Roadmap-ID: RM-planning-topology
status: IN PROGRESS
slices: 8
shipped: —
---

# INCREMENT I02: Executable contracts & the verify gate

**Shippable when:** every coder dispatch is gated by a validated controller-owned `PlanRef`; explicit CLI callers supply `--plan`, while the production chat `invoke_workflow` path lets its initial planner select an existing project increment or submit a controller-validated new-project artifact bundle. Determinate schema/kill-directive diagnostics receive bounded planner repair in the same invocation in both modes; no rejected pre-coder attempt reaches coder or eval. After a successful coder stage, the harness runs each slice's `verify` commands, records real exit codes, and proves every `FUNCTIONAL` contract against production through its declared kill-check. Post-coder verification/eval routing remains governed by Q55/Q56. The 20-slice/≥95% calibration gate is explicitly deferred and is not an I02 shipping condition.

Rationale lives in [`../notes/i02-slice-verification-design.md`](../notes/i02-slice-verification-design.md),
[`../notes/i02-handoff-verify-gate.md`](../notes/i02-handoff-verify-gate.md), and the operator-E2E
ownership/design record [`../notes/e2e-handoff-and-plan-review-design.md`](../notes/e2e-handoff-and-plan-review-design.md).
Do not restate rationale here.

**Current code snapshot (rechecked 2026-10-14; line references are this checkout):**
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
- The production nested caller is `invoke_workflow`: its default roles are `planner,coder,eval`
  (`tools/workflow_tool.py:64, 422-424`), but its schema/context have no plan-path input and its
  handler omits `plan_path` in the `run_workflow` call (`:164-195, :463-484`). CT95 therefore
  cannot require a pre-existing path at workflow entry for every caller. Require a typed,
  controller-validated `PlanRef` before every coder dispatch; allow only the internal
  planner-managed acquisition path to run a planner before that reference exists.
- The current planner writer allowlist is `knowledge/research/` and `.fa/` (`profiles.py:132-146`);
  it cannot create canonical project artifacts, but its `.fa/` prefix currently also covers the
  future admission control-plane subtree. Do not broaden the public allowlist; reserve
  `.fa/admission/` from ordinary planner writes. Planner-managed bootstrap needs a dedicated
  controller-staged bundle submission tool and typed `PlanRef` handoff; Q58 repair needs its own
  exact-candidate writer. These are separate capabilities, not exceptions added to the ordinary
  planner writer.
- The exact-target writer is not wired by `profiles.py` alone: `_run_stage` builds stage kwargs
  (`workflow_controller.py:1008-1039`), `_cmd_run` builds the live registry (`cli.py:2305-2327`),
  `_build_run_tool_registry` delegates to `_build_role_registry` (`cli.py:1794-1804`), and the
  planner registry delegates through `tools/__init__.py:191-221` to `profiles.py:375-427`.
  Thread a typed dispatch kind and exact target through this whole path.
- `resolve_workspace_path` resolves/follows symlinks and checks only workspace containment
  (`tools/base.py:7-17`); `build_write_file_tool` then writes the resolved path
  (`tools/write_file.py:20-23, 56-60`). An in-workspace symlink from a candidate to the canonical
  plan would therefore evade a raw-path-only exact-target check. Reject symlinked path components
  and the leaf, including links whose target remains inside the workspace.
- `load_verify_baseline` reads the stored nodeid map for current slice IDs but does not compare
  stored `test_paths` or reject extra/removed slice IDs (`workflow_controller.py:362-391`). CT86
  requires exact symmetric equality of the stored and current slice→TESTS-path maps before
  comparing any nodeids.
- `PlanDiagnostic.message` can quote an entire offending source line (`plan_ids.py:759-767,
  818-827`; `slice_verification.py:666-675, 732-741`). Do not serialize `.message` into
  `admission.json`; persist an allowlisted, line/rule-only diagnostic projection.
- `_resolve_max_replans` clamps to `MAX_REPLANS_CEILING` but has no caller (`workflow_controller.py:1408-1412`);
  `_cmd_workflow` clamps only the CLI path (`cli.py:1414-1415`), while public `run_workflow`
  passes the value through (`workflow_controller.py:1928-1931`). Normalize at the public controller
  entry so direct callers cannot exceed the shared admission/replan bound.

**Open audit-gap closure map (rechecked 2026-10-14; planned, not closed):**

| Audit gap | Verified open condition | Planned owner and closure oracle |
|---|---|---|
| GAP-01 — empty-plan fail-open | Empty text yields no blocking `precheck` or kill-directive diagnostic; a zero-slice parse is not a usable plan. | SLICE6 CT91/CT95, STEPs 10–16: C1 proves empty/indeterminate input blocks before provider dispatch; only a non-empty determinate structural `FAIL` may enter bounded repair, and the accepted revision has at least one parsed slice. |
| GAP-02 — T0 on eval replan | Adaptive replan preserves `repair_round`, so the coder path can attempt exclusive T0 creation again. | SLICE6 CT86, STEPs 14–16: initial admission repair happens before T0 exists; after the first accepted plan, real workflow proves one baseline is created and reused by later admission/coder/eval-replan stages. A changed per-slice `TESTS:` map blocks as indeterminate. |
| GAP-03 — explicit-plan guard | CLI `--plan` is optional and the public controller has no independent pre-coder admission. | SLICE6 CT90/CT95, STEPs 13 and 16: C2 proves missing CLI `--plan` is rejected before run/session creation; C1 proves the controller requires a valid explicit PlanRef before any provider stage, except for the narrowly authorized `invoke_workflow` planner-acquisition stage (GAP-07). |
| GAP-04 — stale live register | The register still has the obsolete immediate-block expectation and exact duplicate producer/classifier rows. | SLICE7 CT88, STEP3: migrate the normalized unique producer set without loss, replace the CT52 expectation with Q57 repair/revalidation/block behavior, collapse only exact duplicates, and test duplicate-free coverage with local proof distinct from live result. |
| GAP-05 — undelivered live handoff | Design decisions are recorded, but the `e2e/` package, independent checklist entry, and host evidence do not exist. | SLICE7 CT88/CT89, STEPs 1–10: create and locally validate the index, operator sheet, coder handoff, safe main-update run matrix, checklist-only review, and per-producer future cases. Only an operator/LLM with collected deployed-host evidence may assign live status; this plan does not. |
| GAP-06 — D2 precheck ownership drift | D2 still names I03, while the current controller has no `precheck` caller; CT91 is a planned I02 producer, not landed runtime wiring. | SLICE7 STEP3 plus the I02 DoD assign the planned consumer to I02, preserve D2's rule/test/kill oracle, and leave D2 open until C1 proves production wiring; do not tick it from plan text. |
| GAP-07 — nested plan acquisition | `invoke_workflow` defaults to `planner,coder,eval` without a plan path; it cannot work if the controller requires a path before its initial planner runs. | SLICE6 CT95/CT96, STEPs 9–16: distinguish explicit CLI input from planner-managed acquisition; let only the latter run its initial planner before a PlanRef exists; validate a typed existing-plan selection or stage/publish a new-project bundle; require the PlanRef before coder; prove both branches through real C1. |
| GAP-08 — plan-path containment/base | `_cmd_workflow` checks `Path.is_file()` before resolving the selected session workspace (`cli.py:1369-1372, 1432-1433`); relative paths therefore use process CWD, while `WorkflowContext.plan_text()` follows symlinks (`workflow_controller.py:171-183`). | SLICE6 CT90/CT95 and C3: define relative `--plan` as workspace-relative, normalize only after workspace resolution, use no-follow regular-file reads for every PlanRef, and test in-workspace plus escaping symlink components. |
| GAP-09 — controller control-plane writes | The ordinary planner allowlist includes the entire `.fa/` subtree (`profiles.py:132-146, 284-308`), which includes future `.fa/admission/` state/candidates. | SLICE6 CT93/CT96: reserve `.fa/admission/` from the general planner writer; acquisition gets only structured selection/bundle tools and repair gets only its exact candidate writer. Keep the public planner allowlist no broader than today. |
| GAP-10 — direct API replan ceiling | `_resolve_max_replans` is unused; CLI clamps but public `run_workflow` passes the raw caller value into adaptive mode (`workflow_controller.py:1408-1412, 1926-1931`; `cli.py:1414-1415`). | SLICE6 CT74/CT87, STEP12: clamp once at public entry and use one shared counter across admission repair and adaptive eval replans, with a zero-budget oracle. |
| GAP-11 — baseline topology mismatch | `load_verify_baseline` ignores stored TESTS paths and extra/removed slice IDs (`workflow_controller.py:362-391`). | SLICE6 CT86/STEP14: require symmetric equality of slice IDs and normalized per-slice TESTS paths before nodeid comparison; additions/removals/path edits yield indeterminate. |
| GAP-12 — diagnostic disclosure risk | Parser diagnostics can embed complete raw offending lines (`plan_ids.py:759-767, 818-827`; `slice_verification.py:666-675, 732-741`); no admission artifact exists yet. | SLICE6 CT92: write only a versioned, allowlisted diagnostic projection; explicitly prove that source snippets, `.message`, absolute paths, and raw plan bytes are absent. |
| GAP-13 — CLI help drift | `--plan` help says optional (`cli.py:758-767`); `cli_help.py:165-169` retains coder examples without it. | SLICE6 CT90/STEP13: update parser/help/example text for explicit CLI plan mode while preserving the deliberately red E19 test. |
| GAP-14 — PlanRef mutable during provider stage | Coder/implementer has write/edit/bash tools (`profiles.py:117-131`); `SandboxHook` permits general workspace writes by default (`cli.py:1873`, `bash_gate.py:93-96, 180-189`); verification parses the plan before coder and uses that snapshot afterward (`workflow_controller.py:1053-1081, 1093-1104`). | Proposed CT97/STEP15: enforce a real per-stage write boundary for the active PlanRef/control-plane, covering shell/subprocess mutation; keep Q55 eval after successful coder. This is a confirmed capability plus a recommended new invariant; confirm the enforcement mechanism before claiming readiness. |
| GAP-15 — adaptive eval-replan cannot revise canonical plan | `_run_adaptive_replan` dispatches the planner then coder (`workflow_controller.py:1597-1654`), but the production planner can write only `knowledge/research/` and `.fa/` (`profiles.py:132-146`) and controller keeps one `ctx.plan_path` (`workflow_controller.py:132-166, 1907-1924`). | SLICE6 CT93/CT94/CT86 and STEPs 9,12,14,16: route plan-changing adaptive replan through the same Q58 single-target candidate/promotion and admission gate; prove a subsequent coder sees the new PlanRef and T0 remains compatible. |

This index is not a status ledger: it does not tick a CT/STEP, close a gap, or assign a live result. Close each row only through the owning contract's tests and, where required, the operator-owned host evidence.

**Decisions and implementation guardrails (carry forward):**
- `src/fa/inner_loop/slice_verification.py` owns subprocess execution and kill-check behavior;
  keep `plan_ids.py` pure. The kill directive is read from `section()`, never the joined
  contract body. Keep exactly the two existing operators: `neutralise` and `remove-call`.
- `VACUOUS` and `PRODUCER_ABSENT` block with no appeal; kill-check only `FUNCTIONAL` contracts.
  Every kill-check proves that the mutated module is the one imported. A failed provenance probe
  is `ERROR`, never a verdict.
- Preserve I02's explicitly authorized local eight-slice exception (`slices: 8` in this
  increment); do not change I01's global seven-slice limit or turn the precheck ceiling `WARN` into
  a new failure.
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
- E137 is the explicit-input rule for CLI `fa workflow`: if normalized CLI roles contain
  `coder`, `--plan` is required and missing input is rejected before run/session/artifact creation.
  The public controller rule is broader in the right place: no coder dispatch until it holds a
  validated typed `PlanRef`. An explicit-path caller must supply one before any provider stage;
  only `invoke_workflow` may use planner-managed acquisition, and then only its initial planner
  may run before a `PlanRef` exists. Missing/invalid reference, empty input, unreadable input,
  or a zero-slice plan without a determinate repair diagnostic blocks before coder/eval. No
  free-text path extraction or filesystem globbing. If admission repair is needed without a
  configured planner, block without coder/eval.
- `precheck` contributes only determinate `FAIL` diagnostics to repair; `WARN` is recorded but
  does not hold admission. Repair non-empty, diagnosable near-miss structure even when no slice
  parses yet; after revalidation, require at least one parsed slice. Empty input or zero parsed
  slices with no determinate repair diagnostic is indeterminate and blocks. A validator or
  file-read exception is indeterminate and blocks.
- Capture the write-once T0 baseline only after admission accepts the active plan and before the
  first coder. Never key T0 creation only to `repair_round`; later planner/coder rounds reuse the
  same baseline. If a post-coder plan revision changes a slice's `TESTS:` path set, baseline
  comparison is indeterminate and blocks rather than comparing mismatched maps.
- **Q58 — RESOLVED by operator, 2026-10-09:** for an increment plan, the canonical target is the
  exact supplied `--plan` path under that project's `worklogs/<project>/increments/` tree.
  Admission-repair candidates are controller-owned, one fresh path per attempt under
  `.fa/admission/<run_id>/`; the repair planner gets a single-target writer only and never writes
  the active plan or receives a broad `worklogs/` allowlist. After both validators pass, the
  controller promotes the exact candidate bytes back to that same canonical path. A promotion
  lock is a process-shared OS lock keyed by the canonical target (not by run ID); recheck the
  source hash while holding it. Hash/lock protect concurrency only, never human approval.
  Planner-managed first-plan creation is a separate controller-staged project-bundle/no-clobber
  publish protocol; it does not weaken Q58 or broaden the ordinary planner allowlist. A non-increment
  explicit plan may be admitted if already valid, but admission repair blocks rather than promoting
  an unsupported target. E2E uses a disposable workspace copy at the same relative increments
  path, proves same-path replacement, and never edits the tracked source plan.
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
    otherwise it blocks. These are admission outcomes under CT90/CT91/CT95, not post-coder evidence.
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
    coder/eval loop. Resolve/type-check/clamp both `max_repairs` and `max_replans` exactly once at
    public `run_workflow` entry, including direct callers, using their configured ceilings; reject
    bools/strings rather than coercing them. Keep `max_repairs` for the coder/eval repair loop.
    One shared planner counter counts each admission-repair dispatch and each adaptive
    eval-driven planner-replan round as one; initial configured planner/PlanRef-acquisition stages
    are free. Reserve budget before dispatch, including failed attempts. `max_replans=0` admits an
    initially valid plan but blocks if any repair/replan is required. Admission never invokes eval
    while a plan is rejected. Linear remains one-pass for eval-driven outcomes. When eval says
    `complete`, an indeterminate post-coder gate routes `blocked`; non-complete eval routes retain
    Q56 and the bounded repair cap.
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
  CT86 [FUNCTIONAL]: initial PlanRef acquisition/admission repair occurs before T0 exists.
    After the active plan passes admission and before the first `coder` stage, capture T0 from that
    admitted plan's `TESTS:` paths and write `verify_baseline.json` exactly once. Every later
    admission, coder-repair, and eval-driven replan stage loads the same T0; baseline creation is
    not keyed only to `repair_round`. Compare the complete stored and current maps symmetrically:
    the exact slice-ID key sets must match, and each slice's normalized `TESTS:` path set must
    match. Added/removed slices or changed paths are indeterminate; never compare only the
    intersection or ignore stored extra slices.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_stage -> capture_baseline
  CT87 [FUNCTIONAL]: every coder dispatch in initial, linear, adaptive-repair, and adaptive-replan
    flow passes through one shared admission helper before T0 capture or coder dispatch. It uses
    the current controller-owned `PlanRef`, calls `precheck` and `validate_kill_directives`, and
    revalidates the exact candidate bytes after every repair. Any missing, malformed, duplicate,
    or near-miss functional kill directive and any determinate `precheck` `FAIL` is persisted as a
    sanitized per-attempt record and sent to a configured planner repair dispatch. Promote no
    invalid candidate. If determinate diagnostics remain and shared budget remains, keep that
    candidate staging-only and send the updated diagnostic bundle to a fresh planner-repair
    dispatch; do not block merely because one candidate still needs repair. No coder is dispatched
    while any blocker remains and no eval runs for a rejected pre-coder attempt. The same clamped
    `max_replans` budget counts admission repairs and adaptive eval-driven planner-replan rounds
    in both modes; linear's eval outcome remains one-pass. Missing planner, failed/unavailable
    planner, candidate-write/promotion failure, indeterminate validation, or budget exhaustion
    records a final `blocked` route. Once a coder succeeds, normal Q55/Q56 applies. Persist a
    structured `dispatch_kind` so ordinary planning, PlanRef acquisition, and admission repair are
    distinguishable in workflow/session evidence (Q57).
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_validate_plan_admission -> validate_kill_directives
  CT90 [FUNCTIONAL]: a CLI `fa workflow` invocation whose normalized roles contain `coder`
    requires an explicit `--plan` argument (E137). Reject a missing argument before
    `_resolve_workflow_lifecycle` or any run/session/artifact creation; do not require a path at
    `invoke_workflow` entry. Define relative CLI plan paths as relative to the resolved workflow
    workspace, not process CWD. Therefore retain only the argument-presence preflight before
    lifecycle setup; after the actual workspace is known, normalize the supplied path there and
    let CT95 perform no-follow regular-file and containment validation before any provider stage.
    C2 asserts an actionable error, zero session/run artifacts, and zero provider dispatch when
    `--plan` is omitted. Update parser/help and coder examples so they no longer call it optional;
    preserve deliberately red E19. `invoke_workflow` uses planner-managed acquisition (CT96).
    kill: remove-call src/fa/cli.py::_cmd_workflow -> _require_plan_for_coder
  CT91 [FUNCTIONAL]: admission runs `precheck` on the active plan and includes its determinate
    `FAIL` diagnostics in the same bounded repair batch as kill-directive diagnostics; `WARN`
    alone does not block. Revalidate all structural diagnostics on every candidate. An exception
    from reading/parsing/precheck is indeterminate and blocks. Empty input, or a no-slice parse
    without any determinate structural diagnostic, is indeterminate and blocks; a non-empty
    near-miss heading with a reported `FAIL` is repairable before the final parsed-slice check.
    The real composition-root test proves a structural diagnostic reaches planner before coder.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_validate_plan_admission -> precheck
  CT92 [FUNCTIONAL]: create `admission.json` before the first provider stage and append every
    PlanRef-acquisition/revision/admission attempt, sanitized diagnostics, source/candidate/promoted
    hashes, validator result, dispatch kind, and route. Version-1 schema is exact:
    top-level `{schema_version: 1, run_id, status, plan_ref, attempts}` where `schema_version` is
    integer 1, `run_id` matches `^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$`, and `status` is
    `ACQUIRING|ADMITTED|BLOCKED`; `plan_ref` is null or
    `{workspace_relative_path, source_kind, sha256}` with `source_kind` in
    `EXPLICIT|EXISTING_SELECTION|BOOTSTRAP` and lowercase 64-hex SHA-256. The stored path is a
    normalized workspace-relative POSIX path (never absolute, `.`/`..`, or a symlink path).
    Each attempt is exactly `{attempt, dispatch_kind, validation, diagnostics, source_sha256,
    candidate_sha256, promoted_sha256, route}`; `attempt` is a contiguous positive integer,
    `dispatch_kind` is `ACQUISITION|ADMISSION_REPAIR|EVAL_REPLAN`, `validation` is
    `PASS|DIAGNOSTICS|INDETERMINATE`, nullable hashes are lowercase 64-hex, and `route` is
    `RETRY|ADMITTED|BLOCKED`. Each diagnostic has exactly `{validator, rule, severity, line}` plus
    optional `contract_id`: `validator` is one of `precheck|kill-directives|plan-ref|bootstrap|
    promotion|artifact-io`; `severity` is `FAIL|WARN|ERROR`; `line` is a positive JSON integer or
    null (null only when the failure has no source line); and `contract_id`, when present, matches
    `^CT\d+[a-z]?$`. `precheck`/`kill-directives` rules use their owning validators' closed IDs
    (the 12 precheck IDs in D2 and four kill-directive IDs); the other validators use a versioned,
    closed `AdmissionRule` enum declared before implementation (settle its v1 values in Q62).
    Unknown values fail schema validation. Never persist `PlanDiagnostic.message`, source snippets, absolute paths, raw plan
    bytes, credentials, or provider secrets. Schema-check every complete write and fail closed on
    incompatible/corrupt prior data. Serialize read-modify-write
    with an OS process-shared `flock` on a no-follow lock file; atomically replace the artifact,
    private mode, fsync file and parent directory. Every durable append is a barrier before the
    next pre-coder provider stage. On append failure, stop before the next provider dispatch,
    return nonzero, and best-effort record a blocked artifact-write error in `flow_state.json`;
    never claim the admission record persisted. If the final append fails after atomic promotion,
    keep the valid canonical plan and block before coder; do not auto-rollback. No admission write
    after coder may suppress Q55 eval; actual coder/eval dispatch/outcomes stay in workflow/session
    evidence. C1 reads persisted bytes; rejects unknown keys/enums, wrong field types, invalid run IDs and absolute/escaping paths; and injects failures before retry and after promotion.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_record_admission_attempt -> write_admission_record
  CT93 [FUNCTIONAL]: a plan-mutating planner dispatch gets a dedicated registry capability,
    not the ordinary planner `fs_write_file`. Thread typed `dispatch_kind` plus a controller-owned
    target from `_run_stage` through `cli.py::_cmd_run -> _build_run_tool_registry ->
    _build_role_registry`, `tools/__init__.py::build_planner_registry`,
    `profiles.py::build_registry_for_role`, and `tools/write_file.py`. Admission repair and an
    adaptive eval-replan may write only the exact fresh candidate for that dispatch; deny the
    active plan, siblings, `..`, absolute paths, symlinked parent/leaf, and in-workspace redirection.
    Anchor no-follow opens to workspace directory descriptors; a raw string allowlist check plus
    `Path.resolve()` is insufficient. The general planner writer must deny reserved
    `.fa/admission/` even though its existing allowlist contains `.fa/`; acquisition stages expose
    only selection/bundle tools, and repair/replan stages expose only the exact candidate tool.
    Do not broaden the ordinary allowlist to `worklogs/`. C3 exercises the real `_cmd_run`
    registry/handler, allows one exact candidate write, and denies all other paths and symlink
    redirections.
    kill: remove-call src/fa/inner_loop/profiles.py::_build_tool_builders -> build_scoped_write_file_tool
  CT94 [FUNCTIONAL]: for any controller-authorized plan revision of a canonical increment
    (admission repair or adaptive eval-replan), create a fresh candidate per planner attempt under
    `.fa/admission/<run_id>/`, seeded from the current admitted plan or the immediately preceding
    rejected draft so retry fixes are not discarded. Snapshot bytes once; strictly decode, hash,
    and validate that exact snapshot. Acquire a process-shared OS lock keyed by the canonical
    workspace-relative target (not run ID); under it, reject symlink/non-regular targets and
    recheck the source SHA-256 captured before dispatch. Stage the exact validated bytes in a
    hidden unique sibling of the canonical increment; retain required file mode, fsync file and
    parent, then atomically replace the same path. Verify promoted bytes hash to the validated
    candidate hash, update the controller-owned PlanRef, and remove staging/temp files. New-project
    bootstrap is a distinct no-clobber staged-directory publication, never replacement of an
    existing project. An explicit valid non-increment plan may be admitted without repair, but
    cannot be promoted outside Q58's increments scope. Invalid drafts remain staging-only and feed
    the next bounded repair; delete scratch drafts on terminal block. Any failure before successful
    replacement leaves original bytes unchanged. `os.replace` is the irreversible commit point:
    after it succeeds, never auto-rollback; if directory fsync, promoted-hash verification, or the
    final admission append fails, preserve the canonical bytes, block before coder, and best-effort
    persist the failure. C1/C3 inject failures both before and after replacement, run two distinct
    run IDs contending for one target (the second must see a stale source hash), and cover
    invalid-first/valid-later retry.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::_run_admission_repair -> _promote_validated_plan
  CT95 [FUNCTIONAL]: before constructing any artifact path, public `run_workflow` strips role
    whitespace without reordering, requires a non-empty list containing only `planner|coder|eval`,
    accepts only `linear|adaptive`, and type-checks/clamps `max_repairs` and `max_replans` exactly
    once (`None` selects the documented default; bools/strings/other non-integers reject; integer
    ranges are `0..MAX_REPAIRS_CEILING` and `0..MAX_REPLANS_CEILING`). Validate `run_id` against
    `^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$` before `workflow_artifact_paths`; direct callers cannot
    reach `fa_session_log_root()/run_id` with `..`, an absolute path, or an invalid ID. Before every
    coder dispatch require a controller-owned typed `PlanRef` and
    re-read it through a no-follow descriptor walk anchored at the resolved workspace root.
    Explicit CLI/library mode requires a workspace-relative-or-absolute target resolving to a
    readable regular non-symlinked file inside that root, strict UTF-8, non-empty bytes, and a
    1 MiB byte cap. Missing, malformed, empty, outside-workspace, symlinked, unreadable, or
    oversized input is indeterminate and blocks before provider dispatch; record a structured
    blocked admission/terminal state without raw plan bytes. In planner-managed mode, permitted
    only through the `invoke_workflow` adapter, the initial planner may run without a PlanRef; it
    must submit a typed existing-plan selection or a validated staged new-project bundle. The
    controller creates the PlanRef/hash; recheck the hash immediately before each coder dispatch.
    Final zero-slice plans block; a non-empty determinate near-miss may enter Q57 repair, but no
    path is inferred from prose or filesystem globbing. Direct coder-only API calls without an
    explicit PlanRef fail closed. C1/C3 prove explicit/managed modes, input/path/run-ID containment,
    and zero coder/eval on rejection.
    kill: remove-call src/fa/inner_loop/workflow_controller.py::run_workflow -> _require_plan_for_coder
  CT96 [FUNCTIONAL]: RECOMMENDED DESIGN — NOT OPERATOR-RATIFIED. Production chat passes task/context
    to `invoke_workflow` using the payload shape to be selected in Q66; it never guesses or supplies
    a PlanRef path. Select the workflow-first
    route before provider dispatch (prefer an explicit workflow-first entrypoint/capability); for
    that route, enforce a router-only chat registry: read/search/context tools plus
    `invoke_workflow`, but no file write/edit, shell, subagent, or Git-mutating capability. This cannot
    rely on prompt compliance or the optional `chat_escalation_gate`, which defaults to false
    (`src/fa/cli.py:1606-1607`, `src/fa/inner_loop/runtime_limits.py:159`). Keep ordinary chat for
    non-workflow tasks and preserve explicit-plan CLI mode. The adapter passes a typed
    `planner_managed` acquisition capability; only the nested initial planner may choose/construct
    a PlanRef before it exists. It must return exactly one closed-schema choice
    (`additionalProperties: false`): either `PlanSelection` with `kind: SELECT_EXISTING` and
    `workspace_relative_path: string`, or `ProjectBootstrapBundle` with
    `kind: BOOTSTRAP_NEW_PROJECT`, `project_slug: string`, `increment_slug: string`,
    `roadmap_body: string`, and `increment_body: string`. Bodies are strict UTF-8 Markdown without
    model-authored frontmatter. Reject duplicate JSON keys/fields; do not accept a free-form
    `files` map, raw ledger entries, or destination. Existing selection must match the canonical
    `worklogs/<project_slug>/increments/increment-<number>-<increment_slug>.md` layout, where
    `<number>` is zero-padded with at least two decimal digits, with normalized workspace-relative
    separators and no symlink components. Require both slugs to match
    `[a-z0-9]+(?:-[a-z0-9]+)*` (≤48 chars), strict UTF-8, ≤1 MiB per generated file and ≤2 MiB
    total, and no traversal, absolute paths, or symlinks.

    Recommended publication is controller-rendered: emit roadmap frontmatter with
    `Roadmap-ID: RM-<project_slug>`, `slug: <project_slug>`, `created: YYYY-MM-DD` from the UTC
    controller clock, `status: IN PROGRESS`, and `active-increment: I01` (omit `supersedes` for a
    new project). Require roadmap body sections `Intent`, `Artifact schema`, `Increments`,
    `Standing decisions`, and `Sources`; its `Increments` table must contain exactly one I01 row
    with status `IN PROGRESS`, while optional later rows use `OUTLINED` and publish no files.
    Generate `ledger.md` with `Ledger-for: RM-<project_slug>`, `type: EVIDENCE`,
    `append-only: true`, `# EVIDENCE ledger — <project_slug>`, and the canonical append-only
    instructions/entry-format section, ending before any entry; model authors no initial entries.
    Generate I01 frontmatter with `Increment-ID: RM-<project_slug>-I01`, the matching
    `Roadmap-ID`, `status: IN PROGRESS`, and `slices` derived from the parsed increment body;
    use only increment statuses `OUTLINED|IN PROGRESS|SHIPPED` (never `READY`). Validate that body
    with the shared CT91/CT95 precheck and kill-directive admission and require
    at least one slice before publication. Each
    complete rendered artifact remains within the byte caps. The artifact schema defines roadmap
    and ledger grammar, but there is no production roadmap/ledger parser and `parse_ledger` is I04
    work. If the operator instead chooses model-supplied complete roadmap/ledger files, add a
    minimal versioned bootstrap-content validator in I02 before calling them validated; never
    depend on the deferred I04 ledger parser. Use a controller-mediated exact-schema writer with
    no general filesystem path as the only write capability in this acquisition stage.
    Stage with private permissions under `.fa/admission/<run_id>/bootstrap-*`, using workspace-rooted
    no-follow directory descriptors for both staging and `worklogs/`; reject symlinked parents and
    verify `worklogs/<slug>/` is absent. Publish with a supported atomic no-clobber directory rename
    (fail closed if the platform cannot provide it; never overwrite a collision). Treat the rename
    as the publication commit point: if subsequent PlanRef/admission persistence fails, preserve the
    published valid artifacts, record the failure best-effort, and block before coder; do not
    auto-delete or overwrite the project. The controller creates the typed `PlanRef`, source kind,
    and digest only after publication. Existing selection must resolve to an existing regular
    increment under that same canonical project layout. Reserve `.fa/admission/` from the normal
    planner `.fa/` allowlist. Then run shared admission; no PlanRef or blocked admission means no
    coder/eval. Bootstrap is distinct from Q58 repair and never broadens normal planner writes.
    C1 must drive the workflow-first outer chat `drive_session` -> actual `invoke_workflow` handler ->
    nested `run_workflow` -> `_cmd_run` -> planner/coder/eval `drive_session`, mocking only
    `ProviderChain.request`. Assert its workflow-first registry retains `invoke_workflow` but
    excludes `fs_write_file`, `fs_edit_file`, `fs_run_bash`, `fs_spawn_subagent`, and `pr_prepare`,
    while non-workflow chat and Q55/Q56 routing remain unchanged. Assert the exact Q66-approved
    task/context payload is passed to `invoke_workflow` and received by the nested planner, with no
    PlanRef field; fake provider tool calls prove existing-project selection, new-project
    publication, persisted PlanRef/provider
    order, malformed/missing-bundle no-coder blocks, and post-publication admission-write failure
    retaining the valid bundle while dispatching no subsequent provider stage.
    This protocol is a senior recommendation, not an operator decision (Q59/Q60).
    kill: remove-call src/fa/inner_loop/tools/workflow_tool.py::handler -> _run_planner_managed_workflow
  CT97 [FUNCTIONAL]: RECOMMENDED HARDENING — NOT OPERATOR-RATIFIED. A canonical PlanRef is
    controller-owned and may change only through validated controller promotion, never through a
    provider stage. Source audit: the coder/implementer has `fs_write_file`, `fs_edit_file`, and
    `fs_run_bash` (`src/fa/inner_loop/profiles.py:117-131`); `SandboxHook` is in-process middleware and defaults
    to `allow_general_write=True` (`src/fa/inner_loop/hooks/builtin.py:87-104`, registered by
    `src/fa/cli.py:1872-1873`); the bash gate allows general writes by default
    (`src/fa/sandbox/bash_gate.py:93-96, 170-189`); `fs_run_bash` may use a persistent PTY or
    subprocess fallback (`src/fa/inner_loop/tools/run_bash.py:93-149, 152-216, 219-318`). The
    `SandboxHook`'s path-tool set is only `fs_read_file|fs_write_file`
    (`src/fa/inner_loop/hooks/builtin.py:31-36, 132-145`). `fs_write_file` resolves a workspace path,
    checks generic blackboard conflicts, then writes directly (`src/fa/inner_loop/tools/write_file.py:18-58`);
    `fs_edit_file` resolves a workspace path, checks blackboard mutation metadata, then calls
    `path.write_text` (`src/fa/inner_loop/tools/edit_file.py:104-110, 137-155`). Neither has an
    active-PlanRef rule.
    `fs_spawn_subagent` is registered in the baseline (`src/fa/inner_loop/tools/__init__.py:150-151`);
    the hook only classifies its command (`src/fa/inner_loop/hooks/builtin.py:112-131`) and the tool is disabled by a
    default-off flag (`src/fa/inner_loop/tools/spawn_subagent.py:139-154`), which is not a security
    boundary. `_build_run_hook_registry` merely assembles hooks; adding one there alone does not
    prove shell/subprocess isolation. `_run_stage` captures plan IDs before coder and verifies that
    snapshot afterward (`src/fa/inner_loop/workflow_controller.py:1053-1081, 1093-1104`), so the
    current gate can verify stale plan text after a provider mutation.

    Recommended invariant: protect provider-controlled writes at the actual `_cmd_run` stage seam,
    while keeping the trusted workflow controller outside that boundary. Source-confirmed topology:
    `invoke_workflow` synchronously calls `run_workflow` (`src/fa/inner_loop/tools/workflow_tool.py:463-484`), its stage
    callback is `_cmd_run` (`src/fa/cli.py:1687-1706`), and `_cmd_run` reaches `drive_session` (`src/fa/cli.py:2408`);
    a blanket read-only mount around this in-process call stack would also constrain controller
    publication/promotion. For the current topology, apply a PlanRef/inode-aware no-follow guard to
    direct file-tool handlers and a fail-closed OS sandbox to persistent PTY, subprocess fallback,
    and descendants; alternatively, refactor nested orchestration through a trusted controller/worker
    IPC boundary. Either design must deny writes to the active canonical PlanRef and
    `.fa/admission/` through aliases while allowing normal source edits. A read-only bind of one
    pathname or chmod alone is insufficient. Keep candidate/bootstrap submission as narrow
    controller-mediated capabilities and perform canonical promotion outside provider execution. If
    the required sandbox is unavailable, fail closed before coder rather than fall back to the
    current general-write path. Recheck PlanRef bytes/hash immediately
    before and after every provider stage and before post-coder verification; any mismatch is
    indeterminate and cannot use the stale snapshot to produce success. Even on an integrity error
    after a successful coder dispatch, Q55 still requires the real eval stage; reconciliation must
    prevent terminal success.

    C1 drives outer chat `drive_session` -> actual `invoke_workflow` handler -> nested
    `run_workflow` -> `_cmd_run` stage runner. Fake provider calls attempt `fs_write_file`,
    `fs_edit_file`, `fs_run_bash`, a subprocess/alias route, and `fs_spawn_subagent` against a
    disposable active plan. Direct unauthorized writes return denials; the spawn tool is absent or
    its child inherits the same boundary; every attempt leaves PlanRef/control-plane bytes unchanged.
    Ordinary source edits still work, and a valid controller-owned candidate promotion succeeds at
    the exact target with promoted hash equal to the validated candidate hash.
    Q55 eval still runs after successful coder dispatch. The producer kill must remove the boundary
    call at the stage-execution seam, not merely existing hook registration. This recommended
    invariant/mechanism awaits explicit operator acceptance (Q61).
    kill: remove-call src/fa/cli.py::_cmd_run -> run_stage_with_plan_write_boundary
TESTS: tests/test_verify_gate_live.py   (EXISTING — extend; C1/C2/C3 admission proofs are new)
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
- [ ] STEP9: implement the Q58 controller-owned revision channel and CT92 `admission.json`: add the artifact path/schema/writer, per-run append lock, sanitized attempt records, private atomic writes+fsync, exact-target candidate creation under `.fa/admission/<run_id>/`, secure single-target writer wiring through `_run_stage` → `_cmd_run` → role registry → `profiles.py`/`tools/write_file.py`, process-shared target lock, source-hash CAS, validated same-path promotion, and cleanup. Reserve `.fa/admission/` from the existing general planner `.fa/` writer; do not broaden the allowlist. Rejected candidates seed the next fresh candidate so repair progress is preserved; terminal failure cleans drafts. Fail closed on admission-log write failure before the next provider stage; after successful promotion, keep canonical bytes if the final append fails and block before coder (Q58/CT92). Prove exact schema/no source snippets, no lost appends, write-failure barriers, symlink/path attacks, and validated candidate hash equals promoted bytes (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "candidate or admission_artifact"` exits 0)
- [ ] STEP10: implement one controller admission function over the current typed PlanRef. Run `precheck` plus `validate_kill_directives`; record WARN without blocking, combine only determinate FAILs for Q57 repair, and revalidate every exact candidate snapshot. Permit a non-empty structural near-miss to repair even before any slice parses; empty/unreadable/invalid-UTF8/oversized input, validator exceptions, or zero slices without a determinate repair diagnostic is indeterminate; no invalid or zero-slice final plan passes (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "admission or precheck"` exits 0)
- [ ] STEP11: implement the recommended `invoke_workflow` planner-managed PlanRef acquisition (CT96) using the Q66-approved task/context wire payload without adding `plan_path` to the chat tool schema. Select workflow-first mode before provider dispatch and build its router-only registry (read/search/context plus `invoke_workflow`, no direct mutators); preserve ordinary chat and Q55/Q56 routing. Thread a typed capability from `WorkflowInvocationContext` only; the initial planner can select an existing canonical increment or submit the exact new-project bundle. Use dedicated selection/bootstrap tools only, stage under private `.fa/admission/<run_id>/`, enforce schema/size/path limits, and publish new project directories with atomic no-clobber semantics. The controller creates the PlanRef; then shared admission runs. Test both selection and new-project bootstrap through the real outer-chat/nested-workflow C1 path (exit: `uv run pytest tests/test_verify_gate_live.py -q -k planner_managed_acquisition` exits 0)
- [ ] STEP12: route every coder dispatch in initial, linear, adaptive repair, and adaptive eval-replan flow through the shared admission gate before baseline/coder dispatch. Preserve normal role order when already admitted; safety repair is an explicit additional planner dispatch before coder. Thread a single `max_replans` budget across admission-repair dispatches and adaptive eval-driven planner-replan rounds; count every extra dispatch before it starts, including failures. Normalize `max_repairs` and `max_replans` once at public `run_workflow` entry for direct callers; `max_replans=0` admits a valid initial PlanRef but blocks any required repair/replan. Linear remains one-pass for eval outcomes; a rejected pre-coder attempt runs no eval; Q55/Q56 applies after successful coder (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "linear_admission or adaptive_admission or role_order or direct_budget"` exits 0)
- [ ] STEP13: enforce the two explicit-mode boundaries. At `_cmd_workflow`, reject missing `--plan` before run/session creation (CT90); after the selected workspace is resolved, interpret relative paths against that workspace and pass a normalized PlanRef candidate to the controller, never resolve relative to process CWD. At public `run_workflow`, validate roles/mode/run-ID/budget types before artifact-path construction; explicit coder callers need a valid PlanRef before any provider stage. Only the typed `invoke_workflow` adapter may enter planner-managed mode. Migrate the existing SD-C C1 fixture: it currently sets `workspace=REPO_ROOT` but places `plan_path` in `tmp_path`, which CT95 must reject; use an explicit plan contained by the fixture workspace while keeping the real `tests/test_verify_gate_live.py` command accessible. Any repair/promotion fixture instead uses a disposable workspace copy with the increment at the same relative canonical path; never promote over the tracked source. Update parser/help/CLI examples and preserve red E19 (exit: `uv run pytest tests/test_verify_gate_live.py tests/test_cli_ergonomics.py -q -k "plan_preflight or direct_api_plan_guard or plan_help"` exits 0)
- [ ] STEP14: repair T0 lifecycle after admission is wired: all acquisition and repair occur before T0; after the first accepted PlanRef, capture the full slice-ID→normalized-TESTS-path map once before coder. Reuse the same T0 across coder repair and adaptive eval-replan; compare stored/current maps symmetrically, rejecting added/removed slices or changed paths as indeterminate (exit: `uv run pytest tests/test_verify_gate_live.py -q -k baseline` exits 0)
- [ ] STEP15: resolve CT97's recommended PlanRef-integrity boundary before claiming production readiness. Do not blanket-mount the current in-process `_cmd_run` call stack read-only: nested `invoke_workflow` executes the trusted controller in that same stack, so controller promotion would be blocked. Keep the controller outside provider-controlled execution, or refactor nested orchestration through trusted-controller/worker IPC. At the real stage seam, guard `fs_write_file` and `fs_edit_file` by active PlanRef/inode with no-follow operations; sandbox persistent PTY, subprocess fallback, and descendants at the OS boundary; include `fs_spawn_subagent` if exposed or remove it from workflow-stage registries unless its child inherits the boundary. Cover aliases to active PlanRef/`.fa/admission/`; do not rely on the current broad-write hook or the subagent feature flag. Fail closed before coder when the shell/descendant boundary is unavailable; controller candidate/bootstrap capabilities and promotion stay outside provider filesystem access. Check PlanRef hashes immediately before/after each stage and before verification; mismatch is indeterminate and never verifies stale snapshot. Prove ordinary source edits and a valid nested controller promotion still work, and preserve Q55's real eval after a successful coder even when a plan-write attempt is denied or integrity is indeterminate (exit: `uv run pytest tests/test_verify_gate_live.py -q -k plan_write_boundary` exits 0; do not tick until the operator accepts the mechanism and evidence passes)
- [ ] STEP16: prove the full acceptance matrix. Direct C1 boots real `run_workflow` → `_cmd_run` → `drive_session`, mocking only `ProviderChain.request`; nested C1 boots outer chat `drive_session` → `invoke_workflow` → nested run_workflow → `_cmd_run` → planner/coder/eval drive_session, again with only that provider seam mocked. Prove existing selection and bootstrap, linear/adaptive successful admission, invalid-first/valid-later repair, no planner, planner failure, exhausted budget, indeterminate/missing/unreadable/empty/zero-slice inputs, run-ID/path/symlink rejection, stale-hash concurrency, append failure before retry and after promotion, atomic same-path replacement in a disposable workspace, control-plane integrity, T0 reuse, coder→eval, and provider-stage ordering. The existing SD-C C1 plan is contained by its workspace; every repair/promotion case uses a disposable workspace copy at the same relative canonical increment path, and the tracked fixture/source remains byte-identical. Every blocked case proves zero coder/eval and the specified artifact presence/absence (exit: `uv run pytest tests/test_verify_gate_live.py -q -k "real_workflow_admission or planner_managed_acquisition or plan_write_boundary"` exits 0)
- [ ] STEP17: run the full declared `tests/test_verify_gate_live.py` path once for every one of the 18 `FUNCTIONAL` contracts in this slice: CT71, CT72, CT73, CT75, CT76, CT77b, CT77c, CT77, CT86, CT87, CT90, CT91, CT92, CT93, CT94, CT95, CT96, and CT97. Do not replace Q53(c) with `-k` subsets or guessed contract→nodeid mapping. Kill targets include verify_plan, baseline capture, both admission validators, CLI/controller guards, admission writer, scoped candidate writer, promotion, nested PlanRef acquisition, and plan-write boundary; each named producer removal must fail its oracle. Keep mutation roots to `src/` plus explicitly permitted `scripts/`; tests remain outside and mutmut global `source_paths` unchanged. Report all 18 full-path executions, elapsed cost, provenance result, and unrelated-red-path false-proof risk; restore source and confirm clean diff (exit: every named producer mutation is killed)

**SLICE6 policy/progress (Q55/Q56, 2026-10-08; E193–E194; source re-audit 2026-10-14):** eval always runs after a successful coder stage, then enforce-mode reconciliation applies the gate-as-a-floor precedence above. The recorded C1 composition-root run passed (12 tests; its nine Q53(c) contract kills all returned PROVEN), and the combined I02 slice-path run recorded 308 passing tests, with related feature-flag and plan-reference checks also green. These are historical recorded results, not freshly reproduced in this review; the existing C1 proves the verify/eval path, **not** Q57 admission, planner-managed acquisition, or PlanRef integrity. SLICE6 now declares 18 `FUNCTIONAL` contracts against one `TESTS:` path, so the planned full Q53(c) kill pass is O(18 × 1) full-path executions; remeasure versus the historical 9 × 1 / 99.72 s result rather than extrapolating. Preserve the Q53(c) unrelated-red-path false-proof risk and report all contract×path runs.

The 2026-10-14 source re-audit confirms `verify_plan` is wired after coder, but `validate_kill_directives` and `precheck` still have no production caller, `WorkflowArtifactPaths` has no admission artifact, the direct API does not clamp replan/repair budgets or validate `run_id`, and the CLI plan existence check uses the unresolved path before session workspace selection. Planner writes still allow `.fa/` broadly and cannot publish canonical worklogs; coder tools can write/edit/run shell in the workspace while verification uses a pre-coder plan snapshot. The adaptive planner-replan path does not install a new canonical PlanRef. The linear/adaptive admission gate, PlanRef acquisition/bootstrap, schema-checked admission history, secure same-path candidate promotion, exact baseline topology check, explicit CLI/path resolution, PlanRef write boundary, nested C1/C2/C3 proofs, and SLICE7 package remain unimplemented. Q58 is operator-resolved as a transport decision; CT96's `invoke_workflow` acquisition protocol and CT97's OS-level write-boundary mechanism are recommendations, not operator-ratified decisions.

The operator explicitly deferred the 20-slice/≥95% calibration criterion on 2026-10-14. It is **not** an I02 shipping/`SHIPPED` gate and must not be reintroduced as one. I06 is the recommended future owner (Q64 remains open); promotion trigger is before the first I06 calibrated gate-quality/reliability claim or gate-policy change, whichever comes first, with calibration and held-out regression data kept distinct. I02 still requires its existing local proofs, full-suite disposition, manual review, and post-merge main-host E2E; none is newly verified by this planning review. The latest recorded full-suite run ended near 96% in the E174 `WindowsPath` reporter INTERNALERROR without a final summary; preserve the test-by-test comparison and do not fix E19. Full-repo Mypy has nine recorded diagnostics outside SLICE6. Per E51, only STEP8 remains checked to record the operator's explicit Q58 resolution; all other steps and `shipped:` remain unchanged. This review does not ship I02, assign a live result, change the global seven-slice limit, or remove the authorized local `slices: 8` exception.

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
    `NOT RUN | PASS | FAIL | BLOCKED` (confirm in STEP1's schema review, Q63); attempts append run ID,
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
- [ ] STEP3: migrate `notes/e2e-live-verification-register.md` into the case-index model without losing any unique producer: normalize and record the pre-migration producer-key set, then assert that the post-migration unique set is identical; collapse only exact duplicate `_producer_absent` and `_classify` rows. Replace stale CT52 “malformed admission blocks immediately” wording with Q57 bounded repair/revalidation and explicit no-planner, planner-failure, exhausted, and indeterminate blocks. Keep local-proof and live-result fields distinct, retain the Q53(c) attribution caveat, and do not assign live status from local evidence (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k coverage` exits 0)
- [ ] STEP4: after SLICE6 source call sites and local proofs exist, add `e2e/I02/implementation-handoffs.md`. The coder appends CT/producer IDs, verified source call sites and production path, observable artifacts, host prerequisites, candidate command/fixture proposals, local evidence, and limitations. Label source-backed facts separately from proposals; the coder cannot change the acceptance oracle, case ownership, or live result (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k handoff` exits 0)
- [ ] STEP5: after reviewing STEP4's handoff, the planner finalizes `e2e/I02/live-verification.md` from current host facts, not assumed paths. Include copy/paste preflight and stop conditions: confirm current `main` SHA, `fa status`, active `/sessions/<id>/` workspace, feature-flag config, artifact mount, provider readiness without printing secrets, and exact `--plan`/run-ID paths. Only after merge to `main` (there is no staging host), run `fa update` from the host repo root, then verify deployed SHA and container health before workflows. Supply complete commands with defined shell variables and task text (every role requires a shared or per-role task), unique run IDs, and a disposable scratch workspace per scenario. Give the linear repair template explicitly: `fa workflow planner,coder "$TASK" --task-planner "$PLANNER_TASK" --task-coder "$CODER_TASK" --mode linear --max-replans 2 --run-id "$RUN_ID" --workspace "$WORKSPACE" --plan "$PLAN"`; provide corresponding complete commands for: (a) linear repair of a non-empty `precheck` near-miss; (b) adaptive repair of a kill-directive diagnostic; (c) no-planner block; (d) configured-planner exhaustion with `--max-replans 0`; (e) E137 CLI missing-`--plan`; (f) a fixture invoking public `run_workflow` directly inside the deployed application context, bypassing `_cmd_workflow`, for CT95; and (g) adaptive eval-driven replan for T0 reuse; (h) a real workflow-first outer-chat `fa run` that reaches `invoke_workflow` and selects an existing canonical increment; (i) a separate workflow-first outer-chat run that bootstraps a new project with the no-clobber bundle publication; (j) missing/malformed selection or bundle blocked before coder/eval; and (k) a deployed-app-context CT97 integrity probe that uses deterministic provider tool calls to attempt `fs_write_file`, `fs_edit_file`, `fs_run_bash`, subprocess/alias, and `fs_spawn_subagent` mutations of the active plan in a disposable workspace, while proving ordinary source edits and valid controller promotion still work and successful coder reaches eval. Capture actual `invoke_workflow` tool-call evidence; if chat does not invoke it, mark that case BLOCKED, never PASS. Each case has a unique run ID. Successful repair cases use a disposable workspace with a copy at the same relative canonical path `worklogs/planning-topology-and-executable-contracts-loop/increments/<increment-file>.md`; that copy is the exact `--plan` target, and evidence proves validated promotion replaced that path in place while the tracked source stayed byte-identical. Normal authoring workflows continue to use the actual canonical increment path, never a `.fa` candidate. Every rejected workflow case must show no coder/eval dispatch in provider/session evidence; direct-controller rejection records blocked `admission.json` and `flow_state.json` but no T0/verification/eval artifacts; CLI missing-`--plan` additionally creates no run/session artifacts. Record artifacts required for each outcome from `/srv/first-agent/state/session-log/<run_id>/`: blocked workflow cases require admission and terminal state; admitted coder/eval cases also require `verify_baseline.json`, `verification.json`, and the actual `eval_report.json`. Admission blocks regardless of verify-gate `observe`/`enforce`; start gate runs in observe, and do not begin enforce runs until operator review. If `fa update` returns nonzero, capture its printed HEAD/health/test rc and stop to inspect: deployment may already have occurred; do not blindly retry or label the deploy failed. Do not assume host environment variables cross `docker compose exec`; use deployed config or explicit approved container configuration. Check no credentials or raw host logs into Git (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k run_sheet` exits 0)
- [ ] STEP6: update `plan-authoring/SKILL.md`, `feature-planning/{SKILL.md,INJECT.md}`, and `tests-writing/{SKILL.md,INJECT.md}` so the planner records E2E obligations before coding, coder provides only an evidence-backed handoff, planner finalizes the run sheet, an independent reviewer uses the manual checklist, and no harness/eval/coder assigns live `PASS`. Preserve generic `READY` semantics where unrelated (exit: `uv run pytest tests/test_skill_conformance.py -q -k e2e` exits 0)
- [ ] STEP7: before any fixture/helper implementation, an independent reviewer completes the checklist in `e2e/I02/live-verification.md`: every producer has a unique case; local-vs-live oracles are distinct; commands use current deployment/workspace paths; no secrets or unbounded/destructive actions; run IDs/artifact paths and no-coder/no-eval blocked outcomes are observable; `fa update` nonzero-test behavior has a safe stop path; observe/enforce ordering is clear. Record reviewer, date, checked boxes, and prose notes only—no hash-bound approval marker or machine gate. Material oracle/command/fixture changes get a fresh manual checklist entry. The local test checks the checklist's shape, never claims that human approval happened (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k review_checklist` exits 0)
- [ ] STEP8: only after STEP7, add planned fixture/helper files under `e2e/I02/fixtures/`. Keep live-host commands out of default pytest discovery; copy fixtures into a unique scratch area in the session workspace, never edit tracked `src/` or canonical worklogs during a live run, and preserve artifacts until evidence is returned (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k fixtures` exits 0)
- [ ] STEP9: update the case index so every new producer has a distinct future live-host case, including separate CLI CT90 and direct-controller CT95 plan-guard cases (with workspace/symlink containment); CT96 nested-chat acquisition rows for existing-project selection, no-clobber bootstrap, and malformed/missing-selection blocks; CT97 PlanRef integrity rows for `fs_write_file`, `fs_edit_file`, `fs_run_bash`, subprocess/alias, and `fs_spawn_subagent` mutation attempts in a disposable workspace; shared-loop linear/adaptive admission; structural `precheck` and kill-directive repair; `admission.json` writer; exact-target candidate writer; atomic in-place promotion to the exact canonical increment path with no alternate active plan; no-planner and exhausted-budget blocks; and T0 reuse across adaptive replan. Give each producer a stable unique case ID even when a host scenario supplies shared evidence; map each row to its expected artifact presence/absence and a useful observable, and never count a skipped/unobservable row as PASS (exit: `uv run pytest tests/test_e2e_artifact_contract.py -q -k producer_coverage` exits 0)
- [ ] STEP10: run local artifact/skill conformance tests; inspect all required producer mappings, duplicates, command syntax, file paths, and exact review-before-fixture ordering. Mark the package locally complete only; do not set live results, change I02 to `SHIPPED`, or claim host readiness before merge/update (exit: `uv run pytest tests/test_e2e_artifact_contract.py tests/test_skill_conformance.py -q` exits 0)

## Increment definition of done

- [ ] Every `CT#` satisfied: each slice's local `verify` block exits 0; the C1/C2/C3 and declared
      producer mutation proofs pass.
- [ ] Pre-deploy readiness is explicit and closed: Q58 is implemented/proved; CT96's
      planner-managed acquisition and CT97's plan-integrity boundary have recorded operator
      disposition and required local proofs; SLICE6/SLICE7 local proof is complete; the independent
      checklist-only review is recorded; and the E174 full-suite comparison below has a test-by-test
      disposition. The 20-slice/≥95% calibration target is deferred and is not part of this DoD.
      Until readiness is closed, this branch is **not declared ready for merge/deploy or host
      testing**; no unrecorded waiver is inferred.
- [ ] Every required I02 producer case in `e2e/README.md` has a reviewed live-host result from
      the deployed `main` image, with deployed SHA, unique run ID, exact command, exit code,
      observed effect, and persisted-artifact references recorded. There is no separate staging:
      merge to `main`, use the normal host `fa update` path, verify the deployed SHA and health,
      then run the sheet. The first workflow verify-gate run is observe mode; admission remains
      blocking independent of that flag; enforce-mode runs begin only after operator review.
      If `fa update` returns nonzero, read its printed HEAD/health/test rc because deployment may
      already have occurred; stop, preserve outputs, and do not blindly retry. The harness/eval
      never assigns live status. I02 is not `SHIPPED` while an explicit E2E result is unproven.
- [ ] The gate/admission/acquisition run through real compositions in `tests/test_verify_gate_live.py`:
      direct C1 calls `run_workflow` -> `_cmd_run` -> `drive_session`; nested C1 calls outer chat
      `drive_session` -> actual `invoke_workflow` handler -> nested `run_workflow` -> `_cmd_run` ->
      planner/coder/eval `drive_session`. Mock only `ProviderChain.request`. Assert persisted
      `admission.json`/terminal state on controller runs; admitted coder/eval paths also have T0,
      verification, actual eval request/report, PlanRef/provider ordering; rejected paths have zero
      coder/eval and required artifact absence. Deleting any declared producer for
      `_run_stage -> verify_plan`, admission `precheck`/kill validation, CLI preflight, direct API
      PlanRef guard, admission writer, scoped candidate/bootstrap writer, same-path promotion,
      nested acquisition handler, or CT97 plan-write boundary makes its named oracle fail, with
      observable denied attempts through each of `fs_write_file`, `fs_edit_file`, and `fs_run_bash`
      plus a successful ordinary source edit. A test aimed only at `extract_plan_ids` does not count. Q53(c) runs the full declared test path once
      per FUNCTIONAL contract; tests are never mutation roots.
- [ ] The admission matrix proves both `linear` and `adaptive` use the shared bounded pre-coder
      loop; no rejected attempt reaches coder/eval; successful repair reaches coder then eval;
      missing/unreadable/empty input, no-slice input without a determinate repair diagnostic or
      after repair exhaustion, planner absence/failure, candidate containment/promotion failure,
      indeterminate validation, and exhausted budget all fail closed. The actual outer-chat
      `invoke_workflow` path proves existing-project selection and no-clobber new-project bootstrap
      before PlanRef admission; malformed/missing acquisition blocks before coder/eval. CT97
      integrity attempts cover all three mutating provider paths in a disposable workspace, keep
      PlanRef/control-plane bytes unchanged, permit ordinary source edits, and preserve Q55 eval
      after successful coder. Adaptive eval-replan uses Q58 promotion and rechecks the new PlanRef. The CLI C2 proves missing
      `--plan` fails before run/session artifacts; the independent direct-API C1 bypasses the CLI,
      persists a blocked route, and proves zero provider stages. An outside-workspace or symlinked
      plan target is denied by C3. A diagnosable structural near-miss is repaired before the final
      parsed-slice check. Linear keeps one-pass eval semantics and requested normal role order.
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
- [ ] Register rows **D1, D2, D3, D4, D5, D8** are reconciled in
      [`../notes/deferred-verification-register.md`](../notes/deferred-verification-register.md).
      D2's planned production consumer is I02 CT91; it remains OPEN until the real C1 caller and
      kill oracle pass, and must not be ticked by this plan edit. Every required closure cites its
      test. D8 is I02-owned; the standing rule admits no increment that still owns an unticked row.
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
- **The 20-slice calibration corpus and the ≥95% criterion (§6.1).** The operator explicitly
  deferred this on 2026-10-14; it is not an I02 shipping gate. Recommended future owner: I06.
  Promote before I06 makes its first calibrated gate-quality/reliability claim or changes gate
  policy, whichever comes first; define non-overlapping calibration and held-out regression sets.
- **CT10b path-existence rule (Q39).** Lands with the `tests_note` semantics in I03.

## Hand-off to I03 (banked context, not a plan)

- `SliceVerification` is the record the eval stage should read instead of re-deriving
  completion from prose. It already carries real exit codes and per-contract kill-check
  outcomes.
- The judge keeps the questions a command cannot answer: is this a good implementation, did
  it break something adjacent, is the test honest beyond its declared kill-check.
- `steps_mode` is still unread (schema §7 marks it PENDING with I03 as consumer).
