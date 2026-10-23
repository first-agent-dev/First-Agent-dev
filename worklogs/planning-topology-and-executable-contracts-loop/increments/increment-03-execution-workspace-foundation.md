---
Increment-ID: RM-planning-topology-I03
Roadmap-ID: RM-planning-topology
status: OUTLINED
slices: 6
shipped: —
---

# INCREMENT I03: Execution/workspace foundation and integrated acceptance

**Planning state:** E230/E231 retained; E243/E244 directly repair remaining joins/IO semantics before E245 construction.
Q59 advisory/manual + EXISTING experimental suggestion injection, no required mode; Q60 delegated
source-grounded reuse design in spec §7; Q63 four states/optional commentary/no reason enum; Q74
per-stage/episode ordinary-edit checkpoints. E233 found F17/Q75; the operator explicitly selected
Q75(a) in E234: narrowly bound memory-only original completed-reply replay, secret-free journal,
no fresh authority/re-execution/reconstruction. The stop is lifted; SLICE1 implementation resumes. OUTLINED
is deliberately unchanged: plan finalization assigns no implementation tick, READY automation,
live result or deployment authorization. All35 construction steps and final acceptance remain open.

**Depends on:** retained I02 local implementation/checks and plan-versus-diff review; no restored
I02 deployed-host, broad independent-review or inherited-baseline acceptance prerequisite.
**E223 final-acceptance ownership:** all four transferred obligations are unfinished under SLICE6:
deployed functional/source-to-behaviour verification; environment/readiness and inherited baseline
acceptance review; broad independent implementation/evidence review; integrated E2E/deployment signoff.
The E231 decisions finalize the plan, not runtime delivery or either increment’s final acceptance.
**Shippable when:** all project execution uses mandatory Linux/Docker cells, one protected workspace
writer owns coherent private views/pinned readers, terminal sealing/fenced publication/recovery
are proved, real nested selection/bootstrap/context works, and every unique required I02+I03
producer has reviewed deployed-main acceptance. PTY remains. Backend unavailable fails closed in
both observe/enforce and for every role. Partial backend success is not whole-product isolation.

**Normative detail:** [execution/workspace spec](../notes/i03-execution-workspace-spec-2026-10-15.md).
**Evidence/review:** [adversarial review](../notes/i02-i03-adversarial-review-2026-10-15.md).
**Lineage:** [migration bank](../notes/i02-to-i03-scope-migration-2026-10-15.md),
[decisions](../notes/execution-workspace-and-i02-i03-scope-decisions-2026-10-15.md),
[reuse audit](../notes/execution-foundation-scope-reduction-and-reuse-audit-2026-10-15.md).
New module/function/test names below are **planned interfaces**, not claims about complete code.
E234 adds only immutable NamespaceRef/ViewRef, closed operation/purpose names, four grant-result
shapes, canonical input hashing and a bounded completed-grant-reply cache in types.py/supervisor.py.
These are C0/C3 foundations, NOT a wire decoder, journal, dispatcher, issuer, client or service.
E235 adds the complete closed wire/receipt codec and72 C0/C3 cases; all19 operation payload/result
shapes are covered, including real socketpair framing. No authority/service activation.
E236 adds fixed-profile rendering, a single-attempt authenticated-UDS client, receipt binding, all
four managed PTY methods and a cell-local framed PTY worker. C0/C3 only; no factory activation.
E237 adds protected operation journal, one-claim/cancel/start guards, startup singleton scope,
absolute RPC deadline and per-connection kernel-peer dispatcher with REQUIRED authority/backend
callbacks. Q75 covers successful non-grant replies too. C0/C3, not a running production service.
E238 prepares the frozen noneditable Docker install + pre-site gate and real installed CLI C2/C3
fixtures (source-byte matched, no mocked CLI); profile/session mode checked before callbacks.
E239 records the operator's explicit Q76(a) selection: protected admitted PlanRef + source recheck,
ordinary no-active-workflow null permitted, formal evidence requires actual plan; no new workflow
mode. F18 closed admission/context/receipt checks are constructed: owning347PASS/restored347PASS,
six full347kills4/6/3/1/2/1, broader768PASS; actual protected loader/authority/controller persistence
integration remains unproved. No guessed hash, C1/service proof or activation.
E240 corrects F19: fixed noninteractive one-shot worker preserves determinate command status;
interactive worker remains persistent. Local361PASS/restored361PASS, three full-bank kills1/1/8;
broader782PASS. Build toward the complete target contracts, not today's helpers. Existing verification
schedule below already defers required host acceptance without blocking dependency-order coding.
STEP1–4 remain unchecked; producer helpers exist, but C1 factory/authority/kernel wiring is uncredited.
E241 constructs private authenticated Docker create/start/owned-inspect transport + durable one-use
create claim and required injected resource validator. Start ACK is only a CID, not an exec result;
non-exited observations cannot turn provisional exit0 into success. No per-command new-cell reuse,
receipt issuance, real authority or C1/host proof. Actual backend/episode/attach/lifecycle and service
wiring remain target work. Local owning415PASS/restored415PASS, ten full-bank kills2/6/2/1/3/2/2/1/7/1;
no STEP/acceptance ticks or changed verification schedule.
E242 adds fixed live-only upgraded Docker attach, shared closed cell codec and a concurrent private
worker client (one RUN plus control) with bounded framing/deadlines, correlated replies and poisoned
stream uncertainty without reconnect/resend. Actual local PTY/worker transport tests are C0/C3, not
Docker/kernel/C1 acceptance. Protected episode registry, durable per-command backend/lifecycle,
actual authority and service/controller integration still required; all35STEPS remain unchecked.

E243 closes the short-control-RPC/long-command reply defect and makes remaining SLICE1/2 composition
executable in spec §§2.2/4.2: one authority/admission gate, existing journal per command, live-only
episode ownership, same-view read/search and safe SessionManager provisioning/cleanup. Component
repair is not complete backend/authority delivery; all35STEPS/four final duties remain unfinished.

E244 docs-first checkpoint `a7ba6d5` precedes E245 source. E245 constructs internal
`execution/view_io.py`: pinned FD/no-follow text IO, private staging/no-clobber parents, expected-SHA
writes, safe cell modes/UIDs and explicit uncertainty. Real-FS C0/C3 bank93/restored93;17 whole-bank
assertion kills, exact518 Python/build/lock hashes; broader1001PASS, static/Pyrefly PASS. See
[component evidence](../notes/evidence/i03-e245/rooted-io.json.gz). This is the STEP1 building block,
NOT WorkspaceAuthority/admission/materialization, actual public tool/PTY joins or CT101–103 closure.
All35STEPS/four final duties stay unchecked. Next: implement the one actual authority, not more
standalone wrappers or a permissive service. Required host/full-path acceptance remains final SLICE6.

## Grounding, sequence and scope discipline

- Current `run_bash` and `_build_pty_pool` deliberately fall back to host subprocess; SubagentRunner,
  readiness, verifier and Git helpers execute independently. Enforcing only one shell adapter leaks.
- Existing SessionManager rejects second-session reuse; begin_run already reserves unique run/DB
  namespace. I02 `_child_run_context` ALREADY allocates valid distinct child contexts for non-coder
  delegation; extend it for managed acquisition, never duplicate allocation or regress Q70.
- Existing FastAPI server is an optional PTY transport, not supervisor; timeout/identity/lifecycle
  fields and descendant barrier are incomplete. No standalone server-completion milestone.
- Materialized snapshots, one local authority and fixed profiles suffice. No overlay/CAS backend
  matrix, lease service, distributed scheduler, advanced logging/GC or parallel orchestration.
- Sequence is **A→B→C→E→D→F** from the migration bank: whole execution integration (SLICE4) comes
  before nested composition (SLICE5), preventing a nested proof over an unsafe old prologue.
- Do not expose production managed execution until SLICE1–SLICE4 closure. Intermediate commits
  confer no safe deployment claim; do not keep an unsafe permissive backend as a compatibility mode.
- New-session/old-workspace reuse, private Git metadata/history limitations, conservative copy caps
  and filesystem support are explicit contracts in spec §§2–5, not already-supported guarantees.


## E230 trajectory and execution prerequisites (plan review, not implementation)

**Mid-roadmap target:** on the intended Ubuntu/Docker main deployment, execute a real explicit-plan
workflow AND ordinary outer chat→invoke→managed child workflow, with actual provider requests,
useful source edits/tests, admission/T0/verification/actual eval and persisted terminal evidence.
This increment is sufficient in scope for that CURRENT whole-plan system only after its
mechanics and final host acceptance are complete. It does not deliver per-slice scheduling, automatic
STEP/CT tracking or L2 VERIFIED. Those remain the named deferred successor; do not advertise that
broader roadmap loop as live-tested. I01 remains active pending its own disposition, not auto-closed.

**Source truth:** E243 reviews `e736082` (E242); `1132eee`/I02 E229 is historical retained I02 evidence,
not the current execution implementation. The original 17 FUNCTIONAL IDs remain; new private interfaces are obligations to implement/test, not existing-code assertions.
Spec §§2.1–2.2/4.1–4.2/5.1/6.1/7.1/9.1 are part of every affected STEP's contract, including error/restart
paths. All runtime/host boxes remain unchecked. Do not run deployment during plan finalization.

**Verification schedule:** design the per-slice unit/kernel oracles with each slice. Ordinary unit
checks can run during construction; local disposable Docker integration may run where available.
The `FA_REQUIRE_EXECUTION_HOST=1` commands and full declared-path kills are REQUIRED release proof,
not permission to exercise the production main host before final SLICE6 STEP7 review/STEP10 approval.
If there is no approved disposable Docker host earlier, record those checks NOT RUN/BLOCKED, never
PASS or a narrowed unit-only kill. Coding may progress in dependency order; no slice/product safety
acceptance or production enablement follows until all accumulated required checks pass at SLICE6.
Final e2e/I03 fixtures/helpers are different from local tests/integration; STEP7 review precedes their
implementation, followed by review of actual helper code before first main-host execution.

**Deterministic scheduling:** all wire/state/type validation precedes launch. Acquire one owner,
then open views through that authority; stage prologue/provisioning is inside the boundary too.
A workflow deadline is one absolute monotonic budget across admission/provider/stage transitions,
exec and terminal barriers. Each request uses min(configured operation limit, remaining budget);
none may start after expiry. Operation elapsed times are supervisor observations, not caller clocks.
Timeout returns unsuccessful/unknown and retains fencing until terminality. Best-effort eval after
coder still obeys Q55/Q56/Q73 and may use only a safely sealed source plus explicit uncertainty.

## E246 — verified SLICE1 next menu (437ee25, before new implementation)

**SLICE1 is NOT shipped.** E242/e736082 and E245 are construction checkpoints, not completed
CT98–CT100a. Every SLICE1 STEP remains unchecked; test totals do not establish a production join.

| Obligation | Source-verified status at437ee25 | Next required work |
|---|---|---|
| STEP1 / CT98, CT100 seams | Installed entry/codec/client exist. client.py127–129 maps every ERROR to rejection, including unknown/unavailable. | FIRST repair typed ERROR handling through all four BashExecutor methods; assert original request identity/no resend. Retain installed-entry/deadline/receipt checks. |
| STEP2 / CT99–100 | backend.py/CellBackend absent; docker.py396–503 only creates/inspects/attaches. No stop/kill/control leg, exclusive episode map, reused-command owner or restart reconciliation. | NEXT owned Docker stop/kill/observation primitives; then actual CellBackend episode/per-command dispatch/cancel/restart, with the one real WorkspaceAuthority admission/drain dependency. No fake grant issuer. |
| STEP3 / CT98–99 | supervisor.py225–234 accepts callbacks; file ends after serve_connection, no build_supervisor/main/listener/config/install. scripts/fa59 and fa-update.sh839–840 retain legacy imports. | Compose actual authority/backend and closed handlers; prepare service/profile/config. Complete publication-dependent factory in SLICE3 and caller/mount activation atomically in SLICE4, not early. |
| STEP4 / CT100a, release proof | Profile rendering is not approved host facts; tests/integration/test_execution_boundary.py absent. No actual Docker/cgroup/full-path proof supplied. | Implement required integration suite as composition becomes available; execute non-skipped actual host/full-path evidence at final SLICE6. NOT an intervening approval/deployment prerequisite. |

Proceed in this order, not another standalone rooted-IO helper. Cross-slice authority construction
is a necessary dependency of the SLICE1 backend, not a reason to claim SLICE1 complete first.
Existing four final duties, Q59/Q75/Q76 and35 unchecked STEPS remain unchanged.

## E247 — first menu repair implemented, SLICE1 still NOT shipped

E247 closes only the first E246 menu item: existing client ERROR taxonomy, not SLICE1 delivery.
`client.py` now preserves closed uncertainty codes/original-or-supplied operation references and
backend-unavailable metadata across run/INTERRUPT/CLOSE/LIST, with fixed sanitized messages and no
resend. Existing exception constructors/timeout subtype remain compatible; no wire/schema change.
TEST-EDITS: `tests/test_execution_client.py` fixture gains optional error metadata; all old defaults
and assertions retained.142 new cases cover15 codes ×4methods ×2retryable, supplied references and
constructor/closed-bank compatibility. Before repair:61 assertion failures/80pass in141 selected.
Full owning14-module bank623PASS43.09s → six whole623-bank assertion-only kills48/12/36/32/4/141 →
restored623PASS42.15s; all setup/teardown pass, no skips/warnings/collection/runtime/infra credit.
Exact597 tracked non-knowledge/worklogs hashes restored. Ruff/format26PASS, Mypy26/183PASS,
configured+clean-path Pyrefly0errors (existing141suppressed/50warnings); broader27modules1143PASS54.92s,
all phases clean. Local Python3.13.16/frozen tooling, not host/deployment/full just-check acceptance.
Evidence `notes/evidence/i03-e247/typed-errors.json.gz` includes snapshots, mutations, raw phases,
pre-code failures, runners and toolchain provenance; 795957bytes SHA256d85358b63274ce97cbb510b6ded8445667c8bdf39cc1e8d424984d1a43db8f63.
NEXT remains owned Docker termination/observation, then actual CellBackend–WorkspaceAuthority and
factory/caller composition in existing dependency order. All35STEPS/four final duties stay unchecked;
Q59/Q75/Q76/final-SLICE6 host/full-path proof unchanged. No fake authority or early-host gate.

## E248 — next native lifecycle leg clarified before implementation

E247 closed the client taxonomy defect only. NEXT extend existing DockerCells/Engine with owned
fixed-SIGKILL force-stop and independent same-CID observation per spec§2.2. Persist original creation
cancel intent before daemon contact; never equate ACK/409/404 with death or release, never replay
RUN/create/start. No signal/grace configuration or new service/authority/history. The whole STEP2
and actual CellBackend–WorkspaceAuthority join remain open, including per-command cancellation,
completed-creation/live-cell startup discovery and actual descendant/cgroup barrier. Final host/
full-path proof remains SLICE6; no intervening approval gate or completion ticks.

## E249 — native lifecycle leg implemented; backend–authority NEXT

E249 implements the existing E248 native force-stop contract in DockerCells/Engine only.
Original creation namespace/input binding → durable cancel intent → owned inspect → one fixed
full-CID SIGKILL → independent SAME-CID observation. Already-exited needs only fresh inspect;
409 still observes;404/lost/malformed replies stay unavailable/uncertain, never terminal receipts.
No create/start/RUN/reconnect/resend, no signal/grace setting, no result rewrite or lease release.
Recheck the one absolute deadline after journal lookup and at each native HTTP leg. A completed
creation command's still-live cell is stoppable without replacing its original result.
TEST-EDITS:61 appended real-journal/literal-UDS C0/C3 cases; old Docker tests are an exact byte prefix.
Final whole14-module bank684PASS42.05s → nine whole684-bank assertion-only kills48/7/4/32/1/1/1/1/3 →
restored684PASS42.35s; exact597 tracked non-knowledge/worklogs hashes, clean setup/teardown,
no skips/warnings/collection/runtime/infra credit. Ruff/format26PASS; Mypy26/183PASS; configured+
clean-path Pyrefly0errors (existing141suppressed/50warnings). Broader27modules1204PASS54.79s,
all phases clean. First invalid DONE-without-CID fixture and two overly restrictive proof-checker
rejections retained, not relabelled or sensitivity credit. No old assertion/suppression/dependency change.
Evidence `notes/evidence/i03-e249/owned-stop.json.gz` contains source snapshots, raw phases/runners,
restoration, rejected diagnostics and full hash-verified Moby API reference (not host facts).
Archive1407639bytes SHA25650340b4a9e421c8d9dfcf8be1ed4d578218787f041e6bc464be179a0a8b12991. Local tooling only, not full just-check/deployment acceptance.
SLICE1 remains NOT shipped: actual CellBackend–WorkspaceAuthority admission/episodes/per-command
routing/drain/startup discovery/cgroup barrier and factory/callers remain next in existing order.
All35STEPS/four final duties unchecked; Q59/Q75/Q76/final-SLICE6 actual host/full-path proof unchanged.

## E251 — explicit peer/deadline composition seam repaired

E251 repairs the existing dispatcher composition seam, not the actual backend/authority.
DeadlineConnection retains one monotonic request start and exposes read-only start/reply deadline;
required typed authorizer/
handler protocols receive authenticated PeerIdentity and keyword execution deadline through
readonly/reserved operations. Exec deadline = original start + requested command budget; reply
waiting alone keeps the separate control+command allowance. Valid but command-late input invokes
neither authority nor backend. No clock reset, raw-wire identity or fallback callback. Expiry before fresh
authorization/begin/backend prevents late calls; reserved failure remains UNKNOWN. Actual returned
results still persist truthfully even when transport reply expires; Q75 cached original replay
invokes neither callback. Actual admission/drain/command budget/terminality owners remain absent.
TEST-EDITS: dispatch/plan fixtures and direct calls gain explicit peer/deadline arguments; all old
assertion ASTs retained except required deadline keyword in asserted private calls.48 new C0/C3
real-socket/journal cases cover all19 operations, mutating PTY controls, invalid/expired budgets,
authorization/begin elapsed time and no replay. No fake production authority or C1 claim.
Owning15modules732PASS43.34s → nine full732-bank assertion-only kills26/62/26/26/4/16/2/2/1 → restored732PASS42.05s;
all setup/call/teardown clean except intended mutant CALL assertions; no skips/warnings/collection/
runtime/infra credit.598 declared source/input hashes (including new test) exact. Ruff/format27PASS,
Mypy27/183PASS, configured+clean-path Pyrefly0errors (existing141suppressed/50warnings); broader
28modules1251PASS/1FAIL53.71s: immediate second RUN raises WorkerUnavailableError.
This is a real unresolved worker reply/gate race, NOT inherited noise or a green broader gate. Initial missing-keyword fixture migration/lint diagnostics
and missing formatted mutation anchor retained/described, not final kill credit. Superseded
transport-budget source proof and three Pyrefly fixture-unpack errors retained; corrected explicit
ViewRef fields without suppression, fresh final-source baseline/nine kills/restored run PASS.
Evidence `notes/evidence/i03-e251/context-seam.json.gz`, 1929361bytes SHA25689dafdfa8f9fa14c479f21e7d68d76c0acceefa1277a3344aece41941fbd63f7,
contains raw phases/snapshots/runners/restoration and E250 inventory rollforward; all16 production
surfaces/eight joins remain tracked, live verdicts still PLANNED/UNEXECUTED. No actual host run.
NEXT fix the confirmed worker reply/gate handoff race with deterministic scheduling proof; then
actual WorkspaceAuthority registration/generation/materialization/admit/drain joined to the
real CellBackend; no temporary issuer. SLICE1/2/all35STEPS/four final duties remain unfinished;
Q59/Q75/Q76 and final-SLICE6 host/full-path release proof unchanged. No new policy adopted.

## SLICE1: Trusted launch and single supervised execution backend
STEPS: prescriptive
DEPS: none
INTENT: establish immutable controller launch and authenticated fixed-profile Docker jobs with PTY,
  truthful timeout/uncertainty and no command replay; workspace publication follows in SLICE2/3.
CONTRACTS:
  CT98 [FUNCTIONAL]: entrypoint/wrapper/help/auto-run/session launches use installed immutable
    controller_entry with isolated Python and verified package/dependency closure. No project CWD,
    PYTHONPATH/editable pth/project venv import; project imports occur only in cells. The new module
    has an actual __main__ guard; current -m fa.cli is not a runnable CLI. Spec §2.
    kill: remove-call src/fa/controller_entry.py::_main -> _assert_controller_import_closure
  CT99 [FUNCTIONAL]: one private-UDS host supervisor authenticates caller, strictly validates framed
    requests, namespace/view/profile capability and configured limits before Docker. No raw image/
    mount/env/host-path/daemon API or public listener; no daemon socket/control secrets in cells.
    kill: remove-call src/fa/execution/supervisor.py::_dispatch -> _authorize_request
  CT100 [FUNCTIONAL]: ManagedBashExecutor reserves one operation and executes only inside its
    authorized cell; PTY timeout/disconnect remains typed uncertainty, inspect/cancel never replays
    shell through host subprocess. Interactive profiles reuse only their exact live episode; each
    noninteractive one-shot EXEC accepts `session_id=null`, uses a fresh cell/attach, sends one RUN and
    is never cached for a later operation. Same-op replay never creates a replacement. CANCEL of a
    live one-shot must resolve its exact operation/journal-bound CID without the interactive episode map. Preserve
    PtyResult fields/timeout; receipt status is truthful. Spec §§2.1–2.2.
    kill: remove-call src/fa/execution/client.py::ManagedBashExecutor.run -> _execute_once
  CT100a [CONSTRAINT]: deploy a single approved Linux/Docker profile family with private namespaces,
    nonroot/cap-drop/NNP/seccomp/resource limits, digest-pinned image/toolchains, no default network
    or host/control mounts. Dependency cache is approved/read-only; unsupported dependency access
    blocks. Root/daemon/kernel/admin are TCB; profile/cgroup/UID/UDS facts require actual host proof.
TESTS: tests/test_controller_entry.py, tests/test_controller_installed.py, tests/test_execution_supervisor.py, tests/test_execution_protocol.py, tests/test_execution_client.py, tests/test_execution_cell_worker.py, tests/test_execution_journal.py, tests/test_execution_dispatch.py, tests/test_execution_plans.py tests/test_execution_docker.py tests/test_execution_attach.py, tests/integration/test_execution_boundary.py   (NEW)
```verify
uv run pytest tests/test_controller_entry.py tests/test_controller_installed.py tests/test_execution_supervisor.py tests/test_execution_protocol.py tests/test_execution_client.py tests/test_execution_cell_worker.py tests/test_execution_journal.py tests/test_execution_dispatch.py tests/test_execution_plans.py tests/test_execution_docker.py tests/test_execution_attach.py -q
FA_REQUIRE_EXECUTION_HOST=1 uv run pytest tests/integration/test_execution_boundary.py -q -m execution_host
uv run ruff check src/fa/controller_entry.py src/fa/execution tests/test_controller_entry.py tests/test_controller_installed.py tests/test_execution_supervisor.py tests/test_execution_protocol.py tests/test_execution_client.py tests/test_execution_cell_worker.py tests/test_execution_journal.py tests/test_execution_dispatch.py tests/test_execution_plans.py tests/test_execution_docker.py tests/test_execution_attach.py tests/integration/test_execution_boundary.py
```
- [ ] STEP1: retain E251 explicit peer/deadline seam and finish remaining actual spec §§2.1–2.2 composition; retain implemented types/codec/client/installed-entry closure, do not rebuild them; retain E247 typed ERROR reply classification per spec§2.2; remaining backend/authority composition is still required; distinguish control/command deadlines and exec versus non-exec uncertain replay (exit: complete owning bank passes, isolated installed module executes real CLI help under CWD/PYTHONPATH/editable-pth poison, locally invalid input sends no frame and command-over-control-budget reply is observed exactly once)
- [ ] STEP2: retain E249 native owned force-stop/observation (NOT a cgroup/terminal barrier); NEXT implement NEW CellBackend in execution/backend.py over existing DockerCells/WorkerClient/OperationJournal, with per-view live episode ownership, per-command begin/record_container and actual inspect/cancel/drain/restart facts per §2.2; join the actual SLICE2 admission gate before service composition, without a temporary authority (exit: interactive commands preserve shell state in one cell with two durable records; two distinct noninteractive operations with null sessions use two fresh one-shot cells/attaches and one RUN each; same-op duplicate/lost RUN never creates or resends; cancel-before-send, live one-shot cancel by exact journal-bound CID, and completed-creation/DONE-live-cell restart tests pass; lock expiry consumes the original deadline without a late Docker/RUN effect; no success/terminal receipt derives only from worker output)
- [ ] STEP3: prepare service/config/install/image and volume-map changes without activation; compose supervisor.py build_supervisor/main only with real WorkspaceAuthority and CellBackend, then SLICE3 publication handlers; apply controller read-only canonical mounts/private-UDS-only and entrypoint changes atomically with SLICE4 caller cutover, never before provisioner/file tools can operate. The dispatcher must route ALL nineteen closed operations and no others: `health|register_workspace|acquire_writer|pin_reader|create_view|read_file|write_file|edit_file|exec|inspect|cancel|pty_control|stop_view|seal|publish|install_project|prepare_bundle|handoff|release` (that list is `Operation` in `execution/primitives.py`; derive it from the enum, never retype it). `stop_view`, `seal`, `publish`, `install_project`, `prepare_bundle`, `handoff` and `release` are NOT readonly and MUST pass the authority check; a missing route is an explicit closed-code refusal (`INVALID_REQUEST`/`BACKEND_UNAVAILABLE`), never a silent success or a host-side fallback. A view-less route that needs an owner grant must reject a null capability. `create_view` MUST forward the wire's `base_revision` into `WorkspaceAuthority.create_view(base_revision=…)` so the CAS is enforced by the authority, not by the handler (exit: no permissive/failing-main stub or alternate host runner; a route-coverage test enumerates the nineteen `Operation` members and fails on any unrouted one; approved disposable-host test later boots that real factory and proves absent control mounts/secrets, denied profile/raw-path escalation and zero unavailable-backend project commands)
- [ ] STEP4: accumulate required real profile/image/kernel/daemon/cgroup facts and source-restored full-path CT98–CT100 mutation outcomes/cost at final SLICE6, with actual SLICE2 authority and SLICE4 callers, not injected callbacks (exit: every declared path runs non-skipped; each named producer deletion causes assertion failure in the whole owning bank; terminality uncertainty leaves ownership quarantined, source restored and no live owned cell)

## SLICE2: Workspace identity, exclusive writer and coherent private IO
STEPS: prescriptive
DEPS: SLICE1
INTENT: arbitrate all mutators by canonical workspace identity, keep dirty inputs and pinned readers,
  and make file tools and PTY observe one private view, never direct canonical writes.
CONTRACTS:
  CT101 [FUNCTIONAL]: acquire_writer serializes one workspace writer across run/session aliases,
    durably increments generation before a capability is usable, rejects stale/busy requests, and
    never expires a lease while old processes may write. Recovery precedes reacquisition. Spec §4.
    kill: remove-call src/fa/execution/workspace.py::WorkspaceAuthority.acquire_writer -> _claim_generation
  CT102 [FUNCTIONAL]: create_view materializes approved current filesystem bytes including staged/
    unstaged/untracked changes; no clean checkout. Enforce copy/protected/link/size policy and pin
    immutable reader revisions. Canonical index and user sentinels remain byte-identical.
    kill: remove-call src/fa/execution/workspace.py::WorkspaceAuthority.create_view -> _materialize_input
  CT103 [FUNCTIONAL]: actual write/edit tools use supervisor rooted IO against the same authorized
    open view as shell; deny protected/PlanRef/control destinations and alias escapes. Tool+PTY
    edits plus read/search are mutually visible for the active writer; independent readers retain
    their immutable pins. No stale canonical/index fallback or direct canonical write. Spec §§4–4.2.
    kill: remove-call src/fa/execution/workspace.py::WorkspaceAuthority.write_file -> _write_rooted
  CT103a [CONSTRAINT]: SessionManager permits explicit new-session reference to an existing
    registered workspace without transferring session DB/history ownership; one writer remains.
    Validate legacy manifests/run bindings; no blanket guard removal or second session manager.
    Future children inherit parent ownership/view/cancel scope; workflow subagents stay absent.
TESTS: tests/test_execution_view_io.py, tests/test_execution_workspace.py, tests/test_execution_readers.py, tests/test_execution_views.py, tests/test_managed_workspace.py, tests/test_session_lifecycle.py, tests/test_execution_project_tools.py, tests/integration/test_workspace_views.py   (NEW interfaces; existing session lifecycle tests retained)
```verify
uv run pytest tests/test_execution_view_io.py tests/test_execution_workspace.py tests/test_execution_readers.py tests/test_execution_views.py tests/test_managed_workspace.py tests/test_session_lifecycle.py tests/test_execution_project_tools.py -q
FA_REQUIRE_EXECUTION_HOST=1 uv run pytest tests/integration/test_workspace_views.py -q -m execution_host
```
- [ ] STEP1: retain E245 internal execution/view_io.py and its real-descriptor C0/C3 bank per §4.2 E244 (no admission/CT completion claim); retain E253 actual WorkspaceAuthority protected existing-root registration/current/R0/writer generation/startup fencing; retain E255 actual immutable reader pins/rooted reads/release; retain E256 actual WRITE/PROJECT views/rooted IO; NEXT construct execution admit/close-admission/drain semantics per §§2.2/4.2, not a second lock service; reject root aliases/overlaps/rebind and quiesce before R0; `create_view` keeps enforcing the wire's `base_revision` as a CAS precondition (retained from E268 review) rather than silently binding `current` (exit: two OS processes race for one workspace and exactly one obtains a durably advanced writer; denied/stale admissions produce no launch/write; when close wins before the scoped effect there are zero Docker create/start/attach/RUN and file-write effects; when the scoped effect wins, close/drain waits for that bounded effect/handler; independent pins retain original bytes across generation changes)
- [ ] STEP2: retain E256 actual WRITE/PROJECT create_view/_materialize_input and rooted read/write; NEXT complete the four non-PROJECT view purposes and actual execution-admitted read/write/edit on retained descriptors per §§4–4.2 before provisioning consumes them. The purposes are exactly CANDIDATE, VERIFICATION, MUTATION, PROVISIONING (ViewPurpose in execution/types.py; PROJECT is the retained one). Extend create_view's request to the §2 table shape `{workspace_id,base_revision,access,purpose,candidate_scope,plan_ref}` with these exact admission combinations and no purpose switch: CANDIDATE requires plan_ref + exact candidate_scope `{candidate_path,plan_ref}` with identical top-level plan_ref (bytes live in supervisor staging per §5, never canonical .fa/admission); VERIFICATION/MUTATION require nonnull plan_ref (§3.1) and are read-only-source + private scratch; MUTATION is the single write-capable derivative for mutation checks (one permitted src/scripts target, trusted controller only, §6); PROVISIONING is the provisioning view (nonnull plan_ref NOT required) and runs only inside the manager's provisioning RunContext from STEP3; every other combination denies INPUT_POLICY before copy. Keep private-metadata chmod helpers off project parents; preserve dirty/staged/untracked/deleted bytes and canonical index, enforce copy/link/secret/size policy and private-Git limitations; consume STEP1 descriptor IO under actual admission, private same-filesystem staging and explicit profile/protected-PlanRef binding (exit: exact tree/index/sentinel oracles pass; link/special/limit/root-swap failures leave no returned grant or partial revision; expected-SHA conflict and post-admission rename do not silently succeed or touch canonical/control paths; one denied-combination case per forbidden purpose/scope tuple)
- [ ] STEP3: inject the managed provisioner into the existing SessionManager BEFORE `_new_session` calls `_provision_workspace` (this is the SLICE2 component injection; SLICE4 STEP2's repetition means routing the remaining inventory callers through the SAME provisioner at activation, never a second implementation); reserve its real provisioning RunContext via early existing DB/begin_run per §4.2; update both reverse-owner call sites (manager.py `_new_session` and `resolve_workflow_workspace`) for explicit registered references per CT103a and fail non-READY; preserve session DB/run reservations and validate legacy records under authority. The provisioner result contract is exact: a frozen result carrying `{registered: bool, workspace_id, revision_id, tree_sha256}`; manager cleanup may rmtree only `registered is False` scratch the provisioner itself created, and a registered/committed workspace is NEVER an rmtree target. `workspace_preparer` returns ReadyState and the manager treats not-READY as SessionManagerError("workspace_not_ready") in BOTH `_new_session` and `_attach_session` — no log+continue. The host-Git `_provision_workspace`/`provision_git_workspace` path is removed at injection, not retained as a fallback: new-workspace provisioning until SLICE3's publication join is an explicit typed BLOCKED disposition (provisioning_unavailable), while explicit registered reuse bypasses clone/readiness/remotes. The publication-dependent provisioning leg completes with SLICE3, not host Git fallback. SLICE2 half (exit): injection ordering test proves the provisioner runs before any `_provision_workspace` effect; new-session explicit reference to an existing registered workspace succeeds without transferring DB/history and one writer remains; corrupt manifests and legacy run-ID tests pass; provision failure and not-READY leave no active session; post-commit-failure cleanup never deletes registered bytes (covered with a registered=True provisioner result). SLICE3 half (exit, moves to SLICE3's evidence): DB/manifest failure AFTER a real workspace commit via publication keeps registered bytes intact and reports SessionManagerError.
- [ ] STEP4: wire actual tool builders and SessionState internal binding per §4.2: controller fuzzy matching/telemetry, supervisor rooted writes, same-view bounded reads and cell-local existing search/reach/PDF implementations; no new public tools/search service or private state mount; join real authority/backend factory before disposable integration (exit: actual registry tools and PTY observe each other's edits with blackboard on/off and zero host Git/version-stamp reads, active search sees a new symbol, reader search stays pinned, artifacts retain their controller path, PDF/binary/large/truncated/helper-unavailable results are explicit and no canonical fallback occurs; seal/import alias tests complete with SLICE3)
- [ ] STEP5: record CT101–CT103 whole-bank full-path producer kills plus same-inode/different-label contention, queued revoke/stop races at create/start/attach/RUN (not merely after `admit()`), restart and cleanup; accumulate actual Docker/kernel runs for final SLICE6 without substituting unit fixtures (exit: every named producer removal breaks an executed assertion, including no late launch/write after closed admission; all required host cases non-skipped, exact source restored, no leftover live cell or lost pin)

## SLICE3: Terminal seal, fenced publication and forward recovery
STEPS: prescriptive
DEPS: SLICE2
INTENT: prevent descendants or aliases from changing validated bytes; publish complete revisions
  and exact canonical projections with one durable recovery owner and distinct Q58/bootstrap commits.
CONTRACTS:
  CT104 [FUNCTIONAL]: stop_view closes file-write admission, drains handlers, stops all PTYs/cells
    and confirms actual cgroup descendants empty before seal. Exit/Ctrl-C/timeout is not terminality;
    UNKNOWN quarantines and holds ownership. Supervisor restart cannot release a live old writer.
    kill: remove-call src/fa/execution/supervisor.py::stop_view -> _wait_descendants_terminal
  CT105 [FUNCTIONAL]: seal_view recomputes immutable export hashes/type/mode/deletions after barrier,
    rejects protected paths/link/special/escape aliases and stale base/source/generation, and never
    imports a model manifest or live mutable directory. Spec §5.
    kill: remove-call src/fa/execution/publication.py::seal_view -> _validate_sealed_tree
  CT106 [FUNCTIONAL]: publish_view durably prepares full immutable revision+intent, CAS-commits
    current pointer then completes verified canonical projection before receipt/next writer. Managed
    readers see complete pinned revisions; canonical Git index/protected state remains untouched.
    kill: remove-call src/fa/execution/publication.py::publish_view -> _commit_current
  CT107 [FUNCTIONAL]: recover_workspace inspects intent/current/generation, discards only provably
    uncommitted owned scratch or completes committed projection forward; mismatches quarantine.
    No committed rollback, stale token success or partial-current completion at any crash point.
    kill: remove-call src/fa/execution/publication.py::recover_workspace -> _recover_intent
  CT107a [CONSTRAINT]: Q58 exact canonical replacement, no-replace new-project install, and ordinary
    multi-file revision commit keep distinct intent phases/irreversible points. Bootstrap uses real
    Linux RENAME_NOREPLACE, no existence-check+rename. Post-commit artifact failure preserves bytes
    and blocks; fsync errors are uncertainty, not permission to replay/rollback. Spec §5.
TESTS: tests/test_workspace_publication.py, tests/integration/test_publication_recovery.py   (NEW)
```verify
uv run pytest tests/test_workspace_publication.py -q
FA_REQUIRE_EXECUTION_HOST=1 uv run pytest tests/integration/test_publication_recovery.py -q -m execution_host
```
- [ ] STEP1: implement selected Q74 per-stage/episode checkpoint policy and spec §6.1 stage transition table; implement terminal barrier/view state machine and immutable export validation in execution/publication.py plus supervisor.py::stop_view -> _wait_descendants_terminal (CT104's named producers). **Progress and the remaining parts of THIS step:** the terminal barrier shipped in E266 and the immutable export/seal in E267 (both local C0/C3); what STEP1 still owes is (a) the Q74 per-stage/episode checkpoint policy wired to §6.1's transition table, (b) the real Docker/cgroup `CellTermination` implementation behind the existing seam, and (c) `tests/integration/test_publication_recovery.py` running the kernel-observed barrier under `FA_REQUIRE_EXECUTION_HOST=1`. STEP1 is one step with three parts, not one checkbox per part; it closes only when all three exist, and (b)/(c) are host-blocked in any session without an approved Docker daemon. Test split is fixed, no guessing: the view-state machine and immutable export validation run in tests/test_workspace_publication.py over the real local worker/attach cells (E258's fixture pattern) and prove seal/publish is refused while any handler or cell is unsettled; the actual cgroup-populated-empty descendant barrier runs only in tests/integration/test_publication_recovery.py under FA_REQUIRE_EXECUTION_HOST=1 (kernel fact, never mocked). Tests launch fork/double-fork/setsid/background writers in real cells and hold active file operations (exit: none can seal/publish while still writable)
- [ ] STEP2: implement exact intent/current/projection schemas/order/dir fsync and generation/base CAS per spec §5, including canonical Git-index preservation and spec §5.1 exact Q58/bootstrap forward-recovery phases. Materialize Rnext **from the sealed manifest**, re-verifying every digest against the view's frozen source, and materialize it under the id `seal_view` derived (`derive_revision_id`), never a caller-supplied id; the irreversible point for an ordinary revision is the `current.json` replace, and the recovery discriminator is `current.json`, not the phase value. Publish flips the view record to `PUBLISHED` and thereby **settles the owner**: `release_unused_writer` accepts only PUBLISHED/REJECTED WRITE views and refuses OPEN/STOPPING/UNKNOWN/SEALED (retained predicate from the E268 review) (exit: complete old/new pinned-reader and stale/fault unit matrix passes; publishing a SEALED view makes a subsequent `release` succeed and a later re-claim advance generation; publishing a view whose manifest hash or source bytes moved is `CORRUPT_STATE` with no `current.json` change)
- [ ] STEP3: integrate the existing inner_loop/plan_promotion.py Q58 buffer/hash/promotion primitives and this authority's no-clobber bundle primitives (execution/publication.py::prepare_bundle / install_project, per §5's bundle handoff; §1 already assigns no-clobber project install to publication.py) with the same authority; no managed-acquisition UI/protocol before SLICE5 integration (exit: direct controller-authorized tests prove collisions preserve old bytes and post-commit failure never rolls back). **Progress and what this step still owes:** the bundle renderer/store (E271), the `RENAME_NOREPLACE` install under the Q82 (B) ruling (E271 unit B) and the same-path plan replacement with its forward-only commit (E273) are implemented and locally proved. The dispatcher's pre-reservation `authorize` seam is now real (E274); what remains is the nineteen route handlers plus `build_supervisor/main`, and then the controller leg — `_promote_validated_plan` still calls `inner_loop/plan_promotion.publish_plan_buffer` directly and must be moved onto the authority's `publish` of a CANDIDATE view, deleting that transport in the same change so exactly one writer owns the canonical plan. The step closes only when that leg is proved end to end; the components above are not a substitute for it.
- [ ] STEP4: recover from supervisor/process death at each durable boundary, before/after pointer replace and during projection; require approved filesystem and separately label process-crash versus power-loss evidence. The hook points are fixed by existing code: `WorkspaceAuthority.__enter__` calls `journal.recover_uncertain()` then `_load()`, and `_load` currently QUARANTINES every `OWNED` workspace with no forward path — `recover_workspace` must run there, before the quarantine decision, for every workspace with `intent.json`; and `_initialize_genesis` already refuses a non-empty `views/` or a present `intent.json`, so nothing else may assume a pristine workspace. Stale `pending/` staging from a hard kill is NEVER swept today (`__enter__` creates the directory and moves on), so recovery must also classify those directories as owned scratch (discard) versus unknown (quarantine), and must not delete a directory referencing a committed revision (exit: real recovery tests expose only complete current revisions or quarantine, no success from uncertain state; a killed supervisor mid-projection leaves no orphan `pending/` entry that a later authority silently ignores) **Progress (E276):** the local recovery unit is implemented and hooked into `_load` in the same change — CT107's three kinds complete forward or discard only provably-uncommitted owned scratch, stale `pending/` staging is classified, and 17/17 producer mutants are killed over the real authority. STEP4 still owes the kernel-observed matrix on the approved filesystem (`FA_REQUIRE_EXECUTION_HOST=1`), kills *inside* recovery, the fsync-unsupported/EIO cases, and explicit process-crash versus power-loss labelling.
- [ ] STEP5: record full declared-path CT104–CT107 kills and cleanup/ownership evidence (exit: all four producers killed by useful executed oracles; no cells/pins/intent abandoned without disposition)

## SLICE4: Close every execution route and bind verifier/eval evidence
STEPS: prescriptive
DEPS: SLICE3
INTENT: complete CT97 before nested acceptance; no early readiness/import/Git/subagent/fallback path
  may execute project code on controller/host, and stale/uncertain evidence cannot succeed.
CONTRACTS:
  CT97 [FUNCTIONAL]: real _cmd_run boundary covers whole stage prologue, all mutating provider
    tools/PTY/descendants, approved dirty view, protected PlanRef/control paths and source import.
    Valid controller promotion/ordinary edits work; file/shell/alias/rename attempts cannot change
    canonical protected bytes. Keep original stage-seam kill, not merely hook registration.
    kill: remove-call src/fa/cli.py::_cmd_run -> run_stage_with_plan_write_boundary
  CT110 [FUNCTIONAL]: verifier noninteractive commands, baseline/import/collection/mutation probes
    execute through managed operation adapters on pinned source+scratch; no host subprocess runner
    or replay. Actual exit/timeout/tree/profile/terminal identity is captured. Spec §§3/6.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_run_one -> _run_managed_command
  CT111 [FUNCTIONAL]: kill-check classification validates fresh operation/view/tree/PlanRef binding
    plus strengthened detailed pytest report; error/timeout/collection/setup/stale/zero/skip-only
    never PROVEN. Preserve slice sensitivity, genuine test-call failures and Q53(c)/Q54 rules.
    kill: remove-call src/fa/inner_loop/slice_verification.py::_run_kill_check -> _validate_bound_pytest_report
  CT111a [CONSTRAINT]: inventory all project execution and prove closure before product acceptance:
    readiness/dependency hooks/entrypoint, project Git/config/helpers, chat SubagentRunner, PTY and
    verifier routes. Admission/isolation/integrity are mandatory in both modes and every role.
    Keep I02 pinned T0/Q55/Q56/Q73 semantics; unsuccessful safe-view/deadline recovery is explicit,
    never fabricated eval or DONE. Structured reports are not hostile-test correctness attestation.
TESTS: tests/test_verify_gate_live.py, tests/test_verify_slice.py, tests/test_slice_verification_runner.py, tests/test_workflow_deadline.py, tests/test_workflow_global_history.py, tests/integration/test_execution_closure.py   (NEW integration)
```verify
uv run pytest tests/test_verify_gate_live.py tests/test_verify_slice.py tests/test_slice_verification_runner.py tests/test_workflow_deadline.py tests/test_workflow_global_history.py -q
FA_REQUIRE_EXECUTION_HOST=1 uv run pytest tests/integration/test_execution_closure.py -q -m execution_host
```
- [ ] STEP1: complete the inspected notes/i03-execution-call-inventory.md with exact source/caller/profile/view/negative oracle per spec §6; classify newly found subprocess/import/Git entrypoints rather than excluding them by name (exit: inventory covers every production route used by explicit/chat/nested workflows)
- [ ] STEP2: retain _cmd_run signature as pure validation→run_stage_with_plan_write_boundary→_cmd_run_inner; wrap whole _cmd_run prologue and route manager/entrypoint/bootstrap readiness through provisioning cells; remove fail-open readiness and host fallback paths. The managed provisioner was ALREADY injected into SessionManager in SLICE2 STEP3 — this step routes the remaining inventory callers through that same provisioner and activates the route closure; never implement a second injection or second provisioner. No rollback deleting supervisor-owned registered roots. Wire project Git/pair/subagent paths too (exit: backend-down run across each inventory route executes zero project commands; no unsupervised legacy bind/process)
- [ ] STEP3: integrate pinned verification scratch/receipts/report parsing and explicit artifact schema versions; retain old I02 evidence readers, no duplicate verification engine (exit: actual supervised tests prove candidate import provenance, stale-operation/timeout/report negatives and immutable T0 compatibility)
- [ ] STEP4: real direct C1 with actual supervisor/cells and only provider mocked proves each write/edit/shell route, dirty sentinels, denied protected paths and successful ordinary source edit/Q58; real eval sees same attempt and hard-blocks integrity failure in both modes (exit: execution_host closure matrix passes, no all-skips)
- [ ] STEP5: record full-path CT97/CT110/CT111 kills; retain original CT97 producer case identity and all I02 gate regression proofs (exit: source restored and useful executed producer oracles all killed)

## SLICE5: Managed nested selection/bootstrap and initial parent context
STEPS: prescriptive
DEPS: SLICE4
INTENT: deliver actual outer chat→invoke→child workflow with correct child authority, approved
  selection/bootstrap/clarification and Q66 under recorded Q59/Q60 dispositions, reusing one workflow machine.
CONTRACTS:
  CT96 [FUNCTIONAL]: under recorded Q59/Q60 dispositions, actual invoke handler calls managed
    planner acquisition, returns exactly approved stable-ID selection/bundle/clarification, admits
    selected/installed canonical PlanRef before T0/coder, and preserves ordinary chat default.
    No guessed path, public context/PlanRef field, free-form file map or raw ledger. Original kill:
    kill: remove-call src/fa/inner_loop/tools/workflow_tool.py::handler -> _run_planner_managed_workflow
  CT108 [FUNCTIONAL]: managed invocation allocates child RunContext via existing SessionManager
    before child artifacts/provider; distinct run_log_dir/DB binding and parent metadata. Suspend
    parent mutators; scoped child inherits same workspace writer, no deadlock/second writer.
    kill: remove-call src/fa/inner_loop/tools/workflow_tool.py::_run_planner_managed_workflow -> _child_run_context
  CT109 [FUNCTIONAL]: live provider snapshots bounded current parent messages at invocation time,
    feeds only initial planner user task beside its own prompt/skills; no SYSTEM transcript/public
    schema field. Redact credentials; retries/replans use distilled packets, ordinary logs allowed.
    kill: remove-call src/fa/cli.py::_make_workflow_ctx_provider -> _snapshot_parent_for_initial_planner
  CT109a [CONSTRAINT]: implement spec §§7/7.0/7.1 stable pair/schema, clarification, rendering/caps
    and v2 acquisition cross-fields using existing child allocator/PlannerDispatch/SessionOutcome/
    admission/repair/PrDraftStore, not a second engine. Retain v1 readers and current experimental
    injection; no new required-workflow mode. Collision/ambiguity/malformed/missing choice blocks
    before coder/eval; post-install IO failure retains valid bundle. No unavailable stub ships as CT96.
TESTS: tests/test_verify_gate_live.py, tests/test_invoke_workflow_tool.py, tests/test_managed_acquisition.py, tests/integration/test_nested_workflow.py   (NEW acquisition/integration)
```verify
uv run pytest tests/test_managed_acquisition.py tests/test_verify_gate_live.py tests/test_invoke_workflow_tool.py -q
FA_REQUIRE_EXECUTION_HOST=1 uv run pytest tests/integration/test_nested_workflow.py -q -m execution_host
```
- [ ] STEP1: author exact spec §7 managed-v2 keys/rules/rendering fixtures and v1 compatibility/selection-vs-bootstrap hash tests; apply E231 decisions, no re-approval ceremony or new routing mode. Include existing expansion/injection preservation and source-backed registry/pr_prepare seams (exit: source-matched fixture/schema tests pass; no inferred runtime acceptance)
- [ ] STEP2: implement actual handler/reused _child_run_context/parent writer suspension and server-acknowledged handoff and acquisition capability; preserve existing task/roles/mode/budget tool fields, no path/context; reserve invocation/child identity before dispatch (exit: actual handler tests prove parent artifacts byte-identical and unique child namespace)
- [ ] STEP3: implement approved stable-ID selection/clarification and controller-rendered no-clobber bundle via SLICE3 authority, shared I02 repair and before-T0 ordering (exit: exact caps/unknown+duplicate fields/status-smuggling/ambiguous/collision/post-install-fsync+append matrix passes)
- [ ] STEP4: implement live current-message provider, bounded initial task/redaction and distilled retry/replan separation; keep Q66 ordinary log policy (exit: parent-only sentinel occurs in first real planner request, not retries; configured credential sentinel absent)
- [ ] STEP5: actual outer drive_session→invoke→child run_workflow→_cmd_run→drive_session with real supervisor/cells and only ProviderChain.request mocked proves existing selection and new project, clarification/no-coder blocks, child evidence and parent refresh at turn boundary (exit: execution_host nested C1 passes with advisory/manual and existing experimental suggestion paths, in observe/enforce gate modes)
- [ ] STEP6: record CT96/CT108/CT109 full-path mutation outcomes with original CT96 handler producer lineage, no helper-only substitutes (exit: each declared producer killed; no unknown/stale report credited)

## SLICE6: Reviewed I02+I03 package and actual deployed acceptance
STEPS: prescriptive
DEPS: SLICE5
INTENT: execute transferred SLICE7 and E223 acceptance with independent review, exact producer
  preservation and real main-host evidence; local/I02 diff review never assigns a live verdict.
CONTRACTS:
  CT88 [CONSTRAINT]: preserve all original unique I02 producer keys/cases and add I03 producers;
    separate local proof/live result, stable IDs/owners/fixture/oracle/evidence. Shared scenario only
    with explicit per-producer evidence mapping. Q63 exactly NOT RUN/PASS/FAIL/BLOCKED, optional short
    commentary on ALL states, no mandatory/hardcoded reason variant.
    Append deployed SHA/image/profile/config/run/command/rc/effect/artifact/reviewer per attempt.
  CT89 [CONSTRAINT]: planner owns oracle/run sheet; coder appends source-backed seams/proposals;
    independent manual checklist precedes fixtures/helpers, repeated on material changes. Human
    review only, no approval marker. Useful host behavior/artifacts, not private-helper-only cases.
  CT112 [FUNCTIONAL]: case-index checker compares normalized original producer keys to successor
    coverage, preserves renamed/replaced producers through explicit lineage, collapses only exact
    duplicates, and rejects missing/unmapped/orphan/duplicate cases. It never assigns live PASS.
    kill: remove-call scripts/check_execution_e2e_coverage.py::main -> _check_producer_coverage
TESTS: tests/test_e2e_artifact_contract.py, tests/test_skill_conformance.py   (NEW artifact test; existing skill test)
```verify
uv run pytest tests/test_e2e_artifact_contract.py tests/test_skill_conformance.py -q
uv run python scripts/check_execution_e2e_coverage.py
```
- [ ] STEP1: implement recorded Q63 four-state live-result schema, optional short commentary on every state, no reason-code enum/mandatory BLOCKED field; test all states with and without commentary. Keep roadmap/increment/CT vocabularies, generic READY and active I01 distinct (exit: actual artifact conformance tests pass; no live outcome inferred)
- [ ] STEP2: implement planner case index e2e/README.md and master e2e/I03/live-verification.md with append-only attempts/local-vs-live fields; retain old e2e/I02 origins (exit: index/status tests pass)
- [ ] STEP3: mechanically snapshot original normalized unique producer keys from notes/e2e-live-verification-register.md, preserve all unique keys/CT/STEP lineage, add new producers and successor mappings; correct CT52 bounded repair and shell-exit-127 vs genuine launch-error oracles (exit: actual coverage checker/test detects removal of any unique case, not only total counts)
- [ ] STEP4: coder writes e2e/I03/implementation-handoffs.md after real seams/proofs exist, labeling facts vs proposals and limitations (exit: handoff-shape tests pass; coder has changed no oracle/result)
- [ ] STEP5: planner finalizes copy/paste host sheet from actual deployment/workspace facts per spec §9, complete tasks/variables/commands/run IDs/artifacts, safe update stop conditions and observe→review→enforce order (exit: run-sheet checks plus human command review, not pytest claiming deployment happened)
- [ ] STEP6: update plan-authoring/feature-planning/tests-writing skill obligations exactly as transferred STEP6; preserve unrelated READY behavior (exit: artifact+skill conformance tests pass)
- [ ] STEP7: independent reviewer completes manual checklist before the FINAL e2e/I03 fixture/helper package (not earlier local tests/integration kernel tests), including all source/import/readiness/descendant/fencing/recovery and nested cases, maintenance prerequisites/no secrets/stop path; include E223's I02+I03 implementation/evidence scope and record open findings for final review (exit: named reviewer/date/notes recorded; no machine-approved marker; final broad review still required after material changes)
- [ ] STEP8: only after STEP7 implement reviewed bounded fixtures under e2e/I03/fixtures/ in unique disposable workspaces; preserve evidence/owned cleanup and keep live host commands outside default pytest discovery (exit: fixture conformance passes; review-before-implementation provenance exists)
- [ ] STEP9: index every distinct local/live producer, including separate CLI/direct guards, candidate/promotion/schema/T0, CT96 selection/bootstrap/clarification/context, CT97 file/edit/shell/subagent-absence/alias paths, early readiness/imports, no-replay, contention/read pins, terminal seal/publication/recovery; map retained I02 source/functional claims to actual deployed behaviour oracles (exit: all original+new required producer keys mapped with useful evidence oracle; no local-only or missing deployed claim credited)
- [ ] STEP10: run local package conformance, every accumulated non-skipped execution_host suite and all17 full-declared-path kills, and full release gates; review environment/readiness and inherited baseline acceptance using retained I02 manifests, exact test identities/replacements and Mypy contexts, including the unreproduced historical ninth context and relevant hook observations. Resolve/explicitly disposition each item for the intended Ubuntu/Docker/Python deployment without falsifying red results. Before claiming the release gates complete, build the installed-controller wheel with supported CPython 3.13 including `zlib` and the frozen build dependencies (the current 11 setup errors are a blocker, not a skip); provide the approved ShellCheck binary so all 12 shellcheck-gated tests run rather than skip; and provide a trusted Go 1.24.11 SDK plus the pinned Gitleaks/pre-commit dependencies or an approved cached build environment so the actual readiness→hook→commit→publication path and `just test`/`just check` complete without bypass. Go is an indirect test-hook build requirement, not an FA runtime requirement. If any prerequisite remains unavailable, record the row BLOCKED and keep the release gate open. Only with maintenance/deploy authorization perform normal main update and reviewed host runs; inspect nonzero update before retry, verify actual deployed SHA/image/profile/config, execute spec §9.1 unmocked direct+nested workflow witnesses (not only deterministic provider-stub cases), record source-to-behaviour results and broad independent implementation/evidence review plus integrated signoff. No automated/harness PASS (exit: all four E223 acceptance obligations complete with recorded review; all required cases independently reviewed PASS; BLOCKED/NOT RUN/skip never counts)

## Increment definition of done — binary, no partial isolation claim

**Counts in this section are derived, never hand-typed.** Canonical numbers at the E268 review, each
reproducible by the command beside it:

| Quantity | Value | Derive it with |
| --- | --- | --- |
| CT declarations (17 FUNCTIONAL + 7 CONSTRAINT) | **24** | `grep -cE '^\s+CT[0-9]+[a-z]? \[(FUNCTIONAL|CONSTRAINT|PRESERVATION)\]' increments/increment-03-*.md` |
| Declared `kill:` directives | **17** (one per FUNCTIONAL contract; a `grep -c 'kill:'` returns more because prose lines quote the word) | `grep -cE '^\s+kill: remove-call ' increments/increment-03-*.md` |
| Closed wire operations | **19** | `grep -cE '^\s+[A-Z_]+ = "' src/fa/execution/primitives.py` |
| E2E live surfaces / joins | **25 / 8** (E250 recorded 18/8; E267 added `publication.py` as I03-LIVE-19; E269 the publish path as I03-LIVE-20; E271 the bundle path as I03-LIVE-21; E272 the install path as I03-LIVE-22; E273 the plan-replacement path as I03-LIVE-23; E274 the authorizer as I03-LIVE-24; E276 forward recovery as I03-LIVE-25) | `grep -o 'I03-LIVE-[0-9]\{2\}' notes/e2e-live-verification-register.md \| sort -u \| wc -l` |
| Six slices, thirty-five STEPs | **6 / 35** | `grep -cE '^- \[.\] STEP[0-9]+:' increments/increment-03-*.md` |

If a later edit changes a count, the edit updates the table and the ledger entry that introduced the
change; a plan sentence with a stale number is a defect, not a rounding error.

- [ ] All six local verify blocks exit 0 AND collect every path named in their slice's `TESTS:` line —
      collection is proved by `--collect-only -q` naming each file, because a verify block whose single
      path does not exist yet reports "no tests ran" and exits 4, not 0. Required execution_host runs use
      `FA_REQUIRE_EXECUTION_HOST=1` and cannot succeed by skipping unavailable Docker/profile.
      All **17** declared `kill:` directives have useful executed failing oracles, provenance,
      elapsed cost and byte-exact restored source; errors, collection failures, skips and
      `PRODUCER_ABSENT` do not count as kills.
- [ ] Implemented artifacts conform to recorded Q59/Q60/Q63/Q74 and spec §7 managed-v2/schema/rendering
      contract; no conditional runtime proposal/stub remains. Existing Q62/I02 v1 readers and strict IDs stay compatible.
- [ ] Real profile/UID/UDS/cgroup/mount/import proof and complete execution inventory show zero
      project execution outside cells for every production path/role, including readiness and chat
      subagents; backend-down/transport uncertainty never triggers fallback/replay. No legacy writer.
- [ ] New workspace, resumed session and new-session registered-workspace reuse work through actual
      manager/DB. Two writer processes/run/session aliases cannot mutate simultaneously; read pins
      survive publication. Dirty/staged/untracked inputs and canonical Git index preserved; private
      Git/input/secret-dependent compatibility limits have explicit accepted dispositions.
- [ ] File tools/PTY share one private view. Real alias/parent-rename/protected-write/descendant cases
      cannot alter canonical PlanRef/state or import forbidden bytes; ordinary edits/Q58 succeed.
      Seal requires all writers terminal; stale generation/base fails. Crash/durability-uncertainty
      matrix yields complete old/new revision or quarantine, no partial-current success/rollback.
- [ ] Actual direct and nested C1 use real supervisor/cells with only provider mocked. Child artifacts
      never overwrite parent; acquired explicit canonical PlanRef/T0/verification/eval share identity;
      Q66 current initial context/distilled retry and Q55/Q56/Q73/both-mode integrity floor are proved.
- [ ] E223 deployed functional/source-to-behaviour verification covers retained I02 and new I03
      claims, including admission/repair/promotion/T0/eval/failure paths, with actual deployed
      code/image/config identities and useful effect/artifact oracles; local green is not host proof.
- [ ] E223 environment/readiness and inherited baseline acceptance review is complete for the
      intended Ubuntu/Docker/Python deployment. Run existing just test/just check release gates;
      review exact baseline/candidate failure identities/phases, changed/replaced test intent,
      recorded Mypy contexts (including the unreproduced historical ninth) and relevant hook
      observations using preserved I02 evidence. New/changed checks green; no new/missing/
      unclassified failures, aborted/no-summary or count-only waiver. No unauthorized E19 changes,
      skipped security check or invented FA Go runtime requirement; actual red remains red.
- [ ] E223 integrated E2E/deployment acceptance: full CT88/CT89 producer-preserving package/
      manual review/handoff/skills/fixtures complete;
      spec §9.1 real-provider direct+nested witnesses and every unique required I02+I03 deployed-main case have reviewed PASS with code/image/config/run/
      oracle/artifact evidence. No local proof sets live status, no unresolved blocked deployment row.
- [ ] E223 broad independent I02+I03 implementation/security/recovery/evidence review and final
      operator deployment signoff recorded in
      notes/i03-local-and-deployed-acceptance.md with commands/rc/environment/source references;
      registers updated only from actual proof. Until then status remains unshipped.

## E268 — adversarial review of the remaining I03 (2026-10-22): plan and code corrections

**Method.** Read every remaining slice against the modules it touches and their callers, reproduced
each suspected defect before believing it, and separated confirmed defects (fixed here or given a named
owner) from suspicions (recorded, not fixed). Nothing in this section ticks a STEP, closes a contract or
assigns a live verdict. Implementation numbering after this review: **E269 = SLICE3 STEP2 (publish/CAS)**,
**E270 = SLICE4's clean-up of the recovery hook if STEP2/4 split needs it**, **E271 = SLICE3 STEP5 kills**;
recovery itself stays inside STEP4.

### A. Confirmed defects — fixed in this review

| # | Defect (evidence) | Why it would bite | Fix |
| --- | --- | --- | --- |
| D1 | `release_unused_writer` refused settlement for **any** non-READ view, whatever its state (`workspace.py::release_unused_writer`, old `_has_writer_views`) while spec §2.1:168 allows release when there are "no writable/live/unknown jobs or unfinished projection". | With E267's `SEALED` and E269's `PUBLISHED`, a **finished** view kept the writer captive forever; the next `acquire_writer` returns `WORKSPACE_BUSY`, and a restart then quarantines the workspace (`workspace.py::_load`) with no forward path. Reproduced: sealed view → `release REFUSED: WORKSPACE_BUSY`. | `_has_unsettled_views` + `_SETTLED_VIEW_STATES = {PUBLISHED, REJECTED}`: SEALED still holds the writer (an unpublished candidate is unpublishable once the grant dies), OPEN/STOPPING/UNKNOWN always refuse, PUBLISHED/REJECTED settle. Four cases added; 3/3 mutants killed. |
| D2 | `WorkspaceAuthority.create_view` ignored the wire's `base_revision` (`protocol.py:102` requires it; the method had no such parameter). | A caller naming revision A received a view over revision B with no error — the exact stale-base confusion CT102/CT106 and spec §4's "generation/base CAS" exist to prevent, and undetectable by any current test because the field is dropped before any check. | `base_revision` keyword with `STALE_REVISION` before any filesystem effect; two cases added; mutant killed. The dispatcher must forward it (SLICE1 STEP3). |
| D3 | Name collision: `WorkspaceAuthority._install_project` actually installs a **view** directory (`workspace.py::_install_project` @6ff1121), while spec §5 assigns `publication.install_project` (no-clobber *project* install) to the same authority. | An agent implementing the bundle path could "reuse" the existing helper and silently install a view where a project install was intended. | Renamed `_install_view`; the spec name stays reserved for E269+. |
| D4 | Stale line citations inside E267's own section (`_revision` cited at 898 → now 919; `_proof_only` at 2033 → now 2054) because the section's own edit shifted them. | Every later agent either lands on the wrong line or stops trusting citations. | Citations corrected; new rule below. |
| D5 | E250's "18 surfaces / eight joins" is a dated snapshot, but nothing said how the count grows; E267 added a 19th row. | Silent divergence between register prose and the actual inventory. | Growth rule stated in the register (E267 section) and the count table above. |

**Citation rule (normative for this project).** A plan or ledger citation names the **symbol**
(`workspace.py::_proof_only`), never a bare line. A line number may accompany a symbol only when it is
pinned to a commit sha (`workspace.py:2054 @ a299c12`). Line-only citations are treated as drift.

### B. Suspicions — recorded, each with an owner; not fixed here

| # | Suspicion (evidence) | Why it is not fixed now | Owner |
| --- | --- | --- | --- |
| S1 | A composed service with no `CellTermination` configured returns `terminal=false` and leaves the view `STOPPING` forever (`ViewStopper.stop_view`, `supervisor.py`), which is honest but looks like a hang. | The seam is deliberately optional for local tests; requoting it inside the service is composition work. | SLICE1 STEP3 exit: service startup must refuse to run without a real observer. |
| S2 | `_load` quarantines every `OWNED` workspace and nothing recovers it; stale `pending/` staging from a hard kill is never swept (`__enter__` creates the dir then continues). | Recovery is STEP4, and doing it before `publish_view` exists has nothing to recover forward to. | SLICE3 STEP4 (hook point now named in the STEP text). |
| S3 | `_Capture` excludes a component named `.git`/`.fa`/`.venv`/`.env` at **any** depth (component match), so a legitimate nested `.fa/x.py` never enters a revision and `.fa` is "protected" by name only. | Changing the exclusion semantics is a behaviour change with no failing case yet; the protected-plan boundary is the actual safety rule. | SLICE3 STEP2 (§5 wording) — decide "excluded by name at any depth" explicitly. |
| S4 | Sealed/published views persist their full source copy plus manifest forever; nothing garbage-collects them. | Retention is a policy question (evidence vs disk) that belongs with the publication receipt contract. | E269's receipt contract + I06 disposition, explicitly stated. |

### C. Verified fine (checked, no action)

- **`17` kills is correct.** 17 FUNCTIONAL contracts, 17 distinct `kill: remove-call` directives; a raw
  `grep -c 'kill:'` returns 19 because two prose lines quote the word. My first reading flagged a
  mismatch; the count is right and is now derived in the DoD table instead of asserted.
- **Spec §5 steps 1–3 vs the §5.1 table do not contradict each other for REVISION.** Intent may only be
  written after Rnext is durable, and the irreversible point is the `current.json` replace. The one thing
  worth stating explicitly (and now stated in STEP2) is that the recovery **discriminator is
  `current.json`**, not `phase`, because `PREPARED` legitimately exists on both sides of the CAS.
- **Gate/drain vs a running command.** E257 already fixes the intent ("scope ends after dispatch, NOT the
  command reply/exit wait") and the code matches: `admit()` registers work for the dispatch scope only,
  `close_admission` refuses later dispatches, and `stop_cells`/cancel handle the running cell. No defect.
- **`prepare_seal`/`mark_sealed` duplicate checks** are intentional defence (E267 records the masking).

### D. Executability gaps found in the plan text — rewritten in place

1. **SLICE1 STEP3** never said which handlers to route. It now lists all nineteen operations, requires
   authority for the non-readonly ones, forbids a silent fallback, and adds a route-coverage test that
   enumerates `Operation` so a forgotten route fails a test instead of hanging at runtime.
2. **SLICE3 STEP1** was one checkbox covering a shipped barrier and two host-only parts. It now names
   its three parts explicitly, so nobody closes it on local evidence.
3. **SLICE3 STEP2** now says what it must materialize (Rnext from the sealed manifest, under the derived
   id), what the irreversible point is, and that publish is what settles the owner.
4. **SLICE3 STEP4** now names the real hook points (`__enter__` → `recover_workspace` before the
   quarantine decision; `_initialize_genesis`'s existing refusals; the unswept `pending/` directory) so
   an implementer does not have to rediscover them.
5. **The DoD** now proves collection (a missing `TESTS:` path exits 4, not 0) and derives every count.

### E. Explicitly deferred, with reasons

- **The bundle/Q58/BOOTSTRAP half (STEP3)** stays after STEP2: `install_project` needs the current
  pointer, and `publish_plan_buffer` (`inner_loop/plan_promotion.py:183`) already does its own same-path
  atomic replace with its own lock and CAS, so integrating it before the pointer contract exists would
  create two commit paths with different failure vocabularies.
- **Candidate-buffer seal** stays in STEP3 with §5's PLAN intent; sealing a buffer without its publisher
  would produce a half-specified path.
- **Host proofs (Docker/cgroup), deployment and every live verdict** remain SLICE6 or `BLOCKED`.

## E269 — SLICE3 STEP2 pre-code plan: publish (CT106), intent/current/projection (APPROVED after review)

Declared 2026-10-22 **before any code**, per the standing rule, then **reviewed by a peer agent and
amended** the same day. Status: **approved for implementation** — the reviewed rules (E269.3–E269.4) are
the approved version; the lead implements, the reviewer reads the final R5/R6/R9 diff, and neither ticks a
STEP nor assigns a verdict. No STEP is ticked and no contract changes state by this section. Numbering
follows E268: **E269 = SLICE3 STEP2**, `E270` = STEP3 (Q58/BOOTSTRAP bundle), `E271` = STEP5 kills;
recovery stays inside STEP4.

**Review outcome, recorded because it changed the plan.** Seven findings were raised; six held against
source and are incorporated, one was right in diagnosis and wrong in prescription. The one factual claim
*against* the lead that mattered: the plan's D2 justification was **false** (spec:658 says "initial"), so
D2 was withdrawn and promoted to **Q80**, resolved as option (B). Two prescriptions were rejected with
reasons, not preference: a durable stored receipt (exact replays are journal-served, and a foreign id
fails the caller's operation binding) and factoring the drift check out of `_unchanged` (no behavioural
change; five callers already depend on it). Two of the lead's own lines were withdrawn on the reviewer's
evidence: the `operation_ids` append (D10) and the over-broad restart claim (R13).

### E269.0 Blocking questions — Q79 is not one

**Verdict: Q79 does not block E269.** Q79 is about the managed *tool view* (text-only reads, `derive_text`
capability, role→port threading) and gates **SLICE4 STEP2's cutover**. E269 writes no tool, no port, no
registry and no role. Checked against E269's actual surface rather than assumed:

| Q79 claim that could touch publish | Verified position | Verdict |
| --- | --- | --- |
| "`d` (pre-convert outside the sealed tree) is rejected as a publication concern; Stage 1 adopts a content-addressed, view-private cache" | E269 has no converter, no `/scratch` reader and no cache. A view-private cache under `scratch/` is already outside the sealed domain (`_Capture` walks `source/`, not `scratch/`), so nothing in E269 can freeze a derivative. | **not blocking** |
| `session.artifact_store` is `workspace/.fa/artifacts`, inside the validated tree and unreachable through the port | `.fa` is an excluded component at any depth (`_Capture._excluded`), so artifacts can never enter a revision, a manifest or a tombstone. E269's projection never touches `.fa`. This is the *consistent* outcome; whether artifacts should be publishable at all is Q79 Stage 1's question. | **not blocking; agreement recorded** |
| "managed `fs_write_file` is create-only by accident (STALE_REVISION when `expected_sha256` is None)" | That is `write_file`/`edit_file` semantics inside SLICE2. E269 changes no file handler. | **not blocking** |
| Q79 Stage 0 allowed-files list | `tools/__init__.py`, `workspace_port.py`, `read_file.py`, `write_file.py`, `edit_file.py`, `profiles.py`, `recovery/classify.py`, `tool_port.py` — **disjoint** from E269's list (`execution/workspace.py`, `execution/publication.py`, one test file). | **no collision** |

The three Q79 sub-items that *will* land on E269's contract later, so they are named rather than
silently absorbed: (a) `view.record["operation_ids"]` gains its first non-EXEC writer here (publish), so
the "managed records must not carry empty `operation_ids`" rule from §6 has a precedent to follow;
(b) sealed/published views retain bytes with no GC (E268 S4) — Q79's artifact-store GC discussion must
decide retention for *both* stores; (c) a derived-text cache under `scratch/` is view-lifetime by
construction, which E269 makes true structurally rather than by convention.

**Questions raised by this plan, and their rulings (both promoted before any code, per the register-first
rule).** **Q80** — `current.json` has two frozen shapes (spec:658 "initial" three-key vs §5.1 five-key).
Resolved **(B)**: one five-key shape everywhere, spec:658 marked SUPERSEDED, invariant
`current.generation <= metadata.generation`; the union-schema alternative was rejected because it would
accommodate a state with no deployed instance and make the ownership invariant conditional. **Q81** —
canonical roots must be writable on the deployed host (`/repo` ships `read_only: true`). Decided **(A)**:
composition refuses a non-writable root, publish probes without writing and fails fast at prepare, and
the mount decision is verified at SLICE6. Both entries are now in `notes/open-questions-2026-10-07.md`,
which was first **backfilled with Q78 and Q79** — it had ended at Q77, leaving two raised questions cited
only by ledger offset.

### E269.1 Ordering verification

| Claim | Verified against | Result |
| --- | --- | --- |
| publish is the next unit | E267 closed STEP1 part 2; STEP1's remaining parts are Q74 policy + cgroup observer + the host test; STEP2 is "intent/current/projection schemas/order/dir fsync and generation/base CAS" | **holds** — STEP2 needs no cell, no Docker, no service route |
| publish's preconditions all shipped | `prepare_seal`/`mark_sealed`/`_SealInputs` (E267), terminal receipt (E266), `_revision`/`_Capture`/`_snapshot`/`_rename_directory`/`_replace_private_bytes` | **holds** |
| the wire already defines publish | `protocol.py::PUBLISH` request `{sealed_manifest_id, expected_base_revision}`; result `_COMMITTED = {workspace_id, revision_id, tree_sha256, operation_id, projection_complete: true}` | **holds — and it constrains the design**: publish must not reply before projection verifies, and the revision id is *not* a caller field |
| publish needs no dispatcher route | `_dispatch`/`_handle` are injected seams; tests call owners directly (E267 precedent) | **holds**, SLICE1 STEP3 |
| STEP2 does not need STEP4 | STEP2 ships intent/current/projection in-process; restart recovery (`_load` hook) is STEP4 | **holds — stated as a limit, not fudged** |

### E269.2 Current behaviour (source-verified, `6b7f300`)

- `current.json` is `{schema_version, revision_id, tree_sha256}` (`workspace.py::_CURRENT`), written in
  exactly one place today: `_register` (`::_register`), under a `pending/<uuid>` staging tree that is
  renamed in with `renameat2(RENAME_NOREPLACE)`.
- `revisions/<rev>/` = `{tree.json, data/}`; `_revision()` re-walks `data/` and compares it to
  `tree.json` with `mode` substituted, because `data/` is a **retention copy** (0600/0700) while
  `tree.json` carries **logical** modes. `create_view` restores logical modes onto `views/<v>/source/`
  through `_materialize_input`, so a sealed manifest already records the modes a projection must apply.
- `_Capture` fsyncs every copied file and every destination directory it descends through, so a
  materialized tree is durable per level before the walk returns; `_replace_private_bytes` fsyncs the
  file *and* the directory (intent/current writes are durable by construction).
- There is no `intent.json` producer, no `revisions/` writer outside `_register`, and no code that
  writes canonical bytes after registration: `publication.py` is seal-only (`seal_view`,
  `_validate_sealed_tree`, `_derive_revision_id`) and states in its module docstring that publish is
  E268/E269's job.
- `SEALED` is terminal-in-process: seal writes `sealed.json` + flips `view.json`, and `_project_view`
  refuses any state but `OPEN`, so a sealed view's bytes cannot move through the authority again.
- `release_unused_writer` now settles on `PUBLISHED|REJECTED` (E268 D1) — a state nothing can reach
  today, because no producer writes it.

### E269.3 Target behaviour (the rules the tests will hold)

Reviewed 2026-10-22 against a peer review; every rule below is the post-review version. Rules that
changed are marked **(R)** with the reason.

- **R1 preconditions — STATE FIRST, then equality (R).** One transaction, no writes. In this order:
  (a) `_proof_only` capability+principal proof; (b) **dispatch on view state** — `UNKNOWN` →
  `TERMINALITY_UNKNOWN`; `OPEN`/`STOPPING` → `VIEW_CLOSED`; `PUBLISHED` → **R9 replay** (skipping every
  equality check below, because its `current.revision_id` *is* the derived revision); only `SEALED`
  continues; (c) gate closed; (d) `terminal.json` present; (e) `ProtectedPlanContext.recheck()`;
  (f) `binding.metadata["status"] == "OWNED"` with this actor and grant; (g) generation equality
  `view_ref.generation == metadata.generation == manifest.generation` else `STALE_GENERATION`;
  (h) base equality `expected_base_revision == view_ref.base_revision == manifest.base_revision ==
  current.revision_id` else `STALE_REVISION`; (i) payload `sealed_manifest_id ==
  record.sealed_manifest_id` else `STALE_REVISION`.
  *Why (R):* the pre-review plan checked equality before state, so a legitimate retry on a `PUBLISHED`
  view failed `STALE_REVISION` and never reached the replay branch that exists for exactly that case.
- **R2 manifest is read, recomputed against, never re-derived from a directory.** `sealed.json` is read
  from the view directory and re-validated with the *same* `_validate_sealed_tree` seal used
  (`plan_path`/`base_entries` from `prepare_publish`), and cross-checked against the record (`view_id`,
  `workspace_id`, `generation`, `base_revision`). A manifest that disagrees with the record is
  `CORRUPT_STATE`; a malformed one is `INPUT_POLICY`; neither writes anything.
- **R3 id derivation.** `revision_id = derive_revision_id(manifest)` (shipped, content-addressed over the
  canonical manifest). No caller-supplied id exists on the wire, so none can be honoured.
- **R4 materialization verifies every digest.** Copy the frozen `views/<v>/source/` into
  `pending/<uuid>/revisions/<derived>/data/` with `_Capture`, then compare the copied tree to the
  manifest's **non-deleted** entries on `(path, type, size, sha256, link_target)` in sorted order,
  requiring the same length. Extra path, missing path or moved byte ⇒ `CORRUPT_STATE` and no revision is
  installed. `tree.json` is written from the manifest (`revision_id=derived`, `entries=live`,
  `tree_sha256=manifest.tree_sha256`), never from the walk's own hash. A directory that already exists at
  `revisions/<derived>` is accepted only after `_revision()` re-verifies it equals the manifest.
- **R5 pre-flight, install and intent (R).** Before anything: call the existing
  `workspace.py::_unchanged` (canonical re-walk vs `current.tree_sha256`) and the Q81 writability probe
  (§E269.4 D4/D9). Then `renameat2(RENAME_NOREPLACE)` the staged revision into `revisions/<derived>`,
  fsync `revisions/` and `pending/`, and durably write `intent.json` (`kind=REVISION`, `phase=PREPARED`,
  `base_revision`, `next_revision`, `tree_sha256`, `operation_id`, `target_relative/old_sha256/
  new_sha256` null) with read-back equality. **No canonical byte is written in this phase**, and the
  intent precedes the pointer.
- **R6 the irreversible point is the pointer (R).** `_commit_current` re-reads `current.json` (CAS against
  the value R1 validated) and `workspace.json` (still `OWNED`, same generation), replaces `current.json`
  with the five §5.1 keys `{schema_version:1, workspace_id, generation, revision_id, tree_sha256}`,
  read-back verifies. Then — **before the first canonical byte** — advances the intent to
  `phase=PROJECTING`. `COMMITTED` is **not** produced in E269: projection is always entered (and is a no-op when nothing
  differs), so the phase goes `PREPARED → PROJECTING → DONE`. `phase` remains advisory in every case:
  `current.json` alone discriminates whether the commit happened.
  A **determinate** pre-commit failure (CAS lost, generation moved) discards only this attempt's own
  `revisions/<derived>` and clears the intent, leaving `current.json` byte-identical.
- **R7 projection is a pure function of the committed revision.** For each live entry: if the canonical
  path already matches `(type, mode, size, sha256)` it is skipped (idempotent by construction); otherwise a
  directory is created, or a file is written to a sibling temp with the manifest's logical mode, fsynced
  and `os.replace`d into place. Tombstones unlink the canonical path when present (`no-follow`) and are
  otherwise no-ops. Rules: never traverse a symlink, never touch a path with an excluded component at
  **any** depth (`.git`, `.fa`, `.venv`, `.env`, configured exclusions), and refuse (`PATH_DENIED`) a
  destination that is a symlink, a special file or a hard-linked regular file. `.git/index` and every
  excluded tree are therefore untouched structurally, not by luck.
- **R8 completion proof (R).** After projection, re-walk the canonical root with `_snapshot` and require
  equality with the manifest's live entries — this is the "no partial current state" test, including
  extra-path drift. Then intent `DONE` + clear, then flip `view.json` to `PUBLISHED` with read-back
  equality. Return `_COMMITTED` `{workspace_id, revision_id, tree_sha256, operation_id,
  projection_complete: true}` where **`operation_id` is the caller's own** (`"op-" + request_id`).
  Publish does **not** append to `view.record["operation_ids"]` (R; see §E269.4 D10): that field's only
  existing meaning is EXEC's duplicate-id uncertainty, and its only consumers are `release_reader` and
  `admit`'s `EXECUTION_UNKNOWN` branch.
- **R9 replay is state-driven and stores nothing (R).** A new request observing `PUBLISHED`:
  re-verify `current.revision_id == derive_revision_id(stored manifest)`, re-run `_unchanged`, re-verify
  the projection (R8's comparison), and return the same five-field receipt with the caller's own
  `operation_id`. No second commit, no second intent, no stored receipt. Exact same-request-id replays
  never reach here — `_dispatch` serves them from the journal (`supervisor.py:409-414`, Q75). A mismatch
  is `CORRUPT_STATE`. An `intent.json` present in any other situation is `WORKSPACE_BUSY`: uncertain state
  belongs to recovery (STEP4), never to a second attempt.
  *Why (R):* the pre-review plan promised "the same receipt" but `operation_id` is the one non-derivable
  field, and a stored foreign id would fail the caller's own operation-binding check — turning a
  recoverable retry into a false uncertainty.
- **R10 no side effects beyond the contract.** No canonical write before the pointer commit; no revision
  write after it; no change to `.git`, `.fa`, `.venv`, `.env`, other views, reader pins, scratch, cell
  state or the journal; no Docker call; nothing found in the tree is executed; no model metadata is read.
- **R11 bounds and observability.** Every phase deadline-bounded (`_budget`), bounded by `InputLimits`,
  reporting the closed error vocabulary (`INPUT_POLICY`, `PATH_DENIED`, `STALE_*`, `VIEW_CLOSED`,
  `TERMINALITY_UNKNOWN`, `WORKSPACE_BUSY`, `DURABILITY_UNKNOWN`, `CORRUPT_STATE`, `UNAUTHORIZED`). No new
  error code: the wire list is closed, so adding one would be a protocol change.
- **R12 seal bytes stay frozen.** If `sealed.json`'s digest no longer matches a re-walk of the view source
  (bytes moved after the barrier), publish is `CORRUPT_STATE` **before** any write — the check R4 performs
  is ordered before install so a moved source cannot land a revision.
- **R13 uncertainty after the pointer (R).** Any failure at or after the `current.json` replace is
  `DURABILITY_UNKNOWN`, marks the authority unhealthy, quarantines the workspace where state allows, and
  never returns a receipt. The view stays `SEALED`, which keeps the writer captive (E268 D1) so reuse is
  impossible until recovery finishes it forward. The same holds after a *successful* publish until
  `release`: the workspace is `OWNED`, so a restart quarantines it — **restart-clean iff released**.

### E269.4 Decisions (D1–D10; D2 withdrawn and promoted, D4 and D10 revised after review)

- **D1 — kill placement (unchanged).** CT106's declared kill stays literal:
  `publication.py::publish_view -> _commit_current`, where `_commit_current` is a private function in
  `publication.py` that owns the pointer phase and calls `authority.commit_revision_current(...)`.
  Removing that call leaves `current.json` at the base revision, so every functional case fails.
- **D2 — WITHDRAWN, promoted to Q80 and resolved as option (B).** `current.json` is five keys everywhere
  (§5.1), written by `_register` and by publish; `_load` enforces `current.workspace_id == workspace_id`
  and `current.generation <= metadata.generation`. The pre-review justification ("the frozen schema always
  had five keys") was **false** — spec:658 says "initial" and describes a real 3-key shape — so spec:658
  now carries an explicit **SUPERSEDED** note rather than a silent edit. No union schema: it would
  accommodate a state with no deployed instance and no committed fixture, and would make the ownership
  invariant conditional on precisely the files that establish it.
- **D3 — four durable boundaries, one transaction each** (unchanged): `prepare_publish` (validate, no
  writes), `materialize_publication` (copy + verify + install + intent), `_commit_current` (CAS + pointer
  + `PROJECTING`), `project_publication` (projection + proof + `DONE` + `PUBLISHED`). The copy runs under
  the authority mutex exactly as `create_view`'s materialization does, so no new locking model.
- **D4 — drift check REUSES `_unchanged` (R).** Publish calls the existing canonical re-walk rather than
  writing a second comparison. Its global effect is accepted and tested: `_unchanged` marks the authority
  unhealthy, so one drifted project tree disables the supervisor until restart. That is already the
  established rule — **five** callers rely on it (`_register` path, `acquire_writer`, `pin_reader`,
  `create_view` ×2) — so publish joining them is consistency, not new blast radius. Factoring the
  comparison out was rejected: it changes nothing behaviourally and splits one rule across two functions.
- **D5 — deterministic failures write nothing; uncertain ones write no success** (unchanged; see R13).
- **D6 — intent vocabulary complete, REVISION-only producer, `PROJECTING` now written (R).**
  `_INTENT` implements all §5.1 keys and the full `kind ∈ {REVISION, PLAN, BOOTSTRAP}` /
  `phase ∈ {PREPARED, COMMITTED, PROJECTING, DONE}` vocabulary, but E269 produces **only** `kind=REVISION`.
  `PLAN` arrives with STEP3's Q58 path, `BOOTSTRAP` with `install_project`; recovery rows for all three
  are STEP4's. `PROJECTING` is written before the first canonical byte so recovery dispatches rather than
  infers.
- **D7 — projection refuses a symlink/special/hard-linked destination (`PATH_DENIED`)** (unchanged).
- **D8 — scope** (unchanged): no dispatcher route, no `prepare_bundle`/`install_project`, no
  CANDIDATE-buffer seal, no recovery hook, no GC, no `REJECTED` producer.
- **D9 — non-writable canonical root fails at prepare (NEW, Q81).** `prepare_publish` proves writability
  **without writing**: `os.fstatvfs(fd).f_flag & os.ST_RDONLY` (verified `os.ST_RDONLY == 1`) plus
  euid-vs-mode on the root directory; refusal is `PATH_DENIED` before any filesystem effect. No free-space
  or ENOSPC pre-check: advisory, racy, and recovery must exist regardless. This is a fail-fast for a
  composition error; the mount decision itself is Q81 and is verified at SLICE6.
- **D10 — publish does not write `operation_ids` (NEW, R).** Publish's operation id lives in
  `intent.json.operation_id`. Adding a second writer with an idempotent meaning to a field whose only
  semantics today are EXEC's duplicate-id uncertainty would overload it, and the field has no consumer on
  project views beyond `release_reader`/`admit`. Result: Q79 Stage 0's "who may append to a view record"
  rule inherits exactly **one** precedent.

### E269.5 Allowed files (nothing else)

- `src/fa/execution/workspace.py` — `_CURRENT` (5 keys, Q80) + `_INTENT` schema; `_write_intent`/
  `_read_intent`/`_set_intent_phase`/`_clear_intent`; `_PublishInputs`; `prepare_publish`,
  `materialize_publication`, `commit_revision_current`, `project_publication`; `_load`'s `current.json`
  invariants.
- `src/fa/execution/publication.py` — `PublishResult`, `publish_view`, `_read_sealed_manifest`,
  `_commit_current`, pure projection helpers; `__all__` extended.
- `tests/test_workspace_publication.py` — new CT106 cases beside the CT104/CT105 banks.
- Docs: this section, `ledger.md` E269 result (after code), `notes/open-questions-2026-10-07.md`
  (Q78/Q79 backfill + Q80/Q81), the spec note's Q80 amendment and E269 review rules.
- **Forbidden:** `protocol.py`, `primitives.py`, `supervisor.py`, `docker.py`, `backend.py`, `client.py`,
  `view_io.py`, any tool/port/profile file (Q79's surface), any second lock, any second walker, any GC.

### E269.6 Tests (C1 composition-root over the real authority; C0 for pure helpers; one C3 case)

Fixture: the existing `Site`/`native_profile`/`_stopped`/`_seal` helpers, then `publish_view` directly —
the real `WorkspaceAuthority`, real filesystem, real views, real barrier (the `CellTermination` seam
doubled only for the kernel fact, as E266/E267). **28 cases**, each naming the rule it holds:

*Happy path and receipt* (R1,R4,R6,R7,R8): pointer advances to the derived id; `_revision` verifies the
new revision; canonical bytes equal the sealed bytes; logical mode restored (not 0600); `current.json` is
exactly five §5.1 keys; the receipt decodes against `protocol.decode_reply(operation=PUBLISH)`;
`intent.json` is gone.

*Preconditions* (R1): stale `expected_base_revision` (`current.json` byte-identical); wrong
`sealed_manifest_id`; `OPEN` view; `STOPPING` view; wrong capability (`UNAUTHORIZED`); tampered manifest
entry digest (R2, no revision installed); source bytes moved after seal (R12); generation moved
(`STALE_GENERATION`).

*Projection* (R7,R10): tombstone removes the file from canonical and from `tree.json`, digest over live
entries only; `.git/index`, `.fa/artifacts` and a `.venv` sentinel byte-identical; a
symlinked destination refused (`PATH_DENIED`).

*Settlement and pins* (R8, E268 D1): publish settles the owner (real `release` succeeds, re-claim advances
generation) — **and the publish→release sequence is restart-clean** (reopened authority keeps it
`AVAILABLE`); a pinned reader keeps the old bytes while a new pin reads the new revision.

*Replay and uncertainty* (R9,R13): second publish on `PUBLISHED` returns the same
`{revision_id, tree_sha256}` with the **new** caller's `operation_id` and writes no second intent; a
pre-existing `intent.json` ⇒ `WORKSPACE_BUSY`; injected `os.replace` failure mid-projection ⇒
`DURABILITY_UNKNOWN`, `current` **is** the new revision, view still `SEALED`, intent still on disk,
`release` refused, authority refuses further work; publish→restart→quarantine still holds (STEP4 limit).

*Pre-flight* (D4,D9,Q80): canonical drift before publish ⇒ `CORRUPT_STATE`, nothing written, authority
unhealthy (the accepted global consequence); a `0o555` canonical root ⇒ `PATH_DENIED` before any write
(C3); a read-only **mount** ⇒ `PATH_DENIED` via a disclosed `os.fstatvfs` double; `_load` rejects a
`current.json` with a foreign `workspace_id` and accepts `generation < metadata.generation`.

### E269.7 Negative proof — declared kills (assertion-only, byte-exact restore)

1. `publication.py::publish_view -> _commit_current` (CT106's named producer).
2. `publish_view -> materialize_publication` (no revision, no intent, no pointer).
3. `_read_sealed_manifest`'s record cross-check (R2: an edited `sealed.json` would publish).
4. R4's copied-tree-vs-manifest comparison (a moved source byte would land).
5. R7's skip-if-equal rule (a resumed projection would rewrite or fail).
6. R8's canonical re-verification (a partial projection would report success).
7. D4's `_unchanged` pre-flight (unmanaged bytes would publish).
8. R9's replay branch (a retry would double-commit).
9. R6's CAS + read-back on `current.json` (a lost CAS would overwrite a newer pointer).
10. R1's state-first ordering (a `PUBLISHED` retry would be refused `STALE_REVISION`).

Reused and **not** claimed as new credit: `_Capture` (walk, fsync, fingerprint staleness, link rules),
`_revision`, `_unchanged`, `_rename_directory`, `_replace_private_bytes`, `_validate_sealed_tree` (E267),
`_proof_only`, `_gate`, `terminal_receipt`.

### E269.8 Definition of done

Red-first evidence per case; `tests/test_workspace_publication.py` + the execution bank
(`tests/test_execution_*.py`) green; `ruff check`, `ruff format --check`, `mypy src/fa/execution`,
`pyrefly check src/fa/execution` clean; `authoring check` `exit_code 0`; all **ten** kills executed with
byte-exact restore and provenance; `ledger.md` E269 result; register row `I03-LIVE-19` unchanged in
wording and status (same file, no new surface) — **no** STEP tick, **no** CT `VERIFIED`, **no** live
verdict, **no** deployment. Known and stated: after a successful publish a supervisor restart still
quarantines the workspace until STEP4's `recover_workspace` exists; the **only** restart-clean path today
is publish → `release`.

### E269.9 Out of scope, leaks and risks

- **Leak (recorded, not fixed):** a crash before `intent.json` exists leaves `revisions/<derived>` and
  `pending/<uuid>` trees with no reference from `current.json`. They are inert but unbounded; STEP4
  classifies them (owned scratch vs unknown) and GC remains out of scope with E268 S4.
- **R1 — size:** ~430 lines in `workspace.py`, ~260 in `publication.py`, 28 cases. Phases are ordered so
  each is independently verifiable; splitting at `materialize`/`project` remains possible without moving
  CT106's kill.
- **R2 — mode fidelity depends on `_materialize_input`:** it restores logical modes onto the view source,
  which is why publishing modes is faithful. A future change that stops restoring modes would rewrite
  every canonical mode to 0600; the happy-path mode assertion is the tripwire.
- **R3 — hard-linked canonical files** are refused (D7); `_Capture` already refuses them at registration,
  so this is consistency, not new behaviour.
- **R4 — `.fa` exclusion is load-bearing:** publication can never carry `.fa`, so an artifact-store file
  is invisible to revisions by construction. Q79 Stage 1 must reason about that boundary; E269 must not
  "fix" it by widening the manifest domain.
- **R5 — `_unchanged`'s global unhealthy flag** is now deliberately reachable from publish (D4); a single
  drifted tree disables the supervisor until restart. Tested, not assumed.
- **R6 — read failure mode most likely to be misjudged by the implementer:** reading a helper's first
  lines and inferring the rest. Mitigation is procedural: quote whole function bodies in evidence, and the
  R5/R6/R9 commit seam gets a second reader on the final diff, not on the plan.


### E269 result — CT106 publish implemented and locally proved (SLICE3 STEP2)

**Status: implemented as a local C1/C3 component. No STEP ticked, no contract `VERIFIED`, no live verdict,
no deployment.** The dispatcher route, the bundle/Q58 half (STEP3) and restart recovery (STEP4) remain
open, so SLICE2's provisioning leg is *not* closed by this.

**What runs now.** `publication.publish_view` drives four durable boundaries, each its own authority
transaction: `prepare_publish` (validate, zero writes) → `materialize_publication` (copy the frozen view
source, verify every entry against the sealed manifest, install `revisions/<derived>`, write
`intent.json` `PREPARED`) → `_commit_current` (CAS `current.json`, then `PROJECTING`) →
`project_publication` (idempotent canonical projection, re-walk proof, `DONE`, clear intent,
`PUBLISHED`, receipt). `verify_publication` is the `PUBLISHED` replay; `abandon_publication` discards only
a provably uncommitted revision.

**Evidence (all re-run at `HEAD`, commands in the ledger).** `tests/test_workspace_publication.py`
**58 passed** (32 pre-existing CT104/CT105 + **26 new CT106 cases**); execution bank with it
**1146 passed**; `ruff check`/`ruff format --check` clean; `mypy src/fa/execution` 19 files; `pyrefly` 0
errors; `authoring check` `exit_code 0`, `diagnostics []`. **10/10 declared kills executed** with
sha256-verified byte-exact restore (one needed a new oracle: see mutant 3 below).

**Three implementation findings, recorded rather than smoothed over.**

1. **D11 — destination-type pre-flight (implementation refinement of D7/D9).** The first draft let a
   symlink-standing-where-a-file-must-go fail during projection, i.e. *after* the pointer, which
   surfaced as `DURABILITY_UNKNOWN`. That is exactly the failure class D9 exists to prevent, so
   `prepare_publish` now type-checks every non-deleted destination (regular single-link file / matching
   symlink / directory) before the pointer and refuses `PATH_DENIED`. Judged a refinement, not a new
   policy: same refusal, earlier and typed. **If the operator disagrees, this is the line to promote.**
2. **`_derive_revision_id` lives in `workspace.py`.** The id names a directory under `revisions/`, so the
   storage module owns the formula and `publication.derive_revision_id` delegates. One implementation
   means a drifted derivation cannot silently disagree with itself (the E259/E264/E265 drift pattern).
3. **`tree.json` never carries tombstones.** `_TREE` pins `deleted` to `False`, so the revision stores
   the manifest's live entries only; tombstones stay a manifest/transport fact. Asserted in the happy
   path rather than assumed.

**Mutant 3 needed a new oracle, which is the interesting part.** Removing the manifest-vs-record
cross-check survived the first sweep: every existing test failed *earlier*, either in the seal validator
(a tampered digest) or in the copied-tree comparison (moved bytes). The cross-check only matters when a
manifest is internally valid but belongs to another grant, so the new case seals two views of the same
revision and copies one view's `sealed.json` into the other. Its identity fields are then the only thing
standing between a sibling's provenance and this grant — `CORRUPT_STATE` at prepare, pointer untouched.

**Explicitly not proved here.** No Docker/cgroup barrier, no dispatcher route, no restart recovery, no
Q58/BOOTSTRAP path, no retention/GC, no live host. The "published but not released ⇒ restart quarantines"
case is asserted as the STEP4 limit, and "publish → release ⇒ restart-clean" is the one claimed clean
path. Register: `I03-LIVE-20` added (`PLANNED / UNEXECUTED`) with the full host choreography and the two
negative controls; the S06 join row updated to say both halves now exist locally.

### E271 result — STEP3 unit A: trusted bundle renderer + private store (Q58/install open)

**Status: unit A of SLICE3 STEP3 implemented and locally proved. `install_project` is BLOCKED on Q82 and
`publish_plan` (Q58) is not started — STEP3 is NOT done, and nothing here ticks it.**

**What runs now.** `publication.render_bundle` is a pure renderer over plain prose producing exactly the
three spec §7.1 paths, with controller-owned frontmatter (`RM-<slug>`, `RM-<slug>-I01`, created, statuses,
actual slice count, `shipped: —`), a fixed ledger heading, and a fixed Artifacts/Increments table.
`publication.prepare_bundle` validates and stores it through
`WorkspaceAuthority.store_bundle`: OWNER grant + no view + no intent, exact `base_revision` CAS, staging
under `pending/` renamed in with `RENAME_NOREPLACE`, and one self-contained directory
`bundles/<bundle-id>/{bundle.json, worklogs/<slug>/…}` — no shared index a concurrent prepare could
corrupt. The reply is `{validated_bundle_id, bundle_sha256}` per the wire row.

**Evidence.** `tests/test_workspace_publication.py` **67 passed** (9 new: 5 C0 renderer, 3 C1 storage, 1
C3 traversal); execution bank with it **1220 passed**; `ruff check`/`format --check` clean (507 files);
`mypy` 19 files; `pyrefly` 0 errors; `authoring check` `exit_code 0`, `diagnostics []`. **7/7 new kills**
executed with sha256-verified restore: disguised-metadata scan, exact-heading rule, slice contiguity, fixed
frontmatter, bundle base CAS, unsettled-view refusal, bundle path traversal.

**Two things the implementation changed, both recorded.**

1. **Path traversal is refused twice, deliberately.** `protocol._check`'s `_byte_limits` already rejects
   `.`/`..`/empty components for any `path` key, so `store_bundle` now translates that
   `ExecutionContractError` into `INPUT_POLICY` instead of letting it escape as an authority failure; the
   writer keeps its own component guard as defence in depth. Reuse first, duplicate second, never invent.
2. **A bundle is one directory, not a directory plus an index.** The first draft kept a shared
   `bundles/index.json`; a second prepare would have overwritten it. Each bundle now owns its manifest, so
   "the bundle I prepared" and "the bundle I install" cannot be confused.

**Deliberately not done, with the reason.**

- **`install_project` is blocked on Q82** — whether a bundle installs as a sibling project directory or in
  place inside the preparing workspace changes what `_COMMITTED`'s `revision_id` means and which root may
  be created in. The mechanism (no-clobber rename, BOOTSTRAP intent before install, never delete an
  installed bundle) is settled; the destination is not, so no code was written for it.
- **`publish_plan` (Q58) is not started.** It is the inverse of E269's order — the canonical plan replace
  *is* the irreversible point, before any pointer commit — and it needs its own PLAN-kind phase ordering.
  Starting it late in a session to claim STEP3 would be the same defect this project keeps recording.
- No dispatcher route, no auto-registration of an installed project, no GC for stored bundles.

### E272 result — adversarial review of `e4fcfae`: eight findings verified, seven closed

**Status: the review's findings are closed and the owning bank is green. STEP3 is still NOT done
(install and `publish_plan` remain) and nothing here ticks a STEP or assigns a CT verdict.**

**Method.** Each finding was re-derived from source before any edit; none was accepted on assertion,
and none was rejected. Where a fix was possible two ways, the one that removes the defect *class* was
chosen over the one that repairs the instance (F2 below is the clearest case).

| # | Finding | Verdict | Disposition |
| --- | --- | --- | --- |
| F1 | `prepare_publish` loaded base entries only when the view was `SEALED`, so any replay validated the manifest against an empty base. Three `_validate_against_base` rules compare each entry with its base, so replay of any manifest carrying a tombstone, a symlink or a plan was refused — i.e. replay was unreachable for every real workflow. | **real, functional** | Base entries now load unconditionally; only the pointer-equality check stays in the `SEALED` branch. Three replay cases (tombstone / symlink / plan) added; mutant killed. |
| F2 | Projection temporaries were created as `.<name>.<uuid>.publish` **in the canonical directory**, so a killed process left debris that `_verify_projection` and `_unchanged` would see as drift, quarantining a workspace whose only sin was being interrupted. | **real, class-wide** | The class is removed, not swept: temporaries live in `<root>/.fa/publish-tmp` (same filesystem for atomic `os.replace`, and `.fa` is excluded at any depth so debris is structurally invisible), and every projection sweeps its own abandoned `*.publish` files first. Mutants killed: temporary-in-canonical-dir, no-sweep, and the scratch-mode regression below. |
| F2a | Second-order defect found while testing F2: `_temporary_directory` demanded `_private` (0700) on every component, but `.fa` is the project's own artifact directory and is normally 0755 — that would have refused **every** publish in a real project, with `CORRUPT_STATE`. | **real, introduced by F2** | Only "a real directory of ours" is required (`O_NOFOLLOW` already refuses a link); no mode demand on a directory inside the user's own tree. Pinned by a case that plants a 0755 scratch. |
| F3 | `_BUNDLE_FILE` had no `mode`, so install would have chosen one at install time and frozen it into the project's genesis revision. | **real** | `mode` is now recorded per file (0644) and once per bundle for directories (0755). Done now, while the schema is still unshipped. |
| F4 | `_outside_fences` was a hand-rolled ``` scanner, so `~~~` fences and 4-space indented blocks were read as prose: metadata could be smuggled inside either, and a fenced `## SLICE2:` could be counted. §7.1 asks for the existing MarkdownIt tokens. | **real** | The project's existing `markdown_it` dependency yields the tokens; code blocks are blanked (line positions preserved), everything else unchanged. Hand-rolled-scanner mutant killed. |
| F5 | `slices: {max(slices)}` where §7.1 says "actual extracted count". | **cosmetic** | Behaviourally equivalent: the same validator refuses non-contiguous slice numbers, so `max == len` whenever rendering succeeds. Changed to `len` for honesty; no kill exists and none is claimed. |
| F6 | Every `prepare_bundle` mints a fresh id, so identical retries accumulate bundles under `bundles/`. | **accepted by design** | Ids are never reused, because "the bundle I prepared" must not be confusable with an earlier attempt's. Retention is a GC concern for a later increment; recorded here so it is not rediscovered as a defect. |
| F7 | `_owner_only` selected the first binding matching principal+actor and *then* compared the digest, so a caller holding a valid grant on a second workspace got `UNAUTHORIZED` whenever the first matching binding was someone else's. | **real** | The capability is now part of the selection predicate. Mutant killed. |
| F8 | `COMMITTED` is never written (`PREPARED → PROJECTING → DONE`). | **not a defect, needs a record** | §5.1 already says a missing `COMMITTED` write is not evidence that the replacement happened; the recovery decision inspects the target directory, so writing the phase would add a durable write with no branch depending on it. Recorded for STEP4: **recovery must never key on `COMMITTED`** (see the §5.1 note). |

**Q82 settled.** The install destination is **(B) in place** — `<workspace root>/worklogs/<project_slug>`,
with `_COMMITTED.revision_id` naming the preparing workspace's new revision. The ruling, its four
evidentiary grounds and the binding rules it implies are recorded in
[`notes/open-questions-2026-10-07.md`](../notes/open-questions-2026-10-07.md#q82--where-does-a-prepared-bundle-install-and-what-identifies-the-project-it-creates).

**Evidence.** `tests/test_workspace_publication.py` **76 passed** (9 new: three F1 replay cases, two F2
cases — the sweep case also pins the 0755 scratch mode —, F4, F5 pin, F3, F7); execution bank + CLI **1229 passed**; `ruff
check`/`format --check` clean on the three changed files; `mypy src/fa/execution` 19 files; `pyrefly
check src/fa/execution` 0 errors; `fa authoring-check` `exit_code 0`, `diagnostics 0`. **7/7 mutants
killed** with sha256-verified byte-exact restore (`F1`, `F2` location, `F2` sweep, `F2a` scratch mode,
`F3`, `F4`, `F7`); F5 has no mutant because none exists.

Not proved, and not claimed: the Docker/cgroup barrier, the dispatcher route, restart recovery (CT107,
STEP4), Q58/`publish_plan`, retention/GC, and the live host.

### E271 unit B result — `install_project` implemented on the Q82 (B) ruling

**Status: SLICE3 STEP3's install half is implemented and locally proved. STEP3 is still NOT done —
`publish_plan` (Q58) remains — and nothing here ticks a STEP or assigns a CT verdict.**

**What runs now.** `publication.install_project` validates and hands off; `WorkspaceAuthority.install_project`
owns the whole irreversible step. Order is §5.1's BOOTSTRAP row, deliberately *not* publish's: preconditions
(owner grant, no settled view, no intent, canonical bytes still the current revision, bundle bound to this
workspace/generation/base/slug) → the complete post-install tree is computed and digested *before* any write
→ `intent.json` (`kind=BOOTSTRAP`, `target_relative=worklogs/<slug>`, `new_sha256` = bundle manifest hash) →
the bundle is copied into `<root>/.fa/publish-tmp/<op>` and fsynced (same filesystem, invisible to every
walk) → `renameat2(RENAME_NOREPLACE)` → revision from the canonical tree the rename just created →
`current.json` → projection proof → `DONE`. The bundle is never moved, mutated or deleted.

**Two decisions recorded.** Q82 is settled as **(B) in place** (see the open-questions file for the four
grounds). Q83 records why the operation id is derived from the bundle (`op-` + the bundle's hex): the wire
carries none for this call, and a retried install must correlate to the *same* operation for §5.1 recovery.

**One defect found by the unit's own kill-check, and fixed.** The expected entry list was first sorted
component-wise (`a/b` before `a.md`), but `_Capture.finish` orders entries by **plain path string**, so a
workspace containing a file whose name sorts next to the project directory produced a tree whose digest
could never match. The test written for that refactor (`test_install_orders_entries_as_the_capture_walks`)
caught it at once; the sort is now the capture's own order and the case stays as the oracle.

**What is refused, with nothing written.** `COLLISION` for an existing destination (including the
check-then-rename race, where an *empty* racing directory would have been silently replaced by an ordinary
rename), `STALE_REVISION` for a bundle prepared against another revision, `STALE_GENERATION`, `UNAUTHORIZED`
for a bundle directory copied into the wrong store, `INPUT_POLICY` for an unknown id or a retargeted slug,
`WORKSPACE_BUSY` for an unsettled view.

**Evidence.** `tests/test_workspace_publication.py` **87 passed** (10 install cases); execution bank + CLI
**1240 passed**; `ruff check`/`format --check` clean on the changed files; `mypy src/fa/execution` 19 files;
`pyrefly check src/fa/execution` 0 errors; `fa authoring-check` `exit_code 0`, `diagnostics 0`. **8/8 mutants
killed** with sha256-verified byte-exact restore: no base CAS, ordinary rename instead of `RENAME_NOREPLACE`,
no pointer commit, no bundle digest check, no durable intent, empty base entries, chmod of an existing
`worklogs`, component-wise entry order.

**Deliberately not done, with the reason.** Recovery (`CT107`, STEP4) — the intent this unit leaves behind is
the input to it, and no recovery row is implemented or claimed; the dispatcher route (SLICE1 STEP3);
auto-registration of the installed project (SLICE5); bundle GC/retention; and `publish_plan` (Q58), which
is the inverse ordering (the canonical plan replace *is* the irreversible point) and needs its own phase
analysis. `I03-LIVE-22` is PLANNED / UNEXECUTED: no Docker/cgroup barrier, no installed service, no restart.

### E273 result — SLICE3 STEP3 unit C: `publish_plan` (Q58) implemented and locally proved

**Status: STEP3's plan half is implemented. STEP3 is still NOT complete — routing the controller through
it (the dispatcher leg) is what remains — and nothing here ticks a STEP or assigns a CT verdict.**

**The order is the inverse of publish, on purpose.** `publication.publish_plan` validates and hands off;
`WorkspaceAuthority.publish_plan` owns the boundary. Every precondition and the *complete* post-replace tree
are computed before any write (owner grant; no unsettled view; no intent; canonical bytes still the current
revision; the ref's path is exactly `worklogs/<slug>/increments/<name>.md`; the buffer passes the plan rules —
strict UTF-8, non-empty, ≤ 1 MiB; the ref's hash is not the hash of the bytes being written) → durable
`intent.json` (`kind=PLAN`, `target_relative`, `old_sha256`, `new_sha256`, `next_revision`, `phase=PREPARED`) →
`os.replace` of a staged, fsynced, mode-preserving sibling **at the same path** (the irreversible point) →
parent fsync → revision from the canonical tree the replace just created → `current.json` → projection proof →
`DONE`. After the replace there is no step that can restore the old bytes: recovery is forward, by design.

**One mechanism, shared with install (refactor, behaviour-neutral).** `_install_write_revision` and
`_install_commit_current` are now `_write_revision_from_canonical` / `_commit_pointer`, and both forward-only
kinds call them; install is the case where the directory was renamed, replacement the case where the file was.
`_forward_gates` (view/intent check, writability probe, `unchanged` proof) is likewise one helper now. The
install bank stayed at its full size through the refactor — the one test that patched the old private names by
string was re-pointed, and that is the only edit the refactor needed.

**What is shared with `inner_loop/plan_promotion.py`, and what supersedes it.** The *rules* are imported,
never retyped: `_decode_plan_bytes` (strict UTF-8, non-empty, ≤ 1 MiB), `PlanRef`, `PlanSnapshot` from
`plan_admission`. The *transport* cannot be reused from inside the authority: `publish_plan_buffer` reopens the
workspace by host path (which §4's rooted, no-follow IO exists to forbid) and takes a second, path-keyed lock
inside the authority's own mutex. So the promotion discipline — prove the source hash, stage a unique sibling,
fsync, replace the same path, prove the result, never leave a second active plan — is reproduced on
descriptors, and serialization comes from the authority mutex plus the pointer CAS instead of a lock file. The
old transport is not a fallback: it is deleted when the controller is routed (see the last paragraph).

**Two checks were deleted because they could not disagree with the copy proof (found by the unit's own
mutants, which survived).** (a) The revision-level source CAS in `_plan_prepare` was dropped: the pre-replace
re-proof compares the ref's `old_sha256` against the bytes that `_forward_gates`/`_unchanged` has just proved
equal to the current revision, so the two comparisons cannot differ — the surviving double is the one that also
closes the TOCTOU window. (b) The post-replace hash/mode re-check was dropped for the same reason:
`_write_revision_from_canonical` copies this exact path and refuses the whole tree unless every entry's size,
digest, type and mode match *before a revision or pointer exists*. Q58's "post-hash/mode checks" are therefore
satisfied by the copy, not by a second check that could never fire on its own.

**The path shape is enforced here, not by callers.** `publish_plan` is not a general controller file-write API
(spec §7.1, Q58's "not an arbitrary model file-map API"): exactly four components, `worklogs/<slug>/increments/`
and a `.md` leaf, no `.`/`..`/empty component, no protected component. Anything else is `INPUT_POLICY`, or
`PATH_DENIED` for a protected component.

**Refusals, all with nothing written.** `STALE_REVISION` for a stale ref hash (also when the plan vanished
between prepare and replace), for a concurrent host write detected by the pre-replace re-proof, and for a plan
whose bytes are the ones already there is `INPUT_POLICY` (a replacement must replace something);
`PATH_DENIED` for a link swapped in after staging (`O_NOFOLLOW` + `O_NONBLOCK` open, then regular-file and
single-link `fstat`); `INPUT_POLICY` for bytes that are not a plan, for a path that is not the canonical plan,
and for an entry that is not a committed regular file; `UNAUTHORIZED` for a capability that is not this
workspace's owner grant; `WORKSPACE_BUSY` for an unsettled view or an existing intent. A symlinked plan can
never reach a revision at all: admission refuses the ref (`symlink`) and registration refuses the tree.

**Failures after the replace keep the truth and stop serving.** `DURABILITY_UNKNOWN` for an I/O failure
(including the parent fsync), `CORRUPT_STATE` when the copied tree provably differs from the expectation; in
both cases the intent stays `PREPARED`, `_healthy` goes false, and a later operation is refused because the
canonical tree no longer matches any committed revision. No rollback, no replay, no receipt.

**Evidence.** `tests/test_workspace_publication.py` **99 passed** (12 replacement cases, C1 over the real
authority); execution bank + publication **1190 passed**; `ruff check`/`format --check` clean on the three
changed files; `mypy src/fa/execution` 19 files; `pyrefly check src/fa/execution` 0 errors; `fa
authoring-check` `exit_code 0`, `diagnostics 0`. **10/10 mutants killed** with sha256-verified byte-exact
restore: no pre-replace re-proof, no durable intent, no mode preservation, follow the replace path, no plan byte
rules, any path replaceable, no revision commit, rollback after replace, identical bytes accepted, no forward
gates. Two further candidate mutants were removed from the sweep rather than "fixed": the parent-fsync ordering
and the `_healthy` flag are not observable in-process (the API-visible consequence of the latter is the
canonical-vs-revision drift refusal, which is asserted).

**Deliberately not done, with the reason.** The controller leg: `_promote_validated_plan` still calls
`inner_loop/plan_promotion.publish_plan_buffer` directly, because the authority route needs the dispatcher
(SLICE1 STEP3) and a controller-side client handle. That route is the **`publish` of a CANDIDATE view**
(§5: "publish of CANDIDATE uses PLAN intent at the scoped canonical PlanRef path"), not a twentieth
operation — the closed enum stays nineteen, so `publish_plan` is the authority's primitive and never a
wire verb. Until the route lands, the transitional rule is explicit: the
authority refuses any seal whose plan bytes moved outside it (`_validate_plan_boundary`), so mixing the two
writers fails closed instead of silently forking the plan; the switch to a single writer must delete
`publish_plan_buffer`, not keep it as a fallback. Recovery of a `PLAN` intent is CT107/STEP4 — the intent this
unit leaves is its input. `I03-LIVE-23` is PLANNED / UNEXECUTED: no Docker/cgroup barrier, no installed
service, no restart.

### E274 result — SLICE1 STEP3 part 1: the pre-reservation authority check (CT99)

**Status: the dispatcher's `authorize` seam is real. STEP3 is NOT done — the nineteen handlers and
`build_supervisor/main` are the next part — and nothing here ticks a STEP or assigns a CT verdict.**

**What was missing.** `SupervisorDispatcher` existed with an injected `authorize`/`handle` pair, but
every construction of it was a test double (`tests/test_execution_dispatch.py`,
`tests/test_execution_context.py`): "authorized" meant "a fixture said so", and the authority's grants
were only proved *inside* each handler, after a journal reservation. A request that could never own
anything therefore still consumed a reservation.

**What runs now.** `WorkspaceAuthority.authorize(peer, request, *, deadline)` — CT99's
`_authorize_request` owner — decodes the closed envelope, proves the grant the operation names
(`_owner_only` for a view-less request, `_proof_only` for a view-scoped one; `RELEASE` therefore keeps
exactly its two shapes without a special case), and returns the **stored** `ProtectedPlanContext` for
`pin_reader`, `create_view` and `exec`, rechecked against the pinned bytes. It reserves nothing, mints
nothing, writes nothing, and is not admission: every state rule (view state, publication ordering,
collision, CAS) stays with the handler, which re-proves under its own transaction.

**The layering decision, found by two survivors.** The first version also re-derived the §2.1 envelope
shape inside the authorizer (`_VIEWLESS_OPERATIONS`, `_CAPABILITY_FREE_OPERATIONS`). Three mutants
survived because those rules **could never fire**: `authorize` decodes with the same
`decode_request` the dispatcher uses, and that decoder already enforces the null-capability set, the
null-namespace-only-for-health rule and the null-view set. The tables and the duplicate checks are
deleted: the closed wire decoder owns shape, the authority owns proof. The cases stay in the bank as
the composed guarantee (they must still refuse `INVALID_REQUEST`), but they no longer pretend to kill a
second implementation. Two further mutants were retargeted rather than dropped: "any live view instead
of this one" and "namespace not proved" (the second needed a unique anchor inside `_proof_only`).

**One boundary default recorded.** The wire carries no formal-evidence claim, so a plan context built
on the wire has `formal_evidence=False`; only the internal API can set it true. A wire request can
therefore bind a plan but can never claim formal evidence for it.

**Classification is derived, not retyped.** `supervisor.py` now owns `READONLY_OPERATIONS` and
`AUTHORITY_GATED_OPERATIONS`; the dispatcher refuses to construct if a mutator could ever be classified
readonly, and `_dispatch` uses the constant instead of an inline literal set.

**Evidence.** `tests/test_workspace_authorize.py` **10 passed** (C1 over the real authority, C0 for the
classification); execution bank + publication + this bank **1200 passed**; `ruff check`/`format --check`
clean; `mypy src/fa/execution` 19 files; `pyrefly check src/fa/execution` 0 errors; `fa authoring-check`
`exit_code 0`, `diagnostics 0`. **7/7 mutants killed** with sha256-verified byte-exact restore: no owner
proof, any live view instead of this one, no workspace claim check, namespace not proved, pin context
not proved, exec context not proved, named revision not opened.

**Deliberately not done, with the reason.** The nineteen `handle` routes and `build_supervisor/main`:
each route needs its own reply-shape proof, and shipping a table of half-wired owners would be the
"failing-main stub" §4 forbids. Also untouched: service config/install/image and the atomic caller
cutover (SLICE4), and the CANDIDATE `publish` leg that carries Q58's plan replacement onto the wire —
that is the `publish` route for a CANDIDATE view (§5), **not** a twentieth operation; the closed enum
stays nineteen. `I03-LIVE-24` is PLANNED / UNEXECUTED: no installed service, no UDS, no restart.

### E275 — ordering verification for the remaining I03 work (no implementation claim)

**Why this exists.** Two units landed that nothing calls yet (`publish_plan` E273, the authorizer E274),
and an E2E lane (SLICE6) is now being written against these commits. Before adding more, the remaining
order was verified against what the repository actually executes, so no unit lands behind a
composition that does not route it.

**Fact 1 — the whole managed path is dormant, and that is verified, not assumed.**
`src/fa/cli.py` never imports `fa.execution`. Nothing in `src/` imports
`fa.execution.{publication,backend,provisioning}`; `ManagedProvisioner` is constructed only in tests;
`build_tools(..., workspace_io=…)` is never passed a port anywhere in `src/`. What users execute today is
the **host** path. So "dead code in prod" cannot happen yet by construction — the live risk is the
inverse: a composition that starts routing a component whose crash semantics are still open.

**Fact 2 — two merged irreversible points have no forward path.** `_load` rewrites every `OWNED`
workspace to `QUARANTINED` and never inspects `intent.json`; `_forward_gates` then refuses any workspace
whose intent survives (`WORKSPACE_BUSY`). A SIGKILL after `install_project`'s `RENAME_NOREPLACE` or after
`publish_plan`'s same-path replace therefore leaves a workspace that can never advance again, and the
E2E rows already registered (`I03-LIVE-22`, `I03-LIVE-23`) assert exactly that it "must recover forward".

**Fact 3 — the remaining items and their real dependencies.**

| # | Item | Record | Depends on | Lands with |
| --- | --- | --- | --- | --- |
| 1 | CT107 `_recover_intent` + stale `pending/` classification | SLICE3 STEP4 | the two shipped irreversible points; `_write_revision_from_canonical`/`_commit_pointer` | its `_load` hook in the same change, so it is live the moment it exists |
| 2 | the nineteen routes + `build_supervisor/main` | SLICE1 STEP3 | 1 (a routed crash is recoverable), E274 authorizer | one change: route table and composition together |
| 3 | CANDIDATE-view `publish` (Q58 controller leg) | SLICE3 STEP3 rest | 2 (a wire `publish` route) | deletes `inner_loop/plan_promotion.publish_plan_buffer` in the same change |
| 4 | provisioner + file-tool port injection, caller cutover | SLICE2 STEP3 injection / SLICE4 | 2 | `SessionManager(workspace_provisioner=…)`, `workspace_io=…`, host `_provision_workspace` removed together |
| 5 | managed acquisition (SLICE5), then accepted package (SLICE6) | SLICE5/6 | 3, 4 | — |

**Status of this table (2026-10-23).** Item 1 is delivered by E276 — `_recover_intent`, the stale
`pending/` classification and the `_load` hook all shipped in one change, as the "lands with" column
required. Item 2's route table and composition are delivered by E277, and E278 delivered the
`CellTermination` join its `stop_view` route needs. Items 3–5 are unchanged and none is started; the four
execution routes and `handoff` stay dormant until the receipt issuer / PTY control / handoff owners land.

**Why recovery precedes the routes, in one sentence each.** (a) Routes multiply the number of ways to
crash into an unrecoverable workspace, so the recovery owner must exist first. (b) The E2E lane cannot
pass its registered fault rows without it. (c) Routes add no durable semantics, so nothing in them is
blocked by going second — whereas a route table built first would have to be re-opened to thread the
recovery outcomes.

**Why the routes and `build_supervisor` are one change.** A route table with a handler that no
composition can construct is the "failing-main stub" §4 forbids; conversely a `main` that serves a
subset is a silent-success surface. The route-coverage test (every `Operation` member routed, none
extra) is the guard, and it must land with both halves.

**Dead-code rules adopted by this ordering (binding for the remaining units).**

- **R1 — join or declare.** A unit either gains an executing caller in the same change, or is listed in
  this table as dormant with the unit that activates it. No third state.
- **R2 — one enum, one table.** No `Operation` member without a route in the same change; the closed
  enum stays nineteen, and `publish_plan`/`recover_*` are authority primitives, never wire verbs.
- **R3 — replacement, not addition.** Activating a managed path deletes the path it supersedes in the
  same change (`publish_plan_buffer`, host `_provision_workspace`). A retained fallback is a second
  writer by another name.
- **R4 — recovery first.** No new irreversible point before its recovery row exists.
- **R5 — name the real seam.** A kill target may only name a producer that exists and is called.

**Two plan-text repairs made here (recorded, not silently).**

1. CT107's kill target was `publication.py::recover_workspace -> _recover_intent`, but `publication.py`
   imports `workspace.py`; a `publication.recover_workspace` that only tests call would itself be the
   dead entry this unit is meant to prevent. The producer is `workspace.py::_load -> _recover_intent`,
   which is the seam `__enter__` already owns. CT107's *contract* text is unchanged; only the kill site
   is corrected (R5).
2. §5.1's frozen intent keys do not include the directories a BOOTSTRAP attempt created, while the
   operator-approved Q82 ruling requires exactly that ("record the directories an attempt created so
   recovery can remove exactly those"). The key is added as `created_directories` (BOOTSTRAP only, `[]`
   elsewhere) — executing a recorded decision, not a new one. No v1 intent exists outside tests today
   (Fact 1), so the added required key needs no migration rule yet; if the composition ships before a
   later schema change, that changes.

**Q84 raised (non-blocking, default = today's behaviour).** When recovery cannot materialize a
deterministic outcome, `_load` fails closed and the authority refuses to start — which is exactly what
`_load` already does for every unprovable workspace and what CT107 calls "quarantine". The alternative
(mark that one workspace `QUARANTINED`, serve the others) needs a status meaning distinct from the
existing "previous epoch is dead" flip. Recorded in the open questions with the reopen condition; the
implementation follows the existing fail-closed rule.

### E276 — CT107 forward recovery: inspect the target, never roll back (SLICE3 STEP4 part 1)

**Why this exists.** E275 Fact 2 named the defect this unit removes: two merged irreversible points
(`install_project`'s `RENAME_NOREPLACE`, `publish_plan`'s same-path replace) plus the ordinary
`current.json` CAS left state that no later process could advance. `_load` flipped every `OWNED`
workspace to `QUARANTINED` without ever reading `intent.json`, and `_forward_gates` then refused that
workspace for as long as the intent survived — so a SIGKILL anywhere after an irreversible syscall froze
the workspace permanently, while `I03-LIVE-22`/`I03-LIVE-23` assert the opposite ("must recover
forward"). Recovery is now the first of E275's five ordering items and lands with its `_load` hook in the
same change (R1).

**The discriminator, per kind, is the inspected target — never `phase`** (§5.1, E272 note).

| Kind | Inspected | Completed forward | Discarded |
| --- | --- | --- | --- |
| REVISION | `current.json` vs `intent.base_revision`/`next_revision` | pointer already `next_revision`: re-project that revision's own `revisions/<id>/data` (idempotent per entry), prove the whole tree, settle the view, `DONE` | pointer still `base_revision` **and** phase `PREPARED`: discard only the owned, re-derivable `revisions/<next_revision>` |
| PLAN | the canonical plan file's own sha256 | hash `== new_sha256`: rebuild the promised tree from the named base revision plus the observed size/hash, then revision/pointer/proof/`DONE` | hash `== old_sha256`: nothing to undo; discard the uncommitted revision and clear the intent |
| BOOTSTRAP | the installed directory at `target_relative` | present: the whole canonical tree must hash to `intent.tree_sha256`, then revision/pointer/proof/`DONE` | absent: discard the attempt's own scratch, remove exactly `created_directories`, prove canonical still equals `current`, clear the intent |

Anything else — a pointer naming a revision this attempt never named, a projected phase with no commit,
a plan hash that is neither side, an installed tree that is not the approved bundle, canonical drift
where the attempt would have to undo something — raises `CORRUPT_STATE` and the workspace keeps its
intent as evidence. No path rolls committed bytes back to `Rold`, and no path reports success for an
observation it did not make.

**Ordering repair in `project_publication` (a defect removed, not a test adjusted).** The publish path
previously wrote `DONE`, **cleared the intent**, and only then flipped `view.json` to `PUBLISHED`. A kill
in that window left a `SEALED` view holding a committed revision with no intent: `prepare_publish`
refuses the retry (`current != view_ref.base_revision` → `STALE_REVISION`), `release_unused_writer`
accepts only `PUBLISHED|REJECTED`, and no evidence remained to reconstruct which view the commit
belonged to. The settle write now happens **before** the clear, so the intent outlives the last
unrecoverable step, and `_recover_revision` performs the same tail.

**Intent schema extension: `view_ref` (nullable).** Completing a committed publish forward is not enough
— the view record must be settled or the owner can never be released. The intent therefore carries the
view it published (`null` for `PLAN`/`BOOTSTRAP`), which is how recovery knows which record to prove and
flip. This is the same class of extension as `created_directories` (Q82): executing a requirement CT107
and CT106 already state ("completes committed projection forward", "publishing settles the owner"), not a
new decision. §5.1's key list is again amended rather than silently exceeded. Because `_INTENT` requires
every key, an intent written by the previous build would now quarantine; no such intent exists outside
tests (E275 Fact 1 — nothing in `src/` constructs the authority), so no migration rule is owed yet.

**Where it runs, and what failure costs.** `_load` calls `_recover_at_load` after `_verify_revision` (which
already proves `revisions/<current>/tree.json` is the bytes `current.json` names) and `_initialize_genesis`,
and before the `OWNED -> QUARANTINED` write, so recovery always sees the status the crash left. It also runs
before the Q80 pointer check, which now reads `binding.current` because recovery may advance the pointer.
Three consequences, stated rather than inherited:

1. **Q84 is answered by the implementation as the shipped per-workspace rule.** An unsettled workspace
   keeps its intent and is held by the same `QUARANTINED` write that holds every restarted workspace;
   every other workspace keeps loading. Only `DURABILITY_UNKNOWN` — the authority's own writes no longer
   reading back — escapes and refuses the whole start, which is the existing poison rule for anything it
   cannot prove (`_healthy = False`). E275's wording described this as a start refusal; the shipped
   behaviour is the narrower one, and it is what `_load` already did for a leftover intent.
2. **`_verify_revision` still gates the load.** A pointer whose durable revision is missing fails the
   whole load before recovery, because that is unprovable state rather than an interrupted attempt.
3. **Recovery is outside every grant.** It takes no capability, proves no peer and writes no journal
   entry: it is the authority inspecting itself, and the mutex plus the catalog loop serialise it.

**Stale `pending/` staging.** `pending/<uuid4().hex>` has exactly two producers (`store_bundle`'s bundle
copy and `_write_revision_from_canonical`'s revision copy) and neither is ever the committed artifact:
committed revisions live under `workspaces/<id>/revisions/`, which this sweep never opens. `_load`
discards an entry only when its name is the 32-hex stage form, it is a private directory owned by this
authority, and it satisfies `_discard_stage`'s own ownership check; anything else refuses the start and is
left for an operator. That satisfies STEP4's exit clause (a killed supervisor leaves no `pending/` entry a
later authority silently ignores) without inventing a "probably ours" deletion rule.

**Replacement, not addition (R3).** One forward-only tail `_finish_forward` now serves
`install_project`, `publish_plan` and both recovery completions, so "revision, pointer, proof, `DONE`" has
one implementation and one idempotent replay path. `_plan_entries`, `_remove_created` and `_settle_view`
were extracted from the producers that already did that work (`_plan_prepare`, `_install_abort`,
`project_publication`), and `_project_entries`/`_project_file`/`_verify_projection` now take the byte
source and entries explicitly instead of a `_ProjectView`, which is what lets recovery replay a committed
revision from `revisions/<id>/data` rather than from a live view that may no longer exist.

**Evidence.** `tests/test_workspace_recovery.py` **22 passed** (C3: real authority, real filesystem, kills
driven by `SystemExit` at named producers so no `except`/`finally` cleanup runs; C1 for the planted
intent/pointer states). Adoption banks: execution bank + publication + authorizer + this bank
**459 passed**; whole `tests/` **682 passed, 1 error** in the sandbox before the `uv`-dependent
`tests/test_controller_entry.py` cases (6 setup errors from the rebuilt environment's empty `uv` cache
under `--offline`, unrelated to this unit). `ruff check`/`format --check` clean; `mypy src/fa/execution`
19 files; `pyrefly check src/fa/execution` 0 errors; `fa authoring-check` `exit_code 0`,
`diagnostics 0`. **17/17 mutants killed** with sha256-verified byte-exact restore: intent
workspace/epoch guard, phase-vs-pointer guard, keeping the uncommitted revision, completing a revision
the pointer does not name, the completed-projection proof, the settle write, the revision-vs-intent hash
guard, the "old plan bytes" branch, the recomputed-vs-promised plan tree, `_remove_created`, the
canonical-drift proof before undoing, the installed-tree proof, the staging name check, discarding the
staging, both `view.json` proofs, and the single intent-clear.

**Deliberately not done, with the reason.** STEP4 stays unticked: this is the local C0/C3 half. Still
owed are the kernel-observed crash matrix on the approved filesystem (`tests/integration/
test_publication_recovery.py` under `FA_REQUIRE_EXECUTION_HOST=1`, including kills *inside* recovery
itself), the explicit process-crash versus power-loss labelling, and the fsync-unsupported/EIO cases —
none of which a process-only `SystemExit` can produce. `bundles/` retention is left alone: a stored
bundle is a valid retained artifact (E271), and garbage collection is its own unit with its own
reachability rule, not recovery's business. `I03-LIVE-25` is PLANNED / UNEXECUTED: no installed service,
no UDS, no real kill, no restart.

## Scope and ownership handoff

Migration groups A/B/C/E/D/F map respectively to SLICE1/2/3/4/5/6. CT96/CT97 original producer
kills retained; CT88/CT89 and former SLICE7 STEPs1–10 retain IDs inside final SLICE6. Clause
successors for retained CT90/CT92–CT95: managed capability/selection/schema → SLICE5; supervised
IO/PlanRef/promotion → SLICE2/3/4. Local CT66 parser remains I02; supervised binding → SLICE4.
E223's four acceptance successors are SLICE6 STEP7/9/10 and the explicit DoD items above;
[migration bank §9](../notes/i02-to-i03-scope-migration-2026-10-15.md#9-e223-closeout-acceptance-transfer--2026-10-16)
keeps the mapping and uncompleted status. No ownership transfer is evidence, no old unique case
is deleted or assigned PASS. The local plan-versus-diff review remains I02 work, not a substitute
for I03's final broad review. No successor box is checked by this documentation change.

Not delivered: old per-slice scheduler/tracker/L2-eval/TEST-DEFECT/CT10b/tests_note consumers. They
remain the roadmap's named deferred successor; foundation shipping neither expires operator ticking
nor provides L2 VERIFIED. I04–I06 numbering and Q64→I06 unchanged. Parallel orchestration, CAS/
overlay/backend matrix, advanced privacy/anti-persistence/GC, package-proxy platform and calibration
remain outside I03. PTY/FastAPI is a cell transport choice, not a fourth role or independent milestone.

## E250 — E2E source/seam inventory repaired before further implementation

The existing live register previously omitted explicit I03 entries. It now tracks all14 added
Python modules, both modified production surfaces and8 cross-module joins against exact source
hashes/AST inventory.16 omitted-module controls fail; no live case is implemented/executed by this
inventory. Historical I02 project-import/env assertions apply inside cells, not the controller.
Next dependency-ready STEP1 seam: dispatcher must pass authenticated peer and original absolute
deadline explicitly through authorization/handler to actual backend/admission (§2.2, F20/F21),
not infer identity from namespace or reset command budget. Actual owners/SLICE2 remain unfinished.

## E252 — confirmed worker handoff repaired; actual owners NEXT

E252 repairs the E251-confirmed reply-visible/RUN-gate-retirement race in cell_worker.serve.
Production best practice: use the existing publication lock as one linearization boundary for
next-RUN admission and completed-RUN gate retirement, including reply-write failure cleanup.
No retry, scheduler, timeout increase, policy change or parallel command execution. Concurrent
controls and main-thread PTY acquisition/prior-thread join remain. Unavailable stream is still
uncertain; STOP/worker exit remains no cgroup/terminality proof.
TEST-EDITS: tests/test_execution_attach.py — append one deterministic real worker/PTY/UDS/attach
scheduling regression; old file is an exact byte prefix. Native-lock wrappers expose the window,
not fake worker results. Unfixed source fails the admission assertion [True, False] != [True]
(1failed/52deselected0.70s, clean setup/teardown); fixed focused127PASS5.53s.
Final whole15-module owning bank733PASS43.25s → eleven whole733-bank assertion-only kills
26/62/26/26/4/16/2/2/1/1/1 → restored733PASS42.43s. Both worker producers (admission coordination,
retirement-inside-publication) kill independently. All phases clean except intended mutant CALL
assertions; no skips/warnings/collection/runtime/infra credit. All598 source/input hashes
exact; supervisor.py AND cell_worker.py independently match frozen snapshots. Ruff/format27PASS,
Mypy27/183PASS; configured+clean-path Pyrefly0errors (existing141suppressed/50warnings).
Broader28modules1253PASS57.98s, including the actual E251 failing sequential-RUN test.
E2511251PASS1FAIL remains immutable red history, repaired by this changed source, not a rerun waiver.
Evidence `notes/evidence/i03-e252/worker-handoff.json.gz`, 1173316bytes SHA25683da84e828616b1b109579c83866c166f9cefb08348a0eb06fe285fbba4f7c40.
C0/C3 component proof only; C1 actual authority/backend factory and C2 deployed callers remain absent.
E250 inventory unchanged:16 production surfaces/eight joins, all live PLANNED/UNEXECUTED; extend
I03-LIVE-11/S03 with the forced reply-publication/next-RUN schedule. No early host/deployment run.
NEXT implement actual WorkspaceAuthority registration/writer generation/readers/materialization/
admit/drain, reusing E245 RootedViewIO, joined to actual CellBackend per-view episodes/per-command
records and independent terminality; then real factory/caller/mount cutover. SLICE1 is NOT shipped;
SLICE2/all35STEPS/four final duties remain open. Q59/Q75/Q76/final-SLICE6 rollout unchanged.

## E253 — existing-root/R0/writer implemented; actual view/admission/backend NEXT


### E253 — actual owner construction: existing-root registration/R0/writer (before code)

Implement the first real WorkspaceAuthority ownership path in execution/workspace.py; retain
OperationJournal.single_supervisor as the ONE startup lock and journal, not a second lock service.
Existing-root registration is an internal construction API, not a partial production wire dispatcher.
New-root install/provisioning remains the SLICE3 join; do not add a failing factory or permissive gate.
Before snapshot, deployment must already quiesce legacy canonical writers as §4 requires; ordinary
metadata/hash checks detect conflicts, not a kernel CAS or proof of host rollout.

Protected registration uses the exact §3.1 workspace.json schema, initially generation0/AVAILABLE.
Freeze the private initial current.json schema as exactly {schema_version:1,revision_id,tree_sha256};
the retained revision's tree.json is exactly {schema_version:1,revision_id,tree_sha256,entries}, entries
use §5's sorted ordinary tree-entry fields, without deletions for R0. Tree hash is the existing
canonical-JSON nondeleted-entry hash. This is data retention, not a second operation history or seal.
Private manifest cap64MiB is independent of the4MiB wire cap; supported traversal depth is1..64.
Count directory entries while enumerating, before unbounded list allocation. Mutex queueing and
post-generation checks consume the original deadline; expiry cannot issue a grant.
Copy dirty filesystem bytes under descriptor roots, excluding .git/.fa/.venv/.env and configured
exclusions; preserve modes in the manifest, store service-private immutable revision data. No Git
execution/index/config/hooks. Validate relative in-root symlink chains as data, not dereferenced copy;
unsafe links/hardlinks/special files/limits fail. Nested mount crossings fail closed before copy;
Linux fdinfo mount IDs prevent importing an external bind-mounted control tree. Check root identity, approved-root identity and
physical filesystem ancestry (including Linux bind-mount aliases), not only lexical paths.
Stage registration wholly under private state, fsync files/directories/metadata, no-clobber install
then fsync catalog before returning IDs. No canonical mkdir/chmod/chown or registered-tree cleanup.

Acquire holds a per-workspace writer.lock for its lifetime, persists advanced generation plus
owner_namespace/active_actor before creating a memory-only principal+namespace-bound grant. Recheck
canonical bytes against retained current input; detected maintenance changes block/quarantine,
never silently serve stale R0. Release is allowed only for an unused owner with no views/intents;
used-view settlement remains actual admission/backend/publication work. Startup retains pins/views,
quarantines prior OWNED metadata, and never renews old tokens/generations or admits a writer before
real recovery. Persistence ambiguity poisons this owner and blocks further work, not retry success.

Local binary proof: dirty/untracked/deleted/index sentinels and modes; same-inode/physical ancestor/
root-rebind denial; bounded regular copy/link policy; two writer claimers exactly one grant; exact
metadata generation-before-grant, disk secret absence, principal/namespace/release rejection;
startup lock/process contention and restart quarantine; short-write/fsync/copy faults; no canonical
cleanup or mutations on denial. Full owning-bank mutations target root binding/overlap, input policy,
generation persistence and restart quarantine. C0/C3/component sensitivity only, no C1/C2/CT closure.
Then construct immutable pins/views/admission/drain with E245 RootedViewIO and actual CellBackend;
no temporary authority. All checkboxes and final-SLICE6 live rollout obligations remain open.

### E253 implementation/evidence checkpoint

E253 constructs the actual WorkspaceAuthority existing-root/R0/writer path, not a placeholder
admission callback. Reuses the SAME OperationJournal.single_supervisor/startup recovery; one protected
JSON catalog, retained directory identities and per-workspace writer flock, no second DB/service.
Source evidence: src/fa/execution/workspace.py::WorkspaceAuthority:406, register_existing:603, acquire_writer:717, _claim_generation:765, _load:541, release_unused_writer:774.
Registration captures dirty/binary/untracked filesystem bytes and relative safe link chains under
bounded no-follow descriptors, excludes control/Git/env/cache data, rejects root/inode/physical
ancestry/bind aliases and nested mount crossings, then stages/fsyncs/no-clobber installs private R0.
Canonical bytes/index/modes are untouched. Manifest retention cap64MiB is independent of4MiB wire;
entry enumeration allocates only within the limit; input traversal supports1..64 levels.
Writer generation/owner/actor persists and is reread before a memory-only principal/namespace grant;
mutex queueing and post-durability checks consume the original deadline. Unused release cannot settle
views/intents. Restart quarantines old ownership without renewal; persistence ambiguity fences owner.
Legacy-writer quiescence remains the deployment prerequisite, not proved by source/hash checks.
77 new C0/C3 cases, real Linux FS/FDs/flocks and child processes; bind-mount counterfactuals explicitly
simulate kernel facts, NOT actual deployed mount proof. No existing source/test changed. Found root
selection FD leak: actual new fault regression fails unfixed source by assertion1!=0, repaired via
FD ownership transfer before fallible mount reads, not retry/suppression. Focused77PASS (exact timing in raw proof).
Final whole16-module bank810PASS43.84s → fifteen whole810-bank assertion-only kills
1/4/17/1/14/1/1/1/1/1/1/2/1/1/1 → restored810PASS42.77s. All phases clean except intended mutant CALL
assertions; no skips/warnings/collection/runtime/infra credit. All600 source/input hashes restored
exactly. Ruff/format29PASS, Mypy29/184PASS, configured clean-path Pyrefly0errors (existing141suppressed/
50warnings). Broader29modules1330PASS58.06s. First806 trial's copy mutation rejected for two escaping
consumer domain exceptions; two NEW tests now assert authoritative retained bytes BEFORE idempotency/
restart consumers, no catch/reclassification/old assertion weakening. Controlled stopped FD-review
baseline also preserved without credit. Corrected inconsistent directory-mount counterfactual to
assign the whole subtree one foreign mount ID; development77-case producer preflight retained
WITHOUT final sensitivity credit. Complete prior807/14/1327 proof superseded by final review fix:
non-UTF8 symlink targets now return INPUT_POLICY, not escaping UnicodeError; malformed filename/
target and valid Unicode preservation checked. Pre-fix runtime diagnostic is NOT a mutation kill.
Only fresh final-source full-bank proof above counts.
Evidence `notes/evidence/i03-e253/workspace-owner.json.gz`, 3894523bytes SHA2561d60a28c98cfb4588ce885670e0c3bc98c73bbd6afa381b16288942fd4206faf.
E2E inventory now17 production surfaces/eight joins; new module tracked before coding and omission
counterfactual rejects its removal. E250 historical hashes/E251 red/E252 proof unchanged; ALL live
verdicts PLANNED/UNEXECUTED. No C1/C2/service/host/CT101–103 completion or checkbox tick.
NEXT construct immutable pins/views and actual admit/close-admission/drain using retained E245
RootedViewIO and Q76 protected context, then actual CellBackend episodes/per-command records,
startup owned-cell reconciliation/independent terminality and real factory/caller/mount cutover.
SLICE1 remains NOT shipped; all35STEPS/four final duties open. Q59/Q75/Q76/final-SLICE6 rollout unchanged.


## E254 pre-code declaration — Q77 uniformly positive genesis

Operator delegated the production-engineering solution; select genesis1/first-writer2, preserving
positive identity/receipt contracts rather than introducing READ-only zero exceptions. This
supersedes E253's initial0 (historical evidence unchanged). Code scope is workspace.py plus its
existing tests: guarded durable legacy0 initialization after R0 validation under startup lock,
no-owner/no-view/no-intent/native-writer-lock checks, persist/reread before proceeding; nonzero
untouched. No token minted, no caller activation, no pin/admission stub. CT102/103 prerequisite
and SLICE1 STEP2 dependency only. New C0/C3 actual-FS/lock/fault regressions; old generation
expectations shift by one, all other assertions preserved. Full owning-bank sensitivity removes
initialization call/unsafe-state guard/durable persistence; no runtime or infrastructure kill credit.
Future actual fresh-R0 pin/view/PTY service witness remains planned at final SLICE6; all35STEPS
and four duties stay open. Allowed supporting edits: Q77/spec/HANDOFF/ledger/increment/register/
review/index plus evidence/i03-e254/genesis.json.gz. No runtime dependency/schema changes.

### E254 implementation checkpoint

Q77 resolved by explicit operator delegation to production-engineering judgment: select one
uniformly positive epoch. Registration now persists genesis1/AVAILABLE WITHOUT ownership or a
grant; first writer durably advances to2. Existing positive identities/receipts stay strict; no
READ-only zero exception, extra allocator, DB or token renewal. Old epoch0 initializes only under
the original startup guard after R0 validation, no owner/views/intent and acquired native writer
lock. Private atomic replace/fsync plus exact reread precede accepting work; ambiguity blocks.
Source: src/fa/execution/workspace.py::_load:541, _initialize_genesis:568, register_existing:639.
17 new native C0/C3 cases;94focusedPASS2.30s. Exactly17 pre-existing generation assertions shift
by one; original test prefix otherwise exact except required helper imports. No old assertion
removed/caught. New successful-startup tests reuse the existing closed-domain ok oracle; OS/runtime
failures stay uncaught. Whole16-module827PASS46.39s → seven whole827-bank assertion-only kills
19/12/2/2/1/5/1 → restored827PASS46.42s; all collection/setup/teardown clean, no runtime/
infra credit. All600 frozen inputs exact. Ruff/format29PASS, Mypy29/184PASS, Pyrefly0errors with
existing141suppressed/50warnings. Broader1347PASS59.74s. Fixture-only static diagnostics are
retained in the archive without kill credit. Prior E253 evidence is unchanged.
Evidence: `notes/evidence/i03-e254/genesis.json.gz`, 955682bytes SHA25653ebe8dca0e114c32a766cc75ca770767183ae9ee09bb34b9d4ed604e6c70428.
This fixes genesis identity, NOT a reader grant or pin implementation. Actual immutable pins/views,
admit/close-admission/drain, CellBackend episodes/restart/terminality, service/factory and caller/
mount cutover remain next. SLICE1 NOT shipped; all35STEPS/four final duties remain open. Q75/Q76
and final-SLICE6 host rollout unchanged. Inventory17surfaces/eight joins; all live UNEXECUTED.


## E255 pre-code — actual immutable reader ownership and rooted reads

Construct pin_reader/read_file/release_reader inside the existing WorkspaceAuthority, not a second
service or permissive execution authority. CT102/CT103 retention and SLICE1 STEP2 dependency;
no create_view/admit/CellBackend/full-contract completion from reader construction. Protected
view.json uses the existing exact §3.1 schema, READ/PROJECT, OPEN and operation_ids:[]; base revision
is retained before acknowledgement. Capability/principal/formal policy stay process-private.
Required private formal_evidence + admitted PlanRef are supplied by the trusted caller; construct
ProtectedPlanContext from the actual retained source, never infer policy from PROJECT/null. An
explicit operator-approved view_profile config supplies UID/GID; absent config rejects reader IO,
not guessed deployment identities. No new wire key, profile routing mode or runtime dependency.
Reopen/verify protected revision and view identities; validate complete revision on pin creation,
retain its actual source descriptor/tree entries. Rooted reads reuse E245, hash complete files and
compare retained SHA; no canonical fallback. READ pins ignore later writer generation. Writer
unused-release ignores valid READ retention but still blocks unknown/writable views/intents.
Release revokes this exact reader only, retains revision/metadata, never claims cell terminality.
Read/release/shutdown use the existing original-deadline authority lock through IO so admitted
FDs stay alive; no global journal lock is held waiting on handlers. Per-workspace execution
admission/drain remains separate actual construction work, not fulfilled by this coarse reader lock.
Allowed code: workspace.py and NEW test_execution_readers.py; old source/tests otherwise unchanged.
Allowed supporting files: spec/increment/register/ledger/review/HANDOFF/index and new E255 evidence.
Native C0/C3 proof checks durable source first, actual bytes/hash, cross-epoch pins, proof/plan/path/
read-only/restart/fault/drain boundaries. Full owning-bank assertion-only producer kills and exact
restoration required. Real UDS/tool/PTY witnesses remain planned at final SLICE6; no early rollout.

### E255 implementation checkpoint

E255 implements actual immutable READ retention, principal/namespace/token/exact-ref authorization,
rooted read_file and release_reader in the SAME WorkspaceAuthority. Protected view.json uses the
existing exact schema; durable no-clobber install/fsync/reread precedes acknowledgement. Retained
revision/source descriptors, manifest identity, full-file SHA and actual admitted PlanRef rechecks
prevent canonical fallback or stale private input. Reuses E245 RootedViewIO with read-only access;
required trusted formal policy and explicit approved profile are private DI, not wire/model fields.
READ pins do not compare the newest writer epoch; valid READ retention no longer blocks unused
writer release. Read/release/shutdown share the original-deadline coarse authority lock THROUGH IO,
not a global journal lock. This is reader lifetime serialization, NOT execution admission/drain.
Revocation does not depend on a still-valid plan. Post-revocation uncertainty fences the owner;
successful release closes descriptors/discards heavy entry maps idempotently after readers drain,
retains on-disk references/data, and cannot close reused FD numbers at shutdown. No pin GC/token
reconstruction/new service/dependency or cell permission. Source src/fa/execution/workspace.py:
pin_reader:949, _retain_reader:1032, _reader:1088,
_reader_io:1126, read_file:1167, release_reader:1186.
52 new C0/C3 native cases; combined146PASS3.71s. ALL old test files unchanged. Native UID1001 vs
sample1000 originally masked the read-only mutant with fchown EPERM; corrected only the NEW
counterfactual fixture to permit creation absent readonly. Rejected51-case run retained without
credit. Native three-release FD leak reproduced BEFORE repair by assertion28!=22; controlled
old-source proof stop retained without credit. Actual release-close and reused-FD regression added.
Final whole17-module879PASS48.16s → sixteen whole879-bank assertion-only kills
46/1/2/1/5/3/2/1/27/1/2/1/1/2/1/1 → restored879PASS43.48s; collection/setup/teardown clean, no runtime,
warning, skip or infrastructure credit. All601 source/input hashes restored exactly. Ruff/format30
PASS, Mypy30/184PASS; configured Pyrefly0errors, existing141suppressed/50warnings. Broader30-module
1399PASS63.44s. Producer call replacements use explicit closed counterfactuals, not None-deref
runtime failures; exact scripts/outputs/ordered IDs/source snapshots and diagnostics archived.
Evidence `notes/evidence/i03-e255/readers.json.gz`, 2157199bytes SHA2565f0d802f4665b135aedab84b8cbd6bc1638f618b7eef1eb1f95280c20d363acf.
Pins/read ownership is component proof, NOT writable create_view/materialization, actual execution
admit/close-admission/drain, CellBackend episodes/restart/terminality, service/factory or caller/mount
cutover. Those are NEXT. SLICE1 NOT shipped; all35STEPS/four final duties remain open. Q75–77
unchanged. Inventory17 production surfaces/eight joins; all live UNEXECUTED, final-SLICE6 only.

### E256 pre-code — verified remaining SLICE1 and working PROJECT view dependency

Source inspection at9fe2a6c: supervisor.py has dispatcher/reply cache, no build_supervisor/main;
backend.py absent; WorkspaceAuthority has no create_view/write_file/admit/close-admission/drain.
DockerCells and WorkerClient are implemented components, not episode/terminality owners. Retain
E255 pins; do not call them unimplemented or equate their coarse IO lock with execution admission.
SLICE1 STEP1 composition, STEP2 backend, STEP3 real factory/caller/mount cutover and STEP4 full-path
host acceptance remain unchecked. Dependency-ready next: CT102/103 PROJECT working-view ownership.
Allowed code workspace.py + NEW tests/test_execution_views.py; supporting existing spec/increment/
ledger/register/review/HANDOFF/index + new E256 evidence. No new production module or service.
Implement create_view for the concrete WRITE/PROJECT construction path; do not expose dispatcher
handlers or pretend provisioning/candidate/verification views or execution permits exist. Trusted
formal policy/actual PlanRef and explicit approved profile remain private required inputs. Owner
proof authorizes creation, distinct view proof authorizes IO. Copy the validated current revision
using existing bounded no-follow _Capture; only new copied files/directories get approved profile
UID/GID and logical0777 modes (scratch/new source root0755). Canonical bytes/index/modes unchanged.
Use private stage then fsync/no-clobber rename/exact view.json reread before acknowledgement; no
secret-bearing metadata. Retain source/view FDs and exact namespace/principal/epoch/ref/context;
read/write reuse E245 on the SAME materialized tree. Independent pins still use immutable revision.
Recheck actual source/view/registration/plan identities under original-deadline IO lock. This is
file-handler ownership, not command admission. Installation/post-write durability ambiguity fences
owner; no rollback of installed data, cell terminality claim, view GC or unused-writer release.
Binary DoD: native exact dirty/binary/link/mode/UID/tree/index observations; cross-proof denials,
read-your-writes and simulated external private-tree edit visibility; old reader unchanged; stale
SHA/protected/plan/root substitution/restart/fsync/deadline/cleanup negatives. C0/C3 only. Full owning
bank baseline/assertion-only producer kills/restoration plus statics/broader required. Full tool/PTY,
backend/factory/kernel C1/C2 and final-SLICE6 live evidence stay open. No new policy/routing mode.

### E256 implementation checkpoint

E256 source-verified remaining SLICE1 before editing: actual CellBackend/admit and factory/main
are absent, not hidden behind completed component proof. Retain E255 readers; implement next actual
CT102/103 dependency inside SAME WorkspaceAuthority: create_view for WRITE/PROJECT, bounded dirty
input materialization, durable secret-free view retention and distinct principal/namespace/exact-ref
view proof. Existing copier and RootedViewIO reused, no new service/module/dependency or clean Git
checkout. Current retained input verified; canonical/root conflict denies. Newly copied source has
logical0777 modes and explicit approved profile UID/GID; scratch0755, no protected Git/env/control
copy. Native C0 uses actual service UID/GID to reach real operations, NOT deployed different-UID
ownership or mount evidence. Install uses private stage/fsync/no-clobber/exact reread before grant.
write_file/_write_rooted and read_file use SAME working tree; independent READ pins keep old bytes.
Actual PlanRef is bound/rechecked; closed/stale/forged/substituted views deny before IO. Post-write
identity/deadline/context-close/fsync ambiguity fences owner and retains effects, no clean success.
File handlers hold original-deadline lock through IO; this is NOT command admission/drain.
Source src/fa/execution/workspace.py:create_view:1259, _materialize_input:1366,
_install_project:1409, _project_view:1431, _project_io:1484,
write_file:1538, _write_rooted:1556.
46 new C0/C3 native cases;192focusedPASS4.71s. ALL old test files unchanged. Native stage-context
exit fault after install reproduced transient FD leak24!=23 before repair. ExitStack now owns
transient descriptors across that boundary and transfers only after view registration; native
negative proof/cleanup producer retained. No source acceptance before repair. Directory-swap fixture
preserves exact valid metadata AND original source identity to avoid masked deletion. Rooted-write
counterfactual returns closed typed hash/size data; byte/existence oracles run BEFORE consumers.
Final whole18-module925PASS49.62s → nineteen whole925-bank assertion-only kills
30/34/4/1/1/2/3/1/1/1/1/1/2/14/1/1/1/1/1 → restored925PASS46.28s. Clean collection/setup/teardown; no warning/skip/
runtime/infra credit. All602 frozen source/input hashes restored. Ruff/format31PASS, Mypy31/184PASS;
configured Pyrefly0errors with existing141suppressed/50warnings. Broader31-module1445PASS60.60s.
Evidence `notes/evidence/i03-e256/project-views.json.gz`, 2153879bytes SHA256df5a5f4697dc31422f52bff943e420ebfc5a29307b73900f20498160277d7518; exact source/scripts/
ordered outcomes/pre-fix diagnostics and pre-edit SLICE1 inventory retained. Prior E255 unchanged.
NEXT actual per-workspace execution admission/close/drain with approved profile/path triple, then
CellBackend episode/per-command/cancel/restart/independent terminality and actual factory/caller/
mount cutover. Candidate/verification/provisioning view owners, seal/publication remain unimplemented.
No generic purpose switch, dispatcher activation, temporary permit, GC or release/terminality claim.
All35STEPS/four final duties remain open; SLICE1 NOT shipped. All17surfaces/eight joins live PLANNED/
UNEXECUTED at final SLICE6; no early host prerequisite or new policy/routing mode.

### E257 — source assessment and explicit construction order (before code)

At b862632 no complete I03 slice/product execution cutover is shipped. E232–256 are local
component implementations, not 1–2 completed whole contracts per checkpoint. SLICE1 presentation
hid dependencies: authority is SLICE2; factory requires SLICE3; activation joins SLICE4. Do not
report repetitive pending steps as if component checkpoints shipped SLICE1. Actual ordering
(plan-review corrected 2026-10-18; supersedes the earlier compressed tail):
1. Admission/irreversible close/drain + trusted profile/source/scratch/cache (E257 shipped).
2. CellBackend episodes, per-command begin/one-send/cancel/restart/independent terminality
   (E258 shipped).
3. SLICE2 STEP2: the four non-PROJECT view purposes (CANDIDATE/VERIFICATION/MUTATION/
   PROVISIONING) and execution-admitted read/write/edit on retained descriptors.
4. SLICE2 STEP3: managed provisioner injection into SessionManager + provisioning RunContext
   reservation + explicit-registered-reference session ownership (CT103a). Host Git
   provisioning is removed at injection; the publication-dependent provisioning leg
   completes with item 5.
5. SLICE2 STEP4–5 + SLICE3: tool builders + terminal seal/fenced publication/forward
   recovery (publication completes STEP3's provisioning leg and STEP4's seal/import alias
   tests).
6. SLICE4: real factory + atomic caller/mount/registry activation cutover; no
   permissive/failing stub. The provisioner is NOT reimplemented here (route-only).
7. Local full-path C1/C2 and declared producer proofs; final live acceptance at SLICE6.
No completion checkbox is changed by this clarification. All six slices/four final duties open.

Allowed code workspace.py + NEW tests/test_execution_admission.py; existing spec/increment/ledger/
register/review/HANDOFF/index + E257 evidence. Reuse one authority/journal/profile/copier, no new
production module/service/schema/history. Approved dependency-cache path is private operator DI,
never a wire/model path; absent config blocks execution admission, not file IO. READ execution
gets its own bounded materialized readonly source/private scratch, not service0600 R0 mounts.
Admission validates exact actual proof/profile/PlanRef/identities and original EXECUTING uncancelled
journal binding before granting bounded dispatch work. Register work before effects; recheck at
actual create/start/send boundary through scoped effect guard. Scope ends after dispatch, NOT the
command reply/exit wait; stop must be able to signal a running command. File handlers use SAME
view gate. Close wins => no late effect; admitted effect wins => close/drain waits for that bounded
effect/handler. Gate active counts/conditions use existing authority lock for short transitions,
never hold journal lock waiting on drain. Shared mutex serialization is NOT parallel scheduling.
Persist STOPPING before acknowledging close; repeat close does not reopen. Drain waits with original
deadline, never releases writer, deletes source, asserts terminality or interprets expiry as death.
Persist actual operation retention before execution permission. A reader with execution references
cannot be released as an unused file-only pin. Unknown durability fences owner. Shutdown retains
FD owners until scoped work retires. New cache/projection identities must be rechecked before use.
Binary C0/C3 DoD: native bytes/path triple; exact proof/profile/plan/journal/cancel negatives;
queued close => zero effects; admitted effect => close waits; drain consumes deadline; other view
unaffected; file IO closed by same gate; root shutdown does not close live FDs; faults retain refs/
writer quarantine. Whole owning bank assertion-only producer mutations and exact restoration;
actual backend/tool/PTY C1 and final-SLICE6 host proof remain unimplemented/unexecuted.

### E257 checkpoint — SLICE1/2 admission foundation (no slice completion)

Actual authority-owned dispatch admission, trusted source/scratch/cache inputs, irreversible
close/drain and a read-only journal send guard now exist inside the ONE WorkspaceAuthority. This
advances CT99/CT100/CT101-103 preparation; it does not complete any SLICE step or contract.
CT100 ManagedBashExecutor still lacks a CellBackend, so no command permit reaches a cell.
All 35 STEP checkboxes, 17 FUNCTIONAL contracts and four final duties remain unchecked.

### E258 — CellBackend episode owner, one-send discipline, cancel and restart (before code)

E257 proved the authority side (admit/close/drain/trusted inputs). The remaining SLICE1
STEP2 owner is the live cell lifecycle itself. Source-verified: there is NO backend module,
NO episode map, NO one-send command owner and NO restart reconciliation. docker.py creates,
inspects, attaches and force-stops; worker_client.py exchanges private frames; journal.py
records per-operation claims. Nothing owns "one live cell per view with exactly one RUN
send, cancelled before send, and no second cell after restart".

Allowed production files: NEW src/fa/execution/backend.py; src/fa/execution/worker_client.py
(split write from reply wait, existing semantics preserved); src/fa/execution/journal.py
(read-only unfinished-record listing for reconciliation); src/fa/execution/docker.py
(read-only journal accessor); src/fa/execution/workspace.py (read-only approved-profile
accessor). NEW tests/test_execution_backend.py. Existing plan/increment/ledger/register/
review/HANDOFF/index and E258 evidence. No new service, schema, history, receipt type or
routing mode; the ONE journal and the ONE authority stay.

Allowed test edits beyond the new module: tests/test_execution_attach.py and
tests/test_execution_docker.py gain assertion-only oracles for their own success paths
(an expected transport or daemon refusal becomes a failed ASSERTION about the expected
outcome, never a leaked domain-error type). E258's producer mutations reach the worker
transport and the owned stop, so those two modules must fail BY ASSERTION for the
whole-bank kill to count; their expectations are unchanged, only the failure reporting
is normalized. No existing assertion is deleted or weakened. The session configuration
(pyproject.toml) may additionally filter ONE exact CPython 3.13 platform notice by its own
message, as recorded in the amendments below.

Mechanism:
- CellBackend owns a private live episode map keyed by authenticated principal + NamespaceRef
  + exact ViewRef + approved profile id. An episode holds the ORIGINAL creation request, the
  original container id and the SOLE attach/WorkerClient. Worker PTY session ids stay
  subordinate to the episode, so a different namespace/view can never reuse a shell named
  "main".
- execute() consumes the real WorkspaceAuthority admission. A fresh episode performs the
  existing create_once -> durable CID -> start_once path and attaches once. A later command in
  the SAME episode binds the original container id to its own journal record and reuses the
  sole attach; it never creates or starts a second cell and never rebinds the original labels.
- The single RUN frame write happens inside the journal send guard so a persisted cancel
  linearizes against the WRITE, while the reply wait runs OUTSIDE that lock. A lost or late
  reply is EXECUTION_UNKNOWN, never a resend and never a new operation id.
- cancel() persists cancel intent for the exact command operation id BEFORE any stop, then
  stops the OWNED cell through the original creation binding. Cancel intent is not a
  terminal receipt and asserts no process death.
- reconcile() inspects owned cells for uncertain records by id/name/labels and stops a
  surviving cell; it never creates or starts a second cell and never re-runs a command.
- The backend returns a CommandOutcome, NOT a receipt: worker text is untrusted, exit code is
  the command's, and terminal_barrier is always False here because no independent container
  or cgroup fact is established in this increment.
- One cell per episode identity: concurrent commands on the same view share a single
  per-identity creation lock, so a second cell is never created for a live episode and a
  concurrent create is never a duplicate shell.
- The admission scope stays open for the whole command because the work is still in
  flight, while the journal send guard covers ONLY the RUN frame write. The reply wait
  is outside that lock, so a cancel can be persisted while a command runs.
- A daemon answer that violates the owned-cell contract (a foreign container name or
  foreign labels) is PATH_DENIED, never a successful stop and never a synthetic
  completion.

Failure behaviour: unknown/duplicate operation id, forged principal/namespace/view, wrong
profile, expired budget, closed view, cancelled-before-send and lost reply all fail closed
with existing SupervisorError codes; no replay, no second cell, no synthetic completion.

Binary DoD: native local worker over the real attach transport proves one create/start/attach
per episode, shell state preserved across two commands in one cell with two durable records
binding the SAME original container id, the original labels still naming the original
operation, a foreign namespace/view getting its own cell, a duplicate operation id denied
without a second send, cancel-before-send producing NO RUN frame, cancel during a running
command persisting intent while the command is still running (the journal lock is not held
across the reply wait), a lost reply yielding EXECUTION_UNKNOWN with exactly one RUN frame,
and restart reconciliation stopping a surviving owned cell without creating a second one.
Whole owning-bank assertion-only producer kills and exact restoration; statics and broader
regression required. Negative proof must not rely on runtime/name errors.

C0/C3 only. Actual CellBackend -> supervisor -> tool/PTY composition, receipts, independent
terminality, seal/publication, factory/main and caller/mount cutover stay unimplemented.

#### E258 amendment 1 — the scope retirement path and its killable equivalent

execute() now retires the admission scope ONLY through the `with scope:` block; the
redundant `finally: scope.close()` was removed, so there is exactly one retirement path
and the scope's own context manager is the single owner of the admitted work.

A producer mutation that leaves the scope open cannot be counted as a kill: the
authority's shutdown waits for the gate's admitted work with NO deadline, so a leaked
scope hangs the fixture teardown and a timeout is not a kill. The equivalent contract is
therefore proven by a killable producer instead: the native case
test_drain_waits_for_a_running_command_and_returns_when_it_retires requires the drain to
STAY BLOCKED while a command is still running and to return only once that command has
retired, and its producer mutation (WorkspaceAuthority._wait_drained: `while gate.active:`
-> `while False:`) is killed by that assertion. The native case
test_completed_command_leaves_no_admitted_work_behind still proves that a finished
command leaves no admitted work behind, through the unchanged drain path.

E258 amendment 2 (test-surface normalisation, no expectation changed): a command that runs
off the main thread RECORDS its own outcome and the oracle checks that recorded outcome
(EXECUTION_UNKNOWN or BACKEND_UNAVAILABLE for a stopped owned cell). An unhandled thread
exception is a pytest warning, and a warning is never kill credit, so the recorded
outcome replaces the raised one. The session filters ONE exact CPython 3.13 platform
notice by message (the forkpty-in-a-multi-threaded-process DeprecationWarning) in
pyproject.toml: in production the cell worker forks only on the cell's own main thread,
while the native fixtures run that worker inside the pytest process. No assertion is
added, removed or weakened, and no other warning class is filtered.

E258 amendment 3 (the narrow warning filter is a SESSION filter): the forkpty notice can
surface in any bank module, because a producer that wedges the transport leaves a live
thread while a later native case forks its PTY. The single session level filter in
pyproject.toml therefore replaces the per-module filters, so the rule is uniform and the
proof's no-warning claim stays absolute. The notice stays VISIBLE in the pytest output of
any run that does not use the project configuration, and the production cell worker keeps
its own main-thread-only fork rule.

E258 amendment 4 (kill credit): a kill is a call-phase ASSERTION. A setup failure means the
case never ran and is never kill credit. A teardown failure under a producer that
deliberately wedges the transport is a RECORDED signal and never kill credit: the baseline
and the restored source must tear down completely clean, and every producer kill must come
from at least one call-phase assertion with no other failure class in the call phase. The
transport-wedging producer (the worker that never writes its frame) also trips the native
fixture's own teardown assertion; that is recorded in the evidence, not credited.

E258 amendment 5 (the declared docker.py accessor was not needed): the declaration allowed a
read-only journal accessor in src/fa/execution/docker.py. The existing
DockerEngine.inspect_owned and DockerCells.force_stop_owned paths already carry the
owned-cell proof (the exact container name, the operation and view labels and the recorded
container id), so docker.py is UNCHANGED by E258. The E258 producers reach that existing
path to prove the owned stop, and the authority keeps the one trusted path triple.

### E258 — CellBackend episode owner: local component proof (result)

E258 implements the live cell episode owner in a NEW src/fa/execution/backend.py. A
private episode map is keyed by the authenticated principal, the NamespaceRef, the EXACT
ViewRef and the approved profile id, so a shell name alone is never an identity. One
episode performs create -> durable container id -> start -> sole attach exactly once; a
later command in the same episode binds the ORIGINAL container id to its OWN journal
record and reuses the sole attach, so a second cell is never created for a live episode.
Exactly ONE RUN frame write happens per command, inside the journal send guard, while
the reply wait stays OUTSIDE that lock, so a cancel can be persisted while a command is
still running. cancel() persists the exact-command intent BEFORE the owned stop, and a
daemon answer that violates the owned-cell contract (a foreign container name or foreign
labels) is PATH_DENIED, never a successful stop. reconcile() stops a surviving owned
cell of an uncertain record and never creates, starts or re-runs anything. The backend
returns a CommandOutcome, never a receipt: worker text is untrusted, the exit code is
the command's own, and terminal_barrier is always False here because no independent
container or cgroup fact is established in this increment. 19 new native C0/C3 cases;
focused 7-module owning bank 369 PASS 26.05s. Whole 20-module owning bank 985 PASS 68.20s -> twenty-four whole
985-bank assertion-only kills 1/1/2/3/1/3/2/1/1/1/5/2/1/2/16/26/6/1/40/4/7/6/15/15 ->
restored 985 PASS 67.71s; clean collection and setup, no warning/skip/runtime/infra
credit, every kill by a call-phase ASSERTION. All 605 frozen source/input hashes
restored exactly. Ruff/format/Mypy clean; configured Pyrefly 0 errors with the existing
141 suppressed/50 warnings. Broader 31-module 1505 PASS. Evidence
notes/evidence/i03-e258/episodes.json.gz, 2666870 bytes SHA256
299c301625545cd8f6fd69bb9a7b5bb74859f43c4e1f74f5697e040c54a30e90. NOT shipped: other
view purposes, seal/publication/forward recovery, the real build_supervisor/main with
closed handlers, the atomic SessionManager/tool/caller/mount cutover, receipts and
independent terminality. SLICE1 NOT shipped; all 35 STEP checkboxes, 17 FUNCTIONAL
contracts and four final duties remain open; all 17 production surfaces and eight joins
stay PLANNED/UNEXECUTED at final SLICE6. No early host prerequisite, no new policy, no
new routing mode.

### E259 — the four non-PROJECT view purposes (before code)

IDEA: complete SLICE2 STEP2's view-purpose owners: every declared ViewPurpose becomes a
real authority-constructed view with its exact admission combination, reusing the retained
E256 materialization/install and E257 admitted IO — no new service, no purpose switch, no
generic permissive factory.

CONTRACT/GAP IDS: SLICE2 STEP2 (view purposes + admitted IO per §§4–4.2), CT102's
create_view materialization contract (extended to all purposes), CT103's rooted-IO
obligations applied per purpose, §2 create_view table row (purpose/candidate_scope
combinations), §3.1 (VERIFICATION/MUTATION/CANDIDATE need nonnull plan), §5 (CANDIDATE
buffer-in-staging), §6 (MUTATION derivative; VERIFICATION disposable views). Live ledger:
I03-LIVE-17 (workspace.py) witnesses extended; I03-LIVE-S05 join note extended.

ALLOWED FILES: src/fa/execution/workspace.py (purpose-parameterized create_view, purpose
policy in rooted IO, candidate buffer methods); tests/test_execution_purposes.py (NEW);
plus the mechanical create_view call-shape migration of the shared `create` helper in
tests/test_execution_views.py (adds purpose/access/candidate_scope kwargs; NO assertion
changes; the backend/admission fixtures inherit it via import);
existing plan/increment/ledger/register/review/HANDOFF/index + E259 evidence. No protocol,
types, journal, worker, docker, supervisor or session change; wire validation is already
correct and is NOT reimplemented (the authority REVALIDATES independently).

CURRENT BEHAVIOR: create_view (workspace.py:1389) hard-codes Access.WRITE +
ViewPurpose.PROJECT (:1430–1431), always candidate_scope=None; pin_reader hard-codes
READ/PROJECT (:1128–1129); the wire payload's purpose/access/candidate_scope never reach
the authority. The wire layer ALREADY validates the matrix (protocol.py:314–320) and
_VIEW_RECORD already supports nullable candidate_scope (workspace.py:127).

TARGET BEHAVIOR: create_view(peer, namespace, *, workspace_id, capability, purpose,
access, candidate_scope, plan_ref, formal_evidence, deadline) constructs exactly the pinned
matrix and denies every other combination with INPUT_POLICY BEFORE any staging copy:
- PROJECT (retained): WRITE or READ is NOT re-issued here; create_view stays WRITE/PROJECT
  when purpose=PROJECT with candidate_scope=None; pin_reader stays the READ/PROJECT owner.
- VERIFICATION: access=READ, plan_ref REQUIRED (nonnull), materialized immutable input +
  private scratch, formal evidence bound and rechecked; no write path exists on it.
- MUTATION: access=WRITE, plan_ref REQUIRED; rooted writes confined to the approved
  mutation roots src/ and scripts/ (slice_verification._MUTATION_ROOTS); writes to tests/,
  .fa, .env, .git, the plan path, or any path outside those roots deny PATH_DENIED. The
  "one permitted target" discipline is TWO-LAYER (Q77 construction, no new wire field):
  the authority confines writes to the roots; the controller's mutation edit remains a
  single-file expected_sha write (I02 overlay discipline).
- CANDIDATE: plan_ref REQUIRED and candidate_scope REQUIRED with candidate_scope.plan_ref
  == plan_ref; internal binding = source READ materialization + ONE supervisor-owned
  staging buffer addressed by the exact candidate_path; buffer writes/reads go through new
  authority methods (write_candidate/read_candidate) bound to the view's scope; bytes NEVER
  land in canonical .fa/admission or any cell/control mount (§5). Generic write_file denies
  the candidate_path; that tool-level cutover stays STEP4.
- PROVISIONING: access=WRITE, plan_ref NOT required (may be null); materializes the
  registered current bytes like PROJECT; it is the view in which bootstrap/readiness
  commands run (the provisioning consumer lands in STEP3; this increment owns admission +
  construction only).

MECHANISM: one parameterized construction path reusing _materialize_input/_install_project
under a per-purpose policy object; the ViewRef carries the real purpose/access; the view
record carries candidate_scope for CANDIDATE and the plan_ref as today; execution_trusted
and admit keep routing by access with a purpose recheck added at the effect boundary; the
candidate buffer is a service-owned staged file inside the view's protected directory tree,
written only through the scope-checked authority method.

PRODUCTION BEST PRACTICE: closed-enum dispatch with an exhaustive deny (no default-allow
fallthrough); authority-side revalidation of every wire claim (never trust the codec
alone); reuse the one materialization/install path rather than forking per purpose; keep
the frozen request shape (no new wire fields); make the deny path return the existing
INPUT_POLICY code before any filesystem effect.

FAILURE BEHAVIOR: wrong purpose/access/scope/plan combination -> INPUT_POLICY before any
mkdir/copy; candidate write to a path other than the exact scope path -> PATH_DENIED;
MUTATION write outside src//scripts/ -> PATH_DENIED; VERIFICATION write anywhere ->
PATH_DENIED (no write path); plan_ref substitution after creation -> STALE_REVISION at
effect recheck; staging/install failure -> existing BACKEND_UNAVAILABLE /
DURABILITY_UNKNOWN semantics, never a returned grant; secret/capability never in records.

DoD: native bank proves every allowed combination constructs a real materialized view with
the right record/ref fields, and one denied-combination case per forbidden
purpose/access/scope/plan tuple denies INPUT_POLICY with zero filesystem effect (no
pending staging dir left behind); candidate buffer writes land ONLY in the supervisor
staging buffer and never at the canonical path; MUTATION writes outside the roots deny
PATH_DENIED and inside succeed with expected_sha conflict semantics; VERIFICATION exposes
no write path and binds/rechecks its plan; PROVISIONING accepts null plan and refuses
nothing it should allow. NEGATIVE PROOF: no runtime/name-error kill credit; denied cases
assert the typed error + the absence of effects; producer mutations rerun the whole owning
bank, assertion-only kills, exact restoration.

TESTS-WRITING CLASS: C0/C3 native cases over the real authority + real descriptor IO
(no mocks of the filesystem); kill-check on the PRODUCER call sites (the per-purpose
policy call inside create_view's construction and the write path's purpose recheck);
existence pre-check first (grep the call sites); path inventory = all five purposes ×
access × scope × plan on/off; C4 mutation handoff after C1-equivalent native bank.

PRODUCER KILL-CHECK TARGETS (whole-bank mutations): remove the matrix deny in create_view;
remove VERIFICATION's plan-required check; remove MUTATION's root confinement; remove
CANDIDATE's scope-path equality check; allow PROVISIONING plan_ref to be required wrongly;
make candidate writes fall through to the source tree; drop the authority-side revalidation
(the wire-only trust fallacy); drop the purpose recheck at the effect boundary.

E2E LEDGER ENTRIES: extend I03-LIVE-17's live fixture with the purpose matrix witnesses
(five purposes, denied combinations, candidate staging isolation, mutation root
confinement); extend I03-LIVE-S05 with "purpose-correct views" wording; add the E259
checkpoint section at close; surface count unchanged (workspace.py already tracked).

C0/C3 only. Candidate tool cutover (STEP4), the provisioning consumer (STEP3), seal/export
of mutation/candidate outputs (SLICE3) and live proof stay open.

### E259 — the four non-PROJECT view purposes: local component proof (result)

E259 completes SLICE2 STEP2's view-purpose owners in src/fa/execution/workspace.py. create_view
now takes the closed matrix (purpose, access, candidate_scope, plan_ref) and constructs exactly:
VERIFICATION (READ, plan required) and CANDIDATE (READ, plan + exact scope) as immutable reader
views reusing the one reader-registration path; MUTATION (WRITE, plan required) and PROVISIONING
(WRITE, plan optional) as project views reusing the E256 materialization. Every other
combination denies INPUT_POLICY before any filesystem effect, revalidated at the authority
independent of the codec. The purpose write gate at the effect boundary confines MUTATION
writes to the approved src//scripts roots and gives VERIFICATION/CANDIDATE no generic write
path; the scoped candidate buffer is ONE supervisor-owned staged file written only through
write_candidate/read_candidate with exact scope-path equality and expected-absence/exact-SHA
semantics, never canonical .fa/admission. pin_reader stays the READ/PROJECT owner unchanged.
10 new native C0/C3 cases; focused 4-module bank 202 PASS 5.1s. Whole 21-module owning bank
995 PASS 65.6s -> eleven whole-bank assertion-only kills
1/1/2/7/1/2/3/1/2/1/1 -> restored 995 PASS 64.9s; clean collection/setup/teardown,
no warning/skip/runtime/infra credit, every kill a call-phase builtins.AssertionError. Source
restored byte-exact. Ruff/format 35 files clean; Mypy 35+185 files clean; Pyrefly 0 errors with
the existing 141 suppressed/50 warnings; broader 1515 PASS. Evidence
notes/evidence/i03-e259/purposes.json.gz, 1343665 bytes SHA256 e689ea3b92258128c1ab20a2d4e7ed312e63bf7b81bdce53f4a52c4081e1b9bd.
Honest notes: one candidate producer (a second path-traversal parser in the matrix) was found
MASKED by the record-layer path rules (protocol._byte_limits) and DELETED as redundant rather
than counted — the single enforcement point stays the record check. A first runner attempt
aborted on a frozen-hash comparison poisoned by the git tracking pointer moving mid-run (an
environmental artifact); restoration was then verified byte-exact against start-of-run bytes.
NOT shipped: the candidate tool cutover (STEP4), the provisioning consumer (STEP3), seal/export
of mutation/candidate outputs (SLICE3), receipts/independent terminality and live proof. SLICE1
NOT shipped; all 35 STEP checkboxes, 17 FUNCTIONAL contracts and four final duties remain open;
all live verdicts stay PLANNED/UNEXECUTED at final SLICE6. No new policy or routing mode.

## E260 — plan and E2E audit after lifecycle review (2026-10-22)

**Audit result:** the 2026-10-21 review's R1–R5 behaviors have local component implementations/tests,
but do not establish service/host proof. E261 separately records a source-only one-shot CANCEL path
not exercised by the sequential lifecycle tests. E258's planned "one episode" wording did not
explicitly separate persistent interactive reuse from per-operation noninteractive one-shot cells,
and its live witnesses did not name the cross-view cancel, create/start/attach gate race, DONE-owned-cell
restart or absolute lock-deadline cases individually.
Spec §2.2 and the SLICE1/SLICE2 exits now state those contracts; the single existing live register is
extended below. No new protocol, authority, lock service, production module or acceptance status is
introduced.

| Finding / open gap | Normative plan owner and direct remedy step | Future live witness (not run; remains PLANNED/UNEXECUTED) |
|---|---|---|
| R1 — noninteractive EXEC lifecycle | Spec §§2.1–2.2, CT100, SLICE1 STEP2: only interactive profiles reuse a view episode; each distinct noninteractive operation uses null session + fresh one-shot cell/attach + one RUN; same-op replay never launches again. CANCEL during a live one-shot must resolve/stop that exact operation CID without relying on the interactive map. | I03-LIVE-11/18 and S03/S04: two sequential noninteractive ops use distinct CIDs, verify null-session result/exit/timeout/no replay, and issue a concurrent same-view CANCEL against a running one-shot; keep interactive two-command state reuse separate. |
| R2 — `admit()` is not a side-effect guard | Spec §2.2, SLICE2 STEP1/STEP5: `WorkAdmission.effect()` wraps actual Docker create/start/attach; `send()` guards the RUN frame. Paired schedule proves close-wins→zero effects and effect-wins→close/drain waits. | I03-LIVE-18 and S02/S04: actual installed service/daemon barrier schedule; assert zero create/start/attach/RUN when close wins, no late RUN after attach, and bounded drain when the effect wins. |
| R3 — cross-view CANCEL | Spec §2.2, SLICE1 STEP2: compare namespace and exact `ViewRef` with the EXEC journal record in the same transaction that persists cancel; same-namespace operation from another view returns `UNAUTHORIZED` before stop. | I03-LIVE-18 and S04: two real views in one namespace; wrong-view operation ID leaves both journal records and daemon request log unchanged. |
| R4 — DONE record can still own a cell | Spec §2.2, SLICE1 STEP2: enumerate every EXEC record with a durable CID (separate from `unfinished()`), including DONE; stop/inspect only original CID/name/labels and do not rewrite the completed result or create/start/attach/RUN. CT104 cgroup barrier remains independent. | I03-LIVE-07/18 and S03/S04: mark interactive creator DONE while its cell remains live; restart supervisor/backend; inspect/stop that CID only, preserve DONE result and withhold terminality until the independent barrier. |
| R5 — request deadline across locks and effects | Spec §2.2, SLICE1 STEP2: pass the original monotonic deadline through authority/registry/episode locks, every request journal transaction, Docker/attach/RUN; pre-body/pre-effect expiry is `BACKEND_UNAVAILABLE`, possible post-write/effect uncertainty remains uncertain; no reset or late follow-up. | I03-LIVE-06/18 and S02/S03: force journal-flock and episode-lock contention plus late Docker/attach; verify expiry/no effect and truthful uncertainty after a possible write. |
| Q66 — parent context to actual planner input | Existing CT109, SLICE5 STEP4/STEP5 and SLICE6 DoD already directly require an internal bounded snapshot only in the initial planner request, credential redaction and distilled retry separation; no public `context` field. | S08: parent-only sentinel present in first real planner request and absent from retries; credential sentinel absent; direct+nested workflow runs with actual provider requests. |
| Service/factory/caller/mount cutover | Existing CT99, SLICE1 STEP3 and SLICE4 STEP2: compose real `build_supervisor/main` with the one authority/backend/journal; remove controller source-prepending/import shadow and direct host fallbacks; activate caller/mount changes atomically; no unrestricted Docker socket in model-facing controller. | I03-LIVE-01/06/07 and S01/S02/S07: actual installed launch, private UDS supervisor, startup recovery, real tool/PTY/provisioner/verifier routes and denied-backend/no-host-effect oracles. |
| Sealing, publication, recovery and descendant terminality | Existing CT104–CT107, SLICE3 STEP1–STEP5: close admission, drain handlers, stop cells, prove cgroup empty, then seal immutable bytes; recover forward or quarantine. | S04/S06 and `tests/integration/test_publication_recovery.py` under `FA_REQUIRE_EXECUTION_HOST=1`: fork/double-fork/setsid/background writers, held file handler, every irreversible crash/fsync boundary; no seal/publish while writable. |
| Ubuntu/Docker/image and release-environment proof | Existing CT100a, SLICE1 STEP4 and SLICE6 STEP7/9/10: actual approved host/image/profile/mount/daemon/cgroup evidence, complete non-skipped execution inventory and E223 review; specific wheel/zlib, ShellCheck, Go/Gitleaks hook prerequisites are now explicit in STEP10 above. | I03-LIVE-02/05/13/16, all cross-module joins and SLICE6: actual installed wheel/image, approved daemon and host facts; full `just test`/`just check` + readiness acceptance, no setup errors or required-case skips; retain the documented Q19 xfail with its separate disposition; no bypass. |
| Broad independent review and release signoff | CT89, SLICE6 STEP7/10 and the binary DoD: named independent reviewer, pre-fixture manual checklist repeated after material changes, source/image/config/run-bound evidence, all four E223 duties, and explicit operator signoff after required E2E; no harness-generated approval | E223 final acceptance package; S01–S08 artifacts feed review but never self-approve |

All 35 STEP boxes, all FUNCTIONAL contracts and the four transferred E223 duties stay open. The
component regressions and local result remain evidence only; every live witness above is future work
after the service/caller composition exists and at final SLICE6. This audit does not run E2E, authorize
production deployment, or change I02's local/pending-E2E status, Q59–Q66 dispositions, E19, Q53(c),
or the append-only ledger policy.

## E261 — one-shot CANCEL ownership seam found in plan audit (2026-10-22)

Source review during E260 found one additional I03 seam that the R1–R5 passing tests do not cover:
`CellBackend.execute()` creates a noninteractive `_Episode` for the duration of the call but does not
put it in the persistent interactive `_episodes` map; `CellBackend.cancel()` currently resolves its
cell only through that map. Thus the local sequential one-shot tests do not demonstrate that CANCEL
can stop an in-flight one-shot operation. This is a source-path gap, not a newly executed regression;
do not claim one-shot cancellation is implemented or validated.

Direct remedy, with no new service or registry: SLICE1 STEP2 must persist exact-view cancellation in
the existing journal, resolve the running EXEC record's durable CID and original labels, then use the
existing owned-cell Docker stop/observation path. Keep the identity bound to operation + namespace +
exact `ViewRef` + approved profile. A missing/mismatched record denies before Docker effects; no
replacement create/start/RUN, no re-execution and no terminal claim from the stop ACK. Preserve the
interactive episode path. Add a native regression in `tests/test_execution_backend.py` for a running
one-shot command cancelled from its own view and a same-namespace wrong-view cancellation with zero
journal/daemon mutation. The host seam is I03-LIVE-18/S04 and remains PLANNED/UNEXECUTED.

**Status:** open until the owner path and regression are implemented and reviewed in I03; final real
daemon/cgroup proof remains at SLICE6. This audit does not edit product source or claim release
readiness.

### E262 — one-shot CANCEL ownership: declaration before code

**Idea.** Close the seam E261 recorded: a CANCEL issued while a *noninteractive one-shot* EXEC is
running must stop that operation's own journal-bound cell. Today it cannot, because the only
cancel path resolves the cell through the interactive episode map.

**Contract/gap IDs.** I03 SLICE1 STEP2 (exit clause "live one-shot cancel by exact journal-bound
CID"), CT100, CT103a lineage; spec §2.2 (cancel must match namespace + exact `ViewRef` in the same
journal transaction, applies to in-flight one-shot, never create a replacement) and the §E262
implementation note; E261 GAP record in the ledger and the I03-LIVE-18 / S04 witness.

**Allowed files.** `src/fa/execution/docker.py` (one new method on the existing `DockerCells`),
`src/fa/execution/backend.py` (`CellBackend.cancel` branch), `src/fa/execution/journal.py`
(`request_cancel` return value only — no new validation, no schema change),
`tests/test_execution_backend.py`
(new C0/C3 cases + docstring path inventory), plan docs/ledger/E2E register. No new module, no
second registry, no protocol/schema change, no supervisor or service composition, no admission
change for cancel.

**Current behaviour (source-verified).** `CellBackend.cancel` builds an `_EpisodeKey` and reads
`self._episodes`; only the interactive branch of `_live_episode` inserts there (backend.py:281), so
for a noninteractive profile the lookup returns `None` and cancel raises `EXECUTION_UNKNOWN` before
persisting anything — even while the one-shot cell is running. `DockerCells` already owns two
owned-stop entry points (`force_stop_created`, and the engine-level `force_stop_owned`) and
`OperationJournal.request_cancel` already enforces the exact-`ViewRef` match.

**Target behaviour.** Noninteractive cancel resolves the EXEC record by `operation_id` under the
original namespace, verifies `op == exec` and exact `ViewRef`, persists cancel intent, and stops the
record's own durable CID through the existing `force_stop_owned` path (which re-validates
name/labels/image/CID before one fixed SIGKILL and independently re-inspects the same CID). If the
record has no CID yet, the intent alone is durable and the operation is refused a later
create/start; the caller receives a distinct `not_created` observation. Interactive cancel is
unchanged. Return values remain observations, never receipts or terminality.

**Mechanism.** `OperationJournal.request_cancel` returns the record it durably wrote inside its own
transaction (identity, exact view, intent and read of the CID are then one decision point — an extra
`lookup` before it would both duplicate the checks and open a create-then-cancel race). New
`DockerCells.force_stop_operation(*, operation_id, namespace, view, profile, deadline) ->
ContainerObservation | None`: type checks, `journal.request_cancel(...)` (sole authority for
unknown/other-op/foreign-view refusal and for durable intent), then `engine.force_stop_owned(...)`
with `record["container_id"]`, or `None` when it is absent. `CellBackend.cancel` branches once on
`profile.interactive`: the existing episode path, or `force_stop_operation` mapped through the same
error surface (`JournalError → SupervisorError(code)`, `ExecutionContractError → PATH_DENIED`,
`DockerUnavailableError → PATH_DENIED` when no status else `BACKEND_UNAVAILABLE`, `TimeoutError →
BACKEND_UNAVAILABLE`).

**Production best practice.** Reuse the existing journal as the single source of durable truth
instead of adding in-memory state; make identity checks precede effects; keep one stop
implementation (`force_stop_owned`) for every path; express "nothing to stop yet" as data, not as an
exception or a false success; keep the deadline and the error surface uniform across paths.

**Failure behaviour.** Unknown/foreign/other-op id → `EXECUTION_UNKNOWN`; foreign view → 
`UNAUTHORIZED` with no journal write and no daemon request; journal or Docker unavailability →
`BACKEND_UNAVAILABLE`; malformed/foreign observation → `PATH_DENIED`; expired deadline →
`BACKEND_UNAVAILABLE` with no late effect. A stopped cell makes the concurrent command end in
`EXECUTION_UNKNOWN`/`BACKEND_UNAVAILABLE`, never success.

**DoD.** Same-view cancel of a running one-shot: intent durable, one SIGKILL to the exact CID, the
concurrent command ends in a legal closed outcome, exactly one RUN frame, no second create/start/
attach. Cross-view cancel: `UNAUTHORIZED`, `cancel_requested` still false, no daemon request at all.
Unknown operation: `EXECUTION_UNKNOWN`, no daemon request. Cancel before creation: intent durable,
`not_created`, the later execute refuses to create/start and sends zero frames. A fresh
`CellBackend` over the same journal (no episode map) still stops the live one-shot cell.
**Negative proof:** deleting the new branch, the exact-view check, the intent write, or the
CID-based stop each fails a named test.

**Tests-writing class.** C0/C3 (this module's proven level: real authority/journal, literal HTTP
Docker peer, real PTY worker; no container/cgroup/terminality claim). Classes and path inventory are
recorded in the test module docstring.

**Producer kill-check targets (declared, 4 new + 1 reused).** (1) the noninteractive branch in
`CellBackend.cancel`; (2) the exact-`ViewRef` comparison in `journal.request_cancel` — **reused**
pre-existing producer, already killed by journal tests, so not claimed as new evidence; (3) the
durable `request_cancel` intent (mutant: read-only `lookup` instead); (4) the
`record["container_id"]` argument to `force_stop_owned`; (5) the `None`/`not_created` handling for a
record without a CID.

**E2E ledger.** Existing I03-LIVE-18 / S04 witnesses already name the required live case; the
register's open-gap paragraph is updated to "implemented locally, live still PLANNED". Surface
count unchanged (18/8). No STEP checkbox, FUNCTIONAL contract or E223 duty is closed by this
component work.

#### E262 result — implementation, evidence and one design correction

**Shipped.** `journal.request_cancel` now returns the record it wrote (behaviour otherwise identical);
`DockerCells.force_stop_operation` in front of `attach_created`; `CellBackend.cancel` branches once on
`profile.interactive` into `_cancel_operation`. Four new producers, one reused.

**Correction found by mutation testing (recorded, not hidden).** The first implementation looked up the
record, then checked op and view, then called `request_cancel`, then read the CID from the *earlier*
lookup. Mutation exposed both defects: deleting the local checks did not fail anything (they were
duplicates of checks inside `request_cancel` — a masked producer, the E259 pattern), and reading the
CID outside the intent transaction leaves a create-then-cancel window in which a freshly created cell
would be recorded as cancelled but never stopped. Both were fixed by having `request_cancel` return the
record it wrote, so identity, intent and CID belong to one journal transaction. The declared kill (2)
is therefore attributed to the journal, and the `request_cancel` mutation was changed from "delete the
call" to "replace with a read-only lookup", which is the mutation that exists in the final design.

**Red→green.** Before the implementation, the red run was 4 failed / 2 passed with the failure at the
cancel call (`SupervisorError`). After: `pytest tests/test_execution_backend.py -q` → 30 passed in
19.35s; the seven-module execution bank (`backend docker journal dispatch attach client cell_worker`)
→ **462 passed in 36.62s**.

**Static checks (actual output).** `ruff check src tests` → `All checks passed!`; `ruff format --check
src tests` → `498 files already formatted`; `mypy src/fa/execution` → `Success: no issues found in 16
source files`; `pyrefly check src/fa/execution` → `0 errors`.

**Targeted mutation run (assertion-only credit; source SHA256-restored after each mutant and the bank
re-run green).** 5/5 kills:

| Mutant | File | Killed by |
| --- | --- | --- |
| noninteractive branch deleted | `backend.py` | G2, G5, G6 (and G3, since the episode path is taken) |
| exact-`ViewRef` check deleted | `journal.py` | G3 + 2 journal cancel tests (**reused**) |
| `request_cancel` → read-only `lookup` | `docker.py` | G2, G3, G4, G5 |
| `record["container_id"]` → `None` | `docker.py` | G2, G6 |
| `not_created` → `exited` | `backend.py` | G5 |

**Scope unchanged.** No STEP checkbox, FUNCTIONAL contract, or E223 duty is closed. I03-LIVE-18 / S04
remain PLANNED/UNEXECUTED; surface count 18/8.

### E263 — SLICE2 STEP3 (SLICE2 half): managed provisioner injection into SessionManager

**Idea.** `SessionManager` is still the host-Git owner of workspaces: `_new_session` materializes a
directory with `provision_git_workspace`/`copytree`, and the supervisor never learns that the workspace
exists. STEP3 reverses that ownership inside the existing manager: the supervisor becomes the only
creator/registrar of canonical workspace bytes, the manager keeps its manifest/DB/run duties, and the
provisioner receives a real provisioning run identity before it acts. This increment implements the
SLICE2 half only (component injection + contract); the publication-dependent new-root leg is SLICE3's
join and the remaining inventory callers are routed at SLICE4 STEP2 (the same provisioner, never a
second one).

**Contract/gap IDs.** I03 SLICE2 STEP3 (SLICE2 half) exit clauses; CT103a; CT100 lineage; spec §4.1
("Registration and SessionManager cutover") and the §"SessionManager ordering/recovery" note; increment
line 308 (STEP3 declaration) and 297 (CT103a); I03-LIVE rows that consume the provisioning route.

**Allowed files.** New `src/fa/session/provisioning.py` (request/result values + provisioner callable
type; no execution imports, so the session layer stays execution-agnostic), new
`src/fa/execution/provisioning.py` (the adapter that turns `WorkspaceAuthority.register_existing` into
the frozen result), `src/fa/session/manager.py` (injection point, provisioning run reservation,
not-READY enforcement, cleanup ownership, reverse-owner confirmation),
`src/fa/execution/workspace.py` (`register_existing` returns `tree_sha256` as well — no new validation,
no behaviour change), `tests/test_session_lifecycle.py`, new `tests/test_execution_provisioning.py`,
plan/ledger/E2E register. No second provisioner, no new session manager, no manifest schema change, no
CLI/composition change (SLICE4 owns that), no publication code.

**Current behaviour (source-verified).** `SessionManager.__init__` accepts only
`workspace_preparer`; `_new_session` writes a `provisioning` manifest, calls `_provision_workspace`
(host Git clone when `source_workspace` has `.git`, else `copytree`), creates `SessionDatabase`, calls
`workspace_preparer(workspace_path)` and *ignores its `ReadyState`*, then writes `active`.
`_attach_session` likewise ignores a not-READY result. `_check_reverse_workspace_ownership` rejects any
workspace path equal to another session's manifest path. Nothing in the manager knows a run identity
before the CLI's later `begin_run`, so a supervisor-side provisioner would have to invent one.
`WorkspaceAuthority.register_existing` already registers quiescent existing bytes idempotently (returns
the existing ids and re-verifies unchanged bytes when already registered) and returns only
`{workspace_id, revision_id}`.

**Target behaviour.** With a provisioner injected: the manager never clones, copies or chmods canonical
bytes; it creates the manifest (`provisioning`) and session DB, reserves one real provisioning
`RunContext` through the existing `begin_run(session, None)`, passes that namespace plus the session and
workspace root to the provisioner, enforces readiness, and only then writes `active`. A provisioner
result is exactly `{registered, workspace_id, revision_id, tree_sha256}`: `registered=True` means the
supervisor committed and verified those bytes and the manager must never delete them; `registered=False`
means provisioner-created scratch that only the manager may clean up. A new workspace whose bytes do not
exist becomes the typed BLOCKED disposition `provisioning_unavailable` (no host-Git fallback) until
SLICE3 joins publication. A not-READY `ReadyState` is `workspace_not_ready` in both `_new_session` and
`_attach_session`. An explicit reference to another session's registered workspace is permitted
(CT103a: reference, not ownership transfer — the other session keeps its DB/run bindings and manifest),
while an unregistered conflict stays `workspace_already_owned`. Without a provisioner the manager keeps
today's exact behaviour, because SLICE4 STEP2 performs the actual cutover.

**Mechanism.** `fa/session/provisioning.py`: frozen `ProvisionRequest{mode, session_id, run_id,
workspace_path, deadline}` with `ProvisionMode{REUSE, PROVISION}`, frozen
`ProvisionedWorkspace{registered, workspace_id, revision_id, tree_sha256}` whose `__post_init__` rejects
partial results, and `WorkspaceProvisioner = Callable[[ProvisionRequest], ProvisionedWorkspace]`.
`fa/execution/provisioning.py`: `ManagedProvisioner(authority, *, peer, root_id, relative_root)` — REUSE
maps to `register_existing(...)` built from the request's `NamespaceRef`, returns the frozen result with
`registered=True`; PROVISION raises `SessionManagerError("provisioning_unavailable")` before any effect;
`SupervisorError` maps to explicit session codes (`CORRUPT_STATE → workspace_corrupt`,
`UNAUTHORIZED/EXECUTION_UNKNOWN → workspace_denied`, everything else → `workspace_provision_failed`).
Manager: `__init__(workspace_provisioner=...)`; in `_new_session` the reserved run id comes from
`begin_run` on a provisional `SessionContext` under the `provisioning` manifest; the provisioner is
called after DB creation and *before* the readiness gate (so readiness runs against registered bytes,
matching SLICE4 where it executes inside provisioning cells), asking for `PROVISION` when the manager
would have had to create the root and `REUSE` for a named existing directory; its result drives a
three-state cleanup (`None` = never ran,
`False` = scratch, `True` = registered) where only `None`-with-`workspace_created` and `False` are
rmtree-eligible. The reverse-owner scan returns conflicting owners instead of raising when a provisioner
is injected, and the conflict is confirmed after the result is known.

**Production best practice.** Keep one owner per responsibility (manager: identity/DB/run; supervisor:
canonical bytes), express ownership as data in a frozen result rather than as side-channel flags, make
the ordering observable through the injected callable, fail closed with typed dispositions instead of
host fallbacks, and never delete bytes whose registration the manager cannot disprove.

**Failure behaviour.** Provisioner exception → no active session, no workspace deletion unless the
result was `registered is False`; `provisioning_unavailable` for a new root; `workspace_not_ready` for a
degraded/failed readiness result in both paths, with `last_used_at` untouched on attach; conflict without
registration → `workspace_already_owned`; corrupt/unavailable authority → typed session error, no
partial result; run reservations survive rollback, so an issued run id never becomes reusable.

**DoD.** Injection ordering proven (the provisioner observes the workspace absent, creates it itself, and
no source bytes are copied); the request carries an existing session DB binding and run directory;
registered bytes survive a later readiness failure while the session dir is removed; a registered
conflicting workspace can be referenced by a second session with the first session's manifest/DB/run
bindings byte-identical; an unregistered conflict is rejected with no session dir; new-root provisioning
is a typed BLOCKED disposition; not-READY blocks new *and* attach; corrupt-manifest and legacy run-ID
tests still pass. **Negative proof:** deleting the injection call, the run reservation, either readiness
check, the registered-cleanup guard, or either half of the conflict confirmation each fails a named test.

**Tests-writing class.** C1 for the manager (real filesystem, real `SessionDatabase`, injected
provisioner boundary double) and C0/C1 for the adapter (real `WorkspaceAuthority` over a temporary
approved root). No container, no cgroup, no live deployment claim.

**Producer kill-check targets (declared, 8).** (1) the provisioner invocation in `_new_session`;
(2) the provisioning `begin_run` reservation (its namespace must exist before the call);
(3) not-READY enforcement in `_new_session`; (4) not-READY enforcement in `_attach_session`;
(5) the registered-aware cleanup guard; (6) the "permit registered reference" branch; (7) the
"reject unregistered conflict" branch; (8) the typed `provisioning_unavailable` disposition in
`ManagedProvisioner`.

**E2E ledger.** No surface count change (18/8); live rows stay PLANNED/UNEXECUTED. No STEP checkbox,
FUNCTIONAL contract or E223 duty is closed by a component increment.

#### E263 result — SLICE2 half shipped, with the Q78 readiness boundary

**Shipped.** `src/fa/session/provisioning.py` (frozen `ProvisionRequest`/`ProvisionedWorkspace`,
`ProvisionMode`, callable type, no execution imports), `src/fa/execution/provisioning.py`
(`ManagedProvisioner` over `register_existing`), `register_existing` now also returns `tree_sha256`,
and `SessionManager` gains `workspace_provisioner`, the provisioning `begin_run` reservation, the
frozen-result cleanup ownership, the reverse-owner confirmation and the readiness gate. Files:
`src/fa/session/{manager,provisioning}.py`, `src/fa/execution/{provisioning,workspace}.py`,
`tests/test_session_lifecycle.py`, `tests/test_execution_provisioning.py`.

**Evidence (actual outputs).** Red first: `ModuleNotFoundError: fa.session.provisioning`. Green:
`pytest tests/test_session_lifecycle.py tests/test_execution_provisioning.py -q` → 22 passed in 0.92s;
`test_cli.py` + `test_s10c_artifact_posture.py` → 54 passed. Statics: `ruff check src tests` → All
checks passed!; `ruff format --check` → clean; `mypy src/fa/session src/fa/execution` → Success: no
issues found in 21 source files; `python -m pyrefly check` → 0 errors. Targeted mutation: **11/11
assertion-only kills** (the provisioner call, the run reservation, both readiness call sites, the
readiness condition, the cleanup discriminator, both conflict branches, the PROVISION/REUSE mode
selection, the pre-cutover guard and the adapter's blocked disposition), sources restored byte-exact
with the bank green after every mutant.

**Q78 — when is not-READY a closed error?** Enforcing the declared rule unconditionally made the full
suite 141 failed / 6115 passed, of which **130 were one cause** (`workspace_not_ready` on bare `tmp_path`
workspaces) across 14 CLI/workflow modules, plus the sandbox's own repo classifying
`degraded_environment: precommit_prewarm_failed`. That would both hide real regressions in a long-red
suite and turn the inherited STEP10 toolchain gap into a hard product block. Decision (recorded, not
assumed): readiness is enforced **in the managed composition** — the configuration that injects the
provisioner, i.e. exactly the composition SLICE4 STEP2 creates when it removes fail-open readiness. The
pre-cutover host composition keeps reporting readiness without blocking, proven explicitly by
`test_readiness_degradation_without_a_managed_provisioner_stays_non_blocking` so the transition cannot
silently persist. After the change the suite returns to its pre-existing state (6181 passed / 81
failed, of which 78+2 are `T0 baseline unavailable` and 1 is the blocked readiness-integration case;
all 81 reproduce identically with this change stashed).

**SLICE4 STEP2 migration obligation (measured, not deferred silently).** When the provisioner is
injected into the CLI composition, these tests assert the pre-cutover contract and must be migrated to
a registered/real project workspace (or drive the managed provisioner): `test_verify_gate_live` 81,
`test_s8_workflow_controller` 16, `test_s10b_cli_parity` 8, `test_s10a_cli_coverage` 7,
`test_s10c_workflow_exit_contract` 6, `test_cli_ergonomics` 6, `test_s10c_artifact_posture` 6,
`test_s9_stats_projection` 4, `test_s7_cli_run_paths` 3, `test_verify_slice` 2,
`test_scope_hint_cache_key` 2, `test_readiness_announcement` 2, `test_workflow_global_history` 1,
`test_iteration_cap` 1, `test_cli` 1. Total 146 occurrences. This is a cutover task, not a defect.

**Not closed.** STEP3's SLICE3 half (publication-dependent new-root provisioning, post-commit failure
preserving registered bytes), the SLICE4 caller routing, every live row (18 surfaces / 8 joins remain
PLANNED/UNEXECUTED), all STEP checkboxes and FUNCTIONAL contracts. `ManagedProvisioner` is a component
adapter: it is not composed into any running service yet.

### E264 — SLICE2 STEP4 (part A): injectable workspace port for the file tools

**Idea.** `fs_read_file`, `fs_write_file` and `fs_edit_file` reach the filesystem by resolving a host
path under `workspace_root` and calling `Path.read_text`/`write_text`. That is a second, un-rooted write
path beside the supervisor's rooted view IO, so CT103's "tools use the same authorized view as shell"
cannot hold and the view's CAS/policy never applies to model edits. This increment gives those three
tools one injectable IO port, implemented by the execution authority over an admitted view, and carries
that binding on `SessionState` as the internal execution binding §4.2 asks for.

**Contract/gap IDs.** I03 SLICE2 STEP4 (part A; part B — search/reach, PTY parity, artifacts, PDF/
binary — follows as E265); CT103 (actual write/edit tools use supervisor rooted IO against the same
authorized open view as shell; deny protected/PlanRef/control destinations and alias escapes; no
canonical fallback); CT103a lineage; spec §4.2; Q76 (the binding carries the exact `ViewRef`; ordinary
non-workflow execution needs no plan hash).

**Allowed files.** New `src/fa/inner_loop/tools/workspace_port.py` (port protocol, result values,
`port_relative`, error codes; no `fa.execution` import, preserving today's layering where nothing
outside `fa.execution` imports it), new `src/fa/execution/tool_port.py` (adapter over
`WorkspaceAuthority.read_file`/`write_file`), `src/fa/inner_loop/tools/{read_file,write_file,edit_file}.py`
(one optional `workspace_io` parameter and one swapped IO seam each), `src/fa/inner_loop/profiles.py`
and `src/fa/inner_loop/tools/__init__.py` (forward the port; the role builder is the composition point
`build_baseline_registry` already uses), `src/fa/inner_loop/state.py` (`SessionState.workspace_io`),
tests, plan/ledger. No change to fs_search/reach, run_bash, the registry schema, or the CLI.

**Current behaviour (source-verified).** `build_write_file_tool`/`build_edit_file_tool`/
`build_read_file_tool` take only `workspace_root`; handlers call `resolve_workspace_path` then POSIX IO;
`edit_file` reads the whole file and rewrites it with `path.write_text` (no CAS, so a concurrent writer —
a PTY shell, another process — is silently overwritten). `WorkspaceAuthority.read_file`/`write_file`
already provide bounded rooted reads with `sha256`/`eof` and atomic writes with an optional
`expected_sha256` that raises `STALE_REVISION`, and `SessionState` has no execution binding at all. No
production module outside `fa.execution` imports `fa.execution` yet.

**Target behaviour.** With a workspace port present, the three tools read and write only through the
admitted view: relative POSIX paths validated by the port (no host resolution, no absolute paths, no
`..`, no NUL), bounded reads that return the exact `sha256`, and writes that carry the base `sha256`
observed by the edit so a concurrent change is a reported conflict instead of a silent overwrite.
Without a port the tools keep today's behaviour exactly (the pre-cutover composition); the port is the
seam SLICE4 wires into the real factory, never a second implementation of the tools.

**Mechanism.** `workspace_port.py`: frozen `PortRead{content, sha256, eof}`, `PortWrite{sha256, bytes}`,
`WorkspacePortError(code)` with a closed code set (`invalid_request`, `denied`, `stale`, `input_policy`,
`unavailable`, `not_found`), `port_relative(raw) -> str` (rejects empty, absolute, `..`, NUL; normalizes
`/`), and a `WorkspacePort` Protocol with `read_file(path, *, max_bytes)` /
`write_file(path, content, *, expected_sha256)`. `tool_port.py`: `AuthorityWorkspacePort(authority, *,
peer, namespace, view_ref, capability, deadline_factory)` maps `SupervisorError`/`ViewIOError` codes onto
the port vocabulary and passes `deadline` per call. Each tool gains `workspace_io: WorkspacePort | None`
and swaps exactly one seam (`_read_file_text` / the `writer` closure / the read+write pair), keeping its
parsing, framing, telemetry, blackboard guard and result shapes unchanged.

**Production best practice.** One implementation per behaviour with a seam, not a fork: the port is a
Protocol (the tools do not import the execution layer), the adapter is the only place that knows
authority call shapes and error codes, and optimistic concurrency comes from the substrate that already
implements it rather than from a new lock. Failure is expressed as a closed code the tool turns into a
`ToolResult.fail`, so a denied or stale write is never a silent success.

**Failure behaviour.** Path outside the view / absolute / `..` / NUL → `invalid_request` before any IO;
reader view or revoked capability → `denied`; changed base bytes → `stale` with the file left untouched;
too large or binary → `input_policy`; authority timeout or unavailable → `unavailable`; unknown file →
`not_found`. Each maps to a non-retryable or retryable `ToolResult.fail` per its class; no host fallback
occurs when the port is present.

**DoD.** Real tools built with a real `AuthorityWorkspacePort` over a real registered workspace write,
read and edit only the admitted view's bytes; an edit whose base changed between read and write reports
`stale` and leaves the other writer's bytes intact; a READ view denies writes; traversal and NUL are
rejected before the authority is touched; `build_baseline_registry(..., workspace_io=...)` and
`SessionState.workspace_io` carry the port to `fs_write_file`. **Negative proof:** removing the port
write, the read, the `expected_sha256` argument, `port_relative`'s traversal check, the adapter's error
mapping, or the registry forwarding each fails a named test.

**Tests-writing class.** C0 for `port_relative`/error mapping, C1 for the tools+registry over a real
authority and view (producer-level kill), C3 for traversal/reader-write denial. No PTY, container or
live claim in this part.

**Producer kill-check targets (declared, 6).** (1) the port write seam in `write_file`; (2) the port read
seam in `read_file`; (3) the `expected_sha256` base passed by `edit_file`; (4) `port_relative`'s
traversal/NUL rejection; (5) `AuthorityWorkspacePort`'s error mapping; (6) registry/profile forwarding
of `workspace_io`.

#### E264 result — part A shipped, and one mutant that turned out to be equivalent

**Shipped.** `fa/inner_loop/tools/workspace_port.py` (Protocol, `PortRead`/`PortWrite`, closed codes,
`port_relative`, `PORT_READ_MAX_BYTES` mirroring the substrate's single-read bound),
`fa/execution/tool_port.py` (`AuthorityWorkspacePort` over `WorkspaceAuthority.read_file`/`write_file`
with the closed error mapping), the three tool seams (`fs_read_file`/`fs_write_file`/`fs_edit_file`
each take `workspace_io=` and swap exactly one IO seam), registry/role-builder forwarding
(`build_registry_for_role`, `_build_tool_builders`, `_add_optional_tool_builders`,
`build_baseline_registry`), and `SessionState.workspace_io` as the §4.2 internal binding.

**Evidence (actual outputs).** Red first (`ModuleNotFoundError: fa.execution.tool_port`). Green:
`pytest tests/test_execution_tool_port.py -q` → 21 passed; the tool/registry bank
(`test_inner_loop_tools`, `test_inner_loop_registry`, `test_write_file_expected_root`,
`test_s127_fs_surface`, `test_s11_session_state_typing`, `test_prompt_registry_coherence`,
`test_fs_search`, `test_fs_reach`, `test_tools_common`, `test_coverage_tools_batch`, `test_cli`) →
210 passed. Statics: `ruff check src tests` → All checks passed!; `ruff format --check` → clean;
`mypy` on the changed modules → Success: no issues found in 23 source files; `pyrefly check` → 0
errors. Targeted mutation: **7/7 assertion-only kills** with byte-exact restoration.

**Findings the work forced (recorded, not hidden).**
1. *Circular import*: `SessionState` is imported by `fa.inner_loop.artifacts`, so a runtime import of
   the port from `state.py` re-entered the tools package. Fixed with `TYPE_CHECKING` imports in
   `state.py`/`profiles.py`; the annotation-only dependency is also the correct layering signal.
2. *Bound drift*: the first `PORT_READ_MAX_BYTES` (8 MiB) exceeded the substrate's 1 MiB single-read
   limit, so every full-file read would have failed as `input_policy`. The constant now mirrors
   `protocol.MAX_TEXT_BYTES` and the test asserts both values agree, so drift fails loudly.
3. *Absence is not disclosed*: a missing path surfaces as `PATH_DENIED`, not `NOT_FOUND`. The port
   vocabulary therefore has no `not_found` code; the tools report `read_failed` and say the file is
   missing *or* not permitted, which is the substrate's actual guarantee.
4. *Equivalent mutant*: removing `expected_sha256` from the edit write is **not** observable, because
   `RootedViewIO._target` already refuses to overwrite an existing file without a base digest. The
   tool's digest is defence in depth; the load-bearing mutant is a *wrong* digest, which fails the
   ordinary-edit test. Kill credit for the no-clobber rule stays with the substrate's own bank
   (`test_execution_views`), not with this increment.
5. *Test-double drift*: `test_prompt_registry_coherence`'s rogue builder did not accept the new
   `workspace_io` keyword, so the composition root's failure was swallowed by the fallback and the
   wire-name guard stopped firing. The double now mirrors the real signature — a reminder that a
   composition-root signature change must be reflected in every double that stands in for it.
   The full-suite run then found **two more** such doubles (`test_s13_10_tool_names` rogue and
   with_workflow, `test_quality_slice_coverage` broken_builders), each failing with
   `TypeError: ... unexpected keyword argument 'workspace_io'`. This is the same failure mode as (5)
   and worth naming plainly: the targeted bank passed while three suites outside it were red, so the
   *composition-root* signature is a cross-suite contract and only the full run proves it. All three
   doubles now mirror the real signature and take the real `WorkspacePort | None` type instead of an
   `object` stand-in (a weaker type hid the mismatch from mypy as well).

**Not closed.** STEP4 part B (fs_search/fs_reach pinning, PTY mutual visibility, artifact path
retention, PDF/binary/helper-unavailable results, seal/import alias with SLICE3), STEP5's whole-bank
producer kills, all live rows (18 surfaces / 8 joins PLANNED/UNEXECUTED), STEP boxes and FUNCTIONAL
contracts. `AuthorityWorkspacePort` is a component adapter: nothing composes it into a running service
yet (SLICE4 STEP2), so the pre-cutover host-path tools remain the deployed behaviour.

### E265 — SLICE2 STEP4 (part B-1): cell-local indexes, explicit read outcomes, no host Git

**Idea.** Part A gave the file tools a port for *bytes*. The rest of the tool surface still assumes
it owns the filesystem: `fs_search` writes its FTS index to `<root>/.fa/fts.db`, `fs_reach` hardcodes
`<root>/.fa/structural.db`, `fs_checkpoint`/`fs_undo`/`fs_diff` shell out to host `git`, and a `.pdf`
read goes to `_read_file_text`, which opens the *host* path. Under an admitted view those are three
distinct violations of the STEP4 exit clause — a tool writing into project bytes the supervisor owns,
a host Git read, and a canonical read that bypasses the port. This increment makes each one closed and
explicit: indexes move to the view's private cache (never project bytes), the two tools refuse rather
than index in-place when no such home exists, PDF/binary/oversized reads become named results instead
of a generic refusal, artifacts keep resolving through the controller's store, and the managed
composition stops shipping host-Git tools at all.

**Contract/gap IDs.** I03 SLICE2 STEP4 exit clauses (b) zero host Git/version-stamp reads, (c) active
search sees a new symbol while a reader stays pinned, (d) artifacts retain their controller path,
(e) PDF/binary/large/truncated/helper-unavailable results explicit with no canonical fallback;
increment line 309; spec §4.2 ("same-view bounded reads and cell-local existing search/reach
implementations; no new public tools/search service or private state mount"). Part B-2 (PTY/tool
mutual visibility with blackboard on/off) and the seal/import alias stay open — see "Not closed".

**Allowed files.** `src/fa/inner_loop/tools/workspace_port.py` (add the view's private cache home to
the port contract plus one shared index-placement helper), `src/fa/execution/tool_port.py` (adapter
supplies it), `src/fa/inner_loop/tools/fs_search.py`, `src/fa/inner_loop/tools/fs_reach.py` (derive the
index path from the port, refuse in-place indexing), `src/fa/inner_loop/tools/read_file.py` (explicit
PDF/binary/oversize outcomes and no host read on the port path), `src/fa/inner_loop/profiles.py` and
`src/fa/inner_loop/tools/__init__.py` (thread the port to search/reach; suppress host-Git pair tools
when it is bound), new `tests/test_execution_tool_index.py`, plan/ledger/E2E register. No new public
tool, no new search service, no private state mount, no substrate change, no change to the host-mode
(default) behaviour of any tool.

**Current behaviour (source-verified).** `build_fs_search_tool(db_path, workspace_root)` builds
`_IndexHolder(db_path)` and calls `SearchIndex.ensure_indexed(root)`; `profiles._build_tool_builders`
passes `root/<fts_db_path>` (default `.fa/fts.db`) and `tools/__init__._resolve_fts_path` does the same,
so the index lives *inside* the workspace. `build_fs_reach_tool(workspace_root)` hardcodes
`root/.fa/structural.db`. Both index the host directory tree directly (that is the intended "cell-local
existing implementation" — the defect is only where the index is *written*). `_register_extra_tools`
registers `fs_checkpoint`/`fs_undo`/`fs_diff`/`fs_send_ctrl_c`, and `pair_tools` runs
`git status|add|commit|rev-parse|branch|stash|checkout|reset|diff` with `cwd=root`. In `read_file`,
`handler` branches to `_read_file_text(path)` only when no port is bound; with a port it calls
`_read_port_text`, which returns `read_failed` for every closed code with a message that only names the
code — a `input_policy` refusal (the substrate's non-UTF-8/NUL answer) is therefore reported as a
generic workspace refusal, and `.pdf` (whose bytes the port cannot deliver) is reported the same way.
Artifacts never touch either path: `_read_artifact` resolves through `session.artifact_store` and the
run's projection store — the controller's own roots.

**Target behaviour.** With a `workspace_io`, `fs_search`/`fs_reach` place their index under the view's
private cache home (`workspace_io.cache_dir`) and **refuse** (typed, no IO, no index write) when that
home is absent or resolves inside the workspace root. Only the index location changes: both tools still
read the cell's own materialized tree, so an active view sees a symbol written a moment ago while a
pinned reader's index — a different cache home — keeps answering from its own revision. A `.pdf` read
through the port is refused by name before any IO (the substrate is text-only by contract); a
non-UTF-8/NUL refusal (`input_policy`) is named as binary content; an oversized read names the exact
managed bound and does not offer a line-window workaround the port cannot serve. Artifact reads are
unaffected: they resolve through the controller store even with a port bound. With a port bound, the
composition ships no tool that runs host `git`; host mode keeps all three pair tools unchanged.

**Mechanism.** `workspace_port.py` gains `WorkspacePort.cache_dir -> Path | None` (the view's private
scratch, deliberately *not* project bytes) and `index_db(port, root, filename, fallback) -> Path` which
returns `fallback` when no port is bound, else `cache_dir/filename`, raising
`WorkspacePortError("unavailable")` when `cache_dir` is None or is inside `root` — one implementation of
the placement rule for both tools. `tool_port.AuthorityWorkspacePort` takes `cache_dir=` and exposes it
(no authority change: the composition already knows the view's cache from `ViewInputs.cache`).
`fs_search`/`fs_reach` take `workspace_io=None`, resolve their index through `index_db` at *handler*
time (build time stays side-effect free) and return a `search_failed`/`reach_failed` non-retryable
result naming the missing index home. `read_file` maps the closed codes to named outcomes:
`input_policy` → "binary or non-UTF-8 content"; `not read.eof` → the managed bound; `.pdf` →
refusal before IO. `profiles`/`__init__` pass `workspace_io` to both builders and pass
`include_pair=False` when it is bound, logging the omission once (a silent drop would be the worse
failure).

**Production best practice.** Keep the index out of the artifact under validation (writing a cache into
the tree you are hashing invalidates the hash and makes a reader's answer depend on someone else's
write); make "I have nowhere to put this" a typed refusal rather than an implicit fallback to the
canonical tree; keep the default (host) path byte-identical so the pre-cutover behaviour cannot regress;
and let one helper own the placement rule so search and reach cannot drift.

**Failure behaviour.** No port → today's behaviour exactly. Port without a usable cache home → typed
non-retryable failure, zero index writes, zero host reads. Port with a cache home → index under it;
the returned tool result names neither the host path nor the cache path. PDF/binary/oversize → named
non-retryable or retryable-per-reason failures with no host-path mention. A pair tool is simply absent
from the managed registry (the model sees a smaller, honest tool set).

**DoD and negative proof.** New tests: managed search writes no index into the view and answers from
its cache; no cache home and an in-view cache home are both refused with no index file created;
`fs_reach` resolves from its cache home; an active view finds a newly added symbol while a pinned view
with a separate cache home does not; a `.pdf` read refuses without calling the port; `input_policy`
is named as binary content; an oversized read names the bound; an artifact read succeeds while the
bound port refuses any call; the managed registry contains no `fs_checkpoint`/`fs_undo`/`fs_diff`
while the host registry still does. Negative proof: delete `index_db`'s placement check → the in-view
case indexes inside the view; drop the `workspace_io` argument to the search builder → the view gains
`.fa/fts.db`; re-add `include_pair=True` under a port → the managed-registry test fails; restore the
generic `input_policy` message → the binary assertion fails.

**Not closed.** PTY/tool mutual visibility with blackboard on/off (needs the cell's PTY inside the
admission, i.e. the real backend — SLICE4/6), the seal/import alias (SLICE3), STEP5's whole-bank
producer kills, and every live row. Nothing composes `AuthorityWorkspacePort` yet, so the deployed
behaviour is still the host path.

#### E265 result — part B-1 shipped; one oracle had to be rewritten before it could hold

**Shipped.** `WorkspacePort.cache_dir` (the view's private cache home) and the shared `index_db`
placement helper; `AuthorityWorkspacePort(cache_dir=…)`; `fs_search`/`fs_reach` resolve their index
per call and refuse when the home is missing or inside the searched tree; `read_file` refuses `.pdf`
before any IO and names `input_policy` as binary content and a non-`eof` read as the exact bound;
`profiles`/`tools/__init__` forward the port to both index tools and drop the host-Git pair tools under
a bound port; `_safe_walk` skips its `git ls-files` fast path when the root has no `.git`.

**Evidence (actual outputs).** Red first (9 of 14 new cases failed on the unmodified tree). Green:
`tests/test_execution_tool_index.py` → 21 passed; the index/search/reach bank (`+ test_fs_search`,
`test_fs_reach`) → 80 passed. Targeted regression bank (tool, registry, session, provisioning, CLI
suites) → 285 passed. Statics: `ruff check src tests` → All checks passed; `ruff format --check` → 505
files clean; project `mypy` → Success, 493 source files; `pyrefly check` → 0 errors. Targeted mutation:
**10/10 assertion-only kills**, sources restored byte-exact.

**Findings the work forced.**
1. *A fail-degraded producer hides its own deletion.* The first version of the host-Git case made
   `subprocess.run` raise and asserted the search still worked. With the guard removed the search still
   passed: `_git_ls_files` catches every exception and falls back to `os.walk`, so the exception never
   reached the test — a masked producer in exactly the E259 pattern. The case now records invocations
   and asserts the list is empty; only then does deleting the guard fail it. Rule for the rest of
   SLICE2: when the code under test is fail-degraded by design, assert the *call*, never the exception.
2. *Three more composition-root doubles drifted* (`test_quality_slice_coverage` ×2, and the same class
   as E264's five): each failed with `TypeError: … unexpected keyword argument 'workspace_io'` because
   `_register_extra_tools`/`profiles` now pass the port to `build_fs_search_tool`. This is the third
   time this increment series has paid for that; the doubles now mirror the real signature and the
   real type, and the lesson is recorded once here rather than rediscovered per slice.
3. *`index_db` was typed for a port that "cannot be None"* while every caller passes `None` in host
   mode; `mypy` caught it only after the first draft. The signature is now `WorkspacePort | None` and
   the helper owns the host-mode fallback, so callers carry no `type: ignore`.
4. *PDF extraction cannot follow the bytes into the view.* The substrate is text-only by contract
   (`MAX_TEXT_BYTES`, NUL/UTF-8 rejection), so managed PDF reads have no path to the extractor chain.
   The refusal is explicit and named rather than silent — but this is a **capability difference against
   host mode**, so it is raised as Q79 below, not decided here.
5. *Index locality is now structural, not conventional.* Because both tools derive the index home from
   the view's cache, two views cannot share an index even in principle; the pinned-reader case asserts
   that by construction (distinct homes → distinct answers) rather than by timing.

**Not closed.** STEP4 part B-2 (PTY/tool mutual visibility with blackboard on/off — needs the real
cell), the seal/import alias (SLICE3), STEP5's whole-bank producer kills, every live row (18 surfaces /
8 joins still `PLANNED / UNEXECUTED`), and the STEP boxes and FUNCTIONAL contracts. `AuthorityWorkspacePort`
is still a component adapter: nothing composes it into a running service, so the deployed behaviour
remains the host path until SLICE4 STEP2. The live verification plan for these cases (including the
`PATH`-shim and `strace` oracles) is
[notes/i03-live-e2e-test-plan-2026-10-22.md](../notes/i03-live-e2e-test-plan-2026-10-22.md).

### E266 — SLICE3 STEP1 (part 1): the terminal barrier (CT104)

**Idea implemented now.** Closing a view's write admission is already possible and already durable; what
does not exist is the other half of the contract — proving the view's *cells* are dead before anything
downstream treats the tree as frozen. This increment adds exactly that half: a stop flow that closes
admission, drains live handlers, stops the view's cells, and then waits for a positive observation that
the cgroup is empty before the view may become `TERMINAL`. Everything short of that observation leaves
the view `STOPPING` (quarantined), because "we asked it to stop" is not terminality.

**Contract/gap IDs.** CT104 (and its named producer `supervisor.py::stop_view ->
_wait_descendants_terminal`); I03 SLICE3 STEP1 (terminal barrier/view state machine half; the seal and
immutable-export half is the next increment); spec §4.2 ("actual terminality plus sealed-tree/protected-
path validation is the publication authority").

**Allowed files.** `src/fa/execution/workspace.py` (add `mark_terminal` only — the authority stays the
single owner of view state), `src/fa/execution/supervisor.py` (`ViewStopper`, `CellTermination`,
`TerminalVerdict`, `ViewStopResult`, `_wait_descendants_terminal`), new
`tests/test_workspace_publication.py` (the plan's fixed filename for the local half), plan/ledger.
Not touched: `publication.py` (seal/publish — next increment), `docker.py` (no cgroup reader yet), the
backend, the CLI/service composition, any wire schema.

**Current behaviour (source-verified).** `WorkspaceAuthority.close_admission` sets the per-view gate
closed, moves `view.record["state"]` from `OPEN` to `STOPPING` with fsync + read-back, and turns every
subsequent file operation into `VIEW_CLOSED` via `_live_view`. `drain` waits for the gate's active set
and refuses if admission is not already closed. Nothing anywhere transitions `STOPPING` to anything
else: `grep -rn "def stop_view\|_wait_descendants_terminal" src/fa/execution` is empty, `docker.py`
documents "Deliberately no terminal_barrier: Docker stopped != cgroup populated=0", and
`CellBackend.close` is a backend-wide teardown rather than a per-view stop plus observation. So a view
can be admission-closed while its cells still write: the CT104 hole, exactly.

**Target behaviour.** `stop_view` is the only path that may produce `TERMINAL`, and it produces it only
after: (1) irreversible admission closure, (2) a drained handler set, (3) a stop call for the view's
cells, (4) a *positive* observation of descendant emptiness inside the remaining budget. A view whose
cells are still populated, whose observation is unavailable, whose observer raises, or whose budget runs
out stays `STOPPING` and keeps its ownership — no release, no seal, no reuse. A `TERMINAL` view is
idempotent: stopping it again touches no cell. `mark_terminal` alone can advance `STOPPING`, never
`OPEN`, so the barrier cannot be short-circuited by calling the state transition directly.

**Exact mechanism.** `WorkspaceAuthority.mark_terminal(peer, namespace, *, view_ref, capability,
deadline)`: proof, then `VIEW_CLOSED` unless the gate is closed; `OPEN` is refused explicitly; `TERMINAL`
is a no-op; otherwise rewrite `view.json` through the existing `_replace_private_bytes` and read it back —
a mismatch or OS error marks the authority unhealthy and raises `DURABILITY_UNKNOWN`, exactly as
`close_admission` does. `supervisor.CellTermination` is the two-method seam the real backend will
implement (`stop_cells`, `cells_terminal -> bool | None`; `None` means "cannot tell"). `ViewStopper
.stop_view` sequences close → drain → stop → `_wait_descendants_terminal` → `mark_terminal`, and returns a
frozen `ViewStopResult{state, verdict, reason}`. `_wait_descendants_terminal` polls on a small interval
until the deadline, treating `False` as "not yet", `None` and any exception as `UNKNOWN`, and the deadline
itself as `UNKNOWN` — never as success.

**Production best practice.** The state owner stays single: the authority writes view records, the
stopper only decides when to ask it to. The barrier is an injected seam because the observation is a
kernel fact that cannot be faked in-process; a missing seam is a closed refusal, not a bypass. Polling
exists because stopping a container is asynchronous — the API returning is explicitly not the kernel
fact. And the whole flow is bounded: a hung observer must not hang the supervisor.

**Failure behaviour.** Live cells → `POPULATED`, state `STOPPING`, ownership retained. Observer absent,
raising, or unreadable → `UNKNOWN`, state `STOPPING`. Budget exhausted while draining or observing →
`SupervisorError` from the drain or `UNKNOWN` from the observation; either way nothing is marked. Record
persistence failure at the mark → `DURABILITY_UNKNOWN` and the authority goes unhealthy. Repeated stop on
a `TERMINAL` view → `TERMINAL` with no cell traffic.

**DoD and negative proof.** New tests (C0 for `mark_terminal`, C3 for the orchestration over the real
authority, real view records on disk and a recording barrier): write denial is observable *at* cell-stop
time (proving admission closed first); polling continues until a positive observation; a populated view
stays `STOPPING` with its on-disk record unchanged; an exception is `UNKNOWN`; no observer is `UNKNOWN`
and stops no cells; a terminal view is idempotent; `mark_terminal` refuses `OPEN`, is idempotent for
`TERMINAL`, and persists durably. Negative proofs: deleting the `close_admission`, `drain`, or
`stop_cells` call, treating `None`/exception as terminal, treating a deadline as terminal, or dropping
`mark_terminal`'s state guard each breaks a named assertion. Classes: C0 + C3. The kernel fact
(`/sys/fs/cgroup/**/cgroup.events` `populated 0`) is C-host and belongs to
`tests/integration/test_publication_recovery.py` under `FA_REQUIRE_EXECUTION_HOST=1`; it is NOT claimed
here and the local tests use an observer double only where the observation is genuinely external.

**Not closed.** Seal and immutable-export validation (CT105), publish (CT106), recovery (CT107), the real
cgroup reader and the Docker-backed `CellTermination`, "restart cannot release a live old writer"
(durability of the stop intent), and every live row.

#### E266 result — the barrier exists, and two "obvious" oracles had to be replaced

**Shipped.** `WorkspaceAuthority.record_terminal` / `terminal_receipt` (a durable, separate
`terminal.json` receipt; the view keeps the closed state vocabulary the protocol publishes) and
`supervisor.ViewStopper` with `stop_view` + `_wait_descendants_terminal`, the `CellTermination`
seam and typed `TerminalVerdict` / `ViewStopResult` (`to_wire()` == the protocol's `{view_id,
terminal}`). Every path that cannot *observe* emptiness leaves the view `STOPPING` and owned.

**Evidence (actual outputs).** `pytest tests/test_workspace_publication.py` → 11 passed. Execution
bank (`workspace`, `views`, `readers`, `purposes`, `view_io`, `backend`, `journal`, `dispatch`,
`client`, `supervisor`) → 643 passed. Statics: `ruff check src tests` → All checks passed;
`ruff format --check` → 506 files clean; project `mypy` → Success, 494 source files; `pyrefly check`
→ 0 errors. Targeted mutation: **9/9 assertion-only kills**, sources restored byte-exact.

**Findings the work forced.**
1. *A receipt, not a state.* My first design minted a `TERMINAL` view state; the compiled
   `_VIEW_RECORD` schema publishes the closed set `OPEN/STOPPING/SEALED/PUBLISHED/REJECTED/UNKNOWN`,
   so terminality had to become a **separate durable receipt** that sealing will consume. This is the
   better contract anyway: terminality is a precondition of seal, not a view phase.
2. *`drain` is load-bearing only for dispatch work.* Under the authority mutex a file handler
   serializes against `close_admission`, so "skip the drain" was initially an **equivalent mutant**.
   The real window is a `WorkAdmission` held across create/start/send (outside the mutex); the test
   that holds one proves cells are not stopped under a live dispatch. Without that test the drain
   call could have been deleted with no red anywhere.
3. *A read-back needs a non-persisting write to be observable.* Deleting the post-write verification
   survived until a test replaced `_replace_private_bytes` with a no-op and required
   `DURABILITY_UNKNOWN` — the honest oracle for "the write claimed success but did not land".
4. *Three mutation expectations named the wrong test.* The mutants were killed, but by the new
   cases, not the ones listed. The `expect` lists now name the test that actually holds each
   producer; a kill attributed to a test that does not assert the property is not evidence.

**Not closed.** Seal and immutable-export validation (CT105), publish (CT106), recovery (CT107), the
Docker-backed `CellTermination` + real cgroup reader (C-host, `tests/integration/test_publication_recovery.py`
under `FA_REQUIRE_EXECUTION_HOST=1`), "restart cannot release a live old writer", STEP5's full-bank
kills, and every live row (18 surfaces / 8 joins still `PLANNED / UNEXECUTED`). Nothing composes
`ViewStopper` into the service yet: `STOP_VIEW` has an encoded reply but no dispatcher route.


## E267 — SLICE3 STEP1 (part 2): immutable export and seal (CT105) — declaration before code

**Status: PLAN ONLY, awaiting operator approval. No `src/` edit, no STEP tick, no live verdict.**
Written 2026-10-22 after E266 (`6ff1121`) and after a source re-read of `workspace.py`,
`supervisor.py`, `protocol.py` and spec §5. This section is the approval artifact: nothing below
is implemented or claimed.

### E267.0 Ordering verification (the operator asked for this first)

The incoming hand-off said *"E267 — SLICE3 STEP2: seal (CT105)"*. Source and plan say that label is
off by one step, and the **work content is still the right next unit**:

| Claim | Verified against | Result |
| --- | --- | --- |
| seal is STEP1's remainder, not STEP2 | `increment-03:343` — STEP1 = "Q74 policy + stage transition table + terminal barrier + **immutable export validation in execution/publication.py**"; `increment-03:344` — STEP2 = "exact intent/current/projection schemas … generation/base CAS" | **correction:** E266 shipped STEP1's barrier; E267 is STEP1 *part 2* (seal), and STEP2 (CAS/publish state) follows as E268 |
| seal needs no unfinished SLICE2/STEP1 code | seal's inputs all shipped: view records + view records + `workspace.py::_proof_only`, closed gate (`::close_admission`, `::drain`), terminal receipt (`::record_terminal`, `::terminal_receipt`), base revisions (`::_revision`), tree walker (`::_Capture`, `::_snapshot`), purpose matrix (`_purposes`, E259) | **holds** — no dependency on SLICE2 STEP4 part B-2 (needs a real cell), STEP5 (kill recording), SLICE1 STEP2/3 (service composition) or Docker |
| publish is what closes SLICE2 STEP3's provisioning leg | `increment-03:295` (SLICE2 STEP3 "SLICE3 half (exit, moves to SLICE3's evidence)") + spec §5 steps 1–5 | **holds** — seal alone closes nothing; say so and do not imply it |
| `SEALED` is a real state the receipt unlocks | `_VIEW_RECORD` state enum `OPEN|STOPPING|SEALED|PUBLISHED|REJECTED|UNKNOWN` (`workspace.py::_VIEW_RECORD`); E266 left the view in `STOPPING` with `terminal.json` | **holds** — seal is the only `STOPPING → SEALED` transition, and it must require the receipt |
| `STOP_VIEW` has no dispatcher route yet | `_dispatch`/`_handle` are injected seams; no `stop_view`/`seal` route exists in `supervisor.py` | **holds** — local tests call the owners directly; routes land with SLICE1 STEP3 composition |

Two source findings that change the step's shape and must be resolved *inside* E267:

1. **id-prefix contradiction.** The wire says `seal-…`: `Operation.SEAL` result
   (`protocol.py:162`) and `Operation.PUBLISH` payload (`protocol.py:126`). The persisted view record
   says `manifest-…`: `_VIEW_RECORD.sealed_manifest_id` (`workspace.py::_VIEW_RECORD.sealed_manifest_id`). Seal is the first writer
   of that field, so one of the two must move now (decision D5).
2. **the seal manifest is not `_TREE`.** Spec §5 freezes a different header
   (`schema_version, workspace_id, generation, base_revision, view_id, tree_sha256, entries`) and
   requires deletion tombstones, while `_TREE`/`_ENTRY` (`workspace.py::_TREE`, `::_ENTRY`) carry `revision_id`
   and pin `deleted` to `False`. `publication.py` therefore owns its own `_SEALED_MANIFEST`; extending
   `_TREE` would silently widen the revision format that readers verify with `_revision()`.

Also verified so the plan does not promise them: `_seal_readonly_source` (`workspace.py::_seal_readonly_source`) is a
**different** operation (freezing a READ execution input for a cell, write bits stripped) and is not
CT105; and `_Capture` refuses hardlinked files (`nlink == 1`), setuid/setgid/sticky bits, mounts
crossing device ids, non-UTF-8 names and unsafe links — seal inherits those refusals as declared
contract, not surprise.

### E267.1 Contract and gap IDs

CT105 (FUNCTIONAL, kill target `publication.py::seal_view -> _validate_sealed_tree`); SLICE3 STEP1;
spec §5 (seal half only — the current-pointer half is STEP2) and §5.1's `kind`/`phase` vocabulary
only where seal must *not* write it; E266's receipt is the precondition; E259's purpose matrix is
inherited unchanged. Q63/Q74/Q59–Q66 are untouched. Nothing here is L2 `VERIFIED`.

### E267.2 Current behaviour (source-verified, `6ff1121`)

- A writable view is a full private materialization at
  `state/workspaces/<ws>/views/<view_id>/{view.json,source/,scratch/}`, installed once by
  `_install_view` (`workspace.py::_install_view`) through `_rename_directory` → `renameat2(RENAME_NOREPLACE)`
  (`view_io.py:29-33,94-98`). After install nothing re-walks the source tree.
- `view.record` holds `state`, `input_tree_sha256` (base tree hash at creation),
  `sealed_manifest_id` (always `None` today) and `plan_ref`; it is the closed record the protocol
  publishes, and `_project_view` (`workspace.py::_project_view`) refuses any state other than `OPEN`.
- The barrier writes `terminal.json` (`record_terminal:2113`) and leaves `view.json` in `STOPPING`;
  admission is closed and handlers drained before that.
- There is no `publication.py`, no sealed manifest, no `SEALED` transition, and no producer that
  recomputes a view's tree after the barrier. `tests/test_workspace_publication.py` (E266, 11 cases)
  covers CT104 only.

### E267.3 Target behaviour (rules the tests will hold)

- **R1 preconditions.** Exact-view proof by capability and principal (`_proof_only`), gate closed,
  state exactly `STOPPING`, terminal receipt present, binding still `OWNED` by this actor at
  `ref.generation`, `current.revision_id == ref.base_revision`, `input_tree_sha256` equal to that
  revision's tree hash, and `ProtectedPlanContext.recheck()`. Absent receipt → `TERMINALITY_UNKNOWN`;
  open gate / `OPEN` view → `VIEW_CLOSED`; stale base/generation/source → `STALE_REVISION` or
  `INPUT_POLICY`. A `SEALED` view re-seals idempotently (R8). No `seal` on `UNKNOWN`/quarantine.
- **R2 recompute, never trust.** Walk `source/` through the existing `_Capture` under the caller's
  deadline and `InputLimits`, with the authority's exclusions. The tree hash is computed from the
  bytes read after the barrier; `input_tree_sha256`, `tree.json` or any model/cell-supplied manifest
  is cross-checked, never adopted.
- **R3 base comparison and tombstones.** Base entries come from `_revision(binding, base_revision)`.
  Paths present in base and absent in the seal become tombstones carrying that base entry's
  `type/mode/size/sha256/link_target` with `deleted: true`; a type change at one path is delete+add;
  additions/changes carry recomputed facts. `tree_sha256` hashes canonical JSON of **non-deleted**
  entries only (§5), so `deleted` is a transport fact, not part of the digest.
- **R4 manifest v1.** Exact header from §5, entries sorted by unique relative path, `mode` an integer
  `<= 0o777`, `size >= 0`, file SHA over bytes, symlink SHA over UTF-8 target with the byte length as
  size, directory `sha256`/`link_target` null. A `_SEALED_MANIFEST` schema in `publication.py`, not a
  reuse of `_TREE`.
- **R5 protected and excluded domain.** Reject any entry or tombstone that **is**, **contains** or **is
  contained by** the PlanRef canonical path; reject deletion, rename or type change of an ancestor that
  would carry protected/excluded canonical bytes; `.git`, `.fa`, `.venv`, `.env` (and configured
  exclusions) are dropped by `_Capture`, so they can never become tombstones — the test asserts that
  rather than trusting it.
- **R6 links.** Only symlinks already present and unchanged in the base revision may seal; a new or
  changed link is `INPUT_POLICY`. Absolute, escaping and excluded-target links stay refused by
  `_Capture._link` (reused producer, no new credit).
- **R7 durability order.** Write the sealed manifest (`seal-…` id, manifest v1 body) to the view's
  private directory with `_replace_private_bytes` + fsync + read-back equality, **then** flip
  `view.json` to `SEALED` with `sealed_manifest_id` and read it back. Any failure after the manifest
  exists is `DURABILITY_UNKNOWN`; the view stays `STOPPING` and no `SEALED` success is reported.
- **R8 idempotence.** A retried seal on a `SEALED` view returns the stored identity after verifying
  the stored manifest's own hash, without a second manifest and without re-sealing changed bytes
  (there cannot be any: the gate is closed and the barrier holds). A retry that recomputes a
  *different* tree hash than the stored manifest is `CORRUPT_STATE`, never a quiet re-seal. `PUBLISHED`
  is a finished lifecycle and `OPEN`/`REJECTED` have nothing to seal, so both are `VIEW_CLOSED`.
- **R9 failure classification.** Determinate validation failure (protected/link/mode/type/path/limits)
  → its closed error code with **no state write** (D3: `STOPPING` is kept; `REJECTED` is not reachable
  from `STOPPING` per §5:884); staleness (`ref.generation`, `current.revision_id`, source hash) →
  `STALE_GENERATION`/`STALE_REVISION`, never `SEALED`; missing receipt or `UNKNOWN`/quarantined view →
  `TERMINALITY_UNKNOWN`; OS/durability → `DURABILITY_UNKNOWN`, state untouched, authority unhealthy;
  wrong capability/namespace/principal → `UNAUTHORIZED`.
- **R10 no side effects.** Canonical roots, `current.json`, revisions, Git index, other views' pins,
  scratch and any cell state are untouched; no Docker call; no execution of anything found in the
  tree; no model-provided metadata is read.
- **R11 reply.** Exactly `{sealed_manifest_id, revision_id, tree_sha256}` per `protocol.py:162` and
  spec §2.1:163. `sealed_manifest_id` is this seal's opaque object id (`seal-…`, D5); `revision_id` is
  the deterministic id of the revision publish must materialize (D2), recomputable from the stored
  manifest; `tree_sha256` is the sealed tree digest.

### E267.4 Decisions requested (answer these, then code starts)

- **D1 — step label.** Record E267 as SLICE3 **STEP1 part 2** (seal/CT105) and renumber the intended
  next unit (CAS/publish) as E268 = SLICE3 STEP2. Recommended, matches `increment-03:343-344`.
- **D2 — `revision_id` in the SEAL reply. RESOLVED from records (2026-10-22), not asked.** Spec
  §2.1:163 freezes the reply as `{sealed_manifest_id, revision_id, tree_sha256}` and says the
  *"immutable revision may be unpublished"*, while §5's five-step publish flow creates `Rnext` at its
  step 1 and §5.1 only discriminates recovery through `intent.json` (`PREPARED + old current … discard
  only uncommitted owned **Rnext**`). A revision materialized at seal would therefore sit outside every
  documented recovery row. **Decision:** seal mints the id of the revision publish must create, derived
  deterministically from the sealed bytes — `"rev-" + sha256(canonical(sealed_manifest))[:32]` — so
  publish recomputes the same id from the stored manifest instead of trusting a caller, and the id is
  tamper-evident by construction. Seal writes no `revisions/…` bytes, no `intent.json`, no `current.json`.
  Materializing `Rnext` under exactly that id is E268's step. Rejected alternative (materialize at seal)
  is recorded above with the recovery-table reason.
- **D3 — durable `REJECTED`. RESOLVED from records, and it overturns the declaration's own
  recommendation.** Spec §5:884 fixes the chain `OPEN → STOPPING → SEALED → PUBLISHED|REJECTED`:
  `REJECTED` is reachable **from `SEALED`**, never from `STOPPING`. Writing `REJECTED` on a failed seal
  would invent an undocumented transition. **Decision:** a determinate seal validation failure returns
  its closed error code and writes **no** state — the view stays `STOPPING` with its gate closed, its
  receipt and its frozen bytes, so the same deterministic refusal repeats on retry; `REJECTED` belongs
  to E268's `SEALED → PUBLISHED|REJECTED` branch. `UNKNOWN`/quarantined views cannot seal at all
  (`TERMINALITY_UNKNOWN`), and `DURABILITY_UNKNOWN`/`STALE_*` never write `SEALED`.
- **D4 — scope.** E267 seals the tree for `PROJECT`/`PROVISIONING`/`MUTATION`. `CANDIDATE` buffer
  validation and `PLAN`/`BOOTSTRAP` kinds move to STEP3 with `prepare_bundle`/`install_project`
  (recommended: §5 ties the candidate buffer to PLAN-intent publication, and sealing a buffer without
  its publisher would create a second, half-specified path).
- **D5 — `sealed_manifest_id` prefix.** (a) widen `_VIEW_RECORD.sealed_manifest_id` from
  `_id("manifest-")` to `_id("seal-")` so the record and the wire name one object (recommended;
  internal record schema only — the wire contract at `protocol.py:126,162` is unchanged and no test
  writes a `manifest-` id today); (b) mint `manifest-` ids in the record and translate at publish.
- **D6 — evidence environment.** This sandbox has **no Docker** (host work stays `BLOCKED` by
  design) and its source-built CPython 3.13.7 lacks `_ctypes`, `_sqlite3`, `_ssl` and `zlib`
  (no libffi/zlib/sqlite headers, no reachable distro mirror). A disclosed, out-of-repo shim
  (`pysqlite3` alias + `renameat2` emulation) makes the local banks runnable: baseline right now is
  **1126 passed, 6 errors**, the six being the installed-wheel build cases (`uv build` offline).
  Options: (i) I run local construction checks under that shim, label them **non-authoritative**,
  and you re-run the declared fences on your 3.13 host before any STEP tick (recommended);
  (ii) I write code only and you run every bank; (iii) stop until a conforming environment exists.

### E267.5 Allowed files (nothing else)

- `src/fa/execution/publication.py` — **NEW**: `seal_view`, `_validate_sealed_tree`, `_SEALED_MANIFEST`.
- `src/fa/execution/workspace.py` — only the D5 record-prefix widening (and, if D5(b), the mapping).
- `tests/test_workspace_publication.py` — new CT105 cases beside the E266 CT104 bank.
- Docs: this section, `ledger.md` E267 result, one new E2E register row `I03-LIVE-19`.
- **Forbidden:** `protocol.py` (no wire change), `supervisor.py` (no dispatcher route in this step),
  `docker.py`/`backend.py`/`client.py`, any caller, mount or cutover change, any new module beyond
  `publication.py`, any second walker or second lock.

### E267.6 Tests (C0/C3, real filesystem, real authority)

Fixture: the existing `Site`/`Site.claim`/`native_profile` helpers, real view creation through the
authority, real `stop_view` with the `CellTermination` seam doubled only for the kernel fact (as
E266), then `seal_view` called directly. Cases: happy-path seal and exact manifest body; recompute
beats a poisoned `tree.json`; tombstone from a deleted file; type change; protected PlanRef path,
its ancestor and its descendant each refused; new/changed/escaping link refused; unchanged legal link
accepted; setuid bit refused; excluded paths absent from the manifest; stale generation and stale base
refused; missing receipt → `TERMINALITY_UNKNOWN`; `OPEN` view → `VIEW_CLOSED`; seal twice → same id;
manifest rewrite → `CORRUPT_STATE`; read-back failure → `DURABILITY_UNKNOWN` and no `SEALED`; a
concurrent write attempt after the barrier cannot change sealed bytes; canonical root, `current.json`,
revisions and a pinned reader are byte-identical before/after.

### E267.7 Negative proof — declared kills (assertion-only, byte-exact restore)

1. `publication.py::seal_view -> _validate_sealed_tree` (CT105's named producer).
2. the terminal-receipt precondition in R1.
3. the base/generation staleness equality in R1.
4. the protected-path rejection in R5.
5. the tombstone derivation in R3.
6. the recompute in R2 (mutant: trust `input_tree_sha256`/stored manifest).
7. the `SEALED` write + read-back in R7.
8. the manifest-id binding between record and manifest file.
9. the new-link rejection in R6.

Reused and **not** claimed as new credit: `_Capture._link`, `_Capture` fingerprint staleness,
`_revision` corruption checks, `record_terminal`.

### E267.8 Definition of done

Red-first evidence for the functional cases; the owning bank (`tests/test_workspace_publication.py` +
the execution bank) green; `ruff check`, `ruff format --check`, `mypy src/fa/execution`,
`pyrefly check src/fa/execution` clean; all declared kills executed with source restored; the E2E
register extended with `I03-LIVE-19` (`publication.py`, `PLANNED / UNEXECUTED`) and S06 wording
unchanged; no STEP checkbox, no CT `VERIFIED`, no deployment claim. SLICE3 STEP1 stays open
afterwards: Q74's per-stage checkpoint policy and the real cgroup observer are still its parts.

### E267.9 Out of scope (explicit)

`publish_view`/`current.json`/intent/projection/CAS and Git-index preservation (STEP2); recovery
(STEP4); `prepare_bundle`/`install_project`/Q58/BOOTSTRAP and candidate-buffer seal (STEP3); CT104–107
whole-bank kill recording (STEP5); SEAL/STOP_VIEW dispatcher routes, `build_supervisor/main` and any
caller/mount cutover (SLICE1 STEP3, SLICE4 STEP2); real Docker/cgroup proofs
(`tests/integration/test_publication_recovery.py`, `FA_REQUIRE_EXECUTION_HOST=1`, host work);
deployment and every live verdict (final SLICE6).

### E267 result — SLICE3 STEP1 (part 2) shipped as local component proof

**Shipped.** `src/fa/execution/publication.py` (NEW): `seal_view`, `_validate_sealed_tree`, the frozen
`_SEALED_MANIFEST` schema, `derive_revision_id`, `SealResult`. `src/fa/execution/workspace.py`:
`prepare_seal` (all seal preconditions + the post-barrier recompute), `mark_sealed` (the single durable
`STOPPING → SEALED` transition with read-back), `_SealInputs`, and the D5 id alignment
(`sealed_manifest_id` now requires `seal-…`, matching `protocol.py:126,162`). Tests:
`tests/test_workspace_publication.py` (CT105 section added beside the E266 CT104 bank).

**Decisions as resolved.** E267a records D2 (seal mints a *content-derived* revision id, publish
materializes it) and D3 (`REJECTED` is not reachable from `STOPPING`; a determinate seal failure writes
no state). D1/D4/D5 were approved as written.

**Red → green.** Red: with `workspace.py` reverted and `publication.py` absent, the module errors at
`import fa.execution.publication` (collection error, recorded honestly rather than claimed as a
per-rule red). Green: `pytest tests/test_workspace_publication.py` → **24 passed** (11 retained CT104
cases + 13 new CT105 cases).

**Owning/broader banks.** `test_execution_views`, `_workspace`, `_readers`, `_view_io`, `_admission`,
`_purposes`, `test_workspace_publication` → **359 passed**. Execution + readiness + provisioning bank
(`tests/test_execution_*.py`, `test_workspace_publication.py`, `test_controller_entry.py`,
`test_workspace_readiness_integration.py`, `test_session_workspace_provisioning.py`) →
**1241 passed, 1 failed**. The failure is
`test_workspace_readiness_integration.py::test_clean_candidate_real_readiness_commit_and_local_publication`
with `degraded_environment: precommit_prewarm_failed`; **proved pre-existing** by reverting both source
files and reproducing the identical failure (the Q78/E263 sandbox blocker, not this change).

**Static gates (actual output).** `ruff check src tests` → `All checks passed!`; `ruff format --check
src tests` → `507 files already formatted`; `mypy src/fa/execution` → `Success: no issues found in 19
source files`; `pyrefly check src/fa/execution` → `0 errors`.

**Declared kills — 9/9, assertion-only, source restored by sha256 after each mutant.** Mutants and the
test that killed each: validator call removed → the link case; terminal-receipt precondition removed →
the open-view/receipt case; generation equality removed → the generation case; plan boundary removed →
the direct plan case; tombstone derivation removed → the tombstone case; recompute replaced by the
stored hash → three recompute/tombstone/link cases; `SEALED` write removed → 10 cases; reply id unbound
from the record → two cases; new-link rejection removed → the link case.

**Two masked producers found by the sweep, and how each was handled (the E259/E262 pattern).**
1. *Terminal-receipt precondition.* `mark_sealed` repeats the check, so removing it from
   `prepare_seal` was invisible. The real difference is a durable side effect: the manifest would be
   written for a view whose terminality was never proved. The case now asserts the absence of
   `sealed.json` after the refusal, which is the property that matters, and the kill is attributed to
   that assertion.
2. *Plan boundary.* End-to-end it is **fully masked** by `prepare_seal`'s `ProtectedPlanContext.recheck`
   (a WRITE view's context roots at its own source, so an edited plan never reaches the manifest rules).
   The rule is kept as manifest-level defence and given its own direct oracle; the kill is recorded as
   unit-level, not as an end-to-end seal-flow win. Also verified while doing this: the recompute
   mutant (6) is not masked — it fails three independent cases.

**Recorded findings.** (1) `_TREE`/`_ENTRY` cannot express tombstones (`deleted` pinned `false`) and
carry `revision_id`, so the seal manifest needed its own schema — extending the revision format would
have widened what readers verify. (2) The wire id prefix (`seal-`) and the persisted record prefix
(`manifest-`) disagreed; the record moved, the wire did not. (3) A `SEALED` view re-enters
`prepare_seal`, so the idempotent path answers from durable bytes and compares the *recomputed* digest
with the stored one, which is what catches a rewritten manifest. (4) The expected-sha/link rules that
`_Capture` already enforces are reused, not re-implemented.

**Not closed.** SLICE3 STEP1 stays open: Q74's per-stage checkpoint policy, the real Docker/cgroup
`CellTermination` observer and `tests/integration/test_publication_recovery.py` under
`FA_REQUIRE_EXECUTION_HOST=1` are untouched. STEP2 (publish/CAS/projection, CT106) is E268; STEP3
(bundle/Q58/BOOTSTRAP + candidate-buffer seal), STEP4 (recovery, CT107) and STEP5 (whole-bank kills)
remain. `STOP_VIEW`/`SEAL` still have no dispatcher route. No STEP box, FUNCTIONAL contract, live row
or E223 acceptance duty is closed by this work; the SLICE2 STEP3 provisioning leg stays open until
publish lands.

### E277 result — SLICE1 STEP3 part 2: the composed supervisor (route table, socket owner, `main`)

**What shipped.** A new `src/fa/execution/service.py` owns the composition and the private UDS:
`ServiceConfig` (strict, no defaults for trust inputs), `load_config`/`read_config_file`, and
`SupervisorService` — the real `WorkspaceAuthority`, its journal, the completed-reply cache, the
`SupervisorDispatcher` and the one socket. `supervisor.build_supervisor(config)` and `supervisor.main(argv)`
are the §2.2 names and are thin over that object. Two authority additions were required by the wire
schema: `ready` (the `health` fact, true only after flock + `recover_uncertain` + `_load`) and
`release_writer(capability)` (the `release` payload is empty, so only the proved grant can name the
binding; it and `release_unused_writer` now share one `_settle_owner`). `profiles.profile_set_sha256`
is the canonical digest of the enforced profile set.

**Route table (nineteen rows, derived names, checked for totality at construction).** Live against a
real owner: `health`, `register_workspace{create:false}`, `acquire_writer`, `pin_reader`, `create_view`,
`read_file`, `write_file`, `edit_file`, `release` (pin or owner), `stop_view` (close + drain only),
`seal`, `publish`, `prepare_bundle`, `install_project`. Declared dormant with an explicit
`BACKEND_UNAVAILABLE` refusal and the activating unit:

| route | why it cannot be honest yet | activated by |
| --- | --- | --- |
| `exec`, `inspect`, `cancel` | `CellBackend` returns a `CommandOutcome`; there is no `ExecutionReceipt` issuer and no independent (cgroup) terminal barrier, so `EXITED` could not be asserted truthfully | receipt issuer + terminal barrier unit |
| `pty_control` | `WorkerClient` has `begin`/`await_reply`/`request`/`close` only — no list/interrupt/close verbs scoped to an episode | PTY control unit |
| `handoff` | no `WorkspaceAuthority.handoff` exists at all | owner-handoff unit (terminal/settled source, parent-child proof) |
| `register_workspace{create:true}` | only `register_existing` exists; creating a root is managed acquisition | SLICE5 |

**Current vs target behaviour.** Current: the service starts only with an explicit config, completes
recovery before binding, serves one request per connection over a 0600 socket, and answers every
operation with either its real owner's exact closed reply or a closed-code refusal. Target (unchanged):
STEP3's exit also needs the install/image/entrypoint set, the real `CellBackend` composition behind the
execution routes and the disposable-host boot proof — so the box stays unticked.

**Why the publication half cannot complete yet.** `stop_view` has no `CellTermination` adapter, so it
returns `terminal: false` after really closing and draining; `seal` then refuses `TERMINALITY_UNKNOWN`.
That is the truthful consequence of the missing kernel observation, not a gap in the composition, and it
is why a `CellTermination` manufactured out of `CellBackend.episode_container` was deliberately **not**
written: "the container is gone" is not "its cgroup is empty".

**Evidence.** `tests/test_execution_service.py` 21 passed (C0 table/config/digest; C3 real socket + real
codec + real authority); owning bank 556 passed; wider `-k "execution or workspace"` 1563 passed, 1
skipped (3 known offline-install errors elsewhere); ruff/format clean, mypy 21 files, pyrefly 0,
`fa authoring-check` 0. 9/9 assertion-only mutants killed with byte-exact restore. `I03-LIVE-26` is
PLANNED / UNEXECUTED; no STEP box, contract or live verdict is ticked.

### E278 result — CT104's join: `CellTermination` over journal-owned cells + kernel `populated 0`

**What shipped.** `src/fa/execution/cgroup.py` (pure cgroup-v2 reader: both driver layouts, `O_NOFOLLOW`,
regular-file check, 64 KiB bound, exactly one `populated <int>` line; `True` only for `0`, `None` otherwise) and
`src/fa/execution/termination.py::OwnedCellTermination`, the `CellTermination` that `ViewStopper` was written for:
cells come from `OperationJournal.owned_cells()` filtered to the exact namespace and `ViewRef`, the stop goes
through `DockerCells.force_stop_operation` with the record's own operation id, and emptiness comes from the
cgroup. The composed service now always installs it: without Docker it can still prove a never-executed view
empty (a journal fact), and with Docker (`ServiceConfig` gained all-or-none daemon facts, `cgroup_root`,
`startup_timeout_ms`) it builds `CellBackend`, reconciles surviving owned cells before binding the socket, and
closes the backend on shutdown.

**Current vs target behaviour.** Current: `stop_view` reaches `TERMINAL` for views that never bound a cell, and
refuses (`BACKEND_UNAVAILABLE`) for one it cannot stop; `seal`, `publish`, `prepare_bundle`, `install_project`
and `release` are therefore reachable through the closed codec, proved end-to-end on real files. Target: the same
flow with a *real* worker/attach cell and a real cgroup — that is `tests/integration/test_publication_recovery.py`
under `FA_REQUIRE_EXECUTION_HOST=1`, still BLOCKED here. STEP1 stays open (Q74's per-stage checkpoint policy, the
host rows, and the exec half's receipt issuer), so no box is ticked.

**Why a view with a cell is still not sealed locally.** The stop leg is doubled at the `DockerCells` seam in the
local bank (C1); only a host run may claim the daemon actually signalled the cell and that its cgroup emptied.
`cells_terminal` returns `None` for any unreadable fact, so an unproved cell keeps the view `STOPPING` and owned.

**Evidence.** `tests/test_execution_termination.py` 20 passed; `tests/test_execution_service.py` 24 passed
(the publication half now driven through the wire); owning bank 387 passed; wider `-k "execution or workspace"`
1585 passed, 1 skipped; ruff/format clean, mypy 22 files, pyrefly 0, `fa authoring-check` 0; 14/14 assertion-only
mutants killed with byte-exact restore. `I03-LIVE-19/20/25/26` remain PLANNED / UNEXECUTED.
