"""Shared SQLite connection utilities for inner_loop modules.

Both SessionDatabase (per-run authority) and GlobalHistoryStore (derived
analytics projection) share the same connection discipline: short-lived
connections with fixed timeout + busy_timeout PRAGMA + WAL journal mode.

Extracting the connection factory removes duplicate-code (R0801) between
the two stores without forcing them into an inheritance hierarchy they
don't need — their schemas differ intentionally (event_log/blackboard/session_meta
vs runs), so each keeps its own ``_init_schema``.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

# Shared tuning constants. Both stores use the same values because they
# run in the same process and contend on the same kind of short-lived
# write locks; diverging these would be a deliberate change, not drift.
SQLITE_TIMEOUT_SECONDS: float = 15.0
SQLITE_BUSY_TIMEOUT_MS: int = 15_000


def create_sqlite_connection(
    db_path: Path,
    *,
    timeout_seconds: float = SQLITE_TIMEOUT_SECONDS,
    busy_timeout_ms: int = SQLITE_BUSY_TIMEOUT_MS,
) -> sqlite3.Connection:
    """Open a SQLite connection with the project-standard PRAGMAs applied.

    The caller owns the connection lifecycle (close in a ``finally``).
    WAL/synchronous PRAGMAs are set per-connection by ``_init_schema``
    (they persist for the life of the connection once set, but setting
    them at connect time is the caller's choice — not this helper, to
    keep the helper single-responsibility).

    Args:
        db_path: Path to the SQLite file (parent must exist).
        timeout_seconds: sqlite3.connect timeout (waiting for locks).
        busy_timeout_ms: PRAGMA busy_timeout in milliseconds.

    Returns:
        An open :class:`sqlite3.Connection` with busy_timeout applied.
    """
    conn = sqlite3.connect(str(db_path), timeout=timeout_seconds)
    conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms};")
    return conn


def payload_matches_key(payload: Any, key: str | None) -> bool:
    """Return True when ``key`` appears anywhere in a JSON-serialisable payload.

    Shared by :mod:`fa.inner_loop.session_db` and :mod:`fa.blackboard.blackboard`,
    which both filter stored rows by a caller-supplied substring key. The two
    call sites had byte-identical copies of this predicate, which pylint
    correctly flagged as R0801 duplicate-code. Extracting it here keeps one
    definition of "does this row match the query key" so the two stores cannot
    drift apart silently.

    ``key=None`` means "no filter" and matches everything.
    """
    if key is None:
        return True
    if isinstance(payload, dict):
        if key in payload or key in str(payload):
            return True
        if key in json.dumps(payload):
            return True
    elif key in json.dumps(payload):
        return True
    return False


__all__ = [
    "SQLITE_BUSY_TIMEOUT_MS",
    "SQLITE_TIMEOUT_SECONDS",
    "create_sqlite_connection",
    "payload_matches_key",
]
