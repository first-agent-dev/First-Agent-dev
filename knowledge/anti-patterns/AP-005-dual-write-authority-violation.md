---
compiled: 2026-07-18
applies_to: ADR-7 (EventLog), Phase 0.5 Blackboard, session_db authority
---

# AP-005 — Dual-write authority violation

## §Symptom

Tool handler writes to JSONL file but the corresponding `session.db` row is missing or stale. Agent reads from JSONL mirror and gets a different answer than code reading from SQLite authority.

## §Wrong shape

Writing to the JSONL mirror only (or writing to JSONL first, then SQLite), so that the human-readable file and the machine authority diverge on crash or partial failure.

## §Right shape

Always write to SQLite authority first. Only after the authoritative commit succeeds, advance logical state and write the JSONL mirror best-effort. If SQLite write fails, raise `RuntimeError` — do NOT silently fall through to JSONL-only write.

## §Why the wrong shape dominates

JSONL is the file operators see (`cat events.jsonl`). It "feels" like the primary artifact because it's human-readable. The SQLite DB is invisible. This visibility asymmetry makes JSONL-first writing the intuitive default.

## §Detection

1. `session_db.append_event_row()` raises `RuntimeError` if `session_db` is `None` — enforcement point in `src/fa/inner_loop/state.py`.
2. `Blackboard.write()` writes to `session_db` first, JSONL second — pattern in `src/fa/blackboard/blackboard.py`.
3. Test: verify JSONL is empty when SQLite write fails (composition-root test pattern).

## §Linked-ADR

ADR-7 §7 (Trace), Phase 0.5 Blackboard design

## §Evidence

- `src/fa/inner_loop/state.py` — `EventLog.append()` authority-first discipline
- `src/fa/blackboard/blackboard.py` — `Blackboard.write()` authority-first discipline
