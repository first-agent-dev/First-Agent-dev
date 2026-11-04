"""C1 local socket Docker mux framing, not a real daemon/host proof."""

from __future__ import annotations

import socket
import struct
import threading
import time

import pytest

from fa.execution.docker import DockerAttachStream, DockerUnavailableError
from fa.execution.protocol import MAX_EXTENDED_FRAME_BYTES, MAX_FRAME_BYTES


def _mux(data: bytes, *, kind: int = 1) -> bytes:
    return bytes([kind, 0, 0, 0]) + struct.pack("!I", len(data)) + data


def _framed(data: bytes) -> bytes:
    return struct.pack("!I", len(data)) + data


def _run(wire: bytes, *, limit: int | None) -> bytes:
    left, right = socket.socketpair()
    stream = DockerAttachStream(left)

    def send() -> None:
        try:
            right.sendall(wire)
        except OSError:
            pass  # The reader is allowed to refuse the declared size early.
        finally:
            right.close()

    thread = threading.Thread(target=send)
    thread.start()
    try:
        if limit is None:
            return stream.read_frame(deadline=time.monotonic() + 10)
        return stream.read_frame(deadline=time.monotonic() + 10, max_bytes=limit)
    finally:
        stream.close()
        thread.join(10)
        assert not thread.is_alive()


def test_extended_docker_frame_is_opt_in() -> None:
    raw = b"x" * (MAX_FRAME_BYTES + 1)
    wire = _mux(_framed(raw))
    assert _run(wire, limit=MAX_FRAME_BYTES + 1) == raw
    with pytest.raises(DockerUnavailableError):
        _run(wire, limit=None)


def test_mux_limit_and_inner_length_bound_are_enforced() -> None:
    with pytest.raises(DockerUnavailableError):
        _run(_mux(_framed(b"abcd")), limit=3)
    # Each mux frame fits, but the assembled inner length exceeds the budget.
    with pytest.raises(DockerUnavailableError):
        _run(_mux(struct.pack("!I", 4)) + _mux(b"abcd"), limit=3)


def test_extended_read_does_not_allow_unbounded_stderr() -> None:
    # Many individually legal multiplex frames must not evade the aggregate cap.
    wire = _mux(b"eeee", kind=2) * 6000 + _mux(_framed(b"x"))
    with pytest.raises(DockerUnavailableError):
        _run(wire, limit=1)


@pytest.mark.parametrize("bad", [0, True, MAX_EXTENDED_FRAME_BYTES + 1])
def test_invalid_budget_is_refused(bad: int) -> None:
    with pytest.raises(DockerUnavailableError):
        _run(_mux(_framed(b"a")), limit=bad)
