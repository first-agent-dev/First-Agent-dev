"""Bounded descriptor-based inventory primitives for managed discovery calls.

This C0 component deliberately does not replace the legacy host walker. The
managed cell path can preflight a fixed workspace root with explicit Q97 limits
before asking a search or reach index to retain source or results.
"""

from __future__ import annotations

import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fa.memory._safe_walk import DEFAULT_PATTERNS, _matches_any_pattern, _path_is_excluded
from fa.memory.search_index import MAX_SEARCH_FILE_BYTES

MAX_MANAGED_WALK_ENTRIES = 8_192
MAX_MANAGED_WALK_DEPTH = 64
MAX_MANAGED_RELATIVE_PATH_BYTES = 512
MAX_MANAGED_CANDIDATES = 2_048
MAX_MANAGED_SOURCE_BYTES = 32 * 1024 * 1024
MAX_MANAGED_DEADLINE_MS = 25_000


class ManagedDiscoveryError(RuntimeError):
    """Stable, path-free refusal for a bounded managed inventory failure."""

    def __init__(
        self,
        reason: Literal[
            "deadline",
            "walk_budget",
            "depth_budget",
            "path_budget",
            "candidate_budget",
            "source_budget",
            "unsafe_path",
        ],
    ) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class ManagedDiscoveryLimits:
    """Per-call inventory ceilings; production callers use the Q97 defaults."""

    walk_entries: int = MAX_MANAGED_WALK_ENTRIES
    depth: int = MAX_MANAGED_WALK_DEPTH
    relative_path_bytes: int = MAX_MANAGED_RELATIVE_PATH_BYTES
    candidates: int = MAX_MANAGED_CANDIDATES
    source_bytes: int = MAX_MANAGED_SOURCE_BYTES
    per_file_bytes: int = MAX_SEARCH_FILE_BYTES

    def __post_init__(self) -> None:
        names = ("walk_entries", "depth", "relative_path_bytes", "candidates", "source_bytes", "per_file_bytes")
        for name in names:
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"invalid managed discovery limit: {name}")


@dataclass(frozen=True, slots=True)
class ManagedCandidate:
    """One bounded candidate and the stat identity observed during preflight."""

    relative_path: str
    size_bytes: int
    device: int
    inode: int
    mode: int
    mtime_ns: int
    ctime_ns: int
    oversized: bool


@dataclass(frozen=True, slots=True)
class ManagedInventory:
    """Complete inventory or refusal; partial instances are never returned."""

    entries: int
    candidates: tuple[ManagedCandidate, ...]
    eligible_source_bytes: int
    oversized_files: int


def _identity(info: os.stat_result) -> tuple[int, int, int]:
    return info.st_dev, info.st_ino, info.st_mode


def _check_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise ManagedDiscoveryError("deadline")


def _validate_patterns(patterns: tuple[str, ...]) -> None:
    if (
        type(patterns) is not tuple
        or not patterns
        or any(type(pattern) is not str or not pattern for pattern in patterns)
    ):
        raise ValueError("invalid managed discovery patterns")


class _InventoryBuilder:
    def __init__(
        self,
        *,
        root_device: int,
        flags: int,
        patterns: tuple[str, ...],
        extra_exclude_dirs: frozenset[str],
        deadline: float,
        limits: ManagedDiscoveryLimits,
    ) -> None:
        self.root_device = root_device
        self.flags = flags
        self.patterns = patterns
        self.extra_exclude_dirs = extra_exclude_dirs
        self.deadline = deadline
        self.limits = limits
        self.entries = 0
        self.source_bytes = 0
        self.oversized_files = 0
        self.candidates: list[ManagedCandidate] = []
        self.open_fds: set[int] = set()

    def _relative_path(self, parent: tuple[str, ...], name: str, depth: int) -> tuple[tuple[str, ...], str]:
        if type(name) is not str or name in {"", ".", ".."} or "/" in name or "\\" in name:
            raise ManagedDiscoveryError("unsafe_path")
        parts = (*parent, name)
        relative_path = "/".join(parts)
        try:
            encoded_bytes = len(relative_path.encode("utf-8"))
        except UnicodeError:
            raise ManagedDiscoveryError("path_budget") from None
        if encoded_bytes > self.limits.relative_path_bytes:
            raise ManagedDiscoveryError("path_budget")
        if depth > self.limits.depth:
            raise ManagedDiscoveryError("depth_budget")
        return parts, relative_path

    def _open_child_directory(self, directory_fd: int, name: str, info: os.stat_result) -> int:
        try:
            child_fd = os.open(name, self.flags, dir_fd=directory_fd)
            child_info = os.fstat(child_fd)
        except OSError:
            raise ManagedDiscoveryError("unsafe_path") from None
        if (
            not stat.S_ISDIR(child_info.st_mode)
            or child_info.st_dev != self.root_device
            or _identity(info) != _identity(child_info)
        ):
            os.close(child_fd)
            raise ManagedDiscoveryError("unsafe_path")
        self.open_fds.add(child_fd)
        return child_fd

    def _visit_entry(
        self,
        directory_fd: int,
        parent_parts: tuple[str, ...],
        parent_depth: int,
        entry: os.DirEntry[str],
    ) -> tuple[int, tuple[str, ...], int] | None:
        name = entry.name
        depth = parent_depth + 1
        parts, relative_path = self._relative_path(parent_parts, name, depth)
        try:
            info = entry.stat(follow_symlinks=False)
        except OSError:
            raise ManagedDiscoveryError("unsafe_path") from None
        if stat.S_ISLNK(info.st_mode) or _path_is_excluded(parts, self.extra_exclude_dirs):
            return None
        if stat.S_ISDIR(info.st_mode):
            return self._open_child_directory(directory_fd, name, info), parts, depth
        if not stat.S_ISREG(info.st_mode) or not _matches_any_pattern(relative_path, name, self.patterns):
            return None
        if len(self.candidates) >= self.limits.candidates:
            raise ManagedDiscoveryError("candidate_budget")
        oversized = info.st_size > self.limits.per_file_bytes
        if oversized:
            self.oversized_files += 1
        else:
            self.source_bytes += info.st_size
            if self.source_bytes > self.limits.source_bytes:
                raise ManagedDiscoveryError("source_budget")
        self.candidates.append(
            ManagedCandidate(
                relative_path,
                info.st_size,
                info.st_dev,
                info.st_ino,
                info.st_mode,
                info.st_mtime_ns,
                info.st_ctime_ns,
                oversized,
            )
        )
        return None

    def _scan_directory(
        self, directory_fd: int, parent_parts: tuple[str, ...], parent_depth: int
    ) -> list[tuple[int, tuple[str, ...], int]]:
        children: list[tuple[int, tuple[str, ...], int]] = []
        with os.scandir(directory_fd) as entries:
            for entry in entries:
                _check_deadline(self.deadline)
                self.entries += 1
                if self.entries > self.limits.walk_entries:
                    raise ManagedDiscoveryError("walk_budget")
                child = self._visit_entry(directory_fd, parent_parts, parent_depth, entry)
                if child is not None:
                    children.append(child)
        return children

    def walk(self, root_fd: int) -> ManagedInventory:
        self.open_fds.add(root_fd)
        pending: list[tuple[int, tuple[str, ...], int]] = [(root_fd, (), 0)]
        try:
            while pending:
                _check_deadline(self.deadline)
                directory_fd, parts, depth = pending.pop()
                try:
                    children = self._scan_directory(directory_fd, parts, depth)
                finally:
                    if directory_fd in self.open_fds:
                        self.open_fds.remove(directory_fd)
                        os.close(directory_fd)
                pending.extend(children)
            _check_deadline(self.deadline)
            self.candidates.sort(key=lambda candidate: candidate.relative_path)
            return ManagedInventory(self.entries, tuple(self.candidates), self.source_bytes, self.oversized_files)
        finally:
            self.close()

    def close(self) -> None:
        for descriptor in self.open_fds:
            try:
                os.close(descriptor)
            except OSError:
                pass
        self.open_fds.clear()


def inventory_managed_files(
    root: Path,
    *,
    patterns: tuple[str, ...] = DEFAULT_PATTERNS,
    extra_exclude_dirs: frozenset[str] = frozenset(),
    deadline: float,
    limits: ManagedDiscoveryLimits | None = None,
) -> ManagedInventory:
    """Walk one root with strict entry/depth/path/candidate/source bounds.

    Symlink entries are excluded rather than followed. Every traversed directory
    is opened descriptor-relative with ``O_NOFOLLOW`` and checked against the
    lstat identity observed from its parent. Candidate source reads remain a
    separate rooted-reader step, so callers must not retain partial results if
    a later rooted read disagrees with this preflight inventory.
    """
    if not isinstance(root, Path):
        raise ValueError("invalid managed discovery root")
    _validate_patterns(patterns)
    if type(extra_exclude_dirs) is not frozenset or any(type(name) is not str for name in extra_exclude_dirs):
        raise ValueError("invalid managed discovery exclusions")
    if type(deadline) not in {int, float} or deadline <= 0:
        raise ValueError("invalid managed discovery deadline")
    if limits is None:
        limits = ManagedDiscoveryLimits()
    if not isinstance(limits, ManagedDiscoveryLimits):
        raise ValueError("invalid managed discovery limits")
    _check_deadline(deadline)
    try:
        resolved = root.resolve(strict=True)
        before = resolved.stat(follow_symlinks=False)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        root_fd = os.open(resolved, flags)
        opened = os.fstat(root_fd)
    except (OSError, ValueError):
        raise ManagedDiscoveryError("unsafe_path") from None
    if not stat.S_ISDIR(opened.st_mode) or _identity(before) != _identity(opened):
        os.close(root_fd)
        raise ManagedDiscoveryError("unsafe_path")
    builder = _InventoryBuilder(
        root_device=opened.st_dev,
        flags=flags,
        patterns=patterns,
        extra_exclude_dirs=extra_exclude_dirs,
        deadline=deadline,
        limits=limits,
    )
    return builder.walk(root_fd)
