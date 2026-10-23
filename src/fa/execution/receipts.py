"""`ExecutionReceipt` v1: reserved identity plus independent observations.

A receipt is the one place where "the command finished" becomes a wire fact, so
nothing here may come from the cell: the worker's own status and stdout are
untrusted text (`CommandOutcome` says so), and a closed PTY, a Docker "exited"
status, a lost reply or an elapsed budget are *requests*, not proofs.

Three sources, one receipt:

* the reserved operation record — its id, namespace, view and durable container
  id, written before the command started;
* the view record through the caller's own grant — the input tree and plan
  digest the command actually ran against (`WorkspaceAuthority.execution_identity`);
* the approved profile — the single profile the authority admits cells with, so
  the profile, image digest and cgroup parent are the ones that ran.

What is observed afterwards is then only what the kernel and the daemon answer:
the container's exit code (once, and it must agree with the command's own) and
the cgroup's `populated 0`. `EXITED` needs both for a one-shot cell; an
interactive shell may stay alive, and then the barrier honestly stays false
until `stop_view`. Anything unobservable is `EXECUTION_UNKNOWN` — never exit 0,
never a "no exception" success.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fa.execution import cgroup
from fa.execution.backend import CellBackend, CommandOutcome
from fa.execution.docker import ContainerObservation, DockerEngine, DockerUnavailableError
from fa.execution.journal import JournalError
from fa.execution.profiles import ExecutionProfile
from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import (
    ExecutionContractError,
    ExecutionReceipt,
    JobState,
    NamespaceRef,
    Operation,
    OperationRef,
    ViewRef,
)
from fa.execution.workspace import WorkspaceAuthority

_MAX_TAIL_BYTES = 64 * 1024
# A separate, small control allowance for the post-command observation. The
# command's own budget may be spent exactly when its reply arrives, and the plan
# allows the handler to finish (and persist) a truthful result just after the
# caller-facing deadline; the transport deadline stays independent.
_CONTROL_ALLOWANCE_S = 2.0
_DEFAULT_POLL_S = 0.05


def bounded_tail(text: str) -> str:
    """The last 64 KiB of one channel, decoded without splitting a codepoint."""
    raw = text.encode("utf-8", "surrogatepass")
    return raw[-_MAX_TAIL_BYTES:].decode("utf-8", "ignore")


class CommandReceipts:
    """Issues `exec`/`inspect`/`cancel` receipts over the admitted backend.

    The layering mirrors `ViewStopper`: the owner that already holds the durable
    record and the live cell keeps doing exactly that, and this class decides
    only what may be *asserted* afterwards.
    """

    def __init__(
        self,
        authority: WorkspaceAuthority,
        backend: CellBackend,
        engine: DockerEngine,
        *,
        cgroup_root: Path = Path("/sys/fs/cgroup"),
        poll_interval_s: float = _DEFAULT_POLL_S,
    ) -> None:
        if not isinstance(authority, WorkspaceAuthority) or not isinstance(backend, CellBackend):
            raise ExecutionContractError
        if not isinstance(engine, DockerEngine):
            raise ExecutionContractError
        if not isinstance(cgroup_root, Path) or not cgroup_root.is_absolute():
            raise ExecutionContractError
        if type(poll_interval_s) is not float or not 0 < poll_interval_s <= _CONTROL_ALLOWANCE_S:
            raise ExecutionContractError
        self._authority, self._backend, self._engine = authority, backend, engine
        self._cgroup_root, self._poll = cgroup_root, poll_interval_s

    # ------------------------------------------------------------------ routes

    def execute(self, peer: PeerIdentity, request: dict[str, Any], *, deadline: float) -> dict[str, Any]:
        """Run the admitted command, then issue its receipt from observed facts."""
        namespace, view = self._scope(request)
        outcome = self._backend.execute(peer, request, deadline=deadline)
        # The command's budget may be spent exactly now; the observation has its
        # own bounded allowance, and both are absolute monotonic deadlines.
        observed_by = max(deadline, time.monotonic() + _CONTROL_ALLOWANCE_S)
        if outcome.timed_out:
            # The budget expired: no exit code, no barrier, and nothing the cell
            # can answer could change that, so the daemon is not asked at all.
            state, exit_code, barrier = JobState.TIMED_OUT, None, False
        else:
            observation = self._observe(outcome.operation_id, view, outcome.container_id, observed_by)
            state, exit_code, barrier = self._command_state(outcome, observation, observed_by)
        return {
            "receipt": self._receipt(
                peer,
                namespace,
                view,
                capability=self._capability(request),
                operation_id=outcome.operation_id,
                state=state,
                exit_code=exit_code,
                timed_out=state is JobState.TIMED_OUT,
                stdout=outcome.stdout,
                stderr=outcome.stderr,
                truncated=outcome.truncated,
                duration_ms=outcome.duration_ms,
                terminal_barrier=barrier,
                deadline=observed_by,
            )
        }

    def inspect(self, peer: PeerIdentity, request: dict[str, Any], *, deadline: float) -> dict[str, Any]:
        """Report one already-reserved operation; never sends a RUN."""
        namespace, view = self._scope(request)
        operation_id = request["payload"]["operation_id"]
        record = self._record(operation_id, namespace, view)
        # A completed operation answers with the receipt it durably stored: the
        # exact original result, never a second observation of a live cell.
        if record["state"] == "DONE":
            receipt = record["result"]["receipt"]
            if not isinstance(receipt, dict):
                raise SupervisorError("EXECUTION_UNKNOWN")
            return {"receipt": receipt}

        observed_by = max(deadline, time.monotonic() + _CONTROL_ALLOWANCE_S)
        container_id = record["container_id"]
        cancelled = bool(record["cancel_requested"])
        if container_id is None:
            # No cell was ever bound, so nothing can be writing. A persisted
            # cancel also proves none can appear (`create_once`/`start_once`
            # refuse a cancelled record).
            state = JobState.CANCELLED if cancelled else JobState.RESERVED
            barrier = cancelled
            exit_code = None
        else:
            observation = self._observe_optional(operation_id, view, container_id, observed_by)
            state, exit_code, barrier = self._inspected_state(observation, cancelled, view, observed_by)
        return {
            "receipt": self._receipt(
                peer,
                namespace,
                view,
                capability=self._capability(request),
                operation_id=operation_id,
                state=state,
                exit_code=exit_code,
                timed_out=False,
                stdout="",
                stderr="",
                truncated=False,
                duration_ms=0,
                terminal_barrier=barrier,
                deadline=observed_by,
            )
        }

    def cancel(self, peer: PeerIdentity, request: dict[str, Any], *, deadline: float) -> dict[str, Any]:
        """Persist intent, stop the owned cell, then report what was observed.

        A cancel receipt can never be `EXITED`: only an EXEC record binds a
        container id, so the journal itself refuses that state here. The exit
        code, when the stop was observed to complete, is still reported.
        """
        namespace, view = self._scope(request)
        target = request["payload"]["operation_id"]
        record = self._record(target, namespace, view)
        self._backend.cancel(peer, request, deadline=deadline)
        observed_by = max(deadline, time.monotonic() + _CONTROL_ALLOWANCE_S)
        container_id = record["container_id"]
        exit_code: int | None = None
        barrier = container_id is None  # intent alone proves no cell can appear
        if container_id is not None:
            observation = self._observe_optional(target, view, container_id, observed_by)
            if observation is not None and observation.status == "exited":
                exit_code = observation.exit_code
                barrier = self._barrier(container_id, observed_by)
        return {
            "receipt": self._receipt(
                peer,
                namespace,
                view,
                capability=self._capability(request),
                operation_id="op-" + request["request_id"],
                state=JobState.CANCELLED,
                exit_code=exit_code,
                timed_out=False,
                stdout="",
                stderr="",
                truncated=False,
                duration_ms=0,
                terminal_barrier=barrier,
                deadline=observed_by,
            )
        }

    # -------------------------------------------------------------- observation

    def _command_state(
        self, outcome: CommandOutcome, observation: ContainerObservation, deadline: float
    ) -> tuple[JobState, int | None, bool]:
        """The only mapping from a finished RUN plus one observation to a state."""
        profile = self._profile()
        if observation.status == "exited":
            if observation.exit_code != outcome.exit_code:
                # The command's own claim and the container's fact disagree.
                raise SupervisorError("EXECUTION_UNKNOWN")
            if not self._barrier(observation.container_id, deadline):
                # §2.1: a normal EXITED needs the barrier as well as the exit.
                raise SupervisorError("EXECUTION_UNKNOWN")
            return JobState.EXITED, observation.exit_code, True
        if observation.status == "running" and profile.interactive:
            # The interactive shell stays alive by design; barrier is the
            # stop_view question, not this command's.
            return JobState.EXITED, outcome.exit_code, False
        # A one-shot cell that is still running has not finished, and a
        # created/paused/dead cell is not a command result.
        raise SupervisorError("EXECUTION_UNKNOWN")

    def _inspected_state(
        self,
        observation: ContainerObservation | None,
        cancelled: bool,
        view: ViewRef,
        deadline: float,
    ) -> tuple[JobState, int | None, bool]:
        """Observation-only state for an operation whose record is not DONE."""
        if observation is None:
            # The bound cell cannot be observed: an unreserved cancel intent is
            # all that is known, and nothing may be invented beyond it.
            return (JobState.CANCELLED if cancelled else JobState.UNKNOWN), None, False
        if cancelled and observation.status != "exited":
            return JobState.CANCELLED, None, False
        if observation.status == "exited":
            if not self._barrier(observation.container_id, deadline):
                return JobState.UNKNOWN, None, False
            return JobState.EXITED, observation.exit_code, True
        if observation.status == "running":
            return JobState.RUNNING, None, False
        if observation.status == "created":
            return JobState.RESERVED, None, False
        return JobState.UNKNOWN, None, False

    def _observe(self, operation_id: str, view: ViewRef, container_id: str, deadline: float) -> ContainerObservation:
        """One owned observation that must exist; a foreign answer is a refusal."""
        observed = self._observe_optional(operation_id, view, container_id, deadline)
        if observed is None:
            raise SupervisorError("EXECUTION_UNKNOWN")
        return observed

    def _observe_optional(
        self, operation_id: str, view: ViewRef, container_id: str, deadline: float
    ) -> ContainerObservation | None:
        """One owned observation whose absence the caller may report honestly."""
        try:
            return self._engine.inspect_owned(
                operation_id=operation_id,
                view=view,
                profile=self._profile(),
                container_id=container_id,
                deadline=deadline,
            )
        except DockerUnavailableError as error:
            if error.status == 404:
                return None
            if error.status is None:
                # Identity/ownership disagreement: never treated as a fact.
                raise SupervisorError("PATH_DENIED") from None
            raise SupervisorError("EXECUTION_UNKNOWN") from None
        except TimeoutError:
            return None

    def _barrier(self, container_id: str, deadline: float) -> bool:
        """Poll the kernel fact to the deadline; only `populated 0` is true."""
        profile = self._profile()
        while True:
            try:
                verdict = cgroup.descendants_empty(self._cgroup_root, profile.cgroup_parent, container_id)
            except ValueError:
                return False
            if verdict is True:
                return True
            if verdict is None:
                return False  # unreadable is not empty
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(self._poll, remaining))

    # ------------------------------------------------------------------ receipt

    def _receipt(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        view: ViewRef,
        *,
        capability: str,
        operation_id: str,
        state: JobState,
        exit_code: int | None,
        timed_out: bool,
        stdout: str,
        stderr: str,
        truncated: bool,
        duration_ms: int,
        terminal_barrier: bool,
        deadline: float,
    ) -> dict[str, Any]:
        """Build and self-check one receipt against the trusted identity."""
        profile = self._profile()
        tree, plan_sha256 = self._authority.execution_identity(
            peer, namespace, view_ref=view, capability=capability, deadline=deadline
        )
        receipt = ExecutionReceipt(
            schema_version=1,
            operation_id=operation_id,
            namespace=namespace,
            workspace_id=view.workspace_id,
            view_id=view.view_id,
            owner_run_id=view.owner_run_id,
            generation=view.generation,
            revision_id=view.base_revision,
            original_revision_id=view.base_revision,
            input_tree_sha256=tree,
            plan_sha256=plan_sha256,
            profile_id=profile.profile_id,
            image_digest=profile.image_digest,
            state=state,
            exit_code=exit_code,
            timed_out=timed_out,
            stdout_tail=bounded_tail(stdout),
            stderr_tail=bounded_tail(stderr),
            truncated=truncated,
            duration_ms=duration_ms,
            terminal_barrier=terminal_barrier,
        )
        # The same comparison the controller makes: a receipt that does not bind
        # to this operation, view, profile and plan is never sent.
        receipt.require_binding(
            operation=OperationRef(operation_id, view.view_id, view.owner_run_id, view.generation, tree),
            namespace=namespace,
            view=view,
            profile_id=profile.profile_id,
            image_digest=profile.image_digest,
            revision_id=view.base_revision,
            original_revision_id=view.base_revision,
            plan_sha256=plan_sha256,
        )
        return receipt.to_dict()

    # ------------------------------------------------------------------- input

    @staticmethod
    def _scope(request: dict[str, Any]) -> tuple[NamespaceRef, ViewRef]:
        raw = request.get("view_ref")
        if raw is None:
            raise SupervisorError("INPUT_POLICY")
        try:
            return NamespaceRef(**request["namespace"]), ViewRef.from_dict(raw)
        except (KeyError, TypeError, ExecutionContractError):
            raise SupervisorError("INVALID_REQUEST") from None

    @staticmethod
    def _capability(request: dict[str, Any]) -> str:
        capability = request.get("capability")
        if not isinstance(capability, str):
            raise SupervisorError("UNAUTHORIZED")
        return capability

    def _profile(self) -> ExecutionProfile:
        profile = self._authority.approved_profile
        if profile is None:
            raise SupervisorError("UNAPPROVED_PROFILE")
        return profile

    def _record(self, operation_id: str, namespace: NamespaceRef, view: ViewRef) -> dict[str, Any]:
        """The exact EXEC record this request names, in this namespace and view."""
        try:
            record = self._authority.journal.lookup(operation_id, namespace)
        except JournalError as error:
            raise SupervisorError(error.code) from None
        if record is None or record["op"] != Operation.EXEC.value:
            raise SupervisorError("EXECUTION_UNKNOWN")
        if record["view_ref"] != view.to_dict():
            # An operation of the same namespace but another view is not this
            # caller's to inspect or cancel.
            raise SupervisorError("UNAUTHORIZED")
        return record
