# E2E live-host verification register — I02 producers, I03 acceptance owner

**Purpose.** Operator instruction, 2026-10-08: *every producer created by this plan must be
marked for a future end-to-end test, and all of them verified with fixtures on the live host.*
This file is that mark. **E201 owner migration:** final deployed evidence for these I02
producers belongs to foundation I03's final integrated I02+I03 package, not reduced I02's local
SHIPPED prerequisite. All original table rows below remain intact; I03 must preserve the normalized
unique producer set and correct stale oracle wording during case-index implementation.
One row per producer, carrying what the host fixture has to arrange
and what it has to observe — so the e2e suite can be written from this register alone, without
re-deriving any of it from the code.

**Status vocabulary.** `unit` = proven by in-repo tests and a kill-check. `e2e` = proven on the
live host. These historical row labels do not assign current live verdicts. Local scoped I02
completion is distinct from still-incomplete I03 host acceptance; neither implies the other.

**Why in-repo green is not enough here.** Every producer below either spawns a process, reads
an environment the test harness fakes, or depends on a workspace layout that only the deployed
container actually has (`/opt/first-agent/src`, `/opt/fa-venv`, `/sessions/<id>/`,
`workspace_bootstrap`'s prebuilt `.venv`). Those are exactly the conditions a `tmp_path`
fixture cannot reproduce, and exactly where a silent no-op would hide.

---

## Standing fixture requirements (apply to every row)

1. A real session workspace at `/sessions/<id>/` with the bootstrapped `.venv`, **not** a
   `tmp_path` tree — the gate's whole claim is that it verifies the coder's tree.
2. Normal gate runs use a real plan file containing at least one `## SLICE#` section with a
   `verify` fence, passed with `--plan`; nothing infers it. Missing-plan guards are separate
   CT90/CT95 pre-provider cases. CT72 needs an admitted-plan case with genuinely indeterminate
   post-coder evidence, proving actual Q55 eval/reconciliation rather than bypassing admission.
3. Assertions read from the persisted artifacts the operator reads —
   `~/.fa/session-log/<run_id>/{eval_report,flow_state}.json`, host path
   `/srv/first-agent/state/session-log/<run_id>/` — never from in-process objects.
4. Observe-mode first (E132): the first live run must record and not enforce.

---

## SLICE1 — the command runner

| Producer | Unit proof | What the host fixture must arrange | What it must observe | Status |
| :--- | :--- | :--- | :--- | :--- |
| `run_commands` | CT44 kill PROVEN | a slice whose `verify` fence holds one passing and one failing command | both results recorded, in declared order, with the real exit codes | unit |
| `_run_one` | CT44/CT49d | a command that exits non-zero | `outcome=FAIL`, **not** ERROR — the command refused, the harness did not fail | unit |
| `_timeout_result` | CT45 kill PROVEN | a `verify` command that sleeps past the budget | `ERROR`, `exit_code=None`, elapsed seconds recorded; the run continues | unit |
| `_deadline_result` | CT47 | a slice with more commands than the run budget allows | the unreached commands are `ERROR` with `duration_s == 0.0`, never `PASS` | unit |
| `_spawn_failure_result` | CT46, C4-driven | a `verify` command naming a binary absent from the image | `ERROR`, never `FAIL`; the message names the command | unit |
| `_build_env` | CT46/CT49b | a workspace whose `.venv/bin` holds a shim that the image's `/opt/fa-venv` does not | the shim runs — proving workspace-first `PATH`, not image-first | unit |
| `_pin_uv_environment` | CT49e kill PROVEN | a `verify` command of the form `uv run pytest …`, with a stale `UV_PROJECT_ENVIRONMENT` exported in the parent | `uv` resolves the **session's** venv, and no lockfile sync is attempted offline | unit |
| `_workspace_cwd` | CT49c kill PROVEN | a `verify` command that prints `pwd` | the session workspace, not `/opt/first-agent` | unit |
| **`PYTHONPATH` survival** | CT49b kill PROVEN | a workspace copy of a module that also exists in the baked image, differing observably | the **workspace** version is imported. *The highest-value row in this file*: if it fails, the gate passes no matter what the coder wrote | unit |

## SLICE2 — kill directives

| Producer | Unit proof | What the host fixture must arrange | What it must observe | Status |
| :--- | :--- | :--- | :--- | :--- |
| `parse_kill_directives` | CT50 kill PROVEN | a planner-authored plan (model-written, not a fixture) carrying `kill:` lines | the directives are recovered from the artifact the planner actually produced | unit |
| `validate_kill_directives` | CT52 kill PROVEN | a plan with a malformed directive, submitted at admission | the run is **blocked before the coder stage starts** — the scheduling claim CT53 makes and no in-repo test can observe | unit |
| `_near_miss` | CT51 kill PROVEN | a plan with `kill-check:` instead of `kill:` | a `kill-directive-near-miss` reaches the operator's console and the persisted report | unit |
| `_split_dotted` | CT50b (parse half) | a plan naming `Class.method` as a symbol | resolution succeeds; no false `PRODUCER_ABSENT`. **Kill-check deferred**: CT50b names `_resolve_symbol`, which is SLICE3's AST concern and does not exist yet | unit (partial) |

## SLICE4 — the mutation sandbox

| Producer | Unit proof | What the host fixture must arrange | What it must observe | Status |
| :--- | :--- | :--- | :--- | :--- |
| `mutation_overlay` | CT60 kill PROVEN | a kill-check against a real `/sessions/<id>/` workspace, with full `src/` and `scripts/` roots rather than a four-file fixture | only the selected overlay copy changes; both copied roots are removed; `git status --porcelain` in the session clone is unchanged. **Also the first real measurement of copy cost** — 15 ms for this repo's 2.4 MB / 163 files, but a session clone is the number Phase B's budget actually needs | unit |
| `_copy_src` | CT60/CT63 | a workspace whose `tests/` contains the oracle and whose `scripts/` contains a developer producer | `src/` and `scripts/` are the only copied roots; `tests/` is absent, so the mutation cannot reach its judge | unit |
| `_overlay_target` / `_mutation_root` | CT60/CT63 containment kills | planner-authored paths under both roots, with `..`, cross-root paths, root symlinks and per-file symlinks escaping | targets are accepted only beneath their selected source root; escapes raise `OverlayError` and leave workspace files unchanged | unit |
| `_prepend_pythonpath` | CT61 kill PROVEN | a session container where `PYTHONPATH` already carries `<workspace>/src` from `fa-entrypoint.sh:237` | `<overlay>/src` is first and the workspace entry survives behind it; for script targets the overlay parent is also exposed. The in-repo tests supply inherited values by hand; only the container proves the entrypoint really set it | unit |
| `_overlay_env` | CT61 | a kill-check and a plain verify command in the same run, plus a scripts-target subprocess | both keep the same scrubbed environment; scripts pytest loads the bootstrap before collection while the cwd remains the workspace | unit |
| `overlay_pytest_plugin.py::pytest_configure` / `pytest_collection_finish` | CT61/CT62, Q54(b) | a real pytest subprocess with a `scripts/` mutation and workspace-root `scripts` package; also a test path that does not import the target | the imported target's `__file__` is under `<overlay>/scripts`; a missing/wrong module emits the provenance marker and `_run_kill_check` returns `ERROR`, never `PROVEN` | planned |
| `check_kill_directive_ownership.py` | CT83; current increment audit exits 0, fixture oracle 1P, and its scripts-root producer kill is PROVEN through `verify_slice` | a live host plan folder at a moment when a slice has just been ticked and one completed directive is deliberately made unfirable | the exit code is non-zero and the diagnostic names the plan, slice, contract, and symbol; restoring the directive returns the audit to 0 | planned |
| `apply_kill` | CT55/CT57 kills PROVEN | a directive naming a real producer in the session clone, applied to the file as deployed at `/sessions/<id>/src/...` | `targets == 1`, `edits >= 1`, and the returned text still imports inside the overlay | unit |
| `_resolve_targets` | Q47 exactness kill PROVEN (1F) | a plan whose directive is written against a module that was refactored since -- the symbol moved into a class | `targets == 0` -> `PRODUCER_ABSENT`, naming the symbol; no silent match on the same method name elsewhere | unit |
| `_Silence` | CT56 kill PROVEN (9F) | a real producer called several times inside one function in shipped code | every call silenced, `edits` equal to the count a human finds by reading | unit |
| `KillApplication.__post_init__` | kill PROVEN (2F) | nothing -- it is an internal assertion | never fires in a live run; if it does, the bug is in `apply_kill`, not in the plan | unit |
| `DEFAULT_PROBE_TIMEOUT_SECONDS` | Q46(b), kill PROVEN | a session container under real I/O load, with a cold import of the heaviest module a kill-check will target | the probe completes well inside 30 s. If it ever does not, the budget is wrong -- but `ERROR` after 30 s is a diagnosis, where `ERROR` after 600 s is an outage | unit |
| `_assert_overlay_wins` | CT62 producer kill PROVEN; **directive deferred** | the deployed image, where `/opt/first-agent/src` is installed and a session workspace has a `scripts/` package | `PASS` only when the exact module file is inside its selected overlay root (`src/` or `scripts/`); any mismatch is `ERROR`. CT62's own directive names `_run_kill_check`, which arrives in SLICE5 | unit |
| `_run_kill_check` | CT66/CT67/CT82, Q53(c); 8 prior hand-mutants plus all-path truncation mutant killed in SLICE5 | deployed image/session workspace: real `src/` and `scripts/` producers, every path in a slice's `TESTS:`, and `/opt/first-agent/src` installed | one of PROVEN / VACUOUS / PRODUCER_ABSENT / ERROR, gated by exact root-specific provenance. For `scripts/`, the workspace and overlay both contain the package; the real tests must import the mutated target. Every functional contract runs every slice path: O(contracts × paths), and any unrelated failing test can falsely yield PROVEN (accepted Q53(c) risk). Unit tests use a throwaway workspace; live installed-path proof remains necessary | planned |
| `verify_slice` | CT65–CT69, Q53(c); SLICE5 STEP4; SD-C C1 now passes in-repo | `drive_session` boots as the real composition root; only `ProviderChain.request` is mocked. The coder plan has functional contracts and multiple `TESTS:` paths, including a deliberately unrelated red path | the persisted `verification.json` retains per-slice verdicts and contract outcomes; all declared paths run under mutation, including the unrelated red path that demonstrates the accepted attribution risk. Deleting the `verify_slice` call in `verify_plan` makes C1 fail. A deployed-host run remains planned | unit |
| `_compare_baseline` | CT68; green→red, red→red, absent-T0, absent-now and unavailable-report oracles; 9 STEP3 hand-mutants killed across the comparator/classifier | the coder host runs baseline and current `TESTS:` paths with harness-issued `--junitxml` | only T0-green/current-red matching nodeids appear in the regression set; a new nodeid and an absent row do not | planned |
| `pytest_itemcollected` / `fa_pytest_nodeid` | CT68/CT69; real class + parametrized JUnitXML oracle, 2 hand-mutants killed | coder host runs harness-issued `pytest -p fa.inner_loop.junit_nodeid_plugin --junitxml=...` on the deployed workspace | every executed testcase has exactly one property equal to `Item.nodeid`; missing/duplicate property is an unusable report, never a reconstructed id | planned |
| `_producer_absent` | CT67 producer kill; classifier oracle | a real slice whose declared producer target does not exist in the deployed clone | final `PRODUCER_ABSENT`, with contract and target retained in its `KillCheck`; never collapsed into VACUOUS | planned |
| `_classify` | CT65-CT68; STEP3 precedence matrix | a real workflow with command FAIL plus a T0-green/current-red nodeid, and a separate green command with a regression | first case routes as `FAILING`; second as `REGRESSION`; command/kill phase errors route as `ERROR` | planned |
| `_producer_absent` | CT67 producer kill; classifier oracle | a real slice whose declared producer target does not exist in the deployed clone | final `PRODUCER_ABSENT`, with contract and target retained in its `KillCheck`; never collapsed into VACUOUS | planned |
| `_classify` | CT65-CT68; STEP3 precedence matrix | a real workflow with command FAIL plus a T0-green/current-red nodeid, and a separate green command with a regression | first case routes as `FAILING`; second as `REGRESSION`; command/kill phase errors route as `ERROR` | planned |
| `SliceVerdict` | STEP1 gate, `len == 7` | a run that reaches more than one member | the member a human reads matches the member a machine branched on; no synonym invented at the report boundary | unit |
| `KILL_CHECK_VERDICTS` | kill PROVEN (3 members rejected) | nothing -- it is an internal assertion | never fires live; if it does, a caller is minting a per-contract vocabulary the reports do not share | unit |
| `KillCheck.__post_init__` | kill PROVEN (2F) | nothing -- internal assertion | never fires live; a non-PROVEN verdict with an empty `detail` is an alarm no operator can act on | unit |
| `_module_name` | kill PROVEN (5F), 6 parametrised paths | the deployed image, where the module also exists as an installed absolute path | the derived name is the name the probe resolves. A disagreement reads as a probe failure (`ERROR`), never as a pass -- the one way this helper can be wrong is already fail-safe | planned |
| `KILL_CHECK_COMMAND` | used by every `_run_kill_check` oracle (seam patched to this interpreter) | the coder's real uv project at `/sessions/<id>/`, with `UV_PROJECT_ENVIRONMENT` pinned | `uv run pytest` resolves to the workspace venv. **The constant is never exercised verbatim by any unit test** -- the hermetic fixture substitutes it, so the live run is its first real execution | planned |
| `run_commands(env=...)` | kill PROVEN (injected env reaches the subprocess) | a kill-check on the host, where the overlay env differs from `_build_env` by `PYTHONPATH` alone | the subprocess sees the overlay's `PYTHONPATH`, so the kill-check and the verify it judges are the same program (CT61) | planned |

---

## SLICE6 — workflow composition and post-eval gate reconciliation

The in-repo C1 test now reaches `run_workflow` → `_cmd_run` → real `drive_session`; the only
mock is `ProviderChain.request`. Its declared `TESTS:` path runs all nine functional kill-checks
for CT71/72/73/75/76/77b/77c/77/86 and they return `PROVEN`. The first measured C1 run took
99.72 s for 9 contracts × 1 path. Cost remains O(contracts × paths); as Q53(c) accepts, any
unrelated failing test on a path can falsely prove a kill. No contract-to-nodeid mapping is
inferred. The host rows below remain future work: status `unit` means only the in-repo proof
exists; it does not mean live-host e2e is done. The first deployed session still starts in
**observe** mode; switch to enforce only after an operator reviews its persisted artifacts.

| Producer | Unit proof | What the host fixture must arrange | What it must observe | Status |
| :--- | :--- | :--- | :--- | :--- |
| `run_workflow` → `_ensure_eval_after_coder` | CT73 kill `PROVEN`; C1 test omits eval from requested roles | real workspace, `--plan` supplied, requested roles `planner,coder`; begin observe, then repeat in enforce | persisted provider/session evidence shows actual `planner,coder,eval` dispatch in that order; verifier evidence is supplied to eval. Removing the normalizer prevents the eval request and kills the C1 oracle | unit |
| `_run_stage` → `run_stage_fn` → `drive_session` | CT75 kill `PROVEN`; C1 uses real `_cmd_run` | same plan, bootstrapped `.venv`, real stage command; only the in-repo test mocks provider requests | stage artifacts and provider calls exist for planner, coder and eval; no replacement/fake stage result can satisfy the assertion | unit |
| `_run_stage` → `verify_plan` / `verify_slice` | CT71/CT76 kills `PROVEN`; C1 has one plan-level command and two separately attributed slice commands | command in plan-level fence exits 7 after writing a marker; each slice has its own passing verify command | persisted plan command has exit 7; each slice artifact contains only its own command; plan-level marker is written once. Observe does not route; enforce does not end DONE | unit |
| `capture_baseline` / `load_verify_baseline` | CT86 kill `PROVEN`; CT85/86 baseline tests pass | first coder attempt has existing `TESTS:` paths; trigger a bounded repair without changing `run_id` | `verify_baseline.json` predates coder dispatch, remains byte-identical through repair, and its nodeid maps are used on the next attempt | unit |
| `workflow_artifact_paths` / `write_verification` / `_verification_lines` | CT77b kill `PROVEN`; artifact history test passes | first run a workflow in observe and review its artifact; then, in a separate enforce-mode workflow, trigger a bounded coder repair with the mode fixed for that run | each run records its configured mode; the enforce run's `verification.json` appends both attempts/rounds without erasing history, and eval receives only the current attempt's latest evidence block | unit |
| `_verification_evidence_lines` → `_eval_evidence_block` | CT77 kill `PROVEN`; C1 inspects the actual eval request | deliberately fail a plan command; capture the real eval call through provider tracing and read persisted verification/eval artifacts | request includes mode, round, plan command exit, per-slice verdict and kill outcomes; `eval_report.json` is the actual provider-authored report, never a harness replacement | unit |
| `_effective_controller_route` / `_write_terminal_state` / `workflow_exit_code` | CT72 kill `PROVEN`; route matrix, missing-plan and linear composition tests pass | run determinate and indeterminate verifier cases, including a successful coder with no supplied plan; have eval return both `complete` and each non-complete route | determinate + eval complete → `return_to_coder`; indeterminate/missing evidence + eval complete → `blocked`; eval non-complete route is preserved; no blocking enforce result is terminal DONE or exit 0 | unit |
| `load_feature_flags_from_path` / `_gate_mode` | CT77c kill `PROVEN`; call-time HOME/config and mode unit test passes | set `~/.fa/config.yaml` first to observe, review artifacts, then explicitly change to enforce | each run records the resolved mode in `verification.json`; config-read failure defaults to observe and never cold-enforces | unit |
| adaptive repair/replan dispatch helpers (`_finish_adaptive`, `_dispatch_adaptive_round`, `_run_adaptive_repair`, `_run_adaptive_replan`) | adaptive cap/indeterminate-route tests pass | in adaptive mode, use a persistent deterministic failure and a separate eval-authored replan; set finite repair/replan budgets | every coder is followed by eval; determinate gate failures stop at the existing repair cap; indeterminate gate evidence alone does not launch a repair; eval's non-complete replan route is retained | planned |

**Q53(c) cost/risk:** the kill phase is O(functional contracts × slice `TESTS:` paths); an
unrelated red path can falsely make a contract `PROVEN`. No contract-to-nodeid mapping is
inferred. **Q54(b):** the `scripts/` root is narrowly allowlisted beside `src/`; tests stay
outside, and mutmut's global `source_paths` remains src-only.

## Open e2e-only risks, recorded now so they are not rediscovered live

- **Admission timing.** CT53's purity is proven structurally, by walking the functions' AST.
  That proves they *can* run before the coder stage; only a live run proves they *do*.
- **Cost.** Phase B does not start until Phase A yields a measured per-command cost from a
  real run (E130). That measurement has no in-repo proxy.
- **Observe-vs-enforce.** The switch recorded in `verification.json` (E132, CT77c) changes
  nothing a unit test can see; its first real exercise is the live host.

## Amended CT66 — new report producers and planned host cases (2026-10-15)

**PLANNED, not live evidence.** I02 STEP7 supplies C0/parser and C0 real-I/O proof. SLICE6
must first prove the admitted-plan → controller → verifier → eval composition (C1). I03 F
owns deployed C3 acceptance, the independently reviewed fixture package and final artifact schema
(Q63); do not create/run host fixture helpers before that review or infer live completion here.
The pre-existing rows above are historical and unchanged. This section adds the new producer set.

| Producer | Local oracle | Planned host case / fixture | Required deployed observation |
| :--- | :--- | :--- | :--- |
| `_JUnitReport.executed_count` | mixed pass/failure/skip rows, all-skipped and empty subprocess runs | CT66-H01: ordinary failure, pass, mixed skip, all-skip and zero-test variants | real failure → PROVEN; executed all-pass → VACUOUS; zero/all-skip → ERROR; skip never counts as a failure |
| `_JUnitReport.failure_count` | detailed parser distinguishes failure from skip | CT66-H01 plus unrelated genuine failure | only executed failures count; Q53(c) unrelated failure still qualifies without per-contract mapping or a new baseline gate |
| `_junit_property` | missing/empty/duplicate nodeid or duplicate run identity is unusable | CT66-H02: controlled report-boundary omission/duplication in scratch fixture | ERROR with an actionable diagnostic, never a reconstructed nodeid or PROVEN |
| `_junit_testcase` | exact nodeid/run ID, conflicting outcomes, setup/teardown errors | CT66-H03: real setup error, body failure plus teardown error, and collection error plus executed failure | each error dominates any genuine failure and cannot become PROVEN |
| `_junit_counter_error` | per-suite and aggregate count contradictions / invalid structure | CT66-H04: report-boundary counter corruption after a real pytest run | ERROR despite a failure row; all reported counters agree before a report can be accepted |
| `_parse_junit_report` | one detailed parser, malformed/DTD/encoding/duplicate negatives | CT66-H05: missing/malformed report, forbidden declaration and exact previous report replay | ERROR, including when an old report is copied onto the current fresh report path |
| `_kill_check_result` | runner/report agreement, exits 0–5, actual timeout, shell 127 | CT66-H06: timeout, missing command, usage failure, interrupted/internal runner status, and deliberate exit/report disagreement | ERROR; a nonzero shell exit is not kill evidence |
| `pytest_itemcollected` run-ID extension | harness run ID serialized with authoritative nodeid | CT66-H07: two consecutive harness-issued kills; deliberately replay the first report into the second | distinct harness invocation identities and private report locations; replay rejected; temporary report directory cleaned after each operation |

### Safe host execution plan and evidence handoff

1. **Preconditions:** approved I03 fixture package; real deployed session workspace and ready
   venv; admitted explicit PlanRef; current deployed SHA/image recorded; Q63 evidence schema
   ratified. No host execution occurred for this change. Do not substitute this sandbox for
   `/sessions/<id>/` or assume the historically listed image paths still apply.
2. Copy only reviewed fixtures into a unique session-local scratch directory. Use tiny src-layout
   producers, tests outside mutation roots, and both `src/` and `scripts/` cases. Keep PTY and
   mandatory execution authority intact. No tracked production edits, credentials, global debug
   flags, real user files or network-dependent test commands.
3. Run H01's passing/failing controls in **observe** mode first, through the real CLI/workflow,
   not direct private-helper calls. Verify persisted same-attempt typed kill evidence reaches
   eval, without altering the actual eval report. C1 wiring is a prerequisite, not supplied by
   these local helper tests. Repeat relevant negative cases in enforce mode and verify repair
   routing rather than successful completion.
4. H02/H04/H05/H06 use an explicitly reviewed **fixture-only** report/runner fault adapter
   inside the managed job; do not add a production switch that disables validation. Keep that
   adapter separate from the canonical negative parser tests. H03 uses ordinary pytest errors,
   and H07 uses an exact prior report, not fabricated success evidence.
5. Capture run/attempt IDs, deployed revision/image, admitted plan revision, fixture variant,
   selected TESTS paths, runner outcome/exit, persisted verdict/detail and routing outcome under
   the approved run artifact directory. Report paths/run IDs are correlation data, not credentials
   or a claim of hostile-code-proof authenticity. I03 adds independently supervised job/revision
   binding; local report identity does not replace it. Preserve approved evidence before cleanup.
6. Required two-sided verdicts: genuine failure is PROVEN; independent all-pass is VACUOUS;
   each negative above is ERROR, never PROVEN. Repeat the exact CT66 remove-call producer kill
   on the reviewed scratch product build and require an executed test failure. Record every case
   as PASS/FAIL/BLOCKED with actual artifacts; do not relabel missing evidence as PASS.

E204's local CT66 producer kill also exercises the **unpatched** `KILL_CHECK_COMMAND` with
mandatory harness report arguments in this checkout's ready venv. This supersedes the old
row's “never exercised verbatim” local claim, not its deployed-image/workspace risk. It is not
live-host acceptance and leaves the historical row intact.

## SLICE6 request-entry boundary — planned host surface (E205, 2026-10-15)

**Implementation checkpoint, not SLICE6 completion.** CT74/CT95 now share strict pure request
normalization at CLI/direct entry; CLI parses injection before lifecycle allocation. CT90's
workspace-relative explicit-plan guard, admission/repair/promotion, baseline lifecycle and integrated
acceptance remain incomplete. No STEP12/STEP13 or increment-DoD box is closed by this checkpoint.
C0 policy and C2 CLI rejection are local proof classes; C3 is adversarial security testing, not a
synonym for “live host.” The host cases below are planned I03 F acceptance, not executed results.

| Producer | Planned case | Host arrangement and two-sided oracle | Status |
| :--- | :--- | :--- | :--- |
| `_workflow_roles` | REQ-H01 | Real CLI/direct requests with whitespace, omitted/misordered eval, repeated coder; verify non-eval order and actual evaluator insertion. Reject blank/unknown roles, duplicate ordinary planner and planner-after-coder before allocation/provider. Test linear/adaptive separately. | planned |
| `_workflow_budget` | REQ-H02 | Direct raw None/int/bool/string/float plus actual argparse integer inputs. Existing defaults/ceilings apply; real integers clamp, zero remains legal, bool/string/float reject before allocation. Do not pretend a CLI string token remains a string after argparse. | planned |
| `_validate_workflow_run_id` | REQ-H03 | One- and 128-character valid IDs, digit-leading valid ID, forbidden leading dot/traversal/empty/129-character ID, and generated CLI identity. Accepted IDs use the requested namespace; malformed identity creates no addressed run/artifact. | planned |
| `_workflow_tasks` | REQ-H04 | Shared and per-role tasks; coder-omitted eval still needs a usable eval task. Empty/non-string task and missing role task reject before session/run claim; valid per-role-only configuration dispatches normally. | planned |
| `_workflow_injections` | REQ-H05 | Real repeatable --inject parsing and direct resolved overrides. Test valid off/observe/enforce, unknown names/modes, duplicates, missing '=', bad raw types/unhashable values. Invalid explicit configuration cannot allocate a session/run or call a provider. | planned |
| `_validate_workflow_request` / `_WorkflowRequest` | REQ-H06 | Call both shipped public roots with the same matrix, including mismatched/malformed RunContext and a matching control. Assert normalized values actually govern dispatch/budgets; rejected requests return exit 2 before lifecycle/artifact work. Valid requests must continue through eventual admitted workflow, not merely return from the pure helper. | planned |
| `WorkflowRequestError` | REQ-H07 | Inspect direct typed reason and CLI exit/diagnostic, including existing escaped offending-role/allowed-role presentation. No arbitrary budget/task/injection/context bytes in new typed error reasons. CLI presentation is not the closed admission.json vocabulary. | planned |

### Fixture and evidence requirements

- I03 F owns the reviewed host fixture package. Do not add host helper scripts or execute these
  cases before its independent checklist/review. Q63's result schema remains unratified; these
  descriptive case IDs do not silently freeze that schema.
- Record deployed SHA/image, fixture revision, actual CLI argv/API shape, selected workspace,
  requested/generated run ID, mode, exit/reason, provider-stage count/order and request-specific
  session/run/artifact deltas. Use unique reviewed scratch namespaces, no credentials or global
  debug flags, no tracked-source mutation. Concurrent unrelated host activity is not a test delta.
- Run malformed requests in both modes and both entry paths. Observe is not permission to allocate
  or dispatch on invalid configuration. Verify zero provider work and zero request-specific
  allocation, alongside a valid admitted control. Preserve the actual eval report and routing
  evidence when the valid control reaches coder/eval; do not substitute private-helper results.
- **Different failure classes:** malformed request identity/configuration gets exit 2 with no
  allocation. A well-formed direct request with a missing/unusable PlanRef must later produce
  the separately specified BLOCKED admission evidence, not use this no-artifact oracle. That
  PlanRef protocol is still pending; these entry tests do not prove it.
- Supplementary local remove-call kills from `run_workflow` and `_cmd_workflow` to
  `_validate_workflow_request` protect this new wiring. They do not replace CT95's declared
  `run_workflow -> _require_plan_for_coder` kill or any of the 16 full-path SLICE6 runs.
- Exact-byte reader/admission schemas, scoped candidate writer, Q58 fault points, shared planner
  credit, T0/topology, source mismatch/eval integrity and unsupported acquisition each still
  require their own local/adversarial/live cases under the existing register and I03 owner.

### E205 local checkpoint evidence (not host acceptance)

- Python 3.13.16, `uv sync --frozen --extra dev`; repository dependency/profile files unchanged.
- `uv run --frozen pytest tests/test_verify_gate_live.py tests/test_verify_slice.py
  tests/test_slice_verification_runner.py tests/test_workflow_role_allowlist.py -q`:
  **262 passed in 141.48s** on final source/tests. New boundary selection
  `-k 'direct_budget or role_order_request or plan_preflight'`: **89 passed, 12 deselected**.
- **TEST-EDITS:** one import and 89 new parametrized cases appended. All 12 original test
  function ASTs compare equal to clean HEAD `68c0aa6`; no old assertion softened/deleted.
  Negative tests call real public entry with `_cmd_run`, no mocked lifecycle/controller;
  absence of home/state/workspace/run artifacts is the early-stop oracle. These rejected
  requests never reach `drive_session`, so they are not new admitted C1 proof. Existing
  live C1 and its producer-kill table pass in the 262-test run.
- Actual `_run_kill_check` on final source, each `targets=1, edits=1`:
  `run_workflow -> _validate_workflow_request`, selected
  `test_direct_budget_invalid_request_has_no_artifacts_or_dispatch`: **PROVEN**, 1.926s;
  `_cmd_workflow -> _validate_workflow_request`, selected
  `test_plan_preflight_cli_rejects_malformed_request_before_lifecycle`: **PROVEN**, 2.099s.
  These are supplementary boundary kills, not completion of the full 16-contract package.
- Fresh narrowed scratch mutmut sweep of all six entry helpers: **209 selected,
  207 killed, 2 equivalent/unobservable; no other statuses**. Exact current controller
  SHA256: `03db7fef0377c3810eae045788deae79dc05aa9542cdb8de522ca7ccbaf83aa2`.
  Scratch copied exact source/test plus scripts; selectors are the new boundary names above.
  Repository mutation configuration and source suppressions were not changed. Initial sweep
  exposed missing task/unhashable-mode and short-circuited malformed-context coverage;
  add tests, refresh coverage and rerun, rather than label these survivors equivalent.
  Scratch logs/metadata are disposable cache, not required versioned artifacts.
- Equivalence proof 1: `x__workflow_roles__mutmut_47` changes planner index `>` to `>=`.
  Distinct `planner` and `coder` cannot occupy the same list index; validation guarantees
  these are known strings, so equality is impossible and the predicates coincide.
- Equivalence proof 2: `x__validate_workflow_run_id__mutmut_1` changes the private default
  `allow_missing=False` to True. Normalizer always passes the flag explicitly. Sole
  default-using CLI call is after a missing ID has been replaced by a nonempty generated
  string; its non-None branch never observes the default. No reachable public behavior
  changes. These are call-graph proofs, not blanket permission to ignore survivors.
- Ruff (three changed Python files), mypy (same three files), pylint (two production files,
  **10.00/10**) and `git diff --check` pass. No full-repository static/format claim.
- Deadline regression suite: final candidate **9 passed, 2 failed**. Independently extracted
  clean HEAD `68c0aa6` with a separate frozen environment reproduces both failures
  (role-allowlist + deadline baseline: **19 passed, 2 failed**):
  `test_no_deadline_runs_the_full_pipeline`, `test_generous_deadline_runs_the_full_pipeline`.
  Both expect planner/coder while the existing Q55 path inserts eval. **Not waived/fixed**;
  operator-reviewed disposition remains required. This is not the mandatory full-suite
  `d9109f4` versus candidate acceptance comparison, which has not run.
- Pending: PlanRef/admission, bounded Q57 repair/Q58 promotion, explicit shared T0,
  pinned verifier/eval evidence, unsupported managed acquisition, full declared kills,
  full-suite comparison, independent review and operator DoD. I02 remains open.

## SLICE6 workspace / explicit snapshot preflight (E206, 2026-10-15)

**Partial STEP13 / CT90 / CT95 implementation, not admitted-workflow completion.** CLI now
requires a supplied plan for coder, reads it inside the selected workspace before lifecycle,
and checks allocated-workspace agreement before controller dispatch. The new read-only manager
method does not prepare/touch/claim a session. Constructor root creation moved to `_new_session`;
normal lifecycle still provisions private roots. English, Russian/JSON help and five published
examples now describe/provide explicit workspace+plan. No bootstrap or second workspace manager.
Direct API durable BLOCKED admission, validators, Q57/Q58, T0 and pinned attempts are still pending.

### Planned I03 F host cases — all unexecuted

| Producers / changed boundary | Case | Arrangement and observable oracle |
| :--- | :--- | :--- |
| `SessionManager.resolve_workflow_workspace` | PLAN-H01 | New explicit workspace and resumed manifest; process CWD elsewhere with an invalid same-name file. Correct workspace chosen without manifest mtime/DB/run changes during preflight. Unknown/corrupt/inactive/mismatched/missing workspace rejects, no preparation/provider. Fresh generated default needs create/choose guidance; no automatic acquisition. |
| `_require_plan_for_coder` | PLAN-H02 | Omit plan on both modes with coder, plus a non-coder control. CLI rejects before lifecycle allocation. Future direct counterpart must create safely addressed BLOCKED admission/flow; that direct behavior is not delivered here. |
| `_relative_plan_path` | PLAN-H03 | Relative and absolute-inside references yield the same normalized POSIX identity; root/outside/traversal/NUL/unusable workspace rejects. Path inputs are already pathlib-normalized; future persisted/capability string paths need strict schema validation, not inference from pathlib. |
| `_open_plan_component` | PLAN-H04 | Terminal/ancestor/dangling symlink fixtures and replacement races on reviewed scratch targets. No outside bytes consumed; regular-file positive control. Descriptor flags include no-follow, nonblocking and close-on-exec, with directory descriptors used for ancestors. Not an arbitrary-shell containment claim. |
| `_read_plan_bytes` | PLAN-H05 | Exact limit, limit+1, growth after fstat, short reads, nonregular/FIFO and IO/close failures. At most limit+1 bytes consumed, exact bytes preserved, typed failure without provider, owned descriptors released. FIFO completes promptly rather than hanging the fixture. |
| `read_plan_snapshot`, `PlanRef`, `PlanSnapshot` | PLAN-H06 | UTF-8 multibyte and CRLF inputs, invalid/empty text, same-byte absolute/relative controls. Hash/relative identity matches exact read bytes; later source changes do not mutate the snapshot. Frozen records are not admission.json and do not by themselves prove a valid/admitted plan. |
| `PlanRefError` / CLI rejection renderer | PLAN-H07 | Every reference failure yields its static reason/nonzero result without input path/source/exception text. Retain actionable not-found/unreadable guidance; inspect request-specific allocation deltas. |
| `COMMANDS.workflow`, `_WORKFLOW_PLAN_EXAMPLE` / parser help | PLAN-H08 | Shipped English help, Russian help and JSON registry agree; all five examples parse with a selected existing workspace and explicit canonical-relative plan. Missing-plan example is not advertised as a runnable coder workflow. |
| manager constructor / `_new_session`; allocated-workspace check | PLAN-H09 | Construction/resolution on absent roots allocates nothing; normal successful lifecycle still creates private roots. Fault-change fixture manifest between snapshot and allocation: nonzero, zero provider/controller stages even though lifecycle has allocated a run. Do not falsely require zero allocation for this later disagreement. |

Use the standing I03 reviewed fixture/checklist and E205 evidence requirements: unique owned
scratch namespaces, deployed SHA/image/config, actual argv, mode, selected/allocated workspace,
run/session/provider deltas, reason/exit and persisted artifacts where the applicable failure class
requires them. Repeat preflight in observe/enforce and linear/adaptive; observe never waives it.
These IDs are descriptive handoff labels, not ratification of Q63's result schema. No host scripts
or deployed tests were added/run. Actual scoped-writer registry C3 and promotion hard-link/race
proof remain separate pending obligations; a read-only regular hard-link is not publication permission.

### Actual local evidence

- Python 3.13.16, existing frozen dev environment; no dependency or repository mutation-profile change.
- Final command: `uv run --frozen pytest` on `test_verify_gate_live`, `test_verify_slice`,
  `test_slice_verification_runner`, `test_workflow_role_allowlist`, `test_session_lifecycle`,
  `test_session_manifest_guards`, `test_session_workspace_provisioning`, `test_plan_reference`,
  `test_cli_ergonomics`, `test_s8_workflow_controller`, `test_s10b_cli_parity`,
  `test_inject_cli_flag`, `test_s10c_artifact_posture` (all `tests/*.py`), `-q`:
  **619 passed in 234.82s**. Boundary selection `-k 'plan_preflight or plan_help'`:
  **75 passed, 75 deselected**. These are targeted suites, not `just test` full-suite acceptance.
- 49 new cases extend the 101-case live file to 150. All pre-existing function ASTs in that file
  match `1741daf`. Positive selected/resumed CLI controls exercise real factories/lifecycle/session
  with only `ProviderChain.request` mocked. Reader/syscall/close and manifest-switch fault tests are
  supplements with explicitly identified seams, not provider-only admitted C1/security proof.
- **TEST-EDITS:** `tests/test_cli_ergonomics.py::_workflow_args` supplies a disposable canonical-
  relative plan, real tiny test input and existing interpreter; no synthetic baseline/result JSON.
  One generated-ID test uses None instead of now-invalid empty string. Five stale prose assertions
  now pin typed errors; removed-mode test additionally pins the allowed tuple. Stage counts,
  budgets, routing, durable-state/history/quiet-mode assertions and S8 source are unchanged.
  One Namespace-only test now uses tmp_path instead of Path("."); its assertions are unchanged.
  Source audit found exactly that helper and seven declared tests changed, no hidden test deletion.
  Audit caught two owned fixture files temporarily created by the former Path(".") call; exact
  contents were verified and only those files removed. Final 619-test rerun leaves neither file.
- Broad pre-migration CLI run: 33 failed/137 passed. Isolated `git archive 1741daf` with separate
  frozen environment/module-origin check: 6 failed/164 passed on the same five-suite command.
  Six exact identities in `test_cli_ergonomics.py`: `test_workflow_session_manager_uses_one_invocation_run_context`,
  `test_adaptive_mode_requires_coder_and_eval_roles`, `test_repair_mode_is_no_longer_accepted`,
  `test_workflow_invalid_mode_rejected`, `test_workflow_rejects_empty_roles`,
  `test_workflow_requires_task_for_each_role`. All six are corrected fixtures/contract assertions,
  not waived failures. Remaining 27 required the explicit-plan fixture. Migrated five suites:
  **170 passed**. This is a chunk-regression comparison, not the required d9109f4 full baseline.
- Actual final CT90 `remove-call src/fa/cli.py::_cmd_workflow -> _require_plan_for_coder`,
  full `tests/test_verify_gate_live.py` path: **PROVEN**, **1 target / 1 edit**, **36.104s**.
  Real overlay provenance, runner and invocation-bound JUnit checks; no per-contract nodeid mapping.
  Q53(c) slice-wide attribution risk remains. All 16 full-path runs must be repeated/recorded for
  final integrated retained SLICE6 source; this one does not close STEP17.
- Fresh scratch mutmut: **244 selected, 238 killed, 6 equivalent, no other statuses**.
  Includes every function in `plan_admission.py` and only the new manager resolver (58/58 killed).
  Controller/CLI mutation scope is not implied. Scratch pytest selection is the boundary selector
  above. A scratch-only autouse fixture pins mutmut's relative instrumentation paths before real
  test chdir; initial coverage collection failed without it, and produced no mutation proof.
  Production code/tests remain exact copies, with no suppressions or source/profile exclusions.
  Plan module SHA256 `8aaac0b2dcec87b9cb1ad6990efc14b9dddcc503e54e18800d3c1a9e52f1bebd`;
  manager SHA256 `fee56e98e4b90ab19999231aa7d7198bcd071688bbdde1c8daeb5b76df513203`.
- Equivalent IDs (prefix `fa.inner_loop.plan_admission.`):
  `x__open_plan_component__mutmut_17` (follow_symlinks False→None is the same false C-API flag),
  `x__open_plan_component__mutmut_22` (False→None fallback used only as an if operand),
  `x__read_plan_bytes__mutmut_25` (directory False→None used only by `if directory`),
  `x_read_plan_snapshot__mutmut_17` (bytes.decode default encoding is UTF-8),
  `x_read_plan_snapshot__mutmut_18` (default errors is strict),
  `x_read_plan_snapshot__mutmut_20` (UTF-8 codec names are case-insensitive).
  No user-visible result, bytes, IO flags or diagnostics differ in these reachable call graphs.
  Non-equivalent initial survivors instead got tests (short read/growth/resource cap/descriptor
  flags/IO/root failures/resolver reason and ownership), and unreachable Path.parts members were
  removed rather than padded with artificial mocks.
- Ruff/mypy on six changed Python files clean; pylint four production files **10.00/10**;
  `git diff --check` clean. No full-repository static/format claim, no `just check` acceptance.
- Existing two deadline failures remain unwaived. Direct admission, durable schema/locked append,
  Q57/Q58, single T0, pinned evidence, unsupported acquisition, full-suite acceptance, independent
  review and operator DoD remain incomplete. No STEP/DoD ticks or I02 SHIPPED/live claim.
