"""S13.11 provider-visible tool-schema portability contracts.

These tests were authored RED before S13.11 implementation and now pin both
production mechanisms: the typed registry portability gate and the portable
``fs_search`` source schema.

The local JSON-Schema compiler remains authoritative for tool-call validation;
this suite adds the narrower provider-visible PTS-v1 authoring contract.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest

import fa.inner_loop.registry as registry_module
from fa.inner_loop.profiles import PROFILES_RAW, build_registry_for_role
from fa.inner_loop.registry import ToolRegistry, ToolResult, ToolSpec
from fa.inner_loop.tools import build_baseline_registry, build_eval_registry, build_planner_registry


def _noop(_params: Mapping[str, object]) -> ToolResult:
    return ToolResult.ok("noop")


def _portability_contract() -> tuple[Callable[[str, Mapping[str, object]], None], type[Exception]]:
    validator = getattr(registry_module, "validate_tool_schema_portability", None)
    error_type = getattr(registry_module, "ToolSchemaPortabilityError", None)
    assert callable(validator), "S13.11 missing producer: registry.validate_tool_schema_portability(tool_name, schema)"
    assert isinstance(error_type, type) and issubclass(error_type, Exception), (
        "S13.11 missing typed failure: registry.ToolSchemaPortabilityError"
    )
    return cast(Callable[[str, Mapping[str, object]], None], validator), error_type


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object"},
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "description": "Search query"},
                "limit": {"type": "integer", "minimum": 1, "default": 20},
                "mode": {"type": "string", "enum": ["files", "matches"]},
                "paths": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {
                "env": {
                    "type": "object",
                    "description": "String environment map",
                    "additionalProperties": {"type": "string"},
                }
            },
        },
    ],
    ids=["empty-object", "current-constraints", "dynamic-string-map"],
)
def test_pts_v1_accepts_supported_schema_shapes(schema: dict[str, object]) -> None:
    """C0p: every PTS-v1 structural/validation family has a positive row."""

    validator, _error_type = _portability_contract()
    assert validator("test_portable", schema) is None


@pytest.mark.parametrize(
    ("schema", "expected_path", "expected_reason"),
    [
        (
            {"type": "object", "properties": {"value": {"type": ["string", "null"]}}},
            "/properties/value/type",
            "unsupported_type",
        ),
        (
            {"type": "object", "properties": {"value": {"type": "null"}}},
            "/properties/value/type",
            "unsupported_type",
        ),
        (
            {"type": "string"},
            "/type",
            "root_not_object",
        ),
        (
            {"type": "object", "anyOf": [{"type": "object"}]},
            "/anyOf",
            "unsupported_keyword",
        ),
        (
            {"type": "object", "oneOf": [{"type": "object"}]},
            "/oneOf",
            "unsupported_keyword",
        ),
        (
            {"type": "object", "allOf": [{"type": "object"}]},
            "/allOf",
            "unsupported_keyword",
        ),
        (
            {"type": "object", "$ref": "#/$defs/value"},
            "/$ref",
            "unsupported_keyword",
        ),
        (
            {"type": "object", "$defs": {}},
            "/$defs",
            "unsupported_keyword",
        ),
        (
            {"type": "object", "x-provider-only": True},
            "/x-provider-only",
            "unsupported_keyword",
        ),
        (
            {"type": "object", "properties": None},
            "/properties",
            "invalid_properties",
        ),
        (
            {"type": "object", "properties": ["not-a-map"]},
            "/properties",
            "invalid_properties",
        ),
        (
            {"type": "object", "properties": {}, "required": None},
            "/required",
            "invalid_required",
        ),
        (
            {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value", "value"]},
            "/required/1",
            "invalid_required",
        ),
        (
            {"type": "object", "additionalProperties": None},
            "/additionalProperties",
            "invalid_additional_properties",
        ),
        (
            {"type": "object", "additionalProperties": 1},
            "/additionalProperties",
            "invalid_additional_properties",
        ),
        (
            {"type": "object", "properties": {"value": {"type": "string", "description": None}}},
            "/properties/value/description",
            "invalid_description",
        ),
        (
            {"type": "object", "properties": {"value": {"type": "string", "enum": None}}},
            "/properties/value/enum",
            "invalid_enum",
        ),
        (
            {"type": "object", "properties": {"value": {"type": "integer", "minimum": None}}},
            "/properties/value/minimum",
            "invalid_bound",
        ),
        (
            {"type": "object", "properties": {"value": {"type": "string", "description": 7}}},
            "/properties/value/description",
            "invalid_description",
        ),
        (
            {"type": "object", "properties": {"value": {"type": "string", "enum": ["ok", 1]}}},
            "/properties/value/enum/1",
            "invalid_enum",
        ),
        (
            {"type": "object", "properties": {"value": {"type": "integer", "default": "wrong"}}},
            "/properties/value/default",
            "invalid_default",
        ),
        (
            {"type": "object", "properties": {"values": {"type": "array"}}},
            "/properties/values/items",
            "invalid_items",
        ),
        (
            {"type": "object", "properties": {"value": {"type": "string", "minLength": 2, "maxLength": 1}}},
            "/properties/value/maxLength",
            "invalid_bound",
        ),
        (
            {"type": "object", "properties": {"value": {"type": "number", "minimum": 2, "maximum": 1}}},
            "/properties/value/maximum",
            "invalid_bound",
        ),
        (
            {"type": "object", "properties": {}, "required": ["missing"]},
            "/required/0",
            "required_unknown_property",
        ),
        (
            {"type": "object", "properties": {"values": {"type": "array", "items": "bad"}}},
            "/properties/values/items",
            "invalid_items",
        ),
        (
            {"type": "object", "properties": {"value": {"type": "integer", "minimum": True}}},
            "/properties/value/minimum",
            "invalid_bound",
        ),
    ],
    ids=[
        "nullable-union",
        "null-type",
        "root-not-object",
        "any-of",
        "one-of",
        "all-of",
        "ref",
        "defs",
        "unknown-keyword",
        "null-properties",
        "malformed-properties",
        "null-required",
        "duplicate-required",
        "null-additional-properties",
        "malformed-additional-properties",
        "null-description",
        "null-enum",
        "null-bound",
        "bad-description",
        "heterogeneous-enum",
        "bad-default",
        "missing-items",
        "inverted-length-bounds",
        "inverted-numeric-bounds",
        "unknown-required",
        "bad-items",
        "bool-bound",
    ],
)
def test_pts_v1_rejects_nonportable_shapes_with_stable_pointer(
    schema: dict[str, object],
    expected_path: str,
    expected_reason: str,
) -> None:
    """C0p: structural loss is a named failure, never silent projection."""

    validator, error_type = _portability_contract()
    with pytest.raises(error_type) as captured:
        validator("test_nonportable", schema)

    message = str(captured.value)
    assert "tool=test_nonportable" in message
    assert f"path={expected_path}" in message
    assert f"reason={expected_reason}" in message


def test_registry_rejects_nonportable_schema_before_partial_registration() -> None:
    """C1: ToolRegistry.register owns the PTS-v1 gate and stays atomic.

    Kill-check: remove the portability call from ToolRegistry.register and this
    test observes the invalid tool in registry.names().
    """

    _validator, error_type = _portability_contract()
    registry = ToolRegistry()
    spec = ToolSpec(
        name="test_nonportable",
        description="Schema must fail provider portability.",
        input_schema={
            "type": "object",
            "properties": {"value": {"type": ["string", "null"]}},
        },
        permission="read",
        handler=_noop,
    )

    with pytest.raises(error_type):
        registry.register(spec)
    assert registry.names() == ()


def test_every_current_role_tool_schema_satisfies_pts_v1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1: every shipped role/registry path obeys one portable source contract."""

    validator, _error_type = _portability_contract()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    registries = [build_registry_for_role(role, tmp_path) for role in sorted(PROFILES_RAW)]
    registries.extend(
        [
            build_baseline_registry(tmp_path),
            build_planner_registry(tmp_path),
            build_eval_registry(tmp_path),
        ]
    )

    checked: set[tuple[str, str]] = set()
    for registry in registries:
        for spec in registry.specs():
            validator(spec.name, spec.input_schema)
            checked.add((spec.name, str(spec.input_schema)))

    assert any(name == "fs_search" for name, _schema in checked)
    assert any(name == "fs_spawn_subagent" for name, _schema in checked)
