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
from pathlib import Path
from typing import Protocol

#: Upper bound for one full-file model read. It mirrors the substrate's own
#: single-read text bound (``fa.execution.protocol.MAX_TEXT_BYTES``); the adapter
#: refuses anything above it rather than truncating. An offset is available at
#: the port, but the file tool does not yet reconstruct large line windows.
#: ``tests/test_execution_tool_port.py`` asserts the two limits cannot drift.
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
    """The workspace view operations the tools need; nothing else is exposed.

    ``cache_dir`` is the view's own private scratch location. It exists because
    a tool that keeps an index (``fs_search``, ``fs_reach``) must not write that
    index into the tree it is searching: the tree is the artefact under
    validation, and a reader pinned to one revision must not have its answers
    depend on another view's writes. ``None`` means the composition supplied no
    private home, and the tools refuse rather than fall back to project bytes.
    """

    @property
    def cache_dir(self) -> Path | None: ...

    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead: ...

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


def index_db(port: WorkspacePort | None, root: Path, filename: str, fallback: Path) -> Path:
    """Where an index may live: the view's private cache, never project bytes.

    Without a port the caller keeps today's host-mode location (``fallback``).
    With a port the index must live in the view's cache home and must resolve
    outside the searched tree; anything else is a closed ``unavailable``
    refusal, so a misconfigured composition fails instead of silently writing
    into the view. One implementation of the rule, shared by both index tools.

    Resolution happens per call (not at build time) because the cache home is
    part of the view the composition binds, not of the tool definition.
    """

    if port is None:  # defensive: callers pass None for host mode
        return fallback
    cache = port.cache_dir
    if cache is None:
        raise WorkspacePortError("unavailable")
    candidate = Path(cache) / filename
    if candidate.resolve().is_relative_to(Path(root).resolve()):
        raise WorkspacePortError("unavailable")
    return candidate


__all__ = [
    "PORT_READ_MAX_BYTES",
    "PortRead",
    "PortWrite",
    "WorkspacePort",
    "WorkspacePortError",
    "index_db",
    "port_relative",
]
