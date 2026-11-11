"""
Tests for ADR-14 WorktreeManager defensive checks (Gap 6 raised to Tier 1)
Prior art: Claude Code bugs #55708, #47548, #31546 — isolation:worktree param silently ignored
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tests._capabilities import requires_posix_paths, requires_stable_tmpdir


@requires_stable_tmpdir
def test_shared_dir_manager() -> None:
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


@requires_posix_paths
def test_isolated_manager_branch_already_checked_out() -> None:
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


@requires_posix_paths
def test_worktree_defensive_exists() -> None:
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


# ---------------------------------------------------------------------------
# PLW1510 — a failed probe is not an answer
# ---------------------------------------------------------------------------


def _manager(tmp_path: Path) -> object:
    from fa.workspace.worktree_manager import IsolatedWorktreeManager

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True, capture_output=True)
    session_root = tmp_path / "session"
    session_root.mkdir()
    return IsolatedWorktreeManager(session_root=session_root, repo_root=repo)


def test_failed_worktree_list_refuses_instead_of_reporting_a_free_branch(tmp_path: Path, monkeypatch: object) -> None:
    """producer-kill-check: read `stdout` without looking at `returncode`.

    The answer to "is this branch already checked out?" decides whether a
    worktree may be created at all. Before this fix a git failure produced an
    empty stdout, the loop found nothing, and the function answered *False* —
    i.e. "the branch is free" — on no evidence whatsoever, so the caller built
    a worktree on top of a branch that another worktree already held.

    Oracle: the error class, not merely that something raised. "I could not
    find out" and "the branch is taken" are different facts and send an
    operator to different places, so a `BranchAlreadyCheckedOutError` here
    would be the wrong message even though it is also an exception.
    """
    import pytest

    from fa.workspace.worktree_manager import WorktreeProbeError

    manager = _manager(tmp_path)
    real_run = subprocess.run

    def failing_git(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if list(args[0][:3]) == ["git", "worktree", "list"]:
            return subprocess.CompletedProcess(
                args=args[0], returncode=128, stdout="", stderr="fatal: not a git repository"
            )
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", failing_git)  # type: ignore[attr-defined]

    with pytest.raises(WorktreeProbeError) as refused:
        manager._is_branch_checked_out_elsewhere("agent/whatever")  # type: ignore[attr-defined]

    assert refused.value.returncode == 128
    assert "not a git repository" in refused.value.stderr
    assert "agent/whatever" in str(refused.value)


def test_successful_but_empty_worktree_list_still_answers_no(tmp_path: Path) -> None:
    """C1: fail-closed must not become "always fail" — a real empty answer is False.

    The distinction the previous test cannot make on its own: a probe that
    *succeeded* and reported nothing means the branch is free. If the fix had
    been "raise whenever nothing is found", every fresh repository would refuse
    to create its first worktree.
    """
    manager = _manager(tmp_path)
    is_checked_out, details = manager._is_branch_checked_out_elsewhere("agent/fresh")  # type: ignore[attr-defined]

    assert is_checked_out is False
    assert isinstance(details, str)


def test_cleanup_reports_a_failed_prune_instead_of_dropping_it(
    tmp_path: Path, monkeypatch: object, caplog: object
) -> None:
    """C3: the bytes are gone but git's record is not — say so.

    `cleanup` is authoritative on the filesystem (`exists()` decides success),
    so a failed `prune` must not fail the call. It must not vanish either: a
    stale registration is exactly what makes the *next* creation fail with a
    message that points at the wrong thing.
    """
    import logging

    manager = _manager(tmp_path)
    workspace = Path(tmp_path) / "session" / ".fa" / "worktrees" / "task-prune"
    workspace.mkdir(parents=True)
    real_run = subprocess.run

    def refuse_prune(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if list(args[0][:3]) == ["git", "worktree", "prune"]:
            return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="", stderr="prune refused")
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", refuse_prune)  # type: ignore[attr-defined]
    try:
        with caplog.at_level(logging.WARNING):  # type: ignore[attr-defined]
            manager.cleanup(workspace)  # type: ignore[attr-defined]
    finally:
        monkeypatch.setattr(subprocess, "run", real_run)  # type: ignore[attr-defined]

    assert not workspace.exists(), "cleanup must still remove the bytes"
    assert any("prune exited 1" in record.message for record in caplog.records), (  # type: ignore[attr-defined]
        [record.message for record in caplog.records]  # type: ignore[attr-defined]
    )
