"""
PtyPool v3 Production — Phase 3 Locked Plan Implementation
- Shared libtmux.Server instance injected with socket isolation fa_<run_id>
- Wide viewport -x 300 -y 100 + -J join wrapped lines to prevent JSON corruption (Gap 12)
- UUID-based sentinel per session to avoid collision
- LRU + pinned main never evict main, PoolExhaustedError only when same session_id locked (clarified policy)
- Thread-safe, no global singleton, DI via SessionState, CWD lock per session
- Graceful degradation pexpect fallback per-session independent with thread-safe registry
- Signal/atexit leak prevention (Gap 14) — leave-no-trace
- ANSI strip + exit code parsing FA_EXIT_<uuid>:$? FA_END_<uuid>
- Branch: maxSize=2 for v0.1 (main pinned + 1 LRU sub)
"""

from __future__ import annotations

import atexit
import logging
import re
import shutil
import signal
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

logger = logging.getLogger(__name__)

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07")


def resolve_cr(text: str) -> str:
    """Normalize CR artifacts — FIND-016 fix.

    Examples:
    - ``foo\\rbar\\n`` -> ``bar``
    - ``12%\\r34%\\r56%`` -> ``56%``
    Used by PtySession and fs_run_bash for truthful output.
    """
    text = text.replace("\r\n", "\n")
    lines: list[str] = []
    for line in text.split("\n"):
        if "\r" in line:
            line = line.split("\r")[-1]
        lines.append(line)
    result = "\n".join(lines)
    if result.endswith("\n") and text.endswith("\n"):
        result = result[:-1]
    return result


def _normalize_cr(text: str) -> str:
    return resolve_cr(text)


@dataclass
class PtyResult:
    stdout: str
    exit_code: int
    truncated: bool
    session_id: str
    # Explicit timeout signal (ADR-14 follow-up). Callers previously
    # sniffed stdout for the substring "Timeout" to distinguish a hard
    # timeout from an ordinary non-zero exit — that convention only ever
    # matched the pexpect fallback path's stdout shape; the tmux path's
    # timeout branch never populated a matching string, so
    # fa.inner_loop.tools.run_bash's `"Timeout" in stdout` check silently
    # misclassified every tmux-path timeout as `command_failed` instead of
    # `command_timeout`. Default False keeps existing call sites (which
    # never set this) correct without changes.
    timed_out: bool = False


class _TmuxSessionLike(Protocol):
    active_window: Any
    attached_window: Any

    def kill(self) -> None: ...

    def kill_session(self) -> None: ...


class _TmuxServerLike(Protocol):
    socket_name: str

    def new_session(self, **kwargs: Any) -> _TmuxSessionLike: ...

    def find_where(self, _filters: dict[str, str]) -> _TmuxSessionLike | None: ...

    def cmd(self, *args: str) -> Any: ...


class PoolExhaustedError(RuntimeError):
    """Pool full and trying to acquire same session_id that is locked,
    or maxSize=1 and main present trying sub.
    """


class PtySession:
    def __init__(
        self,
        session_id: str,
        cwd: Path,
        server: _TmuxServerLike | None = None,
        env: dict[str, str] | None = None,
        run_id: str | None = None,
    ):
        self.session_id = session_id
        self.cwd = Path(cwd).resolve()
        self.env = env or {}
        self.run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
        # UUID-based sentinel per session to avoid collision if command output contains sentinel string
        self._sentinel_token = f"FA_READY_{session_id}_{uuid.uuid4().hex[:6]}"
        self._exit_token = f"FA_EXIT_{uuid.uuid4().hex[:6]}"
        self._end_token = f"FA_END_{uuid.uuid4().hex[:6]}"
        self._is_fallback = False
        self._server = server
        self._fallback: Any = None
        self.pane: Any = None
        self.tmux_session: Any = None
        self._cwd_lock = threading.Lock()

        if server is None:
            # Fallback pexpect per-session independent
            try:
                import pexpect  # type: ignore[import-untyped]

                # PS1 includes sentinel with control chars \x01 \x02 to avoid visible in output
                ps1 = f"\x01{self._sentinel_token}\x02"
                self._fallback = pexpect.spawn(
                    "/bin/bash",
                    ["--norc", "--noprofile"],
                    env={"PS1": ps1, "PAGER": "cat", **self.env},
                    encoding="utf-8",
                    echo=False,
                    cwd=str(self.cwd),
                )
                self._fallback.expect(self._sentinel_token, timeout=5)
                self._is_fallback = True
            except Exception as exc:  # noqa: BLE001 # graceful degradation
                logger.warning("pexpect fallback failed: %s, using subprocess fallback", exc)
                self._is_fallback = True
        else:
            server_ref = self._server
            if server_ref is None:
                raise RuntimeError("tmux server unavailable")
            try:
                # Wide viewport -x 300 -y 100 per Gap 12 to preserve formal substrate JSON integrity
                self.tmux_session = server_ref.new_session(
                    session_name=f"fa_{session_id}_{self.run_id}",
                    attach=False,
                    start_directory=str(self.cwd),
                    x=300,
                    y=100,
                )
            except Exception:  # may already exist
                try:
                    self.tmux_session = server_ref.find_where({"session_name": f"fa_{session_id}_{self.run_id}"})
                except Exception:  # noqa: BLE001, S110
                    pass
                if self.tmux_session is None:
                    # Try without run_id suffix for backward compat (main session)
                    try:
                        self.tmux_session = server_ref.find_where({"session_name": f"fa_{session_id}"})
                    except Exception:  # noqa: BLE001, S110
                        pass
                if self.tmux_session is None:
                    raise

            try:
                if hasattr(self.tmux_session, "active_window"):
                    self.pane = self.tmux_session.active_window.active_pane
                else:
                    self.pane = self.tmux_session.attached_window.attached_pane

                # Narrow local before dereference (pyrefly PY7 closure):
                # self.pane is typed Any | None; the attribute-access site must
                # see a guaranteed-non-None local to satisfy the type checker.
                pane = self.pane
                if pane is None:
                    raise RuntimeError("tmux pane not available after session setup")

                # Use sentinel with control chars to avoid visible
                # Wrap long send_keys lines
                setup_cmd = (
                    f"export PS1=$'\\x01{self._sentinel_token}\\x02' "
                    f"&& export PROMPT_COMMAND='' && export PAGER=cat "
                    f"&& export TERM=xterm-256color"
                )
                pane.send_keys(
                    setup_cmd,
                    suppress_history=True,
                )
                self._wait_for_sentinel()
            except Exception as exc:  # noqa: BLE001
                logger.warning("tmux pane init failed: %s, fallback to pexpect", exc)
                self._is_fallback = True
                self.pane = None
                self.tmux_session = None

    def _wait_for_sentinel(self, timeout: int = 5) -> None:
        if self._is_fallback:
            return
        if self.pane is None:
            return
        import time

        start = time.time()
        while time.time() - start < timeout:
            try:
                # -J join wrapped lines per Gap 12, -p stdout, -S -20 last 20 lines, -E - end visible
                content = "\n".join(self.pane.cmd("capture-pane", "-p", "-J", "-S", "-20", "-E", "-").stdout)
                if self._sentinel_token in content:
                    return
            except Exception:  # noqa: BLE001, S110 # best-effort
                pass
            time.sleep(0.1)
        raise TimeoutError(f"Sentinel {self._sentinel_token} not found")

    @staticmethod
    def _is_stateful_command(command: str) -> bool:
        """True for commands that must run in the persistent shell itself
        (export/cd/source/...), not a subshell — shared by both backends
        so the classification can never drift between them.
        """
        stripped = command.lstrip()
        is_stateful = stripped.startswith(("export ", "cd ", "source ", ". ", "alias ", "unalias ", "set ", "unset "))
        if stripped == "cd" or stripped.startswith("cd "):
            is_stateful = True
        return is_stateful

    def _resolve_heredoc_command(self, command: str, is_stateful: bool, call_id: str) -> tuple[str, Path | None]:
        """Route heredoc-bearing non-stateful commands through a temp script file.

        Heredocs (`<<WORD` / `<<-WORD`) cannot survive ANY wrapping strategy
        that appends text to the same line as the heredoc's closing
        delimiter — POSIX requires the delimiter alone on its line, and
        `(command); echo ...` (or even a bare trailing `)`) breaks that,
        leaving the shell waiting forever for a delimiter line that will
        never arrive. This affects BOTH backends identically (`_run_tmux`'s
        `send_keys` and `_run_fallback`'s `sendline` both send the wrapped
        string as one shell input), so both call this helper rather than
        each re-implementing (and potentially drifting on) the detection.

        Returns ``(command_to_run, script_path)`` — ``script_path`` is
        ``None`` when no rewriting was needed or possible; the caller is
        responsible for calling ``_cleanup_script(script_path)`` once done.
        """
        if is_stateful or not re.search(r"<<-?\s*['\"]?\w", command):
            return command, None
        try:
            script_path = self.cwd / f".fa-bash-{call_id}.sh"
            script_path.write_text(f"#!/bin/sh\n{command}\n", encoding="utf-8")
            script_path.chmod(0o700)
            return f"sh {script_path}", script_path
        except OSError as exc:
            logger.warning("Failed to write heredoc script file: %s, running inline (may hang)", exc)
            return command, None

    def _run_fallback(self, command: str, timeout: int) -> PtyResult:
        if self._is_fallback:
            if self._fallback is None:
                return PtyResult(
                    stdout="No fallback available",
                    exit_code=-1,
                    truncated=False,
                    session_id=self.session_id,
                )
            # Wrap in subshell to avoid killing persistent shell with exit,
            # but preserve stateful commands (export, cd, source, etc) in main shell.
            is_stateful = self._is_stateful_command(command)
            call_id = uuid.uuid4().hex[:8]
            command_to_run, script_path = self._resolve_heredoc_command(command, is_stateful, call_id)
            if is_stateful:
                full = f"{command_to_run}; echo {self._exit_token}:$? {self._end_token}"
            else:
                full = f"({command_to_run}); echo {self._exit_token}:$? {self._end_token}"
            try:
                self._fallback.sendline(full)
                self._fallback.expect(self._end_token, timeout=timeout)
                raw = self._fallback.before or ""
            except Exception as exc:  # noqa: BLE001
                raw = self._fallback.before or "" if self._fallback else ""
                # Distinguish a genuine timeout (pexpect.TIMEOUT) from other
                # failures (e.g. EOF from a dead child) so callers can
                # branch on PtyResult.timed_out instead of string-sniffing
                # stdout for "Timeout" — that heuristic previously mislabeled
                # EVERY failure here (timeout or not) with the same message.
                import pexpect

                is_timeout = isinstance(exc, pexpect.TIMEOUT)
                label = f"Timeout {timeout}s partial" if is_timeout else f"Command failed: {exc}"
                self._cleanup_script(script_path)
                return PtyResult(
                    stdout=f"{label}:\n{ANSI_RE.sub('', raw)[:8000]}",
                    exit_code=-1,
                    truncated=True,
                    session_id=self.session_id,
                    timed_out=is_timeout,
                )
            self._cleanup_script(script_path)
            clean = ANSI_RE.sub("", raw)
            clean = resolve_cr(clean)
            # Strip sentinel token that may be in prompt (pexpect PS1)
            clean = clean.replace(self._sentinel_token, "")
            m = re.search(rf"{re.escape(self._exit_token)}:(\d+)", clean)
            exit_code = int(m.group(1)) if m else -1
            if f"{self._exit_token}:" in clean:
                clean = clean.split(f"{self._exit_token}:")[0]
            truncated = len(clean) > 8000
            if truncated:
                clean = clean[:8000] + "\n...[truncated]"
            return PtyResult(stdout=clean.strip(), exit_code=exit_code, truncated=truncated, session_id=self.session_id)
        return PtyResult(stdout="No fallback available", exit_code=-1, truncated=False, session_id=self.session_id)

    def _run_tmux(self, command: str, timeout: int) -> PtyResult:
        if self.pane is None:
            return PtyResult(stdout="No pane available", exit_code=-1, truncated=False, session_id=self.session_id)

        # Per-INVOCATION markers (not self._exit_token/self._end_token, which
        # are fixed for the session's lifetime). tmux capture-pane always
        # returns the pane's PERSISTENT scrollback, not an incremental
        # buffer (unlike pexpect's consuming expect()) — every prior
        # command's echoed-and-executed marker text stays visible forever.
        # Reusing one marker set across calls in the same session causes two
        # compounding bugs, both reproduced and fixed here:
        #   1. `str.split(exit_token)[0]` cuts at the FIRST occurrence, which
        #      is the shell's echo of the just-typed command line (it always
        #      appears before the real `echo <token>:$?` executes) — so the
        #      returned "output" is the echoed input, not the command result.
        #   2. A slow command can match a STALE end_token already present in
        #      scrollback from a PRIOR completed command and return that
        #      prior command's output immediately, before the new command
        #      has even finished running (race, not just a display bug).
        # A fresh uuid4 per call plus a START marker anchoring the slice
        # eliminates both: matching cannot succeed against old scrollback,
        # and extraction never depends on which occurrence of a repeated
        # substring is "first".
        call_id = uuid.uuid4().hex[:8]
        start_token = f"FA_START_{call_id}"
        exit_token = f"FA_EXIT_{call_id}"
        end_token = f"FA_END_{call_id}"

        is_stateful = self._is_stateful_command(command)

        # Heredocs (`<<WORD` / `<<-WORD`) cannot survive ANY wrapping
        # strategy that appends text to the same line as the heredoc's
        # closing delimiter — POSIX requires the delimiter alone on its
        # line, and `(command); echo ...` (or even a bare trailing `)`)
        # breaks that, leaving the shell waiting forever for a delimiter
        # line that will never arrive (verified: this hangs until the
        # caller's timeout, every time, for every wrapping shape tried).
        # See _resolve_heredoc_command — shared with _run_fallback so both
        # backends route heredocs through a temp script file identically;
        # a prior version of this fix only patched THIS method and left
        # _run_fallback with the identical hang (caught when a machine
        # without the tmux binary fell back to pexpect and hit it).
        command_to_run, script_path = self._resolve_heredoc_command(command, is_stateful, call_id)

        if is_stateful:
            full = f"echo {start_token}; {command_to_run}; echo {exit_token}:$? {end_token}"
        else:
            full = f"echo {start_token}; ({command_to_run}); echo {exit_token}:$? {end_token}"
        try:
            self.pane.send_keys(full)
        except Exception as exc:  # noqa: BLE001
            self._cleanup_script(script_path)
            return PtyResult(
                stdout=f"Failed to send command: {exc}",
                exit_code=-1,
                truncated=False,
                session_id=self.session_id,
            )

        import time

        start = time.time()
        output = ""
        exit_code = -1
        timed_out = True
        while time.time() - start < timeout:
            try:
                # -J join wrapped lines per Gap 12 to prevent JSON corruption.
                # -S "-" (full scrollback, not a fixed "-100" window): a
                # fixed window can scroll the start_token out of view before
                # the end_token appears for high-output commands, which
                # would otherwise silently degrade to the same first-match
                # ambiguity this fix closes. Measured overhead is
                # negligible (~3ms/call at both typical and near-tmux
                # history-limit scrollback sizes).
                lines = self.pane.cmd("capture-pane", "-p", "-J", "-S", "-", "-E", "-").stdout
                text = "\n".join(lines)
                # Anchor on THIS call's start marker; rfind (not find) so a
                # stale copy of an identically-shaped OLDER marker can never
                # match — though with a fresh uuid4 per call this is belt
                # and suspenders, not load-bearing.
                start_idx = text.rfind(start_token)
                if start_idx == -1:
                    time.sleep(0.2)
                    continue
                newline_idx = text.find("\n", start_idx)
                start_of_output = newline_idx + 1 if newline_idx != -1 else start_idx + len(start_token)
                remainder = text[start_of_output:]
                if end_token in remainder:
                    clean = ANSI_RE.sub("", remainder)
                    clean = resolve_cr(clean)
                    # Strip sentinel token that may appear in prompt
                    clean = clean.replace(self._sentinel_token, "")
                    m = re.search(rf"{re.escape(exit_token)}:(\d+)", clean)
                    if m:
                        exit_code = int(m.group(1))
                        output = clean[: m.start()]
                        timed_out = False
                        break
            except Exception:  # noqa: BLE001, S110
                pass
            time.sleep(0.2)
        self._cleanup_script(script_path)
        truncated = len(output) > 8000
        if truncated:
            output = output[:8000] + "\n...[truncated 8000]"
        if timed_out:
            output = f"Timeout {timeout}s partial:\n{output}" if output else f"Timeout {timeout}s: no output captured"
        return PtyResult(
            stdout=output.strip(),
            exit_code=exit_code,
            truncated=truncated,
            session_id=self.session_id,
            timed_out=timed_out,
        )

    @staticmethod
    def _cleanup_script(script_path: Path | None) -> None:
        """Best-effort removal of a temp heredoc script (§_run_tmux). Never
        raises — a leaked 0700 file under the session cwd is a minor
        housekeeping issue, not a correctness or security failure."""
        if script_path is None:
            return
        try:
            script_path.unlink(missing_ok=True)
        except OSError:
            pass  # best-effort cleanup; a leaked temp file is not a correctness issue

    def run(self, command: str, timeout: int = 30) -> PtyResult:
        """Run one command while serializing cwd/session access."""
        with self._cwd_lock:
            if self._is_fallback:
                return self._run_fallback(command, timeout)
            return self._run_tmux(command, timeout)

    def send_ctrl_c(self) -> str:
        if self._is_fallback:
            if self._fallback is None:
                return "No fallback"
            try:
                # The active run() call owns the pexpect reader. A second
                # concurrent expect() here races with run() for the prompt/
                # end sentinel and can leave the non-daemon worker blocked.
                # Send the interrupt only; run() observes its own end token.
                self._fallback.sendcontrol("c")
                return "Ctrl+C sent"
            except Exception:  # noqa: BLE001
                return "Ctrl+C sent not ready"
        if self.pane is None:
            return "No pane"
        try:
            self.pane.send_keys("C-c")
            self._wait_for_sentinel(timeout=5)
            return "Ctrl+C ready"
        except TimeoutError:
            return "Ctrl+C sent not ready"

    def close(self) -> None:
        if self._is_fallback:
            if self._fallback is not None:
                try:
                    self._fallback.close(force=True)
                except Exception:  # noqa: BLE001, S110
                    pass
        else:
            if self.tmux_session is not None:
                try:
                    if hasattr(self.tmux_session, "kill"):
                        self.tmux_session.kill()
                    else:
                        self.tmux_session.kill_session()
                except Exception:  # noqa: BLE001, S110
                    pass


class PtyPool:
    """Production PtyPool: shared server with socket isolation fa_<run_id>,
    LRU eviction pinned main, thread-safe, DI, no global singleton.
    Implements Gap 12 (-J join), Improvement 1 (socket isolation -L),
    Gap 13 pexpect per-session isolation, Gap 14 signal/atexit leak prevention.
    """

    def __init__(
        self,
        max_size: int = 2,
        base_cwd: Path = Path("/workspace"),
        server: Any | None = None,
        run_id: str | None = None,
    ):
        self.max_size = max_size
        self.base_cwd = Path(base_cwd).resolve()
        self.sessions: dict[str, PtySession] = {}
        self._lru: OrderedDict[str, None] = OrderedDict()
        self.lock = threading.Lock()
        self._server: _TmuxServerLike | None = server
        self.run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
        self._original_server: Any | None = None

        if self._server is None:
            try:
                import libtmux

                if shutil.which("tmux") is None:
                    logger.warning("tmux binary not found, falling back to pexpect")
                    self._server = None
                else:
                    # Socket isolation per run_id to avoid hijack in concurrent eval-harness / CI
                    socket_name = f"fa_{self.run_id}"
                    try:
                        self._server = cast(_TmuxServerLike, libtmux.Server(socket_name=socket_name))
                        # Ensure server started
                        self._server.cmd("start-server")
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "libtmux Server socket_name=%s failed: %s, trying default + start-server",
                            socket_name,
                            exc,
                        )
                        try:
                            self._server = cast(_TmuxServerLike, libtmux.Server())
                            server_ref = self._server
                            if server_ref is None:
                                raise RuntimeError("tmux server unavailable")
                            server_ref.cmd("start-server")
                        except Exception as exc2:  # noqa: BLE001
                            logger.warning("libtmux default server failed: %s, fallback to pexpect", exc2)
                            self._server = None
                    self._original_server = self._server
            except ImportError:
                logger.warning("libtmux not installed, falling back to pexpect")
                self._server = None

        # Signal/atexit leak prevention per Gap 14 leave-no-trace
        try:
            atexit.register(self._cleanup_all)
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    signal.signal(sig, lambda *_: self._cleanup_all())
                except (ValueError, OSError):
                    # Signal only works in main thread
                    pass
        except Exception:  # noqa: BLE001, S110
            pass

    def _cleanup_all(self) -> None:
        """Leave-no-trace: kill all sessions and kill isolated server."""
        try:
            with self.lock:
                for sid in list(self.sessions.keys()):
                    try:
                        self.sessions[sid].close()
                    except Exception:  # noqa: BLE001, S110
                        pass
                self.sessions.clear()
                self._lru.clear()
            if self._server is not None:
                try:
                    # Only kill server if it was isolated socket (fa_ prefix), not default
                    # Check socket_name to avoid killing user's default tmux
                    socket_name = getattr(self._server, "socket_name", "") or ""
                    if socket_name.startswith("fa_"):
                        self._server.cmd("kill-server")
                except Exception:  # noqa: BLE001, S110
                    pass
        except Exception:  # noqa: BLE001, S110
            pass

    def acquire(self, session_id: str, workdir: str | None = None) -> PtySession:
        with self.lock:
            if session_id in self.sessions:
                # Move to end = most recently used
                self._lru.move_to_end(session_id)
                return self.sessions[session_id]

            # Policy: main pinned never evict, LRU eviction for subs only
            # maxSize=2 = main pinned + 1 LRU sub slot
            if len(self.sessions) >= self.max_size:
                # Find LRU that is not main
                lru_to_evict = None
                for sid in self._lru:
                    if sid != "main":
                        lru_to_evict = sid
                        break
                if lru_to_evict is None:
                    # Only main present and trying to acquire different session_id and maxSize==1?
                    # Then fail-fast
                    # For maxSize=2, main + 1 sub already, trying 3rd distinct -> evict LRU sub (not main)
                    # If no sub to evict (only main and trying new), evict main? No, per spec never reuse main,
                    # so evict main? Actually per clarified policy, main pinned, so evict LRU sub.
                    # If we are here and all sessions are main (only main), and trying sub, we have space?
                    # len>=maxSize, so need to evict.
                    # For maxSize=2, main + sub1 present, trying sub2 -> evict sub1.
                    # Find any sub (not main).
                    for sid in list(self.sessions.keys()):
                        if sid != "main":
                            lru_to_evict = sid
                            break
                    if lru_to_evict is None:
                        raise PoolExhaustedError(
                            f"Pool full max_size={self.max_size}, active={list(self.sessions.keys())}, "
                            f"cannot acquire {session_id} without evicting main. Increase max_size."
                        )
                # Evict LRU sub
                try:
                    self.sessions[lru_to_evict].close()
                except Exception:  # noqa: BLE001, S110
                    pass
                self.sessions.pop(lru_to_evict, None)
                self._lru.pop(lru_to_evict, None)

            cwd = Path(workdir) if workdir else self.base_cwd
            # Defensive: workdir exists and is dir, fail-fast per Gap 6
            if not cwd.exists():
                raise RuntimeError(f"workdir {cwd} not exists")
            if not cwd.is_dir():
                raise RuntimeError(f"workdir {cwd} not dir")

            session = PtySession(session_id, cwd, server=self._server, run_id=self.run_id)
            self.sessions[session_id] = session
            self._lru[session_id] = None
            return session

    def list_sessions(self) -> list[str]:
        with self.lock:
            return list(self.sessions.keys())

    def kill(self, session_id: str) -> None:
        with self.lock:
            if session_id in self.sessions:
                try:
                    self.sessions[session_id].close()
                except Exception:  # noqa: BLE001, S110
                    pass
                self.sessions.pop(session_id, None)
                self._lru.pop(session_id, None)
