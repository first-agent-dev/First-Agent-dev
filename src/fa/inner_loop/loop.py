"""Deterministic inner-loop driver (ADR-7 \u00a71 + ADR-8 \u00a71).

``run_session`` executes one batch of :class:`ToolCall` instances through
the registered hooks and tool registry. It reads its iteration cap from
the supplied :class:`RuntimeLimits` (ADR-7 \u00a7Amendment 2026-05-20 rule 1
\u00abcaps in ``~/.fa/config.yaml``, never in code constants\u00bb), wires every
``hook_decision`` row through ``state.log`` (ADR-7 \u00a77), and emits both
``tool_call`` and ``tool_result`` rows for every call \u2014 successful or
denied \u2014 per ADR-7 \u00a710 Acceptance criterion 8.
"""

from __future__ import annotations

from collections.abc import Iterable

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
    # ADR-7 \u00a77 hook_decision projection: every guard/observer step writes
    # one row to ``events.jsonl`` so the audit trail is replay-complete.
    assert state.log is not None
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
                # ADR-7 §8 BETWEEN_ROUNDS is a session-level gate (e.g.
                # ``PauseGuard``): a deny must stop the loop cleanly, not
                # propagate the raw ``PermissionError`` out of the runtime.
                # The audit trail still gets a ``hook_decision`` row from
                # the registry, plus a ``run_stopped`` row here so an
                # operator can tell «loop ended early» from «loop ran to
                # completion» without replaying the chain.
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
            if effective_call is None:
                result = ToolResult.fail("invalid_payload", "hook payload lost tool call")
            else:
                # ADR-7 \u00a75 \u00abRe-validation after pre_tool mutation\u00bb: when
                # the chain mutated ``tool_call``, ``registry.dispatch`` re-
                # runs JSON-Schema validation against the new params (the
                # sandbox-re-check is handled inside HookRegistry.dispatch
                # via ``revalidates_after_modify``).
                result = registry.dispatch(effective_call)
                payload = payload.with_tool_result(result)
                hooks.dispatch(LifecyclePoint.AFTER_TOOL_EXEC, payload)
            state.record_tool_result(effective_call if effective_call is not None else call, result)
            results.append(result)
            state.observations.append(result.summary)
    finally:
        hooks.set_event_sink(None)
    return tuple(results)


__all__ = ["run_session"]
