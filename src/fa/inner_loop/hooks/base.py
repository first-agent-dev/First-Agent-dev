"""HookRegistry middleware chain (ADR-8) + lifecycle points (ADR-7 \u00a78).

Implements the five lifecycle points + Guard / Observer middleware
shape + first-deny short-circuit + one-mutation-per-dispatch rule +
family-disjoint LLM-using middleware check. ``HookRegistry.dispatch``
emits a ``DispatchRecord`` for every step; when ``event_sink`` is
provided, the registry also writes ``kind == "hook_decision"`` rows to
that sink (per [ADR-7 \u00a77](../../../knowledge/adr/ADR-7-inner-loop-tool-registry.md)
+ [ADR-8 \u00a73](../../../knowledge/adr/ADR-8-hook-registry.md)).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from fa.inner_loop.registry import ToolCall, ToolResult

LOGGER = logging.getLogger(__name__)


class LifecyclePoint(StrEnum):
    BETWEEN_ROUNDS = "BETWEEN_ROUNDS"
    BEFORE_LLM_CALL = "BEFORE_LLM_CALL"
    AFTER_LLM_CALL = "AFTER_LLM_CALL"
    BEFORE_TOOL_EXEC = "BEFORE_TOOL_EXEC"
    AFTER_TOOL_EXEC = "AFTER_TOOL_EXEC"


@dataclass(frozen=True)
class HookPayload:
    tool_call: ToolCall | None = None
    tool_result: ToolResult | None = None
    role: str = "coder"
    acting_family: str = ""
    context: Mapping[str, object] = field(default_factory=dict)

    def with_tool_call(self, tool_call: ToolCall) -> HookPayload:
        return HookPayload(
            tool_call=tool_call,
            tool_result=self.tool_result,
            role=self.role,
            acting_family=self.acting_family,
            context=self.context,
        )

    def with_tool_result(self, tool_result: ToolResult) -> HookPayload:
        return HookPayload(
            tool_call=self.tool_call,
            tool_result=tool_result,
            role=self.role,
            acting_family=self.acting_family,
            context=self.context,
        )


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str = ""
    payload: HookPayload | None = None

    @classmethod
    def allow(cls) -> Decision:
        return cls(action="allow")

    @classmethod
    def deny(cls, reason: str) -> Decision:
        if not reason:
            raise ValueError("deny reason is required")
        return cls(action="deny", reason=reason)

    @classmethod
    def modify(cls, payload: HookPayload) -> Decision:
        return cls(action="modify", payload=payload)


@dataclass(frozen=True)
class DispatchRecord:
    middleware: str
    point: LifecyclePoint
    decision: str
    reason: str = ""


HookDecisionSink = Callable[[DispatchRecord, HookPayload], None]


class Middleware:
    name = ""
    attaches_to: tuple[LifecyclePoint, ...] = ()
    uses_llm = False
    attaches_to_role = ""
    family = ""
    # ADR-7 \u00a78 \u00abRe-entry after modify_params\u00bb is the general exception
    # to ADR-8 \u00a73 \u00abalready-run hooks 1..N-1 do not re-run\u00bb: the
    # sandbox check MUST re-run against the mutated payload. Middlewares
    # set this flag to opt in to that re-run; ``HookRegistry.dispatch``
    # replays them once after each ``Decision.modify``.
    revalidates_after_modify = False

    @property
    def middleware_name(self) -> str:
        return self.name or type(self).__name__


class GuardMiddleware(Middleware):
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        raise NotImplementedError


class ObserverMiddleware(Middleware):
    def observe(self, point: LifecyclePoint, payload: HookPayload) -> None:
        raise NotImplementedError


class HookRegistry:
    """Per-process middleware registry; one instance lives on the loop driver.

    Order of registration === order of execution; the registry does not
    auto-sort. ``dispatch`` runs the chain for ``point``, applies
    Guard ``deny``/``modify`` semantics, swallows Observer errors at
    DEBUG, and (if ``event_sink`` is provided at construction) emits a
    ``kind == "hook_decision"`` row for every step \u2014 the durable trace
    projection mandated by ADR-7 \u00a77.
    """

    def __init__(self, *, event_sink: HookDecisionSink | None = None) -> None:
        self._chains: dict[LifecyclePoint, list[Middleware]] = {
            point: [] for point in LifecyclePoint
        }
        self.dispatch_trace: list[DispatchRecord] = []
        self._registered: set[int] = set()
        self._event_sink = event_sink

    def set_event_sink(self, sink: HookDecisionSink | None) -> None:
        """Attach (or detach) an ``events.jsonl`` sink for hook_decision rows."""
        self._event_sink = sink

    def register(self, middleware: Middleware, *, acting_family: str = "") -> None:
        self._validate_middleware(middleware, acting_family=acting_family)
        identity = id(middleware)
        if identity in self._registered:
            return
        self._registered.add(identity)
        for point in middleware.attaches_to:
            self._chains[point].append(middleware)

    def dispatch(self, point: LifecyclePoint, payload: HookPayload) -> HookPayload:
        current = payload
        mutated = False
        run_index = 0
        chain = self._chains[point]
        while run_index < len(chain):
            middleware = chain[run_index]
            if isinstance(middleware, GuardMiddleware):
                decision = middleware.handle(point, current)
                self._record(
                    DispatchRecord(
                        middleware=middleware.middleware_name,
                        point=point,
                        decision=decision.action,
                        reason=decision.reason,
                    ),
                    current,
                )
                if decision.action == "allow":
                    run_index += 1
                    continue
                if decision.action == "deny":
                    raise PermissionError(decision.reason)
                if decision.action == "modify":
                    if mutated:
                        raise RuntimeError("hook_double_mutation")
                    if decision.payload is None:
                        raise RuntimeError("hook_modify_without_payload")
                    mutated = True
                    current = decision.payload
                    # ADR-7 \u00a78 sandbox-re-check exception: replay any
                    # already-run guards with ``revalidates_after_modify =
                    # True`` against the mutated payload before continuing
                    # the chain. One mutation per dispatch (above) still
                    # caps the worst-case work.
                    for replayed in chain[:run_index]:
                        if not isinstance(replayed, GuardMiddleware):
                            continue
                        if not replayed.revalidates_after_modify:
                            continue
                        replay_decision = replayed.handle(point, current)
                        self._record(
                            DispatchRecord(
                                middleware=f"{replayed.middleware_name}@replay",
                                point=point,
                                decision=replay_decision.action,
                                reason=replay_decision.reason,
                            ),
                            current,
                        )
                        if replay_decision.action == "deny":
                            raise PermissionError(replay_decision.reason)
                        if replay_decision.action == "modify":
                            # Replays may not introduce a second mutation.
                            raise RuntimeError("hook_double_mutation")
                    run_index += 1
                    continue
                raise RuntimeError(f"unknown hook decision: {decision.action}")

            if isinstance(middleware, ObserverMiddleware):
                try:
                    middleware.observe(point, current)
                    self._record(
                        DispatchRecord(
                            middleware=middleware.middleware_name,
                            point=point,
                            decision="observed",
                        ),
                        current,
                    )
                # pylint: disable-next=broad-exception-caught
                except Exception as exc:  # pragma: no cover - log branch asserted by trace.
                    LOGGER.debug(
                        "observer middleware failed: %s",
                        middleware.middleware_name,
                        exc_info=exc,
                    )
                    self._record(
                        DispatchRecord(
                            middleware=middleware.middleware_name,
                            point=point,
                            decision="observer_error_swallowed",
                            reason=str(exc),
                        ),
                        current,
                    )
                run_index += 1
                continue

            raise TypeError(f"unsupported middleware type: {type(middleware).__name__}")
        return current

    def _record(self, record: DispatchRecord, payload: HookPayload) -> None:
        self.dispatch_trace.append(record)
        if self._event_sink is None:
            return
        try:
            self._event_sink(record, payload)
        # pylint: disable-next=broad-exception-caught
        except Exception as exc:  # pragma: no cover - sink failure must not break runtime.
            LOGGER.debug("hook_decision sink failed: %s", exc, exc_info=exc)

    def _validate_middleware(self, middleware: Middleware, *, acting_family: str) -> None:
        is_guard = isinstance(middleware, GuardMiddleware)
        is_observer = isinstance(middleware, ObserverMiddleware)
        if is_guard == is_observer:
            raise TypeError("middleware must subclass exactly one middleware base")
        if not middleware.attaches_to:
            raise ValueError("middleware must attach to at least one lifecycle point")
        if middleware.uses_llm:
            family = middleware.family
            if not family:
                raise ValueError("LLM-using middleware must declare family")
            if acting_family and family == acting_family:
                raise ValueError("LLM-using middleware family must be disjoint")


__all__ = [
    "Decision",
    "DispatchRecord",
    "GuardMiddleware",
    "HookDecisionSink",
    "HookPayload",
    "HookRegistry",
    "LifecyclePoint",
    "Middleware",
    "ObserverMiddleware",
]
