---
Increment-ID: RM-planning-topology-I03
Roadmap-ID: RM-planning-topology
status: OUTLINED
slices: 6
shipped: —
---

# INCREMENT I03: Execution/workspace foundation and integrated acceptance

**Planning state:** finalized after E230 adversarial review and E231 operator answers/source audit.
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

**Source truth:** use `1132eee`/I02 E229, not the old d910 line inventory. The original 17 FUNCTIONAL
IDs remain; new private interfaces are obligations to implement/test, not existing-code assertions.
Spec §§2.1/4.1/5.1/6.1/7.1/9.1 are part of every affected STEP's contract, including error/restart
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
TESTS: tests/test_controller_entry.py, tests/test_controller_installed.py, tests/test_execution_supervisor.py, tests/test_execution_protocol.py, tests/test_execution_client.py, tests/test_execution_cell_worker.py, tests/test_execution_journal.py, tests/test_execution_dispatch.py, tests/test_execution_plans.py, tests/integration/test_execution_boundary.py   (NEW)
```verify
uv run pytest tests/test_controller_entry.py tests/test_controller_installed.py tests/test_execution_supervisor.py tests/test_execution_protocol.py tests/test_execution_client.py tests/test_execution_cell_worker.py tests/test_execution_journal.py tests/test_execution_dispatch.py tests/test_execution_plans.py -q
FA_REQUIRE_EXECUTION_HOST=1 uv run pytest tests/integration/test_execution_boundary.py -q -m execution_host
uv run ruff check src/fa/controller_entry.py src/fa/execution tests/test_controller_entry.py tests/test_controller_installed.py tests/test_execution_supervisor.py tests/test_execution_protocol.py tests/test_execution_client.py tests/test_execution_cell_worker.py tests/test_execution_journal.py tests/test_execution_dispatch.py tests/test_execution_plans.py tests/integration/test_execution_boundary.py
```
- [ ] STEP1: implement spec §2.1 closed operations/results (including all four BashExecutor methods), capability/volume-map/startup recovery contracts; define frozen types/protocol/profile validation and new actual controller entry module per spec §§1–3; test strict keys/types/limits and installed import closure, including editable-pth/CWD/PYTHONPATH poisons (exit: unit tests collect and pass; isolated module executes real CLI help, not a no-op)
- [ ] STEP2: implement supervisor service/client/cell worker using existing PTY machinery, approved profile and operation reservation/inspect/cancel; remove no behavior from ordinary PTY contract (exit: unit no-replay/timeout/wire/auth tests pass)
- [ ] STEP3: add service/config/install guidance, immutable image and wrapper/entrypoint changes; make canonical /sessions read-only in controller, keep supervisor StateDirectory unmounted, expose only private UDS, and freeze approved host↔controller↔cell path mappings; root-only fixture setup launches real isolated disposable cell, not a fake Docker response (exit: execution_host proof shows absent control mounts/secrets, denied profile/raw-path escalation and zero project commands when backend unavailable)
- [ ] STEP4: record real profile/image/kernel/daemon/cgroup facts and source-restored full-path CT98–CT100 mutation outcomes/cost (exit: all required tests non-skipped; each named producer deletion breaks an executed oracle)

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
    edits are mutually visible; no separate stale copy or direct canonical write. Spec §4.
    kill: remove-call src/fa/execution/workspace.py::WorkspaceAuthority.write_file -> _write_rooted
  CT103a [CONSTRAINT]: SessionManager permits explicit new-session reference to an existing
    registered workspace without transferring session DB/history ownership; one writer remains.
    Validate legacy manifests/run bindings; no blanket guard removal or second session manager.
    Future children inherit parent ownership/view/cancel scope; workflow subagents stay absent.
TESTS: tests/test_managed_workspace.py, tests/test_session_lifecycle.py, tests/integration/test_workspace_views.py   (NEW)
```verify
uv run pytest tests/test_managed_workspace.py tests/test_session_lifecycle.py -q
FA_REQUIRE_EXECUTION_HOST=1 uv run pytest tests/integration/test_workspace_views.py -q -m execution_host
```
- [ ] STEP1: implement protected registration/current metadata, flock/generation/pin/view authority and strict rooted IO; reject alias/ancestor/descendant re-registration and root rebind (exit: cross-process writer contention, stale generation and reader-pin unit tests pass)
- [ ] STEP2: update SessionManager ownership/provisioning integration per spec §4; replace old second-owner rejection test with explicit registered reuse plus busy-mutation/corrupt-manifest negatives; preserve old run-ID claims (exit: actual session lifecycle suite and new/resume/new-session-reuse matrix pass)
- [ ] STEP3: materialize dirty input and explicit copy policy; preserve canonical index, safely handle/exclude links/credentials/caches, document private-Git history limitation (exit: dirty/staged/untracked/deletion and external-link/hard-link/special/limit cases pass without silent omissions)
- [ ] STEP4: wire actual read/search/write/edit handlers/transaction observations to ViewRef and service IO; exercise shared PTY/file visibility and protected target/ancestor rename/import denial (exit: real execution_host view tests pass; parent pinned reader sees old complete revision)
- [ ] STEP5: record CT101–CT103 full-path producer kills, same-path different-label contention and bounded cleanup/source restoration (exit: all unique named oracles fail when their producer is removed; no leftover live cell)

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
- [ ] STEP1: implement selected Q74 per-stage/episode checkpoint policy and spec §6.1 stage transition table; implement terminal barrier/view state machine and immutable export validation; tests launch fork/double-fork/setsid/background writers in real cells and hold active file operations (exit: none can seal/publish while still writable)
- [ ] STEP2: implement exact intent/current/projection schemas/order/dir fsync and generation/base CAS per spec §5, including canonical Git-index preservation and spec §5.1 exact Q58/bootstrap forward-recovery phases (exit: complete old/new pinned-reader and stale/fault unit matrix passes)
- [ ] STEP3: integrate Q58 buffer/hash/promotion and no-clobber bundle primitives with this same authority; no managed-acquisition UI/protocol before SLICE5 integration (exit: direct controller-authorized tests prove collisions preserve old bytes and post-commit failure never rolls back)
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
- [ ] STEP2: retain _cmd_run signature as pure validation→run_stage_with_plan_write_boundary→_cmd_run_inner; wrap whole _cmd_run prologue and route manager/entrypoint/bootstrap readiness through provisioning cells; remove fail-open readiness and host fallback paths. Inject the managed provisioner into SessionManager BEFORE _new_session provisioning; no rollback deleting supervisor-owned registered roots. Wire project Git/pair/subagent paths too (exit: backend-down run across each inventory route executes zero project commands; no unsupervised legacy bind/process)
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
