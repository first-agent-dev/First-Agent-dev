"""Lazy on-demand artifact index for the Blackboard (S14 / I-56).

Populates typed entries for knowledge/ artifacts (skills, ADRs, research
notes, instructions, prompts, codemaps, anti-patterns, and an enumerated
set of root-level knowledge docs) on first ``fs_blackboard_query`` call.

Design choices (see PLAN-cli-trace-S14-... §0, §4, §11):
- Append-only (V6/S5): new file content gets a NEW physical entry with
  parent_id pointing to the previous revision; never INSERT OR REPLACE.
- Two-level id scheme:
    * logical_id  = f"{entry_type}:{sha256(relpath)[:12]}"   (stable, deterministic)
    * physical id = logical_id (v1)  OR  f"{logical_id}-r{uuid4().hex[:8]}" (revisions)
  payload["logical_id"] is set on every row so future passes can find the
  latest revision of a given logical artifact regardless of physical id.
- Never calls detect_conflict (that is mutation_guard's job for file_version).
- Fail-degraded: never raises out of ensure_artifacts_indexed; per-file and
  top-level errors accumulate in ArtifactIndexStats.errors and are logged.
- Path-contained: rejects symlinks escaping knowledge/ via resolve+relative_to.
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fa.blackboard.blackboard import Blackboard, BlackboardEntry

logger = logging.getLogger(__name__)

ARTIFACT_TYPES: frozenset[str] = frozenset(
    {"skill", "adr", "research", "instruction", "prompt", "codemap", "antipattern"}
)
ARTIFACT_ROOTS: dict[str, str] = {
    "skill": "skills",
    "adr": "adr",
    "research": "research",
    "instruction": "instructions",
    "prompt": "prompts",
    "codemap": "codemaps",
    "antipattern": "anti-patterns",
}
# Root-level knowledge/ docs that are legitimate artifacts (EXPLICIT enumeration;
# NOT "*.md" — AGENTS.md / HANDOFF / archive / stage verification excluded).
_ARTIFACT_ROOT_SPECIAL: tuple[tuple[str, str], ...] = (
    ("BACKLOG.md", "research"),
    ("MAINTENANCE.md", "research"),
    ("README.md", "research"),
    ("project-overview.md", "research"),
    ("reference.md", "research"),
    ("llms.txt", "research"),
)
_MAX_FILE_BYTES = 200_000
_LOGICAL_ID_HASH_LEN = 12
_REVISION_SUFFIX_LEN = 8


@dataclass
class ArtifactIndexStats:
    scanned: int = 0
    added: int = 0
    updated: int = 0
    skipped_unchanged: int = 0
    errors: list[str] = field(default_factory=list)
    indexed_types: set[str] = field(default_factory=set)


def _logical_id(entry_type: str, relpath: str) -> str:
    # sha256 truncated to 12 hex chars (48 bits); sufficient collision domain
    # for ~200 paths (birthday bound ~10M) without triggering S324 (sha1 ban).
    h = hashlib.sha256(relpath.encode("utf-8")).hexdigest()[:_LOGICAL_ID_HASH_LEN]
    return f"{entry_type}:{h}"


def _revision_phys_id(logical: str) -> str:
    return f"{logical}-r{uuid.uuid4().hex[:_REVISION_SUFFIX_LEN]}"


def _title_from_content(text: str, fallback: str) -> str:
    """Extract an ATX H1 heading, else first non-empty line, else fallback."""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()[:200]
    for line in text.splitlines():
        s = line.strip()
        if s:
            return s[:200]
    return fallback


def _iter_candidate_files(knowledge_root: Path, types: set[str]) -> Iterator[tuple[str, Path, str]]:
    """Yield (entry_type, abs_p, relpath) for in-scope files."""
    for entry_type, sub in ARTIFACT_ROOTS.items():
        if entry_type not in types:
            continue
        d = knowledge_root / sub
        if not d.is_dir():
            continue
        for dirpath, _dirnames, filenames in os.walk(d):
            for fn in filenames:
                if not fn.endswith(".md"):
                    continue
                abs_p = Path(dirpath) / fn
                try:
                    rel = abs_p.relative_to(knowledge_root).as_posix()
                except ValueError:
                    continue
                yield entry_type, abs_p, rel
    for fname, entry_type in _ARTIFACT_ROOT_SPECIAL:
        if entry_type not in types:
            continue
        abs_p = knowledge_root / fname
        if abs_p.is_file():
            yield entry_type, abs_p, fname


def _is_within(child: Path, parent: Path) -> bool:
    """Containment check that survives symlinks — both sides resolved."""
    try:
        child.resolve().relative_to(parent.resolve())
    except (ValueError, OSError):
        return False
    return True


def _latest_by_logical_id(blackboard: Blackboard, types: set[str]) -> dict[str, BlackboardEntry]:
    """Build ``{logical_id: latest_entry}`` across all artifact types.

    v1 rows have ``id == logical_id`` and no ``logical_id`` in payload.
    Revision rows carry ``payload["logical_id"]`` and a unique physical id.
    "Latest" = highest ``timestamp`` per logical_id (ISO-8601 string sort
    matches chronological sort when timestamps are produced by the same
    clock, which BlackboardEntry.create ensures via datetime.now(UTC)).
    """
    out: dict[str, BlackboardEntry] = {}
    for t in types:
        for e in blackboard.query(type=t):
            if isinstance(e.payload, dict) and isinstance(e.payload.get("logical_id"), str):
                lid = e.payload["logical_id"]
            else:
                lid = e.id
            prev = out.get(lid)
            if prev is None or e.timestamp >= prev.timestamp:
                out[lid] = e
    return out


def _file_hash_of(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:16]


def ensure_artifacts_indexed(
    blackboard: Blackboard,
    workspace_root: Path,
    types: set[str] | None = None,
) -> ArtifactIndexStats:
    """Index knowledge/ artifacts into ``blackboard`` if missing or stale.

    Purely additive. Never raises. Returns a stats struct describing what
    happened. Safe to call repeatedly (idempotent for unchanged files).
    """
    stats = ArtifactIndexStats()
    try:
        knowledge_root = (workspace_root / "knowledge").resolve()
    except OSError as exc:
        stats.errors.append(f"knowledge_root:{exc}")
        return stats
    if not knowledge_root.is_dir():
        return stats
    target_types = set(types) if types is not None else set(ARTIFACT_TYPES)
    target_types = target_types & set(ARTIFACT_TYPES)
    # If caller requested types but none are artifact types, return zero stats
    # rather than silently indexing everything (which would be a type-error).
    if types is not None and not target_types:
        return stats
    if not target_types:
        return stats
    latest = _latest_by_logical_id(blackboard, target_types)
    for entry_type, abs_p, rel in _iter_candidate_files(knowledge_root, target_types):
        _index_one_file(
            entry_type,
            abs_p,
            rel,
            knowledge_root,
            latest,
            blackboard,
            stats,
        )
    return stats


def _index_one_file(
    entry_type: str,
    abs_p: Path,
    rel: str,
    knowledge_root: Path,
    latest: dict[str, BlackboardEntry],
    blackboard: Blackboard,
    stats: ArtifactIndexStats,
) -> None:
    """Index a single candidate file; updates ``stats`` and ``latest`` in place.

    Extracted to keep ``ensure_artifacts_indexed`` under the C901 budget (15).
    Never raises; failures append to ``stats.errors``.
    """
    stats.scanned += 1
    stats.indexed_types.add(entry_type)
    # Type whitelist belt-and-braces: _iter_candidate_files already filters
    # by `types`, but if a future change yields an unexpected type refuse
    # rather than silently indexing an unintended path class.
    if entry_type not in ARTIFACT_TYPES:
        stats.errors.append(f"unexpected_type:{entry_type}:{rel}")
        return
    if not _is_within(abs_p, knowledge_root):
        stats.errors.append(f"escape:{rel}")
        return
    try:
        st = abs_p.stat()
    except OSError as exc:
        stats.errors.append(f"stat:{rel}:{exc}")
        return
    if st.st_size > _MAX_FILE_BYTES:
        stats.errors.append(f"too_large:{rel}:{st.st_size}")
        return
    try:
        raw = abs_p.read_bytes()
    except OSError as exc:
        stats.errors.append(f"read:{rel}:{exc}")
        return
    file_hash = _file_hash_of(raw)
    # decode with errors="replace" never raises on valid bytes input;
    # keep the call explicit so corrupt/non-UTF-8 content degrades to
    # replacement chars rather than breaking indexing.
    text = raw.decode("utf-8", errors="replace")
    logical = _logical_id(entry_type, rel)
    prev = latest.get(logical)
    prev_hash: str | None = None
    if prev is not None and isinstance(prev.payload, dict):
        prev_hash = prev.payload.get("file_hash")
    if prev is not None and prev_hash == file_hash:
        stats.skipped_unchanged += 1
        return
    payload: dict[str, Any] = {
        "path": rel,
        "relpath": rel,
        "title": _title_from_content(text, fallback=rel),
        "file_hash": file_hash,
        "logical_id": logical,
        "size": st.st_size,
        "mtime": int(st.st_mtime),
    }
    phys_id = logical if prev is None else _revision_phys_id(logical)
    try:
        entry = BlackboardEntry.create(
            id=phys_id,
            type=entry_type,
            payload=payload,
            read_set=[],
            write_set=[rel],
            assumptions=[],
            version_dependencies={},
            parent_id=(prev.id if prev is not None else None),
        )
        blackboard.write(entry)
        if prev is None:
            stats.added += 1
        else:
            stats.updated += 1
        latest[logical] = entry
    except Exception as exc:  # noqa: BLE001 — fail-degraded per Phase-0.5
        msg = str(exc)
        if "blackboard_duplicate_id" in msg:
            # Concurrent indexer wrote the same logical id → treat as
            # already-indexed (idempotent under concurrency).
            stats.skipped_unchanged += 1
        else:
            stats.errors.append(f"write:{rel}:{exc}")
            logger.warning("artifact index write failed for %s: %s", rel, exc)


__all__ = [
    "ARTIFACT_TYPES",
    "ArtifactIndexStats",
    "ensure_artifacts_indexed",
]
