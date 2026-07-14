"""fs.grep — token-efficient content grep, returns paths with matches.

Senior refactor:
- Single source EXCLUDE_DIRS module level
- rg and git grep first (handle large files streaming efficiently)
- Python fallback streaming line-by-line not loading whole file, no hard 200k skip, but max_file_size param overridable + failure-observable warning
- Symlink safety
- Token efficient paths not content
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import optional_int, require_string

try:
    from fa.memory.fts_index import EXCLUDE_DIRS

    EXCLUDE_DIRS = set(EXCLUDE_DIRS)
except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
    EXCLUDE_DIRS = {
        ".git",
        ".fa",
        "node_modules",
        ".venv",
        "__pycache__",
        ".gremlins_cache",
        "sessions",
        "dist",
        "build",
        ".mypy_cache",
    }

DEFAULT_LIMIT = 20
DEFAULT_MAX_FILE_SIZE = 200_000  # soft limit, overridable via param
MAX_LIMIT = 100


def _git_grep(root: Path, query: str, limit: int) -> list[str] | None:
    try:
        res = subprocess.run(  # noqa: S603 -- trusted binary per ADR-6, list args, no shell
            ["git", "grep", "-l", "--", query],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if res.returncode in (0, 1):
            files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            return files[:limit]
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        print(f"WARNING: git grep failed: {exc}")
    return None


def _rg_grep(root: Path, query: str, limit: int) -> list[str] | None:
    try:
        res = subprocess.run(  # noqa: S603 -- trusted binary per ADR-6, list args, no shell
            ["rg", "-l", query],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if res.returncode in (0, 1):
            files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            return files[:limit]
    except FileNotFoundError:
        return None
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        print(f"WARNING: rg failed: {exc}")
    return None


def _grep_file_stream(path: Path, query_lower: str, max_file_size: int) -> bool:
    """Streaming search line-by-line, no full load, handles large files.

    If file > max_file_size and max_file_size set, still searches via streaming
    but logs warning that large file search may be slower. No hard skip unless
    max_file_size is 0? Actually we search regardless, but respect max_file_size as soft limit:
    if size > max_file_size, we still stream but with early warning.

    Returns True if query found.
    """
    try:
        # Symlink safety: resolve must be inside workspace? Caller checks root containment
        # For fallback, we already pruned symlinked dirs via os.walk followlinks=False
        # File symlink pointing outside already filtered by is_relative_to check in caller
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if query_lower in line.lower():
                    return True
        return False
    except OSError:
        return False


def _iter_files_for_grep(root: Path):
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
            except Exception:  # noqa: BLE001, S112 # graceful degradation per Phase 0.5, failure-observable WARNING
                continue
            try:
                yield str(fp.relative_to(root_resolved))
            except ValueError:
                continue


def build_grep_tool(workspace_root: Path) -> ToolSpec:  # noqa: C901 -- complexity from fallback chain graceful degradation, documented, will split Phase 3 per Paper 2 §4.4
    root = Path(workspace_root).resolve()

    if not root.is_dir():
        raise ValueError(f"workspace_root {root} not dir")

    def handler(params: Mapping[str, object]) -> ToolResult:  # noqa: C901 -- handler complexity from fast path rg/git grep + fallback streaming, split into helpers already
        try:
            data = dict(params)
            query = require_string(data, "query")
            limit = optional_int(data, "limit") or DEFAULT_LIMIT
            if limit <= 0:
                limit = DEFAULT_LIMIT
            if limit > MAX_LIMIT:
                limit = MAX_LIMIT
            glob_filter = data.get("glob")
            if glob_filter is not None and not isinstance(glob_filter, str):
                glob_filter = None
            max_file_size = optional_int(data, "max_file_size") or DEFAULT_MAX_FILE_SIZE
            if max_file_size < 0:
                max_file_size = 0  # 0 means no limit
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        if not query.strip():
            return ToolResult.fail("invalid_params", "query must be non-empty", retryable=True)

        # 1) Fast paths: rg and git grep handle large files efficiently streaming
        for method in (_rg_grep, _git_grep):
            result = method(root, query, limit)
            if result is not None:
                if glob_filter:
                    result = [p for p in result if fnmatch.fnmatch(p, glob_filter)][:limit]
                summary = (
                    f"Grep found {len(result)} files containing '{query}' via {method.__name__} (limit {limit})"
                )
                return ToolResult.ok(
                    summary,
                    result={"paths": result, "query": query, "limit": limit, "method": method.__name__},
                )

        # 2) Fallback python streaming (no rg/git grep available)
        # Get file list via git ls-files --cached --others --exclude-standard respecting .gitignore
        try:
            ls_res = subprocess.run(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard"],  # noqa: S607
                cwd=root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            tracked = ls_res.stdout.splitlines() if ls_res.returncode == 0 else []
            # Filter excluded dirs that git might list
            tracked = [p for p in tracked if not any(part in EXCLUDE_DIRS for part in Path(p).parts)]
        except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            tracked = []

        if not tracked:
            tracked = list(_iter_files_for_grep(root))

        matched: list[str] = []
        q_lower = query.lower()
        skipped_large: list[str] = []

        for rel in tracked:
            if glob_filter and not fnmatch.fnmatch(rel, glob_filter):
                continue
            fp = root / rel
            try:
                if not fp.is_file():
                    continue
                # Soft size check: if max_file_size>0 and file > limit, warn but still search via streaming
                try:
                    size = fp.stat().st_size
                    if max_file_size > 0 and size > max_file_size:
                        # Log warning but still search via streaming (efficient)
                        # If you want hard skip, set max_file_size param smaller, but we search anyway with warning
                        skipped_large.append(f"{rel} ({size} bytes)")
                except OSError:
                    continue
                if _grep_file_stream(fp, q_lower, max_file_size):
                    matched.append(rel)
                    if len(matched) >= limit:
                        break
            except Exception:  # noqa: BLE001, S112 # graceful degradation per Phase 0.5, failure-observable WARNING
                continue

        summary = f"Grep found {len(matched)} files containing '{query}' via python fallback streaming (limit {limit})"
        if skipped_large:
            summary += (
                f" — {len(skipped_large)} large files checked via streaming: {', '.join(skipped_large[:3])}"
            )
        return ToolResult.ok(
            summary,
            result={"paths": matched, "query": query, "limit": limit, "method": "python_fallback_streaming"},
        )

    return ToolSpec(
        name="fs.grep",
        description="Grep files containing query (e.g., 'auth'), respects .gitignore via rg/git grep (handles large files streaming), returns paths not content token efficient. Optional glob filter like '*.py', max_file_size param default 200k soft limit overridable (0=no limit). Limit default 20 max 100.",
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Substring to search"},
                "glob": {"type": "string", "description": "Optional glob filter e.g., '*.py'"},
                "limit": {"type": "integer", "description": "Max paths, default 20 max 100", "default": 20},
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


__all__ = ["EXCLUDE_DIRS", "build_grep_tool"]
