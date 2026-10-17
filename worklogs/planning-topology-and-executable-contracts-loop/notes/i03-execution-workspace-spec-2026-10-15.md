# I03 execution/workspace implementation specification

Date: 2026-10-15; refreshed 2026-10-16 against I02 closeout `1132eee` (runtime `a32a72f`).
The d910 evidence below is historical; E230 in the existing adversarial review records current findings.
This is the implementation specification finalized after E230 review and the operator's E231
answers. New files/functions are **planned**, not discovered or implemented interfaces. Q59 keeps
advisory/manual invocation plus EXISTING experimental suggestion injection (no required mode).
Q60 delegates the source-grounded engineering solution; §7 records the selected reuse design.
Q63 is four states with optional short commentary, NO reason-code enum. Q74 selects per-stage/
episode checkpoints. These resolve planning decisions, not implementation/deployment authorization.
No temporary production backend, unsafe fallback or fake acquisition completion is acceptable.

## 1. Smallest coherent ownership model

Keep SessionManager/RunContext/SessionDatabase as the only session/run authority. One privileged,
local host supervisor owns Docker cells **and** one per-workspace publication authority. Controller
retains prompts, providers, workflow routing and policy decisions; no conversations/provider chain
are moved into cells. No second session DB, lease service, distributed coordinator or Git-CAS store.

Planned new modules, deliberately divided by responsibility rather than new services:

| File | Responsibility / public implementation seams |
| --- | --- |
| `src/fa/controller_entry.py` | Isolated image-owned entry module with an actual __main__ guard calling existing cli.main; current `fa.cli` has no module-entry guard |
| `src/fa/execution/types.py` | Frozen NamespaceRef, ViewRef, OperationRef, ExecutionReceipt; closed job/error states and schema validation |
| `src/fa/execution/client.py` | ExecutionClient over private UDS, ManagedBashExecutor, noninteractive adapter; run_stage_with_plan_write_boundary and receipt validation |
| `src/fa/execution/supervisor.py` | Privileged host main/UDS dispatch, fixed profile loading, cell create/inspect/cancel, process-tree barrier; no raw Docker request passthrough |
| `src/fa/execution/journal.py` | Same supervisor’s protected secret-free operation JSON, one-claim guards and restart uncertainty; reuses private IO/flock helpers, no second database |
| `src/fa/execution/profiles.py` | Frozen explicit approved-profile inputs and fixed Docker renderer; not host approval or protected resource authority |
| `src/fa/execution/cell_worker.py` | Thin cell-local adapter reusing PtyPool/InProcessPtyExecutor and result framing; no independent host authority |
| `src/fa/execution/workspace.py` | Same supervisor's registration, writer flock/generation, materialized revisions/candidates, rooted file-tool operations/read pins |
| `src/fa/execution/publication.py` | Same authority's seal validation, prepare/commit/projection/recovery and no-clobber project install |
| `src/fa/inner_loop/managed_acquisition.py` | Small pure approved-choice parser, stable-ID resolver and controller bundle renderer; no separate workflow state machine |

`WorkspaceAuthority` is a helper owned by the supervisor, not a separately deployed service.
Reuse private IO primitives introduced for I02, but keep publication commit semantics separate.

## 2. Launch, wire protocol and installed profile

**Q75(a) ratified, E234:** [operator decision](open-questions-2026-10-07.md#q75--may-exact-completed-request-replay-return-an-original-cached-grant-after-revocation)
lifts E233's hold. Exact completed-reply replay is a narrow memory-only read exception, not fresh
execution authority. Durable results are nonsecret projections, never literal grant-bearing wire
replies. Non-exec observation uses original-operation replay, not a viewless ExecutionReceipt.
The concrete rules below supersede the frozen15dc7cb joins recorded as review F17. No slice/CT
completion or production activation follows from ratification or the first helper implementation.

Controller entry is `/opt/fa-venv/bin/python -I -m fa.controller_entry`, CWD a trusted directory,
not the active workspace. Add the named module first; do not substitute `-m fa.cli` (currently a
silent no-op) or nonexistent `-m fa`. Pin the installed fa package and dependencies, remove editable
.pth files, project PYTHONPATH, user-site and project venv discovery from the controller. Python -I
alone does not sanitize an editable site-packages install. Build/install validation rejects project-
referencing executable/editable pth before controller startup; runtime assertions cannot undo code
already executed by Python site initialization. The immutable approved image is the trust root, not
a late sys.path assertion. Use noneditable install and test build/launch rejection separately.
Check module.__file__, sys.path and
loaded package origin on entrypoint, wrapper exec, help, auto-run and session-manager paths.
Project pytest/import probes deliberately import the candidate **inside a cell**, not in controller.

Update `scripts/fa`, `scripts/fa-entrypoint.sh`, `Dockerfile.fa`, `docker-compose.fa.yml` and
bootstrap/readiness entrypoints. No workspace-first PYTHONPATH export or project-CWD console
launch. Change Dockerfile.fa's existing install to `UV_PROJECT_ENVIRONMENT=/opt/fa-venv uv sync
--frozen --no-dev --no-editable`; retain uv.lock, noneditable wheel install and origin tests.
No second dependency installer/build system; copying source alone does not fix editable pth. Host wrapper help must use installed trusted help or delegated isolated controller, not
host-repo PYTHONPATH. `docker compose exec` does not inherit entrypoint-only exports; configure
and test each path explicitly. Operator `fa shell` is maintenance-only outside active workflow:
no project commands in the secret-bearing controller. Offer managed cell shell or refuse while busy.
Arbitrary entrypoint command overrides must not become an undocumented project-execution bypass.

Add `deploy/fa-execution-supervisor.service` and a documented private config example. The host
service uses an installed immutable supervisor venv with isolated Python, a 0660 UDS accessible
only to the controller group, SO_PEERCRED verification, private 0700 state and no public listener.
Only supervisor gets the Docker daemon socket. Controller/cells never receive that socket, host
PID namespace, privileged mounts/capabilities or supervisor paths. Host/kernel/Docker/admin remain
TCB. An approved UID/GID mapping and cgroup-v2 layout are required deployment inputs, not guesses.

Versioned, length-framed JSON requests; reject unknown keys/types/versions and over-limit frames.
Malformed framing/UTF-8 or invalid request_id closes the connection without launch or echoing an
invalid ID. With valid request_id but invalid payload, return structured INVALID_REQUEST; operation_id
is null before reservation. Never dump raw frames or grant-bearing exceptions to logs.
Max control frame 4 MiB as an independent encoded-frame cap (body caps do not imply wire size),
max individual tool text 1 MiB, bounded output tails 64 KiB/channel. Commands are opaque text;
cwd is relative to an authorized view. Neither wire nor model accepts host paths, image, Docker
flags, mount lists, arbitrary environment, networking, UID, cgroup path or publication destination.
Authenticated controller selects immutable approved profile ID; supervisor expands fixed config.

Closed operations: health, register_workspace, acquire_writer, pin_reader, create_view, read_file,
write_file, edit_file, exec, inspect, cancel, stop_view, seal, publish, install_project, release, pty_control, handoff, prepare_bundle.
Wire envelope v1 is exactly `{protocol_version:1, request_id, op, namespace, view_ref, capability, payload}`.
request_id is a controller UUID key; namespace is null only for health, otherwise exactly
`{session_id,run_id,parent_run_id}` (parent null when absent). view_ref is null for the owner/pre-view operations listed below; other operations carry the
validated ViewRef, not a string path.
Reply exactly `{protocol_version:1,request_id,status,result,error}`; status OK|ERROR, one of result/
error nonnull. error exactly `{code,retryable,operation_id}`; code closed:
INVALID_REQUEST, UNAUTHORIZED, UNAPPROVED_PROFILE, WORKSPACE_BUSY, STALE_GENERATION,
STALE_REVISION, VIEW_CLOSED, BACKEND_UNAVAILABLE, EXECUTION_UNKNOWN, TERMINALITY_UNKNOWN,
PATH_DENIED, INPUT_POLICY, COLLISION, DURABILITY_UNKNOWN, CORRUPT_STATE. No exception text.

Payloads/results are closed per-op schemas in §2.1, the SOLE wire-shape authority. No abbreviated
parallel dataclass may omit its mandatory keys. register/acquire/pin/create_view/prepare_bundle/
install_project/handoff and OWNER release use view_ref=null; health additionally has namespace/capability=null; other operations use the
specified owner/view grant. All successful grants remain private controller DI.

Q75(a) exception: BEFORE any fresh-work authorization branch, an already-DONE operation may return
ONLY its original protected memory-cached completed reply to the same authenticated principal,
namespace, original request ID/op/canonical input and original authorization proof. The original
proof may have been revoked by that completed handoff; compare it to the cache binding, not an
invented fresh grant. Pre-grant calls retain their original null proof and principal binding.
No cache lookup can admit new work, execute a callback, change the result, renew a grant or reserve
another operation. Mismatch rejects. Cache loss/restart/unavailability fails closed for the grant
reply until safe reconciliation; neither durable public metadata nor IDs authorize reconstruction.
Ordinary fresh-work authorization/revocation rules remain mandatory and unchanged.

The controller reserves a unique op-UUID before sending exec; supervisor persists that ID and input
binding before starting it. Other mutation request IDs likewise deduplicate by exact input hash;
a reused key with different input fails, never replays. IDs refer only to supervisor-created state,
not caller-supplied manifests/bundles or filesystem locations. Bind every stored result to caller
namespace and reject cross-run inspection. Capability is a supervisor-minted 256-bit random grant
encoded as 64 lowercase hex characters, null only for health/register/acquire/pin; other requests require its exact actor/view/access binding.
Return it only to authenticated controller DI, never tools/events/receipts/transcripts. IDs are not secrets
and are not themselves authorization. Redact the entire capability field from transport diagnostics. Release cannot discard state needed by live jobs/pins.

Every workspace/source-mutating request validates namespace, current lease/generation and allowed
capability. Pre-lease register/acquire are authenticated controller-only; READ-pin exec/scratch does
not require current writer generation and cannot mutate source. No blanket stale-generation test
may invalidate an otherwise-live immutable reader pin.
Operation IDs are allocated/reserved before starting work. inspect is read-only; exec retry with
an already used operation ID inspects/returns its old receipt, never starts a duplicate command.
No generic path-copy/exec-on-host operation. Service rejects busy/stale/wrong-run requests.

Initial required profiles: interactive project shell, noninteractive verification, provisioning.
Rootfs/toolchain image by digest, non-root cell user, cap_drop ALL, no-new-privileges, private PID/
mount/IPC namespaces, approved seccomp, CPU/memory/pids/output/time limits, no host/control sockets,
no controller env or credentials, only authorized view and scratch mounts. Default network none.
Provisioning uses an approved read-only dependency cache/toolchain; offline miss fails closed.
If a product path actually requires remote dependency access, an explicit tested restricted profile
must be approved before that path is accepted; do not silently grant Docker bridge networking or
pass controller SSH/provider credentials. A dependency/proxy platform is not part of I03.

### 2.1. Closed adapter contract and deployment mapping (E230)

All resource IDs are supervisor-minted: ws-/view-/rev-/op-/seal-/bundle- followed by32 lowercase hex; request_id is32
lowercase hex. root_id/input_id/profile_id are configured lower-kebab IDs≤48chars, not paths.
Namespace IDs use existing SessionManager validators unchanged; parent_run_id is null or a valid run ID. SHA256 is64 lowercase hex. Reject bool-as-int, duplicate JSON keys, nonfinite
numbers, bad UTF-8, null/unknown fields except explicitly nullable values. Paths are UTF-8 POSIX
relative components with no NUL, empty/dot/dotdot component, absolute prefix or traversal; cwd may
be exactly `.`. Limits in §2 apply before allocation, IO or launch. Capability is never a path.

Complete payload additions/results (every object has exactly the named keys; IDs are strings):

| op | payload / successful result |
| --- | --- |
| health | `{}` / `{ready:bool,protocol_version:1,profile_set_sha256}`; health is not execution readiness or a view grant |
| register_workspace | `{root_id,relative_root,create:bool,input_id:null-or-configured-ID}` / `{workspace_id,revision_id}`; create=false requires existing root; create=true installs an owned new root no-clobber from approved materialized input or empty source; no remote clone/ambient credentials |
| acquire_writer | `{workspace_id}` / `{view_ref:null,capability,generation,revision_id}`; grant bound to authenticated controller's namespace and root owner |
| pin_reader | `{workspace_id,revision_id,plan_ref}` / `{view_ref,capability}`; READ pin independent of subsequent writer generations |
| create_view | `{workspace_id,base_revision,access,purpose,candidate_scope,plan_ref}` / `{view_ref,capability}`; purpose PROJECT/PROVISIONING/VERIFICATION/MUTATION/CANDIDATE; candidate_scope null except exact `{candidate_path,plan_ref}` for CANDIDATE, with identical top-level plan_ref; grant checks permitted combinations before copy |
| read_file | `{path,offset_bytes,max_bytes}` / `{content,sha256,eof}`; max_bytes1MiB, exact bounded UTF-8 file snapshot; reject unsupported binary/split-codepoint rather than silently corrupt; SHA covers whole input-policy-bounded file, not the returned window; larger files use the bounded read-only window policy in §4.2, never partial SHA for edits |
| write_file / edit_file | `{path,content,expected_sha256}` / `{sha256,bytes}`; expected_sha256 nullable only for write(create-if-absent); edit requires hash; conflict is STALE_REVISION with no silent retry |
| exec | `{operation_id,profile_id,command,cwd,timeout_ms,session_id}` / `{receipt}`; session_id nonnull only for interactive profile; fixed simple identifier≤64chars, scoped to namespace+view |
| inspect / cancel | `{operation_id}` / `{receipt}`; cancel requests stop, not success or terminality until independently confirmed |
| pty_control | `{action:INTERRUPT|CLOSE|LIST,session_id}` / `{sessions,message}`; LIST uses null ID; other actions require ID; namespace/view scoped, never process-global main |
| stop_view | `{}` / `{view_id,terminal:bool}`; false/unknown cannot seal/release |
| seal | `{}` / `{sealed_manifest_id,revision_id,tree_sha256}`; immutable revision may be unpublished/MUTATION-only; cannot be made writable or used for canonical publication without owner grant |
| publish | `{sealed_manifest_id,expected_base_revision}` / `{workspace_id,revision_id,tree_sha256,operation_id,projection_complete:true}`; no receipt before durable DONE |
| prepare_bundle | `{project_slug,increment_slug,roadmap_text,increment_text,expected_base_revision}` / `{validated_bundle_id,bundle_sha256}`; OWNER grant, fixed three-file renderer/ledger header, recomputed caps/grammar/hash in supervisor; no model file map |
| install_project | `{validated_bundle_id,project_slug}` / same committed result as publish; bundle created by trusted bounded renderer, not arbitrary model file map |
| handoff | `{target_namespace}` / `{view_ref:null,capability,generation,revision_id}`; current actor's views must be terminal/settled; target bound to existing parent-child run relationship; same root owner/generation, exactly one active mutator grant |
| release | `{}` / `{released:true}`; revokes only its grant/pin; writer release requires no writable/live/unknown jobs or unfinished projection; READ release cannot revoke another actor |

Cell-private stdio frames carry exactly `{version:1,request_id,action,payload}`; actions
RUN/INTERRUPT/CLOSE/LIST/STOP. RUN payload exactly `{command,cwd,timeout_ms,session_id}`; control
payload is `{session_id}` or `{}` for LIST/STOP. No capability/namespace/host configuration enters
the worker. Replies exactly `{version:1,request_id,result,error}` with null error on result or
WORKER_UNAVAILABLE; result is complete PtyResult fields for RUN, `{sessions,message}` otherwise.
One active RUN, controls remain responsive; STOP acknowledgement is not a descendant barrier.
Worker output remains untrusted; supervisor reconstructs all receipt bindings and terminality.
F19 implementation clarification: interactive profiles retain the persistent framed worker;
noninteractive profiles select the fixed private `--one-shot` worker mode. It accepts exactly one
RUN and exits with its determinate command status, not unconditional worker-loop exit0. It closes
its PTYs before returning; that cleanup is NOT a descendant barrier. Invalid/control-only input,
lost reply and indeterminate/timeout results never synthesize normal completion. Worker failure
exit78 is not itself a command outcome; a genuine command exit78/124 remains distinguishable by
a complete determinate RUN result, matched actual container exit and independent terminal facts.
The Docker backend must independently observe actual exit, enforce its deadline and confirm the
cgroup barrier; a one-shot result/process code alone cannot issue an authoritative receipt.

`BashExecutor.run/send_ctrl_c/close/list_sessions` map to exec/pty_control. Preserve stateful cwd,
environment and PTY session between commands in ONE open episode. Interrupt/close timeout is
explicit uncertainty, not shell replay or implicit successful cleanup. `run_bash` must catch typed
managed errors BEFORE its current blanket fallback catches and return the existing ToolResult
error envelope; remove the production `_run_subprocess_fallback` branch. A transport loss after
sending exec is inspect/cancel by the SAME exec operation ID; non-exec/control mutation loss uses
exact original-request replay (§2.2), not an exec receipt. Never allocate a new ID to retry the same command.

ExecutionReceipt v1 is exactly `{schema_version:1,operation_id,namespace,workspace_id,view_id,
owner_run_id,generation,revision_id,original_revision_id,input_tree_sha256,plan_sha256,profile_id,
image_digest,state,exit_code,timed_out,stdout_tail,stderr_tail,truncated,duration_ms,terminal_barrier}`.
Nullable revision fields only for pre-source provisioning, never verification. Q76(a): plan_sha256
may also be null for ordinary execution with NO active workflow plan; it never substitutes for
formal workflow/verification/mutation/candidate evidence. exit_code int or null,
timed_out/truncated/terminal_barrier bool, duration_ms nonnegative int, tails≤64KiB/channel.
Normal noninteractive EXITED needs actual container/process exit and terminal_barrier=true;
LAUNCH_FAILED/UNKNOWN never inherit exit0. Interactive completion may leave idle shell and barrier
false until stop_view. Supervisor reconstructs identity from reserved state, never worker JSON.
Exact operation input hashes are private; model/cell text cannot select any binding/profile/mount.

Reserve durably BEFORE Docker create, use deterministic owned name and labels including operation
ID; persist container identity before start. Restart reconciles RESERVED/RUNNING by ID/name/labels
and actual Docker+cgroup facts. Lost create/start reply means inspect the existing identity or
quarantine, NEVER a second create/start. Cancel-before-start also persists and prevents late start.
Before startup recovery, hold the existing private flock primitive in operations/.supervisor for
the accepting service lifetime. Per-operation atomic transitions use the separate short journal
lock. A persisted cancel before the start critical section denies start; write UNKNOWN before ONE
bounded start RPC while holding that journal critical section. Never regain the start claim after
loss. This journal state records write-ahead uncertainty, not an actual Docker observation.
Bound control RPC timeouts separately from command deadline; use one monotonic deadline across
all partial frame reads/writes, not resettable socket inactivity alone; lost reply cannot mean not executed.

E241 construction clarification (not activation/acceptance): DockerCells.launch_new requires the
original reserved exec/input binding and a resource validator; write-ahead UNKNOWN precedes one
bounded create, durable CID precedes one start. Lost replies permit only owned observation, not
replay. Internal journal EXECUTING/UNKNOWN are claim stages, never actual Docker lifecycle facts.
The launch result is a start-ACK CID, not a receipt. Original-name/ID inspection verifies creation
identity/labels and configured pinned reference, reports the actual image config ID and withholds
provisional exit codes outside EXITED; it does not prove approved image facts or a descendant barrier.
Later interactive RUNs must reuse the original live cell and creation binding; per-command operation
reservation is separate. A protected episode registry, actual attach/worker/control/lifecycle and
reconciliation owner are still required before wiring this into exec or service main.

E242 construction adds the actual upgraded non-TTY attach transport and a shared closed worker
codec/client. Fixed live-only attach preserves framed output through Docker multiplexing; one RUN
and concurrent controls retain their own IDs/deadlines and unavailability, with no reconnect/resend.
The client reuses an attached stream, but is NOT the exclusive protected episode registry, durable
command admission, receipt issuer or restart recovery. Only the real backend/authority may use it
after original journal/resource checks; future commands still require their own one-use reservation.
Worker stdout/status, stderr diagnostics, channel close and local serve_once return are not actual
container exit/cgroup facts. These remain required before any authoritative completion/seal.

Deployment contract: controller `/sessions` and any canonical project binds READ-ONLY; replace the
current compose writable `/sessions` bind. Keep controller session/config DB mounts writable but
never expose the supervisor state directory through them. Only private UDS is mounted to controller;
no supervisor state/daemon/credential mount in cells. Host config owns a table of root_id + host
canonical root + controller logical path; cells see `/workspace`, `/scratch`, approved environment.
Never send `/sessions/...` directly to host Docker as if it were the same host path. Profile/image/
UID:GID/cgroup-v2/free-space/daemon+seccomp facts are captured in the approved deployment record
before host runs. Existing entrypoint command overrides and `fa shell` either use managed shell or
explicit quiescent TCB maintenance, never a production alternate runner. No Go runtime is added.

SLICE1 construction exposes no production grant issuer before SLICE2. Supervisor authorization
uses an injected typed ownership-validation callable; unit fixtures may fake it and remain C0.
SLICE2 wires the actual WorkspaceAuthority into service main before any positive managed-project
kernel proof. Do not add a permissive temporary authority, guessed registered view or failing main
stub. Required actual authorization/kernel proof is accumulated for final SLICE6, not claimed from
unit injection. Packaging can be prepared in SLICE1; production service startup follows integration.

### 2.2. Remaining SLICE1/2 composition contract (E243)

These are required implementation interfaces, **not implemented owners**. Keep the existing
protocol/journal/client/worker/Docker transport; do not create a second execution history, session
manager, HTTP supervisor, scheduler, lease daemon or configurable backend matrix.

- **NEW `execution/backend.py::CellBackend`** is the one thin lifecycle owner over `DockerCells`,
  `WorkerClient` and `OperationJournal`. Its private live episode map is keyed by authenticated
  principal + NamespaceRef + exact ViewRef + approved profile; worker PTY session IDs are subordinate
  to that episode. Store the original creation request/CID and sole attach in memory, not credentials
  in another persisted episode file. Different namespaces/views cannot reuse a shell named `main`.
- **NEW `WorkspaceAuthority.admit(peer, request, *, deadline)`** revalidates the actual grant,
  namespace/active actor/generation/view state, protected source identities and PlanRef, and registers
  active work under that workspace's admission lock. It returns an internal scoped admission, never
  a wire grant. A successful earlier `authorize()` call or journal reservation is not this permit.
  Internal admission carries the actual loaded view record, retained source descriptor, trusted
  profile/path triple and ProtectedPlanContext plus deadline; no new wire/persisted grant schema.
  READ grants check their retained pin, not the latest writer generation. The service's private
  backend dispatch must carry authenticated peer and absolute deadline as explicit arguments; the
  E251 `handle(peer, request, *, deadline)` / authorizer seam now propagates these explicitly;
  it is still not the actual admission/backend implementation.
- **NEW `supervisor.py::build_supervisor/main`** compose actual authority + lifecycle owner + existing
  journal/reply cache/dispatcher; configure all closed operation handlers, including SLICE3 publication,
  before production startup. NEW `CellBackend.execute(peer, request, *, deadline)` consumes this
  authority admission; existing planned `supervisor.stop_view` closes that same gate before backend
  drain and `_wait_descendants_terminal` (CT104), not a second stop/lease owner. No permissive
  callback/default authority/failing-main stub. Packaging is
  SLICE1 work, real ownership/IO is SLICE2, publication SLICE3, atomic caller/mount cutover SLICE4.
  `DEPS` expresses construction order, not a demand to tick SLICE1 before constructing its authority.

**One-command ordering, including reused shells:** dispatcher authenticates/validates, checks the
exact cached-completion path, authorizes, reserves and calls existing `journal.begin()` once. For a
fresh cell, retain `create_once → durable CID → start_once` and original creation labels. For a later
command in the SAME live episode, use `record_container(new_command_id, namespace, original_CID)`
before its one RUN send; never call `launch_new/start_once` again or rebind original labels to the new
command. `begin()` is the durable per-command claim: duplicate dispatch/restart cannot claim it again.
No second RUN log or redundant claim API is needed. The original first command may already be in
journal UNKNOWN after its one start RPC; that write-ahead stage is not permission to retry it.

Acquire actual admission before any create/start/RUN/write effect and recheck cancellation at the
bounded send/start boundary. Gate registration and close-admission must linearize: if revoke/stop
wins, no late send/write; if admission wins, stop owns that in-flight work and cannot finish before
it drains. Persist cancel intent before acknowledging cancel; it is not a terminal receipt. Close
admission before STOPPING, wait active file handlers and queued/dispatching sends, stop cells, then
observe real exit/cgroup emptiness. Do not hold the global journal lock while waiting for a command,
handler drain or cgroup. Lock order is workspace admission before short journal transitions; any
cancel path that records intent first releases its journal transaction before waiting for admission.

**E248 owned force-stop contract (native operations implemented E249):** extend the existing private Docker transport,
not the wire operation set. `DockerCells.force_stop_created(original_creation_request, profile,
deadline)` checks the original namespace/input journal binding and durably records cancel intent
before Docker contact, even for a completed creation command with a still-live cell. Never reclaim
begin/create/start, change its command result or infer cancellation completion. Engine
`force_stop_owned` re-inspects exact original name/labels/profile/CID, sends at most one fixed
`POST /containers/<observed-full-CID>/kill?signal=SIGKILL`, then independently re-inspects that SAME
CID. No model-selected signal/grace/name/PID or automatic resend. An already observed exited cell
needs no signal; Docker409 (not running) still requires the independent observation, while404,
lost/malformed acknowledgement or observation fails closed. One caller absolute deadline spans
all legs; no late follow-up or phase loan. Return only ContainerObservation, including still-running
facts; never a receipt/terminal_barrier, journal DONE or lease release. Actual descendant/cgroup
emptiness, per-command cancel routing, admission/drain/restart enumeration remain obligations of
the real backend/authority join, not fulfilled by these native lifecycle operations.

**E252 worker reply/RUN handoff repair (before code):** completion-reply publication and acceptance
of the next RUN must share one synchronization boundary. The caller can receive a reply before
its sender's write returns; releasing the RUN gate only afterward without coordinating admission
can falsely reject the next sequential command. Use the existing reply-write lock for both RUN
admission and gate retirement; retire the gate inside that lock after publishing the reply.
Never release/reacquire it outside that boundary. Reject truly overlapping RUN without parallel
execution; preserve concurrent controls and main-thread PTY acquisition/prior-thread join. A send
failure remains unavailable/uncertain, no resend or terminality assertion. Add deterministic actual
Unix/worker scheduling proof that holds gate retirement after reply visibility and submits RUN2;
RUN2 waits at publication, not rejects. No sleep/retry/longer timeout as a repair.

E252 implemented this boundary in `cell_worker.serve` with deterministic actual-worker/PTY/UDS
regression and independent full-bank kills of both lock producers. Owning733/broader1253 pass;
E251 broader failure remains in its immutable archive. This is component proof, not real
WorkspaceAuthority/CellBackend composition or deployed CT98–100 acceptance. See
[evidence](evidence/i03-e252/worker-handoff.json.gz).

**Restart and loss:** mark uncertain operations with existing `recover_uncertain()` but also discover
and inspect ALL owned cells by original name/CID/labels, including cells whose creation command is
DONE. An idle shell/background writer can outlive a completed interactive command. Memory episode
loss does not permit reconnect/reconstruction/new RUN or replay-cache reconstruction. Stop/inspect
old cells before fresh writer admission; unknown ownership/exit/barrier quarantines, never lease expiry.
A missing cell is not a successful historical command. Build receipts from the reserved command/view,
approved profile, trusted protected input/PlanRef and independently observed execution facts. An
interactive command can be EXITED with barrier=false; one-shot normal completion additionally joins
actual container exit and empty owned cgroup. A worker exit/STOP ack never substitutes for that join.

**Deadlines and error paths:** request input framing is bounded by the short configured control RPC
budget. Once a decoded exec matches a configured profile/mode/limit, transport may add its requested
command budget ONCE to the original absolute deadline; it never resets on a partial read/write and
cannot revive expired input. Client keeps connect/request send on the short budget and adds the same exec budget only after
sending the validated frame;
controls/unapproved exec do not borrow it. E243 implements this transport repair only. The actual
service/backend still need one absolute command deadline measured from request receipt, consuming
queue/admission/create/start/RUN time, not a fresh timeout for each phase. SLICE4's controller clamps
the request to remaining actual workflow budget; profile and backend ceilings still apply. Transport
waiting/expiry is not evidence of command timeout or descendant death. Typed error handling must
cover ERROR envelopes as well as receipts: unknown/durability/terminality errors stay uncertain,
backend unavailability stays unavailable, policy denial remains denial. Never normalize a denial
or missing receipt to exit0/FAIL. Exec uncertainty uses original exec inspect/cancel; uncertain
mutating controls/non-exec requests use exact original request/input replay, not exec inspect with
a control request ID. Q75 permits only the original in-memory completed reply, including after handoff.

**E246 typed ERROR closure (before repair):** ExecutionClient must classify the existing closed
ERROR codes before handing them to ManagedBashExecutor: EXECUTION_UNKNOWN, TERMINALITY_UNKNOWN,
DURABILITY_UNKNOWN and CORRUPT_STATE raise ExecutionUncertainError retaining the code and the
original operation reference (use the original request ID if the error has no reference).
BACKEND_UNAVAILABLE raises ExecutionUnavailableError, preserving a supplied operation reference;
remaining codes are determinate request/policy rejections via ExecutionRejectedError. Preserve
sanitized exception messages and the existing timed-out-receipt subtype. The retryable bit never
permits automatic resend, replacement IDs, reconnect, inspect/cancel or shell fallback. Cover exec,
INTERRUPT, CLOSE and LIST; a control request ID is not an exec inspection key. This changes no wire
schema, exposes no grant/body in errors, and does not implement backend/admission/terminality.

## 3. Identity and job lifecycle

NamespaceRef = `{session_id, run_id, parent_run_id?}` from existing manager/bindings. WorkspaceRef
is an opaque stable workspace_id from protected registration, not a run/session label. ViewRef =
`{workspace_id, generation, base_revision, view_id, owner_run_id, access, purpose}`; access is READ|WRITE.
Opaque writer capability never enters model JSON, transcript or ordinary logs. Paths are not IDs.
OperationRef = `{operation_id, view_id, owner_run_id, generation, input_tree_sha256}`.

ExecutionReceipt has exact identity, profile/image identity, state, actual exit/null, timed_out,
stdout/stderr bounded tails, truncation, start/end monotonic durations and terminal_barrier flag.
State `RESERVED|RUNNING|EXITED|CANCELLED|TIMED_OUT|LAUNCH_FAILED|UNKNOWN`; terminal_barrier is true
only after independently confirming no descendant can still write. EXITED is not itself proof of
that barrier. Null exit, uncertain transport, missing timeout field or wrong operation/view/tree
identity is not a normal command failure or success. Persist receipts outside cells via existing
run evidence/event facades; cell-supplied IDs/status are never authoritative.

ManagedBashExecutor preserves existing BashExecutor methods. `run` returns ordinary PtyResult only
for a determinate completed command; unknown/null-exit receipt raises typed ExecutionUncertain,
launch failure/backend unavailability raises ExecutionUnavailable, confirmed timeout raises ExecutionTimedOut with
its receipt when PtyResult cannot represent null exit. Tool handler maps these to closed
execution_unknown / execution_unavailable / command_timeout errors, no fallback and no automatic
retry. Noninteractive adapter maps timeout/unknown/launch to CommandOutcome.ERROR with null exit;
only a determinate normal nonzero command exit becomes FAIL. Full receipts remain outside cells;
do not force UNKNOWN into exit 0/124 to satisfy the old shape.

Stateful PTY command completion allows the session's idle shell to remain while the view is OPEN.
A timeout/disconnect returns uncertainty and triggers inspect/cancel/stop, **never** subprocess
replay. Reserve/observe the operation first so transport retries cannot duplicate side effects.
At stage/view completion stop all PTYs and all cell processes; wait for the actual cell cgroup-v2
populated=0 (or fail closed). Killing a shell PID or receiving Ctrl-C is not this proof. Background
fork/double-fork/setsid descendants remain in the owned cgroup. Supervisor restart inspects/kills
all labeled owned cells before releasing abandoned generations. Inability to establish terminality
quarantines the view and keeps workspace unavailable, not a timed lease that silently expires.

Optional FastAPI stays cell-internal if actually useful. Existing server/client omit timed_out
(`server.py:62–80`, `bash_executor.py:111–116`); if reused, version their response and preserve
that field, identity, uncertainty and no-replay semantics. Its HTTP success/health/session-close is
not supervisor terminality. Default plan is the thin cell worker reusing PTY machinery, not a
second HTTP management layer or standalone server completion milestone.

### 3.1. Minimal persisted state and retry keys

Use protected JSON files with existing atomic replace/file+directory fsync primitives, not another
session DB. workspace.json keys exactly `{schema_version:1,workspace_id,root_id,relative_root,
root_dev,root_ino,generation,owner_namespace,active_actor,status}`; owner/actor nullable only when
AVAILABLE, status AVAILABLE/OWNED/QUARANTINED. Positive/nonnegative integer rules reject bool.
view.json keys exactly `{schema_version:1,view_ref,actor_namespace,state,input_tree_sha256,
sealed_manifest_id,operation_ids,candidate_scope,plan_ref}`; nullable seal ID before seal, state per §5.
Q76(a): plan_ref is a required nullable key with the EXISTING exact PlanRef shape
`{workspace_relative_path,source_kind,sha256}`. Bind the actual controller-admitted reference once
in protected immutable view/execution context, not from exec/worker text or an invented raw hash.
Both pin_reader/create_view admission must agree with that trusted reference; candidate_scope's
reference must equal it. VERIFICATION/MUTATION/CANDIDATE admission needs a nonnull plan. Ordinary
no-active-workflow execution (and appropriate pre-source provisioning) can have null; an active
workflow's PROJECT view still needs its admitted reference. This adds no routing/workflow mode.
The supervisor rechecks actual bounded no-follow source bytes/hash before fresh view admission
or execution and binds the returned receipt's plan hash to the context. A mismatch before reserve
blocks effects; a mismatched backend receipt after reserve remains uncertain, never DONE/proof.
Q75 completed original-reply replay is unchanged: it does not reread a now-changed source or renew
admission, because no work is being re-executed. Memory cache loss still blocks replay.
`ProtectedPlanContext` is the frozen trusted value supplied by REQUIRED resource authority; its
source_root and formal_evidence policy are private, never new wire fields. Policy must join the
actual controller-admitted/protected execution context; do not infer ordinary policy merely from
PROJECT purpose or a null reference. Construction alone is not authority. The actual protected view loader/persistence, controller admission bridge and
registered-root ownership checks must be supplied by real WorkspaceAuthority integration before
production activation; existing injected dispatcher tests do not prove those consumers.
Do not put raw grant tokens into either file. Revision/pin retention references persist before
acknowledging a pin; restart never garbage-collects a pin with uncertain ownership.

Operation journal `operations/<operation_id>.json` keys exactly `{schema_version:1,operation_id,
request_id,op,namespace,view_ref,input_sha256,state,container_id,cancel_requested,result}`;
state RESERVED/EXECUTING/DONE/UNKNOWN, container_id nullable before create/for non-exec, result
nullable until determined (typed per-op NONSECRET result projection). Non-grant results retain
their closed §2.1 shape. For acquire_writer/handoff, projection is exactly
`{view_ref:null,generation,revision_id}`; for pin_reader/create_view it is exactly `{view_ref}`.
The capability field is OMITTED, never stored/redacted-to-null as a substitute grant. Validate
projection against both the issued grant and original proof BEFORE durability, including secrets
disguised as identity strings. Full grant-bearing reply and original replay proof live only in
protected process memory; no second journal. For every mutating request operation_id is
`op-<request_id>`; exec.payload.operation_id MUST equal it. One journal supplies deduplication,
not separate competing request/execution histories. Hash canonical JSON of op/namespace/view_ref/
payload, excluding credentials/request ID. Canonical encoding is UTF-8 JSON, sorted object keys,
compact comma/colon separators, no ASCII escaping or nonfinite numbers. Same ID+different input
rejects. After actual durable DONE, exact completed input returns its original result only under
ordinary authorization or the strictly bound Q75(a) memory exception above; unknown state inspects/
stops rather than re-executes. Non-exec mutation losses (including publish/install) are observed
by exact original-operation/request replay, NOT inspect/cancel or an invented ExecutionReceipt.
A grant-free projection is never enough to synthesize a successful original grant-bearing reply.
Cache saturation refuses new entries without replacing old replies; it has the same fail-closed
uncertainty rule as cache loss. Journal owner must validate DONE before remembering a completion.
Grant secrets may be cached only in protected process memory; restart revokes them, quarantines
old owned views until inspected/drained, and issues fresh grants only after safe reconciliation.

## 4. Workspace writer, input policy, file tools and readers

Protected supervisor state is host-root-owned `/var/lib/first-agent-execution/` (systemd
StateDirectory); it is NOT below the controller-writable FA state bind. Layout:
`workspaces/<workspace_id>/{workspace.json,writer.lock,current.json,intent.json,revisions/,views/}`.
Registration contains normalized approved canonical root, root `(st_dev,st_ino)` and stable ID.
Reject aliases with the same identity AND ancestor/descendant registered roots (including bind-mount
aliases); nested projects share the containing workspace ID. Path-string equality alone is insufficient. Root identity cannot silently rebind after rename/symlink
replacement. No model-controlled state-root override. Keep session metadata and DBs in their
existing roots, never inside cell mounts.

Only one supervisor process may own the authority root: hold a protected startup flock and reject
a second instance. One process-shared writer flock plus durable monotonically increasing generation
per workspace.
Persist acquisition/generation before handing out a writable ViewRef. On restart no old generation
is resumed as writable. Old cells must be stopped/inspected before a new writer is admitted.
No TTL lease, automatic preemption, extra lock daemon or parallel scheduler. Another session/run
gets WORKSPACE_BUSY for mutation. Read-only pins remain available on complete immutable revisions. Standalone chat acquires mutation
ownership for its active turn, seals/publishes/releases at turn end, and keeps only a reader pin
between turns; a persistent conversation must not monopolize the workspace indefinitely.

Current SessionManager rejects cross-session reuse. Change `_check_reverse_workspace_ownership`
explicitly: new session + explicitly selected existing registered workspace is permitted as a new
**reference**, not ownership transfer; acquire_writer still arbitrates all mutations by workspace
identity. Session manifest/SQLite remain session-scoped; no mass rename/rekey or second session DB.
Keep v1 session manifests unchanged where possible; validate all existing manifests, register their
canonical roots under the supervisor lock, reject contradictory/corrupt records. Old run IDs remain
reserved. Reuse never reruns Git remotes/hooks/readiness against a canonical live workspace.
New workspace provisioning must use the supervisor's provisioning view and publication, not manager's
current host-direct Git path; approved source copies are data inputs, project Git commands/hooks
run inside that cell. Unavailable credentials/network/toolchain means blocked, not host cloning.

Before first snapshot, ensure no legacy unsupervised runtime retains a writable canonical bind.
Deployment maintenance stops old controller/PTY/subagent processes before installing the new
mount model. No coexistence fallback. The controller may read protected state; canonical writes
belong only to the supervised publisher. All product mutation actors, including chat/pair tools,
Git-mutating helpers and future children, use the same authority. Privileged out-of-band host/admin
edits are TCB maintenance: require maintenance/quiescence; detected base conflicts block, never merge.

Snapshot current **filesystem bytes**, including staged/unstaged/untracked input and deletions,
not Git HEAD/clean checkout. Retain the canonical Git index byte-for-byte. Closed initial copy
policy: regular files, directories and in-root nonescaping symlinks as data; reject external
symlinks, special files, hard-linked regular files, excessive count/size/depth, and traversal.
Do not follow symlinks during copy/export. Writable cell tree has no canonical `.git`, `.fa/admission`,
controller state, credentials, or supervisor paths. Preserve safe symlinks in input only if
materialization and rooted readers enforce the same policy; candidate export rejects changed/new
symlinks in v1. This is an explicit limitation, not silent symlink dereferencing.

Version the concrete input limits in trusted config: default 100,000 entries, 2 GiB total,
64 MiB/file, depth 64; failure names a bounded policy error. Exclude `.venv`, dependency caches,
the entire `.fa` control/artifact/cache tree, known controller/log/state roots and configured credential files; default project
`.env` excluded. Larger/generated/secret-dependent projects need explicit approved input profile,
not a model exception. Dependency cache is separately approved/read-only, not a secret-bearing
copy of host caches. Model can read approved project files; this is not a general DLP system.

If Git is needed in a view, initialize private metadata inside the cell from approved materialized
input. Do not expose canonical config/hooks/index/objects through a mount or promise canonical
history/staging semantics inside that private repo. Canonical index/user edits remain unchanged;
publication imports approved source edits as unstaged. Tests requiring canonical history need an
explicit safe input disposition, not hidden access to protected `.git`. Record this compatibility
limitation in help and acceptance; it is not satisfied by a clean checkout losing dirty input.

File write/edit handlers call the supervisor's descriptor-rooted view IO and use the same working
view as PTY; no controller direct writes to canonical paths or separate stale shell copy. Preserve
existing tool names/ToolResult and transaction observations; carry view identity internally. Keep
edit_file._find_fuzzy in the controller: read a bounded snapshot, compute replacement with the existing
fuzzy/first-match algorithm, send exact new content plus expected SHA. Do not reimplement fuzzy edits
in the privileged service or replace the public old_string/new_string fields with a new tool schema.
Serialize model mutator calls within an actor; expected_sha detects ordinary stale reads, NOT a
kernel CAS against arbitrary background shell writes. Rooted IO revalidates path/inode identity; a
concurrent replacement is an explicit conflict, never silent retry. Final authority is the actual
post-terminality sealed tree, not a tool's claim of atomicity against same-owner background code.
Read/search select the active working view or an independent immutable pin as specified in §4.2. Active PlanRef is read-mounted from a pinned revision; do not pretend a leaf read-only bind alone
prevents ancestor substitution inside a private tree. Protected path/identity changes or aliases in
the candidate are rejected at seal/import. Overwrite/unlink/rename/parent substitution cannot alter
canonical PlanRef or be imported; verifier/eval authority uses the separately pinned snapshot. Planner revisions get one distinct narrow candidate capability.

A reader pin retains immutable revision bytes until release. Parent chat switches only **between**
turns after child completion; never reinterpret an existing file descriptor/path as a new revision.
Retain all revisions/views needed by open pins, jobs and recovery intent. Delete only unreferenced
owned scratch after terminality; automated retention/GC platform is deferred, not mandatory.

### 4.1. Registration and SessionManager cutover

Reject overlapping registered roots, same-inode aliases and root replacement; compare identities
and ancestry, not just resolved path strings. Approved host roots exclude controller/supervisor
state, credentials, daemon sockets and ancestors of them. Data copy must not traverse those paths.
Initial R0 imports dirty current bytes under the same no-writers barrier as later snapshots. Do not
silently keep serving stale current.json when quiescent admin maintenance changed canonical bytes:
explicit re-import under authority (fresh generation/revision) or CORRUPT_STATE/quarantine.

Inject an existing-manager managed provisioner BEFORE `_new_session` calls `_provision_workspace`;
`workspace_preparer` alone is too late. Manager creates/owns session manifest/DB, supervisor alone
creates/registers canonical workspace. Provisioner returns a verified workspace/revision or raises
SessionManagerError; `_prepare_managed_workspace` must propagate not-READY, not log+continue.
After workspace commit, later session/DB failure preserves registered bytes and blocks; manager's
finally/cleanup must NEVER rmtree a supervisor-owned workspace. Only uncommitted owned scratch is
eligible for cleanup. Missing remote/network/credential-dependent clone support is an explicit
compatibility BLOCKED disposition, not a host Git exception. Existing workspace references avoid
re-running clone/remotes/hooks. Corrupt legacy bindings block; old run-ID reservations remain.

Reader grants stay valid against their pinned revision despite later generations; they cannot
write/publish or open a writable PROJECT view. Read-only verification may write only its private scratch.
Write grants require current generation AND current active actor. Handoff invalidates parent's
mutating grant server-side after drain/publication, not merely a thread-local flag; never reactivate
the old token on return, even if the tree did not change. Recheck grants at launch after queueing; already queued
requests cannot run late. Child return settles committed/unknown state before fresh parent view;
use SessionState internal execution binding, not captured legacy workspace paths as authorization.


### E253 — actual owner construction: existing-root registration/R0/writer (before code)

Implement the first real WorkspaceAuthority ownership path in execution/workspace.py; retain
OperationJournal.single_supervisor as the ONE startup lock and journal, not a second lock service.
Existing-root registration is an internal construction API, not a partial production wire dispatcher.
New-root install/provisioning remains the SLICE3 join; do not add a failing factory or permissive gate.
Before snapshot, deployment must already quiesce legacy canonical writers as §4 requires; ordinary
metadata/hash checks detect conflicts, not a kernel CAS or proof of host rollout.

Protected registration uses the exact §3.1 workspace.json schema; E253 initially used generation0/AVAILABLE
(historical initialization superseded by Q77/E254 genesis1 below).
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

**E253 implementation checkpoint:** existing-root/R0/writer ownership now exists, including the
actual generation producer and restart quarantine. Pins/views/admit/drain and CellBackend remain
unimplemented; no command or writable-view permission follows from this owner grant alone.
[Local component evidence](evidence/i03-e253/workspace-owner.json.gz),810owning/1330broader,
15 whole-bank assertion-only kills. The prior pre-code contract above is retained.

**E254/Q77 resolved before code:** the operator delegated the robust production solution;
engineering selects uniformly positive epochs. This supersedes E253's generation0 initialization:
registration persists generation1/AVAILABLE without ownership; first writer advances to2. Existing
AVAILABLE/generation0 records may initialize only under the existing startup lock, after exact R0
validation and no-owner/no-views/no-intent checks plus native writer-lock acquisition. Persist and
reread epoch1 before accepting work. Nonzero epochs never change here; unsafe or uncertain zero
records block. No new counter, grant, protocol exception or restart renewal. See
[Q77](open-questions-2026-10-07.md#q77--genesis-reader-pin-generation-before-the-first-writer).
Pins/views/admission/backend still require actual implementation; positive identity shape is not
a pin grant. Q75/Q76 and final-SLICE6 rollout remain unchanged.

**E254 implementation checkpoint:** positive genesis and safe legacy initialization implemented;
[827case/seven-kill/1347broader local evidence](evidence/i03-e254/genesis.json.gz).
No reader grant/admission/backend or C1/C2 completion follows from positive shape compatibility.

### 4.2. Concrete IO/tool and lifecycle joins (E243)

Use ONE WorkspaceAuthority for registration/generation/admission/materialization/rooted IO. Keep
CT101/102/103 as separate obligations and kill producers, not separate services. Protected metadata
can reuse the existing private JSON/flock/fsync patterns. Do NOT use
`workflow_artifacts._private_artifact_directory` on project/cell-owned directories: it creates/chmods
parents and requires the service UID. Likewise `_replace_private_bytes` installs0600 service-owned
files; project writes must preserve appropriate cell access and safe existing modes, not make later
PTY reads fail. Use a small descriptor-rooted project IO implementation with pinned root identity,
no-follow component traversal, bounded regular single-link targets, fsync and explicit conflict/
durability-unknown results; no `resolve()` containment check followed by a path-based privileged write.

**E244 construction order / rooted-IO contract (before implementation):** build the internal
`execution/view_io.py` descriptor/syscall primitive first, then the one WorkspaceAuthority's
protected metadata, writer admission/drain, R0 materialization and actual admitted IO calls. This
is dependency-order construction inside SLICE2 STEP1–2, not an alternate authority, endpoint,
activation flag or completed CT101/102/103. The primitive consumes already selected root/staging
FDs, trusted cell UID/GID, explicit read/write access and protected-path set. Only WorkspaceAuthority
may select these after admission; a raw FD/ViewRef does not establish principal, generation, pin,
PlanRef or lifecycle authorization. Its close/drain must retain all admitted descriptor owners until
handlers finish; never close/reuse their FD numbers under a running handler.

- Root and staging FDs identify directories on the same filesystem. Staging is service-owned,
  private (0700), outside the cell source tree/mounts and absent from all cell mounts. Duplicate/pin
  descriptors; validate configuration before effects. Traverse relative components with
  O_NOFOLLOW/O_DIRECTORY, cap depth64 and path UTF-8 bytes1MiB; reject empty/dot/dotdot/NUL/absolute
  components. Deny `.git`, `.fa`, `.venv`, `.env` components and trusted additional excluded roots;
  protect the active PlanRef from writes, including ancestor substitution. These checks supplement,
  never replace, materialization exclusions and final seal/import validation.
- Pin each opened parent identity and rewalk from root before/after capture/publication. A detected
  substituted/renamed parent or leaf fails STALE_REVISION before publication; after any possible
  publication it fails DURABILITY_UNKNOWN. Do not follow the replacement or silently retry. A pinned
  root alone does not detect host-authority rebind: WorkspaceAuthority must recheck its protected
  registration/view binding. Root/staging selection is never accepted from wire/model fields.
- Read only regular single-link, non-set-id files; O_NONBLOCK prevents FIFO-open hangs before type
  rejection. Capture at most the approved complete-file limit (default64MiB), reject growth/metadata
  changes/leaf substitution, hash ALL captured bytes, and validate the entire file as UTF-8 without
  NUL (v1 text/binary distinction), not just the window. `offset_bytes >= size` returns empty/eof;
  each window boundary must be UTF-8 aligned, max_bytes in1..1MiB. SHA remains the complete-file SHA.
  A multi-window consumer compares every SHA itself; the wire gains no new snapshot token.
- Validate new content UTF-8/no-NUL/1MiB and expected hash before effects. Null expected_sha256 means
  **expected absence**, never unconditional overwrite (as already specified in §2 operation table).
  Existing-target writes require the complete current-file SHA; mismatch/absence/type/link/identity
  conflict fails explicitly. Controller write facade obtains that snapshot just like edit. Both
  write/edit use the same exact-content writer; fuzzy matching stays in the controller.
- Prepare regular files and missing parent directories under protected staging, not under a
  cell-writable guessed temp name. Install parents with Linux renameat2(RENAME_NOREPLACE), reopen/
  verify the exact installed identity; never chmod/chown an existing project directory. Existing
  regular targets must have configured cell UID/GID and no special mode bits; preserve their0777
  access bits. New files0644, new directories0755, both assigned configured non-root cell UID/GID
  in Linux uid_t/gid_t range1..2**32-2 (reject bool, zero, negative, reserved -1 and overflow before IO).
  No service-owned0600 project outputs; unsupported no-replace/same-filesystem primitives fail closed.
- Null-SHA file creation uses atomic no-clobber link from protected staging; replacement uses
  descriptor-relative atomic rename after another current-target/hash/identity check. Fsync staged
  data/metadata and affected directories, verify installed leaf/parent identities and single-link
  status before success. Remove only owned uninstalled staging entries on failure, never project
  targets or preexisting directories. An interrupted create may leave its known new parent dirs;
  do not recursively roll them back, and do not promise failure is effect-free.
- Use existing closed errors, not a new response schema: INVALID_REQUEST for malformed window/hash/
  text arguments; PATH_DENIED for prohibited/aliased/special/unsafe-owner targets; INPUT_POLICY for
  approved input-size/text/depth limits; STALE_REVISION for detected ordinary conflicts;
  BACKEND_UNAVAILABLE for pre-effect OS/backend failure; VIEW_CLOSED after local descriptor close.
  Any fsync/identity/cleanup failure after possible project effects is DURABILITY_UNKNOWN; preserve
  the failure, reconcile through the existing operation owner, do not retry/reconstruct success.
  Parent-creation collision itself is no-clobber and may use the now-existing validated directory;
  a leaf create collision fails STALE_REVISION, never turns into overwrite.
- Ordinary checks are **not** linearizable CAS against arbitrary shell writers: a final check and
  rename still have a gap. Do not claim every background race is detected or make IO replies formal
  evidence. Isolation prevents aliases into canonical/control mounts; actual terminality plus
  sealed-tree/protected-path validation is the publication authority. Existing safe symlinks copied
  as data are not dereferenced by this text-IO primitive; cell-local read helpers may read only the
  independently constrained mounted source. No host path fallback for PDF/binary/search.

Binary local DoD for this building block: real file/descriptor tests assert complete hashes/windows,
read-your-writes, expected-absence/no-clobber, old-content/mode/UID preservation on conflicts, nested
parent modes, symlink/hardlink/FIFO/protected-path rejection, read-only denial, stale-parent injection,
short writes, staged-file/directory fsync faults, post-publication uncertainty and staging/FD cleanup.
Manual producer mutations rerun the entire owning bank, count only executed assertion failures and
restore exact hashes. Classify this as C0/C3/C4, **not** authority/tool/PTY C1 or kernel acceptance.
The latter remain STEP2/4/5 and final SLICE6; no whole-contract completion from a helper bank.

**View selection is internal, not a model field:** active writer file reads/search/edit use its SAME
OPEN private source tree as PTY, including prior tool/shell edits. An independent reader uses the
exact immutable revision retained by its READ pin, including after a newer writer publishes. Never
route all reads to the base revision, change a pin in place, or rebuild indexes on canonical paths.
A pin may support read-only cell execution on its retained source with private scratch; it cannot
open a writable PROJECT view, mutate source, publish or inherit writer authority. Formal verification
still uses its actual admitted PlanRef and immutable input, not an ordinary mutable chat view.

Map public relative/absolute file paths lexically against the controller's logical workspace root,
then send only validated relative paths. Do not resolve/stat canonical source in the controller to
choose a private-view target. Return logical paths and preserve existing ToolResult/path framing;
filesystem authorization and alias handling remain in the supervisor or isolated read cell.

**Preserve existing ACI rather than expanding19 operations:**

- `write_file.build_write_file_tool` and `edit_file.build_edit_file_tool` keep public schemas and
  `_find_fuzzy`/first-match behavior in the controller. Replace source access only: read a bounded
  rooted snapshot/hash, compute existing replacement, write via service with expected SHA. Keep
  `check_mutation_allowed`/Transaction/record_mutation observations on logical relative paths;
  blackboard-absent permission is never workspace authority. Inject actual managed-view/supervised
  metadata for mutation_guard's version stamps: its current `_base_commit` executes host Git and
  `_file_hash` reads canonical paths, so retaining those calls unchanged is NOT safe reuse. Likewise
  discovery attribution is recorded back through controller `add_search_result_paths`, not lost in
  a helper with no SessionState. No managed metadata → explicit error, never a host fallback.
  `write_file.build_scoped_write_file_tool`
  keeps its exact candidate scope and goes through the same authority, not its old host-private writer.
- `read_file.build_read_file_tool` keeps artifact_id resolution in the controller (controller-owned
  artifacts are not cell input). Project text reads use supervisor rooted IO and existing line/frame/
  telemetry formatting; no Path.read_text canonical fallback. A rooted read captures at most the
  approved per-file input limit (default64MiB), computes SHA over those complete captured bytes and
  returns only the requested window (max1MiB), with eof relative to complete length. Reject oversized
  input, binary/non-UTF-8 or a split codepoint explicitly; no partial hash. Multiple windows must have
  identical whole-file SHA or fail STALE_REVISION, not combine different versions. Ordinary RPC edits/
  writes retain their1MiB content limit and fail explicitly above it; large approved files remain
  readable input, not permission for partial tool replacement. A concurrent shell can still change
  bytes: this is bounded read data/ordinary conflict detection, not formal immutable evidence or
  kernel CAS. Test exact window/hash/EOF/UTF-8/limit behavior, including a file over1MiB.
- **NEW `execution/project_tools.py`** is a thin frozen cell-local CLI, NOT a search engine/service.
  Reuse `fs_search.build_fs_search_tool(db_path, workspace_root)` (including outline/listing),
  `fs_reach.build_fs_reach_tool` and existing PDF readers inside the cell through the existing exec
  operation. Add an internal optional scratch-db argument to fs_reach's builder; fs_search already
  accepts one. Source is `/workspace`, index DBs are per-view `/scratch`, never controller .fa/session
  DBs or readonly dependency cache. No shared mutable index across pins/views. Existing search/reach
  algorithms/schemas remain; no privileged search RPC or supervisor state bind to controller.
  Pass only validated tool name+params as encoded/quoted data to the installed isolated interpreter;
  never capability/host path/namespace/profile from tool text. Cell result is untrusted tool data.
  Serialize the existing ToolResult envelope `{summary,result,error,artifacts}` with artifacts empty;
  bound its UTF-8 JSON below the64KiB worker tail, validate result/error exclusivity/types on return.
  Truncated output, malformed JSON, nonzero/unknown execution, missing helper/parser or unavailable
  backend yields the existing explicit error envelope, never a partial success or host retry. Keep
  large-result/artifact projection in existing controller facades; do not transport arbitrary raw
  PDF/full-file output as an unbounded shell tail. Record read-set/file-read observations back in
  controller session context, not in a fictitious cell session DB. This helper does not run providers.

**SessionManager ordering/recovery:** implement materialization/rooted authority before its managed
provisioner. Inject that provisioner BEFORE `_new_session` calls `_provision_workspace`, not only via
workspace_preparer. Its result must distinguish an uncommitted owned scratch from a registered/
committed workspace and verify workspace/revision; existence-before-call is not cleanup ownership.
Close the new-session namespace cycle explicitly: `_new_session` currently provisions before DB
creation, while CLI calls begin_run only AFTER create_or_attach_session. Before managed registration/
provisioning, create the existing session DB under the still-`provisioning` manifest, build a PRIVATE
provisional SessionContext, and use existing `begin_run(..., None)` to reserve one real provisioning
RunContext (DB binding + run directory). Pass that NamespaceRef to the provisioner. No invented run
string, second run allocator/DB, or public attach to an inactive session. Current begin_run already
opens the session DB and checks context/run ownership without requiring an active-manifest attach;
keep public `_read_manifest` strict. Normal CLI begin_run afterward still reserves its separately
requested run ID, never reuses the provisioning claim. Resume/registered-reference paths that do no
provisioning do not allocate this internal run. Failure retains its run-directory reservation even
if uncommitted session metadata is cleaned; original run IDs never become reusable. Test the actual
CLI/entrypoint lifecycle, not an injected pre-made namespace. This is internal execution identity,
not another session manager or workflow subagent.
A commit followed by session DB/manifest/readiness failure keeps registered workspace bytes intact,
leaves no active session, and reports SessionManagerError. Replay/reconcile the original operation
rather than provision twice. New-session explicit registered reuse bypasses clone/readiness/remotes;
resume preserves original session DB. Update `_check_reverse_workspace_ownership` consumers in BOTH
`_new_session` and `resolve_workflow_workspace`: validate all relevant manifests and supervisor
registration, permit a reference, retain DB/run ownership/corruption rejection. Do not delete the guard
wholesale. Initial new workspace commit/publication is the SLICE3 join; do not claim that path ready
from SLICE2 helper tests or keep host Git as a fallback until then. `_prepare_managed_workspace` must
propagate not-READY after managed readiness runs, not log+continue. At SLICE4 atomic activation,
manager no longer creates/chmods canonical project roots; deployment/supervisor own those roots.

**Binary construction/release tests:** two OS-process writers → one durable grant; revoked queued
launch/write → zero effects; admitted handler → stop waits until it drains; two same-episode commands
→ one cell/two command records/state retained; restart with creation-DONE/live shell → stop before
new writer; file write→PTY read and PTY write→file read/search agree; independent pin sees old bytes/
symbols; dirty/index/sentinels unchanged canonically; corrupt manifests and post-commit DB failure
→ no active session/no canonical deletion. Add syscall/rename/fsync fault cases to owning unit banks;
run actual registry/factory + real Docker versions and full declared-path kills at final SLICE6.
Simulated callbacks/socketpairs cannot close these integrated obligations.

## 5. Seal and publication — three different irreversible operations

View state `OPEN → STOPPING → SEALED → PUBLISHED|REJECTED`; UNKNOWN/quarantined cannot seal.
Close admission of tool writes before STOPPING; wait for active file handlers, then stop/confirm all
cell descendants. Export an immutable ordinary tree manifest (path/type/mode/size/hash/deletion,
base revision, generation), validate path/link/protected-path rules and hash all bytes **after**
terminal barrier. Candidate bytes cannot change between validation and import. Reject stale source
version/hash, generation or base revision. No model-produced manifest is trusted without recompute.
No shell publication or host execution of exported hooks/config. Freeze manifest v1 before its
producer: exact header `{schema_version,workspace_id,generation,base_revision,view_id,tree_sha256,
entries}`; entries sorted unique relative paths, each exactly `{path,type,mode,size,sha256,deleted,
link_target}`. type file|directory|symlink, mode integer permission bits only (reject privilege bits),
size nonnegative integer, deleted bool; file SHA hashes bytes, symlink SHA hashes UTF-8 link_target,
directory SHA/link_target null. Unchanged safe input symlinks only; changed/new links rejected.
Deleted entries must match base entries; tree_sha256 hashes canonical JSON of nondeleted entries
(sort keys, compact separators, UTF-8), not transient run/view IDs. Recompute data hashes before
accepting the manifest; never trust a cell's purported tree hash. No bool-as-integer acceptance.

Use materialized immutable revisions and one current manifest; no live overlay lowerdir or Git CAS.
Managed readers read revisions, never a partially updated canonical working directory. A canonical
working tree remains the exact user-visible path, but is a publisher-maintained projection:

1. Under writer lock, validate sealed change set and create complete immutable Rnext; fsync its
   files/directories. Preserve excluded/protected canonical state (especially .git/index).
2. Durably write intent `{operation_id, generation, base_revision, next_revision, tree_hash,
   phase:PREPARED}` with exact schema and file+directory fsync; no canonical projection writes yet.
3. CAS current base/generation; atomically replace current.json with Rnext and fsync its directory.
   That pointer replacement is the logical revision commit. If durability is uncertain, quarantine;
   inspect/recover the same operation rather than dispatch/replay or assume rollback.
4. Apply the committed manifest to canonical path with no-follow atomic per-file replacements/
   deletions and directory fsync, preserving Git index and rejecting protected destinations.
   During projection/recovery block new mutators; pinned readers see complete Rold or Rnext only.
5. Verify the complete canonical projection hash, mark intent DONE durably, return the committed
   receipt, then update admission/flow. No next coder/parent refresh before projection completion.

Recovery under exclusive authority: PREPARED + old current + no projection writes may discard only
uncommitted owned Rnext; current==Rnext completes projection forward idempotently; mismatched IDs,
missing durable bytes or inconsistent projection quarantine. For ordinary multi-file projection there are no canonical writes before durable
current commit; Q58/bootstrap retain their explicitly distinct intent/commit ordering below.
Never roll committed bytes back to Rold. Reader pins survive independently.
Crash at every filesystem boundary, including after current replace/before fsync and mid-projection,
must yield old complete revision or recovered committed complete revision, never successful partial
current state. Test on the actual approved local filesystem; do not infer power-loss proof from a
process-only SIGKILL test. File/dir fsync unsupported or corruption keeps workspace blocked.

Q58 is **single canonical plan replacement**: use its validated byte buffer and source hash, no
alternate active path. I03 routes this through the same supervisor authority, pins a new revision,
and returns only after exact canonical path/projection is verified; preserve I02 pre/post-replace
failure obligations. Bootstrap is **new project directory install** with Linux renameat2
RENAME_NOREPLACE and a fixed controller-rendered three-file bundle; never overwrite an existing
project or implement existence-check+ordinary-rename. Both integrate intent/recovery but are not
mislabelled as the multi-file current-pointer commit. A successful no-replace rename is irreversible:
post-install admission failure retains valid bundle and blocks, never deletes it automatically.
Its own durable intent precedes install; recovery after a completed rename incorporates the valid
bundle into the published revision/projection forward before new mutation/parent refresh. A generic
PREPARED/old-current cleanup must never delete a successfully installed bootstrap directory.

Candidate grants are not ordinary project writes: existing PlannerDispatch logical candidate path
may remain `.fa/admission/...` for v1 compatibility, but bytes live in supervisor-owned staging,
NOT canonical .fa/admission or a cell/control mount. Internal binding carries source READ grant plus
one CANDIDATE grant; generic tools deny control paths, scoped candidate tools route only exact
candidate_path to its buffer. `candidate_scope.plan_ref` is the pinned v1 PlanRef with source hash.
On seal, validate bounded buffer with existing pure I02 validators; publish of CANDIDATE uses PLAN
intent at the scoped canonical PlanRef path, never imports a candidate directory. Parent/model cannot
choose a promotion destination. Q68 tool failures remain authoritative for the attempt.

`prepare_bundle` is the missing upload/validation handoff: controller supplies its rendered bounded
roadmap/increment bytes; supervisor renders fixed ledger header, independently validates metadata/
paths/hashes/caps and mints validated_bundle_id privately. It is bound to namespace/root generation/
expected base. install_project uses that exact stored bundle and CAS base, no caller-provided ID
without a producer. OWNER grant and view_ref=null are required for prepare/install, with all project
writers settled. On collision do not overwrite or mutate the existing project; on post-install
uncertainty retain it and forward-recover. Ordinary grant creation/read/pin cannot publish buffers.

### 5.1. Exact recovery discriminator, not a generic transaction framework

`intent.json` v1 keys: `{schema_version:1,kind,operation_id,workspace_id,generation,base_revision,
next_revision,tree_sha256,phase,target_relative,old_sha256,new_sha256}`. kind REVISION/PLAN/BOOTSTRAP;
phase PREPARED/COMMITTED/PROJECTING/DONE. REVISION has target_relative/old_sha256/new_sha256 null;
PLAN has exact canonical PlanRef path and old/new plan hashes; BOOTSTRAP has canonical project
relative path, old_sha256 null and new_sha256 bundle-manifest hash. Unknown keys/phase/hash mismatch
quarantine. current.json exactly `{schema_version:1,workspace_id,generation,revision_id,tree_sha256}`.
Revisions/intent are protected supervisor state, never cell/model-authored control files.

| Kind | Irreversible point / recovery when current still old |
| --- | --- |
| REVISION | durable current pointer commit; PREPARED+old pointer can discard owned uncommitted scratch only; never canonical projection before commit |
| PLAN | same-path validated buffer replacement, NOT pointer commit; PREPARED must inspect exact canonical hash: old→no commit, new→complete new revision/current/projection forward, neither→quarantine; never rollback a replaced plan |
| BOOTSTRAP | RENAME_NOREPLACE of rendered directory; PREPARED must inspect installed directory's full approved manifest/hash: absent→no commit, exact new→finish revision/current forward, conflicting→quarantine; never delete installed bundle |

Prepare and fsync complete Rnext plus intent BEFORE any PLAN/BOOTSTRAP replace/install. After their
irreversible point, fsync directory, complete current/projection/DONE forward, then acknowledge.
Missing COMMITTED phase write is not evidence that replacement did not happen. No next writer on
uncertainty; inspect the SAME operation. Fault matrix for EACH kind: before intent; after intent;
after irreversible syscall before fsync; after fsync before phase update; current replace; midway
projection; after DONE before reply; artifact append failure; supervisor kill/restart at each point.
Include ENOSPC, EIO and unsupported file/directory fsync. Process-kill tests are not power-loss proof.

Manifest is the complete approved-source tree; excluded environment/cache/.git/controller/credential
paths are not deletion tombstones and survive projection. Reject deletion/rename/type substitution
of ANY ancestor containing protected/excluded canonical bytes. Preserve canonical .git/index and
unrelated sentinels bitwise, while ordinary allowed deletions/mode changes publish. Tree hash covers
only the approved source domain. Paths sorted UTF-8, directories size0, symlink size UTF-8 byte length;
all privilege bits rejected. Rooted no-follow import never follows a cell-provided path or link.

## 6. Whole execution inventory and verification binding

Mandatory boundary covers **every** project-code entry, not only workflow coder tools:

| Existing producer/caller | Required integration |
| --- | --- |
| `_cmd_run`, `_build_pty_pool`, profiles and tool registry | Whole stage prologue uses boundary wrapper; managed executor required, no None/in-process host fallback |
| `_prepare_managed_workspace`, SessionManager workspace_preparer, entrypoint readiness | Provisioning cell before dependency hooks/imports; unavailable/unknown backend hard-blocks, not current fail-open warning |
| `workspace_bootstrap._run_process`, `scripts/bootstrap/workspace.py` | Commands execute only in authorized provisioning view; no checked-out project interpreter on controller |
| `session/workspace.py::_run_git`, pair_tools._run_git, workflow_controller._git_output | Project Git/config/hooks/filters in cells or replace advisory diff with sealed filesystem diff; fixed argv alone is not a boundary |
| `run_bash` executor and fallback, SubagentRunner.run | Managed cell only; remove host fallback/replay. Chat subagent path is mandatory too, not excused by coder-profile absence |
| slice_verification runner, baseline, import/collection probes, mutation overlay pytest | Noninteractive managed operations on pinned/sealed source plus isolated scratch; all subprocess descendants owned |
| file read/search/write/edit and planner candidate tools | Same ViewRef/capabilities; controller reads are non-executable IO; no canonical writes via legacy handlers |
| mutation_guard._base_commit, run_bash write-set lookup, IntentGuard Git runner, memory/_safe_walk and tools/_common enumeration | Use supervised private metadata or approved snapshot data; read-only/BEFORE_TOOL_EXEC metadata is not an exemption from execution closure |

Complete the [initial inspected call inventory](i03-execution-call-inventory.md) during implementation: file:line, caller, execution
kind, profile, lease/view identity, negative integration test for every row and newly found caller.
Static subprocess searches supplement the inventory; they do not prove closure. Remove SubagentRunner's current X_FA_PROXY_TOKEN injection into project-command environment; a
credential-dependent external-agent command is unsupported unless given a separately approved
non-controller credential profile. Do not claim legacy token-dependent subagent behavior preserved.
Fixed trusted
supervisor Docker invocations are control-plane operations and must never execute model shell on host.

After coder succeeds, stop/seal its candidate before verification. Verify and eval read that same
immutable tree identity in disposable verification views; reports/cache/temp are private scratch,
not source revisions or controller artifacts. Verification source is read-only; project commands
that need generated data use declared scratch/report paths, not source edits disguised as a verify.
Each noninteractive operation is drained to terminality before accepting its receipt; an idle PTY
is never used to certify a test job. Background-service test setups must stay inside one owned job
and stop before its terminal receipt. No daemon survives into another source revision.

Mutation checks reuse I02 AST/parser logic but materialize a derivative with the same supervised
view primitives: only trusted controller receives its write capability, modifies the one permitted
src/scripts target, then seals it for a verification job. Tests come from the immutable base and
remain outside mutation roots. No controller-side project interpreter or unregistered /tmp source
mount. Receipt records derivative input hash **and** original base revision/PlanRef; a normal-source
receipt cannot certify its mutant, or vice versa. Preserve the actual overlay-import oracle inside
that cell. Adapt gate env to approved cell-local PATH/venv/PYTHONPATH/report/sentinel bindings; never
send a scrubbed-but-arbitrary copy of the controller environment over exec. Untranslatable gate
configuration is an error, not a host runner exception. No extra overlay/backend/CAS mechanism.

Reuse workspace_bootstrap._compute_fingerprint/ReadyState rather than another dependency planner:
provisioned environment is bound to the candidate's dependency inputs and approved toolchain/cache
profile. A changed pyproject/lock/profile invalidates old readiness; re-provision in a cell before
verification or block on unavailable dependencies. Project .venv/pycache/report outputs are not
canonical source imports or controller dependencies. Test stale dependency fingerprint explicitly.
Reserve operation ID outside the cell, collect
actual exit/timeout/terminality, parse detailed fresh structured pytest report using strengthened
I02 parser, and bind projected PlanVerification to operation/view/tree/PlanRef identity. Wrong,
missing, duplicate, stale, zero-test, skip-only, collection/runner/setup/infra report is ERROR, never
PROVEN. Ordinary command exit !=0 is FAIL; missing binary **inside an already running shell** is
normally exit 127/FAIL, not launcher ERROR. Genuine launch failure gets a separate negative case.
Do not change Q53(c) slice attribution or add an unapproved clean-control/per-contract map.

Binding proves which supervised operation/tree produced captured evidence; it is **not** a claim
that hostile project pytest hooks cannot forge their own report or that tests prove correctness.
No L2 VERIFIED or cryptographic test attestation is delivered. Q55 real eval/Q56 precedence/T0
compatibility from I02 remain, including Q73 missing/indeterminate completion blocking in BOTH modes
with determinate observe advisory and actual negative eval precedence. Hard integrity/publication
failures cannot finish DONE in either mode.
If coder succeeded but sealing/publication fails, still attempt real eval on last known candidate
with explicit uncertainty (read-only/quarantined data only), then nonzero; never execute project
code from a nonterminal writable view. If no safe view/deadline exists, record unsuccessful eval
unavailability; do not fake a report or release a writer while descendants remain.

### 6.1. Stage/verification transitions — Q74 operator-selected checkpoints

After confirmed terminality and path/security validation, checkpoint permitted ordinary edits at
EACH mutating episode/stage boundary, even if provider/stage/functional judgment fails. Failed
workflow stays failed, no rollback promise. Q58 retains separate validated plan replacement.
Workflow-end-only unpublished branches are NOT built; one current revision remains sufficient.

Use this single state transition table (no reopening SEALED views):

| Transition | Required action / next source |
| --- | --- |
| start / initial planner | acquire one workflow owner; admitted R0 pins input; ordinary planner read-only; scoped candidate capability remains distinct |
| T0 | one managed noninteractive read-only-source job on admitted R0; genuine red/empty baseline remains allowed; errors block before coder; preserve T0 bytes through repair/replan |
| coder or chat mutating episode ends | drain file handlers, stop all cells/PTY descendants; seal immutable candidate; security-valid source checkpoint→Rn/current/projection before next episode; functional PASS is NOT a publication prerequisite |
| stage nonzero/interrupt | same bounded stop/seal attempt; allowed terminal edits may checkpoint, stage remains failed; unknown/live/quarantined view cannot publish or release |
| verify / eval | separate READ source Rn with disposable scratch; real eval receives Rn/PlanRef and exact attempt evidence; never read changing OPEN source or stale parent root |
| repair/repeated coder | allocate NEW OPEN view from authoritative Rn after prior publication; old PTY sessions do not resume across stage/view boundaries |
| planner plan revision | buffer-only candidate, shared admission validation, same-path Q58 commit through authority; new Rplan pins updated plan; T0 reuse only with exact unchanged slice→TESTS topology |
| terminal workflow / child return | settle all jobs/intent and persist result; failed result never becomes DONE because bytes checkpointed; parent opens a new view at actual committed current |

Verification v1 supports read-only source: fixed cell-local environment supplies PYTHONDONTWRITEBYTECODE,
pytest cache/basetemp and coverage/report paths under `/scratch`, and approved read-only dependency
venv/toolchain. Never run uv sync against excluded project .venv by accident. Dependency fingerprint
includes pyproject/lock/toolchain/profile; provisioning on a private writable copy builds a separate
environment, not a source revision. In-place build/test requirements need a reviewed scratch mapping;
unsupported source-writing verify commands fail explicitly, not silently switch to writable source
or host fallback. Test these compatibility cases BEFORE choosing the main-host E2E target project.

Use ONE sidecar `execution.json` v1 in the existing private run directory; retain existing I02
admission/T0/verification formats/readers rather than add arbitrary fields to closed v1 schemas.
Sidecar keys `{schema_version:1,run_id,workspace_id,records}`. Each record exactly `{kind,artifact_sha256,
plan_sha256,revision_id,original_revision_id,tree_sha256,operation_ids}`; kind T0/STAGE/VERIFY/KILL,
SHA fields64hex, operation_ids nonempty unique supervisor IDs, immutable record order. Full sanitized
receipts are read by ID from private supervisor evidence, not cell paths; no capabilities recorded.
Persist the artifact then link/hash durably before accepting it. New managed consumers require a
matching sidecar+receipt; legacy v1 remains readable as LEGACY, never accepted as bound managed proof.
A crash between artifact/link is indeterminate, not a reason to recapture T0 or dispatch coder.
T0 binds its initial revision/plan; permitted later plan revisions use validated admission lineage
and unchanged topology, NOT a false requirement that original T0 SHA equal latest plan SHA.

Extend existing junit_nodeid_plugin/parser with bounded per-test setup/call/teardown outcomes and
collection/runner error facts; keep the old boolean nodeid projection for T0. Kill PROVEN requires
fresh expected run+operation+source binding, actual normal pytest exit1, at least one CALL-phase test
failure, zero collection/setup/teardown/runner errors and zero skip-only proof. Exit2–5, malformed/
missing/duplicate/stale/oversize report, timeout, wrong mutant/base or failed import probe is ERROR.
Do not classify a setup failure as a producer kill. Test actual report fixtures for every phase.
Mutation source derivative is immutable before project execution, retains original-base+PlanRef
binding and never modifies tests or canonical current. Every declared TESTS path still executes.

Explicit plumbing, not ambient path inference: add frozen internal ExecutionBinding (namespace,
owner/view/source identities, client reference; no token fields) to WorkflowContext and SessionState.
ExecutionClient alone caches raw grants in private memory and selects them for the typed operation;
never serialize its cache/object as a tool result. Forward binding explicitly through run_commands,
capture_test_nodeids, verify_plan/verify_slice, _run_one and _run_kill_check; executor threads must
not assume ContextVar propagation. Missing binding in a production/library execution call returns
ERROR/BACKEND_UNAVAILABLE, never the legacy host runner. Pure parser calls remain independent.
`_run_managed_command` receives command + binding + timeout/deadline; `_validate_bound_pytest_report`
receives expected stage checkpoint/source/PlanRef plus actual receipt/report, rejecting a merely
self-consistent replay from another revision. StageResult links the completed checkpoint/operations;
legacy bare Path is display identity, not an execution capability.

Whole-stage integration seam: keep `_cmd_run` public args/transport/secrets/outcome_sink/planner_dispatch
signature; validate pure inputs first, call `run_stage_with_plan_write_boundary` with `_cmd_run_inner`
as body and trusted internal execution binding. Inner prologue uses managed SessionManager provisioner,
managed registry/executor and rooted IO; do not recursively call `_cmd_run` from its wrapper. Preserve
outcome_sink/global aggregate semantics and planner dispatch capability. Wrap entrypoint/manager
provisioning separately because it can precede `_cmd_run`. Failure before first project instruction
must execute zero project commands. Add StageResult source-revision/operation links internally (not
model JSON); stop/seal/checkpoint at the controller stage choke point before verifier/eval/repair.

## 7. Nested acquisition and Q66 — source-grounded design, E231

Use real outer drive_session → actual invoke handler → `_run_planner_managed_workflow` → child
run_workflow → `_cmd_run` → drive_session. Reuse the CURRENT workflow_tool._child_run_context (already calls SessionManager.begin_run);
do not allocate the child twice or recreate the old parent-context defect. Child uses the same session
DB, with **new** RunContext/run_log_dir and parent link in execution/event metadata, never parent's
artifact directory. Claim before child artifacts/provider. Parent stays synchronous: close/drain its file commands, stop all parent cell writers, seal and
publish any allowed pending parent edits before child snapshot. Keep the root writer/generation;
delegate one active actor scope to the child, not a second flock or two writable views. Root lease
owner and child actor run are distinct validated identities, linked by controller-owned metadata. Parent with no writer can acquire for the child; other sessions remain
blocked. On return create a fresh parent view from authoritative committed current, including changes
committed by an ultimately unsuccessful child. Never resume its old writable view; uncertain
publication keeps mutation unavailable, while old reader pins remain usable. Future workflow
subagents must inherit that same owner/view/cancel scope; remain absent
from workflow registry until separately proved. No parallel subagent scheduler here.

Q59 operator decision: ordinary chat remains generalist/advisory with manual invoke AND the
EXISTING experimental mid-chat suggestion injection. Preserve expansion/routing/turn_context and
existing --inject/config plumbing and their current semantics; no new injection name, strict router,
--require-workflow flag, success guard or forced escalation. Source: expansion.py:10–23,
routing.py:3–13, cli.py:2408–2437. Mandatory managed execution is separate from advisory workflow
choice; neither injection nor prompts guarantee invocation. Nested E2E must observe actual invoke;
no invoke is a failed/unfulfilled witness, not a new production enforcement feature.

Preserve existing invoke_workflow public task/roles/mode/budget fields and validate raw types with
the I02 shared normalizer before coercion/child allocation. A coder-bearing managed invocation
must include its initial planner because no outer PlanRef field exists; otherwise return
acquisition_requires_planner before child/provider, not a guessed default target. Non-coder-only
workflows retain their existing purpose and do not invent acquisition to justify a coder bypass.

Q60 delegated engineering selection (reuses current surfaces; no parallel state machine): one strict JSON choice,
duplicate/unknown keys rejected, no file map/raw ledger/destination/frontmatter:

- `{kind:SELECT_EXISTING, project_slug, increment_id}`. Slug lower kebab ≤48 chars; increment ID
  `I[0-9]{2,}`. Controller inventories regular canonical increment files, validates their metadata,
  maps this stable pair to exactly one canonical relative path. Existing roadmap ID need not equal
the directory slug: validate declared roadmap↔increment linkage, do not rename the current RM-
planning-topology IDs to fit the bootstrap template. Selectable status is IN PROGRESS in BOTH roadmap and increment, with matching active-increment;
OUTLINED/SHIPPED returns clarification, not automatic mutation authorization. Ambiguous/duplicate/missing match
  does not glob-and-guess or bootstrap automatically.
- `{kind:BOOTSTRAP_NEW_PROJECT, project_slug, increment_slug, roadmap_body, increment_body}` with
  strict UTF-8, slugs as above, no model frontmatter, ≤1 MiB each rendered file/≤2 MiB bundle.
- `{kind:NEEDS_CLARIFICATION, reason}`; reason `AMBIGUOUS_PROJECT|MISSING_CONTEXT|UNKNOWN_INCREMENT`.
  Return to parent chat with zero coder/eval, no implicit project creation. No arbitrary reason text
  in admission control record; ordinary user-facing conversation remains allowed.

Controller renders H1/frontmatter IDs/UTC date/status/active I01; increment I01 metadata/status/
slice count from validated body and shipped `—`; ledger **header only**, no generated E# evidence.
Input roadmap_body has exactly the H2 sections Intent and Out of scope (subheadings allowed);
renderer supplies fixed Artifact schema and its OWN Increments table with exactly I01 IN PROGRESS and the correct
`increments/increment-01-<increment_slug>.md` link. No model-owned status table. Both body inputs
forbid frontmatter/H1/control-metadata lines outside fenced examples; increment STEP records must all be TODO, no claimed
shipped/verified state. Reject invalid plan grammar/kill directives before publish. Exact rendering fixtures live
with managed-acquisition tests; do not introduce the future I04 ledger parser. Bootstrap no-clobber
per §5. Shared I02 admission and bounded repair follow valid acquired PlanRef, before T0/coder.

Managed admission **v2 implementation contract**, selected under delegated Q60 engineering judgment:

- Top keys: v1 keys plus `workspace_id`, `owner_run_id`, `generation`, `base_revision`;
  schema_version is integer 2. owner_run_id is the root lease owner, run_id is child actor;
  generation is positive integer (not bool). IDs are `ws-<32 lowercase hex>` and
  `rev-<32 lowercase hex>` allocated privately, not content-addressed storage/CAS keys.
- PlanRef stays the exact v1 three-field object; EXPLICIT, EXISTING_SELECTION and BOOTSTRAP now
  have real producers. Initial PlanRef may be null, before managed planner acquisition.
- Every attempt has the exact v1 keys plus `input_revision`, `output_revision`, `operation_id`,
  `bundle_sha256`. input_revision is nonnull registered revision; output_revision null until a
  committed change, otherwise its registered ID. operation_id is null or `op-<32 lowercase hex>`
  linking the supervisor publication receipt, not model-supplied process output. bundle_sha256 is
  null except bootstrap, where it hashes the complete rendered three-file manifest; candidate/
  promoted SHA fields still hash **plan bytes**, not the whole bundle.
- Preserve v1 enum/type/hash/route consistency rules UNCHANGED for v1 and existing v2 attempt
  kinds. New v2 ACQUISITION cross-fields are explicit (do not fake a publication on selection):
  EXISTING_SELECTION sets source_sha256/PlanRef SHA to captured bytes, candidate/promoted/bundle
  SHA null, input_revision==output_revision and operation_id null; establish canonical hash from
  source. ADMITTED requires actual validation PASS. BOOTSTRAP has source null, candidate SHA of
  rendered plan and promoted SHA equal candidate ONLY after committed verified install, plus
  matching output revision/operation/bundle receipt; establish canonical hash from promoted SHA.
  Blocked pre-selection/clarification has null PlanRef/source/candidate/promoted and no output
  revision/operation/bundle. Rejected rendered bootstrap may retain candidate/bundle hashes but
  no promotion/PlanRef/output revision; no invented committed effect. A reserved install operation
  remains recorded on failed/lost acknowledgement; inspect its journal rather than retry. Until
  receipt confirms commit, no promoted SHA/committed revision claim; retain any installed directory
  and quarantine uncertainty, never delete it as cleanup. RETRY is allowed only for
  actual determinate validation FAIL of an acquired plan, via existing shared repair. Missing or
  indeterminate acquisition outcome blocks without retry. Persist acquiring history before first
  provider and actual outcome afterward, then use the unchanged durable admission-before-coder
  barrier. Test all these joins with v1 fixtures and mixed valid/invalid histories. Initial managed choice uses ACQUISITION;
  initial planner acquisition consumes the configured initial planner stage once (free), never
  follows it with a duplicate ordinary planner. Required repair/replan uses the shared counter.
- Keep all v1 rule tables; v2 extends bootstrap rules with `invalid-body`, `invalid-metadata`,
  `invalid-grammar`, `too-large`, `collision`, `prepare-failed`, `install-failed`,
  `durability-unknown`, `hash-mismatch`. Add validator `selection` with `choice-malformed`,
  `choice-missing`, `unknown-project`, `unknown-increment`, `ambiguous-project`,
  `ambiguous-increment`, `status-not-active`, `needs-clarification`. Add validator `workspace`
  with `busy`, `stale-generation`, `stale-revision`, `quarantined`, `backend-unavailable`,
  `terminality-unknown`. Unknown pairs still fail; no arbitrary message/source/path field.
- Clarification is a BLOCKED admission/route with selection/needs-clarification, not an invented
  admitted plan; tool returns a typed clarification outcome to parent chat, zero coder/eval.
  Workspace/terminal uncertainty is ERROR/INDETERMINATE/BLOCKED, never a repairable FAIL.
- Versioned reader accepts old complete v1 as v1, new complete v2 as v2, never 'upgrades' old
  records or silently inserts missing binding fields. Admission file belongs to child namespace.

These are concrete values, not an enum to invent during coding. SLICE5 STEP1 freezes fixture
examples and tests these exact keys/rules against existing v1 invariants before implementing the
v2 branch. Delegation selects the design; only actual implementation/proof establishes readiness. Only a controller-minted
managed capability, bound to that child/owner/generation, permits the initial no-PlanRef planner;
CLI/direct explicit callers retain I02 guards. No public boolean/path field bypass is introduced.

Q66 implementation is not conditional policy: `_make_workflow_ctx_provider` captures **current**
messages at invoke time, not registry construction. Build a bounded initial planner **user task**
alongside its own prompt/skills, no SYSTEM parent transcript and no public `context`/PlanRef field.
Initial packet max 32 KiB and 8 recent messages plus explicit goal; redact configured credentials,
retain goal separately, never truncate UTF-8 mid-codepoint. On oversized goal/context ask for concise
clarification rather than silently discard the task. Ordinary existing context logging allowed;
do not globally enable debug bodies or design anti-persistence machinery. Retry/replan packets
contain ≤8 KiB distilled state/diagnostics/latest draft reference, not the original parent packet.
Prove a unique parent-only fact reaches initial planner and does not recur in repair/replan.

### 7.0. Current surface audit and smallest implementation delta (E231)

| Reuse current producer | Already real / exact extension |
| --- | --- |
| tools/workflow_tool._child_run_context:387–403 | Validates parent/session/workspace and calls begin_run today; call once in managed wrapper, not another allocator. Keep non-coder path. |
| WorkflowContext + run_workflow + _run_stage + _run_admission_repair | Keep the ONE workflow machine/budget/history/aggregate. Private ManagedAdmissionEntry permits initial no-PlanRef planner only after actual child/owner grant validation. Do not run an extra pre-workflow planner then replay planner in run_workflow. |
| planner_dispatch.PlannerDispatchKind:17–20 / PlannerDispatch:33–55 | Existing ORDINARY/ADMISSION_REPAIR/EVAL_REPLAN and exact candidate target are real. Add ACQUISITION to THIS type, no candidate target/active plan until selection; managed grant required, read/search+final choice only. Other variants' validation stays unchanged. |
| coder_loop.SessionOutcome.final_text:403–408 | Read strict acquisition JSON from actual initial planner final_text. StageResult carries private parsed choice; no model-facing new context/path field or alternate provider loop. |
| plan_admission.read_plan_snapshot/snapshot_from_bytes:133–168 | Reuse exact bytes/hash/UTF-8/size/IDs for selected and rendered plans, supplying EXISTING_SELECTION/BOOTSTRAP source_kind rather than trusting model hashes. |
| workflow_controller._validate_plan_admission:2231ff / _run_admission_repair:2370ff | Reuse both pure validators and bounded existing repair AFTER valid acquisition; no duplicated admission engine or free initial planner retry. |
| admission_schema._record_plan_ref:93–104 / _record_attempt:154–182 | EXISTING_SELECTION, BOOTSTRAP and attempt ACQUISITION labels already exist, not working acquisition producers. Keep v1 reader EXACT; add explicit v2 branch for bindings/rules, never mutate old records or invent a fresh schema system. |
| plan_promotion.publish_plan_buffer:183–221; scoped write_file:113–150 | Keep validated buffer/source-hash/mode and Q68 failed-tool logic; transfer FS effects into SAME supervisor candidate/publication authority. Not an arbitrary model file-map API. |
| tools/prepare_pr.build_prepare_pr_tool:186–283; pr_draft.PrDraftStore:45–118; cli.py:1788,2285–2290 | Actual pr_prepare producer and current-session digest already exist. Reuse draft validation/store/IntentGuard seam; bounded controller-only run artifact IO, not source publication or another draft engine. |
| plan_ids.extract_plan_ids/precheck and existing PyYAML dependency | Reuse grammar/IDs and YAML parsing machinery. No general new planning/YAML framework, no I04 ledger parser. Skill frontmatter loaders are permissive/fallback-based and not safe admission validators. |

Actually missing (new narrow pure helpers in managed_acquisition.py): strict choice parser, stable
pair resolver, deterministic fixed-three-file renderer. Bounded source AST/name/caller inspection finds no existing managed
choice/selection/renderer producer; existing source_kind strings are NOT evidence those mechanisms
exist. Keep all three helpers behind the existing controller, not a new orchestration service.

Internal ManagedAdmissionEntry holds child RunContext, source READ binding and owner grant reference
(no raw token/public bool). `_validate_workflow_request` still validates raw types BEFORE coercion;
then direct/CLI callers without entry retain missing-plan rejection. Managed entry requires first
configured planner, exact child/session/workspace/root-owner/active-actor binding and acquired view
before provider. Initial _run_stage uses PlannerDispatchKind.ACQUISITION and normal outcome_sink;
consume final choice there exactly once, install/select/admit before T0/coder. Invalid choice or
clarification records BLOCKED with null PlanRef and zero coder/eval; no automatic bootstrap or free
planner retry. Preserve additional requested stages and aggregate initial planner usage once.
Acquisition is read/search/final-choice only: `_build_run_tool_registry` currently unconditionally
registers pr_prepare at cli.py:1788. Filter this EXISTING post-profile addition for ACQUISITION;
otherwise a read-only profile silently gains a writer. Preserve pr_prepare in ordinary/scoped
stages, current-session provenance and Q68 sticky failed-pr_prepare semantics. Its destination is
controller-owned run_log_dir/pr_draft.md outside cell/source mounts, never a caller path; protect
through existing ArtifactStore/run-directory ownership. It does NOT write root-owned supervisor
state and needs no new supervisor wire operation. Review IntentGuard/read_current_text after the
IO adapter change; failed draft persistence never marks the draft trusted.
`_run_planner_managed_workflow` only allocates/delegates/invokes run_workflow/restores parent; it
must NOT become a second acquisition/workflow state machine. Non-coder-only delegation stays intact.

Metadata parser helper `_parse_artifact_metadata`: frontmatter≤4KiB UTF-8, flat scalar mapping,
existing PyYAML SafeLoader with duplicate-key rejection; forbid aliases/anchors/custom tags/nested
values, no permissive skill-loader fallback. Validate required canonical keys/types/linkage from artifact schema §§2/3; slices is integer
1–7, not bool; created is an ISO calendar date (normalize YAML date/string); unknown control keys reject. Canonical roadmap keys Roadmap-ID/slug/created/status/active-increment (existing
supersedes optional); increment keys Increment-ID/Roadmap-ID/status/slices/shipped. IDs/linkage are
not guessed from slug. Use existing plan grammar on the COMPLETE rendered text so positions stay
correct. Keep fixture examples for current RM-planning-topology IDs and generated new-project IDs.

### 7.1. Acquisition source/data handoffs and existing-code reuse

Reuse `_child_run_context`; NamespaceRef parent_run_id is controller-attested after actual begin_run.
Reserve invocation count/child ID once before first provider; retries keep identity and shared budget.
Use real SessionOutcome.final_text for strict managed-choice parsing, not a new temporary plan path
or ordinary chat tool output. A managed acquisition planner uses read/search plus its approved
choice response; it cannot write a canonical bootstrap directory via generic file tools. Q68 failed
publication-tool outcomes still invalidate scoped repair; recovered read/search does not.

Do not add a mandatory-route CLI mode, a new autosuggestion policy or a replacement for the existing
expansion/injection mechanism. Test default/direct chat and suggestion-enabled chat remain usable;
only the managed execution boundary is mandatory. User asks/manual tool dispatch can request the
workflow; the parent must receive truthful child/clarification status, not an invented guarantee.

Freeze literal rendering fixtures before implementing renderer: project directory
`worklogs/<project_slug>/`, roadmap.md, ledger.md, `increments/increment-01-<increment_slug>.md`.
Controller owns frontmatter: Roadmap-ID `RM-<project_slug>`, Increment-ID `RM-<project_slug>-I01`,
roadmap created=UTC date/status IN PROGRESS/active-increment I01; increment status IN PROGRESS,
slices=actual extracted count, shipped=—. ledger is fixed heading only, no model E# rows.
roadmap_body is Intent/Out-of-scope prose ONLY with those exact two headings; controller
renders Artifact schema and Increments table/link. increment_body is validated slice grammar, no
frontmatter, no duplicate increment/roadmap/status metadata or lifecycle claims. Reject disguised
metadata outside code fences using existing MarkdownIt tokens, not substring deletion or a new
general Markdown parser. Preserve literal examples; the UNCHANGED full-plan IDs/precheck/kill
validators still interpret grammar-looking fenced text as documented by schema §4/CT13. This is
not a new ignore-fences mode. No free-form model path/file map. Build all bytes and both validators before
new-project install; invalid acquisition blocks, while acquired existing PlanRef still uses shared
bounded I02 repair. Stable selection validates declared roadmap linkage AND active-increment/status;
matching a filename/IN PROGRESS alone is insufficient. Multiple active matches clarify, never guess.

Q66 requires one explicit loop handoff: coder_loop's live conversation_history is LOCAL, absent from
SessionState. Supply a controller-owned current-message snapshot callback at the pre-tool-dispatch
boundary after compaction; `_make_workflow_ctx_provider` consumes that snapshot at invocation, not
registry construction or replaying parent DB as child history. Copy bounded user/assistant/tool DATA,
no parent system/tools/auth headers, preserve current goal/constraints and label tool content untrusted.
Initial planner dispatch consumes the packet ONCE using existing PlannerDispatch phase; subsequent
repair/replan tasks use distilled state, even though WorkflowContext.task_for('planner') normally
reuses the same override. SecretRedactor applies before crossing chain and ordinary logs remain. If the managed coder path
has no live snapshot, return needs-clarification before planner; do not claim Q66 from a goal-only
fallback. Preserve legacy non-coder delegation rather than blocking all nested requests.

## 8. Tests and mutation policy

Local unit/model tests may fake the UDS transport to classify errors; they do not certify kernel
isolation. Add real Linux/Docker fixtures under `tests/integration/` and a declared `execution_host`
marker, using approved test profile and disposable authority roots. Required integration invocation
sets FA_REQUIRE_EXECUTION_HOST=1; absent Docker/cgroup/profile becomes test failure, not skip.
Default no-host unit suite may skip host tests but is not the release gate. Cleanup is bounded,
checks cgroup terminality, and never deletes live user roots. No privileged broad host probes.

Core local C1 must use actual supervisor/cells and mock only ProviderChain.request.
Adapt existing workflow_fixtures/_ct91_public and CLI lifecycle fixtures to the new registered view
authority; ordinary tests may fake transport only when labeled unit/C0, never silently demote the
existing C1 bank. Mark real-kernel fixtures individually, not the whole mixed C0/C1 public module.
Default no-host skips are explicit and do not discharge any required release/kill proof. Include
existing SessionManager/nested/deadline/history/runner regressions in their owning TESTS paths. Assert useful
persisted receipts/artifacts and host sentinels, not only a helper returning true. Full-path producer
kills retain Q53(c), source restoration and cost; newly planned producer paths must exist before
reporting any kill. CT96/CT97 retain their original stage/handler kill identities. Additional CTs
name small new mechanisms; no kill of unrelated hook/feature-flag registration counts as isolation.

## 9. Final deployed acceptance / Q63

All former I02 SLICE7 CT88/CT89 and STEPs1–10 become I03 SLICE6. Keep original producer keys and
unique cases, separate local vs host proof, planner oracle/coder handoff/independent manual review,
review-before-fixture order and fresh review on material change. No machine approval marker.

**E223 operator-approved acceptance transfer — all four obligations remain INCOMPLETE:**

- [ ] **Deployed functional/source-to-behaviour verification:** use SLICE6 STEP9/10's case index
  to verify retained I02 admission, repair/promotion, T0, eval/routing/failure and new I03 claims
  against actual deployed code/image/config and observed effects/artifacts. Arena local tests
  and I02 plan-versus-diff review are inputs, not a deployed verdict.
- [ ] **Environment/readiness and inherited baseline acceptance review:** SLICE6 STEP10 and the
  release-gate DoD review the intended Ubuntu/Docker/Python environment, readiness/hooks and
  preserved I02 baseline/candidate manifests/phase identities. Include replacement-test intent,
  historical Mypy diagnostics/unreproduced ninth context and relevant source-root hook observations.
  Resolve or explicitly disposition each inherited issue for final acceptance; do not suppress
  checks, fabricate ready state, invent a mandatory FA Go runtime or relabel red results green.
- [ ] **Broad independent implementation/evidence review:** SLICE6 STEP7 keeps manual review
  before fixtures/helpers; STEP10 and final DoD record final independent I02+I03 implementation/
  security/recovery/evidence review, including actual source-to-claim coverage and material-change
  follow-up. This is distinct from the narrower I02 plan-versus-diff review.
- [ ] **Integrated E2E and deployment signoff:** SLICE6 STEP10 and CT88/CT89 require all reviewed
  host cases, actual deployment identities and final operator signoff in the I03 acceptance record.

The [I02 closeout/evidence record](i02-local-acceptance.md) and
[migration bank §9](i02-to-i03-scope-migration-2026-10-15.md#9-e223-closeout-acceptance-transfer--2026-10-16)
are inherited inputs; their factual red/unknown outcomes and original proof identities stay intact.
Transfer is not completion or a baseline PASS/waiver. I02 may close locally before these obligations;
I03 may not ship with them incomplete. This plan-only update runs no host cases or diff review.

Q63 operator decision: live result is exactly `NOT RUN|PASS|FAIL|BLOCKED`. Every state may have an
optional `commentary` string (≤512 UTF-8 bytes, single line, redacted); omission is valid in ALL states.
No mandatory reason field, reason enum, hardcoded BLOCKED subtype or parsing commentary for control
flow. Keep immutable append-only attempts and source/image/config/run/command/effect/artifact/reviewer
fields. This result vocabulary does not change admission/wire diagnostic code tables, CT status,
roadmap/increment status, generic READY or active I01. Only operator/independent evidence reviewer
assigns live results, never coder/harness/local tests. Short commentary is explanation, not proof.

Before normal main-host update obtain operational maintenance approval: stop legacy writable
runtimes, install supervisor/profile/UID/cgroup/UDS configuration, validate immutable image/import
closure and mounts, preserve existing workspaces/state, verify deployed code SHA **and** image/config
identity. No update/merge/deploy is performed by this planning review. If fa update is nonzero,
inspect printed HEAD/health/test rc and stop: deploy may already have happened. No blind retry.
No staging host assumed. First gate workflows observe; enforce starts only after operator review;
backend/admission/integrity floor remains mandatory in both. Record unique run IDs, exact commands,
exit/effect/artifact paths, profile/kernel/daemon/FS facts, bounded redacted evidence. Local green,
all-skipped, NOT RUN, blocked or unobservable never counts as PASS. Full I03 SHIPPED requires all
required unique producer cases reviewed PASS, no unresolved blocked case or policy/deployment gate.


### 9.1. Minimum live workflow witness and acceptance execution order

Required in addition to all producer-specific controlled cases:

1. An authorized deployed explicit-plan planner→coder→eval happy path with production ProviderChain
   and real configured providers: meaningful source edit, a test exercising the edit, actual T0,
   verification, eval report, terminal DONE/exit0 and sealed/published source identity.
2. An authorized deployed outer chat→actual invoke_workflow→managed SELECT_EXISTING child on a
   disposable registered workspace, also with real providers (including outer chat). Prior parent
   constraint reaches first planner, child namespaces differ, actual coder/eval and parent refresh
   are observed. No invocation means NOT a successful witness, even if chat says it completed.
3. Controlled deployed BOOTSTRAP_NEW_PROJECT, clarification, failure/repair, concurrency, no-replay,
   isolation and recovery cases retain useful artifact/host-sentinel oracles; provider stubs may be
   used ONLY when explicitly labeled provider_mode=CONTROLLED. At least the two witnesses above
   are provider_mode=REAL: no ProviderChain/transport/stage/supervisor mock, transcript replay or
   injected success. Record resolved role/model family/config identities and disjoint eval policy,
   budgets, actual calls and redacted usage. This is not an LLM-quality/calibration benchmark.

Final SLICE6 order: freeze oracle/case index and Q63 schema → source-backed handoff → independent
manual review → implement FINAL e2e/I03 helpers → review actual helper diff/commands → run local
conformance/release checks and all accumulated kernel/mutation checks → maintenance/deploy approval
→ quiesce/back up immutable old image/config/state references → install/update → verify actual
SHA/wheel/image/profile/mount/UDS health → reviewed observe runs → operator review → enforce runs
→ independent evidence judgments and integrated signoff. Q73/backend floors apply even in observe.
No planned/controlled/local-only witness is automatically a REAL/live PASS.

Main host is NOT a staging host. Test supervisor authority/labels/approved roots are disposable and
disjoint from live workspaces/secrets/daemon-management paths; mutation of authorization/publication
producers may not gain access to real user roots. Trusted operator-reviewed test drivers/setup are
TCB test code, not permission to run arbitrary project pytest/conftest in controller. Project tests
still run only in cells; main-host fixture commands stay outside default discovery and require
explicit approval. Local tests/integration are not the final e2e/I03 helper package. No host run in
this plan review. Unavailable host/profile/cache/provider or safety prerequisites keep acceptance open.

Cutover rollback is NOT workspace rollback: before irreversible commits, restore the known old
image/config only if it can interpret new state safely; after any new-format state/publication,
stop/quarantine and forward-recover with compatible supervisor. Never auto-downgrade, erase new
intent/admission v2, delete committed bundles or restart legacy writable controllers. Maintain a
source/image/config/state-format compatibility record and recovery command sheet before cutover.


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

Actual pin_reader/read_file/release_reader retention and proof path now exists;52native cases,
879owning/sixteen full-bank kills/restored879/broader1399.
[Local evidence](evidence/i03-e255/readers.json.gz). Successful release retires FDs/heavy maps
idempotently after reader drain, retains disk references; no GC or token reconstruction. Writable
views/execution admission/backend remain absent. The pre-code declaration above remains the scope.
