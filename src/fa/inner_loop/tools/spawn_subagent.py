"""fs.spawn_subagent — spawns a cheap, isolated, stateless subagent.

ADR-14, ADR-15 Phase 3:
- Strictly gated by feature_flags.subagent_spawning_enabled
- Instantiates SubagentRunner and runs stateless commands
- Graceful cleanup and envelope validation
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string
from fa.output import EventType, LogKind

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _SpawnRequest:
    task_id: str
    command: str
    role: str
    env_extra: dict[str, str] | None


def _parse_spawn_request(params: Mapping[str, object]) -> _SpawnRequest | ToolResult:
    """Validate task/role/env input and enforce secret-name filtering."""
    try:
        task_id = require_string(params, "task_id")
        command = require_string(params, "command")
        role = str(params.get("role", "verifier"))
        env_raw = params.get("env")
        env_extra: dict[str, str] | None = None
        if env_raw is not None:
            if not isinstance(env_raw, dict):
                return ToolResult.fail("invalid_params", "env must be an object map string->string", retryable=True)
            from fa.inner_loop.tools.bash_env import SECRET_NAME_RE

            env_extra = {}
            for key, value in env_raw.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    return ToolResult.fail("invalid_params", "env keys and values must be strings", retryable=True)
                if SECRET_NAME_RE.search(key):
                    return ToolResult.fail(
                        "invalid_params", f"env key {key!r} looks like secret and is denied", retryable=False
                    )
                env_extra[key] = value
        return _SpawnRequest(task_id, command, role, env_extra)
    except ValueError as exc:
        return ToolResult.fail("invalid_params", str(exc), retryable=True)


def _emit_subagent_event(session: Any, event_type: EventType, data: dict[str, object]) -> None:
    """Best-effort EventBus emission; listener failures never block the tool."""
    output_bus = session.output_bus if session is not None else None
    if output_bus is not None:
        from fa.output import OutputEvent

        output_bus.emit(OutputEvent(type=event_type, data=data))


def _record_subagent_completion(session: Any, task_id: str, role: str, envelope: Any) -> None:
    """Persist and display a completed/failed subagent envelope."""
    if session is not None and session.log is not None:
        kind: LogKind = "subagent_spawn_done" if envelope.exit_code == 0 else "subagent_spawn_fail"
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
    _emit_subagent_event(
        session,
        "subagent_end",
        {
            "task_id": task_id,
            "role": role,
            "exit_code": envelope.exit_code,
            "duration_ms": envelope.duration_ms,
            "ok": envelope.exit_code == 0,
        },
    )


def _handle_subagent_runner_error(
    session: Any,
    root: Path,
    workdir: Path,
    task_id: str,
    role: str,
    exc: Exception,
) -> ToolResult:
    """Record, display, clean up, and return a structured runner failure."""
    logger.error("Stateless subagent runner encountered unhandled error: %s", exc)
    if session is not None and session.log is not None:
        try:
            session.log.append(
                actor="tool",
                kind="subagent_spawn_fail",
                content={"task_id": task_id, "role": role, "error": str(exc)},
                tool_name="fs.spawn_subagent",
            )
        except Exception as log_exc:  # noqa: BLE001 - best-effort observability logging
            logger.warning("Failed to log subagent failure: %s", log_exc)
    try:
        _emit_subagent_event(
            session,
            "subagent_end",
            {"task_id": task_id, "role": role, "exit_code": -1, "ok": False, "error": str(exc)},
        )
    except Exception as emit_exc:  # noqa: BLE001 - best-effort observability
        logger.warning("Failed to emit subagent failure event: %s", emit_exc)
    if session is not None:
        # Cleanup failure is surfaced by SessionState (V20) but must not mask
        # the original runner error being reported here.
        try:
            session.cleanup_subagent_workspace(workdir)
        except Exception as cleanup_exc:  # noqa: BLE001 - original error takes precedence
            logger.warning("Subagent workspace cleanup failed: %s", cleanup_exc)
    return ToolResult.fail("runner_failed", str(exc), retryable=False)


def _handle_spawn_subagent(root: Path, params: Mapping[str, object]) -> ToolResult:
    # 1. Verify Feature Flag via SessionState
    from fa.inner_loop.context import get_current_session

    session = get_current_session()
    enabled = False
    try:
        if session is not None and session.feature_flags is not None:
            # S13: FAIL-OPEN — subagent_spawning_enabled defaults to False (don't spawn when unconfigured)
            enabled = session.feature_flags.subagent_spawning_enabled if session.feature_flags is not None else False
    except AttributeError as exc:  # best-effort flag check
        logger.warning("subagent_spawning_enabled flag check failed: %s", exc)

    if not enabled:
        return ToolResult.fail(
            "disabled",
            "Subagent spawning is disabled under current feature flags. "
            "Enable 'subagent_spawning_enabled: true' in config.yaml to use.",
            retryable=False,
        )

    # 2. Extract and validate input
    request = _parse_spawn_request(params)
    if isinstance(request, ToolResult):
        return request
    task_id = request.task_id
    command = request.command
    role = request.role
    env_extra = request.env_extra

    # 3. Allocate the per-task artifact root (Q11-B Option A).
    # V18: if it cannot be created the spawn is DENIED. The previous code
    # logged the failure and fell back to ``root`` — the main workspace — which
    # turned an isolation failure into a permission escalation.
    if session is None:
        return ToolResult.fail(
            "no_active_session",
            "Subagent spawning requires an active session to allocate an artifact root.",
            retryable=False,
        )
    try:
        workdir = session.create_subagent_workspace(task_id)
    except Exception as exc:  # noqa: BLE001 - structured denial, never a fallback
        logger.warning("Subagent artifact root unavailable for %s: %s", task_id, exc)
        return ToolResult.fail("workspace_unavailable", str(exc), retryable=True)

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

    # FIX-3: emit subagent_start OutputEvent for console visibility.
    if session is not None:
        try:
            _emit_subagent_event(
                session,
                "subagent_start",
                {"task_id": task_id, "role": role, "command_preview": command[:200]},
            )
        except Exception as exc:  # noqa: BLE001 - best-effort observability
            logger.warning("Failed to emit subagent_start OutputEvent: %s", exc)

    # 5. Instantiate and Execute SubagentRunner
    try:
        from fa.inner_loop.subagent_runner import SubagentRunner

        # S6.5 / Q25(i): reuse the redactor the EventLog already applies, so
        # subagent output is masked by the same policy as the trace. None is a
        # supported configuration and degrades to no masking.
        runner = SubagentRunner(
            session_root=root,
            timeout=60,
            redactor=session.log.redactor if session.log is not None else None,
        )
        envelope = runner.run_stateless(
            task_id=task_id,
            command=command,
            role=role,
            workdir=workdir,
            env_extra=env_extra,
        )

        # 6. Remove the task artifact directory. A failure here raises (V20)
        # rather than leaving a dir the next task with this id would reuse.
        session.cleanup_subagent_workspace(workdir)

        # 7. Persist and display completion/failure.
        try:
            _record_subagent_completion(session, task_id, role, envelope)
        except Exception as exc:  # noqa: BLE001 - best-effort observability
            logger.warning("Failed to record subagent completion: %s", exc)

        if envelope.exit_code != 0:
            summary_err = f"Subagent {task_id} failed with exit_code {envelope.exit_code}. Summary: {envelope.summary}"
            return ToolResult.fail(
                "subagent_failed",
                f"{summary_err} | envelope={envelope.to_json()[:500]}",
                retryable=True,
            )

        return ToolResult.ok(
            f"Subagent {task_id} completed successfully.",
            result=envelope.to_json(),
        )

    except Exception as exc:  # noqa: BLE001 - safe sandbox boundary
        return _handle_subagent_runner_error(session, root, workdir, task_id, role, exc)


def build_spawn_subagent_tool(session_root: Path) -> ToolSpec:
    """Build the role-gated, isolated subagent tool."""
    root = Path(session_root).resolve()

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
                    "description": (
                        "Role affects envelope type and future behavior; both run bash stateless per operator decision"
                    ),
                },
                "env": {
                    "type": "object",
                    "description": (
                        "Optional extra env vars for subagent (string->string, secret names denied fail-closed)"
                    ),
                    "additionalProperties": {"type": "string"},
                },
            },
        },
        permission="workspace",
        handler=lambda params: _handle_spawn_subagent(root, params),
        tags=("fs", "spawn"),
    )


__all__ = ["build_spawn_subagent_tool"]
