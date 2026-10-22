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
     G2 new-root provisioning without the SLICE3 publication join is the typed
        BLOCKED disposition `provisioning_unavailable`
     G3 not-READY readiness blocks new session AND attach (`workspace_not_ready`)
     G4 a registered result is never an rmtree target after a later failure
     G5 registered reference to another session's workspace is permitted without
        transferring its DB/run/manifest; an unregistered conflict stays rejected
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from fa.inner_loop.session_db import SessionDatabase, SessionDatabaseError
from fa.session.manager import SessionManager, SessionManagerError
from fa.session.provisioning import ProvisionedWorkspace, ProvisionMode, ProvisionRequest
from fa.workspace_bootstrap import ReadyState, ReadyStatus


def _ready_state(workspace: Path) -> ReadyState:
    return ReadyState(
        status=ReadyStatus.READY,
        fingerprint="sha256:test",
        reason_code="ready_fast_path",
        log_path=workspace / ".fa" / "bootstrap.log",
        repaired=False,
        elapsed_ms=1,
    )


def _degraded_state(workspace: Path) -> ReadyState:
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


def _manager(
    tmp_path: Path,
    *,
    workspace_preparer: Callable[[Path], ReadyState] | None = None,
    workspace_provisioner: Callable[[ProvisionRequest], ProvisionedWorkspace] | None = None,
) -> SessionManager:
    source = tmp_path / "source"
    source.mkdir(exist_ok=True)
    (source / "README.md").write_text("source", encoding="utf-8")
    return SessionManager(
        state_root=tmp_path / "state",
        workspace_root=tmp_path / "workspaces",
        source_workspace=source,
        workspace_preparer=workspace_preparer,
        workspace_provisioner=workspace_provisioner,
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

    observed: list[tuple[Path, bool, str]] = []

    def prepare(workspace: Path) -> ReadyState:
        manifests = list((tmp_path / "state" / "sessions").glob("*/manifest.json"))
        assert len(manifests) == 1
        manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
        db_path = Path(str(manifest["session_db_path"]))
        observed.append((workspace, db_path.is_file(), str(manifest["status"])))
        return _ready_state(workspace)

    manager = _manager(tmp_path, workspace_preparer=prepare)
    created = manager.create_or_attach_session(session_id=None, workspace_override=None)

    assert observed == [(created.workspace_path, True, "provisioning")]
    manifest = json.loads(created.manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "active"
    assert "bootstrap" not in manifest


def test_attach_prepares_after_db_validation_before_last_used_write(tmp_path: Path) -> None:
    """C1 B: attach readiness precedes the only manifest mutation."""

    creator = _manager(tmp_path)
    created = creator.create_or_attach_session(session_id=None, workspace_override=None)
    before = json.loads(created.manifest_path.read_text(encoding="utf-8"))
    observed: list[tuple[Path, str]] = []

    def prepare(workspace: Path) -> ReadyState:
        current = json.loads(created.manifest_path.read_text(encoding="utf-8"))
        observed.append((workspace, str(current["last_used_at"])))
        return _ready_state(workspace)

    manager = SessionManager(
        state_root=tmp_path / "state",
        workspace_root=tmp_path / "workspaces",
        source_workspace=tmp_path / "source",
        workspace_preparer=prepare,
    )
    attached = manager.create_or_attach_session(
        session_id=created.session_id,
        workspace_override=created.workspace_path,
    )

    assert attached.workspace_path == created.workspace_path
    assert observed == [(created.workspace_path, str(before["last_used_at"]))]
    after = json.loads(created.manifest_path.read_text(encoding="utf-8"))
    assert after["status"] == "active"


def test_unexpected_new_session_preparer_failure_rolls_back_owned_state(tmp_path: Path) -> None:
    """C3 A: callback contract breach cannot publish an active namespace."""

    def fail(_workspace: Path) -> ReadyState:
        raise RuntimeError("preparer contract breach")

    manager = _manager(tmp_path, workspace_preparer=fail)

    with pytest.raises(SessionManagerError, match="session_provision_failed"):
        manager.create_or_attach_session(session_id=None, workspace_override=None)

    assert list(manager.sessions_root.iterdir()) == []
    assert list(manager.workspace_root.iterdir()) == []


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

    with pytest.raises(SessionManagerError, match="workspace_already_owned") as exc:
        manager.create_or_attach_session(session_id=None, workspace_override=created.workspace_path)
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


def test_partial_workspace_provision_is_removed_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C3: failed copytree cannot leave an unowned partial workspace."""
    manager = _manager(tmp_path)

    def partial_copy(_source: Path, destination: Path, *, symlinks: bool) -> None:
        destination.mkdir(parents=True)
        (destination / "partial.txt").write_text("partial", encoding="utf-8")
        raise OSError("copy interrupted")

    monkeypatch.setattr("fa.session.manager.shutil.copytree", partial_copy)
    with pytest.raises(SessionManagerError, match="workspace_provision_failed"):
        manager.create_or_attach_session(session_id=None, workspace_override=None)

    assert not list(manager.sessions_root.iterdir())
    assert not list(manager.workspace_root.iterdir())


def test_managed_provisioner_owns_workspace_bytes_and_receives_a_real_run_namespace(tmp_path: Path) -> None:
    """C1 G1: the provisioner runs instead of host provisioning, after DB+run admission."""

    observed: dict[str, object] = {}

    def provision(request: ProvisionRequest) -> ProvisionedWorkspace:
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
        return _scratch()

    manager = _manager(tmp_path, workspace_provisioner=provision)
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
    assert (workspace / "supervisor.txt").read_text(encoding="utf-8") == "own bytes"
    assert not (workspace / "README.md").exists(), "host provisioning must not run when the provisioner is injected"
    assert json.loads(session.manifest_path.read_text(encoding="utf-8"))["status"] == "active"


def test_new_root_provisioning_without_publication_is_a_typed_blocked_disposition(tmp_path: Path) -> None:
    """C3 G2: no host-Git fallback; the new-root leg is explicitly BLOCKED until SLICE3."""

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
    assert not (tmp_path / "state" / "sessions" / "session-fresh").exists()
    # The provisioning run reservation survives rollback: the id is never reusable.
    assert len(list((tmp_path / "state" / "session-log").iterdir())) == 1


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

    new_manager = _manager(tmp_path, workspace_preparer=_degraded_state, workspace_provisioner=_registers)
    with pytest.raises(SessionManagerError) as new_error:
        new_manager.create_or_attach_session(session_id=None, workspace_override=None)
    assert new_error.value.code == "workspace_not_ready"
    assert len(list((tmp_path / "state" / "sessions").iterdir())) == 1


def test_registered_workspace_bytes_survive_a_later_session_failure(tmp_path: Path) -> None:
    """C1 G4: only uncommitted scratch is cleanup-eligible, never registered bytes."""

    workspace = tmp_path / "workspaces" / "registered"
    workspace.mkdir(parents=True)
    (workspace / "canonical.txt").write_text("registered bytes", encoding="utf-8")

    def provision(_request: ProvisionRequest) -> ProvisionedWorkspace:
        return _registered("ws-1", "rev-1", "0" * 64)

    def fail(_workspace: Path) -> ReadyState:
        raise RuntimeError("readiness contract breach")

    manager = _manager(tmp_path, workspace_preparer=fail, workspace_provisioner=provision)
    with pytest.raises(SessionManagerError, match="session_provision_failed"):
        manager.provision_entrypoint_session(session_id="session-registered", workspace_override=workspace)

    assert (workspace / "canonical.txt").read_text(encoding="utf-8") == "registered bytes"
    assert not (tmp_path / "state" / "sessions" / "session-registered").exists()


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

    def scratch_provision(_request: ProvisionRequest) -> ProvisionedWorkspace:
        return _scratch()

    rejecting = _manager(tmp_path, workspace_provisioner=scratch_provision)
    with pytest.raises(SessionManagerError) as conflict:
        rejecting.provision_entrypoint_session(session_id="session-reject", workspace_override=shared)
    assert conflict.value.code == "workspace_already_owned"
    assert not (tmp_path / "state" / "sessions" / "session-reject").exists()


def test_readiness_degradation_without_a_managed_provisioner_stays_non_blocking(tmp_path: Path) -> None:
    """C3 G3b: pre-cutover host composition reports readiness but does not block.

    SLICE4 STEP2 injects the provisioner and therefore removes this path; the
    case exists so that the transition is explicit rather than accidental.
    """

    manager = _manager(tmp_path, workspace_preparer=_degraded_state)
    session = manager.create_or_attach_session(session_id=None, workspace_override=None)

    assert json.loads(session.manifest_path.read_text(encoding="utf-8"))["status"] == "active"
