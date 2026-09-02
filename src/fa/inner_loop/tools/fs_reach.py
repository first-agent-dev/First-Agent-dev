"""S16 (CT-6): fs_reach — callers/callees navigation over the structural index.

Resolves a symbol by exact suffix (or ``§``-anchor qualname), then BFS-walks
the ``calls`` table in ``up`` (callers) / ``down`` (callees) / ``both``
directions. v1 resolution is in-file only, so unresolved callees are reported
honestly as ``<unresolved:...>`` identifiers — never hallucinated edges.
"""

from __future__ import annotations

import atexit
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import DEFAULT_TOOL_CONTEXT_BYTES, ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string

logger = logging.getLogger(__name__)

_DIRECTIONS = frozenset({"up", "down", "both"})
_KINDS = frozenset({"function", "method", "doc_anchor"})
_DEFAULT_DEPTH = 2
_DEFAULT_LIMIT = 20
_MAX_RESPONSE_BYTES = 30_000

_DESCRIPTION = (
    "Trace call relationships of a Python symbol: find its callers (direction=up) "
    "or callees (direction=down) up to a BFS depth. Python-only in v1; unresolved "
    "callees are reported honestly as <unresolved:...>. Use fs_search first to "
    "find a symbol by name, then fs_reach to trace relationships; for a file's "
    "structural outline (symbols/sections with exact line ranges) use fs_search "
    "output_mode='outline' instead."
)


class _ReachHolder:
    """Lazily holds the process-wide StructuralIndex for one workspace."""

    def __init__(self, db_path: Path) -> None:
        self._db = db_path
        self._index: Any = None

    def get(self) -> Any:
        if self._index is None:
            from fa.memory.structural_index import StructuralIndex

            self._index = StructuralIndex(self._db)
        return self._index

    def close(self) -> None:
        if self._index is not None:
            try:
                self._index.close()
            except Exception:
                logger.debug("error closing StructuralIndex", exc_info=True)


def _parse_bool(params: Mapping[str, object], key: str, default: bool) -> bool:
    value = params.get(key, default)
    if isinstance(value, bool):
        return value
    return default


def _clamped_int(params: Mapping[str, object], key: str, default: int, lo: int, hi: int) -> int | None:
    """Return the clamped int, or None when the value is present but not an int."""
    value = params.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return max(lo, min(hi, value))


def _parse_enum(
    params: Mapping[str, object], key: str, allowed: frozenset[str], default: str | None
) -> tuple[str | None, str | None]:
    """Return (value, error). value is None when absent→default; error on bad input."""
    value = params.get(key)
    if value is None:
        return default, None
    if not isinstance(value, str) or value not in allowed:
        return None, f"{key} must be one of {sorted(allowed)}"
    return value, None


def build_fs_reach_tool(workspace_root: Path) -> ToolSpec:
    """Build the ``fs_reach`` ToolSpec bound to a workspace (CT-6)."""
    root = Path(workspace_root).resolve()
    db = root / ".fa" / "structural.db"
    holder = _ReachHolder(db)
    atexit.register(holder.close)

    def handler(params: Mapping[str, object]) -> ToolResult:
        try:
            return _handle(params, holder, root)
        except Exception as exc:
            logger.warning("fs_reach top-level error: %s", exc, exc_info=True)
            return ToolResult.fail(
                "reach_failed",
                f"internal error in fs_reach: {exc}",
                retryable=False,
            )

    return ToolSpec(
        name="fs_reach",
        description=_DESCRIPTION,
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Symbol name (suffix match) or §anchor id."},
                "direction": {"type": "string", "enum": ["up", "down", "both"], "default": "both"},
                "depth": {"type": "integer", "default": _DEFAULT_DEPTH},
                "limit": {"type": "integer", "default": _DEFAULT_LIMIT},
                "kind": {"type": "string", "enum": ["function", "method", "doc_anchor"]},
                "include_tests": {"type": "boolean", "default": False},
            },
            "required": ["symbol"],
        },
        permission="read",
        handler=handler,
        tags=("fs", "navigation", "discovery"),
        # S12.7 (CT2/GAP4): projection ceiling (was 30_000 — an inventory
        # miss in PLAN-s12.7 preflight, unified with the ceiling tier).
        # _MAX_RESPONSE_BYTES remains the INTERNAL cap.
        max_context_bytes=DEFAULT_TOOL_CONTEXT_BYTES,
    )


def _handle(params: Mapping[str, object], holder: _ReachHolder, root: Path) -> ToolResult:
    symbol = require_string(params, "symbol").strip()
    if not symbol:
        return ToolResult.fail("invalid_params", "symbol must be a non-empty string", retryable=True)

    direction, err = _parse_enum(params, "direction", _DIRECTIONS, "both")
    if err:
        return ToolResult.fail("invalid_params", err, retryable=True)
    if direction is None:
        return ToolResult.fail("reach_failed", "internal: direction default not applied", retryable=False)

    kind, err = _parse_enum(params, "kind", _KINDS, None)
    if err:
        return ToolResult.fail("invalid_params", err, retryable=True)

    depth = _clamped_int(params, "depth", _DEFAULT_DEPTH, 0, 5)
    if depth is None:
        return ToolResult.fail("invalid_params", "depth must be an integer", retryable=True)
    limit = _clamped_int(params, "limit", _DEFAULT_LIMIT, 1, 50)
    if limit is None:
        return ToolResult.fail("invalid_params", "limit must be an integer", retryable=True)
    include_tests = _parse_bool(params, "include_tests", False)

    index = holder.get()
    stats = index.ensure_indexed(root)
    if not stats.available:
        result: dict[str, Any] = {
            "status": "unavailable",
            "query": symbol,
            "resolved_to": None,
            "candidates": [],
            "callers": [],
            "callees": [],
            "truncated": False,
            "unresolved": 0,
            "reason": "structural index is Python-only in v1",
            "detected_languages": list(stats.detected_languages),
        }
        return ToolResult.ok("fs_reach unavailable (non-Python workspace)", result=result)

    # Resolve: §-prefix → exact doc_anchor qualname; else exact-suffix match.
    resolved = None
    candidates_rows = []
    if symbol.startswith("§"):
        rows = [r for r in index.find_symbols(symbol, kind=None) if r.qualname == symbol]
        resolved = rows[0] if rows else None
    else:
        rows = index.find_symbols(symbol, kind=kind)
        if rows:
            resolved = rows[0]
            candidates_rows = rows[1:6]

    callers: list[dict[str, Any]] = []
    callees: list[dict[str, Any]] = []
    truncated = False
    unresolved = 0
    if resolved is not None:
        if direction in ("up", "both"):
            up_rows, up_trunc, up_unresolved = index.reachable(
                resolved.sym_id, "up", depth, limit, include_tests=include_tests
            )
            # reachable returns (row, true-BFS-distance) pairs — never
            # enumerate-fabricated distances (fan-out levels would lie).
            callers = [_row_to_dict(row, dist) for row, dist in up_rows]
            truncated = truncated or up_trunc
            unresolved += up_unresolved
        if direction in ("down", "both"):
            down_rows, down_trunc, down_unresolved = index.reachable(
                resolved.sym_id, "down", depth, limit, include_tests=include_tests
            )
            callees = [_row_to_dict(row, dist) for row, dist in down_rows]
            truncated = truncated or down_trunc
            unresolved += down_unresolved

    result = {
        "status": "ok",
        "query": symbol,
        "resolved_to": _row_to_dict(resolved, 0) if resolved is not None else None,
        "candidates": [r.qualname for r in candidates_rows],
        "callers": callers,
        "callees": callees,
        "truncated": truncated,
        "unresolved": unresolved,
    }
    summary = f"fs_reach {symbol!r}: {len(callers)} callers, {len(callees)} callees, {unresolved} unresolved"
    return ToolResult.ok(summary, result=result)


def _row_to_dict(row: Any, distance: int) -> dict[str, Any]:
    """SymbolRow → CT-6 OUT element (no private fields leak)."""
    return {
        "sym_id": row.sym_id,
        "path": row.path,
        "qualname": row.qualname,
        "kind": row.kind,
        "line": row.start_line,
        "distance": distance,
        "docstring": row.docstring,
    }
