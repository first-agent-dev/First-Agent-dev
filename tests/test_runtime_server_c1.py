from __future__ import annotations

from typing import Any, cast

import pytest

import fa.runtime.server as server
from fa.runtime.pty_pool import PtyResult


class _Session:
    def __init__(self, result: PtyResult | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.ctrl_c_calls = 0

    def run(self, command: str, timeout: int = 30) -> PtyResult:
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result

    def send_ctrl_c(self) -> str:
        self.ctrl_c_calls += 1
        return "Ctrl+C sent"


class _Pool:
    max_size = 2

    def __init__(self, session: _Session) -> None:
        self.session = session
        self.sessions: dict[str, _Session] = {"main": session}
        self.killed: list[str] = []

    def acquire(self, session_id: str, workdir: str | None = None) -> _Session:
        if session_id == "bad":
            raise AssertionError("bad workdir")
        return self.session

    def list_sessions(self) -> list[str]:
        return sorted(self.sessions)

    def kill(self, session_id: str) -> None:
        self.killed.append(session_id)
        self.sessions.pop(session_id, None)


@pytest.mark.skipif(not server.HAS_FASTAPI, reason="runtime server extra is deferred")
def test_runtime_server_endpoints_live_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    result = PtyResult(stdout="ok", exit_code=0, truncated=False, session_id="main")
    pool = _Pool(_Session(result=result))
    monkeypatch.setattr(server, "runtime_pool", pool)

    response = server.execute(server.ExecuteRequest(command="echo ok"))
    assert response.stdout == "ok"
    assert response.exit_code == 0
    assert server.list_sessions() == {"sessions": ["main"]}
    assert server.health() == {"status": "ok", "sessions": 1, "max_size": 2}
    assert server.send_ctrl_c("main")["msg"] == "Ctrl+C sent"
    assert server.kill_session(server.KillRequest(session_id="main")) == {"killed": "main"}
    assert pool.killed == ["main"]


@pytest.mark.skipif(not server.HAS_FASTAPI, reason="runtime server extra is deferred")
def test_runtime_server_errors_are_structured_http_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = _Pool(_Session(result=None, error=RuntimeError("boom")))
    monkeypatch.setattr(server, "runtime_pool", pool)

    with pytest.raises(Exception) as exc_info:
        server.execute(server.ExecuteRequest(command="fail"))
    error = cast(Any, exc_info.value)
    assert error.status_code == 500
    assert error.detail == "boom"

    with pytest.raises(Exception) as exc_info:
        server.execute(server.ExecuteRequest(command="bad", session_id="bad"))
    assert cast(Any, exc_info.value).status_code == 400

    with pytest.raises(Exception) as exc_info:
        server.send_ctrl_c("missing")
    assert cast(Any, exc_info.value).status_code == 404

    with pytest.raises(Exception) as exc_info:
        server.kill_session(server.KillRequest(session_id="missing"))
    assert cast(Any, exc_info.value).status_code == 404
