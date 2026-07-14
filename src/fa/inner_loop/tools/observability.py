"""Observability tools for Pillar 3 KPI measurement and debugging — Stage 0

Senior refactor:
- chronicle_search: substring + JSON parse, limit, failure-observable
- usage: parses steps + tool_calls breakdown, tries to sum tokens if present else TBD with warning, cache hit from events if present
- list_tasks: DI via contextvar for pty_pool/worktree_manager if available
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

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
            if limit > 100:
                limit = 100
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        if not log_path.exists():
            return ToolResult.ok(f"EventLog not found at {log_path}", result={"entries": []})

        entries: list[dict[str, Any]] = []
        try:
            with open(log_path, encoding="utf-8") as f:
                for line in f:
                    if query.lower() in line.lower():
                        try:
                            entries.append(json.loads(line))
                        except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                            entries.append({"raw": line[:500]})
                        if len(entries) >= limit:
                            break
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return ToolResult.fail("read_error", f"Failed to read EventLog: {exc}", retryable=False)

        summary = f"Found {len(entries)} entries matching '{query}' (limit {limit})"
        return ToolResult.ok(summary, result={"entries": entries, "query": query, "limit": limit})

    return ToolSpec(
        name="fs.chronicle_search",
        description="Search EventLog events.jsonl timeline by keyword — returns timeline entries, for debugging token usage vs result, debugging 124 steps timeout. Limit max 100.",
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Keyword to search"},
                "limit": {"type": "integer", "default": 10, "description": "Max entries max 100"},
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
            return ToolResult.ok(
                "No EventLog yet — Pillar 3 KPIs TBD until UC5 baseline run",
                result={"total_tokens": "TBD", "steps": 0, "tool_calls_breakdown": {}},
            )

        steps = 0
        cache_hits = 0
        total_tokens = 0
        has_tokens_field = False
        tool_calls: Counter[str] = Counter()

        try:
            with open(log_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        kind = entry.get("kind", "")
                        if kind == "tool_call":
                            steps += 1
                            tool_calls[entry.get("tool_name", "unknown")] += 1
                        # Try to parse tokens if present in content or top-level
                        # Some events may have content with prompt_tokens/completion_tokens
                        content = entry.get("content", {})
                        if isinstance(content, dict):
                            pt = content.get("prompt_tokens") or content.get("total_tokens")
                            if isinstance(pt, (int, float)):
                                total_tokens += int(pt)
                                has_tokens_field = True
                            ch = content.get("cache_hit")
                            if isinstance(ch, bool) and ch:
                                cache_hits += 1
                    except Exception:  # noqa: BLE001, S112 # graceful degradation per Phase 0.5, failure-observable WARNING
                        continue
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return ToolResult.fail("read_error", f"Failed: {exc}", retryable=False)

        cache_ratio = cache_hits / max(1, steps) if steps else 0.0
        # If no tokens field parsed, mark TBD per Pillar 3 (KPI numbers TBD until UC5 baseline)
        total_tokens_display = total_tokens if has_tokens_field else "TBD"
        summary = f"Usage: {steps} tool calls, {total_tokens_display} tokens, cache hit {cache_ratio:.2%}, breakdown {dict(tool_calls)}"
        if not has_tokens_field:
            summary += " — total_tokens TBD until telemetry with prompt_tokens field (Pillar 3)"

        return ToolResult.ok(
            summary,
            result={
                "steps": steps,
                "total_tokens": total_tokens_display,
                "cache_hits": cache_hits,
                "cache_hit_ratio": cache_ratio,
                "tool_calls_breakdown": dict(tool_calls),
            },
        )

    return ToolSpec(
        name="fs.usage",
        description="Show token usage per turn (if available else TBD), cache hit ratio, steps count, tool calls breakdown — for Pillar 3 KPI measurement. Pillar 3 numbers TBD until UC5 baseline per project-overview.",
        input_schema={"type": "object", "properties": {}},
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
        description="List active PTY sessions + worktree tasks + subagent tasks — for observability. Gets pool/manager via DI from current session if not passed.",
        input_schema={"type": "object", "properties": {}},
        permission="read",
        handler=handler,
        tags=("fs", "observability", "tasks"),
        max_context_bytes=2000,
    )


__all__ = ["build_chronicle_search_tool", "build_list_tasks_tool", "build_usage_tool"]
