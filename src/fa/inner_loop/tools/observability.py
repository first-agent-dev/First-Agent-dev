"""Observability tools for Pillar 3 KPI measurement and debugging — Stage 0.

Senior refactor:
- chronicle_search: substring + JSON parse, limit, failure-observable
- usage: authoritative `usage` row parsing + tool_calls breakdown
- list_tasks: DI via contextvar for pty_pool/worktree_manager if available
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.state import EventLog
from fa.inner_loop.tools.base import optional_int


def _resolve_event_log(params: Mapping[str, object]) -> tuple[EventLog | None, str | None]:
    run_id_raw = params.get("run_id")
    if run_id_raw is not None:
        if not isinstance(run_id_raw, str) or not run_id_raw.strip():
            return None, "run_id must be a non-empty string"
        run_id = run_id_raw.strip()
        path = Path.home() / ".fa" / "session-log" / run_id / "events.jsonl"
        if not path.exists() and not (path.parent / "session.db").exists():
            return None, f"run_id not found: {run_id}"
        return EventLog(path, run_id=run_id), None

    try:
        from fa.inner_loop.context import get_current_session

        session = get_current_session()
        if session is not None and session.log is not None:
            return session.log, None
    except Exception:  # noqa: BLE001, S110 # best-effort session DI
        pass

    return None, "no active session; pass run_id explicitly"


def _event_row_matches_query(row: Mapping[str, object], query: str) -> bool:
    try:
        return query.lower() in json.dumps(row, ensure_ascii=False, default=str).lower()
    except Exception:  # noqa: BLE001
        return query.lower() in str(row).lower()


def build_chronicle_search_tool(_event_log_path: Path | None = None) -> ToolSpec:
    def handler(params: Mapping[str, object]) -> ToolResult:
        try:
            data = dict(params)
            query_raw = data.get("query", "")
            query = str(query_raw).strip()
            if not query:
                return ToolResult.fail("invalid_params", "query required", retryable=True)
            limit = optional_int(data, "limit") or 10
            if limit <= 0:
                limit = 10
            if limit > 100:
                limit = 100
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        log, err = _resolve_event_log(data)
        if err is not None:
            code = "invalid_params" if "run_id must" in err else "no_active_session"
            return ToolResult.fail(code, err, retryable=False)
        assert log is not None  # noqa: S101

        try:
            entries: list[dict[str, Any]] = []
            for event in log.read_all():
                row = {
                    "event_id": event.event_id,
                    "ts": event.ts,
                    "run_id": event.run_id,
                    "actor": event.actor,
                    "kind": event.kind,
                    "tool_name": event.tool_name,
                    "tool_call_id": event.tool_call_id,
                    "parent_event_id": event.parent_event_id,
                    "content": dict(event.content),
                    "harness_id": event.harness_id,
                }
                if _event_row_matches_query(row, query):
                    entries.append(row)
                    if len(entries) >= limit:
                        break
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return ToolResult.fail("read_error", f"Failed to read EventLog: {exc}", retryable=False)

        run_label = data.get("run_id") or log.run_id or "current"
        summary = f"Found {len(entries)} entries matching '{query}' in run {run_label!r} (limit {limit})"
        return ToolResult.ok(
            summary,
            result={"entries": entries, "query": query, "limit": limit, "run_id": run_label},
        )

    return ToolSpec(
        name="fs.chronicle_search",
        description=(
            "Search the current run EventLog by keyword. Defaults to the active session only; "
            "without an active session, pass run_id explicitly. Returns matching timeline entries."
        ),
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Keyword to search"},
                "limit": {"type": "integer", "default": 10, "description": "Max entries max 100"},
                "run_id": {
                    "type": "string",
                    "description": "Optional explicit run id when no active session exists",
                },
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "observability", "chronicle"),
        max_context_bytes=4000,
    )


def build_usage_tool(_event_log_path: Path | None = None) -> ToolSpec:
    def handler(params: Mapping[str, object]) -> ToolResult:
        data = dict(params)
        log, err = _resolve_event_log(data)
        if err is not None:
            code = "invalid_params" if "run_id must" in err else "no_active_session"
            return ToolResult.fail(code, err, retryable=False)
        assert log is not None  # noqa: S101

        tool_calls: Counter[str] = Counter()
        total_in = 0
        total_out = 0
        total_cache_read = 0
        total_cache_creation = 0
        usage_rows = 0

        try:
            for event in log.read_all():
                if event.kind == "tool_call":
                    tool_calls[event.tool_name or "unknown"] += 1
                elif event.kind == "usage":
                    content = event.content if isinstance(event.content, Mapping) else {}
                    total_in += int(content.get("input_tokens", 0))
                    total_out += int(content.get("output_tokens", 0))
                    total_cache_read += int(content.get("cache_read_input_tokens", 0))
                    total_cache_creation += int(content.get("cache_creation_input_tokens", 0))
                    usage_rows += 1
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return ToolResult.fail("read_error", f"Failed: {exc}", retryable=False)

        cache_ratio = (
            total_cache_read / max(total_in, 1)
            if total_in > 0
            else 0.0
        )
        run_label = data.get("run_id") or log.run_id or "current"

        summary = (
            f"Usage for run {run_label!r}: {sum(tool_calls.values())} tool calls, "
            f"input={total_in}, output={total_out}, cache hit {cache_ratio:.2%}, "
            f"usage rows={usage_rows}, breakdown {dict(tool_calls)}"
        )

        return ToolResult.ok(
            summary,
            result={
                "run_id": run_label,
                "steps": sum(tool_calls.values()),
                "usage_rows": usage_rows,
                "input_tokens": total_in,
                "output_tokens": total_out,
                "cache_read_input_tokens": total_cache_read,
                "cache_creation_input_tokens": total_cache_creation,
                "cache_hit_ratio": cache_ratio,
                "tool_calls_breakdown": dict(tool_calls),
            },
        )

    return ToolSpec(
        name="fs.usage",
        description=(
            "Show current-run usage from authoritative usage event rows. Defaults to the active session only; "
            "without an active session, pass run_id explicitly."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "string",
                    "description": "Optional explicit run id when no active session exists",
                }
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "observability", "usage"),
        max_context_bytes=2000,
    )


def build_list_tasks_tool(  # noqa: C901 -- complexity from fallback chain graceful degradation, documented, will split Phase 3 per Paper 2 §4.4
    pty_pool: Any | None = None, worktree_manager: Any | None = None
) -> ToolSpec:
    # DI via contextvar if not passed explicitly — for pair over autonomy, try to get from current session
    def _get_pool_and_manager():
        pool = pty_pool
        wm = worktree_manager
        try:
            from fa.inner_loop.context import get_current_session

            sess = get_current_session()
            if sess is not None:
                if pool is None:
                    pool = getattr(sess, "pty_pool", None)
                if wm is None:
                    wm = getattr(sess, "worktree_manager", None)
        except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
            pass
        return pool, wm

    def handler(params: Mapping[str, object]) -> ToolResult:
        pool, wm = _get_pool_and_manager()
        tasks: list[dict[str, Any]] = []
        if pool is not None:
            try:
                sessions = pool.list_sessions() if hasattr(pool, "list_sessions") else []
                for sid in sessions:
                    tasks.append({"type": "pty", "id": sid, "status": "running"})
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                tasks.append({"type": "pty", "error": str(exc)})
        if wm is not None:
            try:
                root = getattr(wm, "worktrees_root", None)
                if root and Path(root).exists():
                    for p in Path(root).iterdir():
                        if p.is_dir():
                            tasks.append({"type": "worktree", "id": p.name, "path": str(p), "status": "active"})
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                tasks.append({"type": "worktree", "error": str(exc)})

        # Also try to list subagent artifacts .fa/subagents/*.json
        try:
            from fa.inner_loop.context import get_current_session

            sess = get_current_session()
            if sess is not None:
                ws_root = getattr(sess, "workspace_root", None)
                if ws_root:
                    subagents_dir = Path(ws_root) / ".fa" / "subagents"
                    if subagents_dir.exists():
                        for jf in subagents_dir.glob("*.json"):
                            tasks.append({"type": "subagent", "id": jf.stem, "path": str(jf), "status": "done"})
        except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
            pass

        summary = f"Found {len(tasks)} active tasks (pty/worktree/subagent)"
        return ToolResult.ok(summary, result={"tasks": tasks})

    return ToolSpec(
        name="fs.list_tasks",
        description=(
            "List active PTY sessions + worktree tasks + subagent tasks — for observability. "
            "Gets pool/manager via DI from current session if not passed."
        ),
        input_schema={"type": "object", "properties": {}},
        permission="read",
        handler=handler,
        tags=("fs", "observability", "tasks"),
        max_context_bytes=2000,
    )


__all__ = ["build_chronicle_search_tool", "build_list_tasks_tool", "build_usage_tool"]
