# Adversarial review: retained I02 and I03 execution foundation

**Initial review snapshot:** 2026-10-21. The first report was written before product-code or test
edits and recorded source snapshot `9be0a0aee4eb17f2f08bf6f1fc46c8f0caa0ef12`. The checkout’s pre-closeout HEAD
was `2f6b8c1` (the supplied base); the linked implementation is present as the staged diff on the
fixed branch `arena/ca4c996c-first-agent-dev`. This refresh supersedes the first-pass
claim that no fixes or current checks had been completed.

**Final refresh:** 2026-10-21, after confirming the five lifecycle fixes and their regression
coverage, verifying the candidate-buffer stale-plan regression, rerunning affected banks and final
static gates, and reviewing the staged change list. The cumulative staged diff is about 519 files,
with roughly 61,000 additions and 935 deletions; most of the size is retained plans, tests and
compressed evidence. This is a source-and-local-test review, not a deployment acceptance.

## Disposition

- **I02 stays “locally implemented and diff-reviewed, pending E2E tests as I03 ships.”** Its
  `SHIPPED` label remains scoped to the local explicit-plan gate, not deployment. The plan still
  leaves deployed source-to-behaviour, readiness/inherited-baseline review, broad independent review
  and integrated E2E acceptance to I03.
- **I03 remains `OUTLINED`, not production-ready.** E258’s `CellBackend` and E259’s view-purpose
  owners are locally implemented components, but the increment explicitly keeps its construction
  steps and all four transferred acceptance duties open. There is no production service/factory/
  caller cutover that uses `CellBackend`; no real Docker host or cgroup acceptance was run.
- **The five initial lifecycle findings R1–R5 are fixed in source and covered by passing local
  regressions.** This closes those component-level review findings, not I03 integration, service
  wiring or host acceptance. The candidate-buffer stale-plan concern was not a source defect; a
  direct regression now pins the verified reader recheck path.
- **Q66 remains open.** No public `context` field was added, and the source search still does not
  prove that bounded parent-chat context reaches the initial planner’s actual input tokens.
- **Final local verification:** Python 3.13.16; the 26-module affected I02 bank passed **1,399 tests with 12
  shellcheck skips** in 207.19s; the 16-module execution suite passed **1,039 tests** in 41.95s.
  Ruff/format, configured Mypy, full configured Pyrefly, Deptry, Pylint, authoring, lock, contract
  and shell-syntax checks passed. The installed-controller bank has **25 passed and 11 setup
  errors**: wheel builds fail because this toolchain’s CPython lacks `zlib`; these errors are not
  passes. No Docker/Ubuntu host or integrated deployment check ran. Exact commands/results and
  remaining blockers are below.

## Review method and scope

I read the retained I02 increment and acceptance note, the updated I03 plan and execution spec,
then traced the changed I02 admission/verification/controller path and I03 workspace/backend,
worker, Docker and journal call paths. Relevant files include:

- I02: `src/fa/inner_loop/workflow_controller.py`, `slice_verification.py`, `plan_admission.py`,
  `plan_promotion.py`, `admission_schema.py`, and `tests/test_verify_gate_live.py`.
- I03: `src/fa/execution/backend.py`, `workspace.py`, `journal.py`, `docker.py`,
  `cell_protocol.py`, `cell_worker.py`, `profiles.py`, and `tests/test_execution_backend.py` plus
  the workspace/admission/purpose tests.
- Normative references: I02 increment and `notes/i02-local-acceptance.md`; I03 spec §2.2
  (dispatch, episodes, restart, deadlines), §4 (views/admission), and the E240/E258/E259 notes
  embedded in the I03 plan/spec.

The staged delta from the supplied base is about 519 files and 61,000 added lines, including
retained history, plans, evidence and tests (the evidence directory is about 33 MiB). I reviewed the
changed runtime source and tests in the I02/I03 scope, compared the affected behavior against the
retained plans/specs and checked the full staged path inventory/whitespace. Historical compressed
evidence is retained as provenance; it is not independently re-run or recertified here. No unrelated
runtime product edit was identified.

## Initial findings and final resolutions

The impact labels below describe the original defect if the path were used; they are not claims of
an observed production exploit. Each finding was reproduced/fixed at the local component boundary,
and the listed regression passed in the final affected execution bank. Local Docker HTTP peers and
native workers remain C0/C3 evidence, not a real daemon, cgroup, or production integration proof.

### R1 — RESOLVED (original BLOCKER): noninteractive execution could not pass through `CellBackend`

**Initial evidence (pre-fix):** the public EXEC contract accepts `session_id: null` for a noninteractive profile;
`ExecutionProfile.create_spec()` adds `--one-shot` for that profile; but `CellBackend._run()`
rejects `None` before it writes a RUN frame. The private `cell_protocol` RUN schema also requires a
non-null session ID. Separately, `CellBackend` caches one episode per view and reuses its single
worker for later commands, which is incompatible with a worker that accepts one RUN and exits.
The backend fixture’s `native_profile()` uses the interactive profile, so its two-command test does
not cover this mode.

**Original impact:** I03 needs noninteractive jobs for verifier and other bounded operations. Merely
removing the null check would still let the first command consume the one-shot worker and make a
second command reuse an exited cell. The pre-fix path had no successful route matching the I03 contract.

**Resolution / local proof:** the backend now accepts the null session for an approved
noninteractive profile, creates and attaches a fresh one-shot cell per operation, sends one RUN,
then closes that worker instead of retaining it in the interactive episode map. The actual worker
accepts `session_id: null` only in one-shot mode and returns the command’s real exit/timeout result.
`tests/test_execution_backend.py::test_noninteractive_commands_use_null_sessions_and_fresh_one_shot_cells`
pins two successive fresh cells; `tests/test_execution_cell_worker.py` pins null-session success,
exit code 7 and timeout. The 16-module execution bank passed 1,039 tests.

### R2 — RESOLVED (original HIGH): create/start/attach were not under the admission effect gate

**Initial evidence (pre-fix):** `CellBackend.execute()` obtained and entered `WorkAdmission`, then
`_live_episode()` called `DockerCells.launch_new()` and `attach_created()` directly. The only
`scope.effect()` use on
this path is reached later through `scope.send()` for the RUN write. `WorkAdmission.effect()` is
the check that revalidates the live view, closed gate, durable claim and protected inputs. Thus a
close-admission that wins after `admit()` but before cell creation can still be followed by Docker
create/start/attach; the later RUN send can be denied, leaving an idle cell after closure.

**Contract:** the I03 spec requires admission/effect ordering at create/start/RUN boundaries, and the
plan says that if close wins no late effect occurs; if admission wins, drain owns the admitted work.

**Resolution / local proof:** `_live_episode()` now wraps Docker create, start and attach together
in `scope.effect()` (for both interactive and one-shot paths). The effect revalidates the live view,
closed gate, durable execution claim and trusted inputs while holding the authority transaction;
`admit()` itself is not treated as the effect guard. The paired barrier tests
`test_close_admission_that_wins_before_effect_prevents_create_start_attach_and_run` and
`test_effect_that_wins_blocks_close_until_create_attach_finish_then_drain_completes` passed. When
closure wins first there are no Docker requests or RUN; when the effect owns the gate first, closure
cannot cross create/start/attach, and a later closed gate prevents RUN. Journal container binding
continues to use the one-use create claim and request deadline.

### R3 — RESOLVED (original HIGH): cancellation bound the operation to namespace, not the requested view

**Initial evidence (pre-fix):** `CellBackend.cancel()` located an episode using the CANCEL request’s exact
`ViewRef`, but persisted intent using `OperationJournal.request_cancel(operation_id, namespace)`.
The pre-fix journal checked namespace and `op == exec`; it does not compare the record’s `view_ref` with the
requested view. A caller with two legitimate views in one namespace can name an operation from view
B while sending a cancel for view A: the journal can mark B cancelled while the backend force-stops
A’s cell. Request authorization of view A does not by itself establish that the journal operation
belongs to A.

**Resolution / local proof:** `OperationJournal.request_cancel()` now requires the exact `ViewRef`
and compares it with the stored `view_ref` inside the same journal transaction that writes the
cancel flag; `CellBackend.cancel()` passes the request’s view. The regression
`test_cancel_cannot_name_an_operation_from_another_view_in_same_namespace` creates both views,
checks that the cross-view CANCEL is `UNAUTHORIZED`, and asserts the record and Docker request list
are unchanged. The dispatcher/service composition remains unfinished, so its production
authorization/wiring is still an I03 acceptance obligation.

### R4 — RESOLVED (original HIGH): restart reconciliation omitted completed operations that still owned live cells

**Initial evidence (pre-fix):** `CellBackend.reconcile()` enumerated `journal.unfinished()`. That journal method
explicitly excludes `DONE` records. An interactive command can complete while its cell remains
alive with an idle shell or a background writer. After process restart the in-memory episode map is
gone, and a DONE journal record with a container ID is the durable link to that cell; the pre-fix
reconciler never inspected it.

**Contract:** I03 spec §2.2 explicitly says to discover/inspect all owned cells, including cells
whose creation command is DONE, because an idle interactive cell can outlive the command. `unfinished`
remains appropriate for uncertain command recovery, but it is not a complete owned-cell inventory.

**Resolution / local proof:** `OperationJournal.owned_cells()` now returns every EXEC record with
a durable container ID, including `DONE`; `CellBackend.reconcile()` consumes that inventory. The
regression `test_reconcile_inspects_done_owned_cell_after_backend_restart` marks the creation record
DONE while the fixture keeps the owned cell running, constructs a fresh backend and reconciles. It
observes/stops only the journal-bound labelled cell, issues no create/start/attach/RUN, and leaves
the original DONE journal record unchanged. This proves the local reconciliation projection, not
real daemon ownership or cgroup terminality.

### R5 — RESOLVED LOCALLY (original HIGH): the caller’s absolute deadline did not bound the full journal/episode path

**Initial evidence (pre-fix):** `_live_episode()` used an unbounded `with creation_lock:`. The journal had an optional
deadline only on `lookup`; service legs including reserve/begin/create-once/start-once/container
binding/cancel/complete/reconciliation use `_transaction()` without the caller’s deadline. Several
backend and DockerCells calls likewise omit it. Docker RPCs themselves receive the deadline, but a
request can first wait up to the journal’s independent lock budget or indefinitely for another
thread’s episode-creation lock. `_transaction()` currently translates lock acquisition `OSError`
(including deadline expiry) to `DURABILITY_UNKNOWN`, although a caller-deadline lock timeout before
any write is backend unavailability, not necessarily a durability uncertainty.

**Contract:** I03 §2.2 requires one absolute deadline to consume queue/admission/create/start/RUN
work, with no fresh phase budget or late follow-up.

**Resolution / local proof:** request-path journal operations now accept and use the original
absolute deadline; the episode registry mutex and per-episode creation lock are timed from the same
monotonic deadline, and Docker RPC/attach legs receive it unchanged. Journal lock expiry before the
transaction body maps to `BACKEND_UNAVAILABLE`, not a false durability-uncertainty claim.
`tests/test_execution_journal.py::test_deadline_expiring_on_journal_lock_is_backend_unavailable_before_create`
holds a real `flock` and proves no create callback or state transition occurs. The strengthened
`test_episode_creation_lock_uses_the_absolute_request_deadline` holds a real `threading.Lock`, waits
until acquisition is attempted, and proves the call returns at that lock’s deadline with no Docker
request or RUN. Both regressions passed in the final execution suite. This validates the covered
component legs; it does not replace an integrated end-to-end service deadline test on a real host.

## Concern checked and downgraded

### Candidate-buffer PlanRef/record recheck — no source defect; targeted coverage now present

`_candidate_buffer()` itself begins with `_reader_proof()`, which is only the in-memory proof. But
`read_candidate()` and `write_candidate()` call it inside `with self._transaction(...),
self._file_work(...)`. `_file_work()` calls `_live_view()`; for a READ view that calls `_reader()`,
which rechecks the protected view record, retained revision identity/manifest and
`ProtectedPlanContext.recheck()` before the candidate-buffer operation. Therefore the earlier
static suspicion that candidate-buffer operations bypass the full reader recheck was incomplete:
the recheck is indirect and present.

The targeted regression `tests/test_execution_purposes.py::test_candidate_buffer_read_and_write_recheck_the_protected_plan`
now mutates the protected plan after candidate-view creation and confirms both candidate read and
write are rejected before a staging buffer is created. This pins the existing indirect
`_file_work → _live_view → _reader` recheck. No implementation change was needed.

## I02 contract review: positive findings and limits

Static call-path review supports the retained I02 design:

- `_effective_controller_route()` keeps evaluator non-complete routes, blocks missing required
  evidence and indeterminate verification in both gate modes, and makes determinate verification
  failures advisory in observe but repairable in enforce. `_ensure_eval_after_coder()` places eval
  after each coder. The model-authored `EvalReport` is retained rather than replaced by a synthetic
  verifier verdict.
- The coder-stage verifier captures T0 before dispatch, verifies after a successful coder stage,
  and records baseline/current capture or artifact failures as explicit evidence. The baseline is
  created exclusively, validates run/slice/test-path topology when reloaded, and is not refreshed
  for a later repair round. Relevant T0/eval/gate regressions passed in the 26-module I02 bank;
  no Docker/host behavior is inferred.
- Explicit plan admission reads a bounded no-follow snapshot, validates diagnostics against that
  immutable snapshot, stages a scoped candidate, validates the captured candidate bytes, and
  promotes only those bytes. Promotion uses a cooperative lock/CAS and distinguishes pre- and
  post-replacement failure. The append-only admission attempts are validated as a complete v1
  history. I found no basis to alter Q57/Q58 or introduce an unapproved PlanRef protocol.
- `verify_slice()` applies each FUNCTIONAL mutation against every path in that slice’s declared
  `TESTS:` set, as Q53(c) requires. It intentionally does not introduce per-contract nodeid mapping;
  the accepted unrelated-test attribution risk remains. The mutation roots remain `src`/`scripts`,
  not tests. The test fixture for the C1 composition path uses real
  `run_workflow → _cmd_run → drive_session` and replaces only `ProviderChain.request`; it is useful
  local composition evidence, not an OS boundary.
- Q54 keeps FUNCTIONAL mutation roots at `src/` plus only explicitly allowed `scripts/`; tests
  remain outside the mutation roots. The plan’s append-only ledger/history is preserved, and the
  historical E19 obligations are not rewritten or waived. Plan/artifact IO remains fail-closed;
  missing/corrupt admission history or uncertain promotion cannot degrade into an ordinary plan
  success. Q57/Q58 and the approved PlanRef behavior stay within their recorded scope; no new
  protocol was introduced.
- Q65 parser source-position fields are retained. Q64 calibration remains deferred to I06; the
  20-slice / ≥95% target is not an I02 acceptance gate. Q55/Q56 route/status ordering remains as
  reviewed above. The review did not convert Q59/Q62/Q63 or Q60(a) into decisions, add a public
  `context` field, or change I01 ownership. `fs_spawn_subagent` is not enabled in current workflow
  stages; no default-off flag or post-hoc hash is treated as an OS isolation boundary. Q66’s bounded
  parent-context-to-planner-input proof remains a separate obligation.

## Final local verification for this refresh

All results below are from the current staged source/test diff unless explicitly labelled as
historical. Toolchain: external CPython 3.13.16 under `/home/user/arena-toolchain/tests313`, with
`PYTHONPATH=src`; the temporary repository `.venv` symlink used by workflow subprocess fixtures was
removed after testing.

| Check | Final result |
| :--- | :--- |
| Affected I02 plan/verification/workflow bank (26 modules) | **1,399 passed, 12 skipped, 0 failed**, 207.19s. All 12 skips are the deploy-script cases gated on unavailable `shellcheck`. |
| I03 execution component bank (`tests/test_execution_*.py`, 16 modules) | **1,039 passed, 0 skipped/errors**, 41.95s; includes the strengthened real-lock deadline regression and R1–R5 coverage. |
| Installed-controller entry tests (`test_controller_entry.py`, `test_controller_installed.py`) | **25 passed, 11 setup errors**. The errors are not passes: each blocked path attempts an offline wheel build and reaches Hatchling, then fails because this CPython was built without `zlib` (`RuntimeError: Compression requires the (missing) zlib module`). Hatchling itself was present in uv's cache, so the confirmed immediate cause is missing zlib; other offline-install requirements remain untested behind that failure. |
| `uv lock --check`; `fa authoring-check`; dependency, producer-consumer, log-kind, no-mocked-dataclasses contracts; shell syntax | **All exit 0**. |
| Ruff check + format check | **Pass**; 524 files already formatted. |
| Configured MyPy | **Pass**; no issues in 486 source files. |
| Deptry | **Pass**; no dependency issues. |
| Pylint | **10.00/10** for `src/fa`. |
| Configured Pyrefly | **0 errors, 511 modules**, with 142 configured suppressions and 46 warnings not shown; this is not a warning-free claim. The external toolchain initially lacked the locked `pytest-gremlins` package needed by `scripts/count_mutants.py`; it was temporarily installed for this full check and removed afterward because the toolchain's missing zlib makes its pytest/coverage auto-plugin unusable. The new episode-lock test also passed targeted Pyrefly with 0 errors. |
| Staged diff whitespace | Final `git diff --cached --check` passed after staging this report. |

An earlier attempt at the I02 bank, after removing the temporary `.venv` link too soon, had one
fixture setup failure because `tests/workflow_fixtures.py` expects that symlink to exist. After
restoring it, the entire 26-module bank passed as reported above; the symlink was then removed again.
The installed-controller failures remain explicitly visible. The retained E229 full `just check`
result is still **rc 1**, with one readiness integration failure and its documented environment
cause; this review did not rerun or relabel that repository-wide result. The earlier corrected
I02/contract evidence is historical and is not substituted for these current test runs.

## Ubuntu/Docker and unintended-change assessment

The intended image is Ubuntu 24.04/Python 3.13, which matches the project’s declared interpreter
floor. `Dockerfile.fa` now builds a non-editable installed controller closure and runs its install
check/help path. The Python warning filter added for E258 names one forkpty DeprecationWarning
message rather than suppressing warnings broadly. These changes are scoped and documented.

The deployment is still not integrated: `CellBackend` has no production caller/factory in `src/fa`,
`SupervisorDispatcher` has no service main, and the current Compose file has no Docker daemon
connection or execution-supervisor service. The entrypoint still prepends workspace source via
`PYTHONPATH`; the controller’s immutable installed-code boundary is therefore not activated by the
Dockerfile change alone. These are explicitly future I03 cutover work, not deployment proof. Do not
mount an unrestricted Docker socket into the model-facing controller as a shortcut; that grants
broad daemon authority and can collapse the isolation boundary. A trusted host supervisor or
narrowly authorized daemon API is the viable production pattern, but deployment architecture remains
subject to the I03 plan and operator approval.

No Docker image build, Compose validation, Ubuntu runtime test, cgroup-v2 terminality test,
read-only mount check, daemon authorization test, source-to-behaviour test or integrated authority /
backend / receipt test ran here. Local HTTP peers and native-worker fixtures are C0/C3 component
evidence only. The E259 purposes implementation likewise does not prove its still-open provisioning
consumer, candidate-buffer cutover, sealing/export, receipt or terminality requirements.

## Remaining acceptance and next checks

The local component gaps in R1–R5 and the candidate-buffer stale-plan concern are now covered by
passing regressions. Do not repeat them as open implementation defects. The following remain
unproven and are required before production claims:

1. Compose the real `WorkspaceAuthority`, `CellBackend`, dispatcher, startup recovery and service
   lifecycle behind an authenticated production factory; cut callers over only at the plan’s
   prescribed integration step. Preserve a narrow trusted host-supervisor/daemon boundary; do not
   give the model-facing controller unrestricted Docker-socket authority.
2. Finish the I03 consumers and joins still open in the plan: provisioning views, candidate-buffer
   cutover, stage checkpoints, immutable export/sealing, receipts and terminal barriers. Local
   view-purpose tests do not prove those downstream consumers.
3. Keep **Q66 open** until a runtime test captures bounded parent-chat context internally and
   demonstrates that it reaches the initial planner’s actual provider input tokens. Keep the public
   tool schema free of `context`; do not treat task text or a session namespace as this proof.
4. On an approved disposable Ubuntu 24.04/Docker host, execute the frozen-image installed-controller
   build/audit, Compose validation, actual daemon attach/termination and cgroup-v2 descendant
   terminality tests, read-only mount checks, source-to-behaviour checks and integrated authority /
   backend / receipt E2E. Fix or provision CPython zlib in the test environment before retrying the
   installed-wheel bank; retain the current 11 setup errors until a true rerun succeeds.
5. Resolve the retained full-repository `just check` rc1/readiness environment result, and complete
   I03’s inherited-baseline/readiness disposition, broad independent implementation/evidence review
   and final deployment signoff. Keep all four transferred acceptance duties open until their
   source-bound evidence is reviewed; do not upgrade archived PASS counts.

I02 remains **locally implemented and diff-reviewed, pending E2E tests as I03 ships**. Deployed
source-to-behaviour, readiness/inherited-baseline acceptance, broad independent review, integrated
E2E, descendant terminality and Ubuntu/Docker deployment signoff remain open.
