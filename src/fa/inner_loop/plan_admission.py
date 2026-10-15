"""Explicit-plan snapshots for retained I02; not an execution-isolation boundary.

Only the selected workspace is authoritative. A snapshot owns the bytes that
were read, not a promise that arbitrary shell/host writers cannot change them.
"""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from fa.inner_loop.plan_ids import PlanIds, extract_plan_ids

MAX_PLAN_BYTES = 1024 * 1024


class PlanRefError(ValueError):
    """Closed diagnostic reason; never expose input paths or exception bodies."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(f"invalid plan reference: {rule}")


@dataclass(frozen=True, slots=True)
class PlanRef:
    workspace_relative_path: str
    source_kind: str
    sha256: str


@dataclass(frozen=True, slots=True)
class PlanSnapshot:
    ref: PlanRef
    utf8_bytes: bytes
    text: str
    ids: PlanIds


def _require_plan_for_coder(roles: list[str], plan_path: Path | None) -> None:
    """Presence only; callers own read/evidence policy (CT90/95)."""
    if "coder" in roles and plan_path is None:
        raise PlanRefError("missing")


def _relative_plan_path(workspace: Path, plan_path: Path) -> tuple[Path, tuple[str, ...]]:
    try:
        root = workspace.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PlanRefError("unreadable") from exc
    path = plan_path
    if path.is_absolute():
        try:
            path = path.relative_to(root)
        except ValueError as exc:
            raise PlanRefError("path-escape") from exc
    parts = path.parts
    if any("\x00" in part for part in parts):
        raise PlanRefError("unreadable")
    # Path already normalizes empty/dot components; parent traversal remains.
    if not parts or ".." in parts:
        raise PlanRefError("path-escape")
    return root, parts


def _open_plan_component(parent_fd: int, name: str, *, directory: bool) -> int:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    if directory:
        flags |= os.O_DIRECTORY
    try:
        return os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        # Classification only: never authorize an open using this second stat.
        try:
            is_link = stat.S_ISLNK(os.stat(name, dir_fd=parent_fd, follow_symlinks=False).st_mode)
        except OSError:
            is_link = False
        if exc.errno == errno.ELOOP or is_link:
            raise PlanRefError("symlink") from exc
        raise PlanRefError("unreadable") from exc


def _read_plan_bytes(root: Path, parts: tuple[str, ...]) -> bytes:
    parent_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    file_fd: int | None = None
    try:
        for part in parts[:-1]:
            previous_fd = parent_fd
            parent_fd = _open_plan_component(parent_fd, part, directory=True)
            os.close(previous_fd)
        file_fd = _open_plan_component(parent_fd, parts[-1], directory=False)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            raise PlanRefError("not-regular")
        if before.st_size > MAX_PLAN_BYTES:
            raise PlanRefError("too-large")
        chunks: list[bytes] = []
        remaining = MAX_PLAN_BYTES + 1
        while remaining:
            chunk = os.read(file_fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > MAX_PLAN_BYTES:
            raise PlanRefError("too-large")
        after = os.fstat(file_fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise PlanRefError("source-changed")
        return raw
    finally:
        try:
            if file_fd is not None:
                os.close(file_fd)
        finally:
            os.close(parent_fd)


def read_plan_snapshot(workspace: Path, plan_path: Path) -> PlanSnapshot:
    """Read at most limit+1 bytes via no-follow descriptors, then parse once.

    Absolute public inputs are allowed only lexically inside the selected
    workspace. Stored identity is always normalized relative POSIX. Hard-link
    publication restrictions belong to promotion, not this read-only operation.
    """
    root, parts = _relative_plan_path(workspace, plan_path)
    try:
        raw = _read_plan_bytes(root, parts)
    except OSError as exc:
        raise PlanRefError("unreadable") from exc
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PlanRefError("invalid-utf8") from exc
    if not text.strip():
        raise PlanRefError("empty")
    return PlanSnapshot(
        ref=PlanRef(Path(*parts).as_posix(), "EXPLICIT", hashlib.sha256(raw).hexdigest()),
        utf8_bytes=raw,
        text=text,
        ids=extract_plan_ids(text),
    )
