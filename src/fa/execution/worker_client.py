"""Private concurrent worker exchanges; NOT admission, journal or receipt issuer.

One RUN and one control exchange in flight. Durable command reservation and
exclusive episode ownership belong to the backend, not this transport. A lost,
late, forged or unavailable reply poisons the channel; never reconnect/resend.

The write and the reply wait are separate steps so a caller can hold a bounded
journal guard across the FRAME WRITE only, never across a running command.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from fa.execution.cell_protocol import decode_cell_reply, decode_cell_request
from fa.execution.docker import DockerAttachStream, DockerUnavailableError, _remaining
from fa.execution.protocol import _loads
from fa.execution.types import ExecutionContractError


class WorkerUnavailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("execution_worker_unavailable")


@dataclass
class _Pending:
    request: dict[str, Any]
    deadline: float
    event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None


@dataclass
class _Exchange:
    """One in-flight exchange. The caller MUST await_reply or abandon it."""

    request_id: str
    pending: _Pending
    gate: threading.Lock
    retired: bool = False


class WorkerClient:
    def __init__(self, stream: DockerAttachStream) -> None:
        self._stream = stream
        self._condition = threading.Condition()
        self._pending: dict[str, _Pending] = {}
        self._closed = False
        self._run_gate, self._control_gate, self._writes = threading.Lock(), threading.Lock(), threading.Lock()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _fail(self) -> None:
        with self._condition:
            self._closed = True
            for pending in self._pending.values():
                pending.event.set()
            self._condition.notify_all()
        self._stream.close()

    def _read(self) -> None:
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._closed or bool(self._pending))
                    if self._closed:
                        return
                    deadline = min(p.deadline for p in self._pending.values())
                raw = self._stream.read_frame(deadline=deadline)
                request_id = _loads(raw).get("request_id")
                if not isinstance(request_id, str):
                    raise ExecutionContractError
                with self._condition:
                    pending = self._pending.get(request_id)
                    if pending is None or pending.event.is_set():
                        raise ExecutionContractError
                    _remaining(pending.deadline)
                    req = pending.request
                    result = decode_cell_reply(
                        raw, request_id=request_id, action=req["action"], session_id=req["payload"].get("session_id")
                    )
                    if result is None:
                        raise ExecutionContractError
                    pending.result = result
                    pending.event.set()

                    # Do not read again until the caller retires this exchange.
                    def retired(original_id: str = request_id) -> bool:
                        return self._closed or original_id not in self._pending

                    self._condition.wait_for(retired)
        except (OSError, DockerUnavailableError, ExecutionContractError):
            self._fail()

    def begin(self, raw: bytes, *, deadline: float) -> _Exchange:
        """Write ONE bounded frame and return its exchange. Never resends.

        The caller must await_reply() or abandon() the returned exchange; the
        transport stays poisoned after any write or reply failure.
        """
        req = decode_cell_request(raw)  # Closed private request before IO/registration.
        gate = self._run_gate if req["action"] == "RUN" else self._control_gate
        if not gate.acquire(timeout=_remaining(deadline)):
            raise WorkerUnavailableError
        request_id = req["request_id"]
        pending = _Pending(req, deadline)
        registered = False
        try:
            with self._condition:
                if self._closed or request_id in self._pending:
                    raise WorkerUnavailableError
                self._pending[request_id] = pending
                registered = True
                self._condition.notify_all()
            if not self._writes.acquire(timeout=_remaining(deadline)):
                raise WorkerUnavailableError
            try:
                self._stream.write_frame(raw, deadline=deadline)
            finally:
                self._writes.release()
        except (OSError, DockerUnavailableError, ExecutionContractError, WorkerUnavailableError):
            if registered:
                self._fail()
            gate.release()
            raise WorkerUnavailableError from None
        return _Exchange(request_id, pending, gate)

    def await_reply(self, exchange: _Exchange, *, deadline: float) -> dict[str, Any]:
        """Wait for the reply of an already sent exchange. No second frame."""
        try:
            limit = min(deadline, exchange.pending.deadline)
            if not exchange.pending.event.wait(_remaining(limit)):
                raise WorkerUnavailableError
            _remaining(limit)
            if exchange.pending.result is None:
                raise WorkerUnavailableError
            return exchange.pending.result
        except (OSError, DockerUnavailableError, ExecutionContractError, WorkerUnavailableError):
            self._fail()
            raise WorkerUnavailableError from None
        finally:
            self._retire(exchange)

    def abandon(self, exchange: _Exchange) -> None:
        """Retire an exchange whose reply will never be used. Poisons nothing else."""
        self._retire(exchange)

    def _retire(self, exchange: _Exchange) -> None:
        with self._condition:
            if exchange.retired:
                return
            exchange.retired = True
            self._pending.pop(exchange.request_id, None)
            self._condition.notify_all()
        exchange.gate.release()

    def request(self, raw: bytes, *, deadline: float) -> dict[str, Any]:
        """One bounded exchange: write, then wait for its own reply."""
        exchange = self.begin(raw, deadline=deadline)
        return self.await_reply(exchange, deadline=deadline)

    def close(self, *, deadline: float) -> None:
        self._fail()  # No STOP acknowledgement or process/cgroup assertion.
        self._reader.join(_remaining(deadline))
        if self._reader.is_alive():
            raise WorkerUnavailableError
