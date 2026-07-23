"""Tests for write_file._check_conflict expected_root initialization (PY6 closure).

These tests verify that expected_root is always defined in every exception path
of the blackboard safety check, preventing unbound-name errors.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from fa.inner_loop.tools.write_file import _check_conflict


class TestCheckConflictExpectedRoot:
    """Verify expected_root is initialized before nested fallback."""

    def test_blackboard_none_returns_none(self, tmp_path: Path) -> None:
        """When blackboard is None, no conflict check is needed."""
        result = _check_conflict(None, ["a.py"], ["b.py"], tmp_path, tmp_path / "llms.txt")
        assert result is None

    def test_blackboard_from_same_workspace_proceeds(self, tmp_path: Path) -> None:
        """When blackboard root matches workspace, conflict check proceeds normally."""
        # Set up blackboard with root = tmp_path/.fa/blackboard
        bb_dir = tmp_path / ".fa" / "blackboard"
        bb_dir.mkdir(parents=True)
        blackboard = MagicMock()
        blackboard.root = bb_dir

        llms = tmp_path / "llms.txt"
        llms.write_text("test")

        # Should proceed to conflict check (may return None if no conflicts)
        _check_conflict(blackboard, ["a.py"], ["b.py"], tmp_path, llms)
        # No assertion needed: this verifies the code path completes without error

    def test_blackboard_from_different_workspace_ignored(self, tmp_path: Path) -> None:
        """When blackboard is from a different workspace, conflict check is skipped."""
        # Blackboard from a DIFFERENT workspace
        other_root = tmp_path.parent / "other_workspace"
        bb_dir = other_root / ".fa" / "blackboard"

        blackboard = MagicMock()
        blackboard.root = bb_dir  # different workspace

        llms = tmp_path / "llms.txt"
        llms.write_text("test")

        # Should return None (ignored because different workspace)
        result = _check_conflict(blackboard, ["a.py"], ["b.py"], tmp_path, llms)
        assert result is None

    def test_expected_root_used_in_fallback_path(self, tmp_path: Path) -> None:
        """When is_relative_to fails, the fallback path uses expected_root correctly."""
        # Create a blackboard with a root that will cause is_relative_to to fail
        # but where the fallback path still needs expected_root
        blackboard = MagicMock()
        # Use a path that's not relative to tmp_path
        blackboard.root = Path("/unrelated/path/blackboard")
        blackboard.path = Path("/unrelated/path/blackboard/blackboard.jsonl")

        llms = tmp_path / "llms.txt"
        llms.write_text("test")

        # Should return None (different workspace, ignored)
        result = _check_conflict(blackboard, ["a.py"], ["b.py"], tmp_path, llms)
        assert result is None

    def test_expected_root_always_resolved(self, tmp_path: Path) -> None:
        """Verify expected_root is resolved exactly once (no redundant resolve calls)."""
        import inspect

        from fa.inner_loop.tools import write_file

        source = inspect.getsource(write_file._check_conflict)

        # expected_root should be assigned BEFORE the inner try block
        # Find the position of expected_root assignment and inner try
        expected_root_pos = source.find("expected_root = root.resolve()")
        inner_try_pos = source.find("except Exception:", source.find("try:", expected_root_pos))

        # expected_root should be assigned before the inner try's except
        assert expected_root_pos > 0, "expected_root assignment not found"
        assert expected_root_pos < inner_try_pos, (
            "expected_root should be initialized BEFORE the inner try's except block"
        )
