"""S16 (CT-6): fs_reach — callers/callees navigation over the structural index.

Resolves a symbol by exact suffix (or ``§``-anchor qualname), then BFS-walks
the ``calls`` table in ``up`` (callers) / ``down`` (callees) / ``both``
directions. v1 resolution is in-file only, so unresolved callees are reported
honestly as ``<unresolved:...>`` identifiers — never hallucinated edges.
"""

from __future__ import annotations

import atexit
import logging
import time
from collections.abc import Mapping
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import DEFAULT_TOOL_CONTEXT_BYTES, ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string
from fa.inner_loop.tools.workspace_port import WorkspacePort, WorkspacePortError, index_db
from fa.memory._safe_walk import RootedFileReader

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

    def __init__(
        self,
        db_path: Path,
        *,
        in_memory: bool = False,
        strict_rooted_reads: bool = False,
        managed_bounded: bool = False,
        rooted_reader: RootedFileReader | None = None,
    ) -> None:
        self._db = db_path
        self._in_memory = in_memory
        self._strict_rooted_reads = strict_rooted_reads
        self._managed_bounded = managed_bounded
        self._rooted_reader = rooted_reader
        self._index: Any = None

    def get(self) -> Any:
        if self._index is None:
            from fa.memory.structural_index import StructuralIndex

            self._index = StructuralIndex(
                self._db,
                in_memory=self._in_memory,
                strict_rooted_reads=self._strict_rooted_reads,
                managed_bounded=self._managed_bounded,
            )
        return self._index

    def close(self, *, strict: bool = False) -> None:
        if self._index is not None:
            try:
                self._index.close()
            except Exception:
                if strict:
                    raise
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


def build_fs_reach_tool(  # noqa: C901 - managed/legacy builder contracts share one immutable ToolSpec surface
    workspace_root: Path,
    *,
    workspace_io: WorkspacePort | None = None,
    scratch_db: Path | None = None,
    in_memory: bool = False,
    strict_rooted_reads: bool = False,
    managed_bounded: bool = False,
    cleanup: ExitStack | None = None,
    project_tool_executor: Any | None = None,
) -> ToolSpec:
    """Build the ``fs_reach`` ToolSpec bound to a workspace (CT-6).

    An optional cleanup stack owns this tool's lifetime and closes its index
    strictly on exit. Without one, legacy atexit cleanup is unchanged.
    ``managed_bounded=True`` is reserved for the cell helper: it requires
    rooted reads and an in-memory index, preflights the complete Q97 inventory,
    and refuses aggregate work/index overruns without a legacy-walk fallback.
    """
    if type(strict_rooted_reads) is not bool or type(managed_bounded) is not bool:
        raise ValueError("strict_rooted_reads and managed_bounded must be bool")
    if strict_rooted_reads and not in_memory:
        raise ValueError("strict_rooted_reads requires an in-memory index")
    if managed_bounded and not strict_rooted_reads:
        raise ValueError("managed bounded reach requires rooted reads")
    if project_tool_executor is not None and workspace_io is None:
        raise ValueError("project tool executor requires a managed workspace port")
    root = Path(workspace_root).resolve()
    rooted_reader = RootedFileReader(root) if strict_rooted_reads else None
    if rooted_reader is not None:
        if cleanup is None:
            atexit.register(rooted_reader.close)
        else:
            cleanup.callback(rooted_reader.close)
    host_db = scratch_db if scratch_db is not None else root / ".fa" / "structural.db"

    def _resolve_index() -> _ReachHolder | None:
        try:
            db = index_db(workspace_io, root, "structural.db", host_db)
        except WorkspacePortError:
            return None
        holder = _ReachHolder(
            db,
            in_memory=in_memory,
            strict_rooted_reads=strict_rooted_reads,
            managed_bounded=managed_bounded,
            rooted_reader=rooted_reader,
        )
        if cleanup is None:
            atexit.register(holder.close)
        else:
            cleanup.callback(holder.close, strict=True)
        return holder

    # A host root and a private cache path do not prove a view-bound index.
    holder = _resolve_index() if workspace_io is None else None

    def handler(params: Mapping[str, object]) -> ToolResult:
        if workspace_io is not None:
            if project_tool_executor is None:
                return ToolResult.fail("reach_failed", "managed cell-local reach index is unavailable", retryable=False)
            from fa.inner_loop.tools.managed_project_tool import dispatch_managed_project_tool

            return dispatch_managed_project_tool(project_tool_executor, "fs_reach", dict(params))
        if holder is None:
            return ToolResult.fail(
                "reach_failed",
                "no index location outside the managed view; the view supplied no private cache home",
                retryable=False,
            )
        managed_inventory = None
        managed_deadline = None
        try:
            if managed_bounded:
                managed_inventory, managed_deadline = _prepare_managed_inventory(root)
            return _handle(
                params,
                holder,
                root,
                managed_inventory=managed_inventory,
                managed_deadline=managed_deadline,
            )
        except Exception as exc:
            if managed_bounded:
                from fa.memory.managed_discovery import ManagedDiscoveryError

                reason = (
                    exc.reason
                    if isinstance(exc, ManagedDiscoveryError)
                    else "deadline"
                    if managed_deadline is not None and time.monotonic() >= managed_deadline
                    else "index_budget"
                )
                return ToolResult.fail("reach_failed", f"managed reach refused ({reason})", retryable=False)
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
        tags=("fs", "navigation", "discovery", "managed-view-serial")
        if project_tool_executor is not None
        else ("fs", "navigation", "discovery"),
        # S12.7 (CT2/GAP4): projection ceiling (was 30_000 — an inventory
        # miss in PLAN-s12.7 preflight, unified with the ceiling tier).
        # _MAX_RESPONSE_BYTES remains the INTERNAL cap.
        max_context_bytes=DEFAULT_TOOL_CONTEXT_BYTES,
    )


def _prepare_managed_inventory(root: Path) -> tuple[Any, float]:
    from fa.memory.managed_discovery import (
        MAX_MANAGED_DEADLINE_MS,
        ManagedDiscoveryError,
        inventory_managed_files,
    )

    deadline = time.monotonic() + MAX_MANAGED_DEADLINE_MS / 1000
    inventory = inventory_managed_files(root, patterns=("*.py",), deadline=deadline)
    if time.monotonic() >= deadline:
        raise ManagedDiscoveryError("deadline")
    return inventory, deadline


def _check_managed_reach_deadline(holder: _ReachHolder, deadline: float | None) -> None:
    if not holder._managed_bounded:
        return
    from fa.memory.managed_discovery import ManagedDiscoveryError

    if deadline is None:
        raise ManagedDiscoveryError("unsafe_path")
    if time.monotonic() >= deadline:
        raise ManagedDiscoveryError("deadline")


def _ensure_reach_index(
    holder: _ReachHolder,
    root: Path,
    managed_inventory: Any,
    managed_deadline: float | None,
) -> tuple[Any, Any]:
    if not holder._managed_bounded:
        index = holder.get()
        return index, index.ensure_indexed(root)
    from fa.memory.managed_discovery import ManagedDiscoveryError

    if managed_inventory is None or managed_deadline is None or holder._rooted_reader is None:
        raise ManagedDiscoveryError("unsafe_path")
    if time.monotonic() >= managed_deadline:
        raise ManagedDiscoveryError("deadline")
    index = holder.get()
    stats = index.ensure_managed_indexed(
        root,
        managed_inventory,
        rooted_reader=holder._rooted_reader,
        deadline=managed_deadline,
    )
    return index, stats


def _validated_reach_params(
    params: Mapping[str, object],
) -> tuple[str, str, str | None, int, int, bool] | ToolResult:
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
    return symbol, direction, kind, depth, limit, _parse_bool(params, "include_tests", False)


def _handle(
    params: Mapping[str, object],
    holder: _ReachHolder,
    root: Path,
    *,
    managed_inventory: Any = None,
    managed_deadline: float | None = None,
) -> ToolResult:
    validated = _validated_reach_params(params)
    if isinstance(validated, ToolResult):
        return validated
    symbol, direction, kind, depth, limit, include_tests = validated

    index, stats = _ensure_reach_index(holder, root, managed_inventory, managed_deadline)
    _check_managed_reach_deadline(holder, managed_deadline)
    if not stats.available:
        if holder._strict_rooted_reads and stats.errors:
            return ToolResult.fail(
                "reach_failed",
                "rooted workspace read was refused; no partial reach result is available",
                retryable=False,
            )
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
        if holder._managed_bounded and stats.files_skipped:
            result["files_skipped"] = stats.files_skipped
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
    if holder._managed_bounded and stats.files_skipped:
        result["files_skipped"] = stats.files_skipped
    _check_managed_reach_deadline(holder, managed_deadline)
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
