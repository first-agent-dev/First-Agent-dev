"""``invoke_workflow`` — let the chat role escalate a task to the pipeline.

S4b / CT4. The chat role runs a deterministic scope estimator on every task
(S1/S3). Until this tool existed the estimator's verdict had no consumer: it
could say ``workflow_linear`` and nothing could act on it. This is that
consumer — the "expand" stage of the optimistic-estimator design (RN2).

**Why the tool is built here but registered at the CLI seam.** A profile-declared
tool gets a builder in ``profiles.py`` that takes only ``(root)``. This tool
needs values only a live ``fa run`` knows (the parent run id, the session
database, the transport, ``run_stage_fn``), so it cannot be profile-declared
without dragging a ``fa.cli`` import into the tools package and inverting the
dependency direction. Registration therefore happens in
``cli._build_run_tool_registry``, exactly as ``pr_prepare`` already does.

**Run identity.** The child pipeline gets its OWN run id, derived from the
parent's. Sharing the parent's id was measured to corrupt three things: the
shared ``events.jsonl`` (the parent's telemetry then counts the child's turns
and tool calls), the ``global_history.runs`` row (``run_id`` is the PRIMARY KEY
with ``INSERT OR REPLACE``, so the parent's later write erases the child's),
and the child's own ``flow_state.json`` / ``eval_report.json`` on a second
invocation. See CT4 "RUN IDENTITY".
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fa.inner_loop.expansion import TIER_HIGH, TIER_SAFE
from fa.inner_loop.path_risk import (
    ScopeRiskConfig,
    default_scope_risk_config,
    tier_for_path,
)
from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.workflow_controller import (
    DEADLINE_REASON_MARKER,
    MAX_REPAIRS_CEILING,
    MAX_REPLANS_CEILING,
    WORKFLOW_MODES,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    # FlowState is defined in workflow_artifacts; workflow_controller merely
    # re-exports it, and mypy rejects an implicit re-export.
    from fa.inner_loop.workflow_artifacts import FlowState

# The run-id grammar, intersected from its two independent validators so a
# child id is acceptable to BOTH:
#   cli.py            ^[A-Za-z0-9_.-]{1,128}$
#   session/manager   [A-Za-z0-9][A-Za-z0-9_.-]{0,127}
# The manager's leading-character rule is the stricter of the two, so it is the
# one encoded here.
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_RUN_ID_MAX_LEN = 128

DEFAULT_WORKFLOW_ROLES = "planner,coder,eval"
DEFAULT_WORKFLOW_MODE = "linear"
DEFAULT_TOOL_MAX_REPAIRS = 2
DEFAULT_TOOL_MAX_REPLANS = 1

# Re-entrancy is tracked per-thread, not per-process. Read-only tool batches are
# dispatched on a ThreadPoolExecutor, so a plain module-level bool could be
# observed by an unrelated worker thread and refuse a legitimate call.
# ``invoke_workflow`` itself always runs serially today (its permission is
# ``workspace``, and ``_should_parallelize_tool_batch`` refuses to batch any
# non-``read`` tool — verified by execution), but this guard must not silently
# depend on that staying true.
_ACTIVE = threading.local()

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkflowInvocationContext:
    """Everything ``run_workflow`` needs that the tool cannot invent itself.

    Supplied by a provider callable rather than captured at build time because
    ``fa run`` creates several of these values (the session database, the
    resolved run context) after the tool registry is already built.
    """

    parent_run_id: str
    config: Path
    workspace: Path
    max_turns: int
    run_stage_fn: Callable[..., int]
    workflow_timeout_seconds: int
    session_context: Any = None
    run_context: Any = None
    session_db: Any = None
    transport: Any = None
    secrets: Mapping[str, str] | None = None
    # S10 / CT6 (audit F2): structural escalation budget K — the maximum
    # number of invocations allowed per chat session. The tool counts
    # invocations itself (the -wfN closure); this is the bound it enforces.
    max_invocations: int = 2
    # S10 / CT6 (audit F2): called at tool-call time to snapshot LIVE session
    # facts (read/write paths, search leads) for the planner handoff. The tool
    # registry is built before SessionState exists, so the facts cannot be
    # captured at construction — a provider closure reads them on demand, the
    # same seam as run_stage_fn / pr_prepare. None -> goal-only degraded path.
    session_facts_provider: Callable[[], dict[str, Any]] | None = None
    # S10 / CT6: optional blackboard writer (BlackboardEntry) -> None, supplied
    # at the CLI seam so the tool never imports the blackboard package itself.
    blackboard_writer: Callable[[Any], None] | None = None


def child_run_id(parent: str, n: int) -> str:
    """Derive the ``n``-th child run id from ``parent``.

    The PARENT is truncated, never the suffix. Naive concatenation overflows
    the 128-character limit for long parents (measured: a 125-character parent
    yields a 129-character child that BOTH validators reject), and truncating
    the tail would destroy the very discriminator that makes the id unique.
    """
    suffix = f"-wf{n}"
    head = parent[: _RUN_ID_MAX_LEN - len(suffix)]
    return f"{head}{suffix}"


def parse_roles(raw: str) -> list[str]:
    """Split a comma-separated role list, dropping blanks.

    Pure and total: returns ``[]`` for input with no usable roles, which the
    handler turns into a structured ``invalid_roles`` failure.
    """
    return [part.strip() for part in raw.split(",") if part.strip()]


def _clamp(value: int, *, low: int, high: int) -> int:
    return max(low, min(high, value))


def _as_int(params: Mapping[str, object], key: str, default: int) -> int:
    raw = params.get(key, default)
    if isinstance(raw, bool) or not isinstance(raw, int):
        return default
    return raw


def _as_str(params: Mapping[str, object], key: str, default: str) -> str:
    raw = params.get(key, default)
    return raw if isinstance(raw, str) else default


INVOKE_WORKFLOW_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "task": {
            "type": "string",
            "minLength": 1,
            "description": "The complete task statement handed to the pipeline.",
        },
        "mode": {
            "type": "string",
            "enum": list(WORKFLOW_MODES),
            "description": "linear runs each role once; adaptive adds bounded coder-eval repair rounds.",
        },
        "roles": {
            "type": "string",
            "description": f"Comma-separated role sequence, e.g. {DEFAULT_WORKFLOW_ROLES!r}.",
        },
        "max_repairs": {
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_REPAIRS_CEILING,
            "description": "Cap on coder-eval repair rounds in adaptive mode.",
        },
        "max_replans": {
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_REPLANS_CEILING,
            "description": "Cap on planner re-entry rounds in adaptive mode.",
        },
    },
    "required": ["task"],
    "additionalProperties": False,
}


def build_handoff_task(
    *,
    goal: str,
    read_paths: list[str],
    write_paths: list[str],
    search_paths: list[str],
    config: ScopeRiskConfig | None = None,
) -> str:
    """Assemble the planner handoff task text (S10 / CT6, DP-9).

    Pure and deterministic. Sections (positive, imperative — no negative
    instructions):

      * ``Goal:`` the model-supplied task verbatim (trimmed);
      * ``Start here:`` the top HIGH-tier paths, capped at 5;
      * ``Observed (already read):`` read paths grouped by tier with counts;
      * ``Modified:`` the write paths;
      * ``Candidate leads:`` search-grep paths not already read, cap 10;
      * ``Do exactly:`` the 3-step positive checklist for the planner.

    Paths only (v1 — no snippets, no file:line); total paths capped at 30.
    With no facts at all (all lists empty) the task degrades to the goal so
    the planner still has a usable instruction.
    """
    cfg = config if config is not None else default_scope_risk_config()
    goal = goal.strip()

    def _posix(p: str) -> str:
        return str(p).replace("\\", "/")

    reads = sorted({_posix(p) for p in read_paths if p})
    writes = sorted({_posix(p) for p in write_paths if p})
    read_set = set(reads)
    leads = sorted({_posix(p) for p in search_paths if p and _posix(p) not in read_set})

    # Total path cap across the file-map sections (DP-9: <= 30).
    start_here_cap = 5
    leads_cap = 10
    total_paths_cap = 30

    read_high = [p for p in reads if tier_for_path(p, cfg) >= TIER_HIGH]
    start_here = read_high[:start_here_cap]

    grouped: dict[str, list[str]] = {"high": [], "medium": [], "safe": []}
    for p in reads:
        tier = tier_for_path(p, cfg)
        key = "high" if tier >= TIER_HIGH else "safe" if tier <= TIER_SAFE else "medium"
        grouped[key].append(p)

    leads = leads[:leads_cap]

    # Modified is truth but not unbounded (S10.9 / CT-H5): cap the section and
    # keep an explicit overflow marker — writes beyond the cap are summarized,
    # never silently dropped, and the planner can recover them via git status.
    modified_cap = 15
    shown_writes = writes[:modified_cap]
    writes_overflow = len(writes) - len(shown_writes)

    # Enforce the total-path budget, trimming Observed (the largest, most
    # derivable section) first; Start here and Leads are the actionable ones.
    budget = total_paths_cap - len(start_here) - len(shown_writes) - len(leads)
    if budget < 0:
        # Overspent on fixed sections: trim leads to fit (writes are truth and
        # must stay, capped + marked above).
        leads = leads[: max(0, leads_cap + budget)]
        budget = total_paths_cap - len(start_here) - len(shown_writes) - len(leads)
    observed_flat: list[str] = []
    for key in ("high", "medium", "safe"):
        take = max(0, budget - len(observed_flat))
        observed_flat.extend(grouped[key][:take])
    observed_set = set(observed_flat)
    grouped = {k: [p for p in v if p in observed_set] for k, v in grouped.items()}

    lines = [f"Goal: {goal}"]

    if start_here:
        lines.append("")
        lines.append("Start here:")
        lines.extend(f"  - {p}" for p in start_here)

    if any(grouped.values()):
        lines.append("")
        lines.append("Observed (already read):")
        for key, label in (("high", "high risk"), ("medium", "medium risk"), ("safe", "safe")):
            paths = grouped[key]
            if paths:
                lines.append(f"  {label} ({len(paths)}): " + ", ".join(paths))

    if writes:
        lines.append("")
        lines.append("Modified:")
        lines.extend(f"  - {p}" for p in shown_writes)
        if writes_overflow > 0:
            lines.append(f"  (+{writes_overflow} more — run git status for the full set)")

    if leads:
        lines.append("")
        lines.append("Candidate leads:")
        lines.extend(f"  - {p}" for p in leads)

    lines.append("")
    lines.append(
        "Do exactly:\n"
        '  1) Start from the files under "Start here".\n'
        "  2) Use Observed and Candidate leads as your map; do not re-search them.\n"
        "  3) Produce the plan and execute toward the goal from these files."
    )
    return "\n".join(lines)


def _check_budget(invocation_count: int, ctx: WorkflowInvocationContext) -> ToolResult | None:
    """Return a failure ToolResult when the escalation budget K is spent, else None.

    Enforced on the tool (audit F1): level 3 IS this call; the invocation-count
    closure is the authority for the run id, so it also bounds K.
    """
    budget = max(0, int(getattr(ctx, "max_invocations", 2)))
    if invocation_count >= budget:
        if budget == 0:
            return ToolResult.fail(
                "workflow_budget_exhausted",
                "workflow escalation is disabled by config (max_workflow_invocations=0); "
                "finish with an operator report",
            )
        return ToolResult.fail(
            "workflow_budget_exhausted",
            f"workflow escalation budget of {budget} invocation(s) used; "
            "finish with an operator report instead of escalating again",
        )
    return None


def _resolve_handoff_task(*, task: str, candidate: str, ctx: WorkflowInvocationContext) -> str:
    """Build the planner handoff task from LIVE session facts (S10 / CT6).

    A missing/raising provider degrades to the raw goal — the escalation must
    still run. The blackboard mirror is best-effort.
    """
    facts: dict[str, Any] = {}
    if ctx.session_facts_provider is not None:
        try:
            raw = ctx.session_facts_provider()
            if isinstance(raw, dict):
                facts = raw
        except Exception as exc:  # noqa: BLE001 - facts are advisory
            logger.warning("workflow handoff facts unavailable: %s", exc)
            facts = {}

    if not facts:
        return task

    try:
        handoff = build_handoff_task(
            goal=task,
            read_paths=list(facts.get("read_paths") or ()),
            write_paths=list(facts.get("write_paths") or ()),
            search_paths=list(facts.get("last_search_paths") or ()),
            config=facts.get("risk_config"),
        )
    except Exception as exc:  # noqa: BLE001 - handoff is advisory; degrade to goal
        logger.warning("workflow handoff build failed: %s", exc)
        return task
    if ctx.blackboard_writer is not None:
        try:
            ctx.blackboard_writer(
                {
                    "type": "workflow_handoff",
                    "goal": task,
                    "child_run_id": candidate,
                    "read_paths": list(facts.get("read_paths") or ()),
                    "write_paths": list(facts.get("write_paths") or ()),
                    "candidate_leads": list(facts.get("last_search_paths") or ()),
                }
            )
        except Exception as exc:  # noqa: BLE001 - blackboard is derived
            logger.warning("workflow_handoff blackboard write failed: %s", exc)
    return handoff


def build_invoke_workflow_tool(
    run_workflow_fn: Callable[..., tuple[int, FlowState | None]],
    ctx_provider: Callable[[], WorkflowInvocationContext | None],
) -> ToolSpec:
    """Build the ``invoke_workflow`` :class:`ToolSpec`.

    ``run_workflow_fn`` is injected rather than imported so tests can supply a
    real callable with the true keyword-only signature, and so this module
    never has to reach back into the CLI.
    """

    invocation_count = 0

    def handler(params: Mapping[str, object]) -> ToolResult:
        nonlocal invocation_count

        # (a) Re-entrancy. Covers the recursion case: this thread re-entering
        # while a pipeline is already running on it. It does NOT cover
        # `fa workflow --roles planner,chat,eval`, where the chat stage runs in
        # a separate process that thread-local state cannot see; the mitigation
        # for that is a role allowlist in _cmd_workflow, tracked as RK8.
        if getattr(_ACTIVE, "running", False):
            return ToolResult.fail(
                "workflow_reentrant",
                "a workflow is already running on this thread; nested invocation is refused",
            )

        # (b) No live run context -> the tool exists but has nothing to drive.
        ctx = ctx_provider()
        if ctx is None:
            return ToolResult.fail(
                "workflow_unavailable",
                "invoke_workflow needs a live run context and none is bound to this session",
            )

        # (b2) Structural escalation budget K (S10 / CT6, audit F1).
        budget_failure = _check_budget(invocation_count, ctx)
        if budget_failure is not None:
            return budget_failure

        task = _as_str(params, "task", "").strip()
        if not task:
            return ToolResult.fail("invalid_params", "`task` must be a non-empty string", retryable=True)

        # (c) Roles.
        roles = parse_roles(_as_str(params, "roles", DEFAULT_WORKFLOW_ROLES))
        if not roles:
            return ToolResult.fail(
                "invalid_roles",
                "`roles` must name at least one role, e.g. 'planner,coder,eval'",
                retryable=True,
            )

        # (d) Mode. The schema also constrains this; the handler check is the
        # fail-closed half for any caller that bypasses schema validation.
        mode = _as_str(params, "mode", DEFAULT_WORKFLOW_MODE)
        if mode not in WORKFLOW_MODES:
            return ToolResult.fail(
                "invalid_mode",
                f"`mode` {mode!r} is not one of {list(WORKFLOW_MODES)}",
                retryable=True,
            )

        max_repairs = _clamp(_as_int(params, "max_repairs", DEFAULT_TOOL_MAX_REPAIRS), low=0, high=MAX_REPAIRS_CEILING)
        max_replans = _clamp(_as_int(params, "max_replans", DEFAULT_TOOL_MAX_REPLANS), low=0, high=MAX_REPLANS_CEILING)

        # (e) Child run id, validated before use.
        candidate = child_run_id(ctx.parent_run_id, invocation_count + 1)
        if not _RUN_ID_RE.match(candidate):
            return ToolResult.fail(
                "invalid_child_run_id",
                f"derived child run id {candidate!r} does not match {_RUN_ID_RE.pattern}",
            )

        # (f2) Planner handoff (S10 / CT6, DP-9): file-map + Do-exactly built
        # from LIVE session facts; degrades to the raw goal when unavailable.
        handoff_task = _resolve_handoff_task(task=task, candidate=candidate, ctx=ctx)

        # (f) Deadline. Computed here so the elapsed budget covers the whole
        # nested pipeline, not one stage.
        deadline = time.monotonic() + ctx.workflow_timeout_seconds

        invocation_count += 1
        _ACTIVE.running = True
        try:
            exit_code, terminal_state = run_workflow_fn(
                roles=roles,
                task=handoff_task,
                per_role_task={},
                mode=mode,
                max_repairs=max_repairs,
                max_replans=max_replans,
                run_id=candidate,
                config=ctx.config,
                workspace=ctx.workspace,
                max_turns=ctx.max_turns,
                output_mode="quiet",
                run_stage_fn=ctx.run_stage_fn,
                transport=ctx.transport,
                secrets=ctx.secrets,
                session_context=ctx.session_context,
                run_context=ctx.run_context,
                session_db=ctx.session_db,
                deadline_mono=deadline,
            )
        except Exception as exc:  # noqa: BLE001 - a tool must not kill the chat session
            # (h) Contained deliberately. An escaping exception here would end
            # the operator's chat turn over a failure in a *nested* pipeline
            # whose artifacts are already on disk and inspectable.
            return ToolResult.fail(
                "workflow_error",
                f"workflow {candidate} raised {type(exc).__name__}: {exc}",
            )
        finally:
            _ACTIVE.running = False

        # (i) Structured result per CT4 OUTPUTS. No "verdict" field: run_workflow
        # returns (exit_code, FlowState) and FlowState has no verdict; the
        # status mapping is lossy (BLOCKED -> "FAILED"), so a verdict cannot be
        # reconstructed from it either. Consumers that need the verdict read
        # eval_report.json under the child run id.
        status = terminal_state.status if terminal_state is not None else ""
        route = terminal_state.last_route_decision if terminal_state is not None else ""
        reason = terminal_state.last_transition_reason if terminal_state is not None else ""
        timed_out = DEADLINE_REASON_MARKER in reason

        if timed_out:
            summary = f"workflow {candidate} ran out of time ({', '.join(roles)}); artifacts kept"
        elif exit_code == 0:
            summary = f"workflow {candidate} finished: status={status or 'unknown'}"
        else:
            summary = f"workflow {candidate} exited {exit_code}: status={status or 'unknown'}"

        return ToolResult.ok(
            summary,
            result={
                "run_id": candidate,
                "exit_code": exit_code,
                "status": status,
                "route": route,
                "timed_out": timed_out,
            },
        )

    return ToolSpec(
        name="invoke_workflow",
        description=(
            "Run a multi-role workflow pipeline (planner, coder, eval) on a task that is too "
            "large to finish in this conversation. Returns the child run id, exit code and "
            "terminal status; the pipeline's artifacts are written under that run id."
        ),
        input_schema=INVOKE_WORKFLOW_SCHEMA,
        permission="workspace",
        handler=handler,
        tags=("workflow", "escalation"),
    )


__all__ = [
    "DEFAULT_TOOL_MAX_REPAIRS",
    "DEFAULT_TOOL_MAX_REPLANS",
    "DEFAULT_WORKFLOW_MODE",
    "DEFAULT_WORKFLOW_ROLES",
    "INVOKE_WORKFLOW_SCHEMA",
    "WorkflowInvocationContext",
    "build_handoff_task",
    "build_invoke_workflow_tool",
    "child_run_id",
    "parse_roles",
]
