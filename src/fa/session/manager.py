"""Canonical session/workspace/manifest lifecycle boundary.

The manager owns logical session identity and run admission. Container shell
entrypoints may provision a filesystem workspace, but production CLI roots must
use this boundary for manifest, DB identity, and run binding decisions.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from re import fullmatch
from typing import Any
from uuid import uuid4

from fa.inner_loop.session_db import SessionDatabase, SessionDatabaseError

SESSION_SCHEMA_VERSION = "v1"
_SESSION_ID_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}"
_RUN_ID_PATTERN = _SESSION_ID_PATTERN
_REQUIRED_MANIFEST_KEYS = {
    "schema_version",
    "session_id",
    "workspace_path",
    "session_db_path",
    "created_at",
    "last_used_at",
    "status",
}


class SessionManagerError(RuntimeError):
    """Structured lifecycle failure surfaced before provider/tool execution."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class SessionContext:
    """Validated persistent session namespace."""

    session_id: str
    workspace_path: Path
    session_db_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class RunContext:
    """One newly admitted run inside a validated session."""

    run_id: str
    session_id: str
    workspace_path: Path
    session_db_path: Path
    run_log_dir: Path


class SessionManager:
    """Create/attach sessions and atomically admit fresh run identities."""

    def __init__(
        self,
        *,
        state_root: Path,
        workspace_root: Path,
        source_workspace: Path | None = None,
    ) -> None:
        self.state_root = Path(state_root).expanduser().resolve()
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self.source_workspace = Path(source_workspace).expanduser().resolve() if source_workspace is not None else None
        self.sessions_root = self.state_root / "sessions"
        self.run_root = self.state_root / "session-log"
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_session_id(value: str) -> str:
        if not isinstance(value, str) or fullmatch(_SESSION_ID_PATTERN, value) is None:
            raise SessionManagerError(
                "invalid_session_id",
                "session_id must match [A-Za-z0-9][A-Za-z0-9_.-]{0,127}",
            )
        return value

    @staticmethod
    def validate_run_id(value: str) -> str:
        if not isinstance(value, str) or fullmatch(_RUN_ID_PATTERN, value) is None:
            raise SessionManagerError(
                "invalid_run_id",
                "run_id must match [A-Za-z0-9][A-Za-z0-9_.-]{0,127}",
            )
        return value

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _under(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _session_dir(self, session_id: str) -> Path:
        return self.sessions_root / session_id

    def _manifest_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "manifest.json"

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def _read_manifest(self, path: Path, *, expected_session_id: str) -> dict[str, Any]:
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise SessionManagerError("manifest_corrupt", f"cannot read {path}: {exc}") from exc
        if not isinstance(data, dict) or not _REQUIRED_MANIFEST_KEYS.issubset(data):
            raise SessionManagerError("manifest_corrupt", f"missing required fields: {path}")
        if data.get("schema_version") != SESSION_SCHEMA_VERSION:
            raise SessionManagerError("manifest_unsupported", f"unsupported schema at {path}")
        if data.get("session_id") != expected_session_id:
            raise SessionManagerError("manifest_identity_mismatch", f"session ID mismatch at {path}")
        if data.get("status") != "active":
            raise SessionManagerError("session_not_active", f"session status is {data.get('status')!r}: {path}")
        workspace_path = self._resolve_checked_path(data.get("workspace_path"), self.workspace_root, "workspace")
        db_path = self._resolve_checked_path(data.get("session_db_path"), self.state_root, "session DB")
        expected_db = (self._session_dir(expected_session_id) / "session.db").resolve()
        if db_path != expected_db:
            raise SessionManagerError("manifest_path_mismatch", f"session DB path is not canonical: {path}")
        data["workspace_path"] = str(workspace_path)
        data["session_db_path"] = str(db_path)
        return data

    def _resolve_checked_path(self, raw: object, root: Path, label: str) -> Path:
        if not isinstance(raw, str) or not raw:
            raise SessionManagerError("manifest_corrupt", f"manifest {label} path is not a string")
        path = Path(raw).expanduser()
        try:
            resolved = path.resolve()
        except OSError as exc:
            raise SessionManagerError("path_invalid", f"cannot resolve {label} path {path}: {exc}") from exc
        if not self._under(resolved, root):
            raise SessionManagerError("path_escape", f"{label} path escapes approved root: {resolved}")
        return resolved

    def _validate_workspace_override(self, workspace_override: Path | None) -> Path | None:
        if workspace_override is None:
            return None
        try:
            path = Path(workspace_override).expanduser().resolve()
        except OSError as exc:
            raise SessionManagerError("workspace_invalid", str(exc)) from exc
        if not self._under(path, self.workspace_root):
            raise SessionManagerError("workspace_escape", f"workspace escapes approved root: {path}")
        if path.exists() and not path.is_dir():
            raise SessionManagerError("workspace_invalid", f"workspace is not a directory: {path}")
        return path

    def _check_reverse_workspace_ownership(self, workspace_path: Path, *, except_session_id: str | None) -> None:
        if not self.sessions_root.exists():
            return
        for manifest_path in sorted(self.sessions_root.glob("*/manifest.json")):
            owner_id = manifest_path.parent.name
            if except_session_id is not None and owner_id == except_session_id:
                continue
            data = self._read_manifest(manifest_path, expected_session_id=owner_id)
            owner_workspace = Path(str(data["workspace_path"])).resolve()
            if owner_workspace == workspace_path:
                raise SessionManagerError(
                    "workspace_already_owned",
                    f"workspace {workspace_path} already belongs to session {owner_id}",
                )

    def _provision_workspace(self, workspace_path: Path) -> bool:
        """Create a new workspace; return whether this method created it."""
        if workspace_path.exists():
            if not workspace_path.is_dir():
                raise SessionManagerError("workspace_invalid", f"workspace is not a directory: {workspace_path}")
            return False
        workspace_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self.source_workspace is not None:
                if not self.source_workspace.is_dir():
                    raise SessionManagerError("source_workspace_invalid", str(self.source_workspace))
                shutil.copytree(self.source_workspace, workspace_path, symlinks=True)
            else:
                workspace_path.mkdir(parents=False)
        except SessionManagerError:
            raise
        except OSError as exc:
            raise SessionManagerError("workspace_provision_failed", f"{workspace_path}: {exc}") from exc
        return True

    def _manifest_payload(
        self,
        *,
        session_id: str,
        workspace_path: Path,
        db_path: Path,
        created_at: str,
        last_used_at: str,
        status: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": SESSION_SCHEMA_VERSION,
            "session_id": session_id,
            "workspace_path": str(workspace_path),
            "session_db_path": str(db_path),
            "created_at": created_at,
            "last_used_at": last_used_at,
            "status": status,
        }

    def _new_session(self, session_id: str, workspace_override: Path | None) -> SessionContext:
        session_dir = self._session_dir(session_id)
        if session_dir.exists():
            raise SessionManagerError("session_exists", f"session namespace already exists: {session_id}")
        workspace_path = workspace_override or (self.workspace_root / session_id).resolve()
        if not self._under(workspace_path, self.workspace_root):
            raise SessionManagerError("workspace_escape", f"workspace escapes approved root: {workspace_path}")
        self._check_reverse_workspace_ownership(workspace_path, except_session_id=None)
        db_path = (session_dir / "session.db").resolve()
        created_at = self._now()
        session_dir.mkdir(parents=True, exist_ok=False)
        # Record ownership before provisioning so a partial copytree failure
        # is still cleaned up; an explicit pre-existing workspace remains
        # caller-owned and is never removed by this manager.
        workspace_created = not workspace_path.exists()
        try:
            self._atomic_write_json(
                session_dir / "manifest.json",
                self._manifest_payload(
                    session_id=session_id,
                    workspace_path=workspace_path,
                    db_path=db_path,
                    created_at=created_at,
                    last_used_at=created_at,
                    status="provisioning",
                ),
            )
            self._provision_workspace(workspace_path)
            SessionDatabase(db_path, session_id=session_id)
            self._atomic_write_json(
                session_dir / "manifest.json",
                self._manifest_payload(
                    session_id=session_id,
                    workspace_path=workspace_path,
                    db_path=db_path,
                    created_at=created_at,
                    last_used_at=created_at,
                    status="active",
                ),
            )
        except SessionDatabaseError as exc:
            raise SessionManagerError(exc.code, str(exc)) from exc
        except SessionManagerError:
            raise
        except Exception as exc:
            raise SessionManagerError("session_provision_failed", str(exc)) from exc
        except BaseException:
            raise
        finally:
            # Any exception above leaves no ambiguous active namespace. An
            # explicit existing workspace is never removed by this cleanup.
            manifest = session_dir / "manifest.json"
            try:
                active = (
                    manifest.is_file() and json.loads(manifest.read_text(encoding="utf-8")).get("status") == "active"
                )
            except (OSError, json.JSONDecodeError):
                active = False
            if not active and session_dir.exists():
                shutil.rmtree(session_dir, ignore_errors=True)
                if workspace_created and workspace_path.exists():
                    shutil.rmtree(workspace_path, ignore_errors=True)
        return SessionContext(session_id, workspace_path, db_path, session_dir / "manifest.json")

    def _attach_session(self, session_id: str, workspace_override: Path | None) -> SessionContext:
        session_dir = self._session_dir(session_id)
        manifest_path = session_dir / "manifest.json"
        if not manifest_path.is_file():
            raise SessionManagerError("unknown_session", f"session does not exist: {session_id}")
        data = self._read_manifest(manifest_path, expected_session_id=session_id)
        manifest_workspace = Path(str(data["workspace_path"])).resolve()
        if workspace_override is not None and workspace_override != manifest_workspace:
            raise SessionManagerError(
                "workspace_mismatch",
                f"requested {workspace_override}, manifest selects {manifest_workspace}",
            )
        if not manifest_workspace.is_dir():
            raise SessionManagerError("workspace_missing", f"workspace does not exist: {manifest_workspace}")
        db_path = Path(str(data["session_db_path"])).resolve()
        try:
            SessionDatabase.open_existing(db_path, session_id=session_id)
        except SessionDatabaseError as exc:
            raise SessionManagerError(exc.code, str(exc)) from exc
        now = self._now()
        data["last_used_at"] = now
        self._atomic_write_json(manifest_path, data)
        return SessionContext(session_id, manifest_workspace, db_path, manifest_path)

    def provision_entrypoint_session(self, *, session_id: str, workspace_override: Path) -> SessionContext:
        """Provision or attach the session selected by the container adapter.

        This is an internal entrypoint handoff, not a relaxed public attach
        rule: the shell has already selected the workspace, while this method
        remains the sole owner of the manifest and session DB creation.
        """
        validated = self.validate_session_id(session_id)
        override = self._validate_workspace_override(workspace_override)
        if override is None:
            raise SessionManagerError("workspace_required", "entrypoint provisioning requires a workspace")
        manifest_path = self._manifest_path(validated)
        if manifest_path.is_file():
            return self._attach_session(validated, override)
        return self._new_session(validated, override)

    def create_or_attach_session(
        self,
        *,
        session_id: str | None,
        workspace_override: Path | None,
    ) -> SessionContext:
        """Create a new session or attach to an existing explicit session."""
        override = self._validate_workspace_override(workspace_override)
        if session_id is not None:
            validated = self.validate_session_id(session_id)
            return self._attach_session(validated, override)
        for _ in range(5):
            generated = f"session-{uuid4().hex}"
            if not self._session_dir(generated).exists():
                return self._new_session(generated, override)
        raise SessionManagerError("session_id_generation_failed", "could not allocate a free session namespace")

    def _run_id_claimed_elsewhere(self, run_id: str, *, current_session_id: str) -> bool:
        run_dir = self.run_root / run_id
        if run_dir.exists():
            return True
        for manifest_path in sorted(self.sessions_root.glob("*/manifest.json")):
            owner_id = manifest_path.parent.name
            if owner_id == current_session_id:
                continue
            data = self._read_manifest(manifest_path, expected_session_id=owner_id)
            db_path = Path(str(data["session_db_path"]))
            try:
                db = SessionDatabase.open_existing(db_path, session_id=owner_id)
            except SessionDatabaseError as exc:
                raise SessionManagerError(exc.code, str(exc)) from exc
            if db.get_run_binding(run_id) is not None:
                return True
        return False

    def begin_run(self, session: SessionContext, requested_run_id: str | None) -> RunContext:
        """Create a run artifact namespace and atomically bind its ID to session."""
        if session.manifest_path.resolve() != self._manifest_path(session.session_id).resolve():
            raise SessionManagerError("session_context_mismatch", "context does not belong to this manager")
        if requested_run_id is not None and requested_run_id != "":
            run_id = self.validate_run_id(requested_run_id)
            candidate_ids = [run_id]
        else:
            candidate_ids = [f"run-{uuid4().hex}" for _ in range(5)]
        db = SessionDatabase.open_existing(session.session_db_path, session_id=session.session_id)
        for run_id in candidate_ids:
            if self._run_id_claimed_elsewhere(run_id, current_session_id=session.session_id):
                if requested_run_id:
                    raise SessionManagerError("run_id_reused", f"run namespace already exists: {run_id}")
                continue
            run_log_dir = self.run_root / run_id
            try:
                run_log_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError as exc:
                if requested_run_id:
                    raise SessionManagerError("run_id_reused", f"run namespace already exists: {run_id}") from exc
                continue
            try:
                db.reserve_run_binding(run_id, self._now())
            except SessionDatabaseError as exc:
                run_log_dir.rmdir()
                if exc.code == "run_id_reused" and not requested_run_id:
                    continue
                raise SessionManagerError(exc.code, str(exc)) from exc
            return RunContext(
                run_id=run_id,
                session_id=session.session_id,
                workspace_path=session.workspace_path,
                session_db_path=session.session_db_path,
                run_log_dir=run_log_dir,
            )
        raise SessionManagerError("run_id_generation_failed", "could not allocate a free run namespace")


__all__ = ["RunContext", "SessionContext", "SessionManager", "SessionManagerError"]


def _main() -> int:
    parser = argparse.ArgumentParser(prog="python -m fa.session.manager")
    subparsers = parser.add_subparsers(dest="command", required=True)
    provision = subparsers.add_parser("provision")
    provision.add_argument("--state-root", type=Path, required=True)
    provision.add_argument("--workspace-root", type=Path, required=True)
    provision.add_argument("--session-id", required=True)
    provision.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    if args.command != "provision":
        return 2
    manager = SessionManager(state_root=args.state_root, workspace_root=args.workspace_root)
    try:
        context = manager.provision_entrypoint_session(
            session_id=args.session_id,
            workspace_override=args.workspace,
        )
    except SessionManagerError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"session_id": context.session_id, "manifest_path": str(context.manifest_path)}))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by shell boundary tests
    raise SystemExit(_main())
