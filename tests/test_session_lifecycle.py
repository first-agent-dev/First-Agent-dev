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
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from fa.inner_loop.session_db import SessionDatabase, SessionDatabaseError
from fa.session.manager import SessionManager, SessionManagerError


def _manager(tmp_path: Path) -> SessionManager:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("source", encoding="utf-8")
    return SessionManager(
        state_root=tmp_path / "state",
        workspace_root=tmp_path / "workspaces",
        source_workspace=source,
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
