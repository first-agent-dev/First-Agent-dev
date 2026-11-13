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
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from fa.config import DEFAULT_CONFIG_PATH, ExecutionConfigError, load_execution_config
from fa.execution.client import (
    CandidateRead,
    ExecutionClient,
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
    ManagedBashExecutor,
    PendingCandidatePublication,
    PlanPublication,
    StagePublication,
)
from fa.execution.profiles import ExecutionProfile
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
from fa.workspace_bootstrap import ReadyReason, ReadyState, ReadyStatus

_logger = logging.getLogger(__name__)

# The approved environment artifact is mounted read-only at this fixed path in
# managed cells. Use its isolated interpreter rather than PATH/project source;
# the host-side workspace bootstrap wrapper is not a managed product runner.
_MANAGED_READINESS_COMMAND = (
    "/workspace/.venv/bin/python -I -m pytest --version && /workspace/.venv/bin/python -I -m mutmut --version"
)


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
class _PendingHandoff:
    """The non-secret identity needed to replay one unresolved HANDOFF exactly."""

    request_id: str
    target: NamespaceRef
    uncertain: bool = False


@dataclass
class ManagedExecution:
    """One run's client, binding and the single writer grant it holds.

    The writer is acquired once per run, because a second acquisition of the same
    workspace is ``WORKSPACE_BUSY`` by construction (``workspace.py:1326-1338``)
    and holding it makes the run's publications and its host-side stages mutually
    exclusive instead of merely polite. The selected host profile and latest
    authority-reported revision travel with this same run-owned object.
    """

    client: ExecutionClient
    binding: ExecutionBinding
    grant: GrantReply
    view_profile: ExecutionProfile | None = None
    read_only_profile: ExecutionProfile | None = None
    current_revision_id: str = field(init=False)
    _pending_handoff: _PendingHandoff | None = field(default=None, init=False, repr=False)
    # Q138 option B: the run-scoped holder of an unresolved candidate publication.
    # While this is set the writer is not releasable, and reconciliation is the
    # only operation allowed to name it.
    _pending_publication: PendingCandidatePublication | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.binding, ExecutionBinding)
            or not isinstance(self.grant, GrantReply)
            or self.grant.operation not in {Operation.ACQUIRE_WRITER, Operation.HANDOFF}
            or self.grant.revision_id is None
            or (self.view_profile is not None and not isinstance(self.view_profile, ExecutionProfile))
            or (
                self.read_only_profile is not None
                and (not isinstance(self.read_only_profile, ExecutionProfile) or self.read_only_profile.interactive)
            )
        ):
            raise ExecutionContractError
        self._root_owner_run_id = self.binding.namespace.run_id
        self.current_revision_id = self.grant.revision_id

    @property
    def root_owner_run_id(self) -> str:
        """The original writer-owner run id, stable across HANDOFF namespace changes."""
        return self._root_owner_run_id

    @property
    def handoff_pending(self) -> bool:
        """Whether the active owner namespace is unresolved after a HANDOFF attempt."""
        return self._pending_handoff is not None

    @property
    def publication_pending(self) -> bool:
        """Whether a candidate publication is unresolved and still holds the writer."""
        return self._pending_publication is not None

    def handoff_to(self, target: NamespaceRef, *, deadline: float | None = None) -> GrantReply:
        """Transfer this single managed grant to ``target`` without cloning its holder.

        On an indeterminate reply the source binding/grant remain in this object,
        together with only the request identity and target. No other managed
        operation, including RELEASE, is allowed until :meth:`reconcile_handoff`
        proves the result.
        """
        if self._pending_handoff is not None:
            self._raise_handoff_uncertain()
        if (
            not isinstance(target, NamespaceRef)
            or target.session_id != self.binding.namespace.session_id
            or target.run_id == self.binding.namespace.run_id
        ):
            raise ExecutionContractError
        self._pending_handoff = _PendingHandoff(uuid4().hex, target)
        return self._attempt_handoff(deadline=deadline)

    def reconcile_handoff(self, *, deadline: float | None = None) -> GrantReply:
        """Replay one unresolved HANDOFF with its original id, proof, and target."""
        if self._pending_handoff is None:
            raise ExecutionContractError
        return self._attempt_handoff(deadline=deadline)

    def _attempt_handoff(self, *, deadline: float | None) -> GrantReply:
        pending = self._pending_handoff
        if pending is None:
            raise ExecutionContractError
        try:
            moved = self.client.handoff(
                self.binding,
                pending.target,
                grant=self.grant,
                expected_revision_id=self.current_revision_id,
                request_id=pending.request_id,
                deadline=deadline,
            )
        except ExecutionRejectedError as error:
            if pending.uncertain:
                # A later refusal cannot prove what an earlier lost reply did.
                raise ExecutionUncertainError("op-" + pending.request_id, code=error.code) from None
            self._pending_handoff = None
            raise
        except ExecutionUnavailableError as error:
            if pending.uncertain or error.operation_id is not None:
                self._pending_handoff = _PendingHandoff(pending.request_id, pending.target, uncertain=True)
                raise ExecutionUncertainError("op-" + pending.request_id, code="DURABILITY_UNKNOWN") from None
            self._pending_handoff = None
            raise
        except BaseException:
            # Once the request path has begun, an unclassified exception cannot
            # authorize either owner to continue or the composition to RELEASE.
            self._pending_handoff = _PendingHandoff(pending.request_id, pending.target, uncertain=True)
            raise

        if (
            not isinstance(moved, GrantReply)
            or moved.operation is not Operation.HANDOFF
            or moved.generation != self.grant.generation
            or moved.revision_id is None
            or moved.revision_id != self.current_revision_id
        ):
            self._pending_handoff = _PendingHandoff(pending.request_id, pending.target, uncertain=True)
            raise ExecutionUncertainError("op-" + pending.request_id, code="CORRUPT_STATE")

        self.binding = ExecutionBinding(pending.target, self.binding.workspace_id)
        self.grant = moved
        self.current_revision_id = moved.revision_id
        self._pending_handoff = None
        return moved

    def _require_handoff_resolved(self) -> None:
        if self._pending_handoff is not None:
            self._raise_handoff_uncertain()

    def _raise_handoff_uncertain(self) -> None:
        pending = self._pending_handoff
        if pending is None:
            raise ExecutionContractError
        raise ExecutionUncertainError("op-" + pending.request_id, code="DURABILITY_UNKNOWN")

    def publish_plan(
        self, source: PlanSnapshot, candidate: PlanSnapshot, *, deadline: float | None = None
    ) -> PlanPublication:
        """Publish through this run's grant and remember any unresolved outcome.

        Q114 option 1/A: the run-scoped object that owns the writer also owns the
        proof of an indeterminate publication. It is recorded here, before the
        exception leaves, so ``close()`` cannot release the writer behind it.
        """
        self._require_handoff_resolved()
        self._require_publication_resolved()
        try:
            publication = self.client.publish_plan(self.binding, source, candidate, grant=self.grant, deadline=deadline)
        except ExecutionUncertainError as error:
            pending = getattr(error, "pending_publication", None)
            if pending is not None:
                self._pending_publication = pending
            raise
        self.current_revision_id = publication.revision_id
        return publication

    def reconcile_publication(self, *, deadline: float | None = None) -> PlanPublication:
        """Settle this run's unresolved candidate publication, or raise again.

        Replays the same four request ids (never new ones) and, on a proved
        publication, clears the pending record so the writer may be released. An
        unresolved answer leaves the record in place: the workspace stays fenced
        for recovery rather than being handed to the next writer.
        """
        self._require_handoff_resolved()
        pending = self._pending_publication
        if pending is None:
            raise ExecutionContractError
        publication = self.client.reconcile_candidate_publication(pending, deadline=deadline)
        self.current_revision_id = publication.revision_id
        self._pending_publication = None
        return publication

    def _require_publication_resolved(self) -> None:
        pending = self._pending_publication
        if pending is None:
            return
        raise ExecutionUncertainError(
            "op-" + (pending.publish_request_id or pending.create_request_id),
            code="DURABILITY_UNKNOWN",
            pending_publication=pending,
        )

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
        self._require_handoff_resolved()
        return self.client.open_view(
            self.binding,
            access=access,
            purpose=purpose,
            base_revision=base_revision,
            plan_ref=plan_ref,
            grant=self.grant,
            deadline=deadline,
        )

    def open_candidate_view(self, plan_ref: PlanRef, *, deadline: float | None = None) -> GrantReply:
        """Open the run's staged-candidate view for ``plan_ref``.

        The controller names the plan it is repairing and nothing else; the base
        is the authority's to mint, exactly as in ``publish_plan``. Kept on the
        composition so the controller never spells a wire payload itself.
        """
        self._require_handoff_resolved()
        if not isinstance(plan_ref, PlanRef):
            raise ExecutionContractError
        return self.client.open_candidate_view(self.binding, plan_ref=plan_ref, grant=self.grant, deadline=deadline)

    def read_candidate(self, plan_ref: PlanRef, *, deadline: float | None = None) -> CandidateRead:
        """Read the run's staged candidate buffer without publishing it."""
        self._require_handoff_resolved()
        if not isinstance(plan_ref, PlanRef):
            raise ExecutionContractError
        return self.client.read_candidate_buffer(self.binding, plan_ref, grant=self.grant, deadline=deadline)

    def revision_changes(
        self,
        base_revision_id: str,
        target_revision_id: str,
        *,
        deadline: float | None = None,
    ) -> dict[str, Any]:
        """Compare this run's sealed base and current revision through a read pin."""
        self._require_handoff_resolved()
        _hex_id(base_revision_id, "rev-")
        _hex_id(target_revision_id, "rev-")
        if target_revision_id != self.current_revision_id:
            raise ExecutionUnavailableError
        reader = self.client.pin_reader(self.binding, target_revision_id, deadline=deadline)
        view = reader.view_ref
        if view is None:
            raise ExecutionUnavailableError
        try:
            result = self.client.diff_revisions(
                self.binding.namespace,
                view=view,
                grant=reader,
                base_revision=base_revision_id,
                deadline=deadline,
            )
        finally:
            if not self.client.stop_view(self.binding.namespace, view=view, grant=reader, deadline=deadline):
                _logger.warning(
                    "managed execution: revision-diff reader pin not confirmed closed for %s",
                    self.binding.workspace_id,
                )
                raise ExecutionUnavailableError
        return result

    def publish_stage(self, grant: GrantReply, *, deadline: float | None = None) -> StagePublication:
        """Commit the stage view ``grant`` opened; raise when the commit is unproved.

        A stage whose bytes are not committed may not be followed by verification or
        repair, so this reports by raising rather than by a boolean: there is no
        degraded continuation that would be honest. The run keeps its writer — the
        next stage opens its own view over the revision this call produced.
        """
        self._require_handoff_resolved()
        if not isinstance(grant, GrantReply) or grant.view_ref is None:
            raise ExecutionContractError
        publication = self.client.publish_stage(
            self.binding.namespace, view=grant.view_ref, grant=grant, deadline=deadline
        )
        self.current_revision_id = publication.revision_id
        return publication

    def stop_view(self, grant: GrantReply, *, deadline: float | None = None) -> bool:
        """End the view ``grant`` opened; ``False`` when its end was not proved.

        Same contract as :meth:`close`: an unproved end is reported once and never
        turned into a local assumption, because the authority still owns whatever
        the view holds.
        """
        self._require_handoff_resolved()
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
        if self._pending_handoff is not None:
            _logger.warning(
                "managed execution: writer release withheld while HANDOFF is unresolved for %s",
                self.binding.workspace_id,
            )
            return False
        if self._pending_publication is not None:
            # Releasing here would assert that a writer-owned publication is
            # settled, which is the one thing this run cannot prove (Q114).
            _logger.warning(
                "managed execution: writer release withheld while a candidate publication is "
                "unresolved for %s (reconcile before release)",
                self.binding.workspace_id,
            )
            return False
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

    def publish_candidate_receipt(
        self, source: PlanSnapshot, candidate: PlanSnapshot, *, deadline: float | None = None
    ) -> PlanPublication:
        """Publish once, reconcile an ambiguous reply, and return the full receipt.

        Q114 option 1/A puts the proof of an unresolved publication on the run that
        owns the writer, but owning it is only half the selection: the resolution
        says to *reconcile* by exact-request replay "where the existing journal
        permits, then release only after the candidate is proven
        PUBLISHED/REJECTED". Without this hop the ordinary recoverable case - the
        bytes committed, the reply lost - would sit in quarantine until an operator
        intervened, even though the journal could answer immediately.

        This is a reconciliation, not a retry: the same four request ids are
        replayed, so the authority answers from its journal and completed-reply
        cache. No second id is minted, no second view is opened, and no second
        effect can occur. Exactly one attempt is made.

        A run that owns **no** pending saga is not reconciled. That is the
        lost-``CREATE_VIEW`` shape (E512): the view id was never learned, so there
        is nothing to replay and the fence in ``close()`` stays the whole answer.
        """
        try:
            publication = self._managed.publish_plan(source, candidate, deadline=deadline)
        except ExecutionUncertainError:
            if not self._managed.publication_pending:
                raise  # no saga to replay; fail closed exactly as before
            publication = self._managed.reconcile_publication(deadline=deadline)
        return publication

    def publish_candidate(
        self, source: PlanSnapshot, candidate: PlanSnapshot, *, deadline: float | None = None
    ) -> PlanRef:
        """Publish through the managed authority and return only the promoted ``PlanRef``."""
        return self.publish_candidate_receipt(source, candidate, deadline=deadline).plan_ref


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
    capability = acquired.get("capability")
    generation = acquired.get("generation")
    revision_id = acquired.get("revision_id")
    if not isinstance(capability, str) or type(generation) is not int or not isinstance(revision_id, str):
        raise ExecutionContractError
    grant = GrantReply(Operation.ACQUIRE_WRITER, capability, None, generation, revision_id)
    binding = ExecutionBinding(namespace, str(registered["workspace_id"]))
    view_profile = next(
        (profile for profile in config.profiles if profile.profile_id == config.view_profile_id),
        None,
    )
    read_only_profile = next(
        (profile for profile in config.profiles if profile.profile_id == config.read_only_profile_id),
        None,
    )
    return ManagedExecution(
        client,
        binding,
        grant,
        view_profile=view_profile,
        read_only_profile=read_only_profile,
    )


def _settle_readiness_execution(
    managed: ManagedExecution, view_grant: GrantReply | None, executor: ManagedBashExecutor | None
) -> bool:
    """Stop the one provisioning view before releasing its one writer."""
    if executor is not None:
        executor.suspend()
    if view_grant is not None:
        try:
            if not managed.stop_view(view_grant, deadline=time.monotonic() + 15):
                return False
        except Exception:  # noqa: BLE001 — an unproved view end forbids writer release.
            return False
    try:
        return managed.close(deadline=time.monotonic() + 15)
    except Exception:  # noqa: BLE001 — release uncertainty is a failed readiness result.
        return False


def _write_readiness_log(path: Path, output: str) -> bool:
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as handle:
                handle.write(output)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(descriptor)
        return True
    except OSError:
        return False


def managed_environment_readiness(workspace: Path, run_context: RunContext | None) -> ReadyState:
    """Probe required tools in one managed PROVISIONING view before activation."""
    started = time.monotonic()
    reason: ReadyReason = "managed_artifact_probe_failed"
    log_path = Path("/dev/null")
    output = ""
    managed: ManagedExecution | None = None
    view_grant: GrantReply | None = None
    executor: ManagedBashExecutor | None = None
    try:
        if not isinstance(run_context, RunContext) or not isinstance(workspace, Path):
            raise ExecutionContractError
        log_path = run_context.run_log_dir / "managed-readiness.log"
        if workspace.resolve() != run_context.workspace_path.resolve():
            raise ExecutionContractError
        managed = managed_execution_for_run(run_context)
        if managed is None or managed.view_profile is None or not managed.view_profile.interactive:
            raise ExecutionContractError
        base_revision = managed.current_revision_id
        view_grant = managed.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.PROVISIONING,
            base_revision=base_revision,
            deadline=time.monotonic() + 45,
        )
        if view_grant.view_ref is None or view_grant.input_tree_sha256 is None:
            raise ExecutionContractError
        executor = ManagedBashExecutor(
            managed.client,
            namespace=managed.binding.namespace,
            view=view_grant.view_ref,
            grant=view_grant,
            profile=managed.view_profile,
            input_tree_sha256=view_grant.input_tree_sha256,
            plan_sha256=None,
            original_revision_id=base_revision,
            controller_root=workspace,
        )
        result = executor.run(_MANAGED_READINESS_COMMAND, timeout=30, session_id="readiness")
        output = result.stdout
        if result.exit_code == 0 and not result.timed_out:
            reason = "ready_managed_artifact"
    except Exception as error:  # noqa: BLE001 — readiness is a typed total result at the lifecycle boundary.
        output += f"managed readiness refused: {type(error).__name__}\n"
    finally:
        if managed is not None and not _settle_readiness_execution(managed, view_grant, executor):
            reason = "managed_artifact_probe_failed"
    if log_path != Path("/dev/null") and not _write_readiness_log(log_path, output):
        reason = "managed_artifact_probe_failed"
    return ReadyState(
        status=ReadyStatus.READY if reason == "ready_managed_artifact" else ReadyStatus.DEGRADED_ENVIRONMENT,
        fingerprint=None,
        reason_code=reason,
        log_path=log_path,
        repaired=False,
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )


@dataclass(frozen=True)
class ClientWorkspaceProvisioner:
    """CT116's second port: the manager's provisioning ask, answered over the wire.

    ``SessionManager`` calls this once per admitted create/attach run. New roots
    use ``register_workspace{create:true}`` with an absent target leaf and an
    approved input root id (or ``None`` for the empty seed); existing roots use
    ``create:false``. Both paths resolve exclusively against ``approved_roots``.

    ``tree_sha256`` is ``None``: the wire answer carries two fields (``service.py:591``)
    and ``ProvisionedWorkspace`` now accepts a registered result without the hash.

    The service creates the canonical root inside the authority, before any
    active-session publication. A caller cannot choose a materializer path: the
    source is either an approved root id or the empty seed.
    """

    config: ServiceConfig
    client: ExecutionClient

    def __post_init__(self) -> None:
        if not isinstance(self.config, ServiceConfig) or not isinstance(self.client, ExecutionClient):
            raise ExecutionContractError

    def __call__(self, request: ProvisionRequest) -> ProvisionedWorkspace:
        if not isinstance(request, ProvisionRequest):
            raise SessionManagerError("workspace_invalid", "provisioning requires a ProvisionRequest")
        if request.mode not in {ProvisionMode.PROVISION, ProvisionMode.REUSE}:
            raise SessionManagerError("workspace_invalid", f"unknown provisioning mode: {request.mode}")
        workspace = Path(request.workspace_path)
        creating = request.mode is ProvisionMode.PROVISION
        if creating:
            rooted = _new_root_binding(self.config, workspace)
            if rooted is None:
                raise SessionManagerError(
                    "workspace_escape", f"new workspace is not under one approved root: {workspace}"
                )
            input_id = (
                None if request.source_workspace is None else _approved_source_id(self.config, request.source_workspace)
            )
            if request.source_workspace is not None and input_id is None:
                raise SessionManagerError("workspace_escape", "source workspace is not an approved root")
        else:
            if not workspace.is_dir():
                raise SessionManagerError("workspace_missing", f"workspace does not exist: {workspace}")
            rooted = _root_binding(self.config, workspace)
            if rooted is None:
                raise SessionManagerError("workspace_escape", f"workspace escapes every approved root: {workspace}")
            input_id = None
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
                payload={
                    "root_id": root_id,
                    "relative_root": relative_root,
                    "create": creating,
                    "input_id": input_id,
                },
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

    ``None`` means the operator has no configured execution service. Session
    callers must refuse before lifecycle admission; there is no host provisioning
    or readiness fallback. A present but unusable configuration also raises.
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
    """Map an existing workspace onto one approved root."""
    try:
        workspace = workspace_path.expanduser().resolve(strict=True)
    except OSError:
        return None
    matches: list[tuple[str, str]] = []
    for root_id, root in config.approved_roots.items():
        try:
            relative = workspace.relative_to(Path(root).expanduser().resolve(strict=True))
        except (OSError, ValueError):
            continue
        if relative.parts:
            matches.append((root_id, relative.as_posix()))
    return matches[0] if len(matches) == 1 else None


def _new_root_binding(config: ServiceConfig, workspace_path: Path) -> tuple[str, str] | None:
    """Map an absent leaf whose existing parent is beneath exactly one approved root."""
    workspace = workspace_path.expanduser()
    if not workspace.is_absolute() or ".." in workspace.parts or not workspace.name:
        return None
    if os.path.lexists(workspace):
        return None
    try:
        parent = workspace.parent.resolve(strict=True)
    except OSError:
        return None
    matches: list[tuple[str, str]] = []
    for root_id, root in config.approved_roots.items():
        try:
            relative_parent = parent.relative_to(Path(root).expanduser().resolve(strict=True))
        except (OSError, ValueError):
            continue
        relative = (relative_parent / workspace.name).as_posix()
        matches.append((root_id, relative))
    return matches[0] if len(matches) == 1 else None


def _approved_source_id(config: ServiceConfig, source_path: Path) -> str | None:
    """The source contract accepts an approved root itself, never a path inside it."""
    try:
        source = source_path.expanduser().resolve(strict=True)
    except OSError:
        return None
    matches: list[str] = []
    for root_id, root in config.approved_roots.items():
        try:
            if source == Path(root).expanduser().resolve(strict=True):
                matches.append(root_id)
        except OSError:
            continue
    return matches[0] if len(matches) == 1 else None


__all__ = [
    "BoundPlanPublisher",
    "ClientWorkspaceProvisioner",
    "ExecutionBinding",
    "ManagedExecution",
    "client_workspace_provisioner",
    "managed_environment_readiness",
    "managed_execution_for_run",
]
