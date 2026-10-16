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

## SLICE6 admission record and direct rejection checkpoint (E207, 2026-10-15)

**Partial CT92/CT95, STEP9/STEP13, GAP-03/GAP-10; no STEP/DoD tick.**
`admission_schema.py` supplies the closed v1 record vocabulary, exact field/type checks,
all-history route/diagnostic/hash coherence and sanitized errors. This checks record structure;
it does **not** establish accepted nonempty plan bytes or authorize an admitted coder.
`workflow_artifacts.py` supplies descriptor-rooted private IO, a bounded process-shared lock,
old/full-new validation and durable append. The direct controller calls the named presence guard
before artifact derivation, conditionally snapshots a supplied reference, and records a safely
addressed missing/unreadable-reference rejection before providers/T0/verification/eval.
A storage failure is separately observable; best-effort flow storage failure returns no persisted
FlowState object. A post-replace fsync error is **durability unknown**, not proof of file absence.

The existing flow/eval atomic writer now shares the private no-follow publication primitive.
That deliberate sibling change prevents the best-effort blocked-flow write from following an
artifact-directory alias after admission rejects it. No new dependency, transaction framework,
workspace service, acquisition authority, credential policy or mutation-profile suppression.

### Planned I03 F host cases — all unexecuted

Use the standing reviewed fixture requirements and E205/E206 provenance/safety controls.
All namespaces/targets must be explicitly owned scratch fixtures. Record host image/SHA/config,
UID/modes, actual argv, selected workspace and run/context identity, provider/stage deltas,
exit/reason and exact artifact bytes/schema. Do not test hostile paths against operator state.
Repeat public denials in linear/adaptive and observe/enforce; the flag never waives preflight.

| Producers / changed surface | Case | Arrangement and observable oracle |
| :--- | :--- | :--- |
| `AdmissionRecordError`, `_record_object`, `_record_enum`, `_record_hash`, `_record_plan_ref`, `_record_diagnostics`, `_record_attempt_hashes`, `_record_attempt`, `validate_admission_record`, closed `ADMISSION_RULES` | ADM-H01 | Exercise exact-key/version/type/enum/rule matrix, every old attempt, index continuity, FAIL/WARN/ERROR accumulation, RETRY/ADMITTED/BLOCKED truth table and canonical promotion chain. Corrupt old records, duplicate JSON keys and unknown diagnostic bodies never reset or become admission. Reserved values are reader compatibility, not I02 acquisition permission. |
| `_private_artifact_directory`, `_read_admission_at`, `_admission_object`, `AdmissionIOError` | ADM-H02 | Reviewed terminal/ancestor/dangling aliases, hardlinks, FIFO/directory and foreign-owner faults with valid-looking JSON controls. No outside bytes/modes changed, no hangs; private leaf directory 0700. Verify rooted no-follow/nonblocking/close-on-exec descriptors, explicit UTF-8 independently of process locale and owned-FD cleanup. Local metadata fault injection is not a deployed ownership-boundary result. |
| `_admission_lock` | ADM-H03 | Hold the real lock in another process; contend with a bounded absolute workflow deadline, then retry after release. Lock file regular/single-link/owned, 0600/no-follow; deadline exhaustion visibly lock-failed and prior bytes unchanged. Test the 120-second default bound with controlled timing, not an unbounded live waiter. |
| `write_admission_record` | ADM-H04 | Four processes append four attempts each to one safely addressed record. Require all 16 committed attempts exactly once and contiguous, old history retained, full record valid; corrupt prior data never silently initializes. Pin every subprocess import to the deployed candidate source, not an installed sibling. |
| `_replace_private_json` | ADM-H05 | Inject short/zero writes, tempfile-name collision, file fsync, replace and directory fsync faults. Before replacement retain exact prior bytes; after replacement retain published bytes and report durability-unknown without rollback. Only owned unpublished temps are cleaned; record/temp create mode 0600. No claim of persisted admission from a failed/uncertain barrier. |
| `WorkflowArtifactPaths.admission`, `_record_admission_attempt` | ADM-H06 | Direct rejection reaches the real controller writer and persisted artifact at context-specific/default paths. Its named CT92 producer removal must fail the full declared slice path. Later repeat with actual repair/replan/final admission barriers and a valid-plan coder; those consumers remain pending at this checkpoint. |
| `run_workflow -> _require_plan_for_coder`, supplied-reference snapshot, `_blocked_plan_request` | ADM-H07 | Missing/outside/symlink/invalid UTF-8 plus the full supported file-reference denial matrix; valid identity gives BLOCKED admission and FAILED/blocked flow, exact sanitized reason, zero provider/T0/verification/eval. Invalid identity remains the separate no-artifact path. Named direct CT95 producer removal must fail the whole slice path, not a nodeid selector. Valid UTF-8 semantic plan diagnostics still need the later admission-validator consumer. |
| shared `_write_json_atomic`, `write_flow_state`, `write_eval_report`; rejection storage renderer | ADM-H08 | Actual flow/eval outputs remain readable and private. Reject aliased/nonregular/hardlinked control targets and non-JSON numeric metadata without clobbering old bytes. Fault admission-only, flow-only and both writes: distinguish storage errors, preserve any committed history, never falsely claim a missing/uncertain write persisted. After successful coder, future admission IO failure must not suppress required eval; that integrated case is still pending. |

These are handoff labels, not Q63 result-schema ratification. No host scripts, deployed runs,
OS-boundary acceptance or scoped candidate-registry C3 are supplied by this checkpoint.

### TEST-EDITS and explicit remaining gaps

- Extract the existing explicit CLI input builder verbatim into `tests/workflow_fixtures.py`;
  `test_cli_ergonomics::_workflow_args`, deadline, direct history and no-eval helper callers reuse
  it. Supply a real disposable plan/test/interpreter, not synthetic baseline/result JSON.
  Routing, history, terminal and deadline assertions remain unchanged.
- Replace only the superseded public `test_absent_plan_degrades_silently` with
  `test_absent_coder_plan_is_blocked_before_dispatch`; private fallback tests remain unchanged.
- The existing live C1 now copies real source/scripts and its declared test into a disposable
  workspace, with contained plan/marker and the existing interpreter. Its provider sequence,
  verifier/eval/baseline/kill/artifact assertions are unchanged. This is not yet an admitted-plan C1.
- Five existing unwaived failures reproduce on archived **5b10409** with the same interpreter:
  the two deadline full-pipeline cases and `test_workflow_no_eval_terminal`'s linear no-verdict,
  scratch-success and planner/coder-without-eval cases. They reflect mandatory-eval/old terminal
  expectations; do not remove eval or weaken outcomes to make them green.
- **New unresolved integration failure:** `test_workflow_global_history::test_nested_workflow_produces_two_rows`.
  Its real implicit child supplies no PlanRef and is now rejected before dispatch, so no child
  aggregate history row is written. Its assertion was not changed or waived. The final approved
  managed-acquisition/unavailable path and its distinct bootstrap diagnostic still need wiring;
  the present generic missing-reference denial is not that delivery.
- Valid-plan precheck/kill validation, Q57 repair, exact-target registry/Q58 promotion, one admitted
  T0, pinned verifier/eval evidence, unsupported-acquisition routing, all 16 final producer runs,
  d9109f4 full-suite comparison and independent/operator DoD remain open. Do not infer completion
  from a passing partial STEP9 selector or from the existing verifier/eval C1.

### Actual local evidence

- Python 3.13.16, existing frozen dev environment. Final boundary command
  `uv run --frozen pytest tests/test_verify_gate_live.py -k 'admission_artifact or direct_api_plan_guard' -q`:
  **181 passed, 150 deselected (2.38s)**. Live file now has 331 cases, 181 newly added.
  Closed-record/IO tests are C0, including real filesystem/subprocess supplements; actual direct
  root denials use `_cmd_run` and only mock provider IO. They deliberately stop before session
  dispatch, not an admitted `drive_session` success. Hostile-path cases are local adversarial
  artifact-IO evidence, not I03 OS isolation or scoped-writer registry C3.
- The subprocess concurrency and non-UTF-8-locale tests explicitly prepend the importing module's
  source root and assert child module provenance. Initial inherited-only subprocess imports could
  resolve the installed sibling; that gap was corrected before the final mutation audit. Four
  competing processes preserve all 16 attempts. Zero-write and held-lock tests have an independent
  assertion alarm so a wedged mutant becomes a failing test, not a runner-timeout proof.
- Final actual producer kills use `_run_kill_check` with **the whole declared
  `tests/test_verify_gate_live.py` path**, real overlay/provenance/report checks and a 900-second
  outer budget; no nodeid/per-contract mapping. Each resolved **1 target / 1 edit**:
  CT95 `run_workflow -> _require_plan_for_coder`: **PROVEN, 139.719s**;
  CT92 `_record_admission_attempt -> write_admission_record`: **PROVEN, 67.552s**.
  This proves the direct denial/record consumers now wired, not valid-plan repair/admission.
  Q53(c)'s slice-wide unrelated-failure attribution risk remains. Earlier intermediate runs and
  a deliberately cancelled audit are not substituted for these final fixed-test-source runs.
- Fresh final targeted mutmut: **794 selected, 759 killed, 35 equivalents/unobservable**;
  no selected timeout/no-tests/suspicious/error/unchecked result. Breakdown: schema **416/413/3**,
  private IO/writer **255/223/32**, new controller helpers **123/123/0** (selected/killed/equivalent).
  Unselected generated mutants in the existing modules are outside this declared scope; this is
  not whole-controller mutation coverage. Scratch only, no repository profile change or source
  suppression. Initial audit was 666 killed/126 survived/2 timed out; tests were strengthened,
  locale/provenance and shared eval JSON edge cases were added, coverage/meta caches refreshed,
  and the entire selected scope rerun fresh. No timeout was relabelled a kill.
- Scratch configuration: source_paths are `src/fa/inner_loop/{admission_schema,workflow_artifacts,
  workflow_controller}.py`; also_copy `src/fa` and `scripts`; pytest selects the live file with
  `-q -x -k 'admission_artifact or direct_api_plan_guard'`. Mutant filters cover all schema functions;
  artifact `AdmissionIOError`, `_private_artifact_directory`, `_admission_object`, `_read_admission_at`,
  `_replace_private_json`, `_write_json_atomic`, `_admission_lock`, `write_admission_record`; controller
  `*admission*` and `_blocked_plan_request`. Reuse the E206 scratch-only absolute instrumentation-path
  adapter; do not change actual CWD/provenance tests to accommodate mutmut.
- Ruff and targeted mypy: **all ten changed/new Python files pass**. Pylint on the three production
  modules: **10.00/10**. `git diff --check` clean. AST comparison against 5b10409: only the declared
  original live C1 fixture function changes; no old live function removed. Other original function
  changes are the four declared `_run`/`_workflow_args` fixture callers; only the explicitly
  superseded public no-plan test is renamed/replaced. No hidden routing/budget/oracle relaxation.
- Archived `git archive 5b10409`, same interpreter and explicitly checked archived module origin:
  `test_workflow_global_history`, `test_workflow_no_eval_terminal`, `test_workflow_deadline`:
  **5 failed, 19 passed (1.92s)**, the five identities listed above. This is a checkpoint regression
  baseline, not the required d9109f4 full-suite comparison. A first archive command ran from the
  scratch non-Git directory and failed; only the corrected repository-root archive was used.

#### Accepted equivalent / unobservable mutant inventory (35)

IDs below are suffixes of the indicated module/function's `__mutmut_N`; final source hashes follow.
No pragma or mutation-scope suppression hides these results.

| Module/function | IDs | Proof at the supported boundary |
| :--- | :--- | :--- |
| `admission_schema._record_attempt` | 89, 90 | Changing the INDETERMINATE comparison in the ERROR/routing predicate cannot admit a new route: the closed route set plus separate ADMITTED→PASS and RETRY→DIAGNOSTICS guards already force INDETERMINATE to BLOCKED. |
| same | 102 | RETRY's `or`→`and` is redundant with earlier PASS-no-FAIL, DIAGNOSTICS-needs-FAIL and INDETERMINATE-only-BLOCKED guards. The full routing/severity truth table covers the reachable combinations. |
| `workflow_artifacts._read_admission_at` | 23, 25, 31 | `closefd=False`→None is the same false boolean; omitted mode defaults to `r`; UTF-8/utf-8 are identical codec aliases. Locale-dependent encoding removal is **not** accepted: final explicit-source non-UTF-8 child kills 22/26. |
| `_replace_private_json` | 5, 8 | JSON encoder's False→None boolean options are identical false values. |
| same | 6, 7, 10, 11, 12, 14, 15, 16 | Sort order, optional indentation and escaped-vs-literal Unicode change representation only. All remain valid JSON with identical typed record values; no canonical admission-JSON byte serialization is specified. This does not waive exact old-byte preservation on a failed replacement. |
| same | 20 | UTF-8/utf-8 encoder alias. |
| same | 22, 24, 30 | False→None has identical truthiness for the publication/owned-temp flags and `follow_symlinks`. |
| same | 40, 41, 42 | The inner pre-publication error's rule is immediately caught as OSError and normalized to the same outer append-failed. Persisted data, public typed rule/message and cleanup are unchanged; internal cause text is not the diagnostic contract. |
| same | 73, 74, 75, 76, 77, 78 | Zero-write cause errno/message changes normalize to identical append-failed with identical cleanup and retained prior bytes. No public consumer uses that internal cause's errno/text. |
| `write_admission_record` | 48, 50, 51, 67, 69, 71 | False→None matches the encoder boolean; allowing NaN in the **in-memory detach round trip** cannot persist it: old record is already fully validated and full proposed-record schema rejects every nonfinite field/key before publication. Both paths yield the same corrupt-record failure for malformed proposals. This does **not** apply to the shared publication serializer: omission/True there (13/17) is killed by real eval-metadata non-JSON-number tests. |

Production SHA256: schema `cd833ce4d2c480d230061974ec0b41908b99fde8430a5092331970e7eff39427`;
artifacts `27c8a2ca60ced86d8d220b1b0c26b22598e304b1f00ac6df5b086c7744004721`;
controller `d350e8cbdf3b6020abff466e3eb56741a7d214e51accc9c57679a4044ba4126c`.
Final live-test SHA256 `5196e34b28d7ca960397de0562fe29245059cc9828782d717c06e88071839330`.

Final broad checkpoint command: `uv run --frozen pytest -q --tb=short` on these twenty
`tests/*.py` suites: `test_verify_gate_live`, `test_verify_slice`, `test_slice_verification_runner`,
`test_workflow_role_allowlist`, `test_session_lifecycle`, `test_session_manifest_guards`,
`test_session_workspace_provisioning`, `test_plan_reference`, `test_cli_ergonomics`,
`test_s8_workflow_controller`, `test_s10b_cli_parity`, `test_inject_cli_flag`,
`test_s10c_artifact_posture`, `test_workflow_artifacts`, `test_workflow_deadline`,
`test_workflow_global_history`, `test_workflow_no_eval_terminal`, `test_eval_evidence_block`,
`test_slice_id_validation`, `test_s10c_workflow_exit_contract`:
**864 passed, 6 failed in 473.61s** (exit 1). Exactly the five baseline failures and the new
implicit-child history failure enumerated above; no waiver or green full-suite claim.
The existing real verifier/eval C1 passes in this final fixed-source run. An earlier broad run
before the last two serializer cases/provenance correction was 862 passed/6 failed in 562.85s;
it is not substituted for the final run. This is still a targeted twenty-suite checkpoint,
not `just test`, d9109f4 acceptance, or proof that the rest of I02 is complete.

## SLICE6 exact-target planner writer prerequisite (E208, 2026-10-15)

**Disposition:** partial STEP9 / CT93, GAP-04–GAP-06 prerequisite, from E207
`4eaa32c94112c100e01b919bd2d1f29971528e1a`. Re-read remaining SLICE6 and the normative
explicit-admission spec before editing. No blocking policy question found; the remaining
validation/repair, canonical promotion, single admitted T0, pinned verification/eval and
unsupported nested acquisition gaps are real implementation work, not grounds to silently
reduce or reinterpret the plan. No STEP checkbox, I02 completion or deployed-security claim.

### Declared edit / source review / implementation

Pre-edit declaration: add a frozen, controller-owned typed planner dispatch; thread it through
the real stage/CLI/registry composition; install a mandatory single-target writer for admission
repair/eval replan; reuse small descriptor IO and existing mutation bookkeeping rather than a
new transaction framework. Ordinary planning keeps the existing research/`.fa` prefixes but
cannot use `fs_write_file` to overwrite admission storage or the active PlanRef. Failure to
construct/register the scoped writer must stop before provider dispatch, never silently select
the ordinary writer or read+bash fallback. DoD is exact candidate bytes/private modes plus
unchanged protected files, actual provider-visible schema and tool trajectory, malformed
capability zero-provider/no-lifecycle effects and a real producer kill. Tests follow
`knowledge/skills/tests-writing/SKILL.md`; mutation guidance read before test edits.

Exact allowed files (and actual changed scope):

- new `src/fa/inner_loop/planner_dispatch.py`;
- `src/fa/inner_loop/{workflow_artifacts,profiles,workflow_controller}.py`;
- `src/fa/inner_loop/tools/{write_file,__init__}.py`;
- `src/fa/cli.py`, `tests/test_verify_gate_live.py`;
- this register and `../ledger.md`.

Source findings and current→target:

- `_run_stage` previously passed no trusted planner writer scope. It now binds ordinary
  dispatch to the current run/active relative PlanRef; repair/replan overrides must match that
  run and active path and are forbidden on non-planner stages. `_cmd_run` accepts a private
  keyword, not a CLI flag or Namespace/model JSON field; its argument prologue checks actual
  typed instance, planner role and matching run ID before configuration/task/lifecycle work.
- `PlannerDispatchKind` is separate from admission-attempt kinds. Frozen/slotted
  `PlannerDispatch` validates the same admission run-ID grammar, normalized relative slash
  components (no empty/dot/parent/NUL/absolute components), no ordinary candidate and a distinct
  candidate beneath exactly `.fa/admission/<run_id>/`. It does not allocate/seed candidates.
- `_build_run_tool_registry` → `_build_role_registry` → `build_planner_registry` →
  `build_registry_for_role` → `_build_tool_builders` now carries the dispatch. Scoped tool
  creation is outside optional-builder degradation; a missing registered `fs_write_file` is
  fatal for a supplied dispatch. The outer planner fallback rethrows a static
  `PlannerDispatchError` rather than weakening a requested corpus.
- `build_scoped_write_file_tool` closes over the target, advertises a single-value path enum
  and `additionalProperties=False`, and separately checks exact path/content in its handler.
  It never forwards a checked path to the generic writer. `_replace_private_bytes` is the
  existing E207 JSON publication body extracted unchanged into a shared byte primitive;
  `_replace_private_json` still serializes exactly as before and delegates to it. Scoped IO
  uses the private descriptor walk and same-directory exclusive 0600 temp, complete byte write,
  file fsync, replace, directory fsync and owned-temp cleanup. Ancestor/terminal aliases,
  nonregular and multi-link targets fail without following them. IO failures are non-retryable
  tool failures; post-replace durability uncertainty still must not be called a rollback.
- The generic writer retains mkdir/write_text semantics. Both writers use the extracted
  `_write_with_guard` for existing conflict checks/transaction/blackboard bookkeeping; existing
  deliberately-absent-substrate and legacy context-access degradation semantics are not
  redefined in this checkpoint. No new execution-isolation or universal substrate claim.
- The extracted ordinary `_build_limited_write` first retains its existing lexical allowlist,
  then `_planner_target_allowed` denies reserved lexical/resolved storage paths, active path
  and existing same-inode active aliases, and rechecks the resolved destination allowlist.
  No worklogs permission expansion. These are writer-tool checks, not an OS/shell boundary:
  arbitrary bash/PTY and managed exclusive-writer containment remain I03 work.

**TEST-EDITS:** append only, 47 new collected cases. AST comparison against HEAD proves the
entire original 104-node module prefix unchanged; no old oracle, selection or fixture weakened.
New negative fixture initially shared a state root across parametrized roles; it was strengthened
to separate per-role/run roots and explicitly assert no state allocation. Final binding mutation
then fails all three negative cases (the earlier fixture observed only two). Final audits below
use the strengthened test hash, not that intermediate result.

### Local proof classes, path and outcomes

- **C0:** typed/frozen scope and normalized target/type/run/active negatives; direct handler
  wrong-path and UTF-8 failures; repeated positive publication with 0600/0700 modes;
  ancestor/terminal inside-workspace symlinks, hardlink, FIFO and directory sentinels;
  conflict denial and pre-publication replace/fsync faults preserve old bytes and leave no
  owned temporary. These are local filesystem proofs, not deployed ownership/OS isolation.
- **C1/C3:** six parameter combinations of real `_run_stage` → `_cmd_run` → role registry →
  real session/normal hooks/tools/filesystem. Only `ProviderChain.request` is replaced in this
  live-path test. Its first response calls the actual `pr_prepare` producer; no fabricated draft,
  disabled IntentGuard or handcrafted registry. Subsequent real tool calls cover ordinary,
  admission-repair and eval-replan corpora, active/symlink/hardlink and admission aliases,
  forbidden src/worklogs writes and same-prefix ordinary positive controls. Scoped ancestor,
  terminal and hardlink cases assert a real `write_failed` tool-result event, not a hook denial;
  the valid case asserts the exact provider schema, successful tool-result event and bytes.
- **C2/fault checks:** inject unavailable or absent scoped builder while retaining real stage,
  CLI and registry construction. A typed error escapes before any provider/candidate write;
  no fallback success. Misbound CLI dispatch uses real parser-produced valid arguments and a
  callable provider control, not an under-populated Namespace which would fail independently.
- A session can return exit 0 after an ordinary tool denial. **That is not admission success.**
  `_run_stage` does not yet translate scoped writer errors into an admission BLOCKED receipt.
  The future CT91/Q57 repair orchestrator must consume scoped error outcomes (including
  durability-unknown), block on capability/IO errors, validate exact resulting bytes and never
  promote merely because planner text/session exit looks successful. Current scoped-construction
  errors stop by raising before provider dispatch; the repair controller must persist their
  terminal admission routing. This remains explicit missing integration, not a hidden stub.

All commands used the locked pyproject environment through
`/home/user/.local/fa-bootstrap/bin/uv run --frozen` (abbreviated `uv run --frozen` below).
Observed interpreter: Python 3.13.16, GCC 12.2.0. Final focused commands:

```sh
uv run --frozen pytest tests/test_verify_gate_live.py -k ct93 -q --tb=short
# 47 passed, 331 deselected (3.97s)
uv run --frozen pytest tests/test_verify_gate_live.py tests/test_write_allowlist.py \
  tests/test_write_file_expected_root.py -k 'not real_workflow' -q --tb=short
# 409 passed, 1 deselected (6.25s, final rerun)
```

Ruff and Mypy on all eight changed Python files: clean / `Success: no issues found in 8 source
files`. Pylint on planner_dispatch, tools/write_file and profiles: **10.00/10**, no added
suppressions. `git diff --check`: clean. Additional Pyrefly on seven changed production modules:
**0 errors**. Pyrefly including the full live test file reports **59 errors**, all pre-existing
untyped dictionary-unpacking fixtures at lines 705–2480. Reconstructed the six prior production
files and old test file with exact `git show 4eaa32c:<path>` bytes in a separate source/test/config
copy (no branch switch). That baseline also gives **59 errors**, with all 59 ordered diagnostic
messages and locations identical. No Pyrefly test-file/full-project green claim or waiver.
Scratch logs: `/home/user/.cache/fa-i02-ct93-pyrefly-{candidate,baseline}.log`.

### CT93 named producer kill — actual whole declared path

Final real `_run_kill_check` directive:

```python
KillDirective(KillOperator.REMOVE_CALL, "src/fa/inner_loop/profiles.py",
              "_build_tool_builders", "build_scoped_write_file_tool", 0)
# _run_kill_check(directive, "tests/test_verify_gate_live.py", root,
#                 deadline=time.monotonic() + 900)
```

Existence/application precheck: **targets=1, edits=1**. Final verdict **PROVEN**, empty detail,
**144.939421151s**. Uses the real overlay import-origin probe and consistent current JUnit
run-ID evidence; no timeout/collection/infrastructure outcome counted as proof. Runs the whole
`tests/test_verify_gate_live.py`, not `-k ct93`. Q53(c) slice-level attribution risk remains;
this is one checkpoint kill, not STEP17's complete sixteen-contract acceptance rerun.
Scratch driver/log: `/home/user/.cache/fa-i02-ct93-kill.py`,
`/home/user/.cache/fa-i02-ct93-kill-final.log`. Initial pre-strengthening run was PROVEN in
124.047s; it is not substituted for the final fixed-test run above.

### Targeted semantic mutation audit — 17/17 detected

This is an explicit small semantic audit, **not a whole-module mutmut score**. For each row,
assert the named function/site exists and replacement count, apply only that change inside a
disposable production `mutation_overlay`, assert the actual module resolves inside its overlay,
then run `python -m pytest tests/test_verify_gate_live.py -k ct93 -q --tb=short --junitxml=<fresh>`.
The outside tests are never mutated. Require return code 1, 47 collected/executed cases, at least
one assertion/application failure, zero JUnit errors, fresh per-case XML and unchanged test hash.
Timeouts/exceptions fail the audit, not count as kills. Each final row meets those conditions;
no survivors, infrastructure statuses, ignored mutation profiles or equivalence waivers.

| Mutation ID | Function / exact semantic change | Final failed cases (of 47; errors=0) |
|---|---|---:|
| namespace-binding | `PlannerDispatch.__post_init__`: compare only first 2 target components instead of run-bound first 3 | 2 |
| normalized-dot | `_relative_target`: remove `.` from forbidden components | 2 |
| enum-type | `__post_init__`: bypass actual-enum-instance guard | 1 |
| ordinary-no-candidate | `__post_init__`: bypass ordinary candidate prohibition | 1 |
| candidate-not-active | `__post_init__`: bypass candidate/active equality denial | 1 |
| exact-handler-target | `build_scoped_write_file_tool`: bypass handler path comparison | 1 |
| mutation-guard | `_write_with_guard`: ignore non-None guard denial | 1 |
| required-registration | `build_registry_for_role`: bypass required writer lookup failure | 1 |
| no-fallback | `build_planner_registry`: bypass supplied-dispatch exception rethrow | 2 |
| ordinary-protection | `_planner_target_allowed`: replace body with `return True` | 1 |
| stage-capability | `_run_stage`: remove `**dispatch_kwargs` from the real session call | 8 |
| cli-role-run-binding | `_valid_planner_dispatch`: replace body with `return True` | 3 |
| registry-capability | `_build_run_tool_registry`: pass `planner_dispatch=None` instead of the dispatch | 8 |
| single-link | `_replace_private_bytes`: remove `or metadata.st_nlink != 1` | 2 |
| nonregular | `_replace_private_bytes`: replace `not stat.S_ISREG(metadata.st_mode)` with False | 3 |
| ancestor-nofollow | `_private_artifact_directory`: remove both ` | os.O_NOFOLLOW` flag components | 2 |
| durable-file | `_replace_private_bytes`: replace `os.fsync(fd)` with None | 1 |

Scratch driver `/home/user/.cache/fa-i02-ct93-mutations.py`; final log
`/home/user/.cache/fa-i02-ct93-mutations-final.log`; detailed fresh XML/logs and `results.json`
under `/home/user/.cache/fa-i02-ct93-mutations/`. These scratch artifacts are not committed;
the table/method and permanent tests are the reproducible handoff, not a cache dependency.

### Broader regression state — explicitly not green

Twenty E207 suites plus write_allowlist/write_file_expected_root were run (22 files):
`test_verify_gate_live`, `test_verify_slice`, `test_slice_verification_runner`,
`test_workflow_role_allowlist`, `test_session_lifecycle`, `test_session_manifest_guards`,
`test_session_workspace_provisioning`, `test_plan_reference`, `test_cli_ergonomics`,
`test_s8_workflow_controller`, `test_s10b_cli_parity`, `test_inject_cli_flag`,
`test_s10c_artifact_posture`, `test_workflow_artifacts`, `test_workflow_deadline`,
`test_workflow_global_history`, `test_workflow_no_eval_terminal`, `test_eval_evidence_block`,
`test_slice_id_validation`, `test_s10c_workflow_exit_contract`, `test_write_allowlist`,
`test_write_file_expected_root` (each under `tests/`, `.py`).

- Intermediate full-path run: `uv run --frozen pytest -q --tb=short <22 files>`:
  **929 passed, 6 failed / 748.52s** (exit 1). It collected before the final fourteen appended
  cases/state-isolation refinement; production code was already the final source below. Includes
  the original unmutated verifier/eval live composition positive. Not represented as a final
  all-test-file-hash baseline run.
- Final fixed-source/test-bank compatibility run:
  `uv run --frozen pytest -q --tb=short -k 'not real_workflow' <same 22 files>`:
  **942 passed, 6 failed, 1 deselected / 137.20s** (exit 1). The one expensive existing
  real-workflow test is deselected explicitly, not silently replaced by a green subset claim.
  Final C1/C3 writer cases are included; the final named kill above separately runs the whole
  declared live path. Logs `/home/user/.cache/fa-i02-ct93-regressions{,-final}.log`.

The same six E207 failures, with assertions unedited/unwaived:

1. `test_workflow_deadline.py::test_no_deadline_runs_the_full_pipeline`;
2. `test_workflow_deadline.py::test_generous_deadline_runs_the_full_pipeline`;
3. `test_workflow_no_eval_terminal.py::test_eval_requested_but_no_verdict_fails[linear]`;
4. `test_workflow_no_eval_terminal.py::test_scratch_pipeline_succeeds_but_is_marked_unjudged`;
5. `test_workflow_no_eval_terminal.py::test_planner_coder_without_eval_is_also_unjudged`;
6. `test_workflow_global_history.py::test_nested_workflow_produces_two_rows` (unsupported
   implicit child still receives missing-PlanRef rejection rather than approved
   acquisition_unavailable routing; do not manufacture history or waive its assertion).

First five were independently reproduced on 5b10409 in E207. No new pytest failure in this
22-file comparison; no `just test`, d9109f4 comparison, or full acceptance claim.

### New live-host inventory — planned only, I03 F ownership

Standing fixture/provenance/mode/dual-path controls from E205–E207 still apply: reviewed
operator-owned disposable Linux/Docker workspace and outside sentinels, recorded deployed
source/import hashes, real backend/PTY/session/hook path, bounded faults, redacted credential
handling, no global debug-body enable. Local provider-mocked C1/C3 is not a deployed run.
Run future route-dependent cells only after the real Q57/Q58 controller consumers exist.

| Every new/changed surface | Host case | Required independent live-host observable |
|---|---|---|
| `PlannerDispatch`, `PlannerDispatchKind`, `PlannerDispatchError`, `_relative_target`, `_stage_planner_dispatch`, CLI `_valid_planner_dispatch`/prologue | ADM-H09 | Wrong kind/type/run/role/active identity/normalized target stop before provider/lifecycle; controller dispatch stays out of model/Namespace JSON. Ordinary and both scoped kinds have positive same-run controls; frozen fields cannot be widened. |
| `_build_run_tool_registry`, `_build_role_registry`, `build_planner_registry`, `build_registry_for_role`, `_build_tool_builders`, `_candidate_dispatch` | ADM-H10 | Actual deployed composition advertises exact schema and installs the real scoped handler; missing/raising required producer cannot degrade to ordinary/read+bash tools. Capture zero provider on construction failure and named producer sensitivity on the full declared test path. |
| `_build_limited_write`, `_planner_target_allowed` | ADM-H11 | Ordinary `.fa`/research positives alongside active path, resolved symlink/hardlink aliases, admission aliases and src/worklogs negatives. Exact old protected bytes/modes, actual error trajectories; do not claim bash or another tool is contained by this file-writer guard. |
| `build_scoped_write_file_tool`, `_replace_private_bytes`, extracted `_replace_private_json`, `_private_artifact_directory` reuse | ADM-H12 | Both real repair/replan candidates, single-target schema and direct-handler guard, UTF-8 and repeated publication; private modes; inside-workspace ancestor/terminal symlinks, hardlink/FIFO/directory and outside sentinels unchanged on denial. Prove writer-origin failure rather than just an earlier hook. Pre/post-replace faults preserve appropriate old/published bytes and distinguish durability uncertainty. Extends ADM-H02/H05, not substitutes for them. |
| `_write_with_guard`, ordinary writer closure, real `pr_prepare`/IntentGuard + session consumers | ADM-H13 | Real conflict/substrate and read/write-set bookkeeping retained for both writer kinds; positive controlled write and denied write have correct tool-result/blackboard/transaction effects. Capability/IO failure is eventually consumed as admission BLOCKED, even when planner session otherwise stops successfully; no T0/coder/eval or canonical promotion on that path. Do not disable guards to obtain a positive. |

### Final source/test identity and next work

| Path | SHA256 |
|---|---|
| `src/fa/cli.py` | `732ca6bb3e0ac9acf42e1aef200ee50ec21e9693464886f0a278142012650e89` |
| `src/fa/inner_loop/planner_dispatch.py` | `dc30185f8dd89fd0e0beb9ce257b676bc7dd73a3ddcca1667b2f7a8d54686890` |
| `src/fa/inner_loop/profiles.py` | `9dc2780947286c753926fef845b00760df5c813e398f5ecf3ee45f16aa09b2da` |
| `src/fa/inner_loop/tools/write_file.py` | `ce936a1702806163a5463736e7a61226b9def8b0e465d1c0e09ba6b979e80dc4` |
| `src/fa/inner_loop/tools/__init__.py` | `48df5d2bbb54a1dea4af1c873f860a19dd142c6638a1277e62121558b3733229` |
| `src/fa/inner_loop/workflow_artifacts.py` | `984fbfc085aab7f02e27dffb0f4dd13451e410c9a769a4df6a8f939944a00fa1` |
| `src/fa/inner_loop/workflow_controller.py` | `a79cfba018d9821bdc448172d319183789496577c9c9f2ee1840b4795907fab5` |
| `tests/test_verify_gate_live.py` | `64063e8d7840ffffa0c69be404b6c7725fbb48bee258c0f493605f685877a896` |

Next: source-reviewed CT94 fresh-candidate seeding/canonical locked hash-checked promotion,
then CT91/Q57 validation and shared bounded repair/replan credit/error consumption; successful
ADMITTED barrier, exactly one admitted T0 and pinned verifier/real eval local composition;
approved acquisition_unavailable routing. Keep six pytest and 59 old fixture-type findings
visible; no silent assertion migration/suppression. Final 16 whole-path kills, independent
review/operator DoD, full-suite comparison and I03 managed acquisition/OS/live-host work stay open.


## E209 — 2026-10-15 CT94 publication prerequisite (partial, not public admission)

### Source review and edit declaration

Starting checkpoint: `175617eddc563bb340b8953e091de90c2d17a332` (E208). Reviewed retained
SLICE6, explicit-admission spec §§2–6, Q58, migration §3, and `/tests-writing` plus mutation
rules before implementation. Source had the real CT93 scoped writer but no fresh-candidate
producer or canonical publication helper; public admission/repair orchestration was absent.
No unresolved blocking policy question or new policy decision was identified. This implements
an IO/validation prerequisite, **not** a claim that a new public workflow producer is wired.

Exact allowed edits: `src/fa/inner_loop/plan_admission.py`, new
`src/fa/inner_loop/plan_promotion.py`, `src/fa/inner_loop/workflow_controller.py`,
`tests/test_verify_gate_live.py`, this register and `../ledger.md`. No new dependency, public
flag, generic transaction framework, namespace expansion, or logging/privacy policy change.

| Edit / concrete current → target | Contract / gap support (not closure) | Mechanism, failure boundary and negative DoD | Class / producer sensitivity |
|---|---|---|---|
| Reader: filesystem-only snapshot → reusable bounded descriptor read and immutable-buffer capture | CT94/CT95; GAP-08/15 | Extract unchanged bounded descriptor algorithm; strict size/UTF8/nonempty bytes, same hash/parser. Invalid bytes fail before publication allocation; descriptor mutation remains `source-changed`. | C0/C3; strict UTF8/size/descriptor-rule mutations. Existing reader regressions included. |
| Candidate producer: no producer → fresh exclusive private seed from active/latest rejected snapshot | CT94/CT93; GAP-09/15 | Validate dispatch and approved canonical prefix before IO; UUID leaf, O_EXCL/O_NOFOLLOW, complete short-write loop, 0600, file+parent fsync. Preserve foreign collision; remove only incomplete owned seeds. Ordinary kind denied. Rejected draft progress preserved. | C0/C3 and real session subcomposition for both kinds; seed/progress/fsync mutations. Public caller remains missing. |
| Validator: no shared receipt → frozen snapshot-bound PASS/DIAGNOSTICS/INDETERMINATE result | CT87/CT91/CT92; GAP-06/12 | Both real validators consume exact captured text/IDs. Project only closed rules/severities/positive-int line; retain determinate failures alongside validator errors. WARN alone passes; errors and unqualified zero slices cannot pass. Exceptions never become successful admission or persisted bodies. | C0 plus actual writer→validation composition. Remove-call `_validate_plan_admission→precheck` and `→validate_kill_directives`, plus classification/closed-projection mutations. GAP-06 remains OPEN without public caller/full-path proof. |
| Publisher: no canonical installer → validated immutable buffer atomically installed at same approved path | CT94/Q58; GAP-15 | Reuse process-shared deadline flock and private directory primitives. Target-key lock, rooted no-follow canonical parent, regular/single-link source, source-hash and metadata CAS before replace. Unique exclusive sibling, mode preservation, complete write/file fsync/replace/parent fsync, post-hash/mode checks. Parent modes unchanged. Pre-replace failures retain canonical; post-replace failures report uncertainty with `replaced=True`, never roll back. | C0/C3, actual competing publisher processes and held-lock deadline. `_promote_validated_plan→publish_plan_buffer` remove-call plus source/CAS/fsync/replace/hash/mode/lock mutations. Named CT94 public producer still absent. |
| Tests/evidence: no CT94 prerequisite coverage → concrete side-effect/typed-result oracles and explicit missing consumer | CT94 prerequisite; CT87/91 support, GAP-06/12/15 remain open; GAP-04/05 belong to I03 F | Actual schema bytes, IDs/object preservation, tool result/events, canonical/candidate bytes and modes, foreign temp/candidate survival, real process outcomes and bounded deadline failures. No green-by-no-exception or weakened old assertion. | C0; C1/C2 actual `_run_stage→_cmd_run→drive_session` scoped writer subcomposition; adversarial C3; supplemental C4. Not public `run_workflow` admission C1. |

Canonical scope is the approved `worklogs/planning-topology-and-executable-contracts-loop/increments/`
prefix with normalized components, including descendants; an accidental direct-child-only
restriction was corrected during review. Other namespaces remain denied before candidate IO.
The final typing-only cleanup uses `Generator[int]` for `@contextmanager`, removing a newly
introduced Pyrefly deprecation rather than adding a suppression.

### Implementation boundaries / TEST-EDITS

- `seed_plan_candidate` returns the existing frozen dispatch capability; latest rejected bytes can
  seed another fresh target without making the draft an active plan. Completed candidates are
  deliberately retained for the future owning orchestrator. Terminal owned-candidate cleanup
  remains pending; incomplete owned seed/publication temps are cleaned now.
- `_validate_plan_admission` creates a controller-owned immutable receipt.
  `_promote_validated_plan` requires PASS, publishes that captured buffer (not a mutable draft
  pathname), and preserves its text/bytes/IDs object while replacing only its PlanRef.
  The IO module independently enforces byte/target/source invariants, not semantic admission.
- Existing publisher locks/CAS are cooperative local integrity, **not** arbitrary same-UID writer,
  shell, host, namespace or OS isolation. I03 remains required.
- New tests are appended. Top-level typing imports and one now-redundant local typing import
  changed; therefore this is **not** a strict whole-file append-only claim. AST comparison of
  all **91** original top-level test/fixture/class definitions is identical after removing import
  statements only. No prior assertions, routing/budget/deadline/history oracles were changed.
- Public `run_workflow` is not wired to these helpers. `_run_admission_repair` does not exist yet.
  Admission barriers, shared repair/replan credits, consumption of actual scoped tool errors
  even when a session otherwise succeeds, terminal candidate cleanup, successful ADMITTED/T0
  ordering and pinned verifier/real-eval handoff are still open. This is a tested prerequisite,
  not a dead-handler-based product completion claim.

### Commands / actual results

Environment: repository `.venv`, Python **3.13.16**, locked `uv run --frozen`, uv at
`/home/user/.local/fa-bootstrap/bin/uv`. Final production/test source identities below.

```sh
uv run --frozen pytest tests/test_verify_gate_live.py -k ct94 -q --tb=short
# 52 passed, 378 deselected / 2.12s (before final annotation-only cleanup)
uv run --frozen pytest tests/test_verify_gate_live.py tests/test_plan_reference.py \
  tests/test_plan_precheck.py tests/test_write_allowlist.py tests/test_write_file_expected_root.py \
  -k 'not real_workflow' -q --tb=short
# 534 passed, 1 deselected / 7.74s (before final annotation-only cleanup; repeated below)
uv run --frozen ruff check src/fa/inner_loop/plan_admission.py src/fa/inner_loop/plan_promotion.py \
  src/fa/inner_loop/workflow_controller.py tests/test_verify_gate_live.py
# All checks passed!
uv run --frozen mypy src/fa/inner_loop/plan_admission.py src/fa/inner_loop/plan_promotion.py \
  src/fa/inner_loop/workflow_controller.py tests/test_verify_gate_live.py
# Success: no issues found in 4 source files
uv run --frozen pylint src/fa/inner_loop/plan_admission.py src/fa/inner_loop/plan_promotion.py \
  src/fa/inner_loop/workflow_controller.py --score=y
# 10.00/10
uv run --frozen pyrefly check --min-severity warn src/fa/inner_loop/plan_admission.py \
  src/fa/inner_loop/plan_promotion.py src/fa/inner_loop/workflow_controller.py
# 0 errors; exactly 5 existing unnecessary-str warnings in controller (rc 0)
git diff --check
# no output (rc 0)
```

Combined production+test Pyrefly: **59 errors**, all fixture argument/unpacking debt, unwaived.
An archived exact E208 source/test tree under `/home/user/.cache/fa-i02-ct94-typebaseline`,
same executable/config/dependencies, reproduces the **same 59 ordered message/file/column
triples**, each candidate line shifted +3 by typing imports. This is a focused diagnostic
comparison, not the required isolated-environment `d9109f4` full-suite acceptance comparison.
Final combined recheck and focused pytest timing are recorded in the closing results below.

### Supplemental targeted mutation — not named whole-path acceptance

28 explicit mutations use production `apply_kill` (three remove-call cases) and
`mutation_overlay`, one source target at a time. Before each pytest run, `_assert_overlay_wins`
checks actual import provenance; tests remain outside overlay and their SHA256 is unchanged.
Each fresh JUnit report must contain exactly **52 tests**, pytest rc 1, assertion failures >0,
**zero errors/skips**. Runner/timeout/collector errors cannot count as kills. Child publication
cases assert their exact overlay module `__file__`; a held real parent lock makes bypass
sensitivity deterministic. All final **28/28 detected**; individual failures/counts below.

| Mutation | Production symbol / exact edit | Assertion failures |
|---|---|---|
| producer-precheck | `_validate_plan_admission`: `remove-call → precheck` | 31 |
| producer-kill-validator | `_validate_plan_admission`: `remove-call → validate_kill_directives` | 30 |
| producer-publish | `_promote_validated_plan`: `remove-call → publish_plan_buffer` | 25 |
| error-not-pass | `_validate_plan_admission`: `'return PlanAdmissionValidation(snapshot, "INDETERMINATE", diagnostics)' → 'return PlanAdmissionValidation(snapshot, "PASS", diagnostics)'` | 5 |
| failure-not-pass | `_validate_plan_admission`: `'return PlanAdmissionValidation(snapshot, "DIAGNOSTICS", diagnostics)' → 'return PlanAdmissionValidation(snapshot, "PASS", diagnostics)'` | 6 |
| zero-slices | `_validate_plan_admission`: `'if not snapshot.ids.slice_records:' → 'if False:'` | 3 |
| closed-diagnostics | `_admission_diagnostics`: `'if item.rule not in ADMISSION_RULES[validator] or item.severity not in {"WARN", "FAIL", "ERROR"}:' → 'if False:'` | 2 |
| pass-receipt | `_promote_validated_plan`: `'if validated.outcome != "PASS":' → 'if False:'` | 3 |
| canonical-scope | `_canonical_parts`: `body → return tuple(snapshot.ref.workspace_relative_path.split("/"))` | 3 |
| rejected-progress | `seed_plan_candidate`: `'raw = source.utf8_bytes if draft is None else draft.utf8_bytes' → 'raw = source.utf8_bytes'` | 2 |
| seed-no-clobber | `_create_candidate`: `' \| os.O_EXCL' → ''` | 1 |
| seed-file-fsync | `_create_candidate`: `'os.fsync(fd)' → 'None'` | 1 |
| seed-directory-fsync | `_create_candidate`: `'os.fsync(parent)' → 'None'` | 1 |
| source-hash | `_checked_source`: `'if hashlib.sha256(raw).hexdigest() != expected:' → 'if False:'` | 2 |
| single-link | `_checked_source`: `'or metadata.st_nlink != 1' → ''` | 2 |
| final-cas | `_install_buffer`: `'current = _checked_source(parent, name, source.ref.sha256)' → 'current = metadata'` | 5 |
| source-identity | `_install_buffer`: `'if _source_identity(current) != _source_identity(metadata):' → 'if False:'` | 2 |
| staged-bytes | `_stage_replacement`: `'_write_all(fd, raw)' → 'None'` | 10 |
| file-fsync | `_stage_replacement`: `'os.fsync(fd)' → 'None'` | 1 |
| atomic-replace | `_install_buffer`: `'os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)' → 'None'` | 10 |
| directory-fsync | `publish_plan_buffer`: `'os.fsync(parent)' → 'None'` | 1 |
| post-hash | `publish_plan_buffer`: `'if promoted.ref.sha256 != expected_hash:' → 'if False:'` | 1 |
| post-mode | `publish_plan_buffer`: `'if stat.S_IMODE(metadata.st_mode) != expected_mode:' → 'if False:'` | 1 |
| short-write-progress | `_write_all`: `'remaining = remaining[written:]' → 'remaining = remaining[written + 1:]'` | 1 |
| descriptor-change-rule | `publish_plan_buffer`: `'{"symlink", "source-changed", "not-regular"}' → '{"symlink", "not-regular"}'` | 1 |
| utf8-strict | `_decode_plan_bytes`: `'errors="strict"' → 'errors="replace"'` | 1 |
| size-before-publication | `_decode_plan_bytes`: `'if len(raw) > MAX_PLAN_BYTES:' → 'if False:'` | 1 |
| lock-serialization | `publish_plan_buffer`: `'_admission_lock(lock_directory, deadline=deadline)' → 'nullcontext()'` | 1 |

Final driver rc **0**. Scratch driver `/home/user/.cache/fa-i02-ct94-mutations.py`, frozen log
`/home/user/.cache/fa-i02-ct94-mutations-frozen.log`, individual XML/logs and `results.json`
under `/home/user/.cache/fa-i02-ct94-mutations/`. Cache artifacts are not committed; permanent
cases, exact edit table/method and source hashes are the reproducible handoff. No mutmut
whole-module score/equivalence waiver is claimed. These selected-case proofs do **not** satisfy
STEP17: named CT94 `_run_admission_repair→_promote_validated_plan` is still absent, and no new
whole-declared-path named contract kill is reported. Q53(c) slice sensitivity remains unchanged.

### Final compatibility and static state — still not all green

After the annotation cleanup, final focused commands above were repeated:
**52 passed, 378 deselected / 2.04s**, and **534 passed, 1 deselected / 11.08s**.
Final Ruff/Mypy/Pylint are clean as shown above. Production Pyrefly has **0 errors / 5 old
warnings**; combined four-file Pyrefly still returns **1**, **59 errors / 5 old warnings**,
with all 59 ordered diagnostic matches/+3 offsets verified against E208. No suppression.

Same 22-file compatibility list as E208, final command:

```sh
uv run --frozen pytest -q --tb=short -k 'not real_workflow' \
 tests/test_verify_gate_live.py tests/test_verify_slice.py tests/test_slice_verification_runner.py \
 tests/test_workflow_role_allowlist.py tests/test_session_lifecycle.py tests/test_session_manifest_guards.py \
 tests/test_session_workspace_provisioning.py tests/test_plan_reference.py tests/test_cli_ergonomics.py \
 tests/test_s8_workflow_controller.py tests/test_s10b_cli_parity.py tests/test_inject_cli_flag.py \
 tests/test_s10c_artifact_posture.py tests/test_workflow_artifacts.py tests/test_workflow_deadline.py \
 tests/test_workflow_global_history.py tests/test_workflow_no_eval_terminal.py tests/test_eval_evidence_block.py \
 tests/test_slice_id_validation.py tests/test_s10c_workflow_exit_contract.py \
 tests/test_write_allowlist.py tests/test_write_file_expected_root.py
# 6 failed, 994 passed, 1 deselected / 92.06s; rc 1
```

The same six unwaived E208 identities/failure categories:

1. `tests/test_workflow_deadline.py::test_no_deadline_runs_the_full_pipeline` — inserted eval role;
2. `tests/test_workflow_deadline.py::test_generous_deadline_runs_the_full_pipeline` — inserted eval role;
3. `tests/test_workflow_no_eval_terminal.py::test_eval_requested_but_no_verdict_fails[linear]` — blocked-reason expectation;
4. `tests/test_workflow_no_eval_terminal.py::test_scratch_pipeline_succeeds_but_is_marked_unjudged` — required-eval exit differs;
5. `tests/test_workflow_no_eval_terminal.py::test_planner_coder_without_eval_is_also_unjudged` — required-eval exit differs;
6. `tests/test_workflow_global_history.py::test_nested_workflow_produces_two_rows` — implicit child still rejected for missing PlanRef, unavailable route unwired.

First five were independently reproduced on `5b10409` in E207; this is not a new full baseline
comparison. No new failure identity/category in this 22-file run; none waived. The original
expensive `real_workflow` case is explicitly deselected, not re-run here. No full suite/`just test`,
`just check`, isolated `d9109f4` acceptance comparison, all16 kills or independent/operator DoD
claim. Frozen logs: `/home/user/.cache/fa-i02-ct94-regressions-frozen.log` and
`/home/user/.cache/fa-i02-ct94-pyrefly-final.log`.

### New live-host inventory — proposed tests only, I03 F owns acceptance

Use reviewed operator-owned disposable Linux/Docker canonical workspaces; record deployed
commit/import hashes, run IDs, source/candidate/published hashes, real backend/PTY/session/hooks,
actual artifacts and independent outside-byte/mode sentinels. Do not use tracked plans as mutable
fixtures. No keys in evidence, no global debug-body enable. Local provider-mocked session tests
and cooperative locks do not prove deployed isolation. These rows extend the earlier inventory,
not its normalized master/independent review or the actual I03 F package. No live result assigned.
Route-dependent cells wait for the real public admission consumer; a direct helper probe is only
prerequisite diagnostics, never a substituted product PASS.

| Every new/changed producer/consumer surface | Proposed host case | Required independent observable / negative control |
|---|---|---|
| `read_plan_snapshot`, `_read_open_plan_bytes`, `_decode_plan_bytes`, `snapshot_from_bytes` | ADM-H14 | Strict bounded UTF8/size/nonempty snapshot/hash from actual selected workspace; changing opened descriptor returns source-changed. No candidate/provider/canonical mutation on invalid input through the future root; existing lexical/descriptor alias negatives retained. |
| `_canonical_parts`, `seed_plan_candidate`, `_create_candidate`, `_write_all`; existing `PlannerDispatch` consumer | ADM-H15 | Repair and eval-replan each get a fresh private exact-target seed, latest rejected bytes preserved on next attempt. Original bytes/modes unchanged until promotion; ordinary/outside-prefix denied before allocation/provider. Exclusive collision and partial/zero-write/file+directory-fsync faults preserve foreign files and clean only owned incomplete seeds. |
| `AdmissionDiagnostic`, `PlanAdmissionValidation`, `_admission_diagnostics`, `_validate_plan_admission`; both real validator consumers | ADM-H16 | Same captured text/IDs through both validators, WARN positive, structural near-miss repair, exception/zero-slice fail-closed controls; schema-check persisted sanitized projection, no messages/raw bodies. Future public caller plus full-path precheck/kill-validator producer sensitivity, not helper-only success. |
| `_canonical_parent`, `_checked_source`, `_source_identity`, `_stage_replacement`, `_install_buffer`, `publish_plan_buffer` | ADM-H17 | Real source-hash and metadata-CAS races (bytes/inode/mode/symlink/hardlink), mode/parent preservation, exclusive sibling collision, staged partial/zero writes and file-fsync/replace faults. Independent canonical and outside sentinels distinguish pre-replace unchanged from irreversible publication. No race result claimed from deny text alone. |
| `publish_plan_buffer` shared target-lock acquisition and post-replace parent-fsync/hash/mode checks | ADM-H18 | Two actual independent deployed processes/runs compete on one source: exactly one publisher wins, stale peer source-changed. Held real lock/deadline blocks without mutation. Post-replace fsync/hash/mode faults preserve resulting canonical, report typed uncertainty, never auto-rollback. Locks are not malicious-writer containment. |
| `_promote_validated_plan` and its future public `_run_admission_repair`/admission-writer/T0 consumers | ADM-H19 | Both real scoped session kinds: provider only writes owned candidate, receipt publishes exact validated bytes/IDs despite later draft mutation; non-PASS never publishes. Scoped tool failure blocks even when session terminal otherwise succeeds. Final durable admission append failure after replacement preserves canonical and dispatches zero coder/eval/T0; retry credit and owned-terminal cleanup follow the approved spec. Full-root and named CT94 producer kill pending. |

### Frozen source identity / handoff

| Path | SHA256 |
|---|---|
| `src/fa/inner_loop/plan_admission.py` | `ef4119b478a6a61c8322c06c2acb485b47f5aa3047101af4f30d5c3c093b527c` |
| `src/fa/inner_loop/plan_promotion.py` | `48ef11687cf7d9a3d677faba33d4851c24c33e9ae24d56dbaf35336eed204f04` |
| `src/fa/inner_loop/workflow_controller.py` | `471ebf85d55465e2d7da40078f582572b154fdaa47b989a3e42996800fdf6e03` |
| `tests/test_verify_gate_live.py` | `735689c25a22fefff63308187c2c4bee3818ca0a713de6ecb6aeebe55de146dc` |

Next bounded chunk: wire shared CT91/Q57 initial and eval-replan admission through these real
helpers. Persist each attempt before provider dispatch, use the same shared credit (including
failed attempts), consume scoped writer/registry failures as BLOCKED, retain rejected progress,
and clean only owned candidates at terminal exit. Admit valid non-increment input without
promotion; required non-increment repair/replan must stop scope-denied before candidate provider.
Then wire one admitted T0 plus pinned verifier/actual-eval ordering and approved unavailable nested
routing. Add full public C1/C2/C3 matrix and the actual `_run_admission_repair→_promote_validated_plan`
producer; run every retained FUNCTIONAL kill on the whole declared test path. No STEP tick,
SLICE6 completion, I02 SHIPPED, deployed PASS, security acceptance or independent/operator approval.


## E210 — 2026-10-15 remaining-contract source review; Q67 stop

Checkpoint `4b6e3625e63fe00d4ed5f6a6830bb94ec52908bd`, clean worktree before this review.
Reviewed public controller/stage/outcome/adaptive-replan, admission schema/writer, explicit spec
§§2–5, retained SLICE6 contracts, open decisions and tests-writing/mutation rules.
No production implementation was edited: first eval-requested replan from a validator-PASS plan
has no explicit pre-provider admission representation specified. See Q67 for exact options.

**Evidence-only edit declaration:** allowed files are this register, `../ledger.md`, and
`open-questions-2026-10-07.md`. Intent: implicit lifecycle choice → explicit OPEN Q67 with source
references and a real-validator counterexample; do not invent FAILs or relax closed schema.
Contract support CT74/87/91/92/94/95, GAP-06/10/12/15; no closure. Mechanism: append-only decision
and evidence notes, no runtime fallback/stub. Failure behavior: halt the affected implementation
until operator disposition. DoD: capture current source, both rejected pending encodings and the
accepted unchanged canonical state, preserve all prior evidence, commit/push own branch.
Class: C0 schema probe only; no new producer kill target because production code is unchanged.
No C1/C2/C3, mutation, static-code or deployed acceptance result is claimed from this review.

Actual `uv run --frozen python` probe (rc 0), using `validate_admission_record`:

```text
Existing canonical ADMITTED/PASS record: accepted
Pre-dispatch EVAL_REPLAN/PASS/RETRY, no candidate/promoted hash: rejected
Pre-dispatch EVAL_REPLAN/PASS/ADMITTED, no candidate/promoted hash: rejected
Preserving existing ADMITTED history without adding a pending attempt: accepted
```

Recommendation is Q67(a), reuse v1 canonical-state semantics with an unchanged durable barrier,
then record the actual candidate outcome. Not ratified; no new lifecycle semantics implemented.
Existing six pytest failures, 59 fixture-type errors, full-path kills, public admission/T0/pinned
evidence, independent/operator DoD and I03 boundaries remain as E209. No new STEP tick.


## E211 — 2026-10-16 public explicit admission checkpoint (partial)

Q67(a) and Q68(a) explicitly ratified; question/spec records updated. Actual public admission now
shares bounded repair/eval-replan credits, invokes the named publication producer, uses pinned
snapshot/T0/verifier/eval evidence and durable barriers, and blocks control-plane uncertainty.
Q68 permits recovered read errors but rejects publication-tool errors even after recovery.
51 new cases (45 public-root, six unit), only declared old-test migrations. Final focused bank
480passed/1deselected55.83s; relevant Ruff/Mypy six files clean, production Pylint10/10. Production
Pyrefly rc1/6warnings; test-inclusive59 old errors+6warnings, unwaived. Compatibility1031passed/
6failed/2deselected285.86s, same standing failure identities; separately deselected hygiene1pass.
Supplemental15 mutations detected, each33 cases/rc1/nonzero failures/zero errors/skips, actual
import provenance and unchanged source/test hashes. Not 16 normative contract×path acceptance.
Unfiltered baseline stopped after >10min in recursive old C1, no final result. Earlier interrupted
whole-path checks are not PROVEN. Unsupported invoke_workflow acquisition still absent; no STEP
checkbox, full-repo/independent/operator DoD, nested success, boundary or SHIPPED claim.

Exact declaration/mechanism/allowed files, TEST-EDITS, hashes, commands/results, mutation table
and reproducible harness, captured compatibility failures, remaining implementation and planned
ADM-H20–H25 host handoff: `notes/i02-ct91-public-admission-e211-2026-10-16.md`.


## E212 — 2026-10-16 remaining-plan architecture, Q69/Q70 and complete-path producer proof

Source-reviewed retained plan/spec/16 targets and real CLI/session binding; fixed empty STEP16,
STEP14 selector coverage and duplicate spec heading. Operator approved nonrecursive constructed
C1 leaf and selected coder-containing-only acquisition refusal, preserving planner/eval delegation.
No runtime recursion-marker change, guessed plan, public PlanRef extension, stub acquisition or
contract→test mapping. Actual child RunContext comes from SessionManager.begin_run in the same
session. New real CLI/chat matrix mocks only provider IO and verifies child identity/event/history
or no child artifacts/provider on refusal. Q55 compatibility fixture migrations preserve actual
eval obligation, mode-specific missing-verdict and deadline/exit/stage oracles.

Whole public486passed106.92s; final combined604passed117.09s; final tool91passed2.11s. Changed nine
files Ruff/format/Mypy/Pyrefly clean; full deptry/Pylint rc0 (10/10). **Final16 normative full-path
mutations plus2 supplemental real guard/allocation removals all PROVEN:** each complete486nodeid
bank, actual failures, no errors/skips, fresh UUID-bound JUnit and import provenance, one actual
producer edit, unchanged frozen source/test hashes. STEP17 checked for these exact versions only.
Table includes every duration/outcome/UUID/XML hash and tested source hashes; actual production
pipeline reproduction is in the E212 continuation of `i02-ct91-public-admission-e211-2026-10-16.md`.

Full gate is not green: baseline/candidate eight identical Mypy diagnostics, candidate authoring
five baseline plus three new export blocks, broader formatting debt, old46 archived-link failures
(changed Markdown links clean), foreign Arena hook readiness collision preserved. Full candidate
and isolated d9109f4 baseline suites are running with separate environments/verified imports;
no normal terminal manifests/comparison/disposition/acceptance claim until explicitly recorded.
Independent/operator review, retained local DoD and I03 acquisition/OS/deployment proofs remain
open. No SLICE6 complete, SHIPPED, security, managed-success or deployed acceptance claim.

E213 completes E212's preliminary full-suite status: candidate just check rc1,4994pass20fail/
12skip1xfail1053.50s; isolated d9109f4 just test rc1,4451pass11fail14skip1xfail902.76s. Both normal
summaries and complete exact-ID JUnit, no reporter abort/errors. Common4/candidate-only16/
baseline-only7 individual identities, report hashes and phase classifications in E212 note;
no dispositions/waiver or acceptance. CLI function floor separately rc0 (27/78). Six Q70 handoff
compatibility failures migrated through supported planner/eval roles without weakening handoff,
blackboard/K oracles:112passed0.78s, static clean, audited public/production bytes unchanged.
Ten other candidate-only failures, three new authoring blocks, final re-execution/dispositions and
independent/operator DoD remain. E212's completed frozen16+2 proof is unchanged.


## E214 — 2026-10-16 documentation-oracle Q71 stop

Source-reviewed current plan/DoD and E213 failures at c881621. Fresh targeted C0 stale-claim test:
1failed0.54s/rc1, exactly three evidence/audit paths. Its bare-term trigger conflates actual
alias-denial/risk evidence with obsolete capability claims. Q71 records exact source locations,
a bounded three-path/one-trigger exception proposal and required two-sided controls. Not approved;
no guard, production, immutable evidence or status change. No full-suite rerun or new mutation
claim from this review. Preserved Q69/Q70 approvals, frozen16+2 proof and all remaining DoD gates.
Current implementation is paused for the operator decision, not SHIPPED or independent acceptance.
