"""Pure, non-host tests for the W3 prerequisite decision.

These tests exercise the decision from explicitly simulated facts. They do not
probe Docker, certify cgroups on a deployment host, or replace the required
``FA_REQUIRE_EXECUTION_HOST=1`` integration run.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import replace
from pathlib import Path
from urllib.parse import unquote

import pytest

from fa.execution.profiles import ExecutionProfile
from fa.execution.service import ServiceConfig
from tests.integration import _host
from tests.integration._host import (
    MIN_APPROVED_PROFILE_MEMORY_BYTES,
    ExecutionHostPreflightError,
    HostProbeFacts,
    _probe_approved_cache,
    _probe_docker,
    _read_cgroup_facts,
    require_execution_host_opt_in,
    validate_host_preflight,
)

_REQUIRED = frozenset({"cpu", "memory", "pids"})
_SECCOMP = '{"defaultAction":"SCMP_ACT_ERRNO","syscalls":[]}'


def _profiles(*, write_memory: int = MIN_APPROVED_PROFILE_MEMORY_BYTES) -> tuple[ExecutionProfile, ExecutionProfile]:
    return (
        ExecutionProfile(
            profile_id="approved-write",
            image="registry.invalid/fa-write@sha256:" + "a" * 64,
            uid=10001,
            gid=10001,
            nano_cpus=1_000_000_000,
            memory_bytes=write_memory,
            pids_limit=64,
            max_command_ms=30_000,
            interactive=True,
            cgroup_parent="fa-exec.slice/write.slice",
            seccomp_json=_SECCOMP,
        ),
        ExecutionProfile(
            profile_id="approved-read",
            image="registry.invalid/fa-read@sha256:" + "b" * 64,
            uid=10001,
            gid=10001,
            nano_cpus=1_000_000_000,
            memory_bytes=MIN_APPROVED_PROFILE_MEMORY_BYTES,
            pids_limit=64,
            max_command_ms=30_000,
            interactive=False,
            cgroup_parent="fa-exec.slice/read.slice",
            seccomp_json=_SECCOMP,
        ),
    )


def _service_config(tmp_path: Path, *, write_memory: int = MIN_APPROVED_PROFILE_MEMORY_BYTES) -> ServiceConfig:
    write_profile, read_profile = _profiles(write_memory=write_memory)
    return ServiceConfig(
        state_root=tmp_path / "service-state",
        socket_path=tmp_path / "service.sock",
        controller_uids=frozenset({os.geteuid()}),
        approved_roots={"projects": tmp_path / "projects"},
        profiles=(write_profile, read_profile),
        rpc_timeout_ms=2_000,
        lock_timeout_ms=2_000,
        view_profile_id=write_profile.profile_id,
        read_only_profile_id=read_profile.profile_id,
        approved_cache=tmp_path / "approved-cache",
        docker_socket=tmp_path / "docker.sock",
        docker_daemon_uid=0,
        docker_api_version="1.41",
        docker_timeout_ms=2_000,
        cgroup_root=Path("/sys/fs/cgroup"),
    )


def _facts(config: ServiceConfig) -> HostProbeFacts:
    parents = {profile.cgroup_parent: _REQUIRED for profile in config.profiles}
    enabled = {profile.cgroup_parent: _REQUIRED for profile in config.profiles}
    return HostProbeFacts(
        system="Linux",
        effective_uid=os.geteuid(),
        cgroup_controllers=_REQUIRED,
        cgroup_parent_controllers=parents,
        cgroup_parent_enabled=enabled,
        docker_api_ready=True,
        image_references=frozenset(profile.image for profile in config.profiles),
        approved_cache_ready=True,
    )


def test_complete_simulated_facts_produce_a_readiness_value_not_host_acceptance(tmp_path: Path) -> None:
    config = _service_config(tmp_path)

    readiness = validate_host_preflight(config, _facts(config))

    assert readiness.write_profile.profile_id == "approved-write"
    assert readiness.read_only_profile.profile_id == "approved-read"
    assert readiness.profile_set_sha256 == readiness.profile_set_sha256.lower()
    assert len(readiness.profile_set_sha256) == 64


@pytest.mark.parametrize(
    ("system", "uid", "controllers", "docker", "cache", "missing_image", "expected"),
    [
        ("Darwin", None, None, None, None, False, "linux_host_required"),
        (None, -1, None, None, None, False, "controller_uid_not_approved"),
        (None, None, frozenset({"cpu", "memory"}), None, None, False, "cgroup_v2_controllers_unavailable"),
        (None, None, None, False, None, False, "docker_daemon_unavailable"),
        (None, None, None, None, False, False, "approved_cache_unavailable_or_unsafe"),
        (None, None, None, None, None, True, "approved_profile_image_not_present"),
    ],
)
def test_each_missing_host_prerequisite_is_a_closed_error(
    tmp_path: Path,
    system: str | None,
    uid: int | None,
    controllers: frozenset[str] | None,
    docker: bool | None,
    cache: bool | None,
    missing_image: bool,
    expected: str,
) -> None:
    config = _service_config(tmp_path)
    facts = _facts(config)
    changed = replace(
        facts,
        system=facts.system if system is None else system,
        effective_uid=facts.effective_uid if uid is None else uid,
        cgroup_controllers=facts.cgroup_controllers if controllers is None else controllers,
        docker_api_ready=facts.docker_api_ready if docker is None else docker,
        approved_cache_ready=facts.approved_cache_ready if cache is None else cache,
        image_references=(frozenset() if missing_image else facts.image_references),
    )

    with pytest.raises(ExecutionHostPreflightError) as refused:
        validate_host_preflight(config, changed)

    assert refused.value.code == expected


def test_profile_parent_must_have_controllers_available_and_enabled(tmp_path: Path) -> None:
    config = _service_config(tmp_path)
    facts = _facts(config)
    disabled = dict(facts.cgroup_parent_enabled)
    disabled[config.profiles[1].cgroup_parent] = frozenset({"cpu", "memory"})

    with pytest.raises(ExecutionHostPreflightError) as refused:
        validate_host_preflight(config, replace(facts, cgroup_parent_enabled=disabled))

    assert refused.value.code == "profile_cgroup_parent_unavailable"


def test_q97_memory_floor_is_enforced_for_both_selected_profiles(tmp_path: Path) -> None:
    config = _service_config(tmp_path, write_memory=MIN_APPROVED_PROFILE_MEMORY_BYTES - 1)

    with pytest.raises(ExecutionHostPreflightError) as refused:
        validate_host_preflight(config, _facts(config))

    assert refused.value.code == "approved_profile_memory_below_q97_floor"


def test_a_missing_selected_profile_or_docker_configuration_fails_closed(tmp_path: Path) -> None:
    config = _service_config(tmp_path)
    facts = _facts(config)

    with pytest.raises(ExecutionHostPreflightError) as no_write_profile:
        validate_host_preflight(replace(config, view_profile_id=None), facts)
    with pytest.raises(ExecutionHostPreflightError) as no_docker:
        validate_host_preflight(
            replace(
                config,
                docker_socket=None,
                docker_daemon_uid=None,
                docker_api_version=None,
                docker_timeout_ms=None,
            ),
            facts,
        )

    assert no_write_profile.value.code == "approved_profiles_required"
    assert no_docker.value.code == "docker_configuration_required"


@pytest.mark.parametrize("value", [None, "", "0", "true", "01"])
def test_required_host_opt_in_is_exact_and_never_a_skip(value: str | None) -> None:
    with pytest.raises(ExecutionHostPreflightError) as refused:
        require_execution_host_opt_in(value)

    assert refused.value.code == "explicit_host_opt_in_required"
    require_execution_host_opt_in("1")


def test_cgroup_probe_reads_only_regular_metadata_and_requires_every_profile_parent(tmp_path: Path) -> None:
    root = tmp_path / "cgroup"
    parent = root / "fa-exec.slice" / "read.slice"
    parent.mkdir(parents=True)
    (root / "cgroup.controllers").write_text("cpu memory pids\n", encoding="ascii")
    (root / "cgroup.events").write_text("populated 1\nfrozen 0\n", encoding="ascii")
    (parent / "cgroup.controllers").write_text("cpu memory pids\n", encoding="ascii")
    (parent / "cgroup.subtree_control").write_text("cpu memory pids\n", encoding="ascii")
    (parent / "cgroup.events").write_text("populated 0\nfrozen 0\n", encoding="ascii")

    controllers, parent_controllers, parent_enabled = _read_cgroup_facts(
        root,
        {"fa-exec.slice/read.slice"},
    )

    assert controllers == _REQUIRED
    assert parent_controllers == {"fa-exec.slice/read.slice": _REQUIRED}
    assert parent_enabled == {"fa-exec.slice/read.slice": _REQUIRED}


def test_cache_probe_rejects_a_group_writable_directory(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir(mode=0o700)
    cache.chmod(0o770)

    assert not _probe_approved_cache(cache, os.geteuid())


def _install_fake_docker_engine(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mismatched_image: str | None = None,
    api_version: str = "1.45",
    minimum_api_version: str = "1.24",
) -> tuple[list[tuple[str, str]], list[tuple[Path, int, str, int]]]:
    requests: list[tuple[str, str]] = []
    constructors: list[tuple[Path, int, str, int]] = []

    class FakeDockerEngine:
        def __init__(
            self,
            socket_path: Path,
            *,
            daemon_uid: int,
            api_version: str,
            rpc_timeout_ms: int,
        ) -> None:
            constructors.append((socket_path, daemon_uid, api_version, rpc_timeout_ms))

        def _request(
            self,
            method: str,
            path: str,
            *,
            body: dict[str, object] | None,
            status: int,
            deadline: float,
        ) -> bytes:
            assert method == "GET"
            assert body is None
            assert status == 200
            assert deadline > 0
            requests.append((method, path))
            if path == "/_ping":
                return b"OK"
            if path == "/version":
                return json.dumps({"ApiVersion": api_version, "MinAPIVersion": minimum_api_version}).encode()
            if path.startswith("/images/") and path.endswith("/json"):
                reference = unquote(path.removeprefix("/images/").removesuffix("/json"))
                digest = reference
                if reference == mismatched_image:
                    repository, separator, _old_digest = reference.rpartition(":")
                    assert separator
                    digest = f"{repository}:{'0' * 64}"
                return json.dumps({"Id": "sha256:" + "c" * 64, "RepoDigests": [digest]}).encode()
            raise AssertionError(f"unexpected Docker preflight GET path: {path}")

    monkeypatch.setattr(_host, "DockerEngine", FakeDockerEngine)
    return requests, constructors


def _docker_config_with_bound_unix_socket(tmp_path: Path, socket_path: Path) -> tuple[ServiceConfig, socket.socket]:
    endpoint = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    endpoint.bind(str(socket_path))
    config = replace(
        _service_config(tmp_path),
        docker_socket=socket_path,
        docker_daemon_uid=os.geteuid(),
    )
    return config, endpoint


@pytest.mark.parametrize("mismatched_profile_id", [None, "approved-write", "approved-read"])
def test_docker_probe_uses_gets_and_requires_each_exact_pinned_image_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatched_profile_id: str | None,
) -> None:
    """C0: the read-only Docker probe validates both selected image references."""
    socket_path = tmp_path / "docker.sock"
    config, endpoint = _docker_config_with_bound_unix_socket(tmp_path, socket_path)
    try:
        mismatched_image = next(
            (profile.image for profile in config.profiles if profile.profile_id == mismatched_profile_id),
            None,
        )
        requests, constructors = _install_fake_docker_engine(
            monkeypatch,
            mismatched_image=mismatched_image,
        )
        profiles = (config.profiles[0], config.profiles[1])

        images = _probe_docker(config, profiles)
    finally:
        endpoint.close()

    expected = frozenset(profile.image for profile in profiles)
    assert images == (expected if mismatched_profile_id is None else None)
    assert constructors == [(socket_path, os.geteuid(), config.docker_api_version, config.docker_timeout_ms)]
    assert requests[:2] == [("GET", "/_ping"), ("GET", "/version")]
    requested_images = {path for method, path in requests[2:] if method == "GET"}
    expected_image_paths = {f"/images/{profile.image}/json" for profile in profiles}
    assert requested_images <= expected_image_paths
    if mismatched_profile_id is None:
        assert requested_images == expected_image_paths
    else:
        assert mismatched_image is not None
        assert f"/images/{mismatched_image}/json" in requested_images
    assert all(method == "GET" for method, _path in requests)


def test_docker_probe_rejects_an_api_version_outside_the_daemon_range(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C0: incompatible daemon API is a preflight refusal before image inspection."""
    socket_path = tmp_path / "docker.sock"
    config, endpoint = _docker_config_with_bound_unix_socket(tmp_path, socket_path)
    try:
        requests, _constructors = _install_fake_docker_engine(monkeypatch, api_version="1.40")

        images = _probe_docker(config, (config.profiles[0], config.profiles[1]))
    finally:
        endpoint.close()

    assert images is None
    assert requests == [("GET", "/_ping"), ("GET", "/version")]


def test_docker_probe_rejects_a_symlinked_socket_endpoint_before_client_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3: a configured socket alias is refused before the Docker client is created."""
    real_socket = tmp_path / "daemon.sock"
    endpoint = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    endpoint.bind(str(real_socket))
    alias = tmp_path / "docker.sock"
    alias.symlink_to(real_socket)
    config = replace(
        _service_config(tmp_path),
        docker_socket=alias,
        docker_daemon_uid=os.geteuid(),
    )

    class UnexpectedDockerEngine:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("symlinked Docker endpoint reached client construction")

    monkeypatch.setattr(_host, "DockerEngine", UnexpectedDockerEngine)
    try:
        images = _probe_docker(config, (config.profiles[0], config.profiles[1]))
    finally:
        endpoint.close()

    assert images is None


def test_cgroup_probe_rejects_symlinked_metadata_files(tmp_path: Path) -> None:
    """C3: host cgroup facts cannot be read through an attacker-controlled symlink."""
    root = tmp_path / "cgroup"
    root.mkdir()
    outside = tmp_path / "outside.controllers"
    outside.write_text("cpu memory pids\n", encoding="ascii")
    (root / "cgroup.controllers").symlink_to(outside)
    (root / "cgroup.events").write_text("populated 0\nfrozen 0\n", encoding="ascii")

    with pytest.raises(ExecutionHostPreflightError) as refused:
        _read_cgroup_facts(root, set())

    assert refused.value.code == "cgroup_metadata_unavailable"
