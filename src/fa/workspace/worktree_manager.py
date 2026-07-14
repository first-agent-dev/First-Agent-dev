"""
WorktreeManager Abstraction — SharedDir primary for v0.1 (100% stable) per ADR-14/15 v3 reduced surface

IsolatedWorktreeManager kept for tests / future branch worktree-isolated, but Factory returns SharedDir by default with warning if isolated requested (per Q4 A_shared_only).

Per Q1: custom exceptions BranchAlreadyCheckedOutError / CleanupFailedError with git worktree list details per spec Phase 1 fail-fast.
No assert for safety-critical checks (compliance-by-construction §1.2.5), assert only for internal invariants with noqa S101.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, override


class BranchAlreadyCheckedOutError(RuntimeError):
    """Branch already checked out elsewhere — fail-fast with git worktree list details."""

    def __init__(self, branch: str, details: str):
        super().__init__(
            f"Branch {branch} already checked out elsewhere. Details:\n{details}\n"
            f"Create new branch name or remove old worktree via git worktree remove."
        )
        self.branch = branch
        self.details = details


class CleanupFailedError(AssertionError, RuntimeError):
    """Cleanup failed — worktree path still exists after remove --force. Subclasses AssertionError for backward compat."""

    def __init__(self, path: Path, details: str = ""):
        super().__init__(f"worktree_path {path} still exists after remove --force. {details}")
        self.path = path


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
        """Returns Path to workspace for subagent — v0.1 always session_root"""
        ...

    @abstractmethod
    def cleanup(self, path: Path) -> None: ...


class SharedDirWorktreeManager(WorktreeManager):
    def __init__(self, session_root: Path, run_id: str = ""):
        resolved = Path(session_root).resolve()
        if not resolved.exists():
            raise RuntimeError(f"session_root {resolved} not exists")
        if not resolved.is_dir():
            raise RuntimeError(f"session_root {resolved} not dir")
        self.session_root = resolved
        self.run_id = run_id

    @override
    def create_subagent_workspace(self, task_id: str, base_branch: str = "main") -> Path:
        _ = _sanitize_task_id(task_id, run_id=self.run_id)
        return self.session_root

    @override
    def cleanup(self, path: Path) -> None:
        resolved = Path(path).resolve()
        if resolved != self.session_root:
            raise CleanupFailedError(resolved, f"cleanup called on non-session_root {path} in SharedDir mode")
        return


class IsolatedWorktreeManager(WorktreeManager):
    """Isolated worktree — deferred to branch worktree-isolated, kept for tests/backward compat."""

    def __init__(self, session_root: Path, repo_root: Path, run_id: str = ""):
        session_resolved = Path(session_root).resolve()
        repo_resolved = Path(repo_root).resolve()
        if not session_resolved.exists():
            raise RuntimeError(f"session_root {session_resolved} not exists")
        if not repo_resolved.exists():
            raise RuntimeError(f"repo_root {repo_resolved} not exists")
        git_path = repo_resolved / ".git"
        if not (git_path.exists() or git_path.is_file()):
            raise RuntimeError(f"repo_root {repo_resolved} not git repo")

        self.session_root = session_resolved
        self.repo_root = repo_resolved
        self.run_id = run_id
        self.worktrees_root = self.session_root / ".fa" / "worktrees"
        self.worktrees_root.mkdir(parents=True, exist_ok=True)

    def _is_branch_checked_out_elsewhere(self, branch: str) -> tuple[bool, str]:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],  # noqa: S607
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            if not line.startswith("branch "):
                continue
            existing = (
                line.split("refs/heads/")[-1] if "refs/heads/" in line else line.replace("branch ", "", 1)
            )
            if existing == branch:
                return True, result.stdout
        return False, result.stdout

    def _resolve_base_branch(self, base_branch: str) -> str:
        for candidate in [base_branch, "main", "master", "HEAD"]:
            result = subprocess.run(  # noqa: S603 -- git binary trusted per ADR-6
                ["git", "rev-parse", "--verify", candidate],  # noqa: S607
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return candidate
        print(f"WARNING: base_branch {base_branch} not found, fallback to main")
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
            raise BranchAlreadyCheckedOutError(branch, details)

        resolved_base = self._resolve_base_branch(base_branch)

        cmd = ["git", "worktree", "add", str(worktree_path), "-b", branch, resolved_base]
        result = subprocess.run(  # noqa: S603 -- trusted binary per ADR-6
            cmd, cwd=self.repo_root, capture_output=True, text=True, timeout=15
        )

        if result.returncode != 0:
            if "already exists" in result.stderr and "branch" in result.stderr:
                cmd2 = ["git", "worktree", "add", str(worktree_path), branch]
                result2 = subprocess.run(  # noqa: S603 -- trusted binary per ADR-6
                    cmd2, cwd=self.repo_root, capture_output=True, text=True, timeout=10
                )
                if result2.returncode != 0:
                    raise RuntimeError(f"git worktree add failed: {result.stderr} | {result2.stderr}")
            else:
                raise RuntimeError(f"git worktree add failed: {result.stderr} (base {resolved_base})")

        if not worktree_path.exists():
            raise RuntimeError(f"worktree_path {worktree_path} not exists after add")
        if not worktree_path.is_dir():
            raise RuntimeError(f"worktree_path {worktree_path} not dir after add")

        list_result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],  # noqa: S607
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        found = False
        for line in list_result.stdout.splitlines():
            if line.startswith("worktree "):
                wt_path = line.replace("worktree ", "", 1).strip()
                if Path(wt_path).resolve() == worktree_path.resolve():
                    found = True
                    break
        if not found:
            raise RuntimeError(
                f"worktree {worktree_path} not in git worktree list after add: {list_result.stdout}"
            )

        return worktree_path

    @override
    def cleanup(self, path: Path) -> None:
        resolved = Path(path).resolve()
        subprocess.run(  # noqa: S603 -- trusted binary per ADR-6
            ["git", "worktree", "remove", "--force", str(resolved)],  # noqa: S607
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if resolved.exists():
            shutil.rmtree(resolved, ignore_errors=True)
        if resolved.exists():
            raise CleanupFailedError(resolved, "after remove --force + rmtree")
        subprocess.run(
            ["git", "worktree", "prune"],  # noqa: S607
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )


class WorktreeManagerFactory:
    """Factory based on feature_flags.worktree_mode, DI via SessionState.

    v0.1: only SharedDir is used (100% stable) per reduced surface principle.
    Isolated mode deferred to branch worktree-isolated, Factory returns SharedDir with warning.
    """

    @staticmethod
    def from_flags(flags: Any | None, session_root: Path, repo_root: Path, run_id: str = "") -> WorktreeManager:
        mode = getattr(flags, "worktree_mode", "shared") if flags else "shared"
        if mode == "isolated":
            print(
                "WARNING: worktree_mode=isolated requested but isolated deferred to branch "
                "worktree-isolated for v0.1 minimal surface, using shared. See ADR-14/15 v3. "
                "IsolatedWorktreeManager still importable directly for tests."
            )
        return SharedDirWorktreeManager(session_root, run_id=run_id)


__all__ = [
    "BranchAlreadyCheckedOutError",
    "CleanupFailedError",
    "IsolatedWorktreeManager",
    "SharedDirWorktreeManager",
    "WorktreeManager",
    "WorktreeManagerFactory",
    "_sanitize_task_id",
]
