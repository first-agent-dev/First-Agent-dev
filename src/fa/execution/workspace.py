"""Protected existing-workspace registration, R0 retention and exclusive writer.

The actual owner, not a wire service or a temporary admission callback. New-root
installation, pins/views/admission, backend drain and publication are subsequent
construction steps. No factory is activated here. Legacy writers must already be
quiesced by deployment; metadata/hash checks are not a kernel snapshot/CAS.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import math
import os
import secrets
import shutil
import stat
import threading
import time
from collections.abc import Callable, Generator, Mapping
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import TracebackType
from typing import Any, Self, override
from uuid import uuid4

import fastjsonschema  # type: ignore[import-untyped]  # Existing schema library has no typing metadata.

from fa.execution.journal import JournalError, OperationJournal
from fa.execution.profiles import _configured_id
from fa.execution.protocol import (
    NAMESPACE,
    SHA,
    _check,
    _enum,
    _id,
    _nonfinite,
    _nullable,
    _object,
    _pairs,
    encode_json,
)
from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import ExecutionContractError, GrantReply, NamespaceRef, Operation, _hex_id, validate_capability
from fa.execution.view_io import _DIRECTORY, _FILE, ViewIOError, _fingerprint, _identity, _parts, _rename_directory
from fa.inner_loop.workflow_artifacts import _private_artifact_directory, _replace_private_bytes

_UINT = {"type": "integer", "minimum": 0}
_WORKSPACE = fastjsonschema.compile(
    _object(
        schema_version={"type": "integer", "const": 1},
        workspace_id=_id("ws-"),
        root_id={"type": "string"},
        relative_root={"type": "string"},
        root_dev=_UINT,
        root_ino=_UINT,
        generation=_UINT,
        owner_namespace=_nullable(NAMESPACE),
        active_actor=_nullable(NAMESPACE),
        status=_enum("AVAILABLE", "OWNED", "QUARANTINED"),
    )
)
_CURRENT = fastjsonschema.compile(
    _object(
        schema_version={"type": "integer", "const": 1},
        revision_id=_id("rev-"),
        tree_sha256=SHA,
    )
)
_ENTRY = _object(
    path={"type": "string"},
    type=_enum("file", "directory", "symlink"),
    mode={"type": "integer", "minimum": 0, "maximum": 511},
    size=_UINT,
    sha256=_nullable(SHA),
    deleted={"type": "boolean", "const": False},
    link_target=_nullable({"type": "string"}),
)
_TREE = fastjsonschema.compile(
    _object(
        schema_version={"type": "integer", "const": 1},
        revision_id=_id("rev-"),
        tree_sha256=SHA,
        entries={"type": "array", "items": _ENTRY},
    )
)


def _budget(deadline: float) -> None:
    if type(deadline) not in {int, float} or not math.isfinite(deadline):
        raise ExecutionContractError
    if deadline <= time.monotonic():
        raise SupervisorError("BACKEND_UNAVAILABLE")


def _open_absolute(path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts or path == Path("/"):
        raise ExecutionContractError
    fd = os.open("/", _DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, _DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _mount_path(raw: str) -> PurePosixPath:
    # proc mountinfo escapes whitespace and backslash with these octal sequences.
    for source, target in (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\")):
        raw = raw.replace(source, target)
    return PurePosixPath(raw)


def _mount_id(fd: int) -> str:
    info = Path(f"/proc/self/fdinfo/{fd}").read_text()
    return next(line.split()[1] for line in info.splitlines() if line.startswith("mnt_id:"))


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _location(fd: int, path: Path) -> tuple[int, PurePosixPath]:
    """Kernel mount root + mount-relative path exposes bind-mounted aliases.

    Comparing inode/ordinary '..' alone misses a bind of a registered subtree.
    These proc inputs are from the supervisor's own Linux mount namespace, not
    caller data. Missing/inconsistent facts are unsupported, never path fallback.
    """
    mount_id = _mount_id(fd)
    with Path("/proc/self/mountinfo").open() as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise SupervisorError("BACKEND_UNAVAILABLE")
    for line in raw.splitlines():
        parts = line.split()
        if parts[0] == mount_id:
            filesystem_root, mountpoint = _mount_path(parts[3]), _mount_path(parts[4])
            relative = PurePosixPath(str(path)).relative_to(mountpoint)
            return os.fstat(fd).st_dev, filesystem_root / relative
    raise SupervisorError("BACKEND_UNAVAILABLE")


def _overlap(left: tuple[int, PurePosixPath], right: tuple[int, PurePosixPath]) -> bool:
    return left[0] == right[0] and (left[1].is_relative_to(right[1]) or right[1].is_relative_to(left[1]))


def _private(fd: int, *, directory: bool = True) -> None:
    info = os.fstat(fd)
    kind = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1
    if not kind or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise SupervisorError("CORRUPT_STATE")


def _read_json(fd: int, name: str, validator: Callable[..., Any], limit: int) -> dict[str, Any]:
    source = os.open(name, _FILE, dir_fd=fd)
    try:
        _private(source, directory=False)
        before = os.fstat(source)
        if before.st_size > limit:
            raise SupervisorError("CORRUPT_STATE")
        data = bytearray()
        while len(data) <= limit:
            chunk = os.read(source, min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > limit or _fingerprint(before) != _fingerprint(os.fstat(source)):
            raise SupervisorError("CORRUPT_STATE")
        value = json.loads(bytes(data).decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_nonfinite)
        if not isinstance(value, dict):
            raise ExecutionContractError
        _check(validator, value)
        return value
    except (ExecutionContractError, ValueError, UnicodeError, RecursionError):
        raise SupervisorError("CORRUPT_STATE") from None
    finally:
        os.close(source)


def _write_all(fd: int, raw: bytes) -> None:
    left = memoryview(raw)
    while left:
        count = os.write(fd, left)
        if count <= 0:
            raise OSError("workspace_short_write")
        left = left[count:]


@dataclass(frozen=True)
class InputLimits:
    max_entries: int = 100_000
    max_total_bytes: int = 2 * 1024**3
    max_file_bytes: int = 64 * 1024**2
    max_depth: int = 64
    max_manifest_bytes: int = 64 * 1024**2

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in vars(self).values()) or self.max_depth > 64:
            raise ExecutionContractError


@dataclass
class _Capture:
    limits: InputLimits
    exclusions: tuple[tuple[str, ...], ...]
    deadline: float
    entries: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    discovered: int = 0

    def _excluded(self, parts: tuple[str, ...]) -> bool:
        return bool(set(parts) & {".git", ".fa", ".venv", ".env"}) or any(parts[: len(p)] == p for p in self.exclusions)

    def walk(self, source: int, destination: int | None, prefix: tuple[str, ...] = ()) -> None:
        before = os.fstat(source)
        names = self._names(source, prefix)
        for name in sorted(names):
            _budget(self.deadline)
            parts = (*prefix, name)
            if self._excluded(parts):
                continue
            try:
                name.encode("utf-8")
            except UnicodeError:
                raise SupervisorError("INPUT_POLICY") from None
            if len(parts) > self.limits.max_depth:
                raise SupervisorError("INPUT_POLICY")
            info = os.stat(name, dir_fd=source, follow_symlinks=False)
            if info.st_mode & 0o7000:
                raise SupervisorError("INPUT_POLICY")
            entry: dict[str, Any] = {
                "path": "/".join(parts),
                "mode": stat.S_IMODE(info.st_mode),
                "size": 0,
                "sha256": None,
                "deleted": False,
                "link_target": None,
            }
            self.entries.append(entry)
            if stat.S_ISDIR(info.st_mode):
                entry["type"] = "directory"
                self._directory(source, destination, name, parts)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                entry["type"] = "file"
                entry.update(self._file(source, destination, name, info))
            elif stat.S_ISLNK(info.st_mode) and info.st_nlink == 1:
                target = os.readlink(name, dir_fd=source)
                try:
                    raw = target.encode("utf-8")
                except UnicodeError:
                    raise SupervisorError("INPUT_POLICY") from None
                self.total += len(raw)
                entry.update(type="symlink", size=len(raw), sha256=hashlib.sha256(raw).hexdigest(), link_target=target)
                if destination is not None:
                    os.symlink(target, name, dir_fd=destination)
            else:
                raise SupervisorError("INPUT_POLICY")
            if self.total > self.limits.max_total_bytes or _fingerprint(info) != _fingerprint(
                os.stat(name, dir_fd=source, follow_symlinks=False)
            ):
                raise SupervisorError("INPUT_POLICY")
        if _fingerprint(before) != _fingerprint(os.fstat(source)):
            raise SupervisorError("STALE_REVISION")
        if destination is not None:
            os.fsync(destination)

    def _names(self, source: int, prefix: tuple[str, ...]) -> list[str]:
        names = []
        with os.scandir(source) as scan:
            for child in scan:
                _budget(self.deadline)
                if self._excluded((*prefix, child.name)):
                    continue
                self.discovered += 1
                if self.discovered > self.limits.max_entries:
                    raise SupervisorError("INPUT_POLICY")
                names.append(child.name)
        return names

    def _directory(self, source: int, destination: int | None, name: str, parts: tuple[str, ...]) -> None:
        child = os.open(name, _DIRECTORY, dir_fd=source)
        target = None
        try:
            if _mount_id(child) != _mount_id(source):
                raise SupervisorError("INPUT_POLICY")
            if destination is not None:
                os.mkdir(name, 0o700, dir_fd=destination)
                target = os.open(name, _DIRECTORY, dir_fd=destination)
            self.walk(child, target, parts)
        finally:
            os.close(child)
            if target is not None:
                os.close(target)

    def _file(self, source: int, destination: int | None, name: str, expected: os.stat_result) -> dict[str, Any]:
        fd = os.open(name, _FILE, dir_fd=source)
        target = None
        count = 0
        digest = hashlib.sha256()
        try:
            if _mount_id(fd) != _mount_id(source):
                raise SupervisorError("INPUT_POLICY")
            if _fingerprint(expected) != _fingerprint(os.fstat(fd)) or expected.st_size > self.limits.max_file_bytes:
                raise SupervisorError("INPUT_POLICY")
            if destination is not None:
                target = os.open(
                    name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=destination
                )
            while True:
                _budget(self.deadline)
                raw = os.read(fd, min(65536, self.limits.max_file_bytes + 1 - count))
                if not raw:
                    break
                count += len(raw)
                self.total += len(raw)
                if count > self.limits.max_file_bytes or self.total > self.limits.max_total_bytes:
                    raise SupervisorError("INPUT_POLICY")
                digest.update(raw)
                if target is not None:
                    _write_all(target, raw)
            if count != expected.st_size or _fingerprint(expected) != _fingerprint(os.fstat(fd)):
                raise SupervisorError("STALE_REVISION")
            if target is not None:
                os.fsync(target)
            return {"size": count, "sha256": digest.hexdigest()}
        finally:
            os.close(fd)
            if target is not None:
                os.close(target)

    def finish(self) -> tuple[list[dict[str, Any]], str]:
        self.entries.sort(key=lambda entry: entry["path"])
        entries = {entry["path"]: entry for entry in self.entries}
        for entry in self.entries:
            if entry["type"] == "symlink":
                self._link(entry["path"], entry["link_target"], entries)
        raw = _canonical(self.entries)
        if len(raw) > self.limits.max_manifest_bytes:
            raise SupervisorError("INPUT_POLICY")
        return self.entries, hashlib.sha256(raw).hexdigest()

    def _link(self, path: str, target: str, entries: dict[str, dict[str, Any]]) -> None:
        if PurePosixPath(target).is_absolute():
            raise SupervisorError("INPUT_POLICY")
        pending = list(PurePosixPath(path).parent.parts) + target.split("/")
        resolved: list[str] = []
        seen: set[str] = set()
        while pending:
            _budget(self.deadline)
            part = pending.pop(0)
            if part in {"", "."}:
                if part == "" and not resolved:
                    raise SupervisorError("INPUT_POLICY")
                continue
            if part == "..":
                if not resolved:
                    raise SupervisorError("INPUT_POLICY")
                resolved.pop()
                continue
            resolved.append(part)
            key = "/".join(resolved)
            if self._excluded(tuple(resolved)):
                raise SupervisorError("INPUT_POLICY")
            found = entries.get(key)
            if found is not None and found["type"] == "symlink":
                if key in seen or PurePosixPath(found["link_target"]).is_absolute():
                    raise SupervisorError("INPUT_POLICY")
                seen.add(key)
                resolved.pop()
                pending = found["link_target"].split("/") + pending


@dataclass(repr=False)
class _Binding:
    metadata: dict[str, Any]
    current: dict[str, Any]
    fd: int
    source: int
    path: Path
    location: tuple[int, PurePosixPath]
    writer: int | None = None
    grant: str | None = None
    principal: str | None = None

    def close_writer(self) -> None:
        self.grant = None
        self.principal = None
        if self.writer is not None:
            os.close(self.writer)
            self.writer = None

    def close(self) -> None:
        self.close_writer()
        os.close(self.fd)
        os.close(self.source)


class WorkspaceAuthority(AbstractContextManager["WorkspaceAuthority"]):
    """Own the existing operation journal and its startup guard for the lifetime.

    Only existing-root registration/acquisition/unused-owner release are exposed
    in this construction step. There is no permit for a command or writable view
    until the subsequent real view/admission/backend join is implemented.
    """

    def __init__(
        self,
        state_root: Path,
        *,
        approved_roots: Mapping[str, Path],
        controller_uids: frozenset[int],
        lock_timeout_ms: int,
        limits: InputLimits | None = None,
        excluded_paths: tuple[str, ...] = (),
    ) -> None:
        if not approved_roots or not controller_uids or any(type(uid) is not int or uid < 0 for uid in controller_uids):
            raise ExecutionContractError
        self._state = state_root
        self._roots = dict(approved_roots)
        for root_id, path in self._roots.items():
            _configured_id(root_id)
            if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts or path == Path("/"):
                raise ExecutionContractError
            if state_root.is_relative_to(path) or path.is_relative_to(state_root):
                raise ExecutionContractError
        self.journal = OperationJournal(state_root / "operations", lock_timeout_ms=lock_timeout_ms)
        self._uids, self._limits = controller_uids, limits if limits is not None else InputLimits()
        self._excluded = tuple(_parts(path, self._limits.max_depth) for path in excluded_paths)
        self._stack = ExitStack()
        self._mutex = threading.RLock()
        self._bindings: dict[str, _Binding] = {}
        self._root_fds: dict[str, int] = {}
        self._catalog = -1
        self._healthy = False
        self._entered = False

    @override
    def __enter__(self) -> Self:
        if self._entered:
            raise SupervisorError("VIEW_CLOSED")
        self._entered = True
        try:
            self._stack.enter_context(self.journal.single_supervisor())
            state_fd = self._stack.enter_context(_private_artifact_directory(self._state))
            for name in ("workspaces", "pending"):
                try:
                    os.mkdir(name, 0o700, dir_fd=state_fd)
                    os.fsync(state_fd)
                except FileExistsError:
                    pass
            self._catalog = os.open("workspaces", _DIRECTORY, dir_fd=state_fd)
            self._stack.callback(os.close, self._catalog)
            _private(self._catalog)
            for root_id, path in self._roots.items():
                fd = _open_absolute(path)
                self._stack.callback(os.close, fd)
                self._root_fds[root_id] = fd
                if _overlap(_location(fd, path), _location(state_fd, self._state)):
                    raise SupervisorError("PATH_DENIED")
            self.journal.recover_uncertain()
            self._load()
            self._healthy = True
            return self
        except (OSError, JournalError, SupervisorError, ExecutionContractError, ValueError, StopIteration):
            self._stack.close()
            raise SupervisorError("CORRUPT_STATE") from None

    @override
    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        with self._mutex:
            self._healthy = False
            self._stack.close()

    def _check(self, peer: PeerIdentity, deadline: float) -> None:
        _budget(deadline)
        if not self._healthy:
            raise SupervisorError("CORRUPT_STATE")
        if peer.uid not in self._uids:
            raise SupervisorError("UNAUTHORIZED")

    @contextmanager
    def _transaction(self, peer: PeerIdentity, deadline: float) -> Generator[None]:
        _budget(deadline)
        if not self._mutex.acquire(timeout=max(0, deadline - time.monotonic())):
            raise SupervisorError("BACKEND_UNAVAILABLE")
        try:
            self._check(peer, deadline)
            yield
        finally:
            self._mutex.release()

    def _select(self, root_id: str, relative_root: str) -> tuple[int, Path]:
        if root_id not in self._root_fds:
            raise SupervisorError("PATH_DENIED")
        try:
            parts = _parts(relative_root, self._limits.max_depth)
        except ViewIOError as error:
            raise SupervisorError(error.code) from None
        root_path = self._roots[root_id]
        check = _open_absolute(root_path)
        try:
            if _identity(os.fstat(check)) != _identity(os.fstat(self._root_fds[root_id])):
                raise SupervisorError("CORRUPT_STATE")
            for part in parts:
                previous = check
                check = os.open(part, _DIRECTORY, dir_fd=previous)
                os.close(previous)
                if _mount_id(check) != _mount_id(self._root_fds[root_id]):
                    raise SupervisorError("PATH_DENIED")
            return check, root_path.joinpath(*parts)
        except BaseException:
            os.close(check)
            raise

    def _recheck(self, binding: _Binding) -> None:
        fd, path = self._select(binding.metadata["root_id"], binding.metadata["relative_root"])
        try:
            if (
                _identity(os.fstat(fd)) != (binding.metadata["root_dev"], binding.metadata["root_ino"])
                or _location(fd, path) != binding.location
            ):
                raise SupervisorError("CORRUPT_STATE")
        finally:
            os.close(fd)

    def _snapshot(self, source: int, destination: int | None, deadline: float) -> tuple[list[dict[str, Any]], str]:
        capture = _Capture(self._limits, self._excluded, deadline)
        capture.walk(source, destination)
        return capture.finish()

    def _load(self) -> None:
        for workspace_id in sorted(os.listdir(self._catalog)):
            _hex_id(workspace_id, "ws-")
            fd = os.open(workspace_id, _DIRECTORY, dir_fd=self._catalog)
            self._stack.callback(os.close, fd)
            _private(fd)
            metadata = _read_json(fd, "workspace.json", _WORKSPACE, 1024**2)
            available = metadata["status"] == "AVAILABLE"
            if metadata["workspace_id"] != workspace_id or any(
                (metadata[key] is None) != available for key in ("owner_namespace", "active_actor")
            ):
                raise SupervisorError("CORRUPT_STATE")
            current = _read_json(fd, "current.json", _CURRENT, 1024**2)
            source, path = self._select(metadata["root_id"], metadata["relative_root"])
            self._stack.callback(os.close, source)
            binding = _Binding(metadata, current, fd, source, path, _location(source, path))
            self._recheck(binding)
            self._disjoint(binding)
            self._verify_revision(binding, time.monotonic() + 120)
            if metadata["status"] == "OWNED":
                metadata["status"] = "QUARANTINED"
                _replace_private_bytes(fd, "workspace.json", encode_json(metadata))
            self._stack.callback(binding.close_writer)
            self._bindings[workspace_id] = binding

    def _disjoint(self, candidate: _Binding) -> None:
        for binding in self._bindings.values():
            self._recheck(binding)
            if _identity(os.fstat(candidate.source)) == _identity(os.fstat(binding.source)) or _overlap(
                candidate.location, binding.location
            ):
                raise SupervisorError("PATH_DENIED")

    def _verify_revision(self, binding: _Binding, deadline: float) -> None:
        fd = os.open("revisions", _DIRECTORY, dir_fd=binding.fd)
        try:
            child = os.open(binding.current["revision_id"], _DIRECTORY, dir_fd=fd)
        finally:
            os.close(fd)
        try:
            _private(child)
            tree = _read_json(child, "tree.json", _TREE, self._limits.max_manifest_bytes)
            if (
                tree["revision_id"] != binding.current["revision_id"]
                or tree["tree_sha256"] != binding.current["tree_sha256"]
                or hashlib.sha256(_canonical(tree["entries"])).hexdigest() != tree["tree_sha256"]
            ):
                raise SupervisorError("CORRUPT_STATE")
            data = os.open("data", _DIRECTORY, dir_fd=child)
            try:
                actual, _ = self._snapshot(data, None, deadline)
            finally:
                os.close(data)
            if len(actual) != len(tree["entries"]):
                raise SupervisorError("CORRUPT_STATE")
            for got, wanted in zip(actual, tree["entries"], strict=True):
                got["mode"] = wanted["mode"]  # Private retention modes differ from logical source modes.
                if got != wanted:
                    raise SupervisorError("CORRUPT_STATE")
        finally:
            os.close(child)

    def register_existing(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, root_id: str, relative_root: str, deadline: float
    ) -> dict[str, str]:
        """Register quiescent existing bytes, never create/chmod a canonical root."""
        if not isinstance(namespace, NamespaceRef):
            raise ExecutionContractError
        with self._transaction(peer, deadline):
            source = -1
            try:
                source, path = self._select(root_id, relative_root)
                for binding in self._bindings.values():
                    if binding.metadata["root_id"] == root_id and binding.metadata["relative_root"] == relative_root:
                        self._recheck(binding)
                        self._unchanged(binding, deadline)
                        return {
                            "workspace_id": binding.metadata["workspace_id"],
                            "revision_id": binding.current["revision_id"],
                        }
                metadata = {
                    "schema_version": 1,
                    "workspace_id": "ws-" + uuid4().hex,
                    "root_id": root_id,
                    "relative_root": relative_root,
                    "root_dev": os.fstat(source).st_dev,
                    "root_ino": os.fstat(source).st_ino,
                    "generation": 0,
                    "owner_namespace": None,
                    "active_actor": None,
                    "status": "AVAILABLE",
                }
                provisional = _Binding(metadata, {}, -1, source, path, _location(source, path))
                self._disjoint(provisional)
                result = self._register(provisional, deadline)
                source = -1  # The installed binding owns it now.
                return result
            except OSError:
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None
            finally:
                if source != -1:
                    os.close(source)

    def _register(self, binding: _Binding, deadline: float) -> dict[str, str]:
        workspace_id, revision_id = binding.metadata["workspace_id"], "rev-" + uuid4().hex
        stage = self._state / "pending" / uuid4().hex
        installed = False
        try:
            with _private_artifact_directory(stage) as fd:
                os.mkdir("revisions", 0o700, dir_fd=fd)
                revisions = os.open("revisions", _DIRECTORY, dir_fd=fd)
                try:
                    os.mkdir(revision_id, 0o700, dir_fd=revisions)
                    revision = os.open(revision_id, _DIRECTORY, dir_fd=revisions)
                    try:
                        os.mkdir("data", 0o700, dir_fd=revision)
                        data = os.open("data", _DIRECTORY, dir_fd=revision)
                        try:
                            entries, digest = self._snapshot(binding.source, data, deadline)
                        finally:
                            os.close(data)
                        tree = {
                            "schema_version": 1,
                            "revision_id": revision_id,
                            "tree_sha256": digest,
                            "entries": entries,
                        }
                        raw = _canonical(tree)
                        if len(raw) > self._limits.max_manifest_bytes:
                            raise SupervisorError("INPUT_POLICY")
                        _replace_private_bytes(revision, "tree.json", raw)
                    finally:
                        os.close(revision)
                    os.fsync(revisions)
                finally:
                    os.close(revisions)
                binding.current = {"schema_version": 1, "revision_id": revision_id, "tree_sha256": digest}
                _replace_private_bytes(fd, "current.json", encode_json(binding.current))
                _replace_private_bytes(fd, "workspace.json", encode_json(binding.metadata))
                os.mkdir("views", 0o700, dir_fd=fd)
                os.fsync(fd)
                self._recheck(binding)
                _budget(deadline)
                parent = os.open(stage.parent, _DIRECTORY)
                try:
                    _rename_directory(parent, stage.name, self._catalog, workspace_id)
                    installed = True
                    os.fsync(parent)
                    os.fsync(self._catalog)
                finally:
                    os.close(parent)
            binding.fd = os.open(workspace_id, _DIRECTORY, dir_fd=self._catalog)
            self._stack.callback(binding.close)
            self._bindings[workspace_id] = binding
            return {"workspace_id": workspace_id, "revision_id": revision_id}
        finally:
            if not installed and stage.exists():
                shutil.rmtree(stage)  # Only this uninstalled, service-private staging tree.

    def _unchanged(self, binding: _Binding, deadline: float) -> None:
        self._recheck(binding)
        self._verify_revision(binding, deadline)
        _, digest = self._snapshot(binding.source, None, deadline)
        if digest != binding.current["tree_sha256"]:
            self._healthy = False
            raise SupervisorError("CORRUPT_STATE")
        self._recheck(binding)

    def _binding(self, workspace_id: str) -> _Binding:
        _hex_id(workspace_id, "ws-")
        binding = self._bindings.get(workspace_id)
        if binding is None:
            raise SupervisorError("UNAUTHORIZED")
        return binding

    def acquire_writer(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, workspace_id: str, deadline: float
    ) -> GrantReply:
        if not isinstance(namespace, NamespaceRef):
            raise ExecutionContractError
        with self._transaction(peer, deadline):
            binding = self._binding(workspace_id)
            if binding.metadata["status"] != "AVAILABLE":
                raise SupervisorError("WORKSPACE_BUSY")
            try:
                self._unchanged(binding, deadline)
                writer = os.open(
                    "writer.lock",
                    os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                    0o600,
                    dir_fd=binding.fd,
                )
                try:
                    _private(writer, directory=False)
                    fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    _budget(deadline)
                    generation = binding.metadata["generation"] + 1
                    self._claim_generation(binding, namespace)
                    stored = _read_json(binding.fd, "workspace.json", _WORKSPACE, 1024**2)
                    if stored != binding.metadata or stored["generation"] != generation or stored["status"] != "OWNED":
                        self._healthy = False
                        raise SupervisorError("DURABILITY_UNKNOWN")
                    _budget(deadline)
                except BaseException:
                    os.close(writer)
                    raise
                binding.writer = writer
                binding.grant = secrets.token_hex(32)
                binding.principal = peer.principal
                return GrantReply(
                    Operation.ACQUIRE_WRITER,
                    binding.grant,
                    None,
                    binding.metadata["generation"],
                    binding.current["revision_id"],
                )
            except BlockingIOError:
                raise SupervisorError("WORKSPACE_BUSY") from None
            except OSError:
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None

    @staticmethod
    def _claim_generation(binding: _Binding, namespace: NamespaceRef) -> None:
        binding.metadata.update(
            generation=binding.metadata["generation"] + 1,
            owner_namespace=namespace.to_dict(),
            active_actor=namespace.to_dict(),
            status="OWNED",
        )
        _replace_private_bytes(binding.fd, "workspace.json", encode_json(binding.metadata))

    def release_unused_writer(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, workspace_id: str, capability: str, deadline: float
    ) -> dict[str, bool]:
        validate_capability(capability)
        with self._transaction(peer, deadline):
            binding = self._binding(workspace_id)
            if (
                binding.metadata["status"] != "OWNED"
                or binding.principal != peer.principal
                or binding.metadata["active_actor"] != namespace.to_dict()
                or binding.grant is None
                or not hmac.compare_digest(binding.grant, capability)
            ):
                raise SupervisorError("UNAUTHORIZED")
            try:
                self._recheck(binding)
                views = os.open("views", _DIRECTORY, dir_fd=binding.fd)
                try:
                    if os.listdir(views) or "intent.json" in os.listdir(binding.fd):
                        raise SupervisorError("WORKSPACE_BUSY")
                finally:
                    os.close(views)
                binding.metadata.update(owner_namespace=None, active_actor=None, status="AVAILABLE")
                _replace_private_bytes(binding.fd, "workspace.json", encode_json(binding.metadata))
                if binding.writer is not None:
                    os.close(binding.writer)
                    binding.writer = None
                binding.grant = None
                binding.principal = None
                return {"released": True}
            except OSError:
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None
