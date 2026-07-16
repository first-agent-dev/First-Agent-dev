# Slice 9 Patch Design — Hybrid Export `global_history.db`

**Date:** 2026-07-15
**Scope:** Slice 9 only
**Parent:** `substrate-gap-closure-workplan-round2-2026-07-15.md` §Slice 9
**Locked decisions:** D8 unified per-run DB authority, D9 resume mutable, D10 subagent narrow

---

## 1. Slice 9 purpose

Close FIND-009: `global_history.db` export absent.

After slices 0-7, hot-path authority is unified in per-run `~/.fa/session-log/<run_id>/session.db`.
Global history must exist as **derived, safe cross-run projection**, not hot-path authority.

Slice 9 is **not** a DB migration, not a Stage C change, not logging migration.
Slice 9 is **projection + idempotence + failure semantics**.

---

## 2. Locked product/architecture rules for Slice 9

### D8 — Unified per-run DB authority (from decision-freeze)

- Active runtime state converges into per-run `session.db`
- Workspace/global DBs are derived projections, caches, indexes, analytics
- Hot-path must never read global_history.db for correctness

### I1 — One authority per concern

No dual-authority reads. If two stores exist, one authoritative, other derived.

### I3 — No silent degradation on critical paths, but best-effort for derived

Critical path = per-run DB writes. Derived export = best-effort warning, not hard stop.

---

## 3. What ideas are we implementing, with clear intents

### Idea 1 — Derived projection table, not authority

**Intent:** Make `~/.fa/global_history.db` a **read-only analytics mirror** of per-run sessions.
**Why correct:** Respects D8. Global file can lag, be deleted, be corrupted — active run still works. This is same pattern as `events.jsonl` mirror-only after Slice 1.
**Verifiable:** Grep that `SessionState`, `EventLog`, `SessionDatabase`, `Blackboard`, `ContextBudget`, `coder_loop` never import `GlobalHistory`. Only `cli.py` and `stats.py` may read it.

### Idea 2 — Minimal but complete schema

**Intent:** Export must contain enough to render `fa stats --run-id` and cross-run aggregates without reading per-run DBs.

**Proposed columns for table `runs`:**

- `run_id TEXT PRIMARY KEY` — natural id, used for idempotence
- `created_at TEXT NOT NULL` — first event ts or now
- `updated_at TEXT NOT NULL` — export time
- `role TEXT NOT NULL` — planner/coder/eval/compactor
- `model TEXT NOT NULL DEFAULT ''` — model slug from chain config
- `family TEXT NOT NULL DEFAULT ''` — openai/anthropic/etc
- `exit_code INTEGER NOT NULL` — from SessionOutcome
- `stop_reason TEXT NOT NULL` — stopped_by_llm, iteration_cap, context_budget_hard_stop, chain_exhausted, etc
- `turns INTEGER NOT NULL` — outcome.turns
- `input_tokens INTEGER NOT NULL DEFAULT 0`
- `output_tokens INTEGER NOT NULL DEFAULT 0`
- `cache_read_input_tokens INTEGER NOT NULL DEFAULT 0`
- `cache_creation_input_tokens INTEGER NOT NULL DEFAULT 0`
- `cache_hit_ratio REAL NOT NULL DEFAULT 0.0`
- `tool_calls_total INTEGER NOT NULL DEFAULT 0`
- `tool_calls_breakdown_json TEXT NOT NULL DEFAULT '{}'` — JSON map tool_name->count
- `has_compaction_summary INTEGER NOT NULL DEFAULT 0` — 0/1 bool whether compaction_stage3_done event present
- `workspace_root TEXT NOT NULL DEFAULT ''`
- `duration_ms INTEGER NOT NULL DEFAULT 0` — optional wall time

**Why correct:** Covers required tasks:
- run id ✓
- timestamps ✓ (created_at/updated_at)
- role/model ✓
- session summary ✓ (tokens, cache ratio)
- compaction summary presence ✓
- outcome/stop reason ✓
- telemetry rollups ✓ (tool_calls_total + breakdown)

**Verifiable:** Terminal state export completeness test reads back row and asserts all required fields non-empty / correct for known session.

### Idea 3 — Export trigger = session end minimum

**Intent:** Export at end of `fa run` and `fa workflow` stage. Not on every turn.

**Why correct:** Minimal blast radius. Per-run DB is authority during run; global is derived after terminal outcome known. Checkpoint export optional later, not needed for Slice 9 done definition.

**Implementation:** In `cli.py _cmd_run`, after `drive_session` returns `SessionOutcome`, call `export_session_to_global_history(...)` inside try/except. Same for workflow? Workflow currently calls `_cmd_run` per stage, each stage already exports its run_id (same run_id across stages? Workflow uses same run_id for all stages, so export will be upserted each stage — desirable).

**Verifiable:** After a `drive_session` C1 test with mock chain, global_history.db contains row for that run_id.

### Idea 4 — Idempotence via INSERT OR REPLACE on run_id PK

**Intent:** Exporting same run_id twice must not create duplicate, must be safe to retry.

**Why correct:** run_id is natural primary key. INSERT OR REPLACE is atomic in SQLite, provides upsert semantics. Alternative INSERT OR IGNORE would keep first, not latest — we want latest to win (e.g., workflow stage2 overwrites stage1 outcome).

**Verifiable:** `test_global_history_export_idempotent`:
- Export run_id once, count rows =1
- Export same run_id again with different stop_reason, count still 1, row reflects second export (or first, but not duplicate)
- Assert no duplicate rows

### Idea 5 — Concurrent safety via WAL + busy_timeout + short-lived connections

**Intent:** Two `fa run` with different run_ids (or same run_id in workflow) may export concurrently. Must not corrupt DB, must not lose rows.

**Why correct:** Same pattern as `SessionDatabase`:
- PRAGMA journal_mode=WAL
- PRAGMA synchronous=NORMAL
- PRAGMA busy_timeout=15000 ms
- Short-lived connections per operation + threading.Lock for in-process serialization

WAL allows one writer + many readers; busy_timeout retries on SQLITE_BUSY.

**Verifiable:** `test_global_history_export_concurrent`:
- Spawn 5 threads each exporting distinct run_ids to same global_history.db
- Join, assert 5 rows present, no SQLITE_BUSY corruption
- Also test same run_id concurrent upserts: 5 threads same run_id, final count 1, no exception

### Idea 6 — Failure policy = best-effort warning, not hard stop

**Intent:** Global export must never break main session. If global DB unwritable, disk full, permission denied, etc., log warning and continue, returning False.

**Why correct:** Respects I3 but inverted for derived surface: critical path (per-run DB) fails closed, derived may degrade with warning. This matches JSONL mirror policy from Slice 1 (mirror failure = warning only).

**Verifiable:** Force export failure by passing unwritable path (e.g., `/root/no_perm/global.db` or read-only directory). Assert function returns False, does not raise, logs warning. Main session outcome still returned.

### Idea 7 — Projection-only enforcement via import graph

**Intent:** Ensure no hot-path module imports global history for correctness decisions.

**Why correct:** Enforces D8 and I1. If hot-path reads global, we reintroduce split-brain.

**Verifiable:** Grep test `test_global_history_is_projection_only`:
- Scan `src/fa/inner_loop/state.py`, `session_db.py`, `blackboard.py`, `context_budget.py`, `coder_loop.py`, `loop.py`, `compaction/*`
- Assert none imports `global_history`
- Only `cli.py`, `stats.py`, maybe `telemetry` may import (allowed as derived consumers)

---

## 4. Are ideas correct and verifiable? (Checklist)

| Idea | Correct? (arg) | Verifiable by test? | Anti-theater |
|---|---|---|---|
| Derived projection | Yes, respects D8, JSONL mirror precedent | Grep no hot-path import + existing per-run tests still pass | Would fail if code read global for decision |
| Minimal schema | Yes, covers required fields from workplan §Concrete tasks 1 | Terminal completeness test asserts each field | Checks real DB row, not mock |
| Session-end trigger | Yes, minimal, matches per-run authority lifecycle | C1 drive_session + export, then read global | Fails if trigger not called |
| Idempotence OR REPLACE | Yes, natural PK, atomic | Idempotent test counts rows | Would show duplicate if not |
| Concurrent safety WAL | Yes, same as SessionDatabase pattern proven in Slice 1 | Concurrent test with threads | Would corrupt or raise BUSY without |
| Failure best-effort | Yes, derived surface may degrade | Force failure test returns False not raise | Would crash main if wrong |
| Projection-only import | Yes, enforces I1 | Grep test | Would import if violated |

---

## 5. How to translate into code — exact file edit map

### New file

#### `src/fa/inner_loop/global_history.py`

Responsibilities:
- `DEFAULT_GLOBAL_HISTORY_PATH = Path.home() / ".fa" / "global_history.db"`
- `class GlobalHistoryStore`:
  - `__init__(db_path: Path | None = None)` — resolve path, mkdir parent, init schema
  - `_connect() -> sqlite3.Connection` — busy_timeout 15000, WAL, NORMAL
  - `_init_schema()` — CREATE TABLE IF NOT EXISTS runs + indexes
  - `export_run(row: Mapping[str, Any]) -> None` — INSERT OR REPLACE, with write lock
  - `read_run(run_id: str) -> dict | None`
  - `read_all() -> list[dict]`
  - `count_runs() -> int`
- Helper `build_export_row(...) -> dict` — builds row from SessionOutcome + EventLog
- Helper `export_session_to_global_history(...) -> bool` — best-effort wrapper, catches exception, logs warning, returns True/False
- No read of global_history in hot-path; only writes here

Schema SQL:
```sql
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  role TEXT NOT NULL,
  model TEXT NOT NULL DEFAULT '',
  family TEXT NOT NULL DEFAULT '',
  exit_code INTEGER NOT NULL,
  stop_reason TEXT NOT NULL,
  turns INTEGER NOT NULL,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  cache_read_input_tokens INTEGER NOT NULL DEFAULT 0,
  cache_creation_input_tokens INTEGER NOT NULL DEFAULT 0,
  cache_hit_ratio REAL NOT NULL DEFAULT 0.0,
  tool_calls_total INTEGER NOT NULL DEFAULT 0,
  tool_calls_breakdown_json TEXT NOT NULL DEFAULT '{}',
  has_compaction_summary INTEGER NOT NULL DEFAULT 0,
  workspace_root TEXT NOT NULL DEFAULT '',
  duration_ms INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_runs_role ON runs(role);
CREATE INDEX IF NOT EXISTS idx_runs_updated_at ON runs(updated_at);
```

### Modified files

#### `src/fa/cli.py`

- After `drive_session` returns outcome, in `_cmd_run`, call export:
```python
try:
    from fa.inner_loop.global_history import export_session_to_global_history
    export_session_to_global_history(
        run_id=run_id,
        outcome=outcome,
        log=log,
        role=role,
        model=chain_config.model,
        family=chain_config.family,
        workspace_root=workspace,
        duration_ms=...,
    )
except Exception as exc:
    logger.warning(f"global_history export failed for {run_id}: {exc}")
```

- Same for workflow? Since workflow calls `_cmd_run` per stage, export already happens per stage via same path. No extra needed, but ensure workflow's run_id same across stages → upsert works.

#### `src/fa/stats.py` (optional, out of scope for minimal Slice 9, but note)

- Could add reader for global_history.db for `fa stats --global` future, but not required for done definition. Keep out of Slice 9 to preserve discipline, or add read helper later.

#### No edits to

- `state.py`, `session_db.py`, `blackboard.py`, `context_budget.py`, `coder_loop.py` (except for export call in cli, not in loop). This enforces projection-only.

---

## 6. How to verify implementation behaves like stated intents — test plan

### Test file: `tests/test_global_history_export.py` (new, per required tests)

#### Test 1 — `test_global_history_export_idempotent`

- Setup: tmp_path / global.db, create GlobalHistoryStore, build row for run_id "run-1"
- Export once → count 1, read back, assert fields
- Export same run_id again with different stop_reason → count still 1, read back stop_reason == second (REPLACE)
- Export same run_id third time identical → count 1
- Assert idempotence

#### Test 2 — `test_global_history_export_concurrent`

- Setup: tmp global.db, 5 threads each exporting distinct run_ids (run-0..run-4) concurrently
- Join threads
- Assert count 5
- Also: 5 threads same run_id "run-shared" concurrent → after join, count for that run_id is 1 (distinct total still 5 or 6 depending), no exception, no corruption

Uses `threading.Thread`, real SQLite file (no mock), real GlobalHistoryStore (no sqlite3.connect mock) — anti-theater.

#### Test 3 — `test_global_history_export_completeness`

- Setup: Create SessionState + EventLog with known events:
  - 2 tool_call, 2 tool_result, 1 usage row with input/output tokens, 1 compaction_stage3_done
- Create SessionOutcome with exit_code 0, stop_reason stopped_by_llm, turns 2
- Call export_session_to_global_history
- Read back row
- Assert:
  - run_id matches
  - role/model/family matches
  - exit_code, stop_reason, turns matches
  - input_tokens/output_tokens from usage rows
  - tool_calls_total == 2
  - has_compaction_summary ==1
  - workspace_root present
  - tool_calls_breakdown_json contains fs.read_file etc

#### Test 4 — `test_global_history_export_failure_policy`

- Pass unwritable path like /root/forbidden/global.db or use monkeypatch to make _init_schema raise
- Call export_session_to_global_history, assert returns False not raises
- Assert logger warning emitted (caplog)

#### Test 5 — `test_global_history_is_projection_only` (anti-theater)

- Grep src/fa/inner_loop/state.py, session_db.py, blackboard.py, context_budget.py, coder_loop.py, loop.py
- Assert "global_history" not in file content
- Only allowed importers: cli.py, stats.py (optional)

---

## 7. Anti-theater rules for Slice 9

- Do not mock `sqlite3.connect` — use real temp DB file
- Do not assert only that file exists — assert row fields
- Do not test only builder args — test actual export via GlobalHistoryStore
- Concurrent test must use threads + real file, not mocked
- Idempotence test must check count, not just return value
- Projection-only test must grep actual source files

---

## 8. Done definition

Slice 9 done when:

1. `~/.fa/global_history.db` (or tmp path in tests) exists as derived projection after session end
2. Schema contains required fields (run_id PK, timestamps, role/model, summary, compaction presence, outcome, telemetry)
3. Export is idempotent (INSERT OR REPLACE)
4. Concurrent exports safe (WAL + busy_timeout, no corruption)
5. Failure is best-effort warning, not crash
6. No hot-path module imports global_history (projection-only)
7. Tests `test_global_history_export_idempotent`, `..._concurrent`, `..._completeness` pass
8. Existing 1520 tests still pass

---

## 9. Risks & out-of-scope

- Risk: global_history.db grows unbounded — not solved in Slice 9, future pruning needed
- Out-of-scope: `fa stats --global` CLI reading global_history, analytics queries, checkpoint exports
- Out-of-scope: telemetry DB migration, logging migration (already Slice 8)

---

## 10. Implementation sequence

1. Create `src/fa/inner_loop/global_history.py` with schema + store + export helpers
2. Wire export into `src/fa/cli.py _cmd_run` after drive_session (try/except warning)
3. Add tests file `tests/test_global_history_export.py` with 5 tests above
4. Run focused tests, then full suite
5. Verify projection-only via grep test
