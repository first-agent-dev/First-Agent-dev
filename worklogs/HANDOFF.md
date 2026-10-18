# HANDOFF.md — next agent/session

> Read [`knowledge/llms.txt`](../knowledge/llms.txt) §MUST READ FIRST.
> Current local delivery is distinct from final I03/deployed acceptance.

## Current state — I02 LOCAL SHIPPED / I03 IMPLEMENTATION IN PROGRESS, 2026-10-18 / E257

Branch `arena/86633f17-first-agent-dev` only. Retained I02 runtime/test proof snapshot
`a32a72fc58db4b9a5b048a9b6475649bcf3e32b4`. E230/E231 finalized planning; E232 adds the first
I03 source/test chunk described below. Retained I02 implementations/evidence remain unchanged.
I02 is **locally implemented and diff-reviewed, pending E2E tests as I03 ships**.
Read the [final local record](planning-topology-and-executable-contracts-loop/notes/i02-local-acceptance.md),
[retained plan](planning-topology-and-executable-contracts-loop/increments/increment-02-verify-gate-and-kill-checks.md)
and [current inventory](planning-topology-and-executable-contracts-loop/notes/evidence/i02-e229/manifest.json).

**Review:** all43 changed Python files versus d910 reviewed;flow IO/eval/stale receipts, dispatch
boundary deadline, T0 runner/report disagreement, missing observe evidence and unexpected capture
exceptions fixed.125 added review cases pass. Q73 explicitly selects hard-blocking indeterminate
completion in both modes;determinate observe remains advisory,Q56 actual negative routes/report
preserved. Peer help-example defect NOT reproduced:all5 existing examples parse, no pointless fix.
Strict extractor/Q45-B behavior unchanged;test replacement intent reviewed,no new skip/xfail.

**Proof:** actual1002pass/no-skip baseline completed before all29 final affected SLICE5/6 runs:
22FUNCTIONAL+6SUP+1 external exception-revert control killed.23 SLICE6 runs each execute596 cases.
19 unchanged earlier leaf proofs (18FUNCTIONAL+CT79) retained/revalidated, not new executions.
All40 retained FUNCTIONAL covered. Root-file hash-glob omission discovered/fixed in external audit;
corrected v2 hashes every tracked Python source/test/script, preserving original baseline UUID/
timestamps and explicit Git-body validation. Incomplete/rejected attempts remain diagnostic.
Lossless original artifacts/manifests/provenance/commands/hashes retained in E220/E224/E227–E229.

**Actual final wrapper:** just check rc1;5158pass1fail12skip1xfail/5172;all other blocking subgates
pass,CLI27floors/78functions separately pass. Exact d910 comparison:0new failure,1common,
8baseline-only,6superseded IDs,701new. Common readiness rc75/precommit_prewarm_failed remains red;
no blanket environment/baseline PASS. Historical ninth Mypy context remains unreconciled despite
current450-file configured Mypy passing. Foreign208-byte Arena commit-msg hook is not replaced.

**Still INCOMPLETE — final I03 SLICE6:** deployed source-to-behaviour verification;environment/
readiness/inherited-baseline acceptance;broad independent implementation/evidence review;integrated
E2E/deployment signoff. I03 remains OUTLINED/undelivered,all four successors unchecked. No Docker/
Ubuntu host test,OS isolation,managed nested acquisition or host supervisor delivered here. Python
only;Go is an indirect inherited hook-build diagnosis,not a new FA runtime/deployment requirement.
PTY stays. Q69–Q73 resolved;Q72 remains its narrow46-links/15-files+banner repair decision.

**E257 CURRENT — actual dispatch admission/close/drain; CellBackend/cutover NEXT:**

E257 first corrected the reporting defect behind ten repetitive SLICE1 checkpoints: E232-E256 are
local component implementations, NOT 1-2 completed whole contracts per checkpoint, and SLICE1
presentation hid a real dependency order (authority is SLICE2, factory needs SLICE3, activation
joins SLICE4). The explicit order is now recorded: admission/close/drain, then CellBackend
episodes/one-send/cancel/restart/independent terminality, then other view purposes and
seal/publication, then the real factory and atomic caller/mount cutover, then local full-path
proof. Final live acceptance stays at SLICE6. No completion checkbox changed.

E257 implements real authority-owned command-dispatch admission inside the SAME WorkspaceAuthority:
admit() checks the live view proof, approved profile/timeout/mode, the original uncancelled
journal claim and one-shot operation identity, and retains the operation id durably in view.json
BEFORE any effect. WorkAdmission.effect() rechecks view/gate/journal/input identities under the
original deadline; send() adds a read-only journal send guard so a persisted cancel linearizes
against ONE bounded RUN frame write, never against reply waiting. Create/start keep their own
once-guards; no scope wraps command output or terminality. Trusted inputs are real paths with
pinned identities: WRITE/PROJECT uses the materialized working source plus private scratch; READ
gets its own bounded materialized readonly projection and private scratch, never the service0600
immutable revision. The approved dependency cache is private operator DI, absolute, service-owned,
not group/world writable, rejected when it is a project root or the control state directory, and
validated BEFORE any projection copy. READ projections are re-digested against the retained tree
hash; substituted source/scratch/cache paths fail closed. PlanRef is rechecked at the effect
boundary for both access kinds.

close_admission() is irreversible: it closes the view gate, persists STOPPING with readback and
fences the owner on retention failure. It is NOT stop, terminality or release. drain() waits for
admitted work with the original deadline and never releases the writer, deletes source or asserts
process death; expiry is BACKEND_UNAVAILABLE. The same gate governs file handlers, so a closed
view denies read_file/write_file while other views stay usable. A reader holding execution
references cannot be released as an unused file-only pin. Shutdown closes gates and waits for
admitted scopes before releasing descriptors, so live native FDs survive until their scope retires.
Journal lookups and the send guard are capped by the caller's absolute deadline.
40 new native C0/C3 cases; focused 260 PASS 5.84s. Whole 19-module owning bank 965 PASS 47.8s ->
thirteen whole 965-bank assertion-only kills 1/3/6/1/5/1/2/1/1/1/1/17/2 -> restored 965 PASS 48.5s;
clean collection/setup/teardown, no warning/skip/runtime/infra credit. All 602 frozen source/input
hashes restored exactly. Ruff/format/Mypy clean; configured Pyrefly 0 errors with existing
141 suppressed/50 warnings. Broader 31-module 1485 PASS 62.19s. A native partial-send uncertainty
defect (owner left healthy) was reproduced, repaired and covered before acceptance; the pre-fix
failure is retained without credit. Repository tracking was restored from the verified remote
commit b862632 after verifying all 1398 remote files matched the working tree byte-for-byte.
Evidence `notes/evidence/i03-e257/admission.json.gz`, 2393565 bytes SHA256
92ec2742c043cf914edb9610f0dad8b4312391d35e95cc08528cf9ae79f63275.
NOT shipped: CellBackend episodes/one-send ownership/cancel/restart/independent terminality,
candidate/verification/provisioning view owners, seal/publication/forward recovery, real
factory/main and atomic caller/mount cutover. SLICE1 NOT shipped; all 35 STEPS/four final duties
remain open; all 17 surfaces/eight joins live PLANNED/UNEXECUTED at final SLICE6. No early host
prerequisite and no new policy or routing mode.

**E256 retained — actual PROJECT views/rooted writes:**

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

**E255 retained — actual reader owner implemented; writable views/admission/backend NEXT:**

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

**E254 retained — positive genesis implemented; actual pins/views/backend NEXT:**

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

**E253 retained — actual existing-root/R0/writer owner implemented; SLICE1 NOT shipped:**
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

**E252 retained — worker handoff repaired; broader1253PASS at that source:**
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

**Next (implementation, no host approval prerequisite):**
1. Retain E253/E254 registration/writer epochs, E255 immutable readers, E256 PROJECT working
   views/rooted IO and E257 dispatch admission/close/drain with the approved profile/path triple.
   NEXT actual CellBackend episodes/per-command begin/one-send/cancel/restart and independent
   terminality, joined to the SAME authority; no temporary authority or second journal.
2. Then other view purposes, seal/publication/recovery, real factory/main and the atomic
   SessionManager/tool/caller/mount cutover. No permissive or failing-main stub.
3. Q77 is resolved and implemented. Keep full-path Linux/Docker/deployed acceptance at final SLICE6.

**E251 retained historical result — explicit composition seam implemented; broader RED at that source:**
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

**E250 retained — E2E ledger inventory verified/repaired:** source diff exactly14 added Python
modules +2 modified production surfaces, now16 explicit planned live rows +8 joins in existing
E2E register, with SHA/AST evidence and16 omission controls. No live verdict. Next repair the
spec§2.2 dispatcher peer/deadline seam before actual backend/authority construction; all owners,
SLICE2 and final SLICE6 duties remain open. No blocking policy question found in this audit.

**E249 retained — native lifecycle implemented; SLICE1 NOT shipped:**
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

**E247 retained — first menu repair implemented, SLICE1 NOT shipped:**
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

**E246 retained verification — SLICE1 NOT shipped at437ee25:** user asks to verify updated contracts, put missing
steps next and implement. Source confirms backend.py/CellBackend, workspace.py/actual admission,
supervisor factory/main/listener and boundary integration suite absent. Docker is create/inspect/
attach only; episode/cancel/drain/restart and actual host facts remain. Client127–129 incorrectly
maps every ERROR to rejection, including unknown/unavailable. E246 directly records the remaining
menu in increment and fixes target error taxonomy in spec BEFORE implementation. All four SLICE1
STEPS/all35STEPS/four final duties stay open. No early host/deployment request.

**E245 retained — docs-first, then internal rooted IO:** E244/a7ba6d5 was committed/pushed before
source. `execution/view_io.py` now provides pinned descriptor/no-follow bounded text read/write,
complete SHA/windows, expected absence/SHA, private no-clobber staging/parent creation, safe cell
UID/GID/modes and explicit conflict/durability uncertainty. No existing project parent chmod/chown.
Internal building block only: NOT WorkspaceAuthority/admission/materialization or tool/PTY C1.
93 real-FS C0/C3 cases,17 full93-bank assertion kills; restored93PASS and exact518 Python/build/lock
hashes. Ruff/format26,Mypy26/183PASS; configured+clean Pyrefly0errors(existing141suppressed/50warnings).
Broader27modules1001PASS50.19s, clean phases/no skips/warnings. Initial uncertainty/owner-bound defects
fixed; rejected/superseded proof and reporter-origin/missing-tool-PATH diagnostics retained, not credit.
[Evidence](planning-topology-and-executable-contracts-loop/notes/evidence/i03-e245/rooted-io.json.gz)
contains tested sources, raw phases/runners/restoration, rejected trials and local toolchain provenance.
Archive1514276bytes SHA256d3c09ff2dcfa854470144741ea548da9dee74874d2e5022527a71933dda01057.
Final source/test freeze93PASS0.65s/restored93PASS0.74s; doc309PASS/35unchecked. Read-atime excluded
from the preserved-metadata oracle, other byte/metadata assertions retained; huge test inputs use
bounded parameter IDs. Lossless earlier diagnostics remain nested/compressed in the archive.
Python3.13.16/frozen dev deps restored outside application dependencies; zlib header1.3.1/runtime1.2.13
explicit, not a claim of identical prior environment. No live deployment or full-repository gate run.

**E243 retained — mid-slice review completed, not SLICE1/2 acceptance:** reviewed E242/e736082
against remaining SLICE1 + next SLICE2 and real callers. Eight evidence-anchored findings F20–F27
in existing adversarial review. Directly rewrote all nine affected STEPS/CT103/source baseline and
spec §§2.2/4.2: one admission/drain owner, existing journal begin per reused command, original cell
creation identity, startup drain even creation-DONE, writer read-your-writes versus independent
pins, cell-local existing discovery/PDF with scratch indexes, private metadata IO versus project
modes, committed-workspace cleanup ownership and real provisioning namespace before first RPC.
No extra journal/session DB/search service/workflow mode or early-host approval prerequisite.

F20 actual short-RPC/long-command reply defect repaired in protocol/client/supervisor only. Command
budget adds ONCE to original absolute transport deadline after short-budget connect/request send; no expired-frame revival,
control/profile-policy extension, clock reset or replay. This does not implement backend deadlines,
authority, terminality, service activation or all target behavior. Fourteen new C0/C3 fixture cases;
existing assertions retained. Owning481PASS34.21s/restored481PASS34.01s; nine whole481-bank assertion-only
kills1/1/1/1/2/1/3/1/1, clean phases, exact198 hashes. Ruff/format24 and Mypy24/182PASS, full Pyrefly0errors
(existing141suppressed/50warnings), clean-PYTHONPATH also0; broader908PASS48.03s. Initial fixture/new
assertion mistakes rejected/corrected, not proof. Passing v1 proof retained as superseded after final
input/reply phase tightening; final changed source re-proved with the extra phase mutation. Evidence/
runners in notes/evidence/i03-e243. Final audit0FAIL6WARN/6slices17FUNCTIONAL35unchecked,
kill grammar clean/doc309PASS/diffPASS; old assertions/ledger preserved and198 hashes exact.
Final repair SHA256728a228c8f9e1ecf10400bb8a90f2a996ed089556b5f9b83c670bc6ea702c587;
verification+closure SHA25659cfc0cba71d2457cd1d5d275f63f784eda8b16de2a15339ec462fdc7d33262e.

NEXT MENU (SLICE1 first): E247 client classification and E249 native force-stop legs implemented.
E251 explicit authenticated peer/deadline propagation and E252 worker handoff repair are
implemented (broader1253PASS at E252 source; E251 red retained). E253 actual existing-root/R0/
writer ownership is now implemented; NEXT add pins/views/admission/drain, then the actual
CellBackend protected per-view episodes/per-command begin/CID/worker
control/restart together with the ONE actual WorkspaceAuthority admission/drain (necessary SLICE2
dependency). Take authenticated peer + one absolute deadline through this real join; no permissive
callback, fake grant issuer, second history or further rooted-IO helper rebuilding. Actual startup
cell discovery including creation-DONE, per-command cancel routing and descendant/cgroup barrier
remain unimplemented. Then real service/config/install factory (publication leg SLICE3), atomic
SessionManager/tools/wrapper/mount cutover SLICE4. Required actual host/kernel/full-path release
proof remains final SLICE6. All35STEPS/17FUNCTIONAL/four final duties unfinished; Q59/Q75/Q76 intact.

**E242 retained continuation:** actual fixed native Docker Upgrade/stdin/stdout/stderr attach now
joins owned journal inspection to shared cell codec + WorkerClient. Preserves bytes after HTTP
headers, non-TTY mux fragments, bounded stderr diagnostics and per-response (not lifetime) caps.
One RUN plus concurrent control, independent deadlines, exact reply/session binding, all-pending
uncertainty on stream loss, no fallback/reconnect/resend. Existing persistent/one-shot worker share
the codec. Native actual local PTY/worker joins are C0/C3, NOT Docker/kernel/authority/C1 proof.
Configured Pyrefly20errors repaired across execution foundation without suppression; explicit
validated ViewRef fields/overrides, old test assertions preserved. Focused125PASS5.69s before freeze.
Initial fixture race/fork warning and mixed runtime/assertion mutation were rejected, never proof;
raw diagnostics/rejected whole-bank attempt retained in i03-e242.
Final owning14modules467PASS34.34s/restored467PASS33.49s, ten full467assertion kills1/1/1/1/1/1/1/1/5/1,
clean phases/no skips/warnings/exact restore. Ruff/format24 + Mypy24target/182source PASS; configured
Pyrefly0errors (existing141suppressed/50warnings), no new suppression. Broader26modules894PASS49.46s,
all phases clean incl6 real Pyrefly cases. Driver expected892 miscount corrected only after retaining
original rc1/incomplete records + raw rc0/894 results; completion validates IDs/phases/sources, does
not rerun/relabel tests. Final audit0FAIL6WARN/35unchecked/doc309PASS/diffPASS; all198 hashes exact,
protected unrelated groups preserved. Evidence i03-e242 contains raw reports/sources/runners/primary
provenance. No service/host dispatch/cutover or acceptance tick.

NEXT: protected exclusive episode registry + durable per-command backend dispatch/control, actual
Docker cancellation/kill, lifecycle/reconciliation/cgroup barrier; real WorkspaceAuthority/controller
bridge; service/config/provisioner/wrappers. WorkerClient/attach_created are NOT fresh authority,
durable at-most-once admission or receipts. Reuse original live cell/creation binding for later RUNs
with new command reservations; NEVER reattach to reconstruct a lost command or memory-only Q75
reply. Stream/STOP ACK/local one-shot return/empty PTY registry are not actual terminality. All35STEPS
and four final duties remain incomplete; required host/full-path acceptance stays final SLICE6.

**E241 retained continuation:** private DockerEngine now performs authenticated bounded Unix HTTP
create/start/owned-inspect calls; DockerCells requires resource validation and journal create_once
persists UNKNOWN before create, CID before start. No TCP/env endpoint/pull/retry/redirect. Lost
create/start reply cannot regain launch permission; original-name/ID inspection stays read-only.
Identity/name/labels/pinned reference verified, actual image config ID reported (not approved image
facts); provisional non-exited codes withheld. Start ACK returns CID, NOT receipt/command success.
Native Unix HTTP fixture + actual journal persistence/concurrency/fault tests are C0/C3, not Docker
or kernel proof. Owning13modules415PASS32.38s/restored415PASS32.11s; ten full-bank assertion-only
kills2/6/2/1/3/2/2/1/7/1, clean phases/no skips/warnings/exact restore. Ruff/format21 + Mypy21/180
PASS; broader24modules836PASS42.82s, clean. Final audit0FAIL6WARN/35unchecked/doc309PASS/diffPASS;
tested hashes exact, unrelated source/dependency/wrapper groups preserved. Evidence i03-e241 incl
full primary API provenance. Peer auth is not actual daemon endpoint-exposure/host-facts approval.

NEXT: actual protected episode registry + attach/worker command/control, Docker cancellation/kill,
lifecycle/reconciliation and descendant barrier, then real WorkspaceAuthority/controller bridge,
service/config/provisioner/wrappers. launch_new is NOT per-command exec: reuse the original live
interactive cell and creation binding; each command still owns its operation/input reservation.
Do not install CID-returning launcher as exec handler or pretend injected validation is authority.
No production main/cutover or host approval request. All35STEPS/four duties remain incomplete;
required actual-host/full-path acceptance remains final SLICE6 under the existing schedule.

**E240 retained continuation / rollout correction:** operator reaffirmed ALL systems must implement
the plan's TARGET contracts; resolve contradictions first, not replace target behavior with helper
scope. Existing **Verification schedule** already allows construction in dependency order while
host/full-path safety acceptance remains outstanding for final SLICE6. No deployment, Actions job
or live-host test was started; earlier host-choice request was premature and is not pending.
DO NOT ask for an early deployment host or a redundant slice-sequence decision. Actual authority
integration follows the existing spec; no temporary permissive authority or failing main stub.

F19 corrected: noninteractive profiles now select a fixed private one-shot worker, exactly one RUN,
determinate command exit propagation, failure/timeout never synthetic success; interactive PTY
sessions/control preserved. Worker/PTY close STILL is not a descendant barrier. Local C0/C3 only,
including actual PTY and main path with fixed cell-mount paths substituted; no Docker/C1 proof.
Owning12modules361PASS31.70s/restored361PASS30.48s; three full361kills1/1/8 CALL assertions, clean
phases/no skips/warnings/exact restore. Ruff/format19 + Mypy19/179source PASS; broader23modules
782PASS44.40s, no skips/warnings. Raw sources/reports/static in notes/evidence/i03-e240.

NEXT TARGET WORK: implement actual Docker control/attach/lifecycle/inspection/reconciliation with
protected resource bindings, real WorkspaceAuthority and controller bridge, then private service/
configuration and safe provisioner/wrapper cutover under the approved dependency sequence. No
project host fallback/temporary issuer; no unsafe readonly-/sessions switch while legacy prologue
still writes there. Construction and later integrated acceptance tracked separately; all35STEPS/
four final duties remain unfinished. Q76(a) stays resolved and must be carried into actual metadata.

**E239 retained foundation:** Q76(a) is explicitly APPROVED (`view_bound_nullable_ordinary`),
recorded RESOLVED and constructed at C0/C3: required nullable admission PlanRef, candidate equality,
frozen trusted plan context, actual bounded/no-follow source recheck before fresh reservation,
receipt plan binding before DONE/cache. Ordinary no-active-workflow null allowed; formal evidence
needs actual admitted plan. Seven-field ViewRef/Q59/Q75 unchanged; no public mode/root/policy flag.
Owning12modules347PASS28.65s/restored347PASS28.54s; six full347kills4/6/3/1/2/1 assertion failures,
clean phases/no skips/warnings/exact restore. Ruff/format19+Mypy19/179source PASS; broader23modules
768PASS39.87s incl existing PlanRef regressions and actual installed CLI. Raw final/static/history
in notes/evidence/i03-e239; initial oracle TypeError rejected and retained, never final kill credit.

Actual protected view persistence/loader, namespace/root ownership and controller-admission bridge
remain under real WorkspaceAuthority integration. Context construction is NOT authority/C1 proof;
formal policy must come from protected admitted execution context, not be inferred false from null.
No actual issuer, complete Docker backend/reconciliation, service main/unit, integrated wrappers/provisioner
or approved host image/UID/cgroup/cache facts. No fake authority/main or premature writable legacy
cutover. The existing spec already permits C0 injection before SLICE2 authority: do not ask a
redundant sequencing question, and do NOT ask Q76 again. All35STEPS/four final duties remain open.
I02 inner_loop/session, lock/pyproject and runtime wrappers/compose unchanged by E239.

**E238 retained history:** immutable Docker build/install gate and actual installed CLI proof were
committed/checkpointed before Q76 was asked. Broader702PASS and owning294PASS retained unchanged.
No Docker image build or host proof. The F18 recommendation was OPEN then; E239 above supersedes
that question status without rewriting old evidence.

**E237 retained continuation:** durable secret-free journal and per-connection UDS dispatcher now
constructed, with required injected authority/backend, one-claim/cancel/start guards and Q75 replay.
Final286case bank + eleven developmental full-bank kills pass/kill with clean restoration;
static14target/178source pass. No main/issuer/real ownership/Docker/cgroup proof. Existing spec
already allows C0 construction before SLICE2 authority; do not ask about that settled sequence.
E238 immutable Docker install/build gate and actual installed CLI tests are in progress/uncommitted.
F18 active PlanRef/ordinary-nullability join remains collected; exhaust independent work first.

**E236 continuation:** fixed profile renderer, single-attempt peer-authenticated UDS client,
all four managed PTY methods, full receipt binding and real cell-local PTY module now exist.
219case baseline/restored pass without skips/errors/warnings; nine developmental full-bank
mutations killed with exact restoration; installed-entry30cases rerun. Raw evidence/review/ledger
record scope. No production factory/service/authority/kernel proof or STEP/CT completion.
Independent journal is in progress; finish it before asking about the collected authoritative
PlanRef/receipt metadata join. Profiles need actual host approval, not unit fixture defaults.

**E235 retained continuation:** complete19-operation wire/result/error codec and full immutable
receipt/operation data now exist.72new+64existing C0/C3 tests pass; eight developmental full136case
mutations killed with zero runner/collection errors/skips and exact restoration. Details/evidence
in the review/ledger. No service/authority/kernel proof. Follow the operator request to exhaust
independent tasks before questions. No Docker CLI/socket in this sandbox; external supported
Python3.13.16/frozen dev rebuilt. Profile/client/dispatch and deployment joins remain unfinished.
All35STEPS/four final duties unchecked. E234 replay policy remains ratified, never reopen Q75.

**E234 retained action — Q75(a) SELECTED, IMPLEMENTATION RESUMED:** the operator explicitly
selected `exact_cached_replay`. Same authenticated principal, namespace, original request/input
and original proof may recover ONLY the original memory-cached completed reply after that handoff
revoked proof. No fresh work, re-execution, renewal or durable-secret reconstruction. Cache loss/
restart blocks until safe reconciliation; IDs do not authorize. E233/F17 remains historical evidence
of a specification join defect, not a demonstrated runtime vulnerability. Tracker/spec/plan aligned.

New src/fa/execution/{types,supervisor}.py implements immutable identity/grant-result data and a
bounded completed-grant-reply cache. Proofs compared in constant time; journal projection omits
capability and checks known issued/original secrets before durability. Cache duplicate result
replacement is denied; missing/saturated/restarted cache cannot create a reply. No decoder,
durable operation journal/reservation, grant issuer, dispatcher, client, cell or daemon is delivered.
remember_completed requires the future real journal owner to validate durable DONE first. C0/C3
unit proof is NOT real authentication, grant revocation, durable completion or no-command-replay proof.

E234 local outputs/evidence and remaining live-test additions are recorded in the adversarial
review/ledger and notes/evidence/i03-e234/replay.json.gz. Do not borrow E232 numbers as reruns.
Rebuilt external CPython3.13.16 with host SSL3.0.20/SQLite3.40.1/zlib1.2.13; frozen dev dependencies.
Optional stdlib modules remain absent; no full environment or deployment readiness claim.

Next: continue source-declared SLICE1 strict whole-wire/profile/results and single-journal foundation,
then real service/client integration with actual WorkspaceAuthority before production activation.
No permissive temporary authority or failing main stub. Preserve all35 unchecked steps and all four
unfinished final acceptance duties; normative full-SLICE1/host proof remains pending. Q75 is resolved;
do not ask it again or reinstate the E233 hold. Q59/Q60/Q63/Q74 remain resolved.

**E232 retained implementation checkpoint — I03 IMPLEMENTATION STARTED, PARTIAL SLICE1/CT98:** operator authorized
careful source-declared, tested/mutated implementation. No blocking new policy question in this
chunk. New src/fa/controller_entry.py implements real CLI entry, pre-site -I -S install audit and
isolated runtime import-closure gate. Actual fa.cli.main reused; source/wheel byte binding in new
tests/test_controller_entry.py. Covers part of F16/F15. Existing wrappers/entrypoint/Docker image/
bootstrap/session launch paths are UNCHANGED and not safe managed execution yet. No activation.
No STEP/CT/READY tick,all35STEPS still unchecked;I03 remains OUTLINED with implementation in progress.

Actual checks:30new testsPASS;new+existing entrypoint/parser/skill174PASS6.79s;RuffPASS/format2unchanged;
targetedMypy2filesPASS;sourceMypy170filesPASS. Six developmental full-new-module mutations each
execute30tests,exit1 with CALL failures4/17/5/4/1/2,zeroerrors/skip;baseline/restored30PASS/sourcehash
exact. Lossless evidence notes/evidence/i03-e232/controller-entry.json.gz under this roadmap.
NOT normative full-SLICE1 CT98 PROVEN: other declared supervisor/boundary paths remain unimplemented.
Toolchain in /home/user/.cache/i03-impl: uv tools and locally source-built Python3.13.16,SSL/SQLite/
zlib verified; .venv from uv sync --frozen --extra dev. Other optional stdlib modules absent; not
full runtime/deployment readiness. Docker unavailable. Earlier environment/fixture/static errors
were repaired,not kills/waivers. Cache/toolchain paths excluded from persisted snapshots.

E232's implementation continuation now follows the ratified E234 Q75(a) rules above.
Keep SLICE1–4 closure before activation; main-host facts/maintenance authorization, final independent
fixture/helper review and actual direct+nested E2E remain required, not granted by this checkpoint.

E231 decisions remain:Q59advisory/manual+EXISTING experimental suggestion/no required mode;
Q60verified reuse/ONE workflow-admission-repair machine;Q63fourstates/optional commentary/no reason
enum;Q74per-stage safe checkpoints including failure/no rollback. Preserve Q66/Q67/Q68/Q69/Q70/Q73.
Scope remains CURRENT whole-plan direct+nested E2E,not deferred slice-loop/tracker/L2. Active I01/
I04–I06 unchanged. Allfour transferred acceptance duties remain unfinished,including actual red
readiness/just-check and historical Mypy-context disposition; no live PASS or broad review assigned.

Older S18/doc-hygiene notes below are historical,not current I02/I03 action items.

## S18 + I-63 CLOSED — evidence /tmp/s18-evidence-20260825T130324Z/ PASS (2026-08-25)

**Status:** CLOSED, live-verified. Evidence bundle `/tmp/s18-evidence-20260825T130324Z/` (host) contains:

- **C9** turn1 parallel `fs_search` + `fs_blackboard_query` → 9 rows first-try, errors `[None]`, S14B/S16/S15/S17/CAP-PROBE all present.
- **C10** corpus 17, `WIRING_EXIT 0`, git clean.
- Commit `9ab68bb` partial fix (pop+set pinning `_command_environment` hermetic + UV pinning) landed; I-63 context fix still required in patch.

**What S18 fixed:**
- `fs_search` unified (3→1) — `src/fa/inner_loop/tools/fs_search.py` 631 lines, `_resolve_subdir` with `is_relative_to` containment, registered in `cli.py`.
- `fs_reach`, `fs_exploration_metrics` registered.
- `structural_index` present.
- Blackboard artifact index (S14) — `src/fa/blackboard/artifact_index.py` lazy-indexes `knowledge/{skills,adr,...}`.

**What I-63 fixed:**
- Context passing bug in workspace bootstrap / session manager — runtime_limits `role None` guard, `_command_environment(workspace)` hermetic, UV pinning, `pyproject.toml` also_copy `scripts`.
- Remaining I-63 fix (full context propagation) assumed merged for docs_only patch; evidence in `worklogs/archive/root-stale-20260825/I-63-fix-*.patch`.

**Evidence:** `/tmp/s18-evidence-20260825T130324Z/` + `S18-VALIDATOR-CHECKLIST.md` + `S18-I63-FIX-REPORT.md` (both archived to `worklogs/archive/root-stale-20260825/`).

## Active: b_full doc hygiene — IN PROGRESS (2026-08-25)

**Goal:** make docs in order. Update statuses, close implemented plans, move them to archive. Rigorous check for completed items and stale doc.

**Completed in this session (b_full):**
- [x] Archived 17 COMPLETE/EXECUTED/IMPLEMENTED plans to `worklogs/archive/`:
  - S10a,b,c, S11, S12, S13.10, S5, S6, S6.6, S7 container/direct, S8, S9, fs-blackboard-query, S14, S14b.1-hardening, rushed-patch-foundation-closure.
  - Each prepended with `> **Status:** archived <date> — moved per 30-day rule`.
- [x] BACKLOG dedup: merged `worklogs/BACKLOG.md` (57 entries, 2857 lines, had I-34..I-56) into `worklogs/BACKLOG.md` (was 33 entries, now 56 after dedup of duplicate I-53). `worklogs/BACKLOG.md` removed — SSOT is `worklogs/BACKLOG.md`.
- [x] pr-notes dedup: `worklogs/pr-notes/` (30 files) canonical per `worklogs/README.md`. `knowledge/pr-notes/` (25 files) had stale links (`../research/`). Backed up to `worklogs/archive/knowledge-pr-notes-20260825/`, replaced with `README.md` pointer.
- [x] Root stale cleanup: `I-63-fix-*.patch` (2), `rushed-patch-foundation-closure*.patch` (6), `S18-VALIDATOR-CHECKLIST.md`, `S18-I63-FIX-REPORT.md`, `UNDERSTANDING_REPORT.md` → `worklogs/archive/root-stale-20260825/`.
- [x] HANDOFF rewrite: this file, S18+I-63 state, 1426→~300 lines, preserving unrelated older notes below.
- [ ] llms.txt update: BY-DEMAND INDEX § deprecated (S1,S2,S3,S4,S13.11 etc still listed) — formal substrate now Blackboard+fs_search. Needs rewrite (pending).
- [ ] check_doc_links.py run + link fix (pending).
- [ ] docs_only patch production assuming I-63 merged (pending).

**Remaining implementation-plans (15):**
- `PLAN-ble001-waiver-reduction.md` DRAFT — keep, waiver reduction not yet landed.
- `PLAN-cli-trace-S1..S4` READY but verification reports exist (S1-verification, S2-verification, S3-review, S4-verification) — borderline, ask operator before archiving.
- `PLAN-cli-trace-S10-cli-extraction-decision.md` — S10 decision record, keep.
- `PLAN-cli-trace-S13-*` (message-normalization, multi-provider-conformance CLOSED-CORE, thinking-mode-toggle, S13.11 portable-tool-schema) — keep, S13.11 still active.
- `PLAN-cli-trace-S14b-search-tools-memory-expansion.md` READY but code proves IMPLEMENTED (fs_search, fs_reach, structural_index) — user side-quest condition: keep active per instruction.
- `PLAN-session-workspace-readiness-bootstrap.md` v33 READY + `PLAN-session-workspace-readiness-live-closure.md` v18 DELIVERY-READY — keep active per user (commit 9ab68bb only partial).
- `PLAN-workspace-bootstrap-mutation-34-survivors-*` — keep, mutation survivors review.

**S14b.1-hardening verification (code-proven DONE):**
- `src/fa/memory/search_index.py`: `BINARY_SNIFF_BYTES=8192` line 66, `_refresh_state` dict line 79, `_stat_canaries` line 292, `_escape_like` line 511, export line 1415.
- `src/fa/inner_loop/tools/fs_search.py`: `_resolve_subdir` line 234 `is_relative_to` containment fix.
- Hence `PLAN-S14b.1-hardening.md` archived despite READY status — code invariants present.

## Backlog canonical

- **Canonical:** `worklogs/BACKLOG.md` (56 entries after merge, includes I-34..I-56: subagent containment Q19/V24+V25, SessionDatabase concurrency, artifact permissions RESOLVED S10c.3, tool schemas double-send, quiet mode S8.4, composer extras Q55, config gate S10c.1, sys.stderr binding S10b.3/Q53, /tmp hardcoded, ~/.fa Windows write, ruff markdown, install_hooks idempotency, python3 hardcoded, stale clones, mistral-medium-2604 shape, models.yaml stub, resumed workflow assistant-last 400, request_shape discard, resumed history user_msg dropped, S4-F1 residue RESOLVED, prompt caching capability model, subagent WIP, blackboard artifact index CLOSED S14).
- **Old location:** `knowledge/BACKLOG.md` removed 2026-08-25 — SSOT `worklogs/BACKLOG.md`. Git history retains prior content.

## pr-notes canonical

- **Canonical:** `worklogs/pr-notes/` (30 files) per `worklogs/README.md`.
- **Old:** `knowledge/pr-notes/` (25 files) archived backup `worklogs/archive/knowledge-pr-notes-20260825/`, now `README.md` pointer.
- **Diff:** worklogs had 5 extra `CLI_TRACE_S2/S5/S6/S7/QUALITY_GUARDRAILS`; link paths corrected from `../research/` to `../../worklogs/...` in canonical copy.

## Root stale cleanup

All untracked root patches/docs moved to `worklogs/archive/root-stale-20260825/`:
- `I-63-fix-9ab68bb.patch`, `I-63-fix-full-9ab68bb.patch` — superseded by 9ab68bb partial + full I-63 fix.
- `rushed-patch-foundation-closure*.patch` (6) — superseded by 9ab68bb.
- `S18-VALIDATOR-CHECKLIST.md`, `S18-I63-FIX-REPORT.md`, `UNDERSTANDING_REPORT.md` (342 lines, HEAD 234ca80) — moved to archive.

## Archived plans index (this session)

Moved from `worklogs/implementation-plans/` to `worklogs/archive/`:
- `PLAN-cli-trace-S10a-cli-coverage.md` COMPLETE
- `PLAN-cli-trace-S10b-cli-decomposition.md` COMPLETE
- `PLAN-cli-trace-S10c-contract-and-posture-fixes.md` COMPLETE
- `PLAN-cli-trace-S11-controlled-deployment.md` EXECUTED
- `PLAN-cli-trace-S12-platform-capability-markers.md` COMPLETE
- `PLAN-cli-trace-S13.10-tool-name-sanitization.md` COMPLETE
- `PLAN-cli-trace-S5-authority-correctness.md` COMPLETE
- `PLAN-cli-trace-S6-observability-contracts.md` COMPLETE
- `PLAN-cli-trace-S6.6-mutation-gap-closure.md` COMPLETE
- `PLAN-cli-trace-S7-container-verification.md` EXECUTED
- `PLAN-cli-trace-S7-direct-run-vertical-slice.md` COMPLETE
- `PLAN-cli-trace-S8-workflow-controller-surface.md` COMPLETE
- `PLAN-cli-trace-S9-stats-projections.md` COMPLETE
- `PLAN-fs-blackboard-query.md` IMPLEMENTED
- `PLAN-cli-trace-S14-blackboard-substrate-completion.md` IMPLEMENTED
- `PLAN-S14b.1-hardening.md` READY but code-proven DONE → archived
- `PLAN-rushed-patch-foundation-closure.md` READY but 9ab68bb superseded → archived per user

## llms.txt status

`knowledge/llms.txt` 106 lines — BY-DEMAND INDEX still lists S1,S2,S3,S4,S13.11 etc as active. Per S14 substrate, formal substrate is now Blackboard + fs_search, not by-demand file list. Needs rewrite to reflect:
- Blackboard artifact types: skill|adr|research|instruction|prompt|codemap|antipattern + file_version
- fs_search as primary discovery, fs_blackboard_query for typed artifact queries, fs_instant_grep for substring
- Archived plans no longer in active index

Pending update.

## Historical — preserved unrelated notes (pre-S18)

> The following sections are preserved from S14-era HANDOFF but marked superseded. Full 1426-line version backed up to `worklogs/archive/HANDOFF-S14-era-20260825.md`.

### S13 multi-provider conformance — CLOSED (live-verified 2026-08-09)

Parent `PLAN-cli-trace-S13-multi-provider-conformance.md` CLOSED-CORE. Live sheet verified across providers. Thinking-mode toggle (S13 thinking-mode) and message-normalization (S13) remain as follow-ups. See archived plans for S13.10 sanitization (now archived).

### S12 COMPLETE — platform capability markers (2026-08-02)

`PLAN-cli-trace-S12-platform-capability-markers.md` now archived. Capability markers landed.

### S10c COMPLETE — deploy-gate contracts (2026-08-01)

Artifact posture, request cost, config gate validation — all COMPLETE, now archived.

### S10b COMPLETE — cli.py C901-clean (2026-08-01)

Decomposition complete, archived.

### S7/S8/S9 COMPLETE

All archived this session. Direct-run vertical slice + container verification + workflow controller + stats projections — all COMPLETE/EXECUTED.

### S5/S6/S6.6 COMPLETE

Authority correctness, observability contracts, mutation gap closure — all COMPLETE, archived. Mutation survivors workplan remains active: `PLAN-workspace-bootstrap-mutation-34-survivors-review.md` APPROVED, keep.

### Workspace readiness bootstrap

`PLAN-session-workspace-readiness-bootstrap.md` v33 READY + live-closure v18 DELIVERY-READY — still active, commit 9ab68bb only partial (pop+set pinning _command_environment hermetic + UV pinning). Keep per user instruction. Full I-63 context fix still pending in docs_only patch scope.

### Historical doc-hygiene follow-ups

1. Update `knowledge/llms.txt` BY-DEMAND INDEX to reflect archived plans and formal substrate (Blackboard+fs_search).
2. Run `python scripts/check_doc_links.py` and fix broken links from archiving (implementation-plans → archive moves).
3. Produce docs_only patch assuming I-63 merged: includes BACKLOG dedup, pr-notes pointer, root cleanup, HANDOFF rewrite, llms.txt update, link fixes.
4. Ask operator per borderline plan (S1-S4) before archiving.

## Historical E212 next-action list — superseded by E243 current continuation

0. Obtain explicit Q71 disposition before changing the documentation acceptance oracle. The
   exact three-path/one-trigger exception is only a proposal; no spelling workaround, immutable
   evidence rewrite or candidate-only waiver. Q69/Q70 stay resolved.
1. Read E212's final producer table and completed full-suite comparison; no result from
   an interrupted or missing report is PROVEN. Preserve all16 whole-public-path mutations.
2. Preserve/finish dispositions of the usable candidate/d9109f4 manifests and normal summaries with
   separate tree-local environments and verified imports. Cache artifacts are not persisted;
   preserve compact results/hashes in the evidence note. Do not count no-summary/reporter crashes.
3. Repair the ten remaining candidate-only failures and three new authoring export violations,
   then rerun affected checks/proofs and the full candidate suite; classify
   the five old authoring and eight matching Mypy identities explicitly, with operator review.
   Full-tree formatting debt also remains. No skip/suppression or count-only baseline waiver.
4. Complete independent retained-plan/source/evidence review and operator local DoD disposition.
   Existing foreign Arena commit-msg hook blocks managed bootstrap readiness; preserve it,
   do not replace it or bypass checks. Commit/push only this branch and verify the remote SHA.

## Historical S18 session close record

- Evidence: `/tmp/s18-evidence-20260825T130324Z/` PASS, corpus 17, WIRING_EXIT 0.
- Doc hygiene: b_full in progress, 17 plans archived, BACKLOG merged, pr-notes deduped, root cleaned, HANDOFF rewritten.
- No code changes in this session beyond doc moves — docs_only.
