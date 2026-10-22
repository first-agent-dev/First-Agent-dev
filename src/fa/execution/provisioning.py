"""Supervisor-backed provisioning adapter consumed by ``SessionManager`` (E263).

The manager decides identity and ordering; this adapter is the only place that
turns a provisioning ask into supervisor ownership of canonical bytes. It reuses
the existing ``WorkspaceAuthority.register_existing`` path (the same one that
performs the R0 import) instead of adding a second registration route, and it
never creates canonical bytes itself: the publication-dependent new-root leg is
the SLICE3 join, so a new-root ask is a typed BLOCKED disposition today.

Errors are translated into the manager's closed vocabulary so no execution-layer
type escapes into the session boundary, and an unusable identity is never
reported as success.
"""

from __future__ import annotations

import re
from pathlib import Path

from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import ExecutionContractError, NamespaceRef
from fa.execution.workspace import WorkspaceAuthority
from fa.session.manager import SessionManagerError
from fa.session.provisioning import ProvisionedWorkspace, ProvisionMode, ProvisionRequest

_SHA256 = re.compile(r"[0-9a-f]{64}")

#: Closed translation of supervisor refusals into session lifecycle codes.
_ERROR_CODES = {
    "CORRUPT_STATE": "workspace_corrupt",
    "UNAUTHORIZED": "workspace_denied",
    "PATH_DENIED": "workspace_denied",
    "EXECUTION_UNKNOWN": "workspace_denied",
}


class ManagedProvisioner:
    """Register quiescent existing bytes for one admitted session reference."""

    __slots__ = ("_approved_root", "_authority", "_peer", "_root_id")

    def __init__(
        self,
        authority: WorkspaceAuthority,
        *,
        peer: PeerIdentity,
        root_id: str,
        approved_root: Path,
    ) -> None:
        if not isinstance(authority, WorkspaceAuthority) or not isinstance(peer, PeerIdentity):
            raise ExecutionContractError
        if not isinstance(root_id, str) or not root_id:
            raise ExecutionContractError
        if not isinstance(approved_root, Path) or not approved_root.is_absolute():
            raise ExecutionContractError
        self._authority = authority
        self._peer = peer
        self._root_id = root_id
        self._approved_root = approved_root.resolve()

    def __call__(self, request: ProvisionRequest) -> ProvisionedWorkspace:
        if not isinstance(request, ProvisionRequest):
            raise SessionManagerError("workspace_invalid", "provisioning requires a ProvisionRequest")
        if request.mode is ProvisionMode.PROVISION:
            # No host-Git fallback and no half-registered root: the supervisor
            # acquires new bytes only through the SLICE3 publication join.
            raise SessionManagerError(
                "provisioning_unavailable",
                "managed new-root provisioning requires the publication join (SLICE3)",
            )
        if request.mode is not ProvisionMode.REUSE:
            raise SessionManagerError("workspace_invalid", f"unknown provisioning mode: {request.mode}")

        workspace = Path(request.workspace_path)
        if not workspace.is_dir():
            raise SessionManagerError("workspace_missing", f"workspace does not exist: {workspace}")
        try:
            relative = workspace.resolve().relative_to(self._approved_root)
        except ValueError:
            raise SessionManagerError("workspace_escape", f"workspace escapes approved root: {workspace}") from None
        if not relative.parts:
            raise SessionManagerError("workspace_escape", f"approved root itself is not a workspace: {workspace}")

        try:
            namespace = NamespaceRef(request.session_id, request.run_id)
        except ExecutionContractError:
            message = "provisioning requires a valid session/run identity"
            raise SessionManagerError("workspace_invalid", message) from None

        try:
            result = self._authority.register_existing(
                self._peer,
                namespace,
                root_id=self._root_id,
                relative_root=relative.as_posix(),
                deadline=request.deadline,
            )
        except SupervisorError as error:
            raise SessionManagerError(
                _ERROR_CODES.get(error.code, "workspace_provision_failed"),
                f"managed provisioning refused: {error.code}",
            ) from None
        except OSError as error:
            raise SessionManagerError("workspace_provision_failed", f"{workspace}: {error}") from None

        workspace_id = result.get("workspace_id")
        revision_id = result.get("revision_id")
        tree_sha256 = result.get("tree_sha256")
        if (
            not isinstance(workspace_id, str)
            or not workspace_id
            or not isinstance(revision_id, str)
            or not revision_id
            or not isinstance(tree_sha256, str)
            or _SHA256.fullmatch(tree_sha256) is None
        ):
            raise SessionManagerError("workspace_corrupt", "registration returned an incomplete identity")
        try:
            return ProvisionedWorkspace(
                registered=True,
                workspace_id=workspace_id,
                revision_id=revision_id,
                tree_sha256=tree_sha256,
            )
        except ValueError:
            raise SessionManagerError("workspace_corrupt", "registration returned an invalid identity") from None


__all__ = ["ManagedProvisioner"]
