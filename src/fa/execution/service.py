"""The composed private-UDS supervisor: one route table over the real owners.

This module is composition, not a second policy engine. Every route either calls
the owner that already implements the operation (`WorkspaceAuthority`,
`publication`, `ViewStopper`) and projects its result to the exact closed reply
schema, or refuses with a closed error code because that owner does not exist
yet. There is no default authority, no permissive fallback, no host-side runner
and no fabricated result: an unrouted or ownerless operation is `BACKEND_UNAVAILABLE`,
which the caller sees as a typed refusal rather than a silent success (E277).

Dormant owners (declared, with the unit that activates each):

- `exec`, `inspect`, `cancel`, `pty_control`: `CellBackend` observes commands but
  returns a `CommandOutcome`, not an `ExecutionReceipt`, and there is no
  independent terminal-barrier (cgroup) observation or worker-control wrapper.
  Activating unit: the receipt issuer + terminal barrier + PTY control unit.
- `handoff`: no `WorkspaceAuthority.handoff` exists at all.
  Activating unit: the owner-handoff unit (terminal/settled source views,
  parent-child namespace proof).
- `register_workspace` with `create=true`: only `register_existing` exists; the
  creating/materializing provisioner is SLICE5's managed acquisition.

`stop_view` is composed with the real `OwnedCellTermination`: a view that never
bound a cell is empty by the journal alone, and a view that did is stopped
through its own record and observed in its cgroup (E278). Without a Docker
configuration the adapter still proves the first case and refuses the second.

Socket ownership belongs here too: the authority takes its single-supervisor
flock and completes startup recovery (`recover_uncertain` + `_load`, which is
forward recovery) BEFORE the listening socket exists, so no request can be
accepted against unreconciled durable state.
"""

from __future__ import annotations

import json
import os
import socket
import stat
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from fa.execution import publication
from fa.execution.backend import CellBackend
from fa.execution.docker import DockerEngine
from fa.execution.plans import ProtectedPlanContext
from fa.execution.profiles import ExecutionProfile, profile_set_sha256
from fa.execution.supervisor import (
    CompletedReplyCache,
    PeerIdentity,
    SupervisorDispatcher,
    SupervisorError,
    ViewStopper,
)
from fa.execution.termination import OwnedCellTermination
from fa.execution.types import (
    Access,
    ExecutionContractError,
    GrantReply,
    NamespaceRef,
    Operation,
    ViewPurpose,
    ViewRef,
    _hex_id,
    _positive_integer,
)
from fa.execution.workspace import InputLimits, WorkspaceAuthority
from fa.inner_loop.plan_admission import PlanRef

# The socket path is a `sun_path`; anything longer cannot be bound at all.
_MAX_SOCKET_PATH_BYTES = 107
_REQUIRED_KEYS = frozenset(
    {
        "state_root",
        "socket_path",
        "controller_uids",
        "approved_roots",
        "profiles",
        "rpc_timeout_ms",
        "lock_timeout_ms",
    }
)
_OPTIONAL_KEYS = frozenset(
    {
        "view_profile_id",
        "excluded_paths",
        "approved_cache",
        "reply_cache_entries",
        "backlog",
        "max_workers",
        "docker_socket",
        "docker_daemon_uid",
        "docker_api_version",
        "docker_timeout_ms",
        "cgroup_root",
        "startup_timeout_ms",
    }
)
_CONFIG_KEYS = _REQUIRED_KEYS | _OPTIONAL_KEYS


@dataclass(frozen=True)
class ServiceConfig:
    """Operator-supplied deployment facts; every field is explicit, no defaults.

    `profiles` are the approved cell profiles the dispatcher may route; the
    digest published by `health` is derived from these exact objects, so an
    edited file that was never reloaded cannot appear to have been applied.
    `view_profile_id` selects the single profile the authority binds to a view
    (cell dispatch stays closed when it is null).
    """

    state_root: Path
    socket_path: Path
    controller_uids: frozenset[int]
    approved_roots: Mapping[str, Path]
    profiles: tuple[ExecutionProfile, ...]
    rpc_timeout_ms: int
    lock_timeout_ms: int
    view_profile_id: str | None = None
    excluded_paths: tuple[str, ...] = ()
    approved_cache: Path | None = None
    reply_cache_entries: int = 1024
    backlog: int = 16
    max_workers: int = 8
    # All four Docker facts or none: a partial daemon configuration would be a
    # default authority for cell lifecycle, so it is refused instead.
    docker_socket: Path | None = None
    docker_daemon_uid: int | None = None
    docker_api_version: str | None = None
    docker_timeout_ms: int | None = None
    cgroup_root: Path = Path("/sys/fs/cgroup")
    startup_timeout_ms: int = 5000

    def __post_init__(self) -> None:
        _require_path(self.state_root)
        _require_socket_path(self.socket_path, self.state_root, self.approved_roots)
        if not self.controller_uids or any(type(uid) is not int or uid < 0 for uid in self.controller_uids):
            raise ExecutionContractError
        _require_roots(self.approved_roots)
        if not self.profiles or len({profile.profile_id for profile in self.profiles}) != len(self.profiles):
            raise ExecutionContractError
        for value in (self.rpc_timeout_ms, self.lock_timeout_ms, self.reply_cache_entries, self.backlog):
            _positive_integer(value)
        if type(self.max_workers) is not int or not 1 <= self.max_workers <= 64:
            raise ExecutionContractError
        if self.view_profile_id is not None and self.view_profile_id not in {
            profile.profile_id for profile in self.profiles
        }:
            raise ExecutionContractError
        if any(not isinstance(path, str) for path in self.excluded_paths):
            raise ExecutionContractError
        if self.approved_cache is not None and not isinstance(self.approved_cache, Path):
            raise ExecutionContractError
        _require_docker_facts(
            self.docker_socket, self.docker_daemon_uid, self.docker_api_version, self.docker_timeout_ms
        )
        _require_path(self.cgroup_root)
        _positive_integer(self.startup_timeout_ms)


def _require_path(value: object) -> None:
    if not isinstance(value, Path) or not value.is_absolute() or ".." in value.parts or value == Path("/"):
        raise ExecutionContractError


def _require_socket_path(path: object, state_root: Path, approved_roots: object) -> None:
    """One private socket, bounded by `sun_path`, never inside a mounted root."""
    _require_path(path)
    if not isinstance(path, Path) or len(str(path).encode("utf-8")) > _MAX_SOCKET_PATH_BYTES:
        raise ExecutionContractError
    if path.is_relative_to(state_root) or state_root.is_relative_to(path):
        raise ExecutionContractError
    if isinstance(approved_roots, Mapping) and any(
        path.is_relative_to(root) or root.is_relative_to(path)
        for root in approved_roots.values()
        if isinstance(root, Path)
    ):
        raise ExecutionContractError


def _require_roots(approved_roots: object) -> None:
    if not isinstance(approved_roots, Mapping) or not approved_roots:
        raise ExecutionContractError
    for root_id, root in approved_roots.items():
        _require_path(root)
        if not isinstance(root_id, str):
            raise ExecutionContractError


def _require_docker_facts(
    socket_path: Path | None, daemon_uid: int | None, api_version: str | None, timeout_ms: int | None
) -> None:
    """All four daemon facts or none: a partial one would be a default authority."""
    facts = (socket_path, daemon_uid, api_version, timeout_ms)
    if all(fact is None for fact in facts):
        return
    if any(fact is None for fact in facts):
        raise ExecutionContractError
    if not isinstance(socket_path, Path):
        raise ExecutionContractError
    _require_path(socket_path)
    if type(daemon_uid) is not int or daemon_uid < 0 or not isinstance(api_version, str):
        raise ExecutionContractError
    if type(timeout_ms) is not int:
        raise ExecutionContractError
    _positive_integer(timeout_ms)


def load_config(document: object) -> ServiceConfig:
    """Build one config from an already-parsed document; unknown keys are refused.

    Strict on purpose: a typo in an operator file must fail the service, never
    silently fall back to a default authority, root or profile.
    """
    if type(document) is not dict or not _REQUIRED_KEYS <= set(document) <= _CONFIG_KEYS:
        raise ExecutionContractError
    roots = document["approved_roots"]
    if type(roots) is not dict:
        raise ExecutionContractError
    profiles = document["profiles"]
    if type(profiles) is not list:
        raise ExecutionContractError
    excluded = document.get("excluded_paths", [])
    if type(excluded) is not list:
        raise ExecutionContractError
    uids = document["controller_uids"]
    if type(uids) is not list:
        raise ExecutionContractError
    cache = document.get("approved_cache")
    try:
        return ServiceConfig(
            state_root=Path(document["state_root"]),
            socket_path=Path(document["socket_path"]),
            controller_uids=frozenset(uids),
            approved_roots={str(root_id): Path(path) for root_id, path in roots.items()},
            profiles=tuple(_profile(raw) for raw in profiles),
            rpc_timeout_ms=document["rpc_timeout_ms"],
            lock_timeout_ms=document["lock_timeout_ms"],
            view_profile_id=document.get("view_profile_id"),
            excluded_paths=tuple(excluded),
            approved_cache=None if cache is None else Path(cache),
            reply_cache_entries=document.get("reply_cache_entries", 1024),
            backlog=document.get("backlog", 16),
            max_workers=document.get("max_workers", 8),
            docker_socket=_path(document.get("docker_socket")),
            docker_daemon_uid=document.get("docker_daemon_uid"),
            docker_api_version=document.get("docker_api_version"),
            docker_timeout_ms=document.get("docker_timeout_ms"),
            cgroup_root=Path(document.get("cgroup_root", "/sys/fs/cgroup")),
            startup_timeout_ms=document.get("startup_timeout_ms", 5000),
        )
    except TypeError:
        raise ExecutionContractError from None


_PROFILE_KEYS = frozenset(ExecutionProfile.__dataclass_fields__)


def _path(raw: object) -> Path | None:
    if raw is None or isinstance(raw, Path):
        return raw
    if not isinstance(raw, str):
        raise ExecutionContractError
    return Path(raw)


def _profile(raw: object) -> ExecutionProfile:
    if type(raw) is not dict or set(raw) != set(_PROFILE_KEYS):
        raise ExecutionContractError
    try:
        return ExecutionProfile(**raw)
    except TypeError:
        raise ExecutionContractError from None


def read_config_file(path: Path) -> ServiceConfig:
    """Read one operator JSON config. No environment/endpoint discovery."""
    if not path.is_absolute() or ".." in path.parts:
        raise ExecutionContractError
    try:
        document = json.loads(path.read_bytes())
    except (OSError, ValueError, RecursionError):
        raise ExecutionContractError from None
    return load_config(document)


class SupervisorService:
    """Authority + journal + reply cache + dispatcher + the one socket owner.

    Construct, then use as a context manager: `__enter__` completes startup
    recovery and only then creates the private socket. `serve_forever` accepts
    one request per connection, bounded by `max_workers`; `close` stops
    accepting, waits for in-flight handlers and only then leaves the authority
    (which drains its own gates), so shutdown cannot strand admitted work.
    """

    def __init__(self, config: ServiceConfig) -> None:
        if not isinstance(config, ServiceConfig):
            raise ExecutionContractError
        self._config = config
        self._profile_set_sha256 = profile_set_sha256(config.profiles)
        self._view_profile = next(
            (profile for profile in config.profiles if profile.profile_id == config.view_profile_id), None
        )
        self._authority = WorkspaceAuthority(
            config.state_root,
            approved_roots=dict(config.approved_roots),
            controller_uids=config.controller_uids,
            lock_timeout_ms=config.lock_timeout_ms,
            limits=InputLimits(),
            excluded_paths=config.excluded_paths,
            view_profile=self._view_profile,
            approved_cache=config.approved_cache,
        )
        self._dispatcher = SupervisorDispatcher(
            client_uids=config.controller_uids,
            rpc_timeout_ms=config.rpc_timeout_ms,
            profiles=config.profiles,
            journal=self._authority.journal,
            replies=CompletedReplyCache(max_entries=config.reply_cache_entries),
            authorize=self.authorize,
            handle=self.handle,
        )
        self._backend: CellBackend | None = None
        if config.docker_socket is not None:
            daemon_uid, api_version, timeout_ms = (
                config.docker_daemon_uid,
                config.docker_api_version,
                config.docker_timeout_ms,
            )
            if daemon_uid is None or api_version is None or timeout_ms is None:
                raise ExecutionContractError  # refused in __post_init__; narrows the type
            engine = DockerEngine(
                config.docker_socket,
                daemon_uid=daemon_uid,
                api_version=api_version,
                rpc_timeout_ms=timeout_ms,
            )
            self._backend = CellBackend(self._authority, engine, self._authority.journal)
        # The barrier is always composed: a never-executed view is proved empty
        # by the journal alone, and a view that has a cell is refused (None)
        # until a real backend and cgroup fact are both available.
        self._stopper = ViewStopper(
            self._authority,
            cells=OwnedCellTermination(
                self._authority.journal,
                cells=None if self._backend is None else self._backend.cells,
                profile=self._view_profile,
                cgroup_root=config.cgroup_root,
            ),
        )
        self._socket: socket.socket | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._entered = False
        if set(_ROUTE_NAMES) != set(Operation) or len(set(_ROUTE_NAMES.values())) != len(_ROUTE_NAMES):
            # Derived from the closed enum: an unrouted member would otherwise be
            # a silent hole in the only dispatch table this service has.
            raise ExecutionContractError
        for name in _ROUTE_NAMES.values():
            if not callable(getattr(self, name, None)):
                raise ExecutionContractError

    @property
    def authority(self) -> WorkspaceAuthority:
        return self._authority

    @property
    def dispatcher(self) -> SupervisorDispatcher:
        return self._dispatcher

    @property
    def socket_path(self) -> Path:
        return self._config.socket_path

    @property
    def profile_set_sha256(self) -> str:
        return self._profile_set_sha256

    # --- context / socket ownership ---------------------------------------

    def __enter__(self) -> Self:
        if self._entered:
            raise ExecutionContractError
        # Recovery (journal UNKNOWN + per-workspace intent) precedes any socket,
        # and any surviving owned cell is stopped before the first accept.
        self._authority.__enter__()
        self._entered = True
        try:
            if self._backend is not None:
                self._backend.reconcile(deadline=time.monotonic() + self._config.startup_timeout_ms / 1000)
            self._bind()
        except BaseException:
            if self._backend is not None:
                try:
                    self._backend.close(deadline=time.monotonic() + self._config.startup_timeout_ms / 1000)
                except (SupervisorError, OSError):
                    pass
            self._entered = False
            self._authority.__exit__(None, None, None)
            raise
        self._executor = ThreadPoolExecutor(max_workers=self._config.max_workers, thread_name_prefix="fa-exec-svc")
        return self

    def __exit__(
        self, _exc_type: type[BaseException] | None, _exc_value: BaseException | None, _traceback: TracebackType | None
    ) -> None:
        self.close()

    def _bind(self) -> None:
        """Own one private UDS: 0600 mode, owner-only umask, no directory creation."""
        path = self._config.socket_path
        directory = path.parent
        if not directory.is_dir():
            raise ExecutionContractError
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            if path.exists() or path.is_symlink():
                # The single-supervisor flock is already held, so a file here is
                # stale by proof, not by guessing: no live instance can own it.
                mode = path.lstat()
                if not stat.S_ISSOCK(mode.st_mode):
                    raise ExecutionContractError
                path.unlink()
            previous = os.umask(0o077)
            try:
                listener.bind(str(path))
            finally:
                os.umask(previous)
            os.chmod(path, 0o600)
            listener.listen(self._config.backlog)
        except BaseException:
            listener.close()
            raise
        self._socket = listener

    def serve_forever(self, stop: threading.Event) -> None:
        """Accept until `stop` is set; each connection is served exactly once.

        The dispatcher closes the connection itself; this loop only hands it off.
        An accept failure ends the loop instead of spinning, so a closed or
        broken listener is visible to the operator as a stopped service.
        """
        if not self._entered or self._socket is None or self._executor is None:
            raise ExecutionContractError
        listener, executor = self._socket, self._executor
        # Bounded accept: the stop flag is a shutdown signal, never a correctness
        # input, so a short timeout is enough and an interrupted accept is not work.
        listener.settimeout(0.1)
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            if stop.is_set():
                connection.close()
                return
            executor.submit(self._serve, connection)

    def _serve(self, connection: socket.socket) -> None:
        try:
            self._dispatcher.serve_connection(connection)
        finally:
            connection.close()

    def close(self) -> None:
        """Stop accepting, finish in-flight handlers, then leave the authority."""
        listener, executor = self._socket, self._executor
        self._socket, self._executor = None, None
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=False)
        if self._entered:
            self._entered = False
            if self._backend is not None:
                try:
                    self._backend.close(deadline=time.monotonic() + self._config.startup_timeout_ms / 1000)
                except (SupervisorError, OSError):
                    # Teardown is best effort: the authority still drains its own
                    # gates, and a lost attach handle asserts no cell death.
                    pass
            self._authority.__exit__(None, None, None)
        path = self._config.socket_path
        try:
            if path.is_socket():
                path.unlink()
        except OSError:
            pass

    # --- the two dispatcher seams -----------------------------------------

    def authorize(self, peer: PeerIdentity, request: dict[str, Any], *, deadline: float) -> ProtectedPlanContext | None:
        return self._authority.authorize(peer, request, deadline=deadline)

    def handle(self, peer: PeerIdentity, request: dict[str, Any], *, deadline: float) -> GrantReply | dict[str, Any]:
        try:
            operation = Operation(request["op"])
        except (KeyError, ValueError, TypeError):
            raise SupervisorError("INVALID_REQUEST") from None
        route: Callable[[PeerIdentity, dict[str, Any], float], GrantReply | dict[str, Any]] = getattr(
            self, _ROUTE_NAMES[operation]
        )
        return route(peer, request, deadline)

    # --- routes -----------------------------------------------------------

    @staticmethod
    def _namespace(request: Mapping[str, Any]) -> NamespaceRef:
        raw = request.get("namespace")
        if type(raw) is not dict:
            raise SupervisorError("INVALID_REQUEST")
        try:
            return NamespaceRef(**raw)
        except (TypeError, ExecutionContractError):
            raise SupervisorError("INVALID_REQUEST") from None

    @staticmethod
    def _view(request: Mapping[str, Any]) -> ViewRef:
        raw = request.get("view_ref")
        try:
            return ViewRef.from_dict(raw)
        except ExecutionContractError:
            raise SupervisorError("INVALID_REQUEST") from None

    @staticmethod
    def _capability(request: Mapping[str, Any]) -> str:
        capability = request.get("capability")
        if not isinstance(capability, str):
            raise SupervisorError("UNAUTHORIZED")
        return capability

    @staticmethod
    def _plan_ref(raw: object) -> PlanRef | None:
        if raw is None:
            return None
        if type(raw) is not dict:
            raise SupervisorError("INPUT_POLICY")
        try:
            return PlanRef(**raw)
        except TypeError:
            raise SupervisorError("INPUT_POLICY") from None

    def _health(self, _peer: PeerIdentity, _request: dict[str, Any], _deadline: float) -> dict[str, Any]:
        return {
            "ready": self._authority.ready,
            "protocol_version": 1,
            "profile_set_sha256": self._profile_set_sha256,
        }

    def _register_workspace(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> dict[str, Any]:
        payload = request["payload"]
        if payload["create"]:
            # No creating/materializing owner exists yet (SLICE5 acquisition).
            raise SupervisorError("BACKEND_UNAVAILABLE")
        if payload["input_id"] is not None:
            # An approved materialized input is only meaningful for a new root.
            raise SupervisorError("INPUT_POLICY")
        result = self._authority.register_existing(
            peer,
            self._namespace(request),
            root_id=payload["root_id"],
            relative_root=payload["relative_root"],
            deadline=deadline,
        )
        return {"workspace_id": result["workspace_id"], "revision_id": result["revision_id"]}

    def _acquire_writer(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> GrantReply:
        return self._authority.acquire_writer(
            peer,
            self._namespace(request),
            workspace_id=request["payload"]["workspace_id"],
            deadline=deadline,
        )

    def _pin_reader(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> GrantReply:
        payload = request["payload"]
        return self._authority.pin_reader(
            peer,
            self._namespace(request),
            workspace_id=payload["workspace_id"],
            revision_id=payload["revision_id"],
            plan_ref=self._plan_ref(payload["plan_ref"]),
            # The wire carries no formal-evidence claim; only the internal API sets it.
            formal_evidence=False,
            deadline=deadline,
        )

    def _create_view(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> GrantReply:
        payload = request["payload"]
        try:
            access, purpose = Access(payload["access"]), ViewPurpose(payload["purpose"])
        except ValueError:
            raise SupervisorError("INPUT_POLICY") from None
        return self._authority.create_view(
            peer,
            self._namespace(request),
            workspace_id=payload["workspace_id"],
            capability=self._capability(request),
            purpose=purpose,
            access=access,
            candidate_scope=payload["candidate_scope"],
            plan_ref=self._plan_ref(payload["plan_ref"]),
            formal_evidence=False,
            deadline=deadline,
            # E268: the wire's base is a CAS precondition owned by the authority.
            base_revision=payload["base_revision"],
        )

    def _read_file(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> dict[str, Any]:
        payload = request["payload"]
        return dict(
            self._authority.read_file(
                peer,
                self._namespace(request),
                view_ref=self._view(request),
                capability=self._capability(request),
                path=payload["path"],
                offset_bytes=payload["offset_bytes"],
                max_bytes=payload["max_bytes"],
                deadline=deadline,
            )
        )

    def _write_file(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> dict[str, Any]:
        payload = request["payload"]
        return dict(
            self._authority.write_file(
                peer,
                self._namespace(request),
                view_ref=self._view(request),
                capability=self._capability(request),
                path=payload["path"],
                content=payload["content"],
                expected_sha256=payload["expected_sha256"],
                deadline=deadline,
            )
        )

    def _edit_file(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> dict[str, Any]:
        # Edit is a write with a mandatory precondition (the codec refuses null).
        return self._write_file(peer, request, deadline)

    def _exec(self, _peer: PeerIdentity, _request: dict[str, Any], _deadline: float) -> dict[str, Any]:
        raise SupervisorError("BACKEND_UNAVAILABLE")

    def _inspect(self, _peer: PeerIdentity, _request: dict[str, Any], _deadline: float) -> dict[str, Any]:
        raise SupervisorError("BACKEND_UNAVAILABLE")

    def _cancel(self, _peer: PeerIdentity, _request: dict[str, Any], _deadline: float) -> dict[str, Any]:
        raise SupervisorError("BACKEND_UNAVAILABLE")

    def _pty_control(self, _peer: PeerIdentity, _request: dict[str, Any], _deadline: float) -> dict[str, Any]:
        raise SupervisorError("BACKEND_UNAVAILABLE")

    def _stop_view(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> dict[str, Any]:
        result = self._stopper.stop_view(
            peer,
            self._namespace(request),
            view_ref=self._view(request),
            capability=self._capability(request),
            deadline=deadline,
        )
        return result.to_wire()

    def _seal(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> dict[str, Any]:
        result = publication.seal_view(
            self._authority,
            peer,
            self._namespace(request),
            view_ref=self._view(request),
            capability=self._capability(request),
            deadline=deadline,
        )
        return result.to_wire()

    def _publish(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> dict[str, Any]:
        payload = request["payload"]
        result = publication.publish_view(
            self._authority,
            peer,
            self._namespace(request),
            view_ref=self._view(request),
            capability=self._capability(request),
            sealed_manifest_id=payload["sealed_manifest_id"],
            expected_base_revision=payload["expected_base_revision"],
            operation_id=self._operation_id(request),
            deadline=deadline,
        )
        return asdict(result)

    def _prepare_bundle(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> dict[str, Any]:
        payload = request["payload"]
        result = publication.prepare_bundle(
            self._authority,
            peer,
            self._namespace(request),
            capability=self._capability(request),
            project_slug=payload["project_slug"],
            increment_slug=payload["increment_slug"],
            roadmap_text=payload["roadmap_text"],
            increment_text=payload["increment_text"],
            expected_base_revision=payload["expected_base_revision"],
            operation_id=self._operation_id(request),
            # Controller metadata, never model text: the bundle's creation date.
            created=datetime.now(UTC).date().isoformat(),
            deadline=deadline,
        )
        return result.to_wire()

    def _install_project(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> dict[str, Any]:
        payload = request["payload"]
        result = publication.install_project(
            self._authority,
            peer,
            self._namespace(request),
            capability=self._capability(request),
            validated_bundle_id=payload["validated_bundle_id"],
            project_slug=payload["project_slug"],
            deadline=deadline,
        )
        return asdict(result)

    def _handoff(self, _peer: PeerIdentity, _request: dict[str, Any], _deadline: float) -> dict[str, Any]:
        raise SupervisorError("BACKEND_UNAVAILABLE")

    def _release(self, peer: PeerIdentity, request: dict[str, Any], deadline: float) -> dict[str, Any]:
        namespace, capability = self._namespace(request), self._capability(request)
        if request["view_ref"] is None:
            return self._authority.release_writer(peer, namespace, capability=capability, deadline=deadline)
        return self._authority.release_reader(
            peer, namespace, view_ref=self._view(request), capability=capability, deadline=deadline
        )

    @staticmethod
    def _operation_id(request: Mapping[str, Any]) -> str:
        """The journal's own operation id: `op-` + the request's 32-hex id."""
        request_id = request["request_id"]
        if not isinstance(request_id, str):
            raise SupervisorError("INVALID_REQUEST")
        _hex_id(request_id, "")
        return "op-" + request_id


# One row per closed `Operation` member. Names only: `handle` resolves them on
# this service, and construction refuses a table that misses a member.
_ROUTE_NAMES: dict[Operation, str] = {
    Operation.HEALTH: "_health",
    Operation.REGISTER_WORKSPACE: "_register_workspace",
    Operation.ACQUIRE_WRITER: "_acquire_writer",
    Operation.PIN_READER: "_pin_reader",
    Operation.CREATE_VIEW: "_create_view",
    Operation.READ_FILE: "_read_file",
    Operation.WRITE_FILE: "_write_file",
    Operation.EDIT_FILE: "_edit_file",
    Operation.EXEC: "_exec",
    Operation.INSPECT: "_inspect",
    Operation.CANCEL: "_cancel",
    Operation.PTY_CONTROL: "_pty_control",
    Operation.STOP_VIEW: "_stop_view",
    Operation.SEAL: "_seal",
    Operation.PUBLISH: "_publish",
    Operation.PREPARE_BUNDLE: "_prepare_bundle",
    Operation.INSTALL_PROJECT: "_install_project",
    Operation.HANDOFF: "_handoff",
    Operation.RELEASE: "_release",
}
