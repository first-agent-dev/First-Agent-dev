# R13 managed subagent plan — read-only/scratch first rollout

**Status:** R13's W0 Arena-local row DoD is CLOSED (2026-11-04): managed child
behavior, Q122 per-view profile binding, configured-backend negative and
approved-backend positive production-caller oracles, Q124 request/quota/report
proof, and targeted producer/caller kills pass. Global Q113 W0 remains OPEN
until every S4P1 row passes; W1 has not started. Live-host ledger-append and
Docker ENOSPC/mount-release E2E remain NOT RUN and are reserved for the final
wave; Docker host execution is not a W0 requirement.

**Date:** 2026-11-04
**Scope:** R13 S4P1 row and full W0 implementation/negative oracle, the global
Q113 W0 exit, and post-I03 observer sequencing. W1 does not reimplement R13.
**Related:** `notes/i03-execution-call-inventory.md` R13; `roadmap.md` I03 and
observer section; `open-questions-2026-10-07.md` Q121 (operator excerpt);
`increment-03-execution-workspace-foundation.md` W0/W1.

## 1. The clarified contract

The operator's product statement (2026-11-04) is the active contract:

- The two primary surfaces are ordinary `fa run chat` and the heavier workflow
  invoked from that chat.
- A subagent may be called directly from ordinary chat and from workflow
  `planner` and `coder` roles.
- The stable contract is: one restricted generic toolset shared by all parent roles in the first slice; stateless Bash
  (no inherited stateful parent shell); only the delegated task as conversational
  input, not the parent's transcript/context overhead; and a completion report
  returned to the caller.
- Tool policy and scoped execution authority may be supplied as system/runtime
  metadata, but must not become replay of parent history.
- The operator wants a limited, read-oriented same-session chat while a workflow
  continues. This is a requested experience to evaluate, not a ratified I03
  requirement.

The operator's 2026-11-04 refinement (this plan):

- All subagents are read-only for **existing** project files.
- A subagent may write **new artifacts/notes only** in a private scratch area.
- All pre-existing project files are blocked for writing by the subagent.
- The subagent does the work; the main agent receives the report and takes it
  into work. This avoids concurrent mutations.
- The legacy role names are not capability profiles. The subagent is generic;
  the parent role (chat/planner/coder) determines the task.
- The coder subagent is **disabled by default**; each role has its own
  capability flag, default off, in the config file.
- The child uses the chat provider chain, like the ordinary chat role.
- The observer is W-A first, then W-B; W-C is rejected.

## 2. Decision and rationale

### 2.1 R13/W0 sequencing — full behavior in W0 (operator supersedes prior option A)

- Implement the actual generic child in W0 through ordinary chat and workflow
  planner/coder production callers. Do not ship a temporary deny-only route.
- The child uses the S-C read-only/scratch boundary, task-only input, stateless
  Bash, restricted toolset, bounded report, and per-role/default-off admission.
- Bring the minimum Q122 profile-set/per-view binding into this R13/W0 slice;
  the child must use a non-interactive READ view/profile, never the parent
  interactive/write executor.
- Remove controller `subprocess.run` and proxy-token injection from managed
  composition; preserve the legacy manual/controller path.
- Negative oracle: one bounded child `EXEC` request through production
  `drive_session`/registry to a real local supervisor that refuses before
  worker/cell launch. Assert `exec_requests=1`, `exec_allowed=0`,
  `cell_launches=0`, `host_subprocesses=0`, `proxy_credentials=0`,
  `project_writes=0`. Positive composition proves successful managed read-only
  child invocation and bounded report return.
- Q113 remains unchanged: R13 is one S4P1 row; global W0 closes only after all
  R01-R28 named negative oracles pass through their production callers. W1 still
  starts only after global W0; it does not redo R13.
- This supersedes the earlier Q121 option A split. No Q113 weakening or host
  fallback is authorized.

### 2.2 Subagent execution — S-C restricted first rollout + private scratch

- The first implementation is **not** S-A writer handoff. It is S-C (read-only
  child for every role) plus a narrow writable private scratch for new
  artifacts/notes.
- The subagent receives a pinned read view of the latest **published**
  revision. It cannot write to existing project files.
- The subagent may create new notes/artifacts in the cell's writable scratch.
  The report carries the notes/artifact references to the main agent.
- The main agent (chat/planner/coder) receives the report and applies/persists
  it. The subagent does not mutate the project.
- The coder main agent retains the write capability. The coder subagent is
  read-only/scratch for diagnosis/analysis; it does not edit code.
- There is no writer handoff, no second writer, and no concurrent mutation in
  this slice. This is the explicit S-C limitation: a subagent cannot implement
  and test a bounded change; the main agent must do the mutation.
- S-A remains the next step if the operator later funds a write-capable coder
  subagent. S-A requires the full handoff/settlement/uncertainty proof and is
  outside this slice.

### 2.3 Observer — W-A first, W-B target, W-C reject

- W-A: a separately addressable read-only observer attachment for the same
  session/workflow. It reads bounded durable status/event rows and pins the
  latest published revision. It cannot write files, run a second workflow,
  alter authoritative workflow state, or cancel/advance the workflow.
- W-B: the product target after I03. A durable workflow child plus a
  same-session read-only chat lane; restricted observer profile; event cursors;
  revision pins; owner/capability separation; admission/close behavior; explicit
  tool-registry restriction while the workflow is active. `invoke_workflow` stops
  being a blocking call in this mode.
- W-C: reject. Full chat tools plus workflow mutation creates two writers and
  races on read versions, workspace ownership, publication, and stage evidence.
- The observer is post-I03 and is not an implicit side effect of adding
  subagents. The roadmap sequencing remains the baseline.

## 3. Target architecture

### 3.1 One generic subagent capability

The subagent is a nested `drive_session` (`src/fa/inner_loop/coder_loop.py:434`)
with:

- a fresh `SessionState` and a new `run_id` derived from the parent's run id;
- the same `session_db` (child events are durable and visible with a distinct
  run id);
- no inherited parent blackboard, artifact store, telemetry, PTY pool,
  worktree manager, transaction, log, Bash executor, or workspace port;
- a new `transaction` (the child's read/write set is not passed to the parent);
- a restricted tool registry bound to a managed read view;
- a minimal child hook registry (SandboxHook + observe-only IntentGuard bound
  to the child task/view; no parent transcript). Observe-only is intentional:
  the child toolset has no project mutation tool and the supervisor READ view is
  the mutation authority; IntentGuard enforce mode can launch a controller-side
  `git diff` subprocess and would reject private `/scratch` writes before the
  supervisor sees them;
- the chat provider chain (`provider_chain`) and chat compactor chain;
- a task-only prompt: the generic subagent system prompt + the delegated task;
- a bounded `max_turns`/timeout and the atomic per-session spawn budget;
- a validated `SubagentReport` as the only return channel.

The subagent is **not** a shell command. The legacy
`src/fa/inner_loop/subagent_runner.py` and
`src/fa/inner_loop/tools/spawn_subagent.py` are not the managed path.

### 3.2 Read-only project view + writable scratch

- The subagent receives a pinned reader at `managed.current_revision_id`.
  The child runner constructs a child binding
  `ExecutionBinding(child_namespace, managed.binding.workspace_id)` and calls
  `managed.client.pin_reader(child_binding,
  revision_id=managed.current_revision_id, plan_ref=..., deadline=...)`
  (`ExecutionClient.pin_reader`, `src/fa/execution/client.py:255`). The
  `pin_reader` is a client call, not a `ManagedExecution` method; the child
  namespace is the child run id, not the parent namespace. The returned
  `GrantReply` carries the READ/PROJECT `ViewRef`.
- The reader is a READ view; the project source is mounted read-only by
  `ExecutionProfile.create_spec` (`src/fa/execution/profiles.py:75`, source
  mount `ReadOnly: view.access is Access.READ` at `:100`).
- The cell's `scratch` directory is writable (`CellBackend` mounts it
  read-write). The subagent may write new notes/artifacts there.
- The subagent's tool registry omits `fs_write_file`, `fs_edit_file`,
  `fs_spawn_subagent`, and `invoke_workflow`.
- The subagent's `fs_run_bash` uses a read-only managed executor. The project
  source is read-only; the scratch is writable. The subagent cannot modify
  existing project files.
- The report carries `notes`, `artifact_refs`, and `evidence` to the main agent.
  The main agent decides whether to persist them in the project.

### 3.3 Generic subagent toolset

The first slice uses one generic toolset for all parents:

- `fs_read_file`
- `fs_run_bash` (read-only project + writable scratch)

`fs_search` and `fs_reach` are **not** in the first-slice toolset: the managed
cell-local search/reach fail closed when `workspace_io` is not None
(`src/fa/inner_loop/tools/fs_search.py:1061`,
`src/fa/inner_loop/tools/fs_reach.py:136`). The first slice uses `fs_read_file`
and read-only `fs_run_bash` for inspection; `fs_search`/`fs_reach` are added only
after S2P4 wires the managed cell-local index.

`fs_blackboard_query` and `fs_exploration_metrics` are also excluded from the
first slice: `blackboard_query.py:143-154` calls
`ensure_artifacts_indexed(session.blackboard, session.workspace_root, ...)`,
which reads the host workspace and mutates the shared parent blackboard; and
`fs_exploration_metrics.py:128-130` calls `session.clear_gold_files()` on
`reset=true`. The first slice uses only `fs_read_file` and read-only
`fs_run_bash`; a view-bound read-only blackboard/metrics source is a later
option.

No write/edit tools, no `fs_spawn_subagent`, no `invoke_workflow`. The parent role
determines the task, not the child's capability. Role-specific toolsets are a
later option, not part of this slice.

### 3.4 Read-only managed Bash executor

The current `ManagedBashExecutor` (`src/fa/execution/client.py:700`) is
interactive-only and requires `Access.WRITE`:

- `if not profile.interactive ...` at `:723`;
- `view.access is not Access.WRITE` at `:728`;
- `run(..., session_id="main")` at `:805`.

The supervisor already supports non-interactive profiles and read-only views:

- `CellBackend.execute` (`src/fa/execution/backend.py:198`) has a
  non-interactive branch at `:236`;
- `profile.interactive != (session_id is not None)` is enforced at `:319`;
- `ExecutionProfile.create_spec` mounts the source read-only for READ views.

The plan adds a read-only/stateless managed executor (or generalizes
`ManagedBashExecutor` with `read_only`/`interactive` modes) that:

- accepts a READ view and a non-interactive profile;
- passes `session_id=None`;
- issues one `Operation.EXEC` per command;
- never falls back to host subprocess or PTY.

The supervisor's `admit` uses the view's profile (Q122 resolution): the
authority binds a profile set; `create_view`/`pin_reader` select the profile
based on access/purpose (READ -> read-only profile; WRITE -> write profile);
the view record carries `profile_id`; `admit` validates `payload["profile_id"]`
against the view's profile and checks `profile.interactive != (session_id is not
None)` (`src/fa/execution/workspace.py:5357-5364`,
`src/fa/execution/backend.py:319`). The read-only child uses the non-interactive
read-only profile; the parent stages use the interactive write profile. The
`ServiceConfig` adds `read_only_profile_id`; the `WorkspaceAuthority` adds a
profile set and `view_profile(view_ref)`; the `CommandReceipts` and
`OwnedCellTermination` use the view's profile. The `ViewRef` wire is unchanged;
the view record's `profile_id` is internal. If the read-only profile is not
configured, the child returns a structured `subagent_profile_unavailable`
result, not a host shell or PTY. The profile is a deployment/config input, not a
model field.

### 3.5 Report contract

The report is a `SubagentReport` (extending `SubagentEnvelope`):

- `task_id` (the child run id), `parent_role` (chat/planner/coder), `goal`
  (the delegated task), `exit_code` (mapped from `SessionOutcome.exit_code`),
  `summary` (bounded child final message, <= 8000 chars), `verification`
  (the child's test/command evidence);
- `notes` (the child's new notes, bounded; the content, not only a path);
- `artifact_refs` (new artifact paths in the scratch; optional; the content is
  in `notes`/`evidence` because the scratch is private to the view and is not
  readable by the main agent after release);
- `evidence` (command outputs, test results, file references; bounded);
- `files_changed` (new artifacts only; no existing project files);
- `patch_diff` (empty; the subagent does not edit existing files);
- `risks`, `open_questions`, `next_action`;
- `token_usage` (best-effort; `SessionOutcome` does not carry token usage, so
  the field is optional in the first slice and must not be fabricated);
- `duration_ms`;
- `terminal_state` (the confirmed child outcome: `stopped_by_llm`,
  `iteration_cap`, `abnormal_stop:<reason>`, `chain_exhausted`,
  `request_shape`, `interrupt`).

The report is built from the `SessionOutcome` (`final_text`, `tool_results`,
`failed_tools`, `stop_reason`, `turns`) and the child's final message. The
`notes`/`evidence` are extracted from the child's final message and the
`fs_run_bash` tool results; the child is instructed to write a bounded report
with notes/evidence in its final message. The report is validated against a
JSON schema. A lost/uncertain child result returns a structured failure; no
retry, no guessed recovery. The reader is released if possible; the parent
remains fail-closed.

The report is persisted to the run log dir, not to the project. The
`write_envelope_artifact` path (`.fa/subagents/<id>.json` in the workspace) is
not used by the managed child; the managed report writer uses the run log dir.

The `SubagentEnvelope.type` enum is extended with `subagent` (or the parent
role); the `from_verifier` shell path is not used by the managed child. A
`from_session_outcome` classmethod builds the report from the `SessionOutcome`.

### 3.6 Child role prompt and PinnedBuffer

`drive_session` selects the base prompt with
`_ROLE_PROMPTS.get(role, CODER_SYSTEM_PROMPT)`
(`src/fa/inner_loop/coder_loop.py:1087`). `_ROLE_PROMPTS` has `planner`, `coder`,
`eval`, and `chat`, but no `subagent` (`src/fa/inner_loop/prompt.py:1149`).
A child `role="subagent"` would therefore get the **coder** base prompt, with
`GENERIC_SUBAGENT_PROMPT` only appended as extra text. The plan adds a
`SUBAGENT_SYSTEM_PROMPT` and a `"subagent"` key to `_ROLE_PROMPTS`. The child
prompt is the read-only/scratch subagent prompt + the delegated task; it is not
the coder prompt and not the parent transcript.

`drive_session` also creates `PinnedBuffer(state.workspace_root)`
(`src/fa/inner_loop/coder_loop.py:611`), and `PinnedBuffer.refresh` reads
`AGENTS.md`, `knowledge/llms.txt`, and `llms.txt` with `Path.read_text()`
(`src/fa/memory/pinned_buffer.py:45-52`). For the child, this bypasses the READ
view and can inject more project text than the task-only contract allows. The
plan adds a `pinned_buffer` (or `workspace_reader`) parameter to `drive_session`,
defaulting to the current behavior for the parent. The child passes a
**view-bound reader** that reads the three pinned files through the child's
`ClientWorkspacePort` (READ view), or a **disabled** buffer if the operator
prefers a task-only child prompt with no project instructions. The parent path
is unchanged. The child must not read the pinned files from the host workspace.

### 3.7 Q122 per-view profile implementation boundary

Q122 option A fits the existing supervisor and its minimal profile-binding work is pulled into R13/W0. Before R13/W0 acceptance:

- Bind `read_only_profile_id` and `view_profile_id` to validated profiles; a missing
  read-only profile makes the child unavailable before view/EXEC admission. Never
  fall back to the interactive parent/write profile for a child.
- The current `profile_set_sha256()` hashes profile definitions but not the
  read/write role mapping. Extend the supervisor identity digest so changing
  either selected profile changes health identity, even when the approved profile
  set is otherwise unchanged.
- Resolve the profile from the durable view record across `WorkspaceAuthority`,
  `CellBackend` (episode lookup, CANCEL, PTY control and reconciliation),
  `CommandReceipts`, `ViewStopper` and `OwnedCellTermination`; retain
  `approved_profile` only as a compatibility accessor for write-owned paths.
- Keep legacy view-record compatibility explicit; new READ child views bind the
  non-interactive profile, and `admit` rejects profile/access/session mismatches
  before any cell launch.

Tests must prove role-map identity changes, per-view profile use in backend and
recovery consumers, legacy view-record compatibility, and fail-closed absence of
`read_only_profile_id`. These details complete Q122's accepted direction; they do
not authorize W1 before W0 closes.

## 4. Lifecycle

### 4.1 Read-only/scratch child (all roles)

1. Validate the per-role flag: master `subagent_spawning_enabled` AND
   `subagent.<parent_role>.enabled`. If false, return
   `ToolResult.fail("subagent_disabled", ..., retryable=False)`.
2. Reserve one spawn slot atomically
   (`SessionState.try_reserve_subagent_spawn`,
   `src/fa/inner_loop/state.py:662`) **and** one active-child slot
   (`try_reserve_active_subagent`, new in `SessionState`). The spawn limit (3)
   is a total budget; the active-child limit is 1. If either is exhausted,
   return `ToolResult.fail("spawn_limit"/"active_child_busy", ...,
   retryable=False)`. Release the active-child slot only after the child is
   confirmed terminal and the reader is released (or the failure is recorded).
3. Derive the child run id from the parent run id and the task id. Construct the
   child namespace `NamespaceRef(parent_session_id, child_run_id)` and the child
   binding `ExecutionBinding(child_namespace, managed.binding.workspace_id)`.
4. Create a fresh `SessionState` via a child factory. Copy only the parent's
   `session_id`, `session_db`, safe `feature_flags`, and `workspace_root`; use a
   new child `run_id`, `EventLog` in the child run-log directory, and
   `transaction`; bind the child `workspace_io` and read-only Bash executor; set
   `managed_child=True`, `artifact_store=None`, `blackboard=None`,
   `telemetry=None`, `pty_pool=None`, `worktree_manager=None`, and do not
   auto-create those host-backed resources. The optional `output_bus` is a
   separate display channel, not transcript/state authority. `SessionState` is a
   dataclass with these fields (`src/fa/inner_loop/state.py:342-377`); the child
   must not reuse the parent's `transaction`, `log`, `bash_executor`, or
   `workspace_io`.
5. Call `managed.client.pin_reader(child_binding,
   revision_id=managed.current_revision_id, plan_ref=..., deadline=...)`
   (`src/fa/execution/client.py:255`). The child namespace is the child run id,
   not the parent namespace. The returned `GrantReply` carries the READ/PROJECT
   `ViewRef`.
6. Create a read-only `ClientWorkspacePort` (namespace=child_namespace,
   view=reader_grant.view_ref, grant=reader_grant) and a read-only managed Bash
   executor bound to the same reader. The executor must use a non-interactive
   approved profile; if the configured profile is interactive, return
   `ToolResult.fail("subagent_profile_unavailable", ..., retryable=False)`.
7. Build the generic read-only/scratch tool registry with only
   `fs_read_file` and `fs_run_bash`; exclude `fs_blackboard_query`,
   `fs_exploration_metrics`, `fs_search`, `fs_reach`, write/edit/spawn, and
   `invoke_workflow` in this slice.
8. Build the minimal child hook registry: SandboxHook plus observe-only
   IntentGuard using a child-private draft store. Observe-only avoids the guard's
   host `git diff` subprocess and permits private `/scratch` writes; project
   writes remain refused by the READ port and supervisor-mounted READ view.
9. Drive the child with `drive_session(task=task,
   provider_chain=chat_chain, compactor_chain=chat_compactor,
   registry=..., hooks=..., state=..., role="subagent",
   acting_family=chat_family, max_turns=4, max_tokens=1200,
   limits=..., system_prompt_extra="",
   pinned_buffer=None, redactor=..., output=None, injection_modes=None,
   initial_memory_summary="")`. The `subagent` role resolves to
   `SUBAGENT_SYSTEM_PROMPT`; the task is the only mutable input. The child
   disables `PinnedBuffer` rather than constructing the host
   `PinnedBuffer(state.workspace_root)`. Bash commands have a 30-second cap;
   provider calls retain each configured chain entry's finite HTTP timeout.
10. Build the report from the `SessionOutcome`: `exit_code` from
    `SessionOutcome.exit_code`; `terminal_state` from `stop_reason`; `summary`
    from `final_text` (bounded); `evidence` from `tool_results`; `notes` from
    the child's final message; `duration_ms` from the runner; `token_usage`
    best-effort/optional. The child is instructed to write a bounded report with
    notes/evidence in its final message.
11. Validate the report; release the reader; persist the report to the run log
    dir; return the report to the parent.
12. On abnormal/uncertain outcome: return a structured failure; no retry; no
    guessed recovery; release the reader if possible; parent remains fail-closed.

There is no writer handoff and no parent suspend/resume in this slice. The parent
view remains active; the child sees only the published revision, not the
parent's uncommitted edits.

### 4.2 Why no writer handoff in this slice

S-A's writer handoff is sequential, but it requires:

- parent `suspend()` → publish parent view;
- `ManagedExecution.handoff_to(child_namespace)`;
- child `open_view(WRITE/PROJECT)`;
- child `publish_stage`/`stop_view`;
- reverse `handoff_to(parent_namespace)`;
- parent `resume()` → fresh view at the returned revision.

The complexity is in settlement, uncertainty, and lost replies. The operator's
"subagent does, main agent receives and takes it into work" model avoids this
entirely: the subagent investigates in a read-only/scratch view, and the main
agent applies the mutation. This is the S-C restricted first rollout. S-A is the
next step if a write-capable coder subagent is explicitly funded.

## 5. Per-role capability flags

The current flag is global:

- `FeatureFlags.subagent_spawning_enabled` default `False`
  (`src/fa/feature_flags.py:35`);
- `max_subagent_spawns_per_session` default `3` (`:41`);
- `FAIL_OPEN_FLAGS` includes `subagent_spawning_enabled` (`:101`);
- parser `_get_bool` at `:307`.

The plan adds per-role flags, default off, in the same `feature_flags:` block:

```yaml
feature_flags:
  subagent_spawning_enabled: false   # master switch
  subagent:
    chat:
      enabled: false
    planner:
      enabled: false
    coder:
      enabled: false
```

- `FeatureFlags` fields: `subagent_chat_enabled`, `subagent_planner_enabled`,
  `subagent_coder_enabled`, all default `False`.
- `_KNOWN_FLAGS`: `subagent.chat.enabled`, `subagent.planner.enabled`,
  `subagent.coder.enabled` (bool).
- `FAIL_OPEN_FLAGS`: all three (default `False` when config is missing).
- `as_dict`: include the three keys.
- Parser: `_get_bool` for each, default `False`.
- The managed tool is available only if master AND the parent role flag are
  true. The coder flag is default off; the operator opts in explicitly.
- Tests: master off; master on + role off; master on + role on; config missing;
  unknown key warning; non-bool warning; each role independently.

The legacy `spawn_subagent.py` global flag check is not the managed path. The
managed tool checks the per-role flags.

## 6. R13/W0 implementation and negative oracle

**Q124 resolution:** enforce the operator-selected 64 MiB per-child writable
`/scratch` quota at the supervisor/container boundary. The current profile has
no disk cap; do not run a child until the cap is present. Over-limit execution
returns a bounded structured failure and cleanup follows confirmed terminality.

- Implement the real managed child in W0 with the Q124 cap enforced; the managed registry must not use the
  legacy `subprocess.run` runner or inject `X_FA_PROXY_TOKEN`.
- Through production chat/planner/coder `drive_session` and the real child tool
  registry, the scripted negative oracle invokes `fs_run_bash` once on the
  child's non-interactive READ view. A real local supervisor refuses the valid
  bounded `EXEC` before any worker/cell is launched.
- Exact negative counters: `exec_requests=1`, `exec_allowed=0`,
  `cell_launches=0`, `host_subprocesses=0`, `proxy_credentials=0`,
  `project_writes=0`. The child returns a bounded report that records the
  managed denial; no host fallback or parent-shell reuse is permitted.
- Positive production-caller tests use an approved local supervisor backend and
  prove task-only child input, read-only project access, private scratch, bounded
  report return, and terminal cleanup before reader release.
- The named negative test is
  `test_subagent_commands_carry_no_proxy_credential`; add producer and caller-edge
  kill-checks. Row closure still requires the full Q113 evidence, not just this
  named test.

## 7. W1 boundary

R13's real child, Q122 per-view profile binding, role flags, restricted toolset,
and child lifecycle are implemented and tested as part of W0 under the operator's
2026-11-04 decision. W1 must not repeat or defer this work. W1 remains blocked
until every S4P1 row R01-R28 closes under Q113; then continue only with its other
S4P2 caller cutovers and dependencies. Preserve the legacy `WorktreeManager`/
`subagent_runner` separation; R23 remains an independent S4P1 row.

## 8. Observer (post-I03)

- W-A first: separate read-only observer attachment; durable status/event reads;
  latest published revision pin; no write; no second workflow; no
  cancel/advance.
- W-B target: durable workflow child + same-session read-only chat lane;
  restricted observer profile; event cursors; revision pins; owner/capability
  separation; admission/close; tool-registry restriction; `invoke_workflow` no
  longer blocking in this mode.
- W-C rejected.
- The observer must not see uncommitted coder bytes; it must name the pinned
  published revision and say when newer work is still unpublished.
- `pin_reader` reads a saved revision, not a live stage. `EventBus` is
  synchronous in-process; `SessionDatabase.read_event_rows` is a durable read
  API, not a ready concurrent subscription. The observer needs a durable read
  lane, not a new writer.

## 9. Test plan

- `test_subagent_commands_carry_no_proxy_credential` (R13 named oracle).
- `test_subagent_no_host_subprocess` (no `subprocess.run`/`shell=True`).
- `test_subagent_read_only_project` (READ view; no write to existing files).
- `test_subagent_scratch_write` (new artifacts/notes only; project source
  read-only).
- `test_subagent_scratch_quota` (enforce the Q124-selected cap and assert the
  structured over-limit result plus cleanup).
- `test_subagent_no_writer_handoff` (no HANDOFF; one writer).
- `test_subagent_main_agent_applies` (main agent receives report and applies).
- `test_subagent_coder_read_only` (coder subagent cannot edit code).
- `test_subagent_no_concurrent_mutation` (one writer; no parent/child write
  overlap).
- `test_subagent_report` (valid bounded report; notes/artifact refs/evidence).
- `test_subagent_report_mapping` (exit_code/terminal_state/summary/evidence/
  notes mapping from `SessionOutcome`; token_usage optional).
- `test_subagent_report_run_log_dir` (report persisted to run log dir, not the
  workspace).
- `test_subagent_uncertain` (no retry; no guessed recovery; fail-closed).
- `test_subagent_role_flags` (master + per-role flags; default off; each role
  independently).
- `test_subagent_spawn_limit` (atomic per-session budget).
- `test_subagent_terminal` (confirmed terminal before parent resumes).
- `test_subagent_no_parent_transcript` (child prompt = task + role prompt only).
- `test_subagent_generic_toolset` (no write/edit/spawn/invoke tools).
- `test_subagent_search_reach_deferred` (first slice does not include
  `fs_search`/`fs_reach`; managed index unavailable).
- `test_subagent_non_interactive_profile` (non-interactive approved profile
  required; interactive profile returns structured failure).
- `test_subagent_child_binding` (`pin_reader` uses the child namespace, not the
  parent namespace).
- `test_subagent_session_state_factory` (new run id/log/transaction; same
  session DB/blackboard; no parent bash executor/workspace_io).
- `test_subagent_managed_bash_no_host_git` (managed branch skips
  `_get_write_set_from_git_status`; verified at `run_bash.py:172`).
- `test_subagent_no_host_worktree` (no `WorktreeManager` in managed path).
- `test_subagent_view_bound_pinned_buffer` (the child's `PinnedBuffer` reads
  through the READ view or is disabled; no host `Path.read_text` of
  `AGENTS.md`/`knowledge/llms.txt`/`llms.txt`).
- `test_subagent_subagent_prompt` (the actual provider payload uses
  `SUBAGENT_SYSTEM_PROMPT`, not `CODER_SYSTEM_PROMPT`; no parent transcript).
- `test_subagent_active_child_single_flight` (one active child; second call
  fails; slot released only after confirmed terminal/cleanup).
- `test_subagent_resource_limits` (parent-bounded max_turns/max_tokens,
  provider/Bash timeouts, report bytes, Q124 scratch quota, spawn and active
  budgets).
- `test_subagent_secret_paths_excluded` (`.env`, `.git`, `.fa`, `.venv` not in
  the view; `fs_read_file` cannot read them).
- `test_subagent_bash_secret_path_gate` (child Bash referencing
  `/run/secrets/fa.env` is blocked; the cell does not mount host secrets).
- `test_subagent_hostile_write` (`echo > /workspace/foo`, symlink, `git add`/
  `git write-tree` fail; source read-only).
- `test_subagent_blackboard_metrics_excluded` (first slice does not include
  `fs_blackboard_query`/`fs_exploration_metrics`).
- `test_subagent_w0_oracle_metrics` (records `exec_requests`, `exec_allowed`,
  `cell_launches`, `host_subprocesses`, `proxy_credentials`, `project_writes`;
  asserts allowed/effects are zero).

## 10. Source-grounded gaps

| Area | Current source | Gap for this plan |
| --- | --- | --- |
| Feature flags | `feature_flags.py:35` global `subagent_spawning_enabled`; `:41` max spawns; `:101` FAIL_OPEN; `:307` parser | No per-role flags; add three default-off flags and tests |
| Tool profile | `profiles.py:209` legacy builder only when `workspace_io is None`; `:474` managed skip | Add managed deny-only/real builder; add `fs_spawn_subagent` to planner/coder; remove silent skip |
| Legacy tool | `spawn_subagent.py:222` `runner.run_stateless`; `:257` legacy builder | Not the managed path; new managed tool |
| Legacy runner | `subagent_runner.py:338` proxy token; `:343` `subprocess.run`; `:346` `shell=True`; `:183` filtered history | Not the managed path; no parent transcript; no host subprocess |
| Report | `subagent_envelope.py` schema; `from_verifier`; `write_envelope_artifact` | Add notes/artifact_refs/evidence; report from `SessionOutcome`; write to run log dir |
| Scratch | `state.py:678` `create_subagent_workspace`; `:662` spawn budget | Scratch is not managed isolation; managed child uses view + cell scratch; keep budget |
| Managed Bash | `client.py:700` `ManagedBashExecutor`; `:723` interactive-only; `:728` WRITE-only; `:805` `session_id="main"` | Add read-only/stateless executor; `session_id=None`; READ view |
| Workspace port | `tool_port.py:215` `ClientWorkspacePort`; `:268` rebind; `:277` WRITE-only | Read-only child uses read methods; no rebind; write child not in this slice |
| Supervisor | `backend.py:198` `execute`; `:236` non-interactive branch; `:319` interactive/session check | Already supports non-interactive READ cells; use it |
| Supervisor profile | `workspace.py:5357-5364` `admit` checks `self._view_profile.profile_id` and `profile.interactive != (session_id is not None)` | Read-only child requires a non-interactive approved profile; fail closed if the configured profile is interactive |
| View profile | `execution/profiles.py:75` `create_spec`; `:100` read-only source mount | Already mounts READ source read-only; use it |
| Authority | `workspace.py:1627` acquire_writer; `:1714` handoff; `:1830` pin_reader; `:2288` create_view; `:1775` `_settled` | Use `pin_reader`; no handoff in this slice |
| Client pin | `client.py:255` `pin_reader(binding, revision_id, ...)`; `_binding_identity` reads `binding.namespace`/`binding.workspace_id` | Construct a child `ExecutionBinding`; call the client with the child namespace, not the parent |
| Managed execution | `composition.py:82` `ManagedExecution`; `:121` handoff_to; `:211` open_view; `:238` publish_stage; `:255` stop_view | Use reader; no writer handoff |
| Stage lease | `cli.py:1428` `_ManagedStageLease`; `:1581` `_drive_stage_with_managed_workspace`; `:2229` `_build_run_tool_registry` | Build the subagent tool at the CLI seam; no parent suspend in this slice |
| Workflow tool | `workflow_tool.py:513` `run_workflow_fn`; `:430` `_begin_managed_child`; `:490` `_return_managed_child_to_parent` | Existing S-A lifecycle at workflow level; not the subagent slice |
| Child loop | `coder_loop.py:434` `drive_session` | Use for the child; fresh state; task-only |
| Child state | `state.py:342-377` `SessionState` fields; `:419` `__post_init__` | Factory must copy session DB/blackboard/etc. and override run id/log/transaction/bash/workspace_io; do not reuse parent transaction/log/bash |
| Managed search | `fs_search.py:1061`; `fs_reach.py:136` fail closed when `workspace_io` is not None | Defer `fs_search`/`fs_reach` to S2P4; first slice uses `fs_read_file` + read-only `fs_run_bash` |
| Managed Bash tool | `run_bash.py:172` `_get_write_set_from_git_status` only when `not managed`; `:384` managed branch | Verified: managed branch skips host Git; keep it that way |
| Child prompt | `prompt.py:1149` `_ROLE_PROMPTS` has no `subagent`; `coder_loop.py:1087` falls back to `CODER_SYSTEM_PROMPT` | Add `SUBAGENT_SYSTEM_PROMPT` and a `"subagent"` key; test the actual provider payload |
| PinnedBuffer | `coder_loop.py:611` `PinnedBuffer(state.workspace_root)`; `pinned_buffer.py:45-52` reads `AGENTS.md`/`knowledge/llms.txt`/`llms.txt` via `Path.read_text()` | Add a `pinned_buffer`/`workspace_reader` parameter to `drive_session`; child uses a view-bound reader or disabled buffer; no host read |
| Blackboard/metrics | `blackboard_query.py:143-154` `ensure_artifacts_indexed`; `fs_exploration_metrics.py:128-130` `clear_gold_files` | Exclude both from the first slice; they read host paths/mutate shared state |
| Secret paths | `workspace.py:788` `_Capture._excluded` excludes `.git`/`.fa`/`.venv`/`.env`; `view_io.py:34` `_BLOCKED_COMPONENTS`; `sandbox/secret_paths.py` gate | State the policy; add `test_subagent_secret_paths_excluded` and `test_subagent_bash_secret_path_gate` |
| Supervisor profile set | `service.py:118` `ServiceConfig.profiles` (multiple) + `view_profile_id` (single); `workspace.py:1111` `self._view_profile`; `:5355` `admit` uses it | **Q122 resolved (direction): profile set per view.** Add `read_only_profile_id`; authority binds a profile set and `view_profile(view_ref)`; view record carries `profile_id`; `admit`/`CommandReceipts`/`OwnedCellTermination` use the view's profile; `ViewRef` wire unchanged |
| Active child | `state.py:662` `try_reserve_subagent_spawn` (total budget only) | Add `try_reserve_active_subagent`/`release_active_subagent`; active-child limit 1; release only after confirmed terminal/cleanup |
| W0 oracle | `increment-03` W0 `:180`; `inventory` R13 `:87` | Record `exec_requests`, `exec_allowed`, `cell_launches`, `host_subprocesses`, `proxy_credentials`, `project_writes`; assert allowed/effects zero |
| Observer | `roadmap.md:70` | Post-I03; W-A first, W-B target |
| Plan | `increment-03` W0 `:180`; W1 `:181`; S4P1 `:128`; S4P2 `:129` | Update W0/W1 scope and R13 row |
| Inventory | `i03-execution-call-inventory.md:87` R13 | Update with the decision and the read-only/scratch contract |

## 11. Explicit limitations / non-goals

- The subagent cannot implement/test a bounded change; the main agent must do
  the mutation. This is the explicit S-C limitation.
- The coder subagent is read-only/scratch; no write delegation in this slice.
- The subagent is generic; no role-specific toolsets in this slice.
- The observer is post-I03; W-A first, W-B later; W-C rejected.
- The child uses the chat provider chain; no separate model tiering in this
  slice.
- The legacy `subagent_runner`/`worktree_manager` are not used in the managed
  path.
- The real R13 child and Q122 per-view binding are W0 implementation; W1
  starts only after the global Q113 exit and must not reimplement R13.
- Full R13 implementation in W0 is authorized, but Q124 blocks runtime edits
  until the scratch limit is selected; no row is closed by this plan.

## 12. Plan review

The adversarial plan review is recorded in
`notes/r13-managed-subagent-plan-review-2026-11-04.md`. It checks the flag
parser, tool registry, read-only executor, lifecycle, report schema, tests,
W0/W1 sequencing, and observer against the source. Confirmed defects are
separated from suspicions; the plan is rewritten where the review finds a gap.

## 13. Review follow-up fixes (2026-11-04)

The adversarial reviews found additional implementation gaps. The plan is
updated as follows; Q122 is resolved and its per-view profile binding is part
of R13/W0.

1. **Child `PinnedBuffer` host read.** `drive_session` creates
   `PinnedBuffer(state.workspace_root)` (`src/fa/inner_loop/coder_loop.py:611`),
   which reads `AGENTS.md`/`knowledge/llms.txt`/`llms.txt` via `Path.read_text()`
   (`src/fa/memory/pinned_buffer.py:45-52`). Fix: add a `pinned_buffer`/
   `workspace_reader` parameter to `drive_session`; the child passes a
   view-bound reader or a disabled buffer; the parent path is unchanged. Test:
   `test_subagent_view_bound_pinned_buffer`.
2. **`fs_blackboard_query`/`fs_exploration_metrics` side effects.**
   `blackboard_query.py:143-154` calls `ensure_artifacts_indexed` on the parent
   blackboard/workspace; `fs_exploration_metrics.py:128-130` calls
   `clear_gold_files()` on reset. Fix: exclude both from the first slice; the
   toolset is `fs_read_file` + read-only `fs_run_bash`. Test:
   `test_subagent_blackboard_metrics_excluded`.
3. **`subagent` role prompt.** `_ROLE_PROMPTS` has no `subagent`
   (`src/fa/inner_loop/prompt.py:1149`); `coder_loop.py:1087` falls back to
   `CODER_SYSTEM_PROMPT`. Fix: add `SUBAGENT_SYSTEM_PROMPT` and a `"subagent"`
   key; the child prompt is read-only/scratch + task, not the coder prompt.
   Test: `test_subagent_subagent_prompt`.
4. **Secret file policy.** The view excludes `.git`/`.fa`/`.venv`/`.env`
   (`src/fa/execution/workspace.py:788`, `src/fa/execution/view_io.py:34`); the
   `src/fa/sandbox/secret_paths.py` gate blocks secret paths. Fix: state the
   policy; add `test_subagent_secret_paths_excluded` and
   `test_subagent_bash_secret_path_gate`; test hostile writes
   (`test_subagent_hostile_write`).
5. **Supervisor profile set (Q122 resolved).** `ServiceConfig.profiles` is
   multiple but `view_profile_id` originally selected one profile for every
   view. Use the existing authority with a validated profile set and per-view
   selection: WRITE views use `view_profile_id`; READ views use
   `read_only_profile_id`. Bind both role assignments into supervisor identity;
   fail closed if the READ profile is missing. No separate authority and no
   interactive/write-profile fallback.
6. **W0 oracle wording.** "Zero EXEC" is ambiguous. Fix: record
   `exec_requests`, `exec_allowed`, `cell_launches`, `host_subprocesses`,
   `proxy_credentials`, `project_writes`; assert allowed/effects zero; the
   supervisor must be asked and must refuse. Test:
   `test_subagent_w0_oracle_metrics`.
7. **Single-flight and resource limits.** The spawn limit (3) is a total budget,
   not an active-child limit. Fix: add `try_reserve_active_subagent`/
   `release_active_subagent`; active-child limit 1; release only after
   confirmed terminal/cleanup; add per-child `max_turns`/`max_tokens`/
   `timeout_ms`/report bytes/scratch bytes and a cumulative budget. Tests:
   `test_subagent_active_child_single_flight`,
   `test_subagent_resource_limits`.

**Generic vs role-specific toolset.** The operator's 2026-11-04 refinement is
authoritative: the subagent is generic; the parent role determines the
task/prompt; the toolset is the same minimal read-only/scratch profile for all
parents. Q121's initial phrase "role-specific toolset" is superseded by the
operator's generic-toolset refinement, which this plan records. The per-role flags are access gates, not toolset
differentiation. If the operator later wants role-specific toolsets, they can be
added, but the first slice is generic.

**Policy decisions.** Q122 option A is resolved and its required profile binding is included in R13/W0. Q123 is resolved: implement the real child and its supervisor-refused negative oracle directly in W0. The implementation remains OPEN; Q113's global row exit is unchanged.


## 14. Q124 resolution — 64 MiB writable private scratch quota

`ExecutionProfile` bounds memory, PIDs, and command duration, but it has no
scratch-disk limit. `ExecutionProfile.create_spec` mounts the supervisor-owned
view scratch as a writable bind at `/scratch`. The operator selected a hard
64 MiB per-child cap. The implementation must enforce it at the
supervisor/container boundary, return a bounded structured failure on overflow,
and clean up only after confirmed terminality. The source mechanism and request/
no-fallback tests are now present; live-host kernel ENOSPC and post-terminal
mount-release evidence remain outstanding. R13 and W0 remain OPEN.

**Selected enforcement mechanism (Q124-A, source-verified 2026-11-04).** For a
non-interactive READ view, `ExecutionProfile.create_spec` emits Docker
`HostConfig.Tmpfs["/scratch"] = "size=67108864,mode=1777,nosuid,nodev"` and does
not bind the supervisor-owned host scratch into the cell. The fixed
`READ_SCRATCH_BYTES` policy is included in the supervisor profile-set digest.
WRITE/interactive cells keep their existing scratch bind. Docker create
rejection is a closed failure; there is no retry or host-backed fallback. Moby
exposes this through `HostConfig.Tmpfs` ([hostconfig.go](https://github.com/moby/moby/blob/master/api/types/container/hostconfig.go)).
The one-shot cell's private tmpfs is scoped to its container mount namespace;
cleanup evidence must follow the existing exit/cgroup terminal barrier. Arena
C0/C3 tests establish the exact request and no-fallback behavior, not live
kernel ENOSPC or mount-release evidence. Those still require live-host Docker
E2E; R13/W0 remain OPEN until the full row oracles and those deployment checks
are satisfied.

## 15. R13/W0 implementation checkpoint (2026-11-04)

The first production wiring slice is in source:

- `src/fa/inner_loop/tools/managed_subagent.py` creates a task-only managed
  child, pins a fresh child namespace with `PIN_READER`, binds a `ClientWorkspacePort`
  and `ReadOnlyManagedBashExecutor`, provides only `fs_read_file` and
  `fs_run_bash`, disables the host `PinnedBuffer`, drives the `subagent` role,
  bounds the report to 8,000 characters, and confirms `STOP_VIEW`/READ `RELEASE`
  before report persistence and parent return. Failure/uncertain cleanup retains
  the active-child slot and never retries on the host.
- `src/fa/cli.py` binds the managed builder only to managed chat/planner/coder
  production registries. Chat parents reuse their configured chain; workflow
  planner/coder parents use the chat chain or fail closed when it is unavailable.
  Local/legacy `fa run` retains `spawn_subagent.py`.
- `SandboxHook` admits only an exact non-empty task-only `fs_spawn_subagent`
  payload without treating it as Bash. Legacy command payloads still pass the
  existing Bash gate. Child `IntentGuard` is observe-only to avoid host `git`
  subprocesses; READ view/port remain the project-mutation authority.
- Producer tests: `tests/test_managed_subagent.py` (8 passed in the checkpoint
  run), including role gates, task-only registry, report bound, cleanup order,
  and a fake managed EXEC-refusal/no-host-fallback kill-check. That fake refusal
  is **not** supervisor/backend evidence.
- Production caller positive: the managed-chat CLI test in
  `tests/test_execution_composition.py` runs against a real local UDS
  `SupervisorService`; child `fs_read_file` uses the pinned READ view, prompt
  carries only the delegated task, the parent stays the sole writer, and the
  report/log are outside the project after terminal cleanup. Planner/coder
  registry registration has a direct caller-edge test.

**Still open at this checkpoint:** the named R13 negative oracle
`test_subagent_commands_carry_no_proxy_credential` is not yet implemented through
an approved local managed backend; exact counters
`exec_requests=1`, `exec_allowed=0`, `cell_launches=0`,
`host_subprocesses=0`, `proxy_credentials=0`, `project_writes=0` must be proven
through production chat/planner/coder callers. The fake executor refusal does
not substitute for it. Also outstanding are positive private-scratch writes and
quota overflow through the approved backend, live-host Docker ENOSPC/cleanup,
workflow planner/coder nested-child end-to-end, and the full Q113 R01–R28 row
set. R13/W0 remain OPEN; W1 is not authorized to start.

## 16. R13 production-caller oracle follow-up (2026-11-04; local, incomplete)

After restoring the pinned CPython 3.13.16 environment, the named test was added
and exercised: `tests/test_execution_composition.py::test_subagent_commands_carry_no_proxy_credential`
passes both `[False]` and `[True]` parameterizations. It enters the actual
`cli._cmd_run`/`drive_session` registry, starts a real local UDS
`SupervisorService`, submits one bounded child `fs_run_bash` EXEC, observes
`BACKEND_UNAVAILABLE`, then lets the child perform a READ and return its report;
the parent then publishes its own write. Ruff passed, and the selected
managed-subagent/composition/isolation/wiring suite reports **129 passed, 2
expected xfails**.

**This is not the missing approved-backend oracle.** The test asserts
`service._backend is None`: the supervisor's early no-backend refusal is reached
through the production child caller, but no configured cell backend is exercised
and the zero-launch count is structural for that setup. The test's byte snapshot
measures only the child interval, before the subsequent parent publication. No
producer/caller-edge mutation kill has yet been run for this oracle. Do not close
R13 or W0 from these results.

Remaining R13/W0 work includes the approved/configured managed-backend
production-caller negative oracle; positive child writes to private scratch plus
quota overflow through the backend; live-host Docker ENOSPC and terminal
mount-release evidence; and workflow planner/coder nested-child end-to-end.
Q113 still requires every R01–R28 row. R13/W0 remain OPEN; W1 is still
unauthorized.

## 17. R13 producer and caller-edge mutation follow-up (2026-11-04; local)

The existing C1 oracle was challenged with two exact temporary mutations in
`src/fa/cli.py`:

1. Remove `registry.register(build_managed_subagent_tool(...))` from
   `_register_managed_subagent_tool`. The producer registration test and both
   production-chat oracle parameterizations failed (**5 failed**): chat/planner/
   coder registration assertions and the provider trajectory observed the
   missing `fs_spawn_subagent` capability.
2. Replace the `_register_managed_subagent_tool(...)` return edge in `_cmd_run`'s
   registry closure with `return registry`. Both production-chat oracle
   parameterizations failed (**2 failed**) because the spawned tool was absent.

Each mutation exited pytest 1 for the intended missing-tool assertion. The
original `src/fa/cli.py` bytes were restored and byte-equality verified after
each run and in the finalizer. On restored source, Ruff passed for the four R13
source/test files and the seven-file managed-subagent/composition/isolation/
wiring bank passed **129**, with **2 expected xfails**; `git diff --check`
passed.

These kills establish producer/edge sensitivity for the **no-backend chat
refusal** C1 oracle. They do not convert its structural `cell_launches=0` into
configured-backend evidence and do not prove scratch writes, quota exhaustion,
planner/coder nested execution, or live-host cleanup. The later closeout below
supersedes this checkpoint's OPEN status.

## 18. R13/W0 local row closeout (2026-11-04; Arena-local)

**DoD result: R13's local W0 row is CLOSED.** The managed child is exercised
through production callers for ordinary chat and workflow planner/coder; the
legacy `fa workflow` path and one-writer model remain unchanged. The global
Q113 W0 gate remains OPEN because other R01–R28 rows have not passed; W1 has
not started.

| Caller | `unavailable` negative | `unapproved` configured-backend negative | `approved` positive |
| --- | --- | --- | --- |
| Chat | `test_subagent_commands_carry_no_proxy_credential[unavailable-*]` | same oracle `[unapproved-*]` | same oracle `[approved-*]`, both workflow-owner modes |
| Planner/coder workflow stages | `test_workflow_stage_runs_managed_child_with_local_backend[unavailable-*]` | same test `[unapproved-*]` | same test `[approved-*]` |

The configured negative keeps the local `CellBackend`, profiles, cgroup
fixture, and Docker API peer configured, but omits the approved cache from the
service configuration. The real supervisor refuses the child's valid bounded
stateless READ `EXEC` with `UNAPPROVED_PROFILE` before reaching the local daemon
peer or worker. The unavailable mode independently returns
`BACKEND_UNAVAILABLE`. Each of the eight negative cases asserts exactly one
`exec_request`, zero `exec_allowed`, `cell_launches`, R13 Bash-fallback or
legacy-runner subprocesses, proxy credentials, and child project writes; it
also checks the child tool result and bounded report. A broad process probe
observed a parent-side `git diff --cached --name-status` during the parent chat
write/intent path; it is not an R13 child fallback and is not claimed absent.
The final R13 counter instruments only the forbidden child Bash fallback and
legacy `SubagentRunner.run_stateless` seams. Managed Bash's separate no-host-Git
test passes; no other R-row is advanced by this result. The approved path proves
a worker/cell request, task-only child prompt, pinned read-only `/workspace`,
private-scratch write, terminal cleanup before reader release, and bounded
report under the parent's sole project writer. For Q124 the chat positive runs the attempted overflow under the
64 MiB `ulimit` boundary, confirms `overflow.bin` is exactly 64 MiB and the
inner write returns nonzero, and verifies the bounded child report's evidence
contains that result. Docker request construction separately asserts the exact
`/scratch` tmpfs quota and no scratch bind.

**Q122/role/profile checks.** The related workspace reader/view, backend,
service, and profile-set tests pass with separate interactive writer and
non-interactive reader profiles. Per-role default-off flags, child task-only
state, restricted `fs_read_file`/stateless `fs_run_bash` registry, report
mapping/bounds/run-log placement, active-child reservation, stop-before-report,
no host fallback, and no writer handoff are covered by the managed-subagent,
managed-Bash, stage-lease, registry-binding, and local composition suites.

**Verification.** The 12-case production-caller matrix passed (**12 passed**).
The related 12-module R13 suite passed **643 passed, 1 expected xfail** on
CPython 3.13.16; the xfail is the documented SLICE4 STEP2 host-side-write
cutover. Ruff and format checks passed for the five touched test modules. The
producer registration mutant, `_cmd_run` caller-edge mutant (`return registry`),
and Q124 missing-`Tmpfs` producer mutant each failed at the intended assertion;
`src/fa/cli.py` and `src/fa/execution/profiles.py` were restored byte-exactly.
The missing-`Tmpfs` mutant run logged a local candidate-view cleanup refusal
while unwinding the intentionally failed test; restored-source targeted and
12-module suites pass. An earlier edge mutant that removed the closure return
entirely was invalid (`None` registry) and is not counted as the caller-edge
kill.

**Evidence boundary.** This is Arena-local proof using a real local supervisor
and `CellBackend`, a test-local Docker API peer, and a test worker; it is not a
live Docker daemon/runtime result. Actual Docker ENOSPC behavior, tmpfs release,
and ledger appends remain `NOT RUN` until the final wave, as directed. No host
fallback or host claim is inferred. Global W0 remains OPEN under Q113; do not
start W1 or advance to another R-row from this closeout.
