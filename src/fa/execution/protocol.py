"""Closed v1 JSON control contract; shape validation is NEVER authorization.

Four-byte unsigned network-order length followed by bounded UTF-8 JSON. Socket
callers must set a finite control-RPC timeout. There are no retries here.
"""

from __future__ import annotations

import json
import re
import socket
import struct
import time
from typing import Any, Protocol

import fastjsonschema  # type: ignore[import-untyped]  # Existing dependency ships no typing metadata.

from fa.execution.primitives import ExecutionContractError, Operation, _positive_integer

MAX_FRAME_BYTES = 4 * 1024 * 1024
# Opt-in framing ceiling for future large EXEC replies; ordinary requests and
# replies keep MAX_FRAME_BYTES. This is not an EXEC payload/receipt limit.
MAX_EXTENDED_FRAME_BYTES = 16 * 1024 * 1024
MAX_TEXT_BYTES = 1024 * 1024
MAX_TAIL_BYTES = 64 * 1024


def _object(**properties: Any) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def _enum(*values: object) -> dict[str, Any]:
    return {"enum": list(values)}


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _pattern(pattern: str) -> dict[str, Any]:
    # \Z, not $, rejects a trailing newline under Python regular expressions.
    return {"type": "string", "pattern": "^(?:" + pattern + r")\Z"}


def _id(prefix: str) -> dict[str, Any]:
    return _pattern(re.escape(prefix) + "[0-9a-f]{32}")


TEXT: dict[str, Any] = {"type": "string", "maxLength": MAX_TEXT_BYTES}
BOOL = {"type": "boolean"}
UINT = {"type": "integer", "minimum": 0}
POSITIVE = {"type": "integer", "minimum": 1}
SHA = _pattern("[0-9a-f]{64}")
CONFIG_ID = _pattern("[a-z][a-z0-9]*(?:-[a-z0-9]+)*") | {"maxLength": 48}
NAMESPACE_ID = _pattern("[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
SESSION_ID = _pattern("[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
PATH = _pattern(r"[^/\x00]+(?:/[^/\x00]+)*")
NAMESPACE = _object(session_id=NAMESPACE_ID, run_id=NAMESPACE_ID, parent_run_id=_nullable(NAMESPACE_ID))
VIEW = _object(
    workspace_id=_id("ws-"),
    generation=POSITIVE,
    base_revision=_id("rev-"),
    view_id=_id("view-"),
    owner_run_id=NAMESPACE_ID,
    access=_enum("READ", "WRITE"),
    purpose=_enum("PROJECT", "PROVISIONING", "VERIFICATION", "MUTATION", "CANDIDATE"),
)
# Existing PlanRef spelling, not a second abbreviated plan identity.
PLAN_REF = _object(
    workspace_relative_path=PATH, source_kind=_enum("EXPLICIT", "EXISTING_SELECTION", "BOOTSTRAP"), sha256=SHA
)
# CT120 (E302): the CANDIDATE view has one writable target, and the plan it
# publishes is identified by `plan_ref` alone. The controller used to name a
# second path beside it; the authority never used that name for IO.
CANDIDATE_SCOPE = _object(plan_ref=PLAN_REF)
RECEIPT = _object(
    schema_version={"type": "integer", "const": 1},
    operation_id=_id("op-"),
    namespace=NAMESPACE,
    workspace_id=_id("ws-"),
    view_id=_id("view-"),
    owner_run_id=NAMESPACE_ID,
    generation=POSITIVE,
    revision_id=_nullable(_id("rev-")),
    original_revision_id=_nullable(_id("rev-")),
    input_tree_sha256=SHA,
    plan_sha256=_nullable(SHA),
    profile_id=CONFIG_ID,
    image_digest=_pattern("sha256:[0-9a-f]{64}"),
    state=_enum("RESERVED", "RUNNING", "EXITED", "CANCELLED", "TIMED_OUT", "LAUNCH_FAILED", "UNKNOWN"),
    exit_code=_nullable({"type": "integer"}),
    timed_out=BOOL,
    stdout_tail=TEXT,
    stderr_tail=TEXT,
    truncated=BOOL,
    duration_ms=UINT,
    terminal_barrier=BOOL,
)
PAYLOADS: dict[Operation, dict[str, Any]] = {
    Operation.HEALTH: _object(),
    Operation.REGISTER_WORKSPACE: _object(
        root_id=CONFIG_ID, relative_root=PATH, create=BOOL, input_id=_nullable(CONFIG_ID)
    ),
    Operation.ACQUIRE_WRITER: _object(workspace_id=_id("ws-")),
    Operation.PIN_READER: _object(workspace_id=_id("ws-"), revision_id=_id("rev-"), plan_ref=_nullable(PLAN_REF)),
    Operation.CREATE_VIEW: _object(
        workspace_id=_id("ws-"),
        # Null binds the view to whatever is current when the copy starts
        # (CT117): a patch publish must not demand that nothing else moved.
        # Only CANDIDATE/VERIFICATION accept it; a PROJECT/MUTATION writer
        # still names the bytes it intends to mutate.
        base_revision=_nullable(_id("rev-")),
        access=VIEW["properties"]["access"],
        purpose=VIEW["properties"]["purpose"],
        candidate_scope=_nullable(CANDIDATE_SCOPE),
        plan_ref=_nullable(PLAN_REF),
    ),
    Operation.READ_FILE: _object(
        path=PATH, offset_bytes=UINT, max_bytes={"type": "integer", "minimum": 1, "maximum": MAX_TEXT_BYTES}
    ),
    Operation.WRITE_FILE: _object(path=PATH, content=TEXT, expected_sha256=_nullable(SHA)),
    Operation.EDIT_FILE: _object(path=PATH, content=TEXT, expected_sha256=SHA),
    Operation.EXEC: _object(
        operation_id=_id("op-"),
        profile_id=CONFIG_ID,
        command=TEXT,
        cwd=PATH,
        timeout_ms=POSITIVE,
        session_id=_nullable(SESSION_ID),
    ),
    Operation.INSPECT: _object(operation_id=_id("op-")),
    Operation.CANCEL: _object(operation_id=_id("op-")),
    Operation.PTY_CONTROL: _object(action=_enum("INTERRUPT", "CLOSE", "LIST"), session_id=_nullable(SESSION_ID)),
    Operation.STOP_VIEW: _object(),
    Operation.SEAL: _object(),
    Operation.PUBLISH: _object(sealed_manifest_id=_nullable(_id("seal-")), expected_base_revision=_id("rev-")),
    Operation.PREPARE_BUNDLE: _object(
        project_slug=CONFIG_ID,
        increment_slug=CONFIG_ID,
        roadmap_text=TEXT,
        increment_text=TEXT,
        expected_base_revision=_id("rev-"),
    ),
    Operation.INSTALL_PROJECT: _object(validated_bundle_id=_id("bundle-"), project_slug=CONFIG_ID),
    Operation.HANDOFF: _object(target_namespace=NAMESPACE),
    Operation.RELEASE: _object(),
}
_COMMITTED = _object(
    workspace_id=_id("ws-"),
    revision_id=_id("rev-"),
    tree_sha256=SHA,
    operation_id=_id("op-"),
    projection_complete={"type": "boolean", "const": True},
)
_PUBLISH_REPLY = _object(
    workspace_id=_id("ws-"),
    revision_id=_id("rev-"),
    tree_sha256=SHA,
    operation_id=_id("op-"),
    projection_complete={"type": "boolean", "const": True},
    plan_ref=_nullable(PLAN_REF),
    # True only for a candidate publish whose intent is already the current
    # bytes (CT117): the reply then names the revision that already exists
    # instead of committing a second one. Sealed publishes always send False.
    already_published=BOOL,
)
_OWNER_REPLY = _object(view_ref={"type": "null"}, capability=SHA, generation=POSITIVE, revision_id=_id("rev-"))
_VIEW_REPLY = _object(view_ref=VIEW, capability=SHA)
RESULTS: dict[Operation, dict[str, Any]] = {
    Operation.HEALTH: _object(ready=BOOL, protocol_version={"type": "integer", "const": 1}, profile_set_sha256=SHA),
    Operation.REGISTER_WORKSPACE: _object(workspace_id=_id("ws-"), revision_id=_id("rev-")),
    Operation.ACQUIRE_WRITER: _OWNER_REPLY,
    Operation.HANDOFF: _OWNER_REPLY,
    Operation.PIN_READER: _VIEW_REPLY,
    Operation.CREATE_VIEW: _VIEW_REPLY,
    Operation.READ_FILE: _object(content=TEXT, sha256=SHA, eof=BOOL),
    Operation.WRITE_FILE: _object(sha256=SHA, bytes=UINT),
    Operation.EDIT_FILE: _object(sha256=SHA, bytes=UINT),
    Operation.EXEC: _object(receipt=RECEIPT),
    Operation.INSPECT: _object(receipt=RECEIPT),
    Operation.CANCEL: _object(receipt=RECEIPT),
    Operation.PTY_CONTROL: _object(sessions={"type": "array", "items": SESSION_ID, "uniqueItems": True}, message=TEXT),
    Operation.STOP_VIEW: _object(view_id=_id("view-"), terminal=BOOL),
    Operation.SEAL: _object(sealed_manifest_id=_id("seal-"), revision_id=_id("rev-"), tree_sha256=SHA),
    Operation.PUBLISH: _PUBLISH_REPLY,
    Operation.INSTALL_PROJECT: _COMMITTED,
    Operation.PREPARE_BUNDLE: _object(validated_bundle_id=_id("bundle-"), bundle_sha256=SHA),
    Operation.RELEASE: _object(released={"type": "boolean", "const": True}),
}
ERROR_CODES = (
    "INVALID_REQUEST",
    "UNAUTHORIZED",
    "UNAPPROVED_PROFILE",
    "WORKSPACE_BUSY",
    "STALE_GENERATION",
    "STALE_REVISION",
    "VIEW_CLOSED",
    "BACKEND_UNAVAILABLE",
    "EXECUTION_UNKNOWN",
    "TERMINALITY_UNKNOWN",
    "PATH_DENIED",
    "INPUT_POLICY",
    "COLLISION",
    "DURABILITY_UNKNOWN",
    "CORRUPT_STATE",
)
_ERROR = _object(code=_enum(*ERROR_CODES), retryable=BOOL, operation_id=_nullable(_id("op-")))
_ENVELOPE = _object(
    protocol_version={"type": "integer", "const": 1},
    request_id=_id(""),
    op=_enum(*(op.value for op in Operation)),
    namespace=_nullable(NAMESPACE),
    view_ref=_nullable(VIEW),
    capability=_nullable(SHA),
    payload={"type": "object"},
)
_REPLY = _object(
    protocol_version={"type": "integer", "const": 1},
    request_id=_id(""),
    status=_enum("OK", "ERROR"),
    result={},
    error=_nullable(_ERROR),
)
_ENVELOPE_CHECK = fastjsonschema.compile(_ENVELOPE)
_REPLY_CHECK = fastjsonschema.compile(_REPLY)
_RECEIPT_CHECK = fastjsonschema.compile(RECEIPT)
_PLAN_REF_CHECK = fastjsonschema.compile(PLAN_REF)
_PAYLOAD_CHECKS = {op: fastjsonschema.compile(schema) for op, schema in PAYLOADS.items()}
_RESULT_CHECKS = {op: fastjsonschema.compile(schema) for op, schema in RESULTS.items()}


class InvalidRequestError(ExecutionContractError):
    """Valid ID may receive INVALID_REQUEST; otherwise close without any echo."""

    def __init__(self, request_id: str | None) -> None:
        super().__init__()
        self.request_id = request_id


def _byte_limits(value: Any, key: str = "") -> None:
    if isinstance(value, str):
        limit = MAX_TAIL_BYTES if key in {"stdout_tail", "stderr_tail"} else MAX_TEXT_BYTES
        if len(value.encode("utf-8")) > limit:
            raise ExecutionContractError
        if key in {"path", "workspace_relative_path", "relative_root", "cwd"}:
            if value != "." or key != "cwd":
                if any(part in {"", ".", ".."} for part in value.split("/")) or "\0" in value:
                    raise ExecutionContractError
    elif isinstance(value, float):
        raise ExecutionContractError
    elif isinstance(value, dict):
        for name, child in value.items():
            _byte_limits(child, name)
    elif isinstance(value, list):
        for child in value:
            _byte_limits(child)


def _check(checker: Any, value: Any) -> None:
    try:
        checker(value)
        _byte_limits(value)
    except (fastjsonschema.JsonSchemaException, UnicodeError, RecursionError, ValueError):
        raise ExecutionContractError from None


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ExecutionContractError
        result[key] = value
    return result


def _nonfinite(_: str) -> None:
    raise ExecutionContractError


def _loads(raw: bytes, *, max_bytes: int = MAX_FRAME_BYTES) -> dict[str, Any]:
    limit = _frame_limit(max_bytes)
    if not raw or len(raw) > limit:
        raise ExecutionContractError
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_nonfinite)
    except (ValueError, RecursionError, UnicodeError):
        raise ExecutionContractError from None
    if not isinstance(value, dict):
        raise ExecutionContractError
    return value


def encode_json(value: dict[str, Any], *, max_bytes: int = MAX_FRAME_BYTES) -> bytes:
    limit = _frame_limit(max_bytes)
    try:
        _byte_limits(value)
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise ExecutionContractError from None
    if not raw or len(raw) > limit:
        raise ExecutionContractError
    return raw


def decode_request(raw: bytes) -> dict[str, Any]:
    record = _loads(raw)
    request_id = record.get("request_id")
    valid_id = isinstance(request_id, str) and re.fullmatch("[0-9a-f]{32}", request_id) is not None
    if not valid_id:
        raise InvalidRequestError(None)
    try:
        _check(_ENVELOPE_CHECK, record)
        op = Operation(record["op"])
        _check(_PAYLOAD_CHECKS[op], record["payload"])
        _request_bindings(record, op)
    except ExecutionContractError:
        raise InvalidRequestError(request_id) from None
    return record


def _request_bindings(record: dict[str, Any], op: Operation) -> None:
    null_proof = op in {Operation.HEALTH, Operation.REGISTER_WORKSPACE, Operation.ACQUIRE_WRITER, Operation.PIN_READER}
    if (record["capability"] is None) != null_proof or (record["namespace"] is None) != (op is Operation.HEALTH):
        raise ExecutionContractError
    owner = null_proof or op in {
        Operation.CREATE_VIEW,
        Operation.PREPARE_BUNDLE,
        Operation.INSTALL_PROJECT,
        Operation.HANDOFF,
    }
    if op is not Operation.RELEASE and (record["view_ref"] is None) != owner:
        raise ExecutionContractError
    payload = record["payload"]
    if op is Operation.EXEC and payload["operation_id"] != "op-" + record["request_id"]:
        raise ExecutionContractError
    if op is Operation.CREATE_VIEW:
        if payload["base_revision"] is None and payload["purpose"] not in {"CANDIDATE", "VERIFICATION"}:
            raise ExecutionContractError
        if (payload["candidate_scope"] is not None) != (payload["purpose"] == "CANDIDATE"):
            raise ExecutionContractError
        if payload["purpose"] in {"VERIFICATION", "MUTATION", "CANDIDATE"} and payload["plan_ref"] is None:
            raise ExecutionContractError
        if payload["candidate_scope"] is not None and payload["candidate_scope"]["plan_ref"] != payload["plan_ref"]:
            raise ExecutionContractError
    if op is Operation.PUBLISH:
        view = record["view_ref"]
        candidate = view["purpose"] == "CANDIDATE"
        if (payload["sealed_manifest_id"] is None) != candidate:
            raise ExecutionContractError
        if candidate and (view["access"] != "READ" or payload["expected_base_revision"] != view["base_revision"]):
            raise ExecutionContractError
    if op is Operation.PTY_CONTROL and ((payload["session_id"] is None) != (payload["action"] == "LIST")):
        raise ExecutionContractError


def validate_plan_ref(record: dict[str, Any]) -> None:
    """One closed PlanRef spelling for wire and trusted context, not admission."""
    _check(_PLAN_REF_CHECK, record)


def validate_receipt(record: dict[str, Any]) -> None:
    """Structural truth constraints only; actual exit/barrier needs backend facts."""
    _check(_RECEIPT_CHECK, record)
    state, exit_code = record["state"], record["exit_code"]
    if state == "EXITED" and exit_code is None:
        raise ExecutionContractError
    if state in {"RESERVED", "RUNNING", "UNKNOWN", "LAUNCH_FAILED"} and exit_code is not None:
        raise ExecutionContractError
    if state in {"RESERVED", "RUNNING"} and record["terminal_barrier"]:
        raise ExecutionContractError
    if record["timed_out"] != (state == "TIMED_OUT"):
        raise ExecutionContractError


def _publish_reply_compat(result: dict[str, Any]) -> dict[str, Any]:
    """A PUBLISH reply written before ``already_published`` existed is still a reply.

    The key was added without a protocol bump, so a supervisor started before the
    upgrade answers without it. Its absence is not ambiguity: a server that has no
    repeat path always committed, which is exactly ``already_published: False``.
    Tolerance is one-directional and belongs to the newer reader only - the
    server's self-check stays strict, and the opposite window (a newer server
    answering an older client) is why client and supervisor upgrade together.
    """
    if "already_published" not in result:
        return {**result, "already_published": False}
    return result


def decode_reply(raw: bytes, *, operation: Operation, request_id: str, tolerate_legacy: bool = False) -> dict[str, Any]:
    record = _loads(raw)
    _check(_REPLY_CHECK, record)
    if record["request_id"] != request_id:
        raise ExecutionContractError
    if record["status"] == "ERROR":
        if record["error"] is None or record["result"] is not None:
            raise ExecutionContractError
    else:
        if record["error"] is not None:
            raise ExecutionContractError
        if tolerate_legacy and operation is Operation.PUBLISH and isinstance(record["result"], dict):
            record = {**record, "result": _publish_reply_compat(record["result"])}
        _check(_RESULT_CHECKS[operation], record["result"])
        if operation in {Operation.EXEC, Operation.INSPECT, Operation.CANCEL}:
            validate_receipt(record["result"]["receipt"])
        if operation is Operation.PIN_READER and record["result"]["view_ref"]["access"] != "READ":
            raise ExecutionContractError
        if operation is Operation.PUBLISH and record["result"]["already_published"]:
            # Nothing was applied without a plan identity to apply.
            if record["result"]["plan_ref"] is None:
                raise ExecutionContractError
    return record


class FrameConnection(Protocol):
    def recv(self, size: int, /) -> bytes: ...

    def sendall(self, data: bytes, /) -> None: ...


class DeadlineConnection:
    """Absolute RPC budget; an approved exec may add its command budget once."""

    def __init__(self, connection: socket.socket, *, timeout_ms: int) -> None:
        _positive_integer(timeout_ms)
        self._connection = connection
        self._started_at = time.monotonic()
        self._deadline = self._started_at + timeout_ms / 1000
        self._execution_budget_added = False

    @property
    def started_at(self) -> float:
        """One monotonic request start, before receiving its first frame byte."""
        return self._started_at

    @property
    def deadline(self) -> float:
        """Original absolute budget, including only the approved one-time loan."""
        return self._deadline

    def add_execution_budget(self, timeout_ms: int) -> None:
        """No clock reset, expired-frame revival, or repeated budget extension.

        The caller validates the request/profile BEFORE lending command time.
        This bounds transport waiting, not backend execution or terminality.
        """
        _positive_integer(timeout_ms)
        if self._execution_budget_added:
            raise ExecutionContractError
        self.remaining()
        self._deadline += timeout_ms / 1000
        self._execution_budget_added = True

    def remaining(self) -> float:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        return remaining

    def recv(self, size: int, /) -> bytes:
        self._connection.settimeout(self.remaining())
        return self._connection.recv(size)

    def sendall(self, data: bytes, /) -> None:
        self._connection.settimeout(self.remaining())
        self._connection.sendall(data)


def _read_exact(connection: FrameConnection, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = connection.recv(min(size - len(data), 64 * 1024))
        if not chunk:
            raise ExecutionContractError
        data.extend(chunk)
    return bytes(data)


def _frame_limit(max_bytes: int) -> int:
    """Check a caller's frame budget before reading or writing any bytes."""
    if type(max_bytes) is not int or not 0 < max_bytes <= MAX_EXTENDED_FRAME_BYTES:
        raise ExecutionContractError
    return max_bytes


def read_frame(connection: FrameConnection, *, max_bytes: int = MAX_FRAME_BYTES) -> bytes:
    limit = _frame_limit(max_bytes)
    length = struct.unpack("!I", _read_exact(connection, 4))[0]
    if not 0 < length <= limit:
        raise ExecutionContractError
    return _read_exact(connection, length)


def write_frame(connection: FrameConnection, raw: bytes, *, max_bytes: int = MAX_FRAME_BYTES) -> None:
    limit = _frame_limit(max_bytes)
    if not 0 < len(raw) <= limit:
        raise ExecutionContractError
    connection.sendall(struct.pack("!I", len(raw)) + raw)
