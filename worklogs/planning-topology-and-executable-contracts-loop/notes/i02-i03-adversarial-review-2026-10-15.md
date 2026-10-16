# Adversarial review: retained I02, then execution foundation I03

**Current disposition:** E230/E231 below supersede historical open-policy statements. Planning
finalized against I02 source1132eee/runtimea32a72f; operator Q59/Q60/Q63/Q74 reconciled, no runtime
or deployment performed. Older baseline/line references remain historical, not current source claims.

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
