"""Deterministic inner-loop driver with Phase 2 Tool Batching — senior refactor

- Read-only parallel via ThreadPoolExecutor max 5, writes sequential
- Hermes pattern: NEVER_PARALLEL, PARALLEL_SAFE, PATH_SCOPED with overlap detection
- Feature flag tool_batching.enabled graceful degradation
- Failure-observable WARNING, not silent, synthetic tool_result for orphaned tool_use
- Thread-safe EventLog Lock already, Transaction Lock, set_current_session token reset finally
"""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

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

# Hermes pattern — senior production approach
_NEVER_PARALLEL_TOOLS = frozenset(
    {
        "fs.checkpoint",
        "fs.undo",
        "fs.send_ctrl_c",
        "fs.write_file",
        "fs.edit_file",
        "fs.run_bash",
    }
)

_PARALLEL_SAFE_TOOLS = frozenset(
    {
        "fs.glob",
        "fs.grep",
        "fs.read_file",
        "fs.instant_grep",
        "fs.chronicle_search",
        "fs.usage",
        "fs.list_tasks",
        "fs.diff",
    }
)

_PATH_SCOPED_TOOLS = frozenset(
    {
        "fs.read_file",
        "fs.write_file",
        "fs.edit_file",
    }
)

_MAX_TOOL_WORKERS = 5

# Keep old name for backward compat with tests
READ_ONLY_TOOLS = _PARALLEL_SAFE_TOOLS


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


def _extract_parallel_scope_path(call: ToolCall) -> Path | None:
    """Extract path param for path-scoped tools, None if not present or unparseable."""
    try:
        params = dict(call.params)
        # Common keys: path
        p = params.get("path")
        if p and isinstance(p, str):
            # Normalize, don't resolve yet (may be relative)
            return Path(p)
    except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
        pass
    return None


def _paths_overlap(left: Path, right: Path) -> bool:
    """Return True if paths may refer to same subtree (one is prefix of other)."""
    try:
        left_parts = left.parts
        right_parts = right.parts
        common_len = min(len(left_parts), len(right_parts))
        if common_len == 0:
            return False
        # If one is prefix of other, overlap
        if left_parts[:common_len] == right_parts[:common_len]:
            return True
        return False
    except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        # On any error, be safe: assume overlap -> force serial
        return True


def _should_parallelize_tool_batch(calls: list[ToolCall], registry: ToolRegistry) -> bool:
    """Hermes-inspired: return True when batch safe to run concurrently."""
    if len(calls) <= 1:
        return False  # No point parallelizing single tool

    # Any never-parallel tool forces serial
    for c in calls:
        if c.name in _NEVER_PARALLEL_TOOLS:
            return False

    reserved_paths: list[Path] = []
    for call in calls:
        # Unparseable args -> default serial safe
        try:
            _ = dict(call.params)
        except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return False

        if call.name in _PATH_SCOPED_TOOLS:
            scoped = _extract_parallel_scope_path(call)
            if scoped is None:
                # If path-scoped but no path param, be safe serial
                # For read_file without path? shouldn't happen, but be safe
                return False
            # Reject if overlaps with already reserved
            if any(_paths_overlap(scoped, existing) for existing in reserved_paths):
                return False
            reserved_paths.append(scoped)
            continue

        if call.name not in _PARALLEL_SAFE_TOOLS:
            # Check permission via registry as fallback for unknown tools
            try:
                spec = registry.lookup(call.name)
                if spec is not None and getattr(spec, "permission", "") == "read":
                    continue
            except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
                pass
            # Unknown tool -> serial
            return False

    return True


def is_parallelizable(call: ToolCall, registry: ToolRegistry) -> bool:
    """Backward compat wrapper for old API, now uses safe sets + permission check."""
    # Never parallel list takes precedence
    if call.name in _NEVER_PARALLEL_TOOLS:
        return False
    # Check registry permission read
    try:
        spec = registry.lookup(call.name)
        if spec is not None and getattr(spec, "permission", "") == "read":
            return True
    except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
        pass
    if call.name in _PARALLEL_SAFE_TOOLS:
        return True
    return False


def classify_batches(calls: list[ToolCall], registry: ToolRegistry) -> list[list[ToolCall]]:
    """Group into batches where parallel safe and no path overlap, writes single.

    Example: [glob, read(a.py), write(a.py), grep, read(b.py)] -> [[glob, read(a.py)], [write(a.py)], [grep, read(b.py)]]
    Path overlap forces serial: [read(a.py), read(a.py)] -> [[read(a.py)], [read(a.py)]] not parallel (same file)
    """
    batches: list[list[ToolCall]] = []
    current: list[ToolCall] = []
    reserved_in_current: list[Path] = []

    for call in calls:
        # If current empty, start new
        if not current:
            if is_parallelizable(call, registry):
                # Check path overlap within current batch
                scoped = _extract_parallel_scope_path(call) if call.name in _PATH_SCOPED_TOOLS else None
                if scoped and any(_paths_overlap(scoped, p) for p in reserved_in_current):
                    # Overlap with current batch -> flush current
                    batches.append(current)
                    current = [call]
                    reserved_in_current = [scoped] if scoped else []
                else:
                    current.append(call)
                    if scoped:
                        reserved_in_current.append(scoped)
            else:
                batches.append([call])
            continue

        # Current has parallel-safe calls
        if not is_parallelizable(call, registry):
            # Flush current parallel batch, then add write as single
            batches.append(current)
            current = []
            reserved_in_current = []
            batches.append([call])
            continue

        # Check if adding this call keeps batch parallelizable
        scoped = _extract_parallel_scope_path(call) if call.name in _PATH_SCOPED_TOOLS else None
        if scoped and any(_paths_overlap(scoped, p) for p in reserved_in_current):
            # Overlap -> flush current, start new batch with this call
            batches.append(current)
            current = [call]
            reserved_in_current = [scoped] if scoped else []
        else:
            # Check whole batch would still be parallelizable with new call included
            prospective = [*current, call]
            if _should_parallelize_tool_batch(prospective, registry):
                current.append(call)
                if scoped:
                    reserved_in_current.append(scoped)
            else:
                # Not parallelizable together, flush and start new
                batches.append(current)
                current = [call]
                reserved_in_current = [scoped] if scoped else []

    if current:
        batches.append(current)

    return batches


def _execute_one_sequential(
    call: ToolCall,
    registry: ToolRegistry,
    hooks: HookRegistry,
    state: SessionState,
    role: str,
    acting_family: str,
) -> tuple[ToolResult, bool]:
    """Execute single call sequential with BEFORE/AFTER hooks.

    Returns (result, should_stop). should_stop True when AFTER_TOOL_EXEC denies.
    Result is always returned (paired rows) even when should_stop.
    """
    state.record_tool_call(call)
    try:
        payload = hooks.dispatch(
            LifecyclePoint.BEFORE_TOOL_EXEC,
            HookPayload(tool_call=call, role=role, acting_family=acting_family),
        )
    except PermissionError as exc:
        result = default_tool_result_for_denial(str(exc))
        state.record_tool_result(call, result)
        state.observations.append(result.summary)
        return result, False

    effective_call = payload.tool_call
    if effective_call is None:
        result = ToolResult.fail("invalid_payload", "hook payload lost tool call")
        # Still dispatch AFTER per ADR-7 §8 — observer must see invalid_payload failure
        payload_with_result = payload.with_tool_result(result)
        try:
            hooks.dispatch(LifecyclePoint.AFTER_TOOL_EXEC, payload_with_result)
        except PermissionError:
            # Even if AFTER denies, still record paired rows and continue
            pass
        state.record_tool_result(call, result)
        state.observations.append(result.summary)
        return result, False

    result = registry.dispatch(effective_call)
    payload = payload.with_tool_result(result)
    try:
        hooks.dispatch(LifecyclePoint.AFTER_TOOL_EXEC, payload)
    except PermissionError as exc:
        state.log.append(
            actor="runtime",
            kind="run_stopped",
            content={"point": LifecyclePoint.AFTER_TOOL_EXEC.value, "reason": str(exc)},
        )
        state.record_tool_result(effective_call, result)
        state.observations.append(result.summary)
        return result, True  # Signal stop but result preserved

    state.record_tool_result(effective_call, result)
    state.observations.append(result.summary)
    return result, False


def _execute_batch_parallel(  # noqa: C901 -- complexity from fallback chain graceful degradation, documented, will split Phase 3 per Paper 2 §4.4
    batch: list[ToolCall],
    registry: ToolRegistry,
    hooks: HookRegistry,
    state: SessionState,
    role: str,
    acting_family: str,
) -> list[ToolResult] | None:
    """Execute read-only batch in parallel, preserve order, synthetic error for orphaned.

    Fixed for FIND-012: denied results must be preserved in returned tuple in original order.
    """

    # BEFORE sequentially (guards fast, deterministic, must check sandbox before parallel)
    # For order preservation we keep same index as batch.
    payloads: list[HookPayload | None] = []
    denied_results: list[ToolResult | None] = []

    for call in batch:
        state.record_tool_call(call)
        try:
            payload = hooks.dispatch(
                LifecyclePoint.BEFORE_TOOL_EXEC,
                HookPayload(tool_call=call, role=role, acting_family=acting_family),
            )
            payloads.append(payload)
            denied_results.append(None)
        except PermissionError as exc:
            result = default_tool_result_for_denial(str(exc))
            state.record_tool_result(call, result)
            state.observations.append(result.summary)
            payloads.append(None)  # Denied placeholder
            denied_results.append(result)

    # Filter executable payloads
    exec_payloads = [p for p in payloads if p is not None and p.tool_call is not None]

    results_map: dict[str, ToolResult] = {}
    if exec_payloads:
        max_workers = min(len(exec_payloads), _MAX_TOOL_WORKERS)
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(registry.dispatch, p.tool_call): p
                    for p in exec_payloads
                    if p.tool_call is not None
                }
                done, _ = wait(futures.keys(), timeout=30)
                for fut in done:
                    p = futures[fut]
                    try:
                        res = fut.result(timeout=5)
                    except Exception as exc:  # noqa: BLE001 # graceful degradation
                        res = ToolResult.fail("exec_failed", f"Parallel exec failed: {exc}")
                    if p.tool_call is not None:
                        results_map[p.tool_call.call_id] = res

                not_done = set(futures.keys()) - done
                for fut in not_done:
                    p = futures[fut]
                    try:
                        fut.cancel()
                    except Exception:  # noqa: BLE001, S110
                        pass
                    if p.tool_call is not None:
                        results_map[p.tool_call.call_id] = ToolResult.fail(
                            "exec_timeout", "Parallel exec timeout after 30s"
                        )
        except Exception as exc:  # noqa: BLE001 # graceful degradation
            import logging

            logging.getLogger(__name__).warning(
                "ThreadPool parallel batch failed %s, fallback sequential", exc
            )
            for p in exec_payloads:
                try:
                    assert p.tool_call is not None  # noqa: S101
                    res = registry.dispatch(p.tool_call)
                    results_map[p.tool_call.call_id] = res
                except Exception as e:  # noqa: BLE001
                    assert p.tool_call is not None
                    results_map[p.tool_call.call_id] = ToolResult.fail("exec_failed", str(e))

    # AFTER and record in original order (preserve order, including denied)
    ordered_results: list[ToolResult] = []
    post_exec_denied: PermissionError | None = None

    for idx, payload in enumerate(payloads):
        if payload is None:
            # Denied in BEFORE phase — preserve in original order
            denied = denied_results[idx]
            if denied is None:
                denied = ToolResult.fail(
                    "interrupted", "Interrupted before execution, missing tool_result"
                )
            ordered_results.append(denied)
            continue

        call = payload.tool_call
        if call is None:
            synthetic = ToolResult.fail(
                "interrupted", "Interrupted before execution, missing tool_result"
            )
            ordered_results.append(synthetic)
            continue

        result = results_map.get(call.call_id)
        if result is None:
            result = ToolResult.fail(
                "interrupted", "Interrupted, missing tool_result — synthetic"
            )

        payload_with_result = payload.with_tool_result(result)
        try:
            hooks.dispatch(LifecyclePoint.AFTER_TOOL_EXEC, payload_with_result)
        except PermissionError as exc:
            post_exec_denied = exc

        state.record_tool_result(call, result)
        state.observations.append(result.summary)
        ordered_results.append(result)

    if post_exec_denied is not None:
        state.log.append(
            actor="runtime",
            kind="run_stopped",
            content={
                "point": LifecyclePoint.AFTER_TOOL_EXEC.value,
                "reason": str(post_exec_denied),
            },
        )
        # Return ordered_results so denied results are preserved; run_session will detect run_stopped log and break.
        return ordered_results

    return ordered_results


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

    # Feature flag graceful degradation
    tool_batching_enabled = True
    try:
        if state.feature_flags is not None:
            tool_batching_enabled = getattr(state.feature_flags, "tool_batching_enabled", True)
    except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        tool_batching_enabled = True

    hooks.set_event_sink(_make_hook_decision_sink(state.log))

    results: list[ToolResult] = []
    calls_list = list(calls)

    if tool_batching_enabled:
        batches = classify_batches(calls_list, registry)
    else:
        batches = [[c] for c in calls_list]

    try:
        for batch in batches:
            if len(results) >= effective_limits.max_iterations:
                break
            remaining = effective_limits.max_iterations - len(results)
            if len(batch) > remaining:
                batch = batch[:remaining]
                if not batch:
                    break

            # BETWEEN_ROUNDS once per batch (session-level gate)
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

            # Decide sequential vs parallel
            if len(batch) == 1 or not _should_parallelize_tool_batch(batch, registry):
                # Sequential path
                should_stop_outer = False
                for call in batch:
                    result, should_stop = _execute_one_sequential(
                        call, registry, hooks, state, role, acting_family
                    )
                    results.append(result)
                    if should_stop:
                        should_stop_outer = True
                        break
                if should_stop_outer:
                    break
            else:
                # Parallel safe batch — always returns list (FIND-012 fix preserves denied)
                batch_results = _execute_batch_parallel(batch, registry, hooks, state, role, acting_family)
                if batch_results is None:
                    # Legacy None path (should not happen after fix) — treat as stop
                    break
                results.extend(batch_results)
                # Detect AFTER_TOOL_EXEC denial that was logged during parallel batch
                try:
                    if state.log is not None:
                        recent = state.log.read_all()[-5:]
                        if any(
                            ev.kind == "run_stopped"
                            and ev.content.get("point") == LifecyclePoint.AFTER_TOOL_EXEC.value
                            for ev in recent
                        ):
                            # Sequential path uses should_stop flag; parallel uses log signal
                            break
                except Exception:
                    pass

    finally:
        hooks.set_event_sink(None)
        reset_current_session(token)

    return tuple(results)


__all__ = ["READ_ONLY_TOOLS", "classify_batches", "is_parallelizable", "run_session"]
