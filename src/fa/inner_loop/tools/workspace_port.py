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

import atexit
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

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


PROJECT_ARTIFACT_KINDS = frozenset({"missing", "file", "directory", "symlink"})
PROJECT_ENTRY_KINDS = frozenset({"file", "directory", "symlink"})
PORT_PROJECT_LIST_MAX_ENTRIES = 64


@dataclass(frozen=True, slots=True)
class PortDirectoryEntry:
    """One immediate child name/type; never carries contents or link targets."""

    name: str
    kind: Literal["file", "directory", "symlink"]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or self.name in {"", ".", ".."}
            or "/" in self.name
            or "\\" in self.name
            or "\x00" in self.name
            or not isinstance(self.kind, str)
            or self.kind not in PROJECT_ENTRY_KINDS
        ):
            raise WorkspacePortError("invalid_request")
        try:
            name_bytes = self.name.encode("utf-8")
        except UnicodeError:
            raise WorkspacePortError("invalid_request") from None
        if len(name_bytes) > 255:
            raise WorkspacePortError("invalid_request")


@dataclass(frozen=True, slots=True)
class PortProjectArtifactListing:
    """Closed Q60 project metadata returned by one pinned-view operation."""

    project_kind: Literal["missing", "file", "directory", "symlink"]
    roadmap_kind: Literal["missing", "file", "directory", "symlink"]
    increments_kind: Literal["missing", "file", "directory", "symlink"]
    entries: tuple[PortDirectoryEntry, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.project_kind, str)
            or self.project_kind not in PROJECT_ARTIFACT_KINDS
            or not isinstance(self.roadmap_kind, str)
            or self.roadmap_kind not in PROJECT_ARTIFACT_KINDS
            or not isinstance(self.increments_kind, str)
            or self.increments_kind not in PROJECT_ARTIFACT_KINDS
            or type(self.entries) is not tuple
            or len(self.entries) > PORT_PROJECT_LIST_MAX_ENTRIES
            or any(not isinstance(entry, PortDirectoryEntry) for entry in self.entries)
            or tuple(entry.name for entry in self.entries) != tuple(sorted({entry.name for entry in self.entries}))
            or (
                self.project_kind != "directory"
                and (self.roadmap_kind != "missing" or self.increments_kind != "missing" or bool(self.entries))
            )
            or (self.increments_kind != "directory" and self.entries)
        ):
            raise WorkspacePortError("invalid_request")


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

    def list_project_artifacts(self, project_slug: str) -> PortProjectArtifactListing: ...

    def write_file(self, path: str, content: str, *, expected_sha256: str | None = None) -> PortWrite: ...


class CandidateWorkspacePort(Protocol):
    """The staged-candidate buffer of one CANDIDATE view; nothing else.

    Deliberately not a ``WorkspacePort``: the buffer is a purpose-bound operation
    on a READ view (E259), while ``WorkspacePort.write_file`` is general-purpose
    IO confined to ``Access.WRITE``. Keeping the two apart is what stops a READ
    view from acquiring a write path to arbitrary project files, and it is why
    this protocol has no ``read_file``/``list_project_artifacts``: a planner that
    needs ordinary source reads already has the stage's project port.

    The buffer's address is not an argument. Both implementations hold the label
    the view pinned (``CT120``), so a caller cannot widen its own authority by
    naming a path.
    """

    def write_candidate(self, content: str, *, expected_sha256: str | None = None) -> PortWrite: ...

    def read_candidate(self, *, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead: ...

    def candidate_label(self) -> str: ...


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


def _register_discovery_cleanup(cleanup: ExitStack | None, close: Callable[..., None], *, strict: bool = False) -> None:
    """Keep legacy shutdown best-effort; explicit tool scopes close indexes strictly."""
    if cleanup is None:
        atexit.register(close)
    elif strict:
        cleanup.callback(close, strict=True)
    else:
        cleanup.callback(close)


__all__ = [
    "PORT_PROJECT_LIST_MAX_ENTRIES",
    "PORT_READ_MAX_BYTES",
    "PROJECT_ARTIFACT_KINDS",
    "PROJECT_ENTRY_KINDS",
    "CandidateWorkspacePort",
    "PortDirectoryEntry",
    "PortProjectArtifactListing",
    "PortRead",
    "PortWrite",
    "WorkspacePort",
    "WorkspacePortError",
    "index_db",
    "port_relative",
]
