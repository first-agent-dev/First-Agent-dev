"""Cell-local PTY adapter. Never a supervisor, receipt issuer or host runner.

Its JSON output is untrusted worker data. Only the supervisor's protected state
and actual Docker/cgroup observations can establish receipt identity/terminality.
Stdio is a private Docker attach stream, not a project-selected control socket.
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path
from typing import Any, BinaryIO

from fa.execution.cell_protocol import decode_cell_request
from fa.execution.protocol import (
    MAX_TAIL_BYTES,
    FrameConnection,
    encode_json,
    read_frame,
    write_frame,
)
from fa.execution.types import ExecutionContractError, _positive_integer
from fa.runtime.pty_pool import PtyPool, PtySession


class CellWorker:
    def __init__(self, pool: PtyPool, *, workspace: Path, max_command_ms: int) -> None:
        _positive_integer(max_command_ms)
        self._pool = pool
        self._workspace = workspace.resolve(strict=True)
        self._max_command_ms = max_command_ms
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
        session = self._acquire(payload)
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
            "session_id": outcome.session_id,
            "timed_out": outcome.timed_out,
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
    """Exactly one RUN; no synthetic normal exit for indeterminate execution.

    Worker data is still untrusted. The supervisor must check actual container
    exit and the independent descendant barrier before issuing a receipt.
    """
    try:
        raw = read_frame(connection)
        record = decode_cell_request(raw)
        result: dict[str, Any] | None = None
        if record["action"] == "RUN":
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
        try:
            try:
                result = worker.handle(raw)
            except (OSError, ExecutionContractError, RuntimeError):
                result = None
            try:
                reply(request_id, result)
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
                if not running.acquire(blocking=False):
                    reply(record["request_id"], None)
                    continue
                if active is not None:
                    active.join()  # Prior RUN released the gate in its final action.
                # Pexpect forks only here, on the cell's main thread with no
                # active RUN thread. Never forkpty for a new session in run().
                worker._acquire(record["payload"])
                active = threading.Thread(target=run, args=(raw, record["request_id"]), daemon=True)
                active.start()
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Private cell-local PTY worker")
    parser.add_argument("--max-command-ms", type=int, required=True)
    parser.add_argument("--one-shot", action="store_true")
    args = parser.parse_args()
    try:
        _positive_integer(args.max_command_ms)
        for directory in (Path("/scratch/home"), Path("/scratch/tmp")):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        pool = PtyPool(base_cwd=Path("/workspace"))
        worker = CellWorker(pool, workspace=Path("/workspace"), max_command_ms=args.max_command_ms)
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
