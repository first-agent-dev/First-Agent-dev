from __future__ import annotations

from collections.abc import Mapping

import pytest

from fa.inner_loop import ToolCall, ToolRegistry, ToolResult, ToolSpec


def _echo(params: Mapping[str, object]) -> ToolResult:
    return ToolResult.ok("echo", result=dict(params))


def test_registry_dispatches_registered_tool() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="test.echo",
            description="Echo params.",
            input_schema={"type": "object"},
            permission="read",
            handler=_echo,
        )
    )

    result = registry.dispatch(ToolCall(name="test.echo", params={"x": 1}))

    assert result.result == {"x": 1}
    assert registry.names() == ("test.echo",)


def test_registry_rejects_full_permission() -> None:
    with pytest.raises(ValueError, match="reserved"):
        ToolSpec(
            name="test.full",
            description="Future privileged tool.",
            input_schema={"type": "object"},
            permission="full",  # type: ignore[arg-type]
            handler=_echo,
        )


def test_registry_rejects_duplicate_tool_name() -> None:
    spec = ToolSpec(
        name="test.echo",
        description="Echo params.",
        input_schema={"type": "object"},
        permission="read",
        handler=_echo,
    )
    registry = ToolRegistry()
    registry.register(spec)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(spec)
