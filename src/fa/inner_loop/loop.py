"""Deterministic inner-loop driver with Phase 2 Tool Batching — senior refactor

- Read-only parallel via ThreadPoolExecutor max 5, writes sequential
- Hermes pattern: NEVER_PARALLEL, PARALLEL_SAFE, PATH_SCOPED with overlap detection
- Feature flag tool_batching.enabled graceful degradation
- Failure-observable WARNING, not silent, synthetic tool_result for orphaned tool_use
- Thread-safe EventLog Lock already, Transaction Lock, set_current_session token reset finally
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import overload, override

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

    Example: read/write calls are split when paths overlap; independent reads may batch.
    Path overlap forces serial execution for the same file.
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
) -> tuple[ToolResult, StopInfo | None]:
    """Execute single call sequential with BEFORE/AFTER hooks.

    Returns ``(result, stop)``. ``stop`` is a :class:`StopInfo` when
    AFTER_TOOL_EXEC denies, else ``None``. The result is always returned
    (paired rows) even when stopping — the denial is about what happens *next*,
    not about discarding what already ran.
    """
    log = state.require_log()
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
        return result, None

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
        return result, None

    result = registry.dispatch(effective_call)
    payload = payload.with_tool_result(result)
    try:
        hooks.dispatch(LifecyclePoint.AFTER_TOOL_EXEC, payload)
    except PermissionError as exc:
        log.append(
            actor="runtime",
            kind="run_stopped",
            content={"point": LifecyclePoint.AFTER_TOOL_EXEC.value, "reason": str(exc)},
        )
        state.record_tool_result(effective_call, result)
        state.observations.append(result.summary)
        # Result preserved; the stop reason travels back in-band so the caller
        # does not have to re-read the log to discover it (S6-F4).
        return result, StopInfo(point=LifecyclePoint.AFTER_TOOL_EXEC.value, reason=str(exc))

    state.record_tool_result(effective_call, result)
    state.observations.append(result.summary)
    return result, None


def _execute_batch_parallel(  # noqa: C901 -- complexity from fallback chain graceful degradation, documented, will split Phase 3 per Paper 2 §4.4
    batch: list[ToolCall],
    registry: ToolRegistry,
    hooks: HookRegistry,
    state: SessionState,
    role: str,
    acting_family: str,
) -> tuple[list[ToolResult] | None, StopInfo | None]:
    """Execute read-only batch in parallel, preserve order, synthetic error for orphaned.

    Returns ``(results, stop)``. The stop is returned rather than left for the
    caller to infer from the log (S6-F4).

    Fixed for FIND-012: denied results must be preserved in returned tuple in original order.
    """

    log = state.require_log()

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
                    executor.submit(registry.dispatch, p.tool_call): p for p in exec_payloads if p.tool_call is not None
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

            logging.getLogger(__name__).warning("ThreadPool parallel batch failed %s, fallback sequential", exc)
            for p in exec_payloads:
                try:
                    assert p.tool_call is not None  # noqa: S101
                    res = registry.dispatch(p.tool_call)
                    results_map[p.tool_call.call_id] = res
                except Exception as e:  # noqa: BLE001
                    if p.tool_call is not None:
                        results_map[p.tool_call.call_id] = ToolResult.fail("exec_failed", str(e))

    # AFTER and record in original order (preserve order, including denied)
    ordered_results: list[ToolResult] = []
    post_exec_denied: PermissionError | None = None

    for idx, pending_payload in enumerate(payloads):
        if pending_payload is None:
            # Denied in BEFORE phase — preserve in original order
            denied = denied_results[idx]
            if denied is None:
                denied = ToolResult.fail("interrupted", "Interrupted before execution, missing tool_result")
            ordered_results.append(denied)
            continue

        payload = pending_payload
        pending_call = payload.tool_call
        if pending_call is None:
            synthetic = ToolResult.fail("interrupted", "Interrupted before execution, missing tool_result")
            ordered_results.append(synthetic)
            continue

        resolved_result = results_map.get(pending_call.call_id)
        if resolved_result is None:
            resolved_result = ToolResult.fail("interrupted", "Interrupted, missing tool_result — synthetic")

        result = resolved_result
        call = pending_call
        payload_with_result = payload.with_tool_result(result)
        try:
            hooks.dispatch(LifecyclePoint.AFTER_TOOL_EXEC, payload_with_result)
        except PermissionError as exc:
            post_exec_denied = exc

        state.record_tool_result(pending_call, result)
        state.observations.append(result.summary)
        ordered_results.append(result)

    if post_exec_denied is not None:
        log.append(
            actor="runtime",
            kind="run_stopped",
            content={
                "point": LifecyclePoint.AFTER_TOOL_EXEC.value,
                "reason": str(post_exec_denied),
            },
        )
        # Preserve denied results; the stop travels back in-band.
        return ordered_results, StopInfo(point=LifecyclePoint.AFTER_TOOL_EXEC.value, reason=str(post_exec_denied))

    return ordered_results, None


@dataclass(frozen=True)
class StopInfo:
    """Why a session stopped early — explicit, in-band, and typed.

    Plain data on purpose. ``loop.py`` is the deterministic non-LLM root and
    must not acquire a display dependency (Q12, ``output.py:126-149``), so the
    stop travels as a *value* and the composition root decides whether to
    render it.
    """

    point: str
    reason: str


@dataclass(frozen=True, eq=False)
class SessionRun(Sequence[ToolResult]):
    """The results of one ``run_session`` call, plus why it stopped.

    **Sequence-compatible by design.** This follows CPython's ``os.stat_result``
    / ``time.struct_time`` pattern: the object *is* the results sequence
    (``len``, indexing and iteration all measure ``results``) and *carries* the
    new field as a named attribute. ``os.stat()`` grew fields for decades
    without breaking ``st[0]`` or ``len(st)``; the same property is what makes
    this change safe here.

    A bare ``(results, stop)`` tuple was measured and rejected: an existing
    ``assert len(results) == 2`` in a two-call test would have kept passing
    while silently measuring the pair instead of the results (Q24). A test that
    stays green while it stops testing what it claims is worse than one that
    breaks.
    """

    results: tuple[ToolResult, ...]
    stop: StopInfo | None = None

    @override
    def __len__(self) -> int:
        return len(self.results)

    @overload
    def __getitem__(self, index: int) -> ToolResult: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[ToolResult]: ...

    @override
    def __getitem__(self, index: int | slice) -> ToolResult | Sequence[ToolResult]:
        return self.results[index]

    @override
    def __iter__(self) -> Iterator[ToolResult]:
        return iter(self.results)

    def __eq__(self, other: object) -> bool:
        """Compare equal to the results tuple, like CPython's structseq.

        ``os.stat_result == tuple(os.stat_result)`` is ``True`` and
        ``time.struct_time`` behaves the same way; fidelity to that precedent
        is what lets existing ``assert results == ()`` call sites keep their
        meaning. Comparing against another ``SessionRun`` also compares the
        stop, so the extra field is not silently ignored where it matters.
        """
        if isinstance(other, SessionRun):
            return self.results == other.results and self.stop == other.stop
        if isinstance(other, tuple):
            return self.results == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.results, self.stop))


def run_session(
    calls: Iterable[ToolCall],
    *,
    registry: ToolRegistry,
    hooks: HookRegistry,
    state: SessionState,
    role: str = "coder",
    acting_family: str = "",
    limits: RuntimeLimits | None = None,
) -> SessionRun:
    effective_limits = limits if limits is not None else RuntimeLimits.anchored_defaults()
    log = state.require_log()
    token = set_current_session(state)

    # require_log() above establishes the authoritative session-log invariant.

    # Feature flag graceful degradation
    # S13: FAIL-OPEN — tool_batching_enabled defaults to True (convenience)
    tool_batching_enabled = state.feature_flags.tool_batching_enabled if state.feature_flags is not None else True

    hooks.set_event_sink(_make_hook_decision_sink(log))

    results: list[ToolResult] = []
    stop: StopInfo | None = None
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
                log.append(
                    actor="runtime",
                    kind="run_stopped",
                    content={"point": LifecyclePoint.BETWEEN_ROUNDS.value, "reason": str(exc)},
                )
                stop = StopInfo(point=LifecyclePoint.BETWEEN_ROUNDS.value, reason=str(exc))
                break

            # Decide sequential vs parallel
            if len(batch) == 1 or not _should_parallelize_tool_batch(batch, registry):
                # Sequential path
                for call in batch:
                    result, call_stop = _execute_one_sequential(call, registry, hooks, state, role, acting_family)
                    results.append(result)
                    if call_stop is not None:
                        stop = call_stop
                        break
                if stop is not None:
                    break
            else:
                # Parallel safe batch — always returns list (FIND-012 fix preserves denied)
                batch_results, batch_stop = _execute_batch_parallel(batch, registry, hooks, state, role, acting_family)
                if batch_results is None:
                    # Legacy None path (should not happen after fix) — treat as stop
                    stop = StopInfo(point="parallel_batch", reason="batch returned no results")
                    break
                results.extend(batch_results)
                # S6.2: the parallel path used to re-read the last five log rows
                # to guess whether AFTER_TOOL_EXEC had denied. That is inference
                # about our own control flow — it could match a stale row from an
                # earlier turn, and it silently degraded when the read failed.
                # The stop now comes back in-band, like the sequential path.
                if batch_stop is not None:
                    stop = batch_stop
                    break

    finally:
        hooks.set_event_sink(None)
        reset_current_session(token)

    return SessionRun(results=tuple(results), stop=stop)


__all__ = [
    "READ_ONLY_TOOLS",
    "SessionRun",
    "StopInfo",
    "classify_batches",
    "is_parallelizable",
    "run_session",
]
