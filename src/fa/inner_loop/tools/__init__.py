from __future__ import annotations

from pathlib import Path

from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.tools.read_file import build_read_file_tool
from fa.inner_loop.tools.run_bash import build_run_bash_tool
from fa.inner_loop.tools.write_file import build_write_file_tool


def build_baseline_registry(workspace_root: Path) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(build_read_file_tool(workspace_root))
    registry.register(build_write_file_tool(workspace_root))
    registry.register(build_run_bash_tool(workspace_root))
    return registry


__all__ = [
    "build_baseline_registry",
    "build_read_file_tool",
    "build_run_bash_tool",
    "build_write_file_tool",
]
