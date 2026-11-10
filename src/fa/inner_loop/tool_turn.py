"""Tool-turn stop, audit pairing and model-facing projection support.

Execution and hooks remain in loop.py; the session driver owns turn order.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.hooks.base import LifecyclePoint
from fa.inner_loop.hooks.loop_guard import LOOP_GUARD_REASON_PREFIX
from fa.inner_loop.loop import SessionRun, StopInfo
from fa.inner_loop.projection import project_for_model
from fa.inner_loop.registry import ToolCall, ToolRegistry, ToolResult, ToolSpec
from fa.inner_loop.runtime_limits import RuntimeLimits
from fa.inner_loop.state import EventLog, SessionState
from fa.observability.redaction import SecretRedactor
from fa.output import EventBus, OutputEvent


def _redact(redactor: SecretRedactor | None, text: str) -> str:
    """Mask known secret values in model-facing tool output (ADR-12 B2).

    This is the single egress chokepoint between tool results and the LLM
    message stream (pi-style input-side redaction). Even if a tool returns a
    secret value (e.g. the deploy key read via some path the gate missed), it
    is masked — in raw, base64, hex, and url-encoded forms — before it can
    reach the provider and therefore before the model can ever repeat it.
    """
    if redactor is None:
        return text
    return redactor.redact(text)


def _fallback_projection_handler(_params: Mapping[str, object]) -> ToolResult:
    return ToolResult.ok("projection fallback")


def _projection_spec_for_call(registry: ToolRegistry, call: ToolCall) -> ToolSpec:
    try:
        return registry.lookup(call.name)
    except KeyError:
        return ToolSpec(
            name=call.name,
            description="Fallback projection spec for an unregistered tool call.",
            input_schema={"type": "object"},
            permission="read",
            handler=_fallback_projection_handler,
        )


def _pad_unexecuted_tool_results(
    tool_calls: tuple[ToolCall, ...],
    turn_results: SessionRun,
    *,
    state: SessionState,
    log: EventLog,
    log_len_before: int,
    limits: RuntimeLimits,
) -> SessionRun:
    """Pair unexecuted calls with audited failures without dropping the stop signal."""
    # ``run_session`` enforces ``max_iterations`` per invocation.
    # If the LLM emitted more tool calls than the cap, the loop
    # breaks early and returns fewer results. We MUST pad the
    # remainder with synthetic failures so the conversation history
    # stays protocol-valid: every ``tool_call_id`` in the
    # assistant message needs a matching ``role="tool"`` message.
    missing = len(tool_calls) - len(turn_results)
    if missing > 0:
        # Determine whether run_session stopped for a real iteration
        # cap or for a guard denial (PauseGuard, LoopGuard, etc.).
        stop_reason_code = "iteration_cap"
        stop_reason_detail = f"tool call skipped: per-turn iteration limit ({limits.max_iterations}) exceeded"
        if log is not None:
            new_rows = log.read_all()[log_len_before:]
            for row in reversed(new_rows):
                if row.kind == "run_stopped":
                    reason = str(row.content.get("reason", ""))
                    if not reason.startswith("iteration_cap"):
                        stop_reason_code = "run_stopped"
                        stop_reason_detail = f"tool call skipped: session stopped — {reason}"
                    break

        synthetic = ToolResult.fail(
            stop_reason_code,
            stop_reason_detail,
            retryable=True,
        )
        # Rebuild as a SessionRun so the stop signal survives padding —
        # a bare tuple here would silently drop `.stop` and re-open S6-F4
        # for any code reading it after this point.
        turn_results = SessionRun(
            results=(*turn_results.results, *([synthetic] * missing)),
            stop=turn_results.stop,
        )
        # Record synthetic tool results in the audit trail so
        # replay sees a complete paired ``tool_call`` / ``tool_result``
        # row set per ADR-7 §10 Acceptance criterion 8.
        start = len(turn_results) - missing
        for call, result in zip(tool_calls[start:], turn_results[start:], strict=False):
            state.record_tool_call(call)
            state.record_tool_result(call, result)
    return turn_results


def _handle_terminal_tool_stop(stop: StopInfo | None, *, state: SessionState, output: EventBus | None) -> bool:
    """Handle only session-terminal tool stops; turn-local stops continue to padding."""
    if stop is None:
        return False
    if stop.point == LifecyclePoint.AFTER_TOOL_EXEC.value:
        if output is not None:
            output.emit(OutputEvent(type="hook_deny", data={"point": stop.point, "reason": stop.reason}))
    elif stop.point == LifecyclePoint.BETWEEN_ROUNDS.value and stop.reason.startswith(LOOP_GUARD_REASON_PREFIX):
        if output is not None:
            output.emit(OutputEvent(type="hook_deny", data={"point": stop.point, "reason": stop.reason}))
    else:
        return False
    state.observations.append(f"run stopped at {stop.point}: {stop.reason}")
    return True


def _failed_tool_names(calls: Sequence[ToolCall], results: Sequence[ToolResult]) -> set[str]:
    """Trusted call/result pairing, including hook denials; never parse model text."""
    return {call.name for call, result in zip(calls, results, strict=False) if result.error is not None}


def prepare_continuing_tool_results(
    tool_calls: tuple[ToolCall, ...],
    turn_results: SessionRun,
    *,
    state: SessionState,
    log: EventLog,
    log_len_before: int,
    limits: RuntimeLimits,
    role: str,
    output: EventBus | None,
) -> SessionRun:
    """Announce a turn-local cap and pad only after terminal-stop handling."""
    # S14b.2 (CT-2): iteration-cap stops are turn-local — emit the
    # operator-visible signal but DO NOT break the session loop (the
    # model gets the synthetic-failure padding below and may continue
    # next turn). Guard denials above remain session-terminal.
    if turn_results.stop is not None and turn_results.stop.point == "iteration_cap":
        if output is not None:
            output.emit(
                OutputEvent(
                    type="iteration_cap",
                    data={
                        "point": turn_results.stop.point,
                        "reason": turn_results.stop.reason,
                        "profile": role,
                    },
                )
            )

    turn_results = _pad_unexecuted_tool_results(
        tool_calls, turn_results, state=state, log=log, log_len_before=log_len_before, limits=limits
    )
    return turn_results


def append_tool_turn_messages(
    tool_calls: tuple[ToolCall, ...],
    turn_results: SessionRun,
    *,
    exhausted_flag: bool,
    log: EventLog,
    output: EventBus | None,
    turn: int,
    max_turns: int,
    registry: ToolRegistry,
    conversation_history: list[dict[str, Any]],
    redactor: SecretRedactor | None,
    artifact_store: ArtifactStore,
) -> bool:
    """Latch exhaustion and emit/project the paired results in their original order."""
    # S10 / CT6 (SA-2): a workflow_budget_exhausted denial latches the
    # terminal "exhausted" observation so the next request carries it.
    if not exhausted_flag:
        for result in turn_results:
            if result.error is not None and getattr(result.error, "code", "") == "workflow_budget_exhausted":
                exhausted_flag = True
                if log is not None:
                    log.append(actor="harness", kind="expansion_exhausted", content={"turn": turn})
                # S10.9 / CT-H4: console mirror (dual-write contract).
                if output is not None:
                    output.emit(
                        OutputEvent(
                            type="expansion_exhausted",
                            turn=turn,
                            max_turns=max_turns,
                            data={"turn": turn},
                        )
                    )
                break
    for call, result in zip(tool_calls, turn_results, strict=True):
        # ── Output: tool_call ──────────────────────────────────────────
        if output is not None:
            output.emit(
                OutputEvent(
                    type="tool_call",
                    turn=turn,
                    max_turns=max_turns,
                    data={
                        "tool": call.name,
                        "params": dict(call.params),
                        "summary": result.summary,
                        "ok": result.error is None,
                        "error": result.error.message if result.error else None,
                    },
                )
            )
        spec = _projection_spec_for_call(registry, call)
        conversation_history.append(
            {
                "role": "tool",
                "tool_call_id": call.call_id,
                "content": _redact(redactor, project_for_model(spec, result, artifact_store)),
            }
        )
    return exhausted_flag
