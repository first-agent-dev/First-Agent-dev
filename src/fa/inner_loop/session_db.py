"""Per-run authoritative SQLite substrate for hot-path session state.

Slice 1 scope only:
- unify authoritative event-log + blackboard state in one per-run DB
- remove split-brain between JSONL mirrors and SQLite authority
- keep public facades (`EventLog`, `Blackboard`) stable where possible

Non-goals for this module:
- cross-run/global export
- observability query-plane redesign
- compaction/business-logic changes
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop._sqlite_common import create_sqlite_connection

logger = logging.getLogger(__name__)


class SessionDatabase:
    """Authoritative per-run SQLite database.

    Uses short-lived connections per operation to minimize migration risk versus
    the current codebase, while centralizing schema and write discipline.
    """

    def __init__(self, db_path: Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return create_sqlite_connection(self.path)

    def _init_schema(self) -> None:
        # pylint: disable=duplicate-code
        # Rationale: the outer with-lock/connect/PRAGMA boilerplate mirrors
        # the analytics-projection store's own _init_schema (see
        # fa.inner_loop._sqlite_common's module docstring for which two
        # stores share this discipline) because both stores share the same
        # short-lived-connection + WAL + threading.Lock discipline. The
        # table schemas inside the `with conn:` block are ENTIRELY
        # different (event_log/blackboard/session_meta vs the projection
        # store's own table) and are correctly NOT shared. A base class
        # would force both stores through one `_init_schema` contract to
        # save ~10 lines of identical glue, at the cost of coupling two
        # stores with different lifecycles (per-run hot-path authority vs
        # cross-run derived projection) and different failure-wrapping
        # messages — over-engineering for a 2-consumer pair. The
        # connection-opening step itself (not this boilerplate) is already
        # factored out into `fa.inner_loop._sqlite_common`. Similarity
        # here is structural boilerplate, not copy-paste logic.
        try:
            with self._write_lock:
                conn = self._connect()
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS event_log (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            event_id TEXT NOT NULL,
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
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_log_run_id_id ON event_log(run_id, id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_log_tool_call_id ON event_log(tool_call_id);")
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS blackboard (
                            id TEXT PRIMARY KEY,
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
                        "CREATE INDEX IF NOT EXISTS idx_blackboard_run_type_ts ON blackboard(run_id, type, timestamp);"
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
                conn.close()
        except Exception as exc:
            logger.warning("Failed to initialize authoritative SessionDatabase %s: %s", self.path, exc)
            raise RuntimeError(f"session_db_init_failed: {exc}") from exc

    def append_event_row(self, row: Mapping[str, Any]) -> None:
        with self._write_lock:
            conn = self._connect()
            try:
                with conn:
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
            except Exception as exc:
                logger.warning("Authoritative event_log write failed for %s: %s", self.path, exc)
                raise RuntimeError(f"event_log_write_failed: {exc}") from exc
            finally:
                conn.close()

    def read_event_rows(self) -> tuple[dict[str, Any], ...]:
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                SELECT event_id, ts, run_id, actor, kind, tool_name,
                       tool_call_id, parent_event_id, content, harness_id
                FROM event_log ORDER BY id ASC
                """
            )
            rows = []
            for row in cur.fetchall():
                rows.append(
                    {
                        "event_id": row[0],
                        "ts": row[1],
                        "run_id": row[2],
                        "actor": row[3],
                        "kind": row[4],
                        "tool_name": row[5],
                        "tool_call_id": row[6],
                        "parent_event_id": row[7],
                        "content": json.loads(row[8]),
                        "harness_id": row[9],
                    }
                )
            return tuple(rows)
        except Exception as exc:
            logger.warning("Authoritative event_log read failed for %s: %s", self.path, exc)
            raise RuntimeError(f"event_log_read_failed: {exc}") from exc
        finally:
            conn.close()

    def write_blackboard_row(self, row: Mapping[str, Any]) -> None:
        with self._write_lock:
            conn = self._connect()
            try:
                with conn:
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
            except Exception as exc:
                logger.warning("Authoritative blackboard write failed for %s: %s", self.path, exc)
                raise RuntimeError(f"blackboard_write_failed: {exc}") from exc
            finally:
                conn.close()

    def read_blackboard_row(self, entry_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                SELECT id, run_id, type, content_hash, toolchain_digest, schema_version,
                       parent_id, read_set, write_set, assumptions,
                       version_dependencies, timestamp, payload
                FROM blackboard WHERE id = ?
                """,
                (entry_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "id": row[0],
                "run_id": row[1],
                "type": row[2],
                "content_hash": row[3],
                "toolchain_digest": row[4],
                "schema_version": row[5],
                "parent_id": row[6],
                "read_set": json.loads(row[7]),
                "write_set": json.loads(row[8]),
                "assumptions": json.loads(row[9]),
                "version_dependencies": json.loads(row[10]),
                "timestamp": row[11],
                "payload": json.loads(row[12]),
            }
        except Exception as exc:
            logger.warning("Authoritative blackboard read failed for %s: %s", self.path, exc)
            raise RuntimeError(f"blackboard_read_failed: {exc}") from exc
        finally:
            conn.close()

    def query_blackboard_rows(
        self,
        entry_type: str | None = None,
        key: str | None = None,
    ) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            if entry_type is not None:
                cur = conn.execute(
                    """
                    SELECT id, run_id, type, content_hash, toolchain_digest, schema_version,
                           parent_id, read_set, write_set, assumptions,
                           version_dependencies, timestamp, payload
                    FROM blackboard WHERE type = ? ORDER BY timestamp ASC
                    """,
                    (entry_type,),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT id, run_id, type, content_hash, toolchain_digest, schema_version,
                           parent_id, read_set, write_set, assumptions,
                           version_dependencies, timestamp, payload
                    FROM blackboard ORDER BY timestamp ASC
                    """
                )
            rows: list[dict[str, Any]] = []
            for row in cur.fetchall():
                payload = json.loads(row[12])
                if not _payload_matches_key(payload, key):
                    continue
                rows.append(
                    {
                        "id": row[0],
                        "run_id": row[1],
                        "type": row[2],
                        "content_hash": row[3],
                        "toolchain_digest": row[4],
                        "schema_version": row[5],
                        "parent_id": row[6],
                        "read_set": json.loads(row[7]),
                        "write_set": json.loads(row[8]),
                        "assumptions": json.loads(row[9]),
                        "version_dependencies": json.loads(row[10]),
                        "timestamp": row[11],
                        "payload": payload,
                    }
                )
            return rows
        except Exception as exc:
            logger.warning("Authoritative blackboard query failed for %s: %s", self.path, exc)
            raise RuntimeError(f"blackboard_query_failed: {exc}") from exc
        finally:
            conn.close()

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
            cur = conn.execute("SELECT value FROM session_meta WHERE key = ?", (key,))
            row = cur.fetchone()
            if row is None:
                return None
            return json.loads(row[0])
        except Exception as exc:
            logger.warning("Authoritative session_meta read failed for %s: %s", self.path, exc)
            raise RuntimeError(f"session_meta_read_failed: {exc}") from exc
        finally:
            conn.close()


def _payload_matches_key(payload: Any, key: str | None) -> bool:
    if key is None:
        return True
    if isinstance(payload, dict):
        if key in payload or key in str(payload):
            return True
        if key in json.dumps(payload):
            return True
    else:
        if key in json.dumps(payload):
            return True
    return False


__all__ = ["SessionDatabase"]
