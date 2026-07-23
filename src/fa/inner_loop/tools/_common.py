"""Shared utilities for inner_loop tools.

This module contains common functions and constants used by multiple tools
(glob, grep, instant_grep, etc.) to avoid duplication and ensure consistency.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult
from fa.inner_loop.tools.base import optional_int, require_string

logger = logging.getLogger(__name__)


def git_ls_files(root: Path) -> list[str]:
    """Return files respecting .gitignore: tracked + untracked not ignored.

    Uses --cached --others --exclude-standard (token-efficient git native).
    Falls back to empty list on failure — caller will use walk fallback.

    Args:
        root: Repository root directory

    Returns:
        List of file paths relative to root, or empty list on failure

    Example:
        >>> files = git_ls_files(Path("/repo"))
        >>> print(files[:3])
        ['README.md', 'src/main.py', 'tests/test_main.py']
    """
    try:
        res = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except subprocess.TimeoutExpired:
        logger.warning("git ls-files timed out for root=%s", root)
    except Exception as exc:  # noqa: BLE001 — best-effort, fallback to walk
        logger.warning("git ls-files failed: %s, fallback to walk", exc)
    return []


def validate_search_params(
    params: Mapping[str, object],
    default_limit: int,
    max_limit: int,
) -> tuple[str, int]:
    """Validate and normalize search parameters (query, limit).

    Common validation logic for grep-like tools.

    Args:
        params: Parameter mapping from tool invocation
        default_limit: Default limit if not specified or invalid
        max_limit: Maximum allowed limit

    Returns:
        Tuple of (query, normalized_limit)

    Raises:
        ValueError: If query is missing or invalid
    """
    data = dict(params)
    query = require_string(data, "query")
    limit = optional_int(data, "limit") or default_limit
    if limit <= 0:
        limit = default_limit
    if limit > max_limit:
        limit = max_limit

    if not query.strip():
        raise ValueError("query must be non-empty")

    return query, limit


def truncate_for_preview(value: object, preview_len: int | None = 500, max_bytes: int | None = None) -> str:
    """Truncate a value for preview display, showing start and end.

    Converts non-string values to JSON, then truncates if too long,
    showing the first ``preview_len`` chars and last 200 chars with
    a truncation marker in between.

    The ``max_bytes`` parameter is accepted for ``ToolSpec.elide``
    protocol compatibility (the projection layer calls
    ``elider(result, max_context_bytes)``); it does not change the
    truncation length — the 500+200 shape is the fixed token-budget
    preview for fs.run_bash output.

    Args:
        value: Value to render (string or JSON-serializable).
        preview_len: Maximum head length before truncation (default 500).
        max_bytes: Ignored; accepted for elide-callable protocol.

    Returns:
        Rendered string, possibly truncated with marker.

    Example:
        >>> truncate_for_preview("short text")
        'short text'
        >>> truncate_for_preview("x" * 1000)[:5]
        'xxxxx'
    """
    if preview_len is None or preview_len <= 0:
        preview_len = 500
    if isinstance(value, str):
        rendered = value
    else:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=repr)

    if len(rendered) <= preview_len:
        return rendered

    return (
        rendered[:preview_len]
        + f"\n...[truncated {len(rendered)} chars, use | head -n 100 or grep to reduce, full in artifact]...\n"
        + rendered[-200:]
    )


def validate_bash_command(params: Mapping[str, object]) -> tuple[str, ToolResult | None]:
    """Validate and extract bash command from tool parameters.

    Common validation logic for run_bash tools.

    Args:
        params: Parameter mapping from tool invocation

    Returns:
        Tuple of (command, error_result)
        - If validation succeeds: (command, None)
        - If validation fails: ("", ToolResult.fail(...))

    Example:
        >>> command, error = validate_bash_command({"command": "ls -la"})
        >>> if error is None:
        ...     print(f"Valid command: {command}")
    """
    data = dict(params)
    try:
        command = require_string(data, "command")
        return command, None
    except ValueError as exc:
        return "", ToolResult.fail("invalid_params", str(exc), retryable=True)


def prepare_workspace_context(
    workspace_root: Path,
    env_allowlist_extra: Iterable[str] = (),
) -> tuple[Path, frozenset[str]]:
    """Prepare workspace context for bash execution.

    Resolves workspace root and creates environment allowlist frozenset.

    Args:
        workspace_root: Workspace root directory
        env_allowlist_extra: Additional environment variables to allow

    Returns:
        Tuple of (resolved_root, env_allowlist)

    Example:
        >>> root, allowlist = prepare_workspace_context(Path("/repo"), ["DEBUG"])
        >>> print(f"Root: {root}, Allowlist: {allowlist}")
    """
    root = workspace_root.resolve()
    extra_allow = frozenset(env_allowlist_extra)
    return root, extra_allow


__all__ = [
    "git_ls_files",
    "prepare_workspace_context",
    "truncate_for_preview",
    "validate_bash_command",
    "validate_search_params",
]
