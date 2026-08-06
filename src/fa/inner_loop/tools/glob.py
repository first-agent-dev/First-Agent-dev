"""fs_glob — token-efficient file glob, respects .gitignore via git ls-files.

Senior refactor (v3 review):
- Single responsibility helpers, deterministic pure functions
- Safety: resolved root, symlink escape check, EXCLUDE_DIRS single source
- Returns paths rather than content, uses a token-efficient limit of 50, and prunes symlinks.
- Uses git ls-files --cached --others --exclude-standard so untracked, non-ignored files are included.
- Matching centralized: Path.match + fnmatch basename fallback, no duplicate branches
- No size filter (glob returns paths, size irrelevant for token efficiency)
"""

from __future__ import annotations

import fnmatch
import logging
import os
from collections.abc import Generator, Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools._common import git_ls_files
from fa.inner_loop.tools.base import optional_int, require_string
from fa.memory.fts_index import EXCLUDE_DIRS

logger = logging.getLogger(__name__)

# Single source of truth for excluded directories


MAX_LIMIT = 200
DEFAULT_LIMIT = 50


def _iter_files_fallback(root: Path) -> Generator[Path]:
    """Walk filesystem with pruning, yield absolute Paths, symlink-safe.

    - Prunes EXCLUDE_DIRS + dot dirs
    - Does NOT follow symlink dirs (os.walk default)
    - Skips files that resolve outside root (symlink escape)
    """
    root_resolved = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root_resolved, followlinks=False):
        # Prune in-place — senior pattern from fts_index but deterministic
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        dirpath_p = Path(dirpath)
        for fname in filenames:
            fp = dirpath_p / fname
            # Safety: symlink file pointing outside workspace?
            try:
                resolved = fp.resolve()
                if not resolved.is_relative_to(root_resolved):
                    continue
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable, symlink safety
                logger.warning(f"symlink check failed: {exc}, continuing")
                continue
            yield fp


def _matches(rel: str, pattern: str) -> bool:
    """Centralized matching: Path.match (supports **) + fnmatch + basename fallback + **/ handling.

    Handles:
    - Path.match for **/*.py recursive (Python 3.13+)
    - fnmatch full rel for simple *
    - basename fallback for "*.py" matching any file in any dir (user intent)
    - "**/" prefix stripped fallback so "**/*.py" also matches root-level "a.py"
    """
    p = Path(rel)

    # Helper to try both Path.match and fnmatch
    def _try_match(r: str, pat: str) -> bool:
        pp = Path(r)
        try:
            if pp.match(pat):
                return True
        except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
            pass
        if fnmatch.fnmatch(r, pat):
            return True
        return False

    # 1) Direct match
    if _try_match(rel, pattern):
        return True

    # 2) Basename fallback if pattern has no slash: "*.py" should match subdir files
    if "/" not in pattern:
        if fnmatch.fnmatch(p.name, pattern):
            return True

    # 3) "**/" handling: "**/*.py" should also match root-level "*.py"
    #    Strip leading "**/" recursively and try again
    stripped = pattern
    while stripped.startswith("**/"):
        stripped = stripped[3:]
        if not stripped:
            break
        if _try_match(rel, stripped):
            return True
        # Also basename fallback for stripped pattern
        if "/" not in stripped and fnmatch.fnmatch(p.name, stripped):
            return True

    # 4) Special case: pattern "**" alone matches everything
    if pattern == "**":
        return True

    return False


def _collect_matches(files: list[str] | Generator[str], pattern: str, limit: int) -> list[str]:
    """Deduped, order-preserving, limit-aware filtering."""
    seen: set[str] = set()
    matched: list[str] = []
    for rel in files:
        if rel in seen:
            continue
        if _matches(rel, pattern):
            seen.add(rel)
            matched.append(rel)
            if len(matched) >= limit:
                break
    return matched


def _parse_params(params: Mapping[str, object]) -> tuple[str, int]:
    data = dict(params)
    pattern = require_string(data, "pattern")
    limit = optional_int(data, "limit") or DEFAULT_LIMIT
    if limit <= 0:
        limit = DEFAULT_LIMIT
    if limit > MAX_LIMIT:
        limit = MAX_LIMIT
    if not pattern.strip():
        raise ValueError("pattern must be non-empty")
    return pattern.strip(), limit


def build_glob_tool(workspace_root: Path) -> ToolSpec:
    root = Path(workspace_root).resolve()

    if not root.is_dir():
        raise ValueError(f"workspace_root {root} is not a directory")

    def handler(params: Mapping[str, object]) -> ToolResult:
        # 1) Parse — separate concern, fail fast retryable
        try:
            pattern, limit = _parse_params(params)
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        # 2) Get file list — git fast path first, fallback walk
        try:
            tracked = git_ls_files(root)

            if tracked:
                # tracked are already relative, filtered by gitignore, but still respect EXCLUDE_DIRS
                # Filter out excluded dirs that git might list (e.g., .fa if tracked historically)
                filtered_tracked = [rel for rel in tracked if not any(part in EXCLUDE_DIRS for part in Path(rel).parts)]
                matched = _collect_matches(filtered_tracked, pattern, limit)
            else:
                # Fallback: walk + relative conversion
                def rel_gen() -> Generator[str]:
                    for fp in _iter_files_fallback(root):
                        try:
                            yield str(fp.relative_to(root))
                        except ValueError:
                            continue

                matched = _collect_matches(rel_gen(), pattern, limit)

            summary = f"Glob found {len(matched)} files matching '{pattern}' (limit {limit})"
            return ToolResult.ok(summary, result={"paths": matched, "pattern": pattern, "limit": limit})

        except Exception as exc:  # noqa: BLE001 — outer safety net, non-retryable
            return ToolResult.fail("glob_failed", f"Glob failed: {exc}", retryable=False)

    return ToolSpec(
        name="fs_glob",
        description=(
            "Glob files by pattern, respecting .gitignore via git ls-files; returns paths "
            "rather than content with a default limit of 50 and maximum of 200."
        ),
        input_schema={
            "type": "object",
            "required": ["pattern"],
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, e.g., '**/*.py'"},
                "limit": {"type": "integer", "description": "Max paths, default 50 max 200", "default": 50},
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "glob", "search"),
        max_context_bytes=2000,
    )


__all__ = ["DEFAULT_LIMIT", "EXCLUDE_DIRS", "MAX_LIMIT", "build_glob_tool"]
