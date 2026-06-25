"""Tests for fa.inner_loop.prompt — A-bucket residue determinism guards.

The prompt module is deep-dive §3 I-2 A-bucket residue: pure
deterministic functions whose output must be byte-stable for given
inputs. These tests pin that invariant.
"""

from __future__ import annotations

import json

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
    assert "Architect for Agent-FA" in message
    assert "Architect for Agent-FA" in message

    message = build_system_message(role="eval")
    assert "You are the First-Agent evaluator" in message
    assert message.startswith("You are the First-Agent evaluator")


def test_build_system_message_unknown_role_falls_back_to_coder() -> None:
    message = build_system_message(role="nonexistent_role")
    assert message.startswith(CODER_SYSTEM_PROMPT)


def test_build_system_message_from_role_alias_preserves_role_and_extra() -> None:
    message = build_system_message_from_role("planner", extra="prior plan")
    assert "Architect for Agent-FA" in message
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
    specs_by_name = {spec.name: spec for spec in specs}
    for tool in rendered:
        spec = specs_by_name[tool["function"]["name"]]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == spec.name
        assert tool["function"]["description"] == spec.description
        assert tool["function"]["parameters"] == spec.input_schema


def test_render_tool_specs_sorts_by_name() -> None:
    specs = (_make_spec("tool-2"), _make_spec("tool-0"), _make_spec("tool-1"))
    rendered = render_tool_specs(specs)
    names = [t["function"]["name"] for t in rendered]
    assert names == ["tool-0", "tool-1", "tool-2"]


def test_render_tool_specs_is_byte_stable_and_order_independent() -> None:
    specs = (_make_spec("a"), _make_spec("b"), _make_spec("c"))
    first = json.dumps(render_tool_specs(specs), ensure_ascii=False, sort_keys=True)
    second = json.dumps(
        render_tool_specs(tuple(reversed(specs))), ensure_ascii=False, sort_keys=True
    )
    assert first == second


def test_render_tool_specs_empty_input_returns_empty_tuple() -> None:
    assert render_tool_specs(()) == ()
