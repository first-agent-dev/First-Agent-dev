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
import logging
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.prompt import ADVERSARIAL_EVAL_STANCE_PREAMBLE
from fa.inner_loop.workflow_artifacts import (
    EvalReport,
    FlowState,
    FlowStatus,
    load_flow_state,
    parse_eval_report,
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
    """Outcome of dispatching one role stage."""

    role: str
    exit_code: int
    eval_report: EvalReport | None = None


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
    )


def emit_eval_report(
    *,
    report_path: Path,
    final_text: str,
    run_id: str,
    plan_id: str,
    plan_version: int,
    eval_independence: Mapping[str, object] | None = None,
) -> EvalReport:
    """Parse the eval role's final message and persist ``eval_report.json``."""
    report = parse_eval_report(
        final_text,
        run_id=run_id,
        plan_id=plan_id,
        evaluation_id=f"{run_id}-eval",
        plan_version=plan_version,
        eval_independence=eval_independence,
    )
    write_eval_report(report_path, report)
    return report


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


# ── Stage dispatch ─────────────────────────────────────────────────────────


def _run_stage(
    ctx: WorkflowContext,
    role: str,
    *,
    fresh: bool,
    progress: WorkflowProgress,
    transition_reason: str,
    run_stage_fn: Callable[..., int],
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
    if _deadline_exceeded(ctx):
        _write_deadline_state(ctx, role, progress=progress)
        return StageResult(role=role, exit_code=WORKFLOW_DEADLINE_EXIT_CODE)

    write_flow_state(
        ctx.artifact_paths.flow_state,
        FlowState(
            run_id=ctx.run_id,
            task=str(ctx.base_task or ""),
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
    stage_kwargs: dict[str, object] = {
        "task_pos": None,
        "task": ctx.task_for(role),
        "role": role,
        "config": ctx.config,
        "workspace": ctx.workspace,
        "max_turns": ctx.max_turns,
        "run_id": ctx.run_id,
        "resume": not fresh,
        "output_mode": ctx.output_mode,
        "detail": "standard",
        "no_color": False,
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
    # ``sink`` is local to this stage and is read below for eval alone, so
    # collecting a non-eval outcome here is inert.
    code = run_stage_fn(
        stage_args,
        transport=ctx.transport,
        secrets=ctx.secrets,
        outcome_sink=sink,
    )
    report: EvalReport | None = None
    if role == "eval" and code == 0 and sink:
        try:
            from fa.providers import load_models_config_from_path

            _eval_models = load_models_config_from_path(ctx.config.expanduser().resolve(), require_api_keys=False)
            _eval_independence = _eval_independence_mapping(_eval_models)
        except (ConfigurationError, OSError):
            logger.warning(
                "workflow eval-report: could not load config for eval_independence record; omitting field (run=%s)",
                ctx.run_id,
            )
            _eval_independence = None
        report = emit_eval_report(
            report_path=ctx.artifact_paths.eval_report,
            final_text=sink[-1].final_text,
            run_id=ctx.run_id,
            plan_id=ctx.run_id,
            plan_version=progress.plan_version,
            eval_independence=_eval_independence,
        )
        print(
            f"fa workflow: eval verdict={report.verdict} "
            f"route={report.route_decision} → {ctx.artifact_paths.eval_report}",
            file=sys.stderr,
        )
    return StageResult(role=role, exit_code=code, eval_report=report)


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
    elapsed = (
        ""
        if ctx.deadline_mono is None
        else f" after {max(0.0, time.monotonic() - ctx.deadline_mono):.0f}s past deadline"
    )
    write_flow_state(
        ctx.artifact_paths.flow_state,
        FlowState(
            run_id=ctx.run_id,
            task=str(ctx.base_task or ""),
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

    write_flow_state(
        ctx.artifact_paths.flow_state,
        FlowState(
            run_id=ctx.run_id,
            task=str(ctx.base_task or ""),
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


def _write_terminal_state(
    ctx: WorkflowContext,
    *,
    last_role: str,
    eval_report: EvalReport | None,
    progress: WorkflowProgress,
    reason: str,
) -> None:
    status: FlowStatus
    route: str
    if eval_report is not None:
        status = EVAL_VERDICT_TO_TERMINAL_STATUS.get(eval_report.verdict, "FAILED")
        route = eval_report.route_decision
        blocked = eval_report.summary if eval_report.verdict == "BLOCKED" else ""
    else:
        status = "DONE"
        route = ""
        blocked = ""
    write_flow_state(
        ctx.artifact_paths.flow_state,
        FlowState(
            run_id=ctx.run_id,
            task=str(ctx.base_task or ""),
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
    return state


def _print_terminal_summary(
    ctx: WorkflowContext,
    *,
    n_stages: int,
    eval_report: EvalReport | None,
    repair_rounds_used: int,
) -> None:
    if eval_report is not None and eval_report.verdict == "PASS":
        suffix = f" after {repair_rounds_used} repair round(s)" if repair_rounds_used else ""
        print(
            f"\nfa workflow: accepted (verdict=PASS){suffix} — run_id={ctx.run_id}",
            file=sys.stderr,
        )
        return
    if eval_report is not None:
        tail = f" (repair budget {repair_rounds_used} exhausted)" if repair_rounds_used else ""
        print(
            f"\nfa workflow: {n_stages} stage(s) ran (run_id={ctx.run_id}); "
            f"eval verdict={eval_report.verdict} route={eval_report.route_decision} "
            f"— not accepted{tail}.",
            file=sys.stderr,
        )
        return
    print(
        f"\nfa workflow: all {n_stages} stage(s) completed OK (run_id={ctx.run_id})",
        file=sys.stderr,
    )


def _resolve_max_repairs(value: int | None) -> int:
    v = DEFAULT_MAX_REPAIRS if value is None else int(value)
    if v < 0:
        v = 0
    return min(v, MAX_REPAIRS_CEILING)


def _resolve_max_replans(value: int | None) -> int:
    v = DEFAULT_MAX_REPLANS if value is None else int(value)
    if v < 0:
        v = 0
    return min(v, MAX_REPLANS_CEILING)


def _render_mode_label(mode: str, *, max_repairs: int, max_replans: int) -> str:
    if mode == "adaptive":
        return f"adaptive (max repairs {max_repairs}, max replans {max_replans})"
    return mode


def _canonical_loop_roles(roles: list[str], *, include_planner: bool) -> tuple[str, ...]:
    canonical = ["planner", "coder", "eval"] if include_planner else ["coder", "eval"]
    return tuple(role for role in canonical if role in roles)


# ── Pipeline modes ─────────────────────────────────────────────────────────


def _run_initial_roles(
    ctx: WorkflowContext,
    roles: list[str],
    run_stage_fn: Callable[..., int],
) -> tuple[int, int, EvalReport | None]:
    progress = WorkflowProgress()
    eval_report: EvalReport | None = None
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
        )
        if result.exit_code != 0:
            _write_stage_failure_state(ctx, role, result.exit_code, progress=progress)
            return result.exit_code, n_stages, eval_report
        if result.eval_report is not None:
            eval_report = result.eval_report
    return 0, n_stages, eval_report


def _run_adaptive(
    ctx: WorkflowContext,
    roles: list[str],
    max_repairs: int,
    max_replans: int,
    run_stage_fn: Callable[..., int],
) -> int:
    """Run the initial role list, then normalize loops to canonical routes."""
    code, n_stages, eval_report = _run_initial_roles(ctx, roles, run_stage_fn)
    if code != 0:
        return code

    progress = WorkflowProgress()
    if eval_report is None:
        _write_terminal_state(
            ctx,
            last_role=roles[-1],
            eval_report=None,
            progress=progress,
            reason="adaptive workflow completed without eval stage",
        )
        _print_terminal_summary(ctx, n_stages=n_stages, eval_report=None, repair_rounds_used=0)
        return 0

    while True:
        if eval_report.route_decision == "return_to_coder":
            if progress.repair_round >= max_repairs:
                reason = f"repair budget exhausted ({progress.repair_round}/{max_repairs}); last route return_to_coder"
                _write_terminal_state(ctx, last_role="eval", eval_report=eval_report, progress=progress, reason=reason)
                _print_terminal_summary(
                    ctx,
                    n_stages=n_stages,
                    eval_report=eval_report,
                    repair_rounds_used=progress.repair_round,
                )
                return 0
            progress = WorkflowProgress(
                plan_version=progress.plan_version,
                repair_round=progress.repair_round + 1,
                replan_round=progress.replan_round,
            )
            print(
                f"\nfa workflow ─ repair round {progress.repair_round}/{max_repairs} (adaptive route return_to_coder)",
                file=sys.stderr,
            )
            for role in _canonical_loop_roles(roles, include_planner=False):
                result = _run_stage(
                    ctx,
                    role,
                    fresh=False,
                    progress=progress,
                    transition_reason=f"repair round {progress.repair_round}: canonical {role} after return_to_coder",
                    run_stage_fn=run_stage_fn,
                )
                n_stages += 1
                if result.exit_code != 0:
                    _write_stage_failure_state(ctx, role, result.exit_code, progress=progress)
                    return result.exit_code
                if result.eval_report is not None:
                    eval_report = result.eval_report
            continue

        if eval_report.route_decision == "return_to_planner":
            # D4: adaptive accepts a planner-less role list (e.g. coder,eval),
            # which is what the removed ``repair`` mode used to serve. Without
            # a planner there is nobody to replan, so a return_to_planner route
            # is terminal rather than a loop — the alternative would be to spin
            # the canonical loop with the planner silently filtered out by
            # _canonical_loop_roles, re-running coder→eval on an unchanged plan
            # until the replan budget drained.
            if "planner" not in roles:
                reason = (
                    f"eval routed return_to_planner but no planner role is configured "
                    f"(roles={','.join(roles)}); cannot replan"
                )
                _write_terminal_state(ctx, last_role="eval", eval_report=eval_report, progress=progress, reason=reason)
                _print_terminal_summary(
                    ctx,
                    n_stages=n_stages,
                    eval_report=eval_report,
                    repair_rounds_used=progress.repair_round,
                )
                # 0 means "the controller finished normally", not "success":
                # workflow_exit_code maps the non-DONE terminal state to 1.
                # Returning 1 here is an equivalent mutant (verified: identical
                # exit code, status, reason and stage counts), so no test can
                # distinguish them. 0 is used for consistency with every other
                # terminal branch in this function.
                return 0
            if progress.replan_round >= max_replans:
                reason = (
                    f"replan budget exhausted ({progress.replan_round}/{max_replans}); last route return_to_planner"
                )
                _write_terminal_state(ctx, last_role="eval", eval_report=eval_report, progress=progress, reason=reason)
                _print_terminal_summary(
                    ctx,
                    n_stages=n_stages,
                    eval_report=eval_report,
                    repair_rounds_used=progress.repair_round,
                )
                return 0
            progress = WorkflowProgress(
                plan_version=progress.plan_version + 1,
                repair_round=progress.repair_round,
                replan_round=progress.replan_round + 1,
            )
            print(
                f"\nfa workflow ─ replan round {progress.replan_round}/{max_replans} "
                f"(plan version {progress.plan_version})",
                file=sys.stderr,
            )
            for role in _canonical_loop_roles(roles, include_planner=True):
                result = _run_stage(
                    ctx,
                    role,
                    fresh=False,
                    progress=progress,
                    transition_reason=f"replan round {progress.replan_round}: canonical {role} after return_to_planner",
                    run_stage_fn=run_stage_fn,
                )
                n_stages += 1
                if result.exit_code != 0:
                    _write_stage_failure_state(ctx, role, result.exit_code, progress=progress)
                    return result.exit_code
                if result.eval_report is not None:
                    eval_report = result.eval_report
            continue

        reason = (
            f"eval verdict {eval_report.verdict} after {progress.repair_round} repair round(s) "
            f"and {progress.replan_round} replan round(s)"
        )
        _write_terminal_state(ctx, last_role="eval", eval_report=eval_report, progress=progress, reason=reason)
        _print_terminal_summary(
            ctx,
            n_stages=n_stages,
            eval_report=eval_report,
            repair_rounds_used=progress.repair_round,
        )
        return 0


def _run_linear(ctx: WorkflowContext, roles: list[str], run_stage_fn: Callable[..., int]) -> int:
    """Run every role once, in order. Fail-fast on any non-zero stage exit."""
    eval_report: EvalReport | None = None
    progress = WorkflowProgress()
    for index, role in enumerate(roles):
        print(f"\nfa workflow ─ stage {index + 1}/{len(roles)}: {role}", file=sys.stderr)
        result = _run_stage(
            ctx,
            role,
            fresh=index == 0,
            progress=progress,
            transition_reason=f"dispatching stage {index + 1}/{len(roles)}",
            run_stage_fn=run_stage_fn,
        )
        if result.exit_code != 0:
            _write_stage_failure_state(ctx, role, result.exit_code, progress=progress)
            return result.exit_code
        if result.eval_report is not None:
            eval_report = result.eval_report
    _write_terminal_state(
        ctx,
        last_role=roles[-1],
        eval_report=eval_report,
        progress=progress,
        reason=(
            f"eval verdict {eval_report.verdict} (linear; no repair loop)"
            if eval_report is not None
            else "linear workflow completed"
        ),
    )
    _print_terminal_summary(ctx, n_stages=len(roles), eval_report=eval_report, repair_rounds_used=0)
    return 0


def workflow_exit_code(result_code: int, terminal_state: FlowState | None) -> int:
    """Map a workflow run to its process exit code."""
    if result_code != 0 or terminal_state is None:
        return result_code
    return 0 if terminal_state.status == "DONE" else 1


# ── Public API ─────────────────────────────────────────────────────────────


def run_workflow(
    *,
    roles: list[str],
    task: str | None,
    per_role_task: Mapping[str, str | None],
    mode: str,
    max_repairs: int,
    max_replans: int,
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

    artifact_paths = workflow_artifact_paths(
        run_id,
        base_dir=run_context.run_log_dir if run_context is not None else None,
    )
    artifact_paths.base_dir.mkdir(parents=True, exist_ok=True)
    write_flow_state(
        artifact_paths.flow_state,
        FlowState(
            run_id=run_id,
            task=str(task or ""),
            status="PLANNING" if roles[0] == "planner" else "PLAN_READY",
            active_role=roles[0],
            active_plan_id=run_id,
            active_plan_version=1,
            last_actor="workflow",
            last_transition_reason=f"workflow initialized (mode={mode})",
        ),
    )

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
    )
    label = _render_mode_label(mode, max_repairs=max_repairs, max_replans=max_replans)
    print(f"fa workflow: run_id={run_id} mode={label} roles={'→'.join(roles)}", file=sys.stderr)
    if mode == "adaptive":
        result_code = _run_adaptive(ctx, roles, max_repairs, max_replans, run_stage_fn)
    else:
        result_code = _run_linear(ctx, roles, run_stage_fn)

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
    "EVAL_VERDICT_TO_TERMINAL_STATUS",
    "MAX_REPAIRS_CEILING",
    "MAX_REPLANS_CEILING",
    "WORKFLOW_DEADLINE_EXIT_CODE",
    "WORKFLOW_MODES",
    "WORKFLOW_STAGE_ROLES",
    "WORKFLOW_STATUS_TO_STOP_REASON",
    "StageResult",
    "WorkflowArtifactPaths",
    "WorkflowContext",
    "WorkflowProgress",
    "emit_eval_report",
    "eval_system_prompt_extra",
    "read_back_terminal_state",
    "run_workflow",
    "slugify_task",
    "status_for_role",
    "workflow_artifact_paths",
    "workflow_exit_code",
]
