"""
Blackboard — Typed Blackboard with Content Hashes + Transactional Semantics
Phase 0.5 — Formal Shared Harness Substrate
Prior art: MACOG blackboard with content hashes + toolchain digests, L2MAC file store D persistent
Senior eng: interface segregation, DI, feature flags, graceful degradation, thread safety, observable failures
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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
        import sys

        toolchain_digest = f"python-{sys.version_info.major}.{sys.version_info.minor}"
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


class Blackboard:
    """
    Append-only, content-addressed, queryable blackboard
    Store: .fa/blackboard/blackboard.jsonl
    Control Unit manages reads/writes, never overwrites, extended/revised
    Each entry stamped with content hashes, toolchain digests, schema versions for reproducibility
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "blackboard.jsonl"
        self.lock = threading.Lock()
        self.path.touch(exist_ok=True)

    def write(self, entry: BlackboardEntry) -> None:
        """Append-only, never overwrite, content-addressed, thread-safe"""
        try:
            line = json.dumps(asdict(entry), ensure_ascii=False)
            with self.lock:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as e:
            print(f"WARNING: Blackboard write failed {e}, continuing")

    def read(self, id: str) -> BlackboardEntry | None:
        with self.lock:
            if not self.path.exists():
                return None
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if data.get("id") == id:
                            return BlackboardEntry(**data)
                    except Exception:
                        continue
        return None

    def query(self, type: str | None = None, key: str | None = None) -> list[BlackboardEntry]:
        """Queryable: filter by type and optional key in payload"""
        results: list[BlackboardEntry] = []
        with self.lock:
            if not self.path.exists():
                return results
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if type is not None and data.get("type") != type:
                            continue
                        if key is not None and key not in json.dumps(data.get("payload", {})):
                            continue
                        results.append(BlackboardEntry(**data))
                    except Exception:
                        continue
        return results

    def detect_conflict(self, new_entry: BlackboardEntry) -> list[Conflict]:
        """
        Detect conflicts for v0.1: write/write overlap always conflict.
        Simplified per review: any write/write overlap (different id) as conflict.
        """
        conflicts: list[Conflict] = []
        existing = self.query(type=new_entry.type)
        for old in existing:
            if old.id == new_entry.id:
                continue
            ww_overlap = set(new_entry.write_set) & set(old.write_set)
            if ww_overlap:
                conflicts.append(
                    Conflict(
                        entry_id=new_entry.id,
                        conflicting_entry_id=old.id,
                        reason=f"write/write overlap {ww_overlap} — concurrent write without coordination",
                        read_write_overlap=list(ww_overlap),
                    )
                )
        return conflicts
