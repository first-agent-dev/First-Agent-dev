"""Internal descriptor-rooted text IO, NOT workspace admission or immutable evidence.

Only the WorkspaceAuthority may select roots, access, profile and exclusions after
admission. Callers must retain that admission through close/drain. Shell writers
are not serialized by this object's lock; expected SHA is not kernel CAS.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import os
import re
import stat
import threading
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from types import TracebackType
from typing import Self, TypedDict, override
from uuid import uuid4

from fa.execution.protocol import MAX_TEXT_BYTES

_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
_BLOCKED_COMPONENTS = frozenset({".git", ".fa", ".venv", ".env"})
_LIBC = ctypes.CDLL(None, use_errno=True)
_RENAME_NOREPLACE = getattr(_LIBC, "renameat2", None)
if _RENAME_NOREPLACE is not None:
    _RENAME_NOREPLACE.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    _RENAME_NOREPLACE.restype = ctypes.c_int


class ViewIOError(ValueError):
    """Existing wire error code, with no caller paths/content in the message."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"view_io_failed:{code}")


class ReadResult(TypedDict):
    content: str
    sha256: str
    eof: bool


class WriteResult(TypedDict):
    sha256: str
    bytes: int


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _parts(path: str, max_depth: int) -> tuple[str, ...]:
    if not isinstance(path, str):
        raise ViewIOError("INVALID_REQUEST")
    try:
        length = len(path.encode("utf-8"))
    except UnicodeEncodeError:
        raise ViewIOError("INVALID_REQUEST") from None
    if length > MAX_TEXT_BYTES:
        raise ViewIOError("INPUT_POLICY")
    parts = tuple(path.split("/"))
    if any(p in {"", ".", ".."} or "\x00" in p for p in parts):
        raise ViewIOError("PATH_DENIED")
    if len(parts) > max_depth:
        raise ViewIOError("INPUT_POLICY")
    return parts


def _prefix(parent: tuple[str, ...], child: tuple[str, ...]) -> bool:
    return child[: len(parent)] == parent


def _rename_directory(source: int, name: str, destination: int, leaf: str) -> None:
    if _RENAME_NOREPLACE is None:
        raise OSError(errno.ENOSYS, "view_io_unavailable")
    if _RENAME_NOREPLACE(source, os.fsencode(name), destination, os.fsencode(leaf), 1) != 0:
        raise OSError(ctypes.get_errno(), "view_io_unavailable")


@dataclass(frozen=True)
class _Snapshot:
    metadata: os.stat_result
    raw: bytes
    sha256: str


@dataclass
class _Progress:
    changed: bool = False


@dataclass
class _Staged:
    name: str
    fd: int


class RootedViewIO(AbstractContextManager["RootedViewIO"]):
    """Own duplicated FDs; no API accepting canonical paths, grants or ViewRefs.

    `protected_paths` are write-protected (including their ancestors); exclusions
    are inaccessible for read and write. Supply both explicitly from trusted
    materialization/PlanRef policy. The root identity still needs authority-level
    registration checks. Neither this object nor writable=True authorizes a call.
    """

    def __init__(
        self,
        root_fd: int,
        staging_fd: int,
        *,
        uid: int,
        gid: int,
        writable: bool,
        protected_paths: tuple[str, ...],
        excluded_paths: tuple[str, ...],
        max_file_bytes: int = 64 * 1024 * 1024,
        max_depth: int = 64,
    ) -> None:
        if (
            type(uid) is not int
            or not 1 <= uid <= 2**32 - 2
            or type(gid) is not int
            or not 1 <= gid <= 2**32 - 2
            or type(writable) is not bool
            or type(max_file_bytes) is not int
            or max_file_bytes <= 0
            or type(max_depth) is not int
            or not 1 <= max_depth <= 64
            or type(protected_paths) is not tuple
            or type(excluded_paths) is not tuple
        ):
            raise ViewIOError("INVALID_REQUEST")
        self._uid, self._gid, self._writable = uid, gid, writable
        self._max_file_bytes, self._max_depth = max_file_bytes, max_depth
        self._protected = tuple(_parts(p, max_depth) for p in protected_paths)
        self._excluded = tuple(_parts(p, max_depth) for p in excluded_paths)
        self._lock = threading.RLock()
        self._root = self._staging = -1
        try:
            self._root = os.dup(root_fd)
            self._staging = os.dup(staging_fd)
            root, staging = os.fstat(self._root), os.fstat(self._staging)
            if (
                not stat.S_ISDIR(root.st_mode)
                or not stat.S_ISDIR(staging.st_mode)
                or not root.st_nlink
                or not staging.st_nlink
                or root.st_dev != staging.st_dev
                or staging.st_uid != os.getuid()
                or stat.S_IMODE(staging.st_mode) != 0o700
            ):
                raise ViewIOError("INPUT_POLICY")
            self._root_identity = _identity(root)
            # A staging FD below source would expose uninstalled data to the cell.
            self._check_staging_outside_root()
        except (OSError, ViewIOError) as error:
            self.close()
            if isinstance(error, OSError):
                raise ViewIOError("BACKEND_UNAVAILABLE") from None
            raise

    def _check_staging_outside_root(self) -> None:
        fd = os.dup(self._staging)
        try:
            for _ in range(1024):
                here = _identity(os.fstat(fd))
                if here == self._root_identity:
                    raise ViewIOError("INPUT_POLICY")
                parent = os.open("..", _DIRECTORY, dir_fd=fd)
                os.close(fd)
                fd = parent
                if _identity(os.fstat(fd)) == here:
                    return
            raise ViewIOError("INPUT_POLICY")
        finally:
            os.close(fd)

    @override
    def __enter__(self) -> Self:
        with self._lock:
            self._open()
        return self

    @override
    def __exit__(
        self, typ: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            for name in ("_root", "_staging"):
                fd = getattr(self, name)
                if fd != -1:
                    setattr(self, name, -1)
                    os.close(fd)

    def _open(self) -> None:
        if self._root == -1:
            raise ViewIOError("VIEW_CLOSED")
        if _identity(os.fstat(self._root)) != self._root_identity or not os.fstat(self._root).st_nlink:
            raise ViewIOError("STALE_REVISION")

    def _path(self, path: str, *, write: bool) -> tuple[str, ...]:
        parts = _parts(path, self._max_depth)
        if any(p in _BLOCKED_COMPONENTS for p in parts):
            raise ViewIOError("PATH_DENIED")
        if any(_prefix(p, parts) or (write and _prefix(parts, p)) for p in self._excluded):
            raise ViewIOError("PATH_DENIED")
        if write and (not self._writable or any(_prefix(p, parts) or _prefix(parts, p) for p in self._protected)):
            raise ViewIOError("PATH_DENIED")
        return parts

    def _new_parent(self, parent: int, leaf: str, progress: _Progress) -> int:
        name = f"io-dir-{uuid4().hex}"
        os.mkdir(name, 0o700, dir_fd=self._staging)
        fd = -1
        present = True
        try:
            fd = os.open(name, _DIRECTORY, dir_fd=self._staging)
            os.fchown(fd, self._uid, self._gid)
            os.fchmod(fd, 0o755)
            os.fsync(fd)
            try:
                _rename_directory(self._staging, name, parent, leaf)
            except FileExistsError:
                os.close(fd)
                fd = -1
                # Clean before opening the returned FD, even if cleanup fails.
                os.rmdir(name, dir_fd=self._staging)
                present = False
                # No-clobber: do not chmod/chown a concurrently supplied directory.
                return os.open(leaf, _DIRECTORY, dir_fd=parent)
            except OSError as error:
                if error.errno not in {errno.ENOSYS, errno.EOPNOTSUPP, errno.EXDEV}:
                    progress.changed = True
                    raise ViewIOError("DURABILITY_UNKNOWN") from None
                raise
            present = False
            progress.changed = True
            os.fsync(self._staging)
            os.fsync(parent)
            if _identity(os.stat(leaf, dir_fd=parent, follow_symlinks=False)) != _identity(os.fstat(fd)):
                raise ViewIOError("DURABILITY_UNKNOWN")
            result, fd = fd, -1
            return result
        finally:
            if fd != -1:
                os.close(fd)
            if present:
                try:
                    os.rmdir(name, dir_fd=self._staging)
                except FileNotFoundError:
                    pass  # An ambiguous rename may already have moved our entry.

    @contextmanager
    def _parents(self, parts: tuple[str, ...], *, create: bool, progress: _Progress) -> Generator[list[int]]:
        fds = [os.dup(self._root)]
        try:
            for part in parts[:-1]:
                try:
                    child = os.open(part, _DIRECTORY, dir_fd=fds[-1])
                except FileNotFoundError:
                    if not create:
                        raise
                    child = self._new_parent(fds[-1], part, progress)
                fds.append(child)
            yield fds
        finally:
            for fd in reversed(fds):
                os.close(fd)

    def _check_chain(self, parts: tuple[str, ...], fds: list[int], progress: _Progress) -> None:
        try:
            with self._parents(parts, create=False, progress=progress) as current:
                if any(_identity(os.fstat(a)) != _identity(os.fstat(b)) for a, b in zip(current, fds, strict=True)):
                    raise ViewIOError("STALE_REVISION")
        except (OSError, ViewIOError):
            raise ViewIOError("DURABILITY_UNKNOWN" if progress.changed else "STALE_REVISION") from None

    def _snapshot(self, parent: int, leaf: str) -> _Snapshot:
        fd = os.open(leaf, _FILE, dir_fd=parent)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_mode & 0o7000:
                raise ViewIOError("PATH_DENIED")
            if before.st_size > self._max_file_bytes:
                raise ViewIOError("INPUT_POLICY")
            raw = bytearray()
            while True:
                chunk = os.read(fd, min(128 * 1024, self._max_file_bytes - len(raw) + 1))
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > self._max_file_bytes:
                    raise ViewIOError("INPUT_POLICY")
            after = os.fstat(fd)
            try:
                named = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                raise ViewIOError("STALE_REVISION") from None
            if (
                _fingerprint(before) != _fingerprint(after)
                or len(raw) != after.st_size
                or _fingerprint(after) != _fingerprint(named)
            ):
                raise ViewIOError("STALE_REVISION")
            captured = bytes(raw)
            return _Snapshot(after, captured, hashlib.sha256(captured).hexdigest())
        finally:
            os.close(fd)

    @staticmethod
    def _os_error(error: OSError, progress: _Progress) -> ViewIOError:
        if progress.changed:
            return ViewIOError("DURABILITY_UNKNOWN")
        if error.errno in {
            errno.ELOOP,
            errno.ENOTDIR,
            errno.EISDIR,
            errno.EACCES,
            errno.EPERM,
            errno.ENOENT,
            errno.ENAMETOOLONG,
            errno.ENXIO,
            errno.ENODEV,
        }:
            return ViewIOError("PATH_DENIED")
        return ViewIOError("BACKEND_UNAVAILABLE")

    def read_file(self, path: str, *, offset_bytes: int, max_bytes: int) -> ReadResult:
        with self._lock:
            progress = _Progress()
            try:
                self._open()
                parts = self._path(path, write=False)
                if (
                    type(offset_bytes) is not int
                    or offset_bytes < 0
                    or type(max_bytes) is not int
                    or not 1 <= max_bytes <= MAX_TEXT_BYTES
                ):
                    raise ViewIOError("INVALID_REQUEST")
                with self._parents(parts, create=False, progress=progress) as fds:
                    snapshot = self._snapshot(fds[-1], parts[-1])
                    self._check_chain(parts, fds, progress)
                try:
                    if b"\x00" in snapshot.raw:
                        raise UnicodeError
                    snapshot.raw.decode("utf-8")
                    content = snapshot.raw[offset_bytes : offset_bytes + max_bytes].decode("utf-8")
                except UnicodeError:
                    raise ViewIOError("INPUT_POLICY") from None
                return {
                    "content": content,
                    "sha256": snapshot.sha256,
                    "eof": offset_bytes + max_bytes >= len(snapshot.raw),
                }
            except OSError as error:
                raise self._os_error(error, progress) from None

    @contextmanager
    def _stage_file(self, raw: bytes, mode: int) -> Generator[_Staged]:
        name = f"io-file-{uuid4().hex}"
        fd = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self._staging
        )
        staged = _Staged(name, fd)
        try:
            remaining = memoryview(raw)
            while remaining:
                written = os.write(fd, remaining)
                if written <= 0:
                    raise OSError(errno.EIO, "view_io_unavailable")
                remaining = remaining[written:]
            os.fchown(fd, self._uid, self._gid)
            os.fchmod(fd, mode)
            os.fsync(fd)
            yield staged
        finally:
            os.close(fd)
            try:
                os.unlink(name, dir_fd=self._staging)
            except FileNotFoundError:
                pass  # Rename may have consumed it; never trust a publication flag for cleanup.

    def _target(self, parent: int, leaf: str, expected: str | None) -> _Snapshot | None:
        try:
            old = self._snapshot(parent, leaf)
        except FileNotFoundError:
            if expected is not None:
                raise ViewIOError("STALE_REVISION") from None
            return None
        if expected is None or old.sha256 != expected:
            raise ViewIOError("STALE_REVISION")
        if old.metadata.st_uid != self._uid or old.metadata.st_gid != self._gid:
            raise ViewIOError("PATH_DENIED")
        return old

    # §rooted-view-publication: publish only staged owned bytes through pinned parent FDs.
    def write_file(self, path: str, content: str, *, expected_sha256: str | None) -> WriteResult:
        with self._lock:
            progress = _Progress()
            try:
                self._open()
                parts = self._path(path, write=True)
                if not isinstance(content, str) or (
                    expected_sha256 is not None
                    and (not isinstance(expected_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None)
                ):
                    raise ViewIOError("INVALID_REQUEST")
                try:
                    raw = content.encode("utf-8")
                except UnicodeEncodeError:
                    raise ViewIOError("INVALID_REQUEST") from None
                if b"\x00" in raw or len(raw) > MAX_TEXT_BYTES:
                    raise ViewIOError("INVALID_REQUEST")
                if len(raw) > self._max_file_bytes:
                    raise ViewIOError("INPUT_POLICY")
                with self._parents(parts, create=expected_sha256 is None, progress=progress) as fds:
                    parent, leaf = fds[-1], parts[-1]
                    old = self._target(parent, leaf, expected_sha256)
                    mode = 0o644 if old is None else stat.S_IMODE(old.metadata.st_mode)
                    with self._stage_file(raw, mode) as staged:
                        self._check_chain(parts, fds, progress)
                        current = self._target(parent, leaf, expected_sha256)
                        if old is not None and (
                            current is None or _fingerprint(current.metadata) != _fingerprint(old.metadata)
                        ):
                            raise ViewIOError("STALE_REVISION")
                        try:
                            if old is None:
                                os.link(
                                    staged.name,
                                    leaf,
                                    src_dir_fd=self._staging,
                                    dst_dir_fd=parent,
                                    follow_symlinks=False,
                                )
                                progress.changed = True
                                os.unlink(staged.name, dir_fd=self._staging)
                            else:
                                os.replace(staged.name, leaf, src_dir_fd=self._staging, dst_dir_fd=parent)
                                progress.changed = True
                        except FileExistsError:
                            raise ViewIOError("STALE_REVISION") from None
                        except OSError:
                            progress.changed = True
                            raise ViewIOError("DURABILITY_UNKNOWN") from None
                        os.fsync(self._staging)
                        os.fsync(parent)
                        self._check_chain(parts, fds, progress)
                        try:
                            installed = self._snapshot(parent, leaf)
                            if (
                                _identity(installed.metadata) != _identity(os.fstat(staged.fd))
                                or installed.sha256 != hashlib.sha256(raw).hexdigest()
                                or stat.S_IMODE(installed.metadata.st_mode) != mode
                                or installed.metadata.st_uid != self._uid
                                or installed.metadata.st_gid != self._gid
                            ):
                                raise ViewIOError("DURABILITY_UNKNOWN")
                        except (OSError, ViewIOError):
                            raise ViewIOError("DURABILITY_UNKNOWN") from None
                        self._check_chain(parts, fds, progress)
                        return {"sha256": installed.sha256, "bytes": len(raw)}
            except FileNotFoundError as error:
                if expected_sha256 is not None and not progress.changed:
                    raise ViewIOError("STALE_REVISION") from None
                raise self._os_error(error, progress) from None
            except OSError as error:
                raise self._os_error(error, progress) from None
