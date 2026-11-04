from __future__ import annotations

import subprocess
from typing import Any, cast

import pytest
import requests

import fa.runtime.server as server
from fa.runtime.bash_executor import RemoteRuntimeExecutor
from fa.runtime.pty_pool import PtyResult


class _Session:
    def __init__(self, result: PtyResult | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.ctrl_c_calls = 0
        self.run_calls: list[tuple[str, int]] = []

    def run(self, command: str, timeout: int = 30) -> PtyResult:
        self.run_calls.append((command, timeout))
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


class _Response:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.status_checked = False

    def raise_for_status(self) -> None:
        self.status_checked = True

    def json(self) -> object:
        return self.payload


def _execute_http_route(payload: dict[str, object]) -> _Response:
    request = cast(Any, server.ExecuteRequest).model_validate(payload)
    response = server.execute(request)
    return _Response(response.model_dump())


@pytest.mark.skipif(not server.HAS_FASTAPI, reason="runtime server extra is deferred")
def test_runtime_server_endpoints_live_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    result = PtyResult(stdout="ok", exit_code=0, truncated=False, session_id="main")
    pool = _Pool(_Session(result=result))
    monkeypatch.setattr(server, "runtime_pool", pool)

    response = server.execute(server.ExecuteRequest(command="echo ok"))
    assert response.stdout == "ok"
    assert response.exit_code == 0
    assert response.timed_out is False
    assert server.list_sessions() == {"sessions": ["main"]}
    assert server.send_ctrl_c("main")["msg"] == "Ctrl+C sent"
    assert server.kill_session(server.KillRequest(session_id="main")) == {"killed": "main"}
    assert pool.killed == ["main"]


@pytest.mark.skipif(not server.HAS_FASTAPI, reason="runtime server extra is deferred")
def test_http_health_never_certifies_terminality(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = _Pool(_Session(result=PtyResult(stdout="", exit_code=0, truncated=False, session_id="main")))
    monkeypatch.setattr(server, "runtime_pool", pool)

    health = server.health()

    assert health == {"status": "ok", "sessions": 1, "max_size": 2}
    assert not {"terminal", "terminated", "descendants_stopped", "barrier"} & set(health)


@pytest.mark.skipif(not server.HAS_FASTAPI, reason="runtime server extra is deferred")
def test_remote_executor_preserves_timeout_through_execute_route(monkeypatch: pytest.MonkeyPatch) -> None:
    timed_out_result = PtyResult(
        stdout="partial output",
        exit_code=-1,
        truncated=False,
        session_id="main",
        timed_out=True,
    )
    pool = _Pool(_Session(result=timed_out_result))
    monkeypatch.setattr(server, "runtime_pool", pool)
    calls: list[tuple[str, dict[str, object], int]] = []
    responses: list[_Response] = []

    def fake_post(url: str, *, json: dict[str, object], timeout: int) -> _Response:
        calls.append((url, json, timeout))
        response = _execute_http_route(json)
        responses.append(response)
        return response

    monkeypatch.setattr(requests, "post", fake_post)
    result = RemoteRuntimeExecutor("http://runtime", timeout=7).run("sleep 9", timeout=3, session_id="main")

    assert result == timed_out_result
    assert result.timed_out is True
    assert calls == [
        (
            "http://runtime/execute",
            {"session_id": "main", "command": "sleep 9", "timeout": 3, "workdir": None},
            7,
        )
    ]
    assert responses[0].status_checked is True
    assert pool.session.run_calls == [("sleep 9", 3)]


@pytest.mark.skipif(not server.HAS_FASTAPI, reason="runtime server extra is deferred")
def test_remote_executor_rejects_foreign_session_without_host_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = _Pool(_Session(result=PtyResult(stdout="wrong", exit_code=0, truncated=False, session_id="other")))
    monkeypatch.setattr(server, "runtime_pool", pool)
    requests_seen: list[str] = []
    host_process_calls: list[tuple[object, ...]] = []

    def fake_post(url: str, *, json: dict[str, object], timeout: int) -> _Response:
        requests_seen.append(url)
        return _execute_http_route(json)

    def forbidden_host_process(*args: object, **kwargs: object) -> None:
        host_process_calls.append(args)
        raise AssertionError("remote failure must not execute a host process")

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(subprocess, "run", forbidden_host_process)
    monkeypatch.setattr(subprocess, "Popen", forbidden_host_process)

    with pytest.raises(ValueError, match="session identity mismatch"):
        RemoteRuntimeExecutor("http://runtime").run("echo wrong", session_id="main")

    assert requests_seen == ["http://runtime/execute"]
    assert pool.session.run_calls == [("echo wrong", 30)]
    assert host_process_calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {"stdout": "out", "exit_code": 0, "truncated": False, "session_id": "main"},
        {"stdout": "out", "exit_code": 0, "truncated": False, "session_id": "main", "timed_out": "false"},
    ],
    ids=["missing-timeout", "invalid-timeout-type"],
)
def test_remote_executor_rejects_unknown_response_without_host_fallback(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    requests_seen: list[str] = []
    host_process_calls: list[tuple[object, ...]] = []

    def fake_post(url: str, *, json: dict[str, object], timeout: int) -> _Response:
        requests_seen.append(url)
        return _Response(payload)

    def forbidden_host_process(*args: object, **kwargs: object) -> None:
        host_process_calls.append(args)
        raise AssertionError("invalid remote response must not execute a host process")

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(subprocess, "run", forbidden_host_process)
    monkeypatch.setattr(subprocess, "Popen", forbidden_host_process)

    with pytest.raises(ValueError, match="Invalid remote PTY response"):
        RemoteRuntimeExecutor("http://runtime").run("echo untrusted", session_id="main")

    assert requests_seen == ["http://runtime/execute"]
    assert host_process_calls == []


@pytest.mark.skipif(not server.HAS_FASTAPI, reason="runtime server extra is deferred")
def test_remote_close_never_reports_descendant_barrier(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = _Pool(_Session(result=PtyResult(stdout="", exit_code=0, truncated=False, session_id="main")))
    monkeypatch.setattr(server, "runtime_pool", pool)
    response_payloads: list[dict[str, str]] = []

    def fake_post(url: str, *, json: dict[str, object], timeout: int) -> _Response:
        assert url == "http://runtime/kill"
        request = cast(Any, server.KillRequest).model_validate(json)
        payload = server.kill_session(request)
        response_payloads.append(payload)
        return _Response(payload)

    monkeypatch.setattr(requests, "post", fake_post)

    result = RemoteRuntimeExecutor("http://runtime").close("main")

    assert result is None
    assert pool.killed == ["main"]
    assert response_payloads == [{"killed": "main"}]
    assert not {"terminal", "terminated", "descendants_stopped", "barrier"} & set(response_payloads[0])


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
