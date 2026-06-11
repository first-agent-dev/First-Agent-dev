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


def test_tool_spec_rejects_negative_context_budget() -> None:
    with pytest.raises(ValueError, match="max_context_bytes"):
        ToolSpec(
            name="test.bad_budget",
            description="Bad budget.",
            input_schema={"type": "object"},
            permission="read",
            handler=_echo,
            max_context_bytes=-1,
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


def test_register_rejects_malformed_schema() -> None:
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="invalid input_schema"):
        registry.register(
            ToolSpec(
                name="test.bad",
                description="Bad schema.",
                input_schema={"type": "strin"},  # typo
                permission="read",
                handler=_echo,
            )
        )


def test_validate_returns_invalid_params_on_type_mismatch() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="test.typed",
            description="Typed tool.",
            input_schema={"type": "object", "properties": {"text": {"type": "integer"}}},
            permission="read",
            handler=_echo,
        )
    )

    result = registry.dispatch(ToolCall(name="test.typed", params={"text": "not an int"}))

    assert result.error is not None
    assert result.error.code == "invalid_params"
    assert "text" in result.error.message
    assert result.error.retryable is True
