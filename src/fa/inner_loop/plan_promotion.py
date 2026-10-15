"""Q58 candidate allocation and cooperative same-path publication, not OS isolation.

The controller validates a captured buffer before calling publication. A lock/CAS
serializes cooperating publishers; arbitrary host writers still require I03.
"""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from fa.inner_loop.plan_admission import (
    PlanRef,
    PlanRefError,
    PlanSnapshot,
    _decode_plan_bytes,
    _open_plan_component,
    _read_open_plan_bytes,
    read_plan_snapshot,
    snapshot_from_bytes,
)
from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
from fa.inner_loop.workflow_artifacts import AdmissionIOError, _admission_lock, _private_artifact_directory

_CANONICAL_PARENT = ("worklogs", "planning-topology-and-executable-contracts-loop", "increments")


class PlanPromotionError(ValueError):
    """Static closed reason and irreversible-boundary state; no paths or bodies."""

    def __init__(self, rule: str, *, replaced: bool = False) -> None:
        self.rule = rule
        self.replaced = replaced
        super().__init__(f"plan promotion failed: {rule}")


def _canonical_parts(snapshot: PlanSnapshot) -> tuple[str, ...]:
    parts = tuple(snapshot.ref.workspace_relative_path.split("/"))
    if len(parts) < 4 or parts[:3] != _CANONICAL_PARENT or any(p in {"", ".", ".."} or "\x00" in p for p in parts):
        raise PlanPromotionError("scope-denied")
    return parts


def _write_all(fd: int, raw: bytes) -> None:
    remaining = memoryview(raw)
    while remaining:
        written = os.write(fd, remaining)
        if written <= 0:
            raise OSError("short plan write")
        remaining = remaining[written:]


def seed_plan_candidate(
    workspace: Path,
    source: PlanSnapshot,
    *,
    run_id: str,
    kind: PlannerDispatchKind,
    draft: PlanSnapshot | None = None,
) -> PlannerDispatch:
    """Fresh no-clobber draft from exact captured bytes, never a second active plan."""
    _canonical_parts(source)  # Scope rejection must precede candidate allocation/provider.
    if kind == PlannerDispatchKind.ORDINARY_PLANNING:
        raise PlanPromotionError("scope-denied")
    target = f".fa/admission/{run_id}/candidate-{uuid4().hex}.md"
    dispatch = PlannerDispatch(kind, run_id, source.ref.workspace_relative_path, target)
    raw = source.utf8_bytes if draft is None else draft.utf8_bytes
    snapshot_from_bytes(target, raw)  # Strict UTF-8/nonempty/size; structural FAILs may seed.
    path = workspace / target
    try:
        with _private_artifact_directory(path.parent) as parent:
            _create_candidate(parent, path.name, raw)
    except OSError as error:
        raise PlanPromotionError("prepare-failed") from error
    return dispatch


def _create_candidate(parent: int, name: str, raw: bytes) -> None:
    created = False
    complete = False
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent)
        created = True
        try:
            _write_all(fd, raw)
            os.fchmod(fd, 0o600)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(parent)
        complete = True
    finally:
        if created and not complete:
            os.unlink(name, dir_fd=parent)


@contextmanager
def _canonical_parent(workspace: Path, parts: tuple[str, ...]) -> Generator[int]:
    # Unlike private artifact directories, canonical parents are never created/chmodded.
    fd = os.open(workspace.resolve(strict=True), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for part in parts[:-1]:
            previous = fd
            fd = _open_plan_component(fd, part, directory=True)
            os.close(previous)
        yield fd
    finally:
        os.close(fd)


def _checked_source(parent: int, name: str, expected: str) -> os.stat_result:
    fd = _open_plan_component(parent, name, directory=False)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise PlanPromotionError("not-regular")
        raw = _read_open_plan_bytes(fd)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise PlanPromotionError("source-changed")
        return metadata
    finally:
        os.close(fd)


def _source_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _stage_replacement(parent: int, name: str, raw: bytes, mode: int) -> None:
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent)
    try:
        try:
            _write_all(fd, raw)
            # Write first: writing can clear set-id mode bits on Linux.
            os.fchmod(fd, mode)
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        os.unlink(name, dir_fd=parent)
        raise


def _install_buffer(parent: int, name: str, source: PlanSnapshot, raw: bytes) -> int:
    metadata = _checked_source(parent, name, source.ref.sha256)
    temporary = f".{name}.{uuid4().hex}.tmp"
    created = False
    replaced = False
    phase = "prepare-failed"
    try:
        # Failed staging cleans only its exclusively-created sibling.
        _stage_replacement(parent, temporary, raw, stat.S_IMODE(metadata.st_mode))
        created = True
        current = _checked_source(parent, name, source.ref.sha256)
        if _source_identity(current) != _source_identity(metadata):
            raise PlanPromotionError("source-changed")
        phase = "replace-failed"
        os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
        replaced = True
        return stat.S_IMODE(metadata.st_mode)
    except OSError as error:
        raise PlanPromotionError(phase, replaced=replaced) from error
    finally:
        if created and not replaced:
            try:
                os.unlink(temporary, dir_fd=parent)
            except OSError as error:
                raise PlanPromotionError("prepare-failed") from error


def publish_plan_buffer(workspace: Path, source: PlanSnapshot, raw: bytes, *, deadline: float | None = None) -> PlanRef:
    """Install the controller-validated immutable buffer with lock/CAS and no rollback.

    Caller owns semantic admission. This IO layer independently enforces strict
    bytes, namespace, source identity and the irreversible failure boundary.
    """
    parts = _canonical_parts(source)
    _decode_plan_bytes(raw)
    expected_hash = hashlib.sha256(raw).hexdigest()
    lock_key = hashlib.sha256(source.ref.workspace_relative_path.encode("utf-8")).hexdigest()
    replaced = False
    try:
        with _private_artifact_directory(workspace / ".fa/admission/.locks" / lock_key) as lock_directory:
            with _admission_lock(lock_directory, deadline=deadline):
                with _canonical_parent(workspace, parts) as parent:
                    expected_mode = _install_buffer(parent, parts[-1], source, raw)
                    replaced = True
                    os.fsync(parent)
                    try:
                        metadata = _checked_source(parent, parts[-1], expected_hash)
                        if stat.S_IMODE(metadata.st_mode) != expected_mode:
                            raise PlanPromotionError("hash-mismatch", replaced=True)
                        promoted = read_plan_snapshot(workspace, Path(source.ref.workspace_relative_path))
                    except (OSError, ValueError) as error:
                        raise PlanPromotionError("hash-mismatch", replaced=True) from error
                    if promoted.ref.sha256 != expected_hash:
                        raise PlanPromotionError("hash-mismatch", replaced=True)
        return PlanRef(source.ref.workspace_relative_path, source.ref.source_kind, expected_hash)
    except PlanPromotionError:
        raise
    except PlanRefError as error:
        rule = error.rule if error.rule in {"symlink", "source-changed", "not-regular"} else "prepare-failed"
        raise PlanPromotionError(rule, replaced=replaced) from error
    except AdmissionIOError:
        if replaced:
            raise PlanPromotionError("durability-unknown", replaced=True) from None
        raise
    except OSError as error:
        raise PlanPromotionError("durability-unknown" if replaced else "prepare-failed", replaced=replaced) from error
