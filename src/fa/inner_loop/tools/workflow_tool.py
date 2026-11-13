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
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from fa.execution.client import ExecutionRejectedError
from fa.execution.composition import BoundPlanPublisher, ExecutionBinding, ManagedExecution
from fa.execution.types import NamespaceRef
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
    WorkflowRequestError,
    _validate_workflow_request,
)
from fa.paths import fa_state_root
from fa.session.manager import RunContext, SessionContext, SessionManager, SessionManagerError

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


class ParentStageLease(Protocol):
    """Trusted in-process lifecycle seam for a parent stage around child work."""

    @property
    def is_handoff_enabled(self) -> bool: ...

    def suspend(self, *, deadline: float | None = None) -> str: ...

    def resume(self, *, deadline: float | None = None) -> None: ...


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
    # Parent-managed writer and stage lease are supplied only by direct managed
    # ``fa run``. ``fa workflow`` intentionally retains its legacy context.
    managed_execution: Any = None
    parent_stage_lease: ParentStageLease | None = None
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
    # PLAN S5c / Q9: operator-supplied --inject overrides for the CHAT session
    # that owns this tool, already parsed and validated at the CLI seam. A
    # nested pipeline inherits them, because the operator configured this
    # invocation and everything it launches. Empty default keeps every
    # existing construction site byte-identical.
    #
    # Overrides, not resolved modes: the nested pipeline re-resolves per stage
    # via resolve_injection_modes, so role gating still applies and an
    # inherited coder-only injection stays off for a planner stage.
    inject_overrides: Mapping[str, str] = field(default_factory=dict)


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
        return p.replace("\\", "/")

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


def _requires_acquisition(roles: list[str]) -> bool:
    """Q70: only coder-containing nested requests need the unavailable I03 handoff."""
    return "coder" in roles


_ACQUISITION_UNAVAILABLE = (
    "nested coder workflows need I03 managed plan acquisition; use an explicit-plan CLI/library workflow instead"
)
_ACQUISITION_REQUIRES_PLANNER = (
    "a coder-bearing managed workflow must include its initial planner, "
    "and as the first role; no outer plan reference exists to acquire one"
)


def acquisition_refusal(roles: list[str], *, managed: bool) -> tuple[str, str] | None:
    """S5P1: say *why* a coder-bearing request cannot proceed, or None if it may.

    Two distinct contracts, not one refusal with a guess attached (§7):

    * a managed request that would run a coder with no plan to code against is
      refused as ``acquisition_requires_planner`` -- before child/provider, so a
      guessed default target never reaches an admission record;
    * a legacy request keeps its existing purpose: I03 managed acquisition is not
      wired into that path, so it is ``acquisition_unavailable`` as before.

    The controller supplies a plan through its own admission. Holding a managed
    execution or a plan reference is therefore *not* an admission ticket here: it
    only makes the refusal more precise. Wire admission lands with the managed
    caller (S5P2), and until then an unusable approval must not look like one.

    The planner must come first. A planner sequenced after the coder cannot own
    the plan the coder would write against, and stages run in the stated order.
    """
    if not _requires_acquisition(roles):
        return None
    if managed:
        if not roles or roles[0] != "planner":
            return "acquisition_requires_planner", _ACQUISITION_REQUIRES_PLANNER
        return "acquisition_unavailable", _ACQUISITION_UNAVAILABLE
    return "acquisition_unavailable", _ACQUISITION_UNAVAILABLE


def _child_run_context(ctx: WorkflowInvocationContext, candidate: str) -> RunContext | None:
    """Allocate through existing session authority; never reuse/clone the parent run."""
    if ctx.run_context is None and ctx.session_context is None:
        return None  # Explicit legacy library contexts have no session lifecycle.
    parent, session = ctx.run_context, ctx.session_context
    if not isinstance(parent, RunContext) or not isinstance(session, SessionContext):
        raise SessionManagerError("session_context_missing", "nested workflow needs both session contexts")
    if (
        parent.run_id != ctx.parent_run_id
        or parent.session_id != session.session_id
        or parent.workspace_path != ctx.workspace
        or session.workspace_path != ctx.workspace
        or parent.session_db_path != session.session_db_path
    ):
        raise SessionManagerError("session_context_mismatch", "nested workflow parent binding does not match")
    manager = SessionManager(state_root=fa_state_root(), workspace_root=ctx.workspace.parent)
    return manager.begin_run(session, requested_run_id=candidate)


def _managed_parent_namespace(ctx: WorkflowInvocationContext) -> NamespaceRef | None:
    """Validate the direct-run handoff seam before allocating or suspending anything."""
    managed = ctx.managed_execution
    lease = ctx.parent_stage_lease
    if managed is None and lease is None:
        return None
    if (
        not isinstance(managed, ManagedExecution)
        or lease is None
        or getattr(lease, "is_handoff_enabled", False) is not True
        or not callable(getattr(lease, "suspend", None))
        or not callable(getattr(lease, "resume", None))
        or not isinstance(ctx.session_context, SessionContext)
        or not isinstance(ctx.run_context, RunContext)
    ):
        raise SessionManagerError("managed_handoff_unavailable", "parent managed handoff binding is incomplete")
    parent = NamespaceRef(ctx.session_context.session_id, ctx.parent_run_id)
    if (
        ctx.run_context.run_id != ctx.parent_run_id
        or ctx.run_context.session_id != ctx.session_context.session_id
        or ctx.run_context.workspace_path != ctx.workspace
        or ctx.session_context.workspace_path != ctx.workspace
        or managed.binding.namespace != parent
    ):
        raise SessionManagerError("managed_handoff_mismatch", "parent managed handoff binding does not match")
    return parent


def _begin_managed_child(
    *,
    managed: ManagedExecution,
    child_namespace: NamespaceRef,
    parent_stage_lease: ParentStageLease,
    deadline: float,
) -> ToolResult | None:
    """Suspend the parent and require server acknowledgement before child dispatch."""
    try:
        suspended_revision = parent_stage_lease.suspend(deadline=deadline)
        if suspended_revision != managed.current_revision_id:
            raise RuntimeError("parent publication revision did not match the owner grant")
    except Exception as exc:  # noqa: BLE001 - stale parent view is never reused
        return ToolResult.fail("parent_suspend_failed", f"parent workspace suspension failed [{type(exc).__name__}]")
    try:
        managed.handoff_to(child_namespace, deadline=deadline)
    except ExecutionRejectedError as exc:
        # A first, determinate refusal leaves ownership with the parent. Resume
        # only by opening a fresh view; never revive the old grant.
        try:
            parent_stage_lease.resume(deadline=deadline)
        except Exception as resume_error:  # noqa: BLE001 - parent remains fail-closed
            return ToolResult.fail(
                "parent_resume_failed",
                f"HANDOFF refusal could not reopen the parent [{type(resume_error).__name__}]",
            )
        return ToolResult.fail("workflow_handoff_refused", f"child dispatch refused [{exc.code}]")
    except Exception as exc:  # noqa: BLE001 - no dispatch or parent resume on uncertainty
        return ToolResult.fail(
            "workflow_handoff_uncertain",
            f"child ownership could not be confirmed [{type(exc).__name__}]; parent remains suspended",
        )
    if managed.binding.namespace != child_namespace:
        return ToolResult.fail("workflow_handoff_invalid", "HANDOFF did not bind the exact child namespace")
    return None


def _return_managed_child_to_parent(
    *,
    managed: ManagedExecution,
    parent_namespace: NamespaceRef,
    parent_stage_lease: ParentStageLease,
    deadline: float,
) -> str | None:
    """Reverse HANDOFF, then reopen/rebind the parent at the returned revision."""
    try:
        managed.handoff_to(parent_namespace, deadline=deadline)
    except Exception as error:  # noqa: BLE001 - unresolved child authority is fail-closed
        return f"return HANDOFF failed: {type(error).__name__}"
    if managed.binding.namespace != parent_namespace:
        return "return HANDOFF did not restore the exact parent namespace"
    try:
        parent_stage_lease.resume(deadline=deadline)
    except Exception as error:  # noqa: BLE001 - never continue with suspended adapters
        return f"parent view refresh failed: {type(error).__name__}"
    return None


def _dispatch_child_workflow(
    run_workflow_fn: Callable[..., tuple[int, FlowState | None]],
    *,
    workflow_kwargs: dict[str, object],
    managed: ManagedExecution | None,
    child_namespace: NamespaceRef | None,
) -> tuple[int, FlowState | None, Exception | None]:
    """Call the real workflow seam and contain child exceptions for reconciliation."""
    _ACTIVE.running = True
    try:
        if managed is not None:
            if child_namespace is None:
                raise RuntimeError("managed child namespace missing")
            child_binding = ExecutionBinding(child_namespace, managed.binding.workspace_id)
            workflow_kwargs["managed_execution"] = managed
            workflow_kwargs["plan_publisher"] = BoundPlanPublisher(managed, child_binding)
        exit_code, terminal_state = run_workflow_fn(**workflow_kwargs)
        return exit_code, terminal_state, None
    except Exception as exc:  # noqa: BLE001 - reconcile authority before reporting child failure
        return 2, None, exc
    finally:
        _ACTIVE.running = False


def _execute_child_with_managed_lifecycle(
    run_workflow_fn: Callable[..., tuple[int, FlowState | None]],
    *,
    workflow_kwargs: dict[str, object],
    managed: ManagedExecution | None,
    parent_namespace: NamespaceRef | None,
    child_namespace: NamespaceRef | None,
    parent_stage_lease: ParentStageLease | None,
    deadline: float,
) -> tuple[int, FlowState | None, Exception | None, ToolResult | None]:
    """Own the complete HANDOFF/child/return cycle; never resume on stale authority."""
    if managed is not None:
        if parent_namespace is None or child_namespace is None or parent_stage_lease is None:
            return 2, None, None, ToolResult.fail("workflow_context_error", "managed child binding is incomplete")
        failure = _begin_managed_child(
            managed=managed,
            child_namespace=child_namespace,
            parent_stage_lease=parent_stage_lease,
            deadline=deadline,
        )
        if failure is not None:
            return 2, None, None, failure

    exit_code, terminal_state, workflow_error = _dispatch_child_workflow(
        run_workflow_fn,
        workflow_kwargs=workflow_kwargs,
        managed=managed,
        child_namespace=child_namespace,
    )
    if managed is not None and parent_namespace is not None and parent_stage_lease is not None:
        return_error = _return_managed_child_to_parent(
            managed=managed,
            parent_namespace=parent_namespace,
            parent_stage_lease=parent_stage_lease,
            deadline=deadline,
        )
        if return_error is not None:
            return (
                2,
                None,
                None,
                ToolResult.fail("workflow_return_unconfirmed", f"{return_error}; parent remains suspended"),
            )
    return exit_code, terminal_state, workflow_error, None


@dataclass(frozen=True)
class _PreparedInvocation:
    task: str
    roles: list[str]
    mode: str
    max_repairs: int
    max_replans: int
    candidate: str


def _prepare_invocation(
    params: Mapping[str, object], ctx: WorkflowInvocationContext, invocation_count: int
) -> _PreparedInvocation | ToolResult:
    """Validate public fields and reserve the next stable child identifier."""
    task = _as_str(params, "task", "").strip()
    if not task:
        return ToolResult.fail("invalid_params", "`task` must be a non-empty string", retryable=True)
    roles = parse_roles(_as_str(params, "roles", DEFAULT_WORKFLOW_ROLES))
    if not roles:
        return ToolResult.fail(
            "invalid_roles",
            "`roles` must name at least one role, e.g. 'planner,coder,eval'",
            retryable=True,
        )
    mode = _as_str(params, "mode", DEFAULT_WORKFLOW_MODE)
    if mode not in WORKFLOW_MODES:
        return ToolResult.fail(
            "invalid_mode",
            f"`mode` {mode!r} is not one of {list(WORKFLOW_MODES)}",
            retryable=True,
        )
    refusal = acquisition_refusal(roles, managed=ctx.managed_execution is not None)
    if refusal is not None:
        code, message = refusal
        return ToolResult.fail(code, message)
    candidate = child_run_id(ctx.parent_run_id, invocation_count + 1)
    if not _RUN_ID_RE.match(candidate):
        return ToolResult.fail("invalid_child_run_id", f"derived child run id {candidate!r} is invalid")
    return _PreparedInvocation(
        task=task,
        roles=roles,
        mode=mode,
        max_repairs=_clamp(_as_int(params, "max_repairs", DEFAULT_TOOL_MAX_REPAIRS), low=0, high=MAX_REPAIRS_CEILING),
        max_replans=_clamp(_as_int(params, "max_replans", DEFAULT_TOOL_MAX_REPLANS), low=0, high=MAX_REPLANS_CEILING),
        candidate=candidate,
    )


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

        prepared = _prepare_invocation(params, ctx, invocation_count)
        if isinstance(prepared, ToolResult):
            return prepared
        task, roles, mode = prepared.task, prepared.roles, prepared.mode
        max_repairs, max_replans = prepared.max_repairs, prepared.max_replans
        candidate = prepared.candidate

        try:
            parent_namespace = _managed_parent_namespace(ctx)
        except SessionManagerError as exc:
            return ToolResult.fail("workflow_context_error", f"managed child allocation refused: {exc.code}")

        # (f) One absolute deadline includes child allocation, both HANDOFFs,
        # parent-view refresh, and every child stage.
        deadline = time.monotonic() + ctx.workflow_timeout_seconds
        try:
            _validate_workflow_request(
                roles=roles,
                mode=mode,
                max_repairs=max_repairs,
                max_replans=max_replans,
                run_id=candidate,
                task=task,
                per_role_task={},
                inject_overrides=ctx.inject_overrides,
            )
            child_context = _child_run_context(ctx, candidate)
            if parent_namespace is not None and child_context is None:
                raise SessionManagerError("child_context_missing", "managed child needs a session run context")
        except (SessionManagerError, WorkflowRequestError) as exc:
            return ToolResult.fail("workflow_context_error", f"child run allocation refused: {exc.code}")
        invocation_count += 1

        child_namespace = (
            NamespaceRef(child_context.session_id, child_context.run_id, parent_run_id=ctx.parent_run_id)
            if parent_namespace is not None and child_context is not None
            else None
        )

        # (f2) Planner handoff (S10 / CT6, DP-9): file-map + Do-exactly built
        # from LIVE session facts; degrades to the raw goal when unavailable.
        handoff_task = _resolve_handoff_task(task=task, candidate=candidate, ctx=ctx)

        managed = ctx.managed_execution if parent_namespace is not None else None
        parent_lease = ctx.parent_stage_lease if parent_namespace is not None else None
        workflow_kwargs: dict[str, object] = {
            "roles": roles,
            "task": handoff_task,
            "per_role_task": {},
            "mode": mode,
            "max_repairs": max_repairs,
            "max_replans": max_replans,
            "run_id": candidate,
            "config": ctx.config,
            "workspace": ctx.workspace,
            "max_turns": ctx.max_turns,
            "output_mode": "quiet",
            "run_stage_fn": ctx.run_stage_fn,
            "transport": ctx.transport,
            "secrets": ctx.secrets,
            "session_context": ctx.session_context,
            "run_context": child_context,
            "session_db": ctx.session_db,
            "deadline_mono": deadline,
            # PLAN S5c / Q9: inherit the chat session's --inject.
            "inject_overrides": ctx.inject_overrides,
        }
        exit_code, terminal_state, workflow_error, lifecycle_error = _execute_child_with_managed_lifecycle(
            run_workflow_fn,
            workflow_kwargs=workflow_kwargs,
            managed=managed,
            parent_namespace=parent_namespace,
            child_namespace=child_namespace,
            parent_stage_lease=parent_lease,
            deadline=deadline,
        )
        if lifecycle_error is not None:
            return lifecycle_error
        if workflow_error is not None:
            return ToolResult.fail(
                "workflow_error",
                f"workflow {candidate} raised {type(workflow_error).__name__}: {workflow_error}",
            )

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
        if managed is not None:
            summary += "; parent workspace refreshed at the returned revision"

        return ToolResult.ok(
            summary,
            result={
                "run_id": candidate,
                "exit_code": exit_code,
                "status": status,
                "route": route,
                "timed_out": timed_out,
                "parent_view_refreshed": managed is not None,
            },
        )

    return ToolSpec(
        name="invoke_workflow",
        description=(
            "Run a multi-role workflow pipeline (planner, coder, eval) on a task that is too "
            "large to finish in this conversation. Coder-containing requests currently return "
            "acquisition_unavailable; planner/eval-only delegation remains available. "
            "Returns the child run id, exit code and "
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
    "ParentStageLease",
    "WorkflowInvocationContext",
    "build_handoff_task",
    "build_invoke_workflow_tool",
    "child_run_id",
    "parse_roles",
]
