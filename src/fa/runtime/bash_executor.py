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
    def run(self, command: str, timeout: int = 30, workdir: Path | None = None, session_id: str | None = "main") -> PtyResult:
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
    def run(self, command: str, timeout: int = 30, workdir: Path | None = None, session_id: str | None = "main") -> PtyResult:
        session_id = session_id or "main"
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
    timed_out: bool


def _decode_remote_pty_response(data: object, requested_session_id: str) -> PtyResult:
    if not isinstance(data, dict):
        raise ValueError("Invalid remote PTY response: expected an object")
    if (
        not isinstance(data.get("stdout"), str)
        or type(data.get("exit_code")) is not int
        or type(data.get("truncated")) is not bool
        or not isinstance(data.get("session_id"), str)
        or type(data.get("timed_out")) is not bool
    ):
        raise ValueError("Invalid remote PTY response: missing or invalid result fields")

    response = cast(_RemotePtyResponse, data)
    if response["session_id"] != requested_session_id:
        raise ValueError("Remote PTY response session identity mismatch")

    return PtyResult(
        stdout=response["stdout"],
        exit_code=response["exit_code"],
        truncated=response["truncated"],
        session_id=response["session_id"],
        timed_out=response["timed_out"],
    )


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
    def run(self, command: str, timeout: int = 30, workdir: Path | None = None, session_id: str | None = "main") -> PtyResult:
        import requests

        session_id = session_id or "main"

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
            return _decode_remote_pty_response(resp.json(), requested_session_id=session_id)
        except Exception as e:  # fail closed; there is no host-side fallback
            logger.warning("RemoteRuntimeExecutor failed: %s", e)
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
