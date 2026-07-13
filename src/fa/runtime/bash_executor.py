"""
BashExecutor Protocol — interface segregation, senior eng
Protocol abstraction allows switching InProcess ↔ Remote via feature flag without changing callers
ADR-13 final
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Optional
from pathlib import Path

from .pty_pool import PtyResult

@runtime_checkable
class BashExecutor(Protocol):
    def run(self, command: str, timeout: int = 30, workdir: Optional[Path] = None, session_id: str = "main") -> PtyResult:
        ...

    def send_ctrl_c(self, session_id: str) -> str:
        ...

    def close(self, session_id: str) -> None:
        ...

    def list_sessions(self) -> list[str]:
        ...

class InProcessPtyExecutor(BashExecutor):
    """v0.1: in-process PtyPool, no network, DI via SessionState"""

    def __init__(self, pool):
        self.pool = pool

    def run(self, command: str, timeout: int = 30, workdir: Path | None = None, session_id: str = "main") -> PtyResult:
        sess = self.pool.acquire(session_id, workdir=str(workdir) if workdir else None)
        return sess.run(command, timeout=timeout)

    def send_ctrl_c(self, session_id: str) -> str:
        if session_id in self.pool.sessions:
            return self.pool.sessions[session_id].send_ctrl_c()
        return "session not found"

    def close(self, session_id: str) -> None:
        self.pool.kill(session_id)

    def list_sessions(self) -> list[str]:
        return self.pool.list_sessions()

class RemoteRuntimeExecutor(BashExecutor):
    """Future: thin client to fa-runtime-server FastAPI, POST /execute"""

    def __init__(self, base_url: str = "http://fa-runtime-server:8001", timeout: int = 5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def run(self, command: str, timeout: int = 30, workdir: Path | None = None, session_id: str = "main") -> PtyResult:
        import requests
        try:
            resp = requests.post(
                f"{self.base_url}/execute",
                json={"session_id": session_id, "command": command, "timeout": timeout, "workdir": str(workdir) if workdir else None},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return PtyResult(
                stdout=data["stdout"],
                exit_code=data["exit_code"],
                truncated=data["truncated"],
                session_id=data["session_id"],
            )
        except Exception as e:
            # Graceful degradation: fallback to in-process with WARNING, not silent
            print(f"WARNING: RemoteRuntimeExecutor failed {e}, falling back to in-process (if available) or failing")
            raise

    def send_ctrl_c(self, session_id: str) -> str:
        import requests
        resp = requests.post(f"{self.base_url}/send_ctrl_c?session_id={session_id}", timeout=self.timeout)
        return resp.json().get("msg", "")

    def close(self, session_id: str) -> None:
        import requests
        requests.post(f"{self.base_url}/kill", json={"session_id": session_id}, timeout=self.timeout)

    def list_sessions(self) -> list[str]:
        import requests
        resp = requests.get(f"{self.base_url}/list", timeout=self.timeout)
        return resp.json().get("sessions", [])
