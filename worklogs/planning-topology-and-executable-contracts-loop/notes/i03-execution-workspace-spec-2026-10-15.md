# I03 execution/workspace implementation specification

Date: 2026-10-15. Baseline product source `d9109f4`; source evidence in the adversarial review.
This is a proposed implementation specification, not deployed behavior. New files/functions below
are **planned**, not discovered interfaces. Core mechanics can be specified now; §7's Q59/Q60
choices and §9's Q63 vocabulary need exact operator disposition before their slices are dispatched.
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
| `src/fa/execution/cell_worker.py` | Thin cell-local adapter reusing PtyPool/InProcessPtyExecutor and result framing; no independent host authority |
| `src/fa/execution/workspace.py` | Same supervisor's registration, writer flock/generation, materialized revisions/candidates, rooted file-tool operations/read pins |
| `src/fa/execution/publication.py` | Same authority's seal validation, prepare/commit/projection/recovery and no-clobber project install |
| `src/fa/inner_loop/managed_acquisition.py` | Small pure approved-choice parser, stable-ID resolver and controller bundle renderer; no separate workflow state machine |

`WorkspaceAuthority` is a helper owned by the supervisor, not a separately deployed service.
Reuse private IO primitives introduced for I02, but keep publication commit semantics separate.

## 2. Launch, wire protocol and installed profile

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
launch. Host wrapper help must use installed trusted help or delegated isolated controller, not
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
Max control frame 4 MiB as an independent encoded-frame cap (body caps do not imply wire size),
max individual tool text 1 MiB, bounded output tails 64 KiB/channel. Commands are opaque text;
cwd is relative to an authorized view. Neither wire nor model accepts host paths, image, Docker
flags, mount lists, arbitrary environment, networking, UID, cgroup path or publication destination.
Authenticated controller selects immutable approved profile ID; supervisor expands fixed config.

Closed operations: health, register_workspace, acquire_writer, pin_reader, create_view, read_file,
write_file, edit_file, exec, inspect, cancel, stop_view, seal, publish, install_project, release.
Wire envelope v1 is exactly `{protocol_version:1, request_id, op, namespace, view_ref, payload}`.
request_id is a controller UUID key; namespace is null only for health, otherwise exactly
`{session_id,run_id,parent_run_id}` (parent null when absent). view_ref is null only for operations
that precede view creation; other operations carry the validated ViewRef, not a string path.
Reply exactly `{protocol_version:1,request_id,status,result,error}`; status OK|ERROR, one of result/
error nonnull. error exactly `{code,retryable,operation_id}`; code closed:
INVALID_REQUEST, UNAUTHORIZED, UNAPPROVED_PROFILE, WORKSPACE_BUSY, STALE_GENERATION,
STALE_REVISION, VIEW_CLOSED, BACKEND_UNAVAILABLE, EXECUTION_UNKNOWN, TERMINALITY_UNKNOWN,
PATH_DENIED, INPUT_POLICY, COLLISION, DURABILITY_UNKNOWN, CORRUPT_STATE. No exception text.

Payloads are separate closed per-op dataclasses/schemas, not arbitrary kwargs. Key shapes:
register_workspace `{root_id,relative_root}` against a configured approved host-root ID (never an
absolute host path); acquire_writer `{workspace_id}`; create_view `{workspace_id,base_revision,access}`;
write_file `{path,content,expected_sha256}` and edit_file `{path,old,new,expected_sha256}` are rooted
capability-relative IO with bounded UTF-8; exec `{operation_id,profile_id,command,cwd,timeout_ms}`;
inspect/cancel `{operation_id}`; stop_view/seal/release `{}` against view_ref; publish
`{sealed_manifest_id,expected_base_revision}`; install_project `{validated_bundle_id,project_slug}`;
pin_reader `{workspace_id,revision_id}`. Receipt/status data are structured result variants (§3).
The controller reserves a unique op-UUID before sending exec; supervisor persists that ID and input
binding before starting it. Other mutation request IDs likewise deduplicate by exact input hash;
a reused key with different input fails, never replays. IDs refer only to supervisor-created state,
not caller-supplied manifests/bundles or filesystem locations. Bind every stored result to caller
namespace and reject cross-run inspection. Release cannot discard state needed by live jobs/pins.

Every mutating request validates namespace, current lease/generation and allowed view capability.
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

## 3. Identity and job lifecycle

NamespaceRef = `{session_id, run_id, parent_run_id?}` from existing manager/bindings. WorkspaceRef
is an opaque stable workspace_id from protected registration, not a run/session label. ViewRef =
`{workspace_id, generation, base_revision, view_id, owner_run_id, access}`; access is READ|WRITE.
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
launch/backend denial raises ExecutionUnavailable, confirmed timeout raises ExecutionTimedOut with
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

## 4. Workspace writer, input policy, file tools and readers

Protected supervisor state under the existing configured FA state root's `execution/` subtree:
`workspaces/<workspace_id>/{workspace.json,writer.lock,current.json,intent.json,revisions/,views/}`.
Registration contains normalized approved canonical root and stable ID; same canonical root/aliases
cannot register a second writer domain. Root identity cannot silently rebind after rename/symlink
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
`.fa/admission`, known controller/log/state roots and configured credential files; default project
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
existing tool names/ToolResult and transaction observations; carry view identity internally.
Read/search use the pinned view. Active PlanRef is read-mounted from a pinned revision; do not pretend a leaf read-only bind alone
prevents ancestor substitution inside a private tree. Protected path/identity changes or aliases in
the candidate are rejected at seal/import. Overwrite/unlink/rename/parent substitution cannot alter
canonical PlanRef or be imported; verifier/eval authority uses the separately pinned snapshot. Planner revisions get one distinct narrow candidate capability.

A reader pin retains immutable revision bytes until release. Parent chat switches only **between**
turns after child completion; never reinterpret an existing file descriptor/path as a new revision.
Retain all revisions/views needed by open pins, jobs and recovery intent. Delete only unreferenced
owned scratch after terminality; automated retention/GC platform is deferred, not mandatory.

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
compatibility from I02 remain; hard integrity/publication failures cannot finish DONE in either mode.
If coder succeeded but sealing/publication fails, still attempt real eval on last known candidate
with explicit uncertainty (read-only/quarantined data only), then nonzero; never execute project
code from a nonterminal writable view. If no safe view/deadline exists, record unsuccessful eval
unavailability; do not fake a report or release a writer while descendants remain.

## 7. Nested acquisition and Q66 — exact proposal, Q59/Q60 still OPEN

Use real outer drive_session → actual invoke handler → `_run_planner_managed_workflow` → child
run_workflow → `_cmd_run` → drive_session. Child uses SessionManager.begin_run in the same session
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

Q59 proposal: ordinary chat remains generalist/advisory, always managed for execution. Explicit
`--require-workflow` is controller-owned opt-in: router-only read/search/context/invoke registry,
no write/edit/shell/subagent/Git mutators, and refusal to finish with 'success' without an actual
workflow invocation. This flag/name/guarantee needs explicit disposition; do not make it default or
claim prompt compliance guarantees invocation. No selected workflow → clarification/BLOCKED outcome.

Preserve existing invoke_workflow public task/roles/mode/budget fields and validate raw types with
the I02 shared normalizer before coercion/child allocation. A coder-bearing managed invocation
must include its initial planner because no outer PlanRef field exists; otherwise return
acquisition_requires_planner before child/provider, not a guessed default target. Non-coder-only
workflows retain their existing purpose and do not invent acquisition to justify a coder bypass.

Q60 proposal (supersedes old free-path recommendation if approved): one strict JSON choice,
duplicate/unknown keys rejected, no file map/raw ledger/destination/frontmatter:

- `{kind:SELECT_EXISTING, project_slug, increment_id}`. Slug lower kebab ≤48 chars; increment ID
  `I[0-9]{2,}`. Controller inventories regular canonical increment files, validates their metadata,
  maps this stable pair to exactly one canonical relative path. Existing roadmap ID need not equal
the directory slug: validate declared roadmap↔increment linkage, do not rename the current RM-
planning-topology IDs to fit the bootstrap template. Proposed selectable status is IN PROGRESS;
OUTLINED/SHIPPED returns clarification, not automatic mutation authorization. Ambiguous/duplicate/missing match
  does not glob-and-guess or bootstrap automatically.
- `{kind:BOOTSTRAP_NEW_PROJECT, project_slug, increment_slug, roadmap_body, increment_body}` with
  strict UTF-8, slugs as above, no model frontmatter, ≤1 MiB each rendered file/≤2 MiB bundle.
- `{kind:NEEDS_CLARIFICATION, reason}`; reason `AMBIGUOUS_PROJECT|MISSING_CONTEXT|UNKNOWN_INCREMENT`.
  Return to parent chat with zero coder/eval, no implicit project creation. No arbitrary reason text
  in admission control record; ordinary user-facing conversation remains allowed.

Controller renders roadmap IDs/date/status/active I01; increment I01 metadata/status/slice count
from validated body; ledger **header only**, no generated E# evidence. Require roadmap Intent,
Artifact schema, Increments, Out of scope sections and correct I01 link. Reject body metadata/status
smuggling and invalid plan grammar/kill directives before publish. Exact rendering fixtures live
with managed-acquisition tests; do not introduce the future I04 ledger parser. Bootstrap no-clobber
per §5. Shared I02 admission and bounded repair follow valid acquired PlanRef, before T0/coder.

Managed admission **exact v2 proposal**, conditional on STEP1 disposition:

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
- Preserve v1 enum/type/hash/route consistency rules. Initial managed choice uses ACQUISITION;
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

These are concrete proposed values, not a blank enum to invent during coding. Q60 STEP1 must
approve/amend and freeze this schema and choice/rendering fixtures explicitly. The implementation
cannot claim acquisition readiness while that disposition remains absent. Only a controller-minted
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

## 8. Tests and mutation policy

Local unit/model tests may fake the UDS transport to classify errors; they do not certify kernel
isolation. Add real Linux/Docker fixtures under `tests/integration/` and a declared `execution_host`
marker, using approved test profile and disposable authority roots. Required integration invocation
sets FA_REQUIRE_EXECUTION_HOST=1; absent Docker/cgroup/profile becomes test failure, not skip.
Default no-host unit suite may skip host tests but is not the release gate. Cleanup is bounded,
checks cgroup terminality, and never deletes live user roots. No privileged broad host probes.

Core local C1 must use actual supervisor/cells and mock only ProviderChain.request. Assert useful
persisted receipts/artifacts and host sentinels, not only a helper returning true. Full-path producer
kills retain Q53(c), source restoration and cost; newly planned producer paths must exist before
reporting any kill. CT96/CT97 retain their original stage/handler kill identities. Additional CTs
name small new mechanisms; no kill of unrelated hook/feature-flag registration counts as isolation.

## 9. Final deployed acceptance / Q63

All former I02 SLICE7 CT88/CT89 and STEPs1–10 become I03 SLICE6. Keep original producer keys and
unique cases, separate local vs host proof, planner oracle/coder handoff/independent manual review,
review-before-fixture order and fresh review on material change. No machine approval marker.

Q63 exact proposed enum remains `NOT RUN|PASS|FAIL|BLOCKED` with proposed mandatory BLOCKED reason
`DEPLOYMENT_UNAVAILABLE|SAFETY_STOP|EVIDENCE_MISSING|PREREQUISITE_UNRESOLVED`; not ratified here.
Before package finalization obtain exact disposition or keep that step open. Only operator or an
independent evidence reviewer assigns live results, never coder/harness/automatic local checks.

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
