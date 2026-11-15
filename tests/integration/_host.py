"""Fail-closed approved-host preflight and disposable real-service harness.

The suites below this package form the explicit W4 host lane, but are not by
themselves the final ``e2e/I03`` evidence package. They require the configured
Linux/Docker/cgroup host, then exercise the real supervisor, authority, client,
Docker cells and cgroup barrier against unique temporary authority roots. They
never discover an endpoint through Docker environment variables or fall back
to a fake worker.
"""

from __future__ import annotations

import json
import os
import platform
import re
import stat
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from threading import Event, Thread
from typing import Any, cast, override
from urllib.parse import quote
from uuid import uuid4

from fa.config import DEFAULT_CONFIG_PATH, ExecutionConfigError, load_execution_config
from fa.execution.client import (
    ExecutionClient,
    ManagedBashExecutor,
    ReadOnlyManagedBashExecutor,
    _grant,
)
from fa.execution.composition import ExecutionBinding
from fa.execution.docker import DockerEngine, DockerUnavailableError
from fa.execution.profiles import ExecutionProfile, profile_set_sha256
from fa.execution.protocol import PROTOCOL_V2
from fa.execution.service import ServiceConfig, SupervisorService, read_config_file
from fa.execution.tool_port import ClientWorkspacePort
from fa.execution.types import (
    Access,
    ExecutionContractError,
    GrantReply,
    NamespaceRef,
    Operation,
    ViewPurpose,
    ViewRef,
)
from fa.inner_loop.plan_admission import PlanRef

MIN_APPROVED_PROFILE_MEMORY_BYTES = 1_342_177_280
_REQUIRED_CGROUP_CONTROLLERS = frozenset({"cpu", "memory", "pids"})
_CGROUP_POPULATED = re.compile(r"^populated ([01])$")
_DOCKER_API_VERSION = re.compile(r"1\.([0-9]{2})$")
_REPOSITORY_TAG = re.compile(r"(?P<repository>.+?)(?::[^/:]+)?@(?P<digest>sha256:[0-9a-f]{64})$")
_MAX_CGROUP_TEXT_BYTES = 64 * 1024


class ExecutionHostPreflightError(RuntimeError):
    """A stable, redacted reason that required execution-host evidence is absent."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"execution_host_preflight:{code}")


def require_execution_host_opt_in(value: str | None) -> None:
    """The mandatory host marker never silently skips when its gate is absent."""
    if value != "1":
        raise ExecutionHostPreflightError("explicit_host_opt_in_required")


@dataclass(frozen=True)
class HostProbeFacts:
    """The small, non-secret set of facts consumed by the pure preflight decision."""

    system: str
    effective_uid: int
    cgroup_controllers: frozenset[str]
    cgroup_parent_controllers: Mapping[str, frozenset[str]]
    cgroup_parent_enabled: Mapping[str, frozenset[str]]
    docker_api_ready: bool
    image_references: frozenset[str]
    approved_cache_ready: bool


@dataclass(frozen=True)
class ExecutionHostReadiness:
    """Validated operator config plus the exact selected profiles needed by the suites."""

    service_config: ServiceConfig
    write_profile: ExecutionProfile
    read_only_profile: ExecutionProfile
    profile_set_sha256: str


def _static_host_config(
    config: ServiceConfig, *, system: str, effective_uid: int
) -> tuple[ExecutionProfile, ExecutionProfile]:
    if not isinstance(config, ServiceConfig):
        raise ExecutionHostPreflightError("service_config_invalid")
    if system != "Linux":
        raise ExecutionHostPreflightError("linux_host_required")
    if type(effective_uid) is not int or effective_uid not in config.controller_uids:
        raise ExecutionHostPreflightError("controller_uid_not_approved")
    if (
        config.docker_socket is None
        or config.docker_daemon_uid is None
        or config.docker_api_version is None
        or config.docker_timeout_ms is None
    ):
        raise ExecutionHostPreflightError("docker_configuration_required")
    if _DOCKER_API_VERSION.fullmatch(config.docker_api_version) is None:
        raise ExecutionHostPreflightError("docker_configuration_invalid")
    if config.approved_cache is None:
        raise ExecutionHostPreflightError("approved_cache_required")
    if config.view_profile_id is None or config.read_only_profile_id is None:
        raise ExecutionHostPreflightError("approved_profiles_required")
    profiles = {profile.profile_id: profile for profile in config.profiles}
    write_profile = profiles.get(config.view_profile_id)
    read_only_profile = profiles.get(config.read_only_profile_id)
    if write_profile is None or not write_profile.interactive:
        raise ExecutionHostPreflightError("approved_write_profile_invalid")
    if read_only_profile is None or read_only_profile.interactive:
        raise ExecutionHostPreflightError("approved_read_profile_invalid")
    if min(write_profile.memory_bytes, read_only_profile.memory_bytes) < MIN_APPROVED_PROFILE_MEMORY_BYTES:
        raise ExecutionHostPreflightError("approved_profile_memory_below_q97_floor")
    return write_profile, read_only_profile


def validate_host_preflight(config: ServiceConfig, facts: HostProbeFacts) -> ExecutionHostReadiness:
    """Make a pure, fail-closed decision from config and already-collected facts.

    Local tests pass explicitly simulated facts here; only the host fixture calls
    the read-only probes below. This function cannot contact Docker or mutate the
    filesystem, so its simulated-host-present result is not host acceptance.
    """
    if not isinstance(facts, HostProbeFacts):
        raise ExecutionHostPreflightError("invalid_preflight_input")
    write_profile, read_only_profile = _static_host_config(
        config, system=facts.system, effective_uid=facts.effective_uid
    )
    if not _REQUIRED_CGROUP_CONTROLLERS <= facts.cgroup_controllers:
        raise ExecutionHostPreflightError("cgroup_v2_controllers_unavailable")
    for profile in (write_profile, read_only_profile):
        parent = profile.cgroup_parent
        parent_controllers = facts.cgroup_parent_controllers.get(parent)
        parent_enabled = facts.cgroup_parent_enabled.get(parent)
        if (
            parent_controllers is None
            or parent_enabled is None
            or not _REQUIRED_CGROUP_CONTROLLERS <= parent_controllers
            or not _REQUIRED_CGROUP_CONTROLLERS <= parent_enabled
        ):
            raise ExecutionHostPreflightError("profile_cgroup_parent_unavailable")
    if not facts.approved_cache_ready:
        raise ExecutionHostPreflightError("approved_cache_unavailable_or_unsafe")
    if not facts.docker_api_ready:
        raise ExecutionHostPreflightError("docker_daemon_unavailable")
    required_images = {write_profile.image, read_only_profile.image}
    if not required_images <= facts.image_references:
        raise ExecutionHostPreflightError("approved_profile_image_not_present")
    digest = profile_set_sha256(
        config.profiles,
        view_profile_id=config.view_profile_id,
        read_only_profile_id=config.read_only_profile_id,
    )
    return ExecutionHostReadiness(config, write_profile, read_only_profile, digest)


def load_and_probe_execution_host(config_path: Path = DEFAULT_CONFIG_PATH) -> ExecutionHostReadiness:
    """Load the operator's ordinary ``~/.fa/config.yaml`` and verify prerequisites.

    Probes are bounded, read-only and use only configured paths: Linux uid,
    cgroup-v2 controller metadata, the configured cache directory, a Unix-socket
    Docker ping/version and digest-pinned image-inspects. Any missing requirement
    is an error, never a pytest skip; config contents and daemon error bodies are
    not included in diagnostics.
    """
    try:
        yaml_text = config_path.read_text(encoding="utf-8")
    except OSError:
        raise ExecutionHostPreflightError("operator_config_unavailable") from None
    try:
        service_path = load_execution_config(yaml_text)
    except ExecutionConfigError:
        raise ExecutionHostPreflightError("operator_config_invalid") from None
    if service_path is None:
        raise ExecutionHostPreflightError("managed_execution_not_configured")
    try:
        config = read_config_file(service_path)
    except (OSError, ExecutionContractError):
        raise ExecutionHostPreflightError("service_config_invalid") from None

    system = platform.system()
    effective_uid = _effective_uid()
    write_profile, read_only_profile = _static_host_config(config, system=system, effective_uid=effective_uid)
    controllers, parent_controllers, parent_enabled = _read_cgroup_facts(
        config.cgroup_root,
        {write_profile.cgroup_parent, read_only_profile.cgroup_parent},
    )
    cache_ready = _probe_approved_cache(config.approved_cache, effective_uid)
    if not cache_ready:
        raise ExecutionHostPreflightError("approved_cache_unavailable_or_unsafe")
    images = _probe_docker(config, (write_profile, read_only_profile))
    facts = HostProbeFacts(
        system=system,
        effective_uid=effective_uid,
        cgroup_controllers=controllers,
        cgroup_parent_controllers=parent_controllers,
        cgroup_parent_enabled=parent_enabled,
        docker_api_ready=images is not None,
        image_references=frozenset() if images is None else images,
        approved_cache_ready=cache_ready,
    )
    return validate_host_preflight(config, facts)


def _effective_uid() -> int:
    getuid = getattr(os, "geteuid", None)
    if not callable(getuid):
        raise ExecutionHostPreflightError("effective_uid_unavailable")
    try:
        return cast(Callable[[], int], getuid)()
    except OSError:
        raise ExecutionHostPreflightError("effective_uid_unavailable") from None


def _parse_cgroup_controllers(value: str) -> frozenset[str]:
    return frozenset(token.lstrip("+-") for token in value.split() if token)


def _read_fd_text(fd: int, *, limit: int = _MAX_CGROUP_TEXT_BYTES) -> str:
    chunks = bytearray()
    while len(chunks) <= limit:
        part = os.read(fd, min(4096, limit + 1 - len(chunks)))
        if not part:
            break
        chunks.extend(part)
    if len(chunks) > limit:
        raise ExecutionHostPreflightError("cgroup_metadata_too_large")
    try:
        return chunks.decode("ascii")
    except UnicodeError:
        raise ExecutionHostPreflightError("cgroup_metadata_invalid") from None


def _read_regular_file_at(directory_fd: int, name: str) -> str:
    fd = -1
    try:
        fd = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directory_fd,
        )
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ExecutionHostPreflightError("cgroup_metadata_unavailable")
        return _read_fd_text(fd)
    except ExecutionHostPreflightError:
        raise
    except OSError:
        raise ExecutionHostPreflightError("cgroup_metadata_unavailable") from None
    finally:
        if fd != -1:
            os.close(fd)


def _open_directory_path(path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts or path == Path("/"):
        raise ExecutionHostPreflightError("cgroup_path_invalid")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except OSError:
        os.close(fd)
        raise ExecutionHostPreflightError("cgroup_v2_root_unavailable") from None


def _open_directory_beneath(root_fd: int, relative: str) -> int:
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ExecutionHostPreflightError("profile_cgroup_parent_invalid")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.dup(root_fd)
    try:
        for part in path.parts:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except OSError:
        os.close(fd)
        raise ExecutionHostPreflightError("profile_cgroup_parent_unavailable") from None


def _require_populated_fact(text: str) -> None:
    matches = [match.group(1) for line in text.splitlines() if (match := _CGROUP_POPULATED.fullmatch(line))]
    if len(matches) != 1:
        raise ExecutionHostPreflightError("cgroup_events_unavailable")


def _read_cgroup_facts(
    cgroup_root: Path, profile_parents: set[str]
) -> tuple[frozenset[str], dict[str, frozenset[str]], dict[str, frozenset[str]]]:
    root_fd = _open_directory_path(cgroup_root)
    try:
        controllers = _parse_cgroup_controllers(_read_regular_file_at(root_fd, "cgroup.controllers"))
        _require_populated_fact(_read_regular_file_at(root_fd, "cgroup.events"))
        parent_controllers: dict[str, frozenset[str]] = {}
        parent_enabled: dict[str, frozenset[str]] = {}
        for parent in sorted(profile_parents):
            parent_fd = _open_directory_beneath(root_fd, parent)
            try:
                parent_controllers[parent] = _parse_cgroup_controllers(
                    _read_regular_file_at(parent_fd, "cgroup.controllers")
                )
                parent_enabled[parent] = _parse_cgroup_controllers(
                    _read_regular_file_at(parent_fd, "cgroup.subtree_control")
                )
                _require_populated_fact(_read_regular_file_at(parent_fd, "cgroup.events"))
            finally:
                os.close(parent_fd)
        return controllers, parent_controllers, parent_enabled
    finally:
        os.close(root_fd)


def _probe_approved_cache(cache: Path | None, effective_uid: int) -> bool:
    if not isinstance(cache, Path) or not cache.is_absolute() or ".." in cache.parts:
        return False
    try:
        fd = _open_directory_path(cache)
    except ExecutionHostPreflightError:
        return False
    try:
        info = os.fstat(fd)
        return stat.S_ISDIR(info.st_mode) and info.st_uid == effective_uid and not info.st_mode & 0o022
    except OSError:
        return False
    finally:
        os.close(fd)


def _api_pair(value: object) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = _DOCKER_API_VERSION.fullmatch(value)
    return None if match is None else (1, int(match.group(1)))


def _repository_digest(image: str) -> str | None:
    match = _REPOSITORY_TAG.fullmatch(image)
    return None if match is None else f"{match.group('repository')}@{match.group('digest')}"


def _probe_docker(config: ServiceConfig, profiles: tuple[ExecutionProfile, ExecutionProfile]) -> frozenset[str] | None:
    """Verify the configured daemon peer/API and profile images using GETs only."""
    if (
        config.docker_socket is None
        or config.docker_daemon_uid is None
        or config.docker_api_version is None
        or config.docker_timeout_ms is None
    ):
        return None
    try:
        endpoint = config.docker_socket.lstat()
        if not stat.S_ISSOCK(endpoint.st_mode) or endpoint.st_uid != config.docker_daemon_uid:
            return None
        requested_api = _api_pair(config.docker_api_version)
        if requested_api is None:
            return None
        engine = DockerEngine(
            config.docker_socket,
            daemon_uid=config.docker_daemon_uid,
            api_version=config.docker_api_version,
            rpc_timeout_ms=config.docker_timeout_ms,
        )
        deadline = time.monotonic() + min(max(config.docker_timeout_ms * 4, config.docker_timeout_ms), 15_000) / 1000
        ping = engine._request("GET", "/_ping", body=None, status=200, deadline=deadline)
        if ping not in {b"OK", b"OK\n"}:
            return None
        version = json.loads(engine._request("GET", "/version", body=None, status=200, deadline=deadline))
        if type(version) is not dict:
            return None
        daemon_api = _api_pair(version.get("ApiVersion"))
        minimum_api = _api_pair(version.get("MinAPIVersion"))
        if daemon_api is None or minimum_api is None or not minimum_api <= requested_api <= daemon_api:
            return None
        images: set[str] = set()
        for profile in set(profiles):
            expected = _repository_digest(profile.image)
            if expected is None:
                return None
            reference = quote(profile.image, safe="/:@")
            document = json.loads(
                engine._request(
                    "GET",
                    f"/images/{reference}/json",
                    body=None,
                    status=200,
                    deadline=deadline,
                )
            )
            if type(document) is not dict or not isinstance(document.get("Id"), str):
                return None
            repo_digests = document.get("RepoDigests")
            if not isinstance(repo_digests, list):
                return None
            actual = {value for item in repo_digests if isinstance(item, str) if (value := _repository_digest(item))}
            if expected not in actual:
                return None
            images.add(profile.image)
        return frozenset(images)
    except (DockerUnavailableError, OSError, ValueError, TypeError, ExecutionContractError):
        return None


def service_config_document(config: ServiceConfig) -> dict[str, Any]:
    """Render only validated fields accepted by ``service.load_config``."""
    document: dict[str, Any] = {
        "state_root": str(config.state_root),
        "socket_path": str(config.socket_path),
        "controller_uids": sorted(config.controller_uids),
        "approved_roots": {root_id: str(path) for root_id, path in config.approved_roots.items()},
        "profiles": [profile.to_dict() for profile in config.profiles],
        "rpc_timeout_ms": config.rpc_timeout_ms,
        "lock_timeout_ms": config.lock_timeout_ms,
        "view_profile_id": config.view_profile_id,
        "read_only_profile_id": config.read_only_profile_id,
        "excluded_paths": list(config.excluded_paths),
        "reply_cache_entries": config.reply_cache_entries,
        "backlog": config.backlog,
        "max_workers": config.max_workers,
        "cgroup_root": str(config.cgroup_root),
        "startup_timeout_ms": config.startup_timeout_ms,
    }
    if config.approved_cache is not None:
        document["approved_cache"] = str(config.approved_cache)
    if config.docker_socket is not None:
        document.update(
            {
                "docker_socket": str(config.docker_socket),
                "docker_daemon_uid": config.docker_daemon_uid,
                "docker_api_version": config.docker_api_version,
                "docker_timeout_ms": config.docker_timeout_ms,
            }
        )
    return document


def _safe_payload(operation: Operation, raw: object) -> dict[str, Any]:
    if type(raw) is not dict:
        return {}
    keys_by_operation: dict[Operation, tuple[str, ...]] = {
        Operation.REGISTER_WORKSPACE: ("root_id", "relative_root", "create"),
        Operation.ACQUIRE_WRITER: ("workspace_id",),
        Operation.PIN_READER: ("workspace_id", "revision_id"),
        Operation.CREATE_VIEW: ("workspace_id", "base_revision", "access", "purpose"),
        Operation.READ_FILE: ("path", "offset_bytes", "max_bytes"),
        Operation.WRITE_FILE: ("path", "expected_sha256"),
        Operation.EDIT_FILE: ("path", "expected_sha256"),
        Operation.PUBLISH: ("expected_base_revision", "sealed_manifest_id"),
        Operation.EXEC: ("profile_id", "session_id", "timeout_ms"),
        Operation.RELEASE: (),
        Operation.STOP_VIEW: (),
        Operation.SEAL: (),
        Operation.HEALTH: (),
        Operation.HANDOFF: (),
    }
    selected = {key: raw[key] for key in keys_by_operation.get(operation, ()) if key in raw}
    project_tool = raw.get("project_tool")
    if isinstance(project_tool, dict) and isinstance(project_tool.get("tool"), str):
        selected["project_tool"] = {"tool": project_tool["tool"]}
    if operation is Operation.HANDOFF and isinstance(raw.get("target_namespace"), dict):
        selected["target_namespace"] = dict(raw["target_namespace"])
    if operation is Operation.CREATE_VIEW and isinstance(raw.get("plan_ref"), dict):
        selected["plan_ref_sha256"] = raw["plan_ref"].get("sha256")
    return selected


class RecordingExecutionClient(ExecutionClient):
    """Real UDS client that records safe request metadata, never capabilities or bodies."""

    def __init__(
        self,
        socket_path: Path,
        *,
        server_uid: int,
        rpc_timeout_ms: int,
        events: list[dict[str, Any]],
    ) -> None:
        super().__init__(socket_path, server_uid=server_uid, rpc_timeout_ms=rpc_timeout_ms)
        self._events = events
        self._events_lock = threading.Lock()

    @override
    def request(self, operation: Operation, **kwargs: Any) -> dict[str, Any]:
        namespace = kwargs.get("namespace")
        view = kwargs.get("view")
        grant = kwargs.get("grant")
        event: dict[str, Any] = {
            "operation": operation.value,
            "request_id": kwargs.get("request_id"),
            "namespace": namespace.to_dict() if isinstance(namespace, NamespaceRef) else None,
            "view_ref": view.to_dict() if isinstance(view, ViewRef) else None,
            "grant_operation": grant.operation.value if isinstance(grant, GrantReply) else None,
            "payload": _safe_payload(operation, kwargs.get("payload")),
        }
        try:
            result = super().request(operation, **kwargs)
        except Exception as error:
            code = getattr(error, "code", None)
            event["outcome"] = "ERROR"
            event["error_code"] = (
                code if isinstance(code, str) and re.fullmatch(r"[A-Z0-9_]{1,64}", code) else type(error).__name__
            )
            with self._events_lock:
                self._events.append(event)
            raise
        event["outcome"] = "OK"
        with self._events_lock:
            self._events.append(event)
        return result


@dataclass
class HostView:
    namespace: NamespaceRef
    view_ref: ViewRef
    grant: GrantReply
    lifecycle: str = "open"


@dataclass
class HostWorkspace:
    runtime: ExecutionHostRuntime
    namespace: NamespaceRef
    workspace_id: str
    revision_id: str
    root: Path
    binding: ExecutionBinding
    writer_grant: GrantReply | None = None
    views: list[HostView] = field(default_factory=list)
    closed: bool = False

    def acquire_writer(self) -> GrantReply:
        if self.writer_grant is not None:
            raise ExecutionContractError
        result = self.runtime.request(
            Operation.ACQUIRE_WRITER,
            namespace=self.namespace,
            payload={"workspace_id": self.workspace_id},
        )
        self.writer_grant = _grant(Operation.ACQUIRE_WRITER, result)
        if self.writer_grant.revision_id is None:
            raise AssertionError("execution_host_acquire_writer_missing_revision")
        self.revision_id = self.writer_grant.revision_id
        return self.writer_grant

    def open_write_view(
        self,
        *,
        purpose: ViewPurpose = ViewPurpose.PROJECT,
        plan_ref: PlanRef | None = None,
        base_revision: str | None = None,
    ) -> HostView:
        if self.writer_grant is None:
            raise ExecutionContractError
        grant = self.runtime.client.open_view(
            self.binding,
            access=Access.WRITE,
            purpose=purpose,
            base_revision=self.revision_id if base_revision is None else base_revision,
            plan_ref=plan_ref,
            grant=self.writer_grant,
        )
        if grant.view_ref is None:
            raise AssertionError("execution_host_create_view_missing_identity")
        return self.track_view(grant, self.namespace)

    def pin_reader(self, *, revision_id: str | None = None, plan_ref: PlanRef | None = None) -> HostView:
        grant = self.runtime.client.pin_reader(
            self.binding,
            self.revision_id if revision_id is None else revision_id,
            plan_ref=plan_ref,
        )
        if grant.view_ref is None:
            raise AssertionError("execution_host_pin_reader_missing_identity")
        return self.track_view(grant, self.namespace)

    def track_view(self, grant: GrantReply, namespace: NamespaceRef) -> HostView:
        if not isinstance(grant, GrantReply) or grant.view_ref is None or not isinstance(namespace, NamespaceRef):
            raise ExecutionContractError
        if grant.view_ref.owner_run_id != namespace.run_id:
            raise ExecutionContractError
        view = HostView(namespace, grant.view_ref, grant)
        self.views.append(view)
        return view

    def port(self, view: HostView) -> ClientWorkspacePort:
        return ClientWorkspacePort(
            self.runtime.client,
            namespace=view.namespace,
            view=view.view_ref,
            grant=view.grant,
        )

    def managed_bash(
        self,
        view: HostView,
        *,
        profile: ExecutionProfile | None = None,
        plan_ref: PlanRef | None = None,
    ) -> ManagedBashExecutor:
        profile = profile or self.runtime.readiness.write_profile
        if view.view_ref.access is not Access.WRITE or not profile.interactive:
            raise ExecutionContractError
        input_tree_sha256 = view.grant.input_tree_sha256
        if input_tree_sha256 is None:
            raise ExecutionContractError
        return ManagedBashExecutor(
            self.runtime.client,
            namespace=view.namespace,
            view=view.view_ref,
            grant=view.grant,
            profile=profile,
            input_tree_sha256=input_tree_sha256,
            plan_sha256=None if plan_ref is None else plan_ref.sha256,
            original_revision_id=view.view_ref.base_revision,
            controller_root=self.root,
        )

    def managed_read_only_bash(
        self,
        view: HostView,
        *,
        plan_ref: PlanRef | None = None,
    ) -> ReadOnlyManagedBashExecutor:
        if view.view_ref.access is not Access.READ or view.view_ref.purpose is not ViewPurpose.PROJECT:
            raise ExecutionContractError
        return ReadOnlyManagedBashExecutor(
            self.runtime.client,
            namespace=view.namespace,
            view=view.view_ref,
            grant=view.grant,
            profile=self.runtime.readiness.read_only_profile,
            plan_ref=plan_ref,
            controller_root=self.root,
        )

    def publish(self, view: HostView) -> Any:
        view.lifecycle = "publishing"
        try:
            publication = self.runtime.client.publish_stage(
                view.namespace,
                view=view.view_ref,
                grant=view.grant,
            )
        except BaseException:
            view.lifecycle = "unknown"
            raise
        view.lifecycle = "published"
        self.revision_id = publication.revision_id
        return publication

    def close(self) -> None:
        if self.closed:
            return
        failures: list[str] = []
        for tracked in reversed(self.views):
            if tracked.lifecycle in {"published", "settled"}:
                continue
            if tracked.lifecycle not in {"open", "publishing"}:
                failures.append("view_lifecycle_unknown")
                continue
            tracked.lifecycle = "settling"
            try:
                if not self.runtime.client.stop_view(
                    tracked.namespace,
                    view=tracked.view_ref,
                    grant=tracked.grant,
                ):
                    tracked.lifecycle = "unknown"
                    failures.append("view_terminality_unconfirmed")
                    continue
                if tracked.view_ref.access is Access.WRITE and not self.runtime.client.release_stopped_view(
                    tracked.namespace,
                    view=tracked.view_ref,
                    grant=tracked.grant,
                ):
                    tracked.lifecycle = "unknown"
                    failures.append("write_view_rejection_unconfirmed")
                    continue
                tracked.lifecycle = "settled"
            except Exception:  # noqa: BLE001 - any unproved cleanup outcome must fail the host case.
                tracked.lifecycle = "unknown"
                failures.append("view_cleanup_failed")
        if self.writer_grant is not None and all(view.lifecycle in {"published", "settled"} for view in self.views):
            try:
                reply = self.runtime.request(
                    Operation.RELEASE,
                    namespace=self.namespace,
                    grant=self.writer_grant,
                    payload={},
                )
                if reply.get("released") is not True:
                    failures.append("writer_release_unconfirmed")
                else:
                    self.writer_grant = None
            except Exception:  # noqa: BLE001 - a release error cannot imply that ownership ended.
                failures.append("writer_release_failed")
        if failures:
            raise AssertionError(f"execution_host_cleanup_failed:{','.join(sorted(set(failures)))}")
        self.closed = True

    def abandon_after_recovery_restart(self) -> None:
        """Forget this now-quarantined authority reference; never retry its grants."""
        for view in self.views:
            view.lifecycle = "unknown"
        self.writer_grant = None
        self.closed = True


@dataclass
class ExecutionHostRuntime:
    """One real SupervisorService with disposable state/root and the real Docker daemon."""

    base: Path
    config_path: Path
    config_yaml_path: Path
    service_config: ServiceConfig
    readiness: ExecutionHostReadiness
    root_id: str
    approved_root: Path
    events: list[dict[str, Any]] = field(default_factory=list)
    workspaces: list[HostWorkspace] = field(default_factory=list)
    _service: SupervisorService | None = field(default=None, init=False, repr=False)
    _client: RecordingExecutionClient | None = field(default=None, init=False, repr=False)
    _stop: Event | None = field(default=None, init=False, repr=False)
    _thread: Thread | None = field(default=None, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def service(self) -> SupervisorService:
        if self._service is None:
            raise AssertionError("execution_host_supervisor_not_running")
        return self._service

    @property
    def client(self) -> RecordingExecutionClient:
        if self._client is None:
            raise AssertionError("execution_host_client_not_running")
        return self._client

    def _start_service(self) -> None:
        service = SupervisorService(read_config_file(self.config_path))
        service.__enter__()
        stop = threading.Event()
        thread = threading.Thread(
            target=service.serve_forever,
            args=(stop,),
            name="i03-execution-host",
            daemon=True,
        )
        client = RecordingExecutionClient(
            service.socket_path,
            server_uid=_effective_uid(),
            rpc_timeout_ms=self.service_config.rpc_timeout_ms,
            events=self.events,
        )
        self._service, self._stop, self._thread, self._client = service, stop, thread, client
        thread.start()
        try:
            health = client.request(
                Operation.HEALTH,
                request_id=uuid4().hex,
                namespace=None,
                view=None,
                grant=None,
                payload={},
                protocol_version=PROTOCOL_V2,
            )
        except Exception:  # noqa: BLE001 - failed/ambiguous health is a closed host prerequisite.
            self._stop_service()
            raise ExecutionHostPreflightError("disposable_supervisor_unavailable") from None
        if (
            health.get("ready") is not True
            or health.get("protocol_version") != PROTOCOL_V2
            or health.get("profile_set_sha256") != self.readiness.profile_set_sha256
        ):
            self._stop_service()
            raise ExecutionHostPreflightError("disposable_supervisor_health_mismatch")

    def _stop_service(self) -> None:
        service, stop, thread = self._service, self._stop, self._thread
        if stop is not None:
            stop.set()
        if service is not None:
            service.close()
        if thread is not None:
            thread.join(timeout=10)
            if thread.is_alive():
                raise AssertionError("execution_host_supervisor_thread_did_not_stop")
        self._client = None
        self._stop = None
        self._thread = None

    def request(
        self,
        operation: Operation,
        *,
        namespace: NamespaceRef,
        payload: dict[str, Any],
        view: ViewRef | None = None,
        grant: GrantReply | None = None,
        protocol_version: int = 1,
    ) -> dict[str, Any]:
        return self.client.request(
            operation,
            request_id=uuid4().hex,
            namespace=namespace,
            view=view,
            grant=grant,
            payload=payload,
            protocol_version=protocol_version,
        )

    def register_workspace(
        self,
        *,
        files: Mapping[str, bytes] | None = None,
        create: bool = False,
        namespace: NamespaceRef | None = None,
    ) -> HostWorkspace:
        relative_root = "workspace-" + uuid4().hex
        root = self.approved_root / relative_root
        if not create:
            root.mkdir(mode=0o700)
            for relative, content in (files or {}).items():
                if not isinstance(content, bytes):
                    raise TypeError("disposable fixture files must be bytes")
                path = PurePosixPath(relative)
                if (
                    path.is_absolute()
                    or not path.parts
                    or any(part in {"", ".", ".."} for part in path.parts)
                    or "\\" in relative
                ):
                    raise ValueError("fixture path escaped its disposable root")
                target = root.joinpath(*path.parts)
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                if target.exists():
                    raise ValueError("duplicate disposable fixture path")
                target.write_bytes(content)
        elif files:
            raise ValueError("new-root creation cannot also seed host files")
        if namespace is None:
            namespace = NamespaceRef("i03-" + uuid4().hex[:16], "run-" + uuid4().hex[:16])
        if not isinstance(namespace, NamespaceRef):
            raise TypeError("disposable namespace must be a validated NamespaceRef")
        result = self.request(
            Operation.REGISTER_WORKSPACE,
            namespace=namespace,
            payload={
                "root_id": self.root_id,
                "relative_root": relative_root,
                "create": create,
                "input_id": None,
            },
        )
        workspace_id = result.get("workspace_id")
        revision_id = result.get("revision_id")
        if not isinstance(workspace_id, str) or not isinstance(revision_id, str):
            raise AssertionError("execution_host_registration_missing_identity")
        workspace = HostWorkspace(
            runtime=self,
            namespace=namespace,
            workspace_id=workspace_id,
            revision_id=revision_id,
            root=root,
            binding=ExecutionBinding(namespace, workspace_id),
        )
        self.workspaces.append(workspace)
        return workspace

    def _owned_cell_records(self) -> list[dict[str, Any]]:
        return self.service.authority.journal.owned_cells()

    def assert_owned_cells_terminal(self) -> int:
        """Return the number of unique cells positively observed as cgroup-empty."""
        failures: set[str] = set()
        seen: set[tuple[str, str]] = set()
        terminal_cells = 0
        for record in self._owned_cell_records():
            container_id = record.get("container_id")
            raw_view = record.get("view_ref")
            if not isinstance(container_id, str) or not isinstance(raw_view, dict):
                failures.add("cell_inventory_invalid")
                continue
            try:
                view = ViewRef.from_dict(raw_view)
                profile = self.service.authority.view_profile(view)
                if profile is None:
                    failures.add("cell_profile_unavailable")
                    continue
                identity = (container_id, view.view_id)
                if identity in seen:
                    continue
                seen.add(identity)
                from fa.execution.cgroup import descendants_empty

                verdict = descendants_empty(
                    self.service_config.cgroup_root,
                    profile.cgroup_parent,
                    container_id,
                )
                if verdict is not True:
                    failures.add("cgroup_terminality_unconfirmed")
                else:
                    terminal_cells += 1
            except (ExecutionContractError, OSError, ValueError):
                failures.add("cgroup_terminality_unconfirmed")
        if failures:
            raise AssertionError(f"execution_host_cleanup_failed:{','.join(sorted(failures))}")
        return terminal_cells

    def restart_after_unsettled_publication(self) -> None:
        """Restart only a cell-free disposable supervisor with an injected durable intent."""
        if not any(view.lifecycle == "unknown" for workspace in self.workspaces for view in workspace.views):
            raise AssertionError("recovery_restart_requires_an_unsettled_view")
        if self._owned_cell_records():
            raise AssertionError("recovery_restart_refuses_unsettled_cells")
        self._stop_service()
        for workspace in self.workspaces:
            workspace.abandon_after_recovery_restart()
        self.workspaces.clear()
        self._start_service()

    def close(self) -> None:
        if self._closed:
            return
        failures: list[str] = []
        for workspace in reversed(self.workspaces):
            try:
                workspace.close()
            except AssertionError:
                failures.append("workspace_cleanup_failed")
        try:
            self._stop_service()
        except AssertionError:
            failures.append("supervisor_shutdown_failed")
        if self._service is not None:
            try:
                self.assert_owned_cells_terminal()
            except AssertionError:
                failures.append("cgroup_terminality_unconfirmed")
        self._closed = True
        if failures:
            raise AssertionError(f"execution_host_cleanup_failed:{','.join(sorted(set(failures)))}")


def _write_private_file(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
    try:
        remaining = memoryview(data)
        while remaining:
            written = os.write(fd, remaining)
            if written <= 0:
                raise OSError("short private fixture write")
            remaining = remaining[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def start_execution_host_runtime(
    readiness: ExecutionHostReadiness,
    base: Path,
    *,
    config_yaml_path: Path,
) -> ExecutionHostRuntime:
    """Start the production service on unique temporary state/root/socket paths."""
    if not isinstance(readiness, ExecutionHostReadiness):
        raise ExecutionHostPreflightError("execution_host_readiness_required")
    state_root = base / "state"
    approved_root = base / "approved"
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    state_root.mkdir(mode=0o700)
    approved_root.mkdir(mode=0o700)
    # Keep the AF_UNIX socket short and private; do not reuse the operator's
    # configured production endpoint, workspace roots or supervisor state.
    service_config = replace(
        readiness.service_config,
        state_root=state_root,
        socket_path=base / "s.sock",
        approved_roots={"i03-test": approved_root},
    )
    config_path = base / "execution.json"
    _write_private_file(
        config_path,
        json.dumps(service_config_document(service_config), sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    config_yaml_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _write_private_file(
        config_yaml_path,
        f"execution:\n  service_config: {config_path}\n".encode(),
    )
    runtime = ExecutionHostRuntime(
        base=base,
        config_path=config_path,
        config_yaml_path=config_yaml_path,
        service_config=service_config,
        readiness=readiness,
        root_id="i03-test",
        approved_root=approved_root,
    )
    try:
        runtime._start_service()
    except BaseException:
        try:
            runtime._stop_service()
        except Exception:  # noqa: BLE001 - preserve startup failure while attempting bounded service cleanup.
            pass
        raise
    return runtime
