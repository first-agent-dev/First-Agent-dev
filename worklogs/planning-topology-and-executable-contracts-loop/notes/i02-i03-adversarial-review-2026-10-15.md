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
| R02-01 HIGH — initial attempt has no honest schema kind | `notes/i02-to-i03-scope-migration-2026-10-15.md:83–102`; I02 `:491–499` | EXPLICIT-only I02 is told ACQUISITION is I03-reserved, but its initial attempt can only be acquisition/repair/replan. New normative spec adds EXPLICIT_INPUT and cross-field invariants; old schema is historical, not a second authority. |
| R02-02 HIGH — exact schema is not implementable from an unlisted enum | migration bank `:103–111`; `notes/open-questions-2026-10-07.md:1079–1109`; `src/fa/inner_loop/plan_ids.py:760–1210` and `slice_verification.py:667–777` | Supply the concrete per-validator tables and strict JSON type checks, including rejecting bool integers. No arbitrary error text/code or speculative managed bootstrap success. Q62 is explicitly an implementation-spec gap, not an operator-policy decision. |
| R02-03 HIGH — preflight needs a side-effect-free workspace resolver | I02 `:485–488`; `src/fa/cli.py:280–316,1364–1368,1432–1443` | Current lifecycle resolution claims session/run and can prepare workspace; current path check uses CWD. Name a read-only manager method, order task/inject/PlanRef checks before lifecycle, then compare the allocated root. Do not 'resolve' via begin_run. |
| R02-04 HIGH — impossible rejection artifact obligation | I02 `:512–520`; `src/fa/inner_loop/workflow_controller.py:1885–1904`; `src/fa/session/manager.py:408–444` | Cannot both reject malformed run ID before paths and persist admission under it. Split malformed request/no artifacts from safely addressed PlanRef/BLOCKED artifacts, and storage failure/no persistence claim. |
| R02-05 HIGH — requested order contradicts Q55 and permits stale tail planning | I02 `:439–449,512–513`; controller `:1426–1442,1774–1837`; `tests/test_verify_gate_live.py:164–170` | Existing normalizer relocates eval and supports repeated coders. Specify that exception, retain repeated-coder tests, reject ordinary planner-after-coder/duplicate ordinary planner, and use bounded adaptive replanning instead. This is an explicit new limitation, not a scheduler hidden inside admission. |
| R02-06 HIGH — observe can waive the newly required integrity floor | I02 `:434–438,518–520,565–566`; controller `:551–588,1161–1165` | Existing observe returns model route before verifier errors; eval IDs reread the mutable target. Pin one admitted snapshot for verifier/eval; post-coder hash/storage/missing-evidence errors reach real eval then block both modes. Keep ordinary determinate gate judgment advisory in observe. |
| R02-07 HIGH — no binary T0 failure/order contract | I02 `:462–466,533`; controller `:318–359,362–391,1057–1081`; real fixture `tests/test_verify_gate_live.py:548` | CT86 already correctly requires write-once/topology; it lacks what to do on capture/storage failure. Name run-local baseline state; failed T0 blocks before coder, legitimate red baseline allowed, no recapture after repeated coder/replan. Move fixture plan inside its disposable workspace. |
| R02-08 HIGH — future early-error handling could suppress eval | controller `:1093–1141,1448–1477,1774–1800`; I02 `:496–499` | Any nonzero coder StageResult exits current loops immediately. Require post-coder integrity/IO errors as typed attempt evidence, not an early nonzero return; eval then nonzero terminal. Deadline exhaustion is a visible failure, not an impossible promise of model execution. |
| R02-09 MEDIUM — full-suite disposition has no executable comparison contract | I02 `:574–578`; E174 and E192 historical evidence; `justfile:131–183` | Name actual just gates, isolated source baseline and identical environment, complete manifests/normal summaries, exact nodeid+phase comparison, changed-file gates and explicit reviewed baseline dispositions. Aborted/no-summary run cannot pass; acceptance report has a named future path. |
| R02-10 HIGH — target writer/path guarantees stop short of alias/race handling | I02 `:501–511`; `src/fa/inner_loop/profiles.py:275–313`; `tools/write_file.py:15–58`; controller `:436–475` | Exact scoped writer cannot delegate to unchecked write_text after a string prefix check. Require descriptor-rooted no-follow IO, single-link regular target, immutable validated promotion buffer, complete prior-artifact validation and concurrent append proof. Preserve pre/post-replace distinction. |

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

Pending the second bounded review step; OUTLINED/slices=0 is not implementation authorization.
The source-grounded expanded brief and exact residual blockers will be recorded here next.

## 6. Validation log

Results are appended only after checks execute. Runtime pytest/type/Docker results are not implied
by pure document/extractor/AST validation.

First step checks: actual stdlib leaf precheck: I01 7 slices/1 diagnostic, I02 7/8,
I03 outline 0/7; all zero FAIL (warnings are not runtime proof). I02 retains exactly 16 SLICE6
FUNCTIONAL and unchanged checked STEP markers. Closed validator rules match actual source
constructors. Executed actual-source AST normalizer/exit helper: eval relocation and missing-state
exit 0 reproduced. Initial AST harness lacked lineno; corrected with ast.fix_missing_locations,
rerun PASS. `git diff --check` PASS. No package imports, pytest, Mypy or Docker tests executed.
