"""Tests for shared tool utilities (fa.inner_loop.tools._common).

Verifies the extracted common functions work correctly and handle edge cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import fa.inner_loop.tools._common as common
from fa.inner_loop.tools._common import (
    prepare_workspace_context,
    truncate_for_preview,
    validate_bash_command,
    validate_search_params,
)


def test_legacy_git_ls_files_helper_is_removed_from_module_api() -> None:
    """Q131-C: remove the dormant host-Git helper without removing shared utilities."""
    assert not hasattr(common, "git_ls_files")
    assert "git_ls_files" not in common.__all__


class TestValidateSearchParams:
    """Tests for validate_search_params() function."""

    def test_valid_params_pass_through(self) -> None:
        """validate_search_params returns query and limit when valid."""
        params = {"query": "test", "limit": 10}
        query, limit = validate_search_params(params, default_limit=20, max_limit=100)
        assert query == "test"
        assert limit == 10

    def test_missing_limit_uses_default(self) -> None:
        """validate_search_params uses default_limit when limit not specified."""
        params = {"query": "test"}
        query, limit = validate_search_params(params, default_limit=20, max_limit=100)
        assert query == "test"
        assert limit == 20

    def test_zero_limit_uses_default(self) -> None:
        """validate_search_params uses default_limit when limit is 0."""
        params = {"query": "test", "limit": 0}
        query, limit = validate_search_params(params, default_limit=20, max_limit=100)
        assert query == "test"
        assert limit == 20

    def test_negative_limit_uses_default(self) -> None:
        """validate_search_params uses default_limit when limit is negative."""
        params = {"query": "test", "limit": -5}
        query, limit = validate_search_params(params, default_limit=20, max_limit=100)
        assert query == "test"
        assert limit == 20

    def test_limit_above_max_is_capped(self) -> None:
        """validate_search_params caps limit at max_limit."""
        params = {"query": "test", "limit": 150}
        query, limit = validate_search_params(params, default_limit=20, max_limit=100)
        assert query == "test"
        assert limit == 100

    def test_limit_at_max_is_accepted(self) -> None:
        """validate_search_params accepts limit at max_limit."""
        params = {"query": "test", "limit": 100}
        query, limit = validate_search_params(params, default_limit=20, max_limit=100)
        assert query == "test"
        assert limit == 100

    def test_empty_query_raises_error(self) -> None:
        """validate_search_params raises ValueError for empty query."""
        params = {"query": "", "limit": 10}
        with pytest.raises(ValueError, match="query must be non-empty"):
            validate_search_params(params, default_limit=20, max_limit=100)

    def test_whitespace_query_raises_error(self) -> None:
        """validate_search_params raises ValueError for whitespace-only query."""
        params = {"query": "   ", "limit": 10}
        with pytest.raises(ValueError, match="query must be non-empty"):
            validate_search_params(params, default_limit=20, max_limit=100)

    def test_missing_query_raises_error(self) -> None:
        """validate_search_params raises ValueError when query is missing."""
        params = {"limit": 10}
        with pytest.raises(ValueError, match="query"):
            validate_search_params(params, default_limit=20, max_limit=100)

    def test_non_string_query_raises_error(self) -> None:
        """validate_search_params raises ValueError when query is not a string."""
        params = {"query": 123, "limit": 10}
        with pytest.raises(ValueError, match="query"):
            validate_search_params(params, default_limit=20, max_limit=100)


class TestTruncateForPreview:
    """Tests for truncate_for_preview() function."""

    def test_short_string_not_truncated(self) -> None:
        """truncate_for_preview returns short strings unchanged."""
        result = truncate_for_preview("short text", preview_len=500)
        assert result == "short text"

    def test_string_at_limit_not_truncated(self) -> None:
        """truncate_for_preview returns strings at exact limit unchanged."""
        text = "x" * 500
        result = truncate_for_preview(text, preview_len=500)
        assert result == text

    def test_long_string_truncated(self) -> None:
        """truncate_for_preview truncates long strings with marker."""
        text = "x" * 1000
        result = truncate_for_preview(text, preview_len=500)

        assert len(result) > 500  # Includes marker and tail
        assert "x" * 500 in result  # Start preserved
        assert "x" * 200 in result  # End preserved
        assert "truncated 1000 chars" in result  # Marker present

    def test_dict_converted_to_json(self) -> None:
        """truncate_for_preview converts dicts to JSON."""
        data = {"key": "value", "number": 42}
        result = truncate_for_preview(data, preview_len=500)

        # Should be valid JSON
        import json

        parsed = json.loads(result)
        assert parsed == data

    def test_dict_truncated_when_long(self) -> None:
        """truncate_for_preview truncates long JSON output."""
        data = {"key": "x" * 1000}
        result = truncate_for_preview(data, preview_len=500)

        assert "truncated" in result
        assert len(result) > 500

    def test_list_converted_to_json(self) -> None:
        """truncate_for_preview converts lists to JSON."""
        data = [1, 2, 3, "test"]
        result = truncate_for_preview(data, preview_len=500)

        import json

        parsed = json.loads(result)
        assert parsed == data

    def test_custom_preview_len(self) -> None:
        """truncate_for_preview respects custom preview_len."""
        text = "x" * 1000
        result = truncate_for_preview(text, preview_len=100)

        assert "x" * 100 in result  # Custom limit
        assert "x" * 200 in result  # Tail always 200 chars


class TestValidateBashCommand:
    """Tests for validate_bash_command() function."""

    def test_valid_command_returns_command_and_none(self) -> None:
        """validate_bash_command returns (command, None) for valid input."""
        command, error = validate_bash_command({"command": "ls -la"})
        assert command == "ls -la"
        assert error is None

    def test_missing_command_returns_error(self) -> None:
        """validate_bash_command returns error for missing command."""
        command, error = validate_bash_command({})
        assert command == ""
        assert error is not None
        assert "command" in error.summary

    def test_non_string_command_returns_error(self) -> None:
        """validate_bash_command returns error for non-string command."""
        command, error = validate_bash_command({"command": 123})
        assert command == ""
        assert error is not None
        assert "command" in error.summary


class TestPrepareWorkspaceContext:
    """Tests for prepare_workspace_context() function."""

    def test_resolves_workspace_root(self, tmp_path: Path) -> None:
        """prepare_workspace_context resolves workspace root."""
        root, _allowlist = prepare_workspace_context(tmp_path)
        assert root == tmp_path.resolve()

    def test_creates_empty_allowlist_by_default(self, tmp_path: Path) -> None:
        """prepare_workspace_context creates empty frozenset by default."""
        _root, allowlist = prepare_workspace_context(tmp_path)
        assert allowlist == frozenset()

    def test_includes_extra_allowlist(self, tmp_path: Path) -> None:
        """prepare_workspace_context includes extra environment variables."""
        _root, allowlist = prepare_workspace_context(tmp_path, ["DEBUG", "TEST"])
        assert "DEBUG" in allowlist
        assert "TEST" in allowlist
