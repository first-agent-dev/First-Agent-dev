"""Protected existing-workspace registration, R0 retention and exclusive writer.

The actual owner, not a wire service or a temporary admission callback. New-root
installation, backend drain and publication are subsequent
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
import re
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
from fa.execution.plans import ProtectedPlanContext
from fa.execution.profiles import ExecutionProfile, _configured_id
from fa.execution.protocol import (
    CANDIDATE_SCOPE,
    MAX_TEXT_BYTES,
    NAMESPACE,
    PLAN_REF,
    SHA,
    VIEW,
    _check,
    _enum,
    _id,
    _nonfinite,
    _nullable,
    _object,
    _pairs,
    decode_request,
    encode_json,
)
from fa.execution.supervisor import PeerIdentity, SupervisorError, operation_input_sha256
from fa.execution.types import (
    Access,
    ExecutionContractError,
    GrantReply,
    NamespaceRef,
    Operation,
    ViewPurpose,
    ViewRef,
    _hex_id,
    validate_capability,
)
from fa.execution.view_io import (
    _DIRECTORY,
    _FILE,
    ReadResult,
    RootedViewIO,
    ViewIOError,
    WriteResult,
    _fingerprint,
    _identity,
    _parts,
    _rename_directory,
)
from fa.inner_loop.plan_admission import PlanRef
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

_VIEW_RECORD = fastjsonschema.compile(
    _object(
        schema_version={"type": "integer", "const": 1},
        view_ref=VIEW,
        actor_namespace=NAMESPACE,
        state=_enum("OPEN", "STOPPING", "SEALED", "PUBLISHED", "REJECTED", "UNKNOWN"),
        input_tree_sha256=SHA,
        sealed_manifest_id=_nullable(_id("manifest-")),
        operation_ids={"type": "array", "items": _id("op-")},
        candidate_scope=_nullable(CANDIDATE_SCOPE),
        plan_ref=_nullable(PLAN_REF),
    )
)

# E259: the closed create_view matrix. One row per approved purpose; every
# other (purpose, access, plan, scope) combination is INPUT_POLICY before any
# filesystem effect. The authority revalidates independently of the codec.
_PURPOSE_MATRIX: dict[ViewPurpose, tuple[Access, bool, bool]] = {
    ViewPurpose.PROJECT: (Access.WRITE, False, False),
    ViewPurpose.VERIFICATION: (Access.READ, True, False),
    ViewPurpose.MUTATION: (Access.WRITE, True, False),
    ViewPurpose.CANDIDATE: (Access.READ, True, True),
    ViewPurpose.PROVISIONING: (Access.WRITE, False, False),
}
# The approved mutation roots (slice_verification._MUTATION_ROOTS): a MUTATION
# view's rooted writes are confined to these top-level trees. The single-target
# discipline is completed by the controller's expected_sha one-file edit.
_MUTATION_ROOTS = frozenset({"src", "scripts"})


def _plan_ref_dict(plan_ref: PlanRef) -> dict[str, str]:
    return {
        "workspace_relative_path": plan_ref.workspace_relative_path,
        "source_kind": plan_ref.source_kind,
        "sha256": plan_ref.sha256,
    }


def _candidate_scope(
    purpose: ViewPurpose,
    access: Access,
    candidate_scope: Mapping[str, Any] | None,
    plan_ref: PlanRef | None,
) -> dict[str, Any] | None:
    """Revalidate the create_view matrix; deny every other combination."""
    if not isinstance(purpose, ViewPurpose) or not isinstance(access, Access):
        raise ExecutionContractError
    expected_access, plan_required, scope_required = _PURPOSE_MATRIX[purpose]
    if (
        access is not expected_access
        or (plan_required and plan_ref is None)
        or (scope_required != (candidate_scope is not None))
    ):
        raise SupervisorError("INPUT_POLICY")
    if not scope_required:
        return None
    if not isinstance(candidate_scope, Mapping) or set(candidate_scope) != {"candidate_path", "plan_ref"}:
        raise ExecutionContractError
    if not isinstance(plan_ref, PlanRef) or not isinstance(candidate_scope["plan_ref"], Mapping):
        raise ExecutionContractError
    # Path semantics (relative, no traversal/NUL) are enforced once at the
    # record layer (protocol._byte_limits inside _check(_VIEW_RECORD)); this
    # matrix owns only the combination rules, never a second path parser.
    scope = {
        "candidate_path": candidate_scope["candidate_path"],
        "plan_ref": dict(candidate_scope["plan_ref"]),
    }
    if scope["plan_ref"] != _plan_ref_dict(plan_ref):
        raise SupervisorError("INPUT_POLICY")
    return scope


@dataclass(repr=False)
class _ReaderPin:
    ref: ViewRef
    namespace: NamespaceRef
    principal: str
    capability: str | None
    record: dict[str, Any]
    source: int
    directory: int
    manifest: tuple[int, ...]
    entries: dict[str, dict[str, Any]]
    context: ProtectedPlanContext

    def close(self) -> None:
        self.capability = None
        self.entries.clear()
        for name in ("source", "directory"):
            fd = getattr(self, name)
            if fd >= 0:
                setattr(self, name, -1)
                os.close(fd)


@dataclass(repr=False)
class _ProjectView:
    ref: ViewRef
    namespace: NamespaceRef
    principal: str
    capability: str | None
    record: dict[str, Any]
    source: int
    directory: int
    context: ProtectedPlanContext

    def close(self) -> None:
        self.capability = None
        for name in ("source", "directory"):
            fd = getattr(self, name)
            if fd >= 0:
                setattr(self, name, -1)
                os.close(fd)


@dataclass
class _WorkGate:
    active: set[object] = field(default_factory=set)
    closed: bool = False


@dataclass(repr=False)
class _ExecutionInputs:
    source: Path
    scratch: Path
    cache: Path
    source_fd: int
    scratch_fd: int
    cache_fd: int
    context: ProtectedPlanContext
    sealed_sha256: str | None = None
    projection: Path | None = None

    def close(self) -> None:
        for name in ("source_fd", "scratch_fd", "cache_fd"):
            fd = getattr(self, name)
            if fd >= 0:
                setattr(self, name, -1)
                os.close(fd)


@dataclass(repr=False)
class WorkAdmission(AbstractContextManager["WorkAdmission"]):
    """Actual authority-owned bounded DISPATCH scope, never a terminal receipt.

    Hold through queue/create/start/send, end BEFORE waiting for command output.
    Create/start use effect() plus journal's own once guards; RUN frame writes
    use send(). Close/drain may win between legs. Neither scope wraps reply wait.
    """

    _owner: WorkspaceAuthority
    _peer: PeerIdentity
    _namespace: NamespaceRef
    _ref: ViewRef
    _capability: str
    _request: dict[str, Any]
    deadline: float
    profile: ExecutionProfile
    inputs: _ExecutionInputs
    input_tree_sha256: str
    _work: object
    _closed: bool = False

    @override
    def __enter__(self) -> Self:
        if self._closed:
            raise SupervisorError("VIEW_CLOSED")
        return self

    @override
    def __exit__(
        self, _exc_type: type[BaseException] | None, _exc_value: BaseException | None, _traceback: TracebackType | None
    ) -> None:
        self.close()

    def close(self) -> None:
        with self._owner._mutex:
            if not self._closed:
                self._closed = True
                self._owner._gates[self._ref.view_id].active.discard(self._work)
                self._owner._drained.notify_all()

    @contextmanager
    def effect(self) -> Generator[Self]:
        with self._owner._transaction(self._peer, self.deadline):
            if self._closed or self._owner._gate(self._ref).closed:
                raise SupervisorError("VIEW_CLOSED")
            self._owner._live_view(self._peer, self._namespace, self._ref, self._capability)
            self._owner._execution_claim(
                self._request, self._namespace, self._ref, deadline=self.deadline, continuing=True
            )
            self._owner._validate_inputs(self._ref, self.inputs, self.deadline)
            _budget(self.deadline)
            yield self

    @contextmanager
    def send(self) -> Generator[Self]:
        """RUN frame write only. Never wrap WorkerClient's response wait here."""
        with self.effect():
            digest = operation_input_sha256(Operation.EXEC, self._namespace, self._ref, self._request["payload"])
            try:
                with self._owner.journal.send_guard(
                    self._request["payload"]["operation_id"],
                    self._namespace,
                    view=self._ref,
                    input_sha256=digest,
                    deadline=self.deadline,
                ):
                    _budget(self.deadline)
                    yield self
            except JournalError as error:
                if error.code in {"DURABILITY_UNKNOWN", "CORRUPT_STATE"}:
                    self._owner._healthy = False
                raise SupervisorError(error.code) from None


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

    Existing-root ownership, immutable readers and WRITE/PROJECT working views
    with rooted file IO and scoped dispatch admission are exposed. No candidate/provisioning
    view or backend terminality follows from this construction step.
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
        view_profile: ExecutionProfile | None = None,
        approved_cache: Path | None = None,
    ) -> None:
        if not approved_roots or not controller_uids or any(type(uid) is not int or uid < 0 for uid in controller_uids):
            raise ExecutionContractError
        if view_profile is not None and (
            not isinstance(view_profile, ExecutionProfile) or max(view_profile.uid, view_profile.gid) > 2**32 - 2
        ):
            raise ExecutionContractError
        if approved_cache is not None and (
            not isinstance(approved_cache, Path)
            or not approved_cache.is_absolute()
            or ".." in approved_cache.parts
            or approved_cache == Path("/")
            or approved_cache.is_relative_to(state_root)
            or state_root.is_relative_to(approved_cache)
            or any(
                approved_cache.is_relative_to(root) or root.is_relative_to(approved_cache)
                for root in approved_roots.values()
            )
        ):
            raise ExecutionContractError
        self._approved_cache = approved_cache
        self._view_profile = view_profile
        self._readers: dict[str, _ReaderPin] = {}
        self._projects: dict[str, _ProjectView] = {}
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
        self._drained = threading.Condition(self._mutex)
        self._gates: dict[str, _WorkGate] = {}
        self._inputs: dict[str, _ExecutionInputs] = {}
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
        self, _exc_type: type[BaseException] | None, _exc_value: BaseException | None, _traceback: TracebackType | None
    ) -> None:
        with self._mutex:
            self._healthy = False
            for gate in self._gates.values():
                gate.closed = True
            while any(gate.active for gate in self._gates.values()):
                self._drained.wait()
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
            self._initialize_genesis(binding)
            if metadata["status"] == "OWNED":
                metadata["status"] = "QUARANTINED"
                _replace_private_bytes(fd, "workspace.json", encode_json(metadata))
            self._stack.callback(binding.close_writer)
            self._bindings[workspace_id] = binding

    @staticmethod
    def _initialize_genesis(binding: _Binding) -> None:
        """Initialize legacy unowned genesis, never recover or renew ownership."""
        if binding.metadata["generation"] != 0:
            return
        if binding.metadata["status"] != "AVAILABLE" or any(
            binding.metadata[key] is not None for key in ("owner_namespace", "active_actor")
        ):
            raise SupervisorError("CORRUPT_STATE")
        views = os.open("views", _DIRECTORY, dir_fd=binding.fd)
        try:
            _private(views)
            if os.listdir(views) or "intent.json" in os.listdir(binding.fd):
                raise SupervisorError("CORRUPT_STATE")
        finally:
            os.close(views)
        writer = os.open(
            "writer.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            0o600,
            dir_fd=binding.fd,
        )
        try:
            _private(writer, directory=False)
            fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if _read_json(binding.fd, "workspace.json", _WORKSPACE, 1024**2) != binding.metadata:
                raise SupervisorError("CORRUPT_STATE")
            initialized = {**binding.metadata, "generation": 1}
            _replace_private_bytes(binding.fd, "workspace.json", encode_json(initialized))
            if _read_json(binding.fd, "workspace.json", _WORKSPACE, 1024**2) != initialized:
                raise SupervisorError("CORRUPT_STATE")
            binding.metadata.update(initialized)
        finally:
            os.close(writer)

    def _disjoint(self, candidate: _Binding) -> None:
        for binding in self._bindings.values():
            self._recheck(binding)
            if _identity(os.fstat(candidate.source)) == _identity(os.fstat(binding.source)) or _overlap(
                candidate.location, binding.location
            ):
                raise SupervisorError("PATH_DENIED")

    @contextmanager
    def _revision(
        self, binding: _Binding, revision_id: str, deadline: float
    ) -> Generator[tuple[int, dict[str, Any], int]]:
        _hex_id(revision_id, "rev-")
        fd = os.open("revisions", _DIRECTORY, dir_fd=binding.fd)
        try:
            try:
                child = os.open(revision_id, _DIRECTORY, dir_fd=fd)
            except FileNotFoundError:
                raise SupervisorError("STALE_REVISION") from None
        finally:
            os.close(fd)
        try:
            _private(child)
            tree = _read_json(child, "tree.json", _TREE, self._limits.max_manifest_bytes)
            if (
                tree["revision_id"] != revision_id
                or hashlib.sha256(_canonical(tree["entries"])).hexdigest() != tree["tree_sha256"]
            ):
                raise SupervisorError("CORRUPT_STATE")
            data = os.open("data", _DIRECTORY, dir_fd=child)
            try:
                actual, _ = self._snapshot(data, None, deadline)
                if len(actual) != len(tree["entries"]):
                    raise SupervisorError("CORRUPT_STATE")
                for got, wanted in zip(actual, tree["entries"], strict=True):
                    got["mode"] = wanted["mode"]  # Retention modes differ from logical input modes.
                    if got != wanted:
                        raise SupervisorError("CORRUPT_STATE")
                yield data, tree, child
            finally:
                os.close(data)
        finally:
            os.close(child)

    def _verify_revision(self, binding: _Binding, deadline: float) -> None:
        try:
            with self._revision(binding, binding.current["revision_id"], deadline) as (_, tree, _):
                if tree["tree_sha256"] != binding.current["tree_sha256"]:
                    raise SupervisorError("CORRUPT_STATE")
        except SupervisorError as error:
            if error.code == "STALE_REVISION":
                raise SupervisorError("CORRUPT_STATE") from None
            raise

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
                    "generation": 1,
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
                    if self._has_writer_views(binding, views) or "intent.json" in os.listdir(binding.fd):
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

    @staticmethod
    def _has_writer_views(binding: _Binding, views: int) -> bool:
        for name in os.listdir(views):
            # Unknown scratch is not safe unused-owner settlement.
            if len(name) != 37 or not name.startswith("view-"):
                return True
            child = os.open(name, _DIRECTORY, dir_fd=views)
            try:
                _private(child)
                record = _read_json(child, "view.json", _VIEW_RECORD, 1024**2)
                ref = record["view_ref"]
                if ref["workspace_id"] != binding.metadata["workspace_id"] or ref["view_id"] != name:
                    raise SupervisorError("CORRUPT_STATE")
                if ref["access"] != Access.READ.value:
                    return True
            finally:
                os.close(child)
        return False

    def pin_reader(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        workspace_id: str,
        revision_id: str,
        plan_ref: PlanRef | None,
        formal_evidence: bool,
        deadline: float,
    ) -> GrantReply:
        """Private trusted policy inputs; no execution admission or writer authority."""
        if not isinstance(namespace, NamespaceRef) or type(formal_evidence) is not bool:
            raise ExecutionContractError
        with self._transaction(peer, deadline):
            if self._view_profile is None:
                raise SupervisorError("UNAPPROVED_PROFILE")
            binding = self._binding(workspace_id)
            self._recheck(binding)
            try:
                with self._revision(binding, revision_id, deadline) as (data, tree, revision):
                    context = ProtectedPlanContext(
                        self._state / "workspaces" / workspace_id / "revisions" / revision_id / "data",
                        plan_ref,
                        formal_evidence,
                    )
                    context.recheck()
                    ref = ViewRef(
                        workspace_id,
                        "view-" + uuid4().hex,
                        revision_id,
                        namespace.run_id,
                        binding.metadata["generation"],
                        Access.READ,
                        ViewPurpose.PROJECT,
                    )
                    grant = GrantReply(Operation.PIN_READER, secrets.token_hex(32), ref, None, None)
                    record = {
                        "schema_version": 1,
                        "view_ref": ref.to_dict(),
                        "actor_namespace": namespace.to_dict(),
                        "state": "OPEN",
                        "input_tree_sha256": tree["tree_sha256"],
                        "sealed_manifest_id": None,
                        "operation_ids": [],
                        "candidate_scope": None,
                        "plan_ref": context.to_plan_ref(),
                    }
                    _check(_VIEW_RECORD, record)
                    if grant.capability in _canonical(record).decode("utf-8"):
                        raise ExecutionContractError
                    self._register_reader_view(
                        binding, namespace, peer, ref, grant, record, data, tree, revision, context, deadline
                    )
                    return grant
            except ExecutionContractError:
                raise SupervisorError("INPUT_POLICY") from None
            except OSError:
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None

    def _retain_reader(self, binding: _Binding, record: dict[str, Any], deadline: float) -> int:
        stage = self._state / "pending" / uuid4().hex
        installed = False
        try:
            with _private_artifact_directory(stage) as fd, ExitStack() as stack:
                _replace_private_bytes(fd, "view.json", encode_json(record))
                views = os.open("views", _DIRECTORY, dir_fd=binding.fd)
                stack.callback(os.close, views)
                _private(views)
                parent = os.open(stage.parent, _DIRECTORY)
                stack.callback(os.close, parent)
                view_id = record["view_ref"]["view_id"]
                _budget(deadline)
                _rename_directory(parent, stage.name, views, view_id)
                installed = True
                os.fsync(parent)
                os.fsync(views)
                result = os.open(view_id, _DIRECTORY, dir_fd=views)
                try:
                    _private(result)
                    if _read_json(result, "view.json", _VIEW_RECORD, 1024**2) != record:
                        self._healthy = False
                        raise SupervisorError("DURABILITY_UNKNOWN")
                except BaseException:
                    self._healthy = False
                    os.close(result)
                    raise
                return result
        finally:
            if not installed and stage.exists():
                shutil.rmtree(stage)  # Only this uninstalled service-private record.

    def _register_reader_view(
        self,
        binding: _Binding,
        namespace: NamespaceRef,
        peer: PeerIdentity,
        ref: ViewRef,
        grant: GrantReply,
        record: dict[str, Any],
        data: int,
        tree: dict[str, Any],
        revision: int,
        context: ProtectedPlanContext,
        deadline: float,
    ) -> _ReaderPin:
        """The one reader-view registration path (pin_reader and create_view)."""
        source = os.dup(data)
        directory = -1
        try:
            _budget(deadline)
            directory = self._retain_reader(binding, record, deadline)
            _budget(deadline)
            pin = _ReaderPin(
                ref,
                namespace,
                peer.principal,
                grant.capability,
                record,
                source,
                directory,
                _fingerprint(os.stat("tree.json", dir_fd=revision, follow_symlinks=False)),
                {e["path"]: e for e in tree["entries"]},
                context,
            )
            self._readers[ref.view_id] = pin
            self._stack.callback(pin.close)
        except BaseException:
            os.close(source)
            if directory >= 0:
                os.close(directory)
            raise
        return pin

    def _create_read_view(
        self,
        binding: _Binding,
        workspace_id: str,
        capability: str,
        namespace: NamespaceRef,
        peer: PeerIdentity,
        purpose: ViewPurpose,
        scope: dict[str, Any] | None,
        plan_ref: PlanRef | None,
        formal_evidence: bool,
        deadline: float,
    ) -> GrantReply:
        """VERIFICATION/CANDIDATE: one immutable reader view of the CURRENT revision.

        The E257 admitted execution path already materializes a sealed read-only
        source projection plus private scratch for reader views at admission, so
        these purposes gain no second materialization mechanism.
        """
        try:
            self._unchanged(binding, deadline)
            with self._revision(binding, binding.current["revision_id"], deadline) as (data, tree, revision):
                context = ProtectedPlanContext(
                    self._state / "workspaces" / workspace_id / "revisions" / tree["revision_id"] / "data",
                    plan_ref,
                    formal_evidence,
                )
                context.recheck()
                if context.to_plan_ref() is None:  # The matrix requires a real plan for these purposes.
                    raise SupervisorError("INPUT_POLICY")
                ref = ViewRef(
                    workspace_id,
                    "view-" + uuid4().hex,
                    tree["revision_id"],
                    namespace.run_id,
                    binding.metadata["generation"],
                    Access.READ,
                    purpose,
                )
                grant = GrantReply(Operation.CREATE_VIEW, secrets.token_hex(32), ref, None, None)
                record = {
                    "schema_version": 1,
                    "view_ref": ref.to_dict(),
                    "actor_namespace": namespace.to_dict(),
                    "state": "OPEN",
                    "input_tree_sha256": tree["tree_sha256"],
                    "sealed_manifest_id": None,
                    "operation_ids": [],
                    "candidate_scope": scope,
                    "plan_ref": context.to_plan_ref(),
                }
                _check(_VIEW_RECORD, record)
                encoded = _canonical(record).decode("utf-8")
                if any(secret in encoded for secret in (capability, grant.capability)):
                    raise ExecutionContractError
                self._register_reader_view(
                    binding, namespace, peer, ref, grant, record, data, tree, revision, context, deadline
                )
                return grant
        except ExecutionContractError:
            raise SupervisorError("INPUT_POLICY") from None
        except OSError:
            self._healthy = False
            raise SupervisorError("DURABILITY_UNKNOWN") from None

    def _reader_proof(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        ref: ViewRef,
        capability: str,
    ) -> _ReaderPin:
        validate_capability(capability)
        if not isinstance(ref, ViewRef) or not isinstance(namespace, NamespaceRef):
            raise ExecutionContractError
        pin = self._readers.get(ref.view_id)
        if (
            pin is None
            or pin.capability is None
            or not hmac.compare_digest(pin.capability, capability)
            or pin.principal != peer.principal
            or pin.namespace != namespace
            or pin.ref != ref
        ):
            raise SupervisorError("UNAUTHORIZED")
        if pin.record["state"] != "OPEN":
            raise SupervisorError("VIEW_CLOSED")
        return pin

    def _reader(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        ref: ViewRef,
        capability: str,
    ) -> _ReaderPin:
        pin = self._reader_proof(peer, namespace, ref, capability)
        binding = self._binding(ref.workspace_id)
        self._recheck(binding)
        with ExitStack() as stack:
            views = os.open("views", _DIRECTORY, dir_fd=binding.fd)
            stack.callback(os.close, views)
            view = os.open(ref.view_id, _DIRECTORY, dir_fd=views)
            stack.callback(os.close, view)
            _private(view)
            if _identity(os.fstat(view)) != _identity(os.fstat(pin.directory)):
                raise SupervisorError("CORRUPT_STATE")
            if _read_json(view, "view.json", _VIEW_RECORD, 1024**2) != pin.record:
                raise SupervisorError("CORRUPT_STATE")
            revisions = os.open("revisions", _DIRECTORY, dir_fd=binding.fd)
            stack.callback(os.close, revisions)
            revision = os.open(ref.base_revision, _DIRECTORY, dir_fd=revisions)
            stack.callback(os.close, revision)
            data = os.open("data", _DIRECTORY, dir_fd=revision)
            stack.callback(os.close, data)
            if (
                _identity(os.fstat(data)) != _identity(os.fstat(pin.source))
                or _fingerprint(os.stat("tree.json", dir_fd=revision, follow_symlinks=False)) != pin.manifest
            ):
                raise SupervisorError("CORRUPT_STATE")
        try:
            pin.context.recheck()
        except ExecutionContractError:
            raise SupervisorError("INPUT_POLICY") from None
        return pin

    @contextmanager
    def _reader_io(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        view_ref: ViewRef,
        capability: str,
        deadline: float,
    ) -> Generator[tuple[RootedViewIO, _ReaderPin]]:
        # Keep this coarse reader lock through IO: release/shutdown cannot close
        # descriptors underneath a handler. File work shares the dispatch close/drain gate.
        with self._transaction(peer, deadline), self._file_work(peer, namespace, view_ref, capability, deadline):
            try:
                pin = self._reader(peer, namespace, view_ref, capability)
                profile = self._view_profile
                if profile is None:
                    raise SupervisorError("UNAPPROVED_PROFILE")
                with (
                    _private_artifact_directory(self._state / "pending") as staging,
                    RootedViewIO(
                        pin.source,
                        staging,
                        uid=profile.uid,
                        gid=profile.gid,
                        writable=False,
                        protected_paths=()
                        if pin.context.plan_ref is None
                        else (pin.context.plan_ref.workspace_relative_path,),
                        excluded_paths=tuple("/".join(p) for p in self._excluded),
                        max_file_bytes=self._limits.max_file_bytes,
                        max_depth=self._limits.max_depth,
                    ) as io,
                ):
                    _budget(deadline)
                    yield io, pin
                    _budget(deadline)
            except ViewIOError as error:
                raise SupervisorError(error.code) from None
            except OSError:
                raise SupervisorError("CORRUPT_STATE") from None

    def read_file(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        view_ref: ViewRef,
        capability: str,
        path: str,
        offset_bytes: int,
        max_bytes: int,
        deadline: float,
    ) -> ReadResult:
        if not isinstance(view_ref, ViewRef):
            raise ExecutionContractError
        if view_ref.access is Access.WRITE:
            with self._project_io(peer, namespace, view_ref=view_ref, capability=capability, deadline=deadline) as io:
                return io.read_file(path, offset_bytes=offset_bytes, max_bytes=max_bytes)
        with self._reader_io(peer, namespace, view_ref=view_ref, capability=capability, deadline=deadline) as (io, pin):
            result = io.read_file(path, offset_bytes=offset_bytes, max_bytes=max_bytes)
            entry = pin.entries.get(path)
            if entry is None or entry["type"] != "file" or result["sha256"] != entry["sha256"]:
                raise SupervisorError("CORRUPT_STATE")
            return result

    def release_reader(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        view_ref: ViewRef,
        capability: str,
        deadline: float,
    ) -> dict[str, bool]:
        """Revoke unused-for-execution READ retention; never assert cell terminality or GC."""
        with self._transaction(peer, deadline):
            revoked = False
            try:
                pin = self._proof_only(peer, namespace, view_ref, capability)
                if not isinstance(pin, _ReaderPin):
                    raise SupervisorError("UNAUTHORIZED")
                if pin.record["operation_ids"]:
                    raise SupervisorError("WORKSPACE_BUSY")
                self._gate(view_ref).closed = True
                self._wait_drained(view_ref, deadline)
                pin.capability = None
                revoked = True
                pin.record = {**pin.record, "state": "REJECTED"}
                _replace_private_bytes(pin.directory, "view.json", encode_json(pin.record))
                if _read_json(pin.directory, "view.json", _VIEW_RECORD, 1024**2) != pin.record:
                    raise SupervisorError("DURABILITY_UNKNOWN")
                _budget(deadline)
                pin.close()
                return {"released": True}
            except (OSError, SupervisorError):
                if revoked:
                    self._healthy = False
                    raise SupervisorError("DURABILITY_UNKNOWN") from None
                raise

    def _writer_proof(
        self, peer: PeerIdentity, namespace: NamespaceRef, workspace_id: str, capability: str
    ) -> _Binding:
        validate_capability(capability)
        if not isinstance(namespace, NamespaceRef):
            raise ExecutionContractError
        binding = self._binding(workspace_id)
        if (
            binding.metadata["status"] != "OWNED"
            or binding.principal != peer.principal
            or binding.metadata["active_actor"] != namespace.to_dict()
            or binding.grant is None
            or not hmac.compare_digest(binding.grant, capability)
        ):
            raise SupervisorError("UNAUTHORIZED")
        return binding

    def create_view(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        workspace_id: str,
        capability: str,
        purpose: ViewPurpose,
        access: Access,
        candidate_scope: Mapping[str, Any] | None,
        plan_ref: PlanRef | None,
        formal_evidence: bool,
        deadline: float,
    ) -> GrantReply:
        """Construct one view of an EXACT approved purpose; not a command/execution permit.

        The purpose matrix is closed (E259): PROJECT/MUTATION/PROVISIONING are
        writable project views, VERIFICATION/CANDIDATE are immutable reader views
        (CANDIDATE additionally owns one scoped supervisor-staging buffer). Every
        combination is revalidated here before any filesystem effect, independent
        of the codec: no caller-controlled purpose switch and no permissive
        generic view factory exists.
        """
        if type(formal_evidence) is not bool:
            raise ExecutionContractError
        scope = _candidate_scope(purpose, access, candidate_scope, plan_ref)
        with self._transaction(peer, deadline):
            binding = self._writer_proof(peer, namespace, workspace_id, capability)
            profile = self._view_profile
            if profile is None:
                raise SupervisorError("UNAPPROVED_PROFILE")
            if access is Access.READ:
                return self._create_read_view(
                    binding,
                    workspace_id,
                    capability,
                    namespace,
                    peer,
                    purpose,
                    scope,
                    plan_ref,
                    formal_evidence,
                    deadline,
                )
            stage = self._state / "pending" / uuid4().hex
            installed = False
            try:
                self._unchanged(binding, deadline)
                with (
                    self._revision(binding, binding.current["revision_id"], deadline) as (data, tree, _),
                    ExitStack() as descriptors,
                ):
                    context = ProtectedPlanContext(
                        self._state / "workspaces" / workspace_id / "revisions" / tree["revision_id"] / "data",
                        plan_ref,
                        formal_evidence,
                    )
                    context.recheck()
                    ref = ViewRef(
                        workspace_id,
                        "view-" + uuid4().hex,
                        tree["revision_id"],
                        namespace.run_id,
                        binding.metadata["generation"],
                        access,
                        purpose,
                    )
                    grant = GrantReply(Operation.CREATE_VIEW, secrets.token_hex(32), ref, None, None)
                    record = {
                        "schema_version": 1,
                        "view_ref": ref.to_dict(),
                        "actor_namespace": namespace.to_dict(),
                        "state": "OPEN",
                        "input_tree_sha256": tree["tree_sha256"],
                        "sealed_manifest_id": None,
                        "operation_ids": [],
                        "candidate_scope": None,
                        "plan_ref": context.to_plan_ref(),
                    }
                    _check(_VIEW_RECORD, record)
                    encoded = _canonical(record).decode("utf-8")
                    if any(secret in encoded for secret in (capability, grant.capability)):
                        raise ExecutionContractError
                    with _private_artifact_directory(stage) as fd:
                        for name in ("source", "scratch"):
                            os.mkdir(name, 0o700, dir_fd=fd)
                        self._materialize_input(data, fd, tree, profile, deadline)
                        _replace_private_bytes(fd, "view.json", encode_json(record))
                        self._unchanged(binding, deadline)
                        _budget(deadline)
                        directory = self._install_project(binding, stage, record, deadline)
                        descriptors.callback(os.close, directory)
                        installed = True
                    source = os.open("source", _DIRECTORY, dir_fd=directory)
                    descriptors.callback(os.close, source)
                    context = ProtectedPlanContext(
                        self._state / "workspaces" / workspace_id / "views" / ref.view_id / "source",
                        plan_ref,
                        formal_evidence,
                    )
                    context.recheck()
                    _budget(deadline)
                    view = _ProjectView(
                        ref, namespace, peer.principal, grant.capability, record, source, directory, context
                    )
                    self._projects[ref.view_id] = view
                    self._stack.callback(view.close)
                    descriptors.pop_all()
                    return grant
            except SupervisorError:
                if installed or not self._healthy:
                    self._healthy = False
                    raise SupervisorError("DURABILITY_UNKNOWN") from None
                raise
            except ExecutionContractError:
                if installed:
                    self._healthy = False
                    raise SupervisorError("DURABILITY_UNKNOWN") from None
                raise SupervisorError("INPUT_POLICY") from None
            except OSError:
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None
            finally:
                if stage.exists():
                    try:
                        shutil.rmtree(stage)  # Only uninstalled private copy, never a view/revision.
                    except OSError:
                        self._healthy = False
                        raise SupervisorError("DURABILITY_UNKNOWN") from None

    def _materialize_input(
        self,
        data: int,
        stage: int,
        tree: dict[str, Any],
        profile: ExecutionProfile,
        deadline: float,
    ) -> None:
        with ExitStack() as stack:
            source = os.open("source", _DIRECTORY, dir_fd=stage)
            stack.callback(os.close, source)
            actual, _ = self._snapshot(data, source, deadline)
            if len(actual) != len(tree["entries"]):
                raise SupervisorError("CORRUPT_STATE")
            for got, wanted in zip(actual, tree["entries"], strict=True):
                got["mode"] = wanted["mode"]
                if got != wanted:
                    raise SupervisorError("CORRUPT_STATE")
            # All targets are new, private, fully copied and not yet reachable by cells.
            # Children first: restoring a restrictive parent must not hinder its children.
            for entry in sorted(tree["entries"], key=lambda e: e["path"].count("/"), reverse=True):
                _budget(deadline)
                path = entry["path"]
                if entry["type"] == "symlink":
                    os.chown(path, profile.uid, profile.gid, dir_fd=source, follow_symlinks=False)
                else:
                    fd = os.open(path, _DIRECTORY if entry["type"] == "directory" else _FILE, dir_fd=source)
                    try:
                        os.fchown(fd, profile.uid, profile.gid)
                        os.fchmod(fd, entry["mode"])
                        os.fsync(fd)
                    finally:
                        os.close(fd)
            for name in ("source", "scratch"):
                fd = os.open(name, _DIRECTORY, dir_fd=stage)
                try:
                    os.fchown(fd, profile.uid, profile.gid)
                    os.fchmod(fd, 0o755)
                    os.fsync(fd)
                finally:
                    os.close(fd)
            os.fsync(stage)

    def _install_project(self, binding: _Binding, stage: Path, record: dict[str, Any], deadline: float) -> int:
        with ExitStack() as stack:
            parent = os.open(stage.parent, _DIRECTORY)
            stack.callback(os.close, parent)
            views = os.open("views", _DIRECTORY, dir_fd=binding.fd)
            stack.callback(os.close, views)
            _private(views)
            _budget(deadline)
            _rename_directory(parent, stage.name, views, record["view_ref"]["view_id"])
            os.fsync(parent)
            os.fsync(views)
            result = os.open(record["view_ref"]["view_id"], _DIRECTORY, dir_fd=views)
            try:
                _private(result)
                if _read_json(result, "view.json", _VIEW_RECORD, 1024**2) != record:
                    raise SupervisorError("DURABILITY_UNKNOWN")
            except BaseException:
                self._healthy = False
                os.close(result)
                raise
            return result

    def _project_view(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        ref: ViewRef,
        capability: str,
    ) -> _ProjectView:
        validate_capability(capability)
        if not isinstance(ref, ViewRef) or not isinstance(namespace, NamespaceRef):
            raise ExecutionContractError
        view = self._projects.get(ref.view_id)
        if (
            view is None
            or view.capability is None
            or not hmac.compare_digest(view.capability, capability)
            or view.principal != peer.principal
            or view.namespace != namespace
            or view.ref != ref
        ):
            raise SupervisorError("UNAUTHORIZED")
        binding = self._binding(ref.workspace_id)
        if (
            binding.metadata["status"] != "OWNED"
            or binding.grant is None
            or binding.metadata["active_actor"] != namespace.to_dict()
            or binding.metadata["generation"] != ref.generation
            or binding.principal != peer.principal
        ):
            raise SupervisorError("STALE_REVISION")
        if view.record["state"] != "OPEN":
            raise SupervisorError("VIEW_CLOSED")
        self._recheck(binding)
        with ExitStack() as stack:
            views = os.open("views", _DIRECTORY, dir_fd=binding.fd)
            stack.callback(os.close, views)
            directory = os.open(ref.view_id, _DIRECTORY, dir_fd=views)
            stack.callback(os.close, directory)
            _private(directory)
            if _identity(os.fstat(directory)) != _identity(os.fstat(view.directory)):
                raise SupervisorError("CORRUPT_STATE")
            if _read_json(directory, "view.json", _VIEW_RECORD, 1024**2) != view.record:
                raise SupervisorError("CORRUPT_STATE")
            source = os.open("source", _DIRECTORY, dir_fd=directory)
            stack.callback(os.close, source)
            if _identity(os.fstat(source)) != _identity(os.fstat(view.source)):
                raise SupervisorError("CORRUPT_STATE")
        try:
            view.context.recheck()
        except ExecutionContractError:
            raise SupervisorError("INPUT_POLICY") from None
        return view

    @contextmanager
    def _project_io(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        view_ref: ViewRef,
        capability: str,
        deadline: float,
        writable: bool = False,
        write_path: str | None = None,
    ) -> Generator[RootedViewIO]:
        with self._transaction(peer, deadline), self._file_work(peer, namespace, view_ref, capability, deadline):
            completed = False
            try:
                if write_path is not None:
                    # Identity first (a forged ref never reaches the policy),
                    # then the E259 purpose gate at the effect boundary.
                    self._purpose_write_policy(self._proof_only(peer, namespace, view_ref, capability).ref, write_path)
                view = self._project_view(peer, namespace, view_ref, capability)
                profile = self._view_profile
                if profile is None:
                    raise SupervisorError("UNAPPROVED_PROFILE")
                with (
                    _private_artifact_directory(self._state / "pending") as staging,
                    RootedViewIO(
                        view.source,
                        staging,
                        uid=profile.uid,
                        gid=profile.gid,
                        writable=writable,
                        protected_paths=()
                        if view.context.plan_ref is None
                        else (view.context.plan_ref.workspace_relative_path,),
                        excluded_paths=tuple("/".join(p) for p in self._excluded),
                        max_file_bytes=self._limits.max_file_bytes,
                        max_depth=self._limits.max_depth,
                    ) as io,
                ):
                    _budget(deadline)
                    yield io
                    completed = True
                    try:
                        self._project_view(peer, namespace, view_ref, capability)
                        _budget(deadline)
                    except (OSError, SupervisorError):
                        if writable:
                            self._healthy = False
                            raise SupervisorError("DURABILITY_UNKNOWN") from None
                        raise
            except ViewIOError as error:
                if error.code == "DURABILITY_UNKNOWN":
                    self._healthy = False
                raise SupervisorError(error.code) from None
            except OSError:
                if writable and completed:
                    self._healthy = False
                    raise SupervisorError("DURABILITY_UNKNOWN") from None
                raise SupervisorError("CORRUPT_STATE") from None

    @staticmethod
    def _purpose_write_policy(ref: ViewRef, path: str) -> None:
        """E259: the one purpose write gate, applied at the effect boundary.

        VERIFICATION/CANDIDATE views have no generic write path at all (the
        candidate buffer has its own scope-checked methods); MUTATION views are
        confined to the approved mutation roots. PROJECT and PROVISIONING keep
        the ordinary rooted-IO policy.
        """
        if ref.purpose in {ViewPurpose.VERIFICATION, ViewPurpose.CANDIDATE}:
            raise SupervisorError("PATH_DENIED")
        if ref.purpose is ViewPurpose.MUTATION and path.split("/", 1)[0] not in _MUTATION_ROOTS:
            raise SupervisorError("PATH_DENIED")

    def write_file(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        view_ref: ViewRef,
        capability: str,
        path: str,
        content: str,
        expected_sha256: str | None,
        deadline: float,
    ) -> WriteResult:
        with self._project_io(
            peer, namespace, view_ref=view_ref, capability=capability, deadline=deadline, writable=True, write_path=path
        ) as io:
            return self._write_rooted(io, path, content, expected_sha256)

    @staticmethod
    def _write_rooted(io: RootedViewIO, path: str, content: str, expected_sha256: str | None) -> WriteResult:
        return io.write_file(path, content, expected_sha256=expected_sha256)

    def _candidate_buffer(
        self, peer: PeerIdentity, namespace: NamespaceRef, view_ref: ViewRef, capability: str, path: str
    ) -> _ReaderPin:
        """The one scoped candidate buffer binding: exact view, exact path."""
        pin = self._reader_proof(peer, namespace, view_ref, capability)
        if not isinstance(pin, _ReaderPin) or pin.ref.purpose is not ViewPurpose.CANDIDATE:
            raise SupervisorError("UNAUTHORIZED")
        scope = pin.record.get("candidate_scope")
        if scope is None or path != scope["candidate_path"]:
            raise SupervisorError("PATH_DENIED")
        return pin

    @staticmethod
    def _buffer_bytes(pin: _ReaderPin) -> bytes | None:
        try:
            fd = os.open("candidate", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=pin.directory)
        except FileNotFoundError:
            return None
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise SupervisorError("DURABILITY_UNKNOWN")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(fd)

    def write_candidate(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        view_ref: ViewRef,
        capability: str,
        path: str,
        content: str,
        expected_sha256: str | None,
        deadline: float,
    ) -> WriteResult:
        """Write exactly the scoped candidate buffer; never any source or control path.

        The buffer is the ONE supervisor-owned staged file of a CANDIDATE view
        (E259, §5). Canonical .fa/admission is never written here; null
        expected_sha256 means expected ABSENCE, never unconditional overwrite.
        """
        with self._transaction(peer, deadline), self._file_work(peer, namespace, view_ref, capability, deadline):
            pin = self._candidate_buffer(peer, namespace, view_ref, capability, path)
            if not isinstance(content, str) or (
                expected_sha256 is not None
                and (not isinstance(expected_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None)
            ):
                raise SupervisorError("INVALID_REQUEST")
            try:
                raw = content.encode("utf-8")
            except UnicodeEncodeError:
                raise SupervisorError("INVALID_REQUEST") from None
            if b"\x00" in raw or len(raw) > MAX_TEXT_BYTES:
                raise SupervisorError("INVALID_REQUEST")
            if len(raw) > self._limits.max_file_bytes:
                raise SupervisorError("INPUT_POLICY")
            existing = self._buffer_bytes(pin)
            if expected_sha256 is None:
                if existing is not None:
                    raise SupervisorError("STALE_REVISION")
            elif existing is None or hashlib.sha256(existing).hexdigest() != expected_sha256:
                raise SupervisorError("STALE_REVISION")
            try:
                _replace_private_bytes(pin.directory, "candidate", raw)
            except OSError:
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None
            return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}

    def read_candidate(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        view_ref: ViewRef,
        capability: str,
        path: str,
        offset_bytes: int,
        max_bytes: int,
        deadline: float,
    ) -> ReadResult:
        """Read the scoped candidate buffer with ordinary window/SHA semantics."""
        with self._transaction(peer, deadline), self._file_work(peer, namespace, view_ref, capability, deadline):
            pin = self._candidate_buffer(peer, namespace, view_ref, capability, path)
            if (
                type(offset_bytes) is not int
                or offset_bytes < 0
                or type(max_bytes) is not int
                or not 1 <= max_bytes <= MAX_TEXT_BYTES
            ):
                raise SupervisorError("INVALID_REQUEST")
            data = self._buffer_bytes(pin)
            if data is None:
                raise SupervisorError("STALE_REVISION")
            try:
                if b"\x00" in data:
                    raise UnicodeError
                data.decode("utf-8")
                content = data[offset_bytes : offset_bytes + max_bytes].decode("utf-8")
            except UnicodeError:
                raise SupervisorError("INPUT_POLICY") from None
            return {
                "content": content,
                "sha256": hashlib.sha256(data).hexdigest(),
                "eof": offset_bytes + max_bytes >= len(data),
            }

    def _gate(self, ref: ViewRef) -> _WorkGate:
        return self._gates.setdefault(ref.view_id, _WorkGate())

    @property
    def approved_profile(self) -> ExecutionProfile | None:
        """The single approved cell profile, or None when none was configured."""
        return self._view_profile

    def execution_trusted(self, view: ViewRef) -> tuple[NamespaceRef, Path, Path, Path] | None:
        """The authority's own trusted namespace and source/scratch/cache triple.

        A raw path is never an authorization. This exists so the backend can
        prove that the paths it hands to Docker are the ones the authority
        actually admitted, not paths chosen by a caller or a model.
        """
        inputs = self._inputs.get(view.view_id)
        if inputs is None:
            return None
        owner = self._readers.get(view.view_id) if view.access is Access.READ else self._projects.get(view.view_id)
        if owner is None or owner.ref != view:
            return None
        return (owner.namespace, inputs.source, inputs.scratch, inputs.cache)

    def _proof_only(
        self, peer: PeerIdentity, namespace: NamespaceRef, ref: ViewRef, capability: str
    ) -> _ReaderPin | _ProjectView:
        validate_capability(capability)
        if not isinstance(ref, ViewRef) or not isinstance(namespace, NamespaceRef):
            raise ExecutionContractError
        view = self._readers.get(ref.view_id) if ref.access is Access.READ else self._projects.get(ref.view_id)
        if (
            view is None
            or view.capability is None
            or not hmac.compare_digest(view.capability, capability)
            or view.ref != ref
            or view.namespace != namespace
            or view.principal != peer.principal
        ):
            raise SupervisorError("UNAUTHORIZED")
        return view

    def _live_view(
        self, peer: PeerIdentity, namespace: NamespaceRef, ref: ViewRef, capability: str
    ) -> _ReaderPin | _ProjectView:
        view = (
            self._reader(peer, namespace, ref, capability)
            if ref.access is Access.READ
            else self._project_view(peer, namespace, ref, capability)
        )
        if self._gate(ref).closed or view.record["state"] != "OPEN":
            raise SupervisorError("VIEW_CLOSED")
        return view

    @contextmanager
    def _file_work(
        self, peer: PeerIdentity, namespace: NamespaceRef, ref: ViewRef, capability: str, deadline: float
    ) -> Generator[None]:
        # Caller holds authority mutex through bounded native file IO.
        _budget(deadline)
        self._live_view(peer, namespace, ref, capability)
        gate = self._gate(ref)
        work = object()
        gate.active.add(work)
        try:
            yield
        finally:
            gate.active.discard(work)
            self._drained.notify_all()

    def close_admission(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, view_ref: ViewRef, capability: str, deadline: float
    ) -> None:
        """Irreversible gate closure, NOT stop/terminality or permission to release."""
        with self._transaction(peer, deadline):
            view = self._proof_only(peer, namespace, view_ref, capability)
            self._gate(view_ref).closed = True
            if view.record["state"] == "OPEN":
                view.record = {**view.record, "state": "STOPPING"}
                try:
                    _replace_private_bytes(view.directory, "view.json", encode_json(view.record))
                    if _read_json(view.directory, "view.json", _VIEW_RECORD, 1024**2) != view.record:
                        raise SupervisorError("DURABILITY_UNKNOWN")
                    _budget(deadline)
                except (OSError, SupervisorError):
                    self._healthy = False
                    raise SupervisorError("DURABILITY_UNKNOWN") from None

    def _wait_drained(self, ref: ViewRef, deadline: float) -> None:
        gate = self._gate(ref)
        while gate.active:
            _budget(deadline)
            self._drained.wait(timeout=max(0, deadline - time.monotonic()))
        _budget(deadline)

    def drain(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, view_ref: ViewRef, capability: str, deadline: float
    ) -> None:
        with self._transaction(peer, deadline):
            self._proof_only(peer, namespace, view_ref, capability)
            if not self._gate(view_ref).closed:
                raise SupervisorError("VIEW_CLOSED")
            self._wait_drained(view_ref, deadline)

    def _execution_claim(
        self,
        request: dict[str, Any],
        namespace: NamespaceRef,
        ref: ViewRef,
        *,
        deadline: float,
        continuing: bool = False,
    ) -> None:
        try:
            record = self.journal.lookup(request["payload"]["operation_id"], namespace, deadline=deadline)
        except JournalError as error:
            _budget(deadline)
            raise SupervisorError(error.code) from None
        digest = operation_input_sha256(Operation.EXEC, namespace, ref, request["payload"])
        if (
            record is None
            or record["state"] not in ({"EXECUTING", "UNKNOWN"} if continuing else {"EXECUTING"})
            or record["cancel_requested"]
            or record["input_sha256"] != digest
            or record["view_ref"] != ref.to_dict()
        ):
            raise SupervisorError("EXECUTION_UNKNOWN")

    def admit(self, peer: PeerIdentity, request: dict[str, Any], *, deadline: float) -> WorkAdmission:
        """Actual bounded command-dispatch admission for CellBackend, not a RUN sender."""
        req = decode_request(encode_json(request))
        if req["op"] != Operation.EXEC.value:
            raise SupervisorError("INPUT_POLICY")
        namespace = NamespaceRef(**req["namespace"])
        raw = req["view_ref"]
        ref = ViewRef.from_dict(raw)
        with self._transaction(peer, deadline):
            view = self._live_view(peer, namespace, ref, req["capability"])
            profile = self._view_profile
            payload = req["payload"]
            if (
                profile is None
                or self._approved_cache is None
                or payload["profile_id"] != profile.profile_id
                or payload["timeout_ms"] > profile.max_command_ms
                or profile.interactive != (payload["session_id"] is not None)
            ):
                raise SupervisorError("UNAPPROVED_PROFILE")
            self._execution_claim(req, namespace, ref, deadline=deadline)
            if payload["operation_id"] in view.record["operation_ids"]:
                raise SupervisorError("EXECUTION_UNKNOWN")
            gate = self._gate(ref)
            work = object()
            gate.active.add(work)
            created = ref.view_id not in self._inputs
            inputs: _ExecutionInputs | None = None
            try:
                inputs = self._ensure_inputs(view, profile, deadline)
                self._validate_inputs(ref, inputs, deadline)
                operation_id = payload["operation_id"]
                if operation_id not in view.record["operation_ids"]:
                    view.record = {**view.record, "operation_ids": [*view.record["operation_ids"], operation_id]}
                    try:
                        _replace_private_bytes(view.directory, "view.json", encode_json(view.record))
                        if _read_json(view.directory, "view.json", _VIEW_RECORD, 1024**2) != view.record:
                            raise SupervisorError("DURABILITY_UNKNOWN")
                    except (OSError, SupervisorError):
                        self._healthy = False
                        raise SupervisorError("DURABILITY_UNKNOWN") from None
                _budget(deadline)
                return WorkAdmission(
                    self,
                    peer,
                    namespace,
                    ref,
                    req["capability"],
                    req,
                    deadline,
                    profile,
                    inputs,
                    view.record["input_tree_sha256"],
                    work,
                )
            except BaseException:
                gate.active.discard(work)
                self._drained.notify_all()
                if created:
                    # A failed admission must not leave our own projection copy
                    # behind; a leftover would permanently block a retry.
                    self._inputs.pop(ref.view_id, None)
                    if inputs is not None:
                        inputs.close()
                        self._discard_projection(inputs.projection)
                raise

    def _ensure_inputs(
        self, view: _ReaderPin | _ProjectView, profile: ExecutionProfile, deadline: float
    ) -> _ExecutionInputs:
        existing = self._inputs.get(view.ref.view_id)
        if existing is not None:
            return existing
        root = self._state / "workspaces" / view.ref.workspace_id / "views" / view.ref.view_id
        cache = self._approved_cache
        if cache is None:
            raise SupervisorError("UNAPPROVED_PROFILE")
        stage = self._state / "pending" / uuid4().hex
        installed: Path | None = None
        sealed: str | None = None
        try:
            with ExitStack() as opened:
                cache_fd = _open_absolute(cache)
                opened.callback(os.close, cache_fd)
                info = os.fstat(cache_fd)
                if info.st_uid != os.getuid() or info.st_mode & 0o022:
                    raise SupervisorError("PATH_DENIED")
                if isinstance(view, _ReaderPin):
                    binding = self._binding(view.ref.workspace_id)
                    with self._revision(binding, view.ref.base_revision, deadline) as (data, tree, _):
                        with _private_artifact_directory(stage) as fd:
                            for name in ("source", "scratch"):
                                os.mkdir(name, 0o700, dir_fd=fd)
                            self._materialize_input(data, fd, tree, profile, deadline)
                            sealed = self._seal_readonly_source(fd, tree, deadline)
                            _budget(deadline)
                            parent = os.open(stage.parent, _DIRECTORY)
                            try:
                                _rename_directory(parent, stage.name, view.directory, "execution")
                                installed = (
                                    self._state
                                    / "workspaces"
                                    / view.ref.workspace_id
                                    / "views"
                                    / view.ref.view_id
                                    / "execution"
                                )
                                os.fsync(parent)
                                os.fsync(view.directory)
                            finally:
                                os.close(parent)
                    root = root / "execution"
                fds = []
                for path in (root / "source", root / "scratch"):
                    fd = _open_absolute(path)
                    opened.callback(os.close, fd)
                    fds.append(fd)
                context = ProtectedPlanContext(root / "source", view.context.plan_ref, view.context.formal_evidence)
                inputs = _ExecutionInputs(
                    root / "source", root / "scratch", cache, fds[0], fds[1], cache_fd, context, sealed, installed
                )
                self._validate_inputs(view.ref, inputs, deadline)
                self._stack.callback(inputs.close)
                self._inputs[view.ref.view_id] = inputs
                opened.pop_all()
                return inputs
        except OSError:
            self._healthy = False
            self._discard_projection(installed)
            raise SupervisorError("DURABILITY_UNKNOWN") from None
        except SupervisorError:
            # Our own projection copy must not survive a failed admission.
            self._discard_projection(installed)
            raise
        finally:
            if stage.exists():
                try:
                    shutil.rmtree(stage)
                except OSError:
                    self._healthy = False
                    raise SupervisorError("DURABILITY_UNKNOWN") from None

    def _seal_readonly_source(self, stage: int, tree: dict[str, Any], deadline: float) -> str | None:
        """READ execution source is service-owned and not cell-writable.

        The container mount is read-only too; this closes the local copy so the
        cell cannot silently corrupt its own READ source before the digest
        recheck at the effect boundary notices. Write bits are stripped, so the
        strict digest of the SEALED tree replaces the revision tree hash.
        """
        source = os.open("source", _DIRECTORY, dir_fd=stage)
        try:
            for entry in tree["entries"]:
                if entry["type"] == "symlink":
                    os.chown(entry["path"], os.getuid(), os.getgid(), dir_fd=source, follow_symlinks=False)
                    continue
                fd = os.open(entry["path"], _DIRECTORY if entry["type"] == "directory" else _FILE, dir_fd=source)
                try:
                    os.fchown(fd, os.getuid(), os.getgid())
                    os.fchmod(fd, entry["mode"] & ~0o222)
                finally:
                    os.close(fd)
            os.fchown(source, os.getuid(), os.getgid())
            os.fchmod(source, 0o555)
            os.fsync(source)
            _, digest = self._snapshot(source, None, deadline)
            return digest
        finally:
            os.close(source)

    def _discard_projection(self, installed: Path | None) -> None:
        """Remove ONLY our own private projection copy after a failed install.

        A leftover projection would permanently block a later admission with a
        no-clobber rename, so a failed install must not leave one behind.
        """
        if installed is None or not installed.exists():
            return
        try:
            # A sealed READ projection is not writable; restore owner write bits
            # on our own private copy before removing it.
            for parent, directories, _ in os.walk(installed):
                for name in directories:
                    os.chmod(os.path.join(parent, name), 0o700)
            os.chmod(installed, 0o700)
            shutil.rmtree(installed)
        except OSError:
            self._healthy = False
            raise SupervisorError("DURABILITY_UNKNOWN") from None

    def _validate_inputs(self, ref: ViewRef, inputs: _ExecutionInputs, deadline: float) -> None:
        _budget(deadline)
        try:
            for path, fd in (
                (inputs.source, inputs.source_fd),
                (inputs.scratch, inputs.scratch_fd),
                (inputs.cache, inputs.cache_fd),
            ):
                current = _open_absolute(path)
                try:
                    if _identity(os.fstat(current)) != _identity(os.fstat(fd)):
                        raise SupervisorError("CORRUPT_STATE")
                finally:
                    os.close(current)
            cache = os.fstat(inputs.cache_fd)
            if cache.st_uid != os.getuid() or cache.st_mode & 0o022:
                raise SupervisorError("PATH_DENIED")
            inputs.context.recheck()
            if ref.access is Access.READ:
                if inputs.sealed_sha256 is None:
                    raise SupervisorError("CORRUPT_STATE")
                _, digest = self._snapshot(inputs.source_fd, None, deadline)
                if digest != inputs.sealed_sha256:
                    raise SupervisorError("CORRUPT_STATE")
        except ExecutionContractError:
            raise SupervisorError("INPUT_POLICY") from None
        except OSError:
            raise SupervisorError("CORRUPT_STATE") from None
