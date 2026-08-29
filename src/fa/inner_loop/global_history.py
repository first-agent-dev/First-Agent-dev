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
from collections import Counter
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from fa.inner_loop._sqlite_common import create_sqlite_connection
from fa.inner_loop.acrr import compute_acrr, compute_cost, compute_cost_floor, compute_read_amplification
from fa.paths import fa_state_root

logger = logging.getLogger(__name__)

DEFAULT_GLOBAL_HISTORY_PATH = Path.home() / ".fa" / "global_history.db"


# Single source of truth for the ``runs`` table: BOTH the fresh-create DDL and
# the add-missing migration below iterate this tuple, so they cannot drift.
# Found live (2026-08-29, host trial): ``scope_estimate_json`` (S3.5) was in
# CREATE but absent from the hand-written migration list, so every export
# against a pre-S3.5 DB failed with "table runs has no column named
# scope_estimate_json" — silently, per run. Tests never caught it because
# tests always create fresh DBs.
_RUNS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("run_id", "TEXT PRIMARY KEY"),
    ("created_at", "TEXT NOT NULL"),
    ("updated_at", "TEXT NOT NULL"),
    ("role", "TEXT NOT NULL"),
    ("model", "TEXT NOT NULL DEFAULT ''"),
    ("family", "TEXT NOT NULL DEFAULT ''"),
    ("exit_code", "INTEGER NOT NULL"),
    ("stop_reason", "TEXT NOT NULL"),
    ("turns", "INTEGER NOT NULL"),
    ("input_tokens", "INTEGER NOT NULL DEFAULT 0"),
    ("output_tokens", "INTEGER NOT NULL DEFAULT 0"),
    ("cache_read_input_tokens", "INTEGER NOT NULL DEFAULT 0"),
    ("cache_creation_input_tokens", "INTEGER NOT NULL DEFAULT 0"),
    ("cache_hit_ratio", "REAL NOT NULL DEFAULT 0.0"),
    ("tool_calls_total", "INTEGER NOT NULL DEFAULT 0"),
    ("tool_calls_breakdown_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("has_compaction_summary", "INTEGER NOT NULL DEFAULT 0"),
    ("workspace_root", "TEXT NOT NULL DEFAULT ''"),
    ("duration_ms", "INTEGER NOT NULL DEFAULT 0"),
    ("scope_estimate_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("files_read", "INTEGER NOT NULL DEFAULT 0"),
    ("files_changed", "INTEGER NOT NULL DEFAULT 0"),
    ("read_amplification", "REAL"),  # S8: renamed from acrr_proxy; NULL = no denominator
    ("cost_actual", "REAL"),  # S8; NULL = not computed
    ("cost_floor", "REAL"),  # S8
    ("acrr", "REAL"),  # S8
)


def default_global_history_path() -> Path:
    """Resolve the projection DB path at CALL time, not import time (S8.8).

    ``DEFAULT_GLOBAL_HISTORY_PATH`` above is bound when this module is first
    imported, so it captures whatever ``HOME`` happened to be at that instant
    and ignores ``FA_STATE_ROOT`` entirely. Two concrete consequences, both
    measured rather than hypothesised:

    * **Split brain.** The reader already resolves at call time —
      ``fa stats --global-history`` builds ``fa_state_root() / "global_history.db"``
      (``cli.py``). With ``FA_STATE_ROOT=/srv/fa`` the reader looks in
      ``/srv/fa/global_history.db`` while this writer keeps appending to
      ``~/.fa/global_history.db``. The operator sees an empty history and the
      rows are silently accumulating somewhere else.
    * **Test isolation.** A test that repoints ``HOME`` after import — which is
      what ``monkeypatch.setenv`` does — is ignored, so exports leak into the
      real user's ``~/.fa``.

    This is the same defect class as V10 in :mod:`fa.inner_loop.state`, whose
    ``default_state_root`` docstring records how an import-time constant made
    ten tests share one directory. That fix was never swept across the other
    path constants; this is the second instance.

    Production behaviour is unchanged: ``HOME`` is stable in a real process, so
    the resolved value is byte-identical to the old constant unless the
    operator deliberately sets ``FA_STATE_ROOT`` — in which case honouring it
    is the entire point of that variable
    (:func:`fa.paths.fa_state_root` promises resolution "on every call ... so a
    caller that reconfigures its environment is honoured rather than silently
    ignored").

    The module-level constant is retained as a deprecated alias so any external
    importer keeps working; nothing in this repository reads it any more.
    """
    return fa_state_root() / "global_history.db"


def _now_iso_z() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# S5: which tool names count as reading vs changing a file, for the ACRR proxy.
# Kept beside the row they feed. Verified against the live registry: these are
# exactly the filesystem tools that carry a "path" param.
_READ_TOOLS: Final = frozenset({"fs_read_file"})
_CHANGE_TOOLS: Final = frozenset({"fs_write_file", "fs_edit_file"})


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
    scope_estimate_json: str = "{}"  # S3.5: scope estimate projection
    files_read: int = 0  # S5: distinct paths read
    files_changed: int = 0  # S5: distinct paths written/edited
    read_amplification: float | None = None  # S8: renamed from acrr_proxy, see acrr.py
    cost_actual: float | None = None  # S8: E3 Eq. 1 measured cost
    cost_floor: float | None = None  # S8: E3 C_min for this run's change-set
    acrr: float | None = None  # S8: E3 Eq. 3; None when there is no floor


class GlobalHistoryStore:
    """Derived projection store for cross-run analytics.

    Thread-safe for concurrent exports (same process) via Lock + WAL.
    Uses short-lived connections per operation, same discipline as SessionDatabase.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        # S8.8: call-time resolution. An explicit ``db_path`` still wins, so
        # every existing caller that injects a path is unaffected.
        self.path = Path(db_path) if db_path is not None else default_global_history_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return create_sqlite_connection(self.path)

    def _init_schema(self) -> None:
        try:
            with self._write_lock:
                # ``closing()`` guarantees the connection is closed even if
                # an exception is raised between _connect() and the explicit
                # close() that used to live below the ``with conn:`` block.
                # Without this, a failure between PRAGMA/table-creation and
                # conn.close() leaked a sqlite3.Connection and produced
                # ResourceWarning in tests.
                with closing(self._connect()) as conn:
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA synchronous=NORMAL;")
                    with conn:
                        conn.execute(
                            """
                            CREATE TABLE IF NOT EXISTS runs (
                                """
                            + ",\n".join(f"{name} {decl}" for name, decl in _RUNS_COLUMNS)
                            + """
                            );
                            """
                        )
                        # S5 MIGRATION. CREATE TABLE IF NOT EXISTS is a no-op
                        # on an existing DB, so a pre-S5 file would keep the old
                        # column set and every insert would fail with "table
                        # runs has no column named files_read" (reproduced
                        # before writing this). Add whatever is missing.
                        # Additive and idempotent: safe on every open.
                        #
                        # read_amplification is deliberately NULLable with no
                        # DEFAULT — NULL is the storage form of "no
                        # denominator", the same distinction
                        # compute_read_amplification makes by returning None. A
                        # DEFAULT 0.0 would silently claim every legacy run had
                        # a perfect ratio.
                        existing_cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(runs);").fetchall()}

                        # S8 RENAME acrr_proxy -> read_amplification. A real
                        # RENAME COLUMN (sqlite >= 3.25), not an additive
                        # shadow column: it carries the S5 values across in
                        # place, leaves exactly one name behind, and needs no
                        # backfill that could disagree with the source.
                        #
                        # This MUST run before the add-missing loop below.
                        # Reversed, that loop would create an empty
                        # read_amplification, the `not in existing_cols` guard
                        # here would then be false, and every S5 value would be
                        # stranded in an orphaned acrr_proxy column.
                        if "acrr_proxy" in existing_cols and "read_amplification" not in existing_cols:
                            conn.execute("ALTER TABLE runs RENAME COLUMN acrr_proxy TO read_amplification;")
                            existing_cols.discard("acrr_proxy")
                            existing_cols.add("read_amplification")
                        #
                        # S8 adds three more on the same terms. cost_actual,
                        # cost_floor and acrr are NULLable with no DEFAULT for
                        # the same reason: NULL means "not computed", and 0.0
                        # would assert every pre-S8 run was perfectly lean.
                        # Add-missing iterates the SAME tuple the CREATE uses
                        # (drift is now unrepresentable). PRIMARY KEY columns
                        # are skipped: run_id exists in every schema since v0,
                        # and ALTER TABLE cannot add a PRIMARY KEY anyway.
                        for col_name, col_decl in _RUNS_COLUMNS:
                            if "PRIMARY KEY" in col_decl:
                                continue
                            if col_name not in existing_cols:
                                conn.execute(f"ALTER TABLE runs ADD COLUMN {col_name} {col_decl};")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_role ON runs(role);")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_updated_at ON runs(updated_at);")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model);")
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
                            has_compaction_summary, workspace_root, duration_ms,
                            scope_estimate_json,
                            files_read, files_changed,
                            read_amplification, cost_actual, cost_floor, acrr
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            str(row.get("scope_estimate_json", "{}")),  # S3.5
                            int(row.get("files_read", 0)),  # S5
                            int(row.get("files_changed", 0)),  # S5
                            # S5/S8: preserve None as SQL NULL. float(None) raises,
                            # and float(0) would fabricate a ratio.
                            # NULL is a load-bearing value here — it is how the
                            # calibration view tells "no change-set" apart from
                            # "perfectly lean", which are the same number if you
                            # coerce to 0.0.
                            (None if row.get("read_amplification") is None else float(row["read_amplification"])),
                            (None if row.get("cost_actual") is None else float(row["cost_actual"])),
                            (None if row.get("cost_floor") is None else float(row["cost_floor"])),
                            (None if row.get("acrr") is None else float(row["acrr"])),
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
            return dict(zip(col_names, row, strict=True))
        finally:
            conn.close()

    def read_all(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT * FROM runs ORDER BY updated_at DESC")
            col_names = [d[0] for d in cur.description]
            return [dict(zip(col_names, r, strict=True)) for r in cur.fetchall()]
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
    """Extract token totals, tool breakdown, and turns from EventLog authoritative rows.

    NEW-4: The ``turns`` field is counted from ``usage`` events (each usage event
    = one LLM turn). This is accurate for both standalone runs and workflow
    aggregate exports, where outcome.turns may be 0. build_export_row uses
    max(outcome.turns, telemetry.turns) so the correct count wins.
    """
    total_in = 0
    total_out = 0
    total_cache_read = 0
    total_cache_creation = 0
    tool_counter: Counter[str] = Counter()
    has_compaction = 0
    created_at = ""
    turns = 0  # NEW-4: count usage events = LLM turns
    scope_estimate: dict[str, object] = {}  # S3.5: scope estimation projection
    # S5: DISTINCT paths, not call counts. Reading one file five times is one
    # file's worth of context, and counting it five times would inflate ACRR
    # into reporting over-reading that never happened.
    read_paths: set[str] = set()
    changed_paths: set[str] = set()

    try:
        events = log.read_all() if log is not None else ()
        if events:
            # created_at from first event ts
            try:
                created_at = str(events[0].ts)
            except (AttributeError, IndexError):
                created_at = _now_iso_z()
            for ev in events:
                if ev.kind == "usage":
                    c = ev.content if isinstance(ev.content, Mapping) else {}
                    total_in += int(c.get("input_tokens", 0))
                    total_out += int(c.get("output_tokens", 0))
                    total_cache_read += int(c.get("cache_read_input_tokens", 0))
                    total_cache_creation += int(c.get("cache_creation_input_tokens", 0))
                    turns += 1  # NEW-4: each usage event = 1 LLM turn
                elif ev.kind == "tool_call":
                    tool_name = ev.tool_name or "unknown"
                    tool_counter[tool_name] += 1
                    # S5: project distinct file paths for the ACRR proxy. The
                    # path lives in the recorded params (state.py:record_tool_call
                    # stores content={"params": {...}}). A tool call with no
                    # usable path contributes nothing rather than a bogus key.
                    if tool_name in _READ_TOOLS or tool_name in _CHANGE_TOOLS:
                        c = ev.content if isinstance(ev.content, Mapping) else {}
                        params = c.get("params") if isinstance(c.get("params"), Mapping) else {}
                        raw_path = params.get("path") if isinstance(params, Mapping) else None
                        if isinstance(raw_path, str) and raw_path:
                            if tool_name in _READ_TOOLS:
                                read_paths.add(raw_path)
                            else:
                                changed_paths.add(raw_path)
                elif ev.kind == "compaction_stage3_done":
                    has_compaction = 1
                # S3.5: capture scope estimate for cross-run projection
                elif ev.kind == "scope_estimate":
                    c = ev.content if isinstance(ev.content, Mapping) else {}
                    scope_estimate = {
                        "difficulty": int(c.get("difficulty", 0)),
                        "scope": str(c.get("scope", "")),
                        "risk": str(c.get("risk", "")),
                        "confidence": float(c.get("confidence", 0.0)),
                        "recommended_mode": str(c.get("recommended_mode", "")),
                    }
    except Exception as exc:  # noqa: BLE001 — derived export must not crash the hot path
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
        "turns": turns,  # NEW-4: from usage event count
        "scope_estimate_json": json.dumps(scope_estimate, ensure_ascii=False),  # S3.5
        "files_read": len(read_paths),  # S5: distinct paths
        "files_changed": len(changed_paths),  # S5: distinct paths
        # S8: the PATHS themselves, not just how many. compute_cost_floor has to
        # stat each changed file to price its token axis, and until now this
        # function threw the strings away and returned only the two lengths
        # above — the floor was uncomputable from the projection. Sorted so the
        # exported row is byte-identical across runs with the same change-set
        # (set iteration order is not stable, and an unstable row would make
        # every diff of the projection noise).
        "changed_paths": sorted(changed_paths),
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
    except (TypeError, ValueError, AttributeError):
        exit_code = 0
    try:
        stop_reason = str(getattr(outcome, "stop_reason", ""))
    except (TypeError, ValueError, AttributeError):
        stop_reason = ""
    try:
        outcome_turns = int(getattr(outcome, "turns", 0))
    except (TypeError, ValueError, AttributeError):
        outcome_turns = 0
    # NEW-4: Prefer outcome.turns when available (standalone run), fall back
    # to telemetry turns (counted from usage events) for workflow aggregates
    # where outcome.turns is 0.
    turns = max(outcome_turns, int(telemetry.get("turns", 0)))

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
        "scope_estimate_json": str(telemetry.get("scope_estimate_json", "{}")),  # S3.5
    }

    # S5: ACRR proxy. Computed once here, at export time, and stored — the
    # stats renderer reads only this projection and never reopens an event log,
    # so the ratio has to exist as a column by the time it gets there.
    files_read = int(telemetry.get("files_read", 0))
    files_changed = int(telemetry.get("files_changed", 0))
    row["files_read"] = files_read
    row["files_changed"] = files_changed
    read_amplification = compute_read_amplification(files_read, files_changed)
    row["read_amplification"] = read_amplification

    # S8 / CT11: full E3 cost model.
    #
    # ACRR is recorded for EVERY run, successful or not (operator decision
    # Q22). Filtering belongs at DISPLAY time, where the reason can be stated;
    # filtering at write time would destroy the data needed to ask "are failed
    # runs less efficient?" and could never be undone retroactively.
    changed_paths = telemetry.get("changed_paths", [])
    changed_list: list[str] = [str(p) for p in changed_paths] if isinstance(changed_paths, list) else []
    output_tokens = int(telemetry.get("output_tokens", 0))
    cost_floor = compute_cost_floor(changed_list, workspace_root or ".", output_tokens)
    cost_actual = compute_cost(
        latency_s=float(duration_ms) / 1000.0,
        tokens=int(telemetry.get("input_tokens", 0)) + output_tokens,
        tool_calls=int(telemetry.get("tool_calls_total", 0)),
        files=files_read + files_changed,
    )
    row["cost_actual"] = cost_actual
    row["cost_floor"] = cost_floor
    row["acrr"] = compute_acrr(cost_actual, cost_floor)
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
    except Exception as exc:  # noqa: BLE001 — derived export is best-effort and must not break sessions
        logger.warning("global_history export failed for %s: %s", run_id, exc)
        return False


__all__ = [
    "DEFAULT_GLOBAL_HISTORY_PATH",
    "GlobalHistoryStore",
    "GlobalRunRow",
    "build_export_row",
    "default_global_history_path",
    "export_session_to_global_history",
]
