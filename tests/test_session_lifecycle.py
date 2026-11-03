"""C0/C1/C3 proof for the persistent session lifecycle.

Root: SessionManager boundary (the CLI composition root consumes this seam in
S2.2). Pyramid A only; no model/provider I/O.

Path inventory:
  A: default session creation and workspace provisioning
  B: explicit attach and new run allocation
  C: unknown/corrupt/mismatched session rejection
  D: workspace containment and reverse ownership rejection
  E: run-id reuse rejection and DB binding persistence
  F: read-only existing-DB open does not create missing paths
  G: managed provisioner injection (E263)
     G1 explicit reference: provisioner owns the bytes, receives a real
        provisioning run namespace, host cloning never runs
     G2 managed new-root provisioning owns the default root; readiness failure
        retains its Q118 non-active session/DB/run tombstone
     G3 not-READY readiness blocks new session AND attach (`workspace_not_ready`)
     G4 a registered result is never an rmtree target after a later failure
     G5 registered reference to another session's workspace is permitted without
        transferring its DB/run/manifest; an unregistered conflict stays rejected
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from fa.inner_loop.session_db import SessionDatabase, SessionDatabaseError
from fa.session import manager as manager_module
from fa.session.manager import RunContext, SessionManager, SessionManagerError
from fa.session.provisioning import ProvisionedWorkspace, ProvisionMode, ProvisionRequest
from fa.workspace_bootstrap import ReadyState, ReadyStatus


def _ready_state(workspace: Path, _run_context: RunContext | None = None) -> ReadyState:
    return ReadyState(
        status=ReadyStatus.READY,
        fingerprint="sha256:test",
        reason_code="ready_managed_artifact",
        log_path=workspace / "managed-readiness.log",
        repaired=False,
        elapsed_ms=1,
    )


def _degraded_state(workspace: Path, _run_context: RunContext | None) -> ReadyState:
    return ReadyState(
        status=ReadyStatus.DEGRADED_ENVIRONMENT,
        fingerprint=None,
        reason_code="tool_missing",
        log_path=workspace / ".fa" / "bootstrap.log",
        repaired=False,
        elapsed_ms=1,
    )


def _registered(workspace_id: str, revision_id: str, digest: str) -> ProvisionedWorkspace:
    return ProvisionedWorkspace(
        registered=True,
        workspace_id=workspace_id,
        revision_id=revision_id,
        tree_sha256=digest,
    )


def _scratch() -> ProvisionedWorkspace:
    return ProvisionedWorkspace(registered=False, workspace_id=None, revision_id=None, tree_sha256=None)


def _registers(_request: ProvisionRequest) -> ProvisionedWorkspace:
    """Managed-composition provisioner: claims supervisor ownership, creates nothing."""
    return _registered("ws-test", "rev-test", "a" * 64)


def _fixture_provisioner(request: ProvisionRequest) -> ProvisionedWorkspace:
    if request.mode is ProvisionMode.PROVISION:
        if request.source_workspace is None:
            request.workspace_path.mkdir()
        else:
            shutil.copytree(request.source_workspace, request.workspace_path)
    return _registered("ws-fixture", "rev-fixture", "a" * 64)


def _manager(
    tmp_path: Path,
    *,
    workspace_preparer: Callable[[Path, RunContext | None], ReadyState] | None = None,
    workspace_provisioner: Callable[[ProvisionRequest], ProvisionedWorkspace] | None = None,
) -> SessionManager:
    source = tmp_path / "source"
    source.mkdir(exist_ok=True)
    (source / "README.md").write_text("source", encoding="utf-8")
    return SessionManager(
        state_root=tmp_path / "state",
        workspace_root=tmp_path / "workspaces",
        source_workspace=source,
        workspace_preparer=_ready_state if workspace_preparer is None else workspace_preparer,
        workspace_provisioner=_fixture_provisioner if workspace_provisioner is None else workspace_provisioner,
    )


def test_default_session_provisions_manifest_db_workspace_and_fresh_runs(tmp_path: Path) -> None:
    """C1 A/B: one session persists while each admitted run gets a new ID."""
    manager = _manager(tmp_path)

    session = manager.create_or_attach_session(session_id=None, workspace_override=None)
    first = manager.begin_run(session, requested_run_id=None)
    second = manager.begin_run(session, requested_run_id=None)

    assert session.session_id.startswith("session-")
    assert session.workspace_path == (tmp_path / "workspaces" / session.session_id).resolve()
    assert (session.workspace_path / "README.md").read_text(encoding="utf-8") == "source"
    assert session.session_db_path.is_file()
    assert session.manifest_path.is_file()
    manifest = json.loads(session.manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "active"
    assert manifest["session_id"] == session.session_id
    assert manifest["session_db_path"] == str(session.session_db_path)
    assert first.session_id == second.session_id == session.session_id
    assert first.run_id != second.run_id
    assert first.run_log_dir.is_dir()
    assert second.run_log_dir.is_dir()

    db = SessionDatabase.open_existing(session.session_db_path, session_id=session.session_id)
    assert db.get_run_binding(first.run_id)["session_id"] == session.session_id  # type: ignore[index]
    assert db.get_run_binding(second.run_id)["session_id"] == session.session_id  # type: ignore[index]


def test_explicit_attach_reuses_session_authority_and_workspace(tmp_path: Path) -> None:
    """C1 B: explicit attach cannot silently select another namespace."""
    manager = _manager(tmp_path)
    created = manager.create_or_attach_session(session_id=None, workspace_override=None)

    attached = manager.create_or_attach_session(
        session_id=created.session_id,
        workspace_override=created.workspace_path,
    )
    run = manager.begin_run(attached, requested_run_id="controlled-new-run")

    assert attached.session_id == created.session_id
    assert attached.workspace_path == created.workspace_path
    assert attached.session_db_path == created.session_db_path
    assert run.run_log_dir == (manager.run_root / "controlled-new-run").resolve()


def test_new_session_prepares_after_db_before_active_manifest(tmp_path: Path) -> None:
    """C1 A: readiness producer runs inside new-session admission ordering."""

    observed: list[tuple[Path, bool, str, str]] = []
    provision_requests: list[ProvisionRequest] = []

    def prepare(workspace: Path, run_context: RunContext | None) -> ReadyState:
        assert isinstance(run_context, RunContext)
        manifests = list((tmp_path / "state" / "sessions").glob("*/manifest.json"))
        assert len(manifests) == 1
        manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
        db_path = Path(str(manifest["session_db_path"]))
        db = SessionDatabase.open_existing(db_path, session_id=run_context.session_id)
        assert db.get_run_binding(run_context.run_id) is not None
        observed.append((workspace, db_path.is_file(), str(manifest["status"]), run_context.run_id))
        return _ready_state(workspace)

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        provision_requests.append(request)
        return _fixture_provisioner(request)

    manager = _manager(tmp_path, workspace_preparer=prepare, workspace_provisioner=provision)
    created = manager.create_or_attach_session(session_id=None, workspace_override=None)

    assert len(provision_requests) == 1
    assert observed == [(created.workspace_path, True, "provisioning", provision_requests[0].run_id)]
    manifest = json.loads(created.manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "active"
    assert "bootstrap" not in manifest


def test_attach_prepares_after_db_validation_before_last_used_write(tmp_path: Path) -> None:
    """C1 B: attach readiness precedes the only manifest mutation."""

    creator = _manager(tmp_path)
    created = creator.create_or_attach_session(session_id=None, workspace_override=None)
    before = json.loads(created.manifest_path.read_text(encoding="utf-8"))
    observed: list[tuple[Path, str]] = []

    def prepare(workspace: Path, run_context: RunContext | None) -> ReadyState:
        assert isinstance(run_context, RunContext)
        current = json.loads(created.manifest_path.read_text(encoding="utf-8"))
        database = SessionDatabase.open_existing(created.session_db_path, session_id=created.session_id)
        assert database.get_run_binding(run_context.run_id) is not None
        observed.append((workspace, str(current["last_used_at"])))
        return _ready_state(workspace)

    manager = SessionManager(
        state_root=tmp_path / "state",
        workspace_root=tmp_path / "workspaces",
        source_workspace=tmp_path / "source",
        workspace_preparer=prepare,
        workspace_provisioner=_fixture_provisioner,
    )
    attached = manager.create_or_attach_session(
        session_id=created.session_id,
        workspace_override=created.workspace_path,
    )

    assert attached.workspace_path == created.workspace_path
    assert observed == [(created.workspace_path, str(before["last_used_at"]))]
    after = json.loads(created.manifest_path.read_text(encoding="utf-8"))
    assert after["status"] == "active"


def test_unexpected_new_session_preparer_failure_keeps_q118_tombstone(tmp_path: Path) -> None:
    """C3 A: after admission, an unexpected readiness failure leaves a non-active tombstone."""

    def fail(_workspace: Path, _run_context: RunContext | None) -> ReadyState:
        raise RuntimeError("preparer contract breach")

    manager = _manager(tmp_path, workspace_preparer=fail)

    with pytest.raises(SessionManagerError, match="session_provision_failed"):
        manager.provision_entrypoint_session(session_id="session-readiness-failed")

    tombstone = manager.sessions_root / "session-readiness-failed"
    manifest = json.loads((tombstone / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "provisioning"
    database = SessionDatabase.open_existing(tombstone / "session.db", session_id="session-readiness-failed")
    run_dirs = list(manager.run_root.iterdir())
    assert len(run_dirs) == 1
    assert database.get_run_binding(run_dirs[0].name) is not None
    assert database.event_count() == 0
    assert (manager.workspace_root / "session-readiness-failed" / "README.md").read_text(encoding="utf-8") == "source"


def test_unknown_session_and_workspace_mismatch_fail_before_mutation(tmp_path: Path) -> None:
    """C3 C/D: unknown IDs and attach mismatches are fail-closed."""
    manager = _manager(tmp_path)
    state_before = sorted((manager.sessions_root).glob("**/*"))

    with pytest.raises(SessionManagerError, match="unknown_session") as unknown:
        manager.create_or_attach_session(session_id="does-not-exist", workspace_override=None)
    assert unknown.value.code == "unknown_session"
    assert sorted(manager.sessions_root.glob("**/*")) == state_before

    created = manager.create_or_attach_session(session_id=None, workspace_override=None)
    wrong_workspace = tmp_path / "workspaces" / "different"
    with pytest.raises(SessionManagerError, match="workspace_mismatch") as mismatch:
        manager.create_or_attach_session(
            session_id=created.session_id,
            workspace_override=wrong_workspace,
        )
    assert mismatch.value.code == "workspace_mismatch"
    assert not wrong_workspace.exists()
    with pytest.raises(SessionManagerError, match="workspace_mismatch") as entrypoint_mismatch:
        manager.provision_entrypoint_session(
            session_id=created.session_id,
            workspace_override=wrong_workspace,
        )
    assert entrypoint_mismatch.value.code == "workspace_mismatch"
    assert not wrong_workspace.exists()

    with pytest.raises(SessionManagerError, match="workspace_escape") as escape:
        manager.create_or_attach_session(
            session_id=None,
            workspace_override=tmp_path / "outside" / ".." / "escape",
        )
    assert escape.value.code == "workspace_escape"


def test_workspace_cannot_be_owned_by_two_sessions(tmp_path: Path) -> None:
    """C3 D: reverse ownership prevents namespace aliasing."""
    manager = _manager(tmp_path)
    created = manager.create_or_attach_session(session_id=None, workspace_override=None)

    refuser = _manager(tmp_path, workspace_provisioner=lambda _request: _scratch())
    with pytest.raises(SessionManagerError, match="workspace_already_owned") as exc:
        refuser.create_or_attach_session(session_id=None, workspace_override=created.workspace_path)
    assert exc.value.code == "workspace_already_owned"


def test_corrupt_manifest_and_reused_run_id_fail_closed(tmp_path: Path) -> None:
    """C3 C/E: corrupt identity and run reuse never become append/resume."""
    manager = _manager(tmp_path)
    created = manager.create_or_attach_session(session_id=None, workspace_override=None)
    first = manager.begin_run(created, requested_run_id="stable-run")

    with pytest.raises(SessionManagerError, match="run_id_reused") as reused:
        manager.begin_run(created, requested_run_id=first.run_id)
    assert reused.value.code == "run_id_reused"
    assert list(first.run_log_dir.iterdir()) == []

    created.manifest_path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(SessionManagerError, match="manifest_corrupt") as corrupt:
        manager.create_or_attach_session(session_id=created.session_id, workspace_override=None)
    assert corrupt.value.code == "manifest_corrupt"


def test_read_only_open_rejects_legacy_or_missing_without_creating_paths(tmp_path: Path) -> None:
    """C0/C3 F: stats/open-existing has no bootstrap side effect."""
    missing = tmp_path / "missing" / "session.db"
    with pytest.raises(SessionDatabaseError, match="session_db_not_found") as not_found:
        SessionDatabase.open_existing(missing, session_id="session-A")
    assert not_found.value.code == "session_db_not_found"
    assert not missing.exists()
    assert not missing.parent.exists()

    legacy = tmp_path / "legacy.db"
    conn = sqlite3.connect(legacy)
    conn.executescript(
        """
        CREATE TABLE event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            run_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            kind TEXT NOT NULL,
            tool_name TEXT NOT NULL DEFAULT '',
            tool_call_id TEXT NOT NULL DEFAULT '',
            parent_event_id TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL,
            harness_id TEXT NOT NULL
        );
        CREATE TABLE blackboard (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            type TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            toolchain_digest TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            parent_id TEXT,
            read_set TEXT NOT NULL,
            write_set TEXT NOT NULL,
            assumptions TEXT NOT NULL,
            version_dependencies TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            payload TEXT NOT NULL
        );
        CREATE TABLE session_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

    with pytest.raises(SessionDatabaseError, match="session_db_legacy_schema") as unsupported:
        SessionDatabase(legacy, session_id="session-A")
    assert unsupported.value.code == "session_db_legacy_schema"
    assert legacy.is_file()
    assert not (tmp_path / "legacy" / "session.db").exists()


def test_entrypoint_provisioning_uses_same_manager_owner(tmp_path: Path) -> None:
    """C1: shell handoff creates/attaches manifest through SessionManager."""
    manager = _manager(tmp_path)
    workspace = tmp_path / "workspaces" / "entrypoint-session"
    workspace.mkdir(parents=True)

    created = manager.provision_entrypoint_session(
        session_id="entrypoint-session",
        workspace_override=workspace,
    )
    attached = manager.provision_entrypoint_session(
        session_id="entrypoint-session",
        workspace_override=workspace,
    )

    assert created == attached
    assert created.manifest_path.is_file()
    assert created.session_db_path.is_file()


def test_entrypoint_provisioning_uses_manager_owned_default_root_without_workspace(
    tmp_path: Path,
) -> None:
    """C1: omitted shell override selects the manager root and resume reuses it."""
    requests: list[ProvisionRequest] = []
    readiness_contexts: list[RunContext | None] = []

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        requests.append(request)
        return _fixture_provisioner(request)

    def prepare(workspace: Path, run_context: RunContext | None) -> ReadyState:
        readiness_contexts.append(run_context)
        return _ready_state(workspace, run_context)

    manager = _manager(tmp_path, workspace_preparer=prepare, workspace_provisioner=provision)
    created = manager.provision_entrypoint_session(
        session_id="entrypoint-managed-root",
        workspace_override=None,
    )
    attached = manager.provision_entrypoint_session(
        session_id="entrypoint-managed-root",
        workspace_override=None,
    )

    expected_root = (tmp_path / "workspaces" / "entrypoint-managed-root").resolve()
    assert created.workspace_path == attached.workspace_path == expected_root
    assert (expected_root / "README.md").read_text(encoding="utf-8") == "source"
    assert created.manifest_path.is_file()
    assert created.session_db_path.is_file()
    assert [request.mode for request in requests] == [ProvisionMode.PROVISION, ProvisionMode.REUSE]
    assert [request.workspace_path for request in requests] == [expected_root, expected_root]
    assert requests[0].source_workspace == manager.source_workspace
    assert requests[1].source_workspace is None
    assert len(readiness_contexts) == 2
    assert all(isinstance(context, RunContext) for context in readiness_contexts)
    assert [context.run_id for context in readiness_contexts if context is not None] == [
        requests[0].run_id,
        requests[1].run_id,
    ]
    assert requests[0].run_id != requests[1].run_id


def test_entrypoint_manager_refuses_missing_managed_provisioner_before_state_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2/C3: module CLI cannot silently reach the pre-cutover host path."""
    workspace_root = tmp_path / "workspaces"
    state_root = tmp_path / "state"
    monkeypatch.setattr("fa.execution.composition.client_workspace_provisioner", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fa.session.manager",
            "provision",
            "--state-root",
            str(state_root),
            "--workspace-root",
            str(workspace_root),
            "--session-id",
            "session-no-backend",
        ],
    )

    exit_code = manager_module._main()

    assert exit_code == 2
    assert "managed_execution_unavailable" in capsys.readouterr().err
    assert not state_root.exists()
    assert not workspace_root.exists()


def test_entrypoint_manager_injects_configured_provisioner_and_fails_closed_on_rpc_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C1/C3: the production CLI uses the configured port and preserves caller-owned bytes."""
    workspace_root = tmp_path / "workspaces"
    workspace = workspace_root / "existing"
    workspace.mkdir(parents=True)
    sentinel = workspace / "operator-data.txt"
    sentinel.write_text("keep", encoding="utf-8")
    state_root = tmp_path / "state"
    requests: list[ProvisionRequest] = []

    def unavailable(request: ProvisionRequest) -> ProvisionedWorkspace:
        requests.append(request)
        raise SessionManagerError("workspace_provision_failed", "managed backend unavailable")

    monkeypatch.setattr("fa.execution.composition.client_workspace_provisioner", lambda: unavailable)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fa.session.manager",
            "provision",
            "--state-root",
            str(state_root),
            "--workspace-root",
            str(workspace_root),
            "--session-id",
            "session-existing",
            "--workspace",
            str(workspace),
        ],
    )

    exit_code = manager_module._main()

    assert exit_code == 2
    assert "workspace_provision_failed" in capsys.readouterr().err
    assert len(requests) == 1
    assert requests[0].mode is ProvisionMode.REUSE
    assert requests[0].workspace_path == workspace
    assert sentinel.read_text(encoding="utf-8") == "keep"
    tombstone_dir = state_root / "sessions" / "session-existing"
    manifest = json.loads((tombstone_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "provisioning"
    db = SessionDatabase.open_existing(tombstone_dir / "session.db", session_id="session-existing")
    assert db.get_run_binding(requests[0].run_id) is not None
    assert db.event_count() == 0
    assert len(list((state_root / "session-log").iterdir())) == 1


def test_entrypoint_manager_uses_injected_provisioner_for_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """EDGE KILL-CHECK: deleting the factory-result binding bypasses managed registration."""
    workspace_root = tmp_path / "workspaces"
    workspace = workspace_root / "existing"
    workspace.mkdir(parents=True)
    state_root = tmp_path / "state"
    requests: list[ProvisionRequest] = []

    def registered(request: ProvisionRequest) -> ProvisionedWorkspace:
        requests.append(request)
        return _registered("ws-entrypoint", "rev-entrypoint", "a" * 64)

    monkeypatch.setattr("fa.execution.composition.client_workspace_provisioner", lambda: registered)
    monkeypatch.setattr(manager_module, "_managed_workspace_preparer", _ready_state)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fa.session.manager",
            "provision",
            "--state-root",
            str(state_root),
            "--workspace-root",
            str(workspace_root),
            "--session-id",
            "session-existing",
            "--workspace",
            str(workspace),
        ],
    )

    exit_code = manager_module._main()

    assert exit_code == 0
    assert len(requests) == 1
    assert requests[0].mode is ProvisionMode.REUSE
    assert json.loads(capsys.readouterr().out)["session_id"] == "session-existing"
    manifest = state_root / "sessions" / "session-existing" / "manifest.json"
    assert json.loads(manifest.read_text(encoding="utf-8"))["status"] == "active"


def test_entrypoint_cli_provisions_manager_default_root_without_workspace_argument(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C2/C3: CLI omission reaches the managed port with the manager-selected root."""
    workspace_root = tmp_path / "workspaces"
    state_root = tmp_path / "state"
    requests: list[ProvisionRequest] = []
    real_is_dir = Path.is_dir
    monkeypatch.delenv("FA_SESSION_SOURCE", raising=False)

    def source_visible(path: Path) -> bool:
        return True if path == Path("/repo") else real_is_dir(path)

    monkeypatch.setattr(Path, "is_dir", source_visible)

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        requests.append(request)
        request.workspace_path.mkdir(parents=True)
        (request.workspace_path / "managed.txt").write_text("managed", encoding="utf-8")
        return _registered("ws-default-root", "rev-default-root", "c" * 64)

    monkeypatch.setattr("fa.execution.composition.client_workspace_provisioner", lambda: provision)
    monkeypatch.setattr(manager_module, "_managed_workspace_preparer", _ready_state)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fa.session.manager",
            "provision",
            "--state-root",
            str(state_root),
            "--workspace-root",
            str(workspace_root),
            "--session-id",
            "session-cli-default-root",
        ],
    )

    exit_code = manager_module._main()

    assert exit_code == 0
    assert len(requests) == 1
    request = requests[0]
    expected_root = (workspace_root / "session-cli-default-root").resolve()
    assert request.mode is ProvisionMode.PROVISION
    assert request.workspace_path == expected_root
    assert (expected_root / "managed.txt").read_text(encoding="utf-8") == "managed"
    assert request.source_workspace == Path("/repo")
    manifest = json.loads(
        (state_root / "sessions" / "session-cli-default-root" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "active"
    output = json.loads(capsys.readouterr().out)
    assert output["session_id"] == "session-cli-default-root"
    assert output["manifest_path"] == str(state_root / "sessions" / "session-cli-default-root" / "manifest.json")


def test_entrypoint_cli_explicit_source_overrides_default_repo_seed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2: configured source is forwarded instead of the default /repo seed."""
    workspace_root = tmp_path / "workspaces"
    state_root = tmp_path / "state"
    source = tmp_path / "approved-source"
    source.mkdir()
    requests: list[ProvisionRequest] = []
    real_is_dir = Path.is_dir
    monkeypatch.setenv("FA_SESSION_SOURCE", str(source))

    def source_visible(path: Path) -> bool:
        return True if path == Path("/repo") else real_is_dir(path)

    monkeypatch.setattr(Path, "is_dir", source_visible)

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        requests.append(request)
        request.workspace_path.mkdir(parents=True)
        return _registered("ws-explicit-source", "rev-explicit-source", "e" * 64)

    monkeypatch.setattr("fa.execution.composition.client_workspace_provisioner", lambda: provision)
    monkeypatch.setattr(manager_module, "_managed_workspace_preparer", _ready_state)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fa.session.manager",
            "provision",
            "--state-root",
            str(state_root),
            "--workspace-root",
            str(workspace_root),
            "--session-id",
            "session-cli-explicit-source",
        ],
    )

    exit_code = manager_module._main()

    assert exit_code == 0
    assert len(requests) == 1
    assert requests[0].source_workspace == source.resolve()


def test_entrypoint_cli_explicit_empty_source_selects_clean_seed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2: the explicit empty source override wins over a present /repo seed."""
    workspace_root = tmp_path / "workspaces"
    state_root = tmp_path / "state"
    requests: list[ProvisionRequest] = []
    real_is_dir = Path.is_dir
    monkeypatch.setenv("FA_SESSION_SOURCE", "")

    def source_visible(path: Path) -> bool:
        return True if path == Path("/repo") else real_is_dir(path)

    monkeypatch.setattr(Path, "is_dir", source_visible)

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        requests.append(request)
        request.workspace_path.mkdir(parents=True)
        return _registered("ws-clean-seed", "rev-clean-seed", "d" * 64)

    monkeypatch.setattr("fa.execution.composition.client_workspace_provisioner", lambda: provision)
    monkeypatch.setattr(manager_module, "_managed_workspace_preparer", _ready_state)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fa.session.manager",
            "provision",
            "--state-root",
            str(state_root),
            "--workspace-root",
            str(workspace_root),
            "--session-id",
            "session-cli-clean-seed",
        ],
    )

    exit_code = manager_module._main()

    assert exit_code == 0
    assert len(requests) == 1
    assert requests[0].mode is ProvisionMode.PROVISION
    assert requests[0].source_workspace is None
    assert requests[0].workspace_path == (workspace_root / "session-cli-clean-seed").resolve()


def test_ambiguous_partial_managed_root_is_retained_on_failure(tmp_path: Path) -> None:
    """C3/Q118: manager never deletes bytes after an uncertain managed create."""

    def partial_provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        request.workspace_path.mkdir()
        (request.workspace_path / "partial.txt").write_text("partial", encoding="utf-8")
        raise SessionManagerError("workspace_provision_failed", "create reply lost")

    manager = _manager(tmp_path, workspace_provisioner=partial_provision)
    with pytest.raises(SessionManagerError, match="workspace_provision_failed"):
        manager.provision_entrypoint_session(
            session_id="session-partial",
            workspace_override=manager.workspace_root / "session-partial",
        )

    workspace = manager.workspace_root / "session-partial"
    assert (workspace / "partial.txt").read_text(encoding="utf-8") == "partial"
    tombstone = manager.sessions_root / "session-partial"
    manifest = json.loads((tombstone / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "provisioning"
    database = SessionDatabase.open_existing(tombstone / "session.db", session_id="session-partial")
    assert database.event_count() == 0
    assert len(list(manager.run_root.iterdir())) == 1


def test_managed_provisioner_owns_workspace_bytes_and_readiness_receives_same_run_context(
    tmp_path: Path,
) -> None:
    """C1 G1: the existing readiness seam receives the provisioner's exact admitted run."""

    observed: dict[str, object] = {}
    provision_requests: list[ProvisionRequest] = []
    readiness_contexts: list[RunContext | None] = []

    def prepare(workspace: Path, run_context: RunContext | None) -> ReadyState:
        readiness_contexts.append(run_context)
        observed["readiness_workspace"] = workspace
        return _ready_state(workspace)

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        provision_requests.append(request)
        manifest = json.loads(
            (tmp_path / "state" / "sessions" / request.session_id / "manifest.json").read_text(encoding="utf-8")
        )
        database = SessionDatabase.open_existing(Path(str(manifest["session_db_path"])), session_id=request.session_id)
        observed.update(
            mode=request.mode,
            session_id=request.session_id,
            existed=request.workspace_path.exists(),
            status=manifest["status"],
            run_bound=database.get_run_binding(request.run_id) is not None,
            run_dir=(tmp_path / "state" / "session-log" / request.run_id).is_dir(),
            run_id=request.run_id,
        )
        request.workspace_path.mkdir(parents=True)
        (request.workspace_path / "supervisor.txt").write_text("own bytes", encoding="utf-8")
        return _registered("ws-supervisor", "rev-supervisor", "b" * 64)

    manager = _manager(tmp_path, workspace_preparer=prepare, workspace_provisioner=provision)
    workspace = tmp_path / "workspaces" / "explicit"
    session = manager.provision_entrypoint_session(session_id="session-a", workspace_override=workspace)

    assert session.workspace_path == workspace
    assert observed["mode"] is ProvisionMode.PROVISION
    assert observed["session_id"] == "session-a"
    assert observed["existed"] is False
    assert observed["status"] == "provisioning"
    assert observed["run_bound"] is True
    assert observed["run_dir"] is True
    assert isinstance(observed["run_id"], str) and observed["run_id"].startswith("run-")
    assert len(provision_requests) == len(readiness_contexts) == 1
    request = provision_requests[0]
    run_context = readiness_contexts[0]
    assert isinstance(run_context, RunContext)
    assert run_context.run_id == request.run_id == observed["run_id"]
    assert run_context.session_id == request.session_id == session.session_id
    assert run_context.workspace_path == request.workspace_path == workspace
    assert run_context.session_db_path == session.session_db_path
    assert run_context.run_log_dir == manager.run_root / request.run_id
    assert observed["readiness_workspace"] == workspace
    assert (workspace / "supervisor.txt").read_text(encoding="utf-8") == "own bytes"
    assert not (workspace / "README.md").exists(), "host provisioning must not run when the provisioner is injected"
    assert json.loads(session.manifest_path.read_text(encoding="utf-8"))["status"] == "active"


def test_new_root_provisioning_refusal_retains_q118_tombstone_and_run_binding(tmp_path: Path) -> None:
    """C1/C3 G2: failed managed admission retains a non-active, non-reusable reservation."""

    calls: list[ProvisionRequest] = []

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        calls.append(request)
        raise SessionManagerError("provisioning_unavailable", "publication join is SLICE3")

    manager = _manager(tmp_path, workspace_provisioner=provision)
    workspace = tmp_path / "workspaces" / "fresh"

    with pytest.raises(SessionManagerError) as blocked:
        manager.provision_entrypoint_session(session_id="session-fresh", workspace_override=workspace)

    assert blocked.value.code == "provisioning_unavailable"
    assert [request.mode for request in calls] == [ProvisionMode.PROVISION]
    assert not workspace.exists()
    tombstone_dir = tmp_path / "state" / "sessions" / "session-fresh"
    assert tombstone_dir.is_dir()
    manifest_path = tombstone_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "provisioning"
    assert manifest["session_db_path"] == str(tombstone_dir / "session.db")
    db = SessionDatabase.open_existing(tombstone_dir / "session.db", session_id="session-fresh")
    assert db.get_run_binding(calls[0].run_id) is not None
    assert db.event_count() == 0
    assert (manager.run_root / calls[0].run_id).is_dir()

    with pytest.raises(SessionManagerError) as attach_refused:
        manager.create_or_attach_session(session_id="session-fresh", workspace_override=workspace)
    assert attach_refused.value.code == "session_not_active"

    # Prove the DB tombstone, not only the run directory, excludes the ID.
    (manager.run_root / calls[0].run_id).rmdir()
    other_manager = _manager(tmp_path)
    other = other_manager.create_or_attach_session(session_id=None, workspace_override=None)
    with pytest.raises(SessionManagerError) as reused:
        other_manager.begin_run(other, calls[0].run_id)
    assert reused.value.code == "run_id_reused"


def test_not_ready_readiness_blocks_new_session_and_attach(tmp_path: Path) -> None:
    """C1 G3: readiness degradation is closed in both lifecycle paths (managed composition)."""

    creator = _manager(tmp_path)
    created = creator.create_or_attach_session(session_id=None, workspace_override=None)
    before = json.loads(created.manifest_path.read_text(encoding="utf-8"))

    attach_manager = _manager(tmp_path, workspace_preparer=_degraded_state, workspace_provisioner=_registers)
    with pytest.raises(SessionManagerError) as attach_error:
        attach_manager.create_or_attach_session(
            session_id=created.session_id,
            workspace_override=created.workspace_path,
        )
    assert attach_error.value.code == "workspace_not_ready"
    assert json.loads(created.manifest_path.read_text(encoding="utf-8"))["last_used_at"] == before["last_used_at"]

    new_requests: list[ProvisionRequest] = []

    def register_new(request: ProvisionRequest) -> ProvisionedWorkspace:
        new_requests.append(request)
        return _registers(request)

    new_manager = _manager(
        tmp_path,
        workspace_preparer=_degraded_state,
        workspace_provisioner=register_new,
    )
    with pytest.raises(SessionManagerError) as new_error:
        new_manager.create_or_attach_session(session_id=None, workspace_override=None)
    assert new_error.value.code == "workspace_not_ready"
    assert len(list((tmp_path / "state" / "sessions").iterdir())) == 2
    assert len(new_requests) == 1
    failed_session_dir = next(
        path for path in (tmp_path / "state" / "sessions").iterdir() if path.name != created.session_id
    )
    failed_manifest = json.loads((failed_session_dir / "manifest.json").read_text(encoding="utf-8"))
    assert failed_manifest["status"] == "provisioning"
    failed_db = SessionDatabase.open_existing(failed_session_dir / "session.db", session_id=failed_session_dir.name)
    assert failed_db.get_run_binding(new_requests[0].run_id) is not None
    assert failed_db.event_count() == 0


@pytest.mark.parametrize("provision_outcome", ["unavailable", "unregistered"])
def test_managed_attach_refusal_precedes_readiness_and_preserves_existing_state(
    tmp_path: Path, provision_outcome: str
) -> None:
    """C1/C3 G6: failed managed REUSE never falls through to host readiness."""

    creator = _manager(tmp_path)
    created = creator.create_or_attach_session(session_id=None, workspace_override=None)
    workspace_sentinel = created.workspace_path / "operator-data.txt"
    workspace_sentinel.write_text("preserve this", encoding="utf-8")
    manifest_before = created.manifest_path.read_bytes()
    session_db = SessionDatabase.open_existing(created.session_db_path, session_id=created.session_id)
    event_count_before = session_db.event_count()
    readiness_calls: list[Path] = []
    provision_requests: list[ProvisionRequest] = []

    def prepare(workspace: Path, _run_context: RunContext | None) -> ReadyState:
        readiness_calls.append(workspace)
        return _ready_state(workspace)

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        provision_requests.append(request)
        if provision_outcome == "unavailable":
            raise SessionManagerError("workspace_provision_failed", "managed backend unavailable")
        return _scratch()

    attach_manager = _manager(tmp_path, workspace_preparer=prepare, workspace_provisioner=provision)
    with pytest.raises(SessionManagerError) as refused:
        attach_manager.create_or_attach_session(
            session_id=created.session_id,
            workspace_override=created.workspace_path,
        )

    assert refused.value.code == "workspace_provision_failed"
    assert len(provision_requests) == 1
    request = provision_requests[0]
    assert request.mode is ProvisionMode.REUSE
    assert request.session_id == created.session_id
    assert request.workspace_path == created.workspace_path
    assert request.run_id
    assert not readiness_calls
    assert created.manifest_path.read_bytes() == manifest_before
    assert workspace_sentinel.read_text(encoding="utf-8") == "preserve this"
    assert session_db.event_count() == event_count_before
    assert session_db.get_run_binding(request.run_id) is not None
    assert (attach_manager.run_root / request.run_id).is_dir()


def test_managed_attach_registers_before_readiness_and_passes_same_run_context(tmp_path: Path) -> None:
    """C1: attach registration and readiness share the exact admitted run identity."""

    creator = _manager(tmp_path)
    created = creator.create_or_attach_session(session_id=None, workspace_override=None)
    calls: list[str] = []
    provision_requests: list[ProvisionRequest] = []
    readiness_contexts: list[RunContext | None] = []

    def prepare(workspace: Path, run_context: RunContext | None) -> ReadyState:
        calls.append("readiness")
        readiness_contexts.append(run_context)
        return _ready_state(workspace)

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        calls.append("reuse")
        provision_requests.append(request)
        assert request.mode is ProvisionMode.REUSE
        assert request.session_id == created.session_id
        assert request.workspace_path == created.workspace_path
        return _registered("ws-attach", "rev-attach", "b" * 64)

    attach_manager = _manager(tmp_path, workspace_preparer=prepare, workspace_provisioner=provision)
    attached = attach_manager.create_or_attach_session(
        session_id=created.session_id,
        workspace_override=created.workspace_path,
    )

    assert calls == ["reuse", "readiness"]
    assert attached.session_id == created.session_id
    assert attached.workspace_path == created.workspace_path
    assert len(provision_requests) == len(readiness_contexts) == 1
    request = provision_requests[0]
    run_context = readiness_contexts[0]
    assert isinstance(run_context, RunContext)
    assert run_context.run_id == request.run_id
    assert run_context.session_id == request.session_id == created.session_id
    assert run_context.workspace_path == request.workspace_path == created.workspace_path
    assert run_context.session_db_path == created.session_db_path
    assert run_context.run_log_dir == attach_manager.run_root / request.run_id


def test_managed_unregistered_existing_workspace_is_preserved_on_new_session_refusal(tmp_path: Path) -> None:
    """C1/C3 G6: refused REUSE cannot delete a caller-owned workspace."""

    workspace = tmp_path / "workspaces" / "explicit"
    workspace.mkdir(parents=True)
    sentinel = workspace / "operator-data.txt"
    sentinel.write_text("preserve this", encoding="utf-8")
    readiness_calls: list[Path] = []
    provision_requests: list[ProvisionRequest] = []

    def prepare(path: Path, _run_context: RunContext | None) -> ReadyState:
        readiness_calls.append(path)
        return _ready_state(path)

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        provision_requests.append(request)
        return _scratch()

    manager = _manager(tmp_path, workspace_preparer=prepare, workspace_provisioner=provision)
    with pytest.raises(SessionManagerError) as refused:
        manager.create_or_attach_session(session_id=None, workspace_override=workspace)

    assert refused.value.code == "workspace_provision_failed"
    assert len(provision_requests) == 1
    assert provision_requests[0].mode is ProvisionMode.REUSE
    assert not readiness_calls
    assert sentinel.read_text(encoding="utf-8") == "preserve this"
    assert sorted(path.name for path in workspace.iterdir()) == ["operator-data.txt"]
    tombstone_dir = next(manager.sessions_root.iterdir())
    manifest = json.loads((tombstone_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "provisioning"
    db = SessionDatabase.open_existing(tombstone_dir / "session.db", session_id=tombstone_dir.name)
    assert db.get_run_binding(provision_requests[0].run_id) is not None
    assert db.event_count() == 0


def test_registered_workspace_bytes_survive_a_later_session_failure(tmp_path: Path) -> None:
    """C1 G4: only uncommitted scratch is cleanup-eligible, never registered bytes."""

    workspace = tmp_path / "workspaces" / "registered"
    workspace.mkdir(parents=True)
    (workspace / "canonical.txt").write_text("registered bytes", encoding="utf-8")

    requests: list[ProvisionRequest] = []

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        requests.append(request)
        return _registered("ws-1", "rev-1", "0" * 64)

    def fail(_workspace: Path, _run_context: RunContext | None) -> ReadyState:
        raise RuntimeError("readiness contract breach")

    manager = _manager(tmp_path, workspace_preparer=fail, workspace_provisioner=provision)
    with pytest.raises(SessionManagerError, match="session_provision_failed"):
        manager.provision_entrypoint_session(session_id="session-registered", workspace_override=workspace)

    assert (workspace / "canonical.txt").read_text(encoding="utf-8") == "registered bytes"
    tombstone_dir = tmp_path / "state" / "sessions" / "session-registered"
    manifest = json.loads((tombstone_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "provisioning"
    db = SessionDatabase.open_existing(tombstone_dir / "session.db", session_id="session-registered")
    assert db.get_run_binding(requests[0].run_id) is not None
    assert db.event_count() == 0


def test_registered_conflicting_reference_is_permitted_without_transferring_ownership(tmp_path: Path) -> None:
    """C1/C3 G5: CT103a reference succeeds; an unregistered conflict still fails closed."""

    shared = tmp_path / "workspaces" / "shared"
    shared.mkdir(parents=True)
    (shared / "canonical.txt").write_text("shared", encoding="utf-8")

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        return _registered("ws-shared", "rev-1", "1" * 64)

    owner = _manager(tmp_path, workspace_provisioner=provision)
    first = owner.provision_entrypoint_session(session_id="session-owner", workspace_override=shared)
    first_run = owner.begin_run(first, None)
    first_manifest = first.manifest_path.read_bytes()
    first_database = first.session_db_path.read_bytes()

    referrer = _manager(tmp_path, workspace_provisioner=provision)
    second = referrer.provision_entrypoint_session(session_id="session-referrer", workspace_override=shared)
    assert second.workspace_path == shared
    assert first.manifest_path.read_bytes() == first_manifest
    assert first.session_db_path.read_bytes() == first_database
    database = SessionDatabase.open_existing(first.session_db_path, session_id="session-owner")
    assert database.get_run_binding(first_run.run_id) is not None
    assert second.session_db_path != first.session_db_path

    rejected_requests: list[ProvisionRequest] = []

    def scratch_provision(request: ProvisionRequest) -> ProvisionedWorkspace:
        rejected_requests.append(request)
        return _scratch()

    rejecting = _manager(tmp_path, workspace_provisioner=scratch_provision)
    with pytest.raises(SessionManagerError) as conflict:
        rejecting.provision_entrypoint_session(session_id="session-reject", workspace_override=shared)
    assert conflict.value.code == "workspace_already_owned"
    rejected_dir = tmp_path / "state" / "sessions" / "session-reject"
    rejected_manifest = json.loads((rejected_dir / "manifest.json").read_text(encoding="utf-8"))
    assert rejected_manifest["status"] == "provisioning"
    rejected_db = SessionDatabase.open_existing(rejected_dir / "session.db", session_id="session-reject")
    assert rejected_db.get_run_binding(rejected_requests[0].run_id) is not None
    assert rejected_db.event_count() == 0


def test_degraded_managed_readiness_blocks_activation_and_retains_tombstone(tmp_path: Path) -> None:
    """C3 G3: cell-local readiness degradation cannot activate a managed session."""

    manager = _manager(tmp_path, workspace_preparer=_degraded_state)
    with pytest.raises(SessionManagerError) as refused:
        manager.provision_entrypoint_session(
            session_id="session-degraded",
            workspace_override=manager.workspace_root / "session-degraded",
        )

    assert refused.value.code == "workspace_not_ready"
    tombstone = manager.sessions_root / "session-degraded"
    manifest = json.loads((tombstone / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "provisioning"
    database = SessionDatabase.open_existing(tombstone / "session.db", session_id="session-degraded")
    run_id = next(manager.run_root.iterdir()).name
    assert database.get_run_binding(run_id) is not None
    assert database.event_count() == 0
    assert (manager.workspace_root / "session-degraded").is_dir()
