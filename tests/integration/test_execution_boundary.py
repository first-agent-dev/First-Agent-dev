"""C1: the production controller client reaches a real Docker cell, not the host."""

from __future__ import annotations

import json
import shlex
import time
from pathlib import Path
from uuid import uuid4

import pytest

from fa.execution.cgroup import descendants_empty
from fa.execution.docker import DockerEngine
from fa.execution.types import ViewRef
from tests.integration._host import ExecutionHostRuntime

pytestmark = pytest.mark.execution_host


def _cell_for_view(runtime: ExecutionHostRuntime, view: ViewRef) -> str:
    records = [
        record
        for record in runtime._owned_cell_records()
        if record.get("view_ref") == view.to_dict() and isinstance(record.get("container_id"), str)
    ]
    assert records, "the real EXEC must durably bind a Docker container to this view"
    container_ids = {
        container_id for record in records if isinstance((container_id := record.get("container_id")), str)
    }
    assert len(container_ids) == 1, "one interactive view owns one persistent cell"
    return next(iter(container_ids))


def _inspect_cell(runtime: ExecutionHostRuntime, container_id: str) -> dict[str, object]:
    config = runtime.service_config
    assert config.docker_socket is not None
    assert config.docker_daemon_uid is not None
    assert config.docker_api_version is not None
    assert config.docker_timeout_ms is not None
    engine = DockerEngine(
        config.docker_socket,
        daemon_uid=config.docker_daemon_uid,
        api_version=config.docker_api_version,
        rpc_timeout_ms=config.docker_timeout_ms,
    )
    raw = engine._request(
        "GET",
        f"/containers/{container_id}/json",
        body=None,
        status=200,
        deadline=time.monotonic() + min(config.docker_timeout_ms, 10_000) / 1000,
    )
    result = json.loads(raw)
    assert type(result) is dict
    return result


def test_managed_execution_uses_only_the_approved_disposable_view(
    host_runtime: ExecutionHostRuntime,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = host_runtime.register_workspace(files={"src/initial.py": b"INITIAL = True\n"})
    writer = workspace.acquire_writer()
    view = workspace.open_write_view()
    executor = workspace.managed_bash(view)
    view_ref = view.view_ref
    assert view_ref.access.value == "WRITE"

    outside_sentinel = tmp_path / "host-sentinel.txt"
    outside_sentinel.write_text("controller-only sentinel\n", encoding="utf-8")
    secret_name = "FA_I03_HOST_SECRET_" + uuid4().hex[:12].upper()
    secret_value = "must-not-enter-the-cell-" + uuid4().hex
    monkeypatch.setenv(secret_name, secret_value)
    command = "\n".join(
        (
            "set -eu",
            f'test "$(id -u)" = {host_runtime.readiness.write_profile.uid}',
            "test ! -S /var/run/docker.sock",
            f'test "${{{secret_name}+x}}" = ""',
            f"test ! -e {shlex.quote(str(outside_sentinel))}",
            f"if printf 'tampered\\n' > {shlex.quote(str(outside_sentinel))} 2>/dev/null; then exit 73; fi",
            "printf 'CELL_BOUNDARY_OK\\n'",
            "printf 'CELL_WRITE\\n' > src/managed-cell.txt",
        )
    )

    result = executor.run(command, timeout=30)
    assert result.exit_code == 0, result.stdout
    assert "CELL_BOUNDARY_OK" in result.stdout
    assert outside_sentinel.read_text(encoding="utf-8") == "controller-only sentinel\n"
    assert not (workspace.root / "src/managed-cell.txt").exists(), (
        "cell writes remain in the private view before publish"
    )

    container_id = _cell_for_view(host_runtime, view_ref)
    document = _inspect_cell(host_runtime, container_id)
    config = document.get("Config")
    host_config = document.get("HostConfig")
    mounts = document.get("Mounts")
    assert type(config) is dict and type(host_config) is dict and type(mounts) is list
    expected_user = f"{host_runtime.readiness.write_profile.uid}:{host_runtime.readiness.write_profile.gid}"
    assert config.get("User") == expected_user
    assert host_config.get("Privileged") is False
    assert host_config.get("ReadonlyRootfs") is True
    assert host_config.get("CapDrop") == ["ALL"]
    assert host_config.get("NetworkMode") == "none"
    assert secret_value not in json.dumps(config.get("Env", []))

    trusted = host_runtime.service.authority.execution_trusted(view_ref)
    assert trusted is not None
    _namespace, source, scratch, cache, environment = trusted
    mount_sources = {
        Path(item["Source"]).resolve() for item in mounts if type(item) is dict and isinstance(item.get("Source"), str)
    }
    assert source.resolve() in mount_sources
    assert source.resolve() != workspace.root.resolve()
    assert workspace.root.resolve() not in mount_sources
    assert outside_sentinel.resolve() not in mount_sources
    docker_socket = host_runtime.service_config.docker_socket
    assert docker_socket is not None
    assert docker_socket.resolve() not in mount_sources
    assert scratch.resolve() in mount_sources
    assert cache.resolve() in mount_sources
    if environment is not None:
        assert environment.resolve() in mount_sources
    assert all(item.get("Destination") != "/var/run/docker.sock" for item in mounts if type(item) is dict)

    assert (
        descendants_empty(
            host_runtime.service_config.cgroup_root,
            host_runtime.readiness.write_profile.cgroup_parent,
            container_id,
        )
        is False
    ), "the live interactive cell must be observed populated before it is stopped"

    publication = workspace.publish(view)
    assert workspace.revision_id == publication.revision_id
    assert (workspace.root / "src/managed-cell.txt").read_text(encoding="utf-8") == "CELL_WRITE\n"
    assert outside_sentinel.read_text(encoding="utf-8") == "controller-only sentinel\n"
    assert host_runtime.assert_owned_cells_terminal() >= 1

    # Recording is observational only: operation metadata never includes either grant or tool body.
    trace = json.dumps(host_runtime.events, sort_keys=True)
    assert writer.capability not in trace
    assert view.grant.capability not in trace
    assert secret_value not in trace
