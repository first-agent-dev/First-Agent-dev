# Adversarial review: retained I02, then execution foundation I03

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
