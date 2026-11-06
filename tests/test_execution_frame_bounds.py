"""C0: explicit bounded framing, not an expanded EXEC contract."""

from __future__ import annotations

import struct

import pytest

from fa.execution.protocol import (
    MAX_EXTENDED_FRAME_BYTES,
    MAX_FRAME_BYTES,
    _loads,
    encode_json,
    read_frame,
    write_frame,
)
from fa.execution.types import ExecutionContractError


class _Connection:
    def __init__(self, incoming: bytes = b"") -> None:
        self.incoming = incoming
        self.received = 0
        self.sent: list[bytes] = []

    def recv(self, size: int, /) -> bytes:
        # Split each header to exercise fragmented frame reads.
        size = min(size, 2 if self.received < 4 else 65536)
        data, self.incoming = self.incoming[:size], self.incoming[size:]
        self.received += len(data)
        return data

    def sendall(self, data: bytes, /) -> None:
        self.sent.append(data)


def test_frame_budgets_are_explicit_and_finite() -> None:
    assert MAX_FRAME_BYTES == 4 * 1024 * 1024
    assert MAX_EXTENDED_FRAME_BYTES == 16 * 1024 * 1024


def test_default_budget_rejects_larger_frame_before_reading_body() -> None:
    conn = _Connection(struct.pack("!I", MAX_FRAME_BYTES + 1) + b"body")
    with pytest.raises(ExecutionContractError):
        read_frame(conn)
    assert conn.received == 4 and conn.incoming == b"body"


def test_explicit_extended_budget_roundtrips_but_default_writer_refuses() -> None:
    raw = b"x" * (MAX_FRAME_BYTES + 1)
    conn = _Connection()
    with pytest.raises(ExecutionContractError):
        write_frame(conn, raw)
    assert conn.sent == []
    write_frame(conn, raw, max_bytes=MAX_FRAME_BYTES + 1)
    assert read_frame(_Connection(conn.sent[0]), max_bytes=MAX_FRAME_BYTES + 1) == raw


def test_exact_and_over_boundary_are_byte_counted() -> None:
    raw = "яя".encode()
    writer = _Connection()
    write_frame(writer, raw, max_bytes=4)
    assert read_frame(_Connection(writer.sent[0]), max_bytes=4) == raw
    with pytest.raises(ExecutionContractError):
        read_frame(_Connection(writer.sent[0]), max_bytes=3)
    with pytest.raises(ExecutionContractError):
        write_frame(_Connection(), raw, max_bytes=3)


@pytest.mark.parametrize("invalid", [0, -1, True, MAX_EXTENDED_FRAME_BYTES + 1, 1.5])
def test_invalid_limit_rejected_before_io(invalid: object) -> None:
    conn = _Connection(struct.pack("!I", 1) + b"a")
    with pytest.raises(ExecutionContractError):
        read_frame(conn, max_bytes=invalid)  # type: ignore[arg-type]
    with pytest.raises(ExecutionContractError):
        write_frame(conn, b"a", max_bytes=invalid)  # type: ignore[arg-type]
    assert conn.received == 0 and conn.sent == []


def test_maximum_header_rejected_if_declared_one_byte_over() -> None:
    conn = _Connection(struct.pack("!I", MAX_EXTENDED_FRAME_BYTES + 1) + b"body")
    with pytest.raises(ExecutionContractError):
        read_frame(conn, max_bytes=MAX_EXTENDED_FRAME_BYTES)
    assert conn.received == 4 and conn.incoming == b"body"


def test_truncated_payload_fails_closed() -> None:
    conn = _Connection(struct.pack("!I", 5) + b"abc")
    with pytest.raises(ExecutionContractError):
        read_frame(conn, max_bytes=5)


def test_extended_json_codec_is_opt_in_and_keeps_per_string_bounds() -> None:
    value = {"chunks": ["x" * (1024 * 1024)] * 5}
    with pytest.raises(ExecutionContractError):
        encode_json(value)
    raw = encode_json(value, max_bytes=MAX_EXTENDED_FRAME_BYTES)
    assert len(raw) > MAX_FRAME_BYTES
    with pytest.raises(ExecutionContractError):
        _loads(raw)
    assert _loads(raw, max_bytes=MAX_EXTENDED_FRAME_BYTES) == value
    with pytest.raises(ExecutionContractError):
        encode_json({"text": "x" * (1024 * 1024 + 1)}, max_bytes=MAX_EXTENDED_FRAME_BYTES)


@pytest.mark.parametrize("invalid", [0, -1, True, MAX_EXTENDED_FRAME_BYTES + 1])
def test_json_codec_rejects_invalid_frame_budgets(invalid: object) -> None:
    with pytest.raises(ExecutionContractError):
        _loads(b"{}", max_bytes=invalid)  # type: ignore[arg-type]
    with pytest.raises(ExecutionContractError):
        encode_json({}, max_bytes=invalid)  # type: ignore[arg-type]


def test_extended_json_codec_still_rejects_duplicates_and_nonfinite() -> None:
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}'):
        with pytest.raises(ExecutionContractError):
            _loads(raw, max_bytes=MAX_EXTENDED_FRAME_BYTES)
    with pytest.raises(ExecutionContractError):
        encode_json({"x": float("inf")}, max_bytes=MAX_EXTENDED_FRAME_BYTES)
