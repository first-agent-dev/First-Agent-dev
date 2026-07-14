"""
Blackboard — Typed Blackboard with Content Hashes + Transactional Semantics
Phase 0.5 — Formal Shared Harness Substrate
Senior eng: interface segregation, DI, feature flags, graceful degradation, thread safety, observable failures
Senior refactor v3: full read/write conflict + assumption violated, query dict check,
Q2 base_commit linear frontier policy, C901 <15 via extracted helpers
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BlackboardEntry:
    id: str
    type: str
    content_hash: str
    toolchain_digest: str
    schema_version: str
    parent_id: str | None
    read_set: list[str]
    write_set: list[str]
    assumptions: list[str]
    version_dependencies: dict[str, str]
    timestamp: str
    payload: Any

    @classmethod
    def create(
        cls,
        *,
        id: str,
        type: str,
        payload: Any,
        read_set: list[str] | None = None,
        write_set: list[str] | None = None,
        assumptions: list[str] | None = None,
        version_dependencies: dict[str, str] | None = None,
        parent_id: str | None = None,
        schema_version: str = "v1",
    ) -> BlackboardEntry:
        content_str = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]
        model_id = os.environ.get("FA_MODEL_ID", "unknown")
        toolchain_digest = f"python-{sys.version_info.major}.{sys.version_info.minor}-{model_id}"
        timestamp = datetime.now(UTC).isoformat()
        return cls(
            id=id,
            type=type,
            content_hash=content_hash,
            toolchain_digest=toolchain_digest,
            schema_version=schema_version,
            parent_id=parent_id,
            read_set=read_set or [],
            write_set=write_set or [],
            assumptions=assumptions or [],
            version_dependencies=version_dependencies or {},
            timestamp=timestamp,
            payload=payload,
        )


@dataclass
class Conflict:
    entry_id: str
    conflicting_entry_id: str
    reason: str
    read_write_overlap: list[str]
    assumption_violated: str | None = None


def _should_check_conflict(new: BlackboardEntry, old: BlackboardEntry) -> bool:
    """Q2 v0.1 linear chain: parent_id happens-before, same base_commit concurrent,
    different base serialized.
    """
    if new.parent_id == old.id:
        return False
    new_base = new.version_dependencies.get("base_commit")
    old_base = old.version_dependencies.get("base_commit")
    if new_base and old_base:
        return new_base == old_base
    return True


def _ww_overlap(a: set[str], b: set[str]) -> set[str]:
    return a & b


def _rw_overlap(new_read: set[str], old_write: set[str]) -> set[str]:
    return new_read & old_write


def _wr_overlap(old_read: set[str], new_write: set[str]) -> set[str]:
    return old_read & new_write


def _assumption_violated(new: BlackboardEntry, old: BlackboardEntry) -> str | None:
    try:
        new_base = new.version_dependencies.get("base_commit")
        old_base = old.version_dependencies.get("base_commit")
        if new_base and old_base and new_base != old_base:
            for assump in new.assumptions:
                if old_base in assump or "base_commit" in assump:
                    return assump
        for assump in new.assumptions:
            if any(f in assump for f in old.write_set):
                if old.content_hash != new.content_hash:
                    return assump
    except (KeyError, AttributeError, TypeError) as exc:
        print(f"WARNING: assumption check failed: {exc}, continuing")
    return None


def _build_conflict_reason(ww: set[str], rw: set[str], wr: set[str], assump_viol: str | None) -> str:
    parts = []
    if ww:
        parts.append(f"write/write overlap {ww}")
    if rw:
        parts.append(f"read/write stale {rw}")
    if wr:
        parts.append(f"write/read invalidate {wr}")
    if assump_viol:
        parts.append(f"assumption violated '{assump_viol}'")
    return "; ".join(parts) + " — concurrent without coordination"


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


class Blackboard:
    """Append-only, content-addressed, queryable blackboard."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "blackboard.jsonl"
        self.lock = threading.Lock()
        self.path.touch(exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        import sqlite3

        db_path = self.root / "session.db"
        try:
            conn = sqlite3.connect(str(db_path), timeout=15.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS blackboard (
                        id TEXT PRIMARY KEY,
                        type TEXT,
                        content_hash TEXT,
                        toolchain_digest TEXT,
                        schema_version TEXT,
                        parent_id TEXT,
                        read_set TEXT,
                        write_set TEXT,
                        assumptions TEXT,
                        version_dependencies TEXT,
                        timestamp TEXT,
                        payload TEXT
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_bb_type ON blackboard(type);")
            conn.close()
        except Exception as exc:  # noqa: BLE001 # best-effort
            logger.warning("Failed to initialize SQLite Blackboard: %s", exc)

    def write(self, entry: BlackboardEntry) -> None:
        try:
            # 1. Write to JSONL
            line = json.dumps(asdict(entry), ensure_ascii=False)
            with self.lock:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")

            # 2. Write to SQLite3
            import sqlite3

            db_path = self.root / "session.db"
            conn = sqlite3.connect(str(db_path), timeout=15.0)
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO blackboard (
                        id, type, content_hash, toolchain_digest, schema_version, parent_id,
                        read_set, write_set, assumptions, version_dependencies, timestamp, payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.type,
                        entry.content_hash,
                        entry.toolchain_digest,
                        entry.schema_version,
                        entry.parent_id,
                        json.dumps(entry.read_set, ensure_ascii=False),
                        json.dumps(entry.write_set, ensure_ascii=False),
                        json.dumps(entry.assumptions, ensure_ascii=False),
                        json.dumps(entry.version_dependencies, ensure_ascii=False),
                        entry.timestamp,
                        json.dumps(entry.payload, ensure_ascii=False),
                    ),
                )
            conn.close()
        except Exception as e:  # noqa: BLE001 # graceful degradation
            logger.warning("Blackboard write failed: %s", e)

    def read(self, id: str) -> BlackboardEntry | None:
        import sqlite3

        db_path = self.root / "session.db"
        if not db_path.exists():
            return None
        try:
            conn = sqlite3.connect(str(db_path), timeout=15.0)
            cur = conn.execute(
                """
                SELECT id, type, content_hash, toolchain_digest, schema_version, parent_id,
                       read_set, write_set, assumptions, version_dependencies, timestamp, payload
                FROM blackboard WHERE id = ?
                """,
                (id,),
            )
            row = cur.fetchone()
            conn.close()
            if row is not None:
                return BlackboardEntry(
                    id=row[0],
                    type=row[1],
                    content_hash=row[2],
                    toolchain_digest=row[3],
                    schema_version=row[4],
                    parent_id=row[5],
                    read_set=json.loads(row[6]),
                    write_set=json.loads(row[7]),
                    assumptions=json.loads(row[8]),
                    version_dependencies=json.loads(row[9]),
                    timestamp=row[10],
                    payload=json.loads(row[11]),
                )
        except Exception as exc:  # noqa: BLE001 # fallback to JSONL reading
            logger.warning("Failed to read Blackboard from SQLite: %s, falling back to JSONL", exc)
            with self.lock:
                if not self.path.exists():
                    return None
                try:
                    with open(self.path, encoding="utf-8") as f:
                        for line in f:
                            try:
                                data = json.loads(line)
                                if data.get("id") == id:
                                    return BlackboardEntry(**data)
                            except json.JSONDecodeError as exc2:
                                logger.warning("Blackboard read JSON decode failed: %s", exc2)
                                continue
                except OSError as exc2:
                    logger.warning("Blackboard read failed: %s", exc2)
                    return None
        return None

    def query(self, type: str | None = None, key: str | None = None) -> list[BlackboardEntry]:
        """Queryable: filter by type and optional key in payload."""
        import sqlite3

        db_path = self.root / "session.db"
        if not db_path.exists():
            return []
        try:
            conn = sqlite3.connect(str(db_path), timeout=15.0)
            if type is not None:
                cur = conn.execute(
                    """
                    SELECT id, type, content_hash, toolchain_digest, schema_version, parent_id,
                           read_set, write_set, assumptions, version_dependencies, timestamp, payload
                    FROM blackboard WHERE type = ? ORDER BY timestamp ASC
                    """,
                    (type,),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT id, type, content_hash, toolchain_digest, schema_version, parent_id,
                           read_set, write_set, assumptions, version_dependencies, timestamp, payload
                    FROM blackboard ORDER BY timestamp ASC
                    """
                )
            results = []
            for row in cur.fetchall():
                payload = json.loads(row[11])
                if not _payload_matches_key(payload, key):
                    continue
                results.append(
                    BlackboardEntry(
                        id=row[0],
                        type=row[1],
                        content_hash=row[2],
                        toolchain_digest=row[3],
                        schema_version=row[4],
                        parent_id=row[5],
                        read_set=json.loads(row[6]),
                        write_set=json.loads(row[7]),
                        assumptions=json.loads(row[8]),
                        version_dependencies=json.loads(row[9]),
                        timestamp=row[10],
                        payload=payload,
                    )
                )
            conn.close()
            return results
        except Exception as exc:  # noqa: BLE001 # fallback to JSONL query
            logger.warning("Failed to query Blackboard from SQLite: %s, falling back to JSONL", exc)
            results = []
            with self.lock:
                if not self.path.exists():
                    return results
                try:
                    with open(self.path, encoding="utf-8") as f:
                        for line in f:
                            try:
                                data = json.loads(line)
                                if type is not None and data.get("type") != type:
                                    continue
                                payload = data.get("payload", {})
                                if not _payload_matches_key(payload, key):
                                    continue
                                results.append(BlackboardEntry(**data))
                            except json.JSONDecodeError as exc2:
                                logger.warning("Blackboard query JSON decode failed: %s", exc2)
                                continue
                except OSError as exc2:
                    logger.warning("Blackboard query failed: %s", exc2)
                    return results
            return results

    def detect_conflict(self, new_entry: BlackboardEntry) -> list[Conflict]:
        """Full conflict detection per v3 spec + Q2 linear chain policy."""
        conflicts: list[Conflict] = []
        existing = self.query(type=new_entry.type)

        new_write = set(new_entry.write_set)
        new_read = set(new_entry.read_set)

        for old in existing:
            if old.id == new_entry.id:
                continue
            if not _should_check_conflict(new_entry, old):
                continue

            old_write = set(old.write_set)
            old_read = set(old.read_set)

            ww = _ww_overlap(new_write, old_write)
            rw = _rw_overlap(new_read, old_write)
            wr = _wr_overlap(old_read, new_write)
            all_overlap = ww | rw | wr

            assump_viol = _assumption_violated(new_entry, old)

            if all_overlap or assump_viol:
                reason = _build_conflict_reason(ww, rw, wr, assump_viol)
                conflicts.append(
                    Conflict(
                        entry_id=new_entry.id,
                        conflicting_entry_id=old.id,
                        reason=reason,
                        read_write_overlap=list(all_overlap),
                        assumption_violated=assump_viol,
                    )
                )
        return conflicts
