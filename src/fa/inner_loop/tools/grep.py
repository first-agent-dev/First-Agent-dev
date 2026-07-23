"""fs.grep — high-speed code search, returns matched lines with numbers.

Optimized SOTA Inspection tool:
- Fast path: git grep -n --no-color (runs natively in C, bypasses Python I/O)
- Fallback path: pruned os.walk + streaming python line-by-line reading
- Standard library logging used across all warning paths
- Safe resolved paths and symlink containment checks
- Token efficient output limit default 20 max 100
"""

from __future__ import annotations

import fnmatch
import logging
import os
import subprocess
from collections.abc import Generator, Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools._common import validate_search_params
from fa.inner_loop.tools.base import optional_int
from fa.memory.fts_index import EXCLUDE_DIRS

logger = logging.getLogger(__name__)

# Single source of truth — import once at module load, fallback if not available
# Single source of truth for excluded directories


DEFAULT_LIMIT = 20
DEFAULT_MAX_FILE_SIZE = 200_000  # soft limit, overridable via param
MAX_LIMIT = 100


def _git_grep(root: Path, query: str, limit: int) -> list[dict[str, Any]] | None:
    """Run native git grep -n --no-color to fetch matching lines with numbers."""
    try:
        res = subprocess.run(  # noqa: S603
            ["git", "grep", "-n", "--no-color", "--", query],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if res.returncode in (0, 1):
            matches = []
            for line in res.stdout.splitlines():
                if not line.strip():
                    continue
                # git grep output: path:line_no:content
                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue
                path, line_no, content = parts
                try:
                    matches.append({"path": path, "line": int(line_no), "content": content})
                except ValueError:
                    continue
                if len(matches) >= limit:
                    break
            return matches
    except Exception as exc:  # noqa: BLE001 # graceful degradation
        logger.warning("git grep failed: %s, falling back to python search", exc)
    return None


def _grep_file_stream(path: Path, rel_path: str, query_lower: str, limit: int) -> list[dict[str, Any]]:
    """Stream file line-by-line, matching query and capturing line numbers."""
    matches = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, start=1):
                if query_lower in line.lower():
                    matches.append({"path": rel_path, "line": idx, "content": line.rstrip()})
                    if len(matches) >= limit:
                        break
    except OSError as exc:
        logger.warning("Failed to read file %s: %s", path, exc)
    return matches


def _iter_files_for_grep(root: Path) -> Generator[Path]:
    """Yield relative paths for python fallback, pruned, symlink-safe."""
    root_resolved = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root_resolved, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fname in filenames:
            if not fname.endswith((".py", ".md", ".ts", ".js", ".json", ".yaml", ".toml")):
                continue
            fp = Path(dirpath) / fname
            try:
                # Symlink escape check
                if not fp.resolve().is_relative_to(root_resolved):
                    continue
            except Exception as exc:  # noqa: BLE001 # graceful degradation
                logger.warning("symlink resolution failed for %s: %s", fp, exc)
                continue
            yield fp


def build_grep_tool(workspace_root: Path) -> ToolSpec:  # noqa: C901 -- complexity from fallback chain
    root = Path(workspace_root).resolve()

    if not root.is_dir():
        raise ValueError(f"workspace_root {root} not dir")

    def handler(params: Mapping[str, object]) -> ToolResult:  # noqa: C901 -- complexity from fallback chain
        try:
            query, limit = validate_search_params(params, DEFAULT_LIMIT, MAX_LIMIT)
            data = dict(params)
            glob_filter = data.get("glob")
            if glob_filter is not None and not isinstance(glob_filter, str):
                glob_filter = None
            max_file_size = optional_int(data, "max_file_size") or DEFAULT_MAX_FILE_SIZE
            if max_file_size < 0:
                max_file_size = 0  # 0 means no limit
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        # 1) Fast path: git grep (handles large files natively in C)
        result = _git_grep(root, query, limit)
        if result is not None:
            if glob_filter:
                result = [m for m in result if fnmatch.fnmatch(m["path"], glob_filter)][:limit]
            summary = f"Grep found {len(result)} lines matching '{query}' via git grep (limit {limit})"
            return ToolResult.ok(
                summary,
                result={"matches": result, "query": query, "limit": limit, "method": "git_grep"},
            )

        # 2) Fallback: python streaming (no git grep available)
        files_to_scan = []
        try:
            ls_res = subprocess.run(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard"],  # noqa: S607
                cwd=root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if ls_res.returncode == 0:
                tracked = ls_res.stdout.splitlines()
                # Filter excluded dirs that git might list
                files_to_scan = [root / p for p in tracked if not any(part in EXCLUDE_DIRS for part in Path(p).parts)]
        except Exception as exc:  # noqa: BLE001 # fallback to directory walk
            logger.warning("git ls-files failed: %s, falling back to walk", exc)

        if not files_to_scan:
            files_to_scan = list(_iter_files_for_grep(root))

        matched: list[dict[str, Any]] = []
        q_lower = query.lower()
        skipped_large: list[str] = []

        for fp in files_to_scan:
            try:
                rel = str(fp.relative_to(root))
            except ValueError:
                continue
            if glob_filter and not fnmatch.fnmatch(rel, glob_filter):
                continue
            try:
                if not fp.is_file():
                    continue
                # Soft size check
                try:
                    size = fp.stat().st_size
                    if max_file_size > 0 and size > max_file_size:
                        skipped_large.append(f"{rel} ({size} bytes)")
                except OSError:
                    continue

                matches = _grep_file_stream(fp, rel, q_lower, limit - len(matched))
                matched.extend(matches)
                if len(matched) >= limit:
                    break
            except Exception as exc:  # noqa: BLE001 # graceful degradation
                logger.warning("Failed to grep file %s: %s", fp, exc)
                continue

        summary = f"Grep found {len(matched)} lines matching '{query}' via python fallback (limit {limit})"
        if skipped_large:
            summary += f" — {len(skipped_large)} large files checked: {', '.join(skipped_large[:3])}"
        return ToolResult.ok(
            summary,
            result={"matches": matched, "query": query, "limit": limit, "method": "python_fallback_streaming"},
        )

    return ToolSpec(
        name="fs.grep",
        description=(
            "Grep files containing query (e.g., 'auth'), returns matching lines with numbers. "
            "Respects .gitignore natively via git grep, with a streaming fallback. "
            "Optional glob filter like '*.py', max_file_size default 200k soft limit. Limit default 20."
        ),
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Substring to search"},
                "glob": {"type": "string", "description": "Optional glob filter e.g., '*.py'"},
                "limit": {"type": "integer", "description": "Max matched lines, default 20", "default": 20},
                "max_file_size": {
                    "type": "integer",
                    "description": "Soft max file size bytes for streaming check, default 200k, 0=no limit",
                    "default": 200000,
                },
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "grep", "search"),
        max_context_bytes=2000,
    )


__all__ = ["DEFAULT_LIMIT", "DEFAULT_MAX_FILE_SIZE", "EXCLUDE_DIRS", "MAX_LIMIT", "build_grep_tool"]
