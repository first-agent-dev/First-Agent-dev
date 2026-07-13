"""Deterministic inner-loop driver with Phase 2 Tool Batching (ADR-7 §1 + ADR-8 §1 + ADR-14/15).

run_session executes batches of ToolCall through hooks and registry.
- Read-only parallel via ThreadPoolExecutor max 5 (Pillar 3)
- Writes sequential
- EventLog Lock already thread-safe for parallel log write sequential
- Feature flag tool_batching.enabled controls parallel vs sequential fallback
- Failure-observable WARNING, not silent
"""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

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


READ_ONLY_TOOLS = {
    "fs.glob",
    "fs.grep",
    "fs.read_file",
    "fs.instant_grep",
    "fs.chronicle_search",
    "fs.usage",
    "fs.list_tasks",
    "fs.diff",
}


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


def is_parallelizable(call: ToolCall, registry: ToolRegistry) -> bool:
    """Phase 2: determine if tool call can be parallelized (read-only).

    - Permission read → parallelizable
    - Name in whitelist READ_ONLY_TOOLS
    - fs.run_bash always sequential for safety (may write), even if cat/ls
    """
    try:
        spec = registry.lookup(call.name)
        if spec is not None and getattr(spec, "permission", "") == "read":
            return True
    except Exception:
        pass

    if call.name in READ_ONLY_TOOLS:
        return True

    return False


def classify_batches(calls: list[ToolCall], registry: ToolRegistry) -> list[list[ToolCall]]:
    """Group consecutive read-only calls into batches, writes as single.

    Example: [glob, read, write, grep, read] -> [[glob,read], [write], [grep,read]]
    """
    batches: list[list[ToolCall]] = []
    current: list[ToolCall] = []

    for call in calls:
        if is_parallelizable(call, registry):
            current.append(call)
        else:
            if current:
                batches.append(current)
                current = []
            batches.append([call])

    if current:
        batches.append(current)

    return batches


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
    token = set_current_session(state)

    if state.log is None:
        raise ValueError("SessionState.log must be set before run_session")

    # Feature flag for tool batching — graceful degradation
    tool_batching_enabled = True
    try:
        if state.feature_flags is not None:
            tool_batching_enabled = getattr(state.feature_flags, "tool_batching_enabled", True)
    except Exception:
        tool_batching_enabled = True

    hooks.set_event_sink(_make_hook_decision_sink(state.log))

    results: list[ToolResult] = []
    calls_list = list(calls)

    # Classify into batches if batching enabled, else each call single batch sequential
    if tool_batching_enabled:
        batches = classify_batches(calls_list, registry)
    else:
        batches = [[c] for c in calls_list]

    try:
        for batch in batches:
            # Respect max_iterations as total tool calls, not batches
            if len(results) >= effective_limits.max_iterations:
                break
            # Truncate batch if would exceed max_iterations
            remaining = effective_limits.max_iterations - len(results)
            if len(batch) > remaining:
                batch = batch[:remaining]
                if not batch:
                    break

            # BETWEEN_ROUNDS once per batch (for reads) — session-level gate
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

            # Sequential write batch (single call, not parallelizable) — old path
            if len(batch) == 1 and not is_parallelizable(batch[0], registry):
                for call in batch:
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

                    state.record_tool_result(
                        effective_call if effective_call is not None else call, result
                    )
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

            else:
                # Parallel read-only batch
                payloads: list = []
                for call in batch:
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
                        # For denied in batch, skip execution, add to payloads with None tool_call?
                        # Instead, create a denied payload to keep paired rows intact
                        payloads.append(
                            HookPayload(tool_call=None, role=role, acting_family=acting_family)
                        )
                        continue
                    payloads.append(payload)

                # Execute tools in parallel
                # Filter payloads that have tool_call (not denied)
                exec_payloads = [p for p in payloads if p.tool_call is not None]

                results_map: dict[str, ToolResult] = {}
                if exec_payloads:
                    max_workers = min(5, len(exec_payloads))
                    try:
                        with ThreadPoolExecutor(max_workers=max_workers) as executor:
                            futures = {
                                executor.submit(registry.dispatch, p.tool_call): p
                                for p in exec_payloads
                                if p.tool_call is not None
                            }
                            for future in as_completed(futures):
                                p = futures[future]
                                try:
                                    res = future.result(timeout=30)
                                except Exception as exc:
                                    res = ToolResult.fail("exec_failed", f"Parallel exec failed: {exc}")
                                if p.tool_call is not None:
                                    results_map[p.tool_call.call_id] = res
                    except Exception as exc:
                        print(f"WARNING: ThreadPool parallel batch failed {exc}, fallback sequential")
                        # Fallback sequential
                        for p in exec_payloads:
                            try:
                                assert p.tool_call is not None
                                res = registry.dispatch(p.tool_call)
                                results_map[p.tool_call.call_id] = res
                            except Exception as e:
                                results_map[p.tool_call.call_id] = ToolResult.fail(
                                    "exec_failed", str(e)
                                )

                # AFTER and record in original order (preserve order, not completion order)
                post_exec_denied_global: PermissionError | None = None
                for payload in payloads:
                    call = payload.tool_call
                    if call is None:
                        continue
                    result = results_map.get(call.call_id)
                    if result is None:
                        # Denied earlier or failed to execute
                        continue

                    payload_with_result = payload.with_tool_result(result)
                    try:
                        hooks.dispatch(LifecyclePoint.AFTER_TOOL_EXEC, payload_with_result)
                    except PermissionError as exc:
                        post_exec_denied_global = exc

                    state.record_tool_result(call, result)
                    results.append(result)
                    state.observations.append(result.summary)

                if post_exec_denied_global is not None:
                    state.log.append(
                        actor="runtime",
                        kind="run_stopped",
                        content={
                            "point": LifecyclePoint.AFTER_TOOL_EXEC.value,
                            "reason": str(post_exec_denied_global),
                        },
                    )
                    break

    finally:
        hooks.set_event_sink(None)
        reset_current_session(token)

    return tuple(results)


__all__ = ["run_session", "is_parallelizable", "classify_batches", "READ_ONLY_TOOLS"]
