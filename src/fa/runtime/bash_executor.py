"""
BashExecutor Protocol — interface segregation, senior eng
Protocol abstraction allows switching InProcess ↔ Remote via feature flag without changing callers
ADR-13 final
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, override, runtime_checkable

from .pty_pool import PtyResult


@runtime_checkable
class BashExecutor(Protocol):
    def run(
        self, command: str, timeout: int = 30, workdir: Path | None = None, session_id: str = "main"
    ) -> PtyResult:
        ...

    def send_ctrl_c(self, session_id: str) -> str:
        ...

    def close(self, session_id: str) -> None:
        ...

    def list_sessions(self) -> list[str]:
        ...


class InProcessPtyExecutor(BashExecutor):
    """v0.1: in-process PtyPool, no network, DI via SessionState"""

    def __init__(self, pool: Any):
        self.pool = pool

    @override
    def run(
        self, command: str, timeout: int = 30, workdir: Path | None = None, session_id: str = "main"
    ) -> PtyResult:
        sess = self.pool.acquire(session_id, workdir=str(workdir) if workdir else None)
        return sess.run(command, timeout=timeout)

    @override
    def send_ctrl_c(self, session_id: str) -> str:
        if session_id in self.pool.sessions:
            return self.pool.sessions[session_id].send_ctrl_c()
        return "session not found"

    @override
    def close(self, session_id: str) -> None:
        self.pool.kill(session_id)

    @override
    def list_sessions(self) -> list[str]:
        return self.pool.list_sessions()


class RemoteRuntimeExecutor(BashExecutor):
    """Future: thin client to fa-runtime-server FastAPI, POST /execute"""

    def __init__(self, base_url: str = "http://fa-runtime-server:8001", timeout: int = 5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @override
    def run(
        self, command: str, timeout: int = 30, workdir: Path | None = None, session_id: str = "main"
    ) -> PtyResult:
        import requests

        try:
            resp = requests.post(
                f"{self.base_url}/execute",
                json={
                    "session_id": session_id,
                    "command": command,
                    "timeout": timeout,
                    "workdir": str(workdir) if workdir else None,
                },
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
            print(f"WARNING: RemoteRuntimeExecutor failed {e}, falling back")
            raise

    @override
    def send_ctrl_c(self, session_id: str) -> str:
        import requests

        resp = requests.post(f"{self.base_url}/send_ctrl_c?session_id={session_id}", timeout=self.timeout)
        return resp.json().get("msg", "")

    @override
    def close(self, session_id: str) -> None:
        import requests

        requests.post(f"{self.base_url}/kill", json={"session_id": session_id}, timeout=self.timeout)

    @override
    def list_sessions(self) -> list[str]:
        import requests

        resp = requests.get(f"{self.base_url}/list", timeout=self.timeout)
        return resp.json().get("sessions", [])
