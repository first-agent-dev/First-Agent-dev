"""
SubagentRunner — stateless subagents with filtered history, JSON envelope validation, proxy_token foundation
ADR-14, ADR-15, Phase 1 Foundation: uses extracted SubagentEnvelope, spawn limit via SessionState

Prior art:
- OpenAI Sandbox Agents as Tools custom_output_extractor JSON
- Copilot CustomAgents isolated context
- LangChain subagents pattern supervisor maintains context, subagents stateless isolated

Design: Main holds PTY stateful, sub stateless subprocess.run isolated, structured JSON via fastjsonschema  # noqa: S603, S607 -- trusted binary per ADR-6, list args, no shell
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import fastjsonschema

from fa.inner_loop.subagent_envelope import (
    SubagentEnvelope,
    validate_envelope,
    write_envelope_artifact,
)


class SubagentRunner:
    """
    Stateless subagent runner with filtered history, JSON envelope, proxy_token foundation
    Phase 1: spawn limit enforced via SessionState counter (not instance counter), filtered history
    """

    def __init__(
        self,
        session_root: Path,
        proxy_token: str | None = None,
        timeout: int = 30,
        limits: Any | None = None,  # RuntimeLimits
    ):
        self.session_root = Path(session_root).resolve()
        self.proxy_token = proxy_token
        self.timeout = timeout
        self.validator = validate_envelope
        self.limits = limits
        # For backward compat, keep instance counter but prefer SessionState counter
        self._instance_spawn_count = 0

    def _get_limits(self) -> Any:
        if self.limits is not None:
            return self.limits
        try:
            from fa.inner_loop.runtime_limits import RuntimeLimits

            return RuntimeLimits.anchored_defaults()
        except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return None

    def _check_spawn_limit(self) -> None:
        """Enforce max_subagent_spawns_per_session via SessionState if available."""
        # Try SessionState counter first (production-grade)
        try:
            from fa.inner_loop.context import get_current_session

            session = get_current_session()
            if session is not None:
                count = getattr(session, "subagent_spawns", 0)
                limits = self._get_limits()
                max_spawns = getattr(limits, "max_subagent_spawns_per_session", 3) if limits else 3
                if count >= max_spawns:
                    raise RuntimeError(
                        f"Subagent spawn limit {max_spawns} reached (current {count}), "
                        f"1 subagent sequential limit for v0.1 pair over autonomy"
                    )
                try:
                    if hasattr(session, "increment_subagent_spawns"):
                        session.increment_subagent_spawns()  # type: ignore
                    else:
                        session.subagent_spawns = count + 1
                except Exception as exc:  # noqa: BLE001 - increment best-effort
                    print(f"WARNING: increment_subagent_spawns failed: {exc}")
                return
        except RuntimeError:
            # Re-raise intentional limit errors, don't fallback
            raise
        except Exception as exc:  # noqa: BLE001 - graceful fallback to instance counter
            print(f"WARNING: Failed to check SessionState spawn counter: {exc}, using instance counter")

        # Fallback instance counter (when no SessionState)
        limits = self._get_limits()
        max_spawns = getattr(limits, "max_subagent_spawns_per_session", 3) if limits else 3
        if self._instance_spawn_count >= max_spawns:
            raise RuntimeError(f"Subagent spawn limit {max_spawns} reached (instance counter)")
        self._instance_spawn_count += 1

    def run_stateless(
        self,
        task_id: str,
        command: str,
        role: str = "verifier",
        workdir: Path | None = None,
        env_extra: dict[str, str] | None = None,
    ) -> SubagentEnvelope:
        """
        Stateless subprocess.run isolated, scrubbed env, no PTY state.  # noqa: S603, S607 -- trusted binary per ADR-6, list args, no shell
        Returns validated SubagentEnvelope.

        workdir: from WorktreeManager.create_subagent_workspace(task_id)
        Filtered history: not full parent 124 steps, only task + relevant files
        """
        # Enforce spawn limit before execution
        self._check_spawn_limit()

        cwd = Path(workdir) if workdir else self.session_root
        assert cwd.exists() and cwd.is_dir(), f"workdir {cwd} not exists"  # noqa: S101 # internal invariant, not security, fail-fast per Gap 6 defensive checks

        import os

        from .tools.bash_env import build_scrubbed_env

        env = build_scrubbed_env(os.environ, extra_allow=frozenset(env_extra or {}))

        if self.proxy_token:
            env["X_FA_PROXY_TOKEN"] = self.proxy_token

        start = time.time()
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            exit_code = completed.returncode
            output = (stdout + "\n" + stderr) if stderr else stdout
            if len(output) > 8000:
                output = output[:8000] + "\n...[truncated 8000]"
        except subprocess.TimeoutExpired as e:
            stdout = (
                (e.stdout.decode() if e.stdout else "") if isinstance(e.stdout, bytes) else (e.stdout or "")
            )
            exit_code = -1
            output = f"Timeout {self.timeout}s, partial:\n{stdout[:8000]}"
        duration_ms = int((time.time() - start) * 1000)

        envelope = SubagentEnvelope.from_verifier(
            task_id=task_id,
            exit_code=exit_code,
            stdout=output,
            duration_ms=duration_ms,
        )

        try:
            self.validator(asdict(envelope))
        except fastjsonschema.JsonSchemaValueException as exc:
            return SubagentEnvelope(
                task_id=task_id,
                type=role,
                goal=f"Verify {task_id}",
                exit_code=-1,
                summary=f"Envelope validation failed: {exc.message}",
                verification=f"validation error at {exc.path}",
                files_changed=[],
                patch_diff="",
                risks=["envelope validation failed"],
                open_questions=[],
                token_usage={},
                duration_ms=duration_ms,
                next_action="retry",
            )

        # Write artifact .fa/subagents/<id>.json per task completion
        try:
            write_envelope_artifact(envelope, self.session_root)
        except Exception as exc:  # noqa: BLE001 - artifact write best-effort
            print(f"WARNING: Failed to write subagent artifact for {task_id}: {exc}")

        return envelope
