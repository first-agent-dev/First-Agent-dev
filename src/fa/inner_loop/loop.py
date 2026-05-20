from __future__ import annotations

from collections.abc import Iterable

from fa.inner_loop.hooks.base import HookPayload, HookRegistry, LifecyclePoint
from fa.inner_loop.hooks.builtin import default_tool_result_for_denial
from fa.inner_loop.registry import ToolCall, ToolRegistry, ToolResult
from fa.inner_loop.state import SessionState


def run_session(
    calls: Iterable[ToolCall],
    *,
    registry: ToolRegistry,
    hooks: HookRegistry,
    state: SessionState,
    role: str = "coder",
    acting_family: str = "",
) -> tuple[ToolResult, ...]:
    results: list[ToolResult] = []
    for iteration, call in enumerate(calls, start=1):
        if iteration > state.max_iterations:
            break
        hooks.dispatch(
            LifecyclePoint.BETWEEN_ROUNDS,
            HookPayload(role=role, acting_family=acting_family),
        )
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
            result = registry.dispatch(effective_call)
            payload = payload.with_tool_result(result)
            hooks.dispatch(LifecyclePoint.AFTER_TOOL_EXEC, payload)
        state.record_tool_result(effective_call if effective_call is not None else call, result)
        results.append(result)
        state.observations.append(result.summary)
    return tuple(results)


__all__ = ["run_session"]
