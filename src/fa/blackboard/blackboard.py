"""
Blackboard — Typed Blackboard with Content Hashes + Transactional Semantics
Phase 0.5 — Formal Shared Harness Substrate
Prior art: MACOG blackboard with content hashes + toolchain digests, L2MAC file store D persistent never overwritten but extended/revised with Control Unit, SyncMind belief-state divergence |Bk - Sk|

Senior eng: interface segregation, DI, feature flags, graceful degradation, thread safety, observable failures
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

@dataclass
class BlackboardEntry:
    id: str
    type: str  # plan, execution, evaluation, flowstate, tool_result, file_version
    content_hash: str  # sha256 of payload
    toolchain_digest: str  # python version, mypy version, model id
    schema_version: str  # Task IR v1, Plan Artifact v2
    parent_id: Optional[str]  # previous version
    read_set: List[str]  # files read
    write_set: List[str]  # files written
    assumptions: List[str]  # e.g., "main branch is main", "file src/auth.py exists"
    version_dependencies: Dict[str, str]  # e.g., {"base_commit": "abc123", "llms.txt": "sha256:..."}
    timestamp: str
    payload: Any  # actual content

    @classmethod
    def create(
        cls,
        id: str,
        type: str,
        payload: Any,
        read_set: List[str] = None,
        write_set: List[str] = None,
        assumptions: List[str] = None,
        version_dependencies: Dict[str, str] = None,
        parent_id: Optional[str] = None,
        schema_version: str = "v1",
    ) -> "BlackboardEntry":
        # Content hash
        content_str = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]
        # Toolchain digest: python version + model id placeholder
        import sys
        toolchain_digest = f"python-{sys.version_info.major}.{sys.version_info.minor}"
        timestamp = datetime.now(timezone.utc).isoformat()
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
    read_write_overlap: List[str]
    assumption_violated: Optional[str] = None

class Blackboard:
    """
    Append-only, content-addressed, queryable blackboard
    Store: .fa/blackboard/blackboard.jsonl
    Control Unit manages reads/writes, never overwrites, extended/revised
    Each entry stamped with content hashes, toolchain digests, schema versions for reproducibility (MACOG)
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "blackboard.jsonl"
        self.lock = threading.Lock()
        # Ensure file exists
        self.path.touch(exist_ok=True)

    def write(self, entry: BlackboardEntry) -> None:
        """Append-only, never overwrite, content-addressed, thread-safe"""
        try:
            line = json.dumps(asdict(entry), ensure_ascii=False)
            with self.lock:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as e:
            # Graceful degradation: log WARNING and continue, not crash (Gap for Phase 0.5)
            print(f"WARNING: Blackboard write failed {e}, continuing")

    def read(self, id: str) -> Optional[BlackboardEntry]:
        # Simple linear scan for v0.1, could be indexed for future
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

    def query(self, type: str = None, key: str = None) -> List[BlackboardEntry]:
        """Queryable: filter by type and optional key in payload"""
        results = []
        with self.lock:
            if not self.path.exists():
                return results
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if type and data.get("type") != type:
                            continue
                        if key and key not in json.dumps(data.get("payload", {})):
                            continue
                        results.append(BlackboardEntry(**data))
                    except Exception:
                        continue
        return results

    def detect_conflict(self, new_entry: BlackboardEntry) -> List[Conflict]:
        """
        Detect conflicts for v0.1: write/write overlap always conflict.
        Simplified per review Gap 8/12: timestamp logic inverted previously,
        so for v0.1 we treat any write/write overlap (different id) as conflict,
        regardless of timestamp. Read/write overlap not enforced in v0.1 —
        requires Transaction start-time, deferred to Phase 1.
        """
        conflicts = []
        existing = self.query(type=new_entry.type)
        for old in existing:
            if old.id == new_entry.id:
                continue
            # write/write overlap → conflict (core case: two agents write same file)
            ww_overlap = set(new_entry.write_set) & set(old.write_set)
            if ww_overlap:
                conflicts.append(
                    Conflict(
                        entry_id=new_entry.id,
                        conflicting_entry_id=old.id,
                        reason=f"write/write overlap {ww_overlap} — concurrent "
                        f"write without coordination",
                        read_write_overlap=list(ww_overlap),
                    )
                )
        return conflicts

# Example usage:
# bb = Blackboard(Path(".fa/blackboard"))
# entry = BlackboardEntry.create(id="plan-1", type="plan", payload={"goal":"fix auth"}, read_set=["src/auth.py"], write_set=[], assumptions=["main branch is main"], version_dependencies={"base_commit":"abc123"})
# bb.write(entry)
# conflicts = bb.detect_conflict(new_entry)
# if conflicts: return ToolResult.fail("conflict_detected", f"Conflict: {conflicts}", retryable=True)
