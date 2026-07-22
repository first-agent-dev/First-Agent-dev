"""
BashExecutor Protocol — interface segregation, senior eng
Protocol abstraction allows switching InProcess ↔ Remote via feature flag without changing callers
ADR-13 final
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, TypedDict, cast, override, runtime_checkable

from .pty_pool import PtyResult

logger = logging.getLogger(__name__)


@runtime_checkable
class BashExecutor(Protocol):
    def run(
        self, command: str, timeout: int = 30, workdir: Path | None = None, session_id: str = "main"
    ) -> PtyResult:
        pass

    def send_ctrl_c(self, session_id: str) -> str: ...

    def close(self, session_id: str) -> None: ...

    def list_sessions(self) -> list[str]: ...


class _PtySessionLike(Protocol):
    def run(self, command: str, timeout: int = 30) -> PtyResult: ...

    def send_ctrl_c(self) -> str: ...


class _PtyPoolLike(Protocol):
    sessions: dict[str, _PtySessionLike]

    def acquire(self, session_id: str, workdir: str | None = None) -> _PtySessionLike: ...

    def kill(self, session_id: str) -> None: ...

    def list_sessions(self) -> list[str]: ...


class InProcessPtyExecutor(BashExecutor):
    """v0.1: in-process PtyPool, no network, DI via SessionState."""

    def __init__(self, pool: _PtyPoolLike):
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


class _RemotePtyResponse(TypedDict):
    stdout: str
    exit_code: int
    truncated: bool
    session_id: str


class _RemoteSessionsResponse(TypedDict):
    sessions: list[str]


class _RemoteMessageResponse(TypedDict):
    msg: str


class RemoteRuntimeExecutor(BashExecutor):
    """Future: thin client to fa-runtime-server FastAPI, POST /execute."""

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
            data = cast(_RemotePtyResponse, resp.json())
            return PtyResult(
                stdout=data["stdout"],
                exit_code=data["exit_code"],
                truncated=data["truncated"],
                session_id=data["session_id"],
            )
        except Exception as e:  # graceful degradation per Phase 0.5, failure-observable WARNING
            logger.warning(f"RemoteRuntimeExecutor failed {e}, falling back")
            raise

    @override
    def send_ctrl_c(self, session_id: str) -> str:
        import requests

        resp = requests.post(f"{self.base_url}/send_ctrl_c?session_id={session_id}", timeout=self.timeout)
        data = cast(_RemoteMessageResponse, resp.json())
        return data.get("msg", "")

    @override
    def close(self, session_id: str) -> None:
        import requests

        requests.post(f"{self.base_url}/kill", json={"session_id": session_id}, timeout=self.timeout)

    @override
    def list_sessions(self) -> list[str]:
        import requests

        resp = requests.get(f"{self.base_url}/list", timeout=self.timeout)
        data = cast(_RemoteSessionsResponse, resp.json())
        return data.get("sessions", [])
