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
from typing import Any
from uuid import uuid4

from fa.config import DEFAULT_CONFIG_PATH, ExecutionConfigError, load_execution_config
from fa.execution.client import (
    ExecutionClient,
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
    PlanPublication,
    StagePublication,
)
from fa.execution.provisioning import ERROR_CODES
from fa.execution.service import ServiceConfig, read_config_file
from fa.execution.types import (
    Access,
    ExecutionContractError,
    GrantReply,
    NamespaceRef,
    Operation,
    ViewPurpose,
    _hex_id,
)
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

    def open_view(
        self,
        *,
        access: Access,
        purpose: ViewPurpose,
        base_revision: str | None,
        plan_ref: PlanRef | None = None,
        deadline: float | None = None,
    ) -> GrantReply:
        """Open a purpose-bound view for this run, under the run's own writer grant.

        This is the binding point the SLICE4 STEP2 cutover consumes: a stage view
        whose writes the file tools reach through ``ClientWorkspacePort``. Kept on
        the composition, not at the call site, so the controller never spells a
        wire payload itself and a second view-opening path cannot appear.
        """
        return self.client.open_view(
            self.binding,
            access=access,
            purpose=purpose,
            base_revision=base_revision,
            plan_ref=plan_ref,
            grant=self.grant,
            deadline=deadline,
        )

    def publish_stage(self, grant: GrantReply, *, deadline: float | None = None) -> StagePublication:
        """Commit the stage view ``grant`` opened; raise when the commit is unproved.

        A stage whose bytes are not committed may not be followed by verification or
        repair, so this reports by raising rather than by a boolean: there is no
        degraded continuation that would be honest. The run keeps its writer — the
        next stage opens its own view over the revision this call produced.
        """
        if not isinstance(grant, GrantReply) or grant.view_ref is None:
            raise ExecutionContractError
        return self.client.publish_stage(self.binding.namespace, view=grant.view_ref, grant=grant, deadline=deadline)

    def stop_view(self, grant: GrantReply, *, deadline: float | None = None) -> bool:
        """End the view ``grant`` opened; ``False`` when its end was not proved.

        Same contract as :meth:`close`: an unproved end is reported once and never
        turned into a local assumption, because the authority still owns whatever
        the view holds.
        """
        if not isinstance(grant, GrantReply) or grant.view_ref is None:
            raise ExecutionContractError
        view = grant.view_ref
        if self.client.stop_view(self.binding.namespace, view=view, grant=grant, deadline=deadline):
            return True
        _logger.warning(
            "managed execution: view %s was not confirmed closed for %s",
            view.view_id,
            self.binding.workspace_id,
        )
        return False

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
        except (ExecutionRejectedError, ExecutionUnavailableError, ExecutionUncertainError) as error:
            # Every unconfirmed release means the same operational fact - this run's
            # writer may still be held - and the operator can only act on it if it is
            # said out loud. Retrying is still wrong: a refused or lost RELEASE is
            # the authority's answer, not a transport hiccup to paper over.
            _logger.warning(
                "managed execution: writer release not confirmed for %s (%s)",
                self.binding.workspace_id,
                getattr(error, "code", None) or type(error).__name__,
            )
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


def _control(
    client: ExecutionClient,
    operation: Operation,
    *,
    namespace: NamespaceRef,
    payload: dict[str, object],
    deadline: float | None,
) -> dict[str, object]:
    """One control call whose lost reply is replayed once under the SAME request id.

    The authority journals an operation by request id and answers a repeat from its
    completed-reply cache, so a replay is a *reconciliation*, not a second effect:
    a writer grant that was issued against a lost frame comes back as the same
    grant. A fresh id would instead meet ``WORKSPACE_BUSY`` - the run would be
    refused with a reason that is not true (nobody else holds it; this run does and
    cannot prove it). What a replay must never do is invent a grant: if the
    authority cannot answer, that surfaces as the second attempt's own error.
    """
    request_id = uuid4().hex
    call: dict[str, Any] = {
        "request_id": request_id,
        "namespace": namespace,
        "view": None,
        "grant": None,
        "payload": payload,
        "deadline": deadline,
    }
    try:
        return client.request(operation, **call)
    except ExecutionUncertainError:
        _logger.warning(
            "managed execution: %s reply lost for %s; replaying request %s",
            operation.value,
            namespace.run_id,
            request_id,
        )
        return client.request(operation, **call)


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
        registered = _control(
            client,
            Operation.REGISTER_WORKSPACE,
            namespace=namespace,
            payload={"root_id": root_id, "relative_root": relative_root, "create": False, "input_id": None},
            deadline=deadline,
        )
    except (ExecutionRejectedError, ExecutionUnavailableError, ExecutionUncertainError):
        # Registering mints nothing and changes nothing (`create: false`), so an
        # answer we cannot read is still the honest "this run has no managed
        # execution" - there is no grant to strand.
        return None
    try:
        acquired = _control(
            client,
            Operation.ACQUIRE_WRITER,
            namespace=namespace,
            payload={"workspace_id": registered["workspace_id"]},
            deadline=deadline,
        )
    except (ExecutionRejectedError, ExecutionUnavailableError):
        return None
    # `ExecutionUncertainError` deliberately escapes from here: the authority may
    # have issued the writer and lost our frame, and the only safe statement is
    # that this run cannot prove it holds the workspace (see `_control`).
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

    ``None`` means one thing only: the operator has no config file, so the session
    layer keeps its pre-cutover host path. Every *present but unusable*
    configuration raises instead of degrading, because chat and publication must
    fail for the same reason: a managed deployment that cannot reach its authority
    is a deployment fault, not a reason to work on host bytes. The publication
    path answers the same fault by refusing to promote (``_promote_validated_plan``
    has no host fallback), so the two commands now agree.
    """
    path = DEFAULT_CONFIG_PATH if config_path is None else Path(config_path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as error:
        raise SessionManagerError("workspace_config_invalid", f"{path}: {error}") from None
    try:
        service_config = load_execution_config(text)
    except ExecutionConfigError as error:
        raise SessionManagerError("workspace_config_invalid", f"{path}: {error}") from None
    if service_config is None:
        return None
    try:
        config = read_config_file(service_config)
    except (ExecutionContractError, OSError) as error:
        raise SessionManagerError("workspace_config_invalid", f"{service_config}: {error}") from None
    client = _client_for(config)
    if client is None:
        raise SessionManagerError("workspace_denied", "controller uid is not in controller_uids")
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
    try:
        service_config = load_execution_config(text)
    except ExecutionConfigError as error:
        _logger.warning("operator config %s is unusable, so no managed execution: %s", path, error)
        return None
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
    "ClientWorkspaceProvisioner",
    "ExecutionBinding",
    "ManagedExecution",
    "client_workspace_provisioner",
    "managed_execution_for_run",
]
