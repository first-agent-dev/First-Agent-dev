"""C1: stop a real descendant tree and require kernel cgroup terminality evidence."""

from __future__ import annotations

import json
import re
import time

import pytest

from fa.execution.cgroup import descendants_empty
from fa.execution.docker import DockerEngine
from tests.integration._host import ExecutionHostRuntime

pytestmark = pytest.mark.execution_host


def test_stopping_a_view_kills_its_background_descendant_and_proves_cgroup_empty(
    host_runtime: ExecutionHostRuntime,
) -> None:
    workspace = host_runtime.register_workspace(files={"src/keep.py": b"KEEP = True\n"})
    workspace.acquire_writer()
    view = workspace.open_write_view()
    executor = workspace.managed_bash(view)
    port = workspace.port(view)

    launched = executor.run(
        "set -eu\nsleep 300 >/dev/null 2>&1 &\nchild=$!\nprintf '%s\\n' \"$child\" > src/child.pid\n"
        "kill -0 \"$child\"\nprintf 'DESCENDANT_LIVE\\n'",
        timeout=30,
    )
    assert launched.exit_code == 0, launched.stdout
    assert "DESCENDANT_LIVE" in launched.stdout
    pid_text = port.read_file("src/child.pid").content.strip()
    assert re.fullmatch(r"[1-9][0-9]*", pid_text)
    confirmed_live = executor.run(f"kill -0 {pid_text} && printf 'DESCENDANT_STILL_LIVE\\n'", timeout=30)
    assert confirmed_live.exit_code == 0, confirmed_live.stdout
    assert "DESCENDANT_STILL_LIVE" in confirmed_live.stdout

    cells = [
        record
        for record in host_runtime._owned_cell_records()
        if record.get("view_ref") == view.view_ref.to_dict() and isinstance(record.get("container_id"), str)
    ]
    assert cells, "the journal must bind the running descendant to its actual Docker cell"
    container_ids = {record["container_id"] for record in cells}
    assert len(container_ids) == 1
    container_id = next(iter(container_ids))
    assert (
        descendants_empty(
            host_runtime.service_config.cgroup_root,
            host_runtime.readiness.write_profile.cgroup_parent,
            container_id,
        )
        is False
    ), "the kernel must report the live cell populated before the stop request"

    workspace.close()
    assert workspace.closed
    assert not (workspace.root / "src/child.pid").exists(), "an unaccepted view is rejected, not published"
    assert host_runtime.assert_owned_cells_terminal() >= 1
    assert (
        descendants_empty(
            host_runtime.service_config.cgroup_root,
            host_runtime.readiness.write_profile.cgroup_parent,
            container_id,
        )
        is True
    )

    config = host_runtime.service_config
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
    inspected = json.loads(raw)
    assert type(inspected) is dict
    state = inspected.get("State")
    assert type(state) is dict
    assert state.get("Status") == "exited"
    assert state.get("Running") is False
    assert state.get("Pid") == 0
