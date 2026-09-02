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
from typing import Any

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


def truncate_for_preview(value: object, preview_len: int = 500) -> str:
    """Truncate a value for preview display, showing start and end.

    Converts non-string values to JSON, then truncates if too long,
    showing the first ``preview_len`` chars and last 200 chars with
    a truncation marker in between.

    This function is deliberately NOT budget-aware: it always renders a
    fixed-shape (``preview_len`` + 200 tail chars) preview regardless of
    any caller's context-window budget. Do NOT pass this function directly
    as a ``ToolSpec.elide`` callable — ``ToolElider`` is
    ``Callable[[value, max_context_bytes], str]`` and the projection layer
    calls it positionally (``elider(result, spec.max_context_bytes)``); a
    direct reference here would silently bind ``max_context_bytes`` to
    this function's ``preview_len`` parameter, replacing the fixed
    500-char head with whatever budget the tool happens to have (typically
    thousands of characters) and losing the tail + truncation notice.
    Elide callables must go through a small named adapter matching
    ``ToolElider``'s ``(value, max_bytes) -> str`` shape instead — see
    ``_bash_run_elide`` in ``fa.inner_loop.tools.run_bash``.

    Args:
        value: Value to render (string or JSON-serializable).
        preview_len: Maximum head length before truncation (default 500).

    Returns:
        Rendered string, possibly truncated with marker.

    Example:
        >>> truncate_for_preview("short text")
        'short text'
        >>> truncate_for_preview("x" * 1000)[:5]
        'xxxxx'
    """
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

# ── S12.7 (CT4/GAP6): bash tail-frame machinery ────────────────────────────
# Retention arithmetic (R16 lesson — never promise raw-byte whole windows):
# ceiling 32_768 - ~350B envelope scaffolding (keys/ids/flags) - escape
# headroom on shell text (~1.2x) ~= a 30_000B retained stdout tail. The
# envelope then renders under the ceiling and stays INLINE; the FULL stdout
# always goes to the artifact when trimmed. Anything that still overflows
# (huge stderr, escaping inflation) is framed by ``_bash_tail_frame`` at the
# projection chokepoint.
_RETAINED_TAIL_BYTES = 30_000
_BASH_FRAME_RESERVE = 128  # projection appends "\n\n[artifact: …]" after the frame


def _utf8_tail(text: str, max_bytes: int) -> str:
    """Last ``max_bytes`` of ``text``, utf-8-safe (never splits a codepoint)."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[-max_bytes:].decode("utf-8", errors="ignore")


def _retained_stdout(stdout: str) -> tuple[str, bool]:
    """Tail-biased retention within the ceiling. Returns (retained, truncated)."""
    if len(stdout.encode("utf-8")) <= _RETAINED_TAIL_BYTES:
        return stdout, False
    return _utf8_tail(stdout, _RETAINED_TAIL_BYTES), True


def _bash_tail_frame(value: Any, max_bytes: int) -> str:
    """Tail-biased bash frame for over-ceiling envelopes (S12.7 CT4).

    ``ToolElider`` protocol: called positionally as
    ``elider(result.result, spec.max_context_bytes)`` by the projection
    layer. Shape: header, then the stdout tail, then — LAST — the stderr
    block, so the error is always in the frame's final bytes when present
    (stderr-preserving invariant). stderr is capped at a quarter of the
    usable budget so a giant stderr cannot evict stdout entirely. Projection
    appends the ``[artifact: …]`` footer (the single id source).
    """
    if not isinstance(value, Mapping):
        return str(value)
    stdout = str(value.get("stdout", ""))
    stderr = str(value.get("stderr", ""))
    usable = max(0, max_bytes - _BASH_FRAME_RESERVE)
    header = f"[cmd out — TRUNCATED: showing last ~{usable}B of stdout — stderr at end]"

    stderr_block = ""
    if stderr:
        stderr_bytes = len(stderr.encode("utf-8"))
        stderr_budget = min(stderr_bytes, max(0, usable // 4))
        stderr_shown = _utf8_tail(stderr, stderr_budget) if stderr_budget < stderr_bytes else stderr
        stderr_block = f"\n[stderr — last {stderr_budget}B]\n{stderr_shown}"

    body_budget = usable - len(header.encode("utf-8")) - 1 - len(stderr_block.encode("utf-8"))
    stdout_tail = _utf8_tail(stdout, max(0, body_budget))
    return header + "\n" + stdout_tail + stderr_block
