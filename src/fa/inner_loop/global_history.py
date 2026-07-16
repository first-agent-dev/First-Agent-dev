"""Global history derived projection — Slice 9.

Per-run authority DB is ~/.fa/session-log/<run_id>/session.db (SessionDatabase).
Global history is derived analytics projection at ~/.fa/global_history.db,
not hot-path authority. Export happens at session end (cli._cmd_run), best-effort.

Schema covers:
- run_id PK (idempotence via INSERT OR REPLACE)
- timestamps, role/model/family, outcome, turns, token totals, tool breakdown,
  compaction presence, workspace, duration.

Concurrency: WAL + busy_timeout + short-lived connections + threading.Lock.
Failure: best-effort, logs warning, returns False, never crashes main session.
Projection-only: no hot-path module should import this file for correctness.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_GLOBAL_HISTORY_PATH = Path.home() / ".fa" / "global_history.db"

_SQLITE_TIMEOUT_SECONDS = 15.0
_SQLITE_BUSY_TIMEOUT_MS = 15_000


def _now_iso_z() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class GlobalRunRow:
    """Typed view of runs table row — for tests and stats."""

    run_id: str
    created_at: str
    updated_at: str
    role: str
    model: str
    family: str
    exit_code: int
    stop_reason: str
    turns: int
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    cache_hit_ratio: float
    tool_calls_total: int
    tool_calls_breakdown_json: str
    has_compaction_summary: int
    workspace_root: str
    duration_ms: int


class GlobalHistoryStore:
    """Derived projection store for cross-run analytics.

    Thread-safe for concurrent exports (same process) via Lock + WAL.
    Uses short-lived connections per operation, same discipline as SessionDatabase.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.path = Path(db_path) if db_path is not None else DEFAULT_GLOBAL_HISTORY_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=_SQLITE_TIMEOUT_SECONDS)
        conn.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS};")
        return conn

    def _init_schema(self) -> None:
        try:
            with self._write_lock:
                conn = self._connect()
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                with conn:
                    conn.execute(
                        """
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
                        """
                    )
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_role ON runs(role);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_updated_at ON runs(updated_at);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model);")
                conn.close()
        except Exception as exc:
            logger.warning("Failed to initialize global_history DB %s: %s", self.path, exc)
            raise RuntimeError(f"global_history_init_failed: {exc}") from exc

    def export_run(self, row: Mapping[str, Any]) -> None:
        """Idempotent upsert via INSERT OR REPLACE on run_id PK."""
        with self._write_lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO runs (
                            run_id, created_at, updated_at, role, model, family,
                            exit_code, stop_reason, turns,
                            input_tokens, output_tokens,
                            cache_read_input_tokens, cache_creation_input_tokens,
                            cache_hit_ratio,
                            tool_calls_total, tool_calls_breakdown_json,
                            has_compaction_summary, workspace_root, duration_ms
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row["run_id"]),
                            str(row.get("created_at", _now_iso_z())),
                            str(row.get("updated_at", _now_iso_z())),
                            str(row.get("role", "")),
                            str(row.get("model", "")),
                            str(row.get("family", "")),
                            int(row.get("exit_code", 0)),
                            str(row.get("stop_reason", "")),
                            int(row.get("turns", 0)),
                            int(row.get("input_tokens", 0)),
                            int(row.get("output_tokens", 0)),
                            int(row.get("cache_read_input_tokens", 0)),
                            int(row.get("cache_creation_input_tokens", 0)),
                            float(row.get("cache_hit_ratio", 0.0)),
                            int(row.get("tool_calls_total", 0)),
                            str(row.get("tool_calls_breakdown_json", "{}")),
                            int(row.get("has_compaction_summary", 0)),
                            str(row.get("workspace_root", "")),
                            int(row.get("duration_ms", 0)),
                        ),
                    )
            except Exception as exc:
                logger.warning("global_history export failed for %s: %s", row.get("run_id"), exc)
                raise RuntimeError(f"global_history_export_failed: {exc}") from exc
            finally:
                conn.close()

    def read_run(self, run_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cur.fetchone()
            if row is None:
                return None
            col_names = [d[0] for d in cur.description]
            return dict(zip(col_names, row))
        finally:
            conn.close()

    def read_all(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT * FROM runs ORDER BY updated_at DESC")
            col_names = [d[0] for d in cur.description]
            return [dict(zip(col_names, r)) for r in cur.fetchall()]
        finally:
            conn.close()

    def count_runs(self) -> int:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT COUNT(*) FROM runs")
            return int(cur.fetchone()[0])
        finally:
            conn.close()


def _extract_telemetry_from_log(log: Any) -> dict[str, Any]:
    """Extract token totals and tool breakdown from EventLog authoritative rows."""
    total_in = 0
    total_out = 0
    total_cache_read = 0
    total_cache_creation = 0
    tool_counter: Counter[str] = Counter()
    has_compaction = 0
    created_at = ""

    try:
        events = log.read_all() if log is not None else ()
        if events:
            # created_at from first event ts
            try:
                created_at = str(events[0].ts)
            except Exception:
                created_at = _now_iso_z()
            for ev in events:
                if ev.kind == "usage":
                    c = ev.content if isinstance(ev.content, Mapping) else {}
                    total_in += int(c.get("input_tokens", 0))
                    total_out += int(c.get("output_tokens", 0))
                    total_cache_read += int(c.get("cache_read_input_tokens", 0))
                    total_cache_creation += int(c.get("cache_creation_input_tokens", 0))
                elif ev.kind == "tool_call":
                    tool_counter[ev.tool_name or "unknown"] += 1
                elif ev.kind == "compaction_stage3_done":
                    has_compaction = 1
    except Exception as exc:
        logger.warning("Failed to extract telemetry from log for global export: %s", exc)

    cache_hit_ratio = (total_cache_read / max(total_in, 1)) if total_in > 0 else 0.0

    return {
        "input_tokens": total_in,
        "output_tokens": total_out,
        "cache_read_input_tokens": total_cache_read,
        "cache_creation_input_tokens": total_cache_creation,
        "cache_hit_ratio": cache_hit_ratio,
        "tool_calls_total": sum(tool_counter.values()),
        "tool_calls_breakdown_json": json.dumps(dict(tool_counter), ensure_ascii=False),
        "has_compaction_summary": has_compaction,
        "created_at": created_at or _now_iso_z(),
    }


def build_export_row(
    *,
    run_id: str,
    outcome: Any,
    log: Any | None = None,
    role: str = "",
    model: str = "",
    family: str = "",
    workspace_root: Path | str = "",
    duration_ms: int = 0,
) -> dict[str, Any]:
    """Build row dict from SessionOutcome + EventLog + args.

    outcome expected to have exit_code, stop_reason, turns, final_text etc.
    """
    telemetry = _extract_telemetry_from_log(log)

    # outcome may be SessionOutcome or mock
    try:
        exit_code = int(getattr(outcome, "exit_code", 0))
    except Exception:
        exit_code = 0
    try:
        stop_reason = str(getattr(outcome, "stop_reason", ""))
    except Exception:
        stop_reason = ""
    try:
        turns = int(getattr(outcome, "turns", 0))
    except Exception:
        turns = 0

    now = _now_iso_z()

    row = {
        "run_id": run_id,
        "created_at": telemetry.get("created_at", now),
        "updated_at": now,
        "role": role,
        "model": model,
        "family": family,
        "exit_code": exit_code,
        "stop_reason": stop_reason,
        "turns": turns,
        "input_tokens": telemetry.get("input_tokens", 0),
        "output_tokens": telemetry.get("output_tokens", 0),
        "cache_read_input_tokens": telemetry.get("cache_read_input_tokens", 0),
        "cache_creation_input_tokens": telemetry.get("cache_creation_input_tokens", 0),
        "cache_hit_ratio": telemetry.get("cache_hit_ratio", 0.0),
        "tool_calls_total": telemetry.get("tool_calls_total", 0),
        "tool_calls_breakdown_json": telemetry.get("tool_calls_breakdown_json", "{}"),
        "has_compaction_summary": telemetry.get("has_compaction_summary", 0),
        "workspace_root": str(workspace_root),
        "duration_ms": int(duration_ms),
    }
    return row


def export_session_to_global_history(
    *,
    run_id: str,
    outcome: Any,
    log: Any | None = None,
    role: str = "",
    model: str = "",
    family: str = "",
    workspace_root: Path | str = "",
    duration_ms: int = 0,
    db_path: Path | None = None,
) -> bool:
    """Best-effort export of one session to global_history.db.

    Returns True on success, False on failure (never raises to caller).
    """
    try:
        row = build_export_row(
            run_id=run_id,
            outcome=outcome,
            log=log,
            role=role,
            model=model,
            family=family,
            workspace_root=workspace_root,
            duration_ms=duration_ms,
        )
        store = GlobalHistoryStore(db_path=db_path)
        store.export_run(row)
        return True
    except Exception as exc:
        logger.warning("global_history export failed for %s: %s", run_id, exc)
        return False


__all__ = [
    "DEFAULT_GLOBAL_HISTORY_PATH",
    "GlobalHistoryStore",
    "GlobalRunRow",
    "build_export_row",
    "export_session_to_global_history",
]
