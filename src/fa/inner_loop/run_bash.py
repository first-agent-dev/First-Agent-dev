from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.runtime_limits import DEFAULT_BASH_TIMEOUT_SECONDS
from fa.inner_loop.tools.base import require_string
from fa.inner_loop.tools.bash_env import build_scrubbed_env


def _elide_500_preview(value: Any, max_bytes: int) -> str:
    """Elide to 500-char preview + marker, for token efficiency (Stage 0)."""
    import json

    if isinstance(value, str):
        rendered = value
    else:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=repr)
    preview_len = 500
    if len(rendered) <= preview_len:
        return rendered
    return (
        rendered[:preview_len]
        + f"\n...[truncated {len(rendered)} chars, use | head -n 100 or grep to reduce, full in artifact]...\n"
        + rendered[-200:]
    )


def build_run_bash_tool(
    workspace_root: Path,
    *,
    timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
    env_allowlist_extra: Iterable[str] = (),
) -> ToolSpec:
    root = workspace_root.resolve()
    extra_allow = frozenset(env_allowlist_extra)

    def handler(params: Mapping[str, object]) -> ToolResult:
        data = dict(params)
        try:
            command = require_string(data, "command")
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        try:
            completed = subprocess.run(  # noqa: S602
                command,
                cwd=root,
                # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
                # intentional sandbox boundary (ADR-6)
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=build_scrubbed_env(os.environ, extra_allow=extra_allow),
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
        description="""Run a bash command in the workspace after sandbox hooks allow it.

STATEFUL for main agent (via PtyPool EventStream Runtime, ADR-14): cwd, env, and venv
persist across calls (cd, export, and source .venv/bin/activate survive). Stateless for cheap
subagents (structured websearch, simple function) with isolated context.

Background processes: use fs.run_bash_background for long-running commands (dev servers),
then fs.read_terminal, fs.list_tasks, fs.kill_task, and fs.send_ctrl_c.

Output capped at 8000 chars with artifact_id plus a 500-character preview (ADR-13/14).
For large outputs, chain with | head -n 100, | tail -n 100, or grep.

Chain commands with && for atomicity: cd src && ls -la
""",
        input_schema={
            "type": "object",
            "required": ["command"],
            "properties": {"command": {"type": "string"}},
        },
        permission="workspace",
        handler=handler,
        tags=("fs", "bash"),
        max_context_bytes=8000,
        elide=_elide_500_preview,
    )


__all__ = ["build_run_bash_tool"]
