"""Parent stage lease composition over the real managed writer and supervisor."""

from __future__ import annotations

import argparse
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from fa import cli
from fa.cli import _drive_stage_with_managed_workspace
from fa.execution.client import (
    ExecutionClient,
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
)
from fa.execution.composition import ManagedExecution
from fa.execution.tool_port import ClientWorkspacePort
from fa.execution.types import Access, ExecutionContractError, GrantReply, NamespaceRef, Operation, ViewPurpose, ViewRef
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.runtime_limits import RuntimeLimits
from fa.inner_loop.session_db import SessionDatabase
from fa.inner_loop.state import EventLog
from fa.inner_loop.tools.workspace_port import WorkspacePortError
from tests.test_execution_client_port import _served
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site


@pytest.fixture
def lease_site(request: pytest.FixtureRequest) -> Site:
    """Reuse the canonical workspace fixture's byte layout for this bank."""
    return cast(Site, request.getfixturevalue("site"))


class _RecordingClient(ExecutionClient):
    """Real supervisor client with an observable list of attempted wire operations."""

    def __init__(self, source: ExecutionClient) -> None:
        super().__init__(source._path, server_uid=source._server_uid, rpc_timeout_ms=source._timeout_ms)
        self.sent: list[Operation] = []

    def request(self, operation: Operation, **kwargs: Any) -> dict[str, Any]:
        self.sent.append(operation)
        return super().request(operation, **kwargs)


class _ReleaseRefusingClient(_RecordingClient):
    """Inject one authoritative RELEASE refusal while forwarding all stage RPCs."""

    def request(self, operation: Operation, **kwargs: Any) -> dict[str, Any]:
        if operation is Operation.RELEASE:
            self.sent.append(operation)
            raise ExecutionUnavailableError
        return super().request(operation, **kwargs)


def _drive_lease(
    *, workspace_site: Site, tmp_path: Path, managed: ManagedExecution, monkeypatch: pytest.MonkeyPatch
) -> tuple[SessionOutcome, bool, list[Any], _RecordingClient]:
    """Exercise the production stage driver and one child ownership interval."""
    recording = _RecordingClient(managed.client)
    managed.client = recording
    captured: list[Any] = []
    workspace = workspace_site.source
    monkeypatch.setattr(cli, "managed_execution_for_run", lambda _run_context: managed)

    def build_registry(workspace_io: Any, managed_executor: Any, stage_lease: Any) -> ToolRegistry:
        assert isinstance(stage_lease, cli._ManagedStageLease)
        assert stage_lease.is_handoff_enabled
        provider = cli._make_workflow_ctx_provider(
            parent_run_id=managed.binding.namespace.run_id,
            config=workspace_site.source / "models.yaml",
            workspace=workspace_site.source,
            max_turns=1,
            limits=RuntimeLimits(),
            session_context=None,
            run_context=None,
            session_db=None,
            transport=None,
            secrets={},
            parent_stage_lease=stage_lease,
        )
        direct_context = provider()
        assert direct_context.managed_execution is managed
        assert direct_context.parent_stage_lease is stage_lease
        stage_lease.allow_nested_handoff = False
        legacy_context = provider()
        assert legacy_context.managed_execution is None
        assert legacy_context.parent_stage_lease is None
        stage_lease.allow_nested_handoff = True
        captured.extend([workspace_io, managed_executor, stage_lease])
        return ToolRegistry()

    def drive(_registry: ToolRegistry) -> SessionOutcome:
        parent_port, parent_executor, lease = captured
        assert lease is not None
        original_view = parent_port._view
        original_grant = parent_port._grant
        assert original_view is not None and original_grant is not None
        parent_port.write_file("stage-lease-parent.txt", "parent-before-child")
        deadline = time.monotonic() + 300
        parent_revision = lease.suspend(deadline=deadline)
        assert parent_revision == managed.current_revision_id
        assert lease.state == "suspended"

        sent_before_stale_calls = list(recording.sent)
        with pytest.raises(WorkspacePortError, match="unavailable"):
            parent_port.read_file("stage-lease-parent.txt")
        with pytest.raises(ExecutionUnavailableError):
            parent_executor.list_sessions()
        assert recording.sent == sent_before_stale_calls, "suspended bindings must fail before RPC"

        # Adversarial rebind attempts exercise the actual adapter guards while
        # the writer is paused; each refusal must leave both old objects inert.
        other_namespace = NamespaceRef(managed.binding.namespace.session_id, "foreign-parent")
        wrong_workspace_view = replace(original_view, workspace_id="ws-" + "f" * 32)
        wrong_owner_view = replace(original_view, owner_run_id="foreign-owner")
        wrong_purpose_view = replace(original_view, purpose=ViewPurpose.MUTATION)
        wrong_id_view = replace(original_view, view_id="view-" + "e" * 32)
        read_view = replace(original_view, access=Access.READ)

        def matching_grant(view: ViewRef, operation: Operation = Operation.CREATE_VIEW) -> GrantReply:
            return GrantReply(
                operation,
                "c" * 64,
                view,
                None,
                None,
                "d" * 64 if operation is Operation.CREATE_VIEW else None,
            )

        refused_port_rebinds = (
            (other_namespace, original_view, original_grant),
            (lease.namespace, wrong_id_view, original_grant),
            (lease.namespace, wrong_workspace_view, matching_grant(wrong_workspace_view)),
            (lease.namespace, wrong_owner_view, matching_grant(wrong_owner_view)),
            (lease.namespace, wrong_purpose_view, matching_grant(wrong_purpose_view)),
            (lease.namespace, read_view, matching_grant(read_view, Operation.PIN_READER)),
        )
        for namespace, view, grant in refused_port_rebinds:
            with pytest.raises(ExecutionContractError):
                parent_port.rebind(namespace=namespace, view=view, grant=grant)
            with pytest.raises(WorkspacePortError, match="unavailable"):
                parent_port.read_file("must-remain-suspended.txt")
            assert recording.sent == sent_before_stale_calls

        wrong_revision_view = replace(original_view, base_revision="rev-" + "a" * 32)
        wrong_revision_grant = matching_grant(wrong_revision_view)
        for namespace, view, grant, original_revision in (
            (other_namespace, original_view, original_grant, original_view.base_revision),
            (lease.namespace, wrong_id_view, original_grant, original_view.base_revision),
            (lease.namespace, original_view, matching_grant(original_view), "rev-" + "b" * 32),
        ):
            if grant is original_grant:
                # A valid original CREATE_VIEW proof is no longer current once
                # the parent lease has published and surrendered this view.
                grant = wrong_revision_grant
            with pytest.raises(ExecutionContractError):
                parent_executor.rebind(
                    namespace=namespace,
                    view=view,
                    grant=grant,
                    original_revision_id=original_revision,
                )
            with pytest.raises(ExecutionUnavailableError):
                parent_executor.list_sessions()
            assert recording.sent == sent_before_stale_calls
        no_tree_hash_grant = GrantReply(Operation.CREATE_VIEW, "e" * 64, original_view, None, None)
        with pytest.raises(ExecutionContractError):
            parent_executor.rebind(
                namespace=lease.namespace,
                view=original_view,
                grant=no_tree_hash_grant,
                original_revision_id=original_view.base_revision,
            )
        with pytest.raises(ExecutionUnavailableError):
            parent_executor.list_sessions()
        assert recording.sent == sent_before_stale_calls

        child_namespace = NamespaceRef(
            managed.binding.namespace.session_id, "child-stage", parent_run_id=managed.binding.namespace.run_id
        )
        managed.handoff_to(child_namespace, deadline=deadline)
        child_grant = managed.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.PROJECT,
            base_revision=managed.current_revision_id,
            deadline=deadline,
        )
        assert child_grant.view_ref is not None
        child_port = ClientWorkspacePort(
            managed.client,
            namespace=child_namespace,
            view=child_grant.view_ref,
            grant=child_grant,
        )
        child_port.write_file("stage-lease-child.txt", "published-by-child")
        managed.publish_stage(child_grant, deadline=deadline)
        managed.handoff_to(lease.namespace, deadline=deadline)

        lease.resume(deadline=deadline)
        assert lease.state == "active"
        assert captured[0] is parent_port and captured[1] is parent_executor
        assert parent_port.read_file("stage-lease-child.txt").content == "published-by-child"
        assert Operation.READ_FILE in recording.sent
        # The same executor now sends through its newly rebound view. The host
        # backend may reject PTY listing in this test environment; the boundary
        # oracle is that it gets past the local suspended guard and reaches RPC.
        try:
            parent_executor.list_sessions()
        except (ExecutionRejectedError, ExecutionUnavailableError, ExecutionUncertainError, ExecutionContractError):
            pass
        assert recording.sent[-1] is Operation.PTY_CONTROL
        return SessionOutcome(0, "iteration_cap", 1, "")

    outcome, release_confirmed = cli._run_cli_stage(
        args=argparse.Namespace(),
        run_context=None,
        run_id=managed.binding.namespace.run_id,
        run_log_dir=tmp_path / "run-log",
        session_db=None,
        log=cast(EventLog, SimpleNamespace(path=tmp_path / "events.jsonl")),
        workspace=workspace,
        role="chat",
        plan_ref=None,
        build_registry=build_registry,
        drive=drive,
    )
    assert outcome is not None
    return outcome, release_confirmed, captured, recording


def test_managed_parent_lease_settles_handoffs_and_rebinds_same_stage_objects(
    lease_site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1/C3: child commit is visible after parent rebind; stale capabilities stay inert."""
    with _served(lease_site, tmp_path) as managed:
        outcome, release_confirmed, captured, recording = _drive_lease(
            workspace_site=lease_site, tmp_path=tmp_path, managed=managed, monkeypatch=monkeypatch
        )

    assert outcome.exit_code == 0
    assert release_confirmed
    assert len(captured) == 3
    assert captured[2].state == "closed"
    assert captured[2].writer_release_safe
    assert (lease_site.source / "stage-lease-parent.txt").read_text(encoding="utf-8") == "parent-before-child"
    assert (lease_site.source / "stage-lease-child.txt").read_text(encoding="utf-8") == "published-by-child"
    assert recording.sent.count(Operation.PUBLISH) == 3
    assert recording.sent.count(Operation.HANDOFF) == 2


def test_workflow_owned_writer_is_not_released_by_parent_stage(
    lease_site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A controller-owned writer survives a stage; this stage must not RELEASE it."""
    with _served(lease_site, tmp_path) as managed:
        recording = _RecordingClient(managed.client)
        managed.client = recording
        args = argparse.Namespace(_managed_execution=managed)

        def unexpected_acquire(_run_context: Any) -> Any:
            raise AssertionError("a workflow stage must reuse its existing writer")

        monkeypatch.setattr(cli, "managed_execution_for_run", unexpected_acquire)

        def build_registry(workspace_io: Any, managed_executor: Any, lease: Any) -> ToolRegistry:
            assert isinstance(workspace_io, ClientWorkspacePort)
            assert managed_executor is not None
            assert isinstance(lease, cli._ManagedStageLease)
            assert not lease.is_handoff_enabled
            return ToolRegistry()

        outcome, release_confirmed = cli._run_cli_stage(
            args=args,
            run_context=None,
            run_id=managed.binding.namespace.run_id,
            run_log_dir=tmp_path / "run-log",
            session_db=None,
            log=cast(EventLog, SimpleNamespace(path=tmp_path / "events.jsonl")),
            workspace=lease_site.source,
            role="coder",
            plan_ref=None,
            build_registry=build_registry,
            drive=lambda _registry: SessionOutcome(0, "iteration_cap", 1, ""),
        )

        assert outcome is not None and outcome.exit_code == 0
        assert release_confirmed
        assert recording.sent.count(Operation.CREATE_VIEW) == 1
        assert recording.sent.count(Operation.PUBLISH) == 1
        assert recording.sent.count(Operation.RELEASE) == 0


def test_direct_run_records_unconfirmed_release_after_settling_view(
    lease_site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A settled stage still records one refused writer release in the run authority."""
    with _served(lease_site, tmp_path) as managed:
        recording = _ReleaseRefusingClient(managed.client)
        managed.client = recording
        monkeypatch.setattr(cli, "managed_execution_for_run", lambda _run_context: managed)
        session_db = SessionDatabase(tmp_path / "session.db", session_id=managed.binding.namespace.session_id)

        def build_registry(_workspace_io: Any, _managed_executor: Any, lease: Any) -> ToolRegistry:
            assert isinstance(lease, cli._ManagedStageLease)
            return ToolRegistry()

        outcome, release_confirmed = cli._run_cli_stage(
            args=argparse.Namespace(),
            run_context=None,
            run_id=managed.binding.namespace.run_id,
            run_log_dir=tmp_path / "run-log",
            session_db=session_db,
            log=cast(EventLog, SimpleNamespace(path=tmp_path / "events.jsonl")),
            workspace=lease_site.source,
            role="chat",
            plan_ref=None,
            build_registry=build_registry,
            drive=lambda _registry: SessionOutcome(0, "iteration_cap", 1, ""),
        )

        assert outcome is not None and outcome.exit_code == 0
        assert not release_confirmed
        assert recording.sent.count(Operation.RELEASE) == 1
        row = session_db.get_meta("managed_execution_release")
        assert row == {
            "confirmed": False,
            "run_id": managed.binding.namespace.run_id,
            "workspace_id": managed.binding.workspace_id,
            "exit_code": cli.WORKFLOW_RELEASE_EXIT_CODE,
        }
        assert "fa run: writer release for workspace " + managed.binding.workspace_id in capsys.readouterr().err
        assert cli._run_exit_code(outcome, release_confirmed=release_confirmed) == cli.WORKFLOW_RELEASE_EXIT_CODE


def test_parent_lease_cannot_resume_after_uncertain_suspend(
    lease_site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Q114-A: uncertain parent publication breaks the lease; no stale-view retry."""
    with _served(lease_site, tmp_path) as managed:
        recording = _RecordingClient(managed.client)
        managed.client = recording
        args = argparse.Namespace(_managed_execution=managed)
        captured: list[Any] = []

        def build_registry(workspace_io: Any, managed_executor: Any, lease: Any) -> ToolRegistry:
            captured.extend([workspace_io, managed_executor, lease])
            return ToolRegistry()

        def drive(_registry: ToolRegistry) -> SessionOutcome:
            workspace_io, managed_executor, lease = captured
            before = list(recording.sent)
            before_revision = managed.current_revision_id

            def uncertain_publish(_grant: GrantReply, *, deadline: float | None = None) -> None:
                raise ExecutionUncertainError("op-" + "f" * 32)

            monkeypatch.setattr(managed, "publish_stage", uncertain_publish)
            with pytest.raises(ExecutionUncertainError):
                lease.suspend()
            assert lease.state == "broken"
            assert managed.current_revision_id == before_revision
            after_uncertain_publish = list(recording.sent)
            assert after_uncertain_publish == before

            with pytest.raises(ExecutionContractError):
                lease.resume()
            assert recording.sent == after_uncertain_publish, "broken lease must reject before CREATE_VIEW RPC"
            with pytest.raises(WorkspacePortError, match="unavailable"):
                workspace_io.read_file("stale-parent-binding.txt")
            with pytest.raises(ExecutionUnavailableError):
                managed_executor.list_sessions()
            return SessionOutcome(0, "iteration_cap", 1, "")

        outcome, release_confirmed = cli._run_cli_stage(
            args=args,
            run_context=None,
            run_id=managed.binding.namespace.run_id,
            run_log_dir=tmp_path / "run-log",
            session_db=None,
            log=cast(EventLog, SimpleNamespace(path=tmp_path / "events.jsonl")),
            workspace=lease_site.source,
            role="chat",
            plan_ref=None,
            build_registry=build_registry,
            drive=drive,
        )

        assert outcome is None
        assert release_confirmed
        assert captured[2].state == "broken"
        assert Operation.CREATE_VIEW in recording.sent
        assert Operation.RELEASE not in recording.sent


def test_parent_lease_rejects_resume_until_writer_is_returned(lease_site: Site, tmp_path: Path) -> None:
    """A child that fails to return ownership cannot reactivate parent bindings."""
    with _served(lease_site, tmp_path) as managed:
        recording = _RecordingClient(managed.client)
        managed.client = recording
        captured: list[Any] = []

        def build_registry(workspace_io: Any, managed_executor: Any, lease: Any) -> ToolRegistry:
            captured.extend([workspace_io, managed_executor, lease])
            return ToolRegistry()

        def drive(_registry: ToolRegistry) -> SessionOutcome:
            port, executor, lease = captured
            lease.suspend()
            managed.handoff_to(
                NamespaceRef(
                    managed.binding.namespace.session_id, "lost-child", parent_run_id=managed.binding.namespace.run_id
                )
            )
            after_handoff = list(recording.sent)
            with pytest.raises(ExecutionContractError):
                lease.resume()
            assert recording.sent == after_handoff, "resume must reject before opening under the wrong owner"
            assert lease.state == "broken"
            with pytest.raises(WorkspacePortError, match="unavailable"):
                port.read_file("forbidden.txt")
            with pytest.raises(ExecutionUnavailableError):
                executor.list_sessions()
            return SessionOutcome(0, "iteration_cap", 1, "")

        with pytest.raises(ExecutionUnavailableError):
            _drive_stage_with_managed_workspace(
                managed=managed,
                owns_writer=True,
                run_id=managed.binding.namespace.run_id,
                run_log_dir=tmp_path / "run-log",
                session_db=None,
                workspace=lease_site.source,
                role="chat",
                plan_ref=None,
                build_registry=build_registry,
                drive=drive,
            )
        assert captured[2].state == "broken"
        assert not captured[2].writer_release_safe
        assert managed.binding.namespace.run_id == "lost-child"


def test_stage_exception_stops_active_view_before_releasing_writer(
    lease_site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed parent stage aborts its current view before the run-owned writer."""
    with _served(lease_site, tmp_path) as managed:
        recording = _RecordingClient(managed.client)
        managed.client = recording
        monkeypatch.setattr(cli, "managed_execution_for_run", lambda _run_context: managed)
        captured: list[Any] = []

        def build_registry(workspace_io: Any, managed_executor: Any, lease: Any) -> ToolRegistry:
            captured.extend([workspace_io, managed_executor, lease])
            return ToolRegistry()

        def drive(_registry: ToolRegistry) -> SessionOutcome:
            raise RuntimeError("stage failure sentinel")

        with pytest.raises(RuntimeError, match="stage failure sentinel"):
            cli._run_cli_stage(
                args=argparse.Namespace(),
                run_context=None,
                run_id=managed.binding.namespace.run_id,
                run_log_dir=tmp_path / "run-log",
                session_db=None,
                log=cast(EventLog, SimpleNamespace(path=tmp_path / "events.jsonl")),
                workspace=lease_site.source,
                role="chat",
                plan_ref=None,
                build_registry=build_registry,
                drive=drive,
            )

        lease = captured[2]
        assert lease.state == "closed"
        assert lease.writer_release_safe
        assert recording.sent.count(Operation.STOP_VIEW) == 1
        assert recording.sent.count(Operation.PUBLISH) == 0
        assert recording.sent.count(Operation.RELEASE) == 1


def test_uncertain_view_creation_retains_writer_and_does_not_call_registry(
    lease_site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unknown CREATE_VIEW outcome retains the writer; no guessed cleanup/release."""
    with _served(lease_site, tmp_path) as managed:
        recording = _RecordingClient(managed.client)
        managed.client = recording
        monkeypatch.setattr(cli, "managed_execution_for_run", lambda _run_context: managed)

        def uncertain_open_view(**_kwargs: Any) -> Any:
            raise ExecutionUncertainError("op-" + "a" * 32)

        monkeypatch.setattr(managed, "open_view", uncertain_open_view)
        registry_calls: list[str] = []

        def forbidden_registry(*_args: Any) -> ToolRegistry:
            registry_calls.append("built")
            raise AssertionError("registry must not be built without a confirmed parent view")

        outcome, release_confirmed = cli._run_cli_stage(
            args=argparse.Namespace(),
            run_context=None,
            run_id=managed.binding.namespace.run_id,
            run_log_dir=tmp_path / "run-log",
            session_db=None,
            log=cast(EventLog, SimpleNamespace(path=tmp_path / "events.jsonl")),
            workspace=lease_site.source,
            role="chat",
            plan_ref=None,
            build_registry=forbidden_registry,
            drive=lambda _registry: SessionOutcome(0, "iteration_cap", 1, ""),
        )

        assert outcome is None
        assert release_confirmed
        assert registry_calls == []
        assert recording.sent.count(Operation.RELEASE) == 0
        assert "managed stage failed closed" in capsys.readouterr().err
        assert managed.grant.operation is Operation.ACQUIRE_WRITER
