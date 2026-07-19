# Tier 1 Task Declaration — Authoring Hardening Session 2 (2026-07-16)

## Item 1 — `scripts/check_dead_flags.py`

### Intent

Automate detection of dead `FeatureFlags` fields and phantom `getattr` flags.
The re-inventory says "manual inventory of 12 fields — all have ≥1 production use"
but there's no regression guard. Per HR3: script prevents false deletion in future.
Also detects "phantom flags" — fields accessed via `getattr(feature_flags, name)`
that aren't declared in the `FeatureFlags` dataclass.

### How to translate to code

1. **Parse `FeatureFlags`** via `dataclasses.fields()` — extract all declared field names.
2. **Search `src/fa/`** (excluding tests) for each field name:
   - Direct: `feature_flags.<name>` or `ff.<name>` or `. <name>` after FeatureFlags
   - getattr: `getattr(*, "<name>"` or `getattr(*, '<name>'`
3. **Phantom detection**: scan `src/fa/` for `getattr(feature_flags, '` and `getattr(feature_flags, "`
   patterns, extract the string literal, flag if not in declared field set.
4. **Output**: JSON with `--output json`; text summary by default.
   - `declared_fields`: list of `{name, usage_count, is_dead}`
   - `phantom_flags`: list of `{name, access_file, access_line}`
5. **Exit codes**: 0 = no dead, 1 = dead flags found, 2 = usage error.
6. **Stdlib-only** (uses `dataclasses`, `ast`, `re`, `pathlib` — no external deps).

### How to verify

- `python scripts/check_dead_flags.py` → exits 0 (all 12 fields have usage, expect 0 dead)
- `python scripts/check_dead_flags.py --output json` → valid JSON, `phantom_flags` includes
  `blackboard_filtered_history_include_plans` accessed in `subagent_runner.py`
- Kill-check: temporarily comment out a field from FeatureFlags → script reports it as dead
- `fa authoring-check` still green after script lands
- Full test suite still green

---

## Item 2 — `tests/test_list_tasks_wiring.py`

### Intent

Prove `fs.list_tasks` works via live session through `drive_session`. Three code paths:
(1) PTY sessions from pool.list_sessions(), (2) worktree dirs, (3) subagent artifacts.
All three must be exercised as C1 per tests-writing skill §3 (live-path proof).

### How to translate to code

Per tests-writing skill:

- **Class**: C1 composition-root (root: `drive_session`)
- **Matrix**: A-gates-only (default FeatureFlags, no special gates needed)
- **Oracle**: Rank 6 (product-owned FS/DB rows) — tool result `result["tasks"]` contains
  expected entries with correct type/id/status fields
- **Kill-check**: removing `build_list_tasks_tool` from `build_baseline_registry` would
  make `drive_session` return "unknown tool" — test fails
- **Type-honest**: use `tests.fixtures.session_wiring` factories, real `HookRegistry()`

**Test functions:**

1. `test_list_tasks_finds_pty_session` — Create PtyPool, acquire session, call
   `fs.list_tasks` via drive_session, assert result contains `{"type": "pty", "id": "main"}`
2. `test_list_tasks_finds_subagent_artifact` — Spawn subagent first (creates .fa/subagents/t-1.json),
   then call `fs.list_tasks` via drive_session, assert result contains
   `{"type": "subagent", "id": "t-1", "status": "done"}`
3. `test_list_tasks_finds_worktree_dir` — Create worktree dir structure,
   call `fs.list_tasks` via drive_session with worktree_manager, assert worktree entry
4. `test_list_tasks_empty_when_no_pool_or_manager` — No pty_pool, no worktree_manager,
   call `fs.list_tasks` via drive_session, assert empty task list returned

### How to verify

- `pytest tests/test_list_tasks_wiring.py -v` → all tests pass
- Each test has LIVE-PATH PROOF docstring with root, matrix, oracle, kill-check
- `fa authoring-check` still green
- Full suite green

---

## Item 3 — `tests/test_subagent_termination_wiring.py`

### Intent

Prove subagent lifecycle operates as designed — specifically:

1. **SubagentRunner.run_stateless respects timeout**: When a command exceeds the
   timeout, `subprocess.TimeoutExpired` is caught, envelope is produced with
   `exit_code=-1` and timeout output. This is the real termination path for
   stateless subagents (per ADR-15: "sub stateless subprocess.run isolated").

2. **PTY ctrl_c lifecycle for main agent**: `fs.send_ctrl_c` works on PtyPool
   sessions. This is a SEPARATE product claim from subagent termination —
   it's about the main agent's PTY being interruptible.

3. **Spawned subagent cleanup**: After spawn + completion, workspace cleanup
   happens (artifact written, workspace cleaned if workdir != root).

These are distinct product claims that need separate test functions.

### How to translate to code

Per tests-writing skill:

- **Class**: C1 composition-root (root: `drive_session` for spawn/ctrl_c;
  C0 for SubagentRunner timeout since it's subprocess not session)
- **Matrix**: A-gates-only with `subagent_spawning_enabled=True` for spawn tests
- **Oracle**: Rank 1 (events) + Rank 6 (artifact FS) + Rank 2 (outcome)
- **Kill-check**: each test named so removing the call site fails it

**Test functions:**

1. `test_subagent_timeout_produces_exit_code_minus_one` — C0p/C1:
   Create SubagentRunner with timeout=2, run `sleep 10`, assert envelope
   has `exit_code=-1` and output contains "Timeout"

2. `test_ctrl_c_interrupts_pty_session_via_drive_session` — C1:
   Create PtyPool, start a long-running bash via `fs.run_bash`,
   then send ctrl_c via `fs.send_ctrl_c` through drive_session,
   assert tool_result confirms "Ctrl+C ready"

3. `test_subagent_spawn_and_cleanup_via_drive_session` — C1:
   Spawn subagent via `fs.spawn_subagent`, assert spawn_start/spawn_done events,
   assert .fa/subagents/<id>.json artifact exists, assert workspace cleanup

4. `test_subagent_timeout_envelope_is_valid` — C0:
   SubagentEnvelope from timeout still passes fastjsonschema validation

### How to verify

- `pytest tests/test_subagent_termination_wiring.py -v` → all tests pass
- Each test has LIVE-PATH PROOF docstring
- `fa authoring-check` still green
- Full suite green
