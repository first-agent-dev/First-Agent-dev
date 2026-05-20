from __future__ import annotations

import logging
from collections.abc import Mapping
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


class Middleware:
    name = ""
    attaches_to: tuple[LifecyclePoint, ...] = ()
    uses_llm = False
    attaches_to_role = ""
    family = ""

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
    def __init__(self) -> None:
        self._chains: dict[LifecyclePoint, list[Middleware]] = {
            point: [] for point in LifecyclePoint
        }
        self.dispatch_trace: list[DispatchRecord] = []
        self._registered: set[int] = set()

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
        for middleware in self._chains[point]:
            if isinstance(middleware, GuardMiddleware):
                decision = middleware.handle(point, current)
                self.dispatch_trace.append(
                    DispatchRecord(
                        middleware=middleware.middleware_name,
                        point=point,
                        decision=decision.action,
                        reason=decision.reason,
                    )
                )
                if decision.action == "allow":
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
                    continue
                raise RuntimeError(f"unknown hook decision: {decision.action}")

            if isinstance(middleware, ObserverMiddleware):
                try:
                    middleware.observe(point, current)
                    self.dispatch_trace.append(
                        DispatchRecord(
                            middleware=middleware.middleware_name,
                            point=point,
                            decision="observed",
                        )
                    )
                except Exception as exc:  # pragma: no cover - log branch asserted by trace.
                    LOGGER.debug(
                        "observer middleware failed: %s",
                        middleware.middleware_name,
                        exc_info=exc,
                    )
                    self.dispatch_trace.append(
                        DispatchRecord(
                            middleware=middleware.middleware_name,
                            point=point,
                            decision="observer_error_swallowed",
                            reason=str(exc),
                        )
                    )
                continue

            raise TypeError(f"unsupported middleware type: {type(middleware).__name__}")
        return current

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
    "HookPayload",
    "HookRegistry",
    "LifecyclePoint",
    "Middleware",
    "ObserverMiddleware",
]
