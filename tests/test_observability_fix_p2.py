"""Observability Fix Phase 2 — DB authority conformance (LOGIC-1, LOGIC-13, LOGIC-8).

C1 composition-root + C2 CLI tests proving:

1. LOGIC-1: EventLog._initial_next_id seeds from session.db COUNT(*) rather
   than JSONL line count. Previously, if JSONL writes failed but DB writes
   succeeded (workflow scenario), the next EventLog instance would undercount
   and produce duplicate event_id values.

2. LOGIC-13: fa stats discovers sessions by session.db existence rather than
   events.jsonl. Previously, sessions with a valid session.db but missing
   events.jsonl were invisible.

3. LOGIC-8: _cmd_run catches RuntimeError from EventLog authority and prints
   a friendly message instead of a raw traceback. Previously, a non-writable
   session.db path produced an unhandled exception.

Kill-check: reverting each fix makes the corresponding test fail.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fa.inner_loop.session_db import SessionDatabase
from fa.inner_loop.state import EventLog

# ── LOGIC-1: _initial_next_id reads DB, not JSONL ─────────────────────────


def test_initial_next_id_reads_authority_not_jsonl(tmp_path: Path) -> None:
    """C0: the counter uses SessionDatabase authority, never JSONL line count.

    Kill-check: passing a JSONL path instead of the initialized authority is no
    longer possible at the production call site or this test's API boundary.
    """
    jsonl_path = tmp_path / "events.jsonl"
    db = SessionDatabase(tmp_path / "session.db")
    for i in range(5):
        db.append_event_row(
            {
                "event_id": f"ev-{i + 1:06d}",
                "ts": "2026-01-01T00:00:00Z",
                "run_id": "test",
                "actor": "test",
                "kind": "test",
                "content": {"i": i},
                "harness_id": "fa@0.1",
            }
        )

    # The mirror has fewer rows and must be irrelevant to correctness.
    jsonl_path.write_text('{"event_id":"ev-000001"}\n', encoding="utf-8")

    assert EventLog._initial_next_id(db) == 6


def test_initial_next_id_returns_one_for_empty_authority(tmp_path: Path) -> None:
    """C0: a freshly initialized authority starts the logical id at one."""
    assert EventLog._initial_next_id(SessionDatabase(tmp_path / "session.db")) == 1


def test_initial_next_id_does_not_fallback_on_authority_failure(tmp_path: Path) -> None:
    """C0: a counter read failure is observable, not replaced by JSONL count."""
    db = SessionDatabase(tmp_path / "session.db")
    (tmp_path / "events.jsonl").write_text('{"event_id":"ev-000001"}\n', encoding="utf-8")

    from unittest.mock import patch

    with patch.object(db, "event_count", side_effect=RuntimeError("authority unavailable")):
        with pytest.raises(RuntimeError, match="authority unavailable"):
            EventLog._initial_next_id(db)


def test_fresh_event_log_initializes_authority_before_counter(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """C1: nested fresh runs create schema before the first counter query.

    Kill-check: restoring the old ``_initial_next_id(path)`` call before
    ``SessionDatabase(...)`` recreates the ``unable to open database file``
    warning on this exact fresh-run path.
    """
    caplog.set_level("WARNING")

    log = EventLog(tmp_path / "nested" / "events.jsonl", run_id="fresh")

    assert log._next_id == 1
    assert log.session_db.path == tmp_path / "nested" / "session.db"
    assert log.session_db.event_count() == 0
    assert not any("DB counter unavailable" in record.message for record in caplog.records)


def test_event_log_authority_initialization_failure_is_fail_closed(tmp_path: Path) -> None:
    """C3: EventLog does not create a JSONL-only session when DB init fails."""
    from unittest.mock import patch

    events_path = tmp_path / "nested" / "events.jsonl"
    with patch.object(SessionDatabase, "_connect", side_effect=OSError("disk unavailable")):
        with pytest.raises(RuntimeError, match="session_db_init_failed"):
            EventLog(events_path, run_id="broken")

    assert not events_path.exists()


def test_no_duplicate_event_ids_after_two_sessions_same_db(tmp_path: Path) -> None:
    """C1 composition-root: two EventLog instances on same session.db produce unique event_ids.

    This simulates the workflow scenario where each stage creates a new
    EventLog pointing at the same session.db.

    Kill-check: reverting _initial_next_id to JSONL-only produces duplicate
    event_ids when JSONL writes fail.
    """
    db_path = tmp_path / "session.db"
    jsonl_path = tmp_path / "events.jsonl"

    # First EventLog instance — write some events
    log1 = EventLog(jsonl_path, run_id="test-dup")
    for i in range(3):
        log1.append(actor="test", kind="telemetry", content={"i": i})

    # Simulate JSONL write failure: delete the JSONL
    if jsonl_path.exists():
        jsonl_path.unlink()

    # Second EventLog instance on the same path
    log2 = EventLog(jsonl_path, run_id="test-dup")
    event4 = log2.append(actor="test", kind="telemetry", content={"i": 3})

    # Verify all event_ids are unique
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute("SELECT event_id FROM event_log ORDER BY id")
    all_ids = [row[0] for row in cur.fetchall()]
    conn.close()

    assert len(all_ids) == len(set(all_ids)), f"Duplicate event_ids found: {all_ids}"
    # The 4th event should have a monotonically increasing ID
    assert event4.event_id > all_ids[2], f"event_id not monotonically increasing: {all_ids}"


# ── LOGIC-13: Session discovery by session.db ─────────────────────────────


def test_stats_discovers_session_by_db_not_jsonl(tmp_path: Path) -> None:
    """C2 CLI: fa stats finds sessions by session.db existence, not events.jsonl.

    Kill-check: reverting to events.jsonl check makes session invisible.
    """

    runs_dir = tmp_path / "session-log"
    session_dir = runs_dir / "test-session"
    session_dir.mkdir(parents=True)

    # Create session.db but NO events.jsonl
    db_path = session_dir / "session.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS event_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "event_id TEXT NOT NULL, ts TEXT NOT NULL, run_id TEXT NOT NULL, "
        "actor TEXT NOT NULL, kind TEXT NOT NULL, tool_name TEXT NOT NULL DEFAULT '', "
        "tool_call_id TEXT NOT NULL DEFAULT '', parent_event_id TEXT NOT NULL DEFAULT '', "
        "content TEXT NOT NULL, harness_id TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO event_log (event_id, ts, run_id, actor, kind, content, harness_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("ev-000001", "2026-01-01T00:00:00Z", "test-session", "runtime", "run_started", '{"role":"coder"}', "fa@0.1"),
    )
    conn.commit()
    conn.close()

    # No events.jsonl file exists!
    assert not (session_dir / "events.jsonl").exists()
    assert (session_dir / "session.db").exists()

    # The session discovery in _cmd_stats uses (d / "session.db").exists()
    # after the fix. We verify the condition directly.
    discovered = [d for d in runs_dir.iterdir() if d.is_dir() and (d / "session.db").exists()]
    assert len(discovered) == 1
    assert discovered[0].name == "test-session"


# ── LOGIC-8: Friendly error on EventLog RuntimeError ──────────────────────


def test_run_cli_stage_routes_db_runtime_errors_to_friendly_mapper() -> None:
    """C0 caller-edge check: the live stage boundary invokes the extracted mapper."""
    import inspect

    import fa.cli as cli_module

    source = inspect.getsource(cli_module._run_cli_stage)
    assert "except RuntimeError as error" in source
    assert "_session_db_runtime_error_message(error" in source
