from __future__ import annotations

from typing import override

import pytest

from fa.inner_loop import ToolCall
from fa.inner_loop.hooks import (
    Decision,
    GuardMiddleware,
    HookPayload,
    HookRegistry,
    LifecyclePoint,
    ObserverMiddleware,
)


class RecordingGuard(GuardMiddleware):
    attaches_to = (LifecyclePoint.BEFORE_TOOL_EXEC,)

    def __init__(self, name: str, calls: list[str]) -> None:
        self.name = name
        self.calls = calls

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point, payload
        self.calls.append(self.name)
        return Decision.allow()


class DenyGuard(GuardMiddleware):
    name = "deny"
    attaches_to = (LifecyclePoint.BEFORE_TOOL_EXEC,)

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point, payload
        return Decision.deny("blocked")


class ModifyGuard(GuardMiddleware):
    name = "modify"
    attaches_to = (LifecyclePoint.BEFORE_TOOL_EXEC,)

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point
        assert payload.tool_call is not None
        return Decision.modify(
            payload.with_tool_call(
                ToolCall(
                    name=payload.tool_call.name,
                    params={"path": "changed"},
                    call_id=payload.tool_call.call_id,
                )
            )
        )


class ExplodingObserver(ObserverMiddleware):
    name = "boom"
    attaches_to = (LifecyclePoint.AFTER_TOOL_EXEC,)

    @override
    def observe(self, point: LifecyclePoint, payload: HookPayload) -> None:
        del point, payload
        raise RuntimeError("observer failed")


class LlmGuard(GuardMiddleware):
    name = "llm"
    attaches_to = (LifecyclePoint.BEFORE_TOOL_EXEC,)
    uses_llm = True
    family = "qwen"

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point, payload
        return Decision.allow()


def test_hook_registry_preserves_registration_order() -> None:
    calls: list[str] = []
    registry = HookRegistry()
    registry.register(RecordingGuard("first", calls))
    registry.register(RecordingGuard("second", calls))

    registry.dispatch(
        LifecyclePoint.BEFORE_TOOL_EXEC,
        HookPayload(tool_call=ToolCall(name="fs.read_file", params={"path": "README.md"})),
    )

    assert calls == ["first", "second"]


def test_first_deny_short_circuits_chain() -> None:
    calls: list[str] = []
    registry = HookRegistry()
    registry.register(DenyGuard())
    registry.register(RecordingGuard("after", calls))

    with pytest.raises(PermissionError, match="blocked"):
        registry.dispatch(
            LifecyclePoint.BEFORE_TOOL_EXEC,
            HookPayload(tool_call=ToolCall(name="fs.write_file", params={"path": "x"})),
        )

    assert calls == []
    assert registry.dispatch_trace[-1].decision == "deny"


def test_observer_errors_are_swallowed() -> None:
    registry = HookRegistry()
    registry.register(ExplodingObserver())

    payload = HookPayload(tool_call=ToolCall(name="fs.read_file", params={"path": "README.md"}))
    returned = registry.dispatch(LifecyclePoint.AFTER_TOOL_EXEC, payload)

    assert returned == payload
    assert registry.dispatch_trace[-1].decision == "observer_error_swallowed"


def test_double_mutation_is_hard_error() -> None:
    registry = HookRegistry()
    registry.register(ModifyGuard())
    registry.register(ModifyGuard())

    with pytest.raises(RuntimeError, match="hook_double_mutation"):
        registry.dispatch(
            LifecyclePoint.BEFORE_TOOL_EXEC,
            HookPayload(tool_call=ToolCall(name="fs.read_file", params={"path": "README.md"})),
        )


def test_family_disjoint_rejection_for_llm_using_middleware() -> None:
    registry = HookRegistry()

    with pytest.raises(ValueError, match="disjoint"):
        registry.register(LlmGuard(), acting_family="qwen")
