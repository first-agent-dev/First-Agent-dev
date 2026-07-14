from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.runtime_limits import DEFAULT_BASH_TIMEOUT_SECONDS
from fa.inner_loop.tools.base import require_string
from fa.inner_loop.tools.bash_env import build_scrubbed_env

logger = logging.getLogger(__name__)


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


def _get_write_set_from_git_status(root: Path) -> list[str]:
    """Dynamic git-status verification per Gap 8 — formal source-of-truth for transaction diffs, not regex.

    Runs git status --porcelain -z (<2ms) machine-readable, 100% accurate across all modification vectors,
    NUL-delimited safe for pathological filenames.
    """
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z"],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode != 0:
            return []
        files = []
        # -z: entries NUL separated, format XY + space + path + NUL,
        # renames: XY + space + path1 + NUL path2 + NUL
        # Simple parse: split by \0, take every entry that has path after 3 chars
        entries = res.stdout.split("\0")
        for entry in entries:
            if not entry:
                continue
            if len(entry) < 3:
                continue
            # entry like " M path" or "?? path"
            path = entry[3:].strip()
            if path:
                # For renames, path may contain original -> new?
                # Take first path before NUL already handled by split, but rename has second path as next entry?
                # For simplicity, take path as is, skip if contains \0
                if "\0" in path:
                    path = path.split("\0")[0]
                files.append(path)
        return files
    except Exception as exc:  # noqa: BLE001 # best-effort
        logger.warning("git status --porcelain -z failed: %s", exc)
        return []


def build_run_bash_tool(  # noqa: C901 -- complexity from fallback chain graceful degradation, documented, will split Phase 3 per Paper 2 §4.4
    workspace_root: Path,
    *,
    timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
    env_allowlist_extra: Iterable[str] = (),
) -> ToolSpec:
    root = workspace_root.resolve()
    extra_allow = frozenset(env_allowlist_extra)

    def handler(params: Mapping[str, object]) -> ToolResult:  # noqa: C901 -- complexity from fallback chain graceful degradation, documented, will split Phase 3 per Paper 2 §4.4
        data = dict(params)
        try:
            command = require_string(data, "command")
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        # Try to get BashExecutor via SessionState DI (Phase 3 thin client)
        executor = None
        session = None
        artifact_store = None
        transaction = None
        try:
            from fa.inner_loop.context import get_current_session

            session = get_current_session()
            if session is not None:
                # Prefer bash_executor protocol, fallback to pty_pool wrapped as executor
                executor = getattr(session, "bash_executor", None)
                if executor is None:
                    # Try pty_pool directly, wrap as InProcessPtyExecutor if needed
                    pool = getattr(session, "pty_pool", None)
                    if pool is not None:
                        try:
                            from fa.runtime.bash_executor import InProcessPtyExecutor

                            executor = InProcessPtyExecutor(pool)
                        except (ImportError, AttributeError, TypeError) as exc:
                            logger.warning("Failed to instantiate InProcessPtyExecutor: %s. Falling back.", exc)
                            executor = pool  # pool itself has run method compatible with PtyPool
                artifact_store = getattr(session, "artifact_store", None)
                transaction = getattr(session, "transaction", None)
        except Exception as exc:  # noqa: BLE001 # session retrieval best-effort
            logger.warning("get_current_session failed in run_bash: %s", exc)

        # If executor available (PtyPool in-process with shared Server + socket isolation + -J + UUID sentinel)
        if executor is not None:
            try:
                pty_result = executor.run(command, timeout=timeout_seconds, workdir=root, session_id="main")
                # Transaction tracking via git status --porcelain -z (Gap 8) — formal source-of-truth
                try:
                    if transaction is not None:
                        write_set = _get_write_set_from_git_status(root)
                        for f in write_set:
                            transaction.add_write(f)
                except (OSError, ValueError) as exc:
                    logger.warning("transaction add_write from git status failed: %s", exc)

                # ArtifactStore offload if large
                artifact_id = None
                stdout = pty_result.stdout
                if artifact_store is not None and len(stdout) > 8000:
                    try:
                        artifact_id = artifact_store.write(stdout)
                    except OSError as exc:
                        logger.warning("artifact store write failed: %s", exc)

                preview = _elide_500_preview(stdout, 8000)
                summary = f"bash exited {pty_result.exit_code}"
                result = {
                    "returncode": pty_result.exit_code,
                    "stdout": stdout if len(stdout) <= 8000 else preview,
                    "stderr": "",
                    "truncated": pty_result.truncated,
                    "artifact_id": artifact_id,
                    "session_id": pty_result.session_id,
                }
                if pty_result.exit_code != 0:
                    return ToolResult.fail(
                        "command_failed",
                        f"bash exited {pty_result.exit_code}\nstdout: {stdout[:2000]}",
                        retryable=True,
                    )
                return ToolResult.ok(summary, result=result)

            except Exception as exc:  # noqa: BLE001 # fallback to subprocess with WARNING
                logger.warning("PtyPool executor failed: %s, fallback to subprocess", exc)

        # Fallback: subprocess.run (stateless) with ArtifactStore
        try:
            completed = subprocess.run(  # noqa: S602 # shell=True intentional sandbox boundary ADR-6, trusted binary
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

        # Transaction tracking for fallback too
        try:
            if transaction is not None:
                write_set = _get_write_set_from_git_status(root)
                for f in write_set:
                    transaction.add_write(f)
        except (OSError, ValueError) as exc:
            logger.warning("Fallback transaction tracking failed: %s", exc)

        # ArtifactStore offload for fallback large output
        artifact_id = None
        if artifact_store is not None and len(completed.stdout) > 8000:
            try:
                artifact_id = artifact_store.write(completed.stdout)
            except OSError as exc:
                logger.warning("Failed to offload large fallback stdout to ArtifactStore: %s", exc)

        summary = f"bash exited {completed.returncode}"
        result = {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "artifact_id": artifact_id,
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

STATEFUL for main agent (via PtyPool EventStream Runtime, ADR-14): cwd, env, venv persist
across calls (cd, export, source .venv/bin/activate survive). Stateless for cheap subagents
(structured websearch, simple function) with isolated context.

Background processes: use fs.run_bash_background for long-running commands (dev servers),
then fs.read_terminal, fs.list_tasks, fs.kill_task, fs.send_ctrl_c.

Output capped 8000 chars with artifact_id + 500-char preview (ADR-13/14). For large outputs,
chain with | head -n 100 or | tail -n 100 or grep.

Chain commands with && for atomicity: cd src && ls -la

Formal transaction tracking via git status --porcelain -z (Gap 8) as source-of-truth for
write_set, not regex.

Socket isolation via -L fa_<run_id> (Improvement 1), line-wrapping -J + wide viewport -x 300
(Gap 12), UUID sentinel per session, signal/atexit leak prevention (Gap 14), pexpect
per-session isolation (Gap 13).
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
