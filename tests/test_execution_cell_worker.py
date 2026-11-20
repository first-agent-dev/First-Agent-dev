"""C0/C3 local PTY/stream adapter proof, NOT a Docker or host isolation test."""

from __future__ import annotations

import base64
import json
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import fa.execution.cell_worker as cell_worker
from fa.execution.cell_protocol import decode_cell_reply, decode_cell_request, encode_cell_request
from fa.execution.cell_worker import CellWorker, serve
from fa.execution.protocol import (
    MAX_PROJECT_TOOL_ENVELOPE_BYTES,
    MAX_PROJECT_TOOL_REPLY_FRAME_BYTES,
    MAX_PROJECT_TOOL_REQUEST_BYTES,
    MAX_PROJECT_TOOL_TIMEOUT_MS,
    MAX_TAIL_BYTES,
    _loads,
    encode_json,
    read_frame,
    write_frame,
)
from fa.execution.types import ExecutionContractError
from fa.runtime.pty_pool import PtyPool, PtyResult, PtySession


@pytest.fixture
def worker(tmp_path: Path) -> Iterator[CellWorker]:
    pool = PtyPool(base_cwd=tmp_path, run_id="cell-unit")
    worker = CellWorker(pool, workspace=tmp_path, max_command_ms=3000)
    try:
        yield worker
    finally:
        worker.close()


def message(action: str, payload: dict[str, Any], request_id: str = "1" * 32) -> bytes:
    return encode_json({"version": 1, "request_id": request_id, "action": action, "payload": payload})


def run_message(
    command: str,
    *,
    cwd: str = ".",
    timeout_ms: int = 2000,
    request_id: str = "1" * 32,
    session_id: str | None = "main",
) -> bytes:
    return message(
        "RUN", {"command": command, "cwd": cwd, "timeout_ms": timeout_ms, "session_id": session_id}, request_id
    )


def project_message(*, tool: str = "fs_search", params: dict[str, Any] | None = None, timeout_ms: int = 1000) -> bytes:
    return message(
        "PROJECT_TOOL",
        {"tool": tool, "params": {"query": "needle"} if params is None else params, "timeout_ms": timeout_ms},
    )


def test_project_tool_private_codec_is_closed_and_bounded() -> None:
    request = encode_cell_request(
        request_id="1" * 32,
        action="PROJECT_TOOL",
        payload={"tool": "fs_search", "params": {"query": "needle"}, "timeout_ms": 1000},
    )
    assert decode_cell_request(request)["action"] == "PROJECT_TOOL"
    for payload in (
        {"tool": "fs_run_bash", "params": {}, "timeout_ms": 1000},
        {"tool": "fs_search", "params": {}, "timeout_ms": MAX_PROJECT_TOOL_TIMEOUT_MS + 1},
        {"tool": "fs_search", "params": {"query": "x" * (MAX_PROJECT_TOOL_REQUEST_BYTES + 1)}, "timeout_ms": 1000},
        {"tool": "fs_search", "params": {}, "timeout_ms": 1000, "command": "sentinel"},
    ):
        with pytest.raises(ExecutionContractError):
            decode_cell_request(message("PROJECT_TOOL", payload))

    reply = encode_json(
        {
            "version": 1,
            "request_id": "1" * 32,
            "result": {"stdout": "{}", "exit_code": 0, "truncated": False, "session_id": None, "timed_out": False},
            "error": None,
        }
    )
    assert decode_cell_reply(reply, request_id="1" * 32, action="PROJECT_TOOL", session_id=None) is not None
    too_long = encode_json(
        {
            "version": 1,
            "request_id": "1" * 32,
            "result": {
                "stdout": "x" * (MAX_PROJECT_TOOL_ENVELOPE_BYTES + 1),
                "exit_code": 0,
                "truncated": False,
                "session_id": None,
                "timed_out": False,
            },
            "error": None,
        }
    )
    with pytest.raises(ExecutionContractError):
        decode_cell_reply(too_long, request_id="1" * 32, action="PROJECT_TOOL", session_id=None)


def test_real_local_pty_preserves_export_cwd_and_full_result(worker: CellWorker, tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    exported = worker.handle(run_message("export FA_CELL_UNIT=kept"))
    assert exported["exit_code"] == 0 and exported["timed_out"] is False
    assert worker.handle(run_message("cd sub"))["exit_code"] == 0
    observed = worker.handle(run_message('printf "%s\\n" "$FA_CELL_UNIT"; pwd'))
    assert "kept" in observed["stdout"] and str(tmp_path / "sub") in observed["stdout"]
    assert set(observed) == {"stdout", "exit_code", "truncated", "session_id", "timed_out"}
    assert worker.handle(message("LIST", {}))["sessions"] == ["main"]
    assert worker.handle(message("CLOSE", {"session_id": "main"}))["sessions"] == []
    # Empty registry proves only adapter state, NOT a descendant barrier.


@pytest.mark.parametrize(
    "payload", [{"capability": "a" * 64}, {"namespace": {}}, {"command": "touch forbidden"}, {"host_path": "/etc"}]
)
def test_unknown_control_data_never_reaches_pty(worker: CellWorker, payload: dict[str, Any], tmp_path: Path) -> None:
    with pytest.raises(ExecutionContractError):
        worker.handle(message("RUN", payload))
    assert worker.handle(message("LIST", {}))["sessions"] == []
    assert not (tmp_path / "forbidden").exists()


def test_project_tool_uses_fixed_helper_argv_without_pty(worker: CellWorker, monkeypatch: pytest.MonkeyPatch) -> None:
    real_popen = subprocess.Popen
    calls: list[tuple[list[str], dict[str, Any]]] = []
    envelope = '{"summary":"ok","result":{},"error":null,"artifacts":[]}'

    def forbidden_pty(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("PROJECT_TOOL must not acquire a PTY")

    def launch(argv: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        calls.append((argv, kwargs))
        assert argv[:4] == [sys.executable, "-I", "-m", "fa.execution.project_tools"]
        decoded = json.loads(base64.b64decode(argv[4], validate=True))
        assert decoded == {"tool": "fs_search", "params": {"query": "needle"}}
        assert kwargs["cwd"] == str(worker._workspace)
        assert kwargs["start_new_session"] is True
        assert kwargs.get("shell", False) is False
        assert kwargs["stdin"] == subprocess.DEVNULL
        return real_popen(
            [sys.executable, "-c", "import sys; sys.stdout.write(sys.argv[1] + '\\n')", envelope], **kwargs
        )

    monkeypatch.setattr(PtyPool, "acquire", forbidden_pty)
    monkeypatch.setattr(subprocess, "Popen", launch)
    result = worker.handle(project_message())
    assert result == {
        "stdout": envelope,
        "exit_code": 0,
        "truncated": False,
        "session_id": None,
        "timed_out": False,
    }
    assert len(calls) == 1


@pytest.mark.parametrize("tool", ["fs_search", "fs_reach"])
@pytest.mark.parametrize("interactive", [False, True])
@pytest.mark.parametrize("over", [False, True])
def test_project_tool_double_escaped_frame_boundary_is_explicit(
    worker: CellWorker, monkeypatch: pytest.MonkeyPatch, tool: str, interactive: bool, over: bool
) -> None:
    from io import BytesIO

    from fa.execution.cell_worker import _StdioConnection, serve_once
    from fa.execution.project_tools import _envelope
    from fa.inner_loop.registry import ToolResult

    def envelope(filler: int) -> str:
        return _envelope(ToolResult.ok("ok", result={"text": '"' * 16_000 + "x" * filler}))

    def frame_size(stdout: str) -> int:
        return 4 + len(
            encode_json(
                {
                    "version": 1,
                    "request_id": "1" * 32,
                    "result": {
                        "stdout": stdout,
                        "exit_code": 0,
                        "truncated": False,
                        "session_id": None,
                        "timed_out": False,
                    },
                    "error": None,
                }
            )
        )

    filler = MAX_PROJECT_TOOL_REPLY_FRAME_BYTES - frame_size(envelope(0))
    assert filler > 0
    output = envelope(filler + int(over))
    assert len(output.encode("ascii")) <= MAX_PROJECT_TOOL_ENVELOPE_BYTES
    assert frame_size(output) == MAX_PROJECT_TOOL_REPLY_FRAME_BYTES + int(over)
    real_popen = subprocess.Popen

    def launch(argv: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        return real_popen([sys.executable, "-c", "import sys; print(sys.argv[1])", output], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", launch)
    raw = project_message(tool=tool)
    if interactive:
        left, right = socket.socketpair()
        thread = threading.Thread(target=serve, args=(worker, right))
        thread.start()
        try:
            left.settimeout(5)
            write_frame(left, raw)
            response_raw = read_frame(left, max_bytes=MAX_PROJECT_TOOL_REPLY_FRAME_BYTES - 4)
            write_frame(left, message("STOP", {}, "2" * 32))
            read_frame(left)
        finally:
            left.close()
            thread.join(timeout=5)
            right.close()
        assert not thread.is_alive()
    else:
        destination = BytesIO()
        assert serve_once(worker, _StdioConnection(BytesIO(len(raw).to_bytes(4, "big") + raw), destination)) == 0
        assert len(destination.getvalue()) <= MAX_PROJECT_TOOL_REPLY_FRAME_BYTES
        response_raw = read_frame(_StdioConnection(BytesIO(destination.getvalue()), BytesIO()))
    assert len(response_raw) + 4 <= MAX_PROJECT_TOOL_REPLY_FRAME_BYTES
    result = decode_cell_reply(response_raw, request_id="1" * 32, action="PROJECT_TOOL", session_id=None)
    assert result is not None and result["exit_code"] == 0 and result["truncated"] is False
    returned = json.loads(result["stdout"])
    if over:
        assert returned["result"] is None and returned["artifacts"] == []
        assert returned["error"] == {
            "code": "search_failed" if tool == "fs_search" else "reach_failed",
            "message": "managed discovery refused (output_budget)",
            "retryable": False,
        }
    else:
        assert result["stdout"] == output and returned["error"] is None


def test_near_60_kib_plain_project_envelope_is_not_refused() -> None:
    from io import BytesIO

    from fa.execution.cell_worker import _StdioConnection
    from fa.execution.project_tools import _envelope
    from fa.inner_loop.registry import ToolResult

    envelope = _envelope(ToolResult.ok("ok", result={"text": "x" * 61_000}))
    assert 61_000 < len(envelope) <= MAX_PROJECT_TOOL_ENVELOPE_BYTES
    result = {"stdout": envelope, "exit_code": 0, "truncated": False, "session_id": None, "timed_out": False}
    output = BytesIO()
    cell_worker._reply(_StdioConnection(BytesIO(), output), "1" * 32, result, project_tool="fs_search")
    raw = read_frame(_StdioConnection(BytesIO(output.getvalue()), BytesIO()))
    decoded = decode_cell_reply(raw, request_id="1" * 32, action="PROJECT_TOOL", session_id=None)
    assert len(output.getvalue()) <= MAX_PROJECT_TOOL_REPLY_FRAME_BYTES
    assert decoded == result


@pytest.mark.parametrize("failure", ["nonzero", "timeout", "truncated"])
def test_oversized_project_frame_preserves_worker_failure_flags(failure: str) -> None:
    from io import BytesIO

    from fa.execution.cell_worker import _StdioConnection

    result = {
        "stdout": '"' * MAX_PROJECT_TOOL_ENVELOPE_BYTES,
        "exit_code": 7 if failure == "nonzero" else 0,
        "truncated": failure == "truncated",
        "session_id": None,
        "timed_out": failure == "timeout",
    }
    output = BytesIO()
    cell_worker._reply(_StdioConnection(BytesIO(), output), "1" * 32, result, project_tool="fs_search")
    assert len(output.getvalue()) <= MAX_PROJECT_TOOL_REPLY_FRAME_BYTES
    raw = read_frame(_StdioConnection(BytesIO(output.getvalue()), BytesIO()))
    decoded = decode_cell_reply(raw, request_id="1" * 32, action="PROJECT_TOOL", session_id=None)
    assert decoded is not None
    assert decoded == {**result, "stdout": ""}


def test_project_tool_child_output_overrun_is_truncated_non_success(
    worker: CellWorker, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_popen = subprocess.Popen

    def launch(argv: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        script = "import sys;sys.stdout.write('x' * " + str(MAX_PROJECT_TOOL_ENVELOPE_BYTES + 20) + " + '\\n')"
        return real_popen([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", launch)
    result = worker.handle(project_message())
    assert result["truncated"] is True
    assert result["exit_code"] != 0
    assert len(result["stdout"].encode()) <= MAX_PROJECT_TOOL_ENVELOPE_BYTES + 1


def test_project_tool_timeout_kills_and_reaps_its_child_group(
    worker: CellWorker, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_popen = subprocess.Popen
    helper = (
        "import subprocess,sys,time;"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)']);"
        "print(child.pid,flush=True);time.sleep(10)"
    )

    def launch(argv: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        return real_popen([sys.executable, "-c", helper], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", launch)
    result = worker.handle(project_message(timeout_ms=100))
    assert result["timed_out"] is True
    assert result["exit_code"] < 0
    child_pids = [int(pid) for pid in result["stdout"].split() if pid.isdigit()]
    assert child_pids
    for _ in range(100):
        states = []
        for pid in child_pids:
            stat_path = Path(f"/proc/{pid}/stat")
            states.append(None if not stat_path.exists() else stat_path.read_text().split()[2])
        if all(state in {None, "Z"} for state in states):
            break
        time.sleep(0.01)
    assert all(state in {None, "Z"} for state in states)


@pytest.mark.parametrize("cwd", ["../escape", "/", "missing", "link"])
def test_missing_or_escaping_cwd_starts_no_session(worker: CellWorker, tmp_path: Path, cwd: str) -> None:
    (tmp_path / "link").symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ExecutionContractError):
        worker.handle(run_message("touch forbidden", cwd=cwd))
    assert worker.handle(message("LIST", {}))["sessions"] == []
    assert not (tmp_path / "forbidden").exists()


def test_fractional_seconds_timeout_is_preserved_not_normal_completion(worker: CellWorker) -> None:
    result = worker.handle(run_message("sleep 5", timeout_ms=50))
    assert result["timed_out"] is True
    assert result["exit_code"] != 0


def test_stream_can_interrupt_one_active_run_and_stop_without_fabricated_barrier(
    worker: CellWorker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The test server itself runs in a thread; pre-create its real PTY on the
    # test main thread, matching the production main-thread acquisition rule.
    assert worker.handle(run_message("true"))["exit_code"] == 0
    started, interrupted = threading.Event(), threading.Event()

    def waiting(self: PtySession, command: str, timeout: float = 30) -> PtyResult:
        started.set()
        assert interrupted.wait(2), "control message never reached the active session"
        return PtyResult("interrupted", 130, False, self.session_id)

    def interrupt(self: PtySession) -> str:
        interrupted.set()
        return "interrupt acknowledged"

    monkeypatch.setattr(PtySession, "run", waiting)
    monkeypatch.setattr(PtySession, "send_ctrl_c", interrupt)
    left, right = socket.socketpair()
    errors: list[BaseException] = []

    def background() -> None:
        try:
            serve(worker, right)
        except (OSError, ExecutionContractError) as error:
            errors.append(error)

    thread = threading.Thread(target=background)
    with left, right:
        left.settimeout(3)
        thread.start()
        try:
            write_frame(left, run_message("unit fixture, not executed"))
            assert started.wait(2)
            write_frame(left, message("INTERRUPT", {"session_id": "main"}, "2" * 32))
            results = [_loads(read_frame(left)), _loads(read_frame(left))]
            indexed = {r["request_id"]: r for r in results}
            assert indexed["1" * 32]["result"]["exit_code"] == 130
            assert indexed["2" * 32]["result"]["message"] == "interrupt acknowledged"
            assert all(r["error"] is None for r in results)
            write_frame(left, message("STOP", {}, "3" * 32))
            stopped = _loads(read_frame(left))
            assert stopped == {
                "version": 1,
                "request_id": "3" * 32,
                "result": {"sessions": [], "message": ""},
                "error": None,
            }
        finally:
            interrupted.set()
            left.shutdown(socket.SHUT_RDWR)
            thread.join(3)
    assert not thread.is_alive() and errors == []
    assert worker.stopped is True
    with pytest.raises(ExecutionContractError):
        worker.handle(run_message("not after STOP"))


def test_worker_utf8_tail_bound_and_error_output_are_not_receipts(
    worker: CellWorker, monkeypatch: pytest.MonkeyPatch
) -> None:
    def output(self: PtySession, command: str, timeout: float = 30) -> PtyResult:
        return PtyResult("😀" * MAX_TAIL_BYTES, 2, False, self.session_id)

    monkeypatch.setattr(PtySession, "run", output)
    result = worker.handle(run_message("unit fixture, not executed"))
    assert len(result["stdout"].encode()) <= MAX_TAIL_BYTES
    assert result["truncated"] is True and result["exit_code"] == 2
    assert "receipt" not in result and "terminal_barrier" not in result


def test_worker_refuses_missing_legacy_runner_instead_of_normal_exit(
    worker: CellWorker, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing(self: PtySession, command: str, timeout: float = 30) -> PtyResult:
        return PtyResult("No fallback available", -1, False, self.session_id)

    monkeypatch.setattr(PtySession, "run", missing)
    with pytest.raises(ExecutionContractError):
        worker.handle(run_message("unit fixture, not executed"))


def test_complete_payload_with_extra_authority_is_denied_before_side_effect(worker: CellWorker, tmp_path: Path) -> None:
    payload = {
        "command": "touch forbidden",
        "cwd": ".",
        "timeout_ms": 1000,
        "session_id": "main",
        "capability": "a" * 64,
    }
    with pytest.raises(ExecutionContractError):
        worker.handle(message("RUN", payload))
    assert not (tmp_path / "forbidden").exists()
    assert worker.handle(message("LIST", {}))["sessions"] == []


@pytest.mark.parametrize("exit_code", [0, 7, 78, 124, 255])
def test_one_shot_real_pty_exits_with_command_and_never_executes_second_run(
    worker: CellWorker, tmp_path: Path, exit_code: int
) -> None:
    from io import BytesIO

    from fa.execution.cell_worker import _StdioConnection, serve_once

    def frame(raw: bytes) -> bytes:
        return len(raw).to_bytes(4, "big") + raw

    first = run_message(f"printf observed; touch first; (exit {exit_code})")
    second = run_message("touch second", request_id="2" * 32)
    output = BytesIO()
    status = serve_once(worker, _StdioConnection(BytesIO(frame(first) + frame(second)), output))
    response = _loads(read_frame(_StdioConnection(BytesIO(output.getvalue()), BytesIO())))
    assert status == exit_code
    assert response["request_id"] == "1" * 32 and response["error"] is None
    assert response["result"]["exit_code"] == exit_code and response["result"]["timed_out"] is False
    assert "observed" in response["result"]["stdout"]
    assert worker.stopped and worker._pool.list_sessions() == []
    assert (tmp_path / "first").exists() and not (tmp_path / "second").exists()
    assert "terminal_barrier" not in response["result"]


def test_one_shot_timeout_is_not_normal_worker_or_command_success(worker: CellWorker) -> None:
    from io import BytesIO

    from fa.execution.cell_worker import _StdioConnection, serve_once

    raw = run_message("sleep 5", timeout_ms=50)
    output = BytesIO()
    status = serve_once(worker, _StdioConnection(BytesIO(len(raw).to_bytes(4, "big") + raw), output))
    response = _loads(read_frame(_StdioConnection(BytesIO(output.getvalue()), BytesIO())))
    assert status == 78 and response["result"]["timed_out"] is True
    assert response["result"]["exit_code"] != 0
    assert worker.stopped and worker._pool.list_sessions() == []


def test_noninteractive_one_shot_accepts_null_session_and_returns_no_reusable_session(tmp_path: Path) -> None:
    from io import BytesIO

    from fa.execution.cell_worker import _StdioConnection, serve_once

    one_shot = CellWorker(
        PtyPool(base_cwd=tmp_path, run_id="cell-one-shot"),
        workspace=tmp_path,
        max_command_ms=3000,
        one_shot=True,
    )
    raw = run_message("printf one-shot; touch completed", session_id=None)
    output = BytesIO()
    status = serve_once(one_shot, _StdioConnection(BytesIO(len(raw).to_bytes(4, "big") + raw), output))
    response = _loads(read_frame(_StdioConnection(BytesIO(output.getvalue()), BytesIO())))
    assert status == 0
    assert response["result"]["session_id"] is None
    assert "one-shot" in response["result"]["stdout"]
    assert one_shot.stopped and one_shot._pool.list_sessions() == []
    assert (tmp_path / "completed").exists()


def test_interactive_worker_rejects_a_null_session_before_creating_a_pty(worker: CellWorker) -> None:
    with pytest.raises(ExecutionContractError):
        worker.handle(run_message("touch forbidden", session_id=None))
    assert worker._pool.list_sessions() == []


@pytest.mark.parametrize("bad", ["LIST", "missing-cwd", "unknown-key", "invalid-id", "short-frame"])
def test_one_shot_bad_input_starts_no_project_command(worker: CellWorker, tmp_path: Path, bad: str) -> None:
    from io import BytesIO

    from fa.execution.cell_worker import _StdioConnection, serve_once

    raw = run_message("touch forbidden")
    if bad == "LIST":
        raw = message("LIST", {})
    elif bad == "missing-cwd":
        raw = run_message("touch forbidden", cwd="missing")
    elif bad == "unknown-key":
        value = _loads(raw)
        value["payload"]["capability"] = "f" * 64
        raw = encode_json(value)
    elif bad == "invalid-id":
        raw = run_message("touch forbidden", request_id="invalid")
    framed = len(raw).to_bytes(4, "big") + (raw[:-1] if bad == "short-frame" else raw)
    output = BytesIO()
    connection = _StdioConnection(BytesIO(framed), output)
    if bad in {"LIST", "missing-cwd"}:
        assert serve_once(worker, connection) == 78
        response = _loads(read_frame(_StdioConnection(BytesIO(output.getvalue()), BytesIO())))
        assert response["result"] is None and response["error"] == "WORKER_UNAVAILABLE"
    else:
        with pytest.raises(ExecutionContractError):
            serve_once(worker, connection)
        assert output.getvalue() == b""
    assert worker.stopped and worker._pool.list_sessions() == [] and not (tmp_path / "forbidden").exists()


def test_one_shot_main_selects_real_worker_status_with_fixed_cell_paths_substituted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys
    from io import BytesIO, TextIOWrapper

    from fa.execution import cell_worker

    raw = run_message("touch main-ran; (exit 7)", session_id=None)
    output = BytesIO()

    def fixed_path(path: str) -> Path:
        return tmp_path if path == "/workspace" else tmp_path / path.lstrip("/")

    monkeypatch.setattr(cell_worker, "Path", fixed_path)
    monkeypatch.setattr(sys, "argv", ["cell_worker", "--max-command-ms", "3000", "--one-shot"])
    monkeypatch.setattr(sys, "stdin", TextIOWrapper(BytesIO(len(raw).to_bytes(4, "big") + raw)))
    monkeypatch.setattr(sys, "stdout", TextIOWrapper(output))
    assert cell_worker.main() == 7
    response = _loads(read_frame(cell_worker._StdioConnection(BytesIO(output.getvalue()), BytesIO())))
    assert response["result"]["exit_code"] == 7 and response["error"] is None
    assert (tmp_path / "main-ran").exists()
