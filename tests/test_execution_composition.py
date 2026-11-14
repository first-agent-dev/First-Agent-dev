"""CT116: one composition supplies the managed execution, and nothing else does.

The tricky half is the negative space: an absent key, a foreign uid, a workspace
outside the approved roots and a refused writer must all end at ``None`` — the
controller then fails closed (CT115) instead of publishing over a host path.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import shlex
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stderr
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from fa import cli
from fa.execution import composition
from fa.execution.cell_worker import serve, serve_once
from fa.execution.client import (
    ExecutionClient,
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
    PlanPublication,
    StagePublication,
)
from fa.execution.composition import (
    BoundPlanPublisher,
    ClientWorkspaceProvisioner,
    ExecutionBinding,
    ManagedExecution,
    client_workspace_provisioner,
    managed_execution_for_run,
)
from fa.execution.profiles import READ_SCRATCH_BYTES
from fa.execution.service import SupervisorService, read_config_file
from fa.execution.supervisor import SupervisorError
from fa.execution.types import (
    Access,
    ExecutionContractError,
    GrantReply,
    NamespaceRef,
    Operation,
    ViewPurpose,
    ViewRef,
)
from fa.inner_loop import workflow_controller
from fa.inner_loop.plan_admission import PlanRef, read_plan_snapshot, snapshot_from_bytes
from fa.inner_loop.plan_promotion import PlanPromotionError
from fa.inner_loop.registry import ToolResult
from fa.inner_loop.state import EventLog
from fa.providers.base import ResponseInfo
from fa.runtime.pty_pool import PtyPool
from fa.session.manager import RunContext, SessionContext, SessionManagerError
from fa.session.provisioning import ProvisionMode, ProvisionRequest
from fa.workspace_bootstrap import ReadyStatus
from tests.test_execution_backend import CID as CELL_CID
from tests.test_execution_backend import UPGRADE, CountingWorker, MuxWorker
from tests.test_execution_docker import Endpoint, Reply
from tests.test_execution_service import _registered, exchange
from tests.test_execution_views import native_profile, read_only_profile
from tests.test_execution_workspace import Site, install_environment_artifact
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
        "profiles": [asdict(native_profile()), asdict(read_only_profile())],
        "rpc_timeout_ms": 2000,
        "lock_timeout_ms": 25,
        "view_profile_id": native_profile().profile_id,
        "read_only_profile_id": read_only_profile().profile_id,
    }


def _status(site: Site, workspace_id: str) -> dict[str, Any]:
    """The workspace's own record, read the way the authority writes it."""
    return json.loads((site.state / "workspaces" / workspace_id / "workspace.json").read_text())


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


def test_managed_stage_revision_advances_only_after_authority_publication() -> None:
    """The next stage can use only the revision returned by a successful publish."""

    class StageClient:
        publication: StagePublication | None = None
        fail = False

        def publish_stage(self, *_: Any, **__: Any) -> StagePublication:
            if self.fail:
                raise ExecutionRejectedError("publish-refused", None)
            assert self.publication is not None
            return self.publication

    client = StageClient()
    binding = ExecutionBinding(NamespaceRef("session-1", "run-1"), "ws-" + "1" * 32)
    initial_revision = "rev-" + "3" * 32
    managed = ManagedExecution(
        client,  # type: ignore[arg-type]
        binding,
        GrantReply(Operation.ACQUIRE_WRITER, "2" * 64, None, 1, initial_revision),
    )
    stage_grant = GrantReply(
        Operation.CREATE_VIEW,
        "4" * 64,
        ViewRef(
            binding.workspace_id,
            "view-" + "5" * 32,
            initial_revision,
            "run-1",
            1,
            Access.WRITE,
            ViewPurpose.MUTATION,
        ),
        None,
        None,
    )
    client.publication = StagePublication(
        "seal-" + "6" * 32,
        "rev-" + "7" * 32,
        "8" * 64,
        "op-" + "9" * 32,
    )

    assert managed.current_revision_id == initial_revision
    assert managed.publish_stage(stage_grant) is client.publication
    assert managed.current_revision_id == client.publication.revision_id

    current_revision = managed.current_revision_id
    client.fail = True
    with pytest.raises(ExecutionRejectedError):
        managed.publish_stage(stage_grant)
    assert managed.current_revision_id == current_revision


def test_without_an_execution_block_there_is_no_managed_execution(tmp_path: Path) -> None:
    """producer-kill-check: fall back to a default socket when the key is absent."""
    run = _run(tmp_path)
    empty = tmp_path / "config.yaml"
    empty.write_text("capabilities:\n  ENABLE_SERVER_OPS: false\n", encoding="utf-8")
    assert managed_execution_for_run(run, config_path=empty) is None
    assert managed_execution_for_run(run, config_path=tmp_path / "missing.yaml") is None
    # A legacy `--run-id`-only invocation resolves no contexts at all.
    assert managed_execution_for_run(None) is None


def test_session_cli_refuses_missing_provisioner_before_workspace_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing managed backend cannot trigger host clone, attach, or readiness."""
    lifecycle_calls: list[str] = []

    class _HostOnlyManager:
        workspace_provisioner: None = None

        def create_or_attach_session(self, **_kwargs: Any) -> Any:
            lifecycle_calls.append("create_or_attach")
            raise AssertionError("host lifecycle ran without a managed provisioner")

    monkeypatch.setattr(cli, "_session_manager_for_args", lambda _args: _HostOnlyManager())

    with pytest.raises(SessionManagerError) as refused:
        cli._resolve_cli_run_context(argparse.Namespace(session_id="session-test", workspace=None, run_id=None))

    assert refused.value.code == "managed_execution_unavailable"
    assert lifecycle_calls == []


def test_r01_wrapper_run_refuses_overlapping_new_workspace_before_lifecycle_or_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 Q128-B: wrapper preflight refuses an overlapping new root without effects.

    The real ``_cmd_run`` caller uses a real SessionManager with an active
    manifest/DB. Producer kill-check: remove SessionManager's overlap decision.
    EDGE kill-check: bypass ``validate_new_workspace_disjoint`` at the CLI call.
    Either mutant must lose the early ``workspace_overlap`` refusal or perform
    a provider/lifecycle effect.
    """
    from tests.test_cli import _FAKE_MODELS_YAML, _TEST_SECRETS, _make_run_args, _ScriptedTransport
    from tests.test_session_lifecycle import _manager as make_session_manager

    manager = make_session_manager(tmp_path)
    active = manager.create_or_attach_session(session_id=None, workspace_override=None)
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    args = _make_run_args(workspace=tmp_path, config=config, run_id="overlap-preflight")
    args.session_id = None
    args.resume = False
    args.output_mode = "console"
    args.detail = "standard"
    args.no_color = False
    args.workspace = "nested"
    transport = _ScriptedTransport([])

    monkeypatch.setattr(cli, "_session_manager_for_args", lambda _args: manager)
    monkeypatch.setenv("FA_WRAPPER_ACTIVE_WORKSPACE", str(active.workspace_path))
    manifests_before = tuple(sorted(manager.sessions_root.glob("*/manifest.json")))
    nested_workspace = active.workspace_path / "nested"

    code = cli._cmd_run(args, transport=transport, secrets=_TEST_SECRETS)
    stderr = capsys.readouterr().err

    assert transport.calls == []
    assert tuple(sorted(manager.sessions_root.glob("*/manifest.json"))) == manifests_before
    assert not nested_workspace.exists()
    assert args.workspace == "nested" and args.session_id is None
    assert code == 2 and "[workspace_overlap]" in stderr


def test_session_stage_refuses_missing_managed_execution_before_registry_or_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A provisioned session still cannot fall back if its run writer is unavailable."""
    run = _run(tmp_path)
    built: list[str] = []

    monkeypatch.setattr(cli, "_execution_for_cli_stage", lambda *_args: (None, False))

    def forbidden_registry(*_args: Any, **_kwargs: Any) -> Any:
        built.append("registry")
        raise AssertionError("host registry was built without managed execution")

    outcome, release_confirmed = cli._run_cli_stage(
        args=argparse.Namespace(),
        run_context=run,
        run_id=run.run_id,
        run_log_dir=run.run_log_dir,
        session_db=None,
        log=EventLog(run.run_log_dir / "events.jsonl", run_id=run.run_id),
        workspace=run.workspace_path,
        role="chat",
        plan_ref=None,
        build_registry=forbidden_registry,
        drive=forbidden_registry,
    )

    assert outcome is None
    assert release_confirmed
    assert built == []
    assert "managed execution unavailable; refusing host-path stage" in capsys.readouterr().err


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
            assert managed.view_profile == native_profile()
            initial_revision = managed.current_revision_id
            assert initial_revision == managed.grant.revision_id
            publisher = BoundPlanPublisher(managed, managed.binding)
            promoted = publisher.publish_candidate(source, candidate)
            assert promoted.sha256 == candidate.ref.sha256
            assert managed.current_revision_id != initial_revision
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

    An out-of-band host write can change the canonical tree while the run owns its
    writer. At the next commit, `_unchanged` detects that the tree is not the current
    revision and refuses; the managed WRITE-view control below proves the supported
    stage path can instead publish its bytes and continue.
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
        assert isinstance(error.value, (ExecutionUncertainError, ExecutionRejectedError))
        assert error.value.code == "CORRUPT_STATE"
        assert plan_path.read_bytes() == b"# Repaired plan\n"  # the first commit stands


def test_the_runs_own_second_publication_survives_a_managed_stage_write(site: Site, tmp_path: Path) -> None:
    """C1: WRITE-view bytes advance the same run's revision before a second plan publish.

    A raw host-side write is correctly rejected by the authority as corrupt state;
    this test instead exercises the managed composition the stage must use.
    """
    from fa.execution.tool_port import ClientWorkspacePort

    # The parent directory is part of the admitted starting revision; only the file
    # mutation itself is performed through the managed WRITE view.
    (site.source / "src").mkdir(exist_ok=True)
    with _managed_publisher(site, tmp_path) as (managed, plan_path):
        publisher = BoundPlanPublisher(managed, managed.binding)
        first = publisher.publish_candidate(
            read_plan_snapshot(site.source, Path(PLAN_RELATIVE)),
            snapshot_from_bytes("draft.md", b"# Repaired plan\n"),
        )
        assert plan_path.read_bytes() == b"# Repaired plan\n"

        stage_grant = managed.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.MUTATION,
            base_revision=managed.current_revision_id,
            plan_ref=first,
        )
        view = stage_grant.view_ref
        assert view is not None
        port = ClientWorkspacePort(
            managed.client,
            namespace=managed.binding.namespace,
            view=view,
            grant=stage_grant,
        )
        written = port.write_file("src/managed_stage.py", "x = 1\n")
        assert written.bytes == len("x = 1\n")
        port.suspend()

        stage_publication = managed.publish_stage(stage_grant)
        assert managed.current_revision_id == stage_publication.revision_id
        assert (site.source / "src" / "managed_stage.py").read_text(encoding="utf-8") == "x = 1\n"

        next_candidate = snapshot_from_bytes("draft.md", b"# Repaired again\n")
        second = publisher.publish_candidate(read_plan_snapshot(site.source, Path(PLAN_RELATIVE)), next_candidate)
        assert first.sha256 != second.sha256
        assert second.sha256 == next_candidate.ref.sha256
        assert plan_path.read_bytes() == next_candidate.utf8_bytes
        assert managed.close() is True


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
    args = argparse.Namespace(
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
    assert seen["managed_execution"] is managed
    assert published == [snapshot_from_bytes("draft.md", b"# Repaired plan\n").ref.sha256]
    assert client.calls == [Operation.RELEASE]  # the writer is released when the run returns


def test_workflow_root_keeps_plan_unchanged_when_local_authority_refuses_publication(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R25: a real managed PUBLISH refusal has no host-path write fallback."""
    plan_path = site.source / PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        "Plan-ID: PLAN-cli-fixture\n\n## SLICE1: CLI routing fixture\n"
        "CONTRACTS:\n  CT9001 [CONSTRAINT]: fixture input remains present.\n"
        "TESTS: tests/test_fixture_contract.py\n",
        encoding="utf-8",
    )
    test_path = site.source / "tests/test_fixture_contract.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_fixture_input():\n    assert True\n", encoding="utf-8")
    source = read_plan_snapshot(site.source, Path(PLAN_RELATIVE))
    original_bytes = plan_path.read_bytes()
    candidate_text = source.text.replace("fixture input remains present.", "candidate revision remains valid.")
    assert candidate_text != source.text
    candidate = snapshot_from_bytes("draft.md", candidate_text.encode("utf-8"))
    validated = workflow_controller._validate_plan_admission(candidate)
    assert validated.outcome == "PASS"

    service_path, yaml_path = _configs(tmp_path, _document(site))
    refusal_operations: list[str] = []
    run = _run(site.source)

    class _WorkflowManager:
        @staticmethod
        def resolve_workflow_workspace(**_kwargs: Any) -> Path:
            return site.source

    monkeypatch.setattr(cli, "_session_manager_for_args", lambda _args: _WorkflowManager())
    monkeypatch.setattr(cli, "_resolve_workflow_lifecycle", lambda _args, run_id: (run_id, None, run, None))
    managed_instances: list[ManagedExecution] = []

    def real_local_execution(run_context: RunContext) -> ManagedExecution | None:
        managed = managed_execution_for_run(run_context, config_path=yaml_path)
        if managed is not None:
            managed_instances.append(managed)
        return managed

    monkeypatch.setattr(cli, "managed_execution_for_run", real_local_execution)
    promotion_failures: list[tuple[str, bool]] = []

    def fake_run_workflow(**kwargs: Any) -> tuple[int, None]:
        assert isinstance(kwargs["plan_publisher"], BoundPlanPublisher)
        assert kwargs["managed_execution"] is managed_instances[0]
        with pytest.raises(PlanPromotionError) as refused:
            workflow_controller._promote_validated_plan(
                source,
                validated,
                publisher=kwargs["plan_publisher"],
            )
        promotion_failures.append((refused.value.rule, refused.value.replaced))
        return 2, None

    monkeypatch.setattr(cli, "run_workflow", fake_run_workflow)
    args = argparse.Namespace(
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
        plan=Path(PLAN_RELATIVE),
        session_id="session-1",
        workspace=str(site.source),
        config=tmp_path / "models.yaml",
        max_turns=1,
        output_mode="console",
    )

    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)

        def refuse_before_commit(*_args: Any, **kwargs: Any) -> Any:
            refusal_operations.append(str(kwargs["operation_id"]))
            raise SupervisorError("INPUT_POLICY")

        monkeypatch.setattr(service.authority, "publish_candidate_plan", refuse_before_commit)
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        try:
            assert cli._cmd_workflow(args) == 2
        finally:
            stop.set()
            runner.join(timeout=5)
            assert not runner.is_alive()

        assert site.metadata({"workspace_id": workspace_id})["status"] == "AVAILABLE"

    assert len(managed_instances) == 1
    assert promotion_failures == [("prepare-failed", False)]
    assert len(refusal_operations) == 1  # the PUBLISH is not replayed after a refusal
    assert plan_path.read_bytes() == original_bytes


class _ManagedChatProviderOracle:
    """Deterministic provider used to exercise the managed-chat child boundary."""

    def __init__(self, workspace: Path, *, exec_command: str = "printf child-probe", parent_role: str = "chat") -> None:
        self.workspace = workspace
        self.exec_command = exec_command
        self.parent_role = parent_role
        self.observed: list[tuple[tuple[str, bytes], ...]] = []
        self.child_snapshot: list[tuple[tuple[str, bytes], ...]] = []
        self.provider_calls = 0
        self.parent_calls = 0
        self.child_calls = 0
        self.eval_calls = 0
        self.eval_requests: list[Any] = []
        self.child_project_write = False

    def canonical_snapshot(self) -> tuple[tuple[str, bytes], ...]:
        excluded = {".git", ".fa", ".venv", ".env"}
        return tuple(
            (path.relative_to(self.workspace).as_posix(), path.read_bytes())
            for path in sorted(self.workspace.rglob("*"))
            if path.is_file()
            and not path.is_symlink()
            and not excluded.intersection(path.relative_to(self.workspace).parts)
        )

    def __call__(self, _chain: Any, request: Any, *, logical_call_id: str | None = None) -> tuple[Any, str, list[Any]]:
        self.provider_calls += 1
        tool_names = {
            str(tool.get("function", {}).get("name", ""))
            for tool in request.tools
            if isinstance(tool.get("function"), dict)
        }
        is_eval = any(
            message.get("role") == "system"
            and "you are the first-agent evaluator" in str(message.get("content", "")).lower()
            for message in request.messages
        )
        if self.parent_role == "coder" and is_eval:
            self.eval_calls += 1
            self.eval_requests.append(request)
            return (
                ResponseInfo("### Verdict\nPASS\n### Step results\n- S1: PASS - verified\n", 1, 1, "stop"),
                logical_call_id or "managed-eval",
                [],
            )
        if tool_names == {"fs_read_file", "fs_run_bash"}:
            self.child_calls += 1
            assert "fs_write_file" not in tool_names and "invoke_workflow" not in tool_names
            assert "fix typo in README" not in json.dumps(request.messages)
            user_messages = [message.get("content") for message in request.messages if message.get("role") == "user"]
            assert user_messages == ["Task: Read README.md and report the source note."]
            if self.child_calls == 1:
                call = {
                    "id": "managed-child-exec",
                    "type": "function",
                    "function": {
                        "name": "fs_run_bash",
                        "arguments": json.dumps({"command": self.exec_command}),
                    },
                }
                return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "managed-child", []
            if self.child_calls == 2:
                call = {
                    "id": "managed-child-read",
                    "type": "function",
                    "function": {
                        "name": "fs_read_file",
                        "arguments": json.dumps({"path": "README.md"}),
                    },
                }
                return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "managed-child", []
            assert self.child_calls == 3
            return ResponseInfo("README contains source note.", 1, 1, "stop"), logical_call_id or "managed-child", []

        if "fs_spawn_subagent" not in tool_names:
            self.parent_calls += 1
            return (
                ResponseInfo("Managed child tool unavailable.", 1, 1, "stop"),
                logical_call_id or "managed-parent",
                [],
            )

        if self.parent_role == "planner":
            self.parent_calls += 1
            if self.parent_calls == 1:
                snapshot = self.canonical_snapshot()
                self.observed.append(snapshot)
                self.child_snapshot.append(snapshot)
                call = {
                    "id": "managed-planner-spawn",
                    "type": "function",
                    "function": {
                        "name": "fs_spawn_subagent",
                        "arguments": json.dumps({"task": "Read README.md and report the source note."}),
                    },
                }
                return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "managed-planner", []
            assert self.parent_calls == 2
            self.child_project_write = self.child_snapshot != [self.canonical_snapshot()]
            assert not self.child_project_write, "child changed project bytes before planner resumed"
            assert self.observed == [self.canonical_snapshot()]
            return ResponseInfo("Planner review complete.", 1, 1, "stop"), logical_call_id or "managed-planner", []

        if self.parent_role == "coder":
            self.parent_calls += 1
            assert "fs_write_file" in tool_names
            if self.parent_calls == 1:
                self.observed.append(self.canonical_snapshot())
                call = {
                    "id": "managed-coder-prepare",
                    "type": "function",
                    "function": {
                        "name": "pr_prepare",
                        "arguments": json.dumps({"intent": "CHORE", "invariant": "n/a"}),
                    },
                }
                return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "managed-coder", []
            if self.parent_calls == 2:
                self.child_snapshot.append(self.canonical_snapshot())
                call = {
                    "id": "managed-coder-spawn",
                    "type": "function",
                    "function": {
                        "name": "fs_spawn_subagent",
                        "arguments": json.dumps({"task": "Read README.md and report the source note."}),
                    },
                }
                return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "managed-coder", []
            assert self.parent_calls == 3
            self.child_project_write = self.child_snapshot != [self.canonical_snapshot()]
            assert not self.child_project_write
            assert self.observed == [self.canonical_snapshot()]
            return ResponseInfo("Coder review complete.", 1, 1, "stop"), logical_call_id or "managed-coder", []

        self.parent_calls += 1
        assert "fs_write_file" in tool_names
        if self.parent_calls == 1:
            self.observed.append(self.canonical_snapshot())
            call = {
                "id": "managed-chat-prepare",
                "type": "function",
                "function": {
                    "name": "pr_prepare",
                    "arguments": json.dumps({"intent": "CHORE", "invariant": "n/a"}),
                },
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "managed-chat", []
        if self.parent_calls == 2:
            self.child_snapshot.append(self.canonical_snapshot())
            call = {
                "id": "managed-chat-spawn",
                "type": "function",
                "function": {
                    "name": "fs_spawn_subagent",
                    "arguments": json.dumps({"task": "Read README.md and report the source note."}),
                },
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "managed-chat", []
        if self.parent_calls == 3:
            self.child_project_write = self.child_snapshot != [self.canonical_snapshot()]
            assert not self.child_project_write, "child changed project bytes before parent resumed"
            assert not (self.workspace / "managed-chat-note.txt").exists()
            call = {
                "id": "managed-chat-write",
                "type": "function",
                "function": {
                    "name": "fs_write_file",
                    "arguments": json.dumps({"path": "managed-chat-note.txt", "content": "private until publish"}),
                },
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "managed-chat", []
        assert self.parent_calls == 4
        assert self.observed == [self.canonical_snapshot()], "canonical files changed while the chat stage was live"
        assert not (self.workspace / "managed-chat-note.txt").exists()
        return ResponseInfo("done", 1, 1, "stop"), logical_call_id or "managed-chat", []


@pytest.mark.parametrize("refuse_publication", [False, True])
def test_workflow_root_publishes_candidate_through_real_local_authority(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    refuse_publication: bool,
) -> None:
    """S3P3 C1: parsed workflow repairs a plan and uses the actual local publisher."""
    from fa.inner_loop.session_db import SessionDatabase
    from fa.providers import ProviderChain, SecretStore

    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path / "fa-state"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))

    canonical_relative = "worklogs/planning-topology-and-executable-contracts-loop/increments/s3p3-cli-fixture.md"
    plan_path = site.source / canonical_relative
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    source_bytes = b"## SLICE 1: bad heading\n"
    candidate_bytes = (
        b"Plan-ID: PLAN-cli-fixture\n\n## SLICE1: CLI routing fixture\nCONTRACTS:\n"
        b"  CT9001 [CONSTRAINT]: candidate revision remains valid.\n"
        b"TESTS: tests/test_fixture_contract.py\n"
    )
    plan_path.write_bytes(source_bytes)
    candidate_snapshot = snapshot_from_bytes("draft.md", candidate_bytes)
    assert workflow_controller._validate_plan_admission(candidate_snapshot).outcome == "PASS"
    initial_snapshot = read_plan_snapshot(site.source, Path(canonical_relative))
    assert workflow_controller._validate_plan_admission(initial_snapshot).outcome == "DIAGNOSTICS"

    def canonical_snapshot() -> dict[str, bytes]:
        excluded = {".git", ".fa", ".venv", ".env"}
        return {
            path.relative_to(site.source).as_posix(): path.read_bytes()
            for path in sorted(site.source.rglob("*"))
            if path.is_file()
            and not path.is_symlink()
            and not excluded.intersection(path.relative_to(site.source).parts)
        }

    canonical_before = canonical_snapshot()
    index_path = site.source / ".git" / "index"
    index_before = index_path.read_bytes()

    models = tmp_path / "models.yaml"
    models.write_text(
        """planner:
  name: test-model
  family: openai
  chain:
    - provider: openrouter
      model: test/model
      base_url: https://example.invalid/v1
      api_key_env: K
coder:
  name: test-model
  family: openai
  chain:
    - provider: openrouter
      model: test/model
      base_url: https://example.invalid/v1
      api_key_env: K
eval:
  name: test-model
  family: openai
  chain:
    - provider: openrouter
      model: test/model
      base_url: https://example.invalid/v1
      api_key_env: K
""",
        encoding="utf-8",
    )
    service_path, service_config = _configs(tmp_path, _document(site))
    monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", service_config)

    session_id = "s3p3-session"
    run_id = "s3p3-refusal" if refuse_publication else "s3p3-success"
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    session_db_path = session_dir / "session.db"
    session_db = SessionDatabase(session_db_path, session_id=session_id)
    session = SessionContext(session_id, site.source, session_db_path, session_dir / "manifest.json")
    run_log_dir = tmp_path / "workflow-run-logs" / run_id
    run_log_dir.mkdir(parents=True)
    run = RunContext(run_id, session_id, site.source, session_db_path, run_log_dir)
    monkeypatch.setattr(
        cli,
        "_resolve_workflow_lifecycle",
        lambda _args, resolved_run_id: (resolved_run_id, session, run, session_db),
    )

    class _WorkflowWorkspace:
        @staticmethod
        def resolve_workflow_workspace(**_kwargs: Any) -> Path:
            return site.source

    monkeypatch.setattr(cli, "_session_manager_for_args", lambda _args: _WorkflowWorkspace())
    managed_instances: list[ManagedExecution] = []
    original_managed_for_run = managed_execution_for_run

    def capture_managed(*args: Any, **kwargs: Any) -> ManagedExecution | None:
        managed = original_managed_for_run(*args, **kwargs)
        if managed is not None:
            managed_instances.append(managed)
        return managed

    monkeypatch.setattr(cli, "managed_execution_for_run", capture_managed)
    provider_calls: list[str] = []
    candidate_writes: list[str] = []

    def provider_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[Any, str, list[Any]]:
        provider_calls.append(str(logical_call_id or "s3p3"))
        write_spec = next(
            (
                tool
                for tool in request.tools
                if isinstance(tool.get("function"), dict) and tool["function"].get("name") == "fs_write_file"
            ),
            None,
        )
        properties = (
            write_spec.get("function", {}).get("parameters", {}).get("properties", {}) if write_spec is not None else {}
        )
        target_values = properties.get("path", {}).get("enum") if isinstance(properties, dict) else None
        tool_messages = [message for message in request.messages if message.get("role") == "tool"]
        if isinstance(target_values, list) and len(target_values) == 1:
            target = target_values[0]
            if tool_messages:
                response = ResponseInfo("candidate repaired", 1, 1, "stop")
                return response, logical_call_id or "s3p3", []
            candidate_writes.append(target)
            call = {
                "id": "s3p3-candidate-write",
                "type": "function",
                "function": {
                    "name": "fs_write_file",
                    "arguments": json.dumps({"path": target, "content": candidate_bytes.decode("utf-8")}),
                },
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "s3p3", []
        system = request.messages[0].get("content", "") if request.messages else ""
        final_text = (
            "## Verification Summary\n\n### Step results\n- S1: PASS — candidate committed.\n\n"
            "### Verdict\nPASS\n\n### Route decision\ncomplete\n"
            if "First-Agent evaluator" in str(system)
            else "stage complete"
        )
        return ResponseInfo(final_text, 1, 1, "stop"), logical_call_id or "s3p3", []

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    args = cli.build_parser().parse_args(
        [
            "workflow",
            "planner,coder",
            "repair and publish the admitted candidate",
            "--workspace",
            str(site.source),
            "--session-id",
            session_id,
            "--run-id",
            run_id,
            "--config",
            str(models),
            "--max-turns",
            "5",
            "--plan",
            canonical_relative,
        ]
    )
    publish_attempts: list[str] = []
    publish_replies: list[dict[str, Any]] = []
    with SupervisorService(read_config_file(service_path)) as service:
        actual_publish = service.authority.publish_candidate_plan

        def record_publish(*args: Any, **kwargs: Any) -> dict[str, Any]:
            publish_attempts.append(str(kwargs["operation_id"]))
            if refuse_publication:
                raise SupervisorError("INPUT_POLICY")
            reply = actual_publish(*args, **kwargs)
            publish_replies.append(reply)
            return reply

        # S3P3 EDGE oracle: WHICH view carried the candidate write. Without this,
        # a run that wrote the seed to the host `.fa` copy and published it passes
        # every other assertion here, because the bytes and the reply look the same.
        candidate_write_views: list[str] = []

        original_write = service._write_file

        def record_write(peer: Any, request: dict[str, Any], deadline: float) -> Any:
            # The dispatcher looks the handler up by NAME on each call, so the
            # replacement must be the bound attribute it resolves.
            view = request.get("view_ref") or {}
            candidate_write_views.append(str(view.get("purpose")))
            return original_write(peer, request, deadline)

        monkeypatch.setattr(service, "_write_file", record_write)
        monkeypatch.setattr(service.authority, "publish_candidate_plan", record_publish)
        with _serving_supervisor(service):
            exit_code = cli._cmd_workflow(args, secrets=SecretStore({"K": "sk-test-s3p3"}))
            assert len(managed_instances) == 1
            again = managed_execution_for_run(run, config_path=service_config)
            assert again is not None
            assert again.binding.workspace_id == managed_instances[0].binding.workspace_id
            assert again.close() is True
        workspace_id = managed_instances[0].binding.workspace_id
        assert site.metadata({"workspace_id": workspace_id})["status"] == "AVAILABLE"

    assert exit_code == (2 if refuse_publication else 0)
    assert provider_calls and candidate_writes and len(candidate_writes) == 1
    # Both writes travelled through the CANDIDATE view and neither through a project
    # view onto the host seed. Two is the expected count and it is a property of the
    # publication saga, not an accident: the planner stages bytes into the buffer,
    # and `publish_plan` re-stages the validated snapshot into a FRESH candidate view
    # before its PUBLISH CAS. Same purpose, two views -- which is precisely why the
    # oracle records the purpose and not "one write happened".
    assert candidate_write_views == ["CANDIDATE", "CANDIDATE"], candidate_write_views
    assert len(publish_attempts) == 1  # determinate refusal is not replayed
    assert len(publish_replies) == int(not refuse_publication)
    assert index_path.read_bytes() == index_before
    expected_tree = canonical_before.copy()
    if refuse_publication:
        assert canonical_snapshot() == canonical_before
        assert plan_path.read_bytes() == source_bytes
    else:
        expected_tree[canonical_relative] = candidate_bytes
        assert canonical_snapshot() == expected_tree
        assert plan_path.read_bytes() == candidate_bytes
        reply = publish_replies[0]
        assert reply["plan_ref"].sha256 == candidate_snapshot.ref.sha256
        assert reply["plan_ref"].workspace_relative_path == canonical_relative
        assert reply["revision_id"] != managed_instances[0].grant.revision_id


def _constrain_managed_inventory_candidates(monkeypatch: pytest.MonkeyPatch, candidate_limit: int) -> None:
    from fa.memory import managed_discovery

    if type(candidate_limit) is not int or candidate_limit < 1:
        raise ValueError("inventory_candidate_limit must be a positive integer")
    original_inventory = managed_discovery.inventory_managed_files

    def constrained_inventory(root: Path, *, deadline: float, **kwargs: Any) -> Any:
        kwargs["limits"] = managed_discovery.ManagedDiscoveryLimits(candidates=candidate_limit)
        return original_inventory(root, deadline=deadline, **kwargs)

    monkeypatch.setattr(managed_discovery, "inventory_managed_files", constrained_inventory)


def _run_managed_discovery_c1(
    site: Site,
    tmp_path: Path,
    local_cell_peer: Endpoint,
    monkeypatch: pytest.MonkeyPatch,
    *,
    calls: tuple[tuple[str, dict[str, Any]], ...],
    expected_tool_result: str | None = None,
    inventory_candidate_limit: int | None = None,
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    """R20 C1 oracle: fa run reaches the typed cell helper without host fallback."""
    import subprocess
    from types import SimpleNamespace

    import fa.execution.cell_worker as cell_worker
    from fa.execution import project_tools
    from fa.execution.client import ManagedProjectToolExecutor
    from fa.inner_loop.session_db import SessionDatabase
    from fa.providers import ProviderChain, SecretStore

    if inventory_candidate_limit is not None:
        _constrain_managed_inventory_candidates(monkeypatch, inventory_candidate_limit)
    from fa.session.manager import RunContext, SessionContext

    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setattr(cli, "_build_pty_pool", lambda **_kwargs: object())

    models = tmp_path / "models.yaml"
    models.write_text(
        """coder:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
""",
        encoding="utf-8",
    )

    git_invocations: list[list[str]] = []
    helper_tool_names: list[str] = []
    helper_calls_lock = threading.Lock()
    active_executor_calls = 0
    max_active_executor_calls = 0
    executor_calls_lock = threading.Lock()

    def record_host_git(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        git_invocations.append(list(argv))
        return subprocess.CompletedProcess(list(argv), 0, stdout="", stderr="")

    monkeypatch.setattr("fa.memory._safe_walk.subprocess.run", record_host_git)

    class _ProjectToolProcess:
        def __init__(self, args: list[str]) -> None:
            self.args = args

    def start_project_tool(args: list[str], **kwargs: Any) -> _ProjectToolProcess:
        assert len(args) == 5
        assert args[1:4] == ["-I", "-m", "fa.execution.project_tools"]
        assert kwargs == {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": str((tmp_path / "local-cell-workspace").resolve()),
            "env": {
                "HOME": "/scratch/home",
                "PATH": "/usr/bin:/bin",
                "PYTHONNOUSERSITE": "1",
                "TMPDIR": "/scratch/tmp",
            },
            "close_fds": True,
            "shell": False,
            "start_new_session": True,
        }
        return _ProjectToolProcess(args)

    def run_shipped_project_helper(
        process: _ProjectToolProcess,
        *,
        timeout_ms: int,
    ) -> tuple[bytes, bytes, int, bool, bool]:
        assert timeout_ms > 0
        parsed = project_tools._parse(process.args[-1])
        assert parsed is not None
        with helper_calls_lock:
            helper_tool_names.append(parsed[0])
        view_sources = sorted((site.state / "workspaces" / workspace_id / "views").glob("*/source"))
        assert len(view_sources) == 1
        scratch = tmp_path / "project-tool-scratch"
        scratch.mkdir(exist_ok=True)
        result = project_tools._dispatch(parsed[0], parsed[1], root=view_sources[0], scratch=scratch)
        return (project_tools._envelope(result) + "\n").encode("utf-8"), b"", 0, False, False

    monkeypatch.setattr(
        cell_worker,
        "subprocess",
        SimpleNamespace(Popen=start_project_tool, DEVNULL=subprocess.DEVNULL, PIPE=subprocess.PIPE),
    )
    monkeypatch.setattr(cell_worker, "_capture_project_tool", run_shipped_project_helper)
    original_execute = ManagedProjectToolExecutor.execute

    def track_executor_entry(
        executor: ManagedProjectToolExecutor,
        tool: str,
        params: dict[str, Any],
        *,
        timeout: int = 25,
    ) -> str:
        nonlocal active_executor_calls, max_active_executor_calls
        with executor_calls_lock:
            active_executor_calls += 1
            max_active_executor_calls = max(max_active_executor_calls, active_executor_calls)
        try:
            # Measure overlap before ManagedProjectToolExecutor's own lock; otherwise
            # its transport lock would conceal a broken loop scheduler edge.
            time.sleep(0.05)
            return original_execute(executor, tool, params, timeout=timeout)
        finally:
            with executor_calls_lock:
                active_executor_calls -= 1

    monkeypatch.setattr(ManagedProjectToolExecutor, "execute", track_executor_entry)

    provider_calls = 0
    tool_result_messages: list[str] = []

    def provider_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        nonlocal provider_calls
        provider_calls += 1
        names = {
            str(tool.get("function", {}).get("name", ""))
            for tool in request.tools
            if isinstance(tool.get("function"), dict)
        }
        if provider_calls == 1:
            tool_calls = []
            for index, (name, params) in enumerate(calls):
                assert name in names
                tool_calls.append(
                    {
                        "id": f"r20-managed-{name}-{index}",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(params)},
                    }
                )
            return ResponseInfo("", 1, 1, "tool_calls", tuple(tool_calls)), logical_call_id or "r20", []
        tool_result_messages.extend(
            str(message.get("content", "")) for message in request.messages if message.get("role") == "tool"
        )
        return ResponseInfo("done", 1, 1, "stop"), logical_call_id or "r20", []

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    from fa.inner_loop.state import SessionState

    state_instances: list[SessionState] = []

    def capture_state(*args: Any, **kwargs: Any) -> SessionState:
        state = SessionState(*args, **kwargs)
        state_instances.append(state)
        return state

    monkeypatch.setattr(cli, "SessionState", capture_state)
    index_path = site.source / ".git" / "index"
    index_before = index_path.read_bytes()
    canonical_before = {
        "dirty.txt": (site.source / "dirty.txt").read_bytes(),
        "untracked.txt": (site.source / "untracked.txt").read_bytes(),
    }
    fts_path = site.source / ".fa" / "fts.db"
    assert not fts_path.exists()
    document = _document(site)
    _configure_local_cell_backend(
        local_cell_peer,
        tmp_path,
        document,
        interactive_worker=True,
        project_tool_calls=len(calls),
    )
    service_path, config_path = _configs(tmp_path, document)
    session_db_path = tmp_path / "session.db"
    run_log_dir = tmp_path / "session-log" / "run-1"
    session_db = SessionDatabase(session_db_path, session_id="session-1")
    session_context = SessionContext("session-1", site.source, session_db_path, tmp_path / "manifest.json")
    run_context = RunContext("run-1", "session-1", site.source, session_db_path, run_log_dir)

    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        with _serving_supervisor(service):
            managed = managed_execution_for_run(run_context, config_path=config_path)
            assert managed is not None and managed.binding.workspace_id == workspace_id
            operations: list[Operation] = []
            exec_bindings: list[tuple[str, str, str, str]] = []
            original_request = managed.client.request

            def record_request(operation: Operation, **kwargs: Any) -> Any:
                operations.append(operation)
                if operation is Operation.EXEC:
                    view = kwargs["view"]
                    grant = kwargs["grant"]
                    payload = kwargs["payload"]
                    exec_bindings.append(
                        (
                            view.view_id,
                            grant.view_ref.view_id,
                            payload["profile_id"],
                            kwargs["request_id"],
                        )
                    )
                return original_request(operation, **kwargs)

            monkeypatch.setattr(managed.client, "request", record_request)
            args = cli.build_parser().parse_args(
                [
                    "run",
                    "--role",
                    "coder",
                    "--config",
                    str(models),
                    "--workspace",
                    str(site.source),
                    "--run-id",
                    "run-1",
                    "--max-turns",
                    "3",
                    "search the admitted workspace",
                ]
            )
            args._managed_execution = managed
            args._session_context = session_context
            args._run_context = run_context
            args._session_db = session_db
            try:
                assert cli._cmd_run(args, secrets=SecretStore({"K": "sk-test-live"})) == 0
            finally:
                assert managed.close()

    assert provider_calls == 2
    assert len(tool_result_messages) == len(calls)
    if expected_tool_result is None:
        assert all("ERROR[" not in message for message in tool_result_messages)
    else:
        assert tool_result_messages == [expected_tool_result] * len(calls)
    assert sorted(helper_tool_names) == sorted(name for name, _ in calls)
    assert max_active_executor_calls == 1
    assert git_invocations == []
    assert operations.count(Operation.EXEC) == len(calls), operations
    assert len(exec_bindings) == len(calls)
    view_ids = tuple(binding[0] for binding in exec_bindings)
    assert len(set(view_ids)) == 1
    assert all(view_id == grant_view_id for view_id, grant_view_id, _, _ in exec_bindings)
    assert len({profile_id for _, _, profile_id, _ in exec_bindings}) == 1
    assert len({request_id for _, _, _, request_id in exec_bindings}) == len(calls)
    creates = [
        item for item in local_cell_peer.seen if item["method"] == "POST" and "/containers/create?" in item["path"]
    ]
    starts = [item for item in local_cell_peer.seen if item["method"] == "POST" and item["path"].endswith("/start")]
    kills = [item for item in local_cell_peer.seen if item["method"] == "POST" and "/kill?" in item["path"]]
    assert len(creates) == 1 and len(starts) == 1 and len(kills) == 1
    assert creates[0]["body"]["Labels"]["fa.execution.operation_id"] == "op-" + exec_bindings[0][3]
    assert all(
        CELL_CID in item["path"]
        for item in local_cell_peer.seen
        if "/containers/" in item["path"] and "/containers/create?" not in item["path"]
    )
    assert not any(operation in {Operation.READ_FILE, Operation.WRITE_FILE} for operation in operations), operations
    assert index_path.read_bytes() == index_before
    assert {name: (site.source / name).read_bytes() for name in canonical_before} == canonical_before
    assert not fts_path.exists()
    assert len(state_instances) == 1
    if expected_tool_result is None:
        assert state_instances[0].last_search_paths
        assert all(
            not path.startswith("/") and ".." not in path.split("/") for path in state_instances[0].last_search_paths
        )
    else:
        assert not state_instances[0].last_search_paths
    assert not local_cell_peer.replies, "the interactive EXEC and settlement HTTP sequence must be exhausted"
    return max_active_executor_calls, tuple(helper_tool_names), view_ids


def test_managed_fs_search_uses_typed_exec_without_host_git_or_workspace_io(
    site: Site,
    tmp_path: Path,
    local_cell_peer: Endpoint,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R20 C1 success path through the managed role registry and typed helper."""
    max_active, helpers, view_ids = _run_managed_discovery_c1(
        site,
        tmp_path,
        local_cell_peer,
        monkeypatch,
        calls=(("fs_search", {"output_mode": "files"}),),
    )
    assert max_active == 1 and helpers == ("fs_search",) and len(view_ids) == 1


@pytest.mark.parametrize(
    ("tool", "params", "expected_tool_result"),
    [
        (
            "fs_search",
            {"output_mode": "files"},
            "ERROR[search_failed]: managed search refused (candidate_budget)",
        ),
        (
            "fs_reach",
            {"symbol": "Site", "direction": "down"},
            "ERROR[reach_failed]: managed reach refused (candidate_budget)",
        ),
    ],
)
def test_managed_discovery_budget_refusal_reaches_typed_exec_without_host_fallback(
    site: Site,
    tmp_path: Path,
    local_cell_peer: Endpoint,
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
    params: dict[str, Any],
    expected_tool_result: str,
) -> None:
    """Production C1 proves bounded producer and helper edge before index allocation."""
    (site.source / "budget-first.py").write_text("value = 1\n", encoding="utf-8")
    (site.source / "budget-second.py").write_text("value = 2\n", encoding="utf-8")
    max_active, helpers, view_ids = _run_managed_discovery_c1(
        site,
        tmp_path,
        local_cell_peer,
        monkeypatch,
        calls=((tool, params),),
        expected_tool_result=expected_tool_result,
        inventory_candidate_limit=1,
    )
    assert max_active == 1 and helpers == (tool,) and len(view_ids) == 1


def test_managed_discovery_calls_serialize_per_view(
    site: Site,
    tmp_path: Path,
    local_cell_peer: Endpoint,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production C1: same-view search/reach entries do not overlap before EXEC's own lock."""
    max_active, helpers, view_ids = _run_managed_discovery_c1(
        site,
        tmp_path,
        local_cell_peer,
        monkeypatch,
        calls=(
            ("fs_search", {"output_mode": "files"}),
            ("fs_reach", {"symbol": "Site"}),
        ),
    )
    assert max_active == 1
    assert sorted(helpers) == ["fs_reach", "fs_search"]
    assert len(view_ids) == 2 and len(set(view_ids)) == 1


@contextmanager
def _serving_supervisor(service: SupervisorService) -> Iterator[None]:
    stop = threading.Event()
    runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
    runner.start()
    try:
        yield
    finally:
        stop.set()
        runner.join(timeout=5)
        assert not runner.is_alive()


def test_managed_coder_run_never_offers_pair_tools_or_calls_host_git(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R17 production-caller oracle: the managed coder cannot reach pair-tool host Git."""
    from fa.inner_loop.session_db import SessionDatabase
    from fa.inner_loop.tools import pair_tools
    from fa.providers import ProviderChain, SecretStore
    from fa.session.manager import RunContext, SessionContext

    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setattr(cli, "_build_pty_pool", lambda **_kwargs: object())

    models = tmp_path / "models.yaml"
    models.write_text(
        """coder:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
""",
        encoding="utf-8",
    )

    git_calls: list[tuple[list[str], Path]] = []
    original_run_git = pair_tools._run_git

    def record_pair_git(args: list[str], cwd: Path, timeout: int = 10) -> Any:
        git_calls.append((list(args), cwd))
        return original_run_git(args, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(pair_tools, "_run_git", record_pair_git)
    provider_tool_sets: list[set[str]] = []
    pair_names = {"fs_checkpoint", "fs_undo", "fs_diff"}
    pair_probe_sent = False

    def provider_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        nonlocal pair_probe_sent
        names = {
            str(tool.get("function", {}).get("name", ""))
            for tool in request.tools
            if isinstance(tool.get("function"), dict)
        }
        provider_tool_sets.append(names)
        # If a regression offers any host-Git tool, exercise that real
        # registered handler rather than treating schema presence as proof.
        requested = next((name for name in ("fs_checkpoint", "fs_undo", "fs_diff") if name in names), None)
        if requested is not None and not pair_probe_sent:
            pair_probe_sent = True
            arguments = {"message": "R17 host-Git reachability probe"} if requested == "fs_checkpoint" else {}
            call = {
                "id": "r17-pair-tool-probe",
                "type": "function",
                "function": {"name": requested, "arguments": json.dumps(arguments)},
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "r17", []
        return ResponseInfo("done", 1, 1, "stop"), logical_call_id or "r17", []

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    index_path = site.source / ".git" / "index"
    index_before = index_path.read_bytes()
    service_path, config_path = _configs(tmp_path, _document(site))
    session_db_path = tmp_path / "session.db"
    run_log_dir = tmp_path / "session-log" / "run-1"
    session_db = SessionDatabase(session_db_path, session_id="session-1")
    session_context = SessionContext("session-1", site.source, session_db_path, tmp_path / "manifest.json")
    run_context = RunContext("run-1", "session-1", site.source, session_db_path, run_log_dir)

    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        with _serving_supervisor(service):
            managed = managed_execution_for_run(run_context, config_path=config_path)
            assert managed is not None and managed.binding.workspace_id == workspace_id
            args = cli.build_parser().parse_args(
                [
                    "run",
                    "--role",
                    "coder",
                    "--config",
                    str(models),
                    "--workspace",
                    str(site.source),
                    "--run-id",
                    "run-1",
                    "--max-turns",
                    "3",
                    "inspect the workspace",
                ]
            )
            args._managed_execution = managed
            args._session_context = session_context
            args._run_context = run_context
            args._session_db = session_db
            try:
                assert cli._cmd_run(args, secrets=SecretStore({"K": "sk-test-live"})) == 0
            finally:
                assert managed.close()

    assert provider_tool_sets
    assert git_calls == []
    assert all(pair_names.isdisjoint(names) for names in provider_tool_sets)
    assert len(provider_tool_sets) == 1
    assert index_path.read_bytes() == index_before


def test_managed_coder_write_uses_revision_metadata_without_host_git(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R18/R22 C1 oracle: managed write stamps and optional pr_prepare avoid host Git."""
    import subprocess

    from fa.feature_flags import FeatureFlags, FeatureFlagsLoadResult
    from fa.inner_loop.session_db import SessionDatabase
    from fa.inner_loop.tools import mutation_guard
    from fa.providers import ProviderChain, SecretStore
    from fa.session.manager import RunContext, SessionContext

    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setattr(cli, "_build_pty_pool", lambda **_kwargs: object())
    monkeypatch.setattr(
        "fa.feature_flags.load_feature_flags_from_path",
        lambda: FeatureFlagsLoadResult(FeatureFlags(blackboard_enabled=True)),
    )

    llms_content = "# R18 managed workspace map\n"
    knowledge = site.source / "knowledge"
    knowledge.mkdir()
    (knowledge / "llms.txt").write_text(llms_content, encoding="utf-8")
    models = tmp_path / "models.yaml"
    models.write_text(
        """coder:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
""",
        encoding="utf-8",
    )

    base_commit_calls: list[Path] = []
    original_base_commit = mutation_guard._base_commit

    def record_base_commit(root: Path) -> str:
        base_commit_calls.append(root)
        return original_base_commit(root)

    monkeypatch.setattr(mutation_guard, "_base_commit", record_base_commit)
    host_git_calls: list[list[str]] = []
    original_subprocess_run = subprocess.run

    def forbid_host_git(command: Any, *args: Any, **kwargs: Any) -> Any:
        argv = [str(part) for part in command] if isinstance(command, (list, tuple)) else [str(command)]
        if argv and Path(argv[0]).name.casefold() == "git":
            host_git_calls.append(argv)
            raise AssertionError(f"managed pr_prepare reached host Git: {argv!r}")
        return original_subprocess_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", forbid_host_git)
    provider_calls = 0
    canonical_visible_during_run: list[bool] = []
    write_sent = False

    def provider_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        nonlocal provider_calls, write_sent
        provider_calls += 1
        names = {
            str(tool.get("function", {}).get("name", ""))
            for tool in request.tools
            if isinstance(tool.get("function"), dict)
        }
        if provider_calls == 1:
            assert "pr_prepare" in names
            call = {
                "id": "r18-pr-prepare",
                "type": "function",
                "function": {
                    "name": "pr_prepare",
                    "arguments": json.dumps({"intent": "CHORE", "invariant": "n/a"}),
                },
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "r18", []
        if not write_sent:
            assert provider_calls == 2 and "fs_write_file" in names
            write_sent = True
            call = {
                "id": "r18-managed-write",
                "type": "function",
                "function": {
                    "name": "fs_write_file",
                    "arguments": json.dumps({"path": "src/r18.py", "content": "VALUE = 18\n"}),
                },
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "r18", []
        canonical_visible_during_run.append((site.source / "src" / "r18.py").exists())
        return ResponseInfo("done", 1, 1, "stop"), logical_call_id or "r18", []

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    index_path = site.source / ".git" / "index"
    index_before = index_path.read_bytes()
    service_path, config_path = _configs(tmp_path, _document(site))
    session_db_path = tmp_path / "session.db"
    run_log_dir = tmp_path / "session-log" / "run-1"
    session_db = SessionDatabase(session_db_path, session_id="session-1")
    session_context = SessionContext("session-1", site.source, session_db_path, tmp_path / "manifest.json")
    run_context = RunContext("run-1", "session-1", site.source, session_db_path, run_log_dir)

    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        with _serving_supervisor(service):
            managed = managed_execution_for_run(run_context, config_path=config_path)
            assert managed is not None and managed.binding.workspace_id == workspace_id
            operations: list[Operation] = []
            original_request = managed.client.request

            def record_request(operation: Operation, **kwargs: Any) -> Any:
                operations.append(operation)
                return original_request(operation, **kwargs)

            monkeypatch.setattr(managed.client, "request", record_request)
            args = cli.build_parser().parse_args(
                [
                    "run",
                    "--role",
                    "coder",
                    "--config",
                    str(models),
                    "--workspace",
                    str(site.source),
                    "--run-id",
                    "run-1",
                    "--max-turns",
                    "3",
                    "write the R18 probe",
                ]
            )
            args._managed_execution = managed
            args._session_context = session_context
            args._run_context = run_context
            args._session_db = session_db
            run_exit_code: int | None = None
            release_confirmed = False
            try:
                run_exit_code = cli._cmd_run(args, secrets=SecretStore({"K": "sk-test-live"}))
            finally:
                release_confirmed = managed.close()

    assert provider_calls == 3 and write_sent
    assert base_commit_calls == []
    assert host_git_calls == []
    assert run_exit_code == 0
    assert release_confirmed
    draft_path = run_log_dir / "pr_draft.md"
    assert draft_path.is_file()
    assert draft_path.is_relative_to(run_log_dir) and not draft_path.is_relative_to(site.source)
    assert draft_path.read_text(encoding="utf-8").startswith("INTENT: CHORE\nINVARIANT: n/a\n")
    assert canonical_visible_during_run == [False]
    assert operations.count(Operation.WRITE_FILE) == 1
    assert index_path.read_bytes() == index_before
    assert (site.source / "src" / "r18.py").read_text(encoding="utf-8") == "VALUE = 18\n"
    rows = session_db.query_blackboard_rows(entry_type="file_version")
    assert len(rows) == 1
    assert rows[0]["write_set"] == ["src/r18.py"]
    versions = rows[0]["version_dependencies"]
    assert versions["base_revision"].startswith("rev-")
    assert versions["llms.txt"] == hashlib.sha256(llms_content.encode("utf-8")).hexdigest()[:12]
    assert "base_commit" not in versions


def test_managed_fs_search_refuses_before_host_git_or_workspace_io(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R20 C1 oracle: managed search refusal does not reach host Git or the workspace."""
    import subprocess

    from fa.inner_loop.session_db import SessionDatabase
    from fa.providers import ProviderChain, SecretStore
    from fa.session.manager import RunContext, SessionContext

    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setattr(cli, "_build_pty_pool", lambda **_kwargs: object())

    models = tmp_path / "models.yaml"
    models.write_text(
        """coder:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
""",
        encoding="utf-8",
    )

    git_invocations: list[list[str]] = []

    def record_host_git(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        git_invocations.append(list(argv))
        return subprocess.CompletedProcess(list(argv), 0, stdout="", stderr="")

    monkeypatch.setattr("fa.memory._safe_walk.subprocess.run", record_host_git)
    provider_calls = 0
    tool_result_messages: list[str] = []

    def provider_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        nonlocal provider_calls
        provider_calls += 1
        names = {
            str(tool.get("function", {}).get("name", ""))
            for tool in request.tools
            if isinstance(tool.get("function"), dict)
        }
        if provider_calls == 1:
            assert "fs_search" in names
            call = {
                "id": "r20-managed-search",
                "type": "function",
                "function": {
                    "name": "fs_search",
                    "arguments": json.dumps({"query": "alpha", "output_mode": "files"}),
                },
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "r20", []
        tool_result_messages.extend(
            str(message.get("content", "")) for message in request.messages if message.get("role") == "tool"
        )
        return ResponseInfo("done", 1, 1, "stop"), logical_call_id or "r20", []

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    index_path = site.source / ".git" / "index"
    index_before = index_path.read_bytes()
    fts_path = site.source / ".fa" / "fts.db"
    assert not fts_path.exists()
    service_path, config_path = _configs(tmp_path, _document(site))
    session_db_path = tmp_path / "session.db"
    run_log_dir = tmp_path / "session-log" / "run-1"
    session_db = SessionDatabase(session_db_path, session_id="session-1")
    session_context = SessionContext("session-1", site.source, session_db_path, tmp_path / "manifest.json")
    run_context = RunContext("run-1", "session-1", site.source, session_db_path, run_log_dir)

    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        with _serving_supervisor(service):
            managed = managed_execution_for_run(run_context, config_path=config_path)
            assert managed is not None and managed.binding.workspace_id == workspace_id
            operations: list[Operation] = []
            original_request = managed.client.request

            def record_request(operation: Operation, **kwargs: Any) -> Any:
                operations.append(operation)
                return original_request(operation, **kwargs)

            monkeypatch.setattr(managed.client, "request", record_request)
            args = cli.build_parser().parse_args(
                [
                    "run",
                    "--role",
                    "coder",
                    "--config",
                    str(models),
                    "--workspace",
                    str(site.source),
                    "--run-id",
                    "run-1",
                    "--max-turns",
                    "3",
                    "search the admitted workspace",
                ]
            )
            args._managed_execution = managed
            args._session_context = session_context
            args._run_context = run_context
            args._session_db = session_db
            try:
                assert cli._cmd_run(args, secrets=SecretStore({"K": "sk-test-live"})) == 0
            finally:
                assert managed.close()

    assert provider_calls == 2
    assert tool_result_messages == ["ERROR[execution_unavailable]: managed project tool backend unavailable"]
    assert operations.count(Operation.EXEC) == 1
    assert git_invocations == []
    assert not any(operation in {Operation.READ_FILE, Operation.WRITE_FILE} for operation in operations), operations
    assert index_path.read_bytes() == index_before
    assert not fts_path.exists()


def test_managed_coder_first_write_needs_no_pr_prepare_and_never_calls_intent_guard(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R19 production oracle: optional note absent, managed write publishes, legacy guard producers stay cold."""
    from fa.feature_flags import FeatureFlags, FeatureFlagsLoadResult
    from fa.inner_loop.hooks import intent_guard
    from fa.inner_loop.session_db import SessionDatabase
    from fa.providers import ProviderChain, SecretStore
    from fa.session.manager import RunContext, SessionContext

    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setattr(cli, "_build_pty_pool", lambda **_kwargs: object())
    monkeypatch.setattr(
        "fa.feature_flags.load_feature_flags_from_path",
        lambda: FeatureFlagsLoadResult(FeatureFlags(blackboard_enabled=True)),
    )

    llms_content = "# R19 managed workspace map\n"
    knowledge = site.source / "knowledge"
    knowledge.mkdir()
    (knowledge / "llms.txt").write_text(llms_content, encoding="utf-8")
    models = tmp_path / "models.yaml"
    models.write_text(
        """coder:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
""",
        encoding="utf-8",
    )

    git_calls: list[Path] = []
    path_projection_calls: list[tuple[Any, ...]] = []

    def record_git_runner(guard: Any) -> str:
        git_calls.append(guard._repo_root)
        return ""

    def record_project_call(*args: Any, **_kwargs: Any) -> list[Any]:
        path_projection_calls.append(args)
        return []

    monkeypatch.setattr(intent_guard.IntentGuard, "_default_git_runner", record_git_runner)
    monkeypatch.setattr(intent_guard, "_project_call", record_project_call)

    provider_calls = 0
    canonical_visible_during_run: list[bool] = []

    def provider_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        nonlocal provider_calls
        provider_calls += 1
        names = {
            str(tool.get("function", {}).get("name", ""))
            for tool in request.tools
            if isinstance(tool.get("function"), dict)
        }
        if provider_calls == 1:
            assert "fs_write_file" in names and "pr_prepare" in names
            call = {
                "id": "r19-first-write",
                "type": "function",
                "function": {
                    "name": "fs_write_file",
                    "arguments": json.dumps({"path": "src/r19.py", "content": "VALUE = 19\n"}),
                },
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "r19", []
        assert provider_calls == 2
        canonical_visible_during_run.append((site.source / "src" / "r19.py").exists())
        return ResponseInfo("done", 1, 1, "stop"), logical_call_id or "r19", []

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    index_path = site.source / ".git" / "index"
    index_before = index_path.read_bytes()
    service_path, config_path = _configs(tmp_path, _document(site))
    session_db_path = tmp_path / "session.db"
    run_log_dir = tmp_path / "session-log" / "run-1"
    session_db = SessionDatabase(session_db_path, session_id="session-1")
    session_context = SessionContext("session-1", site.source, session_db_path, tmp_path / "manifest.json")
    run_context = RunContext("run-1", "session-1", site.source, session_db_path, run_log_dir)

    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        with _serving_supervisor(service):
            managed = managed_execution_for_run(run_context, config_path=config_path)
            assert managed is not None and managed.binding.workspace_id == workspace_id
            operations: list[Operation] = []
            requests: list[tuple[Operation, dict[str, Any]]] = []
            original_request = managed.client.request

            def record_request(operation: Operation, **kwargs: Any) -> Any:
                operations.append(operation)
                requests.append((operation, kwargs))
                return original_request(operation, **kwargs)

            monkeypatch.setattr(managed.client, "request", record_request)
            args = cli.build_parser().parse_args(
                [
                    "run",
                    "--role",
                    "coder",
                    "--config",
                    str(models),
                    "--workspace",
                    str(site.source),
                    "--run-id",
                    "run-1",
                    "--max-turns",
                    "3",
                    "write the R19 probe",
                ]
            )
            args._managed_execution = managed
            args._session_context = session_context
            args._run_context = run_context
            args._session_db = session_db
            run_exit_code: int | None = None
            release_confirmed = False
            try:
                run_exit_code = cli._cmd_run(args, secrets=SecretStore({"K": "sk-test-live"}))
            finally:
                release_confirmed = managed.close()

    assert provider_calls == 2
    assert run_exit_code == 0 and release_confirmed
    assert canonical_visible_during_run == [False]
    assert operations.count(Operation.WRITE_FILE) == 1
    assert operations.count(Operation.PUBLISH) == 1
    assert operations.index(Operation.WRITE_FILE) < operations.index(Operation.PUBLISH)
    create_view_payload = next(
        kwargs["payload"] for operation, kwargs in requests if operation is Operation.CREATE_VIEW
    )
    assert create_view_payload["purpose"] == "PROJECT"
    assert create_view_payload["access"] == "WRITE"
    assert git_calls == []
    assert path_projection_calls == []
    assert index_path.read_bytes() == index_before
    assert not (run_log_dir / "pr_draft.md").exists(), "the provider must not need or call pr_prepare"
    assert (site.source / "src" / "r19.py").read_text(encoding="utf-8") == "VALUE = 19\n"


@pytest.fixture
def local_cell_peer(tmp_path: Path) -> Iterator[Endpoint]:
    private = tmp_path / "local-docker-peer"
    private.mkdir(mode=0o700)
    peer = Endpoint(private / "engine.sock")
    try:
        yield peer
    finally:
        peer.close()


def _local_cell_observation(peer: Endpoint, profile: Any, status: str, *, exit_code: int = 0) -> dict[str, Any]:
    creates = [item for item in peer.seen if item["method"] == "POST" and "/containers/create?" in item["path"]]
    if not creates:
        return {}
    body = creates[0]["body"]
    labels = body.get("Labels", {})
    operation_id = labels.get("fa.execution.operation_id", "op-" + "0" * 32)
    running = status == "running"
    return {
        "Id": CELL_CID,
        "Name": "/fa-job-" + operation_id.removeprefix("op-"),
        "Image": profile.image_digest,
        "Config": {"Image": profile.image, "Labels": labels},
        "State": {
            "Status": status,
            "Running": running,
            "Paused": False,
            "Restarting": False,
            "Dead": False,
            "OOMKilled": False,
            "Pid": 123 if running else 0,
            "ExitCode": exit_code,
        },
    }


def _configure_local_cell_backend(
    peer: Endpoint,
    tmp_path: Path,
    document: dict[str, Any],
    *,
    interactive_worker: bool = False,
    project_tool_calls: int = 1,
) -> tuple[Any, Any, CountingWorker]:
    cell_profile = replace(native_profile(), uid=os.getuid(), gid=os.getgid(), max_command_ms=5000)
    reader_profile = replace(read_only_profile(), uid=os.getuid(), gid=os.getgid(), max_command_ms=5000)
    document["profiles"] = [asdict(cell_profile), asdict(reader_profile)]
    document["view_profile_id"] = cell_profile.profile_id
    document["read_only_profile_id"] = reader_profile.profile_id
    cgroup_root = tmp_path / "cgroups"
    cgroup = cgroup_root / reader_profile.cgroup_parent / CELL_CID
    cgroup.mkdir(parents=True)
    (cgroup / "cgroup.events").write_text("populated 0\nfrozen 0\n", encoding="utf-8")
    approved_cache = tmp_path / "approved-cache"
    approved_cache.mkdir(mode=0o755)
    document["approved_cache"] = str(approved_cache)
    worker_root = tmp_path / "local-cell-workspace"
    worker_root.mkdir()
    cell_worker = CountingWorker(
        PtyPool(base_cwd=worker_root),
        workspace=worker_root,
        max_command_ms=reader_profile.max_command_ms,
        one_shot=not interactive_worker,
    )
    document.update(
        {
            "docker_socket": str(peer.path),
            "docker_daemon_uid": os.getuid(),
            "docker_api_version": "1.45",
            "docker_timeout_ms": 2000,
            "cgroup_root": str(cgroup_root),
        }
    )

    worker_exit_codes: list[int] = []

    def attach_worker(connection: socket.socket) -> None:
        mux = MuxWorker(connection)
        if interactive_worker:
            try:
                serve(cell_worker, mux)
            except (OSError, ValueError):
                pass  # Service shutdown closes the persistent attach.
        else:
            worker_exit_codes.append(serve_once(cell_worker, mux))

    def inspect_reply(status: str) -> Reply:
        return Reply(
            200,
            lambda _seen: _local_cell_observation(
                peer,
                reader_profile,
                status,
                exit_code=worker_exit_codes[0] if worker_exit_codes else 0,
            ),
        )

    peer.replies.extend(
        [
            Reply(201, {"Id": CELL_CID, "Warnings": []}),
            Reply(204),
            inspect_reply("running"),
            Reply(raw=UPGRADE, upgraded=attach_worker),
        ]
    )
    if interactive_worker:
        if type(project_tool_calls) is not int or project_tool_calls < 1:
            raise ValueError("project_tool_calls must be a positive integer")
        peer.replies.extend(inspect_reply("running") for _ in range(project_tool_calls))
        peer.replies.extend([inspect_reply("running"), Reply(204), inspect_reply("exited")])
    else:
        peer.replies.extend([inspect_reply("exited"), inspect_reply("exited")])
    return cell_profile, reader_profile, cell_worker


def _watch_managed_child_host_execution(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Count only R13's forbidden Bash fallback and legacy subagent runner seams."""
    import fa.inner_loop.tools.run_bash as run_bash_module
    from fa.inner_loop.subagent_runner import SubagentRunner

    calls: list[str] = []
    original_fallback = run_bash_module._run_subprocess_fallback
    original_legacy_runner = SubagentRunner.run_stateless

    def counted_fallback(*args: Any, **kwargs: Any) -> Any:
        calls.append("run_bash._run_subprocess_fallback")
        return original_fallback(*args, **kwargs)

    def counted_legacy_runner(self: Any, *args: Any, **kwargs: Any) -> Any:
        calls.append("SubagentRunner.run_stateless")
        return original_legacy_runner(self, *args, **kwargs)

    monkeypatch.setattr(run_bash_module, "_run_subprocess_fallback", counted_fallback)
    monkeypatch.setattr(SubagentRunner, "run_stateless", counted_legacy_runner)
    return calls


@pytest.mark.parametrize("reuse_workflow_owner", [False, True])
@pytest.mark.parametrize("backend_mode", ["unavailable", "unapproved", "approved"])
def test_subagent_commands_carry_no_proxy_credential(  # noqa: C901 -- intentional production-caller mode matrix
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    local_cell_peer: Endpoint,
    reuse_workflow_owner: bool,
    backend_mode: str,
) -> None:
    """R13 named oracle: production child EXEC has exact refusal or configured-backend effects."""
    import subprocess

    from fa.feature_flags import FeatureFlags, FeatureFlagsLoadResult
    from fa.inner_loop.session_db import SessionDatabase
    from fa.providers import ProviderChain, SecretStore
    from fa.session.manager import SessionManager

    state_root = tmp_path / "fa-state"
    monkeypatch.setattr(
        "fa.feature_flags.load_feature_flags_from_path",
        lambda: FeatureFlagsLoadResult(FeatureFlags(subagent_spawning_enabled=True, subagent_chat_enabled=True)),
    )
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(site.roots))
    monkeypatch.delenv("FA_SESSION_SOURCE", raising=False)
    source = tmp_path / "source-repo"
    source.mkdir()
    (source / "README.md").write_text("source note", encoding="utf-8")
    (source / "knowledge").mkdir()
    (source / "knowledge" / "llms.txt").write_text("# Workspace map\n", encoding="utf-8")
    (source / "models.yaml").write_text(
        """chat:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "remote", "add", "origin", "https://github.com/test/repo.git"],
        check=True,
    )
    subprocess.run(["git", "-C", str(source), "add", "README.md", "knowledge/llms.txt", "models.yaml"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "seed workspace"], check=True)
    document = _document(site)
    document["approved_roots"] = {"projects": str(site.roots), "seed": str(source)}
    cell_profile = None
    reader_profile = None
    cell_worker = None
    private_scratch = tmp_path / "cell-private-scratch"
    private_scratch.mkdir()
    scratch_note = shlex.quote(str(private_scratch / "note.txt"))
    overflow_file = shlex.quote(str(private_scratch / "overflow.bin"))
    exec_command = "printf child-probe"
    if backend_mode != "unavailable":
        cell_profile, reader_profile, cell_worker = _configure_local_cell_backend(local_cell_peer, tmp_path, document)
        if backend_mode == "unapproved":
            document.pop("approved_cache")
    if backend_mode == "approved":
        file_limit_blocks = READ_SCRATCH_BYTES // 1024
        exec_command = (
            f"printf private-scratch-note > {scratch_note}; "
            f"ulimit -f {file_limit_blocks}; "
            f"/bin/dd if=/dev/zero of={overflow_file} bs=512 count={READ_SCRATCH_BYTES // 512 + 1} 2>/dev/null; "
            "overflow_status=$?; "
            f"IFS= read -r note < {scratch_note}; "
            'printf \'note=%s; overflow_exit=%s\\n\' "$note" "$overflow_status"; '
            '[ "$overflow_status" -ne 0 ]'
        )
    service_path, service_config = _configs(tmp_path, document)
    monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", service_config)
    provisioner = client_workspace_provisioner(config_path=service_config)
    assert isinstance(provisioner, ClientWorkspaceProvisioner)
    provision_requests: list[ProvisionRequest] = []

    def admitted_provision(request: ProvisionRequest) -> Any:
        provision_requests.append(request)
        return provisioner(request)

    from fa.workspace_bootstrap import ReadyState, ReadyStatus

    def prepared(workspace_path: Path, run_context: RunContext | None) -> ReadyState:
        assert isinstance(run_context, RunContext)
        assert provision_requests and provision_requests[-1].run_id == run_context.run_id
        assert provision_requests[-1].session_id == run_context.session_id
        return ReadyState(
            ReadyStatus.READY,
            None,
            "ready_managed_artifact",
            workspace_path / "managed-readiness.log",
            False,
            1,
        )

    manager = SessionManager(
        state_root=state_root,
        workspace_root=site.roots,
        source_workspace=source,
        workspace_preparer=prepared,
        workspace_provisioner=admitted_provision,
    )
    with SupervisorService(read_config_file(service_path)) as provisioning_service:
        with _serving_supervisor(provisioning_service):
            session = manager.create_or_attach_session(session_id=None, workspace_override=None)
            run = manager.begin_run(session, requested_run_id="managed-chat-run")
            session_db = SessionDatabase.open_existing(session.session_db_path, session_id=session.session_id)
            workspace = session.workspace_path
    if backend_mode == "approved":
        assert reader_profile is not None
        install_environment_artifact(Path(document["approved_cache"]), workspace, profile=reader_profile)
    assert not (workspace / "managed-chat-note.txt").exists()
    models = workspace / "models.yaml"

    provider_oracle = _ManagedChatProviderOracle(workspace, exec_command=exec_command)

    def provider_request(chain: Any, request: Any, *, logical_call_id: str | None = None) -> Any:
        return provider_oracle(chain, request, logical_call_id=logical_call_id)

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    managed = None
    exec_requests: list[dict[str, Any]] = []
    exec_denials: list[str] = []
    proxy_credential_leaks: list[str] = []
    host_subprocess_calls = _watch_managed_child_host_execution(monkeypatch)
    from fa.inner_loop.hooks import intent_guard as intent_guard_module

    intent_guard_git_calls: list[Path] = []
    intent_guard_path_calls: list[tuple[Any, ...]] = []

    def record_intent_guard_git(guard: Any) -> str:
        intent_guard_git_calls.append(guard._repo_root)
        return ""

    def record_intent_guard_path(*args: Any, **_kwargs: Any) -> list[Any]:
        intent_guard_path_calls.append(args)
        return []

    monkeypatch.setattr(intent_guard_module.IntentGuard, "_default_git_runner", record_intent_guard_git)
    monkeypatch.setattr(intent_guard_module, "_project_call", record_intent_guard_path)
    with SupervisorService(read_config_file(service_path)) as service:
        assert (service._backend is not None) is (backend_mode != "unavailable")
        original_exec = service._exec

        def counted_exec(peer: Any, request: dict[str, Any], deadline: float) -> Any:
            exec_requests.append(request)
            raw_request = json.dumps(request)
            if "X_FA_PROXY_TOKEN" in raw_request or "sk-test-live" in raw_request:
                proxy_credential_leaks.append(raw_request)
            try:
                return original_exec(peer, request, deadline)
            except SupervisorError as exc:
                exec_denials.append(exc.code)
                raise

        service._exec = counted_exec  # type: ignore[method-assign]
        with _serving_supervisor(service):
            args = cli.build_parser().parse_args(
                [
                    "run",
                    "--role",
                    "chat",
                    "--config",
                    str(models),
                    "--workspace",
                    str(workspace),
                    "--run-id",
                    "managed-chat-run",
                    "--max-turns",
                    "5",
                    "fix typo in README",
                ]
            )
            args._session_context, args._run_context, args._session_db = session, run, session_db
            if reuse_workflow_owner:
                managed = managed_execution_for_run(run)
                assert managed is not None
                args._managed_execution = managed
            assert cli._cmd_run(args, secrets=SecretStore({"K": "sk-test-live"})) == 0
            workspace_dirs = list((site.state / "workspaces").iterdir())
            assert len(workspace_dirs) == 1
            metadata = site.metadata({"workspace_id": workspace_dirs[0].name})
            assert metadata["status"] == ("OWNED" if managed is not None else "AVAILABLE")
            if managed is not None:
                assert managed.close()
                assert site.metadata({"workspace_id": workspace_dirs[0].name})["status"] == "AVAILABLE"

    assert (
        provider_oracle.provider_calls == 7 and provider_oracle.parent_calls == 4 and provider_oracle.child_calls == 3
    )
    assert len(exec_requests) == 1
    expected_denials = {
        "unavailable": ["BACKEND_UNAVAILABLE"],
        "unapproved": ["UNAPPROVED_PROFILE"],
        "approved": [],
    }
    assert exec_denials == expected_denials[backend_mode]
    exec_payload = exec_requests[0]["payload"]
    assert exec_requests[0]["op"] == "exec"
    assert exec_payload["command"] == exec_command
    assert exec_payload["session_id"] is None and exec_payload["timeout_ms"] > 0
    assert not proxy_credential_leaks and not host_subprocess_calls
    assert intent_guard_git_calls == []
    assert intent_guard_path_calls == []
    assert (service._backend is not None) is (backend_mode != "unavailable")
    assert not provider_oracle.child_project_write, "child produced a project write"
    cell_launches = sum(
        item["method"] == "POST" and "/containers/create?" in item["path"] for item in local_cell_peer.seen
    )
    project_writes = int(provider_oracle.child_project_write)
    counters = {
        "exec_requests": len(exec_requests),
        "exec_allowed": len(exec_requests) - len(exec_denials),
        "cell_launches": cell_launches,
        "host_subprocesses": len(host_subprocess_calls),
        "proxy_credentials": len(proxy_credential_leaks),
        "project_writes": project_writes,
    }
    assert counters == {
        "exec_requests": 1,
        "exec_allowed": int(backend_mode == "approved"),
        "cell_launches": int(backend_mode == "approved"),
        "host_subprocesses": 0,
        "proxy_credentials": 0,
        "project_writes": 0,
    }
    if backend_mode == "approved":
        assert cell_profile is not None and cell_worker is not None
        assert len(local_cell_peer.seen) == 6
        create = next(item for item in local_cell_peer.seen if "/containers/create?" in item["path"])
        create_body = create["body"]
        expected_tmpfs = {"/scratch": f"size={READ_SCRATCH_BYTES},mode=1777,nosuid,nodev"}
        assert create_body["HostConfig"].get("Tmpfs") == expected_tmpfs
        mounts = create_body["HostConfig"]["Mounts"]
        assert any(mount["Target"] == "/workspace" and mount["ReadOnly"] is True for mount in mounts)
        assert not any(mount["Target"] == "/scratch" for mount in mounts)
        assert "TMPDIR=/scratch/tmp" in create_body["Env"]
        assert cell_worker.runs == 1
        assert (private_scratch / "note.txt").read_text(encoding="utf-8") == "private-scratch-note"
        assert (private_scratch / "overflow.bin").stat().st_size == READ_SCRATCH_BYTES
        assert not (workspace / "note.txt").exists()
        assert not local_cell_peer.replies and not local_cell_peer.errors
    else:
        assert local_cell_peer.seen == []
        if backend_mode == "unapproved":
            assert cell_profile is not None and cell_worker is not None and cell_worker.runs == 0
            assert len(local_cell_peer.replies) == 6
        else:
            assert cell_worker is None and not local_cell_peer.replies
        assert not local_cell_peer.errors
    assert (workspace / "managed-chat-note.txt").read_text(encoding="utf-8") == "private until publish"
    assert provider_oracle.canonical_snapshot() != provider_oracle.observed[0], (
        "successful stage mutation was not published"
    )
    child_dirs = list((run.run_log_dir / "subagents").iterdir())
    assert len(child_dirs) == 1
    child_report_path = child_dirs[0] / "report.json"
    child_report_text = child_report_path.read_text(encoding="utf-8")
    assert len(child_report_text) <= 8_000
    child_report = json.loads(child_report_text)
    assert child_report["summary"] == "README contains source note."
    assert child_report["parent_run_id"] == run.run_id
    assert child_report_path.is_relative_to(run.run_log_dir)
    assert not child_report_path.is_relative_to(workspace)
    if backend_mode == "approved":
        quota_evidence = next(item for item in child_report["evidence"] if "overflow_exit=" in item)
        assert "private-scratch-note" in quota_evidence and len(quota_evidence) <= 600
        reported_overflow_status = quota_evidence.rsplit("overflow_exit=", 1)[1].split()[0]
        assert reported_overflow_status.isdecimal() and int(reported_overflow_status) != 0
    assert child_dirs[0] / "events.jsonl"
    child_rows = session_db.read_event_rows(run_id=child_report["task_id"])
    assert any(row["kind"] == "tool_result" and row["tool_name"] == "fs_read_file" for row in child_rows)
    bash_result = next(
        row["content"] for row in child_rows if row["kind"] == "tool_result" and row["tool_name"] == "fs_run_bash"
    )
    assert bash_result["ok"] is (backend_mode == "approved")
    if backend_mode == "approved":
        assert "private-scratch-note" in bash_result["result"]["stdout"]
        assert "overflow_exit=" in bash_result["result"]["stdout"]
        overflow_status = bash_result["result"]["stdout"].rsplit("overflow_exit=", 1)[1].split()[0]
        assert overflow_status.isdecimal() and int(overflow_status) != 0
    else:
        assert exec_denials == expected_denials[backend_mode]
    rows = session_db.read_event_rows(run_id=run.run_id)
    write_result = next(
        row["content"] for row in rows if row["kind"] == "tool_result" and row["tool_call_id"] == "managed-chat-write"
    )
    assert write_result["ok"] is True
    assert write_result["result"]["path"].endswith("managed-chat-note.txt")


def _watch_workflow_revision_diff(service: Any, provider_oracle: Any, mode: str) -> tuple[list[Any], list[Any]]:
    calls: list[Any] = []
    effects: list[Any] = []
    original = service._diff_revisions

    def counted(peer: Any, request: dict[str, Any], deadline: float) -> Any:
        calls.append(request)
        workspace_id = request["view_ref"]["workspace_id"]
        before_tree = provider_oracle.canonical_snapshot()
        before_revision = service.authority._bindings[workspace_id].current["revision_id"]
        effects.append((workspace_id, before_tree, before_revision))
        if mode == "refused":
            assert provider_oracle.canonical_snapshot() == before_tree
            assert service.authority._bindings[workspace_id].current["revision_id"] == before_revision
            raise SupervisorError("BACKEND_UNAVAILABLE")
        result = original(peer, request, deadline)
        assert provider_oracle.canonical_snapshot() == before_tree
        assert service.authority._bindings[workspace_id].current["revision_id"] == before_revision
        return result

    service._diff_revisions = counted
    return calls, effects


def _assert_workflow_revision_diff(
    stage_role: str,
    mode: str,
    calls: list[Any],
    effects: list[Any],
    provider_oracle: Any,
    service: Any,
    managed: ManagedExecution,
) -> None:
    assert len(calls) == int(stage_role == "coder")
    if stage_role != "coder":
        assert not calls and not provider_oracle.eval_requests
        return
    request = calls[0]
    assert request["protocol_version"] == 2 and request["op"] == "diff_revisions"
    assert request["view_ref"]["access"] == "READ" and request["view_ref"]["purpose"] == "PROJECT"
    assert request["payload"]["base_revision"].startswith("rev-")
    assert len(provider_oracle.eval_requests) == 1
    eval_messages = json.dumps(provider_oracle.eval_requests[0].messages, default=str)
    if mode == "refused":
        assert "Changed files: unavailable" in eval_messages
        assert "Changed files: NONE" not in eval_messages
    else:
        assert "Changed files: NONE between the sealed managed revisions" in eval_messages
    for _workspace_id, before_tree, _before_revision in effects:
        assert provider_oracle.canonical_snapshot() == before_tree
        assert service.authority.journal.lookup("op-" + request["request_id"], managed.binding.namespace) is None


@pytest.mark.parametrize("stage_role", ["planner", "coder"])
@pytest.mark.parametrize("backend_mode", ["unavailable", "unapproved", "approved"])
@pytest.mark.parametrize("revision_diff_mode", ["available", "refused"])
def test_workflow_stage_runs_managed_child_with_local_backend(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    local_cell_peer: Endpoint,
    stage_role: str,
    backend_mode: str,
    revision_diff_mode: str,
) -> None:
    from fa.feature_flags import FeatureFlags, FeatureFlagsLoadResult
    from fa.inner_loop.session_db import SessionDatabase
    from fa.providers import ProviderChain, SecretStore

    monkeypatch.setattr(
        "fa.feature_flags.load_feature_flags_from_path",
        lambda: FeatureFlagsLoadResult(
            FeatureFlags(
                subagent_spawning_enabled=True,
                subagent_chat_enabled=True,
                subagent_planner_enabled=stage_role == "planner",
                subagent_coder_enabled=stage_role == "coder",
            )
        ),
    )
    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path / "fa-state"))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(site.roots))
    (site.source / "README.md").write_text("source note", encoding="utf-8")
    models = site.source / "models.yaml"
    models.write_text(
        """chat:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
planner:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
coder:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
eval:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
""",
        encoding="utf-8",
    )
    document = _document(site)
    reader_profile = None
    cell_worker = None
    if backend_mode != "unavailable":
        _, reader_profile, cell_worker = _configure_local_cell_backend(local_cell_peer, tmp_path, document)
        if backend_mode == "unapproved":
            document.pop("approved_cache")
    service_path, service_config = _configs(tmp_path, document)
    monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", service_config)
    if backend_mode == "approved":
        assert reader_profile is not None
        install_environment_artifact(Path(document["approved_cache"]), site.source, profile=reader_profile)

    scratch_note = f"{stage_role}-scratch"
    scratch_path = shlex.quote(str(tmp_path / f"{stage_role}-private-scratch.txt"))
    exec_command = "printf child-probe"
    if backend_mode == "approved":
        exec_command = (
            f"printf {scratch_note} > {scratch_path}; IFS= read -r note < {scratch_path}; printf '%s' \"$note\""
        )
    provider_oracle = _ManagedChatProviderOracle(site.source, exec_command=exec_command, parent_role=stage_role)

    def provider_request(chain: Any, request: Any, *, logical_call_id: str | None = None) -> Any:
        return provider_oracle(chain, request, logical_call_id=logical_call_id)

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    session_db_path = session_dir / "session.db"
    session_db = SessionDatabase(session_db_path, session_id="workflow-session")
    session = SessionContext("workflow-session", site.source, session_db_path, session_dir / "manifest.json")
    run_log_dir = tmp_path / "workflow-run-logs"
    run_log_dir.mkdir()
    run = RunContext("workflow-run", "workflow-session", site.source, session_db_path, run_log_dir)
    monkeypatch.setattr(
        cli,
        "_resolve_workflow_lifecycle",
        lambda _args, run_id: (run_id, session, run, session_db),
    )
    managed_instances: list[ManagedExecution] = []
    original_managed_for_run = managed_execution_for_run

    def track_managed_for_run(*args: Any, **kwargs: Any) -> ManagedExecution | None:
        managed = original_managed_for_run(*args, **kwargs)
        if managed is not None:
            managed_instances.append(managed)
        return managed

    monkeypatch.setattr(cli, "managed_execution_for_run", track_managed_for_run)

    class _WorkflowWorkspace:
        @staticmethod
        def resolve_workflow_workspace(**_kwargs: Any) -> Path:
            return site.source

    monkeypatch.setattr(cli, "_session_manager_for_args", lambda _args: _WorkflowWorkspace())
    workflow_args = [
        "workflow",
        stage_role,
        "fix typo in README",
        "--workspace",
        str(site.source),
        "--session-id",
        "workflow-session",
        "--run-id",
        "workflow-run",
        "--config",
        str(models),
        "--max-turns",
        "5",
    ]
    if stage_role == "coder":
        plan_path = site.source / PLAN_RELATIVE
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(
            "Plan-ID: PLAN-workflow-coder\n\n## SLICE1: managed child workflow\nCONTRACTS:\n"
            "  CT13 [CONSTRAINT]: child execution remains managed and read-only.\n"
            "TESTS: tests/test_execution_composition.py\n",
            encoding="utf-8",
        )
        workflow_args.extend(["--plan", PLAN_RELATIVE])
    args = cli.build_parser().parse_args(workflow_args)
    host_subprocess_calls = _watch_managed_child_host_execution(monkeypatch)
    exec_requests: list[dict[str, Any]] = []
    exec_denials: list[str] = []
    proxy_credential_leaks: list[str] = []
    revision_diff_calls: list[dict[str, Any]] = []
    revision_diff_effects: list[tuple[str, tuple[tuple[str, bytes], ...], str]] = []
    with SupervisorService(read_config_file(service_path)) as service:
        assert (service._backend is not None) is (backend_mode != "unavailable")
        original_exec = service._exec

        def counted_exec(peer: Any, request: dict[str, Any], deadline: float) -> Any:
            exec_requests.append(request)
            raw_request = json.dumps(request)
            if "X_FA_PROXY_TOKEN" in raw_request or "sk-test-live" in raw_request:
                proxy_credential_leaks.append(raw_request)
            try:
                return original_exec(peer, request, deadline)
            except SupervisorError as exc:
                exec_denials.append(exc.code)
                raise

        service._exec = counted_exec  # type: ignore[method-assign]
        revision_diff_calls, revision_diff_effects = _watch_workflow_revision_diff(
            service, provider_oracle, revision_diff_mode
        )
        with _serving_supervisor(service):
            assert cli._cmd_workflow(args, secrets=SecretStore({"K": "sk-test-live"})) == 0
        assert len(managed_instances) == 1
        metadata = site.metadata({"workspace_id": managed_instances[0].binding.workspace_id})
        assert metadata["status"] == "AVAILABLE"

    assert provider_oracle.parent_calls == (2 if stage_role == "planner" else 3)
    assert provider_oracle.child_calls == 3
    assert provider_oracle.eval_calls == int(stage_role == "coder")
    _assert_workflow_revision_diff(
        stage_role,
        revision_diff_mode,
        revision_diff_calls,
        revision_diff_effects,
        provider_oracle,
        service,
        managed_instances[0],
    )
    assert not provider_oracle.child_project_write
    assert provider_oracle.observed == [provider_oracle.canonical_snapshot()]
    assert not (site.source / "managed-chat-note.txt").exists()
    assert len(exec_requests) == 1
    expected_denials = {
        "unavailable": ["BACKEND_UNAVAILABLE"],
        "unapproved": ["UNAPPROVED_PROFILE"],
        "approved": [],
    }
    assert exec_denials == expected_denials[backend_mode]
    cell_launches = sum(
        item["method"] == "POST" and "/containers/create?" in item["path"] for item in local_cell_peer.seen
    )
    counters = {
        "exec_requests": len(exec_requests),
        "exec_allowed": len(exec_requests) - len(exec_denials),
        "cell_launches": cell_launches,
        "host_subprocesses": len(host_subprocess_calls),
        "proxy_credentials": len(proxy_credential_leaks),
        "project_writes": int(provider_oracle.child_project_write),
    }
    assert counters == {
        "exec_requests": 1,
        "exec_allowed": int(backend_mode == "approved"),
        "cell_launches": int(backend_mode == "approved"),
        "host_subprocesses": 0,
        "proxy_credentials": 0,
        "project_writes": 0,
    }
    assert not local_cell_peer.errors
    if backend_mode == "approved":
        assert cell_worker is not None and cell_worker.runs == 1
        assert (tmp_path / f"{stage_role}-private-scratch.txt").read_text(encoding="utf-8") == f"{stage_role}-scratch"
        assert len(local_cell_peer.seen) == 6
        create_body = next(item["body"] for item in local_cell_peer.seen if "/containers/create?" in item["path"])
        expected_tmpfs = {"/scratch": f"size={READ_SCRATCH_BYTES},mode=1777,nosuid,nodev"}
        assert create_body["HostConfig"].get("Tmpfs") == expected_tmpfs
        assert any(
            mount["Target"] == "/workspace" and mount["ReadOnly"] is True
            for mount in create_body["HostConfig"]["Mounts"]
        )
        assert not any(mount["Target"] == "/scratch" for mount in create_body["HostConfig"]["Mounts"])
    else:
        assert local_cell_peer.seen == []
        if backend_mode == "unapproved":
            assert cell_worker is not None and cell_worker.runs == 0
            assert len(local_cell_peer.replies) == 6
        else:
            assert cell_worker is None and not local_cell_peer.replies
    child_dirs = list((run.run_log_dir / "subagents").iterdir())
    assert len(child_dirs) == 1 and not child_dirs[0].is_relative_to(site.source)
    report = json.loads((child_dirs[0] / "report.json").read_text(encoding="utf-8"))
    assert report["parent_role"] == stage_role and report["summary"] == "README contains source note."
    child_rows = session_db.read_event_rows(run_id=report["task_id"])
    bash_result = next(
        row["content"] for row in child_rows if row["kind"] == "tool_result" and row["tool_name"] == "fs_run_bash"
    )
    assert bash_result["ok"] is (backend_mode == "approved")
    assert any(row["kind"] == "tool_result" and row["tool_name"] == "fs_read_file" for row in child_rows)


def test_failed_stage_stop_is_not_retried_by_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unproved STOP_VIEW is one attempt, not an invitation to retry in cleanup."""
    from fa.inner_loop.coder_loop import SessionOutcome
    from fa.inner_loop.registry import ToolRegistry

    workspace = tmp_path / "project"
    workspace.mkdir()
    workspace_id = "ws-" + "1" * 32
    revision_id = "rev-" + "2" * 32
    view_ref = ViewRef(
        workspace_id,
        "view-" + "3" * 32,
        revision_id,
        "stage-run",
        1,
        Access.WRITE,
        ViewPurpose.PROJECT,
    )
    view_grant = GrantReply(
        Operation.CREATE_VIEW,
        "4" * 64,
        view_ref,
        None,
        None,
        "5" * 64,
    )
    stop_calls = 0

    def stop_view(_grant: GrantReply) -> bool:
        nonlocal stop_calls
        stop_calls += 1
        return False

    managed = ManagedExecution(
        client=ExecutionClient(tmp_path / "supervisor.sock", server_uid=os.getuid(), rpc_timeout_ms=100),
        binding=ExecutionBinding(NamespaceRef("session-1", "stage-run"), workspace_id),
        grant=GrantReply(Operation.ACQUIRE_WRITER, "6" * 64, None, 1, revision_id, None),
        view_profile=native_profile(),
    )
    monkeypatch.setattr(managed, "open_view", lambda **_kwargs: view_grant)
    monkeypatch.setattr(managed, "stop_view", stop_view)

    with pytest.raises(ExecutionUnavailableError):
        cli._drive_stage_with_managed_workspace(
            managed=managed,
            owns_writer=False,
            run_id="stage-run",
            run_log_dir=tmp_path / "run-log",
            session_db=None,
            workspace=workspace,
            role="chat",
            plan_ref=None,
            build_registry=lambda _workspace_io, _managed_executor, _stage_lease: ToolRegistry(),
            drive=lambda _registry: SessionOutcome(1, "iteration_cap", 1, ""),
        )
    assert stop_calls == 1


def test_workflow_forwards_one_managed_execution_to_every_stage(tmp_path: Path) -> None:
    """No stage reacquires authority; every dispatch sees the identical run-owned object."""
    workspace = tmp_path / "project"
    workspace.mkdir()
    run = _run(workspace)
    binding = ExecutionBinding(NamespaceRef("session-1", "run-1"), "ws-" + "1" * 32)

    class StageAuthority:
        def publish_stage(self, *_: Any, **__: Any) -> StagePublication:
            return StagePublication("seal-" + "6" * 32, "rev-" + "7" * 32, "8" * 64, "op-" + "9" * 32)

    initial_revision = "rev-" + "3" * 32
    managed = ManagedExecution(
        StageAuthority(),  # type: ignore[arg-type]
        binding,
        GrantReply(Operation.ACQUIRE_WRITER, "2" * 64, None, 1, initial_revision),
        view_profile=native_profile(),
    )
    stage_grant = GrantReply(
        Operation.CREATE_VIEW,
        "4" * 64,
        ViewRef(
            binding.workspace_id,
            "view-" + "5" * 32,
            initial_revision,
            "run-1",
            1,
            Access.WRITE,
            ViewPurpose.MUTATION,
        ),
        None,
        None,
    )
    dispatched: list[argparse.Namespace] = []
    observed_revisions: list[str] = []

    def stage(args: argparse.Namespace, **_: Any) -> int:
        dispatched.append(args)
        observed_revisions.append(args._managed_execution.current_revision_id)
        if args.role == "planner":
            args._managed_execution.publish_stage(stage_grant)
        return 0

    workflow_controller.run_workflow(
        roles=["planner", "eval"],
        task="exercise managed stage handoff",
        per_role_task={},
        mode="linear",
        max_repairs=None,
        max_replans=None,
        run_id=run.run_id,
        config=tmp_path / "models.yaml",
        workspace=workspace,
        max_turns=1,
        run_stage_fn=stage,
        run_context=run,
        managed_execution=managed,
    )

    assert [args.role for args in dispatched] == ["planner", "eval"]
    assert all(args._managed_execution is managed for args in dispatched)
    assert all(args._managed_execution.view_profile == native_profile() for args in dispatched)
    assert observed_revisions == [initial_revision, "rev-" + "7" * 32]
    assert managed.current_revision_id == observed_revisions[-1]
    assert all(args._managed_plan_ref is None for args in dispatched)


class _ScriptedAuthority:
    """A client double that models the authority's documented replay contract.

    ``lost`` names the operations whose first reply is lost; the repeat of that
    request id answers from the completed-reply cache, exactly as the supervisor
    does (``_completed`` -> ``_replies.replay``).
    """

    def __init__(self, *, lost: set[Operation], answer_the_replay: bool) -> None:
        self.lost = set(lost)
        self.answer_the_replay = answer_the_replay
        self.seen: list[tuple[Operation, str]] = []

    def request(self, operation: Operation, *, request_id: str, **_: Any) -> dict[str, Any]:
        repeat = any(sent_id == request_id for _, sent_id in self.seen)
        self.seen.append((operation, request_id))
        if operation in self.lost and (not repeat or not self.answer_the_replay):
            raise ExecutionUncertainError("op-" + request_id)
        if operation is Operation.REGISTER_WORKSPACE:
            return {"workspace_id": "ws-" + "1" * 32, "revision_id": "rev-" + "2" * 32}
        return {"capability": "9" * 64, "generation": 1, "revision_id": "rev-" + "2" * 32}


def _compose(monkeypatch: pytest.MonkeyPatch, client: Any, tmp_path: Path) -> Any:
    monkeypatch.setattr(
        composition,
        "_service_config",
        lambda path=None: SimpleNamespace(profiles=(), view_profile_id=None),
    )
    monkeypatch.setattr(composition, "_client_for", lambda config: client)
    monkeypatch.setattr(composition, "_root_binding", lambda config, path: ("projects", "."))
    return managed_execution_for_run(_run(tmp_path))


def _paths_to(value: str, holder: Any) -> set[tuple[str, ...]]:
    """Every attribute path reachable from ``holder`` whose value is exactly ``value``."""
    found: set[tuple[str, ...]] = set()
    seen: set[int] = set()

    def walk(item: Any, path: tuple[str, ...]) -> None:
        # Strings are shared objects, so the cycle guard must not swallow a second
        # *path* to the same token - that is exactly the copy this test hunts.
        if isinstance(item, str):
            if item == value:
                found.add(path)
            return
        if id(item) in seen:
            return
        seen.add(id(item))
        if isinstance(item, dict):
            for key, child in item.items():
                walk(child, (*path, str(key)))
            return
        if isinstance(item, (list, tuple, set, frozenset)):
            for index, child in enumerate(item):
                walk(child, (*path, f"[{index}]"))
            return
        fields = getattr(item, "__dict__", None)
        if isinstance(fields, dict):
            for name, child in fields.items():
                walk(child, (*path, name))

    walk(holder, ())
    return found


def test_the_writer_capability_lives_in_exactly_one_place(tmp_path: Path) -> None:
    """Q90, stated as what this design actually claims, and made checkable.

    Q90's letter - "``ExecutionClient`` alone caches and selects raw grants" - is not
    what SLICE7 built: the client is stateless and each operation is handed its grant
    explicitly, which is why the run's one writer grant lives on `ManagedExecution`.
    That is a deliberate contract (STEP6-STEP8), not an oversight, so the invariant
    worth pinning is the one that can actually break: the token has **one** holder
    path, and a second copy anywhere on the CLI's object graph fails here.
    """
    capability = "7" * 64
    binding = ExecutionBinding(NamespaceRef("session-1", "run-1"), "ws-" + "1" * 32)
    managed = ManagedExecution(
        ExecutionClient(tmp_path / "supervisor.sock", server_uid=os.getuid(), rpc_timeout_ms=100),
        binding,
        GrantReply(Operation.ACQUIRE_WRITER, capability, None, 1, "rev-" + "2" * 32),
    )
    publisher = BoundPlanPublisher(managed, binding)

    assert _paths_to(capability, managed) == {("grant", "capability")}
    assert _paths_to(capability, publisher) == {("_managed", "grant", "capability")}
    for holder in (managed, publisher):
        assert capability not in repr(holder)  # what a log line or a traceback would show


def test_a_lost_writer_reply_is_replayed_under_the_same_request_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """producer-kill-check: replay under a fresh id (or not at all) and the grant is lost.

    A fresh id would meet ``WORKSPACE_BUSY``, because the run itself already holds the
    writer the authority issued against the frame nobody read.
    """
    client = _ScriptedAuthority(lost={Operation.ACQUIRE_WRITER}, answer_the_replay=True)
    managed = _compose(monkeypatch, client, tmp_path)

    assert managed is not None and managed.grant.capability == "9" * 64  # the original grant came back
    writers = [request_id for operation, request_id in client.seen if operation is Operation.ACQUIRE_WRITER]
    assert len(writers) == 2 and writers[0] == writers[1]
    registrations = [rid for operation, rid in client.seen if operation is Operation.REGISTER_WORKSPACE]
    assert registrations != writers  # a replay, never one id reused for a different operation


def test_a_writer_grant_that_cannot_be_confirmed_refuses_the_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The run must not continue as if it had no authority: it may hold the writer."""
    client = _ScriptedAuthority(lost={Operation.ACQUIRE_WRITER}, answer_the_replay=False)

    with pytest.raises(ExecutionUncertainError):
        _compose(monkeypatch, client, tmp_path)

    assert [operation for operation, _ in client.seen].count(Operation.ACQUIRE_WRITER) == 2


def test_an_unreadable_registration_is_not_a_strand(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Registering grants nothing, so an unknown answer is still "no managed run"."""
    lost = _ScriptedAuthority(lost={Operation.REGISTER_WORKSPACE}, answer_the_replay=False)

    assert _compose(monkeypatch, lost, tmp_path) is None
    assert {operation for operation, _ in lost.seen} == {Operation.REGISTER_WORKSPACE}
    assert len({request_id for _, request_id in lost.seen}) == 1  # a replay, not a second registration

    # The same lost frame, but the authority can answer the repeat: the run proceeds
    # with the identity it already registered instead of failing for no reason.
    replayed = _ScriptedAuthority(lost={Operation.REGISTER_WORKSPACE}, answer_the_replay=True)
    assert _compose(monkeypatch, replayed, tmp_path) is not None


def test_an_unconfirmed_writer_is_reported_to_the_operator(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """C1: the refusal reaches the operator as one line and a non-zero exit, not a traceback."""
    workspace = tmp_path / "project"
    workspace.mkdir()
    run = _run(workspace)
    monkeypatch.setattr(cli, "_resolve_workflow_lifecycle", lambda args, run_id: (run_id, None, run, None))
    monkeypatch.setattr(
        cli, "managed_execution_for_run", lambda *a, **k: (_ for _ in ()).throw(ExecutionUncertainError("op-1"))
    )
    args = argparse.Namespace(
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
    stderr = io.StringIO()
    with redirect_stderr(stderr):
        assert cli._cmd_workflow(args) == 2
    message = stderr.getvalue()
    assert "writer grant not confirmed" in message and "EXECUTION_UNKNOWN" in message
    assert "needs recovery" in message and "Traceback" not in message


@pytest.mark.parametrize(
    "failure",
    [
        ExecutionUncertainError(None),
        ExecutionRejectedError("NOT_OWNER", None),
        ExecutionUnavailableError(),
    ],
    ids=["uncertain", "rejected", "unavailable"],
)
def test_a_release_that_is_not_confirmed_is_reported_and_never_retried(
    failure: Exception, caplog: pytest.LogCaptureFixture
) -> None:
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
    with caplog.at_level(logging.WARNING, logger="fa.execution.composition"):
        assert managed.close() is False
    assert client.calls == [Operation.RELEASE]  # one attempt: a fixed id, no retry
    assert len([record for record in caplog.records if "writer release not confirmed" in record.getMessage()]) == 1


def test_managed_readiness_probes_both_required_tools_and_settles_same_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C1: readiness executes both probes in the admitted run's PROVISIONING view."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_context = _run(workspace)
    run_context.run_log_dir.mkdir()
    namespace = NamespaceRef(run_context.session_id, run_context.run_id)
    view = ViewRef(
        "ws-" + "1" * 32,
        "view-" + "2" * 32,
        "rev-" + "3" * 32,
        run_context.run_id,
        1,
        Access.WRITE,
        ViewPurpose.PROVISIONING,
    )
    view_grant = SimpleNamespace(view_ref=view, input_tree_sha256="4" * 64)
    calls: list[tuple[str, Any]] = []

    class FakeExecutor:
        def __init__(self, _client: Any, **kwargs: Any) -> None:
            assert kwargs["namespace"] == namespace
            assert kwargs["view"] == view
            calls.append(("bind", kwargs["profile"].profile_id))

        def run(self, command: str, *, timeout: int, session_id: str) -> Any:
            calls.append(("exec", (command, timeout, session_id)))
            return SimpleNamespace(stdout="pytest 9.0\nmutmut 3.6\n", exit_code=0, timed_out=False)

        def suspend(self) -> None:
            calls.append(("suspend", None))

    class FakeManaged:
        client = object()
        binding = ExecutionBinding(namespace, view.workspace_id)
        grant = GrantReply(Operation.ACQUIRE_WRITER, "5" * 64, None, 1, "rev-" + "3" * 32)
        current_revision_id = "rev-" + "3" * 32
        view_profile = native_profile()

        def open_view(self, **kwargs: Any) -> Any:
            calls.append(("open", kwargs))
            return view_grant

        def stop_view(self, grant: Any, *, deadline: float | None = None) -> bool:
            calls.append(("stop", (grant, deadline)))
            return True

        def close(self, *, deadline: float | None = None) -> bool:
            calls.append(("release", deadline))
            return True

    managed = FakeManaged()
    monkeypatch.setattr(composition, "managed_execution_for_run", lambda run: managed)
    monkeypatch.setattr(composition, "ManagedBashExecutor", FakeExecutor)

    state = composition.managed_environment_readiness(workspace, run_context)

    assert state.status is ReadyStatus.READY
    assert state.reason_code == "ready_managed_artifact"
    assert state.log_path.read_text(encoding="utf-8") == "pytest 9.0\nmutmut 3.6\n"
    assert calls[0][0] == "open"
    assert calls[0][1]["access"] is Access.WRITE
    assert calls[0][1]["purpose"] is ViewPurpose.PROVISIONING
    assert calls[1][0] == "bind"
    assert calls[2] == (
        "exec",
        (
            "/workspace/.venv/bin/python -I -m pytest --version && /workspace/.venv/bin/python -I -m mutmut --version",
            30,
            "readiness",
        ),
    )
    assert [name for name, _ in calls[-3:]] == ["suspend", "stop", "release"]


def test_unconfirmed_readiness_view_end_withholds_writer_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C3: an unconfirmed view stop never releases the run's writer."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_context = _run(workspace)
    run_context.run_log_dir.mkdir()
    namespace = NamespaceRef(run_context.session_id, run_context.run_id)
    view = ViewRef(
        "ws-" + "1" * 32,
        "view-" + "2" * 32,
        "rev-" + "3" * 32,
        run_context.run_id,
        1,
        Access.WRITE,
        ViewPurpose.PROVISIONING,
    )
    view_grant = SimpleNamespace(view_ref=view, input_tree_sha256="4" * 64)
    calls: list[str] = []

    class FakeExecutor:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def run(self, *_args: Any, **_kwargs: Any) -> Any:
            return SimpleNamespace(stdout="ok", exit_code=0, timed_out=False)

        def suspend(self) -> None:
            calls.append("suspend")

    class FakeManaged:
        client = object()
        binding = ExecutionBinding(namespace, view.workspace_id)
        grant = GrantReply(Operation.ACQUIRE_WRITER, "5" * 64, None, 1, "rev-" + "3" * 32)
        current_revision_id = "rev-" + "3" * 32
        view_profile = native_profile()

        def open_view(self, **_kwargs: Any) -> Any:
            return view_grant

        def stop_view(self, *_args: Any, **_kwargs: Any) -> bool:
            calls.append("stop")
            return False

        def close(self, **_kwargs: Any) -> bool:
            calls.append("release")
            return True

    monkeypatch.setattr(composition, "managed_execution_for_run", lambda run: FakeManaged())
    monkeypatch.setattr(composition, "ManagedBashExecutor", FakeExecutor)

    state = composition.managed_environment_readiness(workspace, run_context)

    assert state.status is ReadyStatus.DEGRADED_ENVIRONMENT
    assert state.reason_code == "managed_artifact_probe_failed"
    assert calls == ["suspend", "stop"]


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


def test_the_client_provisioner_materializes_a_root_from_an_approved_source(site: Site, tmp_path: Path) -> None:
    """C1 edge proof: SessionManager's provision port emits create=true on the admitted identity."""
    sessions = tmp_path / "sessions"
    repo = tmp_path / "repo"
    sessions.mkdir()
    repo.mkdir()
    (repo / "README.md").write_text("source", encoding="utf-8")
    (repo / ".git").mkdir()
    (repo / ".git" / "index").write_text("not copied", encoding="utf-8")
    document = _document(site)
    document["approved_roots"] = {"sessions": str(sessions), "repo": str(repo)}
    service_path, yaml_path = _configs(tmp_path, document)
    with SupervisorService(read_config_file(service_path)) as service:
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        try:
            provisioner = client_workspace_provisioner(config_path=yaml_path)
            assert isinstance(provisioner, ClientWorkspaceProvisioner)
            target = sessions / "session-1"
            request = ProvisionRequest(
                ProvisionMode.PROVISION,
                "session-1",
                "run-1",
                target,
                time.monotonic() + 5,
                source_workspace=repo,
            )
            provisioned = provisioner(request)
            assert provisioned.registered and provisioned.workspace_id and provisioned.revision_id
            assert (target / "README.md").read_text(encoding="utf-8") == "source"
            assert not (target / ".git").exists()
            empty_request = replace(request, workspace_path=sessions / "clean", source_workspace=None)
            empty = provisioner(empty_request)
            assert empty.registered and empty.workspace_id != provisioned.workspace_id
            assert list(empty_request.workspace_path.iterdir()) == []
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
            assert refused.value.code == "workspace_escape"
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
    args = argparse.Namespace(workspace=site.source)
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


def test_r10_managed_chat_bash_refusal_never_falls_back_to_host(
    tmp_path: Path, site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R10 production-caller oracle: registered chat Bash reaches managed EXEC and fails closed."""
    from fa.inner_loop.session_db import SessionDatabase
    from fa.inner_loop.tools import run_bash as run_bash_module
    from fa.providers import ProviderChain, SecretStore

    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path / "fa-state"))
    monkeypatch.setattr(cli, "_build_pty_pool", lambda **_kwargs: object())
    models = tmp_path / "models.yaml"
    models.write_text(
        """chat:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
""",
        encoding="utf-8",
    )
    service_path, config_path = _configs(tmp_path, _document(site))
    session_db_path = tmp_path / "session.db"
    run_log_dir = tmp_path / "session-log" / "run-r10"
    session_db = SessionDatabase(session_db_path, session_id="session-r10")
    session_context = SessionContext("session-r10", site.source, session_db_path, tmp_path / "manifest.json")
    run_context = RunContext("run-r10", "session-r10", site.source, session_db_path, run_log_dir)
    provider_calls = 0

    def provider_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        nonlocal provider_calls
        provider_calls += 1
        names = {
            str(tool.get("function", {}).get("name", ""))
            for tool in request.tools
            if isinstance(tool.get("function"), dict)
        }
        if provider_calls == 1:
            assert "fs_run_bash" in names, "production chat registry did not expose its assigned Bash tool"
            call = {
                "id": "r10-managed-bash",
                "type": "function",
                "function": {
                    "name": "fs_run_bash",
                    "arguments": json.dumps({"command": "touch r10-host-marker"}),
                },
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "r10", []
        assert provider_calls == 2
        return ResponseInfo("managed refusal recorded", 1, 1, "stop"), logical_call_id or "r10", []

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    fallback_calls: list[tuple[Any, ...]] = []
    host_process_calls: list[tuple[Any, ...]] = []

    def trapped_fallback(*args: Any, **_kwargs: Any) -> Any:
        fallback_calls.append(args)
        return ToolResult.fail("mutant_host_fallback", "host fallback tripwire", retryable=False)

    def trapped_subprocess(*args: Any, **_kwargs: Any) -> Any:
        host_process_calls.append(args)
        raise AssertionError("host subprocess tripwire reached")

    monkeypatch.setattr(run_bash_module, "_run_subprocess_fallback", trapped_fallback)
    monkeypatch.setattr(subprocess, "run", trapped_subprocess)
    exec_requests: list[dict[str, Any]] = []
    exec_denials: list[str] = []

    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        assert workspace_id
        original_exec = service._exec

        def counted_exec(peer: Any, request: dict[str, Any], deadline: float) -> Any:
            exec_requests.append(request)
            try:
                return original_exec(peer, request, deadline)
            except SupervisorError as exc:
                exec_denials.append(exc.code)
                raise

        service._exec = counted_exec  # type: ignore[method-assign]
        with _serving_supervisor(service):
            managed = managed_execution_for_run(run_context, config_path=config_path)
            assert managed is not None
            args = cli.build_parser().parse_args(
                [
                    "run",
                    "--role",
                    "chat",
                    "--config",
                    str(models),
                    "--workspace",
                    str(site.source),
                    "--run-id",
                    "run-r10",
                    "--max-turns",
                    "3",
                    "probe managed Bash refusal",
                ]
            )
            args._managed_execution = managed
            args._session_context = session_context
            args._run_context = run_context
            args._session_db = session_db
            try:
                exit_code = cli._cmd_run(args, secrets=SecretStore({"K": "sk-test-live"}))
            finally:
                release_confirmed = managed.close()

    rows = session_db.read_event_rows(run_id="run-r10")
    bash_results = [
        row["content"] for row in rows if row["kind"] == "tool_result" and row["tool_name"] == "fs_run_bash"
    ]
    assert exit_code == 0 and release_confirmed
    assert provider_calls == 2 and len(bash_results) == 1
    assert fallback_calls == [] and host_process_calls == []
    assert bash_results[0]["ok"] is False
    assert bash_results[0]["error"]["code"] == "execution_unavailable"
    assert bash_results[0]["error"]["retryable"] is False
    assert len(exec_requests) == 1 and exec_denials == ["BACKEND_UNAVAILABLE"]
    assert not (site.source / "r10-host-marker").exists()


@pytest.mark.parametrize("lost_reply", [False, True], ids=["handler-refused", "reply-lost"])
def test_an_unresolved_candidate_publication_keeps_the_writer_and_reconciles(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lost_reply: bool
) -> None:
    """Q138 option B / Q114 1-A: the run, not the caller, holds the pending proof.

    The two failure shapes this covers are exactly the two the journal can answer
    differently, and the difference is the whole reason the pending record exists:

    * ``handler-refused`` — the authority's PUBLISH handler really failed. The
      journal records ``UNKNOWN``, and by design (``_completed``) that id never
      becomes ``DONE``. Replay therefore cannot prove publication; the honest
      outcome is another uncertainty, and the run keeps the writer fenced.
    * ``reply-lost`` — the commit happened and only the reply vanished. Replay of
      the *same* id is answered from the journal and the completed-reply cache, so
      reconciliation proves the publication without performing a second effect.

    The invariant in both: while the outcome is unknown, `close()` must NOT release
    the writer and the CANDIDATE view must NOT be dropped while the workspace goes
    back to `AVAILABLE`.

    R25 binds reconciliation to the port, so this test drives
    ``ManagedExecution.publish_plan`` directly. That is deliberate: the port's own
    behaviour (reconcile once, then classify) is a separate oracle below, and a
    test that went through the port could no longer observe the unresolved state at
    all -- precisely because the port now settles it.
    """
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
        original = service.authority.publish_candidate_plan
        seen: list[str] = []
        client_class = ExecutionClient

        def sabotage(*args: Any, **kwargs: Any) -> dict[str, Any]:
            seen.append(str(kwargs.get("operation_id")))
            if len(seen) <= 2:
                # The handler itself fails. The journal records UNKNOWN, and by
                # design that id never becomes DONE, so replay cannot prove
                # anything and reconciliation must stay honest.
                raise SupervisorError("DURABILITY_UNKNOWN")
            return original(*args, **kwargs)

        handler_calls: list[str] = []
        real = service.authority.publish_candidate_plan

        def counted(*args: Any, **kwargs: Any) -> dict[str, Any]:
            handler_calls.append(str(kwargs.get("operation_id")))
            return real(*args, **kwargs)

        if not lost_reply:
            monkeypatch.setattr(service.authority, "publish_candidate_plan", sabotage)
        else:
            # The authority completes the publication; only the reply is lost on
            # the way back, which is the one shape a same-id replay can settle
            # because the journal and the completed-reply cache both survive it.
            original_request = ExecutionClient.request
            lost: set[str] = set()

            def losing_request(self: Any, operation: Any, *, request_id: str, **kwargs: Any) -> Any:
                if operation is Operation.PUBLISH:
                    seen.append(request_id)
                answer = original_request(self, operation, request_id=request_id, **kwargs)
                if operation is Operation.PUBLISH and not lost:
                    # The supervisor completed the operation; the reply is dropped
                    # exactly once, as a timeout would drop it.
                    lost.add(request_id)
                    raise ExecutionUncertainError("op-" + request_id, code="EXECUTION_UNKNOWN")
                return answer

            monkeypatch.setattr(service.authority, "publish_candidate_plan", counted)
            monkeypatch.setattr(client_class, "request", losing_request)
        try:
            run = _run(site.source)
            managed = managed_execution_for_run(run, config_path=yaml_path)
            assert managed is not None
            with pytest.raises(ExecutionUncertainError) as unresolved:
                managed.publish_plan(source, candidate)
            pending = unresolved.value.pending_publication
            assert pending is not None
            assert managed.publication_pending is True

            # The writer is fenced: no release while the outcome is unknown.
            assert managed.close() is False
            assert _status(site, workspace_id)["status"] == "OWNED"

            if lost_reply:
                proof = managed.reconcile_publication()
                assert proof.plan_ref.sha256 == candidate.ref.sha256
                # The commit was the first attempt's, so `already_published` is the
                # value that attempt would have reported: reconciliation proves the
                # revision exists rather than claiming a second publication.
                assert proof.already_published is False
                assert proof.revision_id.startswith("rev-")
                # Reconciliation replayed the minted id and the authority answered
                # from its journal and reply cache: no second id was ever minted,
                # so no second effect could be performed.
                publish_request_id = pending.publish_request_id
                assert isinstance(publish_request_id, str)
                assert set(seen) == {publish_request_id}
                assert len(seen) == 2  # the lost attempt and the reconciliation
                # ...and the authority performed the publication exactly once.
                assert handler_calls == ["op-" + publish_request_id]
                assert managed.publication_pending is False
                assert plan_path.read_bytes() == candidate.utf8_bytes
                # Only now may the writer go back.
                assert managed.close() is True
                assert _status(site, workspace_id)["status"] == "AVAILABLE"
            else:
                # A failed handler is not proof either way: reconcile honestly
                # raises again, with the same pending record, and stays fenced.
                with pytest.raises(ExecutionUncertainError) as again:
                    managed.reconcile_publication()
                assert again.value.pending_publication is pending
                assert managed.publication_pending is True
                assert managed.close() is False
                assert _status(site, workspace_id)["status"] == "OWNED"
                # The canonical plan never moved: no half-commit is claimed.
                assert plan_path.read_bytes() == b"# Existing plan\n"
        finally:
            stop.set()
            runner.join(timeout=5)
            assert not runner.is_alive()


@pytest.mark.parametrize("ambiguity", ["reply-lost", "handler-refused", "determinate-refusal"])
def test_the_bound_publisher_reconciles_one_ambiguity_and_then_classifies(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ambiguity: str
) -> None:
    """R25 DoD: bound publisher, one-shot uncertainty, no premature release.

    The port is the only place that can decide the difference between "recoverable
    now" and "quarantine", so all three shapes are driven through it and the
    *observable* consequence is asserted, not the internal flag:

    * ``reply-lost`` — the commit happened, the reply vanished. The port replays the
      same ids, proves the revision, returns the promoted PlanRef, and the writer is
      released only afterwards. The run never enters quarantine.
    * ``handler-refused`` — the authority's PUBLISH handler failed, so the journal
      holds UNKNOWN and no replay can prove anything. The port raises the
      uncertainty, the writer stays fenced, and the workspace stays OWNED.
    * ``determinate-refusal`` — the authority refuses before anything was staged.
      That is the pre-existing R25 refusal, and it is the *good* case: no pending
      saga exists, so nothing is replayed and the writer is released normally. The
      canonical plan is untouched and no candidate view is left behind.

    In every arm the canonical plan is only ever the old bytes or the candidate
    bytes — never a partial state — and no second publication id is minted.
    """
    plan_path = site.source / PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(b"# Existing plan\n")
    original_bytes = plan_path.read_bytes()
    source = read_plan_snapshot(site.source, Path(PLAN_RELATIVE))
    candidate = snapshot_from_bytes("draft.md", b"# Repaired plan\n")
    service_path, yaml_path = _configs(tmp_path, _document(site))
    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        original = service.authority.publish_candidate_plan
        seen: list[str] = []

        def sabotage(*args: Any, **kwargs: Any) -> dict[str, Any]:
            seen.append(str(kwargs.get("operation_id")))
            if ambiguity == "determinate-refusal":
                raise SupervisorError("INPUT_POLICY")
            if len(seen) <= 2:
                raise SupervisorError("DURABILITY_UNKNOWN")
            return original(*args, **kwargs)

        lost: set[str] = set()
        client_request = ExecutionClient.request
        published_ids: list[str] = []

        def counting_request(self: Any, operation: Any, *, request_id: str, **kwargs: Any) -> Any:
            if operation is Operation.PUBLISH:
                published_ids.append(request_id)
            answer = client_request(self, operation, request_id=request_id, **kwargs)
            if ambiguity == "reply-lost" and operation is Operation.PUBLISH and not lost:
                lost.add(request_id)
                raise ExecutionUncertainError("op-" + request_id, code="EXECUTION_UNKNOWN")
            return answer

        if ambiguity == "reply-lost":
            monkeypatch.setattr(ExecutionClient, "request", counting_request)
        else:
            monkeypatch.setattr(service.authority, "publish_candidate_plan", sabotage)
        try:
            run = _run(site.source)
            managed = managed_execution_for_run(run, config_path=yaml_path)
            assert managed is not None
            publisher = BoundPlanPublisher(managed, managed.binding)
            if ambiguity == "reply-lost":
                before = managed.current_revision_id
                promoted = publisher.publish_candidate(source, candidate)
                assert promoted.sha256 == candidate.ref.sha256
                # The run must now sit on the revision the authority actually
                # committed. "Changed" is not enough: a wrong-but-different id would
                # make every later CAS fail with STALE_REVISION against the
                # authority's own truth, so the value is pinned to the workspace
                # record rather than to the port's return value (a PlanRef carries
                # no revision id).
                assert managed.current_revision_id != before
                head = json.loads((site.state / "workspaces" / workspace_id / "current.json").read_text())[
                    "revision_id"
                ]
                assert managed.current_revision_id == head
                assert managed.publication_pending is False
                assert plan_path.read_bytes() == candidate.utf8_bytes
                # Exactly one id, replayed: the commit happened once.
                assert len(set(published_ids)) == 1
                assert managed.close() is True
                assert _status(site, workspace_id)["status"] == "AVAILABLE"
            elif ambiguity == "determinate-refusal":
                with pytest.raises(ExecutionRejectedError):
                    publisher.publish_candidate(source, candidate)
                # A determinate refusal leaves no saga behind, so the writer is not
                # fenced: the run ends clean and the workspace is reusable.
                assert managed.publication_pending is False
                assert managed.close() is True
                assert _status(site, workspace_id)["status"] == "AVAILABLE"
                assert plan_path.read_bytes() == original_bytes
            else:
                with pytest.raises(ExecutionUncertainError):
                    publisher.publish_candidate(source, candidate)
                # The port did attempt the reconciliation (it is not the pre-R25
                # behaviour of leaving the ambiguity unexamined) ...
                assert managed.publication_pending is True
                # ... and the writer is fenced behind it.
                assert managed.close() is False
                assert _status(site, workspace_id)["status"] == "OWNED"
                # No half-commit is ever claimed.
                assert plan_path.read_bytes() == original_bytes
        finally:
            stop.set()
            runner.join(timeout=5)
            assert not runner.is_alive()


def test_the_port_does_not_invent_a_saga_when_create_view_was_lost(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EDGE / E512 closure: lost CREATE_VIEW reply reconciles via exact id; unknown CREATE_VIEW stays fenced.

    Two real outcomes on ``CREATE_VIEW`` uncertainty:
    1. Only the reply was lost while the authority recorded the view under
       ``op-<create_request_id>``: ``BoundPlanPublisher`` replays that exact
       ``create_request_id`` once (never minting a second view), recovers the
       view handle, completes publication, and releases the workspace cleanly.
    2. ``CREATE_VIEW`` itself failed/unknown (so the exact-id replay also returns
       ``ExecutionUncertainError``): no second ``create_request_id`` is minted,
       the pending handle remains held, ``close()`` refuses, and the workspace
       stays ``OWNED`` (and quarantines on restart).
    """
    plan_path = site.source / PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(b"# Existing plan\n")
    original_bytes = plan_path.read_bytes()
    source = read_plan_snapshot(site.source, Path(PLAN_RELATIVE))
    candidate = snapshot_from_bytes("draft.md", b"# Repaired plan\n")
    service_path, yaml_path = _configs(tmp_path, _document(site))

    # --- 1. Lost CREATE_VIEW reply recovers cleanly via exact-id replay ---
    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        original = ExecutionClient.request
        create_ids: list[str] = []
        lost: set[str] = set()

        def losing_reply_once(self: Any, operation: Any, *, request_id: str, **kwargs: Any) -> Any:
            if operation is Operation.CREATE_VIEW:
                create_ids.append(request_id)
            answer = original(self, operation, request_id=request_id, **kwargs)
            if operation is Operation.CREATE_VIEW and not lost:
                lost.add(request_id)
                raise ExecutionUncertainError("op-" + request_id, code="EXECUTION_UNKNOWN")
            return answer

        monkeypatch.setattr(ExecutionClient, "request", losing_reply_once)
        try:
            run = _run(site.source)
            managed = managed_execution_for_run(run, config_path=yaml_path)
            assert managed is not None
            publisher = BoundPlanPublisher(managed, managed.binding)
            promoted = publisher.publish_candidate(source, candidate)
            assert promoted.sha256 == candidate.ref.sha256
            assert len(create_ids) == 2 and len(set(create_ids)) == 1
            assert plan_path.read_bytes() == candidate.utf8_bytes
            assert managed.publication_pending is False
            assert managed.close() is True
            assert _status(site, workspace_id)["status"] == "AVAILABLE"
        finally:
            monkeypatch.setattr(ExecutionClient, "request", original)
            stop.set()
            runner.join(timeout=5)
            assert not runner.is_alive()

    # Reset plan for arm 2 and prove unknown CREATE_VIEW fails closed without inventing a second view.
    with SupervisorService(read_config_file(service_path)) as service:
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        original = ExecutionClient.request
        create_ids_fail: list[str] = []

        def persistent_create_unknown(self: Any, operation: Any, *, request_id: str, **kwargs: Any) -> Any:
            if operation is Operation.CREATE_VIEW:
                create_ids_fail.append(request_id)
                raise ExecutionUncertainError("op-" + request_id, code="EXECUTION_UNKNOWN")
            return original(self, operation, request_id=request_id, **kwargs)

        monkeypatch.setattr(ExecutionClient, "request", persistent_create_unknown)
        try:
            source2 = read_plan_snapshot(site.source, Path(PLAN_RELATIVE))
            candidate2 = snapshot_from_bytes("draft.md", b"# Second candidate\n")
            run2 = RunContext("run-2", "session-1", site.source, site.source / ".db", site.source / "logs")
            managed2 = managed_execution_for_run(run2, config_path=yaml_path)
            assert managed2 is not None
            publisher2 = BoundPlanPublisher(managed2, managed2.binding)
            with pytest.raises(ExecutionUncertainError):
                publisher2.publish_candidate(source2, candidate2)
            assert len(create_ids_fail) == 2 and len(set(create_ids_fail)) == 1
            assert managed2.publication_pending is True
            assert managed2.close() is False
            assert _status(site, workspace_id)["status"] == "OWNED"
            assert plan_path.read_bytes() != candidate2.utf8_bytes
            assert plan_path.read_bytes() == candidate.utf8_bytes or plan_path.read_bytes() == original_bytes
        finally:
            monkeypatch.setattr(ExecutionClient, "request", original)
            stop.set()
            runner.join(timeout=5)
            assert not runner.is_alive()

    # Process death before reconciliation leaves the orphaned OWNED workspace QUARANTINED.
    with SupervisorService(read_config_file(service_path)):
        assert _status(site, workspace_id)["status"] == "QUARANTINED"


@pytest.mark.parametrize("lost_op", [Operation.WRITE_FILE, Operation.STOP_VIEW])
def test_bound_plan_publisher_reconciles_lost_write_and_stop_view_without_duplicate_view(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lost_op: Operation
) -> None:
    """E512: lost WRITE_FILE or STOP_VIEW reply recovers the same single CANDIDATE view and commits cleanly."""
    plan_path = site.source / PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(b"# Existing plan\n")
    source = read_plan_snapshot(site.source, Path(PLAN_RELATIVE))
    candidate = snapshot_from_bytes("draft.md", b"# Repaired plan\n")
    service_path, yaml_path = _configs(tmp_path, _document(site))

    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        original = ExecutionClient.request
        lost_ids: set[str] = set()
        create_ids: list[str] = []
        target_ids: list[str] = []

        def lose_once(self: Any, operation: Any, *, request_id: str, **kwargs: Any) -> Any:
            if operation is Operation.CREATE_VIEW:
                create_ids.append(request_id)
            if operation is lost_op:
                target_ids.append(request_id)
            answer = original(self, operation, request_id=request_id, **kwargs)
            if operation is lost_op and not lost_ids:
                lost_ids.add(request_id)
                raise ExecutionUncertainError("op-" + request_id, code="EXECUTION_UNKNOWN")
            return answer

        monkeypatch.setattr(ExecutionClient, "request", lose_once)
        with _serving_supervisor(service):
            managed = managed_execution_for_run(_run(site.source), config_path=yaml_path)
            assert managed is not None
            publisher = BoundPlanPublisher(managed, managed.binding)
            promoted = publisher.publish_candidate(source, candidate)
            assert promoted.sha256 == candidate.ref.sha256
            assert len(create_ids) == 1
            assert len(target_ids) == 2 and len(set(target_ids)) == 1
            assert managed.publication_pending is False
            assert managed.close() is True
            assert _status(site, workspace_id)["status"] == "AVAILABLE"


@pytest.mark.parametrize("saga", ["pending-publication", "orphaned-candidate-view"])
def test_a_second_run_on_a_workspace_the_first_left_unsettled_is_refused_not_stranded(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, saga: str
) -> None:
    """E509 step 6 — the cross-cutting oracle, as a *consequence* rather than a detail.

    Every other Q114 oracle asserts an inner fact (a flag, a code, one call count).
    This one asserts the thing an operator actually experiences: run A ends badly,
    and then run B arrives at the same workspace. There are exactly two acceptable
    endings - B works, or B is refused for a reason it can report. What must never
    happen is the third: B succeeds while A's private bytes are still stranded, so
    the workspace looks free, the buffer is unreachable forever, and nobody is told.

    Two shapes of "left unsettled", because they fail differently:

    * ``pending-publication`` — A owns a replayable saga whose outcome the journal
      can still prove (a lost *reply*), so A settles it and its writer goes back. B
      then succeeds; the workspace was never lost.
    * ``orphaned-candidate-view`` — A did not reconcile after a lost ``CREATE_VIEW``
      reply, so A holds the unresolved saga fence (``publication_pending is True``
      and ``close() is False``) and the workspace stays ``OWNED`` so B is refused
      with ``WORKSPACE_BUSY``. Once A calls ``reconcile_publication()`` with
      recovered transport, the exact ``create_request_id`` settles the same view,
      ``close()`` releases to ``AVAILABLE``, and a subsequent run succeeds cleanly.
    """
    plan_path = site.source / PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(b"# Existing plan\n")
    source = read_plan_snapshot(site.source, Path(PLAN_RELATIVE))
    candidate = snapshot_from_bytes("draft.md", b"# Repaired plan\n")
    service_path, yaml_path = _configs(tmp_path, _document(site))
    run = _run(site.source)

    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        seen: list[str] = []
        original_request = ExecutionClient.request
        lost_create: set[str] = set()
        lost_publish: set[str] = set()

        def losing_create(self: Any, operation: Any, *, request_id: str, **kwargs: Any) -> Any:
            answer = original_request(self, operation, request_id=request_id, **kwargs)
            if operation is Operation.CREATE_VIEW and not lost_create:
                lost_create.add(request_id)
                raise ExecutionUncertainError("op-" + request_id, code="EXECUTION_UNKNOWN")
            return answer

        def losing_publish(self: Any, operation: Any, *, request_id: str, **kwargs: Any) -> Any:
            # The commit happens; only the reply is lost, so the journal proves it.
            answer = original_request(self, operation, request_id=request_id, **kwargs)
            seen.append(request_id)
            if operation is Operation.PUBLISH and not lost_publish:
                lost_publish.add(request_id)
                raise ExecutionUncertainError("op-" + request_id, code="EXECUTION_UNKNOWN")
            return answer

        with _serving_supervisor(service):
            # --- run A -----------------------------------------------------------
            if saga == "orphaned-candidate-view":
                monkeypatch.setattr(ExecutionClient, "request", losing_create)
            else:
                monkeypatch.setattr(ExecutionClient, "request", losing_publish)
            first = managed_execution_for_run(run, config_path=yaml_path)
            assert first is not None
            with pytest.raises(ExecutionUncertainError):
                first.publish_plan(source, candidate)

            if saga == "pending-publication":
                # A can still settle what it owns: the authority answers the replay.
                assert first.publication_pending is True
                first.reconcile_publication()
                assert first.publication_pending is False
                assert first.close() is True
                expected_status = "AVAILABLE"
                second_must_work = True
            else:
                # Before A reconciles, the fence holds the workspace OWNED and B is refused.
                assert first.publication_pending is True
                assert first.close() is False
                expected_status = "OWNED"
                second_must_work = False
            assert _status(site, workspace_id)["status"] == expected_status

            # --- run B on the same workspace ------------------------------------
            if saga == "orphaned-candidate-view":
                monkeypatch.setattr(ExecutionClient, "request", original_request)
            second = managed_execution_for_run(_run(site.source), config_path=yaml_path)
            if second_must_work:
                assert second is not None
                assert second.binding.workspace_id == workspace_id
                assert second.close() is True
                assert _status(site, workspace_id)["status"] == "AVAILABLE"
            else:
                # The refusal is the answer: no half-acquired writer, no silent
                # takeover of the run that still owns the workspace.
                assert second is None
                assert _status(site, workspace_id)["status"] == "OWNED"
                # Reconciling A via its retained create_request_id now settles the
                # orphaned CANDIDATE view and releases the workspace cleanly.
                first.reconcile_publication()
                assert first.publication_pending is False
                assert first.close() is True
                assert _status(site, workspace_id)["status"] == "AVAILABLE"
                run3 = RunContext("run-3", "session-1", site.source, site.source / ".db", site.source / "logs")
                third = managed_execution_for_run(run3, config_path=yaml_path)
                assert third is not None and third.close() is True


def test_bound_plan_publisher_receipt_carries_real_operation_id(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D10/D11: BoundPlanPublisher.publish_candidate_receipt exposes revision_id and operation_id."""
    import re

    plan_path = site.source / PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(b"# Existing plan\n")
    source = read_plan_snapshot(site.source, Path(PLAN_RELATIVE))
    candidate = snapshot_from_bytes("draft.md", b"# Promoted plan\n")
    service_path, yaml_path = _configs(tmp_path, _document(site))
    run = _run(site.source)

    with SupervisorService(read_config_file(service_path)) as service:
        _registered(service)
        with _serving_supervisor(service):
            managed = managed_execution_for_run(run, config_path=yaml_path)
            assert managed is not None
            publisher = BoundPlanPublisher(managed, managed.binding)
            receipt = publisher.publish_candidate_receipt(source, candidate)
            assert isinstance(receipt, PlanPublication)
            assert receipt.plan_ref.sha256 == candidate.ref.sha256
            assert receipt.revision_id == managed.current_revision_id
            assert receipt.operation_id is not None
            assert re.fullmatch(r"op-[0-9a-f]{32}", receipt.operation_id) is not None
            assert managed.close() is True


def test_bound_plan_publisher_reconcile_preserves_operation_id(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reconciliation after a lost PUBLISH reply still surfaces the exact op-<32hex> receipt."""
    import re

    plan_path = site.source / PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(b"# Existing plan\n")
    source = read_plan_snapshot(site.source, Path(PLAN_RELATIVE))
    candidate = snapshot_from_bytes("draft.md", b"# Reconciled plan\n")
    service_path, yaml_path = _configs(tmp_path, _document(site))
    run = _run(site.source)

    with SupervisorService(read_config_file(service_path)) as service:
        _registered(service)
        original_request = ExecutionClient.request
        lost_publish: list[str] = []

        def lose_first_publish(self: Any, operation: Any, *, request_id: str, **kwargs: Any) -> Any:
            answer = original_request(self, operation, request_id=request_id, **kwargs)
            if operation is Operation.PUBLISH and not lost_publish:
                lost_publish.append(request_id)
                raise ExecutionUncertainError("op-" + request_id, code="EXECUTION_UNKNOWN")
            return answer

        with _serving_supervisor(service):
            monkeypatch.setattr(ExecutionClient, "request", lose_first_publish)
            managed = managed_execution_for_run(run, config_path=yaml_path)
            assert managed is not None
            publisher = BoundPlanPublisher(managed, managed.binding)
            receipt = publisher.publish_candidate_receipt(source, candidate)
            assert receipt.plan_ref.sha256 == candidate.ref.sha256
            assert receipt.operation_id == "op-" + lost_publish[0]
            assert re.fullmatch(r"op-[0-9a-f]{32}", receipt.operation_id or "") is not None
            assert managed.close() is True


def test_reconcile_publication_determinate_refusal_clears_pending_fence(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E512: a determinate ExecutionRejectedError during reconciliation clears publication_pending and releases."""
    import hashlib

    from fa.inner_loop.plan_admission import PlanSnapshot
    from fa.inner_loop.plan_ids import extract_plan_ids

    plan_path = site.source / PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(b"# Existing plan\n")
    source = read_plan_snapshot(site.source, Path(PLAN_RELATIVE))
    bad_bytes = b"   \n"
    bad_candidate = PlanSnapshot(
        ref=PlanRef(PLAN_RELATIVE, "draft", hashlib.sha256(bad_bytes).hexdigest()),
        utf8_bytes=bad_bytes,
        text="   \n",
        ids=extract_plan_ids(""),
    )
    service_path, yaml_path = _configs(tmp_path, _document(site))
    run = _run(site.source)

    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        original_request = ExecutionClient.request
        drop_next_stop = [True]

        def lose_first_stop(self: Any, operation: Any, *, request_id: str, **kwargs: Any) -> Any:
            answer = original_request(self, operation, request_id=request_id, **kwargs)
            if operation is Operation.STOP_VIEW and drop_next_stop[0]:
                drop_next_stop[0] = False
                raise ExecutionUncertainError("op-" + request_id, code="EXECUTION_UNKNOWN")
            return answer

        with _serving_supervisor(service):
            monkeypatch.setattr(ExecutionClient, "request", lose_first_stop)
            managed = managed_execution_for_run(run, config_path=yaml_path)
            assert managed is not None

            with pytest.raises(ExecutionUncertainError):
                managed.publish_plan(source, bad_candidate)
            assert managed.publication_pending is True

            # Reconciling replays STOP_VIEW -> PUBLISH, hits real authority INPUT_POLICY refusal,
            # settles the candidate view cleanly, clears the pending fence, and releases AVAILABLE.
            with pytest.raises(ExecutionRejectedError):
                managed.reconcile_publication()
            assert managed.publication_pending is False
            assert managed.close() is True
            assert _status(site, workspace_id)["status"] == "AVAILABLE"
