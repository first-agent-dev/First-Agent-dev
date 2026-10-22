"""Narrow port through which the file tools reach workspace bytes (E264).

The tools must not own the path policy. Today each of them resolves a host path
and calls POSIX IO; under the managed execution route the same reads and writes
have to happen on the supervisor's admitted view, which supplies rooted
descriptor IO, byte bounds and an optimistic-concurrency write. This module is
the seam: a Protocol the tools depend on, the closed error vocabulary they map to
tool failures, and the one path normalizer both sides agree on.

It deliberately imports nothing from ``fa.execution``: the implementation lives
in ``fa.execution.tool_port`` and is injected at the composition root, so the
tool layer keeps no dependency on the execution subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

#: Upper bound for one full-file model read. It mirrors the substrate's own
#: single-read text bound (``fa.execution.protocol.MAX_TEXT_BYTES``); the adapter
#: refuses anything above it rather than truncating, and a larger file must be
#: read as a line window. ``tests/test_execution_tool_port.py`` asserts the two
#: values agree so the constant cannot drift away from the substrate.
PORT_READ_MAX_BYTES = 1024 * 1024


class WorkspacePortError(Exception):
    """A closed refusal from the workspace substrate.

    Codes are deliberately few and stable: the tool layer maps each one to a
    ``ToolResult`` failure, so a denial, a lost race and a size refusal are never
    indistinguishable to the model or to the operator. There is no separate
    "missing" code: the substrate does not disclose whether a path exists, so
    absence and refusal share ``denied``.
    """

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class PortRead:
    """One bounded read plus the digest that a later write must be based on."""

    content: str
    sha256: str
    eof: bool


@dataclass(frozen=True, slots=True)
class PortWrite:
    """One committed write as the substrate observed it."""

    sha256: str
    bytes: int


class WorkspacePort(Protocol):
    """The two operations the file tools need; nothing else is exposed."""

    def read_file(self, path: str, *, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead: ...

    def write_file(self, path: str, content: str, *, expected_sha256: str | None = None) -> PortWrite: ...


def port_relative(raw: object) -> str:
    """Normalize a model-supplied path to a view-relative POSIX path.

    Rejected before any IO: non-strings, empty strings, NUL bytes, backslashes
    (ambiguous separator on a POSIX-only deployment), absolute paths, empty or
    ``.`` segments and any ``..`` segment. What remains is exactly the form the
    substrate accepts, so path policy has one implementation rather than one per
    tool.
    """

    if not isinstance(raw, str) or raw == "" or "\x00" in raw or "\\" in raw:
        raise WorkspacePortError("invalid_request")
    if raw.startswith("/"):
        raise WorkspacePortError("invalid_request")
    parts = raw.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise WorkspacePortError("invalid_request")
    return "/".join(parts)


__all__ = [
    "PORT_READ_MAX_BYTES",
    "PortRead",
    "PortWrite",
    "WorkspacePort",
    "WorkspacePortError",
    "port_relative",
]
