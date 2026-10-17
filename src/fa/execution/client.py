"""Single-attempt private-UDS client and managed BashExecutor, never host shell.

Not installed into the live controller until real authority/journal integration.
Local UUID allocation is not durable reservation; only the supervisor can attest
that. No transport failure here triggers a resend or replacement operation ID.
"""

from __future__ import annotations

import socket
import stat
import struct
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from fa.execution.profiles import ExecutionProfile
from fa.execution.protocol import DeadlineConnection, decode_reply, decode_request, encode_json, read_frame, write_frame
from fa.execution.types import (
    ExecutionContractError,
    ExecutionReceipt,
    JobState,
    NamespaceRef,
    Operation,
    OperationRef,
    ViewRef,
    _positive_integer,
    validate_capability,
)
from fa.runtime.pty_pool import PtyResult


class ExecutionUnavailableError(RuntimeError):
    def __init__(self, *, operation_id: str | None = None) -> None:
        super().__init__("execution_unavailable")
        self.code = "BACKEND_UNAVAILABLE"
        self.operation_id = operation_id


class ExecutionUncertainError(RuntimeError):
    def __init__(self, operation_id: str | None, *, code: str = "EXECUTION_UNKNOWN") -> None:
        super().__init__("execution_unknown")
        self.operation_id = operation_id
        self.code = code


class ExecutionTimedOutError(ExecutionUncertainError):
    def __init__(self, receipt: ExecutionReceipt) -> None:
        super().__init__(receipt.operation_id)
        self.receipt = receipt


class ExecutionRejectedError(RuntimeError):
    def __init__(self, code: str, operation_id: str | None) -> None:
        super().__init__("execution_rejected")
        self.code = code
        self.operation_id = operation_id


def _connect_authenticated(connection: socket.socket, path: Path, server_uid: int) -> None:
    # Peer credentials after connect are authoritative even across a path
    # replacement race. A same-UID malicious server is inside the host TCB.
    parent = path.parent.stat(follow_symlinks=False)
    endpoint = path.stat(follow_symlinks=False)
    if (
        not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != server_uid
        or parent.st_mode & 0o022
        or not stat.S_ISSOCK(endpoint.st_mode)
        or endpoint.st_uid != server_uid
    ):
        raise ExecutionUnavailableError
    connection.connect(str(path))
    _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
    if uid != server_uid:
        raise ExecutionUnavailableError


class ExecutionClient:
    def __init__(self, socket_path: Path, *, server_uid: int, rpc_timeout_ms: int) -> None:
        if type(server_uid) is not int or server_uid < 0:
            raise ExecutionContractError
        _positive_integer(rpc_timeout_ms)
        if not socket_path.is_absolute() or ".." in socket_path.parts:
            raise ExecutionContractError
        self._path = socket_path
        self._server_uid = server_uid
        self._timeout_ms = rpc_timeout_ms

    def _connect(self, connection: socket.socket) -> None:
        _connect_authenticated(connection, self._path, self._server_uid)

    def request(
        self,
        operation: Operation,
        *,
        request_id: str,
        namespace: NamespaceRef | None,
        view: ViewRef | None,
        capability: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        raw = encode_json(
            {
                "protocol_version": 1,
                "request_id": request_id,
                "op": operation.value,
                "namespace": None if namespace is None else namespace.to_dict(),
                "view_ref": None if view is None else view.to_dict(),
                "capability": capability,
                "payload": payload,
            }
        )
        decode_request(raw)  # Reject caller bugs BEFORE connecting/sending.
        attempted_send = False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                framed = DeadlineConnection(connection, timeout_ms=self._timeout_ms)
                connection.settimeout(framed.remaining())
                self._connect(connection)
                attempted_send = True  # sendall can lose a partial/completed write.
                write_frame(framed, raw)
                if operation is Operation.EXEC:
                    framed.add_execution_budget(payload["timeout_ms"])
                response = decode_reply(read_frame(framed), operation=operation, request_id=request_id)
        except (OSError, ExecutionContractError):
            if attempted_send:
                raise ExecutionUncertainError("op-" + request_id) from None
            raise ExecutionUnavailableError from None
        if response["status"] == "ERROR":
            error = response["error"]
            if error["code"] in {"EXECUTION_UNKNOWN", "TERMINALITY_UNKNOWN", "DURABILITY_UNKNOWN", "CORRUPT_STATE"}:
                raise ExecutionUncertainError(error["operation_id"] or "op-" + request_id, code=error["code"])
            if error["code"] == "BACKEND_UNAVAILABLE":
                raise ExecutionUnavailableError(operation_id=error["operation_id"])
            raise ExecutionRejectedError(error["code"], error["operation_id"])
        return cast(dict[str, Any], response["result"])


class ManagedBashExecutor:
    """All four BashExecutor methods, with a fixed trusted episode binding.

    The profile must be interactive to preserve stateful PTY semantics. A caller
    must supply current protected source/PlanRef metadata, never infer it from a
    worker response. This constructor does not authorize or create the view.
    """

    def __init__(
        self,
        client: ExecutionClient,
        *,
        namespace: NamespaceRef,
        view: ViewRef,
        capability: str,
        profile: ExecutionProfile,
        input_tree_sha256: str,
        plan_sha256: str | None,
        original_revision_id: str | None,
        controller_root: Path,
    ) -> None:
        validate_capability(capability)
        if not profile.interactive or not controller_root.is_absolute() or ".." in controller_root.parts:
            raise ExecutionContractError
        self._client = client
        self._namespace = namespace
        self._view = view
        self._capability = capability
        self._profile = profile
        self._tree = input_tree_sha256
        self._plan = plan_sha256
        self._original_revision = original_revision_id
        self._root = controller_root

    def _request(self, operation: Operation, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        return self._client.request(
            operation,
            request_id=request_id,
            namespace=self._namespace,
            view=self._view,
            capability=self._capability,
            payload=payload,
        )

    def _cwd(self, workdir: Path | None) -> str:
        if workdir is None:
            return "."
        try:
            return (workdir.relative_to(self._root) if workdir.is_absolute() else workdir).as_posix()
        except ValueError:
            raise ExecutionContractError from None

    def run(self, command: str, timeout: int = 30, workdir: Path | None = None, session_id: str = "main") -> PtyResult:
        _positive_integer(timeout)
        request_id = uuid4().hex
        return self._execute_once(command, timeout, workdir, session_id, request_id)

    # §execution-client-once: transport uncertainty never resends a shell command.
    def _execute_once(
        self, command: str, timeout: int, workdir: Path | None, session_id: str, request_id: str
    ) -> PtyResult:
        operation = OperationRef(
            "op-" + request_id, self._view.view_id, self._view.owner_run_id, self._view.generation, self._tree
        )
        result = self._request(
            Operation.EXEC,
            {
                "operation_id": operation.operation_id,
                "profile_id": self._profile.profile_id,
                "command": command,
                "cwd": self._cwd(workdir),
                "timeout_ms": min(timeout * 1000, self._profile.max_command_ms),
                "session_id": session_id,
            },
            request_id,
        )
        receipt = ExecutionReceipt.from_dict(result["receipt"])
        try:
            receipt.require_binding(
                operation=operation,
                namespace=self._namespace,
                view=self._view,
                profile_id=self._profile.profile_id,
                image_digest=self._profile.image_digest,
                revision_id=self._view.base_revision,
                original_revision_id=self._original_revision,
                plan_sha256=self._plan,
            )
        except ExecutionContractError:
            raise ExecutionUncertainError(operation.operation_id) from None
        if receipt.state is JobState.TIMED_OUT:
            raise ExecutionTimedOutError(receipt)
        if receipt.state is JobState.LAUNCH_FAILED:
            raise ExecutionUnavailableError
        if receipt.state is not JobState.EXITED or receipt.exit_code is None:
            raise ExecutionUncertainError(operation.operation_id)
        return PtyResult(
            receipt.stdout_tail + receipt.stderr_tail, receipt.exit_code, receipt.truncated, session_id, False
        )

    def _control(self, action: str, session_id: str | None) -> dict[str, Any]:
        return self._request(Operation.PTY_CONTROL, {"action": action, "session_id": session_id}, uuid4().hex)

    def send_ctrl_c(self, session_id: str) -> str:
        return str(self._control("INTERRUPT", session_id)["message"])

    def close(self, session_id: str) -> None:
        self._control("CLOSE", session_id)

    def list_sessions(self) -> list[str]:
        result = self._control("LIST", None)
        return list(result["sessions"])
