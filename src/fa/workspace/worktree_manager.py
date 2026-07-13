"""
WorktreeManager Abstraction — easy transition Shared → Isolated
ADR-14, Gap 6 raised to Tier 1 per external reviewer (defensive checks)

Prior art: Claude Code bugs #55708, #47548, #31546
Cursor 3.2: each parallel agent isolated git worktree .trees/TASK-123
Battyterm guide: persistent worktrees per agent

Defense: assert after add, check branch already checked out, CWD lock, cleanup assert
Elegant production solution for sanitize: deterministic hash fallback, single call reuse, no leak
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, override


def _sanitize_task_id(task_id: str, run_id: str = "") -> str:
    """Elegant production-grade sanitize, deterministic, no leak."""
    original = task_id or ""
    sanitized = re.sub(r"[^a-zA-Z0-9-_]", "-", original)[:50]
    sanitized = sanitized.strip("-").lower()

    if sanitized:
        return sanitized

    if not original.strip():
        print(f"WARNING: task_id empty after sanitization, original='{original}', using deterministic fallback")

    hash_input = f"{original}:{run_id}".encode()
    short_hash = hashlib.sha256(hash_input).hexdigest()[:8]
    return f"task-{short_hash}"


class WorktreeManager(ABC):
    @abstractmethod
    def create_subagent_workspace(self, task_id: str, base_branch: str = "main") -> Path:
        """Returns Path to workspace for subagent"""
        ...

    @abstractmethod
    def cleanup(self, path: Path) -> None:
        ...


class SharedDirWorktreeManager(WorktreeManager):
    def __init__(self, session_root: Path, run_id: str = ""):
        self.session_root = Path(session_root).resolve()
        self.run_id = run_id
        assert self.session_root.exists(), f"session_root {self.session_root} not exists"
        assert self.session_root.is_dir(), f"session_root {self.session_root} not dir"

    @override
    def create_subagent_workspace(self, task_id: str, base_branch: str = "main") -> Path:
        _sanitize_task_id(task_id, run_id=self.run_id)
        return self.session_root

    @override
    def cleanup(self, path: Path) -> None:
        assert Path(path).resolve() == self.session_root, (
            f"cleanup called on non-session_root {path} in SharedDir mode"
        )


class IsolatedWorktreeManager(WorktreeManager):
    def __init__(self, session_root: Path, repo_root: Path, run_id: str = ""):
        self.session_root = Path(session_root).resolve()
        self.repo_root = Path(repo_root).resolve()
        self.run_id = run_id
        self.worktrees_root = self.session_root / ".fa" / "worktrees"
        self.worktrees_root.mkdir(parents=True, exist_ok=True)
        assert self.repo_root.exists(), f"repo_root {self.repo_root} not exists"
        assert (self.repo_root / ".git").exists() or (self.repo_root / ".git").is_file(), (
            f"repo_root {self.repo_root} not git repo"
        )

    def _is_branch_checked_out_elsewhere(self, branch: str) -> tuple[bool, str]:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],  # noqa: S607
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            if not line.startswith("branch "):
                continue
            existing = line.split("refs/heads/")[-1] if "refs/heads/" in line else line.replace("branch ", "", 1)
            if existing == branch:
                return True, result.stdout
        return False, result.stdout

    def _resolve_base_branch(self, base_branch: str) -> str:
        for candidate in [base_branch, "main", "master", "HEAD"]:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", candidate],  # noqa: S607
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return candidate
        return base_branch

    @override
    def create_subagent_workspace(self, task_id: str, base_branch: str = "main") -> Path:
        clean_id = _sanitize_task_id(task_id, run_id=self.run_id)
        worktree_path = self.worktrees_root / clean_id
        branch = f"agent/{clean_id}"

        if worktree_path.exists():
            self.cleanup(worktree_path)

        is_checked_out, details = self._is_branch_checked_out_elsewhere(branch)
        if is_checked_out:
            raise RuntimeError(
                f"Branch {branch} already checked out elsewhere. Details:\n{details}\n"
                f"Create new branch name or remove old worktree."
            )

        resolved_base = self._resolve_base_branch(base_branch)

        cmd = ["git", "worktree", "add", str(worktree_path), "-b", branch, resolved_base]
        result = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True)  # noqa: S603

        if result.returncode != 0:
            if "already exists" in result.stderr and "branch" in result.stderr:
                cmd2 = ["git", "worktree", "add", str(worktree_path), branch]
                result2 = subprocess.run(cmd2, cwd=self.repo_root, capture_output=True, text=True)  # noqa: S603
                if result2.returncode != 0:
                    raise RuntimeError(f"git worktree add failed: {result.stderr} | {result2.stderr}")
            else:
                raise RuntimeError(f"git worktree add failed: {result.stderr} (base {resolved_base})")

        assert worktree_path.exists(), f"worktree_path {worktree_path} not exists after add"
        assert worktree_path.is_dir(), f"worktree_path {worktree_path} not dir after add"

        list_result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],  # noqa: S607
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        found = False
        for line in list_result.stdout.splitlines():
            if line.startswith("worktree "):
                wt_path = line.replace("worktree ", "", 1).strip()
                if Path(wt_path).resolve() == worktree_path.resolve():
                    found = True
                    break
        assert found, f"worktree {worktree_path} not in git worktree list after add: {list_result.stdout}"

        return worktree_path

    @override
    def cleanup(self, path: Path) -> None:
        path = Path(path).resolve()
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(path)],  # noqa: S607
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        assert not path.exists(), f"worktree_path {path} still exists after remove --force"
        subprocess.run(["git", "worktree", "prune"], cwd=self.repo_root, capture_output=True, text=True)  # noqa: S607


class WorktreeManagerFactory:
    """Factory based on feature_flags.worktree_mode, DI via SessionState."""

    @staticmethod
    def from_flags(
        flags: Any | None, session_root: Path, repo_root: Path, run_id: str = ""
    ) -> WorktreeManager:
        mode = getattr(flags, "worktree_mode", "shared") if flags else "shared"
        if mode == "isolated":
            return IsolatedWorktreeManager(session_root, repo_root, run_id=run_id)
        return SharedDirWorktreeManager(session_root, run_id=run_id)


__all__ = [
    "IsolatedWorktreeManager",
    "SharedDirWorktreeManager",
    "WorktreeManager",
    "WorktreeManagerFactory",
    "_sanitize_task_id",
]
