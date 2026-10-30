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
import json
import logging
import os
import re
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from fa.inner_loop.admission_schema import ADMISSION_RULES
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.injections import INJECTION_MODES, INJECTION_SPECS, resolve_injection_modes
from fa.inner_loop.plan_admission import (
    PlanRef,
    PlanRefError,
    PlanSnapshot,
    _require_plan_for_coder,
    read_plan_snapshot,
)
from fa.inner_loop.plan_ids import (
    PlanDiagnostic,
    PlanIds,
    canonical_slice_id,
    extract_plan_id,
    extract_plan_ids,
    precheck,
)
from fa.inner_loop.plan_promotion import CandidatePlanPublisher, PlanPromotionError, seed_plan_candidate
from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchError, PlannerDispatchKind
from fa.inner_loop.prompt import ADVERSARIAL_EVAL_STANCE_PREAMBLE
from fa.inner_loop.slice_verification import (
    TAIL_LIMIT,
    CommandOutcome,
    CommandResult,
    NodeidCapture,
    PlanVerification,
    SliceVerdict,
    SliceVerification,
    _gate_mode,
    capture_test_nodeids,
    validate_kill_directives,
    verify_plan,
)
from fa.inner_loop.workflow_artifacts import (
    AdmissionIOError,
    EvalReport,
    FlowState,
    FlowStatus,
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
    baseline: Literal["NOT_CAPTURED", "CAPTURED", "FAILED"] = "NOT_CAPTURED"
    admitted: bool = False
    failure: str | None = None


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
    # CT77c: resolved once at workflow start so one run cannot switch between
    # observe/enforce if the operator edits config while a stage is in flight.
    verify_gate_mode: str = "observe"
    admission: _WorkflowAdmission | None = None
    # Managed candidate promotion is supplied only by the execution composition.
    # None is a fail-closed boundary; the controller has no host-path writer fallback.
    plan_publisher: CandidatePlanPublisher | None = None

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


def _capture_nodeids_by_slice(
    plan_ids: PlanIds,
    *,
    root: Path,
    deadline: float | None = None,
) -> BaselineCapture:
    """Capture each slice's own TESTS set so regression evidence stays attributed."""
    nodeids_by_slice: dict[str, Mapping[str, bool] | None] = {}
    captures: dict[str, NodeidCapture] = {}
    errors: list[str] = []
    for record in plan_ids.slice_records:
        try:
            capture = capture_test_nodeids(record.test_paths, root=root, deadline=deadline)
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
) -> BaselineCapture:
    """Capture and write the one permitted T0 snapshot before coder dispatch (CT85/86)."""
    captured = _capture_nodeids_by_slice(plan_ids, root=root, deadline=deadline)
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


def _verification_attempt_payload(
    verification: PlanVerification,
    *,
    mode: str,
    repair_round: int,
) -> dict[str, object]:
    return {
        "mode": mode,
        "repair_round": repair_round,
        "blocking": verification.blocking,
        "plan_commands": [_command_result_payload(result) for result in verification.plan_command_results],
        "slices": [_slice_verification_payload(result) for result in verification.slice_verifications],
        "errors": list(verification.errors),
    }


def write_verification(
    path: Path,
    verification: PlanVerification,
    *,
    run_id: str,
    mode: str,
    repair_round: int,
    plan_ref: PlanRef | None = None,
    deadline: float | None = None,
) -> None:
    """Append typed attempt evidence with the established private locked atomic IO."""
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
            attempt = _verification_attempt_payload(verification, mode=mode, repair_round=repair_round)
            if plan_ref is not None:
                attempt["plan_ref"] = asdict(plan_ref)
            attempts.append(attempt)
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
"""Cap on detailed deterministic verification evidence sent to the evaluator."""

EVAL_GIT_TIMEOUT_SECONDS: Final = 15
"""Per-invocation cap on the advisory git calls.

A hung ``git`` must not silently consume the workflow deadline; on timeout the
section is omitted and the run continues.
"""

EVAL_DOC_PATHS: Final = ("knowledge/adr/DIGEST.md", "knowledge/adr/README.md")
"""Repo docs offered to the judge as PATHS, not pasted bodies.

Eval has ``fs_read_file``; pasting bodies would burn context on documents it
may not need. Only paths that exist are listed, so a moved doc drops out
rather than sending the judge to a dead reference.
"""


def _git_output(args: list[str], cwd: Path, runner: Callable[..., object] | None = None) -> str | None:
    """Run one advisory git command; ``None`` when it could not be answered.

    Deliberately NOT ``fa.hygiene.pr_intent._run_git``: that helper passes
    ``check=True`` and raises on a non-zero exit. This input is advisory, so a
    workspace that is not a git repo, a detached HEAD, or a missing git binary
    must degrade to "no diff available" rather than take the run down. Every
    failure mode collapses to ``None``.
    """
    # Local import: keeps subprocess off this module's import surface.
    import subprocess

    run = runner if runner is not None else subprocess.run
    try:
        # Fixed "git" argv, list form, no shell.
        result = run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=EVAL_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        # FileNotFoundError (git absent), TimeoutExpired, bad cwd -- all advisory.
        logger.warning("workflow: advisory `git %s` unavailable; continuing", " ".join(args))
        return None
    if getattr(result, "returncode", 1) != 0:
        return None
    return str(getattr(result, "stdout", "") or "")


def _verification_evidence_lines(
    verification: PlanVerification,
    *,
    mode: str,
    repair_round: int,
    artifact_path: Path,
) -> tuple[str, ...]:
    """Render the current attempt's authoritative facts for the evaluator."""
    lines = [
        f"Harness verify gate (mode={mode}, repair_round={repair_round}, blocking={verification.blocking}):",
        f"Detailed artifact: {artifact_path}",
    ]
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
    runner: Callable[..., object] | None = None,
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

    Every section degrades independently. A missing plan, a workspace that is
    not a git repo, or an absent git binary each drop their own section and
    leave the rest intact; none raises. Sections that would be empty are
    OMITTED rather than emitted as a bare heading, because an empty heading
    reads as "checked, found nothing" when the truth is "never looked".

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
            )
        )

    stat = _git_output(["diff", "HEAD", "--stat"], ctx.workspace, runner)
    diff = _git_output(["diff", "HEAD"], ctx.workspace, runner)
    status = _git_output(["status", "--porcelain"], ctx.workspace, runner)

    if stat is None and diff is None and status is None:
        lines.append("Changed files: unavailable (not a git repository, or git could not be run).")
    else:
        # `git diff HEAD` covers staged AND unstaged work, so a coder that
        # staged everything and one that staged nothing yield the same
        # evidence. It CANNOT see untracked files, which is why porcelain
        # status is included: a slice whose entire contribution is a new file
        # would otherwise show an empty diff and could be passed on nothing.
        untracked = tuple(line[3:] for line in (status or "").splitlines() if line.startswith("??"))
        if untracked:
            lines.append(f"New untracked files ({len(untracked)}): {', '.join(untracked)}")
            lines.append("These are NOT in the diff below; read them with fs_read_file before judging.")
        if stat:
            lines.append(f"Diff stat (git diff HEAD):\n{stat.rstrip()}")
        if diff:
            body = diff
            if len(body) > EVAL_DIFF_MAX_CHARS:
                body = (
                    body[:EVAL_DIFF_MAX_CHARS] + f"\n[diff truncated at {EVAL_DIFF_MAX_CHARS} chars of {len(diff)}"
                    " -- read the remaining files with fs_read_file]"
                )
            lines.append(f"Diff (git diff HEAD):\n{body}")
        elif not untracked:
            # Explicit, not silence: "nothing changed" is itself a finding
            # worth a FAIL, and an absent section reads as "diff unavailable".
            lines.append("Changed files: NONE. `git diff HEAD` is empty and there are no untracked files.")

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
    if dispatch is None or dispatch.kind == PlannerDispatchKind.ORDINARY_PLANNING:
        return False
    return not sink or sink[-1].exit_code != 0 or not {"fs_write_file", "pr_prepare"}.isdisjoint(sink[-1].failed_tools)


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


def _stage_task(
    ctx: WorkflowContext, role: str, verification: PlanVerification | None, repair_round: int
) -> str | None:
    # S13: the judge is handed the contract and the evidence. Eval only --
    # the coder and planner already have the plan by other means, and a diff
    # of the coder's own work is not input to writing it.
    stage_task = ctx.task_for(role)
    if role == "eval":
        evidence = _eval_evidence_block(ctx, verification=verification, repair_round=repair_round)
        if evidence:
            # Appended, never substituted: the task states what to judge and
            # the block states what to judge it against.
            stage_task = f"{stage_task}\n\n{evidence}" if stage_task else evidence

    return stage_task


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
    dispatch = _stage_planner_dispatch(ctx, role, planner_dispatch)
    progress = _admission_progress(ctx, progress)
    if _deadline_exceeded(ctx):
        _write_deadline_state(ctx, role, progress=progress)
        return StageResult(role=role, exit_code=WORKFLOW_DEADLINE_EXIT_CODE)
    if role == "coder" and not _admit_plan(ctx, progress, run_stage_fn):
        return StageResult(role=role, exit_code=_admission_exit_code(ctx))
    progress = _admission_progress(ctx, progress)

    _announce_stage(ctx, role, progress, transition_reason)
    stage_task = _stage_task(ctx, role, prior_verification, progress.repair_round)

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
            capture_baseline(
                ctx.artifact_paths.verify_baseline,
                plan_ids_for_stage,
                root=ctx.workspace,
                run_id=ctx.run_id,
                deadline=ctx.deadline_mono,
            )
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
    code = run_stage_fn(
        stage_args,
        transport=ctx.transport,
        secrets=ctx.secrets,
        outcome_sink=sink,
        **dispatch_kwargs,
    )
    if _scoped_stage_failed(dispatch, sink):
        return StageResult(role=role, exit_code=code or 2)
    report: EvalReport | None = None
    verification: PlanVerification | None = None
    if role == "coder" and code == 0:
        plan_ids = plan_ids_for_stage or PlanIds()
        baseline = baseline_capture or BaselineCapture(nodeids_by_slice={})
        now = _capture_nodeids_by_slice(plan_ids, root=ctx.workspace, deadline=ctx.deadline_mono)
        try:
            verification = verify_plan(
                plan_ids,
                root=ctx.workspace,
                baseline_by_slice=baseline.nodeids_by_slice,
                now_by_slice=now.nodeids_by_slice,
                deadline=ctx.deadline_mono,
            )
        except Exception as error:  # Uncertainty is a recorded ERROR, never a pass.
            logger.exception("workflow verification failed unexpectedly (run=%s)", ctx.run_id)
            verification = PlanVerification(
                plan_command_results=(),
                slice_verifications=(),
                errors=(f"verify_plan raised {type(error).__name__}: {error}",),
            )
        capture_errors = tuple(
            error
            for error in (
                *((plan_read_error,) if plan_read_error else ()),
                *baseline.errors,
                *now.errors,
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
        _eval_independence = _load_eval_independence(ctx)
        # S12/§24 D-1: build -> adjust -> write, exactly one write. Calling
        # emit_eval_report here and rewriting afterwards would persist a report
        # that contradicts the routing decision for the window in between.
        report = build_eval_report(
            sink[-1].final_text,
            run_id=ctx.run_id,
            # S12a: the plan's declared ID when one was supplied, else run_id.
            plan_id=ctx.plan_identity(),
            plan_version=progress.plan_version,
            eval_independence=_eval_independence,
        )
        report, _slice_warnings = validate_slice_ids(
            report,
            ctx.plan_text(),
            plan_ids=ctx.admission.snapshot.ids if ctx.admission is not None else None,
        )
        for _warning in _slice_warnings:
            logger.warning("workflow eval-report: %s (run=%s)", _warning, ctx.run_id)
            print(f"fa workflow: {_warning}", file=sys.stderr)
        _write_stage_eval_report(ctx, report)
    return StageResult(role=role, exit_code=code, eval_report=report, verification=verification)


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


def _run_initial_roles(
    ctx: WorkflowContext,
    roles: list[str],
    run_stage_fn: Callable[..., int],
) -> tuple[int, int, EvalReport | None, PlanVerification | None]:
    """Run the configured initial role sequence, carrying facts from coder to eval."""
    progress = WorkflowProgress()
    eval_report: EvalReport | None = None
    verification: PlanVerification | None = None
    n_stages = 0
    for index, role in enumerate(roles):
        n_stages += 1
        print(f"\nfa workflow ─ stage {index + 1}/{len(roles)}: {role}", file=sys.stderr)
        result = _run_stage(
            ctx,
            role,
            fresh=index == 0,
            progress=progress,
            transition_reason=f"dispatching stage {index + 1}/{len(roles)}",
            run_stage_fn=run_stage_fn,
            prior_verification=verification,
        )
        if result.exit_code != 0:
            _write_stage_failure_state(ctx, role, result.exit_code, progress=progress)
            return result.exit_code, n_stages, eval_report, verification
        if role == "coder":
            verification = result.verification
        if result.eval_report is not None:
            eval_report = result.eval_report
    return 0, n_stages, eval_report, verification


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
) -> tuple[int, int, EvalReport, PlanVerification | None]:
    """Run one canonical coder/eval or planner/coder/eval adaptive round."""
    for role in stage_roles:
        result = _run_stage(
            ctx,
            role,
            fresh=False,
            progress=progress,
            transition_reason=f"{reason_prefix}: canonical {role}",
            run_stage_fn=run_stage_fn,
            prior_verification=verification,
        )
        n_stages += 1
        if result.exit_code != 0:
            _write_stage_failure_state(ctx, role, result.exit_code, progress=progress)
            return result.exit_code, n_stages, eval_report, verification
        if role == "coder":
            verification = result.verification
        if result.eval_report is not None:
            eval_report = result.eval_report
    return 0, n_stages, eval_report, verification


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
) -> tuple[bool, int, int, WorkflowProgress, EvalReport, PlanVerification | None]:
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
        return False, 0, n_stages, progress, eval_report, verification

    progress = WorkflowProgress(
        plan_version=progress.plan_version,
        repair_round=progress.repair_round + 1,
        replan_round=progress.replan_round,
    )
    print(
        f"\nfa workflow ─ repair round {progress.repair_round}/{max_repairs} (adaptive route return_to_coder)",
        file=sys.stderr,
    )
    code, n_stages, eval_report, verification = _dispatch_adaptive_round(
        ctx,
        _canonical_loop_roles(roles, include_planner=False),
        run_stage_fn,
        progress=progress,
        n_stages=n_stages,
        eval_report=eval_report,
        verification=verification,
        reason_prefix=f"repair round {progress.repair_round}: after return_to_coder",
    )
    return code == 0, code, n_stages, progress, eval_report, verification


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
) -> tuple[bool, int, int, WorkflowProgress, EvalReport, PlanVerification | None]:
    """Use one bounded planner round, or terminate if it cannot be honored."""
    if ctx.admission is not None:
        if not _admit_plan(
            ctx,
            progress,
            run_stage_fn,
            replan=True,
            reason=f"Eval requested {eval_report.route_decision}: {eval_report.summary}",
        ):
            return False, _admission_exit_code(ctx), n_stages, progress, eval_report, verification
        progress = replace(progress, plan_version=progress.plan_version + 1, replan_round=ctx.admission.planner_calls)
        code, n_stages, eval_report, verification = _dispatch_adaptive_round(
            ctx,
            _canonical_loop_roles(roles, include_planner=False),
            run_stage_fn,
            progress=progress,
            n_stages=n_stages,
            eval_report=eval_report,
            verification=verification,
            reason_prefix="admitted eval replan",
        )
        return code == 0, code, n_stages, progress, eval_report, verification
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
        return False, 0, n_stages, progress, eval_report, verification
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
        return False, 0, n_stages, progress, eval_report, verification

    progress = WorkflowProgress(
        plan_version=progress.plan_version + 1,
        repair_round=progress.repair_round,
        replan_round=progress.replan_round + 1,
    )
    print(
        f"\nfa workflow ─ replan round {progress.replan_round}/{max_replans} (plan version {progress.plan_version})",
        file=sys.stderr,
    )
    code, n_stages, eval_report, verification = _dispatch_adaptive_round(
        ctx,
        _canonical_loop_roles(roles, include_planner=True),
        run_stage_fn,
        progress=progress,
        n_stages=n_stages,
        eval_report=eval_report,
        verification=verification,
        reason_prefix=f"replan round {progress.replan_round}: after return_to_planner",
    )
    return code == 0, code, n_stages, progress, eval_report, verification


def _run_adaptive(
    ctx: WorkflowContext,
    roles: list[str],
    max_repairs: int,
    max_replans: int,
    run_stage_fn: Callable[..., int],
) -> int:
    """Run normalized roles, evaluate every coder attempt, then route on eval plus gate facts."""
    code, n_stages, eval_report, verification = _run_initial_roles(ctx, roles, run_stage_fn)
    if code != 0:
        return code

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
            keep_going, code, n_stages, progress, eval_report, verification = _run_adaptive_repair(
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
            keep_going, code, n_stages, progress, eval_report, verification = _run_adaptive_replan(
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


def _run_linear(ctx: WorkflowContext, roles: list[str], run_stage_fn: Callable[..., int]) -> int:
    """Run every role once, evaluating after coder and enforcing verifier facts afterward."""
    eval_report: EvalReport | None = None
    verification: PlanVerification | None = None
    progress = WorkflowProgress()
    n_stages = 0
    last_role = roles[0]
    for index, role in enumerate(roles):
        n_stages += 1
        last_role = role
        print(f"\nfa workflow ─ stage {index + 1}/{len(roles)}: {role}", file=sys.stderr)
        result = _run_stage(
            ctx,
            role,
            fresh=index == 0,
            progress=progress,
            transition_reason=f"dispatching stage {index + 1}/{len(roles)}",
            run_stage_fn=run_stage_fn,
            prior_verification=verification,
        )
        if result.exit_code != 0:
            _write_stage_failure_state(ctx, role, result.exit_code, progress=progress)
            return result.exit_code
        if role == "coder":
            verification = result.verification
        if result.eval_report is not None:
            eval_report = result.eval_report

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
    """Both validators consume the same captured text/IDs; no filesystem authority."""
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


def _promote_validated_plan(
    workspace: Path,
    source: PlanSnapshot,
    validated: _PlanAdmissionValidation,
    *,
    publisher: CandidatePlanPublisher | None = None,
    deadline: float | None = None,
) -> PlanSnapshot:
    """Publish only validated bytes through the injected supervisor candidate port.

    ``workspace`` is retained for the stable workflow call signature, but is not
    opened here. A missing managed publisher is a closed refusal, never a
    fallback to host-path replacement.
    """
    del workspace
    if validated.outcome != "PASS":
        raise PlanPromotionError("prepare-failed")
    if publisher is None:
        raise PlanPromotionError("prepare-failed")
    try:
        ref = publisher.publish_candidate(source, validated.snapshot, deadline=deadline)
    except PlanPromotionError:
        raise
    except Exception as error:  # sanitize transport/backend details into the admission schema's closed vocabulary
        code = getattr(error, "code", None)
        uncertain = code in {"DURABILITY_UNKNOWN", "CORRUPT_STATE", "EXECUTION_UNKNOWN", "TERMINALITY_UNKNOWN"}
        rule = "durability-unknown" if uncertain else "prepare-failed"
        raise PlanPromotionError(rule, replaced=uncertain) from error
    expected = PlanRef(
        source.ref.workspace_relative_path,
        source.ref.source_kind,
        validated.snapshot.ref.sha256,
    )
    if ref != expected:
        raise PlanPromotionError("hash-mismatch", replaced=True)
    return replace(validated.snapshot, ref=ref)


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


def _admission_attempt(
    ctx: WorkflowContext,
    validation: _PlanAdmissionValidation,
    *,
    kind: str,
    route: str,
    candidate: bool = False,
    promoted: PlanSnapshot | None = None,
) -> None:
    state = ctx.admission
    if state is None:
        raise RuntimeError("admission authority absent")
    _record_admission_attempt(
        ctx.artifact_paths,
        run_id=ctx.run_id,
        plan_ref=(promoted or state.snapshot).ref,
        attempt={
            "dispatch_kind": kind,
            "validation": validation.outcome,
            "diagnostics": [asdict(item) for item in validation.diagnostics],
            "source_sha256": state.snapshot.ref.sha256,
            "candidate_sha256": validation.snapshot.ref.sha256 if candidate else None,
            "promoted_sha256": promoted.ref.sha256 if promoted is not None else None,
            "route": route,
        },
        status={"RETRY": "ACQUIRING", "ADMITTED": "ADMITTED", "BLOCKED": "BLOCKED"}[route],
        deadline=ctx.deadline_mono,
    )


def _check_admission_source(ctx: WorkflowContext) -> None:
    if ctx.admission is None:
        raise RuntimeError("admission authority absent")
    source = ctx.admission.snapshot
    actual = read_plan_snapshot(ctx.workspace, Path(source.ref.workspace_relative_path))
    if actual.ref.sha256 != source.ref.sha256:
        raise PlanRefError("source-changed")


def _run_admission_repair(
    ctx: WorkflowContext,
    progress: WorkflowProgress,
    run_stage_fn: Callable[..., int],
    *,
    kind: PlannerDispatchKind,
    draft: PlanSnapshot,
    diagnostics: tuple[_AdmissionDiagnostic, ...] = (),
    reason: str = "",
) -> tuple[_PlanAdmissionValidation, PlanSnapshot | None]:
    """One reserved planner attempt; own its target through cleanup, then use only bytes."""
    if ctx.admission is None:
        raise RuntimeError("admission authority absent")
    source = ctx.admission.snapshot
    ctx.admission.candidate = None
    _check_admission_source(ctx)
    dispatch = seed_plan_candidate(ctx.workspace, source, run_id=ctx.run_id, kind=kind, draft=draft)
    if dispatch.candidate_target is None:
        raise PlannerDispatchError
    target = Path(dispatch.candidate_target)
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
            )
        except Exception as error:
            raise PlanPromotionError("prepare-failed") from error
        if result.exit_code != 0:
            raise PlanPromotionError("prepare-failed")
        candidate = read_plan_snapshot(ctx.workspace, target)
        ctx.admission.candidate = candidate
    finally:
        # Remove only the exact controller-owned leaf, never follow a replacement alias.
        # Keep progress in the immutable buffer, not in a live pathname. Cleanup precedes
        # publication so a cleanup failure cannot occur after irreversible replacement.
        with _private_artifact_directory(ctx.workspace / target.parent) as parent:
            os.unlink(target.name, dir_fd=parent)
            os.fsync(parent)
    validation = _validate_plan_admission(candidate)
    promoted = (
        _promote_validated_plan(
            ctx.workspace, source, validation, publisher=ctx.plan_publisher, deadline=ctx.deadline_mono
        )
        if validation.outcome == "PASS"
        else None
    )
    return validation, promoted


def _admission_error(
    ctx: WorkflowContext,
    error: PlanRefError | PlanPromotionError | PlannerDispatchError,
    *,
    kind: str = "EXPLICIT_INPUT",
) -> None:
    if ctx.admission is None:
        raise RuntimeError("admission authority absent")
    validator = "plan-ref" if isinstance(error, PlanRefError) else "promotion"
    rule = "scope-denied" if isinstance(error, PlannerDispatchError) else error.rule
    candidate = ctx.admission.candidate if kind != "EXPLICIT_INPUT" else None
    validation = _PlanAdmissionValidation(
        candidate or ctx.admission.snapshot, "INDETERMINATE", (_AdmissionDiagnostic(validator, rule, "ERROR"),)
    )
    try:
        _admission_attempt(ctx, validation, kind=kind, route="BLOCKED", candidate=candidate is not None)
    except (OSError, ValueError) as failure:
        _admission_storage_failure(ctx, failure)
        return
    _admission_failed(ctx, f"{validator}/{rule}")


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
    if state is None:  # Internal legacy stage fixtures; public coder entry always binds authority.
        return True
    if state.failure is not None:
        if state.block_exit_code == WORKFLOW_DEADLINE_EXIT_CODE:
            return False
        _admission_failed(ctx, state.failure)
        return False
    attempt_kind = "EXPLICIT_INPUT"
    try:
        _check_admission_source(ctx)
        if state.admitted and not replan:
            return True
        kind = PlannerDispatchKind.EVAL_REPLAN if replan else PlannerDispatchKind.ADMISSION_REPAIR
        validated = _validate_plan_admission(state.snapshot)
        promoted = None
        candidate = False
        if replan and validated.outcome != "PASS":
            replan = False
        if replan:
            # Q67(a): canonical remains ADMITTED; no invented pre-dispatch FAIL/RETRY.
            _record_admission_attempt(
                ctx.artifact_paths,
                run_id=ctx.run_id,
                plan_ref=state.snapshot.ref,
                attempt=None,
                status="ADMITTED",
                deadline=ctx.deadline_mono,
            )
            state.admitted = False
        while True:
            can_retry = (
                state.planner_allowed and state.planner_calls < state.planner_limit and not _deadline_exceeded(ctx)
            )
            if not replan:
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
                    kind=kind.value if candidate else "EXPLICIT_INPUT",
                    route=route,
                    candidate=candidate,
                    promoted=promoted,
                )
                if route == "ADMITTED":
                    state.plan_version += int(kind == PlannerDispatchKind.EVAL_REPLAN)
                    state.snapshot = promoted or validated.snapshot
                    state.admitted = True
                    return True
                if route == "BLOCKED":
                    _admission_failed(ctx, "validation-or-planner-budget")
                    return False
            elif not can_retry:
                _admission_attempt(ctx, validated, kind="EXPLICIT_INPUT", route="BLOCKED")
                _admission_failed(ctx, "planner-budget" if state.planner_allowed else "planner-unavailable")
                return False
            attempt_kind = kind.value
            state.planner_calls += 1  # Reserve even when seeding/provider/writer/publication fails.
            validated, promoted = _run_admission_repair(
                ctx,
                progress,
                run_stage_fn,
                kind=kind,
                draft=validated.snapshot,
                diagnostics=validated.diagnostics,
                reason=reason,
            )
            candidate = True
            replan = False
    except (PlanRefError, PlanPromotionError, PlannerDispatchError) as error:
        if state.block_exit_code != WORKFLOW_DEADLINE_EXIT_CODE:
            _admission_error(ctx, error, kind=attempt_kind)
    except (OSError, ValueError) as error:
        _admission_storage_failure(ctx, error)
    return False


def _record_admission_attempt(
    paths: WorkflowArtifactPaths,
    *,
    run_id: str,
    plan_ref: PlanRef | None,
    attempt: Mapping[str, object] | None,
    status: str,
    deadline: float | None,
) -> None:
    """Durable controller barrier; a failed write is never a persisted attempt."""
    write_admission_record(
        paths.admission, run_id=run_id, plan_ref=plan_ref, attempt=attempt, status=status, deadline=deadline
    )


def _blocked_plan_request(
    *, run_id: str, task: str | None, rule: str, base_dir: Path | None, deadline: float | None
) -> tuple[int, FlowState | None]:
    paths = workflow_artifact_paths(run_id, base_dir=base_dir)
    attempt: dict[str, object] = {
        "dispatch_kind": "EXPLICIT_INPUT",
        "validation": "INDETERMINATE",
        "diagnostics": [{"validator": "plan-ref", "rule": rule, "severity": "ERROR", "line": None}],
        "source_sha256": None,
        "candidate_sha256": None,
        "promoted_sha256": None,
        "route": "BLOCKED",
    }
    print(f"fa workflow: invalid plan reference: {rule}", file=sys.stderr)
    try:
        _record_admission_attempt(
            paths, run_id=run_id, plan_ref=None, attempt=attempt, status="BLOCKED", deadline=deadline
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
) -> tuple[int, FlowState | None]:
    """Run the workflow pipeline. Callable from CLI and from tools.

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

    snapshot: PlanSnapshot | None = None
    try:
        _require_plan_for_coder(roles, plan_path)
        if plan_path is not None:
            if not isinstance(plan_path, Path):
                raise PlanRefError("unreadable")
            snapshot = read_plan_snapshot(workspace, plan_path)
            plan_path = workspace / snapshot.ref.workspace_relative_path
    except PlanRefError as error:
        return _blocked_plan_request(
            run_id=run_id,
            task=task,
            rule=error.rule,
            base_dir=run_context.run_log_dir if run_context is not None else None,
            deadline=deadline_mono,
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
        plan_path=plan_path,
        plan_publisher=plan_publisher,
        verify_gate_mode=_gate_mode(),
        admission=(
            _WorkflowAdmission(snapshot, "planner" in roles, max_replans)
            if snapshot is not None and "coder" in roles
            else None
        ),
    )
    try:
        if _deadline_exceeded(ctx):
            _write_deadline_state(ctx, roles[0], progress=WorkflowProgress())
            return WORKFLOW_DEADLINE_EXIT_CODE, read_back_terminal_state(artifact_paths.flow_state, run_id)
        if ctx.admission is not None:
            try:
                _record_admission_attempt(
                    artifact_paths,
                    run_id=run_id,
                    plan_ref=ctx.admission.snapshot.ref,
                    attempt=None,
                    status="ACQUIRING",
                    deadline=deadline_mono,
                )
            except (OSError, ValueError) as error:
                _admission_storage_failure(ctx, error)
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
    "EVAL_DIFF_MAX_CHARS",
    "EVAL_DOC_PATHS",
    "EVAL_GIT_TIMEOUT_SECONDS",
    "EVAL_VERDICT_TO_TERMINAL_STATUS",
    "EVAL_VERIFICATION_MAX_CHARS",
    "MAX_REPAIRS_CEILING",
    "MAX_REPLANS_CEILING",
    "WORKFLOW_DEADLINE_EXIT_CODE",
    "WORKFLOW_MODES",
    "WORKFLOW_STAGE_ROLES",
    "WORKFLOW_STATUS_TO_STOP_REASON",
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
