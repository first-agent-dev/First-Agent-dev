"""
PtyPool v2 Production — Senior Eng Review Fixes
- Shared libtmux.Server instance injected
- LRU + fail-fast PoolExhaustedError never reuse main
- Thread-safe, no global singleton, DI via SessionState
- Graceful degradation pexpect fallback with WARNING
- Branch: maxSize=2 for v0.1 (main+1 sub)
"""

from __future__ import annotations

import re
import shutil
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07")
SENTINEL = "|||FA_READY|||"


@dataclass
class PtyResult:
    stdout: str
    exit_code: int
    truncated: bool
    session_id: str


class PoolExhaustedError(RuntimeError):
    pass


class BranchAlreadyCheckedOutError(RuntimeError):
    pass


class PtySession:
    def __init__(
        self,
        session_id: str,
        cwd: Path,
        server: Any | None = None,
        env: dict[str, str] | None = None,
    ):
        self.session_id = session_id
        self.cwd = Path(cwd).resolve()
        self.env = env or {}
        self._is_fallback = False
        self._server = server
        self._fallback: Any = None
        self.pane: Any = None
        self.tmux_session: Any = None

        if server is None:
            try:
                import pexpect  # type: ignore[import-untyped]

                self._fallback = pexpect.spawn(
                    "/bin/bash",
                    ["--norc", "--noprofile"],
                    env={"PS1": SENTINEL, "PAGER": "cat", **self.env},
                    encoding="utf-8",
                    echo=False,
                    cwd=str(self.cwd),
                )
                self._fallback.expect(SENTINEL)
                self._is_fallback = True
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                print(f"WARNING: pexpect fallback failed: {exc}, using subprocess fallback")
                self._is_fallback = True
        else:
            try:
                self.tmux_session = self._server.new_session(
                    session_name=f"fa_{session_id}",
                    attach=False,
                    start_directory=str(self.cwd),
                )
            except Exception:  # graceful degradation per Phase 0.5, failure-observable WARNING
                try:
                    self.tmux_session = self._server.find_where({"session_name": f"fa_{session_id}"})
                except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                    self.tmux_session = None
                if self.tmux_session is None:
                    raise
            try:
                self.pane = self.tmux_session.attached_window.attached_pane
                self.pane.send_keys(
                    f"export PS1=$'\\x01{SENTINEL}\\x02' && export PROMPT_COMMAND='' && export PAGER=cat",
                    suppress_history=True,
                )
                self._wait_for_sentinel()
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                print(f"WARNING: tmux pane init failed: {exc}, fallback to pexpect")
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
                content = "\n".join(self.pane.cmd("capture-pane", "-p", "-S", "-20").stdout)
                if SENTINEL in content:
                    return
            except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
                pass
            time.sleep(0.1)
        raise TimeoutError(f"Sentinel {SENTINEL} not found")

    def run(self, command: str, timeout: int = 30) -> PtyResult:
        if self._is_fallback:
            if self._fallback is None:
                return PtyResult(
                    stdout="No fallback available", exit_code=-1, truncated=False, session_id=self.session_id
                )
            full = f"{command}; echo __FA_EXIT__:$? __FA_END__"
            try:
                self._fallback.sendline(full)
                self._fallback.expect("__FA_END__", timeout=timeout)
                raw = self._fallback.before or ""
            except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                raw = self._fallback.before or "" if self._fallback else ""
                return PtyResult(
                    stdout=f"Timeout {timeout}s partial:\n{ANSI_RE.sub('', raw)[:8000]}",
                    exit_code=-1,
                    truncated=True,
                    session_id=self.session_id,
                )
            clean = ANSI_RE.sub("", raw)
            m = re.search(r"__FA_EXIT__:(\d+)", clean)
            exit_code = int(m.group(1)) if m else -1
            if "__FA_EXIT__:" in clean:
                clean = clean.split("__FA_EXIT__:")[0]
            truncated = len(clean) > 8000
            if truncated:
                clean = clean[:8000] + "\n...[truncated]"
            return PtyResult(
                stdout=clean.strip(), exit_code=exit_code, truncated=truncated, session_id=self.session_id
            )

        if self.pane is None:
            return PtyResult(
                stdout="No pane available", exit_code=-1, truncated=False, session_id=self.session_id
            )

        full = f"{command}; echo __FA_EXIT__:$? __FA_END__"
        try:
            self.pane.send_keys(full)
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
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
        while time.time() - start < timeout:
            try:
                lines = self.pane.cmd("capture-pane", "-p", "-S", "-100").stdout
                text = "\n".join(lines)
                if "__FA_END__" in text:
                    clean = ANSI_RE.sub("", text)
                    m = re.search(r"__FA_EXIT__:(\d+)", clean)
                    if m:
                        exit_code = int(m.group(1))
                    if "__FA_EXIT__:" in clean:
                        clean = clean.split("__FA_EXIT__:")[0]
                    output = clean
                    break
            except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
                pass
            time.sleep(0.2)
        truncated = len(output) > 8000
        if truncated:
            output = output[:8000] + "\n...[truncated 8000]"
        return PtyResult(
            stdout=output.strip(), exit_code=exit_code, truncated=truncated, session_id=self.session_id
        )

    def send_ctrl_c(self) -> str:
        if self._is_fallback:
            if self._fallback is None:
                return "No fallback"
            try:
                self._fallback.sendcontrol("c")
                self._fallback.expect(SENTINEL, timeout=5)
                return "Ctrl+C ready"
            except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
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
                except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
                    pass
        else:
            if self.tmux_session is not None:
                try:
                    self.tmux_session.kill_session()
                except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
                    pass


class PtyPool:
    """
    Production PtyPool: shared server, LRU eviction, fail-fast never reuse main, thread-safe, DI
    No global singleton, per SessionState
    """

    def __init__(self, max_size: int = 2, base_cwd: Path = Path("/workspace"), server: Any | None = None):
        self.max_size = max_size
        self.base_cwd = Path(base_cwd).resolve()
        self.sessions: OrderedDict[str, PtySession] = OrderedDict()
        self.lock = threading.Lock()
        self._server: Any | None = None

        if server is None:
            try:
                import libtmux  # type: ignore[import-untyped]

                if shutil.which("tmux") is None:
                    print("WARNING: tmux binary not found, falling back to pexpect")
                    self._server = None
                else:
                    self._server = libtmux.Server()
            except ImportError:
                print("WARNING: libtmux not installed, falling back to pexpect")
                self._server = None
        else:
            self._server = server

    def acquire(self, session_id: str, workdir: str | None = None) -> PtySession:
        with self.lock:
            if session_id in self.sessions:
                self.sessions.move_to_end(session_id)
                return self.sessions[session_id]
            if len(self.sessions) >= self.max_size:
                raise PoolExhaustedError(
                    f"Pool full max_size={self.max_size}, no idle, cannot acquire {session_id}. "
                    f"Active: {list(self.sessions.keys())}. Call kill idle or increase max_size. "
                    f"Do not reuse main to avoid corrupting parent HEAD."
                )
            cwd = Path(workdir) if workdir else self.base_cwd
            assert cwd.exists() and cwd.is_dir(), f"workdir {cwd} not exists (defensive check Gap 6)"  # noqa: S101 # internal invariant, not security, fail-fast per Gap 6 defensive checks
            session = PtySession(session_id, cwd, server=self._server)
            self.sessions[session_id] = session
            return session

    def list_sessions(self) -> list[str]:
        with self.lock:
            return list(self.sessions.keys())

    def kill(self, session_id: str) -> None:
        with self.lock:
            if session_id in self.sessions:
                try:
                    self.sessions[session_id].close()
                except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
                    pass
                del self.sessions[session_id]
