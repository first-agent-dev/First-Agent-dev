"""The one managed-execution composition a controller run can reach (CT116).

Nothing here mints authority. The endpoint is one string in the file `fa` already
reads (``DEFAULT_CONFIG_PATH``), validated by the same reader the supervisor uses;
the workspace identity comes from the supervisor's own ``register_workspace``; the
writer grant comes from one ``acquire_writer``. When any of those is absent or
refused the composition returns ``None`` and the controller fails closed
(CT115) — there is no host-path fallback, no environment variable, no endpoint
file and no default socket.

This is the only module in ``src/`` that constructs ``ExecutionClient``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fa.config import DEFAULT_CONFIG_PATH, load_execution_config
from fa.execution.client import (
    ExecutionClient,
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
    PlanPublication,
)
from fa.execution.provisioning import ERROR_CODES
from fa.execution.service import ServiceConfig, read_config_file
from fa.execution.types import ExecutionContractError, GrantReply, NamespaceRef, Operation, _hex_id
from fa.inner_loop.plan_admission import PlanRef, PlanSnapshot
from fa.session.manager import RunContext, SessionManagerError
from fa.session.provisioning import ProvisionedWorkspace, ProvisionMode, ProvisionRequest

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionBinding:
    """One run's managed identity: who it is, and which registered bytes it owns.

    Data only — no capability and no revision (CT116). The grant belongs to the
    client, and a revision is whatever the authority reports per operation, so a
    stale copy cannot be mistaken for authority.
    """

    namespace: NamespaceRef
    workspace_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, NamespaceRef):
            raise ExecutionContractError
        _hex_id(self.workspace_id, "ws-")


@dataclass(frozen=True)
class ManagedExecution:
    """One run's client, binding and the single writer grant it holds.

    The writer is acquired once per run, because a second acquisition of the same
    workspace is ``WORKSPACE_BUSY`` by construction (``workspace.py:1326-1338``)
    and holding it makes the run's publications and its host-side stages mutually
    exclusive instead of merely polite.
    """

    client: ExecutionClient
    binding: ExecutionBinding
    grant: GrantReply

    def publish_plan(
        self, source: PlanSnapshot, candidate: PlanSnapshot, *, deadline: float | None = None
    ) -> PlanPublication:
        return self.client.publish_plan(self.binding, source, candidate, grant=self.grant, deadline=deadline)

    def close(self, *, deadline: float | None = None) -> bool:
        """Release the writer this run holds; ``False`` when the release was not confirmed.

        A lost release is reported, never retried and never replaced by a local
        assumption: the authority keeps the workspace ``OWNED`` and recovery owns
        it from there.
        """
        try:
            self.client.request(
                Operation.RELEASE,
                request_id=uuid4().hex,
                namespace=self.binding.namespace,
                view=None,
                grant=self.grant,
                payload={},
                deadline=deadline,
            )
        except (ExecutionRejectedError, ExecutionUnavailableError):
            return False
        except ExecutionUncertainError:
            # A lost release leaves the workspace OWNED with no owner: say so and
            # let recovery decide, rather than pretending the writer is settled.
            _logger.warning("managed execution could not confirm its writer release")
            return False
        return True


class BoundPlanPublisher:
    """The controller's ``CandidatePlanPublisher`` port over a managed execution.

    It holds no token: the grant lives in ``managed`` and the binding is the one
    proved at registration, so this adapter cannot outlive its authority.
    """

    def __init__(self, managed: ManagedExecution, binding: ExecutionBinding) -> None:
        if not isinstance(managed, ManagedExecution) or not isinstance(binding, ExecutionBinding):
            raise ExecutionContractError
        if binding != managed.binding:
            raise ExecutionContractError  # One managed execution publishes for its own run only.
        self._managed = managed
        self._binding = binding

    def publish_candidate(
        self, source: PlanSnapshot, candidate: PlanSnapshot, *, deadline: float | None = None
    ) -> PlanRef:
        publication = self._managed.publish_plan(source, candidate, deadline=deadline)
        return publication.plan_ref


def managed_execution_for_run(
    run_context: RunContext | None,
    *,
    config_path: Path | None = None,
    deadline: float | None = None,
) -> ManagedExecution | None:
    """Bind one run to the managed execution, or ``None`` when there is none.

    ``run_context`` alone carries the run identity (``session_id`` + ``run_id`` is
    the namespace) and the workspace path, so no second context is threaded and
    the two cannot disagree.

    ``None`` covers every honest absence: a local namespace with no run context
    (the legacy ``run_id``-only path), no ``execution:`` block, an unreadable or
    invalid operator file, a uid outside ``controller_uids``, a workspace that
    escapes every approved root, and a supervisor that refuses registration or the
    writer grant. Returning a half-built execution instead would move the failure
    to the first publish, where the reason is harder to see.
    """
    if run_context is None:
        return None  # A local namespace owns no workspace, so it has no managed one.
    if not isinstance(run_context, RunContext):
        raise ExecutionContractError
    config = _service_config(config_path)
    if config is None:
        return None
    client = _client_for(config)
    if client is None:
        return None
    rooted = _root_binding(config, run_context.workspace_path)
    if rooted is None:
        return None
    root_id, relative_root = rooted
    namespace = NamespaceRef(run_context.session_id, run_context.run_id)
    try:
        registered = client.request(
            Operation.REGISTER_WORKSPACE,
            request_id=uuid4().hex,
            namespace=namespace,
            view=None,
            grant=None,
            payload={"root_id": root_id, "relative_root": relative_root, "create": False, "input_id": None},
            deadline=deadline,
        )
        acquired = client.request(
            Operation.ACQUIRE_WRITER,
            request_id=uuid4().hex,
            namespace=namespace,
            view=None,
            grant=None,
            payload={"workspace_id": registered["workspace_id"]},
            deadline=deadline,
        )
    except (ExecutionRejectedError, ExecutionUnavailableError):
        return None
    grant = GrantReply(
        Operation.ACQUIRE_WRITER,
        acquired["capability"],
        None,
        acquired["generation"],
        acquired["revision_id"],
    )
    binding = ExecutionBinding(namespace, str(registered["workspace_id"]))
    return ManagedExecution(client, binding, grant)


@dataclass(frozen=True)
class ClientWorkspaceProvisioner:
    """CT116's second port: the manager's provisioning ask, answered over the wire.

    ``SessionManager`` calls this once per newly created session, so the ask is one
    ``register_workspace{create:false}`` and the answer is the identity the authority
    already holds — the same one publication uses, because both resolve the
    workspace against the same ``approved_roots`` with ``_root_binding``.

    ``tree_sha256`` is ``None``: the wire answer carries two fields (``service.py:591``)
    and ``ProvisionedWorkspace`` now accepts a registered result without the hash.

    A new root is a typed blocked disposition, exactly as in the in-process adapter:
    the only registration shape this port sends is ``create:false``, and minting
    canonical bytes is the SLICE3 publication join's work.
    """

    config: ServiceConfig
    client: ExecutionClient

    def __post_init__(self) -> None:
        if not isinstance(self.config, ServiceConfig) or not isinstance(self.client, ExecutionClient):
            raise ExecutionContractError

    def __call__(self, request: ProvisionRequest) -> ProvisionedWorkspace:
        if not isinstance(request, ProvisionRequest):
            raise SessionManagerError("workspace_invalid", "provisioning requires a ProvisionRequest")
        if request.mode is ProvisionMode.PROVISION:
            raise SessionManagerError(
                "provisioning_unavailable",
                "managed new-root provisioning requires the publication join (SLICE3)",
            )
        if request.mode is not ProvisionMode.REUSE:
            raise SessionManagerError("workspace_invalid", f"unknown provisioning mode: {request.mode}")
        workspace = Path(request.workspace_path)
        if not workspace.is_dir():
            raise SessionManagerError("workspace_missing", f"workspace does not exist: {workspace}")
        rooted = _root_binding(self.config, workspace)
        if rooted is None:
            raise SessionManagerError("workspace_escape", f"workspace escapes every approved root: {workspace}")
        root_id, relative_root = rooted
        try:
            namespace = NamespaceRef(request.session_id, request.run_id)
        except ExecutionContractError:
            message = "provisioning requires a valid session/run identity"
            raise SessionManagerError("workspace_invalid", message) from None
        try:
            registered = self.client.request(
                Operation.REGISTER_WORKSPACE,
                request_id=uuid4().hex,
                namespace=namespace,
                view=None,
                grant=None,
                payload={"root_id": root_id, "relative_root": relative_root, "create": False, "input_id": None},
                deadline=request.deadline,
            )
        except (ExecutionRejectedError, ExecutionUncertainError, ExecutionUnavailableError) as error:
            code = ERROR_CODES.get(str(getattr(error, "code", "")), "workspace_provision_failed")
            raise SessionManagerError(code, f"managed provisioning refused: {error.code}") from None
        except OSError as error:
            raise SessionManagerError("workspace_provision_failed", f"{workspace}: {error}") from None
        workspace_id = registered.get("workspace_id")
        revision_id = registered.get("revision_id")
        if not isinstance(workspace_id, str) or not isinstance(revision_id, str):
            raise SessionManagerError("workspace_corrupt", "registration returned an incomplete identity")
        try:
            return ProvisionedWorkspace(
                registered=True,
                workspace_id=workspace_id,
                revision_id=revision_id,
                tree_sha256=None,
            )
        except ValueError:
            raise SessionManagerError("workspace_corrupt", "registration returned an invalid identity") from None


def client_workspace_provisioner(*, config_path: Path | None = None) -> ClientWorkspaceProvisioner | None:
    """The provisioner ``fa`` injects into the session manager, or ``None``.

    ``None`` means the operator configured no execution service: the session layer
    then keeps its pre-cutover host path, which is the behaviour every command has
    today. One config read, one uid rule, one client builder — the same ones the
    run's publication uses.
    """
    config = _service_config(config_path)
    if config is None:
        return None
    client = _client_for(config)
    if client is None:
        return None
    return ClientWorkspaceProvisioner(config=config, client=client)


def _client_for(config: ServiceConfig) -> ExecutionClient | None:
    """The one client builder: a controller the authority does not list gets none."""
    uid = os.getuid()
    if uid not in config.controller_uids:
        return None
    return ExecutionClient(config.socket_path, server_uid=uid, rpc_timeout_ms=config.rpc_timeout_ms)


def _service_config(config_path: Path | None) -> ServiceConfig | None:
    """The validated operator config, or ``None`` — the file both processes read."""
    path = DEFAULT_CONFIG_PATH if config_path is None else Path(config_path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    service_config = load_execution_config(text)
    if service_config is None:
        return None
    try:
        return read_config_file(service_config)
    except (ExecutionContractError, OSError):
        return None


def _root_binding(config: ServiceConfig, workspace_path: Path) -> tuple[str, str] | None:
    """Map a workspace onto one approved root: the ids the authority already owns."""
    try:
        workspace = workspace_path.expanduser().resolve(strict=True)
    except OSError:
        return None
    for root_id, root in config.approved_roots.items():
        try:
            relative = workspace.relative_to(Path(root).expanduser().resolve(strict=True))
        except (OSError, ValueError):
            continue
        if not relative.parts:
            return None  # The root itself is not a workspace.
        return root_id, relative.as_posix()
    return None


__all__ = [
    "BoundPlanPublisher",
    "ExecutionBinding",
    "ManagedExecution",
    "managed_execution_for_run",
]
