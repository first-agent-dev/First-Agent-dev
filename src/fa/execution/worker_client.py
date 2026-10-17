"""Private concurrent worker exchanges; NOT admission, journal or receipt issuer.

One RUN and one control exchange in flight. Durable command reservation and
exclusive episode ownership belong to the backend, not this transport. A lost,
late, forged or unavailable reply poisons the channel; never reconnect/resend.
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

    def request(self, raw: bytes, *, deadline: float) -> dict[str, Any]:
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
            if not pending.event.wait(_remaining(deadline)):
                raise WorkerUnavailableError
            _remaining(deadline)
            if pending.result is None:
                raise WorkerUnavailableError
            return pending.result
        except (OSError, DockerUnavailableError, ExecutionContractError, WorkerUnavailableError):
            if registered:
                self._fail()
            raise WorkerUnavailableError from None
        finally:
            if registered:
                with self._condition:
                    self._pending.pop(request_id, None)
                    self._condition.notify_all()
            gate.release()

    def close(self, *, deadline: float) -> None:
        self._fail()  # No STOP acknowledgement or process/cgroup assertion.
        self._reader.join(_remaining(deadline))
        if self._reader.is_alive():
            raise WorkerUnavailableError
