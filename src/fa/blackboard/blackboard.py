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

from fa.inner_loop._sqlite_common import payload_matches_key
from fa.inner_loop.session_db import SessionDatabase

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
    # Writer identity (S5.4.1 / Q18). Persisted since the schema's first
    # version in the ``blackboard.run_id`` column and always populated by
    # ``Blackboard.write``, but previously discarded when rebuilding entries on
    # the read path — which left ``detect_conflict`` unable to distinguish an
    # agent's own prior entry from a genuine concurrent writer. Defaults to ""
    # ("unknown writer") so legacy rows and external constructors keep working;
    # unknown is deliberately NOT treated as self (see ``_is_same_writer``).
    run_id: str = ""

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
    """Decide whether ``new`` must be conflict-checked against ``old``.

    Only an explicit ``parent_id`` link establishes happens-before. An entry that
    names its predecessor is a linear successor by construction, so it cannot
    conflict with it.

    ``base_commit`` deliberately does NOT suppress the check. The previous
    implementation returned ``new_base == old_base``, treating a differing base
    as "serialized" and skipping detection entirely. That made the guarantee
    expire: once any commit landed, every pre-commit entry became unenforceable,
    and coding agents commit routinely. Measured in the S3 audit — agent B was
    correctly blocked at HEAD1, one unrelated commit landed, and agent C writing
    the same file was allowed through (finding S3-F10).

    A different ``base_commit`` means *later*, not *safe*: two agents editing the
    same path across a commit boundary is precisely the write/write overlap
    ADR-16 I-6.3 requires to fail with ``conflict_detected``. Divergent bases are
    still reported separately via :func:`_assumption_violated`, which is where
    that signal belongs.
    """
    return new.parent_id != old.id


def _is_same_writer(writer_run_id: str, old: BlackboardEntry) -> bool:
    """Return True when ``old`` was written by the agent now being checked.

    ADR-16 I-6.3 exists to catch *"concurrent [writes] without coordination"* —
    a **different** actor touching a path we are touching. An agent's own
    earlier entry is its own history, not a conflict, and reporting it as one
    makes iterative single-file editing impossible (measured: the second
    ``write_file`` to a path was denied by the first one's entry, silently
    dropping the later content).

    Both ids must be non-empty. An empty ``run_id`` means *unknown writer*,
    which cannot be **proven** to be self, so it stays conflict-eligible: rows
    written before this field existed must keep failing closed rather than
    silently becoming unguarded.

    Scoping a concurrency guard by writer identity is the shape shipped agents
    converge on — opencode keys its staleness guard by ``sessionID``
    (``FileTime.read``/``FileTime.assert``), and the most-reported Claude Code
    Edit defect is precisely a guard firing on the agent's own prior edit.
    """
    return bool(writer_run_id) and bool(old.run_id) and writer_run_id == old.run_id


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
        logger.warning(f"assumption check failed: {exc}, continuing")
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


class Blackboard:
    """Append-only, content-addressed, queryable blackboard.

    `root` remains a workspace-identity anchor for safety checks and optional
    JSONL mirroring. Authoritative hot-path state may instead be backed by the
    per-run SessionDatabase when injected.
    """

    def __init__(
        self,
        root: Path,
        *,
        session_db: SessionDatabase | None = None,
        run_id: str = "",
        session_id: str = "",
    ):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "blackboard.jsonl"
        self.lock = threading.Lock()
        self.path.touch(exist_ok=True)
        self._run_id = run_id
        self._injected_session_db = session_db is not None
        self._session_db = session_db if session_db is not None else SessionDatabase(self.root / "session.db")
        self.session_id = session_id or self._session_db.session_id
        if self.session_id and self._session_db.session_id and self.session_id != self._session_db.session_id:
            raise ValueError(
                "session_db_identity_mismatch: "
                f"Blackboard session {self.session_id!r} != DB session {self._session_db.session_id!r}"
            )
        self._init_db()

    def _init_db(self) -> None:
        try:
            _ = self._session_db
        except Exception as exc:  # best-effort
            logger.warning("Failed to initialize authoritative Blackboard database: %s", exc)
            raise

    def write(self, entry: BlackboardEntry) -> None:
        row = {
            "id": entry.id,
            "session_id": self.session_id,
            "run_id": self._run_id,
            "type": entry.type,
            "content_hash": entry.content_hash,
            "toolchain_digest": entry.toolchain_digest,
            "schema_version": entry.schema_version,
            "parent_id": entry.parent_id,
            "read_set": entry.read_set,
            "write_set": entry.write_set,
            "assumptions": entry.assumptions,
            "version_dependencies": entry.version_dependencies,
            "timestamp": entry.timestamp,
            "payload": entry.payload,
        }
        # 1. Authoritative write to per-run DB.
        self._session_db.write_blackboard_row(row)

        # 2. Best-effort JSONL mirror. Stamp the mirror with the SAME writer id
        # the authority row was written under (``self._run_id``), not whatever
        # the caller happened to leave on the entry — otherwise the mirror and
        # the DB could disagree about who wrote a row, and the degraded read
        # path would reach a different conflict verdict than the authority.
        try:
            line = json.dumps({**asdict(entry), "run_id": self._run_id}, ensure_ascii=False)
            with self.lock:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as exc:  # noqa: BLE001 # mirror-only degradation
            logger.warning("Blackboard JSONL mirror write failed: %s", exc)

    def read(self, id: str) -> BlackboardEntry | None:
        try:
            row = self._session_db.read_blackboard_row(id)
            if row is not None:
                return BlackboardEntry(
                    id=row["id"],
                    type=row["type"],
                    content_hash=row["content_hash"],
                    toolchain_digest=row["toolchain_digest"],
                    schema_version=row["schema_version"],
                    parent_id=row["parent_id"],
                    read_set=row["read_set"],
                    write_set=row["write_set"],
                    assumptions=row["assumptions"],
                    version_dependencies=row["version_dependencies"],
                    timestamp=row["timestamp"],
                    payload=row["payload"],
                    run_id=row.get("run_id", ""),
                )
        except Exception as exc:  # legacy/degraded fallback
            logger.warning("Failed to read Blackboard from authoritative SessionDatabase: %s", exc)
            if self._injected_session_db:
                raise
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
        try:
            rows = self._session_db.query_blackboard_rows(type, key)
            return [
                BlackboardEntry(
                    id=row["id"],
                    type=row["type"],
                    content_hash=row["content_hash"],
                    toolchain_digest=row["toolchain_digest"],
                    schema_version=row["schema_version"],
                    parent_id=row["parent_id"],
                    read_set=row["read_set"],
                    write_set=row["write_set"],
                    assumptions=row["assumptions"],
                    version_dependencies=row["version_dependencies"],
                    timestamp=row["timestamp"],
                    payload=row["payload"],
                    run_id=row.get("run_id", ""),
                )
                for row in rows
            ]
        except Exception as exc:  # fallback to JSONL query
            logger.warning("Failed to query Blackboard from authoritative SessionDatabase: %s", exc)
            if self._injected_session_db:
                raise
            results: list[BlackboardEntry] = []
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
                                if not payload_matches_key(payload, key):
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
            # S5.4.1 (Q18): never conflict with our own earlier entry. Checked
            # against this Blackboard's writer id rather than ``new_entry``'s,
            # because ``write()`` stamps the row from ``self._run_id`` — that
            # is the identity the entry will actually be persisted under.
            if _is_same_writer(self._run_id, old):
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
