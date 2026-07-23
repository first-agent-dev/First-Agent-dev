"""Tests for shared tool utilities (fa.inner_loop.tools._common).

Verifies the extracted common functions work correctly and handle edge cases.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from fa.inner_loop.tools._common import (
    git_ls_files,
    validate_search_params,
    truncate_for_preview,
    validate_bash_command,
    prepare_workspace_context,
)


class TestGitLsFiles:
    """Tests for git_ls_files() function."""

    def test_git_ls_files_returns_tracked_files(self, tmp_path: Path) -> None:
        """git_ls_files returns tracked files from git repository."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
        
        # Create and track files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.py").write_text("content2")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)
        
        result = git_ls_files(tmp_path)
        
        assert "file1.txt" in result
        assert "file2.py" in result
        assert len(result) == 2

    def test_git_ls_files_returns_untracked_not_ignored(self, tmp_path: Path) -> None:
        """git_ls_files returns untracked files that are not in .gitignore."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
        
        # Create .gitignore
        (tmp_path / ".gitignore").write_text("*.log\n")
        
        # Create tracked file
        (tmp_path / "tracked.txt").write_text("tracked")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)
        
        # Create untracked files
        (tmp_path / "untracked.txt").write_text("untracked")
        (tmp_path / "ignored.log").write_text("ignored")
        
        result = git_ls_files(tmp_path)
        
        assert "tracked.txt" in result
        assert "untracked.txt" in result
        assert "ignored.log" not in result
        assert ".gitignore" in result

    def test_git_ls_files_returns_empty_on_non_git_dir(self, tmp_path: Path) -> None:
        """git_ls_files returns empty list when not in a git repository."""
        result = git_ls_files(tmp_path)
        assert result == []

    def test_git_ls_files_handles_subprocess_timeout(self, tmp_path: Path) -> None:
        """git_ls_files returns empty list on subprocess timeout."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
        
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git ls-files", timeout=10)
            result = git_ls_files(tmp_path)
        
        assert result == []

    def test_git_ls_files_handles_subprocess_error(self, tmp_path: Path) -> None:
        """git_ls_files returns empty list on subprocess error."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
        
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Permission denied")
            result = git_ls_files(tmp_path)
        
        assert result == []

    def test_git_ls_files_handles_nonzero_return_code(self, tmp_path: Path) -> None:
        """git_ls_files returns empty list when git returns non-zero exit code."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
        
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_run.return_value = mock_result
            result = git_ls_files(tmp_path)
        
        assert result == []

    def test_git_ls_files_filters_empty_lines(self, tmp_path: Path) -> None:
        """git_ls_files filters out empty lines from git output."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
        
        # Create a file
        (tmp_path / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)
        
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "file.txt\n\n\n"
            mock_run.return_value = mock_result
            result = git_ls_files(tmp_path)
        
        assert result == ["file.txt"]

    def test_git_ls_files_strips_whitespace(self, tmp_path: Path) -> None:
        """git_ls_files strips whitespace from file paths."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
        
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "  file1.txt  \n  file2.py  \n"
            mock_run.return_value = mock_result
            result = git_ls_files(tmp_path)
        
        assert result == ["file1.txt", "file2.py"]


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
        root, allowlist = prepare_workspace_context(tmp_path)
        assert root == tmp_path.resolve()

    def test_creates_empty_allowlist_by_default(self, tmp_path: Path) -> None:
        """prepare_workspace_context creates empty frozenset by default."""
        root, allowlist = prepare_workspace_context(tmp_path)
        assert allowlist == frozenset()

    def test_includes_extra_allowlist(self, tmp_path: Path) -> None:
        """prepare_workspace_context includes extra environment variables."""
        root, allowlist = prepare_workspace_context(tmp_path, ["DEBUG", "TEST"])
        assert "DEBUG" in allowlist
        assert "TEST" in allowlist
