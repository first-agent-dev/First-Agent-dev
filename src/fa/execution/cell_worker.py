"""Cell-local PTY adapter. Never a supervisor, receipt issuer or host runner.

Its JSON output is untrusted worker data. Only the supervisor's protected state
and actual Docker/cgroup observations can establish receipt identity/terminality.
Stdio is a private Docker attach stream, not a project-selected control socket.
"""

from __future__ import annotations

import argparse
import base64
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from fa.execution.cell_protocol import decode_cell_request
from fa.execution.protocol import (
    MAX_PROJECT_TOOL_ENVELOPE_BYTES,
    MAX_PROJECT_TOOL_TIMEOUT_MS,
    MAX_TAIL_BYTES,
    FrameConnection,
    encode_json,
    project_tool_request_bytes,
    read_frame,
    write_frame,
)
from fa.execution.types import ExecutionContractError, _positive_integer
from fa.runtime.pty_pool import PtyPool, PtySession

_PROJECT_TOOL_ENV = {
    "HOME": "/scratch/home",
    "PATH": "/usr/bin:/bin",
    "PYTHONNOUSERSITE": "1",
    "TMPDIR": "/scratch/tmp",
}


def _kill_project_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _drain_project_streams(selector: selectors.BaseSelector, deadline: float) -> tuple[bool, bool]:
    timed_out = False
    truncated = False
    while selector.get_map():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            break
        for key, _ in selector.select(min(remaining, 0.1)):
            chunk = os.read(key.fd, 4096)
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            target, limit = key.data
            if len(target) + len(chunk) > limit:
                truncated = True
                break
            target.extend(chunk)
        if truncated:
            break
    return timed_out, truncated


def _capture_project_tool(process: subprocess.Popen[bytes], *, timeout_ms: int) -> tuple[bytes, bytes, int, bool, bool]:
    if process.stdout is None or process.stderr is None:
        raise ExecutionContractError
    streams = (
        (process.stdout, bytearray(), MAX_PROJECT_TOOL_ENVELOPE_BYTES + 1),
        (process.stderr, bytearray(), MAX_TAIL_BYTES),
    )
    selector = selectors.DefaultSelector()
    try:
        for stream, buffer, limit in streams:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, (buffer, limit))
        deadline = time.monotonic() + timeout_ms / 1000
        timed_out, truncated = _drain_project_streams(selector, deadline)
        if not timed_out and not truncated:
            try:
                process.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
        if timed_out or truncated:
            _kill_project_process_group(process)
        try:
            exit_code = process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            _kill_project_process_group(process)
            try:
                exit_code = process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                raise ExecutionContractError from None
        return bytes(streams[0][1]), bytes(streams[1][1]), exit_code, timed_out, truncated
    except BaseException:
        _kill_project_process_group(process)
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            _kill_project_process_group(process)
        raise
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()


class CellWorker:
    def __init__(self, pool: PtyPool, *, workspace: Path, max_command_ms: int, one_shot: bool = False) -> None:
        _positive_integer(max_command_ms)
        if type(one_shot) is not bool:
            raise ExecutionContractError
        self._pool = pool
        self._workspace = workspace.resolve(strict=True)
        self._max_command_ms = max_command_ms
        self._one_shot = one_shot
        self._one_shot_consumed = False
        self.stopped = False

    def handle(self, raw: bytes) -> dict[str, Any]:
        record = decode_cell_request(raw)
        action, payload = record["action"], record["payload"]
        if self.stopped:
            raise ExecutionContractError
        if action == "STOP":
            self.close()
            self.stopped = True
            return {"sessions": [], "message": ""}
        if action == "RUN":
            return self._run(payload)
        if action == "PROJECT_TOOL":
            return self._project_tool(payload)
        if action == "LIST":
            return {"sessions": self._pool.list_sessions(), "message": ""}
        session_id = payload["session_id"]
        if action == "CLOSE":
            self._pool.kill(session_id)
            return {"sessions": self._pool.list_sessions(), "message": ""}
        if session_id not in self._pool.sessions:
            raise ExecutionContractError
        message = self._pool.sessions[session_id].send_ctrl_c()
        return {"sessions": self._pool.list_sessions(), "message": message}

    def _acquire(self, payload: dict[str, Any]) -> PtySession:
        try:
            cwd = (self._workspace / payload["cwd"]).resolve(strict=True)
            cwd.relative_to(self._workspace)
            if not cwd.is_dir():
                raise ExecutionContractError
        except (OSError, ValueError):
            raise ExecutionContractError from None
        return self._pool.acquire(payload["session_id"], workdir=str(cwd))

    def _run(self, payload: dict[str, Any]) -> dict[str, Any]:
        requested_session_id = payload["session_id"]
        if self._one_shot:
            if requested_session_id is not None or self._one_shot_consumed:
                raise ExecutionContractError
            self._one_shot_consumed = True
            worker_session_id = "oneshot-" + uuid4().hex
        else:
            if requested_session_id is None:
                raise ExecutionContractError
            worker_session_id = requested_session_id
        session = self._acquire({**payload, "session_id": worker_session_id})
        outcome = session.run(payload["command"], timeout=min(payload["timeout_ms"], self._max_command_ms) / 1000)
        if outcome.exit_code < 0 and not outcome.timed_out:
            raise ExecutionContractError  # Legacy missing/EOF fallback is not a normal exit.
        encoded = outcome.stdout.encode("utf-8")
        trimmed = len(encoded) > MAX_TAIL_BYTES
        stdout = encoded[-MAX_TAIL_BYTES:].decode("utf-8", errors="ignore")
        # Preserve all PtyResult fields, including timeout. No identity/receipt,
        # container exit or descendant-barrier assertion comes from the worker.
        return {
            "stdout": stdout,
            "exit_code": outcome.exit_code,
            "truncated": outcome.truncated or trimmed,
            "session_id": None if requested_session_id is None else outcome.session_id,
            "timed_out": outcome.timed_out,
        }

    def _project_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._one_shot:
            if self._one_shot_consumed:
                raise ExecutionContractError
            self._one_shot_consumed = True
        request = project_tool_request_bytes(payload["tool"], payload["params"])
        timeout_ms = min(payload["timeout_ms"], self._max_command_ms, MAX_PROJECT_TOOL_TIMEOUT_MS)
        argv = [sys.executable, "-I", "-m", "fa.execution.project_tools", base64.b64encode(request).decode("ascii")]
        try:
            process = subprocess.Popen(  # noqa: S603 - fixed interpreter/module/argv, bounded JSON is one base64 argument
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self._workspace),
                env=dict(_PROJECT_TOOL_ENV),
                close_fds=True,
                shell=False,
                start_new_session=True,
            )
        except OSError:
            return {"stdout": "", "exit_code": 78, "truncated": False, "session_id": None, "timed_out": False}
        stdout, stderr, exit_code, timed_out, truncated = _capture_project_tool(process, timeout_ms=timeout_ms)
        if stdout.endswith(b"\n"):
            stdout = stdout[:-1]
        else:
            exit_code = 1
        if stderr:
            exit_code = 1
        try:
            output = stdout.decode("utf-8")
        except UnicodeError:
            output = ""
            exit_code = 1
        return {
            "stdout": output,
            "exit_code": exit_code,
            "truncated": truncated,
            "session_id": None,
            "timed_out": timed_out,
        }

    def close(self) -> None:
        for session_id in self._pool.list_sessions():
            self._pool.kill(session_id)
        # This is only PTY cleanup, NOT proof of no remaining cell descendants.


class _StdioConnection:
    def __init__(self, source: BinaryIO, destination: BinaryIO) -> None:
        self._source = source
        self._destination = destination

    def recv(self, size: int, /) -> bytes:
        return self._source.read(size)

    def sendall(self, data: bytes, /) -> None:
        remaining = memoryview(data)
        while remaining:
            written = self._destination.write(remaining)
            if written is None or written <= 0:
                raise OSError("cell_stream_unavailable")
            remaining = remaining[written:]
        self._destination.flush()


def _reply(connection: FrameConnection, request_id: str, result: dict[str, Any] | None) -> None:
    write_frame(
        connection,
        encode_json(
            {
                "version": 1,
                "request_id": request_id,
                "result": result,
                "error": "WORKER_UNAVAILABLE" if result is None else None,
            }
        ),
    )


def serve_once(worker: CellWorker, connection: FrameConnection) -> int:
    """Exactly one RUN or PROJECT_TOOL; no synthetic normal exit for indeterminate execution.

    Worker data is still untrusted. The supervisor must check actual container
    exit and the independent descendant barrier before issuing a receipt.
    """
    try:
        raw = read_frame(connection)
        record = decode_cell_request(raw)
        result: dict[str, Any] | None = None
        if record["action"] in {"RUN", "PROJECT_TOOL"}:
            try:
                result = worker.handle(raw)
                if (
                    type(result["exit_code"]) is not int
                    or type(result["timed_out"]) is not bool
                    or (not result["timed_out"] and not 0 <= result["exit_code"] <= 255)
                ):
                    raise ExecutionContractError
            except (OSError, ExecutionContractError, RuntimeError):
                result = None
        _reply(connection, record["request_id"], result)
        # 78 is worker failure, NOT a command result or timeout attestation.
        return 78 if result is None or result["timed_out"] else result["exit_code"]
    finally:
        worker.stopped = True
        worker.close()  # PTY cleanup, never a cgroup/descendant proof.


def _serve_project_tool(
    worker: CellWorker,
    connection: FrameConnection,
    raw: bytes,
    request_id: str,
    *,
    writes: Any,
    running: Any,
    stream_failed: threading.Event,
) -> None:
    with writes:
        accepted = running.acquire(blocking=False)
    if not accepted:
        with writes:
            try:
                _reply(connection, request_id, None)
            except OSError:
                stream_failed.set()
                worker.stopped = True
        return
    result: dict[str, Any] | None = None
    try:
        try:
            result = worker.handle(raw)
        except (OSError, ExecutionContractError, RuntimeError):
            result = None
    finally:
        with writes:
            try:
                _reply(connection, request_id, result)
            except OSError:
                stream_failed.set()
                worker.stopped = True
            finally:
                running.release()


def serve(worker: CellWorker, connection: FrameConnection) -> None:
    """One active RUN, concurrent controls, bounded memory and correlated replies.

    The background reader belongs to the existing PTY run path; controls never
    compete for its pexpect reader. This is not parallel job orchestration.
    """
    writes = threading.Lock()
    running = threading.Lock()
    active: threading.Thread | None = None
    stream_failed = threading.Event()

    def reply(request_id: str, result: dict[str, Any] | None) -> None:
        with writes:
            _reply(connection, request_id, result)

    def run(raw: bytes, request_id: str) -> None:
        result: dict[str, Any] | None = None
        try:
            try:
                result = worker.handle(raw)
            except (OSError, ExecutionContractError, RuntimeError):
                result = None
        finally:
            # A receiver may observe bytes before sendall returns. Retire the
            # gate under the SAME lock used by next-RUN admission, not afterward.
            with writes:
                try:
                    _reply(connection, request_id, result)
                except OSError:
                    stream_failed.set()
                    worker.stopped = True
                finally:
                    running.release()

    try:
        while not worker.stopped:
            raw = read_frame(connection)
            record = decode_cell_request(raw)
            if record["action"] == "RUN":
                with writes:
                    accepted = running.acquire(blocking=False)
                if not accepted:
                    reply(record["request_id"], None)
                    continue
                if active is not None:
                    active.join()  # Prior RUN released the gate in its final action.
                # Pexpect forks only here, on the cell's main thread with no
                # active RUN thread. Never forkpty for a new session in run().
                worker._acquire(record["payload"])
                active = threading.Thread(target=run, args=(raw, record["request_id"]), daemon=True)
                active.start()
            elif record["action"] == "PROJECT_TOOL":
                _serve_project_tool(
                    worker,
                    connection,
                    raw,
                    record["request_id"],
                    writes=writes,
                    running=running,
                    stream_failed=stream_failed,
                )
            else:
                result = worker.handle(raw)
                if worker.stopped and active is not None:
                    active.join(worker._max_command_ms / 1000)
                    if active.is_alive():
                        raise ExecutionContractError
                reply(record["request_id"], result)
    finally:
        worker.close()
        if active is not None:
            active.join(worker._max_command_ms / 1000)
        if stream_failed.is_set():
            raise ExecutionContractError


def _cell_pool(workspace: Path) -> PtyPool:
    """Retain up to the cell protocol tail; the worker enforces the byte bound."""
    return PtyPool(base_cwd=workspace, output_limit=MAX_TAIL_BYTES)


def main() -> int:
    parser = argparse.ArgumentParser(description="Private cell-local PTY worker")
    parser.add_argument("--max-command-ms", type=int, required=True)
    parser.add_argument("--one-shot", action="store_true")
    args = parser.parse_args()
    try:
        _positive_integer(args.max_command_ms)
        for directory in (Path("/scratch/home"), Path("/scratch/tmp")):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        pool = _cell_pool(Path("/workspace"))
        worker = CellWorker(
            pool, workspace=Path("/workspace"), max_command_ms=args.max_command_ms, one_shot=args.one_shot
        )
        connection = _StdioConnection(sys.stdin.buffer, sys.stdout.buffer)
        if args.one_shot:
            return serve_once(worker, connection)
        serve(worker, connection)
    except (OSError, ExecutionContractError):
        sys.stderr.write("fa: cell_worker_unavailable\n")
        return 78
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
