from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.runtime_limits import DEFAULT_BASH_TIMEOUT_SECONDS
from fa.inner_loop.tools.base import require_string


def build_run_bash_tool(
    workspace_root: Path,
    *,
    timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
) -> ToolSpec:
    """Build the ``fs.run_bash`` ToolSpec.

    ``timeout_seconds`` defaults to the documented anchor (30 s) so the
    smoke entrypoint runs cleanly. The deterministic loop driver passes
    the user-configured value from ``RuntimeLimits.bash_timeout_seconds``
    (ADR-7 \u00a7Amendment 2026-05-20 rule 1: caps live in
    ``~/.fa/config.yaml``, never in code constants).
    """

    root = workspace_root.resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        data = dict(params)
        try:
            command = require_string(data, "command")
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        try:
            completed = subprocess.run(
                command,
                cwd=root,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return ToolResult.fail(
                "command_timeout",
                f"bash command timed out after {timeout_seconds}s",
                retryable=True,
            )

        summary = f"bash exited {completed.returncode}"
        result = {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        if completed.returncode != 0:
            detail = f"bash exited {completed.returncode}"
            if completed.stderr:
                detail += f"\nstderr: {completed.stderr[:2000]}"
            if completed.stdout:
                detail += f"\nstdout: {completed.stdout[:2000]}"
            return ToolResult.fail(
                "command_failed",
                detail,
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
