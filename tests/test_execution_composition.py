"""CT116: one composition supplies the managed execution, and nothing else does.

The tricky half is the negative space: an absent key, a foreign uid, a workspace
outside the approved roots and a refused writer must all end at ``None`` — the
controller then fails closed (CT115) instead of publishing over a host path.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import shlex
import socket
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
from fa.execution.cell_worker import serve_once
from fa.execution.client import (
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
    StagePublication,
)
from fa.execution.composition import (
    BoundPlanPublisher,
    ClientWorkspaceProvisioner,
    ExecutionBinding,
    ManagedExecution,
    PlanPublication,
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
        workspace_provisioner = None

        def create_or_attach_session(self, **_kwargs: Any) -> Any:
            lifecycle_calls.append("create_or_attach")
            raise AssertionError("host lifecycle ran without a managed provisioner")

    monkeypatch.setattr(cli, "_session_manager_for_args", lambda _args: _HostOnlyManager())

    with pytest.raises(SessionManagerError) as refused:
        cli._resolve_cli_run_context(argparse.Namespace(session_id="session-test", workspace=None, run_id=None))

    assert refused.value.code == "managed_execution_unavailable"
    assert lifecycle_calls == []


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
        log=SimpleNamespace(path=run.run_log_dir / "events.jsonl"),
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
        if self.parent_calls == 4:
            assert self.observed == [self.canonical_snapshot()], "canonical files changed before the edit call"
            assert not (self.workspace / "managed-chat-note.txt").exists()
            call = {
                "id": "managed-chat-edit",
                "type": "function",
                "function": {
                    "name": "fs_edit_file",
                    "arguments": json.dumps(
                        {
                            "path": "managed-chat-note.txt",
                            "old_string": "private until publish",
                            "new_string": "edited through admitted view",
                        }
                    ),
                },
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "managed-chat", []
        assert self.parent_calls == 5
        assert self.observed == [self.canonical_snapshot()], "canonical files changed while the chat stage was live"
        assert not (self.workspace / "managed-chat-note.txt").exists()
        return ResponseInfo("done", 1, 1, "stop"), logical_call_id or "managed-chat", []


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
    peer: Endpoint, tmp_path: Path, document: dict[str, Any]
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
        one_shot=True,
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
        worker_exit_codes.append(serve_once(cell_worker, MuxWorker(connection)))

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
            inspect_reply("exited"),
            inspect_reply("exited"),
        ]
    )
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
    """R13 EXEC oracle plus R15 production write/edit through the managed view before publication."""
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
        provider_oracle.provider_calls == 8 and provider_oracle.parent_calls == 5 and provider_oracle.child_calls == 3
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
    assert (workspace / "managed-chat-note.txt").read_text(encoding="utf-8") == "edited through admitted view"
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
    edit_result = next(
        row["content"] for row in rows if row["kind"] == "tool_result" and row["tool_call_id"] == "managed-chat-edit"
    )
    assert edit_result["ok"] is True
    assert edit_result["result"]["path"].endswith("managed-chat-note.txt")


def test_r12_production_managed_chat_never_uses_remote_runtime_when_server_unavailable(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    local_cell_peer: Endpoint,
) -> None:
    """Q113/R12: production chat fails at the managed supervisor without optional-runtime or host use."""
    import subprocess
    import sys

    import fa.inner_loop.tools.run_bash as run_bash_module
    import fa.runtime as public_runtime
    import fa.runtime.bash_executor as runtime_executor
    import fa.runtime.server as runtime_server
    from fa.feature_flags import FeatureFlags, FeatureFlagsLoadResult
    from fa.inner_loop.session_db import SessionDatabase
    from fa.providers import ProviderChain, SecretStore
    from fa.runtime.pty_pool import PtySession
    from fa.session.manager import SessionManager
    from fa.workspace_bootstrap import ReadyState, ReadyStatus

    # Force the optional boundary into its absent state, independent of whether
    # this test environment happens to have the deferred FastAPI extra installed.
    monkeypatch.setattr(public_runtime, "app", None)
    monkeypatch.setattr(runtime_server, "HAS_FASTAPI", False)
    monkeypatch.setattr(runtime_server, "app", None)
    monkeypatch.setattr(runtime_server, "pool", None)
    monkeypatch.setattr(runtime_server, "runtime_pool", None)

    remote_runtime_requests: list[str] = []

    class ForbiddenRemoteRuntimeExecutor:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            remote_runtime_requests.append("construct")
            raise AssertionError("production managed chat must not construct RemoteRuntimeExecutor")

        def run(self, *_args: Any, **_kwargs: Any) -> Any:
            remote_runtime_requests.append("run")
            raise AssertionError("production managed chat must not call RemoteRuntimeExecutor")

    monkeypatch.setattr(runtime_executor, "RemoteRuntimeExecutor", ForbiddenRemoteRuntimeExecutor)

    fastapi_server_starts: list[str] = []

    def forbidden_uvicorn_start(*_args: Any, **_kwargs: Any) -> None:
        fastapi_server_starts.append("uvicorn.run")
        raise AssertionError("fa run must not start the optional HTTP runtime")

    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=forbidden_uvicorn_start))

    host_fallbacks: list[str] = []
    host_pty_runs: list[str] = []

    def forbidden_fallback(*_args: Any, **_kwargs: Any) -> Any:
        host_fallbacks.append("run_bash._run_subprocess_fallback")
        raise AssertionError("managed execution refusal must not fall back to host subprocess")

    def forbidden_host_pty(_self: Any, *_args: Any, **_kwargs: Any) -> Any:
        host_pty_runs.append("PtySession.run")
        raise AssertionError("managed execution refusal must not run a host PTY command")

    monkeypatch.setattr(run_bash_module, "_run_subprocess_fallback", forbidden_fallback)
    monkeypatch.setattr(PtySession, "run", forbidden_host_pty)

    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(site.roots))
    monkeypatch.delenv("FA_SESSION_SOURCE", raising=False)
    monkeypatch.setattr(
        "fa.feature_flags.load_feature_flags_from_path",
        lambda: FeatureFlagsLoadResult(FeatureFlags(subagent_spawning_enabled=False, subagent_chat_enabled=False)),
    )

    source = tmp_path / "source-repo"
    source.mkdir()
    (source / "README.md").write_text("source note", encoding="utf-8")
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
    subprocess.run(["git", "-C", str(source), "add", "README.md", "models.yaml"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "seed workspace"], check=True)

    document = _document(site)
    document["approved_roots"] = {"projects": str(site.roots), "seed": str(source)}
    service_path, service_config = _configs(tmp_path, document)
    monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", service_config)
    provisioner = client_workspace_provisioner(config_path=service_config)

    def prepared(workspace_path: Path, _run_context: RunContext | None) -> ReadyState:
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
        workspace_provisioner=provisioner,
    )
    with SupervisorService(read_config_file(service_path)) as provisioning_service:
        with _serving_supervisor(provisioning_service):
            session = manager.create_or_attach_session(session_id=None, workspace_override=None)
            run = manager.begin_run(session, requested_run_id="r12-managed-chat")
            session_db = SessionDatabase.open_existing(session.session_db_path, session_id=session.session_id)
            workspace = session.workspace_path

    marker = workspace / "r12-host-fallback-marker.txt"
    command = f"printf r12-host-effect > {shlex.quote(str(marker))}"
    provider_calls: list[str] = []

    def provider_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        provider_calls.append("request")
        tool_names = {
            str(tool.get("function", {}).get("name", ""))
            for tool in request.tools
            if isinstance(tool.get("function"), dict)
        }
        if len(provider_calls) == 1:
            assert "pr_prepare" in tool_names
            call = {
                "id": "r12-prepare",
                "type": "function",
                "function": {"name": "pr_prepare", "arguments": json.dumps({"intent": "CHORE", "invariant": "n/a"})},
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "r12-chat", []
        if len(provider_calls) == 2:
            assert "fs_run_bash" in tool_names
            call = {
                "id": "r12-managed-bash",
                "type": "function",
                "function": {"name": "fs_run_bash", "arguments": json.dumps({"command": command})},
            }
            return ResponseInfo("", 1, 1, "tool_calls", (call,)), logical_call_id or "r12-chat", []
        assert len(provider_calls) == 3
        return ResponseInfo("managed refusal observed", 1, 1, "stop"), logical_call_id or "r12-chat", []

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    exec_requests: list[dict[str, Any]] = []
    exec_denials: list[str] = []
    proxy_credential_leaks: list[str] = []
    secret = "r12-private-secret-sentinel"
    with SupervisorService(read_config_file(service_path)) as service:
        assert service._backend is None
        original_exec = service._exec

        def counted_exec(peer: Any, request: dict[str, Any], deadline: float) -> Any:
            exec_requests.append(request)
            raw_request = json.dumps(request)
            if "X_FA_PROXY_TOKEN" in raw_request or secret in raw_request:
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
                    str(workspace / "models.yaml"),
                    "--workspace",
                    str(workspace),
                    "--run-id",
                    run.run_id,
                    "--max-turns",
                    "4",
                    "exercise optional runtime absence",
                ]
            )
            args._session_context, args._run_context, args._session_db = session, run, session_db
            assert cli._cmd_run(args, secrets=SecretStore({"K": secret})) == 0

    rows = session_db.read_event_rows(run_id=run.run_id)
    bash_result = next(
        row["content"]
        for row in rows
        if row["kind"] == "tool_result"
        and row["tool_name"] == "fs_run_bash"
        and row["tool_call_id"] == "r12-managed-bash"
    )
    assert bash_result["ok"] is False
    assert bash_result["error"]["code"] == "execution_unavailable"
    assert bash_result["error"]["retryable"] is False
    assert len(exec_requests) == 1 and exec_denials == ["BACKEND_UNAVAILABLE"]
    assert exec_requests[0]["op"] == "exec"
    assert exec_requests[0]["payload"]["command"] == command
    assert provider_calls == ["request", "request", "request"]

    counters = {
        "remote_runtime_requests": len(remote_runtime_requests),
        "fastapi_server_starts": len(fastapi_server_starts),
        "host_fallbacks": len(host_fallbacks),
        "host_pty_runs": len(host_pty_runs),
        "proxy_credentials": len(proxy_credential_leaks),
        "exec_requests": len(exec_requests),
        "exec_allowed": len(exec_requests) - len(exec_denials),
        "cell_launches": len(local_cell_peer.seen),
        "project_writes": int(marker.exists()),
    }
    assert counters == {
        "remote_runtime_requests": 0,
        "fastapi_server_starts": 0,
        "host_fallbacks": 0,
        "host_pty_runs": 0,
        "proxy_credentials": 0,
        "exec_requests": 1,
        "exec_allowed": 0,
        "cell_launches": 0,
        "project_writes": 0,
    }
    assert public_runtime.app is None
    assert runtime_server.app is None and runtime_server.pool is None and runtime_server.runtime_pool is None


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

    service._diff_revisions = counted  # type: ignore[method-assign]
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
    original_managed_for_run = cli.managed_execution_for_run

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


def test_failed_stage_stop_is_not_retried_by_cleanup(tmp_path: Path) -> None:
    """An unproved STOP_VIEW is one attempt, not an invitation to retry in cleanup."""
    from fa.execution.client import ExecutionClient
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

    managed = SimpleNamespace(
        view_profile=native_profile(),
        current_revision_id=revision_id,
        binding=ExecutionBinding(NamespaceRef("session-1", "stage-run"), workspace_id),
        client=ExecutionClient(tmp_path / "supervisor.sock", server_uid=os.getuid(), rpc_timeout_ms=100),
        open_view=lambda **_kwargs: view_grant,
        stop_view=stop_view,
    )

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


def test_the_writer_capability_lives_in_exactly_one_place() -> None:
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
        _ScriptedAuthority(lost=set(), answer_the_replay=True),
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


@pytest.mark.parametrize("role", ["chat", "coder", "planner", "eval"])
def test_r14_managed_profile_failure_never_reaches_host_tools(
    role: str,
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    local_cell_peer: Endpoint,
) -> None:
    """R14/Q113: actual fa run must refuse profile failure without host registry fallback."""
    import subprocess

    import fa.inner_loop.tools.run_bash as run_bash_module
    from fa.feature_flags import FeatureFlags, FeatureFlagsLoadResult
    from fa.inner_loop import profiles
    from fa.inner_loop.session_db import SessionDatabase
    from fa.providers import ProviderChain, SecretStore
    from fa.runtime.pty_pool import PtySession
    from fa.session.manager import SessionManager
    from fa.workspace_bootstrap import ReadyState, ReadyStatus

    host_fallbacks: list[str] = []
    host_pty_runs: list[str] = []

    def forbidden_fallback(command: str, *_args: Any, **_kwargs: Any) -> Any:
        host_fallbacks.append(command)
        raise AssertionError("managed registry failure must not run host subprocess")

    def forbidden_host_pty(_self: Any, command: str, *_args: Any, **_kwargs: Any) -> Any:
        host_pty_runs.append(command)
        raise AssertionError("managed registry failure must not run host PTY")

    monkeypatch.setattr(run_bash_module, "_run_subprocess_fallback", forbidden_fallback)
    monkeypatch.setattr(PtySession, "run", forbidden_host_pty)

    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(site.roots))
    monkeypatch.delenv("FA_SESSION_SOURCE", raising=False)
    monkeypatch.setattr(
        "fa.feature_flags.load_feature_flags_from_path",
        lambda: FeatureFlagsLoadResult(FeatureFlags(subagent_spawning_enabled=False, subagent_chat_enabled=False)),
    )

    source = tmp_path / "source-repo"
    source.mkdir()
    (source / "README.md").write_text("source note", encoding="utf-8")
    role_config = [
        '  name: "test-model"',
        '  family: "openai"',
        "  chain:",
        "    - provider: openrouter",
        '      model: "test/model"',
        '      base_url: "https://example.invalid/v1"',
        "      api_key_env: K",
    ]
    models_yaml = "\n".join(f"{name}:\n" + "\n".join(role_config) for name in ("chat", "coder", "planner", "eval"))
    (source / "models.yaml").write_text(models_yaml + "\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(source), "add", "README.md", "models.yaml"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "seed workspace"], check=True)

    document = _document(site)
    document["approved_roots"] = {"projects": str(site.roots), "seed": str(source)}
    service_path, service_config = _configs(tmp_path, document)
    monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", service_config)
    provisioner = client_workspace_provisioner(config_path=service_config)

    def prepared(workspace_path: Path, _run_context: RunContext | None) -> ReadyState:
        return ReadyState(ReadyStatus.READY, None, "ready_managed_artifact", workspace_path / "ready.log", False, 1)

    manager = SessionManager(
        state_root=state_root,
        workspace_root=site.roots,
        source_workspace=source,
        workspace_preparer=prepared,
        workspace_provisioner=provisioner,
    )
    with SupervisorService(read_config_file(service_path)) as provisioning_service:
        with _serving_supervisor(provisioning_service):
            session = manager.create_or_attach_session(session_id=None, workspace_override=None)
            run = manager.begin_run(session, requested_run_id=f"r14-{role}")
            session_db = SessionDatabase.open_existing(session.session_db_path, session_id=session.session_id)
            workspace = session.workspace_path

    marker = workspace / "r14-host-fallback-marker.txt"
    command = f"printf r14-host-effect > {shlex.quote(str(marker))}"
    profile_calls: list[dict[str, Any]] = []

    def broken_profile_builder(*_args: Any, **kwargs: Any) -> Any:
        profile_calls.append(kwargs)
        raise RuntimeError("r14 profile assembly failed")

    monkeypatch.setattr(profiles, "build_registry_for_role", broken_profile_builder)
    provider_calls: list[str] = []

    def provider_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        provider_calls.append("request")
        tool_names = {
            str(tool.get("function", {}).get("name", ""))
            for tool in request.tools
            if isinstance(tool.get("function"), dict)
        }
        if len(provider_calls) == 1:
            assert "pr_prepare" in tool_names
            return (
                ResponseInfo(
                    "",
                    1,
                    1,
                    "tool_calls",
                    (
                        {
                            "id": "r14-prepare",
                            "type": "function",
                            "function": {
                                "name": "pr_prepare",
                                "arguments": json.dumps({"intent": "CHORE", "invariant": "n/a"}),
                            },
                        },
                    ),
                ),
                logical_call_id or "r14-registry",
                [],
            )
        if len(provider_calls) == 2:
            assert "fs_run_bash" in tool_names
            return (
                ResponseInfo(
                    "",
                    1,
                    1,
                    "tool_calls",
                    (
                        {
                            "id": "r14-host-bash",
                            "type": "function",
                            "function": {"name": "fs_run_bash", "arguments": json.dumps({"command": command})},
                        },
                    ),
                ),
                logical_call_id or "r14-registry",
                [],
            )
        raise AssertionError("unexpected provider request after host fallback call")

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    exec_requests: list[dict[str, Any]] = []
    with SupervisorService(read_config_file(service_path)) as service:
        original_exec = service._exec

        def counted_exec(peer: Any, request: dict[str, Any], deadline: float) -> Any:
            exec_requests.append(request)
            return original_exec(peer, request, deadline)

        service._exec = counted_exec  # type: ignore[method-assign]
        with _serving_supervisor(service):
            args = cli.build_parser().parse_args(
                [
                    "run",
                    "--role",
                    role,
                    "--config",
                    str(workspace / "models.yaml"),
                    "--workspace",
                    str(workspace),
                    "--run-id",
                    run.run_id,
                    "--max-turns",
                    "3",
                    "exercise managed registry failure",
                ]
            )
            args._session_context, args._run_context, args._session_db = session, run, session_db
            with pytest.raises(RuntimeError, match="r14 profile assembly failed"):
                cli._cmd_run(args, secrets=SecretStore({"K": "r14-test-secret"}))

    assert len(profile_calls) == 1 and profile_calls[0].get("workspace_io") is not None
    assert provider_calls == []
    assert exec_requests == []
    assert host_fallbacks == [] and host_pty_runs == []
    assert local_cell_peer.seen == []
    assert not marker.exists()


def test_r01_wrapper_run_resolves_active_workspace_and_revalidates_session(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    local_cell_peer: Endpoint,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Q119-A: wrapper active path resolves by manifest, then attaches through lifecycle."""
    import subprocess

    import fa.inner_loop.tools.run_bash as run_bash_module
    from fa.feature_flags import FeatureFlags, FeatureFlagsLoadResult
    from fa.providers import ProviderChain, SecretStore
    from fa.runtime.pty_pool import PtySession
    from fa.session.manager import SessionManager
    from fa.workspace_bootstrap import ReadyState, ReadyStatus

    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(site.roots))
    monkeypatch.delenv("FA_SESSION_SOURCE", raising=False)
    monkeypatch.setattr(
        "fa.feature_flags.load_feature_flags_from_path",
        lambda: FeatureFlagsLoadResult(FeatureFlags(subagent_spawning_enabled=False, subagent_chat_enabled=False)),
    )

    source = tmp_path / "seed-repo"
    source.mkdir()
    (source / "README.md").write_text("seed for active session", encoding="utf-8")
    (source / "knowledge").mkdir()
    (source / "knowledge" / "llms.txt").write_text("# authoring marker\n", encoding="utf-8")
    (source / "docs").mkdir()
    (source / "docs" / "manifest.toml").write_text('[kernel]\nversion = "0.1"\n', encoding="utf-8")
    (source / "manifest.toml").write_text('[kernel]\nversion = "0.1"\n', encoding="utf-8")
    (source / "subproject" / "knowledge").mkdir(parents=True)
    (source / "subproject" / "knowledge" / "llms.txt").write_text("# subproject marker\n", encoding="utf-8")
    (source / "subproject" / "manifest.toml").write_text('[kernel]\nversion = "0.1"\n', encoding="utf-8")
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
        [
            "git",
            "-C",
            str(source),
            "add",
            "README.md",
            "models.yaml",
            "knowledge/llms.txt",
            "docs/manifest.toml",
            "manifest.toml",
            "subproject/knowledge/llms.txt",
            "subproject/manifest.toml",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "seed active workspace"], check=True)

    document = _document(site)
    document["approved_roots"] = {"projects": str(site.roots), "seed": str(source)}
    service_path, service_config = _configs(tmp_path, document)
    monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", service_config)
    provisioner = client_workspace_provisioner(config_path=service_config)
    assert provisioner is not None
    active_workspace = site.roots / "friendly-workspace-name"

    def prepared(workspace_path: Path, _run_context: RunContext | None) -> ReadyState:
        return ReadyState(
            ReadyStatus.READY,
            None,
            "ready_managed_artifact",
            workspace_path / "ready.log",
            False,
            1,
        )

    manager = SessionManager(
        state_root=state_root,
        workspace_root=site.roots,
        source_workspace=source,
        workspace_preparer=prepared,
        workspace_provisioner=provisioner,
    )
    with SupervisorService(read_config_file(service_path)) as provisioning_service:
        with _serving_supervisor(provisioning_service):
            session = manager.create_or_attach_session(session_id=None, workspace_override=active_workspace)
    assert session.workspace_path == active_workspace
    assert session.session_id != active_workspace.name  # never infer the ID from the path basename
    monkeypatch.setenv("FA_SESSION_SOURCE", str(source))
    monkeypatch.setenv("FA_WRAPPER_ACTIVE_WORKSPACE", str(active_workspace))
    monkeypatch.setattr(cli, "_prepare_managed_workspace", prepared)

    resolver_calls: list[tuple[Path, str]] = []
    original_resolve = SessionManager.resolve_active_session_for_workspace

    def recorded_resolve(self: SessionManager, workspace_path: Path | None) -> Any:
        result = original_resolve(self, workspace_path)
        resolver_calls.append((Path(workspace_path), result.session_id))
        return result

    monkeypatch.setattr(SessionManager, "resolve_active_session_for_workspace", recorded_resolve)
    attach_calls: list[tuple[str, Path | None]] = []
    original_attach = SessionManager._attach_session

    def recorded_attach(self: SessionManager, session_id: str, workspace_override: Path | None) -> Any:
        attach_calls.append((session_id, workspace_override))
        return original_attach(self, session_id, workspace_override)

    monkeypatch.setattr(SessionManager, "_attach_session", recorded_attach)
    run_contexts: list[RunContext] = []
    original_begin_run = SessionManager.begin_run

    def recorded_begin_run(self: SessionManager, session: Any, requested_run_id: str | None) -> RunContext:
        run = original_begin_run(self, session, requested_run_id)
        run_contexts.append(run)
        return run

    monkeypatch.setattr(SessionManager, "begin_run", recorded_begin_run)

    host_fallbacks: list[str] = []
    host_pty_runs: list[str] = []
    monkeypatch.setattr(
        run_bash_module,
        "_run_subprocess_fallback",
        lambda command, *_args, **_kwargs: host_fallbacks.append(command),
    )
    monkeypatch.setattr(
        PtySession,
        "run",
        lambda _self, command, *_args, **_kwargs: host_pty_runs.append(command),
    )
    provider_calls: list[str] = []

    def provider_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        provider_calls.append("request")
        names = {tool.get("function", {}).get("name") for tool in request.tools}
        assert "fs_run_bash" in names
        return ResponseInfo("active session selected", 1, 1, "stop"), logical_call_id or "r01-active", []

    monkeypatch.setattr(ProviderChain, "request", provider_request)
    exec_requests: list[dict[str, Any]] = []
    run_resolver_start = len(resolver_calls)
    with SupervisorService(read_config_file(service_path)) as service:
        original_exec = service._exec

        def counted_exec(peer: Any, request: dict[str, Any], deadline: float) -> Any:
            exec_requests.append(request)
            return original_exec(peer, request, deadline)

        service._exec = counted_exec  # type: ignore[method-assign]
        with _serving_supervisor(service):
            args = cli.build_parser().parse_args(
                ["run", "--config", "./models.yaml", "--max-turns", "2", "resolve the active session"]
            )
            assert args.workspace is None and args.session_id is None
            assert cli._cmd_run(args, secrets=SecretStore({"K": "r01-test-secret"})) == 0

            manifests_before_owner_reuse = sorted(manager.sessions_root.glob("*/manifest.json"))
            for explicit_workspace in (".", str(active_workspace)):
                explicit_run_args = cli.build_parser().parse_args(
                    [
                        "run",
                        "--workspace",
                        explicit_workspace,
                        "--config",
                        "./models.yaml",
                        "--max-turns",
                        "2",
                        "reuse the active owner",
                    ]
                )
                assert cli._cmd_run(explicit_run_args, secrets=SecretStore({"K": "r01-test-secret"})) == 0
                assert explicit_run_args.workspace == active_workspace
                assert explicit_run_args.session_id == session.session_id
            assert sorted(manager.sessions_root.glob("*/manifest.json")) == manifests_before_owner_reuse
            capsys.readouterr()  # isolate the following negative oracle's no-output assertion

            mismatched_id_args = cli.build_parser().parse_args(
                [
                    "run",
                    "--workspace",
                    ".",
                    "--session-id",
                    "explicit-other-session",
                    "--config",
                    "./models.yaml",
                    "--max-turns",
                    "2",
                    "preserve the explicit identity",
                ]
            )
            calls_before_mismatched_id = len(provider_calls)
            assert cli._cmd_run(mismatched_id_args, secrets=SecretStore({"K": "r01-test-secret"})) == 2
            mismatch_output = capsys.readouterr()
            assert "[workspace_session_mismatch]" in mismatch_output.err
            assert mismatched_id_args.session_id == "explicit-other-session"
            assert mismatch_output.out == ""
            assert len(provider_calls) == calls_before_mismatched_id
            assert sorted(manager.sessions_root.glob("*/manifest.json")) == manifests_before_owner_reuse

            nested_run_args = cli.build_parser().parse_args(
                [
                    "run",
                    "--workspace",
                    "nested-workspace",
                    "--config",
                    "./models.yaml",
                    "--max-turns",
                    "2",
                    "refuse overlapping workspace",
                ]
            )
            run_count_before_nested_refusal = len(run_contexts)
            provider_count_before_nested_refusal = len(provider_calls)
            assert cli._cmd_run(nested_run_args, secrets=SecretStore({"K": "r01-test-secret"})) == 2
            nested_output = capsys.readouterr()
            assert "[workspace_overlap]" in nested_output.err
            assert nested_output.out == ""
            assert len(run_contexts) == run_count_before_nested_refusal
            assert len(provider_calls) == provider_count_before_nested_refusal
            assert sorted(manager.sessions_root.glob("*/manifest.json")) == manifests_before_owner_reuse
            assert not (active_workspace / "nested-workspace").exists()

            sibling_workspace = site.roots / "new-sibling-workspace"
            sibling_run_args = cli.build_parser().parse_args(
                [
                    "run",
                    "--workspace",
                    "../new-sibling-workspace",
                    "--config",
                    "./models.yaml",
                    "--max-turns",
                    "2",
                    "create a disjoint workspace session",
                ]
            )
            assert cli._cmd_run(sibling_run_args, secrets=SecretStore({"K": "r01-test-secret"})) == 0
            assert sibling_run_args.workspace == sibling_workspace
            assert sibling_run_args.session_id is None
            assert run_contexts[-1].workspace_path == sibling_workspace
            assert run_contexts[-1].session_id != session.session_id

    run_resolver_end = len(resolver_calls)
    chunk_resolver_start = len(resolver_calls)
    chunk_args = cli.build_parser().parse_args(["chunk", "README.md"])
    assert chunk_args.func(chunk_args) == 0
    chunk_output = capsys.readouterr().out
    assert str(active_workspace / "README.md") in chunk_output

    workflow_calls: list[dict[str, Any]] = []

    def fake_run_workflow(**kwargs: Any) -> tuple[int, None]:
        workflow_calls.append(kwargs)
        return 0, None

    monkeypatch.setattr(cli, "run_workflow", fake_run_workflow)
    workflow_resolver_start = len(resolver_calls)
    workflow_attach_start = len(attach_calls)
    with SupervisorService(read_config_file(service_path)) as workflow_service:
        with _serving_supervisor(workflow_service):
            workflow_args = cli.build_parser().parse_args(
                [
                    "workflow",
                    "eval",
                    "review the active workspace",
                    "--config",
                    "./models.yaml",
                    "--run-id",
                    "r01-workflow-active",
                ]
            )
            assert workflow_args.workspace is None and workflow_args.session_id is None
            assert cli._cmd_workflow(workflow_args) == 0

    import fa.stats as stats_module

    stats_sources = [
        ("stats-session-a", tmp_path / "stats-a.db", site.roots / "stats-a", "stats-run-a"),
        ("stats-session-b", tmp_path / "stats-b.db", site.roots / "stats-b", "stats-run-b"),
    ]
    stats_filters: list[str | None] = []
    monkeypatch.setattr(
        cli,
        "_discover_stats_sources",
        lambda **kwargs: stats_filters.append(kwargs["selected_session_id"]) or stats_sources,
    )
    monkeypatch.setattr(stats_module, "parse_session_db", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(stats_module, "aggregate_sessions", lambda _sessions: {})
    monkeypatch.setattr(stats_module, "render_aggregate", lambda _sessions: None)
    dead_zone_workspaces: list[Path] = []
    monkeypatch.setattr(
        cli,
        "_render_dead_zones",
        lambda workspace, _sessions: dead_zone_workspaces.append(Path(workspace)),
    )
    stats_resolver_start = len(resolver_calls)
    for workspace_args, expected_workspace in (
        ([], active_workspace),
        (["--workspace", "reports"], active_workspace / "reports"),
    ):
        stats_args = cli.build_parser().parse_args(
            ["stats", "--session-id", "explicit-stats-session", "--dead-zones", *workspace_args]
        )
        assert stats_args.session_id == "explicit-stats-session"
        assert cli._cmd_stats(stats_args) == 0
        assert stats_args.workspace == expected_workspace

    source_read_count = len(stats_filters)
    escaped_stats_args = cli.build_parser().parse_args(
        ["stats", "--session-id", "explicit-stats-session", "--dead-zones", "--workspace", "../outside"]
    )
    assert cli._cmd_stats(escaped_stats_args) == 2
    escape_output = capsys.readouterr()
    assert "[workspace_escape]" in escape_output.err
    assert escape_output.out == ""
    assert len(stats_filters) == source_read_count
    assert dead_zone_workspaces == [active_workspace, active_workspace / "reports"]

    from types import SimpleNamespace

    authoring_calls: list[tuple[Path, Path | None]] = []
    authoring_resolver_start = len(resolver_calls)

    def fake_run_all(workspace: Path, *, manifest_path: Path | None, rules: Any) -> Any:
        authoring_calls.append((Path(workspace), manifest_path))
        return SimpleNamespace(exit_code=0)

    monkeypatch.setattr(cli, "run_all", fake_run_all)
    monkeypatch.setattr(cli, "render_text", lambda _report: "authoring ok")
    for argv, expected_workspace, expected_manifest in (
        (
            ["authoring-check", "--manifest", "docs/manifest.toml"],
            active_workspace,
            active_workspace / "docs" / "manifest.toml",
        ),
        (
            ["authoring-check", "--workspace", "subproject", "--manifest", "manifest.toml"],
            active_workspace / "subproject",
            active_workspace / "manifest.toml",
        ),
    ):
        authoring_args = cli.build_parser().parse_args(argv)
        assert cli._cmd_authoring_check(authoring_args) == 0
        assert authoring_args.workspace == expected_workspace
        assert authoring_args.manifest == expected_manifest

    authoring_call_count = len(authoring_calls)
    escaped_authoring_args = cli.build_parser().parse_args(["authoring-check", "--manifest", "../outside.toml"])
    assert cli._cmd_authoring_check(escaped_authoring_args) == 2
    authoring_error = capsys.readouterr()
    assert "[workspace_escape]" in authoring_error.err
    assert authoring_error.out.count("authoring ok") == 2
    assert len(authoring_calls) == authoring_call_count == 2

    config_resolver_start = len(resolver_calls)
    config_captures: list[tuple[str, Path]] = []
    config_commands = (
        ("inject", "_cmd_inject"),
        ("selfcheck", "_cmd_selfcheck"),
        ("routing-check", "_cmd_routing_check"),
        ("probe", "_cmd_probe"),
        ("conformance", "_cmd_conformance"),
    )
    for config_command, function_name in config_commands:
        command_capture: list[Path] = []
        monkeypatch.setattr(
            cli,
            function_name,
            lambda command_args, captures=command_capture: captures.append(command_args.config) or 0,
        )
        monkeypatch.setattr(cli.sys, "argv", ["fa", config_command, "--config", "configs/models.yaml"])
        with pytest.raises(SystemExit) as exit_info:
            cli.main()
        assert exit_info.value.code == 0
        expected_config = active_workspace / "configs" / "models.yaml"
        assert command_capture == [expected_config]
        config_captures.append((config_command, command_capture[0]))

    assert args.workspace == active_workspace
    assert args.session_id == session.session_id
    assert args.config == active_workspace / "models.yaml"
    assert resolver_calls[run_resolver_start:run_resolver_end] == [(active_workspace, session.session_id)] * 9
    assert resolver_calls[chunk_resolver_start:workflow_resolver_start] == [(active_workspace, session.session_id)]
    assert resolver_calls[workflow_resolver_start:stats_resolver_start] == [(active_workspace, session.session_id)]
    assert resolver_calls[stats_resolver_start:authoring_resolver_start] == [
        (active_workspace, session.session_id),
        (active_workspace, session.session_id),
        (active_workspace, session.session_id),
    ]
    assert resolver_calls[authoring_resolver_start:config_resolver_start] == [
        (active_workspace, session.session_id),
        (active_workspace, session.session_id),
        (active_workspace, session.session_id),
    ]
    assert resolver_calls[config_resolver_start:] == [
        (active_workspace, session.session_id),
        (active_workspace, session.session_id),
        (active_workspace, session.session_id),
        (active_workspace, session.session_id),
        (active_workspace, session.session_id),
    ]
    assert config_captures == [
        (command, active_workspace / "configs" / "models.yaml") for command, _func in config_commands
    ]
    assert authoring_calls == [
        (active_workspace, active_workspace / "docs" / "manifest.toml"),
        (active_workspace / "subproject", active_workspace / "manifest.toml"),
    ]
    assert stats_filters == ["explicit-stats-session", "explicit-stats-session"]
    assert dead_zone_workspaces == [active_workspace, active_workspace / "reports"]
    assert attach_calls[:1] == [(session.session_id, active_workspace)]
    assert attach_calls[workflow_attach_start:] == [(session.session_id, active_workspace)]
    assert run_contexts[0].session_id == session.session_id
    assert run_contexts[0].workspace_path == active_workspace
    assert all(run.session_id == session.session_id for run in run_contexts[:6])
    sibling_contexts = [run for run in run_contexts if run.workspace_path == sibling_workspace]
    assert len(sibling_contexts) == 2  # attach readiness and the admitted run each bind once
    assert all(run.session_id != session.session_id for run in sibling_contexts)
    assert workflow_args.workspace == active_workspace
    assert workflow_args.session_id == session.session_id
    assert workflow_args.config == active_workspace / "models.yaml"
    assert len(workflow_calls) == 1
    assert workflow_calls[0]["workspace"] == active_workspace
    assert workflow_calls[0]["session_context"].session_id == session.session_id
    assert workflow_calls[0]["run_context"].workspace_path == active_workspace
    assert run_contexts[-1].session_id == session.session_id
    assert run_contexts[-1].workspace_path == active_workspace
    assert provider_calls == ["request"] * 4
    assert host_fallbacks == [] and host_pty_runs == []
    assert not local_cell_peer.seen
    assert not (active_workspace / "r01-host-effect").exists()
    assert not (active_workspace / ".fa" / "smoke").exists()


@pytest.mark.parametrize(
    ("active_value", "error_code"),
    [("relative-active-workspace", "workspace_invalid"), ("unowned-active-path", "workspace_missing")],
)
def test_r01_wrapper_run_rejects_unowned_active_workspace_before_lifecycle_effects(
    active_value: str,
    error_code: str,
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from fa.providers import ProviderChain, SecretStore

    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(site.roots))
    active_workspace = active_value if active_value == "relative-active-workspace" else str(site.roots / active_value)
    monkeypatch.setenv("FA_WRAPPER_ACTIVE_WORKSPACE", active_workspace)
    monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", tmp_path / "missing-config.yaml")
    provider_calls: list[str] = []
    monkeypatch.setattr(
        ProviderChain,
        "request",
        lambda *_args, **_kwargs: provider_calls.append("request"),
    )
    args = cli.build_parser().parse_args(["run", "task"])

    assert cli._cmd_run(args, secrets=SecretStore({})) == 2
    assert f"[{error_code}]" in capsys.readouterr().err
    assert provider_calls == []
    assert not state_root.exists()


@pytest.mark.parametrize(
    ("active_value", "error_code"),
    [("relative-active-workspace", "workspace_invalid"), ("unowned-active-path", "workspace_missing")],
)
def test_r01_wrapper_chunk_rejects_invalid_active_workspace_before_read(
    active_value: str,
    error_code: str,
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(site.roots))
    monkeypatch.delenv("FA_SESSION_SOURCE", raising=False)
    active_workspace = active_value if active_value == "relative-active-workspace" else str(site.roots / active_value)
    monkeypatch.setenv("FA_WRAPPER_ACTIVE_WORKSPACE", active_workspace)
    monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", tmp_path / "missing-config.yaml")
    args = cli.build_parser().parse_args(["chunk", "pyproject.toml"])

    assert Path("pyproject.toml").is_file()
    assert args.func(args) == 2
    output = capsys.readouterr()
    assert f"[{error_code}]" in output.err
    assert output.out == ""
    assert not state_root.exists()


@pytest.mark.parametrize(
    ("selection", "error_code"),
    [
        ("wrapper-active", "smoke_active_workspace_refused"),
        ("managed-root", "smoke_managed_workspace_refused"),
        ("source-root", "smoke_managed_workspace_refused"),
        ("relative", "smoke_workspace_invalid"),
    ],
)
def test_inner_loop_smoke_refuses_non_disposable_workspace_before_effects(
    selection: str,
    error_code: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from fa import cli

    managed_root = tmp_path / "managed-workspaces"
    managed_root.mkdir()
    disposable_workspace = tmp_path / "disposable"
    disposable_workspace.mkdir()
    managed_workspace = managed_root / "session-123"
    managed_workspace.mkdir()
    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(managed_root))
    monkeypatch.delenv("FA_SESSION_SOURCE", raising=False)

    if selection == "wrapper-active":
        monkeypatch.setenv("FA_WRAPPER_ACTIVE_WORKSPACE", str(managed_workspace))
        workspace_arg = str(disposable_workspace)
        target_workspace = disposable_workspace
    elif selection == "managed-root":
        monkeypatch.delenv("FA_WRAPPER_ACTIVE_WORKSPACE", raising=False)
        workspace_arg = str(managed_workspace)
        target_workspace = managed_workspace
    elif selection == "source-root":
        monkeypatch.delenv("FA_WRAPPER_ACTIVE_WORKSPACE", raising=False)
        source_workspace = tmp_path / "canonical-source"
        source_workspace.mkdir()
        monkeypatch.setenv("FA_SESSION_SOURCE", str(source_workspace))
        workspace_arg = str(source_workspace)
        target_workspace = source_workspace
    else:
        monkeypatch.delenv("FA_WRAPPER_ACTIVE_WORKSPACE", raising=False)
        workspace_arg = "relative-disposable"
        target_workspace = None

    args = cli.build_parser().parse_args(["inner-loop-smoke", "--workspace", workspace_arg])

    assert cli._cmd_inner_loop_smoke(args) == 2
    output = capsys.readouterr()
    assert f"[{error_code}]" in output.err
    assert output.out == ""
    assert not state_root.exists()
    assert target_workspace is None or not (target_workspace / ".fa" / "smoke").exists()
    assert target_workspace is None or not (target_workspace / "knowledge" / "trace").exists()


@pytest.mark.parametrize(
    ("active_value", "error_code"),
    [("relative-active-workspace", "workspace_invalid"), ("unowned-active-path", "workspace_missing")],
)
def test_r01_wrapper_workflow_rejects_invalid_active_workspace_before_preflight(
    active_value: str,
    error_code: str,
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(site.roots))
    monkeypatch.delenv("FA_SESSION_SOURCE", raising=False)
    active_workspace = active_value if active_value == "relative-active-workspace" else str(site.roots / active_value)
    monkeypatch.setenv("FA_WRAPPER_ACTIVE_WORKSPACE", active_workspace)
    monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", tmp_path / "missing-config.yaml")
    workflow_calls: list[str] = []
    monkeypatch.setattr(cli, "run_workflow", lambda **_kwargs: workflow_calls.append("run"))
    args = cli.build_parser().parse_args(["workflow", "coder", "review active workspace", "--plan", "plans/missing.md"])

    assert cli._cmd_workflow(args) == 2
    output = capsys.readouterr()
    assert f"active workspace selection failed [{error_code}]" in output.err
    assert output.out == ""
    assert workflow_calls == []
    assert not state_root.exists()


@pytest.mark.parametrize(
    ("active_value", "error_code"),
    [("relative-active-workspace", "workspace_invalid"), ("unowned-active-path", "workspace_missing")],
)
def test_r01_wrapper_stats_rejects_invalid_active_workspace_before_source_reads(
    active_value: str,
    error_code: str,
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(site.roots))
    monkeypatch.delenv("FA_SESSION_SOURCE", raising=False)
    active_workspace = active_value if active_value == "relative-active-workspace" else str(site.roots / active_value)
    monkeypatch.setenv("FA_WRAPPER_ACTIVE_WORKSPACE", active_workspace)
    source_reads: list[str] = []
    monkeypatch.setattr(cli, "_discover_stats_sources", lambda **_kwargs: source_reads.append("read"))
    args = cli.build_parser().parse_args(["stats", "--dead-zones"])

    assert cli._cmd_stats(args) == 2
    output = capsys.readouterr()
    assert f"active workspace selection failed [{error_code}]" in output.err
    assert output.out == ""
    assert source_reads == []
    assert not state_root.exists()


@pytest.mark.parametrize(
    ("active_value", "error_code"),
    [("relative-active-workspace", "workspace_invalid"), ("unowned-active-path", "workspace_missing")],
)
def test_r01_wrapper_authoring_check_rejects_invalid_active_workspace_before_check(
    active_value: str,
    error_code: str,
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(site.roots))
    monkeypatch.delenv("FA_SESSION_SOURCE", raising=False)
    active_workspace = active_value if active_value == "relative-active-workspace" else str(site.roots / active_value)
    monkeypatch.setenv("FA_WRAPPER_ACTIVE_WORKSPACE", active_workspace)
    check_calls: list[str] = []
    monkeypatch.setattr(cli, "run_all", lambda *_args, **_kwargs: check_calls.append("check"))
    args = cli.build_parser().parse_args(["authoring-check", "--manifest", "manifest.toml"])

    assert cli._cmd_authoring_check(args) == 2
    output = capsys.readouterr()
    assert f"active workspace selection failed [{error_code}]" in output.err
    assert output.out == ""
    assert check_calls == []
    assert not state_root.exists()


@pytest.mark.parametrize(
    ("active_value", "error_code"),
    [("relative-active-workspace", "workspace_invalid"), ("unowned-active-path", "workspace_missing")],
)
def test_r01_wrapper_config_command_rejects_invalid_active_before_dispatch(
    active_value: str,
    error_code: str,
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(site.roots))
    monkeypatch.delenv("FA_SESSION_SOURCE", raising=False)
    active_workspace = active_value if active_value == "relative-active-workspace" else str(site.roots / active_value)
    monkeypatch.setenv("FA_WRAPPER_ACTIVE_WORKSPACE", active_workspace)
    command_calls: list[str] = []
    monkeypatch.setattr(cli, "_cmd_inject", lambda _args: command_calls.append("inject") or 0)
    monkeypatch.setattr(cli.sys, "argv", ["fa", "inject", "--config", "models.yaml"])

    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    output = capsys.readouterr()
    assert exit_info.value.code == 2
    assert f"active workspace selection failed [{error_code}]" in output.err
    assert output.out == ""
    assert command_calls == []
    assert not state_root.exists()
