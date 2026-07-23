from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.runtime_limits import DEFAULT_BASH_TIMEOUT_SECONDS
from fa.inner_loop.tools._common import prepare_workspace_context, truncate_for_preview, validate_bash_command
from fa.inner_loop.tools.bash_env import build_scrubbed_env

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _Completed:
    """Normalized subprocess output after decoding bytes."""

    stdout: str
    stderr: str
    returncode: int


def _normalize_carriage_return(text: str) -> str:
    """Normalize CR artifacts from PTY / progress-bar outputs.

    Delegates to fa.runtime.pty_pool.resolve_cr for single source of truth (FIND-016).
    Examples: foo\\rbar\\n -> bar, 12%\\r34%\\r56% -> 56%
    """
    try:
        from fa.runtime.pty_pool import resolve_cr

        return resolve_cr(text)
    except Exception:  # noqa: BLE001 — optional PTY normalizer must fall back safely
        text = text.replace("\r\n", "\n")
        cleaned_lines = []
        for line in text.split("\n"):
            if "\r" in line:
                line = line.split("\r")[-1]
            cleaned_lines.append(line)
        result = "\n".join(cleaned_lines)
        if result.endswith("\n") and text.endswith("\n"):
            result = result[:-1]
        return result


def _bash_run_elide(value: Any, _max_bytes: int) -> str:
    """Adapt ``truncate_for_preview`` to the ``ToolElider`` protocol.

    ``ToolElider`` is ``Callable[[value, max_context_bytes], str]`` and
    ``ToolRegistry``'s projection layer calls it POSITIONALLY as
    ``elider(result, spec.max_context_bytes)``. ``truncate_for_preview``'s
    own second positional parameter is ``preview_len`` — passing it
    directly as ``elide=truncate_for_preview`` would silently bind the
    tool's context budget (thousands of bytes) into ``preview_len``,
    producing a preview an order of magnitude larger than the intended
    fixed 500-char head + 200-char tail shape and losing the truncation
    notice (this exact regression shipped once; see
    tests/test_run_bash_tool_projection.py for the kill-check).

    ``_max_bytes`` (the tool's ``max_context_bytes``) is intentionally
    unused here: fs.run_bash's preview length is a fixed token-budget
    constant (500+200), not proportional to the tool's overall budget.
    """
    return truncate_for_preview(value, preview_len=500)


def _get_write_set_from_git_status(root: Path) -> list[str]:
    """Dynamic git-status verification per Gap 8 — formal source-of-truth for transaction diffs, not regex."""
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
        entries = res.stdout.split("\0")
        for entry in entries:
            if not entry:
                continue
            if len(entry) < 3:
                continue
            path = entry[3:].strip()
            if path:
                if "\0" in path:
                    path = path.split("\0")[0]
                files.append(path)
        return files
    except Exception as exc:  # noqa: BLE001
        logger.warning("git status --porcelain -z failed: %s", exc)
        return []


@dataclass(frozen=True, slots=True)
class _ExecutionContext:
    executor: Any | None
    artifact_store: Any | None
    transaction: Any | None


def _resolve_execution_context(root: Path) -> _ExecutionContext:
    """Resolve session-owned execution dependencies without crossing workspaces."""
    executor = None
    session = None
    artifact_store = None
    transaction = None
    try:
        from fa.inner_loop.context import get_current_session

        session = get_current_session()
        if session is not None:
            # Guard against cross-workspace contamination
            try:
                sess_root = session.workspace_root if session is not None else None
                if sess_root is not None:
                    sess_root_resolved = Path(sess_root).resolve()
                    if sess_root_resolved != root:
                        # Different workspace — don't reuse the PTY pool.
                        # Artifact/transaction state may still be retained.
                        executor = None
                    else:
                        executor = session.bash_executor if session is not None else None
                        if executor is None:
                            pool = session.pty_pool if session is not None else None
                            if pool is not None:
                                try:
                                    from fa.runtime.bash_executor import InProcessPtyExecutor

                                    executor = InProcessPtyExecutor(pool)
                                except (ImportError, AttributeError, TypeError) as exc:
                                    logger.warning("Failed to instantiate InProcessPtyExecutor: %s. Falling back.", exc)
                                    executor = pool
                else:
                    executor = session.bash_executor if session is not None else None
                    if executor is None:
                        pool = session.pty_pool if session is not None else None
                        if pool is not None:
                            try:
                                from fa.runtime.bash_executor import InProcessPtyExecutor

                                executor = InProcessPtyExecutor(pool)
                            except (ImportError, AttributeError, TypeError) as exc:
                                logger.warning("Failed to instantiate InProcessPtyExecutor: %s. Falling back.", exc)
                                executor = pool
            except Exception as exc:  # noqa: BLE001 — optional session lookup falls back to subprocess
                logger.warning("get_current_session/pty_pool resolution failed: %s", exc)
                executor = None

            try:
                artifact_store = session.artifact_store if session is not None else None
                transaction = session.transaction if session is not None else None
            except Exception as exc:  # noqa: BLE001 # best-effort attribute extraction
                logger.debug("artifact_store/transaction extraction failed: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_current_session failed in run_bash: %s", exc)

    return _ExecutionContext(executor, artifact_store, transaction)


def _run_pty_executor(
    executor: Any,
    command: str,
    root: Path,
    timeout_seconds: int,
    artifact_store: Any | None,
    transaction: Any | None,
) -> ToolResult | None:
    """Run through the stateful executor; return None when subprocess fallback is required."""
    if executor is not None:
        try:
            pty_result = executor.run(command, timeout=timeout_seconds, workdir=root, session_id="main")
            try:
                if transaction is not None:
                    write_set = _get_write_set_from_git_status(root)
                    for f in write_set:
                        transaction.add_write(f)
            except (OSError, ValueError) as exc:
                logger.warning("transaction add_write from git status failed: %s", exc)

            artifact_id = None
            stdout = _normalize_carriage_return(pty_result.stdout)
            if artifact_store is not None and len(stdout) > 8000:
                try:
                    put_method = getattr(artifact_store, "put", None) or getattr(artifact_store, "write", None)
                    if put_method is not None:
                        artifact_id = put_method(stdout)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("artifact store write failed: %s", exc)

            preview = truncate_for_preview(stdout, preview_len=500)
            summary = f"bash exited {pty_result.exit_code}"
            result = {
                "returncode": pty_result.exit_code,
                "stdout": stdout if len(stdout) <= 8000 else preview,
                "stderr": "",
                "truncated": pty_result.truncated,
                "artifact_id": artifact_id,
                "session_id": pty_result.session_id,
            }
            if pty_result.timed_out:
                logger.warning("PtyPool executor timeout, fallback to subprocess for command %s", command[:200])
                raise RuntimeError(f"PtyPool timeout fallback: {stdout[:200]}")
            if pty_result.exit_code != 0:
                return ToolResult.fail(
                    "command_failed",
                    f"bash exited {pty_result.exit_code}\nstdout: {stdout[:2000]}",
                    retryable=True,
                )
            return ToolResult.ok(summary, result=result)

        except Exception as exc:  # noqa: BLE001
            logger.warning("PtyPool executor failed: %s, fallback to subprocess", exc)

    return None


def _run_subprocess_fallback(
    command: str,
    root: Path,
    timeout_seconds: int,
    extra_allow: frozenset[str],
    artifact_store: Any | None,
    transaction: Any | None,
) -> ToolResult:
    """Run the stateless fallback and project its result into ToolResult."""
    # Fallback: subprocess.run (stateless) with binary mode to preserve \r
    try:
        completed_bytes = subprocess.run(  # noqa: S602 — shell is the product contract after sandbox admission
            command,
            cwd=root,
            # The command is an intentional LLM-selected shell program; the
            # sandbox/IntentGuard admission path runs before this tool.
            shell=True,
            check=False,
            capture_output=True,
            text=False,
            timeout=timeout_seconds,
            env=build_scrubbed_env(os.environ, extra_allow=extra_allow),
        )
        try:
            stdout_raw = completed_bytes.stdout.decode("utf-8", errors="ignore")
        except UnicodeError:
            stdout_raw = ""
        try:
            stderr_raw = completed_bytes.stderr.decode("utf-8", errors="ignore")
        except UnicodeError:
            stderr_raw = ""

        completed = _Completed(
            stdout=stdout_raw,
            stderr=stderr_raw,
            returncode=completed_bytes.returncode,
        )
    except subprocess.TimeoutExpired:
        return ToolResult.fail(
            "command_timeout",
            f"bash command timed out after {timeout_seconds}s",
            retryable=True,
        )

    try:
        if transaction is not None:
            write_set = _get_write_set_from_git_status(root)
            for f in write_set:
                transaction.add_write(f)
    except (OSError, ValueError) as exc:
        logger.warning("Fallback transaction tracking failed: %s", exc)

    stdout_clean = _normalize_carriage_return(completed.stdout)
    stderr_clean = _normalize_carriage_return(completed.stderr)
    artifact_id = None
    if artifact_store is not None and len(stdout_clean) > 8000:
        try:
            put_method = getattr(artifact_store, "put", None) or getattr(artifact_store, "write", None)
            if put_method is not None:
                artifact_id = put_method(stdout_clean)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to offload large fallback stdout to ArtifactStore: %s", exc)

    truncated = len(stdout_clean) > 8000
    preview_stdout = stdout_clean if len(stdout_clean) <= 8000 else truncate_for_preview(stdout_clean, preview_len=500)
    summary = f"bash exited {completed.returncode}"
    result = {
        "returncode": completed.returncode,
        "stdout": preview_stdout,
        "stderr": stderr_clean,
        "artifact_id": artifact_id,
        "truncated": truncated,
    }

    if completed.returncode != 0:
        detail = f"bash exited {completed.returncode}"
        if stderr_clean:
            detail += f"\nstderr: {stderr_clean[:2000]}"
        if stdout_clean:
            detail += f"\nstdout: {stdout_clean[:2000]}"
        return ToolResult.fail(
            "command_failed",
            detail,
            retryable=True,
        )
    return ToolResult.ok(summary, result=result)


def build_run_bash_tool(
    workspace_root: Path,
    *,
    timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
    env_allowlist_extra: Iterable[str] = (),
) -> ToolSpec:
    root, extra_allow = prepare_workspace_context(workspace_root, env_allowlist_extra)

    def handler(params: Mapping[str, object]) -> ToolResult:
        command, error = validate_bash_command(params)
        if error is not None:
            return error

        context = _resolve_execution_context(root)
        executor = context.executor
        artifact_store = context.artifact_store
        transaction = context.transaction

        if executor is not None:
            try:
                pty_result = _run_pty_executor(executor, command, root, timeout_seconds, artifact_store, transaction)
                if pty_result is not None:
                    return pty_result
            except Exception as exc:  # noqa: BLE001
                logger.warning("PtyPool executor failed: %s, fallback to subprocess", exc)

        return _run_subprocess_fallback(command, root, timeout_seconds, extra_allow, artifact_store, transaction)

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
        elide=_bash_run_elide,
    )


__all__ = ["build_run_bash_tool"]
