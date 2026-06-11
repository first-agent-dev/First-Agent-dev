"""Tests for fa.inner_loop.prompt — A-bucket residue determinism guards.

The prompt module is deep-dive §3 I-2 A-bucket residue: pure
deterministic functions whose output must be byte-stable for given
inputs. These tests pin that invariant.
"""

from __future__ import annotations

from fa.inner_loop.prompt import (
    CODER_SYSTEM_PROMPT,
    build_system_message,
    build_system_message_from_role,
    render_tool_specs,
)
from fa.inner_loop.registry import ToolSpec


def _make_spec(name: str = "echo") -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"echo tool ({name})",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        handler=lambda call: None,  # type: ignore[arg-type,return-value]
        permission="read",
    )


def test_build_system_message_with_no_extra_returns_canonical_prompt() -> None:
    assert build_system_message() == CODER_SYSTEM_PROMPT
    assert build_system_message("") == CODER_SYSTEM_PROMPT


def test_build_system_message_appends_extra_after_blank_line() -> None:
    message = build_system_message("workspace: /tmp/wk")
    assert message.startswith(CODER_SYSTEM_PROMPT)
    assert message.endswith("workspace: /tmp/wk")
    assert "\n\n## Previous Work Log\nworkspace: /tmp/wk" in message


def test_build_system_message_with_role_uses_role_prompt() -> None:
    message = build_system_message(role="planner")
    assert "You are the First-Agent planner" in message
    assert message.startswith("You are the First-Agent planner")

    message = build_system_message(role="eval")
    assert "You are the First-Agent evaluator" in message
    assert message.startswith("You are the First-Agent evaluator")


def test_build_system_message_unknown_role_falls_back_to_coder() -> None:
    message = build_system_message(role="nonexistent_role")
    assert message.startswith(CODER_SYSTEM_PROMPT)


def test_build_system_message_from_role_alias_preserves_role_and_extra() -> None:
    message = build_system_message_from_role("planner", extra="prior plan")
    assert message.startswith("You are the First-Agent planner")
    assert message.endswith("prior plan")


def test_build_system_message_is_byte_deterministic() -> None:
    a = build_system_message("ctx: a")
    b = build_system_message("ctx: a")
    assert a == b
    assert a.encode("utf-8") == b.encode("utf-8")


def test_render_tool_specs_projects_to_openai_function_shape() -> None:
    specs = (_make_spec("alpha"), _make_spec("beta"))
    rendered = render_tool_specs(specs)
    assert len(rendered) == 2
    for tool, spec in zip(rendered, specs, strict=True):
        assert tool["type"] == "function"
        assert tool["function"]["name"] == spec.name
        assert tool["function"]["description"] == spec.description
        assert tool["function"]["parameters"] == spec.input_schema


def test_render_tool_specs_preserves_order() -> None:
    specs = tuple(_make_spec(f"tool-{i}") for i in range(5))
    rendered = render_tool_specs(specs)
    names = [t["function"]["name"] for t in rendered]
    assert names == [f"tool-{i}" for i in range(5)]


def test_render_tool_specs_is_byte_deterministic() -> None:
    specs = (_make_spec("a"), _make_spec("b"))
    first = render_tool_specs(specs)
    second = render_tool_specs(specs)
    # Mappings are not necessarily identity-equal but the projection
    # is dict-equal across runs — the A-bucket determinism property.
    assert list(first) == list(second)


def test_render_tool_specs_empty_input_returns_empty_tuple() -> None:
    assert render_tool_specs(()) == ()
