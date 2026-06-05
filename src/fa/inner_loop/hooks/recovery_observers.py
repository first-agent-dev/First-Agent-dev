"""Wave-2 R-3 + R-6 observers: classify failures + log attempts.

Both are :class:`ObserverMiddleware` so a failure in either never blocks
tool execution. They run at ``AFTER_TOOL_EXEC`` where the
:class:`ToolResult` is already available on the payload.

- :class:`FailureClassifierObserver` (R-3): calls
  :func:`fa.inner_loop.recovery.classify.classify_result` and emits a
  ``kind="recovery_action"`` row to ``events.jsonl``.
- :class:`AttemptHistoryObserver` (R-6): appends a row to
  ``attempt_history.json`` so the future coder-recovery prompt can read
  it before the next retry.

Both observers receive an :class:`fa.inner_loop.state.EventLog` (or
``None`` for tests that do not need event projection) and the
:class:`AttemptHistory` to write into. They are intentionally tiny —
the work lives in the recovery module.
"""

from __future__ import annotations

import logging
from typing import Any, override

from fa.inner_loop.hooks.base import (
    HookPayload,
    LifecyclePoint,
    ObserverMiddleware,
)
from fa.inner_loop.recovery.attempt_history import (
    AttemptHistory,
    canonical_params_hash,
)
from fa.inner_loop.recovery.classify import RecoveryAction, classify_result
from fa.inner_loop.state import EventLog

LOGGER = logging.getLogger(__name__)


class FailureClassifierObserver(ObserverMiddleware):
    """Emit a ``recovery_action`` event for every failed tool result.

    On success → no event. On failure → one ``recovery_action`` row
    with the category, kind, target, and reason. The loop driver
    (future ``fa run``) reads these rows to surface category +
    action to the coder role and to the HANDOFF.md / hot.md projection.
    """

    name = "FailureClassifierObserver"
    attaches_to = (LifecyclePoint.AFTER_TOOL_EXEC,)

    def __init__(self, *, event_log: EventLog | None = None) -> None:
        self._event_log = event_log
        # Tests / callers that want the in-memory classification trail
        # without an EventLog read this directly.
        self.recent_actions: list[RecoveryAction] = []

    @override
    def observe(self, point: LifecyclePoint, payload: HookPayload) -> None:
        if point is not LifecyclePoint.AFTER_TOOL_EXEC:
            return
        result = payload.tool_result
        if result is None or result.error is None:
            return
        target = payload.tool_call.name if payload.tool_call is not None else ""
        action = classify_result(result, target=target)
        if action is None:
            return
        self.recent_actions.append(action)
        if self._event_log is None:
            return
        content: dict[str, Any] = {
            "category": action.category.value,
            "action": action.kind.value,
            "target": action.target,
            "reason": action.reason,
            "retryable": action.retryable,
            "error_code": result.error.code,
        }
        self._event_log.append(
            actor="hook",
            kind="recovery_action",
            content=content,
            tool_name=target,
            tool_call_id=payload.tool_call.call_id if payload.tool_call is not None else "",
        )


class AttemptHistoryObserver(ObserverMiddleware):
    """Append one row to ``attempt_history.json`` per failed tool call.

    Successful calls are NOT recorded — the coder-recovery prompt only
    cares about failures so the file size stays bounded and the reader
    table stays signal-only. ``time_source`` is injectable for tests.
    """

    name = "AttemptHistoryObserver"
    attaches_to = (LifecyclePoint.AFTER_TOOL_EXEC,)

    def __init__(
        self,
        history: AttemptHistory,
        *,
        time_source: object | None = None,
    ) -> None:
        self._history = history
        # ``time_source`` accepts any callable returning a float, or
        # ``None`` to fall through to ``time.time()`` inside
        # :meth:`AttemptHistory.append`.
        self._time_source = time_source

    @override
    def observe(self, point: LifecyclePoint, payload: HookPayload) -> None:
        if point is not LifecyclePoint.AFTER_TOOL_EXEC:
            return
        if payload.tool_call is None or payload.tool_result is None:
            return
        result = payload.tool_result
        if result.error is None:
            return
        action = classify_result(result, target=payload.tool_call.name)
        if action is None:
            return
        ts: float | None
        if self._time_source is None:
            ts = None
        else:
            try:
                ts = float(self._time_source())  # type: ignore[operator]
            except (TypeError, ValueError):
                ts = None
        self._history.append(
            tool_name=payload.tool_call.name,
            params_hash=canonical_params_hash(payload.tool_call.name, payload.tool_call.params),
            error_code=result.error.code,
            error_message=result.error.message,
            recovery_action=action.kind.value,
            recovery_category=action.category.value,
            ts=ts,
        )
