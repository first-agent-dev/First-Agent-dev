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
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from fa import cli
from fa.execution import composition
from fa.execution.client import ExecutionRejectedError, ExecutionUnavailableError, ExecutionUncertainError
from fa.execution.composition import (
    BoundPlanPublisher,
    ClientWorkspaceProvisioner,
    ExecutionBinding,
    ManagedExecution,
    PlanPublication,
    client_workspace_provisioner,
    managed_execution_for_run,
)
from fa.execution.service import SupervisorService, read_config_file
from fa.execution.types import ExecutionContractError, GrantReply, NamespaceRef, Operation
from fa.inner_loop import workflow_controller
from fa.inner_loop.plan_admission import PlanRef, read_plan_snapshot, snapshot_from_bytes
from fa.session.manager import RunContext, SessionManagerError
from fa.session.provisioning import ProvisionMode, ProvisionRequest
from tests.test_execution_service import _registered, exchange
from tests.test_execution_views import native_profile
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site

PLAN_RELATIVE = "worklogs/demo/increments/increment-01-demo.md"


def _document(
    site: Site,
    *,
    uid: int | None = None,
    roots: Path | None = None,
    socket_path: Path | None = None,
    root_id: str = "projects",
) -> dict[str, Any]:
    """One operator config document, exactly the keys ``service.load_config`` demands."""
    return {
        "state_root": str(site.state),
        "socket_path": str(socket_path if socket_path is not None else site.state.parent / "supervisor.sock"),
        "controller_uids": [os.getuid() if uid is None else uid],
        "approved_roots": {root_id: str(site.roots if roots is None else roots)},
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


@contextmanager
def _managed_publisher(site: Site, tmp_path: Path) -> Iterator[tuple[ManagedExecution, Path]]:
    """A live supervisor plus one run's writer, over a workspace whose plan exists."""
    plan_path = site.source / PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(b"# Existing plan\n")
    service_path, yaml_path = _configs(tmp_path, _document(site))
    with SupervisorService(read_config_file(service_path)) as service:
        _registered(service)
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        try:
            managed = managed_execution_for_run(_run(site.source), config_path=yaml_path)
            assert managed is not None
            yield managed, plan_path
        finally:
            stop.set()
            runner.join(timeout=5)
            assert not runner.is_alive()


def test_a_host_side_write_before_the_second_publish_is_refused(site: Site, tmp_path: Path) -> None:
    """C1 (CT121): the authority refuses to commit onto bytes it does not hold.

    Today a host-side stage can still write the project tree under the run's own
    writer. The authority notices at the next commit — `_unchanged` sees a tree that
    is not the current revision — and refuses. This is the behaviour the strict
    `xfail` below is aimed at: the refusal is honest, but the write should never be
    possible in the first place (SLICE4 STEP2).
    """
    with _managed_publisher(site, tmp_path) as (managed, plan_path):
        publisher = BoundPlanPublisher(managed, managed.binding)
        first = publisher.publish_candidate(
            read_plan_snapshot(site.source, Path(PLAN_RELATIVE)),
            snapshot_from_bytes("draft.md", b"# Repaired plan\n"),
        )
        assert first.sha256 != ""
        assert plan_path.read_bytes() == b"# Repaired plan\n"

        (site.source / "src").mkdir(exist_ok=True)
        (site.source / "src" / "host_side.py").write_text("x = 1\n", encoding="utf-8")

        with pytest.raises((ExecutionUncertainError, ExecutionRejectedError)) as error:
            publisher.publish_candidate(
                read_plan_snapshot(site.source, Path(PLAN_RELATIVE)),
                snapshot_from_bytes("draft.md", b"# Repaired again\n"),
            )
        assert error.value.code == "CORRUPT_STATE"
        assert plan_path.read_bytes() == b"# Repaired plan\n"  # the first commit stands


@pytest.mark.xfail(strict=True, reason="SLICE4 STEP2 cutover: host-side stages must stop writing bytes")
def test_the_runs_own_second_publication_survives_a_host_side_write(site: Site, tmp_path: Path) -> None:
    """The limitation, pinned instead of hidden (Q96 = A).

    This asserts what the run's held writer *should* buy it — the authority keeps
    serving this run while host-side stages stop touching the tree. It fails today,
    which is why it is a strict `xfail`: the step that makes host stages respect the
    writer must delete this mark, and the mark cannot rot silently.
    """
    with _managed_publisher(site, tmp_path) as (managed, _plan_path):
        publisher = BoundPlanPublisher(managed, managed.binding)
        publisher.publish_candidate(
            read_plan_snapshot(site.source, Path(PLAN_RELATIVE)),
            snapshot_from_bytes("draft.md", b"# Repaired plan\n"),
        )
        (site.source / "src").mkdir(exist_ok=True)
        (site.source / "src" / "host_side.py").write_text("x = 1\n", encoding="utf-8")
        promoted = publisher.publish_candidate(
            read_plan_snapshot(site.source, Path(PLAN_RELATIVE)),
            snapshot_from_bytes("draft.md", b"# Repaired again\n"),
        )
        assert promoted.sha256 == snapshot_from_bytes("draft.md", b"# Repaired again\n").ref.sha256


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


def test_the_workflow_root_reaches_promotion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """producer-kill-check: drop `plan_publisher=` from the `run_workflow` call site.

    STEP11's EDGE case, the one that would have caught E288: it is not enough that
    the CLI hands over an object, so the handed port is driven through the
    controller's own ``_promote_validated_plan`` and must actually publish.
    """
    client = _RecordingClient()
    binding = ExecutionBinding(NamespaceRef("session-1", "run-1"), "ws-" + "1" * 32)
    grant = GrantReply(Operation.ACQUIRE_WRITER, "2" * 64, None, 1, "rev-" + "3" * 32)
    managed = ManagedExecution(client, binding, grant)  # type: ignore[arg-type]
    workspace = tmp_path / "project"
    workspace.mkdir()
    run = _run(workspace)
    monkeypatch.setattr(cli, "_resolve_workflow_lifecycle", lambda args, run_id: (run_id, None, run, None))
    monkeypatch.setattr(cli, "managed_execution_for_run", lambda *a, **k: managed)
    plan_path = workspace / PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(b"# Existing plan\n")
    published: list[str] = []

    def fake_publish(self: Any, source: Any, candidate: Any, *, deadline: float | None = None) -> Any:
        published.append(candidate.ref.sha256)
        return PlanPublication(
            PlanRef(source.ref.workspace_relative_path, source.ref.source_kind, candidate.ref.sha256),
            "rev-" + "7" * 32,
            False,
        )

    monkeypatch.setattr(ManagedExecution, "publish_plan", fake_publish)
    seen: dict[str, Any] = {}

    def fake_run_workflow(**kwargs: Any) -> tuple[int, None]:
        seen.update(kwargs)
        source = read_plan_snapshot(workspace, Path(PLAN_RELATIVE))
        candidate = snapshot_from_bytes("draft.md", b"# Repaired plan\n")
        validation = workflow_controller._PlanAdmissionValidation(candidate, "PASS", ())
        workflow_controller._promote_validated_plan(source, validation, publisher=kwargs["plan_publisher"])
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
    assert published == [snapshot_from_bytes("draft.md", b"# Repaired plan\n").ref.sha256]
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


def test_the_client_provisioner_answers_with_the_registered_identity(site: Site, tmp_path: Path) -> None:
    """producer-kill-check: report a tree hash the wire does not carry, or a fresh id."""
    service_path, yaml_path = _configs(tmp_path, _document(site))
    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        try:
            provisioner = client_workspace_provisioner(config_path=yaml_path)
            assert isinstance(provisioner, ClientWorkspaceProvisioner)
            request = ProvisionRequest(ProvisionMode.REUSE, "session-1", "run-1", site.source, time.monotonic() + 5)
            provisioned = provisioner(request)
            assert provisioned.registered is True
            assert provisioned.tree_sha256 is None  # the wire answer carries two fields
            assert provisioned.workspace_id == workspace_id
            assert provisioned.revision_id is not None and provisioned.revision_id.startswith("rev-")
            assert provisioner(request) == provisioned  # idempotent: same bytes, same identity
        finally:
            stop.set()
            runner.join(timeout=5)


def test_the_client_provisioner_refuses_what_it_cannot_prove(site: Site, tmp_path: Path) -> None:
    """producer-kill-check: register a root the operator never approved, or invent an id."""
    (tmp_path / "elsewhere").mkdir()
    service_path, yaml_path = _configs(tmp_path, _document(site))
    with SupervisorService(read_config_file(service_path)) as service:
        _registered(service)
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        try:
            provisioner = client_workspace_provisioner(config_path=yaml_path)
            assert provisioner is not None
            deadline = time.monotonic() + 5
            with pytest.raises(SessionManagerError) as refused:
                provisioner(ProvisionRequest(ProvisionMode.PROVISION, "session-1", "run-1", site.source, deadline))
            assert refused.value.code == "provisioning_unavailable"
            with pytest.raises(SessionManagerError) as missing:
                provisioner(ProvisionRequest(ProvisionMode.REUSE, "session-1", "run-1", tmp_path / "absent", deadline))
            assert missing.value.code == "workspace_missing"
            with pytest.raises(SessionManagerError) as escape:
                provisioner(
                    ProvisionRequest(ProvisionMode.REUSE, "session-1", "run-1", tmp_path / "elsewhere", deadline)
                )
            assert escape.value.code == "workspace_escape"
            with pytest.raises(SessionManagerError) as root_itself:
                provisioner(ProvisionRequest(ProvisionMode.REUSE, "session-1", "run-1", site.roots, deadline))
            assert root_itself.value.code == "workspace_escape"
            # A client whose root id the authority does not know: refused, not re-rooted.
            (tmp_path / "stale").mkdir()
            _, stale_yaml = _configs(tmp_path / "stale", _document(site, root_id="legacy"))
            stale = client_workspace_provisioner(config_path=stale_yaml)
            assert stale is not None
            with pytest.raises(SessionManagerError) as denied:
                stale(ProvisionRequest(ProvisionMode.REUSE, "session-1", "run-1", site.source, deadline))
            assert denied.value.code == "workspace_denied"
        finally:
            stop.set()
            runner.join(timeout=5)
    # The same ask once the supervisor is gone: refused, never a host-path answer.
    provisioner = client_workspace_provisioner(config_path=yaml_path)
    assert provisioner is not None
    with pytest.raises(SessionManagerError) as unavailable:
        provisioner(ProvisionRequest(ProvisionMode.REUSE, "session-1", "run-1", site.source, time.monotonic() + 1))
    assert unavailable.value.code == "workspace_provision_failed"


def test_the_manager_takes_its_provisioner_from_the_operator_config(
    monkeypatch: pytest.MonkeyPatch, site: Site, tmp_path: Path
) -> None:
    """producer-kill-check: leave the manager on the host path while an execution service is configured."""
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", config_path)
    args = SimpleNamespace(workspace=site.source)
    assert cli._session_manager_for_args(args).workspace_provisioner is None  # no operator file: host path
    service_path = tmp_path / "execution.json"
    service_path.write_text(json.dumps(_document(site)), encoding="utf-8")
    config_path.write_text(f"execution:\n  service_config: {service_path}\n", encoding="utf-8")
    wired = cli._session_manager_for_args(args).workspace_provisioner
    assert isinstance(wired, ClientWorkspaceProvisioner)
    assert wired.config.approved_roots == {"projects": site.roots}
    # A uid the authority does not list composes nothing — and says so.
    service_path.write_text(json.dumps(_document(site, uid=os.getuid() + 1)), encoding="utf-8")
    with pytest.raises(SessionManagerError) as foreign_uid:
        cli._session_manager_for_args(args)
    assert foreign_uid.value.code == "workspace_denied"
    # A broken present block is a deployment fault, not a reason to work on host bytes.
    config_path.write_text("execution:\n  service_config: ./relative.json\n", encoding="utf-8")
    with pytest.raises(SessionManagerError) as broken:
        cli._session_manager_for_args(args)
    assert broken.value.code == "workspace_config_invalid"
    config_path.unlink()
    assert cli._session_manager_for_args(args).workspace_provisioner is None
