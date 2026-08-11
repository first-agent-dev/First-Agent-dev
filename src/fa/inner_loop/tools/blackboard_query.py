"""Blackboard query tool — formal-substrate artifact lookup (S13.x + S14).

Wraps :meth:`fa.blackboard.blackboard.Blackboard.query` as an LLM-callable,
read-only tool so a role can discover artifacts (skill/research/adr/file rows)
from the session blackboard without ``grep -ril``.

**Why this exists.** AGENTS.md / llms.txt / reference.md instruct the agent to
use ``fs_blackboard_query`` for artifact discovery. The tool reads file_version
rows from mutation_guard and, lazily on first artifact-type query, indexes
knowledge/ artifacts (skill, adr, research, instruction, prompt, codemap,
antipattern + enumerated root docs) via ``fa.blackboard.artifact_index``
(S14 / I-56). Returns compact metadata rows (id, type, content_hash, read/write
sets, timestamp, path, title-inferred-path) rather than full payload blobs for
token efficiency (Pillar-3). Content search is ``fs_search``'s job (use
output_mode="files" for path discovery; "matches"/"regions" for line content).

**Access seam.** Tool handlers get the session-bound blackboard via the
thread-local ``get_current_session()`` → ``session.blackboard`` (same seam as
``edit_file``). Imported lazily inside the handler to avoid a circular import
through ``state`` / ``profiles``.

**Read-mostly + failure-observable.** The only write this tool performs is the
lazy additive artifact index (purely append-only, content-hash-addressed).
``Blackboard.query`` may raise (authoritative SessionDatabase failure re-raises
when injected); the handler catches it and returns a structured
``blackboard_query_failed`` ToolResult so ``ToolRegistry.dispatch`` does NOT
mask it as ``internal_error``. Indexer failures are fail-degraded (log WARNING,
return existing rows). When there is no session / blackboard, returns
``blackboard_unavailable``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from fa.inner_loop.registry import ToolResult, ToolSpec

logger = logging.getLogger(__name__)

# "blackboard_unavailable" — mirrors fa.inner_loop.tools.mutation_guard.BLACKBOARD_UNAVAILABLE
BLACKBOARD_UNAVAILABLE = "blackboard_unavailable"

DEFAULT_LIMIT = 10
MAX_LIMIT = 50

# S14 (I-56): artifact types recognized for lazy indexing. Imported lazily at
# module level to avoid a hard dependency on fa.blackboard.artifact_index at
# import time; resolved once at first handler call. The set is written via the
# lazy attribute so tests can monkeypatch it via the module.
_ARTIFACT_TYPES: frozenset[str] | None = None


def _resolve_artifact_types() -> frozenset[str]:
    global _ARTIFACT_TYPES
    if _ARTIFACT_TYPES is None:
        from fa.blackboard import artifact_index as _ai

        _ARTIFACT_TYPES = frozenset(_ai.ARTIFACT_TYPES)
    return _ARTIFACT_TYPES


def _clamp_limit(params: Mapping[str, object]) -> int:
    """Return a clamped limit: default 10, max 50 (mirrors validate_search_params)."""
    raw = params.get("limit")
    if isinstance(raw, int):
        if raw <= 0:
            return DEFAULT_LIMIT
        return min(raw, MAX_LIMIT)
    return DEFAULT_LIMIT


def _compact(entry: Any) -> dict[str, object]:
    """Project one BlackboardEntry to compact metadata (attribute access — it is a dataclass).

    Never returns the full payload blob (token efficiency). ``path`` is derived
    from the entry's payload (file_version writes ``payload={"path": write_set[0]}``;
    artifact indexer writes ``payload={"path": relpath, "title": ...}``) falling
    back to the first write_set / read_set path. ``title`` is surfaced for
    artifact entries so the LLM can show a human-readable label without reading
    the file.
    """
    payload = getattr(entry, "payload", None)
    path: object = None
    title: object = None
    if isinstance(payload, dict):
        path = payload.get("path")
        title = payload.get("title")
    if path is None:
        write_set = getattr(entry, "write_set", None) or []
        read_set = getattr(entry, "read_set", None) or []
        path = write_set[0] if write_set else (read_set[0] if read_set else None)
    out: dict[str, object] = {
        "id": entry.id,
        "type": entry.type,
        "content_hash": entry.content_hash,
        "read_set": list(getattr(entry, "read_set", None) or []),
        "write_set": list(getattr(entry, "write_set", None) or []),
        "assumptions": list(getattr(entry, "assumptions", None) or []),
        "version_dependencies": dict(getattr(entry, "version_dependencies", None) or {}),
        "timestamp": entry.timestamp,
        "path": path,
    }
    if title is not None:
        out["title"] = title
    return out


def build_blackboard_query_tool() -> ToolSpec:
    """Build the read-only blackboard query tool."""

    def handler(params: Mapping[str, object]) -> ToolResult:
        # Lazy import to avoid a circular import through state/profiles (edit_file pattern).
        from fa.inner_loop.context import get_current_session

        limit = _clamp_limit(params)
        type_ = params.get("type")
        key = params.get("key")

        session = get_current_session()
        if session is None or session.blackboard is None:
            return ToolResult.fail(
                BLACKBOARD_UNAVAILABLE,
                "No active session blackboard available to query (blackboard disabled or no session).",
                retryable=False,
            )

        # S14 (I-56): lazy-index knowledge/ artifacts before querying. Imported
        # lazily so the tool still works (returning file_version rows) if the
        # artifact_index module fails to import for any reason (fail-degraded,
        # same pattern as get_current_session above).
        #
        # We only trigger indexing for (a) wildcard (type=None) or (b) a type
        # that is a recognized artifact type. Unknown types (e.g. user typos
        # like type="skil") skip indexing entirely — indexing them would
        # incorrectly walk all artifacts because types=set() would become
        # types=None inside ensure_artifacts_indexed.
        index_stats = None
        artifact_types = _resolve_artifact_types()
        is_artifact_query = type_ is None or (isinstance(type_, str) and type_ in artifact_types)
        if is_artifact_query and session.blackboard is not None:
            try:
                from fa.blackboard import artifact_index

                ws_root = getattr(session, "workspace_root", None)
                if ws_root is not None:
                    target_types: set[str] | None = None if type_ is None else {str(type_)}
                    index_stats = artifact_index.ensure_artifacts_indexed(
                        session.blackboard,
                        ws_root,
                        types=target_types,
                    )
            except Exception as exc:  # noqa: BLE001 — fail-degraded per Phase-0.5
                logger.warning("fs_blackboard_query: artifact index unavailable: %s", exc)
                index_stats = None

        try:
            rows = session.blackboard.query(
                type=type_ if isinstance(type_, str) else None, key=key if isinstance(key, str) else None
            )
        except Exception as exc:  # noqa: BLE001 — handler must catch to surface blackboard_query_failed
            return ToolResult.fail(
                "blackboard_query_failed",
                f"Blackboard query failed: {exc}",
                retryable=False,
            )

        # Blackboard.query returns list[BlackboardEntry] ordered timestamp ASC (oldest first);
        # take the most recent `limit`.
        rows = rows[-limit:]
        compact_rows = [_compact(entry) for entry in rows]
        indexed_dict: dict[str, object] = {}
        if index_stats is not None:
            indexed_dict = {
                "indexed": {
                    "scanned": index_stats.scanned,
                    "added": index_stats.added,
                    "updated": index_stats.updated,
                    "skipped": index_stats.skipped_unchanged,
                    "errors": index_stats.errors[:5],
                    "types": sorted(index_stats.indexed_types),
                }
            }
        return ToolResult.ok(
            f"Found {len(compact_rows)} blackboard rows (type={type_ or '*'}, key={key or '*'} limit={limit})",
            result={
                "rows": compact_rows,
                "type": type_ if isinstance(type_, str) else None,
                "key": key if isinstance(key, str) else None,
                "limit": limit,
                "count": len(compact_rows),
                **indexed_dict,
            },
        )

    return ToolSpec(
        name="fs_blackboard_query",
        description=(
            "Query the session blackboard (formal substrate artifact store) and return compact "
            "metadata rows (id, type, content_hash, read/write sets, timestamp, path, title). "
            "Filters by optional type and key substring; returns at most limit rows (default 10, "
            "max 50). Artifact types (skill, adr, research, instruction, prompt, codemap, "
            "antipattern) are indexed lazily from knowledge/ on first such query and returned "
            "alongside file_version rows. Use fs_search (not this tool) for substring "
            "content search. Use for artifact discovery instead of grep -ril."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": (
                        "Optional entry type filter, e.g. 'file_version' or 'skill'. "
                        "Artifact types: skill, adr, research, instruction, prompt, codemap, antipattern."
                    ),
                },
                "key": {
                    "type": "string",
                    "description": "Optional substring matched against entry payload.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return, default 10 max 50 (over-max is clamped).",
                    "default": 10,
                },
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "blackboard", "query", "search"),
        max_context_bytes=2048,
    )


__all__ = ["BLACKBOARD_UNAVAILABLE", "DEFAULT_LIMIT", "MAX_LIMIT", "build_blackboard_query_tool"]
