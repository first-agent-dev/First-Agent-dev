"""C0/C3 literal Unix HTTP peer + real journal, NOT a Docker engine/host proof."""

from __future__ import annotations

import json
import os
import socket
import socketserver
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, override

import pytest

from fa.execution.docker import DockerCells, DockerEngine, DockerUnavailableError
from fa.execution.journal import JournalError, OperationJournal
from fa.execution.types import ExecutionContractError, NamespaceRef, ViewRef
from tests.test_execution_client import profile
from tests.test_execution_journal import CID, NS, OID, VIEW, request


@dataclass
class Reply:
    status: int = 201
    value: dict[str, Any] = field(default_factory=lambda: {"Id": CID, "Warnings": []})
    raw: bytes | None = None
    chunks: list[bytes] | None = None
    upgraded: Callable[[socket.socket], None] | None = None


class Endpoint:
    """No Docker simulation/state machine: queue literal HTTP replies only."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.replies: deque[Reply] = deque()
        self.seen: list[dict[str, Any]] = []
        self.journal_file: Path | None = None
        self.errors: list[str] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            @override
            def log_message(self, format: str, *args: Any) -> None:
                pass  # Test fixture never logs opaque daemon/client bodies.

            def respond(self) -> None:
                try:
                    raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                    seen = {"method": self.command, "path": self.path, "body": None if not raw else json.loads(raw)}
                    if owner.journal_file is not None:
                        seen["journal"] = json.loads(owner.journal_file.read_text())
                    owner.seen.append(seen)
                    reply = owner.replies.popleft() if owner.replies else Reply(500)
                    if reply.chunks is not None:
                        for chunk in reply.chunks:
                            self.connection.sendall(chunk)
                            time.sleep(0.03)  # Deliberate slow-peer deadline fault, not polling.
                    elif reply.raw is not None:
                        self.connection.sendall(reply.raw)
                    else:
                        body = b"" if reply.status == 204 else json.dumps(reply.value).encode()
                        self.connection.sendall(
                            f"HTTP/1.1 {reply.status} Unit\r\nContent-Length: {len(body)}\r\n\r\n".encode() + body
                        )
                    if reply.upgraded is not None:
                        reply.upgraded(self.connection)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # Expected when an adversarial response is rejected early.
                except (ValueError, OSError) as exc:
                    owner.errors.append(type(exc).__name__)

            do_GET = respond  # noqa: N815 — BaseHTTPRequestHandler protocol name
            do_POST = respond  # noqa: N815 — BaseHTTPRequestHandler protocol name

        class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
            daemon_threads = False
            block_on_close = True

        self.server = Server(str(path), Handler)
        path.chmod(0o660)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()

    def engine(self, timeout: int = 1000) -> DockerEngine:
        return DockerEngine(self.path, daemon_uid=os.getuid(), api_version="1.45", rpc_timeout_ms=timeout)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        assert not self.thread.is_alive() and self.errors == []


@pytest.fixture
def endpoint(tmp_path: Path) -> Iterator[Endpoint]:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    case = Endpoint(private / "engine.sock")
    try:
        yield case
    finally:
        case.close()


def deadline() -> float:
    return time.monotonic() + 2


def create(engine: DockerEngine, *, until: float | None = None) -> str:
    return engine.create(
        profile=profile(),
        operation_id=OID,
        view=VIEW,
        source=Path("/protected/source"),
        scratch=Path("/protected/scratch"),
        cache=Path("/approved/cache"),
        deadline=deadline() if until is None else until,
    )


def observation(status: str = "running") -> dict[str, Any]:
    running = status in {"running", "paused"}
    return {
        "Id": CID,
        "Name": "/fa-job-" + OID.removeprefix("op-"),
        "Image": "sha256:" + "8" * 64,
        "Config": {
            "Image": profile().image,
            "Labels": {"fa.execution.operation_id": OID, "fa.execution.view_id": VIEW.view_id},
        },
        "State": {
            "Status": status,
            "Running": running,
            "Paused": status == "paused",
            "Restarting": status == "restarting",
            "Dead": status == "dead",
            "OOMKilled": False,
            "Pid": 123 if running else 0,
            "ExitCode": 7 if status == "exited" else 0,
        },
    }


class Case:
    def __init__(self, endpoint: Endpoint, tmp_path: Path) -> None:
        self.endpoint = endpoint
        self.journal = OperationJournal(tmp_path / "operations", lock_timeout_ms=1000)
        self.req = request()
        self.journal.reserve(self.req)
        self.journal.begin(OID, NS)
        endpoint.journal_file = tmp_path / "operations" / (OID + ".json")
        self.validated: list[tuple[Any, ...]] = []
        self.denied = False
        self.cells = DockerCells(endpoint.engine(), self.journal, validate_binding=self.validate)

    def validate(self, ns: NamespaceRef, view: ViewRef, source: Path, scratch: Path, cache: Path) -> None:
        self.validated.append((ns, view, source, scratch, cache))
        if self.denied:
            raise ExecutionContractError

    def launch(self, *, until: float | None = None) -> str:
        return self.cells.launch_new(
            self.req,
            profile=profile(),
            source=Path("/protected/source"),
            scratch=Path("/protected/scratch"),
            cache=Path("/approved/cache"),
            deadline=deadline() if until is None else until,
        )

    def inspect(self) -> Any:
        return self.cells.inspect_created(self.req, profile=profile(), deadline=deadline())


def test_real_http_launch_orders_unknown_create_cid_unknown_start(endpoint: Endpoint, tmp_path: Path) -> None:
    case = Case(endpoint, tmp_path)
    endpoint.replies.extend([Reply(), Reply(204)])
    assert case.launch() == CID
    assert len(case.validated) == 1 and case.validated[0][:2] == (NS, VIEW)
    assert len(endpoint.seen) == 2
    first, second = endpoint.seen
    assert first["path"] == "/v1.45/containers/create?name=fa-job-" + OID.removeprefix("op-")
    assert first["method"] == second["method"] == "POST"
    assert second["path"] == f"/v1.45/containers/{CID}/start"
    assert first["journal"]["state"] == "UNKNOWN" and first["journal"]["container_id"] is None
    assert second["journal"]["state"] == "UNKNOWN" and second["journal"]["container_id"] == CID
    body = first["body"]
    assert body["Labels"] == {"fa.execution.operation_id": OID, "fa.execution.view_id": VIEW.view_id}
    assert body["Image"] == profile().image and body["HostConfig"]["NetworkMode"] == "none"
    assert case.req["capability"] not in json.dumps(body) and case.req["payload"]["command"] not in json.dumps(body)
    record = case.journal.lookup(OID, NS)
    assert record is not None and record["state"] == "UNKNOWN"
    with pytest.raises(JournalError):
        case.launch()
    assert len(endpoint.seen) == 2  # Acknowledged start cannot create/start again.


@pytest.mark.parametrize("phase", ["create", "start"])
def test_lost_daemon_reply_never_replays_and_preserves_lookup_identity(
    endpoint: Endpoint, tmp_path: Path, phase: str
) -> None:
    case = Case(endpoint, tmp_path)
    endpoint.replies.extend([Reply(raw=b"")] if phase == "create" else [Reply(), Reply(raw=b"")])
    with pytest.raises(DockerUnavailableError, match=r"^execution_engine_unavailable$"):
        case.launch()
    record = case.journal.lookup(OID, NS)
    assert record is not None and record["state"] == "UNKNOWN"
    assert record["container_id"] == (None if phase == "create" else CID)
    count = len(endpoint.seen)
    with pytest.raises(JournalError):
        case.launch()
    assert len(endpoint.seen) == count
    endpoint.replies.append(Reply(200, observation("created")))
    observed = case.inspect()
    assert observed.container_id == CID and observed.exit_code is None
    expected = "fa-job-" + OID.removeprefix("op-") if phase == "create" else CID
    assert endpoint.seen[-1]["path"] == f"/v1.45/containers/{expected}/json"
    assert len(endpoint.seen) == count + 1  # Read-only original-name/ID observation, no fresh start.


@pytest.mark.parametrize("bad", ["binding", "cancel", "input", "profile", "mode", "timeout", "expired"])
def test_all_prelaunch_gates_precede_daemon_contact(endpoint: Endpoint, tmp_path: Path, bad: str) -> None:
    case = Case(endpoint, tmp_path)
    endpoint.replies.extend([Reply(), Reply(204)])
    if bad == "binding":
        case.denied = True
    elif bad == "cancel":
        case.journal.request_cancel(OID, NS)
    elif bad == "input":
        case.req["payload"]["command"] = "different command"
    elif bad == "profile":
        case.req["payload"]["profile_id"] = "other"
    elif bad == "mode":
        case.req["payload"]["session_id"] = None
    elif bad == "timeout":
        case.req["payload"]["timeout_ms"] = profile().max_command_ms + 1
    with pytest.raises((ExecutionContractError, JournalError, TimeoutError)):
        case.launch(until=time.monotonic() - 1 if bad == "expired" else None)
    assert endpoint.seen == []


@pytest.mark.parametrize("status", ["created", "running", "paused", "restarting", "dead", "exited"])
def test_inspection_requires_real_exited_state_not_provisional_exit_zero(endpoint: Endpoint, status: str) -> None:
    endpoint.replies.append(Reply(200, observation(status)))
    observed = endpoint.engine().inspect_owned(
        operation_id=OID, view=VIEW, profile=profile(), container_id=CID, deadline=deadline()
    )
    assert observed.status == status and observed.container_id == CID
    assert observed.image_id == "sha256:" + "8" * 64
    assert observed.exit_code == (7 if status == "exited" else None)
    assert not hasattr(observed, "terminal_barrier")


@pytest.mark.parametrize(
    "field,value",
    [
        ("Id", "9" * 64),
        ("Name", "/foreign"),
        ("Image", "invalid"),
        ("Config.Image", "foreign@sha256:" + "9" * 64),
        ("Config.Labels.fa.execution.operation_id", "op-" + "9" * 32),
        ("Config.Labels.fa.execution.view_id", "view-" + "9" * 32),
        ("State.Running", 1),
        ("State.Pid", True),
        ("State.Pid", -1),
        ("State.ExitCode", False),
        ("State.Status", "unknown"),
        ("State.Running", True),
    ],
)
def test_foreign_or_indeterminate_inspection_is_rejected(endpoint: Endpoint, field: str, value: Any) -> None:
    data = observation("exited")
    parent: Any = data
    parts = field.split(".")
    # Docker labels contain literal dots, not nested namespace components.
    if field.startswith("Config.Labels."):
        parent = data["Config"]["Labels"]
        parts = [field.removeprefix("Config.Labels.")]
    for part in parts[:-1]:
        parent = parent[part]
    parent[parts[-1]] = value
    endpoint.replies.append(Reply(200, data))
    with pytest.raises(DockerUnavailableError):
        endpoint.engine().inspect_owned(
            operation_id=OID, view=VIEW, profile=profile(), container_id=CID, deadline=deadline()
        )
    assert len(endpoint.seen) == 1


@pytest.mark.parametrize(
    "raw",
    [
        b"HTTP/1.1 302 Unit\r\nLocation: http://forbidden.invalid\r\nContent-Length: 0\r\n\r\n",
        b"HTTP/1.1 500 Unit\r\nContent-Length: 17\r\n\r\nprivate diagnostic",
        b"HTTP/1.1 201 Unit\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n{}",
        b"HTTP/1.1 201 Unit\r\nContent-Length: 9999999999\r\n\r\n",
        b"HTTP/1.1 201 Unit\r\nTransfer-Encoding: chunked\r\nContent-Length: 2\r\n\r\n0\r\n\r\n",
        b"HTTP/1.1 201 Unit\r\nContent-Length: 10\r\n\r\n{}",
        b"HTTP/1.1 201 Unit\r\nContent-Length: 8\r\n\r\nnot-json",
    ],
)
def test_malformed_redirect_or_error_never_leaks_body_or_retries(endpoint: Endpoint, raw: bytes) -> None:
    endpoint.replies.append(Reply(raw=raw))
    with pytest.raises(DockerUnavailableError) as caught:
        create(endpoint.engine())
    assert str(caught.value) == "execution_engine_unavailable"
    assert len(endpoint.seen) == 1


def test_valid_chunked_create_response_is_supported(endpoint: Endpoint) -> None:
    body = json.dumps({"Id": CID, "Warnings": []}).encode()
    endpoint.replies.append(
        Reply(
            raw=b"HTTP/1.1 201 Unit\r\nTransfer-Encoding: chunked\r\n\r\n"
            + f"{len(body):x}\r\n".encode()
            + body
            + b"\r\n0\r\n\r\n"
        )
    )
    assert create(endpoint.engine()) == CID and len(endpoint.seen) == 1


@pytest.mark.parametrize("value", [{"Id": "invalid", "Warnings": []}, {"Id": CID, "Warnings": ["ignored isolation"]}])
def test_create_rejects_invalid_identity_or_daemon_warning(endpoint: Endpoint, value: dict[str, Any]) -> None:
    endpoint.replies.append(Reply(value=value))
    with pytest.raises(DockerUnavailableError):
        create(endpoint.engine())
    assert len(endpoint.seen) == 1


def test_kernel_peer_is_checked_before_sending(endpoint: Endpoint, monkeypatch: pytest.MonkeyPatch) -> None:
    import struct

    monkeypatch.setattr(
        socket.socket, "getsockopt", lambda *args: struct.pack("3i", os.getpid(), os.getuid() + 1, os.getgid())
    )
    with pytest.raises(DockerUnavailableError):
        create(endpoint.engine())
    assert endpoint.seen == []


def test_slow_drip_cannot_reset_absolute_rpc_budget(endpoint: Endpoint, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.execution.docker import _DeadlineSocket

    budgets: list[float | None] = []
    original = _DeadlineSocket.recv_into

    def receive(self: _DeadlineSocket, buffer: Any, nbytes: int = 0, flags: int = 0) -> int:
        try:
            return original(self, buffer, nbytes, flags)
        finally:
            budgets.append(self.gettimeout())

    monkeypatch.setattr(_DeadlineSocket, "recv_into", receive)
    body = json.dumps({"Id": CID, "Warnings": []}).encode()
    head = f"HTTP/1.1 201 Unit\r\nContent-Length: {len(body)}\r\n\r\n".encode()
    endpoint.replies.append(Reply(chunks=[head, *[body[i : i + 5] for i in range(0, len(body), 5)]]))
    with pytest.raises(DockerUnavailableError):
        create(endpoint.engine(timeout=70))
    assert len(endpoint.seen) == 1
    finite = [value for value in budgets if value is not None]
    assert len(finite) >= 2 and finite[-1] < finite[0] - 0.01


@pytest.mark.parametrize(
    "changes", [{"daemon_uid": True}, {"rpc_timeout_ms": 0}, {"api_version": "1.40"}, {"api_version": "1.45/evil"}]
)
def test_invalid_private_daemon_configuration_is_rejected(endpoint: Endpoint, changes: dict[str, Any]) -> None:
    params: dict[str, Any] = {"daemon_uid": os.getuid(), "api_version": "1.45", "rpc_timeout_ms": 1000, **changes}
    with pytest.raises(ExecutionContractError):
        DockerEngine(endpoint.path, **params)
    assert endpoint.seen == []


def test_nonzero_length_on_start_ack_is_not_silently_discarded(endpoint: Endpoint) -> None:
    endpoint.replies.append(Reply(raw=b"HTTP/1.1 204 Unit\r\nContent-Length: 4\r\n\r\nbody"))
    with pytest.raises(DockerUnavailableError):
        endpoint.engine().start(CID, deadline=deadline())
    assert len(endpoint.seen) == 1


def test_inspect_input_collision_never_contacts_daemon(endpoint: Endpoint, tmp_path: Path) -> None:
    case = Case(endpoint, tmp_path)
    case.req["payload"]["command"] = "changed"
    with pytest.raises(JournalError):
        case.inspect()
    assert endpoint.seen == []


def test_daemon_id_is_returned_not_synthesized(endpoint: Endpoint) -> None:
    actual = "9" * 64
    endpoint.replies.append(Reply(value={"Id": actual, "Warnings": None}))
    assert create(endpoint.engine()) == actual and len(endpoint.seen) == 1
