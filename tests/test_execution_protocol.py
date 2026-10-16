"""C0/C3 closed wire data and real socketpair framing, not service/OS proof."""

from __future__ import annotations

import copy
import json
import socket
import struct
from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

from fa.execution.protocol import (
    MAX_FRAME_BYTES,
    MAX_TAIL_BYTES,
    MAX_TEXT_BYTES,
    InvalidRequestError,
    decode_reply,
    decode_request,
    encode_json,
    read_frame,
    write_frame,
)
from fa.execution.types import ExecutionContractError, ExecutionReceipt, JobState, NamespaceRef, Operation, OperationRef

RID = "1" * 32
WS = "ws-" + "2" * 32
REV = "rev-" + "3" * 32
VID = "view-" + "4" * 32
SHA = "5" * 64
CAP = "6" * 64
NS = {"session_id": "session-1", "run_id": "run-1", "parent_run_id": None}
VIEW = {
    "workspace_id": WS,
    "generation": 1,
    "base_revision": REV,
    "view_id": VID,
    "owner_run_id": "run-1",
    "access": "WRITE",
    "purpose": "PROJECT",
}
RECEIPT = {
    "schema_version": 1,
    "operation_id": "op-" + RID,
    "namespace": NS,
    "workspace_id": WS,
    "view_id": VID,
    "owner_run_id": "run-1",
    "generation": 1,
    "revision_id": REV,
    "original_revision_id": REV,
    "input_tree_sha256": SHA,
    "plan_sha256": SHA,
    "profile_id": "verification",
    "image_digest": "sha256:" + SHA,
    "state": "EXITED",
    "exit_code": 0,
    "timed_out": False,
    "stdout_tail": "ok",
    "stderr_tail": "",
    "truncated": False,
    "duration_ms": 1,
    "terminal_barrier": True,
}
# Literal independent v1 witnesses, not generated from the implementation schema.
PAYLOADS: dict[Operation, dict[str, Any]] = {
    Operation.HEALTH: {},
    Operation.REGISTER_WORKSPACE: {
        "root_id": "projects",
        "relative_root": "project",
        "create": False,
        "input_id": None,
    },
    Operation.ACQUIRE_WRITER: {"workspace_id": WS},
    Operation.PIN_READER: {"workspace_id": WS, "revision_id": REV},
    Operation.CREATE_VIEW: {
        "workspace_id": WS,
        "base_revision": REV,
        "access": "WRITE",
        "purpose": "PROJECT",
        "candidate_scope": None,
    },
    Operation.READ_FILE: {"path": "src/main.py", "offset_bytes": 0, "max_bytes": 1024},
    Operation.WRITE_FILE: {"path": "src/main.py", "content": "ü", "expected_sha256": None},
    Operation.EDIT_FILE: {"path": "src/main.py", "content": "ü", "expected_sha256": SHA},
    Operation.EXEC: {
        "operation_id": "op-" + RID,
        "profile_id": "verification",
        "command": "pytest",
        "cwd": ".",
        "timeout_ms": 30000,
        "session_id": None,
    },
    Operation.INSPECT: {"operation_id": "op-" + RID},
    Operation.CANCEL: {"operation_id": "op-" + RID},
    Operation.PTY_CONTROL: {"action": "LIST", "session_id": None},
    Operation.STOP_VIEW: {},
    Operation.SEAL: {},
    Operation.PUBLISH: {"sealed_manifest_id": "seal-" + RID, "expected_base_revision": REV},
    Operation.PREPARE_BUNDLE: {
        "project_slug": "project",
        "increment_slug": "i03",
        "roadmap_text": "roadmap",
        "increment_text": "increment",
        "expected_base_revision": REV,
    },
    Operation.INSTALL_PROJECT: {"validated_bundle_id": "bundle-" + RID, "project_slug": "project"},
    Operation.HANDOFF: {"target_namespace": {**NS, "run_id": "child", "parent_run_id": "run-1"}},
    Operation.RELEASE: {},
}
COMMITTED = {
    "workspace_id": WS,
    "revision_id": REV,
    "tree_sha256": SHA,
    "operation_id": "op-" + RID,
    "projection_complete": True,
}
RESULTS: dict[Operation, dict[str, Any]] = {
    Operation.HEALTH: {"ready": False, "protocol_version": 1, "profile_set_sha256": SHA},
    Operation.REGISTER_WORKSPACE: {"workspace_id": WS, "revision_id": REV},
    Operation.ACQUIRE_WRITER: {"view_ref": None, "capability": CAP, "generation": 1, "revision_id": REV},
    Operation.HANDOFF: {"view_ref": None, "capability": CAP, "generation": 1, "revision_id": REV},
    Operation.PIN_READER: {"view_ref": {**VIEW, "access": "READ"}, "capability": CAP},
    Operation.CREATE_VIEW: {"view_ref": VIEW, "capability": CAP},
    Operation.READ_FILE: {"content": "ü", "sha256": SHA, "eof": True},
    Operation.WRITE_FILE: {"sha256": SHA, "bytes": 2},
    Operation.EDIT_FILE: {"sha256": SHA, "bytes": 2},
    Operation.EXEC: {"receipt": RECEIPT},
    Operation.INSPECT: {"receipt": RECEIPT},
    Operation.CANCEL: {"receipt": RECEIPT},
    Operation.PTY_CONTROL: {"sessions": ["main"], "message": "ok"},
    Operation.STOP_VIEW: {"view_id": VID, "terminal": False},
    Operation.SEAL: {"sealed_manifest_id": "seal-" + RID, "revision_id": REV, "tree_sha256": SHA},
    Operation.PUBLISH: COMMITTED,
    Operation.INSTALL_PROJECT: COMMITTED,
    Operation.PREPARE_BUNDLE: {"validated_bundle_id": "bundle-" + RID, "bundle_sha256": SHA},
    Operation.RELEASE: {"released": True},
}


def request(op: Operation) -> dict[str, Any]:
    pregrant = op in {Operation.HEALTH, Operation.REGISTER_WORKSPACE, Operation.ACQUIRE_WRITER, Operation.PIN_READER}
    owner = pregrant or op in {
        Operation.CREATE_VIEW,
        Operation.PREPARE_BUNDLE,
        Operation.INSTALL_PROJECT,
        Operation.HANDOFF,
        Operation.RELEASE,
    }
    return copy.deepcopy(
        {
            "protocol_version": 1,
            "request_id": RID,
            "op": op.value,
            "namespace": None if op is Operation.HEALTH else NS,
            "view_ref": None if owner else VIEW,
            "capability": None if pregrant else CAP,
            "payload": PAYLOADS[op],
        }
    )


def response(op: Operation) -> dict[str, Any]:
    return copy.deepcopy(
        {"protocol_version": 1, "request_id": RID, "status": "OK", "result": RESULTS[op], "error": None}
    )


@pytest.mark.parametrize("op", list(Operation))
def test_all_nineteen_complete_payloads_and_results(op: Operation) -> None:
    assert set(PAYLOADS) == set(RESULTS) == set(Operation)
    req, res = request(op), response(op)
    assert decode_request(encode_json(req)) == req
    assert decode_reply(encode_json(res), operation=op, request_id=RID) == res
    for target in [req, req["payload"]]:
        target["injected_host_path"] = "/var/run/docker.sock"
        with pytest.raises(InvalidRequestError) as caught:
            decode_request(encode_json(req))
        assert caught.value.request_id == RID
        assert CAP not in str(caught.value)
        del target["injected_host_path"]
    for key in list(req["payload"]):
        broken = copy.deepcopy(req)
        del broken["payload"][key]
        with pytest.raises(InvalidRequestError):
            decode_request(encode_json(broken))
    for key in list(res["result"]):
        broken = copy.deepcopy(res)
        del broken["result"][key]
        with pytest.raises(ExecutionContractError):
            decode_reply(encode_json(broken), operation=op, request_id=RID)
    res["result"]["secret"] = CAP
    with pytest.raises(ExecutionContractError):
        decode_reply(encode_json(res), operation=op, request_id=RID)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"[]",
        b"null",
        b"\xff",
        b'{"request_id":"bad"}',
        b'{"request_id":true}',
        b'{"request_id":"' + RID.encode() + b'","request_id":"' + RID.encode() + b'"}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b"[" * 2000,
        b" " * (MAX_FRAME_BYTES + 1),
    ],
)
def test_untrusted_or_malformed_id_is_never_echoed(raw: bytes) -> None:
    with pytest.raises(ExecutionContractError) as caught:
        decode_request(raw)
    assert getattr(caught.value, "request_id", None) is None
    assert str(caught.value) == "execution_contract_invalid"


@pytest.mark.parametrize(
    "field,value",
    [
        ("protocol_version", True),
        ("protocol_version", 1.0),
        ("op", "host_exec"),
        ("capability", None),
        ("view_ref", None),
        ("namespace", None),
    ],
)
def test_wrong_envelope_types_or_authority_shapes(field: str, value: Any) -> None:
    req = request(Operation.EXEC)
    req[field] = value
    with pytest.raises(InvalidRequestError):
        decode_request(json.dumps(req).encode())


@pytest.mark.parametrize("path", ["/absolute", "../escape", "a/../b", "a//b", "a/./b", "a/", ".", "a\0b", "a\n"])
def test_paths_cannot_escape_or_normalize_away_components(path: str) -> None:
    req = request(Operation.READ_FILE)
    req["payload"]["path"] = path
    # Newline is valid POSIX data, unlike traversal/NUL; do not invent a shell grammar.
    if path == "a\n":
        assert decode_request(encode_json(req)) == req
    else:
        with pytest.raises(ExecutionContractError):
            decode_request(encode_json(req))


@pytest.mark.parametrize(
    "field,value",
    [
        ("timeout_ms", False),
        ("timeout_ms", 0),
        ("timeout_ms", 1.0),
        ("operation_id", "op-" + "f" * 32),
        ("cwd", "../outside"),
        ("session_id", "../outside"),
    ],
)
def test_exec_input_cannot_change_reserved_identity_or_types(field: str, value: Any) -> None:
    req = request(Operation.EXEC)
    req["payload"][field] = value
    with pytest.raises(ExecutionContractError):
        decode_request(json.dumps(req).encode())


def test_candidate_and_pty_dependent_shapes() -> None:
    req = request(Operation.CREATE_VIEW)
    req["payload"]["purpose"] = "CANDIDATE"
    with pytest.raises(InvalidRequestError):
        decode_request(encode_json(req))
    req["payload"]["candidate_scope"] = {
        "candidate_path": "draft.md",
        "plan_ref": {"workspace_relative_path": "plan.md", "source_kind": "EXPLICIT", "sha256": SHA},
    }
    assert decode_request(encode_json(req)) == req
    req["payload"]["purpose"] = "PROJECT"
    with pytest.raises(InvalidRequestError):
        decode_request(encode_json(req))
    req = request(Operation.PTY_CONTROL)
    req["payload"]["action"] = "CLOSE"
    with pytest.raises(InvalidRequestError):
        decode_request(encode_json(req))
    req["payload"]["session_id"] = "main"
    assert decode_request(encode_json(req)) == req


@pytest.mark.parametrize(
    "changes",
    [
        {"exit_code": None},
        {"duration_ms": True},
        {"generation": 0},
        {"schema_version": True},
        {"state": "UNKNOWN", "exit_code": 0},
        {"state": "LAUNCH_FAILED", "exit_code": 0},
        {"state": "RUNNING", "exit_code": None, "terminal_barrier": True},
        {"timed_out": True},
        {"stdout_tail": "ü" * (MAX_TAIL_BYTES // 2 + 1)},
    ],
)
def test_receipt_cannot_manufacture_determinate_success(changes: dict[str, Any]) -> None:
    with pytest.raises(ExecutionContractError):
        ExecutionReceipt.from_dict({**RECEIPT, **changes})


def test_receipt_full_roundtrip_immutability_and_all_states() -> None:
    receipt = ExecutionReceipt.from_dict(RECEIPT)
    assert receipt.to_dict() == RECEIPT
    assert receipt.namespace == NamespaceRef("session-1", "run-1")
    for state in JobState:
        body = {
            **RECEIPT,
            "state": state.value,
            "exit_code": 0 if state is JobState.EXITED else None,
            "timed_out": state is JobState.TIMED_OUT,
            "terminal_barrier": False,
        }
        assert ExecutionReceipt.from_dict(body).state is state
    assert replace(receipt, stdout_tail="ü" * (MAX_TAIL_BYTES // 2)).stdout_tail
    assert OperationRef("op-" + RID, VID, "run-1", 1, SHA).operation_id == "op-" + RID
    with pytest.raises(ExecutionContractError):
        OperationRef("op-" + RID, VID, "run-1", True, SHA)
    with pytest.raises(ExecutionContractError):
        OperationRef("op-" + RID, VID, "../escape", 1, SHA)


def test_text_utf8_limits_and_nonfinite_numbers() -> None:
    req = request(Operation.WRITE_FILE)
    req["payload"]["content"] = "ü" * (MAX_TEXT_BYTES // 2)
    assert decode_request(encode_json(req)) == req
    req["payload"]["content"] += "ü"
    with pytest.raises(ExecutionContractError):
        decode_request(json.dumps(req, ensure_ascii=False).encode())
    with pytest.raises(ExecutionContractError):
        encode_json(req)
    for raw in [b'{"a":1e999}', b'{"a":"\\ud800"}']:
        with pytest.raises(ExecutionContractError):
            decode_request(raw)
    with pytest.raises(ExecutionContractError):
        encode_json({"a": float("nan")})


def test_error_reply_is_closed_correlated_and_never_contains_exception_text() -> None:
    body: dict[str, Any] = {
        "protocol_version": 1,
        "request_id": RID,
        "status": "ERROR",
        "result": None,
        "error": {"code": "EXECUTION_UNKNOWN", "retryable": False, "operation_id": "op-" + RID},
    }
    assert decode_reply(encode_json(body), operation=Operation.EXEC, request_id=RID) == body
    for changed in [
        {**body, "request_id": "f" * 32},
        {**body, "result": {}},
        {**body, "error": None},
        {**body, "error": {**body["error"], "message": CAP}},
    ]:
        with pytest.raises(ExecutionContractError):
            decode_reply(encode_json(changed), operation=Operation.EXEC, request_id=RID)


def test_real_socketpair_framing_and_partial_eof() -> None:
    left, right = socket.socketpair()
    with left, right:
        left.settimeout(1)
        right.settimeout(1)
        write_frame(left, b'{"a":1}')
        assert read_frame(right) == b'{"a":1}'
        left.sendall(struct.pack("!I", 4) + b"xy")
        left.shutdown(socket.SHUT_WR)
        with pytest.raises(ExecutionContractError):
            read_frame(right)


@pytest.mark.parametrize("length", [0, MAX_FRAME_BYTES + 1, 0xFFFFFFFF])
def test_header_limit_checked_before_body_read(length: int) -> None:
    left, right = socket.socketpair()
    with left, right:
        right.settimeout(0.2)
        left.sendall(struct.pack("!I", length))
        with pytest.raises(ExecutionContractError):
            read_frame(right)
    left, right = socket.socketpair()
    with left, right:
        with pytest.raises(ExecutionContractError):
            write_frame(left, b"" if length == 0 else b"x" * (MAX_FRAME_BYTES + 1))


def test_encoded_frame_limit_is_independent_of_individual_body_limits() -> None:
    req = encode_json(request(Operation.HEALTH))
    assert decode_request(req + b" " * (MAX_FRAME_BYTES - len(req)))["op"] == "health"
    with pytest.raises(ExecutionContractError):
        decode_request(req + b" " * (MAX_FRAME_BYTES + 1 - len(req)))
    with pytest.raises(ExecutionContractError):
        encode_json({str(i): "x" * MAX_TEXT_BYTES for i in range(5)})


@pytest.mark.parametrize("field", ["state", "exit_code", "namespace"])
def test_receipt_frozen_fields_cannot_be_replaced(field: str) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(ExecutionReceipt.from_dict(RECEIPT), field, None)
