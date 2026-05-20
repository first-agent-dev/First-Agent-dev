from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string


def build_run_bash_tool(workspace_root: Path) -> ToolSpec:
    root = workspace_root.resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        data = dict(params)
        try:
            command = require_string(data, "command")
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        completed = subprocess.run(
            command,
            cwd=root,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        summary = f"bash exited {completed.returncode}"
        result = {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        if completed.returncode != 0:
            return ToolResult.fail(
                "command_failed",
                summary,
                retryable=True,
            )
        return ToolResult.ok(summary, result=result)

    return ToolSpec(
        name="fs.run_bash",
        description="Run a bash command in the workspace after sandbox hooks allow it.",
        input_schema={
            "type": "object",
            "required": ["command"],
            "properties": {"command": {"type": "string"}},
        },
        permission="workspace",
        handler=handler,
        tags=("fs", "bash"),
    )


__all__ = ["build_run_bash_tool"]
