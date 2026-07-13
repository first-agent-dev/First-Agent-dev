"""fs.glob — token-efficient file glob, respects .gitignore via git ls-files.

Phase 1 Foundation: researcher needs [glob,grep,read,instant_grep] 600 tokens vs full 3000.
Implements fs.glob pattern matching, returns paths not content, <50ms via git ls-files.
"""

from __future__ import annotations

import fnmatch
import subprocess
from collections.abc import Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import optional_int, require_string


def _git_ls_files(root: Path) -> list[str]:
    try:
        res = subprocess.run(
            ["git", "ls-files"],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception as exc:  # noqa: BLE001 - fallback to rglob
        print(f"WARNING: git ls-files failed: {exc}, fallback to rglob")
    return []


def _rglob_with_pruning(root: Path, exclude_dirs: set[str]) -> list[Path]:
    import os

    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs and not d.startswith(".")]
        for fname in filenames:
            fp = Path(dirpath) / fname
            try:
                if fp.stat().st_size > 200_000:
                    continue
            except OSError:
                continue
            files.append(fp)
    return files


def build_glob_tool(workspace_root: Path) -> ToolSpec:
    root = Path(workspace_root).resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        try:
            data = dict(params)
            pattern = require_string(data, "pattern")
            limit = optional_int(data, "limit") or 50
            if limit <= 0:
                limit = 50
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        try:
            tracked = _git_ls_files(root)
            matched: list[str] = []

            if tracked:
                for rel in tracked:
                    if fnmatch.fnmatch(rel, pattern) or Path(rel).match(pattern):
                        matched.append(rel)
                        if len(matched) >= limit:
                            break
                    if "/" not in pattern:
                        if fnmatch.fnmatch(Path(rel).name, pattern):
                            if rel not in matched:
                                matched.append(rel)
                                if len(matched) >= limit:
                                    break
            else:
                exclude = {
                    ".git",
                    ".fa",
                    "node_modules",
                    ".venv",
                    "__pycache__",
                    "sessions",
                    "dist",
                    "build",
                    ".mypy_cache",
                }
                all_files = _rglob_with_pruning(root, exclude)
                for fp in all_files:
                    rel = str(fp.relative_to(root))
                    if fnmatch.fnmatch(rel, pattern) or fp.match(pattern):
                        matched.append(rel)
                        if len(matched) >= limit:
                            break

            summary = f"Glob found {len(matched)} files matching '{pattern}' (limit {limit})"
            return ToolResult.ok(summary, result={"paths": matched, "pattern": pattern, "limit": limit})

        except Exception as exc:
            return ToolResult.fail("glob_failed", f"Glob failed: {exc}", retryable=False)

    return ToolSpec(
        name="fs.glob",
        description="Glob files by pattern (e.g., '**/*.py', 'src/**/*.md'), respects .gitignore via git ls-files, returns paths not content, token efficient, limit default 50.",
        input_schema={
            "type": "object",
            "required": ["pattern"],
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, e.g., '**/*.py'"},
                "limit": {"type": "integer", "description": "Max paths, default 50", "default": 50},
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "glob", "search"),
        max_context_bytes=2000,
    )


__all__ = ["build_glob_tool"]
