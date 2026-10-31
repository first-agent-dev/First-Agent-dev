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
from fa.execution.service import ServiceConfig, read_config_file
from fa.execution.types import ExecutionContractError, GrantReply, NamespaceRef, Operation, _hex_id
from fa.inner_loop.plan_admission import PlanRef, PlanSnapshot
from fa.session.manager import RunContext

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
    uid = os.getuid()
    if uid not in config.controller_uids:
        return None
    rooted = _root_binding(config, run_context.workspace_path)
    if rooted is None:
        return None
    root_id, relative_root = rooted
    namespace = NamespaceRef(run_context.session_id, run_context.run_id)
    client = ExecutionClient(config.socket_path, server_uid=uid, rpc_timeout_ms=config.rpc_timeout_ms)
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
