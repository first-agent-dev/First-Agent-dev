from __future__ import annotations

from pathlib import Path

from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.runtime_limits import DEFAULT_BASH_TIMEOUT_SECONDS
from fa.inner_loop.tools.prepare_pr import build_prepare_pr_tool
from fa.inner_loop.tools.read_file import build_read_file_tool
from fa.inner_loop.tools.run_bash import build_run_bash_tool
from fa.inner_loop.tools.write_file import build_write_file_tool


def build_baseline_registry(
    workspace_root: Path,
    *,
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
) -> ToolRegistry:
    """Register the three M-1 baseline tools (``fs.read_file`` / ``fs.write_file``
    / ``fs.run_bash``) against a fresh :class:`ToolRegistry`.

    ``bash_timeout_seconds`` is plumbed through to the bash tool so the
    cap comes from ``~/.fa/config.yaml`` rather than a code constant.
    """

    registry = ToolRegistry()
    registry.register(build_read_file_tool(workspace_root))
    registry.register(build_write_file_tool(workspace_root))
    registry.register(build_run_bash_tool(workspace_root, timeout_seconds=bash_timeout_seconds))
    return registry


def build_planner_registry(
    workspace_root: Path,
    *,
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
) -> ToolRegistry:
    """Planner/Architect role: read-only tools only.

    The planner analyses the codebase and produces plans — it does NOT
    mutate workspace files. ``fs.write_file`` is deliberately absent.
    ``fs.run_bash`` is available for reconnaissance (read-only commands).
    """
    registry = ToolRegistry()
    registry.register(build_read_file_tool(workspace_root))
    registry.register(build_run_bash_tool(workspace_root, timeout_seconds=bash_timeout_seconds))
    return registry


def build_eval_registry(
    workspace_root: Path,
    *,
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
) -> ToolRegistry:
    """Eval/Reviewer role: read-only tools only.

    The evaluator verifies completed work — it does NOT mutate workspace
    files except to update the work log via ``pr.prepare`` (added separately
    by the CLI in ``_cmd_run``). ``fs.run_bash`` is available for running
    tests, linters, and other verification commands.
    """
    registry = ToolRegistry()
    registry.register(build_read_file_tool(workspace_root))
    registry.register(build_run_bash_tool(workspace_root, timeout_seconds=bash_timeout_seconds))
    return registry


__all__ = [
    "build_baseline_registry",
    "build_eval_registry",
    "build_planner_registry",
    "build_prepare_pr_tool",
    "build_read_file_tool",
    "build_run_bash_tool",
    "build_write_file_tool",
]
