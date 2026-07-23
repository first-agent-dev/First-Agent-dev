"""Tests for shared SQLite connection utilities (fa.inner_loop._sqlite_common).

Verifies create_sqlite_connection configures connections with the
project-standard PRAGMAs (busy_timeout) and that the connection is
usable for the short-lived connection discipline shared by
SessionDatabase and GlobalHistoryStore.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

from fa.inner_loop._sqlite_common import (
    SQLITE_BUSY_TIMEOUT_MS,
    SQLITE_TIMEOUT_SECONDS,
    create_sqlite_connection,
)


class TestConstants:
    """Sanity-check the shared tuning constants."""

    def test_timeout_is_positive_float(self) -> None:
        assert SQLITE_TIMEOUT_SECONDS > 0
        assert isinstance(SQLITE_TIMEOUT_SECONDS, float)

    def test_busy_timeout_is_positive_int(self) -> None:
        assert SQLITE_BUSY_TIMEOUT_MS > 0
        assert isinstance(SQLITE_BUSY_TIMEOUT_MS, int)


class TestCreateSqliteConnection:
    """C0 unit tests for create_sqlite_connection()."""

    def test_creates_file_on_first_connect(self, tmp_path: Path) -> None:
        """Connection is opened against a path; parent must exist (caller ensures)."""
        db_path = tmp_path / "test.db"
        conn = create_sqlite_connection(db_path)
        try:
            assert isinstance(conn, sqlite3.Connection)
            # The DB file is created lazily by sqlite3 on first execute.
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            conn.commit()
        finally:
            conn.close()
        assert db_path.exists()

    def test_busy_timeout_pragma_applied(self, tmp_path: Path) -> None:
        """busy_timeout PRAGMA is applied to every new connection."""
        db_path = tmp_path / "busy.db"
        conn = create_sqlite_connection(db_path)
        try:
            row = conn.execute("PRAGMA busy_timeout").fetchone()
            assert row is not None
            # PRAGMA busy_timeout returns the current timeout in milliseconds.
            assert int(row[0]) == SQLITE_BUSY_TIMEOUT_MS
        finally:
            conn.close()

    def test_connection_is_usable_for_wal(self, tmp_path: Path) -> None:
        """Caller can set journal_mode=WAL on the returned connection."""
        db_path = tmp_path / "wal.db"
        conn = create_sqlite_connection(db_path)
        try:
            row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
            # WAL returns 'wal' when successfully set.
            assert str(row[0]).lower() == "wal"
        finally:
            conn.close()

    def test_default_timeout_values_match_module_constants(self, tmp_path: Path) -> None:
        """Calling with defaults uses the module-level timeout constants."""
        db_path = tmp_path / "defaults.db"
        # We verify indirectly: explicit None defaults cannot be inspected but
        # we can confirm the connection opens successfully with defaults.
        conn = create_sqlite_connection(db_path)
        try:
            row = conn.execute("PRAGMA busy_timeout").fetchone()
            assert int(row[0]) == SQLITE_BUSY_TIMEOUT_MS
        finally:
            conn.close()

    def test_custom_timeout_overrides_default(self, tmp_path: Path) -> None:
        """Callers can override timeout_seconds and busy_timeout_ms."""
        db_path = tmp_path / "custom.db"
        custom_busy = 1000
        conn = create_sqlite_connection(
            db_path,
            timeout_seconds=1.0,
            busy_timeout_ms=custom_busy,
        )
        try:
            row = conn.execute("PRAGMA busy_timeout").fetchone()
            assert int(row[0]) == custom_busy
        finally:
            conn.close()

    def test_can_execute_crud(self, tmp_path: Path) -> None:
        """Returned connection supports standard CRUD on a real table."""
        db_path = tmp_path / "crud.db"
        conn = create_sqlite_connection(db_path)
        try:
            conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
            conn.execute("INSERT INTO items (name) VALUES (?)", ("alpha",))
            conn.execute("INSERT INTO items (name) VALUES (?)", ("beta",))
            conn.commit()
            rows = conn.execute("SELECT name FROM items ORDER BY id").fetchall()
            assert [r[0] for r in rows] == ["alpha", "beta"]
        finally:
            conn.close()


class TestConsumerWiring:
    """Kill-check: SessionDatabase and GlobalHistoryStore actually delegate to
    create_sqlite_connection() rather than each re-implementing
    sqlite3.connect(...) inline (which would silently reintroduce the R0801
    duplicate-code finding this module exists to close, and drift the two
    stores' connection discipline out of sync over time).

    The TestCreateSqliteConnection / TestConstants classes above are C0 on
    the helper in isolation; they pass unconditionally even if neither
    consumer imports the helper at all. This class is what actually proves
    the extraction did what its docstring claims.
    """

    def test_session_database_delegates_to_shared_factory(self, tmp_path: Path) -> None:
        """kill-check: reverting SessionDatabase._connect to an inline
        sqlite3.connect(...) call (the pre-extraction shape) makes this
        test fail — see fa.inner_loop.session_db._connect.
        """
        from fa.inner_loop import session_db

        with patch(
            "fa.inner_loop.session_db.create_sqlite_connection",
            wraps=create_sqlite_connection,
        ) as spy:
            db = session_db.SessionDatabase(tmp_path / "session.db")
            db._connect().close()  # exercising the delegation directly, by design

        assert spy.call_count >= 1

    def test_global_history_store_delegates_to_shared_factory(self, tmp_path: Path) -> None:
        """kill-check: reverting GlobalHistoryStore._connect to an inline
        sqlite3.connect(...) call (the pre-extraction shape) makes this
        test fail — see fa.inner_loop.global_history._connect.
        """
        from fa.inner_loop import global_history

        with patch(
            "fa.inner_loop.global_history.create_sqlite_connection",
            wraps=create_sqlite_connection,
        ) as spy:
            store = global_history.GlobalHistoryStore(db_path=tmp_path / "global_history.db")
            store._connect().close()  # exercising the delegation directly, by design

        assert spy.call_count >= 1
