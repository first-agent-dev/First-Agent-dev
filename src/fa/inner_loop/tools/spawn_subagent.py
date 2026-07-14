"""fs.spawn_subagent — spawns a cheap, isolated, stateless subagent.

ADR-14, ADR-15 Phase 3:
- Strictly gated by feature_flags.subagent_spawning_enabled
- Instantiates SubagentRunner and runs stateless commands
- Graceful cleanup and envelope validation
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string

logger = logging.getLogger(__name__)


def build_spawn_subagent_tool(session_root: Path) -> ToolSpec:
    root = Path(session_root).resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        # 1. Verify Feature Flag via SessionState
        from fa.inner_loop.context import get_current_session

        session = get_current_session()
        enabled = False
        try:
            if session is not None and session.feature_flags is not None:
                enabled = getattr(session.feature_flags, "subagent_spawning_enabled", False)
        except AttributeError as exc:  # best-effort flag check
            logger.warning("subagent_spawning_enabled flag check failed: %s", exc)

        if not enabled:
            return ToolResult.fail(
                "disabled",
                "Subagent spawning is disabled under current feature flags. "
                "Enable 'subagent_spawning_enabled: true' in config.yaml to use.",
                retryable=False,
            )

        # 2. Extract and Validate Input
        try:
            task_id = require_string(params, "task_id")
            command = require_string(params, "command")
            role = str(params.get("role", "verifier"))
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        # 3. Create isolated Worktree via SessionState
        workdir = root
        if session is not None:
            try:
                workdir = session.create_subagent_workspace(task_id)
            except Exception as exc:  # noqa: BLE001 # graceful fallback
                logger.warning("Subagent workspace creation failed: %s, using session_root", exc)

        # 4. Instantiate and Execute SubagentRunner
        try:
            from fa.inner_loop.subagent_runner import SubagentRunner

            runner = SubagentRunner(session_root=root, timeout=60)
            envelope = runner.run_stateless(
                task_id=task_id,
                command=command,
                role=role,
                workdir=workdir,
            )

            # 5. Cleanup Worktree
            if session is not None and workdir != root:
                session.cleanup_subagent_workspace(workdir)

            if envelope.exit_code != 0:
                summary_err = (
                    f"Subagent {task_id} failed with exit_code {envelope.exit_code}. "
                    f"Summary: {envelope.summary}"
                )
                return ToolResult.fail(
                    "subagent_failed",
                    summary_err,
                    result=envelope.to_json(),
                    retryable=True,
                )

            return ToolResult.ok(
                f"Subagent {task_id} completed successfully.",
                result=envelope.to_json(),
            )

        except Exception as exc:  # noqa: BLE001 # safe sandbox boundary
            logger.error("Stateless subagent runner encountered unhandled error: %s", exc)
            if session is not None and workdir != root:
                try:
                    session.cleanup_subagent_workspace(workdir)
                except Exception:  # noqa: BLE001, S110 # best-effort cleanup
                    pass
            return ToolResult.fail("runner_failed", str(exc), retryable=False)

    return ToolSpec(
        name="fs.spawn_subagent",
        description="Spawns an isolated, cheap, stateless subagent in a separate workspace worktree.",
        input_schema={
            "type": "object",
            "required": ["task_id", "command"],
            "properties": {
                "task_id": {"type": "string", "description": "Unique task identifier"},
                "command": {"type": "string", "description": "Command to execute inside subagent"},
                "role": {"type": "string", "enum": ["verifier", "researcher"], "default": "verifier"},
            },
        },
        permission="workspace",
        handler=handler,
        tags=("fs", "spawn"),
    )


__all__ = ["build_spawn_subagent_tool"]
