"""CT116: one composition supplies the managed execution, and nothing else does.

The tricky half is the negative space: an absent key, a foreign uid, a workspace
outside the approved roots and a refused writer must all end at ``None`` — the
controller then fails closed (CT115) instead of publishing over a host path.
"""

from __future__ import annotations

import json
import os
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from fa import cli
from fa.execution.client import ExecutionRejectedError, ExecutionUnavailableError, ExecutionUncertainError
from fa.execution.composition import (
    BoundPlanPublisher,
    ExecutionBinding,
    ManagedExecution,
    managed_execution_for_run,
)
from fa.execution.service import SupervisorService, read_config_file
from fa.execution.types import ExecutionContractError, GrantReply, NamespaceRef, Operation
from fa.inner_loop.plan_admission import read_plan_snapshot, snapshot_from_bytes
from fa.session.manager import RunContext
from tests.test_execution_service import _registered, exchange
from tests.test_execution_views import native_profile
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site

PLAN_RELATIVE = "worklogs/demo/increments/increment-01-demo.md"


def _document(
    site: Site, *, uid: int | None = None, roots: Path | None = None, socket_path: Path | None = None
) -> dict[str, Any]:
    """One operator config document, exactly the keys ``service.load_config`` demands."""
    return {
        "state_root": str(site.state),
        "socket_path": str(socket_path if socket_path is not None else site.state.parent / "supervisor.sock"),
        "controller_uids": [os.getuid() if uid is None else uid],
        "approved_roots": {"projects": str(site.roots if roots is None else roots)},
        "profiles": [asdict(native_profile())],
        "rpc_timeout_ms": 2000,
        "lock_timeout_ms": 25,
        "view_profile_id": native_profile().profile_id,
    }


def _configs(tmp_path: Path, document: dict[str, Any]) -> tuple[Path, Path]:
    service_path = tmp_path / "execution.json"
    service_path.write_text(json.dumps(document), encoding="utf-8")
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(f"execution:\n  service_config: {service_path}\n", encoding="utf-8")
    return service_path, yaml_path


def _run(workspace: Path) -> RunContext:
    """The run context alone carries the namespace and the workspace (STEP8)."""
    return RunContext("run-1", "session-1", workspace, workspace / ".db", workspace / "logs")


@contextmanager
def _listening_socket(path: Path) -> Iterator[list[bool]]:
    """A real endpoint that records whether anything ever connected to it."""
    path.parent.mkdir(mode=0o700, exist_ok=True)
    path.parent.chmod(0o700)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    listener.listen(8)
    listener.settimeout(0.05)
    reached: list[bool] = []
    stop = threading.Event()

    def accept_until_stopped() -> None:
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            reached.append(True)
            connection.close()

    worker = threading.Thread(target=accept_until_stopped, daemon=True)
    worker.start()
    try:
        yield reached
    finally:
        stop.set()
        worker.join(timeout=2)
        listener.close()


class _RecordingClient:
    """Stands in for the transport only where the test asserts the CLI's own calls."""

    def __init__(self) -> None:
        self.calls: list[Operation] = []

    def request(self, operation: Operation, **_: Any) -> dict[str, Any]:
        self.calls.append(operation)
        return {}


def test_without_an_execution_block_there_is_no_managed_execution(tmp_path: Path) -> None:
    """producer-kill-check: fall back to a default socket when the key is absent."""
    run = _run(tmp_path)
    empty = tmp_path / "config.yaml"
    empty.write_text("capabilities:\n  ENABLE_SERVER_OPS: false\n", encoding="utf-8")
    assert managed_execution_for_run(run, config_path=empty) is None
    assert managed_execution_for_run(run, config_path=tmp_path / "missing.yaml") is None
    # A legacy `--run-id`-only invocation resolves no contexts at all.
    assert managed_execution_for_run(None) is None


def test_the_managed_execution_publishes_through_the_operator_config(site: Site, tmp_path: Path) -> None:
    """producer-kill-check: compose a client that skips registration or the writer grant."""
    plan_path = site.source / PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(b"# Existing plan\n")
    source = read_plan_snapshot(site.source, Path(PLAN_RELATIVE))
    candidate = snapshot_from_bytes("draft.md", b"# Repaired plan\n")
    service_path, yaml_path = _configs(tmp_path, _document(site))
    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        try:
            run = _run(site.source)
            managed = managed_execution_for_run(run, config_path=yaml_path)
            assert managed is not None
            assert managed.binding == ExecutionBinding(NamespaceRef("session-1", "run-1"), workspace_id)
            publisher = BoundPlanPublisher(managed, managed.binding)
            promoted = publisher.publish_candidate(source, candidate)
            assert promoted.sha256 == candidate.ref.sha256
            assert plan_path.read_bytes() == candidate.utf8_bytes
            with pytest.raises(ExecutionContractError):
                BoundPlanPublisher(managed, ExecutionBinding(NamespaceRef("session-1", "run-2"), workspace_id))
            assert managed.close() is True
            # The writer is back: a second acquisition must not be WORKSPACE_BUSY.
            again = managed_execution_for_run(run, config_path=yaml_path)
            assert again is not None
            assert again.close() is True
        finally:
            stop.set()
            runner.join(timeout=5)
            assert not runner.is_alive()


def test_the_guards_not_a_dead_socket_decide_which_runs_are_managed(site: Site, tmp_path: Path) -> None:
    """producer-kill-check: accept any uid, or any workspace the caller names."""
    service_path, yaml_path = _configs(tmp_path, _document(site))
    with SupervisorService(read_config_file(service_path)) as service:
        _registered(service)
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        try:
            run = _run(site.source)
            control = managed_execution_for_run(run, config_path=yaml_path)
            assert control is not None  # Same document, same socket: every None below is a guard.
            assert control.close() is True
        finally:
            stop.set()
            runner.join(timeout=5)

    # The rejected runs are not merely unconnectable: they must never reach a
    # socket at all, or a wrong config would still be answered by a host path.
    (tmp_path / "elsewhere").mkdir()
    listener = tmp_path / "watched" / "supervisor.sock"
    with _listening_socket(listener) as reached:
        (tmp_path / "foreign").mkdir()
        _, foreign = _configs(tmp_path / "foreign", _document(site, uid=os.getuid() + 1, socket_path=listener))
        assert managed_execution_for_run(run, config_path=foreign) is None
        (tmp_path / "outside").mkdir()
        _, outside = _configs(tmp_path / "outside", _document(site, socket_path=listener))
        outside_run = _run(tmp_path / "elsewhere")
        assert managed_execution_for_run(outside_run, config_path=outside) is None
        (tmp_path / "rooted").mkdir()
        _, rooted = _configs(tmp_path / "rooted", _document(site, socket_path=listener))
        root_run = _run(site.roots)
        assert managed_execution_for_run(root_run, config_path=rooted) is None
        assert reached == []


def test_a_broken_execution_block_is_no_execution(site: Site, tmp_path: Path) -> None:
    """producer-kill-check: resolve a relative or traversing `service_config` against the cwd."""
    _, good = _configs(tmp_path, _document(site))
    run = _run(site.source)
    for body in ("./execution.json", "../execution.json", f'{{"service_config": "{good}"}}'):
        broken = tmp_path / "broken.yaml"
        broken.write_text(f"execution:\n  service_config: {body}\n", encoding="utf-8")
        assert managed_execution_for_run(run, config_path=broken) is None, body


def test_a_refused_writer_grant_yields_none(site: Site, tmp_path: Path) -> None:
    """producer-kill-check: keep a half-built execution when acquisition is refused."""
    service_path, yaml_path = _configs(tmp_path, _document(site))
    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        held = exchange(service, Operation.ACQUIRE_WRITER, {"workspace_id": workspace_id}, request_id="7" * 32)
        assert held["status"] == "OK"
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        try:
            run = _run(site.source)
            assert managed_execution_for_run(run, config_path=yaml_path) is None
        finally:
            stop.set()
            runner.join(timeout=5)


def test_the_workflow_root_supplies_the_managed_publisher(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """producer-kill-check: drop `plan_publisher=` from the `run_workflow` call site."""
    client = _RecordingClient()
    binding = ExecutionBinding(NamespaceRef("session-1", "run-1"), "ws-" + "1" * 32)
    grant = GrantReply(Operation.ACQUIRE_WRITER, "2" * 64, None, 1, "rev-" + "3" * 32)
    managed = ManagedExecution(client, binding, grant)  # type: ignore[arg-type]
    workspace = tmp_path / "project"
    workspace.mkdir()
    run = _run(workspace)
    monkeypatch.setattr(cli, "_resolve_workflow_lifecycle", lambda args, run_id: (run_id, None, run, None))
    monkeypatch.setattr(cli, "managed_execution_for_run", lambda *a, **k: managed)
    seen: dict[str, Any] = {}

    def fake_run_workflow(**kwargs: Any) -> tuple[int, None]:
        seen.update(kwargs)
        return 0, None

    monkeypatch.setattr(cli, "run_workflow", fake_run_workflow)
    args = SimpleNamespace(
        task="ship it",
        task_planner=None,
        task_coder=None,
        task_eval=None,
        run_id="run-1",
        mode="linear",
        roles="planner",
        inject=None,
        max_repairs=None,
        max_replans=None,
        plan=None,
        session_id="session-1",
        workspace=str(workspace),
        config=tmp_path / "models.yaml",
        max_turns=1,
        output_mode="console",
    )
    assert cli._cmd_workflow(args) == 0
    publisher = seen["plan_publisher"]
    assert isinstance(publisher, BoundPlanPublisher)
    assert client.calls == [Operation.RELEASE]  # the writer is released when the run returns


@pytest.mark.parametrize(
    "failure",
    [
        ExecutionUncertainError(None),
        ExecutionRejectedError("NOT_OWNER", None),
        ExecutionUnavailableError(),
    ],
    ids=["uncertain", "rejected", "unavailable"],
)
def test_a_release_that_is_not_confirmed_is_reported_and_never_retried(failure: Exception) -> None:
    """producer-kill-check: treat any failed RELEASE as a settled writer."""

    class _Failing:
        def __init__(self) -> None:
            self.calls: list[Operation] = []

        def request(self, operation: Operation, **_: Any) -> dict[str, Any]:
            self.calls.append(operation)
            raise failure

    client = _Failing()
    binding = ExecutionBinding(NamespaceRef("session-1", "run-1"), "ws-" + "4" * 32)
    grant = GrantReply(Operation.ACQUIRE_WRITER, "5" * 64, None, 1, "rev-" + "6" * 32)
    managed = ManagedExecution(client, binding, grant)  # type: ignore[arg-type]
    assert managed.close() is False
    assert client.calls == [Operation.RELEASE]
