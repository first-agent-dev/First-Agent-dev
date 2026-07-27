"""Session-scoped authoritative SQLite substrate for hot-path state.

The production composition roots open one physical database per persistent
session. Event rows are filtered by ``run_id`` at the ``EventLog`` facade;
Blackboard rows are session-scoped and retain the producing ``run_id`` as
provenance. JSONL files are mirrors, never the current-format authority.

Direct construction without ``session_id`` remains a compatibility path for
existing isolated unit fixtures and legacy helper surfaces. The production
``fa run``/``fa workflow`` roots must inject a session-bound instance.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop._sqlite_common import create_sqlite_connection, payload_matches_key

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = "session-v1"
_SCHEMA_META_KEY = "__fa_schema__"
_SESSION_ID_META_KEY = "__fa_session_id__"
_RUN_BINDING_PREFIX = "run_binding:"

_EVENT_COLUMNS = {
    "id",
    "event_id",
    "session_id",
    "ts",
    "run_id",
    "actor",
    "kind",
    "tool_name",
    "tool_call_id",
    "parent_event_id",
    "content",
    "harness_id",
}
_BLACKBOARD_COLUMNS = {
    "id",
    "session_id",
    "run_id",
    "type",
    "content_hash",
    "toolchain_digest",
    "schema_version",
    "parent_id",
    "read_set",
    "write_set",
    "assumptions",
    "version_dependencies",
    "timestamp",
    "payload",
}


class SessionDatabaseError(RuntimeError):
    """Structured authority/bootstrap failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class SessionDatabase:
    """Authoritative SQLite database for one persistent session.

    ``session_id`` is required for the production path. The empty default is
    retained only so existing isolated tests and legacy helpers can construct a
    local authority without having to model a persistent session namespace.
    """

    def __init__(self, db_path: Path, *, session_id: str = "") -> None:
        self.path = Path(db_path)
        self.session_id = session_id
        self._write_lock = threading.Lock()
        self._legacy_schema = False
        self._initialize_or_validate()

    @classmethod
    def open_existing(cls, db_path: Path, *, session_id: str) -> SessionDatabase:
        """Open a current-format DB without creating a file or parent directory."""
        path = Path(db_path)
        if not path.is_file():
            raise SessionDatabaseError("session_db_not_found", f"database does not exist: {path}")
        instance = cls.__new__(cls)
        instance.path = path
        instance.session_id = session_id
        instance._write_lock = threading.Lock()
        instance._legacy_schema = False
        try:
            instance._validate_current_schema(require_identity=True)
        except SessionDatabaseError:
            raise
        except Exception as exc:
            raise SessionDatabaseError("session_db_open_failed", str(exc)) from exc
        return instance

    def _connect(self) -> sqlite3.Connection:
        return create_sqlite_connection(self.path)

    @staticmethod
    def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row[1]) for row in rows}

    @staticmethod
    def _has_table(conn: sqlite3.Connection, table: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None

    def _initialize_or_validate(self) -> None:
        existed = self.path.exists() and self.path.stat().st_size > 0
        if existed:
            try:
                conn = self._connect()
                try:
                    has_event = self._has_table(conn, "event_log")
                    has_blackboard = self._has_table(conn, "blackboard")
                    if has_event or has_blackboard:
                        event_columns = self._columns(conn, "event_log") if has_event else set()
                        blackboard_columns = self._columns(conn, "blackboard") if has_blackboard else set()
                        if not _EVENT_COLUMNS.issubset(event_columns) or not _BLACKBOARD_COLUMNS.issubset(
                            blackboard_columns
                        ):
                            if self.session_id:
                                raise SessionDatabaseError(
                                    "session_db_legacy_schema",
                                    f"database is not a current session DB: {self.path}",
                                )
                            # Isolated fixtures created by the pre-session schema
                            # remain readable through the explicit compatibility path.
                            self._legacy_schema = True
                            return
                finally:
                    conn.close()
            except SessionDatabaseError:
                raise
            except Exception as exc:
                raise SessionDatabaseError("session_db_inspect_failed", str(exc)) from exc

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_current_schema()
        if self.session_id:
            self._ensure_identity()

    def _init_current_schema(self) -> None:
        try:
            with self._write_lock:
                conn = self._connect()
                try:
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA synchronous=NORMAL;")
                    with conn:
                        conn.execute(
                            """
                            CREATE TABLE IF NOT EXISTS event_log (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                event_id TEXT NOT NULL,
                                session_id TEXT NOT NULL DEFAULT '',
                                ts TEXT NOT NULL,
                                run_id TEXT NOT NULL,
                                actor TEXT NOT NULL,
                                kind TEXT NOT NULL,
                                tool_name TEXT NOT NULL DEFAULT '',
                                tool_call_id TEXT NOT NULL DEFAULT '',
                                parent_event_id TEXT NOT NULL DEFAULT '',
                                content TEXT NOT NULL,
                                harness_id TEXT NOT NULL
                            );
                            """
                        )
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_event_log_kind ON event_log(kind);")
                        conn.execute(
                            "CREATE INDEX IF NOT EXISTS idx_event_log_session_run_id_id "
                            "ON event_log(session_id, run_id, id);"
                        )
                        conn.execute(
                            "CREATE INDEX IF NOT EXISTS idx_event_log_tool_call_id ON event_log(tool_call_id);"
                        )
                        conn.execute(
                            """
                            CREATE TABLE IF NOT EXISTS blackboard (
                                id TEXT PRIMARY KEY,
                                session_id TEXT NOT NULL DEFAULT '',
                                run_id TEXT NOT NULL,
                                type TEXT NOT NULL,
                                content_hash TEXT NOT NULL,
                                toolchain_digest TEXT NOT NULL,
                                schema_version TEXT NOT NULL,
                                parent_id TEXT,
                                read_set TEXT NOT NULL,
                                write_set TEXT NOT NULL,
                                assumptions TEXT NOT NULL,
                                version_dependencies TEXT NOT NULL,
                                timestamp TEXT NOT NULL,
                                payload TEXT NOT NULL
                            );
                            """
                        )
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_blackboard_type ON blackboard(type);")
                        conn.execute(
                            "CREATE INDEX IF NOT EXISTS idx_blackboard_session_type_ts "
                            "ON blackboard(session_id, type, timestamp);"
                        )
                        conn.execute(
                            """
                            CREATE TABLE IF NOT EXISTS session_meta (
                                key TEXT PRIMARY KEY,
                                value TEXT NOT NULL,
                                updated_at TEXT NOT NULL
                            );
                            """
                        )
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO session_meta(key, value, updated_at)
                            VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                            """,
                            (_SCHEMA_META_KEY, json.dumps({"schema_version": CURRENT_SCHEMA_VERSION})),
                        )
                finally:
                    conn.close()
        except SessionDatabaseError:
            raise
        except Exception as exc:
            logger.warning("Failed to initialize authoritative SessionDatabase %s: %s", self.path, exc)
            raise SessionDatabaseError("session_db_init_failed", str(exc)) from exc

    def _validate_current_schema(self, *, require_identity: bool) -> None:
        try:
            conn = self._connect()
            try:
                if not self._has_table(conn, "event_log") or not self._has_table(conn, "blackboard"):
                    raise SessionDatabaseError(
                        "session_db_schema_unsupported", f"missing authority tables: {self.path}"
                    )
                if not _EVENT_COLUMNS.issubset(self._columns(conn, "event_log")):
                    raise SessionDatabaseError("session_db_schema_unsupported", f"event_log schema: {self.path}")
                if not _BLACKBOARD_COLUMNS.issubset(self._columns(conn, "blackboard")):
                    raise SessionDatabaseError("session_db_schema_unsupported", f"blackboard schema: {self.path}")
                schema = self._get_meta_from_connection(conn, _SCHEMA_META_KEY)
                if not isinstance(schema, dict) or schema.get("schema_version") != CURRENT_SCHEMA_VERSION:
                    raise SessionDatabaseError("session_db_schema_unsupported", f"schema marker: {self.path}")
                if require_identity:
                    identity = self._get_meta_from_connection(conn, _SESSION_ID_META_KEY)
                    if identity != self.session_id:
                        raise SessionDatabaseError(
                            "session_db_identity_mismatch",
                            f"expected session {self.session_id!r}, found {identity!r} at {self.path}",
                        )
            finally:
                conn.close()
        except SessionDatabaseError:
            raise
        except Exception as exc:
            raise SessionDatabaseError("session_db_schema_check_failed", str(exc)) from exc

    @staticmethod
    def _get_meta_from_connection(conn: sqlite3.Connection, key: str) -> Any | None:
        row = conn.execute("SELECT value FROM session_meta WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def _ensure_identity(self) -> None:
        with self._write_lock:
            conn = self._connect()
            try:
                with conn:
                    existing = self._get_meta_from_connection(conn, _SESSION_ID_META_KEY)
                    if existing is None:
                        conn.execute(
                            "INSERT INTO session_meta(key, value, updated_at) "
                            "VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
                            (_SESSION_ID_META_KEY, json.dumps(self.session_id)),
                        )
                    elif existing != self.session_id:
                        raise SessionDatabaseError(
                            "session_db_identity_mismatch",
                            f"expected session {self.session_id!r}, found {existing!r} at {self.path}",
                        )
            finally:
                conn.close()

    def event_count(self) -> int:
        """Return the authoritative number of persisted event rows."""
        conn = self._connect()
        try:
            if self._legacy_schema or not self.session_id:
                cur = conn.execute("SELECT COUNT(*) FROM event_log")
            else:
                cur = conn.execute("SELECT COUNT(*) FROM event_log WHERE session_id = ?", (self.session_id,))
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("event_log count query returned no row")
            return int(row[0])
        except (OSError, sqlite3.Error, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Authoritative event_log count failed for %s: %s", self.path, exc)
            raise RuntimeError(f"event_log_count_failed: {exc}") from exc
        finally:
            conn.close()

    def append_event_row(self, row: Mapping[str, Any]) -> None:
        row_session_id = str(row.get("session_id", self.session_id))
        if self.session_id and row_session_id != self.session_id:
            raise SessionDatabaseError(
                "session_db_identity_mismatch",
                f"event row session {row_session_id!r} does not match {self.session_id!r}",
            )
        with self._write_lock:
            conn = self._connect()
            try:
                with conn:
                    if self._legacy_schema:
                        conn.execute(
                            """
                            INSERT INTO event_log (
                                event_id, ts, run_id, actor, kind, tool_name,
                                tool_call_id, parent_event_id, content, harness_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(row["event_id"]),
                                str(row["ts"]),
                                str(row["run_id"]),
                                str(row["actor"]),
                                str(row["kind"]),
                                str(row.get("tool_name", "")),
                                str(row.get("tool_call_id", "")),
                                str(row.get("parent_event_id", "")),
                                json.dumps(row.get("content", {}), ensure_ascii=False),
                                str(row["harness_id"]),
                            ),
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO event_log (
                                event_id, session_id, ts, run_id, actor, kind, tool_name,
                                tool_call_id, parent_event_id, content, harness_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(row["event_id"]),
                                row_session_id,
                                str(row["ts"]),
                                str(row["run_id"]),
                                str(row["actor"]),
                                str(row["kind"]),
                                str(row.get("tool_name", "")),
                                str(row.get("tool_call_id", "")),
                                str(row.get("parent_event_id", "")),
                                json.dumps(row.get("content", {}), ensure_ascii=False),
                                str(row["harness_id"]),
                            ),
                        )
            except SessionDatabaseError:
                raise
            except Exception as exc:
                logger.warning("Authoritative event_log write failed for %s: %s", self.path, exc)
                raise RuntimeError(f"event_log_write_failed: {exc}") from exc
            finally:
                conn.close()

    def read_event_rows(self, *, run_id: str | None = None) -> tuple[dict[str, Any], ...]:
        conn = self._connect()
        try:
            if self._legacy_schema:
                if run_id is None:
                    cur = conn.execute(
                        """
                        SELECT event_id, '' AS session_id, ts, run_id, actor, kind, tool_name,
                               tool_call_id, parent_event_id, content, harness_id
                        FROM event_log ORDER BY id ASC
                        """
                    )
                else:
                    cur = conn.execute(
                        """
                        SELECT event_id, '' AS session_id, ts, run_id, actor, kind, tool_name,
                               tool_call_id, parent_event_id, content, harness_id
                        FROM event_log WHERE run_id = ? ORDER BY id ASC
                        """,
                        (run_id,),
                    )
            elif self.session_id and run_id is not None:
                cur = conn.execute(
                    """
                    SELECT event_id, session_id, ts, run_id, actor, kind, tool_name,
                           tool_call_id, parent_event_id, content, harness_id
                    FROM event_log WHERE session_id = ? AND run_id = ? ORDER BY id ASC
                    """,
                    (self.session_id, run_id),
                )
            elif self.session_id:
                cur = conn.execute(
                    """
                    SELECT event_id, session_id, ts, run_id, actor, kind, tool_name,
                           tool_call_id, parent_event_id, content, harness_id
                    FROM event_log WHERE session_id = ? ORDER BY id ASC
                    """,
                    (self.session_id,),
                )
            elif run_id is not None:
                cur = conn.execute(
                    """
                    SELECT event_id, session_id, ts, run_id, actor, kind, tool_name,
                           tool_call_id, parent_event_id, content, harness_id
                    FROM event_log WHERE run_id = ? ORDER BY id ASC
                    """,
                    (run_id,),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT event_id, session_id, ts, run_id, actor, kind, tool_name,
                           tool_call_id, parent_event_id, content, harness_id
                    FROM event_log ORDER BY id ASC
                    """
                )
            rows = []
            for row in cur.fetchall():
                rows.append(
                    {
                        "event_id": row[0],
                        "session_id": row[1],
                        "ts": row[2],
                        "run_id": row[3],
                        "actor": row[4],
                        "kind": row[5],
                        "tool_name": row[6],
                        "tool_call_id": row[7],
                        "parent_event_id": row[8],
                        "content": json.loads(row[9]),
                        "harness_id": row[10],
                    }
                )
            return tuple(rows)
        except Exception as exc:
            logger.warning("Authoritative event_log read failed for %s: %s", self.path, exc)
            raise RuntimeError(f"event_log_read_failed: {exc}") from exc
        finally:
            conn.close()

    def write_blackboard_row(self, row: Mapping[str, Any]) -> None:
        row_session_id = str(row.get("session_id", self.session_id))
        if self.session_id and row_session_id != self.session_id:
            raise SessionDatabaseError(
                "session_db_identity_mismatch",
                f"Blackboard row session {row_session_id!r} does not match {self.session_id!r}",
            )
        with self._write_lock:
            conn = self._connect()
            try:
                with conn:
                    if self._legacy_schema:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO blackboard (
                                id, run_id, type, content_hash, toolchain_digest, schema_version,
                                parent_id, read_set, write_set, assumptions,
                                version_dependencies, timestamp, payload
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(row["id"]),
                                str(row["run_id"]),
                                str(row["type"]),
                                str(row["content_hash"]),
                                str(row["toolchain_digest"]),
                                str(row["schema_version"]),
                                row.get("parent_id"),
                                json.dumps(row.get("read_set", []), ensure_ascii=False),
                                json.dumps(row.get("write_set", []), ensure_ascii=False),
                                json.dumps(row.get("assumptions", []), ensure_ascii=False),
                                json.dumps(row.get("version_dependencies", {}), ensure_ascii=False),
                                str(row["timestamp"]),
                                json.dumps(row.get("payload"), ensure_ascii=False),
                            ),
                        )
                    else:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO blackboard (
                                id, session_id, run_id, type, content_hash, toolchain_digest, schema_version,
                                parent_id, read_set, write_set, assumptions,
                                version_dependencies, timestamp, payload
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(row["id"]),
                                row_session_id,
                                str(row["run_id"]),
                                str(row["type"]),
                                str(row["content_hash"]),
                                str(row["toolchain_digest"]),
                                str(row["schema_version"]),
                                row.get("parent_id"),
                                json.dumps(row.get("read_set", []), ensure_ascii=False),
                                json.dumps(row.get("write_set", []), ensure_ascii=False),
                                json.dumps(row.get("assumptions", []), ensure_ascii=False),
                                json.dumps(row.get("version_dependencies", {}), ensure_ascii=False),
                                str(row["timestamp"]),
                                json.dumps(row.get("payload"), ensure_ascii=False),
                            ),
                        )
            except SessionDatabaseError:
                raise
            except Exception as exc:
                logger.warning("Authoritative blackboard write failed for %s: %s", self.path, exc)
                raise RuntimeError(f"blackboard_write_failed: {exc}") from exc
            finally:
                conn.close()

    def _blackboard_select(
        self,
        *,
        entry_id: str | None = None,
        entry_type: str | None = None,
    ) -> list[tuple[Any, ...]]:
        conn = self._connect()
        try:
            if self._legacy_schema:
                if entry_id is not None:
                    cur = conn.execute(
                        """
                        SELECT id, '' AS session_id, run_id, type, content_hash, toolchain_digest, schema_version,
                               parent_id, read_set, write_set, assumptions,
                               version_dependencies, timestamp, payload
                        FROM blackboard WHERE id = ? ORDER BY timestamp ASC
                        """,
                        (entry_id,),
                    )
                elif entry_type is not None:
                    cur = conn.execute(
                        """
                        SELECT id, '' AS session_id, run_id, type, content_hash, toolchain_digest, schema_version,
                               parent_id, read_set, write_set, assumptions,
                               version_dependencies, timestamp, payload
                        FROM blackboard WHERE type = ? ORDER BY timestamp ASC
                        """,
                        (entry_type,),
                    )
                else:
                    cur = conn.execute(
                        """
                        SELECT id, '' AS session_id, run_id, type, content_hash, toolchain_digest, schema_version,
                               parent_id, read_set, write_set, assumptions,
                               version_dependencies, timestamp, payload
                        FROM blackboard ORDER BY timestamp ASC
                        """
                    )
            elif self.session_id and entry_id is not None:
                cur = conn.execute(
                    """
                    SELECT id, session_id, run_id, type, content_hash, toolchain_digest, schema_version,
                           parent_id, read_set, write_set, assumptions,
                           version_dependencies, timestamp, payload
                    FROM blackboard WHERE session_id = ? AND id = ? ORDER BY timestamp ASC
                    """,
                    (self.session_id, entry_id),
                )
            elif self.session_id and entry_type is not None:
                cur = conn.execute(
                    """
                    SELECT id, session_id, run_id, type, content_hash, toolchain_digest, schema_version,
                           parent_id, read_set, write_set, assumptions,
                           version_dependencies, timestamp, payload
                    FROM blackboard WHERE session_id = ? AND type = ? ORDER BY timestamp ASC
                    """,
                    (self.session_id, entry_type),
                )
            elif self.session_id:
                cur = conn.execute(
                    """
                    SELECT id, session_id, run_id, type, content_hash, toolchain_digest, schema_version,
                           parent_id, read_set, write_set, assumptions,
                           version_dependencies, timestamp, payload
                    FROM blackboard WHERE session_id = ? ORDER BY timestamp ASC
                    """,
                    (self.session_id,),
                )
            elif entry_id is not None:
                cur = conn.execute(
                    """
                    SELECT id, session_id, run_id, type, content_hash, toolchain_digest, schema_version,
                           parent_id, read_set, write_set, assumptions,
                           version_dependencies, timestamp, payload
                    FROM blackboard WHERE id = ? ORDER BY timestamp ASC
                    """,
                    (entry_id,),
                )
            elif entry_type is not None:
                cur = conn.execute(
                    """
                    SELECT id, session_id, run_id, type, content_hash, toolchain_digest, schema_version,
                           parent_id, read_set, write_set, assumptions,
                           version_dependencies, timestamp, payload
                    FROM blackboard WHERE type = ? ORDER BY timestamp ASC
                    """,
                    (entry_type,),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT id, session_id, run_id, type, content_hash, toolchain_digest, schema_version,
                           parent_id, read_set, write_set, assumptions,
                           version_dependencies, timestamp, payload
                    FROM blackboard ORDER BY timestamp ASC
                    """
                )
            return list(cur.fetchall())
        finally:
            conn.close()

    @staticmethod
    def _blackboard_row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "session_id": row[1],
            "run_id": row[2],
            "type": row[3],
            "content_hash": row[4],
            "toolchain_digest": row[5],
            "schema_version": row[6],
            "parent_id": row[7],
            "read_set": json.loads(row[8]),
            "write_set": json.loads(row[9]),
            "assumptions": json.loads(row[10]),
            "version_dependencies": json.loads(row[11]),
            "timestamp": row[12],
            "payload": json.loads(row[13]),
        }

    def read_blackboard_row(self, entry_id: str) -> dict[str, Any] | None:
        try:
            rows = self._blackboard_select(entry_id=entry_id)
            return self._blackboard_row(rows[0]) if rows else None
        except Exception as exc:
            logger.warning("Authoritative blackboard read failed for %s: %s", self.path, exc)
            raise RuntimeError(f"blackboard_read_failed: {exc}") from exc

    def query_blackboard_rows(
        self,
        entry_type: str | None = None,
        key: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            rows = [self._blackboard_row(row) for row in self._blackboard_select(entry_type=entry_type)]
            return [row for row in rows if payload_matches_key(row["payload"], key)]
        except Exception as exc:
            logger.warning("Authoritative blackboard query failed for %s: %s", self.path, exc)
            raise RuntimeError(f"blackboard_query_failed: {exc}") from exc

    def set_meta(self, key: str, value: Any, updated_at: str) -> None:
        with self._write_lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO session_meta (key, value, updated_at) VALUES (?, ?, ?)",
                        (key, json.dumps(value, ensure_ascii=False), updated_at),
                    )
            except Exception as exc:
                logger.warning("Authoritative session_meta write failed for %s: %s", self.path, exc)
                raise RuntimeError(f"session_meta_write_failed: {exc}") from exc
            finally:
                conn.close()

    def get_meta(self, key: str) -> Any | None:
        conn = self._connect()
        try:
            return self._get_meta_from_connection(conn, key)
        except Exception as exc:
            logger.warning("Authoritative session_meta read failed for %s: %s", self.path, exc)
            raise RuntimeError(f"session_meta_read_failed: {exc}") from exc
        finally:
            conn.close()

    def reserve_run_binding(self, run_id: str, created_at: str) -> None:
        """Atomically claim ``run_id`` for this session; never replace a claim."""
        if not self.session_id:
            raise SessionDatabaseError(
                "session_id_required",
                "run binding reservation requires a session-bound database",
            )
        key = f"{_RUN_BINDING_PREFIX}{run_id}"
        value = {"run_id": run_id, "session_id": self.session_id, "created_at": created_at}
        with self._write_lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        "INSERT INTO session_meta (key, value, updated_at) VALUES (?, ?, ?)",
                        (key, json.dumps(value, ensure_ascii=False), created_at),
                    )
            except sqlite3.IntegrityError as exc:
                raise SessionDatabaseError("run_id_reused", f"run_id already bound: {run_id}") from exc
            except Exception as exc:
                raise SessionDatabaseError("run_binding_failed", str(exc)) from exc
            finally:
                conn.close()

    def get_run_binding(self, run_id: str) -> dict[str, Any] | None:
        value = self.get_meta(f"{_RUN_BINDING_PREFIX}{run_id}")
        return value if isinstance(value, dict) else None

    def list_run_ids(self) -> tuple[str, ...]:
        """Return admitted run IDs for this session in deterministic order."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT key FROM session_meta WHERE key LIKE ? ORDER BY key ASC",
                (f"{_RUN_BINDING_PREFIX}%",),
            ).fetchall()
            return tuple(str(row[0])[len(_RUN_BINDING_PREFIX) :] for row in rows)
        except Exception as exc:
            raise RuntimeError(f"run_binding_list_failed: {exc}") from exc
        finally:
            conn.close()


__all__ = ["CURRENT_SCHEMA_VERSION", "SessionDatabase", "SessionDatabaseError"]
