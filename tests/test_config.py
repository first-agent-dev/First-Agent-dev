"""Tests for ``fa.config`` capability-flag parser (Wave-1 R-21)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.config import (
    Capabilities,
    CapabilityLoadResult,
    CapabilityWarning,
    load_capabilities,
    load_capabilities_from_path,
)


def test_empty_text_yields_all_false_defaults() -> None:
    result = load_capabilities("")
    assert isinstance(result, CapabilityLoadResult)
    assert result.capabilities == Capabilities()
    assert result.warnings == ()
    for name in result.capabilities.names():
        assert getattr(result.capabilities, name) is False


def test_capabilities_block_with_only_some_keys_keeps_defaults() -> None:
    text = """
capabilities:
  ENABLE_DYNAMIC_TOOLS: true
  ENABLE_SERVER_OPS: true
"""
    result = load_capabilities(text)
    assert result.capabilities.ENABLE_DYNAMIC_TOOLS is True
    assert result.capabilities.ENABLE_SERVER_OPS is True
    # Three other flags still default False.
    assert result.capabilities.REQUIRE_DYNAMIC_TOOL_SANDBOX is False
    assert result.capabilities.ENABLE_MCP_GATEWAY_MANAGEMENT is False
    assert result.capabilities.ENABLE_DYNAMIC_MCP_SERVERS is False
    assert result.warnings == ()


def test_all_five_flags_can_be_enabled() -> None:
    text = """
capabilities:
  ENABLE_DYNAMIC_TOOLS: true
  REQUIRE_DYNAMIC_TOOL_SANDBOX: true
  ENABLE_MCP_GATEWAY_MANAGEMENT: true
  ENABLE_DYNAMIC_MCP_SERVERS: true
  ENABLE_SERVER_OPS: true
"""
    result = load_capabilities(text)
    as_map = result.capabilities.as_dict()
    assert all(as_map.values())
    assert set(as_map) == set(result.capabilities.names())


def test_boolean_literal_variants_all_accepted() -> None:
    text = """
capabilities:
  ENABLE_DYNAMIC_TOOLS: yes
  REQUIRE_DYNAMIC_TOOL_SANDBOX: on
  ENABLE_MCP_GATEWAY_MANAGEMENT: 1
  ENABLE_DYNAMIC_MCP_SERVERS: no
  ENABLE_SERVER_OPS: off
"""
    result = load_capabilities(text)
    assert result.capabilities.ENABLE_DYNAMIC_TOOLS is True
    assert result.capabilities.REQUIRE_DYNAMIC_TOOL_SANDBOX is True
    assert result.capabilities.ENABLE_MCP_GATEWAY_MANAGEMENT is True
    assert result.capabilities.ENABLE_DYNAMIC_MCP_SERVERS is False
    assert result.capabilities.ENABLE_SERVER_OPS is False


def test_unknown_flag_becomes_warning_not_error() -> None:
    text = """
capabilities:
  ENABLE_DYNAMIC_TOOLS: true
  ENABLE_TYPO_FLAG: true
"""
    result = load_capabilities(text)
    assert result.capabilities.ENABLE_DYNAMIC_TOOLS is True
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert isinstance(warning, CapabilityWarning)
    assert warning.key == "ENABLE_TYPO_FLAG"
    assert "not a recognised" in warning.detail


def test_non_boolean_value_becomes_warning() -> None:
    text = """
capabilities:
  ENABLE_DYNAMIC_TOOLS: maybe
  ENABLE_SERVER_OPS: true
"""
    result = load_capabilities(text)
    assert result.capabilities.ENABLE_DYNAMIC_TOOLS is False
    assert result.capabilities.ENABLE_SERVER_OPS is True
    assert len(result.warnings) == 1
    assert result.warnings[0].key == "ENABLE_DYNAMIC_TOOLS"
    assert "not boolean" in result.warnings[0].detail


def test_list_under_capabilities_raises() -> None:
    text = """
capabilities:
  - ENABLE_DYNAMIC_TOOLS
"""
    with pytest.raises(ValueError, match="key-value map"):
        load_capabilities(text)


def test_keys_outside_capabilities_are_ignored() -> None:
    text = """
unrelated_section:
  ENABLE_DYNAMIC_TOOLS: true

capabilities:
  ENABLE_SERVER_OPS: true
"""
    result = load_capabilities(text)
    # Top-level `unrelated_section` does not bleed in.
    assert result.capabilities.ENABLE_DYNAMIC_TOOLS is False
    assert result.capabilities.ENABLE_SERVER_OPS is True
    assert result.warnings == ()


def test_load_capabilities_from_path_missing_file_returns_defaults(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "absent.yaml"
    result = load_capabilities_from_path(missing)
    assert result.capabilities == Capabilities()
    assert result.warnings == ()


def test_load_capabilities_from_path_reads_existing_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "capabilities:\n  ENABLE_DYNAMIC_TOOLS: true\n",
        encoding="utf-8",
    )
    result = load_capabilities_from_path(path)
    assert result.capabilities.ENABLE_DYNAMIC_TOOLS is True
    assert result.capabilities.ENABLE_SERVER_OPS is False


def test_capabilities_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    caps = Capabilities()
    with pytest.raises(FrozenInstanceError):
        caps.ENABLE_DYNAMIC_TOOLS = True  # type: ignore[misc]
