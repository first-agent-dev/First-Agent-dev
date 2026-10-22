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
    shell through host subprocess. Preserve PtyResult fields/timeout; receipt status is truthful.
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
- [ ] STEP2: retain E249 native owned force-stop/observation (NOT a cgroup/terminal barrier); NEXT implement NEW CellBackend in execution/backend.py over existing DockerCells/WorkerClient/OperationJournal, with per-view live episode ownership, per-command begin/record_container and actual inspect/cancel/drain/restart facts per §2.2; join the actual SLICE2 admission gate before service composition, without a temporary authority (exit: two commands preserve shell state in one cell with two durable records; duplicate/lost RUN never resends; cancel-before-send and completed-creation/live-cell restart tests pass; no success/terminal receipt derives only from worker output)
- [ ] STEP3: prepare service/config/install/image and volume-map changes without activation; compose supervisor.py build_supervisor/main only with real WorkspaceAuthority and CellBackend, then SLICE3 publication handlers; apply controller read-only canonical mounts/private-UDS-only and entrypoint changes atomically with SLICE4 caller cutover, never before provisioner/file tools can operate (exit: no permissive/failing-main stub or alternate host runner; approved disposable-host test later boots that real factory and proves absent control mounts/secrets, denied profile/raw-path escalation and zero unavailable-backend project commands)
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
- [ ] STEP1: retain E245 internal execution/view_io.py and its real-descriptor C0/C3 bank per §4.2 E244 (no admission/CT completion claim); retain E253 actual WorkspaceAuthority protected existing-root registration/current/R0/writer generation/startup fencing; retain E255 actual immutable reader pins/rooted reads/release; retain E256 actual WRITE/PROJECT views/rooted IO; NEXT construct execution admit/close-admission/drain semantics per §§2.2/4.2, not a second lock service; reject root aliases/overlaps/rebind and quiesce before R0 (exit: two OS processes race for one workspace and exactly one obtains a durably advanced writer; denied/stale/closed admissions produce no launch/write; independent pins retain original bytes across generation changes)
- [ ] STEP2: retain E256 actual WRITE/PROJECT create_view/_materialize_input and rooted read/write; NEXT complete the four non-PROJECT view purposes and actual execution-admitted read/write/edit on retained descriptors per §§4–4.2 before provisioning consumes them. The purposes are exactly CANDIDATE, VERIFICATION, MUTATION, PROVISIONING (ViewPurpose in execution/types.py; PROJECT is the retained one). Extend create_view's request to the §2 table shape `{workspace_id,base_revision,access,purpose,candidate_scope,plan_ref}` with these exact admission combinations and no purpose switch: CANDIDATE requires plan_ref + exact candidate_scope `{candidate_path,plan_ref}` with identical top-level plan_ref (bytes live in supervisor staging per §5, never canonical .fa/admission); VERIFICATION/MUTATION require nonnull plan_ref (§3.1) and are read-only-source + private scratch; MUTATION is the single write-capable derivative for mutation checks (one permitted src/scripts target, trusted controller only, §6); PROVISIONING is the provisioning view (nonnull plan_ref NOT required) and runs only inside the manager's provisioning RunContext from STEP3; every other combination denies INPUT_POLICY before copy. Keep private-metadata chmod helpers off project parents; preserve dirty/staged/untracked/deleted bytes and canonical index, enforce copy/link/secret/size policy and private-Git limitations; consume STEP1 descriptor IO under actual admission, private same-filesystem staging and explicit profile/protected-PlanRef binding (exit: exact tree/index/sentinel oracles pass; link/special/limit/root-swap failures leave no returned grant or partial revision; expected-SHA conflict and post-admission rename do not silently succeed or touch canonical/control paths; one denied-combination case per forbidden purpose/scope tuple)
- [ ] STEP3: inject the managed provisioner into the existing SessionManager BEFORE `_new_session` calls `_provision_workspace` (this is the SLICE2 component injection; SLICE4 STEP2's repetition means routing the remaining inventory callers through the SAME provisioner at activation, never a second implementation); reserve its real provisioning RunContext via early existing DB/begin_run per §4.2; update both reverse-owner call sites (manager.py `_new_session` and `resolve_workflow_workspace`) for explicit registered references per CT103a and fail non-READY; preserve session DB/run reservations and validate legacy records under authority. The provisioner result contract is exact: a frozen result carrying `{registered: bool, workspace_id, revision_id, tree_sha256}`; manager cleanup may rmtree only `registered is False` scratch the provisioner itself created, and a registered/committed workspace is NEVER an rmtree target. `workspace_preparer` returns ReadyState and the manager treats not-READY as SessionManagerError("workspace_not_ready") in BOTH `_new_session` and `_attach_session` — no log+continue. The host-Git `_provision_workspace`/`provision_git_workspace` path is removed at injection, not retained as a fallback: new-workspace provisioning until SLICE3's publication join is an explicit typed BLOCKED disposition (provisioning_unavailable), while explicit registered reuse bypasses clone/readiness/remotes. The publication-dependent provisioning leg completes with SLICE3, not host Git fallback. SLICE2 half (exit): injection ordering test proves the provisioner runs before any `_provision_workspace` effect; new-session explicit reference to an existing registered workspace succeeds without transferring DB/history and one writer remains; corrupt manifests and legacy run-ID tests pass; provision failure and not-READY leave no active session; post-commit-failure cleanup never deletes registered bytes (covered with a registered=True provisioner result). SLICE3 half (exit, moves to SLICE3's evidence): DB/manifest failure AFTER a real workspace commit via publication keeps registered bytes intact and reports SessionManagerError.
- [ ] STEP4: wire actual tool builders and SessionState internal binding per §4.2: controller fuzzy matching/telemetry, supervisor rooted writes, same-view bounded reads and cell-local existing search/reach/PDF implementations; no new public tools/search service or private state mount; join real authority/backend factory before disposable integration (exit: actual registry tools and PTY observe each other's edits with blackboard on/off and zero host Git/version-stamp reads, active search sees a new symbol, reader search stays pinned, artifacts retain their controller path, PDF/binary/large/truncated/helper-unavailable results are explicit and no canonical fallback occurs; seal/import alias tests complete with SLICE3)
- [ ] STEP5: record CT101–CT103 whole-bank full-path producer kills plus same-inode/different-label contention, queued revoke/stop races, restart and cleanup; accumulate actual Docker/kernel runs for final SLICE6 without substituting unit fixtures (exit: every named producer removal breaks an executed assertion, including no late launch/write after closed admission; all required host cases non-skipped, exact source restored, no leftover live cell or lost pin)

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
- [ ] STEP1: implement selected Q74 per-stage/episode checkpoint policy and spec §6.1 stage transition table; implement terminal barrier/view state machine and immutable export validation in execution/publication.py plus supervisor.py::stop_view -> _wait_descendants_terminal (CT104's named producers). Test split is fixed, no guessing: the view-state machine and immutable export validation run in tests/test_workspace_publication.py over the real local worker/attach cells (E258's fixture pattern) and prove seal/publish is refused while any handler or cell is unsettled; the actual cgroup-populated-empty descendant barrier runs only in tests/integration/test_publication_recovery.py under FA_REQUIRE_EXECUTION_HOST=1 (kernel fact, never mocked). Tests launch fork/double-fork/setsid/background writers in real cells and hold active file operations (exit: none can seal/publish while still writable)
- [ ] STEP2: implement exact intent/current/projection schemas/order/dir fsync and generation/base CAS per spec §5, including canonical Git-index preservation and spec §5.1 exact Q58/bootstrap forward-recovery phases (exit: complete old/new pinned-reader and stale/fault unit matrix passes)
- [ ] STEP3: integrate the existing inner_loop/plan_promotion.py Q58 buffer/hash/promotion primitives and this authority's no-clobber bundle primitives (execution/publication.py::prepare_bundle / install_project, per §5's bundle handoff; §1 already assigns no-clobber project install to publication.py) with the same authority; no managed-acquisition UI/protocol before SLICE5 integration (exit: direct controller-authorized tests prove collisions preserve old bytes and post-commit failure never rolls back)
- [ ] STEP4: recover from supervisor/process death at each durable boundary, before/after pointer replace and during projection; require approved filesystem and separately label process-crash versus power-loss evidence (exit: real recovery tests expose only complete current revisions or quarantine, no success from uncertain state)
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
- [ ] STEP10: run local package conformance, every accumulated non-skipped execution_host suite and all17 full-declared-path kills, and full release gates; review environment/readiness and inherited baseline acceptance using retained I02 manifests, exact test identities/replacements and Mypy contexts, including the unreproduced historical ninth context and relevant hook observations. Resolve/explicitly disposition each item for the intended Ubuntu/Docker/Python deployment without falsifying red results. Only with maintenance/deploy authorization perform normal main update and reviewed host runs; inspect nonzero update before retry, verify actual deployed SHA/image/profile/config, execute spec §9.1 unmocked direct+nested workflow witnesses (not only deterministic provider-stub cases), record source-to-behaviour results and broad independent implementation/evidence review plus integrated signoff. No automated/harness PASS (exit: all four E223 acceptance obligations complete with recorded review; all required cases independently reviewed PASS; BLOCKED/NOT RUN/skip never counts)

## Increment definition of done — binary, no partial isolation claim

- [ ] All six local verify blocks collect their required tests and exit 0; required execution_host
      runs use FA_REQUIRE_EXECUTION_HOST=1 and cannot succeed by skipping unavailable Docker/profile.
      All 17 FUNCTIONAL full-declared-path kills have useful executed failing oracles, provenance,
      elapsed cost and restored source; errors do not count as kills.
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
