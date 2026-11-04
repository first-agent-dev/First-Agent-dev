# R13 managed subagent plan — adversarial review (2026-11-04)

**Reviewer role:** senior engineer accountable for the code in production.
**Scope:** the R13/W1 plan
([r13-managed-subagent-plan-2026-11-04.md](r13-managed-subagent-plan-2026-11-04.md)),
the affected I03 plan sections, the R13 inventory row, and the roadmap observer
section. This review is a plan review, not an implementation review. No runtime
code was changed.

**Method:** read the plan against the current source, then check each assumption
about the flag parser, tool registry, managed view, read-only executor, child
loop, report schema, W0/W1 sequencing, and observer. Each finding cites the
source line. Confirmed defects are separated from suspicions. The plan was
rewritten where a finding required it.

## 1. Confirmed defects and fixes

### D1 — Managed `fs_search`/`fs_reach` are not available in the first slice

**Evidence:** `src/fa/inner_loop/tools/fs_search.py:1061` returns
`ToolResult.fail("search_failed", "managed cell-local search index is unavailable")`
when `workspace_io is not None`; `src/fa/inner_loop/tools/fs_reach.py:136` returns
`ToolResult.fail("reach_failed", "managed cell-local reach index is unavailable")`.
The plan's generic toolset originally included both.

**Fix:** removed `fs_search`/`fs_reach` from the first-slice toolset. The first
slice uses `fs_read_file` and read-only `fs_run_bash`; `fs_search`/`fs_reach` are
deferred until S2P4 wires the managed cell-local index. Added
`test_subagent_search_reach_deferred`.

### D2 — `pin_reader` is a client method; the plan's lifecycle was underspecified

**Evidence:** `ExecutionClient.pin_reader(binding, revision_id, ...)`
(`src/fa/execution/client.py:255`) takes a binding, not a namespace; it calls
`_binding_identity(binding)` and reads `binding.namespace` /
`binding.workspace_id`. `ManagedExecution` has no `pin_reader` method. The
`ExecutionBinding` dataclass is at `src/fa/execution/composition.py:55`.

**Fix:** the plan now constructs a child
`ExecutionBinding(child_namespace, managed.binding.workspace_id)` and calls
`managed.client.pin_reader(child_binding, revision_id=managed.current_revision_id,
...)`. The child namespace is the child run id, not the parent namespace. Added
`test_subagent_child_binding`.

### D3 — The read-only child requires a non-interactive approved profile

**Evidence:** `WorkspaceAuthority.admit` checks
`payload["profile_id"] == self._view_profile.profile_id` and
`profile.interactive != (session_id is not None)`
(`src/fa/execution/workspace.py:5357-5364`); `CellBackend.execute` enforces the
same at `src/fa/execution/backend.py:319`. The supervisor's `_view_profile` is a
single approved profile (`src/fa/execution/service.py:283`). The current
`ManagedBashExecutor` requires `profile.interactive` and `Access.WRITE`
(`src/fa/execution/client.py:723`, `:728`).

**Fix:** the plan now requires a non-interactive approved profile for the child
and a structured `subagent_profile_unavailable` failure if the configured
profile is interactive. The read-only executor must pass `session_id=None`.
Added `test_subagent_non_interactive_profile`.

**Suspicion (not a confirmed defect):** the supervisor may need a profile set if
the operator wants both interactive parent stages and non-interactive child
cells. The current `ServiceConfig` has a single `profile` field
(`src/fa/execution/service.py:118`, `:283`). The implementation must verify the
deployment config supports the child profile; if not, this is a config change,
not a plan change.

### D4 — `SessionOutcome` does not carry token usage

**Evidence:** `SessionOutcome` (`src/fa/inner_loop/coder_loop.py:400-422`) has
`exit_code`, `stop_reason`, `turns`, `final_text`, `tool_results`,
`failed_tools`; no token usage. The plan's `SubagentReport` originally listed
`token_usage` as a field.

**Fix:** `token_usage` is optional/best-effort in the first slice and must not be
fabricated. Added `test_subagent_report_mapping`.

### D5 — `SessionState` construction was underspecified

**Evidence:** `SessionState` is a dataclass with `workspace_root`, `session_id`,
`run_id`, `log`, `observations`, `transaction`, `blackboard`, `telemetry`,
`feature_flags`, `artifact_store`, `pty_pool`, `bash_executor`, `workspace_io`,
`worktree_manager`, `session_db`, `output_bus`
(`src/fa/inner_loop/state.py:342-377`); `__post_init__` at `:419` creates an
`EventLog` and bootstraps the session DB.

**Fix:** the plan now specifies a child factory that copies the parent's
`session_id`, `session_db`, `blackboard`, `telemetry`, `artifact_store`,
`feature_flags`, `output_bus`, and `workspace_root`, and overrides `run_id`,
`log`, `transaction`, `bash_executor`, `workspace_io`, `pty_pool=None`,
`worktree_manager=None`. The factory must not reuse the parent's `transaction`,
`log`, `bash_executor`, or `workspace_io`. Added
`test_subagent_session_state_factory`.

### D6 — The report's `artifact_refs` are in a private scratch the main agent cannot read

**Evidence:** the cell's scratch is private to the view; the main agent cannot
read it after the reader is released. The plan originally listed
`artifact_refs` as paths without saying the content must be in the report.

**Fix:** the report includes the notes/evidence content (bounded); the
`artifact_refs` are optional. The main agent persists the content in the run log
dir/project notes. Added `test_subagent_report_run_log_dir`.

### D7 — The report schema and writer are legacy

**Evidence:** `SubagentEnvelope.type` enum does not include `subagent`;
`from_verifier` builds the envelope from a shell exit code;
`write_envelope_artifact` writes to `.fa/subagents/<id>.json` in the workspace
(`src/fa/inner_loop/subagent_envelope.py:20-90`, `:180`).

**Fix:** the plan extends the enum with `subagent` (or the parent role), adds a
`from_session_outcome` builder, and uses a run-log-dir writer. The managed child
does not use `from_verifier` or the workspace artifact path.

### D8 — The global subagent flag is not per-role

**Evidence:** `FeatureFlags.subagent_spawning_enabled` is a single global flag
(`src/fa/feature_flags.py:35`); there are no per-role fields. The operator
requires a per-role flag, default off, for each role.

**Fix:** the plan adds `subagent_chat_enabled`, `subagent_planner_enabled`,
`subagent_coder_enabled` (default `False`), `_KNOWN_FLAGS` entries
`subagent.chat.enabled`, `subagent.planner.enabled`, `subagent.coder.enabled`,
`FAIL_OPEN_FLAGS` entries, `as_dict` entries, and parser `_get_bool` calls. The
managed tool is available only when the master and the parent-role flag are both
true. Added `test_subagent_role_flags`.

### D9 — The managed composition silently skips `fs_spawn_subagent`

**Evidence:** `profiles.py:209` adds the legacy builder only when
`workspace_io is None`; `profiles.py:474` skips `fs_spawn_subagent` with a
warning when `workspace_io is not None`. The `planner` and `coder` profiles do
not declare the tool.

**Fix:** the plan adds a managed deny-only/real builder, adds
`fs_spawn_subagent` to the planner/coder profiles, and removes the silent skip.
The managed composition always registers a builder for the tool (real or
deny-only).

### D10 — The read-only executor and port are not the current `ManagedBashExecutor`

**Evidence:** `ManagedBashExecutor` requires `profile.interactive` and
`Access.WRITE` (`src/fa/execution/client.py:723`, `:728`); `run` passes
`session_id="main"` (`:805`). `ClientWorkspacePort.rebind` requires
`Access.WRITE` (`src/fa/execution/tool_port.py:268`, `:277`).

**Fix:** the plan adds a read-only/stateless managed executor (or generalizes
`ManagedBashExecutor`) that accepts a READ view, a non-interactive profile, and
passes `session_id=None`. The read-only child uses `ClientWorkspacePort` read
methods and does not rebind. Added `test_subagent_read_only_project` and
`test_subagent_scratch_write`.

### D11 — The legacy scratch and runner are not managed isolation

**Evidence:** `SessionState.create_subagent_workspace` returns a scratch path
under `.fa/subagents` (`src/fa/inner_loop/state.py:678`);
`subagent_runner.py:338` injects `X_FA_PROXY_TOKEN`, `:343` calls
`subprocess.run`, `:346` uses `shell=True`, `:183` builds filtered history but
does not pass it to a child model; `spawn_subagent.py:222` calls the legacy
runner.

**Fix:** the plan does not use the legacy runner or scratch for the managed
child. The managed child uses the pinned reader and the cell scratch. The
`try_reserve_subagent_spawn` budget (`state.py:662`) is retained. Added
`test_subagent_no_host_subprocess`, `test_subagent_no_host_worktree`, and
`test_subagent_no_parent_transcript`.

## 2. Verified fine points (not defects)

- **Managed `fs_run_bash` skips host Git.** `run_bash.py:172` calls
  `_get_write_set_from_git_status` only when `not managed`; the managed branch
  at `:384` passes `managed=True`. The child's managed Bash does not run host
  Git. Keep it that way; `test_subagent_managed_bash_no_host_git` pins it.
- **The supervisor already supports non-interactive READ cells.**
  `CellBackend.execute` has a non-interactive branch at
  `src/fa/execution/backend.py:236`; `ExecutionProfile.create_spec` mounts the
  source read-only for READ views at
  `src/fa/execution/profiles.py:100`. The gap is the client executor and the
  profile config, not the supervisor.
- **`ClientWorkspacePort` read methods work with a READ view.**
  `read_file` and `list_project_artifacts` are available; `write_file` is denied
  (`src/fa/execution/tool_port.py:351`). The read-only child omits write tools.
- **The one-writer contract is preserved.** The first slice has no writer
  handoff; the parent remains the only writer. The coder main agent applies
  mutations. This is the S-C restricted first rollout, not S-A.
- **The observer is separate.** W-A/W-B are post-I03 and do not change the
  subagent decision. The roadmap sequencing remains the baseline.

## 3. Suspicions / open questions (not confirmed defects)

- **S1 — Hostile write via the scratch.** The cell's source is read-only and the
  scratch is writable, but the plan must test hostile commands (e.g.
  `echo > /workspace/foo`, `ln -s /workspace /scratch/link`,
  `git add`/`git write-tree` in the source). The supervisor's mount is the
  boundary; the test should prove it. This is a test gap, not a confirmed
  defect.
- **S2 — Blackboard content.** The child's `fs_blackboard_query` reads the
  parent's blackboard. The blackboard is a structured state, not the transcript,
  but the implementation must verify that the child cannot reconstruct the
  parent's conversation from blackboard entries. If it can, the child's
  blackboard access must be restricted or removed.
- **S3 — Supervisor profile set.** The supervisor's `_view_profile` is a single
  profile. If the operator wants both interactive parent stages and
  non-interactive child cells, the supervisor config may need a profile set.
  This is a deployment/config question; the implementation must verify it.
- **S4 — Report content bound.** The child's final message and tool results may
  be large. The report bound (8000 chars) is a plan choice; the implementation
  must enforce it and test a large-output child.
- **S5 — `token_usage` provenance.** If the operator requires token usage, the
  implementation must add a provider-chain usage hook; it is not in
  `SessionOutcome`. The first slice treats it as optional.

## 4. Plan edits made

- `notes/r13-managed-subagent-plan-2026-11-04.md`: added the child binding and
  `pin_reader` call; removed `fs_search`/`fs_reach` from the first slice; added
  the non-interactive profile requirement; added the `SessionState` factory;
  added the report mapping and run-log-dir writer; added the per-role flags;
  added the source-grounded gaps and tests.
- `increments/increment-03-execution-workspace-foundation.md`: added the R13
  managed subagent section and the W0/W1 impact.
- `roadmap.md`: updated the I03 row and the observer section (W-A then W-B).
- `notes/i03-execution-call-inventory.md`: added the R13 decision subsection.
- `notes/open-questions-2026-10-07.md`: added Q121 with the decision and the
  acceptance boundary.

## 5. Residual risk / what the implementation must prove

- The R13 negative oracle must run through the production caller, not a helper.
- The read-only child must be proven unable to write existing project files,
  including hostile commands and symlinks.
- The per-role flags must be proven default-off and independently effective.
- The report must be bounded, validated, and persisted to the run log dir.
- The child must be terminal before the parent resumes; no retry or guessed
  recovery on uncertainty.
- The observer remains post-I03; W-A first, W-B later; W-C rejected.
- No row is closed by this plan or review. R13, W0, and W1 remain OPEN.

## 6. Second review — follow-up (2026-11-04)

The operator supplied a second adversarial review with seven findings. I
verified each against the current source and updated the plan. The findings and
fixes:

### F1 — Child `PinnedBuffer` reads the host workspace (confirmed)

`drive_session` creates `PinnedBuffer(state.workspace_root)`
(`src/fa/inner_loop/coder_loop.py:611`); `PinnedBuffer.refresh` reads
`AGENTS.md`, `knowledge/llms.txt`, and `llms.txt` with `Path.read_text()`
(`src/fa/memory/pinned_buffer.py:45-52`). The child's READ view is bypassed, and
the child can receive more project text than the task-only contract allows.

**Fix:** add a `pinned_buffer`/`workspace_reader` parameter to `drive_session`
(default = current parent behavior). The child passes a view-bound reader that
reads the three pinned files through the child's `ClientWorkspacePort` (READ
view), or a disabled buffer if the operator prefers a task-only child prompt.
The parent path is unchanged. Test: `test_subagent_view_bound_pinned_buffer`.

### F2 — `fs_blackboard_query`/`fs_exploration_metrics` side effects (confirmed)

`blackboard_query.py:143-154` calls
`ensure_artifacts_indexed(session.blackboard, session.workspace_root, ...)`,
which reads the host workspace and mutates the shared parent blackboard.
`fs_exploration_metrics.py:128-130` calls `session.clear_gold_files()` on
`reset=true`.

**Fix:** exclude both from the first-slice toolset. The first slice uses only
`fs_read_file` and read-only `fs_run_bash`. A view-bound read-only
blackboard/metrics source is a later option. Test:
`test_subagent_blackboard_metrics_excluded`.

### F3 — `subagent` role prompt falls back to coder (confirmed)

`_ROLE_PROMPTS` has `planner`, `coder`, `eval`, `chat`, but no `subagent`
(`src/fa/inner_loop/prompt.py:1149`); `coder_loop.py:1087` uses
`_ROLE_PROMPTS.get(role, CODER_SYSTEM_PROMPT)`. A child `role="subagent"` gets
the coder base prompt; `GENERIC_SUBAGENT_PROMPT` is only extra text.

**Fix:** add `SUBAGENT_SYSTEM_PROMPT` and a `"subagent"` key to
`_ROLE_PROMPTS`. The child prompt is read-only/scratch + task, not the coder
prompt. Test the actual provider payload: `test_subagent_subagent_prompt`.

### F4 — Secret file policy (test gap; current code has a baseline)

The view excludes `.git`, `.fa`, `.venv`, and `.env`
(`src/fa/execution/workspace.py:788`, `src/fa/execution/view_io.py:34`); the
`src/fa/sandbox/secret_paths.py` gate blocks commands referencing secret paths.
The child's Bash runs in the cell; host secrets are not mounted. This is not a
confirmed defect, but the policy must be stated and tested.

**Fix:** state the policy in the plan; add
`test_subagent_secret_paths_excluded` and
`test_subagent_bash_secret_path_gate`; add `test_subagent_hostile_write` for
`/workspace` writes, symlinks, and `git add`/`git write-tree`.

### F5 — Supervisor profile set (confirmed; Q122)

`ServiceConfig.profiles` is a tuple of approved profiles, but
`view_profile_id` selects one (`src/fa/execution/service.py:118-136`);
`WorkspaceAuthority` binds one `_view_profile` (`src/fa/execution/workspace.py:1111`);
`admit` uses it (`:5357-5364`). The read-only child needs a non-interactive
profile; the parent stages may use an interactive profile. The current
authority cannot serve both.

**Fix:** **Q122 resolved (direction): option A.** Extend `WorkspaceAuthority` to
a profile set and select the profile per view; the view record carries the
profile id; `create_view`/`pin_reader` select the profile; `admit` uses the
view's profile. Add `read_only_profile_id` to `ServiceConfig`; the
`CommandReceipts`/`OwnedCellTermination` use the view's profile; the `ViewRef`
wire is unchanged. Option B (separate authority) and option C (same interactive
profile, PTY child) are rejected. The implementation remains OPEN; W1's real
child requires this direction to be implemented.

### F6 — W0 oracle wording (confirmed ambiguity)

"Zero EXEC" is ambiguous: if the supervisor refuses EXEC, there is an EXEC
request. The oracle must distinguish requests from allowed operations/effects.

**Fix:** record `exec_requests` (may be 1), `exec_allowed` (must be 0),
`cell_launches` (must be 0), `host_subprocesses` (must be 0),
`proxy_credentials` (must be 0), and `project_writes` (must be 0). The
supervisor must be asked and must refuse. Test:
`test_subagent_w0_oracle_metrics`.

### F7 — Single-flight and resource limits (confirmed gap)

The spawn limit (3) is a total budget, not an active-child limit. The tool is
synchronous, but a batch/concurrent caller could start multiple children.

**Fix:** add `try_reserve_active_subagent`/`release_active_subagent` to
`SessionState`; active-child limit 1; release only after confirmed
terminal/cleanup. Add per-child `max_turns`, `max_tokens`, `timeout_ms`, report
bytes, scratch bytes, and a cumulative budget. Tests:
`test_subagent_active_child_single_flight`, `test_subagent_resource_limits`.

### Generic vs role-specific toolset (clarification)

The operator's 2026-11-04 refinement is authoritative: the subagent is generic;
the parent role determines the task/prompt; the toolset is the same minimal
read-only/scratch profile for all parents. Q121's "role-specific toolset" is the
legacy contract; the plan records the refinement. The per-role flags are access
gates, not toolset differentiation. If the operator later wants role-specific
toolsets, they can be added, but the first slice is generic.

### Plan changes made

- `notes/r13-managed-subagent-plan-2026-11-04.md`: added section 3.6 (child
  role prompt and PinnedBuffer), updated section 3.3 (toolset), 4.1 (active-child
  reservation and `pinned_buffer`), 6 (W0 oracle metrics), 9 (tests), 10
  (source-grounded gaps), and 13 (review follow-up fixes).
- `notes/open-questions-2026-10-07.md`: added Q122 (supervisor profile set).

### Residual risk

- Q122 is resolved (direction: profile set per view); the implementation remains
  OPEN. The R13/W0 deny-only oracle can still run; the real child in W1 requires
  the Q122 direction to be implemented.
- The other findings are code/test fixes or plan wording; no runtime code was
  changed by this review.
- No row is closed. R13, W0, and W1 remain OPEN.
