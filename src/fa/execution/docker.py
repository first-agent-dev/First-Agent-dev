"""Private Docker launch/observation, not workspace authority or receipt issuer.

No TCP/DOCKER_HOST, image pull, generic public API, retry or production main.
Actual resource validation is REQUIRED. New-cell creation is not another RUN in
an existing interactive episode: the attach/backend owner must reuse that cell
and its original creation binding for later commands. Host proof is separate.
"""

from __future__ import annotations

import http.client
import math
import re
import select
import socket
import struct
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, override

from fa.execution.client import ExecutionUnavailableError, _connect_authenticated
from fa.execution.journal import JournalError, OperationJournal
from fa.execution.profiles import ExecutionProfile
from fa.execution.protocol import MAX_FRAME_BYTES, MAX_TAIL_BYTES, _loads, decode_request, encode_json, read_frame
from fa.execution.supervisor import operation_input_sha256
from fa.execution.types import Access, ExecutionContractError, NamespaceRef, Operation, ViewPurpose, ViewRef, _hex_id


class DockerUnavailableError(RuntimeError):
    def __init__(self, status: int | None = None) -> None:
        super().__init__("execution_engine_unavailable")
        self.status = status


def _remaining(deadline: float) -> float:
    if type(deadline) not in {int, float} or not math.isfinite(deadline):
        raise ExecutionContractError
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError
    return remaining


class _DeadlineSocket(socket.socket):
    """SocketIO.makefile uses recv_into: enforce the SAME absolute deadline."""

    def __init__(self, deadline: float) -> None:
        remaining = _remaining(deadline)
        super().__init__(socket.AF_UNIX, socket.SOCK_STREAM)
        self._deadline, self._received = deadline, 0
        self.settimeout(remaining)

    @override
    def connect(self, address: Any) -> None:
        self.settimeout(_remaining(self._deadline))
        super().connect(address)

    @override
    def sendall(self, data: Any, flags: int = 0) -> None:
        self.settimeout(_remaining(self._deadline))
        super().sendall(data, flags)

    @override
    def recv_into(self, buffer: Any, nbytes: int = 0, flags: int = 0) -> int:
        # Any is the stdlib's writable-buffer boundary; SocketIO supplies its
        # bytearray. Budget includes HTTP framing/headers, not just JSON length.
        self.settimeout(_remaining(self._deadline))
        count = super().recv_into(buffer, nbytes, flags)
        self._received += count
        if self._received > MAX_FRAME_BYTES + 64 * 1024:
            raise ExecutionContractError
        return count


@dataclass(frozen=True)
class ContainerObservation:
    container_id: str
    image_id: str
    status: str
    running: bool
    exit_code: int | None
    pid: int
    oom_killed: bool
    # Deliberately no terminal_barrier: Docker stopped != cgroup populated=0.


class DockerAttachStream:
    """One non-TTY hijacked stream. Single reader/writer; never reconnects.

    No socket inactivity deadline or cumulative lifetime frame cap: each exchange
    has its own absolute budget. Separate nonblocking read/write operations avoid
    concurrent controls resetting the RUN reader's timeout. Close != cell stop.
    """

    def __init__(self, connection: socket.socket) -> None:
        self._connection = connection
        connection.setblocking(False)
        self._left = 0
        self._wire_bytes = 0
        self._stderr = bytearray()

    def _receive(self, size: int, deadline: float) -> bytes:
        _remaining(deadline)
        while True:
            try:
                result = self._connection.recv(size)
                if not result:
                    raise ExecutionContractError
                _remaining(deadline)
                return result
            except BlockingIOError:
                select.select([self._connection], [], [], _remaining(deadline))

    def _exact(self, size: int, deadline: float) -> bytes:
        result = bytearray()
        while len(result) < size:
            part = self._receive(min(size - len(result), 64 * 1024), deadline)
            self._wire_bytes += len(part)
            if self._wire_bytes > MAX_FRAME_BYTES + 64 * 1024:
                raise ExecutionContractError
            result.extend(part)
        return bytes(result)

    def _send(self, data: bytes, deadline: float) -> None:
        pending = memoryview(data)
        while pending:
            _remaining(deadline)
            try:
                count = self._connection.send(pending)
                if count <= 0:
                    raise ExecutionContractError
                pending = pending[count:]
            except BlockingIOError:
                select.select([], [self._connection], [], _remaining(deadline))
        _remaining(deadline)

    def upgrade(self, request: bytes, *, deadline: float) -> None:
        self._send(request, deadline)
        # No BufferedReader: bytes following CRLFCRLF must remain on the socket.
        head = bytearray()
        while not head.endswith(b"\r\n\r\n"):
            if len(head) >= 64 * 1024:
                raise ExecutionContractError
            head.extend(self._receive(1, deadline))
        lines = head.decode("ascii").split("\r\n")
        if re.fullmatch(r"HTTP/1\.[01] 101 [^\r\n]*", lines[0]) is None:
            raise ExecutionContractError
        headers: dict[str, str] = {}
        for line in lines[1:-2]:
            name, separator, value = line.partition(":")
            if not separator or re.fullmatch(r"[a-zA-Z0-9-]+", name) is None or name.lower() in headers:
                raise ExecutionContractError
            headers[name.lower()] = value.strip().lower()
        if (
            headers.get("connection") != "upgrade"
            or headers.get("upgrade") != "tcp"
            or headers.get("content-type") != "application/vnd.docker.raw-stream"
            or "transfer-encoding" in headers
            or headers.get("content-length", "0") != "0"
        ):
            raise ExecutionContractError

    def _stdout(self, size: int, deadline: float) -> bytes:
        while not self._left:
            head = self._exact(8, deadline)
            kind, length = head[0], struct.unpack("!I", head[4:])[0]
            if head[1:4] != b"\0\0\0" or kind not in {0, 1, 2} or length > MAX_FRAME_BYTES + 4:
                raise ExecutionContractError
            if kind == 2:
                while length:
                    part = self._exact(min(length, 64 * 1024), deadline)
                    self._stderr.extend(part)
                    del self._stderr[:-MAX_TAIL_BYTES]
                    length -= len(part)
            else:
                self._left = length
        part = self._exact(min(size, self._left), deadline)
        self._left -= len(part)
        return part

    def read_frame(self, *, deadline: float) -> bytes:
        stream = self

        class Reader:
            def recv(self, size: int, /) -> bytes:
                return stream._stdout(size, deadline)

            def sendall(self, data: bytes, /) -> None:
                stream._send(data, deadline)

        try:
            self._wire_bytes = 0
            return read_frame(Reader())
        except (OSError, ValueError, ExecutionContractError):
            raise DockerUnavailableError from None

    def write_frame(self, raw: bytes, *, deadline: float) -> None:
        try:
            if not 0 < len(raw) <= MAX_FRAME_BYTES:
                raise ExecutionContractError
            self._send(struct.pack("!I", len(raw)) + raw, deadline)
        except (OSError, ValueError, ExecutionContractError):
            raise DockerUnavailableError from None

    @property
    def stderr_tail(self) -> bytes:
        return bytes(self._stderr)

    def close(self) -> None:
        # shutdown wakes a concurrent select/recv; an already-closed peer is normal.
        with suppress(OSError):
            self._connection.shutdown(socket.SHUT_RDWR)
        self._connection.close()


class DockerEngine:
    """Explicit private daemon config; no environment endpoint/version discovery."""

    def __init__(self, socket_path: Path, *, daemon_uid: int, api_version: str, rpc_timeout_ms: int) -> None:
        if (
            not socket_path.is_absolute()
            or ".." in socket_path.parts
            or type(daemon_uid) is not int
            or daemon_uid < 0
            or type(rpc_timeout_ms) is not int
            or rpc_timeout_ms <= 0
            or not isinstance(api_version, str)
            or re.fullmatch(r"1\.(?:4[1-9]|[5-9][0-9])", api_version) is None
        ):
            raise ExecutionContractError
        self._path, self._uid = socket_path, daemon_uid
        self._version, self._timeout_ms = api_version, rpc_timeout_ms

    def _request(self, method: str, path: str, *, body: dict[str, Any] | None, status: int, deadline: float) -> bytes:
        raw = b"" if body is None else encode_json(body)
        _remaining(deadline)
        bounded = min(deadline, time.monotonic() + self._timeout_ms / 1000)
        head = (
            f"{method} /v{self._version}{path} HTTP/1.1\r\nHost: docker\r\n"
            f"Connection: close\r\nContent-Type: application/json\r\nContent-Length: {len(raw)}\r\n\r\n"
        ).encode("ascii")
        try:
            with _DeadlineSocket(bounded) as connection:
                _connect_authenticated(connection, self._path, self._uid)
                connection.sendall(head + raw)
                with http.client.HTTPResponse(connection) as response:
                    response.begin()
                    if response.status != status:
                        raise DockerUnavailableError(response.status)  # NEVER expose daemon error bodies.
                    lengths = response.headers.get_all("Content-Length", [])
                    encodings = response.headers.get_all("Transfer-Encoding", [])
                    if (
                        len(lengths) > 1
                        or len(encodings) > 1
                        or (lengths and encodings)
                        or (encodings and encodings[0].lower().strip() != "chunked")
                    ):
                        raise ExecutionContractError
                    if lengths and (
                        re.fullmatch(r"[0-9]{1,10}", lengths[0]) is None or int(lengths[0]) > MAX_FRAME_BYTES
                    ):
                        raise ExecutionContractError
                    if status == 204 and (encodings or (lengths and int(lengths[0]) != 0)):
                        raise ExecutionContractError
                    content = response.read(MAX_FRAME_BYTES + 1)
                    if (
                        len(content) > MAX_FRAME_BYTES
                        or (status == 204 and content)
                        or response.length not in (None, 0)
                    ):
                        raise ExecutionContractError
                    _remaining(bounded)
                    return content
        except (OSError, http.client.HTTPException, ExecutionContractError, ExecutionUnavailableError):
            raise DockerUnavailableError from None

    def create(
        self,
        *,
        profile: ExecutionProfile,
        operation_id: str,
        view: ViewRef,
        source: Path,
        scratch: Path,
        cache: Path,
        deadline: float,
    ) -> str:
        spec = profile.create_spec(operation_id=operation_id, view=view, source=source, scratch=scratch, cache=cache)
        raw = self._request(
            "POST", "/containers/create?name=" + spec["name"], body=spec["body"], status=201, deadline=deadline
        )
        try:
            value = _loads(raw)
            _hex_id(value.get("Id"), "", 64)
            if set(value) != {"Id", "Warnings"} or value["Warnings"] not in (None, []):
                raise ExecutionContractError
            return str(value["Id"])
        except ExecutionContractError:
            raise DockerUnavailableError from None

    def start(self, container_id: str, *, deadline: float) -> None:
        _hex_id(container_id, "", 64)
        self._request("POST", f"/containers/{container_id}/start", body=None, status=204, deadline=deadline)

    def attach(self, container_id: str, *, deadline: float) -> DockerAttachStream:
        """Fixed upgraded non-TTY stdio, no logs or automatic reattach/replay."""
        _hex_id(container_id, "", 64)
        _remaining(deadline)
        bounded = min(deadline, time.monotonic() + self._timeout_ms / 1000)
        remaining = _remaining(bounded)
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stream: DockerAttachStream | None = None
        try:
            connection.settimeout(remaining)
            _connect_authenticated(connection, self._path, self._uid)
            stream = DockerAttachStream(connection)
            query = "stream=1&stdin=1&stdout=1&stderr=1&logs=0&detachKeys="
            request = (
                f"POST /v{self._version}/containers/{container_id}/attach?{query} HTTP/1.1\r\n"
                "Host: docker\r\nConnection: Upgrade\r\nUpgrade: tcp\r\nContent-Length: 0\r\n\r\n"
            ).encode("ascii")
            stream.upgrade(request, deadline=bounded)
            return stream
        except (OSError, ValueError, ExecutionContractError, ExecutionUnavailableError):
            if stream is not None:
                stream.close()
            else:
                connection.close()
            raise DockerUnavailableError from None

    def inspect_owned(
        self,
        *,
        operation_id: str,
        view: ViewRef,
        profile: ExecutionProfile,
        container_id: str | None,
        deadline: float,
    ) -> ContainerObservation:
        """ID or deterministic original creation name; never trust status alone."""
        _hex_id(operation_id, "op-")
        if container_id is not None:
            _hex_id(container_id, "", 64)
        name = "fa-job-" + operation_id.removeprefix("op-")
        raw = self._request("GET", f"/containers/{container_id or name}/json", body=None, status=200, deadline=deadline)
        try:
            value = _loads(raw)
            actual_id = value.get("Id")
            _hex_id(actual_id, "", 64)
            if container_id is not None and actual_id != container_id:
                raise ExecutionContractError
            config, state = value["Config"], value["State"]
            if (
                value["Name"] != "/" + name
                or config["Image"] != profile.image
                or config["Labels"]["fa.execution.operation_id"] != operation_id
                or config["Labels"]["fa.execution.view_id"] != view.view_id
            ):
                raise ExecutionContractError
            _hex_id(value["Image"], "sha256:", 64)
            for key in ("Running", "Paused", "Restarting", "Dead", "OOMKilled"):
                if type(state[key]) is not bool:
                    raise ExecutionContractError
            if type(state["Pid"]) is not int or state["Pid"] < 0 or type(state["ExitCode"]) is not int:
                raise ExecutionContractError
            status = state["Status"]
            if status not in {"created", "running", "paused", "restarting", "exited", "dead", "removing"}:
                raise ExecutionContractError
            if (status == "running" and (not state["Running"] or state["Pid"] == 0)) or (
                status in {"created", "exited", "dead"} and state["Running"]
            ):
                raise ExecutionContractError
            exited = (
                status == "exited"
                and not any(state[k] for k in ("Running", "Paused", "Restarting", "Dead"))
                and state["Pid"] == 0
            )
            if status == "exited" and not exited:
                raise ExecutionContractError
            return ContainerObservation(
                str(actual_id),
                value["Image"],
                status,
                state["Running"],
                state["ExitCode"] if exited else None,
                state["Pid"],
                state["OOMKilled"],
            )
        except (ExecutionContractError, KeyError, TypeError):
            raise DockerUnavailableError from None


class DockerCells:
    """New-cell creation only, not per-command dispatch or an authority/issuer.

    Existing interactive commands MUST reuse their original live cell/creation
    binding in the future attach/backend layer. This class issues no receipt and
    makes no descendant-terminal, startup-reconciliation or grant claim.
    """

    def __init__(
        self,
        engine: DockerEngine,
        journal: OperationJournal,
        *,
        validate_binding: Callable[[NamespaceRef, ViewRef, Path, Path, Path], None],
    ) -> None:
        if not callable(validate_binding):
            raise ExecutionContractError
        self._engine, self._journal, self._validate_binding = engine, journal, validate_binding

    @staticmethod
    def _binding(
        request: dict[str, Any], profile: ExecutionProfile
    ) -> tuple[dict[str, Any], NamespaceRef, ViewRef, str]:
        req = decode_request(encode_json(request))
        if req["op"] != "exec" or req["payload"]["profile_id"] != profile.profile_id:
            raise ExecutionContractError
        if req["payload"]["timeout_ms"] > profile.max_command_ms or profile.interactive != (
            req["payload"]["session_id"] is not None
        ):
            raise ExecutionContractError
        namespace = NamespaceRef(**req["namespace"])
        view = ViewRef(
            workspace_id=req["view_ref"]["workspace_id"],
            view_id=req["view_ref"]["view_id"],
            base_revision=req["view_ref"]["base_revision"],
            owner_run_id=req["view_ref"]["owner_run_id"],
            generation=req["view_ref"]["generation"],
            access=Access(req["view_ref"]["access"]),
            purpose=ViewPurpose(req["view_ref"]["purpose"]),
        )
        digest = operation_input_sha256(Operation.EXEC, namespace, view, req["payload"])
        return req, namespace, view, digest

    def launch_new(
        self,
        request: dict[str, Any],
        *,
        profile: ExecutionProfile,
        source: Path,
        scratch: Path,
        cache: Path,
        deadline: float,
    ) -> str:
        _remaining(deadline)
        req, namespace, view, digest = self._binding(request, profile)
        self._validate_binding(namespace, view, source, scratch, cache)
        operation_id = req["payload"]["operation_id"]
        container_id = self._journal.create_once(
            operation_id,
            namespace,
            input_sha256=digest,
            create=lambda: self._engine.create(
                profile=profile,
                operation_id=operation_id,
                view=view,
                source=source,
                scratch=scratch,
                cache=cache,
                deadline=deadline,
            ),
        )
        with self._journal.start_once(operation_id, namespace) as owned_id:
            self._engine.start(owned_id, deadline=deadline)
        return container_id  # Start ACK, NOT command success or terminality.

    def inspect_created(
        self,
        creation_request: dict[str, Any],
        *,
        profile: ExecutionProfile,
        deadline: float,
    ) -> ContainerObservation:
        req, namespace, view, digest = self._binding(creation_request, profile)
        record = self._journal.lookup(req["payload"]["operation_id"], namespace)
        if record is None or record["input_sha256"] != digest:
            raise JournalError("EXECUTION_UNKNOWN")
        return self._engine.inspect_owned(
            operation_id=record["operation_id"],
            view=view,
            profile=profile,
            container_id=record["container_id"],
            deadline=deadline,
        )

    def attach_created(
        self,
        creation_request: dict[str, Any],
        *,
        profile: ExecutionProfile,
        deadline: float,
    ) -> DockerAttachStream:
        """Original journal binding + owned running cell, not a fresh exec grant.

        The future protected episode owner must ensure this is the sole attach.
        Inspect/attach alone never recover lost command state after restart.
        """
        observed = self.inspect_created(creation_request, profile=profile, deadline=deadline)
        if observed.status != "running" or not observed.running:
            raise DockerUnavailableError
        return self._engine.attach(observed.container_id, deadline=deadline)
