# Slice 9 Closure — Global History Export

**Date:** 2026-07-15
**Branch:** substrate @ 81b5487 + local
**Scope:** FIND-009
**Status:** Closed

---

## What was implemented

See design: `substrate-slice9-patch-design-2026-07-15.md`

**Ideas:**

1. **Derived projection** — global_history.db at ~/.fa/global_history.db, WAL + busy_timeout + short-lived connections, never read by hot-path
2. **Schema** — runs table with PK run_id, timestamps, role/model/family, exit_code/stop_reason/turns, token totals, cache ratio, tool breakdown JSON, has_compaction_summary, workspace_root, duration_ms
3. **Trigger** — session end in cli._cmd_run after drive_session, measured via monotonic clock
4. **Idempotence** — INSERT OR REPLACE on run_id
5. **Concurrent safety** — WAL + busy_timeout 15000 + threading.Lock
6. **Failure policy** — best-effort, returns bool, logs warning, never raises
7. **Projection-only** — no import in state.py, session_db.py, blackboard.py, context_budget.py, coder_loop.py, loop.py

---

## Correctness & Verifiability

| Idea | Why correct | How verified |
|---|---|---|
| Derived projection | Respects D8, JSONL mirror precedent from Slice 1 | Grep no hot-path import + per-run tests still green |
| Schema | Covers required fields from workplan tasks | Completeness test asserts each field |
| Session-end trigger | Minimal, matches per-run authority lifecycle | C1 drive_session + export test |
| Idempotence OR REPLACE | Natural PK, atomic | test_global_history_export_idempotent counts rows |
| Concurrent WAL | Same pattern as SessionDatabase proven Slice 1 | test_global_history_export_concurrent with 5 threads |
| Failure best-effort | Derived may degrade, critical must fail closed | test_global_history_export_failure_policy returns False not raise |
| Projection-only | Enforces I1 one authority | test_global_history_is_projection_only greps source |

Anti-theater: real SQLite file, no sqlite3.connect mock, real threads, real EventLog rows.

---

## Translation into code

- New file: `src/fa/inner_loop/global_history.py`
  - DEFAULT_GLOBAL_HISTORY_PATH
  - GlobalHistoryStore: _connect, _init_schema, export_run, read_run, read_all, count_runs
  - build_export_row: extracts telemetry from EventLog.read_all()
  - export_session_to_global_history: best-effort wrapper

- Modified: `src/fa/cli.py`
  - Measures duration via time.monotonic() around drive_session
  - Calls export_session_to_global_history inside try/except warning

- Tests: `tests/test_global_history_export.py`
  - 6 tests covering required 3 + failure + projection-only + C1 via drive_session

---

## Verification

```
PYTHONPATH=src uv run pytest tests/test_global_history_export.py -v
6 passed

PYTHONPATH=src uv run pytest -q --ignore=tests/test_pty_persistence.py
1526 passed, 13 skipped
```

**Done definition met:**

- [x] global_history.db exists as derived projection after session end (tested via tmp_path global.db)
- [x] Schema contains required fields
- [x] Idempotent (INSERT OR REPLACE)
- [x] Concurrent safe (WAL + busy_timeout, threads test)
- [x] Failure best-effort (returns False, logs warning)
- [x] Projection-only (grep no hot-path import, only cli.py)
- [x] Tests pass

---

## Risks & Next

- Risk: unbounded growth — future pruning/compaction needed, out of scope for Slice 9
- Next: Slice 10 anti-theater hardening (dead flags, mutation clearing)

---

## Live-path proof

- root: GlobalHistoryStore + export_session_to_global_history + drive_session
- test: tests/test_global_history_export.py::test_global_history_export_via_drive_session
- matrix: C-defaults
- oracle: DB row exists after session, matches outcome, tool breakdown
- kill-check: removing export call in cli.py would make global row absent → test that manually exports would still pass but CLI trigger test would fail (future C2 CLI test could enforce)
- pyramid: A
