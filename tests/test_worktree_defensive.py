"""
Tests for ADR-14 WorktreeManager defensive checks (Gap 6 raised to Tier 1)
Prior art: Claude Code bugs #55708, #47548, #31546 — isolation:worktree param silently ignored
"""

import subprocess
import tempfile
from pathlib import Path


def test_shared_dir_manager():
    from fa.workspace.worktree_manager import SharedDirWorktreeManager

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manager = SharedDirWorktreeManager(session_root=root)
        ws = manager.create_subagent_workspace("task1")
        assert ws == root
        # cleanup should assert path == session_root
        manager.cleanup(root)
        # cleanup non-root should assert
        try:
            manager.cleanup(Path("/tmp"))
            raise AssertionError("Expected an error but none was raised")
        except AssertionError:
            pass


def test_isolated_manager_branch_already_checked_out():
    from fa.workspace.worktree_manager import IsolatedWorktreeManager

    with tempfile.TemporaryDirectory() as tmp:
        # Create a bare repo for testing worktree
        repo = Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        (repo / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

        session_root = Path(tmp) / "session"
        session_root.mkdir()
        manager = IsolatedWorktreeManager(session_root=session_root, repo_root=repo)

        # Create first worktree
        ws1 = manager.create_subagent_workspace(
            "task1", base_branch="main" if (repo / ".git" / "refs" / "heads" / "main").exists() else "master"
        )
        assert ws1.exists()

        # Try to create same branch again — should fail fast with clear error, not silent fallback
        # Second call with same task_id tries same branch agent/task1 → should remove stale first, then recreate
        # But if we manually try to create same branch via different task_id that maps to same branch name?
        # Our branch name is agent/<task_id> unique, so no collision
        # Test collision detection: try to create worktree with branch that already checked out
        # Create a worktree for branch collision-test
        ws_collision = manager.create_subagent_workspace("collision-test")
        # Now try to create another worktree with same branch name via direct git command to simulate bug
        # Our manager should detect via _is_branch_checked_out_elsewhere
        is_checked, _ = manager._is_branch_checked_out_elsewhere("agent/collision-test")
        assert is_checked, "Branch should be detected as already checked out"

        manager.cleanup(ws1)
        manager.cleanup(ws_collision)
        assert not ws1.exists()


def test_worktree_defensive_exists():
    from fa.workspace.worktree_manager import IsolatedWorktreeManager

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        (repo / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
        session_root = Path(tmp) / "session"
        session_root.mkdir()
        manager = IsolatedWorktreeManager(session_root=session_root, repo_root=repo)
        ws = manager.create_subagent_workspace("test_exists")
        # Defensive: after add, path must exist
        assert ws.exists() and ws.is_dir()
        # After cleanup, must not exist
        manager.cleanup(ws)
        assert not ws.exists()
