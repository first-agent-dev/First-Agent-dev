from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import DEFAULT_TOOL_CONTEXT_BYTES, ToolResult, ToolSpec
from fa.inner_loop.runtime_limits import DEFAULT_BASH_TIMEOUT_SECONDS
from fa.inner_loop.tools._common import (
    _bash_tail_frame,
    _retained_stdout,
    prepare_workspace_context,
    validate_bash_command,
)
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
            # S12.7 (CT4): tail-biased retention replaces the 8,000B/500-char
            # head preview — the model sees the END of long output (where the
            # answer/error usually is); FULL stdout goes to the artifact.
            retained, trimmed = _retained_stdout(stdout)
            if trimmed and artifact_store is not None:
                try:
                    put_method = getattr(artifact_store, "put", None) or getattr(artifact_store, "write", None)
                    if put_method is not None:
                        artifact_id = put_method(stdout)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("artifact store write failed: %s", exc)

            # F7: ``returncode`` is the shell/pipeline last-stage exit
            # (here PtyPool ``exit_code``). FA does not wrap ``set -o pipefail``
            # (``| head`` / ``| grep`` would then SIGPIPE and burn turns) and
            # does not inject ``PIPESTATUS``: the subprocess fallback is
            # ``shell=True`` → ``/bin/sh -c`` (dash on Ubuntu: no PIPESTATUS),
            # so a pipestatus field would be PTY-vs-fallback inconsistent.
            # Out-of-band capture only if that is ever pursued.
            summary = f"bash exited {pty_result.exit_code}"
            result = {
                "returncode": pty_result.exit_code,
                "stdout": retained,
                "stderr": "",
                "truncated": bool(pty_result.truncated) or trimmed,
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
    # S12.1 (CT1): prepend the readiness venv AFTER scrubbing — the secret
    # filter is never bypassed, PATH is already allowlisted by bash_env.
    # Covers the main-agent fallback AND subagents (executor=None reaches
    # this same function). Same predicate as PtySession (runtime/pty_pool.py).
    env = build_scrubbed_env(os.environ, extra_allow=extra_allow)
    venv_bin = root / ".venv" / "bin"
    if venv_bin.is_dir():
        env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', os.defpath)}"
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
            env=env,
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
    # S12.7 (CT4): tail-biased retention replaces the 8,000B/500-char head
    # preview; FULL stdout goes to the artifact iff trimmed. stderr stays
    # whole here — if the envelope still overflows the ceiling (huge stderr,
    # escaping inflation), projection's _bash_tail_frame frames it with the
    # stderr block LAST.
    retained, trimmed = _retained_stdout(stdout_clean)
    if trimmed and artifact_store is not None:
        try:
            put_method = getattr(artifact_store, "put", None) or getattr(artifact_store, "write", None)
            if put_method is not None:
                artifact_id = put_method(stdout_clean)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to offload trimmed stdout to ArtifactStore: %s", exc)

    # F7: last-stage pipeline exit (see PTY path). ``shell=True`` here is
    # ``/bin/sh -c`` — not bash — so ``PIPESTATUS`` is unavailable.
    summary = f"bash exited {completed.returncode}"
    result = {
        "returncode": completed.returncode,
        "stdout": retained,
        "stderr": stderr_clean,
        "artifact_id": artifact_id,
        "truncated": trimmed,
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
        name="fs_run_bash",
        description="""Run a bash command in the workspace after sandbox hooks allow it.

STATEFUL for main agent (via PtyPool EventStream Runtime, ADR-14): cwd, env, venv persist
across calls (cd, export, source .venv/bin/activate survive). Stateless for cheap subagents
(structured websearch, simple function) with isolated context.

Background processes: use fs_run_bash_background for long-running commands (dev servers),
then fs_read_terminal, fs_list_tasks, fs_kill_task, fs_send_ctrl_c.

Output over ~30,000 chars is retained TAIL-biased (the end, where errors/answers usually
are) with the full output stored under artifact_id — follow it with fs_read_file
{"artifact_id": ...} (S12.7). Prefer grep / | tail -n N for huge outputs.

returncode is the shell/pipeline exit (last stage), not each command in a pipe.
Piping a failing producer into tail/grep reports tail's 0. FA does not enable
pipefail for you. If you need the producer's status, put set -o pipefail in THAT
command or do not pipe.

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
        # S12.7 (CT2/GAP4): projection ceiling (was 8_000). The tool's
        # INTERNAL >8000 pre-truncation stays until the S5 tail frame.
        max_context_bytes=DEFAULT_TOOL_CONTEXT_BYTES,
        elide=_bash_tail_frame,
    )


__all__ = ["build_run_bash_tool"]
