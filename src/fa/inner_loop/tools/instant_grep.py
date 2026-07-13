"""Instant Grep tool — FTS5 trigram substring search, <50ms, token efficient — Stage 2

Fixes:
- Gap: fallback rglob slow → use git ls-files for tracked files only (respects .gitignore, fast)
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping
import subprocess

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string


def build_instant_grep_tool(db_path: Path, workspace_root: Path) -> ToolSpec:
    db_path = Path(db_path).resolve()
    workspace_root = Path(workspace_root).resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        try:
            query = require_string(dict(params), "query")
            limit = int(params.get("limit", 10)) if "limit" in params else 10
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        try:
            from fa.memory.fts_index import InstantGrepIndex

            index = InstantGrepIndex(db_path)
            try:
                count = index.conn.execute("SELECT COUNT(*) FROM files_fts").fetchone()[0]
                if count == 0:
                    index.index_repo(workspace_root)
            except Exception:
                try:
                    index.index_repo(workspace_root)
                except Exception:
                    pass
            paths = index.instant_grep(query, limit=limit)
            index.close()
            summary = f"Found {len(paths)} files matching '{query}' (limit {limit}) via FTS5 trigram <50ms"
            return ToolResult.ok(
                summary,
                result={"paths": paths, "query": query, "limit": limit, "method": "fts5"},
            )
        except Exception as e:
            # High ROI Improvement: use git ls-files for tracked files only (fast, respects .gitignore)
            try:
                git_result = subprocess.run(
                    ["git", "ls-files"],
                    cwd=workspace_root,
                    capture_output=True,
                    text=True,
                )
                if git_result.returncode == 0:
                    files = git_result.stdout.splitlines()
                    matched = []
                    q_lower = query.lower()
                    for file_rel in files:
                        # Skip large or binary? quick size check
                        fp = workspace_root / file_rel
                        try:
                            if not fp.is_file():
                                continue
                            if fp.stat().st_size > 100_000:
                                continue
                            # Fast path: check filename contains query
                            if q_lower in file_rel.lower():
                                matched.append(file_rel)
                                if len(matched) >= limit:
                                    break
                                continue
                            content = fp.read_text(encoding="utf-8", errors="ignore")
                            if q_lower in content.lower():
                                matched.append(file_rel)
                                if len(matched) >= limit:
                                    break
                        except Exception:
                            continue
                    summary = f"Found {len(matched)} files matching '{query}' via git ls-files fallback (FTS failed: {e})"
                    return ToolResult.ok(
                        summary,
                        result={
                            "paths": matched,
                            "query": query,
                            "limit": limit,
                            "method": "git_ls_files",
                            "fts_error": str(e),
                        },
                    )
                # If git ls-files failed (not a git repo), fallback to rglob limited
                matched = []
                q_lower = query.lower()
                # Use os.walk with pruning for speed
                import os

                exclude_dirs = {".fa", "node_modules", ".venv", "__pycache__", ".git", "sessions", ".gremlins_cache", "dist", "build", ".mypy_cache"}
                for dirpath, dirnames, filenames in os.walk(workspace_root):
                    # Prune excluded dirs in-place
                    dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
                    # Avoid descending into hidden . dirs beyond root? allow but skip .git etc already
                    for fname in filenames:
                        if not any(fname.endswith(ext) for ext in (".md", ".py", ".ts", ".js", ".json", ".yaml", ".yml", ".toml", ".txt")):
                            continue
                        fp = Path(dirpath) / fname
                        try:
                            if fp.stat().st_size > 100_000:
                                continue
                            content = fp.read_text(encoding="utf-8", errors="ignore")
                            if q_lower in content.lower() or q_lower in str(fp.relative_to(workspace_root)).lower():
                                matched.append(str(fp.relative_to(workspace_root)))
                                if len(matched) >= limit:
                                    break
                        except Exception:
                            continue
                    if len(matched) >= limit:
                        break
                summary = f"Found {len(matched)} files matching '{query}' via fallback glob grep (FTS failed: {e})"
                return ToolResult.ok(
                    summary,
                    result={"paths": matched, "query": query, "limit": limit, "method": "fallback", "fts_error": str(e)},
                )
            except Exception as exc2:
                return ToolResult.fail(
                    "search_failed",
                    f"Instant grep failed: {e}, fallback failed: {exc2}",
                    retryable=False,
                )

    return ToolSpec(
        name="fs.instant_grep",
        description="Instant substring search via FTS5 trigram index (Cursor-like), <50ms, returns paths not content, token efficient, substring search 'auth'→'AuthMiddleware', excludes .fa/, node_modules/, .venv/, sessions/. Falls back to git ls-files (respects .gitignore, fast) if FTS not available.",
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Substring to search, e.g., 'auth', 'AuthMiddleware'"},
                "limit": {"type": "integer", "description": "Max paths to return, default 10", "default": 10},
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "memory", "instant_grep", "search"),
        max_context_bytes=2000,
    )


__all__ = ["build_instant_grep_tool"]
