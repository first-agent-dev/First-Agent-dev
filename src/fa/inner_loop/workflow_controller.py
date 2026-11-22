"""Workflow controller — multi-role pipeline orchestration.

Extracted from cli.py (S4a). This module owns the workflow pipeline:
linear and adaptive modes. It is callable from both the CLI
(``fa workflow``) and from tools (``invoke_workflow``).

Dependency direction: this module does NOT import from cli.py.
The stage dispatcher (``_cmd_run``) is passed as a callable parameter
(``run_stage_fn``) to avoid circular imports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol, runtime_checkable

from fa.execution.client import (
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
    ReadOnlyManagedBashExecutor,
)
from fa.execution.primitives import ExecutionContractError
from fa.execution.tool_port import ClientWorkspacePort
from fa.execution.types import Access, Operation, ViewPurpose
from fa.inner_loop.acceptance_bundle import AcceptanceBundle, AcceptanceBundleError, mint_seal
from fa.inner_loop.acceptance_collection import (
    AcceptanceCollectionError,
    collect_sealed_tree,
    sealed_attempt,
    verify_sealed_acceptance,
)
from fa.inner_loop.acceptance_seal_store import SealStore
from fa.inner_loop.admission_schema import ADMISSION_RULES, ADMISSION_RULES_V2
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.injections import INJECTION_MODES, INJECTION_SPECS, resolve_injection_modes
from fa.inner_loop.managed_acquisition import (
    INITIAL_INCREMENT_SLUG,
    AcquisitionChoiceError,
    AcquisitionOutcome,
    parse_acquisition_choice,
    resolve_acquisition_choice,
)
from fa.inner_loop.plan_admission import (
    PLAN_V1,
    PLAN_V2,
    DispositionDeclaration,
    PlanRef,
    PlanRefError,
    PlanSnapshot,
    _require_plan_for_coder,
    bind_dispositions,
    read_plan_snapshot,
    snapshot_from_bytes,
)
from fa.inner_loop.plan_ids import (
    PlanDiagnostic,
    PlanIds,
    canonical_slice_id,
    extract_plan_id,
    extract_plan_ids,
    precheck,
)
from fa.inner_loop.plan_promotion import (
    CandidatePlanPublisher,
    PlanPromotionError,
    retain_plan_draft,
    seed_plan_candidate,
)
from fa.inner_loop.plan_v2 import PlanV2Error
from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchError, PlannerDispatchKind
from fa.inner_loop.project_metadata import MetadataError, check_project_metadata
from fa.inner_loop.prompt import ADVERSARIAL_EVAL_STANCE_PREAMBLE
from fa.inner_loop.slice_verification import (
    TAIL_LIMIT,
    CommandOutcome,
    CommandResult,
    ManagedVerifyCommandExecutor,
    NodeidCapture,
    PlanVerification,
    SliceVerdict,
    SliceVerification,
    VerifyCommandExecutor,
    _gate_mode,
    capture_test_nodeids,
    validate_kill_directives,
    verify_plan,
)
from fa.inner_loop.stage_candidate import reset_stage_candidate, stage_candidate_reader
from fa.inner_loop.tools.workspace_port import WorkspacePort, WorkspacePortError, port_relative
from fa.inner_loop.verification_attempt import ClaimEvidence, VerificationAttempt, VerificationIdentity
from fa.inner_loop.workflow_artifacts import (
    AdmissionIOError,
    EvalReport,
    FlowState,
    FlowStatus,
    ManagedAdmissionBinding,
    RouteDecision,
    _admission_lock,
    _private_artifact_directory,
    _read_admission_at,
    _replace_private_json,
    default_route_for_verdict,
    load_flow_state,
    parse_eval_report,
    write_admission_record,
    write_eval_report,
    write_flow_state,
)
from fa.paths import fa_session_log_root

# F5: ConfigurationError imported at module level for use in except clauses.
from fa.providers.errors import ConfigurationError

if TYPE_CHECKING:
    from fa.execution.composition import ManagedExecution
    from fa.inner_loop.session_db import SessionDatabase
    from fa.providers import ModelsConfig
    from fa.providers.base import Transport
    from fa.session.manager import RunContext, SessionContext

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────────

EVAL_VERDICT_TO_TERMINAL_STATUS: dict[str, FlowStatus] = {
    "PASS": "DONE",
    "REPAIR_REQUIRED": "REPAIR_REQUIRED",
    "REPLAN_REQUIRED": "REPLAN_REQUIRED",
    "BLOCKED": "FAILED",
}

WORKFLOW_STATUS_TO_STOP_REASON: dict[str, str] = {
    "DONE": "workflow_complete",
    "FAILED": "workflow_failed",
    "REPAIR_REQUIRED": "workflow_repair_required",
    "REPLAN_REQUIRED": "workflow_replan_required",
}

DEFAULT_MAX_REPAIRS = 2
# S4b/RK6: exit code for a pipeline stopped by its wall-clock deadline. 124 is
# the conventional timeout code (GNU ``timeout``), so operators reading an exit
# status see "timed out" rather than a generic failure. It is deliberately a
# value no stage can return: ``_cmd_run`` returns 0/1/2.
WORKFLOW_DEADLINE_EXIT_CODE = 124

# The exact substring written into ``FlowState.last_transition_reason`` when the
# deadline stops a run. The ``invoke_workflow`` tool matches on it to report
# ``timed_out=True``, so treat it as a wire contract between the controller and
# the tool, not as prose.
DEADLINE_REASON_MARKER = "workflow deadline exceeded"

MAX_REPAIRS_CEILING = 3
DEFAULT_MAX_REPLANS = 1
MAX_REPLANS_CEILING = 2

WORKFLOW_MODES = ("linear", "adaptive")

# RK8 (S5): the roles a workflow STAGE may run as. An ALLOWLIST, not a denial
# of "chat", because the question worth asking at the boundary is "is this a
# role this pipeline knows how to run", not "is this the one role we already
# know is dangerous". A denylist accepts every typo and every future role by
# default — which is exactly why `--roles bogus_role` used to run.
#
# Derived from nothing on purpose. NOT from PROFILES_RAW: this is a policy
# statement about pipeline stages, not a restatement of which profiles exist.
# `chat` IS a real profile and must stay absent here — a chat stage would build
# its own invoke_workflow tool and could recurse into a fresh workflow, and the
# S4b re-entrancy guard is thread-local so it cannot see across the separate
# call frames that stages run in. Excluding chat at the CLI boundary is what
# makes that guard's blind spot unreachable.
#
# Adding a role here is meant to be a deliberate edit with a test beside it.
WORKFLOW_STAGE_ROLES: Final = frozenset({"planner", "coder", "eval"})


# ── Dataclasses ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WorkflowArtifactPaths:
    base_dir: Path
    eval_report: Path
    flow_state: Path
    verification: Path
    verify_baseline: Path

    @property
    def admission(self) -> Path:
        return self.base_dir / "admission.json"


@dataclass(frozen=True, slots=True)
class _BootstrapReceipt:
    """Committed authority receipt from ``prepare_bundle`` + ``install_project``."""

    bundle_sha256: str
    input_revision: str
    output_revision: str
    operation_id: str


@dataclass(frozen=True, slots=True)
class _BootstrapFailure:
    """Closed v2 failure details preserved alongside legacy ``PlanRefError``."""

    validator: str
    rule: str
    severity: str
    validation: str
    operation_id: str | None = None
    candidate_sha256: str | None = None
    bundle_sha256: str | None = None


@dataclass(slots=True)
class _WorkflowAdmission:
    """Run-local canonical authority and the shared planner-attempt counter."""

    snapshot: PlanSnapshot
    planner_allowed: bool
    planner_limit: int
    planner_calls: int = 0
    plan_version: int = 1
    block_exit_code: int = 2
    candidate: PlanSnapshot | None = None
    last_eval_report: EvalReport | None = None
    #: F10: the V2 verification attempt for the most recent coder gate. ``None`` means the legacy
    #: route ran (or the V2 route could not build one), never "the attempt was empty".
    last_attempt: VerificationAttempt | None = None
    baseline: Literal["NOT_CAPTURED", "CAPTURED", "FAILED"] = "NOT_CAPTURED"
    admitted: bool = False
    failure: str | None = None
    # True when the snapshot arrived as bytes from a pinned view (acquisition), so
    # there is no host copy to re-read. A positive fact, not "plan_path is None":
    # the legacy host path is also absent for a planner-only run, which has no
    # admission at all. Declared last so the three positional fields keep theirs.
    snapshot_backed: bool = False
    from_acquisition: bool = False
    bootstrap_receipt: _BootstrapReceipt | None = None


@dataclass(slots=True)
class _ManagedRevisionPair:
    """The sealed revision boundary around the most recent coder stage."""

    base_revision_id: str | None = None
    target_revision_id: str | None = None


@dataclass(slots=True)
class _InitialPlannerContextSlot:
    """One-shot parent context consumed only by the initial planner dispatch (S5P4/CT109)."""

    text: str = ""
    consumed: bool = False


@dataclass(frozen=True)
class WorkflowContext:
    """Invariant per-run configuration shared by every workflow stage."""

    run_id: str
    base_task: str | None
    per_role_task: Mapping[str, str | None]
    artifact_paths: WorkflowArtifactPaths
    config: Path
    workspace: Path
    max_turns: int
    output_mode: str
    transport: Transport | None = None
    secrets: Mapping[str, str] | None = None
    session_context: SessionContext | None = None
    run_context: RunContext | None = None
    session_db: SessionDatabase | None = None
    # S4b/RK6: absolute ``time.monotonic()`` instant after which no NEW stage
    # is dispatched. ``None`` means no deadline, which is what every existing
    # caller (``_cmd_workflow``) passes, so their behaviour is unchanged.
    deadline_mono: float | None = None
    # PLAN S5a / Q8: operator-supplied ``--inject NAME=MODE`` overrides for
    # this run, already parsed and validated. Empty for every existing
    # construction site, so their behaviour is unchanged.
    #
    # Q7: the WORKFLOW owns the switch. Injections are about executing a
    # planned slice, which is the pipeline's job. Q8: resolution happens once
    # per stage dispatch (flag > config > off) rather than per turn -- modes
    # change between invocations, not mid-loop (plan v5 RK15).
    inject_overrides: Mapping[str, str] = field(default_factory=dict)
    # S12a: the plan artifact this run executes against. ``None`` -- the
    # default and what every pre-S12a caller passes -- means the harness has no
    # contract to check against, so S12 (slice-ID validation) and S13 (the eval
    # evidence block) degrade silently rather than warning about a plan the
    # operator never supplied.
    plan_path: Path | None = None
    #: D-V2-9.8: how many create-new *repair* stages this run has already dispatched.
    #: The shared ``_WorkflowAdmission.planner_calls`` counter cannot carry this: on the
    #: create-new route admission authority is created *by* the refusal being repaired,
    #: so before the first repair there is no counter object at all. One integer on the
    #: frozen context, threaded the same way the stage dispatch already is.
    authored_repairs: int = 0
    # CT77c: resolved once at workflow start so one run cannot switch between
    # observe/enforce if the operator edits config while a stage is in flight.
    verify_gate_mode: str = "observe"
    admission: _WorkflowAdmission | None = None
    #: The grammar this run admits its plan under, chosen by the route that
    #: renders the artifact (never by the document). ``PLAN-V1`` is the frozen
    #: legacy default so every existing caller is unchanged; the V2 bootstrap
    #: route sets ``PLAN-V2`` once it renders the V2 manifest.
    plan_format: str = PLAN_V1
    #: Chat-supplied project slug for a create-new run (CT-2.1). ``None`` keeps
    #: the planner's own choice, which is the only behaviour the legacy route had.
    project_hint: str | None = None
    #: R1 (E577): the caller's disposition grants. Empty for every existing
    #: construction site, and empty for a run that has no plan to authorise.
    dispositions: tuple[DispositionDeclaration, ...] = ()
    # Managed candidate promotion is supplied only by the execution composition.
    # None is a fail-closed boundary; the controller has no host-path writer fallback.
    plan_publisher: CandidatePlanPublisher | None = None
    # One workflow-owned writer is forwarded unchanged to every stage. The stage
    # boundary can consult its selected profile and latest authority revision.
    managed_execution: ManagedExecution | None = None
    managed_revision_pair: _ManagedRevisionPair = field(default_factory=_ManagedRevisionPair)
    managed_plan_ref: PlanRef | None = None
    # S3P3: the managed read-back of a staged candidate. Bound by the composition
    # to a callable over the run's own managed execution, so the controller never
    # holds a client and never opens a view itself. ``None`` in host mode, where
    # `_run_admission_repair` reads the controller's own host copy instead.
    managed_candidate_reader: Callable[[PlanRef], tuple[str, str] | None] | None = None
    # S5P1: the run's replan budget. Admission is bound *after* the acquisition
    # planner has already run, so the binder cannot read it off a request object it
    # never received; without this the bound admission would claim a limit of zero
    # and a repair leg would be refused for a plan that allows repairs.
    replans_allowed: int = 0
    # S5P1: bound only for an acquisition run -- the pinned view plus the names it
    # named. None means this run must already have its plan, as every other run does.
    acquisition: AcquisitionSubstrate | None = None
    # Q150=A: present solely on managed-child runs (owner_run_id != run_id) to
    # select v2 admission.json without altering unmanaged v1 callers.
    admission_binding: ManagedAdmissionBinding | None = None
    # S5P4 / CT109 / Q66: bounded, credential-redacted snapshot of parent chat
    # messages consumed ONLY by the initial planner dispatch.
    initial_planner_slot: _InitialPlannerContextSlot = field(default_factory=_InitialPlannerContextSlot)

    def plan_text(self) -> str | None:
        """Use the immutable admitted snapshot, or read legacy optional input.

        Explicit admission treats this snapshot as authority; source changes
        are checked separately. Legacy contexts tolerate absent/unreadable input.
        """
        if self.admission is not None:
            return self.admission.snapshot.text
        if self.plan_path is None:
            return None
        try:
            return self.plan_path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("workflow: plan not readable at %s; continuing without it", self.plan_path)
            return None

    def plan_identity(self) -> str:
        """The plan's declared ``Plan-ID``, falling back to ``run_id``.

        Historically ``plan_id`` was passed ``run_id`` at every call site -- a
        field whose name promised a plan reference while holding a run
        identifier. When a plan IS supplied and declares an ID, records now
        carry the real thing; otherwise the old value is kept so existing
        artifacts stay shaped as before.
        """
        text = self.plan_text()
        if text is None:
            return self.run_id
        return extract_plan_id(text) or self.run_id

    def task_for(self, role: str) -> str | None:
        return self.per_role_task.get(role) or self.base_task


@dataclass(frozen=True)
class WorkflowProgress:
    """Mutable controller counters threaded through a workflow run."""

    plan_version: int = 1
    repair_round: int = 0
    replan_round: int = 0


@dataclass(frozen=True)
class StageResult:
    """Outcome of dispatching one role stage, including harness verification evidence."""

    role: str
    exit_code: int
    eval_report: EvalReport | None = None
    verification: PlanVerification | None = None
    # S5P1 §7.0: the typed choice an ACQUISITION planner returned. Set on exactly
    # one stage of one run, and only when an acquisition substrate was bound, so
    # the controller can bind admission between planner and coder instead of
    # running a second planner outside the workflow.
    acquisition: AcquisitionOutcome | None = None
    #: D-V2-9: this stage authored a NEW project and published one revision. A
    #: positive fact rather than "acquisition is None and something happened",
    #: because the binding step after it is destructive (it admits a plan).
    authored_project: bool = False


# ── Helper functions ───────────────────────────────────────────────────────


def slugify_task(task: str, *, limit: int = 24) -> str:
    """Derive a short, run-id-safe slug from a task string."""
    import re

    slug = re.sub(r"[^A-Za-z0-9]+", "-", task.strip().lower()).strip("-")
    return slug[:limit] or "task"


def workflow_artifact_paths(run_id: str, *, base_dir: Path | None = None) -> WorkflowArtifactPaths:
    """Return canonical workflow artifact paths under ``~/.fa/session-log``."""
    base_dir = base_dir or (fa_session_log_root() / run_id)
    return WorkflowArtifactPaths(
        base_dir=base_dir,
        eval_report=base_dir / "eval_report.json",
        flow_state=base_dir / "flow_state.json",
        verification=base_dir / "verification.json",
        verify_baseline=base_dir / "verify_baseline.json",
    )


class _WorkflowStorageError(OSError):
    """Typed internal boundary for failed flow-state persistence, without raw paths/bodies."""


def _persist_flow_state(path: Path, state: FlowState) -> None:
    try:
        write_flow_state(path, state)
    except (OSError, ValueError) as error:
        raise _WorkflowStorageError("workflow flow-state storage failed") from error


@dataclass(frozen=True)
class BaselineCapture:
    """T0/now nodeid maps plus any harness evidence needed for an operator report."""

    nodeids_by_slice: Mapping[str, Mapping[str, bool] | None]
    captures: Mapping[str, NodeidCapture] = field(default_factory=dict)
    errors: tuple[str, ...] = ()


def _command_result_payload(result: CommandResult) -> dict[str, object]:
    return {
        "command": result.command,
        "outcome": result.outcome.value,
        "exit_code": result.exit_code,
        "stdout_tail": result.stdout_tail,
        "stderr_tail": result.stderr_tail,
        "duration_s": result.duration_s,
    }


def _nodeid_capture_payload(capture: NodeidCapture) -> dict[str, object]:
    payload: dict[str, object] = {
        "nodeids": None if capture.nodeids is None else dict(capture.nodeids),
        "detail": capture.detail,
    }
    if capture.command_result is not None:
        payload["command_result"] = _command_result_payload(capture.command_result)
    return payload


@dataclass(frozen=True, slots=True)
class _VerifySubstrate:
    """Where the verification gate runs, when it is not the controller host.

    Two pieces travel together because they answer the same question from two sides:
    ``executor`` runs the command on the pinned read-only view, and ``port`` answers
    what the snapshot actually contains. Splitting them would let a run verify one
    tree and inspect another, which is the defect R24 exists to remove.
    """

    executor: VerifyCommandExecutor
    port: WorkspacePort | None


@contextmanager
def _pinned_verify_substrate(ctx: WorkflowContext) -> Iterator[_VerifySubstrate | None]:
    """Pin one read-only view of the current revision, or yield ``None`` when unmanaged.

    ``None`` is not a fallback to the host: an unmanaged run *is* the host tree, so
    there is nothing to move. A managed run that cannot build the substrate raises,
    because verifying the controller copy of a revision the coder edited out of view
    would report a verdict about a tree nobody asked about.

    The pin is the mechanism the spec names for read-only verification
    (``i03-execution-workspace-spec:640,806``): a READ view over sealed source with a
    private tmpfs scratch, whose writes cannot become a revision
    (``workspace.py:5374``). It is stopped before this returns, so a verify never
    outlives the stage that asked for it.
    """
    managed = ctx.managed_execution
    if managed is None:
        yield None
        return
    profile = managed.read_only_profile
    if profile is None or profile.interactive:
        raise ExecutionContractError
    deadline = ctx.deadline_mono if ctx.deadline_mono is not None else time.monotonic() + 30.0
    # The plan the stage ran against, not the one the run started with: a promoted
    # candidate changes the plan's bytes, and the authority proves the pinned ref
    # against THIS revision.
    plan_ref = ctx.admission.snapshot.ref if ctx.admission is not None else ctx.managed_plan_ref
    grant = managed.client.pin_reader(
        managed.binding,
        revision_id=managed.current_revision_id,
        plan_ref=plan_ref,
        deadline=deadline,
    )
    view = grant.view_ref
    if (
        grant.operation is not Operation.PIN_READER
        or view is None
        or view.access is not Access.READ
        or view.purpose is not ViewPurpose.PROJECT
        or view.workspace_id != managed.binding.workspace_id
        or view.owner_run_id != managed.binding.namespace.run_id
        or grant.input_tree_sha256 is None
    ):
        raise ExecutionContractError
    reader = ReadOnlyManagedBashExecutor(
        managed.client,
        namespace=managed.binding.namespace,
        view=view,
        grant=grant,
        profile=profile,
        plan_ref=plan_ref,
        controller_root=ctx.workspace,
    )
    port = ClientWorkspacePort(
        managed.client,
        namespace=managed.binding.namespace,
        view=view,
        grant=grant,
        cache_dir=ctx.artifact_paths.base_dir / "verify-read-cache",
        plan_ref=plan_ref,
    )
    try:
        yield _VerifySubstrate(executor=ManagedVerifyCommandExecutor(reader, root=ctx.workspace), port=port)
    finally:
        # A pin that did not become terminal stays owned by this run; saying so is the
        # honest outcome, and the next run on the workspace will be refused until it is
        # settled rather than silently reading a view someone else may hold.
        if not managed.client.stop_view(managed.binding.namespace, view=view, grant=grant, deadline=deadline):
            logger.error("verify read-only view did not become terminal (run=%s view=%s)", ctx.run_id, view.view_id)


def _sealed_snapshot(ctx: WorkflowContext) -> PlanSnapshot | None:
    """The admitted snapshot when its grammar is ``PLAN-V2``, else ``None``.

    The branch is on the grammar, never on "are there commands": a V2 snapshot's ``ids`` are empty
    by design (`plan_admission.py:74-76`), so a route that decided by commands would pick the
    legacy verifier on exactly the grammar that retired it (F10).
    """
    if ctx.admission is None:
        return None
    snapshot = ctx.admission.snapshot
    return snapshot if snapshot.format == PLAN_V2 else None


def _record_stage_attempt(ctx: WorkflowContext, attempt: VerificationAttempt | None) -> None:
    """Keep the stage's attempt on the admission record for the artifact writer (F10 item 4).

    ``None`` is recorded as ``None`` rather than left stale: an attempt from an earlier repair
    round describes another candidate, and a writer that read it would attach the wrong evidence.
    """
    if ctx.admission is not None:
        ctx.admission.last_attempt = attempt


def _stage_acceptance_bundle(ctx: WorkflowContext) -> tuple[AcceptanceBundle | None, tuple[str, ...]]:
    """The seal this workspace admitted, or the closed rule that says why there is none.

    A V2 stage cannot fall back to the planner's ``verify`` fence when the seal is missing: the
    fence is exactly what the route retired (CT-3.6), so "no seal" is a blocking error, not an
    invitation to run something else.
    """
    try:
        return SealStore(ctx.workspace).current(), ()
    except AcceptanceBundleError as error:
        # ``seal-pointer-missing`` is the store's name for "nothing sealed yet", which on this
        # route is the same fact the old missing-file check reported.
        rule = "missing" if error.rule == "seal-pointer-missing" else error.rule
        return None, (f"acceptance-seal/{rule}",)


def _sealed_stage_verification(
    ctx: WorkflowContext,
    snapshot: PlanSnapshot,
    substrate: _VerifySubstrate | None,
    *,
    attempt: int,
    repair_round: int,
) -> tuple[PlanVerification, VerificationAttempt | None]:
    """CT-3.6 on the ``PLAN-V2`` route: the seal is the oracle, the plan's fence never runs (F10).

    ``verify_plan`` is not called here at all -- not with a guard and not with an empty id set.
    The measured defect was that a V2 snapshot's ids are empty by design, so the planner's fences
    were the only commands and a stage that measured nothing read as a pass; branching on the
    snapshot's *grammar* is what retires that, because the two routes have different oracles and
    nothing in the route is allowed to decide by "are there commands".

    Every refusal below is recorded as a ``PlanVerification`` error rather than raised, so the
    existing gate (enforce/observe) keeps judging it; the difference is that the error is now the
    reason a V2 stage blocks, instead of an empty command list reading as green.
    """
    bundle, errors = _stage_acceptance_bundle(ctx)
    if substrate is None:
        # No pinned cell means the host tree, and the host tree is what the coder just edited.
        errors = (*errors, "verifier-substrate-required")
    if bundle is None or substrate is None:
        return PlanVerification(plan_command_results=(), slice_verifications=(), errors=errors), None

    executor = substrate.executor
    candidate_revision_id = getattr(executor, "view_revision_id", None)
    if not isinstance(candidate_revision_id, str) or not candidate_revision_id:
        return PlanVerification(
            plan_command_results=(),
            slice_verifications=(),
            errors=(*errors, "verifier-revision-mismatch"),
        ), None
    managed = ctx.managed_execution
    profile = None if managed is None else managed.read_only_profile
    try:
        verification = verify_sealed_acceptance(
            bundle,
            workspace=ctx.workspace,
            candidate_revision_id=candidate_revision_id,
            plan_bytes=snapshot.utf8_bytes,
            # F9/CT-3.4: V2 `KILL-TARGETS` carry attribution only (`KillTarget(target_id, ct,
            # test_id)`), so no executable mutation can be declared on this grammar and nothing
            # is required -- not because a mutation was skipped.
            kill_required=(),
            deadline=ctx.deadline_mono,
            executor=executor,
        )
    except (AcceptanceCollectionError, AcceptanceBundleError) as error:
        rule = getattr(error, "rule", type(error).__name__)
        return PlanVerification(
            plan_command_results=(),
            slice_verifications=(),
            errors=(*errors, f"sealed-verification/{rule}"),
        ), None
    identity = VerificationIdentity(
        plan_sha256=snapshot.ref.sha256,
        candidate_revision_id=candidate_revision_id,
        profile_id="managed-readonly" if profile is None else profile.profile_id,
        substrate="managed-readonly" if managed is not None else "host",
        run_id=ctx.run_id,
        attempt=attempt,
        repair_round=repair_round,
        mode=_gate_mode(ctx.verify_gate_mode),
        seal_sha256=bundle.seal_sha256,
        closure_sha256=bundle.closure.digest,
        sealed_revision_id=bundle.revision_id,
    )
    try:
        sealed = sealed_attempt(
            bundle,
            verification,
            identity=identity,
            # N2/Q-V2-SLICE3-4 = A: the grammar's targets are attribution, so they are recorded
            # as declared-and-not-executed rather than dropped. ``kill_required`` stays empty for
            # the same reason -- nothing on this grammar is executable, which is a fact about the
            # plan, not about the attempt.
            kill_declared=snapshot.graph.kill_targets() if snapshot.graph is not None else (),
        )
    except AcceptanceCollectionError as error:
        return PlanVerification(
            plan_command_results=(),
            slice_verifications=(),
            errors=(*errors, f"sealed-attempt/{error.rule}"),
        ), None
    # One command, attributed to the oracle that actually ran: the harness built it from the seal.
    plan_verification = PlanVerification(
        plan_command_results=(verification.command,),
        slice_verifications=(),
        errors=(*errors, *(("sealed-attempt/" + sealed.first_reason,) if sealed.blocking else ())),
    )
    return plan_verification, sealed


def _capture_nodeids_by_slice(
    plan_ids: PlanIds,
    *,
    root: Path,
    deadline: float | None = None,
    execution: _VerifySubstrate | None = None,
) -> BaselineCapture:
    """Capture each slice's own TESTS set so regression evidence stays attributed.

    ``execution`` is where the run happens: unmanaged runs use the host tree, while
    managed runs pin a READ view at the current revision so T0 and post-coder checks
    never execute project code on the controller host or compare mismatched trees.
    """
    nodeids_by_slice: dict[str, Mapping[str, bool] | None] = {}
    captures: dict[str, NodeidCapture] = {}
    errors: list[str] = []
    for record in plan_ids.slice_records:
        try:
            capture = capture_test_nodeids(
                record.test_paths,
                root=root,
                deadline=deadline,
                executor=None if execution is None else execution.executor,
                port=None if execution is None else execution.port,
            )
        except Exception as error:  # Capture uncertainty is evidence; BaseException signals still propagate.
            logger.exception("workflow nodeid capture failed for slice %s", record.slice_id)
            detail = f"nodeid capture raised {type(error).__name__}: {error}"[:TAIL_LIMIT]
            capture = NodeidCapture(nodeids=None, detail=detail)
        captures[record.slice_id] = capture
        nodeids_by_slice[record.slice_id] = capture.nodeids
        if capture.nodeids is None:
            errors.append(f"{record.slice_id}: {capture.detail or 'unusable JUnit nodeid report'}")
    return BaselineCapture(nodeids_by_slice=nodeids_by_slice, captures=captures, errors=tuple(errors))


def _baseline_payload(
    *,
    run_id: str,
    plan_ids: PlanIds,
    capture: BaselineCapture,
) -> dict[str, object]:
    records = {record.slice_id: record for record in plan_ids.slice_records}
    slices: dict[str, object] = {}
    for slice_id, snapshot in capture.nodeids_by_slice.items():
        record = records[slice_id]
        slice_payload: dict[str, object] = {
            "test_paths": list(record.test_paths),
            "nodeids": None if snapshot is None else dict(snapshot),
        }
        nodeid_capture = capture.captures.get(slice_id)
        if nodeid_capture is not None:
            slice_payload["capture"] = _nodeid_capture_payload(nodeid_capture)
        slices[slice_id] = slice_payload
    return {"schema_version": 1, "run_id": run_id, "slices": slices}


def _write_json_exclusive(path: Path, payload: Mapping[str, object]) -> None:
    """Create a private JSON file exactly once; never replace an existing T0."""
    with _private_artifact_directory(path.parent) as parent:
        descriptor = os.open(
            path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.fsync(parent)
        except Exception:
            os.unlink(path.name, dir_fd=parent)
            raise


def capture_baseline(
    path: Path,
    plan_ids: PlanIds,
    *,
    root: Path,
    run_id: str,
    deadline: float | None = None,
    execution: _VerifySubstrate | None = None,
) -> BaselineCapture:
    """Capture and write the one permitted T0 snapshot before coder dispatch (CT85/86)."""
    captured = _capture_nodeids_by_slice(plan_ids, root=root, deadline=deadline, execution=execution)
    try:
        _write_json_exclusive(path, _baseline_payload(run_id=run_id, plan_ids=plan_ids, capture=captured))
    except (OSError, ValueError, TypeError) as error:
        detail = f"verify_baseline.json was not created without overwriting: {error}"
        logger.error("workflow verification baseline: %s", detail)
        return BaselineCapture(
            nodeids_by_slice=dict.fromkeys(captured.nodeids_by_slice),
            captures=captured.captures,
            errors=(*captured.errors, detail),
        )
    return captured


def _capture_stage_baseline(ctx: WorkflowContext, plan_ids: PlanIds) -> BaselineCapture:
    """Capture T0 through ``_pinned_verify_substrate`` so managed runs never test the host."""
    try:
        with _pinned_verify_substrate(ctx) as substrate:
            return capture_baseline(
                ctx.artifact_paths.verify_baseline,
                plan_ids,
                root=ctx.workspace,
                run_id=ctx.run_id,
                deadline=ctx.deadline_mono,
                execution=substrate,
            )
    except Exception as error:  # noqa: BLE001 -- Managed pin/profile failures fail closed with zero host subprocesses.
        logger.warning(
            "workflow verification T0 substrate failed (run=%s): %s",
            ctx.run_id,
            type(error).__name__,
        )
        code = getattr(error, "code", None)
        code_tag = f"[{code}] " if isinstance(code, str) and code else ""
        failed = BaselineCapture(
            nodeids_by_slice={record.slice_id: None for record in plan_ids.slice_records},
            errors=(f"T0 verify substrate failed ({type(error).__name__}): {code_tag}{error}",),
        )
        try:
            _write_json_exclusive(
                ctx.artifact_paths.verify_baseline,
                _baseline_payload(run_id=ctx.run_id, plan_ids=plan_ids, capture=failed),
            )
        except (OSError, ValueError, TypeError):
            pass
        return failed


def load_verify_baseline(path: Path, plan_ids: PlanIds, *, run_id: str) -> BaselineCapture:
    """Load the immutable T0 maps for a later coder repair stage; malformed is ERROR."""
    empty = {record.slice_id: None for record in plan_ids.slice_records}
    try:
        with _private_artifact_directory(path.parent) as directory:
            payload = _read_admission_at(directory, path.name)
    except (OSError, ValueError) as error:
        return BaselineCapture(nodeids_by_slice=empty, errors=(f"T0 baseline unavailable: {error}",))
    if (
        not isinstance(payload, dict)
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
        or payload.get("run_id") != run_id
    ):
        return BaselineCapture(nodeids_by_slice=empty, errors=("T0 baseline schema or run_id does not match",))
    stored_slices = payload.get("slices")
    if not isinstance(stored_slices, dict):
        return BaselineCapture(nodeids_by_slice=empty, errors=("T0 baseline has no slices mapping",))

    topology = {
        record.slice_id: sorted({Path(p).as_posix() for p in record.test_paths}) for record in plan_ids.slice_records
    }
    actual = {
        key: sorted({Path(p).as_posix() for p in value.get("test_paths", [])})
        for key, value in stored_slices.items()
        if isinstance(value, dict)
        and isinstance(value.get("test_paths"), list)
        and all(isinstance(p, str) for p in value["test_paths"])
    }
    if actual != topology or set(stored_slices) != set(topology):
        return BaselineCapture(nodeids_by_slice=empty, errors=("T0 slice/test-path topology does not match",))

    maps: dict[str, Mapping[str, bool] | None] = {}
    errors: list[str] = []
    for record in plan_ids.slice_records:
        slice_payload = stored_slices.get(record.slice_id)
        raw_nodeids = slice_payload.get("nodeids") if isinstance(slice_payload, dict) else None
        if raw_nodeids is None:
            maps[record.slice_id] = None
            errors.append(f"{record.slice_id}: T0 nodeid snapshot is unavailable")
            continue
        if not isinstance(raw_nodeids, dict) or any(
            not isinstance(nodeid, str) or type(passed) is not bool for nodeid, passed in raw_nodeids.items()
        ):
            maps[record.slice_id] = None
            errors.append(f"{record.slice_id}: T0 nodeid snapshot is malformed")
            continue
        maps[record.slice_id] = dict(raw_nodeids)
    return BaselineCapture(nodeids_by_slice=maps, errors=tuple(errors))


def _slice_verification_payload(result: SliceVerification) -> dict[str, object]:
    """Serialize one slice explicitly at the artifact boundary."""
    return {
        "slice_id": result.slice_id,
        "verdict": result.verdict.value,
        "test_paths": list(result.test_paths),
        "commands": [_command_result_payload(command) for command in result.command_results],
        "kill_checks": [
            {
                "contract_id": contract_id,
                "operator": check.directive.operator.value,
                "path": check.directive.path,
                "symbol": check.directive.symbol,
                "callee": check.directive.callee,
                "verdict": check.verdict.value,
                "detail": check.detail,
                "duration_s": check.duration_s,
            }
            for contract_id, check in result.kill_checks
        ],
        "regression_nodeids": list(result.regression_nodeids),
        "failed_nodeids": list(result.failed_nodeids),
        "detail": result.detail,
    }


def _claim_payload(claim: ClaimEvidence) -> dict[str, object]:
    """One contract's evidence, explicitly: what ran, whether it passed, and the mutation."""
    mutation = claim.mutation
    return {
        "contract_id": claim.contract_id,
        "test_id": claim.test_id,
        "nodeid": claim.nodeid,
        "outcome": claim.outcome,
        "proven": claim.proven,
        "mutation": (
            None
            if mutation is None
            else {
                "operator": mutation.operator,
                "target": mutation.target,
                "verdict": mutation.verdict,
                "detail": mutation.detail,
            }
        ),
        "detail": claim.detail,
    }


def _sealed_attempt_payload(attempt: VerificationAttempt) -> dict[str, object]:
    """The attempt's own facts (F10 item 4): route, identity, claims, authorship.

    Deliberately additive. The legacy keys stay where they were, because the legacy route still
    writes them and the eval contract they serve is unchanged; what was missing is the part a
    reader needs to tell *which* candidate, *which* seal and *which* claims a verdict is about.
    """
    identity = attempt.identity
    return {
        "route": attempt.route,
        "identity": (
            None
            if identity is None
            else {
                "plan_sha256": identity.plan_sha256,
                "candidate_revision_id": identity.candidate_revision_id,
                "sealed_revision_id": identity.sealed_revision_id,
                "seal_sha256": identity.seal_sha256,
                "closure_sha256": identity.closure_sha256,
                "profile_id": identity.profile_id,
                "substrate": identity.substrate,
                "run_id": identity.run_id,
                "attempt": identity.attempt,
                "repair_round": identity.repair_round,
                "mode": identity.mode,
            }
        ),
        "claims": [_claim_payload(claim) for claim in attempt.claims],
        "commands_authored_by": sorted({command.authored_by for command in attempt.commands}),
        "attested": list(attempt.attested),
        "pending": list(attempt.pending),
        "contracts_total": attempt.contracts_total,
        "attestations": [
            {
                "contract_id": record.contract_id,
                "invariant_id": record.invariant_id,
                "reason": record.reason,
                "route": record.route,
                "artifact": record.artifact,
                "owner": record.owner,
                "reviewed_at": record.reviewed_at,
                "scope_sha256": record.scope_sha256,
            }
            for record in attempt.attestations
        ],
        "kill_required": list(attempt.kill_required),
        # N2: declared, not executed. ``kill_required`` alone cannot tell "none declared" from
        # "declared and never run", and those are different facts about the plan.
        "kill_declared": [
            {"target_id": target.target_id, "ct_id": target.ct, "test_id": target.test_id, "executed": False}
            for target in attempt.kill_declared
        ],
        "attempt_blocking": attempt.blocking,
        "first_reason": attempt.first_reason,
    }


def _verification_attempt_payload(
    verification: PlanVerification,
    *,
    mode: str,
    repair_round: int,
    attempt: VerificationAttempt | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "mode": mode,
        "repair_round": repair_round,
        # The gate's own verdict plus the attempt's, so a disagreement can never be smoothed into
        # a pass: either face of the same evidence may block.
        "blocking": verification.blocking or (attempt is not None and attempt.blocking),
        "plan_commands": [_command_result_payload(result) for result in verification.plan_command_results],
        "slices": [_slice_verification_payload(result) for result in verification.slice_verifications],
        "errors": list(verification.errors),
    }
    if attempt is not None:
        payload.update(_sealed_attempt_payload(attempt))
    return payload


def write_verification(
    path: Path,
    verification: PlanVerification,
    *,
    run_id: str,
    mode: str,
    repair_round: int,
    plan_ref: PlanRef | None = None,
    deadline: float | None = None,
    attempt: VerificationAttempt | None = None,
) -> None:
    """Append typed attempt evidence with the established private locked atomic IO.

    ``attempt`` is the sealed route's own record (F10): when it is supplied the entry carries
    ``route``, ``identity`` and ``claims`` beside the legacy keys, and its verdict is OR-ed into
    ``blocking``. The legacy route passes nothing and its artifact is byte-for-byte unchanged.
    """
    with _private_artifact_directory(path.parent) as parent:
        with _admission_lock(parent, deadline=deadline):
            try:
                previous = _read_admission_at(parent, path.name)
            except FileNotFoundError:
                previous = {"schema_version": 1, "run_id": run_id, "attempts": []}
            if (
                not isinstance(previous, dict)
                or type(previous.get("schema_version")) is not int
                or previous.get("schema_version") != 1
                or previous.get("run_id") != run_id
                or not isinstance(previous.get("attempts"), list)
            ):
                raise ValueError("existing verification.json has an incompatible run identity or schema")
            attempts = list(previous["attempts"])
            entry = _verification_attempt_payload(verification, mode=mode, repair_round=repair_round, attempt=attempt)
            if plan_ref is not None:
                entry["plan_ref"] = asdict(plan_ref)
            attempts.append(entry)
            _replace_private_json(parent, path.name, {"schema_version": 1, "run_id": run_id, "attempts": attempts})


def _verification_lines(path: Path) -> tuple[str, ...]:
    """Render the latest observed per-slice verdicts for the eval evidence block (CT77)."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        attempts = payload.get("attempts") if isinstance(payload, dict) else None
        if not isinstance(attempts, list) or not attempts or not isinstance(attempts[-1], dict):
            return ()
        latest = attempts[-1]
        mode = latest.get("mode", "unknown")
        lines = [f"Harness verify gate (mode={mode}, repair_round={latest.get('repair_round', '?')}):"]
        slices = latest.get("slices", [])
        if isinstance(slices, list):
            for item in slices:
                if isinstance(item, dict) and isinstance(item.get("slice_id"), str):
                    lines.append(f"- {item['slice_id']}: {item.get('verdict', 'unknown')}")
        for error in latest.get("errors", []):
            lines.append(f"- Harness error: {error}")
        return tuple(lines)
    except FileNotFoundError:
        return ()
    except (OSError, json.JSONDecodeError, TypeError, AttributeError) as error:
        logger.warning("workflow verification evidence unavailable at %s: %s", path, error)
        return (f"Harness verification artifact unavailable: {error}",)


def _verification_is_indeterminate(verification: PlanVerification) -> bool:
    """Whether the verifier could not determine a trustworthy pass/fail result."""
    return bool(
        verification.errors
        or any(result.outcome is CommandOutcome.ERROR for result in verification.plan_command_results)
        or any(
            result.verdict is SliceVerdict.ERROR
            or any(command.outcome is CommandOutcome.ERROR for command in result.command_results)
            for result in verification.slice_verifications
        )
    )


def _verification_block_detail(verification: PlanVerification) -> str:
    """Return one concise, deterministic reason the enforce gate did not pass."""
    if verification.errors:
        return verification.errors[0]
    for result in verification.plan_command_results:
        if result.outcome is not CommandOutcome.PASS:
            return (
                f"plan command {result.command!r}: outcome={result.outcome.value}, "
                f"exit_code={result.exit_code}, stderr={result.stderr_tail or '(empty)'}"
            )
    for slice_result in verification.slice_verifications:
        if slice_result.verdict in {SliceVerdict.PROVEN, SliceVerdict.SKIPPED}:
            continue
        for result in slice_result.command_results:
            if result.outcome is not CommandOutcome.PASS:
                return (
                    f"{slice_result.slice_id} command {result.command!r}: outcome={result.outcome.value}, "
                    f"exit_code={result.exit_code}, stderr={result.stderr_tail or '(empty)'}"
                )
        for contract_id, check in slice_result.kill_checks:
            if check.verdict is not SliceVerdict.PROVEN:
                return f"{slice_result.slice_id} {contract_id} kill-check is {check.verdict.value}: {check.detail}"
        if slice_result.regression_nodeids:
            return f"{slice_result.slice_id} regression: {', '.join(slice_result.regression_nodeids)}"
        return f"{slice_result.slice_id} verification is {slice_result.verdict.value}: {slice_result.detail}"
    return "the harness verification gate is blocking without a more specific result"


def _effective_controller_route(
    report: EvalReport | None,
    verification: PlanVerification | None,
    *,
    gate_mode: str,
    eval_requested: bool,
    verification_required: bool = False,
    integrity_failed: bool = False,
) -> RouteDecision | None:
    """Reconcile actual eval with non-waivable evidence floors in both modes.

    Eval's non-complete route always wins (Q56). Missing required evidence or
    indeterminate verification blocks completion in observe and enforce.
    Determinate gate failures remain advisory in observe; enforce routes them
    to the existing bounded coder repair. Never replace the model EvalReport.
    """
    if integrity_failed and (report is None or report.route_decision == "complete"):
        return "blocked"
    if report is not None and report.route_decision != "complete":
        return report.route_decision
    if verification_required and verification is None:
        return "blocked"
    if verification is not None and _verification_is_indeterminate(verification):
        return "blocked"
    if report is None:
        if eval_requested:
            return "blocked"
        if verification is not None and gate_mode == "enforce" and verification.blocking:
            return "return_to_coder"
        return None
    if gate_mode == "enforce" and verification is not None and verification.blocking:
        return "return_to_coder"
    return report.route_decision


def emit_eval_report(
    *,
    report_path: Path,
    final_text: str,
    run_id: str,
    plan_id: str,
    plan_version: int,
    eval_independence: Mapping[str, object] | None = None,
) -> EvalReport:
    """Parse the eval role's final message and persist ``eval_report.json``.

    Kept as the one-call convenience wrapper for callers that need no
    post-processing. Anything that must ADJUST the report before it lands on
    disk -- S12 (drop invented slice IDs), S11b (reconcile the verdict against
    harness observation) -- must call :func:`build_eval_report` and
    :func:`write_eval_report` around its own step, NOT call this and rewrite
    the artifact afterwards.
    """
    report = build_eval_report(
        final_text,
        run_id=run_id,
        plan_id=plan_id,
        plan_version=plan_version,
        eval_independence=eval_independence,
    )
    write_eval_report(report_path, report)
    return report


def build_eval_report(
    final_text: str,
    *,
    run_id: str,
    plan_id: str,
    plan_version: int,
    eval_independence: Mapping[str, object] | None = None,
) -> EvalReport:
    """Parse the eval role's final message WITHOUT writing anything.

    Split out of :func:`emit_eval_report` because three planned steps (S12,
    S13, S11b) each need to adjust the report between parsing and persisting
    it. With parse-and-write fused, each would have had to re-open and rewrite
    ``eval_report.json`` after the fact: three writes of one file, a window in
    which the artifact on disk contradicts the routing decision, and a
    last-writer-wins ordering dependency between otherwise independent steps.

    Separating the two makes the pipeline explicit and single-write:
    ``build -> adjust -> write``.
    """
    return parse_eval_report(
        final_text,
        run_id=run_id,
        plan_id=plan_id,
        evaluation_id=f"{run_id}-eval",
        plan_version=plan_version,
        eval_independence=eval_independence,
    )


def validate_slice_ids(
    report: EvalReport,
    plan_text: str | None,
    *,
    plan_ids: PlanIds | None = None,
) -> tuple[EvalReport, tuple[str, ...]]:
    """Cross-check the evaluator's claimed slice IDs against the plan. (S12/Q16)

    Returns the adjusted report and the human-readable warnings to emit. Pure:
    it neither logs nor writes, so the decision is testable without booting a
    workflow, and the caller keeps a single write of ``eval_report.json``
    (§24 D-1 -- ``build -> adjust -> write``, never ``emit -> rewrite``).

    Three adjustments, in order:

    1. **Invented IDs are dropped.** ``_STEP_LINE_RE`` accepts any ``S<digits>``
       token, so ``- S404: PASS`` parses as a real slice. An ID absent from the
       plan is noise, not evidence, and carrying it would inflate apparent
       coverage.
    2. **Omitted slices are recorded** in ``unreported_slices``. This is the
       one that matters: invention is cosmetic, but silently DROPPING ``S7``
       from the list yields a clean ``PASS`` over unexamined work.
    3. **Q16 -- a per-slice ``fail`` forces ``REPAIR_REQUIRED``.** Before this,
       ``step_results`` was inert: a run could end ``DONE`` while carrying
       ``S7: FAIL``. Only the literal ``fail`` verdict blocks; ``partial`` and
       ``not_evaluated`` do not, because neither asserts the slice is broken
       and widening the rule would turn "the evaluator was unsure" into a hard
       route.

    Degrades to a no-op when no plan is resolvable (``plan_text is None``, or
    the plan declares no slices). Legacy plans failing extraction is expected
    and is not a kill signal, so an unparseable plan must not manufacture
    warnings about slices nobody declared.

    Comparison is exact and case-sensitive: ``S5`` and ``S5a`` are different
    slices, and folding them would report a real omission as covered.
    """
    warnings: list[str] = []

    # Q16 applies even with no plan: a reported failure is a fact about the
    # work, independent of whether the harness can see the contract.
    failed = tuple(step.step_id for step in report.step_results if step.verdict == "fail")
    if failed and report.verdict == "PASS":
        warnings.append(
            f"eval returned PASS while reporting per-slice failure(s): {', '.join(failed)}; "
            "routing to REPAIR_REQUIRED (Q16)"
        )
        report = replace(
            report,
            verdict="REPAIR_REQUIRED",
            route_decision=default_route_for_verdict("REPAIR_REQUIRED"),
            summary=f"per-slice failure reported for {', '.join(failed)}: {report.summary}",
        )

    if plan_text is None and plan_ids is None:
        return report, tuple(warnings)
    declared = (plan_ids if plan_ids is not None else extract_plan_ids(plan_text or "")).slices
    if not declared:
        return report, tuple(warnings)

    known = {canonical_slice_id(d) for d in declared}
    kept = tuple(step for step in report.step_results if canonical_slice_id(step.step_id) in known)
    invented = tuple(step.step_id for step in report.step_results if canonical_slice_id(step.step_id) not in known)
    if invented:
        warnings.append(f"eval reported slice id(s) absent from the plan, dropped: {', '.join(invented)}")

    reported = {canonical_slice_id(step.step_id) for step in kept}
    unreported = tuple(slice_id for slice_id in declared if canonical_slice_id(slice_id) not in reported)
    if unreported:
        warnings.append(f"plan slice(s) with no eval verdict: {', '.join(unreported)}")

    return replace(report, step_results=kept, unreported_slices=unreported), tuple(warnings)


def status_for_role(role: str) -> FlowStatus:
    if role == "planner":
        return "PLANNING"
    if role == "coder":
        return "CODING"
    if role == "eval":
        return "EVALUATING"
    return "CODING"


def eval_system_prompt_extra(role: str, models: ModelsConfig) -> str:
    """Return the eval system-prompt extra for a role based on independence."""
    if role != "eval" or models.eval_independence is None:
        return ""
    if models.eval_independence.stance != "adversarial":
        return ""
    return ADVERSARIAL_EVAL_STANCE_PREAMBLE


def _eval_independence_mapping(models: ModelsConfig) -> Mapping[str, object] | None:
    """Project the config's EvalIndependence to a serialisable mapping."""
    indep = models.eval_independence
    if indep is None:
        return None
    return {"disjoint": indep.disjoint, "stance": indep.stance}


EVAL_DIFF_MAX_CHARS: Final = 60_000
"""Cap on the diff embedded in the eval evidence block.

Large enough that a normal slice arrives whole, small enough that a runaway
diff cannot evict the rest of the block -- and the task itself -- from the
judge's context. Truncation is always announced, never silent.
"""

EVAL_VERIFICATION_MAX_CHARS: Final = 20_000
#: One claim's free text inside the eval block. ``ClaimEvidence.detail`` is already bounded at
#: ``DETAIL_LIMIT`` for the artifact; the block has its own budget and ten claims at 2000 characters
#: would spend it on coder-influenced text (F6).
EVAL_CLAIM_DETAIL_MAX_CHARS: Final = 300
"""Cap on detailed deterministic verification evidence sent to the evaluator."""

EVAL_DOC_PATHS: Final = ("knowledge/adr/DIGEST.md", "knowledge/adr/README.md")
"""Repo docs offered to the judge as PATHS, not pasted bodies.

Eval has ``fs_read_file``; pasting bodies would burn context on documents it
may not need. Only paths that exist are listed, so a moved doc drops out
rather than sending the judge to a dead reference.
"""


def _claim_evidence_lines(attempt: VerificationAttempt) -> list[str]:
    """Render the attempt's claims: what ran, what it proved, and who authored the command (F6).

    ``detail`` is assertion text and command output, i.e. bytes a coder can influence, so it is
    labelled ``untrusted`` and cut to the block's own budget rather than the artifact's. The
    ``proven`` word is the harness's verdict, not the coder's, and it is what the evaluator must
    read first.
    """
    lines = [
        f"- Route: {attempt.route}",
        f"- Commands authored by: {', '.join(sorted({c.authored_by for c in attempt.commands}))}",
    ]
    identity = attempt.identity
    if identity is not None:
        lines.append(
            "- Identity: plan={plan} seal={seal} closure={closure} candidate={candidate} sealed={sealed}".format(
                plan=identity.plan_sha256[:12],
                seal=(identity.seal_sha256 or "none")[:12],
                closure=(identity.closure_sha256 or "none")[:12],
                candidate=identity.candidate_revision_id,
                sealed=identity.sealed_revision_id or "none",
            )
        )
    for claim in attempt.claims:
        state = "proven" if claim.proven else "NOT proven"
        lines.append(f"- {claim.contract_id} {claim.test_id} [{state}]: {claim.outcome} at {claim.nodeid}")
        if claim.mutation is not None:
            lines.append(f"  mutation {claim.mutation.operator} {claim.mutation.target}: {claim.mutation.verdict}")
        if claim.detail:
            detail = claim.detail[:EVAL_CLAIM_DETAIL_MAX_CHARS]
            lines.append(f"  detail (untrusted): {detail}")
    for record in attempt.attestations:
        # N3/P4-8: the ids alone say *that* a contract was carried; this says who carried it, on
        # what, and when. ``owner`` and ``artifact`` are caller text, so both are cut and labelled.
        lines.append(
            f"- {record.contract_id} attested (untrusted): reason={record.reason} route={record.route} "
            f"artifact={record.artifact[:EVAL_CLAIM_DETAIL_MAX_CHARS]} "
            f"owner={(record.owner or 'none')[:EVAL_CLAIM_DETAIL_MAX_CHARS]} reviewed_at={record.reviewed_at or 'none'}"
        )
    for target in attempt.kill_declared:
        lines.append(
            f"- {target.ct} kill target {target.target_id} ({target.test_id}): declared, not executed "
            "on this route (the V2 grammar expresses attribution only)"
        )
    if attempt.attested:
        lines.append(f"- Attested elsewhere (not run here): {', '.join(attempt.attested)}")
    if attempt.pending:
        lines.append(f"- Pending deploy debt (does not block this attempt): {', '.join(attempt.pending)}")
    return lines


def _verification_evidence_lines(
    verification: PlanVerification,
    *,
    mode: str,
    repair_round: int,
    artifact_path: Path,
    attempt: VerificationAttempt | None = None,
) -> tuple[str, ...]:
    """Render the current attempt's authoritative facts for the evaluator."""
    lines = [
        f"Harness verify gate (mode={mode}, repair_round={repair_round}, blocking={verification.blocking}):",
        f"Detailed artifact: {artifact_path}",
    ]
    if attempt is not None:
        lines.extend(_claim_evidence_lines(attempt))
    for result in verification.plan_command_results:
        lines.append(
            f"- Plan command: outcome={result.outcome.value}, exit_code={result.exit_code}, "
            f"duration_s={result.duration_s:.3f}; {result.command}"
        )
        if result.stderr_tail:
            lines.append(f"  stderr tail: {result.stderr_tail}")
    for slice_result in verification.slice_verifications:
        lines.append(f"- {slice_result.slice_id}: {slice_result.verdict.value}")
        if slice_result.detail:
            lines.append(f"  detail: {slice_result.detail}")
        for result in slice_result.command_results:
            lines.append(
                f"  verify command: outcome={result.outcome.value}, exit_code={result.exit_code}, "
                f"duration_s={result.duration_s:.3f}; {result.command}"
            )
            if result.stderr_tail:
                lines.append(f"    stderr tail: {result.stderr_tail}")
        for contract_id, check in slice_result.kill_checks:
            lines.append(f"  {contract_id} kill-check: {check.verdict.value}")
            if check.detail:
                lines.append(f"    detail: {check.detail}")
        if slice_result.regression_nodeids:
            lines.append(f"  regression nodeids: {', '.join(slice_result.regression_nodeids)}")
        if slice_result.failed_nodeids:
            lines.append(f"  currently failing nodeids: {', '.join(slice_result.failed_nodeids)}")
    for error in verification.errors:
        lines.append(f"- Harness error: {error}")
    rendered = "\n".join(lines)
    if len(rendered) > EVAL_VERIFICATION_MAX_CHARS:
        rendered = (
            rendered[:EVAL_VERIFICATION_MAX_CHARS]
            + f"\n[verification evidence truncated at {EVAL_VERIFICATION_MAX_CHARS} characters; "
            f"full artifact: {artifact_path}]"
        )
    return tuple(rendered.splitlines())


def _eval_evidence_block(
    ctx: WorkflowContext,
    *,
    verification: PlanVerification | None = None,
    repair_round: int = 0,
) -> str:
    """Build the evidence preamble handed to the eval stage. (S13)

    **Why this exists.** The eval prompt asks the judge whether the coder
    satisfied "the planner's execution contract", but eval received only
    ``ctx.task_for(role)`` -- a task string. The contract it is asked to check
    against was never handed to it, while under the default
    ``fresh=index == 0`` it sits inside the coder's own transcript, reading the
    defendant's success narration as context. This block supplies, as text the
    HARNESS controls rather than text the coder wrote: the plan path, the
    declared slice IDs, what actually changed on disk, and where the reference
    docs live.

    Managed revision metadata is read-only and advisory. If the sealed revision
    pair or its metadata comparison is unavailable, the block says so explicitly;
    it never falls back to controller-side Git and never reports unavailable as
    an empty change set. The current eval remains an LLM judgment; verify evidence
    below is still the separate mechanical gate.

    Returns ``""`` when nothing could be gathered, so the caller appends
    nothing rather than a hollow frame.
    """
    lines: list[str] = []

    plan_text = ctx.plan_text()
    if ctx.admission is not None:
        lines.append(f"Admitted Plan-ID: {ctx.plan_identity()}")
        lines.append(f"Admitted PlanRef SHA256: {ctx.admission.snapshot.ref.sha256}")
    if ctx.plan_path is not None:
        lines.append(f"Plan: {ctx.plan_path}")
        if plan_text is not None:
            slices = (ctx.admission.snapshot.ids if ctx.admission is not None else extract_plan_ids(plan_text)).slices
            if slices:
                # IDs only. The plan can run to thousands of lines and pasting
                # it would evict the diff -- the judge has fs_read_file.
                lines.append(f"Plan slices to judge ({len(slices)}): {', '.join(slices)}")
        lines.append("Read the plan for the execution contract; do not infer it from the transcript.")

    if verification is None:
        lines.extend(_verification_lines(ctx.artifact_paths.verification))
    else:
        lines.extend(
            _verification_evidence_lines(
                verification,
                mode=ctx.verify_gate_mode,
                repair_round=repair_round,
                artifact_path=ctx.artifact_paths.verification,
                # F10: the sealed route's claim-level evidence lives on the admission record, so
                # the evaluator reads the same attempt the gate judged rather than a re-derivation.
                attempt=None if ctx.admission is None else ctx.admission.last_attempt,
            )
        )

    pair = ctx.managed_revision_pair
    if ctx.managed_execution is None or pair.base_revision_id is None or pair.target_revision_id is None:
        lines.append("Changed files: unavailable (managed sealed-revision evidence was not captured).")
    else:
        try:
            revision_diff = ctx.managed_execution.revision_changes(
                pair.base_revision_id,
                pair.target_revision_id,
                deadline=ctx.deadline_mono,
            )
            changes = revision_diff["changes"]
            total_changes = revision_diff["total_changes"]
            truncated = revision_diff["truncated"]
            if (
                not isinstance(changes, list)
                or type(total_changes) is not int
                or total_changes < len(changes)
                or type(truncated) is not bool
                or truncated != (total_changes > len(changes))
                or any(
                    not isinstance(item, dict)
                    or not isinstance(item.get("path"), str)
                    or item.get("change") not in {"added", "modified", "deleted"}
                    for item in changes
                )
            ):
                raise ValueError("managed revision metadata is malformed")
        except Exception as error:  # noqa: BLE001 — incomplete advisory evidence is never treated as success
            logger.warning("workflow: managed revision evidence unavailable (%s)", type(error).__name__)
            lines.append("Changed files: unavailable (managed sealed-revision comparison failed).")
        else:
            if total_changes == 0:
                lines.append(
                    "Changed files: NONE between the sealed managed revisions "
                    f"{pair.base_revision_id} and {pair.target_revision_id}."
                )
            else:
                entries = [f"- {item['change']}: {item['path']}" for item in changes]
                body = "\n".join(entries)
                if len(body) > EVAL_DIFF_MAX_CHARS:
                    body = body[:EVAL_DIFF_MAX_CHARS] + (
                        f"\n[metadata display truncated at {EVAL_DIFF_MAX_CHARS} characters; "
                        "read relevant files with fs_read_file]"
                    )
                lines.append(
                    f"Changed files between sealed managed revisions "
                    f"({total_changes} total; metadata_truncated={truncated}):\n{body}"
                )
                lines.append(
                    "Revision records contain paths only; read relevant current files with fs_read_file before judging."
                )

    existing_docs = [name for name in EVAL_DOC_PATHS if (ctx.workspace / name).is_file()]
    if existing_docs:
        lines.append(f"Reference docs (read as needed): {', '.join(existing_docs)}")

    if not lines:
        return ""
    return "## Evidence supplied by the harness\n\n" + "\n".join(lines)


# ── Stage dispatch ─────────────────────────────────────────────────────────


def _stage_planner_dispatch(
    ctx: WorkflowContext, role: str, dispatch: PlannerDispatch | None
) -> PlannerDispatch | None:
    if role != "planner":
        if dispatch is not None:
            raise PlannerDispatchError
        return None
    active = None
    if ctx.plan_path is not None:
        path = ctx.plan_path
        active = (path.relative_to(ctx.workspace.resolve()) if path.is_absolute() else path).as_posix()
    if dispatch is None:
        if ctx.acquisition is not None and ctx.admission is None and active is None:
            # D-V2-9 (CT-2.3): a create-authorized run does not *choose* a target,
            # it authors one. The route decides the kind, so the planner stage gets
            # a writer scoped to ``worklogs/<slug>/`` instead of a read-only
            # selector -- and the scaffold, written by the harness through the same
            # port, is what makes the first write legal. A select-only route keeps
            # ACQUISITION: it has no directory to write into.
            slug = ctx.acquisition.project_slug
            if slug is not None:
                return PlannerDispatch(
                    PlannerDispatchKind.CREATE_NEW_PROJECT, ctx.run_id, authoring_root=f"worklogs/{slug}"
                )
            return PlannerDispatch(PlannerDispatchKind.ACQUISITION, ctx.run_id)
        return PlannerDispatch(PlannerDispatchKind.ORDINARY_PLANNING, ctx.run_id, active)
    if not isinstance(dispatch, PlannerDispatch) or dispatch.run_id != ctx.run_id or dispatch.active_plan != active:
        raise PlannerDispatchError
    return dispatch


def _mark_integrity_failure(ctx: WorkflowContext, reason: str) -> None:
    if ctx.admission is not None:
        ctx.admission.failure = reason


def _integrity_failed(ctx: WorkflowContext) -> bool:
    return ctx.admission is not None and ctx.admission.failure is not None


def _plan_integrity_errors(ctx: WorkflowContext) -> tuple[str, ...]:
    if ctx.admission is None:
        return ()
    try:
        _check_admission_source(ctx)
    except PlanRefError as error:
        reason = f"plan-ref/{error.rule}"
        _mark_integrity_failure(ctx, reason)
        return (reason,)
    return ()


def _stage_eval_report(ctx: WorkflowContext, final_text: str, *, progress: WorkflowProgress) -> EvalReport:
    """Build, adjust, then write the eval report -- exactly one write (S12/§24 D-1).

    Calling ``emit_eval_report`` here and rewriting afterwards would persist a report that
    contradicts the routing decision for the window in between, which is why this stays one
    function with one write.
    """
    report = build_eval_report(
        final_text,
        run_id=ctx.run_id,
        # S12a: the plan's declared ID when one was supplied, else run_id.
        plan_id=ctx.plan_identity(),
        plan_version=progress.plan_version,
        eval_independence=_load_eval_independence(ctx),
    )
    report, slice_warnings = validate_slice_ids(
        report,
        ctx.plan_text(),
        plan_ids=ctx.admission.snapshot.ids if ctx.admission is not None else None,
    )
    for warning in slice_warnings:
        logger.warning("workflow eval-report: %s (run=%s)", warning, ctx.run_id)
        print(f"fa workflow: {warning}", file=sys.stderr)
    _write_stage_eval_report(ctx, report)
    return report


def _write_stage_eval_report(ctx: WorkflowContext, report: EvalReport) -> None:
    if ctx.admission is not None:
        ctx.admission.last_eval_report = report
    saved = True
    try:
        write_eval_report(ctx.artifact_paths.eval_report, report)
    except (OSError, ValueError):
        if ctx.admission is None:
            raise
        saved = False
        _mark_integrity_failure(ctx, "artifact-io/append-failed")
        print("fa workflow: eval report storage error: append-failed", file=sys.stderr)
    print(
        f"fa workflow: eval verdict={report.verdict} route={report.route_decision} "
        f"persisted={saved} artifact={ctx.artifact_paths.eval_report}",
        file=sys.stderr,
    )


def _stage_plan(ctx: WorkflowContext) -> tuple[PlanIds, str | None]:
    if ctx.admission is not None:
        return ctx.admission.snapshot.ids, None
    text = ctx.plan_text()
    error = None
    if text is None:
        error = (
            "plan artifact was not supplied before coder dispatch"
            if ctx.plan_path is None
            else f"plan artifact was unreadable before coder dispatch: {ctx.plan_path}"
        )
    return extract_plan_ids(text) if text is not None else PlanIds(), error


def _needs_baseline(ctx: WorkflowContext, progress: WorkflowProgress) -> bool:
    state = ctx.admission
    if state is None:
        return progress.repair_round == 0
    if state.baseline != "NOT_CAPTURED":
        return False
    state.baseline = "FAILED"  # Reserve once, including capture/storage failure.
    try:
        ctx.artifact_paths.verify_baseline.lstat()  # Existence only; loader authorizes via descriptors.
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return False


def _coder_admission_ready(ctx: WorkflowContext, baseline: BaselineCapture) -> bool:
    state = ctx.admission
    if state is None:
        return True
    if baseline.errors:
        state.baseline = "FAILED"
        _admission_failed(ctx, "baseline-unavailable")
        return False
    state.baseline = "CAPTURED"
    try:
        _check_admission_source(ctx)
    except PlanRefError as error:
        _admission_error(ctx, error)
        return False
    return True


def _load_eval_independence(ctx: WorkflowContext) -> Mapping[str, object] | None:
    try:
        from fa.providers import load_models_config_from_path

        models = load_models_config_from_path(ctx.config.expanduser().resolve(), require_api_keys=False)
        return _eval_independence_mapping(models)
    except (ConfigurationError, OSError):
        logger.warning("workflow eval independence unavailable (run=%s)", ctx.run_id)
        return None


def _scoped_stage_failed(dispatch: PlannerDispatch | None, sink: list[SessionOutcome]) -> bool:
    # Only candidate-owning stages (ADMISSION_REPAIR, EVAL_REPLAN) have a staged
    # buffer whose write/pr_prepare fault invalidates the attempt. ACQUISITION
    # runs before admission and must reach `_stage_acquisition_choice` when exit_code == 0.
    if dispatch is None or not dispatch.owns_candidate:
        return False
    return (
        not sink or sink[-1].exit_code != 0 or bool({"fs_write_file", "pr_prepare"}.intersection(sink[-1].failed_tools))
    )


def _announce_stage(ctx: WorkflowContext, role: str, progress: WorkflowProgress, transition_reason: str) -> None:
    try:
        _persist_flow_state(
            ctx.artifact_paths.flow_state,
            FlowState(
                run_id=ctx.run_id,
                task=(ctx.base_task or ""),
                status=status_for_role(role),
                active_role=role,
                active_plan_id=ctx.run_id,
                active_plan_version=progress.plan_version,
                repair_round=progress.repair_round,
                replan_round=progress.replan_round,
                last_actor="workflow",
                last_transition_reason=transition_reason,
            ),
        )
    except _WorkflowStorageError:
        if role != "eval" or ctx.admission is None:
            raise
        # Q55: a missing transition receipt cannot erase a successful coder's judge.
        # The in-memory integrity floor still prevents success, even if writes recover.
        _mark_integrity_failure(ctx, "artifact-io/append-failed")
        print("fa workflow: eval transition storage error: append-failed", file=sys.stderr)


def _acquisition_stage_task(ctx: WorkflowContext, stage_task: str | None) -> str | None:
    """Attach pinned project/incomplete lists to the initial acquisition task (Q145, Q151=A)."""
    substrate = ctx.acquisition
    if substrate is None:
        return stage_task
    # D-V2-9: a create-authorized run is an *authoring* stage. It gets no menu to
    # choose from and no JSON to emit -- it fills the scaffold that is already in
    # its view. Stating the closed JSON shapes here would be the P0-1/P2-3 drift
    # again, so the two routes get different task text rather than one text with a
    # conditional sentence.
    if substrate.project_slug is not None:
        return _authoring_stage_task(stage_task, slug=substrate.project_slug)
    projects_line = ", ".join(substrate.project_names) if substrate.project_names else "(none)"
    incomplete_line = ", ".join(substrate.incomplete_names) if substrate.incomplete_names else "(none)"
    lines = [
        "Acquisition context (pinned read-only view):",
        f"- Projects (SELECT_EXISTING): {projects_line}",
        (
            "- Incomplete (do NOT select or bootstrap over these slugs; "
            f"return NEEDS_CLARIFICATION with MISSING_CONTEXT if targeted): {incomplete_line}"
        ),
        # CT-2.1: the route the planner is *allowed* to take is stated, because it is
        # enforced. Offering creation to a run that may only select produces a
        # well-formed bootstrap the controller must then refuse.
        "- Project creation is NOT authorized for this call: return SELECT_EXISTING or NEEDS_CLARIFICATION.",
        "- If no existing project fits the goal, return NEEDS_CLARIFICATION with reason AMBIGUOUS_PROJECT.",
    ]
    block = "\n".join(lines)
    return f"{stage_task}\n\n{block}" if stage_task else block


def _deadline_refusal(ctx: WorkflowContext, role: str, progress: WorkflowProgress) -> StageResult | None:
    """The deadline refusal for this stage, or ``None`` while budget remains."""
    if not _deadline_exceeded(ctx):
        return None
    _write_deadline_state(ctx, role, progress=progress)
    return StageResult(role=role, exit_code=WORKFLOW_DEADLINE_EXIT_CODE)


def _stage_dispatch_outcome(
    ctx: WorkflowContext, role: str, planner_dispatch: PlannerDispatch | None
) -> tuple[PlannerDispatch | None, StageResult | None]:
    """The stage's dispatch, or the refusal that ends the stage before it runs.

    D-V2-9.2 lives here rather than in ``_run_stage`` for the same reason the
    deadline check is one branch there and not five: the refusal belongs to the
    dispatch decision, and the stage body is already at its complexity ceiling.
    """
    dispatch = _stage_planner_dispatch(ctx, role, planner_dispatch)
    collision = _authoring_collision(ctx, dispatch)
    if collision is None:
        return dispatch, None
    return dispatch, StageResult(role=role, exit_code=_refusal_exit_code(ctx, collision))


def _authoring_collision(ctx: WorkflowContext, dispatch: PlannerDispatch | None) -> PlanRefError | None:
    """Whether the name this stage would create already exists (D-V2-9.2).

    Only the authoring kind can collide, so every other stage returns ``None``
    immediately -- the check is part of the dispatch, not of the stage.

    The answer comes from the pinned acquisition inventory, which already
    distinguishes a complete project from an incomplete ``worklogs/<slug>/``:
    either way the directory exists, and a create can only refuse. Returning a
    ``PlanRefError`` rather than raising keeps the caller's refusal path -- the
    same one every other closed rule takes -- instead of a new exception family.
    """
    if dispatch is None or dispatch.kind is not PlannerDispatchKind.CREATE_NEW_PROJECT:
        return None
    root = dispatch.authoring_root
    if root is None:  # __post_init__ refused this already; a create with no root cannot be
        return PlanRefError("bootstrap-collision")
    slug = root.removeprefix("worklogs/")
    substrate = ctx.acquisition
    if substrate is None:
        return None
    if slug in substrate.project_names or slug in substrate.incomplete_names:
        logger.warning("create refused: worklogs/%s already exists (run=%s)", slug, ctx.run_id)
        return PlanRefError("bootstrap-collision")
    return None


def _authoring_stage_task(stage_task: str | None, *, slug: str) -> str:
    """The task text for the stage that owns a new project's documents (D-V2-9).

    It names the files that already exist and says plainly that they are empty:
    the planner's job is to fill them, not to decide what the project is called or
    to emit a choice. The last line is the one a model needs to know before it
    writes anything -- the harness publishes the whole tree as one revision, so a
    write is not visible to the run until the stage ends.
    """
    root = f"worklogs/{slug}"
    lines = [
        "## This run creates a new project",
        "",
        f"The harness has already published the empty scaffold of `{root}/`. Fill it:",
        "",
        f"- `{root}/roadmap.md` — `## Intent` and `## Out of scope`, under the front matter already there.",
        f"- `{root}/increments/increment-01-initial-plan.md` — `## INVARIANTS`, then one `## SLICE<N>: <name>`",
        "  per slice, each with `STEPS:`, `## CONTRACTS`, `## ACCEPTANCE`, `## KILL-TARGETS`,",
        "  `## STEP-EXIT-CHECKS` and its step list.",
        f"- `{root}/open-questions.md` — the questions that gate scope, or leave it as it is.",
        f"- `{root}/ledger.md` — the first entry.",
        f"- `{root}/acceptance/tests/` — the test modules your selectors name.",
        "",
        "The project slug and the increment are fixed; do not restate or change them.",
        "Every write lands in one revision that the harness publishes when this stage ends,",
        "so nothing you write is visible to you until then. Do not emit a JSON choice.",
    ]
    block = "\n".join(lines)
    return f"{stage_task}\n\n{block}" if stage_task else block


def _stage_task(
    ctx: WorkflowContext,
    role: str,
    verification: PlanVerification | None,
    repair_round: int,
    *,
    dispatch: PlannerDispatch | None = None,
) -> str | None:
    # S13: the judge is handed the contract and the evidence. Eval only --
    # the coder and planner already have the plan by other means, and a diff
    # of the coder's own work is not input to writing it.
    stage_task = ctx.task_for(role)
    if dispatch is not None and dispatch.kind is PlannerDispatchKind.ACQUISITION:
        return _acquisition_stage_task(ctx, stage_task)
    if role == "eval":
        evidence = _eval_evidence_block(ctx, verification=verification, repair_round=repair_round)
        if evidence:
            # Appended, never substituted: the task states what to judge and
            # the block states what to judge it against.
            stage_task = f"{stage_task}\n\n{evidence}" if stage_task else evidence

    return stage_task


def _capture_managed_revision_boundary(ctx: WorkflowContext, role: str, *, after_stage: bool = False) -> None:
    """Capture the writer's published revision IDs around one coder dispatch."""
    if role != "coder":
        return
    pair = ctx.managed_revision_pair
    if after_stage:
        if ctx.managed_execution is not None:
            pair.target_revision_id = ctx.managed_execution.current_revision_id
        return
    pair.base_revision_id = ctx.managed_execution.current_revision_id if ctx.managed_execution is not None else None
    pair.target_revision_id = None


def _consume_initial_planner_context(
    ctx: WorkflowContext,
    *,
    role: str,
    progress: WorkflowProgress,
    dispatch: PlannerDispatch | None,
) -> str:
    """Release the one-shot parent chat snapshot strictly to the initial planner."""
    if (
        role != "planner"
        or progress.repair_round != 0
        or progress.replan_round != 0
        or (dispatch is not None and dispatch.owns_candidate)
        or not ctx.initial_planner_slot.text
        or ctx.initial_planner_slot.consumed
    ):
        return ""
    ctx.initial_planner_slot.consumed = True
    return ctx.initial_planner_slot.text


def _run_stage(
    ctx: WorkflowContext,
    role: str,
    *,
    fresh: bool,
    progress: WorkflowProgress,
    transition_reason: str,
    run_stage_fn: Callable[..., int],
    prior_verification: PlanVerification | None = None,
    planner_dispatch: PlannerDispatch | None = None,
    candidate_seed_text: str | None = None,
) -> StageResult:
    """Dispatch one role session and, for ``eval``, persist its report.

    Writes a pre-dispatch FlowState mirror so the active role / repair round is
    inspectable even mid-run, then runs the role through ``run_stage_fn``. For
    the ``eval`` role the terminal outcome is captured and translated into
    ``eval_report.json``.

    S4b/RK6 — the deadline is checked HERE, at the single choke point every
    dispatch funnels through (four call sites today), rather than at each call
    site: adding or removing a pipeline mode then cannot silently escape the
    cap. The check is cooperative and cannot interrupt a stage already in
    flight, so the honest worst case is ``deadline + one stage``. That is
    acceptable because a single stage is already bounded by ``max_iterations``
    and ``bash_timeout_seconds``; the unbounded quantity was the NUMBER of
    stages, which is exactly what this caps.
    """
    dispatch, refusal = _stage_dispatch_outcome(ctx, role, planner_dispatch)
    progress = _admission_progress(ctx, progress)
    refusal = refusal or _deadline_refusal(ctx, role, progress)
    if refusal is not None:
        return refusal
    if role == "coder" and not _admit_plan(ctx, progress, run_stage_fn):
        return StageResult(role=role, exit_code=_admission_exit_code(ctx))
    progress = _admission_progress(ctx, progress)

    _announce_stage(ctx, role, progress, transition_reason)
    stage_task = _stage_task(ctx, role, prior_verification, progress.repair_round, dispatch=dispatch)

    stage_plan_ref = ctx.admission.snapshot.ref if ctx.admission is not None else ctx.managed_plan_ref
    initial_planner_context = _consume_initial_planner_context(ctx, role=role, progress=progress, dispatch=dispatch)

    stage_kwargs: dict[str, object] = {
        "task_pos": None,
        "task": stage_task,
        "role": role,
        "config": ctx.config,
        "workspace": ctx.workspace,
        "max_turns": ctx.max_turns,
        "run_id": ctx.run_id,
        "resume": not fresh,
        "output_mode": ctx.output_mode,
        "detail": "standard",
        "no_color": False,
        # PLAN S5a: resolved injection modes for THIS role. A separate
        # stage_kwargs key because the pre-existing L2 skill-injection site is
        # gated on ``_is_chat_role`` (coder_loop.py, ``_is_chat_role = role ==
        # "chat" and bool(scope_mode)``) -- a predicate about a DIFFERENT
        # feature -- so a workflow coder stage could never reach it. The
        # ceremony site added in S5b therefore sits OUTSIDE that gate.
        # Role gating lives in resolve_injection_modes, so a coder-only
        # injection stays off here for a planner or eval stage.
        "injection_modes": resolve_injection_modes(role, overrides=ctx.inject_overrides),
        "_managed_execution": ctx.managed_execution,
        "_managed_plan_ref": stage_plan_ref,
        **({"_initial_planner_context": initial_planner_context} if initial_planner_context else {}),
        # S3P3: says "this stage owns a candidate", so the stage boundary opens
        # the CANDIDATE view. Derived from the dispatch the controller already
        # built, never from a role name, and from the dispatch's own positive fact
        # rather than "kind is not ordinary": an ordinary planner stage owns no
        # candidate, and neither does an ACQUISITION stage -- granting either one a
        # buffer would be a capability nobody asked for, and (worse) it has no plan
        # identity to label one with (CT120).
        "_candidate_dispatch": dispatch is not None and dispatch.owns_candidate,
        **(
            {"_candidate_seed": (dispatch.candidate_target, candidate_seed_text)}
            if dispatch is not None
            and dispatch.owns_candidate
            and dispatch.candidate_target is not None
            and candidate_seed_text is not None
            else {}
        ),
    }
    if ctx.run_context is not None and ctx.session_context is not None:
        stage_kwargs.update(
            {
                "session_id": ctx.session_context.session_id,
                "_session_context": ctx.session_context,
                "_run_context": ctx.run_context,
                "_session_db": ctx.session_db,
            }
        )
    stage_args = argparse.Namespace(**stage_kwargs)
    sink: list[SessionOutcome] = []
    # D5: the sink is passed for EVERY role, not just eval.
    #
    # ``outcome_sink`` does double duty in ``_cmd_run``: it captures the
    # terminal outcome *and* suppresses that stage's own global_history
    # export (cli.py:1945), because the controller writes one aggregate row
    # for the whole workflow after all stages finish. Passing ``None`` for
    # planner and coder meant each of them exported a row under the shared
    # workflow ``run_id`` — a table keyed by ``run_id`` with INSERT OR
    # REPLACE — so the stages overwrote each other and the aggregate was
    # correct only by virtue of being written last. LOGIC-11 already
    # documented the single-aggregate intent; only eval was honouring it.
    #
    # CT86: establish T0 before the first coder dispatch, not after its edits.
    # Keep this parsed plan snapshot for the post-stage gate so a coder cannot
    # rewrite the plan during its own stage and thereby move the target.
    plan_ids_for_stage: PlanIds | None = None
    baseline_capture: BaselineCapture | None = None
    plan_read_error: str | None = None
    if role == "coder":
        plan_ids_for_stage, plan_read_error = _stage_plan(ctx)
        baseline_capture = (
            _capture_stage_baseline(ctx, plan_ids_for_stage)
            if _needs_baseline(ctx, progress)
            else load_verify_baseline(ctx.artifact_paths.verify_baseline, plan_ids_for_stage, run_id=ctx.run_id)
        )
        if not _coder_admission_ready(ctx, baseline_capture):
            return StageResult(role=role, exit_code=2)

    # ``sink`` is local to this stage and is read below for eval alone, so
    # collecting a non-eval outcome here is inert.
    dispatch_kwargs = {"planner_dispatch": dispatch} if dispatch is not None else {}
    # Admission/T0/evidence preparation may have consumed the remaining budget.
    # Check at the actual dispatch boundary, not only at entry to this function.
    if _deadline_exceeded(ctx):
        _write_deadline_state(ctx, role, progress=progress)
        return StageResult(role=role, exit_code=WORKFLOW_DEADLINE_EXIT_CODE)
    _capture_managed_revision_boundary(ctx, role)
    code = run_stage_fn(
        stage_args,
        transport=ctx.transport,
        secrets=ctx.secrets,
        outcome_sink=sink,
        **dispatch_kwargs,
    )
    _capture_managed_revision_boundary(ctx, role, after_stage=True)
    if _scoped_stage_failed(dispatch, sink):
        return StageResult(role=role, exit_code=code or 2)
    report: EvalReport | None = None
    verification: PlanVerification | None = None
    if role == "coder" and code == 0:
        plan_ids = plan_ids_for_stage or PlanIds()
        baseline = baseline_capture or BaselineCapture(nodeids_by_slice={})
        # One substrate for the whole gate: the same pinned read view answers what the
        # snapshot contains and where the commands run, so T1 and the comparison can
        # never disagree about which tree they are talking about.
        now: BaselineCapture | None = None
        sealed_attempt_for_stage: VerificationAttempt | None = None
        sealed_snapshot = _sealed_snapshot(ctx)
        try:
            with _pinned_verify_substrate(ctx) as substrate:
                if sealed_snapshot is not None:
                    # F10: the oracle is the seal, and `verify_plan` is not reached at all -- not
                    # with a guard and not with the empty id set the route carries by design.
                    verification, sealed_attempt_for_stage = _sealed_stage_verification(
                        ctx,
                        sealed_snapshot,
                        substrate,
                        attempt=progress.repair_round + 1,
                        repair_round=progress.repair_round,
                    )
                else:
                    now = _capture_nodeids_by_slice(
                        plan_ids, root=ctx.workspace, deadline=ctx.deadline_mono, execution=substrate
                    )
                    verification = verify_plan(
                        plan_ids,
                        root=ctx.workspace,
                        baseline_by_slice=baseline.nodeids_by_slice,
                        now_by_slice=now.nodeids_by_slice,
                        deadline=ctx.deadline_mono,
                        executor=None if substrate is None else substrate.executor,
                        port=None if substrate is None else substrate.port,
                    )
        except Exception as error:  # Uncertainty is a recorded ERROR, never a pass.
            logger.exception("workflow verification failed unexpectedly (run=%s)", ctx.run_id)
            verification = PlanVerification(
                plan_command_results=(),
                slice_verifications=(),
                errors=(f"verify_plan raised {type(error).__name__}: {error}",),
            )
        _record_stage_attempt(ctx, sealed_attempt_for_stage)
        capture_errors = tuple(
            error
            for error in (
                *((plan_read_error,) if plan_read_error else ()),
                *baseline.errors,
                *(now.errors if now is not None else ()),
                *_plan_integrity_errors(ctx),
            )
        )
        if capture_errors:
            verification = replace(verification, errors=(*verification.errors, *capture_errors))
        gate_mode = _gate_mode(ctx.verify_gate_mode)
        verification_saved = False
        try:
            write_verification(
                ctx.artifact_paths.verification,
                verification,
                run_id=ctx.run_id,
                mode=gate_mode,
                repair_round=progress.repair_round,
                plan_ref=ctx.admission.snapshot.ref if ctx.admission is not None else None,
                deadline=ctx.deadline_mono,
                attempt=sealed_attempt_for_stage,
            )
            verification_saved = True
        except Exception as error:  # Artifact failure stays explicit and blocks enforce mode.
            _mark_integrity_failure(ctx, "artifact-io/append-failed")
            logger.exception("workflow verification artifact write failed (run=%s)", ctx.run_id)
            verification = replace(
                verification,
                errors=(*verification.errors, f"verification.json write failed: {type(error).__name__}: {error}"),
            )
        print(
            f"fa workflow: verify gate mode={gate_mode} blocking={verification.blocking} "
            f"persisted={verification_saved} artifact={ctx.artifact_paths.verification}",
            file=sys.stderr,
        )
    if role == "eval" and code == 0 and sink:
        report = _stage_eval_report(ctx, sink[-1].final_text, progress=progress)
    terminal, acquisition_outcome, _refused = _post_stage_binding(
        ctx, role, code, sink, report, verification, dispatch=dispatch
    )
    if terminal is not None:
        return terminal
    return StageResult(
        role=role,
        exit_code=code,
        eval_report=report,
        verification=verification,
        acquisition=acquisition_outcome,
    )


def _deadline_exceeded(ctx: WorkflowContext) -> bool:
    """Return ``True`` when the run's wall-clock deadline has passed.

    ``time.monotonic`` (never ``time.time``) so a system clock adjustment
    mid-run cannot extend or collapse the budget.
    """
    return ctx.deadline_mono is not None and time.monotonic() >= ctx.deadline_mono


def _write_deadline_state(
    ctx: WorkflowContext,
    role: str,
    *,
    progress: WorkflowProgress,
) -> None:
    """Persist the terminal FlowState for a deadline-stopped pipeline.

    Deliberately terminal-and-observable rather than an exception: the run
    stays auditable and the artifacts stay well-formed, matching the existing
    budget-exhausted branches. ``DEADLINE_REASON_MARKER`` is the substring the
    ``invoke_workflow`` tool matches to set ``timed_out=True``, so it is a
    contract, not a log string.
    """
    if ctx.admission is not None:
        ctx.admission.block_exit_code = WORKFLOW_DEADLINE_EXIT_CODE
        ctx.admission.failure = DEADLINE_REASON_MARKER
    progress = _admission_progress(ctx, progress)
    elapsed = (
        ""
        if ctx.deadline_mono is None
        else f" after {max(0.0, time.monotonic() - ctx.deadline_mono):.0f}s past deadline"
    )
    _persist_flow_state(
        ctx.artifact_paths.flow_state,
        FlowState(
            run_id=ctx.run_id,
            task=(ctx.base_task or ""),
            status="FAILED",
            active_role=role,
            active_plan_id=ctx.run_id,
            active_plan_version=progress.plan_version,
            repair_round=progress.repair_round,
            replan_round=progress.replan_round,
            last_actor="workflow",
            last_transition_reason=f"{DEADLINE_REASON_MARKER}{elapsed}",
            blocked_reason=f"{DEADLINE_REASON_MARKER}; stage {role!r} was not dispatched",
        ),
    )
    print(
        f"fa workflow: {DEADLINE_REASON_MARKER} — stage {role!r} not dispatched, pipeline stopped.",
        file=sys.stderr,
    )


def _write_stage_failure_state(
    ctx: WorkflowContext,
    role: str,
    code: int,
    *,
    progress: WorkflowProgress,
) -> None:
    """Persist the fail-fast terminal state for a stage that exited non-zero.

    S4b/RK6: a deadline stop is reported through the same non-zero return path,
    but its FlowState is already written and strictly more informative. Writing
    over it with ``stage exited 124`` would erase the deadline marker the tool
    matches on, so that one code is passed through untouched.
    """
    if code == WORKFLOW_DEADLINE_EXIT_CODE:
        return

    if ctx.admission is not None and ctx.admission.failure is not None:
        return
    progress = _admission_progress(ctx, progress)
    _persist_flow_state(
        ctx.artifact_paths.flow_state,
        FlowState(
            run_id=ctx.run_id,
            task=(ctx.base_task or ""),
            status="FAILED",
            active_role=role,
            active_plan_id=ctx.run_id,
            active_plan_version=progress.plan_version,
            repair_round=progress.repair_round,
            replan_round=progress.replan_round,
            last_actor=role,
            last_transition_reason=f"stage exited {code}",
            blocked_reason=f"stage {role!r} exited {code}",
        ),
    )
    print(
        f"fa workflow: stage {role!r} exited {code} — pipeline stopped (fail-fast).",
        file=sys.stderr,
    )


def terminal_status_without_eval(*, eval_requested: bool) -> tuple[FlowStatus, str]:
    """Map a run that produced no eval report to a terminal status. (S11a/F6)

    Extracted as a pure function so the decision is testable directly and so a
    mutation that flips it dies at a named oracle rather than only inside a
    full workflow boot.

    Two genuinely different situations were previously collapsed into
    ``DONE``:

    * ``eval_requested`` -- the operator asked for a judge and none ruled
      (the stage produced no final message, so ``_run_stage``'s
      ``role == "eval" and code == 0 and sink`` guard left the report unset).
      Absence of evidence is not evidence of success: fail closed.
    * not requested -- e.g. ``fa workflow --roles coder``, a legitimate
      scratch pipeline. It still succeeded; it simply was never judged, which
      the caller records via ``FlowState.judged``.
    """
    if eval_requested:
        return "FAILED", "eval stage produced no verdict"
    return "DONE", ""


def _write_terminal_state(
    ctx: WorkflowContext,
    *,
    last_role: str,
    eval_report: EvalReport | None,
    progress: WorkflowProgress,
    reason: str,
    eval_requested: bool = False,
    route_override: RouteDecision | None = None,
) -> None:
    progress = _admission_progress(ctx, progress)
    status: FlowStatus
    route: str
    if eval_report is not None:
        status = EVAL_VERDICT_TO_TERMINAL_STATUS.get(eval_report.verdict, "FAILED")
        route = eval_report.route_decision
        blocked = eval_report.summary if eval_report.verdict == "BLOCKED" else ""
    else:
        status, blocked = terminal_status_without_eval(eval_requested=eval_requested)
        route = ""

    if route_override is not None:
        route = route_override
        if route_override == "return_to_coder":
            status = "REPAIR_REQUIRED"
        elif route_override == "return_to_planner":
            status = "REPLAN_REQUIRED"
        elif route_override == "blocked":
            status = "FAILED"
            blocked = reason

    integrity_errors = _plan_integrity_errors(ctx)
    if status == "DONE" and (_integrity_failed(ctx) or integrity_errors):
        status, route = "FAILED", "blocked"
        blocked = "workflow control-plane integrity failed"
    _persist_flow_state(
        ctx.artifact_paths.flow_state,
        FlowState(
            run_id=ctx.run_id,
            task=(ctx.base_task or ""),
            status=status,
            active_role=last_role,
            active_plan_id=ctx.run_id,
            active_plan_version=progress.plan_version,
            repair_round=progress.repair_round,
            replan_round=progress.replan_round,
            last_actor=last_role,
            last_transition_reason=reason,
            last_route_decision=route,
            blocked_reason=blocked,
            judged=eval_report is not None,
            plan_path=str(ctx.plan_path) if ctx.plan_path else "",
        ),
    )


def read_back_terminal_state(flow_state_path: Path, run_id: str) -> FlowState | None:
    """Re-read the terminal FlowState this invocation just persisted."""
    try:
        state = load_flow_state(flow_state_path)
    except (OSError, ValueError, KeyError, TypeError):
        logger.warning(
            "workflow terminal-state read-back failed for %s; falling back to exit-code semantics",
            run_id,
            exc_info=True,
        )
        return None
    if state.run_id != run_id:
        logger.warning(
            "workflow terminal-state identity mismatch at %s: artifact says %r, expected %r",
            flow_state_path,
            state.run_id,
            run_id,
        )
        return None
    if state.status not in {"DONE", "FAILED", "REPAIR_REQUIRED", "REPLAN_REQUIRED"}:
        logger.warning("workflow terminal-state read-back found only an in-progress receipt (run=%s)", run_id)
        return None
    return state


def _print_terminal_summary(
    ctx: WorkflowContext,
    *,
    n_stages: int,
    eval_report: EvalReport | None,
    repair_rounds_used: int,
    effective_route: RouteDecision | None = None,
) -> None:
    if _integrity_failed(ctx):
        print(f"fa workflow: control-plane integrity blocked run_id={ctx.run_id}", file=sys.stderr)
        return
    route = effective_route or (eval_report.route_decision if eval_report is not None else None)
    if eval_report is not None and eval_report.verdict == "PASS" and route == "complete":
        suffix = f" after {repair_rounds_used} repair round(s)" if repair_rounds_used else ""
        print(
            f"\nfa workflow: accepted (verdict=PASS){suffix} — run_id={ctx.run_id}",
            file=sys.stderr,
        )
        return
    if eval_report is not None:
        tail = f" (repair budget {repair_rounds_used} exhausted)" if repair_rounds_used else ""
        route_note = f" (eval proposed {eval_report.route_decision})" if route != eval_report.route_decision else ""
        print(
            f"\nfa workflow: {n_stages} stage(s) ran (run_id={ctx.run_id}); "
            f"eval verdict={eval_report.verdict} route={route or 'unresolved'}{route_note} "
            f"— not accepted{tail}.",
            file=sys.stderr,
        )
        return
    if route not in {None, "complete"}:
        print(
            f"\nfa workflow: {n_stages} stage(s) ran (run_id={ctx.run_id}); verification route={route} — not accepted.",
            file=sys.stderr,
        )
        return
    print(
        f"\nfa workflow: all {n_stages} stage(s) completed OK (run_id={ctx.run_id})",
        file=sys.stderr,
    )


class WorkflowRequestError(ValueError):
    """Sanitized input failure: no user-supplied values enter the diagnostic."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"invalid workflow request: {code}")


@dataclass(frozen=True, slots=True)
class _WorkflowRequest:
    roles: tuple[str, ...]
    max_repairs: int
    max_replans: int


def _workflow_roles(value: object, mode: object) -> list[str]:
    if not isinstance(value, list) or not value:
        raise WorkflowRequestError("roles")
    roles: list[str] = []
    for role in value:
        if not isinstance(role, str) or role.strip() not in WORKFLOW_STAGE_ROLES:
            raise WorkflowRequestError("roles")
        roles.append(role.strip())
    if mode not in WORKFLOW_MODES:
        raise WorkflowRequestError("mode")
    if mode == "adaptive" and "coder" not in roles:
        raise WorkflowRequestError("adaptive-roles")
    if roles.count("planner") > 1 or (
        "planner" in roles and "coder" in roles and roles.index("planner") > roles.index("coder")
    ):
        raise WorkflowRequestError("role-order")
    return roles


def _workflow_budget(value: object, *, default: int, ceiling: int, code: str) -> int:
    if value is None:
        return default
    if type(value) is not int:
        raise WorkflowRequestError(code)
    return min(max(value, 0), ceiling)


def _validate_workflow_run_id(value: object, *, allow_missing: bool = False) -> None:
    if value is None and allow_missing:
        return
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value) is None:
        raise WorkflowRequestError("run-id")


def _workflow_tasks(roles: list[str], task: object, per_role_task: object) -> None:
    if task is not None and (not isinstance(task, str) or not task.strip()):
        raise WorkflowRequestError("task")
    if not isinstance(per_role_task, Mapping):
        raise WorkflowRequestError("task")
    for role, value in per_role_task.items():
        if role not in WORKFLOW_STAGE_ROLES or (
            value is not None and (not isinstance(value, str) or not value.strip())
        ):
            raise WorkflowRequestError("task")
    if any(not (per_role_task.get(role) or task) for role in roles):
        raise WorkflowRequestError("task")
    # Q55 requires an evaluator even when omitted from the requested sequence.
    # Actual stage insertion stays at run_workflow's declared CT73 choke point.
    if "coder" in roles and not (per_role_task.get("eval") or task):
        raise WorkflowRequestError("task")


def _workflow_injections(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping):
        raise WorkflowRequestError("injection")
    for name, mode in value.items():
        if not isinstance(name, str) or not isinstance(mode, str):
            raise WorkflowRequestError("injection")
        if name not in INJECTION_SPECS or mode not in INJECTION_MODES:
            raise WorkflowRequestError("injection")


def _validate_workflow_request(
    *,
    roles: object,
    mode: object,
    max_repairs: object,
    max_replans: object,
    run_id: object,
    task: object,
    per_role_task: object,
    inject_overrides: object = None,
    allow_missing_run_id: bool = False,
    workspace: Path | None = None,
    run_context: RunContext | None = None,
) -> _WorkflowRequest:
    """Shared side-effect-free public boundary (CT74/95, admission spec §1).

    CLI permits an absent requested ID before generating one; direct API does
    not. Both validate the actual ID before deriving any artifact path. This
    function never resolves/provisions a workspace or loads feature/config files.
    """
    normalized_roles = _workflow_roles(roles, mode)
    repairs = _workflow_budget(
        max_repairs, default=DEFAULT_MAX_REPAIRS, ceiling=MAX_REPAIRS_CEILING, code="max-repairs"
    )
    replans = _workflow_budget(
        max_replans, default=DEFAULT_MAX_REPLANS, ceiling=MAX_REPLANS_CEILING, code="max-replans"
    )
    _validate_workflow_run_id(run_id, allow_missing=allow_missing_run_id)
    if run_context is not None and (
        getattr(run_context, "run_id", None) != run_id or getattr(run_context, "workspace_path", None) != workspace
    ):
        raise WorkflowRequestError("context-binding")
    _workflow_tasks(normalized_roles, task, per_role_task)
    _workflow_injections(inject_overrides)
    return _WorkflowRequest(tuple(normalized_roles), repairs, replans)


def _render_mode_label(mode: str, *, max_repairs: int, max_replans: int) -> str:
    if mode == "adaptive":
        return f"adaptive (max repairs {max_repairs}, max replans {max_replans})"
    return mode


def _canonical_loop_roles(roles: list[str], *, include_planner: bool) -> tuple[str, ...]:
    canonical = ["planner", "coder", "eval"] if include_planner else ["coder", "eval"]
    return tuple(role for role in canonical if role in roles)


def _ensure_eval_after_coder(roles: list[str]) -> list[str]:
    """Place one eval stage immediately after every coder stage. (Q55)

    A successful coder dispatch is always judged, even when the caller omits
    ``eval`` or lists it before ``coder``. Explicit eval entries are relocated
    rather than duplicated.
    """
    if "coder" not in roles:
        return list(roles)
    normalized: list[str] = []
    for role in roles:
        if role == "eval":
            continue
        normalized.append(role)
        if role == "coder":
            normalized.append("eval")
    return normalized


# ── Pipeline modes ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _StageLoopResult:
    """Outcome of running a sequence of workflow stages through the shared loop."""

    ctx: WorkflowContext
    exit_code: int
    n_stages: int
    last_role: str
    eval_report: EvalReport | None
    verification: PlanVerification | None


def _run_role_loop(
    ctx: WorkflowContext,
    roles: Sequence[str],
    run_stage_fn: Callable[..., int],
    *,
    progress: WorkflowProgress,
    n_stages: int = 0,
    eval_report: EvalReport | None = None,
    verification: PlanVerification | None = None,
    fresh_first: bool = True,
    reason_prefix: str | None = None,
) -> _StageLoopResult:
    """Run one stage sequence through the single shared acquisition/failure loop.

    All pipeline executions — linear pass, adaptive initial pass, and adaptive
    repair/replan rounds — funnel through this loop so acquisition admission
    binding, fail-fast state persistence, and coder→eval evidence handoff live
    in one place (Q57 / S5P1 §7.0).
    """
    last_role = roles[0] if roles else "workflow"
    total = len(roles)
    for index, role in enumerate(roles):
        n_stages += 1
        last_role = role
        if reason_prefix is None:
            print(f"\nfa workflow ─ stage {index + 1}/{total}: {role}", file=sys.stderr)
            transition_reason = f"dispatching stage {index + 1}/{total}"
        else:
            transition_reason = f"{reason_prefix}: canonical {role}"
        result = _run_stage(
            ctx,
            role,
            fresh=fresh_first and index == 0,
            progress=progress,
            transition_reason=transition_reason,
            run_stage_fn=run_stage_fn,
            prior_verification=verification,
        )
        if result.exit_code != 0:
            _write_stage_failure_state(ctx, role, result.exit_code, progress=progress)
            return _StageLoopResult(ctx, result.exit_code, n_stages, last_role, eval_report, verification)
        if result.authored_project:
            ctx, blocked = _bind_authored_project(ctx, progress=progress, run_stage_fn=run_stage_fn)
            if blocked is not None:
                return _StageLoopResult(ctx, blocked, n_stages, last_role, eval_report, verification)
        if result.acquisition is not None:
            ctx, blocked = _bind_acquisition_admission(ctx, result.acquisition)
            if blocked is not None:
                return _StageLoopResult(ctx, blocked, n_stages, last_role, eval_report, verification)
        if role == "coder":
            verification = result.verification
        if result.eval_report is not None:
            eval_report = result.eval_report
    return _StageLoopResult(ctx, 0, n_stages, last_role, eval_report, verification)


def _run_initial_roles(
    ctx: WorkflowContext,
    roles: list[str],
    run_stage_fn: Callable[..., int],
) -> tuple[int, int, EvalReport | None, PlanVerification | None]:
    """Run the configured initial role sequence, carrying facts from coder to eval."""
    loop = _run_role_loop(ctx, roles, run_stage_fn, progress=WorkflowProgress())
    return loop.exit_code, loop.n_stages, loop.eval_report, loop.verification


def _finish_adaptive(
    ctx: WorkflowContext,
    *,
    n_stages: int,
    eval_report: EvalReport | None,
    progress: WorkflowProgress,
    route: RouteDecision | None,
    reason: str,
    eval_requested: bool = True,
    last_role: str = "eval",
) -> int:
    """Persist and summarize one terminal adaptive route."""
    _write_terminal_state(
        ctx,
        last_role=last_role,
        eval_report=eval_report,
        progress=progress,
        reason=reason,
        eval_requested=eval_requested,
        route_override=route,
    )
    _print_terminal_summary(
        ctx,
        n_stages=n_stages,
        eval_report=eval_report,
        repair_rounds_used=progress.repair_round,
        effective_route=route,
    )
    return 0


def _dispatch_adaptive_round(
    ctx: WorkflowContext,
    stage_roles: tuple[str, ...],
    run_stage_fn: Callable[..., int],
    *,
    progress: WorkflowProgress,
    n_stages: int,
    eval_report: EvalReport,
    verification: PlanVerification | None,
    reason_prefix: str,
) -> tuple[WorkflowContext, int, int, EvalReport, PlanVerification | None]:
    """Run one canonical coder/eval or planner/coder/eval adaptive round."""
    loop = _run_role_loop(
        ctx,
        stage_roles,
        run_stage_fn,
        progress=progress,
        n_stages=n_stages,
        eval_report=eval_report,
        verification=verification,
        fresh_first=False,
        reason_prefix=reason_prefix,
    )
    return loop.ctx, loop.exit_code, loop.n_stages, loop.eval_report or eval_report, loop.verification


def _run_adaptive_repair(
    ctx: WorkflowContext,
    roles: list[str],
    max_repairs: int,
    run_stage_fn: Callable[..., int],
    *,
    progress: WorkflowProgress,
    n_stages: int,
    eval_report: EvalReport,
    verification: PlanVerification | None,
    route: RouteDecision,
) -> tuple[bool, int, WorkflowContext, int, WorkflowProgress, EvalReport, PlanVerification | None]:
    """Use one bounded repair round, or terminate when the existing cap is spent."""
    if progress.repair_round >= max_repairs:
        if verification is not None and verification.blocking and eval_report.route_decision == "complete":
            reason = (
                f"enforce verification gate remains blocking after repair budget "
                f"({progress.repair_round}/{max_repairs}): {_verification_block_detail(verification)}"
            )
        else:
            reason = f"repair budget exhausted ({progress.repair_round}/{max_repairs}); last route return_to_coder"
        _finish_adaptive(
            ctx,
            n_stages=n_stages,
            eval_report=eval_report,
            progress=progress,
            route=route,
            reason=reason,
        )
        return False, 0, ctx, n_stages, progress, eval_report, verification

    progress = WorkflowProgress(
        plan_version=progress.plan_version,
        repair_round=progress.repair_round + 1,
        replan_round=progress.replan_round,
    )
    print(
        f"\nfa workflow ─ repair round {progress.repair_round}/{max_repairs} (adaptive route return_to_coder)",
        file=sys.stderr,
    )
    ctx, code, n_stages, eval_report, verification = _dispatch_adaptive_round(
        ctx,
        _canonical_loop_roles(roles, include_planner=False),
        run_stage_fn,
        progress=progress,
        n_stages=n_stages,
        eval_report=eval_report,
        verification=verification,
        reason_prefix=f"repair round {progress.repair_round}: after return_to_coder",
    )
    return code == 0, code, ctx, n_stages, progress, eval_report, verification


def _run_adaptive_replan(
    ctx: WorkflowContext,
    roles: list[str],
    max_replans: int,
    run_stage_fn: Callable[..., int],
    *,
    progress: WorkflowProgress,
    n_stages: int,
    eval_report: EvalReport,
    verification: PlanVerification | None,
    route: RouteDecision,
) -> tuple[bool, int, WorkflowContext, int, WorkflowProgress, EvalReport, PlanVerification | None]:
    """Use one bounded planner round, or terminate if it cannot be honored."""
    if ctx.admission is not None:
        if not _admit_plan(
            ctx,
            progress,
            run_stage_fn,
            replan=True,
            reason=f"Eval requested {eval_report.route_decision}: {eval_report.summary}",
        ):
            return False, _admission_exit_code(ctx), ctx, n_stages, progress, eval_report, verification
        progress = replace(progress, plan_version=progress.plan_version + 1, replan_round=ctx.admission.planner_calls)
        ctx, code, n_stages, eval_report, verification = _dispatch_adaptive_round(
            ctx,
            _canonical_loop_roles(roles, include_planner=False),
            run_stage_fn,
            progress=progress,
            n_stages=n_stages,
            eval_report=eval_report,
            verification=verification,
            reason_prefix="admitted eval replan",
        )
        return code == 0, code, ctx, n_stages, progress, eval_report, verification
    if "planner" not in roles:
        reason = (
            f"eval routed return_to_planner but no planner role is configured (roles={','.join(roles)}); cannot replan"
        )
        _finish_adaptive(
            ctx,
            n_stages=n_stages,
            eval_report=eval_report,
            progress=progress,
            route=route,
            reason=reason,
        )
        return False, 0, ctx, n_stages, progress, eval_report, verification
    if progress.replan_round >= max_replans:
        reason = f"replan budget exhausted ({progress.replan_round}/{max_replans}); last route return_to_planner"
        _finish_adaptive(
            ctx,
            n_stages=n_stages,
            eval_report=eval_report,
            progress=progress,
            route=route,
            reason=reason,
        )
        return False, 0, ctx, n_stages, progress, eval_report, verification

    progress = WorkflowProgress(
        plan_version=progress.plan_version + 1,
        repair_round=progress.repair_round,
        replan_round=progress.replan_round + 1,
    )
    print(
        f"\nfa workflow ─ replan round {progress.replan_round}/{max_replans} (plan version {progress.plan_version})",
        file=sys.stderr,
    )
    ctx, code, n_stages, eval_report, verification = _dispatch_adaptive_round(
        ctx,
        _canonical_loop_roles(roles, include_planner=True),
        run_stage_fn,
        progress=progress,
        n_stages=n_stages,
        eval_report=eval_report,
        verification=verification,
        reason_prefix=f"replan round {progress.replan_round}: after return_to_planner",
    )
    return code == 0, code, ctx, n_stages, progress, eval_report, verification


def _run_adaptive(
    ctx: WorkflowContext,
    roles: list[str],
    max_repairs: int,
    max_replans: int,
    run_stage_fn: Callable[..., int],
) -> int:
    """Run normalized roles, evaluate every coder attempt, then route on eval plus gate facts."""
    loop = _run_role_loop(ctx, roles, run_stage_fn, progress=WorkflowProgress())
    if loop.exit_code != 0:
        return loop.exit_code
    ctx = loop.ctx
    n_stages = loop.n_stages
    eval_report = loop.eval_report
    verification = loop.verification

    progress = WorkflowProgress()
    eval_requested = "eval" in roles
    verification_required = "coder" in roles
    route = _effective_controller_route(
        eval_report,
        verification,
        gate_mode=ctx.verify_gate_mode,
        eval_requested=eval_requested,
        verification_required=verification_required,
        integrity_failed=_integrity_failed(ctx),
    )
    if eval_report is None:
        if ctx.verify_gate_mode == "enforce" and verification is not None and verification.blocking:
            reason = f"enforce verification gate: {_verification_block_detail(verification)}"
        elif eval_requested:
            reason = "eval stage produced no verdict"
        elif verification_required:
            reason = "coder stage completed without an eval verdict"
        else:
            reason = "adaptive workflow completed without eval stage"
        return _finish_adaptive(
            ctx,
            n_stages=n_stages,
            eval_report=None,
            progress=progress,
            route=route,
            reason=reason,
            eval_requested=eval_requested,
            last_role=roles[-1] if roles else "workflow",
        )

    while True:
        route = _effective_controller_route(
            eval_report,
            verification,
            gate_mode=ctx.verify_gate_mode,
            eval_requested=eval_requested,
            verification_required=verification_required,
            integrity_failed=_integrity_failed(ctx),
        )
        if route == "blocked":
            detail = (
                _verification_block_detail(verification)
                if verification is not None and verification.blocking
                else eval_report.summary
            )
            return _finish_adaptive(
                ctx,
                n_stages=n_stages,
                eval_report=eval_report,
                progress=progress,
                route=route,
                reason=f"workflow blocked after eval: {detail}",
            )
        if route == "return_to_coder":
            keep_going, code, ctx, n_stages, progress, eval_report, verification = _run_adaptive_repair(
                ctx,
                roles,
                max_repairs,
                run_stage_fn,
                progress=progress,
                n_stages=n_stages,
                eval_report=eval_report,
                verification=verification,
                route=route,
            )
            if not keep_going:
                return code
            continue
        if route == "return_to_planner":
            keep_going, code, ctx, n_stages, progress, eval_report, verification = _run_adaptive_replan(
                ctx,
                roles,
                max_replans,
                run_stage_fn,
                progress=progress,
                n_stages=n_stages,
                eval_report=eval_report,
                verification=verification,
                route=route,
            )
            if not keep_going:
                return code
            continue

        if (
            ctx.verify_gate_mode == "enforce"
            and verification is not None
            and verification.blocking
            and eval_report.route_decision == "complete"
        ):
            reason = f"enforce verification gate remains blocking: {_verification_block_detail(verification)}"
        else:
            reason = (
                f"eval verdict {eval_report.verdict} after {progress.repair_round} repair round(s) "
                f"and {progress.replan_round} replan round(s)"
            )
        return _finish_adaptive(
            ctx,
            n_stages=n_stages,
            eval_report=eval_report,
            progress=progress,
            route=route,
            reason=reason,
        )


@dataclass(frozen=True)
class AcquisitionSubstrate:
    """What one acquisition planner may read, and the names it may choose from.

    Both halves come from the *same* pinned READ view: the port answers the reads the
    planner performs with its own tools, and ``project_names`` / ``incomplete_names``
    are the Q146 lists taken from that view. Handing the planner a port it can read
    through but a name list from somewhere else would let it select a project the
    view cannot resolve.
    """

    # The protocol, not `ClientWorkspacePort`: the resolver and the planner's tools
    # need only these five operations, and a narrower type would force every test
    # double to impersonate a client it never uses.
    port: WorkspacePort
    project_names: tuple[str, ...]
    incomplete_names: tuple[str, ...] = ()
    # The caller's create authorization (CT-2.1), carried with the pinned view
    # because it belongs to this run's acquisition contract: ``None`` means the
    # route may only select, so a bootstrap reply is refused rather than installed.
    # It is not read here -- the prelude never names a project -- it is the one
    # caller-owned fact the binding step needs after the planner has spoken.
    project_slug: str | None = None
    #: R1 (E577): the caller's disposition grants, carried to the same binding step
    #: for the same reason -- the plan only *requests* them, and only this run can
    #: authorise the request it is about to install.
    dispositions: tuple[DispositionDeclaration, ...] = ()


@dataclass(frozen=True)
class AcquisitionSubstrateRequest:
    """Ask `run_workflow` to pin its own acquisition view for this run.

    A marker rather than a port: the caller cannot supply one, because a substrate
    built before the child's HANDOFF would carry the parent's binding. The view must
    be pinned inside the run, after that run's own binding exists.

    ``project_slug`` is the one thing the caller *may* decide (CT-2.1): a chat
    session knows the project name before the planner runs, and letting the model
    restate it would make the slug a model claim rather than an operator input.
    The run refuses a choice that is not a new-project bootstrap when this is set,
    because "create this exact project" cannot be satisfied by selecting another.
    """

    project_slug: str | None = None
    dispositions: tuple[DispositionDeclaration, ...] = ()


@contextmanager
def _pinned_acquisition_substrate(ctx: WorkflowContext) -> Iterator[AcquisitionSubstrate | None]:
    """Pin one READ view of the current revision for the acquisition planner.

    ``plan_ref`` is deliberately ``None``: acquisition runs *before* any plan is
    admitted, and ``ProtectedPlanContext.recheck`` treats a null ref as the ordinary
    no-active-plan context rather than formal evidence. Passing a plan here would be
    a claim about a target nobody has selected yet -- the same reasoning that makes
    ``PlannerDispatchKind.ACQUISITION`` refuse an ``active_plan``.

    ``None`` means "no substrate available" and the caller refuses the run with a
    rule, never a host fallback: the host tree is not the revision the authority
    will later admit a plan from, so choosing against it would admit a coder to a
    plan the pinned view cannot resolve.
    """
    managed = ctx.managed_execution
    if managed is None:
        yield None
        return
    deadline = ctx.deadline_mono if ctx.deadline_mono is not None else time.monotonic() + 30.0
    try:
        grant = managed.client.pin_reader(
            managed.binding,
            revision_id=managed.current_revision_id,
            plan_ref=None,
            deadline=deadline,
        )
    except (ExecutionRejectedError, ExecutionUnavailableError, ExecutionUncertainError) as error:
        logger.warning(
            "managed acquisition unavailable: the authority refused the read pin [%s] (run=%s)",
            getattr(error, "code", type(error).__name__),
            ctx.run_id,
        )
        yield None
        return
    view = grant.view_ref
    if (
        grant.operation is not Operation.PIN_READER
        or view is None
        or view.access is not Access.READ
        or view.purpose is not ViewPurpose.PROJECT
        or view.owner_run_id != managed.binding.namespace.run_id
    ):
        # A grant that is not the one asked for is a contract violation, not a
        # degraded case: continuing would read a view this run does not own.
        raise ExecutionContractError
    port = ClientWorkspacePort(
        managed.client,
        namespace=managed.binding.namespace,
        view=view,
        grant=grant,
        cache_dir=ctx.workspace / ".fa" / "acquisition-read-cache",
    )
    try:
        try:
            listed = port.list_project_names()
        except WorkspacePortError as error:
            # A failed listing is not evidence that the pinned workspace is empty.
            # Refuse acquisition before the planner can select/bootstrap from a
            # fabricated empty inventory; the pinned view is still stopped below.
            logger.warning("managed acquisition: project list refused [%s] (run=%s)", error.code, ctx.run_id)
            yield None
            return
        yield AcquisitionSubstrate(
            port=port,
            project_names=listed.projects,
            incomplete_names=listed.incomplete,
        )
    finally:
        if not managed.client.stop_view(managed.binding.namespace, view=view, grant=grant, deadline=deadline):
            logger.error(
                "acquisition read-only view did not become terminal (run=%s view=%s)", ctx.run_id, view.view_id
            )


def _stage_acquisition_choice(
    ctx: WorkflowContext,
    role: str,
    code: int,
    sink: list[SessionOutcome],
    *,
    dispatch: PlannerDispatch | None = None,
) -> tuple[AcquisitionOutcome | None, bool]:
    """Read the acquisition choice on the one stage entitled to make it.

    Extracted from ``_run_stage``: that function is at its complexity ceiling, and
    this is a self-contained decision with its own failure contract. A malformed or
    absent choice is a closed refusal reported on stderr, never an exception
    escaping a stage dispatcher.
    """
    if (
        role != "planner"
        or code != 0
        or ctx.acquisition is None
        or ctx.admission is not None
        or (dispatch is not None and dispatch.owns_candidate)
    ):
        return None, False
    try:
        return _read_acquisition_choice(sink, ctx.acquisition), False
    except AcquisitionChoiceError as error:
        print(f"fa workflow: acquisition choice refused: {error.rule}", file=sys.stderr)
        severity = "FAIL" if error.validator == "bootstrap" else "ERROR"
        outcome = "DIAGNOSTICS" if error.validator == "bootstrap" else "INDETERMINATE"
        _blocked_plan_request(
            run_id=ctx.run_id,
            task=ctx.base_task,
            rule=error.rule,
            base_dir=ctx.artifact_paths.base_dir,
            deadline=ctx.deadline_mono,
            managed_binding=ctx.admission_binding,
            attempt_kind="ACQUISITION" if ctx.admission_binding is not None else "EXPLICIT_INPUT",
            v2_diagnostic=(error.validator, error.rule, severity, outcome, None),
        )
        return None, True


def _read_acquisition_choice(sink: list[SessionOutcome], substrate: AcquisitionSubstrate) -> AcquisitionOutcome:
    """Turn the acquisition planner's final message into the prelude's outcome.

    The channel is the one eval already uses (``_run_stage`` passes ``outcome_sink``
    for every role and ``_cmd_run`` appends the terminal outcome), so the choice
    arrives on a production path rather than a test-only hook.

    Absence is an error, not an empty choice: a planner that stopped without one
    settled message has not selected anything, and defaulting here would submit a
    plan nobody chose.
    """
    if not sink:
        raise AcquisitionChoiceError("selection", "choice-missing")
    choice = parse_acquisition_choice(sink[-1].final_text or "")
    return resolve_acquisition_choice(
        choice,
        inventory_view=substrate.port,
        inventory_slugs=substrate.project_names,
    )


def _refusal_exit_code(
    ctx: WorkflowContext,
    refusal: PlanRefError,
    *,
    failure_detail: _BootstrapFailure | None = None,
) -> int:
    """Record a bootstrap refusal the same way every other closed refusal is."""
    v2_diag = (
        (
            failure_detail.validator,
            failure_detail.rule,
            failure_detail.severity,
            failure_detail.validation,
            failure_detail.operation_id,
        )
        if failure_detail is not None
        else None
    )
    return _blocked_plan_request(
        run_id=ctx.run_id,
        task=ctx.base_task,
        rule=refusal.rule,
        base_dir=ctx.artifact_paths.base_dir,
        deadline=ctx.deadline_mono,
        managed_binding=ctx.admission_binding,
        attempt_kind="ACQUISITION" if ctx.admission_binding is not None else "EXPLICIT_INPUT",
        v2_diagnostic=v2_diag,
        candidate_sha256=None if failure_detail is None else failure_detail.candidate_sha256,
        bundle_sha256=None if failure_detail is None else failure_detail.bundle_sha256,
    )[0]


def _valid_v2_operation_id(raw: object) -> str | None:
    """A well-formed v2 operation id, or ``None``.

    Shared by the promotion receipt path and the refusal classifiers: an id the
    authority reports must be syntactically v2 before it is recorded, because a
    malformed one in a durable record is a lie about what can be recovered.
    """
    if isinstance(raw, str) and _V2_OP_ID_RE.fullmatch(raw) is not None:
        return raw
    return None


def _post_stage_binding(
    ctx: WorkflowContext,
    role: str,
    code: int,
    sink: list[SessionOutcome],
    report: EvalReport | None,
    verification: PlanVerification | None,
    *,
    dispatch: PlannerDispatch | None,
) -> tuple[StageResult | None, AcquisitionOutcome | None, bool]:
    """What the stage produced, in one place: an authored project, a choice, or a refusal.

    Two routes answer differently and must not both run. An authoring stage
    (D-V2-9) emits no JSON -- the revision it published is the answer -- so it
    returns its own ``StageResult`` and the choice reader is never consulted.
    Every other acquisition stage keeps the S5P1 wire.
    """
    authored = _authored_stage_result(role, code, report, verification, dispatch=dispatch)
    if authored is not None:
        return authored, None, False
    outcome, refused = _stage_acquisition_choice(ctx, role, code, sink, dispatch=dispatch)
    if refused:
        return StageResult(role=role, exit_code=2), None, True
    return None, outcome, False


def _authored_stage_result(
    role: str,
    code: int,
    report: EvalReport | None,
    verification: PlanVerification | None,
    *,
    dispatch: PlannerDispatch | None,
) -> StageResult | None:
    """The stage result for an authoring stage, or ``None`` for every other stage.

    D-V2-9: the authoring stage emits no choice -- the view it published *is* the
    answer, so there is nothing to parse and nothing that can be malformed. The
    binding step admits the revision and reports a closed rule if it refuses.
    """
    if dispatch is None or dispatch.kind is not PlannerDispatchKind.CREATE_NEW_PROJECT:
        return None
    return StageResult(
        role=role,
        exit_code=code,
        eval_report=report,
        verification=verification,
        authored_project=code == 0,
    )


def _authored_refusal_detail(rule: str) -> _BootstrapFailure:
    """The structured diagnostic for an authoring refusal, in the closed vocabulary.

    ``invalid-metadata`` is reported as ``bootstrap/invalid-body``: admission's rule set
    is closed and already has no separate slot for front-matter -- the repair round
    reads ``invalid-body`` -- while the *specific* metadata rule is logged, so nothing
    an operator needs is lost by the mapping.
    """
    if rule == "bootstrap-invalid-metadata":
        return _BootstrapFailure("bootstrap", "invalid-body", "FAIL", "DIAGNOSTICS", None)
    if rule == "bootstrap-unavailable":
        return _BootstrapFailure("workspace", "backend-unavailable", "ERROR", "INDETERMINATE", None)
    if rule.startswith("bootstrap-"):
        return _BootstrapFailure("bootstrap", "invalid-body", "ERROR", "INDETERMINATE", None)
    if rule == "project-route-mismatch":
        return _BootstrapFailure("selection", "project-route-mismatch", "ERROR", "INDETERMINATE", None)
    if rule == "disposition-undeclared":
        # The persisted record has no `disposition-*` slot: `ADMISSION_RULES_V2` extends the
        # v1 vocabularies by name, and none of them names a grant. `needs-clarification` is
        # the closest true statement -- the caller must decide something -- while the exact
        # rule survives in `blocked_reason` (which is what the caller's failure code keys
        # on). Q-V2-RULES-1 carries the choice that would let the record keep the rule.
        return _BootstrapFailure("selection", "needs-clarification", "ERROR", "INDETERMINATE", None)
    return _BootstrapFailure("selection", "needs-clarification", "ERROR", "INDETERMINATE", None)


def _may_repair_authored_project(ctx: WorkflowContext, refusal: PlanRefError) -> bool:
    """Whether this refusal is repairable, and whether the run has budget for it (D-V2-9.8).

    Three of the four refusal families are worth a second authoring stage, and one is
    emphatically not. A collision is a fact about the workspace, not about the bytes:
    asking the planner to author a project into a directory it does not own is how a
    repair turns into an overwrite. Unavailability means the authority, not the plan,
    is the problem, and re-running the stage would fail the same way. Only a refusal
    about the *content* of the pair admission read is repairable, and only while the
    run still has attempts.

    The budget is one integer on the context rather than the shared planner counter
    because on this route admission authority is created by the very refusal being
    repaired: at the first repair there is no ``_WorkflowAdmission`` to count on.
    """
    if refusal.rule in {"bootstrap-collision", "bootstrap-unavailable", "project-route-mismatch"}:
        return False
    # A grant is the caller's to give (R1). A repair rewrites the plan, so its cheapest
    # way to satisfy this refusal is to delete the request -- silently dropping a claim
    # the planner said it could not test. The run stops and the caller either supplies the
    # declaration (retryable) or the claim changes on a new plan revision.
    if refusal.rule == "disposition-undeclared":
        return False
    # "bootstrap-refused" is the repair stage's own failure; repairing a failed repair
    # with another repair is a loop, and the operator needs the failure instead.
    if refusal.rule == "bootstrap-refused":
        return False
    # N1: an unsealed project is usually a content problem -- an acceptance tree that does not
    # collect, a selector outside its own closure -- and ``acceptance/`` is inside the repair
    # scope (S1 item 4) precisely so the planner can fix it. The consistency half is not:
    # there, admission accepted what the seal refused, and the planner has nothing to repair.
    if refusal.rule == "bootstrap-acceptance-unsealed" and refusal.detail in _UNREPAIRABLE_SEAL_RULES:
        return False
    return ctx.authored_repairs < ctx.replans_allowed


def _authored_diagnostics(refusal: PlanRefError) -> tuple[_AdmissionDiagnostic, ...]:
    """The refusal as the repair stage is told it: one closed rule, nothing free-form.

    Sanitized on purpose -- the stage gets a rule name and the files it may write, not
    a rendered traceback. The repair stage's job is to fix content; anything else it is
    told is either redundant (it can read the files) or a leak into the prompt.
    """
    return (_AdmissionDiagnostic("bootstrap", refusal.rule, "FAIL"),)


def _bind_authored_project(
    ctx: WorkflowContext,
    *,
    progress: WorkflowProgress | None = None,
    run_stage_fn: Callable[..., int] | None = None,
) -> tuple[WorkflowContext, int | None]:
    """Admit the revision an authoring stage published, or stop the run (D-V2-9).

    The shape mirrors ``_bind_acquisition_admission`` -- return a new context on
    success, an exit code on refusal -- so the loop has one way to spell "this
    stage produced the plan". What differs is the source: there is no choice to
    interpret, because the planner wrote the documents instead of describing them.

    A refusal is not the end of the run while the planner still has an attempt left
    (D-V2-9.8): the repair is a *second authoring stage*, not the candidate buffer,
    because a project is a tree and the candidate path publishes one file. When no
    stage driver is available -- tests that assert the refusal itself -- the refusal
    is reported directly rather than silently repaired by nothing.
    """
    bound, refusal = _admit_published_project(ctx)
    if refusal is None:
        return bound, None
    if run_stage_fn is not None and progress is not None and _may_repair_authored_project(ctx, refusal):
        repairing = replace(ctx, authored_repairs=ctx.authored_repairs + 1)
        repaired, repair_refusal = _run_create_new_repair(
            repairing,
            progress,
            run_stage_fn,
            diagnostics=_authored_diagnostics(refusal),
            reason=refusal.rule,
            rule=refusal.detail,
        )
        if repair_refusal is None:
            return repaired, None
        bound, refusal = repaired, repair_refusal
    # The rule must reach the durable record, not just stderr: an operator reading a
    # blocked run has no stage output to fall back on, and a BLOCKED attempt with an
    # empty ``diagnostics`` is indistinguishable from one that failed to normalise.
    # ``bootstrap-*`` rules are the bootstrap validator's own vocabulary, so they map
    # to their own validator name; everything else is an admission-level refusal.
    detail = _authored_refusal_detail(refusal.rule)
    return bound, _refusal_exit_code(bound, refusal, failure_detail=detail)


def _granted_dispositions(
    port: WorkspacePort, declarations: tuple[DispositionDeclaration, ...]
) -> tuple[DispositionDeclaration, ...]:
    """Verify every ``doc:`` grant against the pinned view's bytes (R6).

    The digest is what pins the claim, so it is checked before the grant can
    authorise anything: a missing file, a file too large for one bounded read, or
    bytes that differ from the declared digest all refuse. ``issue:``/``review:``
    are typed references this system cannot resolve, so they pass through as
    well-formed and are *reported* as attested, never as verified.

    This lived inside the bootstrap installer until D-V2-9 deleted that path. It is
    not an install-time courtesy: it is the only thing that makes a ``doc:`` grant a
    claim about real bytes, so the authoring route verifies it just the same.
    """
    if not any(declaration.evidence.kind == "doc" for declaration in declarations):
        return declarations
    for declaration in declarations:
        evidence = declaration.evidence
        if evidence.kind != "doc":
            continue
        try:
            read = port.read_file(port_relative(evidence.target))
        except WorkspacePortError as error:
            rule = "disposition-evidence-invalid" if error.code == "invalid_request" else "disposition-evidence-missing"
            raise PlanRefError(rule) from None
        if not read.eof:
            raise PlanRefError("disposition-evidence-invalid")
        if read.sha256 != evidence.digest:
            raise PlanRefError("disposition-evidence-mismatch")
    return declarations


#: The allowlist a create-new *repair* stage writes through (D-V2-9.8).
#:
#: Wider than the two documents a metadata refusal needs, and narrower than the
#: authoring root, because a repair must be able to fix every refusal that *is*
#: repairable without being able to publish a project nobody re-read. The accepted
#: families are: the pair admission parses, the question record, and the acceptance
#: tree. The acceptance tree is here because D-V2-10 makes evidence the common
#: refusal and the fix for it is a test -- admitting only the plan would tell the
#: model to discharge a contract in a file it may not write. The roadmap is here
#: because ``plan-format-marker-roadmap`` is repairable and its only fix lives there;
#: leaving it out made that repair a guaranteed failure that cost a planner call and
#: ended in the worse code ``bootstrap-refused``. The ledger is not here: nothing
#: admission refuses can be fixed by editing it.
#:
#: Widening this cannot weaken the gate -- the second revision is re-admitted whole,
#: including the metadata cross-check -- it only stops a dead-end repair.
_REPAIR_WRITABLE_SUFFIXES = (
    "roadmap.md",
    "increments/increment-01-initial-plan.md",
    "open-questions.md",
    # A subtree, spelled without a trailing slash: the dispatch validates its entries as
    # path components, and the writer's matcher is component-wise, so a bare parent admits
    # the whole tree without admitting a sibling whose name merely starts with "acceptance".
    "acceptance",
)


#: A parser rule as it may appear in a prompt: lowercase kebab, bounded. The rules embed
#: document identifiers (``invariant-1-text``), so the value is model-influenced; the
#: prompt is the last place it can do harm.
_REPAIR_RULE_RE = re.compile(r"[a-z][a-z0-9-]{0,63}")


def _bounded_rule(rule: str | None) -> str | None:
    """The rule if it is shaped like one of ours, else ``None``. Never raises."""
    if rule is None or _REPAIR_RULE_RE.fullmatch(rule) is None:
        return None
    return rule


def _repair_allowlist(root: str) -> tuple[str, ...]:
    """The exact paths a create-new repair may write, spelled as prefixes.

    Prefixes rather than paths because that is the shape the limited writer consumes
    (``is_path_in_write_scope``: an exact entry, or a subtree). Three entries are full file
    names, so each admits exactly one file and no sibling; ``acceptance`` is a subtree,
    which is the only shape that can admit a test the planner has not written yet.
    """
    return tuple(f"{root}/{suffix}" for suffix in _REPAIR_WRITABLE_SUFFIXES)


def _repair_stage_task(
    base_task: str | None,
    *,
    slug: str,
    diagnostics: tuple[_AdmissionDiagnostic, ...],
    rule: str | None = None,
) -> str:
    """The task for a create-new repair: fix the refused documents, change nothing else.

    A repair is not a re-authoring. The project already published one revision with
    a scaffold and the planner's documents; the refusal was about the *content of the
    pair admission reads*. Telling the model that plainly is what keeps a repair from
    wandering -- and the allowlist enforces it anyway, which is why the task can be
    generous in prose (D-V2-9.8: the allowlist, not the prompt, is the protection).
    """
    root = f"worklogs/{slug}"
    payload = json.dumps([asdict(item) for item in diagnostics], sort_keys=True)
    # Built from the allowlist rather than spelled out: the previous text promised "exactly
    # two files" in prose, which is how a prompt and a writer drift apart when the allowlist
    # moves. The rule is bounded HERE, at the boundary where a code becomes prose: it is the
    # only place that turns it into text, so there is one guard rather than a contract each
    # caller has to remember.
    writable = "\n".join(f"- `{root}/{suffix}`" for suffix in _REPAIR_WRITABLE_SUFFIXES)
    rule = _bounded_rule(rule)
    rule_line = f"Admission's rule: `{rule}`." if rule else "Admission gave no rule name."
    return (
        f"{base_task or ''}\n"
        f"This project's documents were refused by admission. The revision is already "
        f"published; fix it in place -- do not start over and do not re-plan.\n\n"
        f"{rule_line}\n\n"
        f"You may write exactly these paths:\n{writable}\n\n"
        f"Anything else -- the ledger, `.fa/`, any path outside `{root}/` -- is fixed "
        f"and a write to it is refused. The identity fields in the front matter are checked "
        f"again on the next admission, so changing them refuses the repair.\n\n"
        f"There are two legal ways out of an evidence refusal: give the contract a test in "
        f"`{root}/acceptance/tests/` and name it in `ACCEPTANCE`, or declare why the claim "
        f"cannot be tested (`DISPOSITION-REASON`) and leave the grant to the caller. "
        f"Deleting the contract or the invariant to satisfy admission is not a repair.\n\n"
        f"The refusal, sanitized: {payload}"
    )


def _run_create_new_repair(
    ctx: WorkflowContext,
    progress: WorkflowProgress,
    run_stage_fn: Callable[..., int],
    *,
    diagnostics: tuple[_AdmissionDiagnostic, ...] = (),
    reason: str = "",
    rule: str | None = None,
) -> tuple[WorkflowContext, PlanRefError | None]:
    """Repair a refused create-new project with a second authoring stage (D-V2-9.8).

    The candidate buffer is the wrong tool here and the source says so: `seed_plan_candidate`
    refuses anything but `ADMISSION_REPAIR`/`EVAL_REPLAN`, writes one draft under
    `.fa/admission/<run>/`, and `publish_candidate_plan` commits **one** file at a pinned
    ref. A create-new project is a tree, not one file: repairing only the increment would
    publish a revision whose roadmap still holds whatever admission refused, and the
    other documents would be unrestorable because they never had a draft.

    So the repair is a second stage of the *same* kind over the published revision, with
    the allowlist narrowed to the documents a repairable refusal can be fixed in -- the
    pair admission parses, the roadmap, the question record and the acceptance tree
    (``_REPAIR_WRITABLE_SUFFIXES``), which is narrower than the authoring root and still
    admits every legal fix. ``plan_ref`` stays ``None``: the
    stage's business is to change the very bytes a plan-ref would freeze (D-V2-9.5), and
    the allowlist -- not `_validate_plan_boundary`, which protects coders and verifiers --
    is what bounds it.

    Returns the bound context on success; on refusal, the context unchanged and the rule,
    so the caller reports exactly one refusal per attempt.
    """
    managed = ctx.managed_execution
    if managed is None:  # pragma: no cover - the route proved this before the stage
        return ctx, PlanRefError("bootstrap-unavailable")
    slug = ctx.project_hint
    if slug is None:  # pragma: no cover - the authoring kind cannot exist without one
        return ctx, PlanRefError("project-route-mismatch")
    root = f"worklogs/{slug}"
    role_tasks = dict(ctx.per_role_task)
    role_tasks["planner"] = _repair_stage_task(ctx.base_task, slug=slug, diagnostics=diagnostics, rule=rule)
    repair_ctx = replace(ctx, per_role_task=role_tasks)
    dispatch = PlannerDispatch(
        PlannerDispatchKind.CREATE_NEW_PROJECT,
        ctx.run_id,
        authoring_root=root,
        repair_allowlist=_repair_allowlist(root),
    )
    result = _run_stage(
        repair_ctx,
        "planner",
        fresh=False,
        progress=progress,
        transition_reason=f"create-new repair revision ({reason or 'admission'})",
        run_stage_fn=run_stage_fn,
        planner_dispatch=dispatch,
    )
    if result.exit_code != 0:
        # The repair stage itself failed. Not a content refusal, so it does not get a
        # content rule: the run stops with the code the stage chose.
        return ctx, PlanRefError("bootstrap-refused")
    # The stage published a second revision; admission reads it exactly as it read the
    # first, which is what makes "the repair is re-validated" a fact rather than a plan.
    return _admit_published_project(repair_ctx)


def _admit_published_project(ctx: WorkflowContext) -> tuple[WorkflowContext, PlanRefError | None]:
    """Admit the project the authoring stage just published (D-V2-9, CT-2.4).

    The stage already committed one revision containing the scaffold plus the
    planner's documents (``STOP_VIEW → SEAL → PUBLISH``), so there is nothing to
    install and no bundle to render. Admission reads that revision through a fresh
    pin -- the same mechanism the install path used -- and binds the plan, which is
    what makes the coder dispatchable and what D-V2-8 keeps honest: the revision
    exists in history whether or not it admitted.

    ``plan_ref`` is ``None`` on the pin for the same reason it is ``None`` on the
    stage (D-V2-9.5): the plan being admitted is the one inside the revision, and a
    ref to it would be a claim made before reading it.

    Every refusal is closed and pre-coder, so a rejected authoring stage leaves a
    published revision with no consumer rather than a coder bound to bad bytes.
    """
    managed = ctx.managed_execution
    slug = ctx.project_hint
    if managed is None:  # pragma: no cover - the route proved this before the stage
        return ctx, PlanRefError("bootstrap-unavailable")
    if slug is None:  # pragma: no cover - the authoring kind cannot exist without one
        return ctx, PlanRefError("project-route-mismatch")
    with _pinned_acquisition_substrate(ctx) as substrate:
        if substrate is None:
            return ctx, PlanRefError("bootstrap-unreadable")
        try:
            granted = _granted_dispositions(substrate.port, ctx.dispositions)
        except PlanRefError as error:
            logger.warning("disposition grant refused [%s] (run=%s)", error.rule, ctx.run_id)
            return ctx, error
        roadmap_path = f"worklogs/{slug}/roadmap.md"
        increment_path = f"worklogs/{slug}/increments/increment-01-{INITIAL_INCREMENT_SLUG}.md"
        try:
            roadmap = substrate.port.read_file(roadmap_path)
            increment = substrate.port.read_file(increment_path)
        except WorkspacePortError:
            # The published revision does not hold the pair the stage was told to
            # author. That is the planner's failure to produce documents, not an
            # unreadable tree: the stage published, so the view is exactly what the
            # planner left in it. Naming it "unreadable" would send the operator to
            # look at the authority for a defect that lives in the authoring stage.
            logger.warning("published project has no authored pair [%s] (run=%s)", slug, ctx.run_id)
            return ctx, PlanRefError("bootstrap-invalid-body")
    try:
        check_project_metadata({roadmap_path: roadmap.content, increment_path: increment.content})
    except MetadataError as error:
        logger.warning("project metadata refused [%s] (run=%s)", error.rule, ctx.run_id)
        return ctx, PlanRefError("bootstrap-invalid-metadata", detail=error.rule)
    snapshot = snapshot_from_bytes(
        increment_path,
        increment.content.encode("utf-8"),
        source_kind="BOOTSTRAP",
        format=PLAN_V2,
        roadmap=roadmap.content,
    )
    if snapshot.format_error is not None:
        # The grammar refused the authored pair. Reported as the metadata rule the
        # repair round already knows how to name, with the parser's own rule logged:
        # admission's vocabulary is closed, the operator's is not.
        logger.warning("authored plan refused [%s] (run=%s)", snapshot.format_error, ctx.run_id)
        # The rule travels with the refusal even though the *code* stays the metadata one:
        # the repair prompt is the only place that can act on it, and "invalid metadata"
        # alone tells a planner nothing it could not have guessed (P4-3).
        return ctx, PlanRefError("bootstrap-invalid-metadata", detail=snapshot.format_error)
    if snapshot.graph is not None:
        # R1/D-V2-10: the plan only *requests* a disposition; the caller's declaration is
        # the sole source of owner and reference. Binding therefore always runs -- the old
        # `and granted` skipped it precisely when the caller sent nothing, which is the one
        # case where an unbound request has no other gate: the plan was admitted, sealed and
        # handed to a coder with a waiver nobody gave. `bind_dispositions` is a no-op for a
        # graph with no requests, so the always-bound form costs nothing on that route.
        try:
            snapshot = replace(
                snapshot,
                graph=bind_dispositions(snapshot.graph, granted, today=datetime.now(UTC).date()),
            )
        except PlanRefError as error:
            logger.warning("disposition binding refused [%s] (run=%s)", error.rule, ctx.run_id)
            return ctx, error
    bound = replace(
        ctx,
        admission=_WorkflowAdmission(
            snapshot,
            True,
            ctx.replans_allowed,
            snapshot_backed=True,
            from_acquisition=True,
        ),
        managed_plan_ref=snapshot.ref,
        plan_path=ctx.workspace / snapshot.ref.workspace_relative_path,
        acquisition=None,
    )
    try:
        _record_admission_attempt(
            ctx.artifact_paths,
            run_id=ctx.run_id,
            plan_ref=snapshot.ref,
            attempt=None,
            status="ACQUIRING",
            deadline=ctx.deadline_mono,
            managed_binding=bound.admission_binding,
        )
    except (OSError, ValueError) as error:
        _admission_storage_failure(bound, error)
    # N1/D-V2-5: mint and store the seal now, so the coder stage has an oracle and the gate can
    # refuse a missing one instead of rewriting the plan to make absence legal.
    refused = _seal_published_project(bound, snapshot)
    if refused is not None:
        logger.warning("published project not sealed [%s/%s] (run=%s)", refused.rule, refused.detail, ctx.run_id)
        # The *bound* context is not handed back (every other refusal in this function returns
        # ``ctx``): an unsealed project has no oracle, so the value a caller could dispatch a
        # coder from must not carry an admission.
        return ctx, refused
    return bound, None


#: Seal refusals that a second authoring stage cannot fix.
#:
#: The family is one rule (``bootstrap-acceptance-unsealed``) because the caller sees one fact
#: -- "the project was not sealed" -- while the *detail* is the closed rule of the producer
#: that refused. These details are the consistency half: admission accepted the graph and the
#: seal refused it, which is a defect in this build, not in the planner's prose. Spending the
#: repair budget on our own inconsistency would burn a model call and end in a worse code.
_UNREPAIRABLE_SEAL_RULES: frozenset[str] = frozenset(
    {
        "plan-graph-missing",
        "seal-uncovered-contracts",
        "seal-attestation-unowned",
        "seal-attestation-artifact-missing",
        "seal-plan-graph-mismatch",
        "seal-totality-mismatch",
        "seal-conflict",
        "seal-record-mismatch",
        "seal-record-missing",
        "seal-pointer-invalid",
        "seal-pointer-unreadable",
        "seal-store-unwritable",
        "seal-store-unreadable",
    }
)


def _seal_published_project(ctx: WorkflowContext, snapshot: PlanSnapshot) -> PlanRefError | None:
    """Mint the acceptance seal for the revision admission just read, or refuse (N1, D-V2-5).

    Before this function the route had no seal at all: ``mint_seal`` was reachable only from
    the defect-correction route and from tests, so every V2 stage refused
    ``acceptance-seal/missing`` and CT-3.6 -- and every rule inside it -- was a guard nobody
    tripped. The two halves of that gap are visible here: the collection report the mint needs
    could only be produced by a collector that needed a minted seal (:func:`collect_sealed_tree`
    breaks that cycle), and nothing ran the mint after admission succeeded.

    Order is load-bearing. The seal is minted *after* every admission refusal has already
    returned, so a project that admission would reject never gets a seal that outlives the
    refusal, and it is minted *before* the coder is dispatched, so the coder's first stage can
    rely on the pointer existing (D-V2-5 §3).

    ``candidate_revision_id`` is the sealed revision here, not a candidate: the acceptance
    closure lives in the revision the authoring stage published, and C2 says the revision pin
    is consulted once -- at admission -- while standing custody is content-based
    (``verify_plan`` + ``verify_sealed_root``) from then on.
    """
    managed = ctx.managed_execution
    slug = ctx.project_hint
    graph = snapshot.graph
    if managed is None or slug is None:  # pragma: no cover - the route proved both before the stage
        return PlanRefError("bootstrap-unavailable")
    if graph is None:
        # A PLAN-V2 snapshot with no graph cannot describe a contract, let alone seal one.
        return PlanRefError("bootstrap-acceptance-unsealed", detail="plan-graph-missing")
    sealed_root = f"worklogs/{slug}/acceptance"
    acceptance_root = ctx.workspace / sealed_root
    with _pinned_verify_substrate(ctx) as substrate:
        if substrate is None:
            # No pinned cell means the collection would run on the host tree, which is what the
            # coder just edited; that is an authority fact, so it is retryable and pre-seal.
            return PlanRefError("bootstrap-unavailable")
        try:
            collection = collect_sealed_tree(
                acceptance_root,
                sealed_root=sealed_root,
                workspace=ctx.workspace,
                deadline=ctx.deadline_mono,
                executor=substrate.executor,
            )
        except AcceptanceCollectionError as error:
            return PlanRefError("bootstrap-acceptance-unsealed", detail=error.rule)
        except AcceptanceBundleError as error:
            # ``sealed-root-invalid`` stays the seal's rule on the way in, by design.
            return PlanRefError("bootstrap-acceptance-unsealed", detail=error.rule)
    try:
        bundle = mint_seal(
            graph=graph,
            plan_bytes=snapshot.utf8_bytes,
            revision_id=managed.current_revision_id,
            sealed_root=sealed_root,
            acceptance_root=acceptance_root,
            collected=collection.nodeids,
        )
    except AcceptanceBundleError as error:
        return PlanRefError("bootstrap-acceptance-unsealed", detail=error.rule)
    except PlanV2Error as error:
        # ``mint_seal`` resolves the plan's selectors against the collection, so a selector
        # nothing collected surfaces here as the parser's own rule. It is content, and the
        # repair prompt is the only place that can act on it (P4-3).
        return PlanRefError("bootstrap-acceptance-unsealed", detail=error.rule)
    try:
        SealStore(ctx.workspace).store(bundle)
    except AcceptanceBundleError as error:
        # A second mint with a different digest means the pointer already names another seal.
        # On the create route that is a conflict, not a supersede: D-V2-9 allows one revision,
        # so nothing here may swing the pointer over a record a reviewer is reading.
        rule = "seal-conflict" if error.rule == "seal-supersede-required" else error.rule
        return PlanRefError("bootstrap-acceptance-unsealed", detail=rule)
    return None


_CLARIFICATION_V2_RULES: dict[str, str] = {
    "AMBIGUOUS_PROJECT": "ambiguous-project",
    "UNKNOWN_INCREMENT": "unknown-increment",
    "MISSING_CONTEXT": "needs-clarification",
}


def _bind_acquisition_admission(
    ctx: WorkflowContext, outcome: AcquisitionOutcome
) -> tuple[WorkflowContext, int | None]:
    """Bind the admitted plan after the acquisition planner, or stop the run.

    Returns ``(context, None)`` when the run may continue, or ``(context, code)``
    when it may not. The context is immutable, so a binding returns a *new* one
    rather than mutating the run: a frozen context that could be edited mid-run
    would be a second source of truth for what the coder is bound to.

    The three non-snapshot outcomes are distinct operator facts, not one generic
    failure: a clarification needs another question, a bootstrap needs the
    authority to render and install a project, and an unusable choice needs a
    retry -- so each is recorded under its own rule.
    """
    if outcome.snapshot is None:
        if outcome.clarification is not None:
            rule = f"clarification/{outcome.clarification.reason.lower().replace('_', '-')}"
            v2_rule = _CLARIFICATION_V2_RULES.get(outcome.clarification.reason, "needs-clarification")
            v2_diag: tuple[str, str, str, str, str | None] = ("selection", v2_rule, "ERROR", "INDETERMINATE", None)
        else:  # pragma: no cover - AcquisitionOutcome forbids the shape
            rule = "acquisition-unresolved"
            v2_diag = ("selection", "needs-clarification", "ERROR", "INDETERMINATE", None)
        return ctx, _blocked_plan_request(
            run_id=ctx.run_id,
            task=ctx.base_task,
            rule=rule,
            base_dir=ctx.artifact_paths.base_dir,
            deadline=ctx.deadline_mono,
            managed_binding=ctx.admission_binding,
            attempt_kind="ACQUISITION" if ctx.admission_binding is not None else "EXPLICIT_INPUT",
            v2_diagnostic=v2_diag,
        )[0]

    snapshot = outcome.snapshot
    if ctx.project_hint is not None:
        # The caller asked for a NEW project by name; the planner answered by
        # selecting an EXISTING one. Continuing would bind the run to a repository
        # the operator did not ask for, so this is a refusal rather than a retry:
        # no plan was authored, and re-planning under the same request would only
        # ask the model to guess again which project the caller meant. The mirror
        # case -- a bootstrap on a select-only route -- is refused above under the
        # same rule, so both directions name one fact: the planner's project route
        # contradicted the caller's.
        return ctx, _blocked_plan_request(
            run_id=ctx.run_id,
            task=ctx.base_task,
            rule="project-route-mismatch",
            base_dir=ctx.artifact_paths.base_dir,
            deadline=ctx.deadline_mono,
            managed_binding=ctx.admission_binding,
            attempt_kind="ACQUISITION" if ctx.admission_binding is not None else "EXPLICIT_INPUT",
            v2_diagnostic=("selection", "project-route-mismatch", "ERROR", "INDETERMINATE", None),
        )[0]
    # A coder-bearing run always has a planner (the role list was validated at
    # entry), so the shared planner budget is allowed from here on.
    bound = replace(
        ctx,
        admission=_WorkflowAdmission(
            snapshot,
            True,
            ctx.replans_allowed,
            snapshot_backed=True,
            from_acquisition=True,
        ),
        managed_plan_ref=snapshot.ref,
        plan_path=ctx.plan_path or ctx.workspace / snapshot.ref.workspace_relative_path,
        acquisition=None,
    )
    try:
        _record_admission_attempt(
            ctx.artifact_paths,
            run_id=ctx.run_id,
            plan_ref=snapshot.ref,
            attempt=None,
            status="ACQUIRING",
            deadline=ctx.deadline_mono,
            managed_binding=bound.admission_binding,
        )
    except (OSError, ValueError) as error:
        _admission_storage_failure(bound, error)
        return bound, _admission_exit_code(bound)
    return bound, None


def _run_linear(ctx: WorkflowContext, roles: list[str], run_stage_fn: Callable[..., int]) -> int:
    """Run every role once, evaluating after coder and enforcing verifier facts afterward."""
    progress = WorkflowProgress()
    loop = _run_role_loop(ctx, roles, run_stage_fn, progress=progress)
    if loop.exit_code != 0:
        return loop.exit_code
    ctx = loop.ctx
    n_stages = loop.n_stages
    last_role = loop.last_role
    eval_report = loop.eval_report
    verification = loop.verification

    route = _effective_controller_route(
        eval_report,
        verification,
        gate_mode=ctx.verify_gate_mode,
        eval_requested="eval" in roles,
        verification_required="coder" in roles,
        integrity_failed=_integrity_failed(ctx),
    )
    if route == "blocked":
        detail = (
            _verification_block_detail(verification)
            if verification is not None and verification.blocking
            else "eval stage produced no usable verdict"
        )
        reason = f"workflow blocked after eval: {detail}"
    elif ctx.verify_gate_mode == "enforce" and verification is not None and verification.blocking:
        reason = f"enforce verification gate: {_verification_block_detail(verification)}"
    elif eval_report is not None:
        reason = f"eval verdict {eval_report.verdict} (linear; no repair loop)"
    elif "eval" in roles:
        reason = "eval stage ran but produced no verdict"
    else:
        reason = "linear workflow completed"

    _write_terminal_state(
        ctx,
        last_role=last_role,
        eval_report=eval_report,
        progress=progress,
        reason=reason,
        eval_requested="eval" in roles,
        route_override=route,
    )
    _print_terminal_summary(
        ctx, n_stages=n_stages, eval_report=eval_report, repair_rounds_used=0, effective_route=route
    )
    return 0


def workflow_exit_code(result_code: int, terminal_state: FlowState | None) -> int:
    """Map a workflow run to its process exit code."""
    if result_code != 0:
        return result_code
    if terminal_state is None:
        return 1
    return 0 if terminal_state.status == "DONE" else 1


# ── Public API ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _AdmissionDiagnostic:
    """Projection deliberately excludes paths, messages and exception bodies."""

    validator: str
    rule: str
    severity: str
    line: int | None = None


@dataclass(frozen=True, slots=True)
class _PlanAdmissionValidation:
    snapshot: PlanSnapshot
    outcome: Literal["PASS", "DIAGNOSTICS", "INDETERMINATE"]
    diagnostics: tuple[_AdmissionDiagnostic, ...]


def _admission_diagnostics(validator: str, diagnostics: tuple[PlanDiagnostic, ...]) -> tuple[_AdmissionDiagnostic, ...]:
    projected = []
    for item in diagnostics:
        if item.rule not in ADMISSION_RULES[validator] or item.severity not in {"WARN", "FAIL", "ERROR"}:
            raise ValueError("unrecognized validator diagnostic")
        line = item.line if type(item.line) is int and item.line > 0 else None
        projected.append(_AdmissionDiagnostic(validator, item.rule, item.severity, line))
    return tuple(projected)


def _validate_plan_admission(snapshot: PlanSnapshot) -> _PlanAdmissionValidation:
    """Admit one snapshot under the grammar it was captured with.

    A ``PLAN-V2`` snapshot never reaches the V1 validators: they read ``ids``
    and slice records the V1 extractor would have produced from V2 bytes, and
    judging a correct V2 plan by V1 rules is the mixed state INV-01 forbids.
    """
    if snapshot.format != PLAN_V1:
        return _validate_v2_admission(snapshot)
    diagnostics: tuple[_AdmissionDiagnostic, ...] = ()
    try:
        diagnostics += _admission_diagnostics(
            "precheck", precheck(snapshot.text, path=snapshot.ref.workspace_relative_path).diagnostics
        )
    except Exception:  # noqa: BLE001 - closed failure evidence, never swallow a validator error as success
        diagnostics += (_AdmissionDiagnostic("plan-ref", "validator-error", "ERROR"),)
    try:
        diagnostics += _admission_diagnostics(
            "kill-directives",
            tuple(
                validate_kill_directives(
                    snapshot.text,
                    snapshot.ids,
                    path=snapshot.ref.workspace_relative_path,
                )
            ),
        )
    except Exception:  # noqa: BLE001 - preserve other validator diagnostics, without leaking exception bodies
        diagnostics += (_AdmissionDiagnostic("plan-ref", "validator-error", "ERROR"),)
    if not snapshot.text.strip():
        return _PlanAdmissionValidation(
            snapshot, "INDETERMINATE", (_AdmissionDiagnostic("plan-ref", "empty", "ERROR"),)
        )
    if any(item.severity == "ERROR" for item in diagnostics):
        return _PlanAdmissionValidation(snapshot, "INDETERMINATE", diagnostics)
    if any(item.severity == "FAIL" for item in diagnostics):
        return _PlanAdmissionValidation(snapshot, "DIAGNOSTICS", diagnostics)
    if not snapshot.ids.slice_records:
        return _PlanAdmissionValidation(
            snapshot,
            "INDETERMINATE",
            (
                *diagnostics,
                _AdmissionDiagnostic("plan-ref", "zero-slices", "ERROR"),
            ),
        )
    return _PlanAdmissionValidation(snapshot, "PASS", diagnostics)


def _validate_v2_admission(snapshot: PlanSnapshot) -> _PlanAdmissionValidation:
    """Admit a V2 snapshot from its already-parsed graph or its closed rule.

    ``snapshot_from_bytes`` parsed the pair once, so admission here is a
    projection and not a second parse: no repair, no fallback, and a snapshot
    that somehow carries neither a graph nor a rule fails closed rather than
    passing by default.
    """
    if snapshot.format != PLAN_V2:
        return _PlanAdmissionValidation(
            snapshot, "INDETERMINATE", (_AdmissionDiagnostic("plan-v2", "format-mismatch", "ERROR"),)
        )
    if snapshot.format_error is not None:
        return _PlanAdmissionValidation(
            snapshot, "INDETERMINATE", (_AdmissionDiagnostic("plan-v2", snapshot.format_error, "ERROR"),)
        )
    if snapshot.graph is None:
        return _PlanAdmissionValidation(
            snapshot, "INDETERMINATE", (_AdmissionDiagnostic("plan-v2", "graph-missing", "ERROR"),)
        )
    return _PlanAdmissionValidation(snapshot, "PASS", ())


def _require_managed_publisher(ctx: WorkflowContext) -> CandidatePlanPublisher:
    """CT115: a repair needs the authority, and its absence is a named refusal.

    A plan that admits needs no publication — its bytes are already canonical — so
    an unmanaged run keeps working for explicit plans. A repair invalidates that:
    the revised bytes must be committed somewhere, and ``prepare-failed`` would
    name the wrong fault when the real one is "this run has no managed execution".
    The check therefore sits next to the reserved planner attempt, not at the top
    of the gate, and it is the only place that decides the run cannot publish.
    """
    publisher = ctx.plan_publisher
    if publisher is None:
        raise PlanPromotionError("managed-execution-absent")
    return publisher


_V2_RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_V2_WORKSPACE_ID_RE = re.compile(r"ws-[0-9a-f]{32}")
_V2_REVISION_ID_RE = re.compile(r"rev-[0-9a-f]{32}")
_V2_OP_ID_RE = re.compile(r"op-[0-9a-f]{32}")


def _managed_admission_binding(managed: ManagedExecution | None, *, run_id: str) -> ManagedAdmissionBinding | None:
    """Build immutable v2 binding strictly for managed-child runs (Q150 = A).

    Returns ``None`` for unmanaged runs, top-level runs where ``owner_run_id == run_id``,
    and partial test doubles that omit authority identity fields, keeping v1 exact.
    """
    if managed is None:
        return None
    workspace_id = getattr(getattr(managed, "binding", None), "workspace_id", None)
    owner_run_id = getattr(managed, "root_owner_run_id", None)
    generation = getattr(getattr(managed, "grant", None), "generation", None)
    base_revision = getattr(managed, "current_revision_id", None)
    if (
        not isinstance(workspace_id, str)
        or _V2_WORKSPACE_ID_RE.fullmatch(workspace_id) is None
        or not isinstance(owner_run_id, str)
        or _V2_RUN_ID_RE.fullmatch(owner_run_id) is None
        or owner_run_id == run_id
        or type(generation) is not int
        or generation < 1
        or not isinstance(base_revision, str)
        or _V2_REVISION_ID_RE.fullmatch(base_revision) is None
    ):
        return None
    return ManagedAdmissionBinding(
        workspace_id=workspace_id,
        owner_run_id=owner_run_id,
        generation=generation,
        base_revision=base_revision,
    )


def _current_managed_revision(ctx: WorkflowContext) -> str | None:
    if ctx.admission_binding is None or ctx.managed_execution is None:
        return None
    rev = getattr(ctx.managed_execution, "current_revision_id", None)
    if isinstance(rev, str) and _V2_REVISION_ID_RE.fullmatch(rev) is not None:
        return rev
    return ctx.admission_binding.base_revision


@dataclass(frozen=True, slots=True)
class _PromotionReceipt:
    """Promoted plan snapshot plus authority revision/operation receipt when available."""

    snapshot: PlanSnapshot
    revision_id: str | None = None
    operation_id: str | None = None


@runtime_checkable
class _ReceiptCandidatePublisher(Protocol):
    def publish_candidate_receipt(
        self, source: PlanSnapshot, candidate: PlanSnapshot, *, deadline: float | None = None
    ) -> Any: ...


def _promote_validated_plan_receipt(
    source: PlanSnapshot,
    validated: _PlanAdmissionValidation,
    *,
    publisher: CandidatePlanPublisher,
    deadline: float | None = None,
) -> _PromotionReceipt:
    """Publish validated bytes through the injected candidate port and retain receipts."""
    if validated.outcome != "PASS":
        raise PlanPromotionError("prepare-failed")
    try:
        if isinstance(publisher, _ReceiptCandidatePublisher):
            publication = publisher.publish_candidate_receipt(source, validated.snapshot, deadline=deadline)
            ref = publication.plan_ref
            rev_id = getattr(publication, "revision_id", None)
            op_id = _valid_v2_operation_id(getattr(publication, "operation_id", None))
        else:
            ref = publisher.publish_candidate(source, validated.snapshot, deadline=deadline)
            rev_id = None
            op_id = None
    except PlanPromotionError:
        raise
    except Exception as error:  # sanitize transport/backend details into the admission schema's closed vocabulary
        code = getattr(error, "code", None)
        uncertain = code in {"DURABILITY_UNKNOWN", "CORRUPT_STATE", "EXECUTION_UNKNOWN", "TERMINALITY_UNKNOWN"}
        rule = "durability-unknown" if uncertain else "prepare-failed"
        op_id = _valid_v2_operation_id(getattr(error, "operation_id", None)) if uncertain else None
        raise PlanPromotionError(rule, replaced=uncertain, operation_id=op_id) from error
    expected = PlanRef(
        source.ref.workspace_relative_path,
        source.ref.source_kind,
        validated.snapshot.ref.sha256,
    )
    if ref != expected:
        raise PlanPromotionError("hash-mismatch", replaced=True)
    return _PromotionReceipt(
        snapshot=replace(validated.snapshot, ref=ref),
        revision_id=rev_id if isinstance(rev_id, str) else None,
        operation_id=op_id,
    )


def _promote_validated_plan(
    source: PlanSnapshot,
    validated: _PlanAdmissionValidation,
    *,
    publisher: CandidatePlanPublisher,
    deadline: float | None = None,
) -> PlanSnapshot:
    """Publish only validated bytes through the injected managed candidate port.

    The host path is not opened here and there is no fallback: the caller supplies
    the port it proved it has (``_require_managed_publisher``), so a missing
    authority is refused before any repair is dispatched.
    """
    return _promote_validated_plan_receipt(
        source,
        validated,
        publisher=publisher,
        deadline=deadline,
    ).snapshot


def _admission_progress(ctx: WorkflowContext, progress: WorkflowProgress) -> WorkflowProgress:
    if ctx.admission is None:
        return progress
    return replace(progress, plan_version=ctx.admission.plan_version, replan_round=ctx.admission.planner_calls)


def _admission_exit_code(ctx: WorkflowContext) -> int:
    return ctx.admission.block_exit_code if ctx.admission is not None else 2


def _admission_failed(ctx: WorkflowContext, reason: str) -> FlowState | None:
    state = ctx.admission
    if state is None:
        raise RuntimeError("admission authority absent")
    state.block_exit_code = 1 if reason in {"planner-unavailable", "planner-budget"} else 2
    state.failure = reason
    state.admitted = False
    print(f"fa workflow: admission blocked: {reason}", file=sys.stderr)
    failed = FlowState(
        run_id=ctx.run_id,
        task=ctx.base_task or "",
        status="FAILED",
        active_role="workflow",
        active_plan_id=ctx.plan_identity(),
        active_plan_version=state.plan_version,
        replan_round=state.planner_calls,
        last_actor="workflow",
        last_transition_reason="explicit plan admission blocked",
        last_route_decision="blocked",
        blocked_reason=f"admission/{reason}",
        judged=state.last_eval_report is not None,
    )
    try:
        _persist_flow_state(ctx.artifact_paths.flow_state, failed)
    except (OSError, ValueError):
        print("fa workflow: blocked flow storage error: append-failed", file=sys.stderr)
        return None
    return failed


def _admission_storage_failure(ctx: WorkflowContext, error: OSError | ValueError) -> None:
    rule = error.rule if isinstance(error, AdmissionIOError) else "append-failed"
    if rule == "lock-failed" and _deadline_exceeded(ctx):
        _write_deadline_state(ctx, "workflow", progress=WorkflowProgress())
        return
    _admission_failed(ctx, f"artifact-io/{rule}")


def _v2_attempt_diagnostics(
    diagnostics: tuple[_AdmissionDiagnostic, ...], *, kind: str, route: str, ref: PlanRef | None
) -> list[dict[str, Any]]:
    if kind == "ACQUISITION" and ref is not None and ref.source_kind == "EXISTING_SELECTION" and route == "RETRY":
        # v2 EXISTING_SELECTION RETRY accepts only FAIL diagnostics in the pre-coder set.
        filtered = [item for item in diagnostics if item.severity == "FAIL"]
        if filtered:
            return [asdict(item) for item in filtered]
    return [asdict(item) for item in diagnostics]


def _admission_attempt(
    ctx: WorkflowContext,
    validation: _PlanAdmissionValidation,
    *,
    kind: str,
    route: str,
    candidate: bool = False,
    promoted: PlanSnapshot | None = None,
    input_revision: str | None = None,
    output_revision: str | None = None,
    operation_id: str | None = None,
    bundle_sha256: str | None = None,
    plan_ref_override: PlanRef | None = None,
    clear_plan_ref: bool = False,
) -> None:
    state = ctx.admission
    if state is None:
        raise RuntimeError("admission authority absent")
    plan_ref = None if clear_plan_ref else (plan_ref_override or (promoted or state.snapshot).ref)
    diagnostics = (
        _v2_attempt_diagnostics(validation.diagnostics, kind=kind, route=route, ref=plan_ref)
        if ctx.admission_binding is not None
        else [asdict(item) for item in validation.diagnostics]
    )
    attempt: dict[str, object] = {
        "dispatch_kind": kind,
        "validation": validation.outcome,
        "diagnostics": diagnostics,
        "source_sha256": None if bundle_sha256 is not None else state.snapshot.ref.sha256,
        "candidate_sha256": validation.snapshot.ref.sha256 if candidate else None,
        "promoted_sha256": promoted.ref.sha256 if promoted is not None else None,
        "route": route,
    }
    if ctx.admission_binding is not None:
        resolved_in = input_revision or _current_managed_revision(ctx) or ctx.admission_binding.base_revision
        resolved_out = (
            output_revision if clear_plan_ref or operation_id is not None else (output_revision or resolved_in)
        )
        attempt.update(
            {
                "input_revision": resolved_in,
                "output_revision": resolved_out,
                "operation_id": operation_id,
                "bundle_sha256": bundle_sha256,
            }
        )
    _record_admission_attempt(
        ctx.artifact_paths,
        run_id=ctx.run_id,
        plan_ref=plan_ref,
        attempt=attempt,
        status={"RETRY": "ACQUIRING", "ADMITTED": "ADMITTED", "BLOCKED": "BLOCKED"}[route],
        deadline=ctx.deadline_mono,
        managed_binding=ctx.admission_binding,
    )


def _check_admission_source(ctx: WorkflowContext) -> None:
    """Re-verify the admitted plan against the substrate that actually holds it.

    Two substrates, one rule: the digest recorded at admission must still describe
    the bytes this run is bound to.

    * host mode -- the plan is a file under the workspace, so re-read it and
      compare. This is the original behaviour and stays byte-for-byte.
    * snapshot mode -- the plan arrived as bytes from a pinned view, so there is
      no host copy and reading one would judge a different tree (the defect R24
      removed for the verify gate). The bytes are in the admission record's own
      snapshot, and re-hashing them is the check that they were not replaced
      after validation.
    """
    if ctx.admission is None:
        raise RuntimeError("admission authority absent")
    source = ctx.admission.snapshot
    if ctx.admission.snapshot_backed:
        if hashlib.sha256(source.utf8_bytes).hexdigest() != source.ref.sha256:
            raise PlanRefError("source-changed")
        return
    actual = read_plan_snapshot(ctx.workspace, Path(source.ref.workspace_relative_path))
    if actual.ref.sha256 != source.ref.sha256:
        raise PlanRefError("source-changed")


@dataclass(frozen=True, slots=True)
class _RepairPromotionOutcome:
    """Repair validation plus authority publication receipts when promoted."""

    validation: _PlanAdmissionValidation
    promoted: PlanSnapshot | None
    input_revision: str | None = None
    output_revision: str | None = None
    operation_id: str | None = None


def _run_admission_repair_with_receipt(
    ctx: WorkflowContext,
    progress: WorkflowProgress,
    run_stage_fn: Callable[..., int],
    *,
    kind: PlannerDispatchKind,
    draft: PlanSnapshot,
    publisher: CandidatePlanPublisher,
    diagnostics: tuple[_AdmissionDiagnostic, ...] = (),
    reason: str = "",
) -> _RepairPromotionOutcome:
    """One reserved planner attempt; own its target through cleanup, then use only bytes."""
    if ctx.admission is None:
        raise RuntimeError("admission authority absent")
    source = ctx.admission.snapshot
    ctx.admission.candidate = None
    _check_admission_source(ctx)
    # The captured bytes describe ONE stage. Clearing here -- before the stage is
    # dispatched, not only when this round first runs -- is what keeps a second
    # repair round from validating the previous round's candidate, which would
    # silently promote bytes nobody wrote this time.
    reset_stage_candidate()
    dispatch = seed_plan_candidate(ctx.workspace, source, run_id=ctx.run_id, kind=kind, draft=draft)
    if dispatch.candidate_target is None:
        raise PlannerDispatchError
    target = Path(dispatch.candidate_target)
    seed_text = (source.utf8_bytes if draft is None else draft.utf8_bytes).decode("utf-8")
    try:
        role_tasks = dict(ctx.per_role_task)
        role_tasks["planner"] = (
            f"{ctx.base_task or ''}\nRevise only the owned candidate {target.as_posix()}. "
            "Read that candidate; fix structural and kill-directive diagnostics. "
            "Do not edit the canonical plan.\n"
            f"Revision reason: {reason}\n"
            f"Sanitized diagnostics: {json.dumps([asdict(item) for item in diagnostics])}"
        )
        try:
            result = _run_stage(
                replace(ctx, per_role_task=role_tasks),
                "planner",
                fresh=False,
                progress=progress,
                transition_reason=f"{kind.value} candidate revision",
                run_stage_fn=run_stage_fn,
                planner_dispatch=dispatch,
                candidate_seed_text=seed_text,
            )
        except Exception as error:
            raise PlanPromotionError("prepare-failed") from error
        if result.exit_code != 0:
            raise PlanPromotionError("prepare-failed")
        candidate = _read_repair_candidate(ctx, source, target)
        ctx.admission.candidate = candidate
    finally:
        # Remove only the exact controller-owned leaf, never follow a replacement alias.
        # Keep progress in the immutable buffer, not in a live pathname. Cleanup precedes
        # publication so a cleanup failure cannot occur after irreversible replacement.
        with _private_artifact_directory(ctx.workspace / target.parent) as parent:
            os.unlink(target.name, dir_fd=parent)
            os.fsync(parent)
    validation = _validate_plan_admission(candidate)
    if validation.outcome != "PASS":
        return _RepairPromotionOutcome(
            validation=validation, promoted=None, input_revision=_current_managed_revision(ctx)
        )
    in_rev = _current_managed_revision(ctx)
    try:
        receipt = _promote_validated_plan_receipt(source, validation, publisher=publisher, deadline=ctx.deadline_mono)
    except PlanPromotionError:
        # CT119: the candidate was already unlinked above, so the only copy of
        # the bytes the authority refused is the snapshot in memory.
        _retain_rejected_draft(ctx, validation.snapshot)
        raise
    return _RepairPromotionOutcome(
        validation=validation,
        promoted=receipt.snapshot,
        input_revision=in_rev,
        output_revision=receipt.revision_id,
        operation_id=receipt.operation_id,
    )


def _run_admission_repair(
    ctx: WorkflowContext,
    progress: WorkflowProgress,
    run_stage_fn: Callable[..., int],
    *,
    kind: PlannerDispatchKind,
    draft: PlanSnapshot,
    publisher: CandidatePlanPublisher,
    diagnostics: tuple[_AdmissionDiagnostic, ...] = (),
    reason: str = "",
) -> tuple[_PlanAdmissionValidation, PlanSnapshot | None]:
    outcome = _run_admission_repair_with_receipt(
        ctx,
        progress,
        run_stage_fn,
        kind=kind,
        draft=draft,
        publisher=publisher,
        diagnostics=diagnostics,
        reason=reason,
    )
    return outcome.validation, outcome.promoted


def _read_repair_candidate(ctx: WorkflowContext, source: PlanSnapshot, target: Path) -> PlanSnapshot:
    """Read the repaired candidate from the substrate that actually holds it.

    Managed: the planner wrote the authority's staged buffer, so the bytes come
    back through that view. Host mode: the planner wrote the controller's own
    `.fa/admission` copy and it is read as a file, exactly as before.

    The choice is made HERE, once, from what the composition bound. A managed run
    (one with a reader) never falls back to the host path: the file under `.fa`
    holds the *seed*, so reading it after the stage would validate bytes nobody
    wrote and could publish an unchanged candidate as a repair.
    """
    label = source.ref.workspace_relative_path
    reader = ctx.managed_candidate_reader
    captured = None if reader is None else reader(source.ref)
    if captured is None:
        # No buffer bytes for this stage: it owns no candidate (host mode) or the
        # double driving it binds no buffer. A candidate-owning managed stage
        # cannot land here -- the composition root fails it closed instead.
        return read_plan_snapshot(ctx.workspace, target)
    content, digest = captured
    snapshot = snapshot_from_bytes(label, content.encode("utf-8"))
    if snapshot.ref.sha256 != digest:
        # The buffer changed between the read and the digest the authority
        # reported; validating either one now would be picking a favourite.
        raise PlanPromotionError("hash-mismatch")
    return snapshot


def _retain_rejected_draft(ctx: WorkflowContext, snapshot: PlanSnapshot) -> None:
    """Keep refused bytes under their hash; never turn retention into the failure."""
    try:
        retain_plan_draft(ctx.workspace, ctx.run_id, snapshot.utf8_bytes, deadline=ctx.deadline_mono)
    except Exception as error:  # noqa: BLE001 - the promotion rule must survive any retention fault
        logger.warning("plan.draft.retained=false run_id=%s workspace=%s error=%s", ctx.run_id, ctx.workspace, error)


def _admission_error(
    ctx: WorkflowContext,
    error: PlanRefError | PlanPromotionError | PlannerDispatchError,
    *,
    kind: str = "EXPLICIT_INPUT",
    input_revision: str | None = None,
) -> None:
    if ctx.admission is None:
        raise RuntimeError("admission authority absent")
    validator = "plan-ref" if isinstance(error, PlanRefError) else "promotion"
    rule = "scope-denied" if isinstance(error, PlannerDispatchError) else error.rule
    effective_kind = (
        "ACQUISITION"
        if ctx.admission_binding is not None and ctx.admission.from_acquisition and kind == "EXPLICIT_INPUT"
        else kind
    )
    candidate = ctx.admission.candidate if kind != "EXPLICIT_INPUT" else None
    op_id = (
        _valid_v2_operation_id(getattr(error, "operation_id", None)) if isinstance(error, PlanPromotionError) else None
    )
    bootstrap_receipt = ctx.admission.bootstrap_receipt if ctx.admission_binding is not None else None
    if effective_kind == "ACQUISITION" and bootstrap_receipt is not None:
        # Bootstrap rejections must satisfy _validate_v2_bootstrap (ref=None, validator=bootstrap).
        validation = _PlanAdmissionValidation(
            ctx.admission.snapshot, "INDETERMINATE", (_AdmissionDiagnostic("bootstrap", "hash-mismatch", "ERROR"),)
        )
        try:
            _admission_attempt(
                ctx,
                validation,
                kind="ACQUISITION",
                route="BLOCKED",
                candidate=True,
                input_revision=bootstrap_receipt.input_revision,
                bundle_sha256=bootstrap_receipt.bundle_sha256,
                clear_plan_ref=True,
            )
        except (OSError, ValueError) as failure:
            _admission_storage_failure(ctx, failure)
            return
        ctx.admission.bootstrap_receipt = None
        _admission_failed(ctx, f"{validator}/{rule}")
        return
    validation = _PlanAdmissionValidation(
        candidate or ctx.admission.snapshot, "INDETERMINATE", (_AdmissionDiagnostic(validator, rule, "ERROR"),)
    )
    try:
        _admission_attempt(
            ctx,
            validation,
            kind=effective_kind,
            route="BLOCKED",
            candidate=candidate is not None,
            input_revision=input_revision,
            operation_id=op_id,
        )
    except (OSError, ValueError) as failure:
        _admission_storage_failure(ctx, failure)
        return
    _admission_failed(ctx, f"{validator}/{rule}")


def _admit_bootstrap_attempt(
    ctx: WorkflowContext,
    validated: _PlanAdmissionValidation,
    receipt: _BootstrapReceipt,
) -> bool:
    """Persist the v2 ACQUISITION attempt for an installed BOOTSTRAP increment."""
    state = ctx.admission
    if state is None:  # pragma: no cover
        raise RuntimeError("admission authority absent")
    if validated.outcome == "PASS":
        _admission_attempt(
            ctx,
            _PlanAdmissionValidation(state.snapshot, "PASS", ()),
            kind="ACQUISITION",
            route="ADMITTED",
            candidate=True,
            promoted=state.snapshot,
            input_revision=receipt.input_revision,
            output_revision=receipt.output_revision,
            operation_id=receipt.operation_id,
            bundle_sha256=receipt.bundle_sha256,
        )
        state.bootstrap_receipt = None
        state.admitted = True
        return True
    severity = "FAIL" if validated.outcome == "DIAGNOSTICS" else "ERROR"
    rejected = _PlanAdmissionValidation(
        state.snapshot,
        validated.outcome,
        (_AdmissionDiagnostic("bootstrap", "invalid-body", severity),),
    )
    _admission_attempt(
        ctx,
        rejected,
        kind="ACQUISITION",
        route="BLOCKED",
        candidate=True,
        input_revision=receipt.input_revision,
        bundle_sha256=receipt.bundle_sha256,
        clear_plan_ref=True,
    )
    state.bootstrap_receipt = None
    _admission_failed(ctx, "bootstrap/invalid-body")
    return False


def _record_budget_blocked_acquisition(
    ctx: WorkflowContext,
    validated: _PlanAdmissionValidation,
    *,
    input_revision: str | None,
) -> None:
    """In v2, an EXISTING_SELECTION with FAIL diagnostics emits RETRY then BLOCKED ADMISSION_REPAIR."""
    _admission_attempt(
        ctx,
        validated,
        kind="ACQUISITION",
        route="RETRY",
        input_revision=input_revision,
    )
    _admission_attempt(
        ctx,
        validated,
        kind="ADMISSION_REPAIR",
        route="BLOCKED",
        input_revision=input_revision,
    )
    _admission_failed(ctx, "validation-or-planner-budget")


def _record_replan_barrier(ctx: WorkflowContext, state: _WorkflowAdmission) -> None:
    """Q67(a): keep canonical ADMITTED on eval replan entry without an invented RETRY."""
    _record_admission_attempt(
        ctx.artifact_paths,
        run_id=ctx.run_id,
        plan_ref=state.snapshot.ref,
        attempt=None,
        status="ADMITTED",
        deadline=ctx.deadline_mono,
        managed_binding=ctx.admission_binding,
    )
    state.admitted = False


def _record_nonreplan_route(
    ctx: WorkflowContext,
    state: _WorkflowAdmission,
    validated: _PlanAdmissionValidation,
    *,
    kind: PlannerDispatchKind,
    candidate: bool,
    can_retry: bool,
    promoted: PlanSnapshot | None,
    input_revision: str | None,
    output_revision: str | None,
    operation_id: str | None,
) -> bool | None:
    """Record one non-replan admission attempt; return bool to terminate gate or None to retry."""
    initial_kind = "ACQUISITION" if (ctx.admission_binding is not None and state.from_acquisition) else "EXPLICIT_INPUT"
    if not candidate and initial_kind == "ACQUISITION" and validated.outcome == "DIAGNOSTICS" and not can_retry:
        _record_budget_blocked_acquisition(ctx, validated, input_revision=input_revision)
        return False
    route = (
        "ADMITTED"
        if validated.outcome == "PASS"
        else "RETRY"
        if validated.outcome == "DIAGNOSTICS" and can_retry
        else "BLOCKED"
    )
    _admission_attempt(
        ctx,
        validated,
        kind=kind.value if candidate else initial_kind,
        route=route,
        candidate=candidate,
        promoted=promoted,
        input_revision=input_revision,
        output_revision=output_revision,
        operation_id=operation_id,
    )
    if route == "ADMITTED":
        state.plan_version += int(kind == PlannerDispatchKind.EVAL_REPLAN)
        state.snapshot = promoted or validated.snapshot
        state.admitted = True
        return True
    if route == "BLOCKED":
        _admission_failed(ctx, "validation-or-planner-budget")
        return False
    return None


def _admit_plan(
    ctx: WorkflowContext,
    progress: WorkflowProgress,
    run_stage_fn: Callable[..., int],
    *,
    replan: bool = False,
    reason: str = "",
) -> bool:
    """Mandatory public pre-coder gate; shared bounded repair/replan state belongs to this run."""
    state = ctx.admission
    if state is None:
        # Internal legacy stage fixtures; public coder entry always binds
        # authority. A PLAN-V2 run has no such fixtures and no legacy excuse:
        # an unbound admission is a defect, so it fails closed (CT-1.4).
        return ctx.plan_format != PLAN_V2
    if state.failure is not None:
        if state.block_exit_code == WORKFLOW_DEADLINE_EXIT_CODE:
            return False
        _admission_failed(ctx, state.failure)
        return False
    attempt_kind = "EXPLICIT_INPUT"
    repair_input_rev = _current_managed_revision(ctx)
    repair_output_rev: str | None = None
    repair_op_id: str | None = None
    try:
        _check_admission_source(ctx)
        if state.admitted and not replan:
            return True
        kind = PlannerDispatchKind.EVAL_REPLAN if replan else PlannerDispatchKind.ADMISSION_REPAIR
        validated = _validate_plan_admission(state.snapshot)
        if not replan and ctx.admission_binding is not None and state.bootstrap_receipt is not None:
            return _admit_bootstrap_attempt(ctx, validated, state.bootstrap_receipt)
        promoted = None
        candidate = False
        replan = replan and validated.outcome == "PASS"
        if replan:
            _record_replan_barrier(ctx, state)
        while True:
            can_retry = (
                state.planner_allowed and state.planner_calls < state.planner_limit and not _deadline_exceeded(ctx)
            )
            if not replan:
                decision = _record_nonreplan_route(
                    ctx,
                    state,
                    validated,
                    kind=kind,
                    candidate=candidate,
                    can_retry=can_retry,
                    promoted=promoted,
                    input_revision=repair_input_rev,
                    output_revision=repair_output_rev,
                    operation_id=repair_op_id,
                )
                if decision is not None:
                    return decision
            elif not can_retry:
                _admission_attempt(
                    ctx,
                    validated,
                    kind=kind.value if ctx.admission_binding is not None else "EXPLICIT_INPUT",
                    route="BLOCKED",
                    candidate=candidate if ctx.admission_binding is not None else False,
                    input_revision=repair_input_rev,
                )
                _admission_failed(ctx, "planner-budget" if state.planner_allowed else "planner-unavailable")
                return False
            attempt_kind = kind.value
            publisher = _require_managed_publisher(ctx)  # CT115: before the attempt is reserved.
            state.planner_calls += 1  # Reserve even when seeding/provider/writer/publication fails.
            repair_input_rev = _current_managed_revision(ctx)
            repair_outcome = _run_admission_repair_with_receipt(
                ctx,
                progress,
                run_stage_fn,
                kind=kind,
                draft=validated.snapshot,
                publisher=publisher,
                diagnostics=validated.diagnostics,
                reason=reason,
            )
            validated = repair_outcome.validation
            promoted = repair_outcome.promoted
            repair_input_rev = repair_outcome.input_revision or repair_input_rev
            repair_output_rev = repair_outcome.output_revision
            repair_op_id = repair_outcome.operation_id
            candidate = True
            replan = False
    except (PlanRefError, PlanPromotionError, PlannerDispatchError) as error:
        if state.block_exit_code != WORKFLOW_DEADLINE_EXIT_CODE:
            _admission_error(ctx, error, kind=attempt_kind, input_revision=repair_input_rev)
    except (OSError, ValueError) as error:
        _admission_storage_failure(ctx, error)
    return False


# The `plan-ref` values the persisted admission schema accepts. Pulled from the
# schema itself rather than copied, so the two cannot drift apart.
_PERSISTED_PLAN_REF_RULES = frozenset(ADMISSION_RULES["plan-ref"])

_V2_BLOCKED_RULE_MAP: dict[str, tuple[str, str, str, str]] = {
    "acquisition-unavailable": ("workspace", "backend-unavailable", "ERROR", "INDETERMINATE"),
    "bootstrap-unavailable": ("bootstrap", "unavailable", "ERROR", "INDETERMINATE"),
    "bootstrap-refused": ("bootstrap", "install-failed", "FAIL", "DIAGNOSTICS"),
    "bootstrap-unreadable": ("bootstrap", "install-failed", "ERROR", "INDETERMINATE"),
    # D-V2-9.2: the name the caller asked to create is taken. Same recorded rule
    # the install path uses, so one event has one diagnostic in the record.
    "bootstrap-collision": ("bootstrap", "collision", "FAIL", "DIAGNOSTICS"),
}


def _v2_blocked_diagnostic(
    rule: str, override: tuple[str, str, str, str, str | None] | None
) -> tuple[str, str, str, str, str | None]:
    if override is not None:
        v_name, v_rule, sev, outcome, op_id = override
        if v_name in ADMISSION_RULES_V2 and v_rule in ADMISSION_RULES_V2[v_name]:
            return v_name, v_rule, sev, outcome, op_id
    if rule in ADMISSION_RULES_V2["selection"]:
        return ("selection", rule, "ERROR", "INDETERMINATE", None)
    mapped = _V2_BLOCKED_RULE_MAP.get(rule)
    if mapped is not None:
        return (*mapped, None)
    if rule in ADMISSION_RULES_V2["plan-ref"]:
        return ("plan-ref", rule, "ERROR", "INDETERMINATE", None)
    return ("plan-ref", "validator-error", "ERROR", "INDETERMINATE", None)


def _record_admission_attempt(
    paths: WorkflowArtifactPaths,
    *,
    run_id: str,
    plan_ref: PlanRef | None,
    attempt: Mapping[str, object] | None,
    status: str,
    deadline: float | None,
    managed_binding: ManagedAdmissionBinding | None = None,
) -> None:
    """Durable controller barrier; a failed write is never a persisted attempt."""
    write_admission_record(
        paths.admission,
        run_id=run_id,
        plan_ref=plan_ref,
        attempt=attempt,
        status=status,
        managed_binding=managed_binding,
        deadline=deadline,
    )


def _blocked_plan_request(
    *,
    run_id: str,
    task: str | None,
    rule: str,
    base_dir: Path | None,
    deadline: float | None,
    managed_binding: ManagedAdmissionBinding | None = None,
    attempt_kind: str = "EXPLICIT_INPUT",
    v2_diagnostic: tuple[str, str, str, str, str | None] | None = None,
    candidate_sha256: str | None = None,
    bundle_sha256: str | None = None,
) -> tuple[int, FlowState | None]:
    paths = workflow_artifact_paths(run_id, base_dir=base_dir)
    if managed_binding is not None:
        v_name, v_rule, severity, validation, op_id = _v2_blocked_diagnostic(rule, v2_diagnostic)
        both_hashes = candidate_sha256 is not None and bundle_sha256 is not None
        attempt: dict[str, object] = {
            "dispatch_kind": attempt_kind,
            "validation": validation,
            "diagnostics": [{"validator": v_name, "rule": v_rule, "severity": severity, "line": None}],
            "source_sha256": None,
            "candidate_sha256": candidate_sha256 if both_hashes else None,
            "promoted_sha256": None,
            "route": "BLOCKED",
            "input_revision": managed_binding.base_revision,
            "output_revision": None,
            "operation_id": op_id if (both_hashes or attempt_kind != "ACQUISITION") else None,
            "bundle_sha256": bundle_sha256 if both_hashes else None,
        }
    else:
        # I02 spec: the persisted validator/rule vocabulary is closed, and a rule
        # outside it must be recorded as `validator-error` rather than silently
        # dropped. This mattered in practice -- `conflict` and
        # `admission-without-coder` are controller-shape refusals with no schema
        # entry, and passing them through made `write_admission_record` reject the
        # whole record, so a refused run left no durable trace at all. The exact
        # reason still reaches the operator: it is carried in `blocked_reason` below,
        # which is free text, while the closed field keeps a value the schema accepts.
        recorded_rule = rule if rule in _PERSISTED_PLAN_REF_RULES else "validator-error"
        attempt = {
            "dispatch_kind": "EXPLICIT_INPUT",
            "validation": "INDETERMINATE",
            "diagnostics": [{"validator": "plan-ref", "rule": recorded_rule, "severity": "ERROR", "line": None}],
            "source_sha256": None,
            "candidate_sha256": None,
            "promoted_sha256": None,
            "route": "BLOCKED",
        }
    print(f"fa workflow: invalid plan reference: {rule}", file=sys.stderr)
    try:
        _record_admission_attempt(
            paths,
            run_id=run_id,
            plan_ref=None,
            attempt=attempt,
            status="BLOCKED",
            deadline=deadline,
            managed_binding=managed_binding,
        )
    except (OSError, ValueError) as error:
        reason = error.rule if isinstance(error, AdmissionIOError) else "append-failed"
        print(f"fa workflow: admission storage error: {reason}", file=sys.stderr)
    state = FlowState(
        run_id=run_id,
        task=task or "",
        status="FAILED",
        active_role="workflow",
        active_plan_id=run_id,
        active_plan_version=1,
        last_actor="workflow",
        last_transition_reason="explicit plan admission blocked",
        last_route_decision="blocked",
        blocked_reason=f"plan-ref/{rule}",
        judged=False,
    )
    try:
        write_flow_state(paths.flow_state, state)
    except (OSError, ValueError):
        print("fa workflow: blocked flow storage error: append-failed", file=sys.stderr)
        return 2, None
    return 2, state


def _resolve_admitted_plan(
    *,
    roles: list[str],
    workspace: Path,
    plan_path: Path | None,
    admission_snapshot: PlanSnapshot | None,
    acquisition: AcquisitionSubstrate | None,
) -> tuple[PlanSnapshot | None, Path | None]:
    """Resolve the one plan this run is bound to, from exactly one substrate.

    Two inputs, never both. Acquisition supplies bytes it already read through a
    pinned view (S5P1 STEP2); the CLI supplies a host path. Accepting both would
    make this function pick a favourite between two plans at the one place where
    the choice decides what a coder is bound to.

    Extracted from ``run_workflow`` because that function is already at its
    complexity ceiling and this is a self-contained closed decision.
    """
    if admission_snapshot is not None:
        if plan_path is not None:
            raise PlanRefError("conflict")
        if not isinstance(admission_snapshot, PlanSnapshot):
            raise PlanRefError("unreadable")
        if "coder" not in roles:
            # A snapshot bounds what a coder may write against. With no coder it
            # constrains nothing, so accepting it would silently discard the
            # caller's stated authority instead of reporting the mismatch.
            raise PlanRefError("admission-without-coder")
        return admission_snapshot, plan_path
    # An acquisition run is the one shape where a coder-bearing request has no
    # plan at entry: the plan cannot exist until the planner the same run
    # dispatches has chosen one. Guarded by `acquisition is not None` so every
    # other caller keeps the plain presence check.
    if acquisition is None:
        _require_plan_for_coder(roles, plan_path)
    elif roles[:1] != ["planner"]:
        # A plan acquired inside the run can only be owned by a planner that runs
        # first; a coder before the planner would have nothing to code against, and
        # claiming otherwise would be an admission without an owner.
        raise PlanRefError("admission-without-planner")
    if plan_path is None:
        return None, None
    if not isinstance(plan_path, Path):
        raise PlanRefError("unreadable")
    snapshot = read_plan_snapshot(workspace, plan_path)
    return snapshot, workspace / snapshot.ref.workspace_relative_path


def run_workflow(
    *,
    roles: list[str],
    task: str | None,
    per_role_task: Mapping[str, str | None],
    mode: str,
    max_repairs: int | None,
    max_replans: int | None,
    run_id: str,
    config: Path,
    workspace: Path,
    max_turns: int,
    output_mode: str = "console",
    run_stage_fn: Callable[..., int],
    transport: Transport | None = None,
    secrets: Mapping[str, str] | None = None,
    session_context: SessionContext | None = None,
    run_context: RunContext | None = None,
    session_db: SessionDatabase | None = None,
    deadline_mono: float | None = None,
    inject_overrides: Mapping[str, str] | None = None,
    plan_path: Path | None = None,
    plan_publisher: CandidatePlanPublisher | None = None,
    managed_execution: ManagedExecution | None = None,
    admission_snapshot: PlanSnapshot | None = None,
    acquisition: AcquisitionSubstrate | AcquisitionSubstrateRequest | None = None,
    initial_planner_context: str = "",
) -> tuple[int, FlowState | None]:
    """Run the workflow pipeline, pinning an acquisition view when asked.

    ``acquisition=None`` is the whole public contract of every other caller; the
    tool-side entry passes ``acquisition=AcquisitionSubstrateRequest()`` and this
    function then owns the view's lifetime.
    """

    def _bound(
        substrate: AcquisitionSubstrate | None,
        *,
        binding: ManagedAdmissionBinding | None,
    ) -> tuple[int, FlowState | None]:
        return _run_workflow_bound(
            roles=roles,
            task=task,
            per_role_task=per_role_task,
            mode=mode,
            max_repairs=max_repairs,
            max_replans=max_replans,
            run_id=run_id,
            config=config,
            workspace=workspace,
            max_turns=max_turns,
            output_mode=output_mode,
            run_stage_fn=run_stage_fn,
            transport=transport,
            secrets=secrets,
            session_context=session_context,
            run_context=run_context,
            session_db=session_db,
            deadline_mono=deadline_mono,
            inject_overrides=inject_overrides,
            plan_path=plan_path,
            plan_publisher=plan_publisher,
            managed_execution=managed_execution,
            admission_snapshot=admission_snapshot,
            acquisition=substrate,
            admission_binding=binding,
            initial_planner_context=initial_planner_context,
        )

    admission_binding = _managed_admission_binding(managed_execution, run_id=run_id)
    if isinstance(acquisition, AcquisitionSubstrateRequest):
        # Pin here, inside the run, so `ctx.managed_execution` is this run's own
        # binding -- the child's after a HANDOFF, never the parent's before it.
        ctx = WorkflowContext(
            run_id=run_id,
            base_task=task,
            per_role_task=per_role_task,
            artifact_paths=workflow_artifact_paths(
                run_id, base_dir=run_context.run_log_dir if run_context is not None else None
            ),
            config=config,
            workspace=workspace,
            max_turns=max_turns,
            output_mode=output_mode,
            managed_execution=managed_execution,
            deadline_mono=deadline_mono,
            admission_binding=admission_binding,
        )
        with _pinned_acquisition_substrate(ctx) as substrate:
            if substrate is None:
                # No view means no acquisition: refuse before any stage, and let the
                # refusal be recorded like every other unreachable-plan case.
                return _blocked_plan_request(
                    run_id=run_id,
                    task=task,
                    rule="acquisition-unavailable",
                    base_dir=ctx.artifact_paths.base_dir,
                    deadline=deadline_mono,
                    managed_binding=admission_binding,
                    attempt_kind="ACQUISITION" if admission_binding is not None else "EXPLICIT_INPUT",
                    v2_diagnostic=("workspace", "backend-unavailable", "ERROR", "INDETERMINATE", None),
                )
            return _bound(
                replace(
                    substrate,
                    project_slug=acquisition.project_slug,
                    dispositions=acquisition.dispositions,
                ),
                binding=admission_binding,
            )
    if acquisition is None or isinstance(acquisition, AcquisitionSubstrate):
        return _bound(acquisition, binding=admission_binding)
    raise PlanRefError("unreadable")


def _initialize_admission_record(ctx: WorkflowContext) -> bool:
    """Write the initial ACQUIRING admission barrier before stage dispatch."""
    if ctx.admission is not None:
        try:
            _record_admission_attempt(
                ctx.artifact_paths,
                run_id=ctx.run_id,
                plan_ref=ctx.admission.snapshot.ref,
                attempt=None,
                status="ACQUIRING",
                deadline=ctx.deadline_mono,
                managed_binding=ctx.admission_binding,
            )
            return True
        except (OSError, ValueError) as error:
            _admission_storage_failure(ctx, error)
            return False
    if ctx.acquisition is not None and ctx.admission_binding is not None:
        try:
            _record_admission_attempt(
                ctx.artifact_paths,
                run_id=ctx.run_id,
                plan_ref=None,
                attempt=None,
                status="ACQUIRING",
                deadline=ctx.deadline_mono,
                managed_binding=ctx.admission_binding,
            )
            return True
        except (OSError, ValueError) as error:
            rule = error.rule if isinstance(error, AdmissionIOError) else "append-failed"
            print(f"fa workflow: admission storage error: {rule}", file=sys.stderr)
            return False
    return True


def _run_workflow_bound(
    *,
    roles: list[str],
    task: str | None,
    per_role_task: Mapping[str, str | None],
    mode: str,
    max_repairs: int | None,
    max_replans: int | None,
    run_id: str,
    config: Path,
    workspace: Path,
    max_turns: int,
    output_mode: str,
    run_stage_fn: Callable[..., int],
    transport: Transport | None,
    secrets: Mapping[str, str] | None,
    session_context: SessionContext | None,
    run_context: RunContext | None,
    session_db: SessionDatabase | None,
    deadline_mono: float | None,
    inject_overrides: Mapping[str, str] | None,
    plan_path: Path | None,
    plan_publisher: CandidatePlanPublisher | None,
    managed_execution: ManagedExecution | None,
    admission_snapshot: PlanSnapshot | None,
    acquisition: AcquisitionSubstrate | None,
    admission_binding: ManagedAdmissionBinding | None = None,
    initial_planner_context: str = "",
) -> tuple[int, FlowState | None]:
    """The workflow body, with a resolved acquisition substrate.

    Returns ``(exit_code, terminal_state)`` where ``terminal_state`` may be
    ``None`` if the artifact was missing or corrupt.

    ``deadline_mono`` (S4b/RK6) is an absolute ``time.monotonic()`` instant
    after which no NEW stage is dispatched. ``None`` — the default, and what
    ``_cmd_workflow`` passes — means no deadline, so the CLI path is unchanged.
    On expiry the pipeline writes a terminal ``FAILED`` FlowState carrying
    ``DEADLINE_REASON_MARKER``, exports its aggregate row as usual, and returns
    ``WORKFLOW_DEADLINE_EXIT_CODE``; it does not raise.
    """
    _wf_start_mono = time.monotonic()
    try:
        request = _validate_workflow_request(
            roles=roles,
            mode=mode,
            max_repairs=max_repairs,
            max_replans=max_replans,
            run_id=run_id,
            task=task,
            per_role_task=per_role_task,
            inject_overrides=inject_overrides,
            workspace=workspace,
            run_context=run_context,
        )
    except WorkflowRequestError as error:
        print(f"fa workflow: {error}", file=sys.stderr)
        return 2, None
    roles = _ensure_eval_after_coder(list(request.roles))
    max_repairs, max_replans = request.max_repairs, request.max_replans

    effective_binding = (
        admission_binding
        if admission_binding is not None
        else _managed_admission_binding(managed_execution, run_id=run_id)
    )
    project_hint = acquisition.project_slug if acquisition is not None else None
    dispositions = acquisition.dispositions if acquisition is not None else ()
    try:
        snapshot, plan_path = _resolve_admitted_plan(
            roles=roles,
            workspace=workspace,
            plan_path=plan_path,
            admission_snapshot=admission_snapshot,
            acquisition=acquisition,
        )
    except PlanRefError as error:
        return _blocked_plan_request(
            run_id=run_id,
            task=task,
            rule=error.rule,
            base_dir=run_context.run_log_dir if run_context is not None else None,
            deadline=deadline_mono,
            managed_binding=effective_binding,
        )

    artifact_paths = workflow_artifact_paths(
        run_id,
        base_dir=run_context.run_log_dir if run_context is not None else None,
    )
    try:
        artifact_paths.base_dir.mkdir(parents=True, exist_ok=True)
        _persist_flow_state(
            artifact_paths.flow_state,
            FlowState(
                run_id=run_id,
                task=(task or ""),
                status="PLANNING" if roles[0] == "planner" else "PLAN_READY",
                active_role=roles[0],
                active_plan_id=run_id,
                active_plan_version=1,
                last_actor="workflow",
                last_transition_reason=f"workflow initialized (mode={mode})",
            ),
        )
    except (OSError, ValueError):
        print("fa workflow: initial flow storage error: append-failed", file=sys.stderr)
        return 2, None

    ctx = WorkflowContext(
        run_id=run_id,
        base_task=task,
        per_role_task=per_role_task,
        artifact_paths=artifact_paths,
        config=config,
        workspace=workspace,
        max_turns=max_turns,
        output_mode=output_mode,
        transport=transport,
        secrets=secrets,
        session_context=session_context,
        run_context=run_context,
        session_db=session_db,
        deadline_mono=deadline_mono,
        inject_overrides=dict(inject_overrides or {}),
        project_hint=project_hint,
        dispositions=dispositions,
        plan_path=plan_path,
        plan_publisher=plan_publisher,
        managed_execution=managed_execution,
        # The managed read-back is bound only where a managed execution exists.
        # Host mode keeps its `.fa/admission` read; nothing here is a fallback,
        # the two are different substrates and each run picks one at composition.
        managed_candidate_reader=stage_candidate_reader,
        replans_allowed=max_replans,
        acquisition=acquisition,
        admission_binding=effective_binding,
        managed_plan_ref=None if snapshot is None else snapshot.ref,
        verify_gate_mode=_gate_mode(),
        initial_planner_slot=_InitialPlannerContextSlot(text=initial_planner_context),
        admission=(
            _WorkflowAdmission(
                snapshot,
                "planner" in roles,
                max_replans,
                snapshot_backed=admission_snapshot is not None,
            )
            if snapshot is not None and "coder" in roles
            else None
        ),
    )
    try:
        if _deadline_exceeded(ctx):
            _write_deadline_state(ctx, roles[0], progress=WorkflowProgress())
            return WORKFLOW_DEADLINE_EXIT_CODE, read_back_terminal_state(artifact_paths.flow_state, run_id)
        if not _initialize_admission_record(ctx):
            return _admission_exit_code(ctx), read_back_terminal_state(artifact_paths.flow_state, run_id)
        label = _render_mode_label(mode, max_repairs=max_repairs, max_replans=max_replans)
        print(f"fa workflow: run_id={run_id} mode={label} roles={'→'.join(roles)}", file=sys.stderr)
        if mode == "adaptive":
            result_code = _run_adaptive(ctx, roles, max_repairs, max_replans, run_stage_fn)
        else:
            result_code = _run_linear(ctx, roles, run_stage_fn)
    except _WorkflowStorageError:
        print("fa workflow: flow storage error: append-failed", file=sys.stderr)
        if ctx.admission is None:
            return 2, None
        if ctx.admission.block_exit_code == WORKFLOW_DEADLINE_EXIT_CODE:
            return WORKFLOW_DEADLINE_EXIT_CODE, None
        # Return only a receipt actually persisted by this failure handler, never
        # a stale CODING/DONE/FAILED artifact left by an earlier write or invocation.
        return 2, _admission_failed(ctx, "artifact-io/append-failed")

    terminal_state = read_back_terminal_state(artifact_paths.flow_state, run_id)
    exit_code = workflow_exit_code(result_code, terminal_state)

    # Best-effort global_history export
    try:
        from fa.inner_loop.coder_loop import SessionOutcome as _SessionOutcome
        from fa.inner_loop.global_history import export_session_to_global_history
        from fa.inner_loop.state import EventLog as _EventLog
        from fa.providers import load_models_config_from_path

        session_dir = fa_session_log_root() / run_id
        log_path = session_dir / "events.jsonl"
        workflow_log = _EventLog(
            log_path,
            run_id=run_id,
            session_db=session_db,
            session_id=session_context.session_id if session_context is not None else "",
        )
        _fallback_stop_reason = "workflow_complete" if result_code == 0 else "workflow_failed"
        _stop_reason = (
            WORKFLOW_STATUS_TO_STOP_REASON.get(terminal_state.status, _fallback_stop_reason)
            if terminal_state is not None
            else _fallback_stop_reason
        )
        aggregate_outcome = _SessionOutcome(
            exit_code=exit_code,
            stop_reason=_stop_reason,
            turns=0,
            final_text="",
            tool_results=(),
        )
        _models = load_models_config_from_path(config.expanduser().resolve(), require_api_keys=False)
        _last_role = roles[-1] if roles else "coder"
        _last_chain = _models.roles.get(_last_role)
        _last_model = _last_chain.name if _last_chain else ""
        _last_family = _last_chain.family if _last_chain else ""

        export_session_to_global_history(
            run_id=run_id,
            outcome=aggregate_outcome,
            log=workflow_log,
            role="→".join(roles),
            model=_last_model,
            family=_last_family,
            workspace_root=workspace,
            duration_ms=int((time.monotonic() - _wf_start_mono) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 — best-effort, never crash workflow
        logger.warning("workflow global_history export failed for %s: %s", run_id, exc)

    return exit_code, terminal_state


__all__ = [
    "DEADLINE_REASON_MARKER",
    "DEFAULT_MAX_REPAIRS",
    "DEFAULT_MAX_REPLANS",
    "EVAL_CLAIM_DETAIL_MAX_CHARS",
    "EVAL_DIFF_MAX_CHARS",
    "EVAL_DOC_PATHS",
    "EVAL_VERDICT_TO_TERMINAL_STATUS",
    "EVAL_VERIFICATION_MAX_CHARS",
    "MAX_REPAIRS_CEILING",
    "MAX_REPLANS_CEILING",
    "WORKFLOW_DEADLINE_EXIT_CODE",
    "WORKFLOW_MODES",
    "WORKFLOW_STAGE_ROLES",
    "WORKFLOW_STATUS_TO_STOP_REASON",
    "AcquisitionSubstrate",
    "AcquisitionSubstrateRequest",
    "BaselineCapture",
    "StageResult",
    "WorkflowArtifactPaths",
    "WorkflowContext",
    "WorkflowProgress",
    "WorkflowRequestError",
    "build_eval_report",
    "capture_baseline",
    "emit_eval_report",
    "eval_system_prompt_extra",
    "load_verify_baseline",
    "read_back_terminal_state",
    "run_workflow",
    "slugify_task",
    "status_for_role",
    "terminal_status_without_eval",
    "validate_slice_ids",
    "workflow_artifact_paths",
    "workflow_exit_code",
    "write_verification",
]
