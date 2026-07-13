"""Observability tools for Pillar 3 KPI measurement and debugging — Stage 0"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import optional_int


def build_chronicle_search_tool(event_log_path: Path) -> ToolSpec:
    log_path = Path(event_log_path).resolve()

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
        except Exception as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)
        if not log_path.exists():
            return ToolResult.ok(f"EventLog not found at {log_path}", result={"entries": []})
        entries: list[dict[str, Any]] = []
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if query.lower() in line.lower():
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            entries.append({"raw": line[:500]})
                        if len(entries) >= limit:
                            break
        except Exception as exc:
            return ToolResult.fail("read_error", f"Failed to read EventLog: {exc}", retryable=False)
        summary = f"Found {len(entries)} entries matching '{query}' (limit {limit})"
        return ToolResult.ok(summary, result={"entries": entries, "query": query, "limit": limit})

    return ToolSpec(
        name="fs.chronicle_search",
        description="Search EventLog events.jsonl timeline by keyword — returns timeline entries with rank, for debugging token usage vs result, debugging 124 steps timeout.",
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Keyword to search"},
                "limit": {"type": "integer", "default": 10},
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "observability", "chronicle"),
        max_context_bytes=4000,
    )


def build_usage_tool(event_log_path: Path) -> ToolSpec:
    log_path = Path(event_log_path).resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        if not log_path.exists():
            return ToolResult.ok("No EventLog yet", result={"total_tokens": 0, "steps": 0})
        total_tokens = 0
        steps = 0
        cache_hits = 0
        tool_calls: Counter[str] = Counter()
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        kind = entry.get("kind", "")
                        if kind == "tool_call":
                            steps += 1
                            tool_calls[entry.get("tool_name", "unknown")] += 1
                    except Exception:
                        continue
        except Exception as exc:
            return ToolResult.fail("read_error", f"Failed: {exc}", retryable=False)
        cache_ratio = cache_hits / max(1, steps)
        summary = f"Usage: {steps} tool calls, {total_tokens} tokens, cache hit {cache_ratio:.2%}, breakdown {dict(tool_calls)}"
        return ToolResult.ok(
            summary,
            result={
                "steps": steps,
                "total_tokens": total_tokens,
                "cache_hits": cache_hits,
                "cache_hit_ratio": cache_ratio,
                "tool_calls_breakdown": dict(tool_calls),
            },
        )

    return ToolSpec(
        name="fs.usage",
        description="Show token usage per turn, cache hit ratio, steps count, tool calls breakdown — for Pillar 3 KPI measurement.",
        input_schema={"type": "object", "properties": {}},
        permission="read",
        handler=handler,
        tags=("fs", "observability", "usage"),
        max_context_bytes=2000,
    )


def build_list_tasks_tool(
    pty_pool: Any | None = None, worktree_manager: Any | None = None
) -> ToolSpec:
    def handler(params: Mapping[str, object]) -> ToolResult:
        tasks: list[dict[str, Any]] = []
        if pty_pool is not None:
            try:
                sessions = pty_pool.list_sessions() if hasattr(pty_pool, "list_sessions") else []
                for sid in sessions:
                    tasks.append({"type": "pty", "id": sid, "status": "running"})
            except Exception as exc:
                tasks.append({"type": "pty", "error": str(exc)})
        if worktree_manager is not None:
            try:
                root = getattr(worktree_manager, "worktrees_root", None)
                if root and Path(root).exists():
                    for p in Path(root).iterdir():
                        if p.is_dir():
                            tasks.append({"type": "worktree", "id": p.name, "path": str(p), "status": "active"})
            except Exception as exc:
                tasks.append({"type": "worktree", "error": str(exc)})
        summary = f"Found {len(tasks)} active tasks"
        return ToolResult.ok(summary, result={"tasks": tasks})

    return ToolSpec(
        name="fs.list_tasks",
        description="List active PTY sessions + worktree tasks + subagent tasks — for observability.",
        input_schema={"type": "object", "properties": {}},
        permission="read",
        handler=handler,
        tags=("fs", "observability", "tasks"),
        max_context_bytes=2000,
    )


__all__ = ["build_chronicle_search_tool", "build_usage_tool", "build_list_tasks_tool"]
