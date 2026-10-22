"""Closed cell-private codec shared by worker and supervisor-side attach client.

These are untrusted worker outcomes, NEVER execution receipts or authority.
"""

from __future__ import annotations

from typing import Any

import fastjsonschema  # type: ignore[import-untyped]  # Existing dependency lacks typing metadata.

from fa.execution.protocol import (
    BOOL,
    MAX_TAIL_BYTES,
    PATH,
    POSITIVE,
    SESSION_ID,
    TEXT,
    _check,
    _id,
    _loads,
    _nullable,
    _object,
    encode_json,
)
from fa.execution.types import ExecutionContractError

_PAYLOADS = {
    "RUN": _object(command=TEXT, cwd=PATH, timeout_ms=POSITIVE, session_id=_nullable(SESSION_ID)),
    "INTERRUPT": _object(session_id=SESSION_ID),
    "CLOSE": _object(session_id=SESSION_ID),
    "LIST": _object(),
    "STOP": _object(),
}
_CHECKS = {action: fastjsonschema.compile(schema) for action, schema in _PAYLOADS.items()}
_ENVELOPE = fastjsonschema.compile(
    _object(
        version={"type": "integer", "const": 1},
        request_id=_id(""),
        action={"enum": list(_PAYLOADS)},
        payload={"type": "object"},
    )
)
_REPLY = fastjsonschema.compile(
    _object(
        version={"type": "integer", "const": 1},
        request_id=_id(""),
        result={"anyOf": [{"type": "object"}, {"type": "null"}]},
        error=_nullable({"const": "WORKER_UNAVAILABLE"}),
    )
)
_RUN = fastjsonschema.compile(
    _object(
        stdout=TEXT,
        exit_code={"type": "integer"},
        truncated=BOOL,
        session_id=_nullable(SESSION_ID),
        timed_out=BOOL,
    )
)
_CONTROL = fastjsonschema.compile(
    _object(
        sessions={"type": "array", "items": SESSION_ID, "uniqueItems": True},
        message=TEXT,
    )
)


def decode_cell_request(raw: bytes) -> dict[str, Any]:
    record = _loads(raw)
    _check(_ENVELOPE, record)
    _check(_CHECKS[record["action"]], record["payload"])
    if record["action"] == "RUN":
        cwd = record["payload"]["cwd"]
        if cwd != "." and any(part in {"", ".", ".."} for part in cwd.split("/")):
            raise ExecutionContractError
    return record


def encode_cell_request(*, request_id: str, action: str, payload: dict[str, Any]) -> bytes:
    raw = encode_json({"version": 1, "request_id": request_id, "action": action, "payload": payload})
    decode_cell_request(raw)
    return raw


def decode_cell_reply(raw: bytes, *, request_id: str, action: str, session_id: str | None) -> dict[str, Any] | None:
    record = _loads(raw)
    _check(_REPLY, record)
    if record["request_id"] != request_id or action not in _PAYLOADS:
        raise ExecutionContractError
    if record["error"] is not None:
        if record["result"] is not None:
            raise ExecutionContractError
        return None
    result = record["result"]
    _check(_RUN if action == "RUN" else _CONTROL, result)
    if action == "RUN":
        if (
            result["session_id"] != session_id
            or len(result["stdout"].encode("utf-8")) > MAX_TAIL_BYTES
            or (not result["timed_out"] and not 0 <= result["exit_code"] <= 255)
        ):
            raise ExecutionContractError
    elif len(result["message"].encode("utf-8")) > MAX_TAIL_BYTES:
        raise ExecutionContractError
    return dict(result)
