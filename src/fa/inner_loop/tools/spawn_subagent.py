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
            # Optional env injection — explicit map[str,str] for subagent
            env_raw = params.get("env")
            env_extra: dict[str, str] | None = None
            if env_raw is not None:
                if not isinstance(env_raw, dict):
                    return ToolResult.fail(
                        "invalid_params", "env must be an object map string->string", retryable=True
                    )
                env_extra = {}
                for k, v in env_raw.items():
                    if not isinstance(k, str) or not isinstance(v, str):
                        return ToolResult.fail(
                            "invalid_params", "env keys and values must be strings", retryable=True
                        )
                    # Fail-closed secret filter on env key name
                    from fa.inner_loop.tools.bash_env import SECRET_NAME_RE

                    if SECRET_NAME_RE.search(k):
                        return ToolResult.fail(
                            "invalid_params", f"env key {k!r} looks like secret and is denied", retryable=False
                        )
                    env_extra[k] = v
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        # 3. Create isolated Worktree via SessionState
        workdir = root
        if session is not None:
            try:
                workdir = session.create_subagent_workspace(task_id)
            except Exception as exc:  # noqa: BLE001 # graceful fallback
                logger.warning("Subagent workspace creation failed: %s, using session_root", exc)

        # 4. Log spawn start event (observability per Slice5)
        if session is not None and session.log is not None:
            try:
                session.log.append(
                    actor="tool",
                    kind="subagent_spawn_start",
                    content={
                        "task_id": task_id,
                        "role": role,
                        "command_preview": command[:500],
                        "workdir": str(workdir),
                        "env_keys": list((env_extra or {}).keys()),
                    },
                    tool_name="fs.spawn_subagent",
                )
            except Exception as exc:  # noqa: BLE001 - best-effort observability
                logger.warning("Failed to log subagent_spawn_start: %s", exc)

        # 5. Instantiate and Execute SubagentRunner
        try:
            from fa.inner_loop.subagent_runner import SubagentRunner

            runner = SubagentRunner(session_root=root, timeout=60)
            envelope = runner.run_stateless(
                task_id=task_id,
                command=command,
                role=role,
                workdir=workdir,
                env_extra=env_extra,
            )

            # 6. Cleanup Worktree
            if session is not None and workdir != root:
                session.cleanup_subagent_workspace(workdir)

            # 7. Log spawn done/fail events
            if session is not None and session.log is not None:
                try:
                    kind = "subagent_spawn_done" if envelope.exit_code == 0 else "subagent_spawn_fail"
                    session.log.append(
                        actor="tool",
                        kind=kind,
                        content={
                            "task_id": task_id,
                            "role": role,
                            "exit_code": envelope.exit_code,
                            "duration_ms": envelope.duration_ms,
                            "verification": envelope.verification,
                        },
                        tool_name="fs.spawn_subagent",
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to log subagent_spawn_done/fail: %s", exc)

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
            if session is not None and session.log is not None:
                try:
                    session.log.append(
                        actor="tool",
                        kind="subagent_spawn_fail",
                        content={"task_id": task_id, "role": role, "error": str(exc)},
                        tool_name="fs.spawn_subagent",
                    )
                except Exception:
                    pass
            if session is not None and workdir != root:
                try:
                    session.cleanup_subagent_workspace(workdir)
                except Exception:  # noqa: BLE001, S110 # best-effort cleanup
                    pass
            return ToolResult.fail("runner_failed", str(exc), retryable=False)

    return ToolSpec(
        name="fs.spawn_subagent",
        description=(
            "Spawns an isolated, cheap, stateless subagent in a separate workspace worktree. "
            "Role-bounded (verifier=verification, researcher=read-only+web search future), "
            "stateless, limited-function, safety-equivalent to parent shell (sandbox/intent/secret). "
            "Env injection optional but secret-filtered fail-closed."
        ),
        input_schema={
            "type": "object",
            "required": ["task_id", "command"],
            "properties": {
                "task_id": {"type": "string", "description": "Unique task identifier"},
                "command": {"type": "string", "description": "Command to execute inside subagent"},
                "role": {
                    "type": "string",
                    "enum": ["verifier", "researcher"],
                    "default": "verifier",
                    "description": "Role affects envelope type and future behavior; both run bash stateless per operator decision",
                },
                "env": {
                    "type": "object",
                    "description": "Optional extra env vars for subagent (string->string, secret names denied fail-closed)",
                    "additionalProperties": {"type": "string"},
                },
            },
        },
        permission="workspace",
        handler=handler,
        tags=("fs", "spawn"),
    )


__all__ = ["build_spawn_subagent_tool"]
