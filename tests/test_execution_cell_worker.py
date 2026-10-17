"""C0/C3 local PTY/stream adapter proof, NOT a Docker or host isolation test."""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from fa.execution.cell_worker import CellWorker, serve
from fa.execution.protocol import MAX_TAIL_BYTES, _loads, encode_json, read_frame, write_frame
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


def run_message(command: str, *, cwd: str = ".", timeout_ms: int = 2000, request_id: str = "1" * 32) -> bytes:
    return message("RUN", {"command": command, "cwd": cwd, "timeout_ms": timeout_ms, "session_id": "main"}, request_id)


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

    raw = run_message("touch main-ran; (exit 7)")
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
