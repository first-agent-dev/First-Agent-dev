# Adversarial review: retained I02, then execution foundation I03

**Current disposition:** E243 below reviews remaining SLICE1/next SLICE2 against E242/e736082,
records F20–F27, repairs the RPC/command deadline defect and directly rewrites the executable plan.
E230/E231 policy decisions and Q75/Q76 remain; all35STEPS/four final duties are still incomplete.
No deployed/host acceptance or production activation. Older baselines/line references are historical.

Date: 2026-10-15. Review baseline: E201 / `f0cef5b02120f8c9a44e7bc9ef616e11d2420559`;
product source is unchanged from `d9109f4`. Document line references below identify **that immutable
baseline**, unless explicitly marked revised. Source facts were read at the named functions/callers.
This is planning work; no runtime/security/deployment acceptance is claimed.

## 1. Trajectory and sound decisions

The migration is directionally sound: retained I02 can prove a local explicit-plan gate without
pretending to isolate arbitrary shell; I03 owns that mandatory boundary and actual deployed proof.
PTY, Linux/Docker, fail-closed backend, real model eval, Q53(c) slice-level attribution, Q55/Q56,
Q58's irreversible replacement and the named deferred tracker/L2 capability are preserved.
Reuse existing SessionManager/SessionDatabase/ArtifactStore/BashExecutor/verifier facades, not
parallel session managers, journals or a new terminal stack. No CAS/overlay/backend matrix is needed.

## 2. Confirmed I02 specification defects and source-grounded gaps

A code gap already accurately named by a contract is **not** presented as a newly discovered plan
bug. The repair column says what this review actually changes.

| ID / severity | Evidence (baseline file:line) | Consequence / repair |
| --- | --- | --- |
| R02-01 HIGH — initial attempt has no honest schema kind | `notes/i02-to-i03-scope-migration-2026-10-15.md:83–102`; I02 `:479–486` | EXPLICIT-only I02 is told ACQUISITION is I03-reserved, but its initial attempt can only be acquisition/repair/replan. New normative spec adds EXPLICIT_INPUT and cross-field invariants; old schema is historical, not a second authority. |
| R02-02 HIGH — exact schema is not implementable from an unlisted enum | migration bank `:103–111`; `notes/open-questions-2026-10-07.md:1079–1109`; `src/fa/inner_loop/plan_ids.py:760–1210` and `slice_verification.py:667–777` | Supply the concrete per-validator tables and strict JSON type checks, including rejecting bool integers. No arbitrary error text/code or speculative managed bootstrap success. Q62 is explicitly an implementation-spec gap, not an operator-policy decision. |
| R02-03 HIGH — preflight needs a side-effect-free workspace resolver | I02 `:471–474`; `src/fa/cli.py:280–316,1364–1368,1432–1443` | Current lifecycle resolution claims session/run and can prepare workspace; current path check uses CWD. Name a read-only manager method, order task/inject/PlanRef checks before lifecycle, then compare the allocated root. Do not 'resolve' via begin_run. |
| R02-04 HIGH — impossible rejection artifact obligation | I02 `:503–510`; `src/fa/inner_loop/workflow_controller.py:1885–1904`; `src/fa/session/manager.py:408–444` | Cannot both reject malformed run ID before paths and persist admission under it. Split malformed request/no artifacts from safely addressed PlanRef/BLOCKED artifacts, and storage failure/no persistence claim. |
| R02-05 HIGH — requested order contradicts Q55 and permits stale tail planning | I02 `:439–446,503–504`; controller `:1426–1442,1774–1837`; `tests/test_verify_gate_live.py:164–170` | Existing normalizer relocates eval and supports repeated coders. Specify that exception, retain repeated-coder tests, reject ordinary planner-after-coder/duplicate ordinary planner, and use bounded adaptive replanning instead. This is an explicit new limitation, not a scheduler hidden inside admission. |
| R02-06 HIGH — observe can waive the newly required integrity floor | I02 `:434–437,508–510,556–558`; controller `:551–588,1161–1165` | Existing observe returns model route before verifier errors; eval IDs reread the mutable target. Pin one admitted snapshot for verifier/eval; post-coder hash/storage/missing-evidence errors reach real eval then block both modes. Keep ordinary determinate gate judgment advisory in observe. |
| R02-07 HIGH — no binary T0 failure/order contract | I02 `:461–464`; controller `:318–359,362–391,1057–1081`; real fixture `tests/test_verify_gate_live.py:548` | CT86 already correctly requires write-once/topology; it lacks what to do on capture/storage failure. Name run-local baseline state; failed T0 blocks before coder, legitimate red baseline allowed, no recapture after repeated coder/replan. Move fixture plan inside its disposable workspace. |
| R02-08 HIGH — future early-error handling could suppress eval | controller `:1093–1141,1448–1477,1774–1800`; I02 `:483–486` | Any nonzero coder StageResult exits current loops immediately. Require post-coder integrity/IO errors as typed attempt evidence, not an early nonzero return; eval then nonzero terminal. Deadline exhaustion is a visible failure, not an impossible promise of model execution. |
| R02-09 MEDIUM — full-suite disposition has no executable comparison contract | I02 `:568–571`; E174 and E192 historical evidence; `justfile:131–183` | Name actual just gates, isolated source baseline and identical environment, complete manifests/normal summaries, exact nodeid+phase comparison, changed-file gates and explicit reviewed baseline dispositions. Aborted/no-summary run cannot pass; acceptance report has a named future path. |
| R02-10 HIGH — target writer/path guarantees stop short of alias/race handling | I02 `:488–502`; `src/fa/inner_loop/profiles.py:275–313`; `tools/write_file.py:15–58`; controller `:436–475` | Exact scoped writer cannot delegate to unchecked write_text after a string prefix check. Require descriptor-rooted no-follow IO, single-link regular target, immutable validated promotion buffer, complete prior-artifact validation and concurrent append proof. Preserve pre/post-replace distinction. |

**R02-11 HIGH — non-executable historical DoD command (second pass).** Baseline I02
`:572–573` requires `git diff 3c0caad`; `git cat-file -e 3c0caad^{commit}` confirms the object
is absent in this checkout. Replace the runnable comparison with available d9109f4 and preserve
Q45-B/current extractor semantics; no clean historical diff is inferred from an unavailable object.

Other existing gaps confirmed, not new discoveries: direct budgets coerce via int at controller
`:1401–1412` and CLI `:1404–1409`; nested invocation passes the parent's RunContext at
`tools/workflow_tool.py:463–484`; terminal helper allows `workflow_exit_code(0,None)` at controller
`:1840–1844`. The revised implementation spec includes shared strict budget validation, unavailable
nested negative and a nonzero missing-terminal oracle. These are not proofs that new code exists.

## 3. I02 changes and acceptance boundary

The active I02 CT/STEP IDs, seven sections and 16 SLICE6 FUNCTIONAL producers remain; no progress
box is newly checked. Details live in `i02-explicit-admission-spec-2026-10-15.md`, linked by the
increment. Historical CT92 text is retained with a superseded banner. Q43's historical accessor
question is not ratified: current `plan_ids.py:218–255` is already strict; I02 uses extractor-origin
IDs and does not change those semantics. Q59/Q60/Q63 stay pending.

I02 local SHIPPED still needs real implementation, amended CT66 classification, all local/mutation
proofs, usable full-suite/type-gate disposition and independent/operator signoff. It does not need
I03's successful nested workflow, kernel isolation or main-host results. No integrated/security
deployment readiness follows from I02 local SHIPPED.

## 4. Suspicions / proof obligations — not confirmed exploits

- Arbitrary shell can race or replace local I02 paths; no-follow/CAS only detects defined cases.
  A successful escape on the eventual Docker profile is **not** established by source reading.
- Kernel/cgroup/daemon/filesystem behavior, fsync/power-loss durability and cross-process fencing
  require real profile/filesystem fault tests. Existing patterns are not that evidence.
- E174 reporter failure identities and nine Mypy diagnostics are historical blockers until rerun;
  this review has not reproduced or disposed of them in a supported environment.
- New safety restrictions on ordinary planner ordering need explicit implementation/review/help
  coverage; no existing valid user invocation is silently claimed backward compatible.

## 5. I03 review

The old outline was honest about incompleteness, not a deliverable implementation plan. Its
six groups now become concrete SLICE1/2/3/4/5/6 ordered A/B/C/**E/D**/F, with files, typed contracts,
error/order/commit paths, tests, 17 declared FUNCTIONAL kills and binary DoD. This is conditional
planning completion, **not** a claim that unresolved policy choices or deployment are ready.

| ID / severity | Evidence (baseline file:line) | Consequence / repair |
| --- | --- | --- |
| R03-01 HIGH — implementation readiness gap, already acknowledged | `increments/increment-03-execution-workspace-foundation.md:1–15,32–79` | Zero slices/no CT/test/producer briefs cannot be handed to a coder as executable. Replace with six concrete briefs and a linked mechanics spec, retaining OUTLINED and explicit affected-slice decision gates. |
| R03-02 HIGH — successful nested path overwrites parent namespace | `src/fa/inner_loop/tools/workflow_tool.py:463–484`; controller `:1888–1891`; `session/manager.py:408–444` | Different child run_id is passed with parent's run_log_dir. Allocate real child begin_run and keep existing DB; inherit scoped workspace writer, not parent artifact path or another lease. |
| R03-03 HIGH — timeout/transport uncertainty can replay side effects | `tools/run_bash.py:202–216,329–347`; `cli.py:1931–1959` | Executor error/timeouts fall through to subprocess. Managed operation reservation, explicit uncertainty/inspect/cancel and no alternate host runner; unchanged old fallback is not safe compatibility. |
| R03-04 HIGH — optional PTY wire loses timeout fact | `runtime/pty_pool.py:73–87`; `runtime/server.py:62–81`; `runtime/bash_executor.py:111–118` | Server omits timed_out and remote client defaults it false even if a response contains true. Version optional wire, preserve all receipt facts, or use the thin cell worker. HTTP health is not process-tree terminality. Actual source-body projection probe confirmed the loss. |
| R03-05 HIGH — first project code precedes tool boundary | `cli.py:147–156`; `session/manager.py:292–295`; `workspace_bootstrap.py:263–289`; `scripts/fa-entrypoint.sh:153–171`; `scripts/bootstrap/workspace.py:13–17` | Readiness/import/hooks run early and fail-open. Whole prologue/provisioning routes must acquire managed view before first instruction; integrate closure before nested C1. |
| R03-06 HIGH — controller launch can import project source | `scripts/fa-entrypoint.sh:231–248`; `scripts/fa:36–74`; `Dockerfile.fa:86–98`; `src/fa/cli.py:3842–3849` (no module guard) | Remove workspace-first launches/editable install, use new actual isolated entry module, verify immutable install before startup. A runtime sys.path assertion cannot undo already executed .pth code. Do not invent nonexistent -m fa entry or silent -m fa.cli. |
| R03-07 HIGH — lifecycle target is not current behavior | `session/manager.py:195–208,211–239`; `tests/test_session_lifecycle.py:195` second-owner rejection; outline `:65–67` | Explicitly support new session reference to registered old workspace, with workspace-level writer exclusion and preserved session DB/run claims. No silent deletion of reverse-ownership guard or transfer platform. |
| R03-08 HIGH — read/metadata helpers hide additional project Git | `workflow_controller.py:774–803,909–911`; `tools/run_bash.py:56–65`; `tools/mutation_guard.py:51–69,115`; `hooks/intent_guard.py:272–280,304–316`; `memory/_safe_walk.py:130–167,267–268` | Fixed argv/read-only purpose does not prove no project config/helper execution. Add inspected inventory including pre-tool/search/transaction/Git-hook paths; use supervised metadata or snapshot data. Actual Git-hook exploit is not claimed. |
| R03-09 HIGH — ordinary chat subagent route is not excused by workflow absence | `subagent_runner.py:293–358`; `tools/__init__.py:145–151,281–300`; compose `:118–135` | run_stateless executes project shell and injects X_FA_PROXY_TOKEN. Route through cell, remove controller credential injection, fail closed on unsupported credential-dependent behavior; registry fallback cannot restore host shell. Future workflow children remain disabled pending inherited-boundary proof. |
| R03-10 HIGH — publication atomicity/recovery underspecified | outline `:38–54,68–71`; `workspace_bootstrap.py:195–236`; controller `:436–475`; `session/manager.py:130–145` | Existing one-file replace/locks are not multi-file transactions or descendant barriers. Define immutable revisions, current pointer, canonical projection, exact intent phases/forward recovery and pinned-reader visibility. Keep Q58/bootstrap irreversible semantics separate; no live overlay lowerdir. |
| R03-11 HIGH — old live oracle confuses shell failure with spawn failure | `notes/e2e-live-verification-register.md:48`; `slice_verification.py:332–358` | A missing binary inside an already started shell is exit 127/FAIL. Actual source-body probe confirmed. Keep producer row but replace scenario with genuine launch failure; don't 'prove' ERROR using the wrong host setup. |
| R03-12 HIGH — source/input/pin/profile assumptions are not specified | outline `:68–71`; migrated CT97 body preserved at commit 5530496; `worktree_manager.py:145–264` | Freeze conservative copy/type/link/caps/protected path rules, preserve dirty/index input, explicitly document private-Git/history and secret/dependency limits. Real FS/cgroup/UID/profile and maintenance approval remain gates, not fake-executor evidence. |

The new spec also separates truthful OS execution/revision binding from semantic trust in a
project-authored pytest report. Structured JUnit is not adversarial test attestation or L2 VERIFIED.
Do not add a cryptographic verifier platform to pretend otherwise.

### Exact remaining blockers and scope limits

1. **Q59**: exact opt-in guaranteed-workflow behavior/name versus model-mediated invocation.
   Ordinary chat remains advisory; no default forced-workflow policy has been selected here.
2. **Q60**: approve/amend stable-ID selection/clarification/controller-rendered bundle, supported
   metadata/statuses and exact proposed managed admission v2 table in spec §7. Values are supplied
   as a reviewable proposal; they are not unlisted guesses delegated to the implementer.
3. **Q63**: exact live enum/BLOCKED reason-code invariant before final package/fixtures.
4. **Operational acceptance**: immutable installed images, approved source/cache/input policy and
   compatibility limits, real UID/UDS/cgroup/local-filesystem/profile and maintenance cutover. Actual
   implementation/tests plus authorized main-host acceptance must satisfy them; this review cannot.

No code implementation or readiness status is substituted for those approvals. Scope remains one
single-host authority, one backend/family, PTY, materialized views and existing facades. Core brief
mechanics are concrete; the whole increment is **not approved for unconditional dispatch**.

## 6. Validation log

Results are appended only after checks execute. Runtime pytest/type/Docker results are not implied
by pure document/extractor/AST validation.

First step checks: actual stdlib leaf precheck: I01 7 slices/1 diagnostic, I02 7/8,
I03 outline 0/7; all zero FAIL (warnings are not runtime proof). I02 retains exactly 16 SLICE6
FUNCTIONAL and unchanged checked STEP markers. Closed validator rules match actual source
constructors. Executed actual-source AST normalizer/exit helper: eval relocation and missing-state
exit 0 reproduced. Initial AST harness lacked lineno; corrected with ast.fix_missing_locations,
rerun PASS. `git diff --check` PASS. No package imports, pytest, Mypy or Docker tests executed.

Second-step bounded probes: actual RemoteRuntimeExecutor.run and actual PtyResult class, with a
fake HTTP response/no network, drop timed_out=True to False. Actual _run_one body executes a
nonexistent command under minimal PATH and returns exit 127/FAIL. `3c0caad` object check fails as
reported; no historical baseline result is inferred. Python is 3.11.2; python3.13/uv/pytest/Docker
are absent. No supported package/runtime/security/type suite executed.

Actual kill-parser AST validation initially used reversed arguments; corrected the spec/call to
`validate_kill_directives(text, ids, path=…)`. An overbroad assertion then included unchanged I01,
which predates FUNCTIONAL kill directives; narrowed new kill coverage to I02/I03, not edited I01.
Final actual leaf precheck: I01 7 slices/1 diagnostic; I02 7/8; I03 6/6, all zero FAIL. Actual
I02/I03 kill grammar/ownership PASS: I02 40 FUNCTIONAL overall (16 in SLICE6); I03 17. New I03
producer paths remain planned, not source-presence/mutation proof. All I03 checkboxes unchecked.

Final cross-document checks PASS: eight newly added/changed link occurrences and their anchors;
question Status lines unchanged; I02 CT IDs/classes and checked STEP markers unchanged; exact
historical SLICE7/removed-DoD body unchanged; original live register/schema/I01 byte-identical;
roadmap active I01 and I04–I06 rows unchanged; no src/tests/scripts/knowledge changes; ledger
append-only and whitespace clean. Executed the updated checked-in extractor example successfully.
First major step commit 5687d9e was pushed and remote SHA verified; second step records E203.

**Verdict:** retained I02 has a materially more executable local spec/DoD, but is not proved done.
I03 now has concrete conditional briefs, not an approved/deployed implementation; exact Q59/Q60/Q63
and operational compatibility/profile dispositions plus all implementation/runtime/host evidence
remain. No blanket READY, SHIPPED, VERIFIED or live PASS is assigned by this review.


## E230 — I03 finalization review, 2026-10-16 (current source 1132eee)

**Trajectory verdict:** enough scope to reach a deployed whole-plan workflow demonstration, NOT the
full roadmap's per-slice/tracker/L2 loop. The latter was explicitly moved to a named successor and
must not be accidentally advertised as delivered. Foundation is still large (17 FUNCTIONAL across
six slices); retain one backend/authority/materialized-copy implementation, not optional platforms.
No additional runtime subsystem or foundation implementation is introduced by this review.

### Confirmed plan defects / stale assumptions and direct repairs

Line references in the evidence column are frozen `1132eee` BEFORE this review, unless a source
module is named (runtime files remain unchanged). plan = increments/increment-03-execution-workspace-foundation.md;
spec = notes/i03-execution-workspace-spec-2026-10-15.md. Updated normative sections are in that spec.

| ID | Severity / confirmed finding | Evidence file:line | Correction / binary future oracle |
| --- | --- | --- | --- |
| F01 | High: no explicit real-provider witness; local/mock deployed cases could satisfy vague live E2E wording | I03 plan:24–28,234–259; spec:483–497 | §9.1 requires unmocked direct AND outer-chat nested useful-code workflows; actual calls, effect/tests/artifacts/identity; no invocation or replay is not PASS |
| F02 | Medium: child allocation treated as absent, proposed duplicate helper; baseline/Q73 stale | plan:204–207; src/fa/inner_loop/tools/workflow_tool.py:387–403,487–533; src/fa/inner_loop/workflow_controller.py:613–645 | Reuse _child_run_context and actual SessionManager authority; preserve Q70 non-coder and Q73 floors; zero double allocation/parent overwrite |
| F03 | High: protocol cannot implement promised PTY facade, exec lacks session ID, no interrupt/close/list | spec:68–87,124; src/fa/runtime/bash_executor.py:18–27,53–69 | §2.1 exact PTY wire mapping and namespaced session; four methods tested, persistent state within episode, no replay on loss |
| F04 | High: opaque grant required but absent from exact envelope; read pins conflicted with blanket current-generation mutation rule | spec:70–97,110–114,163–165 | Explicit redacted capability and OWNER/READ/WRITE grants; server handoff revokes late parent mutation, pins survive generation advance |
| F05 | High: supervisor state below controller-writable state; canonical compose bind remains writable, container/host paths differ | spec:150–155; docker-compose.fa.yml:100–111; scripts/fa:36–45 | Root-owned unmounted StateDirectory; canonical binds RO; UDS only; approved three-way path mapping, real mount/UID negative proof |
| F06 | High: canonical-path alias rule omits overlapping workspace roots and stale canonical re-import | spec:152–165,185–186 | §4.1 rejects ancestor/descendant/bind aliases, rebind and stale-import ambiguity; two writer processes cannot overlap same filesystem domain |
| F07 | High: Q58 irreversible replace has no exact recovery phase/schema, unlike ordinary pointer commit | spec:245–276; src/fa/inner_loop/plan_promotion.py:195–221 | §5.1 distinct REVISION/PLAN/BOOTSTRAP discriminator and hash-based ambiguous-PREPARED recovery; fault every boundary, never delete/rollback committed bytes |
| F08 | High: after coder seal, next repair/replan source/view and publication timing unspecified | spec:223–228,301–307,336–339; src/fa/inner_loop/workflow_controller.py:1295–1317 | §6.1 transition table; never reopen sealed PTY/view. Q74 checkpoint-vs-workflow-end is a genuine operator policy question, NOT silently chosen |
| F09 | High: bundle ID has no upload/validation producer; generic protected-path denial conflicts with existing scoped candidate writer | spec:83–92,266–275; src/fa/inner_loop/tools/write_file.py:113–136 | prepare_bundle→stored validated ID→no-clobber install; narrow CANDIDATE grant outside canonical/control mounts; exact scoped plan publish |
| F10 | High: wrapping stage misses prior provisioning; old manager cleanup can remove a newly committed registered root | src/fa/session/manager.py:293–296,316–329; src/fa/cli.py:150–159,2214–2227 | Inject provisioner BEFORE _new_session; propagate non-ready; preserve supervisor-owned roots after later session failure; backend-down executes zero project instructions |
| F11 | Medium: planned edit op risks replacing existing fuzzy/first-match semantics with a second privileged implementation | spec:83–84; src/fa/inner_loop/tools/edit_file.py:120–135 | Existing controller fuzzy helper produces exact replacement+hash; service only bounded rooted IO; no fake kernel-CAS claim vs arbitrary background writes |
| F12 | High: context provider cannot capture conversation merely from state_ref; current history is loop-local | src/fa/cli.py:1644–1659; src/fa/inner_loop/coder_loop.py:600–623,1847; src/fa/inner_loop/state.py:339–369 | §7.1 pre-dispatch snapshot callback after compaction; consume once via PlannerDispatch; no repeated raw history/system schema/credentials or goal-only false inheritance |
| F13 | High: host tests required in slices1–5 but fixture review only at slice6; final-review scope/main-host timing ambiguous | plan:77–86,228–259; spec:437–456 | Separate local tests/integration from final e2e/I03 helpers; required non-skipped accumulated kernel/mutation proof before acceptance, no early main-host runs |
| F14 | High: immutable-source verification omits environment/report paths and migration binding; existing public C1 fixtures would no longer work | spec:301–323; src/fa/inner_loop/slice_verification.py:539–581; src/fa/inner_loop/workflow_controller.py:1271–1283 | §6.1 scratch/dependency compatibility tests, execution sidecar and mandatory managed receipt binding; preserve T0 bytes/lineage and honest C1 classification |
| F15 | Medium: declared TESTS omit existing lifecycle suite already in verify, and changed nested/deadline/history/runner seams | plan:110–114,182–186,216–219 | Add relevant existing paths to owning slices; full declared paths under kills, no per-contract selector mapping |
| F16 | High: safe immutable launch has no exact existing build change or cutover/downgrade constraint | Dockerfile.fa:86–98; spec:34–52,488–492 | Reuse uv.lock/uv sync with --no-editable, test imports; §9.1 approved quiescent cutover and forward-compatible recovery, no automatic legacy restart after new-format commit |

### Genuine unresolved decisions / suspicions (not runtime defects proved here)

- Q59: advisory-only default or default plus explicit router-only required-workflow option. Proposed
  success guarantee is an ACTUAL successful coder-bearing/eval child, not mere invocation count.
- Q60: proposed stable selection + fixed three-file bootstrap, exact v2 schema/render fixtures.
- Q63: exact four live-result values and mandatory BLOCKED reasons; source status vocabularies differ.
- Q74: when ordinary source edits publish; current behavior keeps even failed-stage edits, but
  workflow-end atomic publication would require a different unpublished-source/base representation.
- Actual main host Docker/cgroup/UID/seccomp/FS, offline cache/toolchain and provider readiness remain
  unverified operational inputs. No host failure or compatibility success is inferred from source.
- Ordinary same-owner background shell writes are not a kernel file-CAS transaction; seal binds
  actual final bytes. No stronger intra-owner lost-update guarantee is claimed without a mechanism.
- Malicious project tests can forge their reports; supervised receipt binding is not correctness
  attestation, L2 VERIFIED or calibration. Preserve Q53(c) full-slice attribution limitations.

### What is genuinely sound

One host authority/backend, existing SessionManager/DB, fixed profiles, materialized copies, actual
cgroup terminality before export, no rollback of irreversible publication, role-independent boundary,
Q70 narrow unavailable guard, Python-only controller/supervisor, and end-of-I03 broad/deployed review
are appropriate. No CAS/overlay/backend matrix, proxy platform, second workflow/session engine,
mandatory debug-body suppression, automatic escalation or parallel scheduler is added.

**Plan verdict:** mechanics revised directly; whole-increment unconditional dispatch remains blocked
until explicit Q59/Q60/Q63/Q74 decisions. Current planning review is NOT future independent review
of unwritten implementation/fixtures and assigns no source/live PASS or runtime checkbox.


### E230 executed planning checks (not runtime acceptance)

Actual stdlib-only plan_ids extractor/precheck and AST-loaded actual pure kill parser/validator:
6slices,17FUNCTIONAL, all existing CT IDs/classes preserved, CT96/97 original target lineage,
CT108 changed deliberately to existing _child_run_context.35STEP boxes all unchecked. Zero FAIL;
6existing undeclared cross-increment-reference WARNs retained, not hidden. All declared TESTS and
verify commands extract, including added existing lifecycle/nested/deadline/history/runner paths.
`python scripts/check_doc_links.py`:308Markdown files, no broken links; git diff --check clean.
Initial checker mistakenly iterated PrecheckReport rather than .diagnostics; corrected and rerun,
not runtime/proof evidence. Python3.11.2 here is below package>=3.13; pytest/uv/Docker are absent.
No supported-runtime suite, mutation, host/profile/deployment or real-provider check is claimed.
Only worklogs files changed; source/tests/scripts/knowledge/deployment/I02 plan/status untouched.

## E231 — Operator dispositions and actual-surface reuse, 2026-10-16

**Immutable review inputs:** plan/spec at `ffc8b6ac23981a0b477bf91155079524b251f9c6`; runtime/test
source unchanged from I02 `a32a72f` (also present at1132eee). The operator's actual answers, not a
review recommendation, resolve Q59/Q63/Q74. Q60 is delegated engineering judgment after source
verification, NOT blanket operator ratification of the earlier packet or implementation authority.

| Confirmed input / file:line | Selected correction and ownership |
| --- | --- |
| Frozen spec `:617–626,707–717` proposes new required-workflow router. Actual `src/fa/inner_loop/expansion.py:10–23`, `routing.py:3–13`, `cli.py:2408–2437` already provide escalation/injection seams. | Q59 advisory/manual PLUS existing experimental suggestion. Remove new required mode/success guard, preserve current configuration/expansion/--inject behavior. Actual invocation remains an E2E witness obligation, not a guaranteed production route. |
| `src/fa/inner_loop/tools/workflow_tool.py:387–403`; `planner_dispatch.py:17–55`; `workflow_controller.py:1181–1383,2231–2270,2370–2428`; `coder_loop.py:379–408`. | Q60 extends existing child allocator/PlannerDispatch/stage/SessionOutcome/admission/repair, ONE machine and shared budget/history. New choice/resolve/render helpers are pure; no pre-workflow planner replay or duplicate engine. Spec §7.0 names actual vs new seams. |
| `src/fa/inner_loop/admission_schema.py:93–104,129–151,154–182`; frozen spec `:652–684` carries v1 invariants into v2 without the selected-plan hash join. | Reserved ACQUISITION/source_kind values are not producers. v1 requires non-EXPLICIT ADMITTED promoted hash. New v2 selection explicitly binds captured source without a fake promotion; bootstrap requires real committed receipt. Null/blocked choice, failed install and uncertain receipt cases are explicit; v1 stays byte-for-byte compatible. |
| `src/fa/inner_loop/tools/prepare_pr.py:186–283`, `cli.py:1749–1796,2285–2290`, `pr_draft.py:45–118`. | Actual pr_prepare producer found, not tools/pr_prepare.py. Reuse current-session draft/digest/IntentGuard; bounded existing controller artifact IO, no new supervisor op/draft subsystem. Registry adds draft tool AFTER profile: explicitly filter ACQUISITION, preserve ordinary/scoped Q68 behavior. |
| Frozen spec `:791–795` mandates BLOCKED reason variants; `:529–541` leaves checkpoint policy conditional. | Q63 exactly four states, optional short commentary on ALL/no enum or required BLOCKED reason. Q74 per-stage/episode checkpoint after terminality/security, including failure; no rollback promise or workflow-end unpublished branch. Rewrite active schema/plan/spec/questions/roadmap/HANDOFF directly; preserve older proposals as clearly historical. |

**Engineering design, not discovered production code:** private ManagedAdmissionEntry, new enum
branch, strict metadata/choice helpers, v2 cross-fields, controlled three-file renderer, live-history
snapshot handoff and managed draft IO remain construction/test obligations. Actual source inspection
found the existing seams above, not those future implementations. Existing permissive skill-frontmatter
loaders are NOT reused as fail-closed admission validators. Reuse existing PyYAML/MarkdownIt/plan
grammar machinery with a small strict adapter; fixed roadmap schema/status table belong to controller.
No broader ledger parser, route policy, second planning framework or platform backend is added.

**Verdict:** finalized plan is adequate in scope for the mid-roadmap CURRENT whole-plan live explicit
AND nested workflow target. Not the deferred per-slice scheduler/STEP tracker/L2 VERIFIED target.
No remaining Q59/Q60/Q63/Q74 policy gate; I03 remains OUTLINED/unimplemented. Four transferred
acceptance duties and all35 steps remain incomplete, all17 FUNCTIONAL IDs/classes preserved.

**Actual E231 planning checks:** stdlib actual-source extractor/precheck + pure kill-validator leaf
harness (`/home/user/.cache/i03-review/validate.py`), 6 slices/17 FUNCTIONAL/35 unchecked steps,
0 FAIL/6 retained cross-increment WARNs; source AST checks confirm current inventory symbol ranges.
Original CT96 handler/CT97 stage-boundary lineage intact; CT108 uses existing _child_run_context.
`python scripts/check_doc_links.py`:308files/no broken links. `git diff --check`:clean after EOF repair.
No src/tests/scripts/knowledge/deployment changes versus1132eee; schema example markers preserved.
Python3.11/no uv/pytest/Docker: no supported-runtime suite, kernel/isolation/mutation/deployed test
run; no live result assigned. Environment/toolchain/host/profile approval, source declarations and
actual per-slice construction/proof, independent final helper/evidence review, authorized normal
main update and unmocked direct+nested witnesses remain required implementation/release work.

## E232 — I03 implementation starts: installed-entry/audit chunk, 2026-10-16

**Authority/scope:** operator explicitly authorizes careful implementation. No blocking policy
question surfaced in this chunk; Q59/Q60/Q63/Q74 remain resolved. Contract CT98, review gap F16
(immutable install/launch/cutover), owning TESTS adjustment F15. Not SLICE1 completion: protocol,
supervisor/cells and all launcher/image/cutover changes remain absent. No STEP tick/status change.

**Source before edit:** cli.py ends with a callable main but no module main guard; scripts/fa:59
injects repository PYTHONPATH for help; fa-entrypoint.sh:237 injects workspace src; Dockerfile.fa:97
uv sync lacks --no-editable. These production paths are intentionally UNCHANGED in this chunk.

**Implemented idea/mechanism:** new src/fa/controller_entry.py:33–119 provides bounded install-data
audit, no dependency/project import; `-I -S <trusted-entry-file> --check-install <absolute-venv>`
is the pre-site build check. Deny executable/editable/external .pth, egg-link, root/nested startup
customization, external package symlinks, ambiguous/system site config and editable metadata.
Internal .pth directories are permitted; ZIP/file .pth import layouts are unsupported under the
selected unpacked-wheel profile, not silently trusted. Runtime :122–150 requires isolated Linux
Python>=3.13 in a closed venv, installed entry origin, approved stdlib/venv path and loaded module/
namespace origins. :153–173 is a REAL main guard/dispatcher, checks closure before CLI import,
sets trusted venv CWD and invokes existing fa.cli.main. Sanitize audit failures to exit78 and one
fixed error; no fallback. Immutable frozen image and pre-site audit remain the trust root: late
runtime assertions CANNOT undo Python startup code. This does not sandbox project execution yet.

**Tests-writing:** C0 strict install-data/loaded-origin tests; C2 actual noneditable wheel build,
locked offline install and real CLI help; C3 cwd/PYTHONPATH/user-site poison, unsafe launch, nested
customizer/deep symlink/loaded-origin faults. Wheel/source bytes explicitly equal in fixture. No
provider mock/helper returning success substitutes for CLI execution. Fake install DATA fixtures
are C0/C3 only, never claimed runnable product environments. No final live fixtures added early.

**Actual checks:** Python3.13.16 local source build (SSL/SQLite/zlib verified, other optional modules
not all present; not deployment readiness). New tests30PASS; broader new+entrypoint+plan/parser/
skill suites174PASS in6.79s. Ruff check PASS; Ruff format2files unchanged; strict targeted Mypy
2filesPASS; source-tree Mypy170filesPASS. Earlier attempted runs had environment/pre-collection
errors, then19PASS/4 offline fixture setup errors and static findings; all fixed, not accepted as
inherited, skipped or counted as kills. Toolchain/caches/binaries stay outside Git.

**Developmental mutation evidence (NOT normative CT98 PROVEN):**
[lossless command/log/JUnit/hash bundle](evidence/i03-e232/controller-entry.json.gz). Entire new
30-test path runs for baseline, EVERY mutation, restored baseline. Each mutant exits1 with actual
CALL assertion failures, no setup/collection/runner errors, no skips; source restored hash exact.

| Removed mechanism | CALL failures / cases |
| --- | --- |
| _main → _assert_controller_import_closure (declared CT98 producer) | 4 /30 |
| _assert_installation → _audit_site | 17 /30 |
| _audit_pth unsafe import/external-path guard | 5 /30 |
| _audit_site → _audit_customization | 4 /30 |
| _audit_site deep external-symlink guard | 1 /30 |
| _assert_controller_import_closure → _assert_loaded_origins | 2 /30 |

Baseline/restored each exit0/30PASS. No equivalents accepted, no suppression/test narrowing.
The FULL declared SLICE1 TESTS also include still-unimplemented supervisor/boundary paths, so no
full-slice kill is claimed; do not assign CT98 IMPLEMENTED/VERIFIED or STEP1 complete from this.

**Final live-case planning (not implemented/executed):** preserve CT98 producer lineage and add
case rows in the reviewed SLICE6 package for image build/install, host wrapper help/delegation,
compose-exec, entrypoint auto-run and session launches. On approved disposable/main hosts, prove
actual immutable package/dependency origins and trusted CWD with poisoned project src/PYTHONPATH/
user site; pre-site executable-pth rejection must leave a host sentinel absent. Verify real frozen
noneditable image, read-only controller code, no legacy editable startup, exact deployed SHA/image/
config/artifacts. Run/session project behavior additionally requires SLICE1–4 supervised boundary:
backend-down must execute zero project instructions; no premature host run to test this entry alone.
Independent final fixture/oracle design review precedes new e2e/I03 helpers, review actual helper
code again before main-host use; real-provider direct+nested final witnesses and allfour transferred
acceptance duties remain incomplete. Existing live-result schema/READY/I01 remain unchanged.

**Next bounded implementation:** frozen protocol/types/strict profile contracts plus continued CT98
image/wrapper/entrypoint/bootstrap inventory/cutover in dependency order. Re-declare exact scope and
source behavior before editing; no production activation until SLICE1–4 closure and authorization.

Final actual planning guards: extractor/precheck/kill grammar0FAIL/6retainedWARN; unchanged6slices/
17FUNCTIONAL/35uncheckedSTEPS, current CT98 producer call exists EXACTLY once. Evidence8runs/source/
tests/uv.lock hashes validated. Doc links309filesPASS; staged diff/whitespace inspected clean.
CI uses setup-uv + uv sync --locked --extra dev, matching offline installed-fixture prerequisites.

## E233 — Stop-rule finding F17: grant-reply replay policy is not closed, 2026-10-16

**Source verified before edit:** restored working files exactly match pushed15dc7cb; stale local
d910 Git metadata safely aligned ONLY after a separate-index diff and extra-file check found zero
differences. No user/source bytes overwritten. No src/fa/execution directory or protocol/supervisor/
client exists. E232 controller_entry/test/evidence remain exact.

**F17 — confirmed specification join defect, not proved runtime vulnerability.** Frozen15dc7cb
execution spec:89–100 requires namespace/capability binding; :132–147 returns capabilities from
grant operations and gives inspect only ExecutionReceipt; :241–251 promises typed per-op journal
results/non-exec inspectability but prohibits durable grants and revokes them on restart. Handoff
revokes original actor before reply delivery; losing that reply leaves no ordinary authorized
recovery route. A request ID is explicitly NOT authorization. Storing the literal wire reply would
violate memory-only secrets; calling non-exec output an ExecutionReceipt would fabricate bindings.

**Policy requiring disposition:** whether exact originally-authorized completed-request replay may
return its cached grant reply AFTER that operation revoked the supplied proof. Recommended Q75(a)
is memory-only exact-reply replay with principal/namespace/input/original-proof binding, no mutation
or renewed grant. Q75(b) retains strict revocation and needs maintenance after lost handoff ack.
Both retain one nonsecret durable journal; no automatic secret reconstruction after restart.
Recommendations are NOT ratification. Current spec/plan/roadmap/tracker/HANDOFF explicitly paused;
no protocol code, permissive authority, live test or production activation introduced.

**Future binary proof:** original/mismatched principal, namespace, request/input and proof; cached
reply after handoff; restart/cache loss fail-closed; all non-exec result types; no durable/log/error
tokens and exactly one execution/grant issuance. Unit injection stays C0; actual dispatcher/
authority composition plus full-slice CT99/CT100 mutations and kernel/live acceptance remain required.

**Actual checks in this stop checkpoint:** documentation-only. Source/tests/deployment/lock and
E232 evidence unchanged versus15dc7cb. Pure actual-source plan extractor/precheck/kill grammar and
document-link/whitespace checks recorded at E233 closeout. Restored environment is Python3.11.2
without uv/pytest/Docker; no supported-runtime/security/mutation/live suite executed or credited.

E233 actual closeout: stdlib actual-source planning leaf6slices/17FUNCTIONAL/35uncheckedSTEPS,
0FAIL/6retainedWARN; IDs/classes/kill grammar preserved. Doc checker308filesPASS. Initial EOF blank
line finding repaired; final diff whitespace clean. No source/tests/scripts/knowledge/deploy/lock
changes versus15dc7cb; E232 compressed artifact exact and source/test proof hashes match.

## E234 — Q75(a) ratified; bounded replay/type foundation, 2026-10-16

**Disposition:** the operator selected `exact_cached_replay`. F17's policy join is resolved by
Q75(a); the historical E233 finding/alternatives remain above. Spec §§2/3.1 now separate nonsecret
journal results from private in-memory grant replies and use original-operation replay for
non-exec observation. No viewless ExecutionReceipt, new durable authority or second journal.

**Source-backed implementation:** prior source had no execution package. New types.py reuses
SessionManager validators and freezes NamespaceRef/ViewRef, the actual nineteen operation names,
READ/WRITE and five purpose values. GrantReply implements only the four grant-result shapes,
including READ-only pin result shape. These are NOT a whole-wire decoder or grant authorization.
A 256-bit grant is encoded as64 lowercase hex; no issuer has been added. Canonical input SHA256
covers operation/namespace/full view/payload, excluding credentials and request ID; it expects
already wire-validated input and does not itself enforce the whole frame/body/operation schema.

supervisor.py contains only CompletedReplyCache/replay-binding helpers, not a supervisor daemon.
A cache read checks original authenticated-principal identity, namespace, op/request/input and
original proof (constant-time proof comparison), then returns only the same immutable result.
remember_completed permits identical duplicate storage, denies changed results/grant renewal,
requires the future real journal owner to establish durable DONE first, and refuses capacity
without replacing existing entries. Missing/restarted state raises uncertainty, never invokes an
execution callback or rebuilds a grant. Actual journal/dedup/reservation, current-grant revocation,
peer authentication and fresh-work authorization are not implemented or proved by this helper.

GrantReply's explicit journal projection omits capability and rejects the issued/original proof
hidden in identity fields BEFORE the caller persists it. This is not generic secret scanning or
proof that real journal files/logs are safe; no journal integration exists yet. Returned dictionaries
are copies; frozen data and opaque repr prevent accidental cache mutation/grant repr exposure.
No production launcher, image, dependency lock, existing I02 source, authority or tool path changes.

**Tests-writing / actual final source-bound checks:** tests/test_execution_supervisor.py is C0/C3
primitive proof, not C1/service/kernel proof. Final baseline/restored64PASS0.44s each; broader eight
modules383PASS7.97s (new primitives, actual installed controller, session lifecycle/manifest/workspace,
plan extractor/precheck and skill conformance). RuffPASS/format4unchanged; targeted Mypy4filesPASS;
source Mypy173filesPASS. No skips/xfails in the owning/broader runs. Earlier draft enum/ViewRef
vocabulary mismatches were corrected against the real spec and exact wire-name/shape assertions
added. Initial static/test-boundary errors were repaired, not counted as kills or waived.

Nine DEVELOPMENTAL mutations each execute ALL64 owning cases: replay authorization call7CALL
failures; identity binding7; original proof1; changed-result guard2; capacity guard1; journal grant
leak5; known-secret guard1; input namespace1; cache producer14. Each exits1 with zero collection,
setup/teardown errors or skips; baseline/restored exit0 and source/test bytes match exactly.
These are NOT normative CT99/CT100 kills: _dispatch/_authorize_request/client remain absent.
Lossless commands/stdout/stderr/pytest reports/mutations/hashes/runner and external-toolchain
provenance: [E234 evidence](evidence/i03-e234/replay.json.gz). Historical E232 proof stays exact.

**Live-host E2E additions planned, NOT RUN:** extend the actual private-UDS/service/controller
fixture, not a fake callback and not premature I02 deployed testing:
- Drop the first completed handoff reply after actual durable DONE and revocation, retry the same
  authenticated original request/proof, then use the original child grant. Assert one durable operation,
  one grant issuance and one intended work effect; altered principal/namespace/input/proof cannot launch anything.
- Kill/restart the real service after DONE but before reply delivery: no raw capability in durable
  files, logs, events, transcripts or receipts; cache loss quarantines/blocks until actual drain and
  safe reconciliation, with no reconstructed secret or second execution.
- Inject real journal persistence/fsync uncertainty: no cached successful reply before durable DONE;
  bounded-cache saturation keeps old replies intact and cannot admit replacement/fresh work.
- Retain the existing immutable-entry poison matrix and backend-down zero-project-instruction
  oracle, then run direct+nested real-provider/controller paths only after SLICE1–4 integration.
Independent oracle/helper review, actual Ubuntu/Docker/cgroup/profile facts and maintenance consent
are still required at final acceptance. No live result, CT/STEP tick, READY or deployment signoff.
All35STEPS and all four transferred final duties remain incomplete.

E234 closeout: actual-source plan0FAIL/6retainedWARN;6slices17FUNCTIONAL35uncheckedSTEPS;
IDs/classes/kill grammar preserved. Doc309filesPASS;whitespace clean. E232 unchanged and final
source/test hashes bound to restored proof. E234 archive SHA256 `20fb15a64ed248e8303e1e332255bfb94c7e5165f375d579f065a3b14653c2e7`.

## E235 — closed wire and complete receipt foundation, 2026-10-16

Continuation instruction explicitly requests all remaining SLICE1 contracts; independent tasks
are pursued before asking about blocked work. Sandbox reset was repaired by separate-index exact
comparison with c0676de, no extras, then mixed metadata alignment only; no source bytes replaced.
External supported CPython3.13.16/frozen dev environment rebuilt. No Docker CLI/daemon socket is
available; no production host/cgroup/image approval supplied. Do not label host proof passed.

New protocol.py reuses existing fastjsonschema, closes all19 request payloads/results and error
shapes, applies independent4MiB frame/1MiB UTF-8 text/64KiB tail bounds, duplicate/nonfinite/type/
path checks, reserved exec ID and response correlation. Invalid IDs are not echoed; valid-ID
schema failures retain only the ID, never exception data/grants. Four-byte network-order framing
uses real socketpair tests and performs no retries. Complete immutable OperationRef/ExecutionReceipt
and closed JobState added; shape truth does not attest actual exit, authority or descendant barrier.
Nullable receipt fields are structurally admitted for provisioning; profile/stage semantic checks
and authoritative source/PlanRef binding remain integration work, not an inferred authorization.

Actual owning baseline136PASS0.77s/restored136PASS0.86s (72new wire+64existing replay cases).
RuffPASS/format5unchanged;targeted Mypy5filesPASS. Eight developmental full136case mutations have
28/1/1/1/2/1/2/1 CALL failures, respectively schema/duplicate-key/decode-frame-size/encode-frame-size/
UTF-8-size/reserved-op-ID/unknown-exit/reply-correlation; zero collection/setup/teardown errors/skips,
exact restoration. Not normative full-SLICE1 kills. Initial formatting/import-library typing and
fixture typing defects repaired, not kills or waivers. Lossless [wire evidence](evidence/i03-e235/wire.json.gz)
includes raw reports, commands, source/test hashes and driver. E232/E234 evidence untouched.

No STEP/CT completion: fixed profiles, service/client/cell integration, launch/path mapping,
actual WorkspaceAuthority and host/kernel proof are still absent. Continue independent profile,
transport/client and dispatch work; collect unresolved joins without prematurely stopping others.

## E236 — fixed profiles, managed client and cell-local PTY worker, 2026-10-16

New profiles.py takes explicit trusted digest/resource/UID/GID/cgroup/seccomp inputs, no production
defaults or wire Docker options. Renderer fixes nonroot/cap-drop/NNP/private namespaces/read-only
rootfs/no-network/resource limits and exactly source/scratch/read-only-cache targets. Actual image,
seccomp/cgroup configuration and protected path ownership still require authority/host approval;
rendering is not Docker/kernel proof. Empty syscall policy in unit fixtures is deliberately NOT
an approved deployable host profile. Worker argv includes its configured maximum command budget.

ExecutionClient checks private socket metadata and actual SO_PEERCRED server UID, validates both
wire directions and sends once. Partial/lost reply yields typed uncertainty with the original
operation ID; no resend, replacement ID or host subprocess. ManagedBashExecutor implements all four
methods and caps command timeout, normalizes only logical cwd, checks every reserved receipt field,
retains normal nonzero command exits and rejects timeout/backend/unknown as determinate success.
No current controller/tool factory is wired; existing production fallback is not claimed removed.

cell_worker.py provides a real module entry with private framed stdio, no grant/namespace input,
stateful PtyPool reuse, all control methods plus STOP and bounded UTF-8 tails. One RUN thread allows
concurrent interrupt controls without parallel job orchestration; replies carry separate request
IDs. PTY creation happens on the main thread before RUN, not forkpty from the RUN thread. A first
combined test run exposed the forkpty-thread warning; mechanism/test setup repaired rather than
suppressing it. Local worker results are UNTRUSTED DATA, never receipts or descendant barriers.
Only three existing PtySession timeout annotations change int→float; integer callers preserved,
real50ms local timeout exercised. Supervisor's independent deadline/cgroup barrier remains required.

Actual final bank219PASS24.50s/restored219PASS24.27s (seven owning+existing PTY modules), no skips,
errors or warnings. Installed-entry30PASS3.81s separately rerun. RuffPASS/format11unchanged;
targeted Mypy11files/source178filesPASS in working tree (includes journal construction separately
in progress, not journal runtime proof). Nine developmental ALL219case mutations: execute-once
call24CALL failures; receipt binding12; server peer1; after-send uncertainty1; READ mount1; network2;
worker schema5; timeout signal1; truncation signal1. Zero collection/setup/teardown errors/skips,
exact source restoration. Lossless [client/worker evidence](evidence/i03-e236/client-worker.json.gz).
Not normative full-SLICE1 CT98–100 proof: actual service/authority/kernel paths remain absent.

Collected join for later: exec has no PlanRef field and normal view metadata lacks an active PlanRef
binding, yet receipt must be reconstructed authoritatively with plan_sha256. Ordinary no-workflow
execution (Q59) also needs explicit nullable-plan semantics. Do not fabricate hashes or let worker
text select a binding. Continue independent journal work before asking about this join.

## E237 — durable journal and injected-authority dispatcher, 2026-10-16

Contracts CT99/CT100 construction; F17/Q75 integration and F15 owning paths. journal.py is a helper
of the SAME supervisor, protected operations/<op-ID>.json, using existing private directory/flock/
atomic replace+file/directory fsync. No session DB or alternate history. Exact canonical input hash,
namespace/view binding, one durable execution claim, recorded container ID, persistent cancel and
one start claim with write-ahead UNKNOWN; actual bounded Docker start remains backend responsibility.
Failed directory fsync never reports successful admission even if replace became visible. Corrupt/
aliased state never overwritten. Restart marks unfinished UNKNOWN only while holding startup
singleton scope; this is NOT actual Docker/cgroup reconciliation, draining, authorization or renewal.
Completed execution records validate known bound identities and reject indeterminate/missing-exit
as DONE; full source/profile/PlanRef authority remains outside this helper. Grant projections derive
from the sole wire schemas, remove capability and reject known issued/original secrets before IO.

SupervisorDispatcher serves one accepted AF_UNIX connection, checks actual SO_PEERCRED UID before
reading a frame, closed codec before dispatch, fixed configured profile ID/command budget and the
REQUIRED ownership callback before reservation/handler. No callback default, service main, issuer,
Docker backend or permissive production authority. Exact completed replay precedes fresh authority;
principal/namespace/input/original-proof mismatch rejects, cache loss never calls handler/issuer.
Non-grant immutable successful snapshots support release/other mutation replies without capability
reconstruction. Body schema validation + durable DONE precede cache+ack; lost ack does not undo DONE.
Unexpected backend exceptions return sanitized uncertainty and persist UNKNOWN, without exception
body/cause logging. One BLE001 reviewer anchor at this deliberate private exception boundary, not
a global lint/rule waiver; KeyboardInterrupt/SystemExit not swallowed. Callback request copies keep
original input/request key/proof stable even if trusted callback code normalizes its own copy.
Client and dispatcher now use a single monotonic RPC deadline across partial reads/writes.

Actual final all10current owning/regression modules286PASS27.89s/restored286PASS28.07s, zero skips,
collection/setup/teardown errors or warnings. Nine full286case developmental mutations:
fresh-authorize producer10CALLfails; reservation durability27; execution claim3; start claim2;
persist cancel2; known-grant guard1; completed input/proof10; absolute deadline1; startup ownership1.
Callback authority/handler-copy mutations separately run full286 each and kill1/1CALL; baseline
286PASS28.06s/restored286PASS27.90s. Static RuffPASS/format14unchanged/Mypy14target+178sourcePASS;
entry30PASS2.95s separately. Exact source restoration. NOT normative full service/kernel C1 proof.

Evidence: [final286 bank](evidence/i03-e237/journal-dispatch-final.json.gz),
[callback-copy bank](evidence/i03-e237/callback-copies.json.gz),
[earlier285 development](evidence/i03-e237/journal-dispatch.json.gz).
Initial combined baseline283PASS2FAIL because reporter imported from external cache violated C0
origin-root assumption; identical test-only plugin moved under repository .arena, no guard/oracle
weakened and no kill credit. Initial reports retained. Review also restored unrelated GrantReply
EXEC negative fixture accidentally changed by broad text replacement; only replay binding expands
to non-health vocabulary. Final286 evidence is rerun on exact repaired fixtures/source, not relabelled.

Source confirms spec §2.1 already permits this C0 typed injected ownership construction and defers
actual WorkspaceAuthority/service main/positive managed kernel proof until integration. No new
slice-sequence decision needed. Independent immutable installation/build proof continues in E238.
Collected F18 PlanRef join remains: ordinary execution vs nullable-only-provisioning text, and no
active PlanRef in ordinary view metadata. Do not fabricate a plan hash or move that choice to worker.

## E238 — immutable install/build preparation and remaining F18 join, 2026-10-16

CT98/F16/F15: Dockerfile.fa now uses existing frozen uv sync --no-dev --no-editable, then installed
closure audit under -I -S BEFORE any site-enabled CLI, then real isolated controller help. The RUN
&& chain fails build on invalid closure. No dependency/lock/build system change or Docker-build claim.
tests/test_controller_installed.py rebuilds the real package into a runtime-only venv using the frozen
lock, forces first-agent rebuild and checks ALL installed .py bytes equal current checkout. Actual
installed controller_entry/cli.main run, no mocked CLI. Project CWD/fa/sitecustomize/PYTHONPATH/
PYTHONHOME/project-venv poison cannot run its marker; actual nonisolated launch returns78 before CLI;
pre-site executable/outside .pth/editable metadata reject without marker. New profile/session gate
checks BOTH interactive-null and noninteractive-nonnull before ownership callback/handler.

Final owning11module bank294PASS30.13s/restored294PASS30.03s, zero skips/warnings/collection/setup/
teardown errors. Four all294case developmental mutations: entry producer5CALLfails including
ACTUAL rebuilt installed nonisolated-entry case; noneditable recipe1; pre-site recipe1; profile
session mode2. Recipe kills are STATIC C0, not a Docker image build. Actual installed producer is
C2, but does NOT prove wrappers/auto-run/session launch paths or deployed immutable ownership.
One fourth-selector precheck missed Ruff multiline formatting; no mutation applied/no kill credit.
Only already-finished three prefix runs preserved after exact source-hash equality, then fourth,
restored and static checks executed; history retained. Exact source restoration.
RuffPASS/format17unchanged/Mypy17target+178sourcePASS; entry30PASS2.84s separately.
[Installed/build evidence](evidence/i03-e238/installed-build.json.gz)262323bytes
SHA256370f252d661b5655f945c3f70972d496d88de46152962f2a3605d266e21f9f15.

Broader initial690PASS12SKIP35.79s: existing deploy tests lacked shellcheck. Not credited as proof;
obtained shellcheck-py0.11.0.1 manylinux wheel from PyPI, verified wheel SHA256
1b274df81de5b000ff78db433e7328b87e52e3c38481c60f8e488c3095beef05, extracted test-only ShellCheck0.11.0
outside Git (binary SHA2564da528ddb3a4d1b7b24a59d4e16eb2f5fd960f4bd9a3708a15baddbdf1d5a55b).
No runtime/app dependency or new Go/Haskell requirement. Deploy90PASS2.93s; final broader21modules
**702PASS37.75s, zero skips/warnings**, including lifecycle/plan/skills/deploy/entrypoint/secret tests.
[Initial broader](evidence/i03-e238/broader.json.gz) retained; [final broader](evidence/i03-e238/broader-final.json.gz).
Development static-slice assertion and missed parametrization (two unwanted libtmux setup errors)
were fixed explicitly, not hidden by skip/tool installation or counted as kills. Earlier installed
snapshot preview from a584017 is labelled preview only; final fixture byte-matches current source.

**F18 — confirmed specification/producer-consumer join defect, not a proved runtime exploit.**
Spec §2.1 exec payload carries no PlanRef; create_view includes plan_ref only inside CANDIDATE scope;
§3.1 ordinary view metadata has no active PlanRef. Yet §2.1 receipt requires authoritative plan_sha256
and permits null only before source provisioning, never verification. Existing ordinary/manual chat
and Q59 advisory invocation can execute without an active workflow PlanRef. Selecting a fake hash,
implicit unrelated plan, worker-reported hash or requiring every ordinary run to enter a workflow
would silently change that contract. Source verified actual nullable workflow plan context in
workflow_controller.py and optional normal CLI execution; this is not solved by journal/DTO shape.
Recommend trusted immutable view-level active PlanRef, supplied by existing controller admission and
rehashed under supervisor authority, null for genuinely unplanned ordinary execution/provisioning;
formal workflow/verification evidence requires its actual admitted PlanRef. No new model routing
mode. [Q76](open-questions-2026-10-07.md#q76--authoritative-planref-binding-and-ordinary-execution-without-a-workflow)
was OPEN at E238, recommendation NOT then ratification. Independent construction was exhausted before ask.
The operator explicitly selected (a) afterward; E239 below records that approval and correction.

Remaining activation: actual WorkspaceAuthority/issuer + Docker backend/reconciliation, protected
volume maps/approved image+UID/cgroup/cache facts, real service main/unit and coherent controller
factory/provisioner/wrapper integration. Existing spec explicitly postpones positive managed kernel
proof until actual authority is wired. No fake authority/failing-main/service placeholder, no unsafe
read-only-/sessions cutover into current writable legacy prologue. All35STEPS and four final duties
remain unchecked; local broad regression is NOT independent review or deployed signoff.

Final [source/plan audit](evidence/i03-e238/source-plan.json.gz): actual-source parser0FAIL6WARN,
6slices17FUNCTIONAL35unchecked, kill grammar valid; doc links309PASS and diff-checkPASS. Six warnings
remain visible external-contract references, not relabelled zero-warning. Exact preserved I02/session,
lock/pyproject and existing wrapper/compose sources checked against E235. E238 source commit dbaaade;
branch-only remote verified. No runtime/STEP acceptance inferred from documentation audit.


## E239 — Q76(a) admitted-plan context and source/receipt join, 2026-10-17

**Decision:** operator explicitly selected `view_bound_nullable_ordinary`. Q76(a) is RESOLVED, not
pending another question. Actual admitted PlanRef in protected immutable view/execution context;
supervisor rechecks source/hash; ordinary no-active-workflow execution can be null, formal workflow/
verification evidence cannot. Q59 routing/manual behavior unchanged. No fabricated hash/worker choice.

**Pre-edit source declaration / F18, CT99–CT100:** existing PlanRef is in
`inner_loop/plan_admission.py`, not a new abbreviated identity. Its bounded no-follow descriptor
reader is reusable. Current normal wire/view metadata lacks the reference and authorizer returns
no context. Target: required nullable admission key + identical candidate reference; immutable trusted
context from REQUIRED authority; fresh source recheck BEFORE reservation; backend receipt plan must
match BEFORE DONE/cache. Exact source files: execution/protocol.py, execution/plans.py (new),
execution/supervisor.py; test_execution_protocol.py, test_execution_plans.py (new),
test_execution_dispatch.py (callback return annotation only). Docs: Q76, spec, I03 plan, this review,
ledger, HANDOFF, knowledge/llms index. ViewRef remains seven fields; no public formal/root flag.
Binary negatives: missing/conflicting/stale/symlinked/nonregular/invalid source, null formal evidence,
and erased/replaced/fabricated receipt plan block. After-side-effect receipt uncertainty stays
UNKNOWN with null durable result; no retry. Q75 cached original completion does not reread source.

**Classification/producer targets:** C0/C3 actual reader+closed decoder+dispatcher/journal/socketpair,
explicit injected test authority and simulated container/receipt witnesses ONLY. Retained installed
CLI C2/C3 runs in the same full owning bank. No C1 resource/service/controller composition claim.
Developmental mutations remove dispatcher context.recheck, admission-context equality and
context.check_receipt_plan calls/checks; additionally formal/candidate admission and formal context
requirements. All run the complete owning bank, not a contract-to-case map, with clean collection,
setup/teardown and exact source restoration. Existing tests changed only for the newly required
wire fields/candidate equality and honest callback typing. Negative oracles strengthened to assert
ERROR/shape before indexing; no bypass/skip/xfail or weaker policy.

**Implementation scope:** frozen ProtectedPlanContext carries existing PlanRef, private registered
source root and existing formal-evidence requirement. It is NOT admission authority. Actual protected
view metadata persistence/loader, real registered-root ownership and controller-admission bridge are
still missing production consumers under WorkspaceAuthority integration. The normative schema join
is corrected and dispatcher checks are constructed; F18's integrated authority proof is NOT closed.
No service main, permissive authority, Docker backend, wrapper cutover or deployment activation.

**Development history:** snapshot resume reset Git metadata/cache; direct Git blob+mode comparison
confirmed all1355 pushed checkpoint files identical (0 mismatches), metadata-only HEAD recovery,
no source replacement. Recovered supported CPython3.13.16 test build from same checked source hash,
matching OpenSSL/zlib/SQLite headers/system libraries, frozen uv dev dependencies; no lock/dependency
change. Optional stdlib absences are not host readiness. Initial importlib-mode helper import,
fixture grant arguments/image property and fixture type annotations were corrected before proof.
Initial347 bank passed; first mutation had3 assertion failures plus1 CALL TypeError because a framed
negative indexed a null error. Driver rejected it; exact restoration and original archive retained,
no complete kill credit. Strengthened status/shape oracles, then reran the full bank/proofs.

**Verification:** final full owning12module347PASS28.65s; restored347PASS28.54s. Six full347
mutations yield4/6/3/1/2/1 CALL assertion failures, no collection/setup/teardown failures, skips or
warnings; byte-exact restoration of all source/tests/lock/build inputs. RuffPASS/format19unchanged;
Mypy19target+179sourcePASS. Broader23modules768PASS39.87s, zero skips/warnings, including existing
PlanRef reader/admission regressions and actual rebuilt installed CLI. Same verified test-only
ShellCheck0.11.0 supplied. No Docker image/host proof. Raw runner sources/reports/history retained:
notes/evidence/i03-e239/plan-binding.json.gz (395688bytes,
SHA256 c5007ce8b63565ba29d2cfea20299d3c40179ee9a36f5a947d4f89c8944917e2),
verification.json.gz (82603bytes,
SHA256 4a1bb8710faaf11a75ef74c9eddfc6aefcba67e4b0e460743fc8938d4e893703),
plan-binding-initial.json.gz (116453bytes,
SHA256 86fc5d32960d95365842905424354cb6fd63630aa275ce149d14db29f9028a56).
All35STEPS/four transferred final duties remain open. No I02 policy/implementation rewrite or
I01/I04–I06 scope change. Protected loader/authority/backend/controller integration and real host
facts remain next; this ratified correction is no longer a question/stop. Inspect/cancel/recovery
must retain the original protected operation/view plan binding, not reconstruct one from worker
text or treat a later source change as fresh admission. No real backend is claimed here.

Final source/plan audit:0FAIL6WARN (existing external contract references visible),6slices,
17FUNCTIONAL,35unchecked; kill grammar clean. Actual309 markdown link audit passes; git diff
--check passes. Source matches final tested hashes; I02 inner_loop/session, lock/pyproject,
Dockerfile and wrappers/compose unchanged from ba50092. Raw source-plan.json.gz SHA256
1b1815aaac14d0ab859295996242f638279ecef01475d2293bac631e865a6607.


## E240 — target semantics and noninteractive worker lifetime, 2026-10-17

**Rollout correction:** operator reaffirmed building ALL target contract behavior, resolving actual
contradictions before edits. The existing I03 **Verification schedule** already permits coding in
dependency order without an early approved Docker host; required host/full-path acceptance remains
outstanding for final SLICE6. Earlier assistant request to choose a host was premature, NOT a new
operator rollout decision. No deployment, workflow dispatch or live-host test occurred. No new
question about sequence or Q76 is pending. Do not confuse construction progress with acceptance or
substitute current helper behavior for the target service/system.

**F19 — verified lifetime/status producer mismatch, not a deployed exploit:** both profile kinds
rendered the same persistent worker. Cell-worker main returned0 after its control loop regardless
of RUN command status. Target normal noninteractive completion needs actual container/process exit;
using that loop's eventual0 as command success would be false, and waiting for natural one-command
exit would not finish. Resolve inside the existing worker/profile, not by weakening receipts or
adding a second executor/service. Interactive episodes remain persistent.

**Pre-edit declaration / CT100:** read_set execution/profiles.py, cell_worker.py, existing client/
worker tests and spec §§2.1/3 plus plan schedule; base216302a, llms SHA256
ac2d1c2821c1c769bdd061de07937630e9af94acb74e85a28262035b43334a75. Write_set those two source/two test
files plus existing spec/review/plan/HANDOFF/ledger/index/evidence. Mechanism: fixed private profile
flag, main→serve_once, exactly one validated framed RUN, actual existing local PTY execution,
correlated bounded reply and determinate status propagation; failure78 never supplies a synthetic
command success or timeout124. Reuse existing framing/PTY operations. Binary DoD: exit0/7/78/124/
255 preserved, second RUN has zero side effects, timeout/control-only/malformed/escaping cwd do not
become normal completion, interactive state/control tests retained. C0/C3 with actual local PTY and
main path (fixed mount paths substituted), NOT Docker/C1/deployed-main proof. Developmental full-bank
producer kills: profile selects mode; main calls serve_once; serve_once propagates command status.
No existing test oracle weakened. No new dependency, authority, workflow mode or deployment flag.

**Minimalism/goal:** reuse CellWorker/PtyPool/_run and one reply helper rather than another runtime
or service. Without the mode, a noninteractive container cannot naturally complete one RUN with
its observed status. Existing repo precedent runtime/pty_pool.py and inner_loop/slice_verification.py
retain determinate process outcomes. Goal-lens: truthful mandatory execution boundary (axis C),
subtraction evaluated YES, session-type bug-fix. No research/deployment platform added.

**Development:** recovered the same supported3.13.16 frozen test toolchain from E239's archived
bootstrap, no application dependency/lock change. First focused69PASS1FAIL: fixture substituted
SimpleNamespace for sys.stdout, breaking pexpect's normal text-stream requirements; restored honest
TextIOWrapper with binary buffer, without changing production fallback or weakening failure rules.
Mypy fixture imports corrected to import sys explicitly. Final focused70PASS3.72s. Full-bank/static
verification follows; no kill/proof credit from fixture failure.

**Still target work:** actual Docker control/attach/lifecycle/observation and restart reconciliation;
real protected WorkspaceAuthority/controller bridge; private service/config and safe wrapper/
provisioner integration. No fake authority/failing main or early readonly-/sessions cutover. Build
these toward full CT98–CT100a/SLICE2–4 target seams before enablement. Required real-host/system
acceptance stays final SLICE6, never waived by this local worker fix. All35STEPS/final duties open.

**Final E240 verification:** owning12module361PASS31.70s/restored361PASS30.48s. Three full361case
mutations1/1/8 CALL assertion failures, zero collection/setup/teardown failures/skips/pytest warnings,
exact source restoration. RuffPASS/format19unchanged; Mypy19target+179sourcePASS. Broader23modules
782PASS44.40s with verified test-only ShellCheck0.11.0, no skips/warnings. Actual installed CLI
rebuild/source matching retained in both banks. Raw one-shot.json.gz261875bytes SHA256
2c87a2eee75395815f9b15c14310e44d3615620828b04997743b637dc2203921. Verification archive records actual
commands/reports and recovered test-toolchain provenance; no application dependency or lock changes.
No live host/production acceptance, service activation or construction tick inferred.

Final plan/doc audit:0FAIL6WARN,6slices17FUNCTIONAL35unchecked,kill grammar clean;309 markdown
links PASS,diff --check PASS,tested source hashes exact;I02/session/dependency/lock/Dockerfile/
wrapper/compose source preserved from216302a. Raw source-plan.json.gz SHA256
5bbbec172297de00008b83aebd73bec60a36d36def6b86bfa0794ae0e92cb72e.
Verification archive SHA256 98cb8a0d50579455e43230d56d66b7c30d741e5764dfb10c98f0936534816b52.
An inherited runner metadata field described E239 checkout recovery instead of current E240;
explicit correction retains original field and executed runner source, with all commands/reports/
return codes unchanged. No rerun or reinterpretation of test results for metadata status.

## E241 — private Docker launch and owned observation construction, 2026-10-17

**Scope / pre-edit declaration (CT99–CT100):** continue actual target implementation in the already
approved dependency order, NOT another admission audit or host-choice gate. Read_set: execution
client/journal/profile/protocol/supervisor/worker, their tests, this review, spec §2.1 and increment
Verification schedule, tests-writing/doc-maintenance skills. Base f92d9b54134c92ea7fb336113b78a7c1b6df7f9a;
pre-doc llms SHA256 4ebce21f9175e4ab53ebcef503754dd802c55adfa5be3f0502328ab53c2e7738.
Write_set: execution/{client,journal,docker}.py, tests/test_execution_{journal,docker}.py, existing
spec/review/increment/ledger/HANDOFF/index, notes/evidence/i03-e241. No dependency/lock, I02/session,
Dockerfile, wrapper, compose, workflow-mode or deployment change. No concurrent writer observed.

**Mechanism / minimalism:** reuse the existing endpoint/SO_PEERCRED checks, closed input hashing,
fixed profile renderer and fsync/flock journal. DockerEngine makes actual fixed create/start/inspect
HTTP calls over authenticated AF_UNIX; required socket/UID/API/RPC-budget configuration, no TCP,
DOCKER_HOST, endpoint/version discovery, pull, redirect or retries. One absolute deadline through
HTTPResponse's SocketIO reads, bounded framing/body, sanitized daemon failures. Required resource
binding validator runs before launch; it is NOT a temporary issuer or a claim that real authority
exists. The launch coordinator requires the reserved EXECUTING exec claim and original input hash,
durably writes UNKNOWN before one create RPC, then CID before start; start already has its own
write-ahead one-use guard. Cancellation and competing create claims serialize on the real journal.
Lost reply, invalid CID or CID durability fault never regains create permission. Journal claim
states are internal bookkeeping, NOT actual process state. Start acknowledgement returns a CID,
NOT an ExecutionReceipt, command success or terminality.

Owned inspection verifies original deterministic name/labels, full CID, configured pinned image
reference and syntax of observed image config ID. It reports that ID; it does NOT establish that a
manifest digest equals its config digest or approve deployed image/kernel facts. Original-name
lookup after lost create is read-only; no fresh start or grant reconstruction. Non-exited Docker
states never expose provisional ExitCode=0 as command completion. Even EXITED observation has NO
cgroup terminal_barrier or authoritative receipt. Backend attach/command/control, cancellation/
kill, durable episode registry, reconciliation and descendant-terminal lifecycle are still required.

**Interactive lifetime:** launch_new is only a new cell. Later RUNs in an interactive session must
reuse its live cell and original creation-operation binding, while reserving each command's own
operation/input. Do NOT wire this CID-returning coordinator as an exec handler or create a new cell
per RUN; the real episode registry/backend must enforce namespace/view/session ownership first.
No production factory/main activation, permissive authority or failing-main stub was introduced.

**Reference:** primary Moby v20.10.0 api/swagger.yaml blob
9f1019681af5135c20ecdaaebe03975bb7497461, decoded382944bytes SHA256
7b5de4c18a20092932ecf184d6afada89e2f8d511dfdb7b63be958b02e7d0fa8. Create name/201 Id+Warnings,
start204 and inspect fields informed the transport. Required API is explicit, no downgrade. API1.41
is a minimum feature reference, NOT approved deployment version; fixture1.45 is NOT compatibility
proof. Full fetched primary text, hashes and retrieval provenance retained in primary-api.json.gz.
No Go/runtime library dependency added. Goal-lens: truthful mandatory execution boundary (axis C),
necessary target transport/one-use launch producers, reuse instead of a second runtime/service.

**C0/C3 tests / development:** literal native Unix HTTP peer + real protected journal files/locks;
NOT Docker, namespaces, seccomp, cgroup, host image or actual authority/C1 tests. Covered positive
create/start ordering and payload, required binding and mode/limit/cancel/hash gates before any
request, lost create/start replies, read-only recovery lookup, concurrent claims, CID persistence
fault, peer rejection, malformed/oversized/truncated/ambiguous framing, redirects/error sanitizing,
chunked success and bounded slow drip. Inspection identity/labels/image/state and provisional exit
codes checked independently of profile rendering. Per-edit review found Python HTTPResponse silently
discards body on204: reject explicitly declared nonzero length/transfer encoding before reading;
regression added, no response-body success assumption. Initial style diagnostics and three optional
lookup typing errors corrected; focused119PASS3.10s + Ruff/Mypy5PASS. No kill credit for development
diagnostics and no existing test oracle weakened.

**Owning proof:** all13module415cases PASS32.38s, restored415PASS32.11s. Ten separate full415case
producer mutations killed with CALL assertion counts **2/6/2/1/3/2/2/1/7/1**: resource validation,
create write-ahead, input binding, deterministic create name, durable CID propagation, start RPC,
kernel peer gate, absolute receive budget, exit observation and204 framing. All415 setup/teardown
phases PASS each run; zero collection failures/skips/pytest warnings; no runtime-error kill credit.
All source hashes restored exactly after every mutation. These are developmental full-component-bank
sensitivity checks, NOT the plan's final session/nested normative kill acceptance. Raw runner,
node IDs/phases/output, mutations and changed source snapshots in docker-launch.json.gz675489bytes,
SHA256 d031abf8e822eea5099321578182f151e21445f05ffb1c767a934e6b0b1c5eb7.

**Restored verification:** Ruff/format21PASS, Mypy21target +180sourcePASS. Broader24modules
836PASS42.82s, all setup/call/teardown phases clean, no skips/pytest warnings. Existing installed
CLI and inherited source/PlanRef/session/entrypoint/security regressions included. Existing cached
Python3.13.16 and hash-verified ShellCheck0.11.0 used; no new bootstrap/dependency/lock changes.
Actual commands/output/full broader report in verification.json.gz; not a full-repo just-check or
inherited-baseline readiness claim. Final source/plan/doc audit recorded below. All35STEPS, SLICE1 and
four transferred final duties remain incomplete. Required actual-host/full-path acceptance stays
at final SLICE6 under the existing Verification schedule, not waived or claimed by this component.


**Final source/plan/doc audit:**0FAIL6WARN,6slices17FUNCTIONAL35unchecked; kill grammar clean;
309 markdown files/link check PASS, diff --check PASS. Tested source hashes exact. I02/session,
lock/dependencies, Dockerfile/wrappers/compose and unchanged execution/controller sources preserved
from f92d9b5. Source-plan archive SHA256 a3b86de242c5b18ee8a4c7486883aeaa85e28e6fdf8a1ed536028dac95f56d26.
Verification archive SHA256 29ce44e66a1ae3d05f0858e97969848eecf73f2143751421a8efa281efd1bd2d.
Primary API archive SHA256 af2d7617b4e576166d170ab88cf329d2d31b08104a198e5fbe182e9e7c5b6641.
Actual daemon/version, image config mapping, endpoint exposure/UID policy, protected mounts and
kernel facts remain deployment acceptance inputs; peer authentication alone does not prove them.

## E242 — private attach/worker transport construction, 2026-10-17

**Session/pre-edit declaration (CT99–CT100):** base1aed72999c5bceb174c23d7c0f294ca3f4bf17c7,
clean branch arena/86633f17-first-agent-dev; pre-doc llms SHA256
ad31f879e4b910e4c49866c35dd12d73cac035e7ffa7d371a67d8c7e36cc33db. AGENTS/bootstrap,
project-overview/ADR digest/reference/HANDOFF, active increment/spec, tests-writing, pr-creation and
doc-maintenance read; recency command surfaced E238–241, no new research-note supersession to cite.
Read_set: execution Docker/client/journal/profile/protocol/supervisor/cell worker, owning fixtures,
Moby attach API and source. Write_set declared before edits: Docker/cell worker, shared private codec,
private worker client, attach/codec tests + literal HTTP fixture, existing records/evidence. Expanded
before typing repairs to journal/supervisor and tests execution dispatch/plans. Source edits scoped
to that set; no parallel writer observed. Arena lacks fs_blackboard/fs_search mutation-guard tools;
used bounded direct file reads, clean-status/read-set declarations and exact source-hash checks,
not a claim that the unavailable substrate guard ran.

Subtraction: existing cell worker covers execution but no supervisor-side Docker attach consumer;
omission loses command/control access to created cells. Reuse existing PTY worker/frame primitives
and fixed private daemon config, no second executor/HTTP runtime. Repo precedent runtime/pty_pool.py
retains persistent sessions and explicit controls. Goal-lens: truthful mandatory execution boundary;
axis C, subtraction evaluated YES, session-type new-feature. Automated consumers are DockerCells
owned attach + WorkerClient and native component tests; not a production service factory.

**Construction:** DockerEngine.attach authenticates the kernel peer before fixed POST, explicit
Upgrade=>101/raw-stream, stdin/stdout/stderr, logs=0 and empty detachKeys. No TCP, CLI/environment
endpoint selection, historical-log replay, redirect, fallback, reconnect or resend. A bounded header
reader consumes exactly through CRLFCRLF, preserving coalesced first output bytes. Non-TTY Docker
8-byte mux decodes stdout (including documented type0), separates bounded stderr diagnostics,
rejects unknown/reserved/oversized/truncated frames and retains stdout fragments across replies.
Per-response encoded-wire cap is NOT a lifetime cap. Nonblocking duplex reads/writes keep absolute
exchange budgets separate; concurrent controls cannot reset a RUN socket inactivity timeout.
Stderr bytes are worker-process diagnostics, not trusted command status or authoritative receipt.

DockerCells.attach_created checks the original journal namespace/view/input binding, performs owned
inspection and requires a running cell before attach. It does NOT authorize fresh work or establish
exclusive episode ownership; the protected backend registry must do that before use. Existing live
cells/creation bindings must be reused for later interactive commands with separate command claims.
A lost command stream cannot be recovered by calling attach_created again and reconstructing replies.

Shared cell_protocol is now consumed by both existing worker paths (persistent and one-shot) and
WorkerClient. Request/response objects are closed, relative cwd rules match the existing public
contract, RUN binds request/session IDs, preserves timed_out/truncated/exit data and bounds UTF-8
output bytes. No namespace/capability/host paths/receipt fields are admitted into the cell message.
WorkerClient permits one RUN plus one control in flight with a single correlated reply reader and
serialized writes. Expired/lost/forged/unavailable replies poison the channel and wake pending callers;
never synthesize success or resend. No outstanding-ID collision can replace an active request, and
an unsent queued-RUN timeout leaves the original exchange intact. It has NO durable at-most-once
command admission: original operation reservation and completed-reply Q75 policy remain backend/
journal responsibilities. Closing this channel is NOT stopping a container or proving terminality.

**Primary reference, not host approval:** retained E241 Moby v20.10.0 API blob + attach excerpt;
container_routes.go blob7f3fb34f4b6074d6203ee964c7a9c876ac059bc6,
daemon/attach.go blobc6553f79d391905c8ca5e38e9d32a654146e1b01 and
container/stream/attach.go blob0269a226b1bd6d26116bac86ed5d718ba242b083. Full bytes/hashes/retrieval
provenance in primary-attach.json.gz. API docs permit200 without Upgrade; this client explicitly
requests Upgrade, so missing101 fails closed, not an invented compatibility fallback. Empty detach
keys are accepted by daemon; this is non-TTY framed stdin, not Docker CLI escape handling. No Go
runtime/dependency added. Actual engine/version/image/kernel/endpoint approval remains outstanding.

**Tests / diagnostics:** C0/C3 real Unix HTTP upgrade/mux + actual existing local PTY/worker; NOT
Docker/cgroup/authority/session C1 proof. Native positive root joins owned inspect→attach→WorkerClient
→shared codec→actual serve/PTY and reuses ONE attach for stateful commands and controls. Separate
actual serve_once path preserves command7 and local worker function return7, NOT actual container
exit. Literal gated peer proves concurrent out-of-order RUN/INTERRUPT correlation and all-pending
EOF wakeup. Negative gates cover protocol/peer/ownership/state, malformed header/mux/framing/replies,
foreign IDs/session/extra authority fields, UTF-8 tail cap, read drip/write backpressure, no replay,
unsent queue timeout/collision, and >4MiB cumulative stream lifetime with bounded individual frames.

Initial focused107PASS1FAIL1warning was rejected as proof: fixture forked its PTY after HTTP thread
startup and asserted Ctrl-C hit a RUN not yet known to have started. PTY fixture now explicitly
precedes server threads; native test claims state/control ACK, gated peer claims concurrent ordering.
No production fallback or terminality weakening. Lambda inference/style diagnostics fixed. Full
configured Pyrefly then found20 execution-foundation errors: missing overrides and heterogeneous
**dict construction (not a deployment failure). Repaired all20 with @override/explicit validated
seven-field ViewRef construction and honest fixture map annotation; no suppressions or schema/
authorization changes. Existing test assertions preserved. Focused125PASS5.69s and both type checkers
clean before proof freeze; raw initial/fixed Pyrefly logs retained in verification evidence.

**Rejected developmental mutation:** initial absolute-read mutant reset each receive to1s, also
shortening a valid native RUN. Whole467case run produced one intended assertion plus a runtime
WorkerUnavailableError; runner rejected mixed failure, restored every source hash exactly and stopped.
Entire initial archive retained (attach-worker-initial.json.gz); NO final kill credit. Corrected ONLY
the mutant to a long resettable budget, no source/test oracle edits, then reran the whole owning bank.
Final owning/static/broader results follow after execution. No STEP, SLICE1 or final duty marked done.

**Final E242 owning proof:**14modules467PASS34.34s/restored467PASS33.49s. Ten full467case
mutations killed with CALL assertion counts **1/1/1/1/1/1/1/1/5/1**: live-only attach query,
stdin enablement, Upgrade status, mux padding, worker reply decoder producer, request correlation,
session binding, absolute receive budget, running-cell admission and UTF-8 tail limit. All467
setup/teardown phases PASS every run; zero collection failures/skips/pytest warnings, no runtime
error kill credit. Exact source hashes restored after each mutation and at end. This is component
sensitivity, NOT the final normative session/nested kill acceptance. Raw commands/node IDs/phases/
mutations/changed source snapshots in attach-worker.json.gz735419bytes SHA256
3c22d79c10ac534cac7e6d6ff83efdbb732c8f1815bcaeb0433bdc069568e815. Rejected initial archive569704bytes
SHA256 5fef74a0fd782677d7737c87671de78ac4c510ee00a4eb173bc093f57adc64b0 retained unchanged.

**Restored static/broader:** Ruff/format24PASS; Mypy24target+182sourcePASS; full configured Pyrefly
0errors (existing141suppressed/50warnings, no new suppression). Explicit clean-PYTHONPATH check also
passes; reporter path is only needed by evidence pytest plugin. Broader26modules **894PASS49.46s**,
all collected IDs unique and all setup/CALL/teardown phases pass, no collection failure/skip/pytest
warning. Includes existing source/installed CLI/session/entrypoint/security/PlanRef regressions and
six real Pyrefly-topology tests. Driver initially expected892 by incorrectly assuming four topology
cases; actual pytest rc0/raw894 report is retained, original driver rc1/incomplete archive embedded.
Completion validator checked all894 phases + exact sources and finished remaining versions/diff
checks WITHOUT rerunning or altering test results. Runner metadata correction is not new proof or
a relabelled test failure. Original executed runners and completion validator retained verbatim.
Existing supported3.13.16/frozen dev/hash-verified ShellCheck0.11.0 used, no bootstrap/lock/config/
application dependency change. No full-repo just-check/readiness or inherited-baseline PASS claimed.

Required actual Docker image/API/kernel/namespace/capability/cgroup/daemon/endpoint facts, exclusive
registry/backend/authority/service/controller wrapper full paths and four final acceptance duties
remain open. Do not use the transport CID/worker data as receipt or early cutover approval. Existing
verification schedule and Q59/Q75/Q76 remain unchanged. All35STEPS/SLICE1 incomplete.


**Final source/plan/doc audit:**0FAIL6WARN,6slices17FUNCTIONAL35unchecked, kill grammar clean;
309 markdown/link check PASS, diff --check PASS. All198 tested source/test/build/lock hashes exact;
initial rejected snapshot restored exactly too. I02/session/dependency/lock/Dockerfile/wrapper/
compose, client/profile/public protocol/plan/types/controller entry groups unchanged from1aed729.
Source-plan archive SHA256 5ca402b9644cbae316d840a9f4571d27435dec8f9f85653920b3bca442a7d70d.
Verification archive SHA256 395ce9a24252c6cb5cc55364aef4d8951103977f6c95bff845d8f63be7043082.
Primary attach archive SHA256 deba5fabcdebdac0a352f997ec3e8b21e9bce72faddea06ed2c9491d668a83b7.
No service main/cutover/host dispatch or acceptance tick. Next work is actual registry/backend/
terminal lifecycle and authority, not another evidence-only substitution or early-host question.

## E243 — adversarial mid-slice review: remaining SLICE1 and next SLICE2 (2026-10-17)

**Scope/authority:** review baseline `e73608247575251bae674db1dfee14a265cec4da` (E242).
The evidence anchors below are **file:line at that commit**, so later rewrites do not change their
meaning. Read code plus dispatcher/journal/Docker/client callers, SessionManager/CLI provisioning,
file-tool builders/transaction/blackboard and search-index/PDF dependents. No broad product rewrite,
new approval gate or actual deployment. Recommendation is not completion. Required host acceptance
remains accumulated for final SLICE6; Q59/Q75/Q76 and all35unchecked STEPS/four duties remain.

**Trajectory verdict:** SLICE2 advances the real goal: authority and coherent private IO are the
missing consumers of SLICE1's transport, not optional scope. Keep six slices/17FUNCTIONAL; fold
CT101/102/103 implementation into ONE WorkspaceAuthority, not three subsystems. Keep operation
journal/reply cache/PTY/search/session/run facades. Reject another journal, persistent episode DB,
search service, lease platform or backend matrix. The new thin lifecycle owner and frozen cell
project-tool entry are necessary glue over existing capabilities, not replacements for them.

### Findings — confirmed defects or confirmed contract gaps

| ID / severity / disposition | Evidence and failure | Direct correction / binary exit |
| --- | --- | --- |
| F20 / HIGH / **runtime transport repair implemented; full backend deadline join still open** | `client.py:115–120`, `supervisor.py:411–421`, `protocol.py:369–389`: the same short fixed RPC deadline spans command execution/reply. Valid command time can exceed it; server drops a reply even after handler/uncertain journal transition. Corrected regression reaches handler exactly once and observes missing reply; client independently raises uncertainty. | Add validated exec time ONCE to original absolute transport deadline, no reset/revival/control loan. New tests require usable post-control-budget command reply, bounded controls and profile rejection. §2.2 separately requires actual backend queue/admission/execution deadline propagation; transport time is not timeout/kill evidence. |
| F21 / HIGH / **confirmed missing target join, not a demonstrated deployed exploit** | `supervisor.py:260–276,305–310,380–384`: initial authority returns only PlanRef context; `handle(request)` receives neither peer nor deadline after reserve/begin. `docker.py:449–468` validates binding before later create/start. No owner yet linearizes revoke/STOPPING versus launch/file admission. | §2.2 names explicit private peer/deadline dispatch and `WorkspaceAuthority.admit`/close/drain ownership. Recheck actual grant/source at effect boundary. Race oracles: revoke wins→zero sends/writes; admission wins→stop waits for tracked work then actual terminality. No global journal lock across RUN/drain. |
| F22 / HIGH / **confirmed remaining lifecycle/identity contract gap** | `docker.py:396–401,439–505` intentionally supports new-cell creation/original creation attach, not per-command dispatch. `journal.py:280–287,324–355,409–425` already provides one `begin` claim/CID association but recovery marks only RESERVED/EXECUTING uncertain. A creation-command DONE is compatible with a live interactive shell; journal DONE is not container death. | §2.2 reuses begin/record_container per new command, keeps original creation labels/CID/attach, forbids repeat create/start/RUN. Startup scans/drains all owned cells, including creation-DONE, without reconstructing Q75 cache. Two stateful commands→one cell/two records; crash with DONE+live shell→no writer reacquire until drain. No redundant RUN claim API/log. |
| F23 / HIGH / **confirmed inconsistent/incomplete IO composition contract** | Spec §4 `:410–420` requires same tool/PTY view but says all read/search use a pin; increment SLICE2 STEP4 `:188` names no viable search route. Closed19 ops (`types.py:38–57`, `protocol.py:93+`) have no listing/search RPC. Actual `read_file.py:426–484` reads host paths and special-cases controller artifacts; PDF reader `:22–109` loads native parsers. `fs_search.py:961–979` accepts an explicit DB; `fs_reach.py:89–94` hardcodes workspace .fa; mutation_guard `:51–76` invokes host Git/canonical hash while discovery attribution `fs_search.py:561–583` needs controller SessionState. | §§2.2/4.2 distinguish active-writer read-your-writes from independent immutable reader pins, retaining public schemas. Reuse search/reach/PDF in a thin fixed cell helper over exec, indexes in private scratch; text and expected-SHA writes use rooted IO, artifact_id stays controller-side. Exact bounded whole-file SHA/window policy closes the >1MiB ambiguity. Real tool+PTY/new-symbol and independent old-pin oracles; truncation/helper failure never partial success/canonical fallback. |
| F24 / HIGH / **confirmed integration/ordering gap, not a new current-manager ownership bug** | Increment SLICE2 STEP2 `:186` requires provisioner before STEP3 materialization. Manager `:269,293–296` checks reverse ownership/provisions before workspace_preparer, `:280,316–329` derives cleanup permission from prior path absence. `_check_reverse_workspace_ownership` also called by `resolve_workflow_workspace:403`. CLI `_prepare_managed_workspace:150–159` logs not-READY and returns. Existing spec §4.1 already warns about these seams, but STEP ordering/DoD does not enforce them. | Reorder materialization before managed provisioner; update both reverse-reference call sites, preserve manifest/session DB/run validators and old claims. Provision result must identify committed authority ownership; post-commit DB/readiness/manifest failure cannot rmtree registered bytes. Publication-dependent new-workspace leg joins SLICE3, no temporary host clone. Test new/resume/reuse, corrupt manifests, busy mutation, post-commit failure/no deletion. |
| F25 / MEDIUM / **confirmed prescriptive-step inconsistency/stale DoD** | SLICE1 STEP3 `:155` tells implementer to flip canonical mounts read-only before SLICE2 file/provisioning consumers; STEP2 `:154` says generic service/client/worker despite implemented E236–242 components. Spec §2.1 `:248–253` already forbids a real issuer until actual SLICE2 authority, while final host schedule `increment:105–114` defers acceptance. | Rewrite all remaining SLICE1/2 STEPS against existing code. Packaging first, actual authority→publication→atomic SLICE4 caller/mount cutover; no temporary main or early-host request. Exit criteria specify bytes/counts/errors/ordering and whole-bank assertion kills, not merely tests-collect/no exception. DEPS remains construction ordering, not fabricated completion. |
| F26 / MEDIUM / **confirmed reuse hazard; no existing workspace implementation to blame** | `workflow_artifacts.py:566–585` creates parents/requires service UID/chmods0700; `:616–649` writes0600 service-owned replacement. These are correct for private artifacts, not drop-in project IO for another cell UID. `tools/base.py:7–17` is resolve-then-use containment, not a privileged descriptor fence. `plan_promotion.py:102–111` explicitly distinguishes canonical parents from private chmod helpers. | §4.2 reuses private IO only for protected metadata and specifies small descriptor-rooted project IO preserving safe cell access/modes. Test no canonical chmod/creation, PTY readability after tool replacement, symlink/ancestor/inode substitution, expected-SHA conflict and fsync uncertainty; no generic transaction framework. |
| F27 / HIGH / **confirmed missing provisioning namespace order** | `manager.py:293–296` provisions before creating session DB; `cli.py:314–318` allocates the first RunContext only after create_or_attach_session returns. All non-health wire operations need NamespaceRef (`protocol.py:299–302`), and managed provisioning must not invent a run ID. Existing `begin_run:441–477` already reserves a real binding/run directory using a SessionContext plus existing DB without public active-manifest attach. | §4.2 moves DB initialization before managed provisioning under the existing provisioning manifest and reuses begin_run for one private provisioning RunContext; normal requested CLI run stays distinct. No relaxed public manifest reader, second allocator or new DB. Actual new-session/entrypoint tests require DB binding before first supervisor request and retain failed-run reservation. |

All execution-module anchors in the table are under `src/fa/execution/`; tool anchors under
`src/fa/inner_loop/tools/`; manager under `src/fa/session/manager.py`; CLI under `src/fa/cli.py`;
workflow_artifacts/plan_promotion under `src/fa/inner_loop/`. Spec means `notes/i03-execution-workspace-spec-2026-10-15.md`; increment means
`increments/increment-03-execution-workspace-foundation.md`, both under this project worklog.
Every cited line is at e736082, not a guessed current line.
These are source-grounded contract gaps and an actual local defect, not claims that missing owners
already ran insecurely in a deployed system.

### Sound parts and hypotheses not promoted to bugs

- Installed noneditable controller/pre-site gate already exercises real CLI import closure; keep it.
  Closed wire validation, authenticate-before-read, exact reserved input, secret-free journal and
  Q75 memory replay are useful implemented foundations, not evidence to rewrite them again.
- Existing `begin()` supplies the durable reused-command claim. Initial suspicion that every RUN
  needed another claim/journal is rejected. `record_container` is the existing CID seam.
- No demonstrated `WorkerClient` deadline/reader race was found. A minimum pending read deadline
  and stream poisoning are conservative fail-closed behavior; do not invent a fix without a failing
  trajectory. Actual Docker/cgroup/root-alias facts remain unproved until required host checks.
- Existing mutation_guard/Transaction are observations/conflict coordination, not security authority
  (`mutation_guard.py:141–148` deliberately permits absent/mismatched blackboard). Preserve them;
  do not mistake their thread locks or pre-write checks for workspace admission.
- Earlier review commentary named nonexistent `inner_loop/fs_safety.py`; filename discovery disproved
  that premise. Real precedents are workflow_artifacts, plan_admission and plan_promotion. No new
  code/import uses that nonexistent path. `session/workspace.py`, not workspace_provisioning.py,
  is the current host Git implementation; it is not a target managed fallback.

### Rewrites and remaining construction sequence

Directly updated increment SLICE1 STEP1–4 and SLICE2 STEP1–5, CT103, source baseline and test inventory;
added normative spec §§2.2/4.2 and corrected blanket pin/non-exec inspect language. No new public tool,
wire operation, workflow mode, retention platform or approval prerequisite. Preserve17FUNCTIONAL and every constraint;
fold shared mechanism/owners rather than delete their distinct guarantees.

Next implementation order is: **CellBackend over existing transport/journal → real WorkspaceAuthority
registration/admission + materialization/rooted IO → managed SessionManager/tool joins → SLICE3
publication + full factory → SLICE4 atomic caller/mount cutover**. Backend and authority integration
is a join, not a reason to stub either or wait for early deployment. The private cell project-tools
entry reuses existing algorithms; it is a planned interface, not code falsely claimed delivered.
Per-slice component checks may execute now; actual declared-path/kernel proof accumulates to SLICE6.
No STEP, CT, SLICE1 or SLICE2 acceptance tick follows from this review/transport repair.

### E243 executed repair evidence (component proof, not whole-slice acceptance)

F20 repair changes only protocol DeadlineConnection plus its client/server call sites; no public
wire/profile/authority/cell/wrapper change. Added14 tests, retained existing assertions. New helper
budgets are validated/once-only; original absolute clock retained, expired input not revived, no
control or unapproved-profile budget loan. Client connect/request send stays on the short budget; only reply waiting borrows command time.
Client/server after-control-budget regressions use a
logical elapsed clock with actual Unix sockets and explicit fixtures, not fake Docker/kernel facts.
Initial wrong-CAP fixture and nonexistent new assertion field were rejected/corrected, not kill proof.
Corrected before-code server failure reaches exactly one handler then fails on missing response.

Owning14modules **481PASS34.21s / restored481PASS34.01s**; nine full481-case producer mutations
fail only assertion oracles: client/server budget calls, client input-phase budget, once-only guard, original absolute clock,
expired-input guard, positive budget validator, server profile limit and mode. Counts **1/1/1/1/2/1/3/1/1**;
all phases clean, no skips/collection errors/warnings, exact198 source/test/build/lock hashes restored.
Use raw archive timings/reports as authority; wall-clock runner overhead is separately recorded.
Ruff/format24PASS; Mypy24target/182sourcePASS; configured Pyrefly0errors with existing141suppressed/
50warnings (also clean-PYTHONPATH check). Broader26modules **908PASS48.03s**, clean reports/IDs/phases.
No configured full-repo just-check, readiness/baseline or actual host result is claimed. Same supported
Python3.13.16/frozen dev tools and cached ShellCheck0.11.0, no dependency/config/bootstrap change.

Passing v1 proof is retained as deadline-review-v1.json.gz and its static/broader archive is embedded
in the final verification archive: final review tightened client input/reply phase separation, and
source changes required fresh proof. An edit-driver SyntaxError made no edits; its old-source smoke
check is not new proof. No passing or failed run was relabelled.

Raw commands, collected IDs/phases, literal mutations, tested sources, runner, rejected-development
summary and corrected before-code failure: [deadline repair archive](evidence/i03-e243/deadline-review.json.gz).
Raw static/broader reports and closure audit: [verification archive](evidence/i03-e243/verification.json.gz).

**E243 final closure audit:**0FAIL6WARN;6slices17FUNCTIONAL35unchecked; kill grammar clean;
309Markdown files/link check PASS; diff --check PASS; all198 tested hashes exact. Prior test
assertions and append-only ledger prefix retained; only12 declared tracked files changed, all other
source/session/dependency/profile/type/plan/worker/Docker/entrypoint/wrapper groups preserved from
`e736082`. No actual backend/authority/host acceptance added by this audit.
Final deadline-review.json.gz689985bytes SHA256
728a228c8f9e1ecf10400bb8a90f2a996ed089556b5f9b83c670bc6ea702c587;
verification.json.gz207295bytes SHA256
59cfc0cba71d2457cd1d5d275f63f784eda8b16de2a15339ec462fdc7d33262e.
Superseded v1 proof629618bytes SHA256
5b4d63482b8b75450b665c4a6bdf3108d25b9b038f5714899df2a037089eb3bc retained unchanged.

### E244 — docs-first disposition before continuing implementation (2026-10-17)

F20 remains the executed E243 transport repair. F21/F22 admission/backend/startup obligations
remain open implementation work; no worker/creation-DONE substitution. F23/F24/F25/F26/F27 now
have direct target rules in spec §§2.2/4.2 and increment STEPS, not recommendations in this review.
E244 additionally fixes construction order and the remaining project-IO ambiguities: selected FD
is not authority; safe private staging/new-parent no-replace; expected absence; complete-file SHA/
UTF-8 windows; cell ownership/modes; stale versus possible-effect/durability errors; no kernel-CAS
claim. Existing SessionManager DB/provisioning, metadata/search attribution and SLICE3/4 joins remain
mandatory. Implementation starts only after this docs checkpoint; local helper proof cannot close
F21–F27 or CT101–103. Actual host/full-path proof remains final SLICE6.
