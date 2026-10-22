"""Protected existing-workspace registration, R0 retention and exclusive writer.

The actual owner, not a wire service or a temporary admission callback. New-root
installation, backend drain and publication are subsequent
construction steps. No factory is activated here. Legacy writers must already be
quiesced by deployment; metadata/hash checks are not a kernel snapshot/CAS.
"""

from __future__ import annotations

import errno
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
from collections.abc import Callable, Generator, Mapping, Sequence
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
    CONFIG_ID,
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
# Q80/E269: ONE shape, five keys, written at registration and after every
# publish (spec §5.1). The "initial" three-key form in §4 never shipped in a
# deployed workspace and has no committed fixture, so this is an amendment, not
# a migration; a field three-key file would need a migration, not a union.
_CURRENT = fastjsonschema.compile(
    _object(
        schema_version={"type": "integer", "const": 1},
        workspace_id=_id("ws-"),
        generation=_UINT,
        revision_id=_id("rev-"),
        tree_sha256=SHA,
    )
)

# A prepared bundle is a private, pre-install object: paths and digests only,
# bound to the workspace/generation/base it was prepared against (E271).
# Modes are recorded per file now, while the schema is still unshipped: at
# install these bytes become the project's genesis revision, and a mode chosen
# at install time would be frozen into every later revision of that project.
_BUNDLE_FILE = _object(
    path={"type": "string", "maxLength": 4096},
    sha256=SHA,
    size=_UINT,
    mode={"type": "integer", "minimum": 0, "maximum": 511},
)
# The manifest states what install will apply; the staging copy itself stays
# private (0700) so a half-written bundle is never world-readable.
_BUNDLE_FILE_MODE = 0o644
_BUNDLE_DIRECTORY_MODE = 0o755
_BUNDLE = fastjsonschema.compile(
    _object(
        schema_version={"type": "integer", "const": 1},
        kind={"type": "string", "const": "BUNDLE"},
        bundle_id=_id("bundle-"),
        operation_id=_id("op-"),
        workspace_id=_id("ws-"),
        generation=_UINT,
        base_revision=_id("rev-"),
        project_slug={"type": "string", "maxLength": 48},
        increment_slug={"type": "string", "maxLength": 48},
        files={"type": "array", "items": _BUNDLE_FILE},
        directory_mode={"type": "integer", "minimum": 0, "maximum": 511},
        bundle_sha256=SHA,
    )
)

# Spec §5.1's exact intent vocabulary. E269 produces only kind=REVISION; PLAN
# arrives with the Q58 path and BOOTSTRAP with install_project. `phase` is
# advisory for recovery: `current.json` alone discriminates a commit.
_INTENT = fastjsonschema.compile(
    _object(
        schema_version={"type": "integer", "const": 1},
        kind=_enum("REVISION", "PLAN", "BOOTSTRAP"),
        operation_id=_id("op-"),
        workspace_id=_id("ws-"),
        generation=_UINT,
        base_revision=_id("rev-"),
        next_revision=_id("rev-"),
        tree_sha256=SHA,
        phase=_enum("PREPARED", "COMMITTED", "PROJECTING", "DONE"),
        target_relative=_nullable({"type": "string", "maxLength": 4096}),
        old_sha256=_nullable(SHA),
        new_sha256=_nullable(SHA),
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
        sealed_manifest_id=_nullable(_id("seal-")),
        operation_ids={"type": "array", "items": _id("op-")},
        candidate_scope=_nullable(CANDIDATE_SCOPE),
        plan_ref=_nullable(PLAN_REF),
    )
)

# Terminality is a *precondition of sealing*, not a view state: the state
# vocabulary above is the closed one the protocol publishes, so the barrier
# records its positive observation in its own small receipt file.
_TERMINAL_RECEIPT = fastjsonschema.compile(_object(schema_version={"type": "integer", "const": 1}, view_ref=VIEW))

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
# Components the canonical projection never traverses or writes, at any depth.
# `_Capture` drops them from every revision, so a manifest naming one is forged.
_PROTECTED_COMPONENTS = frozenset({".git", ".fa", ".venv", ".env"})
# Projection scratch: inside the canonical root (same filesystem, atomic
# replace) but inside `.fa`, which every walk excludes at any depth.
_PROJECTION_SCRATCH = (".fa", "publish-tmp")
_TEMPORARY_SUFFIX = ".publish"
# Install (Q82 (B)): a new project lives at `<canonical root>/worklogs/<slug>`,
# the same workspace-relative path §7.1 freezes for a rendered project.
_INSTALL_ROOT = "worklogs"
_SLUG = re.compile(str(CONFIG_ID["pattern"]))


def _derive_revision_id(manifest: Mapping[str, Any]) -> str:
    """Content-address the revision a sealed manifest describes (E267 D2).

    Lives here, not in `publication`, because the id names a directory under
    `revisions/`: storage owns the formula, publication re-exports it. One
    implementation means a drifted derivation cannot silently disagree.
    """
    return "rev-" + hashlib.sha256(_canonical(dict(manifest))).hexdigest()[:32]


def _require_manifest_match(copied: Sequence[dict[str, Any]], sealed: Sequence[Mapping[str, Any]]) -> None:
    """The copied tree must be exactly the manifest's live entries.

    Seal hashed these bytes after the barrier; the copy is the last moment the
    two can disagree before a revision becomes installable. Modes are compared
    strictly (unlike retention copies), because a view source keeps logical modes.
    """
    live = [dict(entry) for entry in sealed if not entry["deleted"]]
    if len(copied) != len(live):
        raise SupervisorError("CORRUPT_STATE")
    for got, wanted in zip(copied, live, strict=True):
        if got != wanted:
            raise SupervisorError("CORRUPT_STATE")


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


def _terminal_record(directory: int) -> dict[str, Any] | None:
    """The durable "descendants observed empty" receipt, or None when absent."""
    try:
        return _read_json(directory, "terminal.json", _TERMINAL_RECEIPT, 1024)
    except FileNotFoundError:
        return None


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


@dataclass(frozen=True)
class _SealInputs:
    """Everything seal needs, validated once under the authority mutex.

    Seal must not re-open roots of its own: the authority hands over the view it
    already proved, the *recomputed* entries of that view's frozen source, the
    base revision's entries and the caller's deadline. No descriptor is kept,
    so a seal failure can never leak one.
    """

    view_ref: ViewRef
    record: dict[str, Any]
    directory: int
    entries: tuple[dict[str, Any], ...]
    base_entries: tuple[dict[str, Any], ...]
    tree_sha256: str
    base_revision: str
    generation: int
    plan_path: str | None


@dataclass
class _PublishInputs:
    """Everything publish needs, validated once under the authority mutex.

    Deliberately carries **no capability**: the secret is passed as an argument
    to each phase and re-proved there, so a retained `_PublishInputs` can never
    act on its own. `entries` includes tombstones; `revision_id` is recomputed
    from the manifest, never supplied by a caller.
    """

    view_ref: ViewRef
    record: dict[str, Any]
    directory: int
    entries: tuple[dict[str, Any], ...]
    revision_id: str
    tree_sha256: str
    base_revision: str
    generation: int
    operation_id: str


@dataclass(frozen=True)
class _InstallInputs:
    """Everything install needs, proved once under the authority mutex (Q82 (B)).

    Carries **no capability**, like `_PublishInputs`. `entries` is the complete
    post-install tree, computed before the irreversible rename so the intent can
    name the revision and digest it will commit.
    """

    workspace_id: str
    generation: int
    base_revision: str
    revision_id: str
    tree_sha256: str
    operation_id: str
    bundle_id: str
    project_slug: str
    target_relative: str
    bundle_sha256: str
    files: tuple[dict[str, Any], ...]
    entries: tuple[dict[str, Any], ...]
    intent: dict[str, Any]


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
            # Q80: after genesis normalizes a legacy 0 to 1, the pointer must
            # name this workspace and no later epoch than its owner metadata.
            # Equality is NOT required: release + re-claim legally advances
            # workspace.json past the epoch that committed the pointer.
            if current["workspace_id"] != workspace_id or current["generation"] > binding.metadata["generation"]:
                raise SupervisorError("CORRUPT_STATE")
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
        """Register quiescent existing bytes, never create/chmod a canonical root.

        Returns the committed identity `{workspace_id, revision_id, tree_sha256}`;
        the digest is the verified tree of that revision, so a caller can bind
        session ownership to exactly the bytes it was given.
        """
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
                            "tree_sha256": binding.current["tree_sha256"],
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
                binding.current = {
                    "schema_version": 1,
                    "workspace_id": workspace_id,
                    "generation": binding.metadata["generation"],
                    "revision_id": revision_id,
                    "tree_sha256": digest,
                }
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
            return {"workspace_id": workspace_id, "revision_id": revision_id, "tree_sha256": digest}
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
                    if self._has_unsettled_views(binding, views) or "intent.json" in os.listdir(binding.fd):
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

    # Settled = no further writer-owned work can arrive: publish finished the
    # view (PUBLISHED) or publication rejected it (REJECTED). Everything else on
    # a WRITE view is either writable, stopping, or unknown, and must keep the
    # owner (spec §2.1 release row: "no writable/live/unknown jobs or unfinished
    # projection"). A SEALED view is unfinished *publication*, so it still holds
    # the writer: releasing it would strand an unpublishable candidate whose
    # capability dies with the grant.
    _SETTLED_VIEW_STATES = frozenset({"PUBLISHED", "REJECTED"})

    @classmethod
    def _has_unsettled_views(cls, binding: _Binding, views: int) -> bool:
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
                if ref["access"] != Access.READ.value and record["state"] not in cls._SETTLED_VIEW_STATES:
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
        base_revision: str | None = None,
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
        if base_revision is not None:
            _hex_id(base_revision, "rev-")
        with self._transaction(peer, deadline):
            binding = self._writer_proof(peer, namespace, workspace_id, capability)
            # The wire's base_revision is a CAS precondition, not decoration: a
            # caller that names different bytes than current must be refused
            # before any copy, never silently given the newer revision.
            if base_revision is not None and base_revision != binding.current["revision_id"]:
                raise SupervisorError("STALE_REVISION")
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
                        directory = self._install_view(binding, stage, record, deadline)
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

    def _install_view(self, binding: _Binding, stage: Path, record: dict[str, Any], deadline: float) -> int:
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

    def record_terminal(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, view_ref: ViewRef, capability: str, deadline: float
    ) -> dict[str, Any]:
        """Durably record that this view's descendants were observed empty.

        Deliberately NOT a view state: ``view.json`` keeps the closed vocabulary
        the protocol publishes, and terminality is a precondition of sealing.
        An OPEN view (or one whose admission is still open) is refused, so this
        cannot be used to skip close/drain; an existing receipt is returned
        unchanged, so a retried stop pays no second write. A failed rewrite is
        uncertainty, never permission to retry into a success.
        """
        with self._transaction(peer, deadline):
            view = self._proof_only(peer, namespace, view_ref, capability)
            if view.record["state"] == "OPEN" or not self._gate(view_ref).closed:
                raise SupervisorError("VIEW_CLOSED")
            existing = _terminal_record(view.directory)
            if existing is not None:
                return existing
            receipt = {"schema_version": 1, "view_ref": view_ref.to_dict()}
            try:
                _replace_private_bytes(view.directory, "terminal.json", encode_json(receipt))
                if _terminal_record(view.directory) != receipt:
                    raise SupervisorError("DURABILITY_UNKNOWN")
                _budget(deadline)
            except (OSError, SupervisorError):
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None
            return receipt

    def prepare_seal(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, view_ref: ViewRef, capability: str, deadline: float
    ) -> _SealInputs:
        """Validate every seal precondition and recompute the frozen view's tree.

        The recomputation is the point: the caller may not hand seal a manifest,
        a tree hash or a directory, and the bytes are read *after* the barrier,
        so nothing a cell wrote earlier can still move them. A view that is not
        stopped-and-observed never reaches this method's success path: `OPEN`,
        `SEALED`, `PUBLISHED`, `REJECTED` are `VIEW_CLOSED` here (E267 D3 keeps
        `REJECTED` off this edge), and an `UNKNOWN` view is `TERMINALITY_UNKNOWN`
        because nobody can prove its descendants are gone.
        """
        with self._transaction(peer, deadline):
            view = self._proof_only(peer, namespace, view_ref, capability)
            state = view.record["state"]
            if state == "UNKNOWN":
                raise SupervisorError("TERMINALITY_UNKNOWN")
            # SEALED is allowed so a retried seal can answer from durable bytes;
            # the transition itself is refused below when the state is not STOPPING.
            if state not in {"STOPPING", "SEALED"}:
                raise SupervisorError("VIEW_CLOSED")
            if not self._gate(view_ref).closed:
                raise SupervisorError("VIEW_CLOSED")
            if _terminal_record(view.directory) is None:
                raise SupervisorError("TERMINALITY_UNKNOWN")
            try:
                view.context.recheck()
            except ExecutionContractError:
                raise SupervisorError("INPUT_POLICY") from None
            binding = self._binding(view_ref.workspace_id)
            self._recheck(binding)
            if binding.metadata["generation"] != view_ref.generation:
                raise SupervisorError("STALE_GENERATION")
            if (
                binding.metadata["status"] != "OWNED"
                or binding.grant is None
                or binding.metadata["active_actor"] != namespace.to_dict()
                or binding.principal != peer.principal
            ):
                raise SupervisorError("STALE_GENERATION")
            if binding.current["revision_id"] != view_ref.base_revision:
                raise SupervisorError("STALE_REVISION")
            with self._revision(binding, view_ref.base_revision, deadline) as (_, base, _child):
                if base["tree_sha256"] != view.record["input_tree_sha256"]:
                    raise SupervisorError("STALE_REVISION")
                base_entries = tuple(dict(entry) for entry in base["entries"])
            source = self._sealed_source(view)
            try:
                entries, digest = self._snapshot(source, None, deadline)
            finally:
                os.close(source)
            plan = view.record.get("plan_ref")
            return _SealInputs(
                view_ref=view_ref,
                record={**view.record, "operation_ids": list(view.record["operation_ids"])},
                directory=view.directory,
                entries=tuple(entries),
                base_entries=base_entries,
                tree_sha256=digest,
                base_revision=view_ref.base_revision,
                generation=binding.metadata["generation"],
                plan_path=None if plan is None else plan["workspace_relative_path"],
            )

    @staticmethod
    def _sealed_source(view: _ReaderPin | _ProjectView) -> int:
        """Open this view's own frozen source, refusing a swapped directory."""
        if not isinstance(view, _ProjectView):
            raise SupervisorError("VIEW_CLOSED")
        source = os.open("source", _DIRECTORY, dir_fd=view.directory)
        if _identity(os.fstat(source)) != _identity(os.fstat(view.source)):
            os.close(source)
            raise SupervisorError("CORRUPT_STATE")
        return source

    def mark_sealed(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        view_ref: ViewRef,
        capability: str,
        sealed_manifest_id: str,
        deadline: float,
    ) -> dict[str, Any]:
        """The single durable `STOPPING -> SEALED` transition, and its read-back.

        Only the manifest id is persisted here; the revision id is derived from
        the sealed bytes (E267 D2), so a restart can recompute it instead of
        trusting a stored claim. Anything short of a verified read-back is
        `DURABILITY_UNKNOWN` and leaves the view `STOPPING` — seal never reports
        success for a state it could not prove.
        """
        _hex_id(sealed_manifest_id, "seal-")
        with self._transaction(peer, deadline):
            view = self._proof_only(peer, namespace, view_ref, capability)
            if not isinstance(view, _ProjectView):
                raise SupervisorError("VIEW_CLOSED")  # A READ pin is never sealable (D4).
            if view.record["state"] == "SEALED":
                if view.record["sealed_manifest_id"] != sealed_manifest_id:
                    raise SupervisorError("CORRUPT_STATE")
                return dict(view.record)
            if view.record["state"] != "STOPPING" or not self._gate(view_ref).closed:
                raise SupervisorError("VIEW_CLOSED")
            if _terminal_record(view.directory) is None:
                raise SupervisorError("TERMINALITY_UNKNOWN")
            updated = {**view.record, "state": "SEALED", "sealed_manifest_id": sealed_manifest_id}
            try:
                _replace_private_bytes(view.directory, "view.json", encode_json(updated))
                if _read_json(view.directory, "view.json", _VIEW_RECORD, 1024**2) != updated:
                    raise SupervisorError("DURABILITY_UNKNOWN")
                _budget(deadline)
            except (OSError, SupervisorError):
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None
            view.record = updated
            return dict(updated)

    def terminal_receipt(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, view_ref: ViewRef, capability: str
    ) -> dict[str, Any] | None:
        """Read-only: the receipt for this exact view, or None."""
        return _terminal_record(self._proof_only(peer, namespace, view_ref, capability).directory)

    # -- Prepared bundle (E271 / STEP3): stored, validated, installable ------

    def store_bundle(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        capability: str,
        project_slug: str,
        increment_slug: str,
        files: Mapping[str, bytes],
        expected_base_revision: str,
        operation_id: str,
        deadline: float,
    ) -> dict[str, str]:
        """Durably store one rendered bundle and mint its id. Writes no project.

        The owner must hold the grant, own no unsettled view and extend exactly
        the base revision the caller named: a bundle prepared against revision A
        must never be installable against revision B.
        """
        _hex_id(operation_id, "op-")
        _hex_id(expected_base_revision, "rev-")
        with self._transaction(peer, deadline):
            binding = self._owner_only(peer, namespace, capability)
            if binding.current["revision_id"] != expected_base_revision:
                raise SupervisorError("STALE_REVISION")
            views = os.open("views", _DIRECTORY, dir_fd=binding.fd)
            try:
                _private(views)
                if self._has_unsettled_views(binding, views) or self._read_intent(binding.fd) is not None:
                    raise SupervisorError("WORKSPACE_BUSY")
            finally:
                os.close(views)
            bundle_id = "bundle-" + uuid4().hex
            manifest = {
                "schema_version": 1,
                "kind": "BUNDLE",
                "bundle_id": bundle_id,
                "operation_id": operation_id,
                "workspace_id": binding.metadata["workspace_id"],
                "generation": binding.metadata["generation"],
                "base_revision": expected_base_revision,
                "project_slug": project_slug,
                "increment_slug": increment_slug,
                "files": [
                    {
                        "path": path,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "size": len(raw),
                        "mode": _BUNDLE_FILE_MODE,
                    }
                    for path, raw in sorted(files.items())
                ],
                "directory_mode": _BUNDLE_DIRECTORY_MODE,
                "bundle_sha256": hashlib.sha256(
                    _canonical([[path, hashlib.sha256(files[path]).hexdigest()] for path in sorted(files)])
                ).hexdigest(),
            }
            try:
                _check(_BUNDLE, manifest)
            except ExecutionContractError:
                raise SupervisorError("INPUT_POLICY") from None
            self._write_bundle(binding, manifest, files, deadline)
            return {"validated_bundle_id": bundle_id, "bundle_sha256": manifest["bundle_sha256"]}

    def _owner_only(self, peer: PeerIdentity, namespace: NamespaceRef, capability: str) -> _Binding:
        """A view-less owner proof: OWNER grant, active actor, principal, all exact."""
        validate_capability(capability)
        binding = next(
            (
                candidate
                for candidate in self._bindings.values()
                if candidate.grant is not None
                and candidate.principal == peer.principal
                and candidate.metadata["active_actor"] == namespace.to_dict()
                and hmac.compare_digest(candidate.grant, capability)
            ),
            None,
        )
        if binding is None:
            raise SupervisorError("UNAUTHORIZED")
        self._recheck(binding)
        if binding.metadata["status"] != "OWNED" or binding.principal != peer.principal:
            raise SupervisorError("STALE_GENERATION")
        return binding

    def _write_bundle(
        self, binding: _Binding, manifest: dict[str, Any], files: Mapping[str, bytes], deadline: float
    ) -> None:
        """Stage one self-contained directory under `pending/`, then rename it in.

        A partial bundle is therefore never visible, and each bundle owns its
        own manifest: there is no shared index that a concurrent prepare could
        overwrite.
        """
        stage = self._state / "pending" / uuid4().hex
        installed = False
        try:
            with _private_artifact_directory(stage) as stage_fd:
                for path, raw in sorted(files.items()):
                    self._write_bundle_file(stage, path, raw, deadline)
                _replace_private_bytes(stage_fd, "bundle.json", _canonical(manifest))
                if _read_json(stage_fd, "bundle.json", _BUNDLE, 1024**2) != manifest:
                    raise SupervisorError("DURABILITY_UNKNOWN")
                try:
                    os.mkdir("bundles", 0o700, dir_fd=binding.fd)
                    os.fsync(binding.fd)
                except FileExistsError:
                    pass
                bundles = os.open("bundles", _DIRECTORY, dir_fd=binding.fd)
                try:
                    parent = os.open(stage.parent, _DIRECTORY)
                    try:
                        _budget(deadline)
                        _rename_directory(parent, stage.name, bundles, manifest["bundle_id"])
                        installed = True
                        os.fsync(bundles)
                    finally:
                        os.close(parent)
                finally:
                    os.close(bundles)
            os.fsync(binding.fd)
        except OSError:
            self._healthy = False
            raise SupervisorError("DURABILITY_UNKNOWN") from None
        finally:
            if not installed and stage.exists():
                shutil.rmtree(stage)

    @staticmethod
    def _write_bundle_file(stage: Path, path: str, raw: bytes, deadline: float) -> None:
        """Create only ordinary nested directories, never a link or a dot path."""
        parts = path.split("/")
        if any(part in {"", ".", ".."} or part.startswith(".") for part in parts):
            raise SupervisorError("INPUT_POLICY")
        parent = os.open(stage, _DIRECTORY)
        try:
            for part in parts[:-1]:
                try:
                    os.mkdir(part, 0o700, dir_fd=parent)
                except FileExistsError:
                    pass
                child = os.open(part, _DIRECTORY, dir_fd=parent)
                os.close(parent)
                parent = child
            _budget(deadline)
            fd = os.open(
                parts[-1],
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                _BUNDLE_FILE_MODE,
                dir_fd=parent,
            )
            try:
                os.fchmod(fd, _BUNDLE_FILE_MODE)
                _write_all(fd, raw)
                os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(parent)
        finally:
            os.close(parent)

    # -- Install (STEP3 unit B, Q82 (B)): BOOTSTRAP one bundle in place --------

    def install_project(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        capability: str,
        validated_bundle_id: str,
        project_slug: str,
        deadline: float,
    ) -> dict[str, Any]:
        """Install one prepared bundle as `<root>/worklogs/<project_slug>`.

        The order is §5.1's BOOTSTRAP row, not REVISION's: a durable intent, then
        the irreversible no-clobber rename, then the revision and pointer that
        describe the directory that now exists, then the proof. Everything after
        the rename is forward-only — no path here deletes installed bytes.

        The wire carries no operation id for this call, so it is derived from the
        bundle it names: retrying the same install converges on the same
        operation instead of inventing a second one (Q83).
        """
        _hex_id(validated_bundle_id, "bundle-")
        with self._transaction(peer, deadline):
            binding = self._owner_only(peer, namespace, capability)
            inputs = self._install_prepare(binding, validated_bundle_id, project_slug, deadline)
            parent, created = self._install_destination(binding.source, inputs.target_relative)
            scratch = -1
            renamed = False
            try:
                try:
                    os.stat(inputs.project_slug, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise SupervisorError("COLLISION")  # determinate; nothing written
                scratch = self._install_stage(binding, inputs, deadline)
                # Durable BEFORE the first irreversible byte (spec §5.1).
                self._write_intent(binding.fd, inputs.intent)
                try:
                    _rename_directory(scratch, inputs.operation_id, parent, inputs.project_slug)
                except OSError as error:
                    if error.errno in {errno.EEXIST, errno.ENOTEMPTY}:
                        raise SupervisorError("COLLISION") from None
                    if error.errno == errno.ENOSYS:
                        raise SupervisorError("BACKEND_UNAVAILABLE") from None
                    raise SupervisorError("DURABILITY_UNKNOWN") from None
                renamed = True
                os.fsync(parent)
            except SupervisorError:
                if not renamed:
                    # Nothing irreversible happened: discard only this attempt's
                    # scratch, the directories it created, and its intent.
                    self._install_abort(binding, inputs, scratch, created)
                raise
            except OSError:
                if not renamed:
                    self._install_abort(binding, inputs, scratch, created)
                    raise SupervisorError("DURABILITY_UNKNOWN") from None
                # The directory exists but its durability is unknown: keep the
                # intent for forward recovery and block further work.
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None
            finally:
                os.close(parent)
                if scratch != -1:
                    os.close(scratch)
            return self._install_finish(binding, inputs, deadline)

    def _install_prepare(
        self, binding: _Binding, validated_bundle_id: str, project_slug: str, deadline: float
    ) -> _InstallInputs:
        """Prove every precondition and compute the exact tree that will exist."""
        if not isinstance(project_slug, str) or _SLUG.fullmatch(project_slug) is None:
            raise SupervisorError("INPUT_POLICY")
        views = os.open("views", _DIRECTORY, dir_fd=binding.fd)
        try:
            _private(views)
            if self._has_unsettled_views(binding, views) or self._read_intent(binding.fd) is not None:
                raise SupervisorError("WORKSPACE_BUSY")
        finally:
            os.close(views)
        self._probe_writable(binding)
        # The canonical tree must still be exactly the current revision, so the
        # expected tree below is the truth rather than a hope.
        self._unchanged(binding, deadline)
        bundles = os.open("bundles", _DIRECTORY, dir_fd=binding.fd)
        try:
            try:
                bundle = os.open(validated_bundle_id, _DIRECTORY, dir_fd=bundles)
            except FileNotFoundError:
                raise SupervisorError("INPUT_POLICY") from None  # no such bundle here
            try:
                _private(bundle)
                manifest = _read_json(bundle, "bundle.json", _BUNDLE, 1024**2)
            finally:
                os.close(bundle)
        finally:
            os.close(bundles)
        if manifest["bundle_id"] != validated_bundle_id:
            raise SupervisorError("CORRUPT_STATE")  # directory name vs its own manifest
        if manifest["workspace_id"] != binding.metadata["workspace_id"]:
            raise SupervisorError("UNAUTHORIZED")  # another workspace's bundle
        if manifest["generation"] != binding.metadata["generation"]:
            raise SupervisorError("STALE_GENERATION")
        if manifest["base_revision"] != binding.current["revision_id"]:
            raise SupervisorError("STALE_REVISION")  # prepared against other bytes
        if manifest["project_slug"] != project_slug:
            raise SupervisorError("INPUT_POLICY")  # an id cannot be retargeted
        target = f"{_INSTALL_ROOT}/{project_slug}"
        files = tuple(self._install_file_record(entry, project_slug) for entry in manifest["files"])
        with self._revision(binding, binding.current["revision_id"], deadline) as (_, base, _child):
            base_entries = tuple(dict(entry) for entry in base["entries"])
        entries = self._install_entries(base_entries, files)
        tree_sha256 = hashlib.sha256(_canonical(list(entries))).hexdigest()
        operation_id = "op-" + validated_bundle_id.removeprefix("bundle-")
        install_manifest = {
            "schema_version": 1,
            "kind": "BOOTSTRAP",
            "operation_id": operation_id,
            "workspace_id": binding.metadata["workspace_id"],
            "generation": binding.metadata["generation"],
            "base_revision": binding.current["revision_id"],
            "project_slug": project_slug,
            "bundle_sha256": manifest["bundle_sha256"],
            "tree_sha256": tree_sha256,
            "entries": list(entries),
        }
        revision_id = _derive_revision_id(install_manifest)
        return _InstallInputs(
            workspace_id=binding.metadata["workspace_id"],
            generation=binding.metadata["generation"],
            base_revision=binding.current["revision_id"],
            revision_id=revision_id,
            tree_sha256=tree_sha256,
            operation_id=operation_id,
            bundle_id=validated_bundle_id,
            project_slug=project_slug,
            target_relative=target,
            bundle_sha256=str(manifest["bundle_sha256"]),
            files=files,
            entries=entries,
            intent={
                "schema_version": 1,
                "kind": "BOOTSTRAP",
                "operation_id": operation_id,
                "workspace_id": binding.metadata["workspace_id"],
                "generation": binding.metadata["generation"],
                "base_revision": binding.current["revision_id"],
                "next_revision": revision_id,
                "tree_sha256": tree_sha256,
                "phase": "PREPARED",
                "target_relative": target,
                "old_sha256": None,
                "new_sha256": str(manifest["bundle_sha256"]),
            },
        )

    @staticmethod
    def _install_file_record(entry: Mapping[str, Any], project_slug: str) -> dict[str, Any]:
        """One bundle file, re-validated as a path inside this project."""
        path = str(entry["path"])
        parts = tuple(path.split("/"))
        if len(parts) < 3 or parts[:2] != (_INSTALL_ROOT, project_slug):
            raise SupervisorError("INPUT_POLICY")
        if any(part in {"", ".", ".."} or part.startswith(".") for part in parts):
            raise SupervisorError("INPUT_POLICY")
        if any(part in _PROTECTED_COMPONENTS for part in parts):
            raise SupervisorError("INPUT_POLICY")
        return {
            "path": path,
            "relative_path": "/".join(parts[2:]),
            "sha256": str(entry["sha256"]),
            "size": int(entry["size"]),
            "mode": int(entry["mode"]),
        }

    @staticmethod
    def _install_entries(
        base_entries: Sequence[Mapping[str, Any]], files: Sequence[Mapping[str, Any]]
    ) -> tuple[dict[str, Any], ...]:
        """The complete post-install tree: base plus this project, nothing else.

        Directories this install creates are `_BUNDLE_DIRECTORY_MODE`; a
        directory that already exists keeps its recorded base entry, so an
        existing `worklogs` mode is preserved instead of silently rewritten.
        """
        by_path = {str(entry["path"]): dict(entry) for entry in base_entries if not entry["deleted"]}
        needed: set[str] = set()
        for record in files:
            parts = str(record["path"]).split("/")[:-1]
            for depth in range(1, len(parts) + 1):
                needed.add("/".join(parts[:depth]))
        for path in sorted(needed):
            if path not in by_path:
                by_path[path] = {
                    "path": path,
                    "type": "directory",
                    "mode": _BUNDLE_DIRECTORY_MODE,
                    "size": 0,
                    "sha256": None,
                    "deleted": False,
                    "link_target": None,
                }
        for record in files:
            if str(record["path"]) in by_path:
                raise SupervisorError("COLLISION")  # a bundle never overwrites bytes
            by_path[str(record["path"])] = {
                "path": str(record["path"]),
                "type": "file",
                "mode": int(record["mode"]),
                "size": int(record["size"]),
                "sha256": str(record["sha256"]),
                "deleted": False,
                "link_target": None,
            }
        # `_Capture.finish` orders entries by plain path string, and the tree
        # digest is taken over that list: reproducing it exactly is what makes
        # the expected tree byte-identical to the snapshot the revision is
        # written from. (Component-wise order would put `a/b` before `a.md`.)
        return tuple(by_path[path] for path in sorted(by_path))

    def _install_destination(self, root: int, relative: str) -> tuple[int, list[str]]:
        """Open (creating) every component above the leaf; never follow a link."""
        try:
            parts = _parts(relative, self._limits.max_depth)
        except ViewIOError as error:
            raise SupervisorError(error.code) from None
        if any(part in _PROTECTED_COMPONENTS for part in parts) or any(
            parts[: len(exclusion)] == exclusion for exclusion in self._excluded
        ):
            raise SupervisorError("PATH_DENIED")
        fd = os.dup(root)
        created: list[str] = []
        try:
            for index, part in enumerate(parts[:-1]):
                try:
                    child = os.open(part, _DIRECTORY, dir_fd=fd)
                except FileNotFoundError:
                    os.mkdir(part, _BUNDLE_DIRECTORY_MODE, dir_fd=fd)
                    child = os.open(part, _DIRECTORY, dir_fd=fd)
                    os.fchmod(child, _BUNDLE_DIRECTORY_MODE)
                    created.append("/".join(parts[: index + 1]))
                os.close(fd)
                fd = child
            return fd, created
        except OSError:
            os.close(fd)
            raise SupervisorError("PATH_DENIED") from None
        except BaseException:
            os.close(fd)
            raise

    def _install_stage(self, binding: _Binding, inputs: _InstallInputs, deadline: float) -> int:
        """Copy the bundle into project scratch, fsynced, before the rename.

        Staging inside the canonical root is what makes the next step a real
        same-filesystem `renameat2(RENAME_NOREPLACE)`; the bundle itself may sit
        on another filesystem and is never moved, mutated or consumed.
        """
        scratch = self._temporary_directory(binding.source)
        try:
            self._discard_stage(scratch, inputs.operation_id)
            os.mkdir(inputs.operation_id, _BUNDLE_DIRECTORY_MODE, dir_fd=scratch)
            stage = os.open(inputs.operation_id, _DIRECTORY, dir_fd=scratch)
            try:
                os.fchmod(stage, _BUNDLE_DIRECTORY_MODE)
                bundles = os.open("bundles", _DIRECTORY, dir_fd=binding.fd)
                try:
                    bundle = os.open(inputs.bundle_id, _DIRECTORY, dir_fd=bundles)
                    try:
                        for record in inputs.files:
                            _budget(deadline)
                            self._install_copy(bundle, stage, record, deadline)
                    finally:
                        os.close(bundle)
                finally:
                    os.close(bundles)
                os.fsync(stage)
            finally:
                os.close(stage)
            return scratch
        except BaseException:
            os.close(scratch)
            raise

    def _install_copy(self, bundle: int, stage: int, record: Mapping[str, Any], deadline: float) -> None:
        """Copy one file, proving size and digest against the stored manifest."""
        parts = str(record["relative_path"]).split("/")
        parent = os.dup(stage)
        try:
            for part in parts[:-1]:
                try:
                    os.mkdir(part, _BUNDLE_DIRECTORY_MODE, dir_fd=parent)
                except FileExistsError:
                    pass
                child = os.open(part, _DIRECTORY, dir_fd=parent)
                os.fchmod(child, _BUNDLE_DIRECTORY_MODE)
                os.close(parent)
                parent = child
            source = self._open_relative(bundle, str(record["path"]))
            target = -1
            try:
                target = os.open(
                    parts[-1],
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                    int(record["mode"]),
                    dir_fd=parent,
                )
                os.fchmod(target, int(record["mode"]))
                digest = hashlib.sha256()
                size = 0
                while True:
                    _budget(deadline)
                    raw = os.read(source, 65536)
                    if not raw:
                        break
                    size += len(raw)
                    digest.update(raw)
                    _write_all(target, raw)
                if size != record["size"] or digest.hexdigest() != record["sha256"]:
                    raise SupervisorError("CORRUPT_STATE")  # stored bytes are not the manifest
                os.fsync(target)
            finally:
                if target != -1:
                    os.close(target)
                os.close(source)
            os.fsync(parent)
        finally:
            os.close(parent)

    def _install_abort(self, binding: _Binding, inputs: _InstallInputs, scratch: int, created: Sequence[str]) -> None:
        """Discard only what this attempt created, before the irreversible step.

        Cleanup failures are deliberately not raised over the refusal that
        caused them: a leftover intent blocks the workspace visibly on the next
        call, while a masked `COLLISION` would misreport why nothing happened.
        """
        try:
            if scratch != -1:
                self._discard_stage(scratch, inputs.operation_id)
            for path in reversed(created):  # deepest first
                try:
                    parts = path.split("/")
                    parent = os.open(
                        "." if len(parts) == 1 else "/".join(parts[:-1]), _DIRECTORY, dir_fd=binding.source
                    )
                    try:
                        os.rmdir(parts[-1], dir_fd=parent)
                    finally:
                        os.close(parent)
                except OSError:
                    pass  # not ours to empty: someone else's bytes already live here
            if self._read_intent(binding.fd) is not None:
                self._clear_intent(binding.fd)
        except (OSError, SupervisorError):
            pass  # the original refusal is the fact the caller must see

    def _discard_stage(self, scratch: int, name: str) -> None:
        """Remove this operation's own staging directory, if a prior attempt left one."""
        try:
            info = os.stat(name, dir_fd=scratch, follow_symlinks=False)
        except FileNotFoundError:
            return
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise SupervisorError("PATH_DENIED")  # not the scratch this operation owns
        directory = os.open(name, _DIRECTORY, dir_fd=scratch)
        try:
            self._discard_tree(directory)
        finally:
            os.close(directory)
        os.rmdir(name, dir_fd=scratch)

    def _discard_tree(self, directory: int, depth: int = 0) -> None:
        """Remove this operation's own staging entries, bounded by `max_depth`.

        Never follows a link and never recurses past the depth the copy could
        have created, so a crafted entry cannot turn cleanup into a traversal.
        """
        if depth > self._limits.max_depth:
            raise SupervisorError("PATH_DENIED")
        for child in os.listdir(directory):
            info = os.stat(child, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                nested = os.open(child, _DIRECTORY, dir_fd=directory)
                try:
                    self._discard_tree(nested, depth + 1)
                finally:
                    os.close(nested)
                os.rmdir(child, dir_fd=directory)
            else:
                os.unlink(child, dir_fd=directory)

    def _install_finish(self, binding: _Binding, inputs: _InstallInputs, deadline: float) -> dict[str, Any]:
        """Revision, pointer, proof, DONE — all forward-only after the rename."""
        try:
            self._install_write_revision(binding, inputs, deadline)
            self._install_commit_current(binding, inputs)
            _, digest = self._snapshot(binding.source, None, deadline)
            if digest != inputs.tree_sha256:
                raise SupervisorError("CORRUPT_STATE")
            self._set_intent_phase(binding.fd, inputs.intent, "DONE")
        except OSError:
            # The directory exists; only forward recovery may finish this.
            self._healthy = False
            raise SupervisorError("DURABILITY_UNKNOWN") from None
        except SupervisorError as error:
            self._healthy = False
            if error.code == "CORRUPT_STATE":
                raise  # determinate: the bytes on disk are not the manifest's
            raise SupervisorError("DURABILITY_UNKNOWN") from None
        self._clear_intent(binding.fd)
        return {
            "workspace_id": inputs.workspace_id,
            "revision_id": inputs.revision_id,
            "tree_sha256": inputs.tree_sha256,
            "operation_id": inputs.operation_id,
            "projection_complete": True,
        }

    def _install_write_revision(self, binding: _Binding, inputs: _InstallInputs, deadline: float) -> None:
        """Write `revisions/<derived>` from the canonical tree the install created."""
        stage = self._state / "pending" / uuid4().hex
        installed = False
        try:
            with _private_artifact_directory(stage) as stage_fd:
                os.mkdir("revisions", 0o700, dir_fd=stage_fd)
                staged = os.open("revisions", _DIRECTORY, dir_fd=stage_fd)
                try:
                    os.mkdir(inputs.revision_id, 0o700, dir_fd=staged)
                    revision = os.open(inputs.revision_id, _DIRECTORY, dir_fd=staged)
                    try:
                        os.mkdir("data", 0o700, dir_fd=revision)
                        data = os.open("data", _DIRECTORY, dir_fd=revision)
                        try:
                            entries, digest = self._snapshot(binding.source, data, deadline)
                        finally:
                            os.close(data)
                        _require_manifest_match(entries, inputs.entries)
                        if digest != inputs.tree_sha256:
                            raise SupervisorError("CORRUPT_STATE")
                        tree = {
                            "schema_version": 1,
                            "revision_id": inputs.revision_id,
                            "tree_sha256": inputs.tree_sha256,
                            "entries": [dict(entry) for entry in inputs.entries],
                        }
                        _replace_private_bytes(revision, "tree.json", _canonical(tree))
                        os.fsync(revision)
                    finally:
                        os.close(revision)
                    os.fsync(staged)
                    revisions = os.open("revisions", _DIRECTORY, dir_fd=binding.fd)
                    try:
                        _budget(deadline)
                        _rename_directory(staged, inputs.revision_id, revisions, inputs.revision_id)
                        installed = True
                        os.fsync(revisions)
                    finally:
                        os.close(revisions)
                finally:
                    os.close(staged)
        finally:
            if not installed and stage.exists():
                shutil.rmtree(stage)  # Only this uninstalled, service-private staging tree.

    def _install_commit_current(self, binding: _Binding, inputs: _InstallInputs) -> None:
        """CAS the pointer from the base revision to the installed one."""
        try:
            current = _read_json(binding.fd, "current.json", _CURRENT, 1024**2)
        except (OSError, SupervisorError):
            raise SupervisorError("DURABILITY_UNKNOWN") from None
        if current["revision_id"] != inputs.base_revision:
            raise SupervisorError("STALE_REVISION")
        updated = {
            "schema_version": 1,
            "workspace_id": inputs.workspace_id,
            "generation": inputs.generation,
            "revision_id": inputs.revision_id,
            "tree_sha256": inputs.tree_sha256,
        }
        try:
            _replace_private_bytes(binding.fd, "current.json", encode_json(updated))
            if _read_json(binding.fd, "current.json", _CURRENT, 1024**2) != updated:
                raise SupervisorError("DURABILITY_UNKNOWN")
        except (OSError, SupervisorError):
            raise SupervisorError("DURABILITY_UNKNOWN") from None
        binding.current = updated
        # Durable before the proof, so recovery dispatches instead of inferring.
        self._set_intent_phase(binding.fd, inputs.intent, "PROJECTING")

    # -- Publication (E269 / CT106): intent, pointer, projection ------------

    def prepare_publish(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        view_ref: ViewRef,
        capability: str,
        sealed_manifest_id: str,
        expected_base_revision: str,
        operation_id: str,
        manifest_reader: Callable[[int, str | None, tuple[dict[str, Any], ...]], dict[str, Any]],
        deadline: float,
    ) -> _PublishInputs:
        """Prove every precondition and read the sealed manifest. Writes nothing.

        Ordering is deliberate and load-bearing (E269 R1): **state first, then
        equality**. A `PUBLISHED` view's `current.revision_id` *is* the derived
        revision, so checking base equality before dispatch would refuse the
        very retry replay exists for.

        `manifest_reader` receives this view's directory descriptor, the plan
        path and the base entries, and must return a validated manifest without
        retaining the descriptor: the filesystem stays the authority's, the
        manifest rules stay `publication`'s.
        """
        _hex_id(operation_id, "op-")
        _hex_id(expected_base_revision, "rev-")
        with self._transaction(peer, deadline):
            view = self._proof_only(peer, namespace, view_ref, capability)
            if not isinstance(view, _ProjectView):
                raise SupervisorError("VIEW_CLOSED")
            state = view.record["state"]
            if state == "UNKNOWN":
                raise SupervisorError("TERMINALITY_UNKNOWN")
            if state not in {"SEALED", "PUBLISHED"}:
                raise SupervisorError("VIEW_CLOSED")
            if not self._gate(view_ref).closed:
                raise SupervisorError("VIEW_CLOSED")
            if _terminal_record(view.directory) is None:
                raise SupervisorError("TERMINALITY_UNKNOWN")
            try:
                view.context.recheck()
            except ExecutionContractError:
                raise SupervisorError("INPUT_POLICY") from None
            binding = self._binding(view_ref.workspace_id)
            self._recheck(binding)
            if (
                binding.metadata["status"] != "OWNED"
                or binding.grant is None
                or binding.metadata["active_actor"] != namespace.to_dict()
                or binding.principal != peer.principal
                or binding.metadata["generation"] != view_ref.generation
            ):
                raise SupervisorError("STALE_GENERATION")
            if sealed_manifest_id != view.record["sealed_manifest_id"]:
                raise SupervisorError("STALE_REVISION")
            if expected_base_revision != view_ref.base_revision:
                raise SupervisorError("STALE_REVISION")
            if state == "SEALED" and binding.current["revision_id"] != view_ref.base_revision:
                raise SupervisorError("STALE_REVISION")
            # The base entries are ALWAYS loaded, not only on the first publish:
            # the replay path re-validates the same manifest with the same
            # validator, and three of that validator's rules (tombstones,
            # symlinks, the plan boundary) compare each entry against its base.
            # An empty base would refuse every manifest carrying a deletion, a
            # link or a plan — i.e. the replay would fail precisely where it
            # matters. Revisions are retained forever (no GC), so the base is
            # always available; if a future GC removes it, replay must fail
            # closed rather than validate against nothing.
            with self._revision(binding, view_ref.base_revision, deadline) as (_, base, _child):
                base_entries: tuple[dict[str, Any], ...] = tuple(dict(entry) for entry in base["entries"])
            # Canonical bytes must still be the revision this publish extends.
            # Reuses the one established drift check (D4); its global
            # "unhealthy" consequence is deliberate and tested.
            self._unchanged(binding, deadline)
            plan = view.record.get("plan_ref")
            plan_path = None if plan is None else plan["workspace_relative_path"]
            manifest = manifest_reader(view.directory, plan_path, base_entries)
            if (
                manifest["workspace_id"] != view_ref.workspace_id
                or manifest["view_id"] != view_ref.view_id
                or manifest["base_revision"] != view_ref.base_revision
                or manifest["generation"] != view_ref.generation
            ):
                raise SupervisorError("CORRUPT_STATE")
            revision_id = _derive_revision_id(manifest)
            if state == "PUBLISHED":
                if binding.current["revision_id"] != revision_id:
                    raise SupervisorError("CORRUPT_STATE")
            else:
                self._probe_writable(binding)
                self._preflight_projection(binding, manifest["entries"])
            return _PublishInputs(
                view_ref=view_ref,
                record=dict(view.record),
                directory=view.directory,
                entries=tuple(dict(entry) for entry in manifest["entries"]),
                revision_id=revision_id,
                tree_sha256=str(manifest["tree_sha256"]),
                base_revision=view_ref.base_revision,
                generation=binding.metadata["generation"],
                operation_id=operation_id,
            )

    def materialize_publication(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, capability: str, inputs: _PublishInputs, deadline: float
    ) -> None:
        """Stage the revision from the sealed manifest, install it, write intent.

        No canonical byte is written here and `current.json` is untouched. The
        copy is verified entry-by-entry against the manifest **before** install,
        so a source that moved after the barrier cannot land a revision.
        """
        with self._transaction(peer, deadline):
            view, binding = self._publish_owner(peer, namespace, capability, inputs)
            pending = self._read_intent(binding.fd)
            if pending is not None and pending["operation_id"] != inputs.operation_id:
                raise SupervisorError("WORKSPACE_BUSY")
            if not self._revision_exists(binding, inputs.revision_id, deadline):
                self._install_revision(binding, view, inputs, deadline)
            self._write_intent(
                binding.fd,
                {
                    "schema_version": 1,
                    "kind": "REVISION",
                    "operation_id": inputs.operation_id,
                    "workspace_id": inputs.view_ref.workspace_id,
                    "generation": inputs.generation,
                    "base_revision": inputs.base_revision,
                    "next_revision": inputs.revision_id,
                    "tree_sha256": inputs.tree_sha256,
                    "phase": "PREPARED",
                    "target_relative": None,
                    "old_sha256": None,
                    "new_sha256": None,
                },
            )

    def commit_revision_current(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, capability: str, inputs: _PublishInputs, deadline: float
    ) -> None:
        """CAS the current pointer to Rnext, then mark the projection phase.

        The pointer replace is the irreversible point. Everything before it is
        discardable; everything after it is forward-only and `current.json`
        alone says whether it happened.
        """
        with self._transaction(peer, deadline):
            _view, binding = self._publish_owner(peer, namespace, capability, inputs)
            intent = self._read_intent(binding.fd)
            if (
                intent is None
                or intent["operation_id"] != inputs.operation_id
                or intent["next_revision"] != inputs.revision_id
                or intent["phase"] != "PREPARED"
            ):
                raise SupervisorError("WORKSPACE_BUSY")
            if binding.metadata["generation"] != inputs.generation:
                raise SupervisorError("STALE_GENERATION")
            try:
                current = _read_json(binding.fd, "current.json", _CURRENT, 1024**2)
            except (OSError, SupervisorError):
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None
            if current["revision_id"] != inputs.base_revision:
                raise SupervisorError("STALE_REVISION")
            updated = {
                "schema_version": 1,
                "workspace_id": inputs.view_ref.workspace_id,
                "generation": inputs.generation,
                "revision_id": inputs.revision_id,
                "tree_sha256": inputs.tree_sha256,
            }
            try:
                _replace_private_bytes(binding.fd, "current.json", encode_json(updated))
                if _read_json(binding.fd, "current.json", _CURRENT, 1024**2) != updated:
                    raise SupervisorError("DURABILITY_UNKNOWN")
            except (OSError, SupervisorError):
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None
            binding.current = updated
            try:
                # Durable BEFORE the first canonical byte, so recovery
                # dispatches instead of inferring "projection may be partial".
                self._set_intent_phase(binding.fd, intent, "PROJECTING")
            except (OSError, SupervisorError):
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None

    def project_publication(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, capability: str, inputs: _PublishInputs, deadline: float
    ) -> dict[str, Any]:
        """Apply the committed revision to canonical, prove it, then publish.

        Idempotent by construction: every entry that already matches is skipped,
        so a resumed projection after a crash converges instead of rewriting.
        """
        with self._transaction(peer, deadline):
            view, binding = self._publish_owner(peer, namespace, capability, inputs)
            intent = self._read_intent(binding.fd)
            if intent is None or intent["next_revision"] != inputs.revision_id or intent["phase"] != "PROJECTING":
                raise SupervisorError("WORKSPACE_BUSY")
            if binding.current["revision_id"] != inputs.revision_id:
                raise SupervisorError("CORRUPT_STATE")
            published = {**view.record, "state": "PUBLISHED"}
            try:
                self._project_entries(binding, view, inputs, deadline)
                self._verify_projection(binding, inputs, deadline)
                self._set_intent_phase(binding.fd, intent, "DONE")
                self._clear_intent(binding.fd)
                _replace_private_bytes(view.directory, "view.json", encode_json(published))
                if _read_json(view.directory, "view.json", _VIEW_RECORD, 1024**2) != published:
                    raise SupervisorError("DURABILITY_UNKNOWN")
            except (OSError, SupervisorError):
                self._healthy = False
                raise SupervisorError("DURABILITY_UNKNOWN") from None
            view.record = published
            return self._published_receipt(inputs)

    def verify_publication(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, capability: str, inputs: _PublishInputs, deadline: float
    ) -> dict[str, Any]:
        """Replay: prove an already-published revision without committing again."""
        with self._transaction(peer, deadline):
            view, binding = self._publish_owner(peer, namespace, capability, inputs)
            if view.record["state"] != "PUBLISHED" or binding.current["revision_id"] != inputs.revision_id:
                raise SupervisorError("CORRUPT_STATE")
            self._unchanged(binding, deadline)
            self._verify_projection(binding, inputs, deadline)
            return self._published_receipt(inputs)

    def abandon_publication(
        self, peer: PeerIdentity, namespace: NamespaceRef, *, capability: str, inputs: _PublishInputs, deadline: float
    ) -> None:
        """Discard this attempt's uncommitted revision; never touch committed bytes."""
        with self._transaction(peer, deadline):
            _view, binding = self._publish_owner(peer, namespace, capability, inputs)
            if binding.current["revision_id"] != inputs.base_revision:
                return
            intent = self._read_intent(binding.fd)
            if intent is not None and intent["operation_id"] == inputs.operation_id:
                self._clear_intent(binding.fd)
            self._discard_revision(binding, inputs.revision_id)

    def _publish_owner(
        self, peer: PeerIdentity, namespace: NamespaceRef, capability: str, inputs: _PublishInputs
    ) -> tuple[_ProjectView, _Binding]:
        """Re-prove the exact view, actor and epoch on every phase boundary."""
        view = self._proof_only(peer, namespace, inputs.view_ref, capability)
        if not isinstance(view, _ProjectView):
            raise SupervisorError("VIEW_CLOSED")
        binding = self._binding(inputs.view_ref.workspace_id)
        self._recheck(binding)
        if (
            binding.metadata["status"] != "OWNED"
            or binding.grant is None
            or binding.metadata["active_actor"] != namespace.to_dict()
            or binding.principal != peer.principal
            or binding.metadata["generation"] != inputs.generation
        ):
            raise SupervisorError("STALE_GENERATION")
        return view, binding

    @staticmethod
    def _published_receipt(inputs: _PublishInputs) -> dict[str, Any]:
        return {
            "workspace_id": inputs.view_ref.workspace_id,
            "revision_id": inputs.revision_id,
            "tree_sha256": inputs.tree_sha256,
            "operation_id": inputs.operation_id,
            "projection_complete": True,
        }

    def _probe_writable(self, binding: _Binding) -> None:
        """Refuse a canonical root we could not project into, before any write (Q81)."""
        try:
            mount = os.fstatvfs(binding.source)
        except OSError:
            self._healthy = False
            raise SupervisorError("DURABILITY_UNKNOWN") from None
        if mount.f_flag & os.ST_RDONLY:
            raise SupervisorError("PATH_DENIED")
        info = os.fstat(binding.source)
        if not stat.S_ISDIR(info.st_mode):
            raise SupervisorError("PATH_DENIED")
        if os.geteuid() == 0:
            return
        if info.st_uid == os.geteuid():
            bits = (info.st_mode >> 6) & 0o7
        elif info.st_gid == os.getegid():
            bits = (info.st_mode >> 3) & 0o7
        else:
            bits = info.st_mode & 0o7
        if bits & 0o3 != 0o3:
            raise SupervisorError("PATH_DENIED")

    def _preflight_projection(self, binding: _Binding, entries: Sequence[Mapping[str, Any]]) -> None:
        """Refuse an impossible destination type BEFORE the irreversible pointer (D7).

        Every type conflict here is predictable at prepare time; discovering it
        during projection would turn a policy refusal into `DURABILITY_UNKNOWN`
        plus a half-projected tree, which is the one outcome this design exists
        to avoid.
        """
        for entry in entries:
            if entry["deleted"]:
                continue
            try:
                parent = self._project_parent(binding.source, entry["path"])
            except FileNotFoundError:
                continue  # A missing ancestor is created by projection.
            except OSError:
                raise SupervisorError("PATH_DENIED") from None
            try:
                name = entry["path"].rsplit("/", 1)[-1]
                try:
                    info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if entry["type"] == "directory":
                    if not stat.S_ISDIR(info.st_mode):
                        raise SupervisorError("PATH_DENIED")
                elif entry["type"] == "symlink":
                    if not stat.S_ISLNK(info.st_mode) or os.readlink(name, dir_fd=parent) != entry["link_target"]:
                        raise SupervisorError("PATH_DENIED")
                elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise SupervisorError("PATH_DENIED")
            finally:
                os.close(parent)

    def _revision_exists(self, binding: _Binding, revision_id: str, deadline: float) -> bool:
        revisions = os.open("revisions", _DIRECTORY, dir_fd=binding.fd)
        try:
            try:
                child = os.open(revision_id, _DIRECTORY, dir_fd=revisions)
            except FileNotFoundError:
                return False
            os.close(child)
        finally:
            os.close(revisions)
        with self._revision(binding, revision_id, deadline) as (_data, tree, _child):
            return bool(tree["revision_id"] == revision_id)

    def _install_revision(self, binding: _Binding, view: _ProjectView, inputs: _PublishInputs, deadline: float) -> None:
        """Copy the frozen view source into revisions/<derived>, verified, then rename."""
        source = os.open("source", _DIRECTORY, dir_fd=view.directory)
        stage = self._state / "pending" / uuid4().hex
        installed = False
        try:
            if _identity(os.fstat(source)) != _identity(os.fstat(view.source)):
                raise SupervisorError("CORRUPT_STATE")
            with _private_artifact_directory(stage) as stage_fd:
                os.mkdir("revisions", 0o700, dir_fd=stage_fd)
                staged = os.open("revisions", _DIRECTORY, dir_fd=stage_fd)
                try:
                    os.mkdir(inputs.revision_id, 0o700, dir_fd=staged)
                    revision = os.open(inputs.revision_id, _DIRECTORY, dir_fd=staged)
                    try:
                        os.mkdir("data", 0o700, dir_fd=revision)
                        data = os.open("data", _DIRECTORY, dir_fd=revision)
                        try:
                            entries, _digest = self._snapshot(source, data, deadline)
                        finally:
                            os.close(data)
                        _require_manifest_match(entries, inputs.entries)
                        # `_TREE` pins `deleted` to False: tombstones are a
                        # manifest/transport fact and never live in a revision.
                        tree = {
                            "schema_version": 1,
                            "revision_id": inputs.revision_id,
                            "tree_sha256": inputs.tree_sha256,
                            "entries": [dict(entry) for entry in inputs.entries if not entry["deleted"]],
                        }
                        _replace_private_bytes(revision, "tree.json", _canonical(tree))
                        os.fsync(revision)
                    finally:
                        os.close(revision)
                    os.fsync(staged)
                    revisions = os.open("revisions", _DIRECTORY, dir_fd=binding.fd)
                    try:
                        _budget(deadline)
                        _rename_directory(staged, inputs.revision_id, revisions, inputs.revision_id)
                        installed = True
                        os.fsync(revisions)
                    finally:
                        os.close(revisions)
                finally:
                    os.close(staged)
        finally:
            os.close(source)
            if not installed and stage.exists():
                shutil.rmtree(stage)  # Only this uninstalled, service-private staging tree.

    def _project_entries(self, binding: _Binding, view: _ProjectView, inputs: _PublishInputs, deadline: float) -> None:
        """Apply live entries (directories, files, links) then tombstones."""
        self._sweep_temporaries(binding.source)
        directories = sorted(
            (entry for entry in inputs.entries if entry["type"] == "directory" and not entry["deleted"]),
            key=lambda entry: (entry["path"].count("/"), entry["path"]),
        )
        for entry in directories:
            _budget(deadline)
            self._project_directory(binding, entry)
        for entry in inputs.entries:
            if entry["deleted"] or entry["type"] == "directory":
                continue
            _budget(deadline)
            if entry["type"] == "symlink":
                self._project_link(binding, entry)
            else:
                self._project_file(binding, view, entry, deadline)
        for entry in sorted(
            (entry for entry in inputs.entries if entry["deleted"]),
            key=lambda entry: entry["path"].count("/"),
            reverse=True,
        ):
            _budget(deadline)
            self._project_tombstone(binding, entry)

    def _project_directory(self, binding: _Binding, entry: dict[str, Any]) -> None:
        parent = self._project_parent(binding.source, entry["path"])
        try:
            name = entry["path"].rsplit("/", 1)[-1]
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                os.mkdir(name, 0o700, dir_fd=parent)
            else:
                if not stat.S_ISDIR(info.st_mode):
                    raise SupervisorError("PATH_DENIED")
            child = os.open(name, _DIRECTORY, dir_fd=parent)
            try:
                if stat.S_IMODE(os.fstat(child).st_mode) != entry["mode"]:
                    os.fchmod(child, entry["mode"])
                os.fsync(child)
            finally:
                os.close(child)
            os.fsync(parent)
        finally:
            os.close(parent)

    def _project_link(self, binding: _Binding, entry: dict[str, Any]) -> None:
        parent = self._project_parent(binding.source, entry["path"])
        try:
            name = entry["path"].rsplit("/", 1)[-1]
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                os.symlink(entry["link_target"], name, dir_fd=parent)
                os.fsync(parent)
                return
            if not stat.S_ISLNK(info.st_mode):
                raise SupervisorError("PATH_DENIED")
            if os.readlink(name, dir_fd=parent) != entry["link_target"]:
                raise SupervisorError("PATH_DENIED")
        finally:
            os.close(parent)

    def _temporary_directory(self, root: int) -> int:
        """Open (creating) the projection scratch dir under the canonical root.

        `.fa` is excluded from every walk at any depth, so an interrupted
        projection's debris is *invisible* to `_unchanged` and
        `_verify_projection` instead of poisoning them — the difference between a
        resumable projection and a workspace that quarantines itself. It lives
        inside the canonical root because `os.replace` is only atomic within one
        filesystem, and `pending/` staging may be on another.
        """
        fd = os.dup(root)
        try:
            for name in _PROJECTION_SCRATCH:
                try:
                    os.mkdir(name, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                child = os.open(name, _DIRECTORY, dir_fd=fd)
                os.close(fd)
                fd = child
            # Not `_private`: `.fa` is the project's own artifact directory and
            # legitimately carries the project's mode (a 0755 `.fa` must not
            # refuse every publish). This directory is inside the user's tree and
            # is therefore no security boundary -- it only has to be a real
            # directory of ours (`O_NOFOLLOW` above already refused a link).
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise SupervisorError("PATH_DENIED")
            return fd
        except OSError:
            os.close(fd)
            raise SupervisorError("PATH_DENIED") from None
        except SupervisorError:
            os.close(fd)
            raise

    def _sweep_temporaries(self, root: int) -> None:
        """Discard only our own abandoned temporaries; bounded, one directory."""
        directory = self._temporary_directory(root)
        try:
            for name in os.listdir(directory):
                if not (name.startswith(".") and name.endswith(_TEMPORARY_SUFFIX)):
                    continue
                try:
                    info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid():
                        os.unlink(name, dir_fd=directory)
                except FileNotFoundError:
                    continue
            os.fsync(directory)
        finally:
            os.close(directory)

    def _project_file(self, binding: _Binding, view: _ProjectView, entry: dict[str, Any], deadline: float) -> None:
        parent = self._project_parent(binding.source, entry["path"])
        scratch = -1
        try:
            name = entry["path"].rsplit("/", 1)[-1]
            if self._project_matches(parent, name, entry):
                return
            source = self._open_relative(view.source, entry["path"])
            scratch = self._temporary_directory(binding.source)
            temporary = f".{name}.{uuid4().hex}{_TEMPORARY_SUFFIX}"
            created = False
            target = -1
            try:
                target = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                    0o600,
                    dir_fd=scratch,
                )
                created = True
                digest = hashlib.sha256()
                size = 0
                while True:
                    _budget(deadline)
                    raw = os.read(source, 65536)
                    if not raw:
                        break
                    size += len(raw)
                    if size > self._limits.max_file_bytes:
                        raise SupervisorError("INPUT_POLICY")
                    digest.update(raw)
                    _write_all(target, raw)
                if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
                    raise SupervisorError("CORRUPT_STATE")
                os.fchmod(target, entry["mode"])
                os.fsync(target)
                os.close(target)
                target = -1
                os.replace(temporary, name, src_dir_fd=scratch, dst_dir_fd=parent)
                created = False
                os.fsync(parent)
            except OSError:
                raise SupervisorError("DURABILITY_UNKNOWN") from None
            finally:
                if target != -1:
                    os.close(target)
                os.close(source)
                if created:
                    try:
                        os.unlink(temporary, dir_fd=scratch)
                    except FileNotFoundError:
                        pass
        finally:
            if scratch != -1:
                os.close(scratch)
            os.close(parent)

    @staticmethod
    def _project_matches(parent: int, name: str, entry: dict[str, Any]) -> bool:
        """Idempotence oracle: exact bytes, mode and type, or the entry is rewritten."""
        try:
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return False
        # Type first: a symlink, directory, special file or hard link at a file
        # path is drift or an attack, never something a rewrite may clobber (D7).
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SupervisorError("PATH_DENIED")
        if stat.S_IMODE(info.st_mode) != entry["mode"] or info.st_size != entry["size"]:
            return False
        fd = os.open(name, _FILE, dir_fd=parent)
        try:
            if _fingerprint(info) != _fingerprint(os.fstat(fd)):
                return False
            digest = hashlib.sha256()
            while True:
                raw = os.read(fd, 65536)
                if not raw:
                    break
                digest.update(raw)
            return bool(digest.hexdigest() == entry["sha256"])
        finally:
            os.close(fd)

    def _project_tombstone(self, binding: _Binding, entry: dict[str, Any]) -> None:
        try:
            parent = self._project_parent(binding.source, entry["path"])
        except FileNotFoundError:
            return  # Ancestor already gone: the deletion is complete.
        try:
            name = entry["path"].rsplit("/", 1)[-1]
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                return
            if stat.S_ISDIR(info.st_mode):
                os.rmdir(name, dir_fd=parent)
            elif stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                os.unlink(name, dir_fd=parent)
            else:
                raise SupervisorError("PATH_DENIED")
            os.fsync(parent)
        except OSError:
            raise SupervisorError("DURABILITY_UNKNOWN") from None
        finally:
            os.close(parent)

    def _project_parent(self, root: int, path: str) -> int:
        """Open the entry's parent without following a single component."""
        try:
            parts = _parts(path, self._limits.max_depth)
        except ViewIOError as error:
            raise SupervisorError(error.code) from None
        if any(part in _PROTECTED_COMPONENTS for part in parts):
            raise SupervisorError("PATH_DENIED")
        if any(parts[: len(exclusion)] == exclusion for exclusion in self._excluded):
            raise SupervisorError("PATH_DENIED")
        fd = os.dup(root)
        try:
            for part in parts[:-1]:
                previous = fd
                fd = os.open(part, _DIRECTORY, dir_fd=previous)
                os.close(previous)
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _open_relative(self, root: int, path: str) -> int:
        """Open one existing file under `root`, refusing symlinked components."""
        parent = self._project_parent(root, path)
        try:
            return os.open(path.rsplit("/", 1)[-1], _FILE, dir_fd=parent)
        finally:
            os.close(parent)

    def _verify_projection(self, binding: _Binding, inputs: _PublishInputs, deadline: float) -> None:
        """The complete canonical tree must equal the manifest's live entries."""
        actual, digest = self._snapshot(binding.source, None, deadline)
        live = [dict(entry) for entry in inputs.entries if not entry["deleted"]]
        if len(actual) != len(live):
            raise SupervisorError("CORRUPT_STATE")
        for got, wanted in zip(actual, live, strict=True):
            if got != wanted:
                raise SupervisorError("CORRUPT_STATE")
        if digest != inputs.tree_sha256:
            raise SupervisorError("CORRUPT_STATE")

    def _read_intent(self, fd: int) -> dict[str, Any] | None:
        try:
            return _read_json(fd, "intent.json", _INTENT, 1024**2)
        except FileNotFoundError:
            return None

    def _write_intent(self, fd: int, intent: dict[str, Any]) -> None:
        try:
            _replace_private_bytes(fd, "intent.json", encode_json(intent))
            if _read_json(fd, "intent.json", _INTENT, 1024**2) != intent:
                raise SupervisorError("DURABILITY_UNKNOWN")
        except (OSError, SupervisorError):
            self._healthy = False
            raise SupervisorError("DURABILITY_UNKNOWN") from None

    def _set_intent_phase(self, fd: int, intent: dict[str, Any], phase: str) -> None:
        self._write_intent(fd, {**intent, "phase": phase})

    def _clear_intent(self, fd: int) -> None:
        try:
            os.unlink("intent.json", dir_fd=fd)
            os.fsync(fd)
        except (OSError, SupervisorError):
            self._healthy = False
            raise SupervisorError("DURABILITY_UNKNOWN") from None

    def _discard_revision(self, binding: _Binding, revision_id: str) -> None:
        revisions = os.open("revisions", _DIRECTORY, dir_fd=binding.fd)
        try:
            try:
                child = os.open(revision_id, _DIRECTORY, dir_fd=revisions)
            except FileNotFoundError:
                return
            os.close(child)
        finally:
            os.close(revisions)
        try:
            shutil.rmtree(self._state / "workspaces" / binding.metadata["workspace_id"] / "revisions" / revision_id)
        except OSError:
            self._healthy = False
            raise SupervisorError("DURABILITY_UNKNOWN") from None

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
