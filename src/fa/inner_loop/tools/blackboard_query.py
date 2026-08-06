"""Blackboard query tool — formal-substrate artifact lookup (S13.x).

Wraps :meth:`fa.blackboard.blackboard.Blackboard.query` as an LLM-callable,
read-only tool so a role can discover artifacts (skill/research/adr/file rows)
from the session blackboard without ``grep -ril``.

**Why this exists.** AGENTS.md / llms.txt / reference.md instruct the agent to
use ``blackboard.query(...)`` for artifact discovery, but no tool exposed it —
a dead instruction. This tool makes that instruction true, returning compact
metadata rows (id, type, content_hash, read/write sets, timestamp) rather than
full payload blobs, for token efficiency (Pillar-3).

**Access seam.** Tool handlers get the session-bound blackboard via the
thread-local ``get_current_session()`` → ``session.blackboard`` (same seam as
``edit_file``). Imported lazily inside the handler to avoid a circular import
through ``state`` / ``profiles``.

**Read-only + failure-observable.** Never writes. ``Blackboard.query`` may raise
(authoritative SessionDatabase failure re-raises when injected); the handler
catches it and returns a structured ``blackboard_query_failed`` ToolResult so
``ToolRegistry.dispatch`` does NOT mask it as ``internal_error``. When there is
no session / blackboard, returns ``blackboard_unavailable``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fa.inner_loop.registry import ToolResult, ToolSpec

# "blackboard_unavailable" — mirrors fa.inner_loop.tools.mutation_guard.BLACKBOARD_UNAVAILABLE
BLACKBOARD_UNAVAILABLE = "blackboard_unavailable"

DEFAULT_LIMIT = 10
MAX_LIMIT = 50


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

    Never returns the payload blob (token efficiency). ``path`` is derived from the
    entry's payload (file_version writes ``payload={"path": write_set[0]}``) falling back
    to the first write_set / read_set path.
    """
    payload = getattr(entry, "payload", None)
    path: object = None
    if isinstance(payload, dict):
        path = payload.get("path")
    if path is None:
        write_set = getattr(entry, "write_set", None) or []
        read_set = getattr(entry, "read_set", None) or []
        path = write_set[0] if write_set else (read_set[0] if read_set else None)
    return {
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
        return ToolResult.ok(
            f"Found {len(compact_rows)} blackboard rows (type={type_ or '*'}, key={key or '*'} limit={limit})",
            result={
                "rows": compact_rows,
                "type": type_ if isinstance(type_, str) else None,
                "key": key if isinstance(key, str) else None,
                "limit": limit,
                "count": len(compact_rows),
            },
        )

    return ToolSpec(
        name="fs_blackboard_query",
        description=(
            "Query the session blackboard (formal substrate artifact store) and return compact "
            "metadata rows (id, type, content_hash, read/write sets, timestamp). Filters by optional "
            "type and key substring; returns at most limit rows (default 10, max 50). "
            "Use for artifact discovery instead of grep -ril."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Optional entry type filter, e.g. 'file_version'.",
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
