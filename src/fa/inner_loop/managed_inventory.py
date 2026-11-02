"""Bounded canonical artifact inventory over one already-authorized workspace view.

The controller supplies the view root; this module never resolves a host/user
path from model text. Directory enumeration is descriptor-relative and
no-follow. File bytes are read through the existing RootedFileReader so this
module does not introduce a second file-reading policy.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Literal

from fa.inner_loop.managed_acquisition import CanonicalIncrementArtifact, ProjectArtifactInventory, _valid_slug
from fa.memory._safe_walk import RootedFileReader, RootedReadError

__all__ = ["AcquisitionInventoryError", "inventory_project_artifacts"]

_MAX_ARTIFACT_BYTES = 1024 * 1024
_MAX_INCREMENT_FILES = 64
_MAX_INVENTORY_BYTES = 8 * 1024 * 1024
_CANONICAL_INCREMENT_NAME_RE = re.compile(r"increment-[0-9]{2,}-.+\.md\Z")


class AcquisitionInventoryError(ValueError):
    """Sanitized refusal for incomplete, unsafe, or oversized inventory reads."""

    def __init__(self, rule: Literal["unavailable", "unsafe-entry", "too-large", "too-many"]) -> None:
        self.rule = rule
        super().__init__(f"acquisition inventory unavailable: {rule}")


def _open_directory(parent_fd: int, name: str) -> int | None:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
    except FileNotFoundError:
        return None
    except OSError as error:
        raise AcquisitionInventoryError("unsafe-entry") from error
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise AcquisitionInventoryError("unsafe-entry")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _entry_identity(parent_fd: int, name: str) -> tuple[int, int, int, int, int, int, int]:
    try:
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as error:
        raise AcquisitionInventoryError("unavailable") from error
    if not stat.S_ISREG(info.st_mode):
        raise AcquisitionInventoryError("unsafe-entry")
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _assert_directory_binding(parent_fd: int, name: str, child_fd: int) -> None:
    try:
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        opened = os.fstat(child_fd)
    except OSError as error:
        raise AcquisitionInventoryError("unavailable") from error
    if (
        not stat.S_ISDIR(named.st_mode)
        or (named.st_dev, named.st_ino, named.st_mode) != (opened.st_dev, opened.st_ino, opened.st_mode)
    ):
        raise AcquisitionInventoryError("unsafe-entry")


def _read_canonical_file(reader: RootedFileReader, relative_path: str) -> bytes:
    try:
        canonical_path, content = reader.read_bytes_with_path(relative_path, max_bytes=_MAX_ARTIFACT_BYTES)
    except RootedReadError as error:
        rule: Literal["unavailable", "unsafe-entry", "too-large", "too-many"]
        if error.reason == "file_too_large":
            rule = "too-large"
        elif error.reason in {"symlink_escape", "path_changed", "invalid_path", "root_changed"}:
            rule = "unsafe-entry"
        else:
            rule = "unavailable"
        raise AcquisitionInventoryError(rule) from None
    if canonical_path != relative_path:
        raise AcquisitionInventoryError("unsafe-entry")
    return content


def _open_project_directories(
    root: Path, project_slug: str
) -> tuple[int, int, int, int | None] | None:
    try:
        before = root.stat(follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            raise AcquisitionInventoryError("unsafe-entry")
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except AcquisitionInventoryError:
        raise
    except OSError as error:
        raise AcquisitionInventoryError("unavailable") from error

    descriptors = [root_fd]
    try:
        opened = os.fstat(root_fd)
        if not stat.S_ISDIR(opened.st_mode) or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise AcquisitionInventoryError("unsafe-entry")
        worklogs_fd = _open_directory(root_fd, "worklogs")
        if worklogs_fd is None:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
            return None
        descriptors.append(worklogs_fd)
        project_fd = _open_directory(worklogs_fd, project_slug)
        if project_fd is None:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
            return None
        descriptors.append(project_fd)
        increments_fd = _open_directory(project_fd, "increments")
        if increments_fd is not None:
            descriptors.append(increments_fd)
        return root_fd, worklogs_fd, project_fd, increments_fd
    except BaseException:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise


def _canonical_increment_names(
    increments_fd: int | None,
) -> tuple[list[str], dict[str, tuple[int, int, int, int, int, int, int]]]:
    if increments_fd is None:
        return [], {}
    try:
        names = sorted(os.listdir(increments_fd))
    except OSError as error:
        raise AcquisitionInventoryError("unavailable") from error
    canonical_names = [name for name in names if _CANONICAL_INCREMENT_NAME_RE.fullmatch(name)]
    if len(canonical_names) > _MAX_INCREMENT_FILES:
        raise AcquisitionInventoryError("too-many")
    identities = {name: _entry_identity(increments_fd, name) for name in canonical_names}
    return canonical_names, identities


def _read_project_inventory(
    root: Path,
    project_slug: str,
    roadmap_identity: tuple[int, int, int, int, int, int, int],
    descriptors: tuple[int, int, int, int | None],
) -> ProjectArtifactInventory:
    root_fd, worklogs_fd, project_fd, increments_fd = descriptors
    canonical_names, increment_identities = _canonical_increment_names(increments_fd)
    roadmap_path = f"worklogs/{project_slug}/roadmap.md"
    with RootedFileReader(root) as reader:
        reader_root = reader.root.stat(follow_symlinks=False)
        root_identity = os.fstat(root_fd)
        if (reader_root.st_dev, reader_root.st_ino) != (root_identity.st_dev, root_identity.st_ino):
            raise AcquisitionInventoryError("unsafe-entry")
        roadmap_content = _read_canonical_file(reader, roadmap_path)
        if roadmap_identity != _entry_identity(project_fd, "roadmap.md"):
            raise AcquisitionInventoryError("unsafe-entry")
        total_bytes = len(roadmap_content)
        if total_bytes > _MAX_INVENTORY_BYTES:
            raise AcquisitionInventoryError("too-large")

        increments: list[CanonicalIncrementArtifact] = []
        for name in canonical_names:
            if increments_fd is None:
                raise AcquisitionInventoryError("unsafe-entry")
            relative_path = f"worklogs/{project_slug}/increments/{name}"
            content = _read_canonical_file(reader, relative_path)
            if increment_identities[name] != _entry_identity(increments_fd, name):
                raise AcquisitionInventoryError("unsafe-entry")
            total_bytes += len(content)
            if total_bytes > _MAX_INVENTORY_BYTES:
                raise AcquisitionInventoryError("too-large")
            increments.append(CanonicalIncrementArtifact(relative_path, content))

        if increments_fd is not None:
            current_names = sorted(os.listdir(increments_fd))
            current_canonical_names = [name for name in current_names if _CANONICAL_INCREMENT_NAME_RE.fullmatch(name)]
            if current_canonical_names != canonical_names:
                raise AcquisitionInventoryError("unsafe-entry")
            _assert_directory_binding(project_fd, "increments", increments_fd)
        _assert_directory_binding(root_fd, "worklogs", worklogs_fd)
        _assert_directory_binding(worklogs_fd, project_slug, project_fd)

    return ProjectArtifactInventory(roadmap_path, roadmap_content, tuple(increments))


def inventory_project_artifacts(workspace_view: Path, project_slug: str) -> ProjectArtifactInventory | None:
    """Read one selected project's roadmap and canonical increments fail-closed.

    ``workspace_view`` must be the current authorized view supplied by the
    trusted controller (not a path from the planner). ``None`` means that no
    canonical roadmap exists at the requested stable project slug; all other
    incomplete or unsafe reads raise one sanitized inventory error.
    """
    if not isinstance(workspace_view, Path) or not _valid_slug(project_slug):
        raise AcquisitionInventoryError("unsafe-entry")
    try:
        root = workspace_view.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise AcquisitionInventoryError("unavailable") from error
    opened = _open_project_directories(root, project_slug)
    if opened is None:
        return None
    root_fd, worklogs_fd, project_fd, increments_fd = opened
    descriptors = (root_fd, worklogs_fd, project_fd, increments_fd)
    try:
        try:
            roadmap_identity = _entry_identity(project_fd, "roadmap.md")
        except AcquisitionInventoryError as error:
            if isinstance(error.__cause__, FileNotFoundError):
                return None
            raise
        return _read_project_inventory(root, project_slug, roadmap_identity, descriptors)
    except AcquisitionInventoryError:
        raise
    except OSError as error:
        raise AcquisitionInventoryError("unavailable") from error
    finally:
        for descriptor in reversed([fd for fd in descriptors if fd is not None]):
            os.close(descriptor)
