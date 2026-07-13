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
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass
from collections import OrderedDict

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
    def __init__(self, session_id: str, cwd: Path, server=None, env: Optional[Dict[str, str]] = None):
        self.session_id = session_id
        self.cwd = Path(cwd).resolve()
        self.env = env or {}
        self._is_fallback = False
        self._server = server

        # Graceful degradation: check tmux binary
        if server is None:
            # Fallback to pexpect
            import pexpect
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
            self.pane = None
            self.tmux_session = None
        else:
            # libtmux path with shared server
            self.pane = None
            try:
                self.tmux_session = self._server.new_session(
                    session_name=f"fa_{session_id}",
                    attach=False,
                    start_directory=str(self.cwd),
                )
            except Exception:
                # Session exists, find
                self.tmux_session = self._server.find_where({"session_name": f"fa_{session_id}"})
                if self.tmux_session is None:
                    raise
            self.pane = self.tmux_session.attached_window.attached_pane
            self.pane.send_keys(
                f"export PS1=$'\\x01{SENTINEL}\\x02' && export PROMPT_COMMAND='' && export PAGER=cat",
                suppress_history=True,
            )
            self._wait_for_sentinel()

    def _wait_for_sentinel(self, timeout: int = 5):
        if self._is_fallback:
            return
        import time
        start = time.time()
        while time.time() - start < timeout:
            content = "\n".join(self.pane.cmd("capture-pane", "-p", "-S", "-20").stdout)
            if SENTINEL in content:
                return
            time.sleep(0.1)
        raise TimeoutError(f"Sentinel {SENTINEL} not found")

    def run(self, command: str, timeout: int = 30) -> PtyResult:
        if self._is_fallback:
            full = f"{command}; echo __FA_EXIT__:$? __FA_END__"
            self._fallback.sendline(full)
            try:
                self._fallback.expect("__FA_END__", timeout=timeout)
                raw = self._fallback.before or ""
            except Exception:
                raw = self._fallback.before or ""
                return PtyResult(stdout=f"Timeout {timeout}s partial:\n{ANSI_RE.sub('', raw)[:8000]}", exit_code=-1, truncated=True, session_id=self.session_id)
            clean = ANSI_RE.sub("", raw)
            m = re.search(r"__FA_EXIT__:(\d+)", clean)
            exit_code = int(m.group(1)) if m else -1
            if "__FA_EXIT__:" in clean:
                clean = clean.split("__FA_EXIT__:")[0]
            truncated = len(clean) > 8000
            if truncated:
                clean = clean[:8000] + "\n...[truncated]"
            return PtyResult(stdout=clean.strip(), exit_code=exit_code, truncated=truncated, session_id=self.session_id)

        full = f"{command}; echo __FA_EXIT__:$? __FA_END__"
        self.pane.send_keys(full)
        import time
        start = time.time()
        output = ""
        exit_code = -1
        while time.time() - start < timeout:
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
            time.sleep(0.2)
        truncated = len(output) > 8000
        if truncated:
            output = output[:8000] + "\n...[truncated 8000]"
        return PtyResult(stdout=output.strip(), exit_code=exit_code, truncated=truncated, session_id=self.session_id)

    def send_ctrl_c(self) -> str:
        if self._is_fallback:
            self._fallback.sendcontrol("c")
            try:
                self._fallback.expect(SENTINEL, timeout=5)
                return "Ctrl+C ready"
            except Exception:
                return "Ctrl+C sent not ready"
        self.pane.send_keys("C-c")
        try:
            self._wait_for_sentinel(timeout=5)
            return "Ctrl+C ready"
        except TimeoutError:
            return "Ctrl+C sent not ready"

    def close(self):
        if self._is_fallback:
            self._fallback.close(force=True)
        else:
            if hasattr(self, 'tmux_session') and self.tmux_session:
                try:
                    self.tmux_session.kill_session()
                except Exception:
                    pass

class PtyPool:
    """
    Production PtyPool: shared server, LRU eviction, fail-fast never reuse main, thread-safe, DI
    No global singleton, per SessionState
    """

    def __init__(self, max_size: int = 2, base_cwd: Path = Path("/workspace"), server=None):
        self.max_size = max_size
        self.base_cwd = Path(base_cwd).resolve()
        self.sessions: OrderedDict[str, PtySession] = OrderedDict()  # LRU order
        self.lock = threading.Lock()
        # Shared server instance, injected or created once
        if server is None:
            # Try libtmux, fallback None -> PtySession will fallback to pexpect
            try:
                import libtmux
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

    def acquire(self, session_id: str, workdir: Optional[str] = None) -> PtySession:
        with self.lock:
            if session_id in self.sessions:
                # Move to end (LRU)
                self.sessions.move_to_end(session_id)
                return self.sessions[session_id]
            if len(self.sessions) >= self.max_size:
                # Fail-fast, never reuse main, prevents isolation break (Gap B fix)
                raise PoolExhaustedError(
                    f"Pool full max_size={self.max_size}, no idle, cannot acquire {session_id}. "
                    f"Active: {list(self.sessions.keys())}. Call kill idle or increase max_size. "
                    f"Do not reuse main to avoid corrupting parent HEAD."
                )
            cwd = Path(workdir) if workdir else self.base_cwd
            assert cwd.exists() and cwd.is_dir(), f"workdir {cwd} not exists (defensive check Gap 6)"
            session = PtySession(session_id, cwd, server=self._server)
            self.sessions[session_id] = session
            return session

    def list_sessions(self):
        with self.lock:
            return list(self.sessions.keys())

    def kill(self, session_id: str):
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].close()
                del self.sessions[session_id]
