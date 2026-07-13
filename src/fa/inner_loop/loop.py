"""Deterministic inner-loop driver (ADR-7 §1 + ADR-8 §1).

``run_session`` executes one batch of :class:`ToolCall` instances through
the registered hooks and tool registry. It reads its iteration cap from
the supplied :class:`RuntimeLimits` (ADR-7 §Amendment 2026-05-20 rule 1
«caps in ``~/.fa/config.yaml``, never in code constants»), wires every
``hook_decision`` row through ``state.log`` (ADR-7 §7), and emits both
``tool_call`` and ``tool_result`` rows for every call — successful or
denied — per ADR-7 §10 Acceptance criterion 8.
"""

from __future__ import annotations

from collections.abc import Iterable

from fa.inner_loop.context import reset_current_session, set_current_session
from fa.inner_loop.hooks.base import (
    DispatchRecord,
    HookDecisionSink,
    HookPayload,
    HookRegistry,
    LifecyclePoint,
)
from fa.inner_loop.hooks.builtin import default_tool_result_for_denial
from fa.inner_loop.registry import ToolCall, ToolRegistry, ToolResult
from fa.inner_loop.runtime_limits import RuntimeLimits
from fa.inner_loop.state import EventLog, SessionState


def _make_hook_decision_sink(log: EventLog) -> HookDecisionSink:
    def sink(record: DispatchRecord, payload: HookPayload) -> None:
        call = payload.tool_call
        log.append(
            actor="hook",
            kind="hook_decision",
            content={
                "middleware": record.middleware,
                "point": record.point.value,
                "decision": record.decision,
                "reason": record.reason,
            },
            tool_name="" if call is None else call.name,
            tool_call_id="" if call is None else call.call_id,
        )

    return sink


def run_session(
    calls: Iterable[ToolCall],
    *,
    registry: ToolRegistry,
    hooks: HookRegistry,
    state: SessionState,
    role: str = "coder",
    acting_family: str = "",
    limits: RuntimeLimits | None = None,
) -> tuple[ToolResult, ...]:
    effective_limits = limits if limits is not None else RuntimeLimits.anchored_defaults()
    # Phase 0.5: set current session in contextvar so tool handlers can access
    # transaction/blackboard via DI without signature change
    token = set_current_session(state)

    if state.log is None:
        raise ValueError("SessionState.log must be set before run_session")
    hooks.set_event_sink(_make_hook_decision_sink(state.log))

    results: list[ToolResult] = []
    try:
        for iteration, call in enumerate(calls, start=1):
            if iteration > effective_limits.max_iterations:
                break
            try:
                hooks.dispatch(
                    LifecyclePoint.BETWEEN_ROUNDS,
                    HookPayload(role=role, acting_family=acting_family),
                )
            except PermissionError as exc:
                state.log.append(
                    actor="runtime",
                    kind="run_stopped",
                    content={"point": LifecyclePoint.BETWEEN_ROUNDS.value, "reason": str(exc)},
                )
                break
            state.record_tool_call(call)
            try:
                payload = hooks.dispatch(
                    LifecyclePoint.BEFORE_TOOL_EXEC,
                    HookPayload(tool_call=call, role=role, acting_family=acting_family),
                )
            except PermissionError as exc:
                result = default_tool_result_for_denial(str(exc))
                state.record_tool_result(call, result)
                results.append(result)
                state.observations.append(result.summary)
                continue

            effective_call = payload.tool_call
            post_exec_denied: PermissionError | None = None
            if effective_call is None:
                result = ToolResult.fail("invalid_payload", "hook payload lost tool call")
            else:
                result = registry.dispatch(effective_call)

            payload = payload.with_tool_result(result)
            try:
                hooks.dispatch(LifecyclePoint.AFTER_TOOL_EXEC, payload)
            except PermissionError as exc:
                post_exec_denied = exc
            state.record_tool_result(effective_call if effective_call is not None else call, result)
            results.append(result)
            state.observations.append(result.summary)
            if post_exec_denied is not None:
                state.log.append(
                    actor="runtime",
                    kind="run_stopped",
                    content={
                        "point": LifecyclePoint.AFTER_TOOL_EXEC.value,
                        "reason": str(post_exec_denied),
                    },
                )
                break
    finally:
        hooks.set_event_sink(None)
        reset_current_session(token)
    return tuple(results)


__all__ = ["run_session"]
