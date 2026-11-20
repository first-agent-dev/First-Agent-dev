"""
WorktreeManager Abstraction — SharedDir primary for v0.1 (100% stable) per ADR-14/15 v3 reduced surface

IsolatedWorktreeManager is retained only for historical direct-test compatibility.
It is not a supported product route; the factory refuses isolated mode.

Per Q1, custom BranchAlreadyCheckedOutError and CleanupFailedError exceptions include git worktree details.
Safety-critical checks do not use assert; asserts are limited to internal invariants
(compliance-by-construction §1.2.5).
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, override

logger = logging.getLogger(__name__)


class BranchAlreadyCheckedOutError(RuntimeError):
    """Branch already checked out elsewhere — fail-fast with git worktree list details."""

    def __init__(self, branch: str, details: str):
        super().__init__(
            f"Branch {branch} already checked out elsewhere. Details:\n{details}\n"
            f"Create new branch name or remove old worktree via git worktree remove."
        )
        self.branch = branch
        self.details = details


class WorktreeProbeError(RuntimeError):
    """`git worktree list` failed, so branch occupancy could not be established.

    Distinct from `BranchAlreadyCheckedOutError` on purpose: that one says the
    branch *is* taken, this one says the question could not be answered. The
    caller must refuse either way, but an operator reading the log needs to know
    which — "create a different name" is the wrong advice for a broken probe.
    """

    def __init__(self, branch: str, returncode: int, stderr: str) -> None:
        super().__init__(
            f"Could not establish whether branch {branch!r} is checked out elsewhere: "
            f"`git worktree list --porcelain` exited {returncode}. Refusing to create a "
            f"worktree on an unproven branch. stderr:\n{stderr}"
        )
        self.branch = branch
        self.returncode = returncode
        self.stderr = stderr


class CleanupFailedError(AssertionError, RuntimeError):
    """Cleanup failed after remove --force; path still exists (AssertionError-compatible)."""

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
        logger.warning(f"task_id empty after sanitization, original='{original}', using deterministic fallback")

    hash_input = f"{original}:{run_id}".encode()
    short_hash = hashlib.sha256(hash_input).hexdigest()[:8]
    return f"task-{short_hash}"


SUBAGENT_ARTIFACT_DIRNAME = "subagents"


def subagent_artifact_root(session_workspace: Path, task_id: str, run_id: str = "") -> Path:
    """Return the artifact directory for one subagent task (Q11-B Option A).

    ``<session_workspace>/.fa/subagents/<sanitized_task_id>/``

    **Single source of truth.** V24/V25 were two faces of one defect: the
    sandbox gate and the executor each derived their own idea of where a
    subagent may write, and disagreed. Every caller now goes through this
    function, so the gate and the runner cannot drift apart — a
    compliance-by-construction fix rather than a second guard.

    The path is *derived*, not created; callers that need the directory to
    exist call :func:`ensure_subagent_artifact_root`. Task ids are sanitized by
    :func:`_sanitize_task_id`, which strips everything outside
    ``[A-Za-z0-9-_]`` and falls back to a deterministic hash, so a hostile id
    such as ``../../etc`` cannot traverse out of the subagents directory.
    """
    clean_id = _sanitize_task_id(task_id, run_id=run_id)
    return Path(session_workspace).resolve() / ".fa" / SUBAGENT_ARTIFACT_DIRNAME / clean_id


def ensure_subagent_artifact_root(session_workspace: Path, task_id: str, run_id: str = "") -> Path:
    """Create and return the artifact root for a task.

    Failure to create it must **deny the spawn** rather than fall back to the
    session workspace (V18): a subagent that cannot get its own directory is
    not a subagent that should be allowed to write into the main tree.
    """
    root = subagent_artifact_root(session_workspace, task_id, run_id=run_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


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
        """Return the shared session root.

        **Not the subagent write root.** Since S5.6 the subagent artifact
        directory comes from :func:`subagent_artifact_root` via
        ``SessionState.create_subagent_workspace``, which is the only
        production caller on that path. This method is retained for the
        ``WorktreeManager`` interface and for direct/legacy callers, and still
        answers the question it was written for — *"where does shared mode put
        work?"* — which is the session root by definition.

        Do not route a subagent here: returning the session root as a write
        root is precisely the V18 defect that S5.6 removed.
        """
        _ = _sanitize_task_id(task_id, run_id=self.run_id)
        return self.session_root

    @override
    def cleanup(self, path: Path) -> None:
        resolved = Path(path).resolve()
        if resolved != self.session_root:
            raise CleanupFailedError(resolved, f"cleanup called on non-session_root {path} in SharedDir mode")
        return


class IsolatedWorktreeManager(WorktreeManager):
    """Historical host-Git implementation, retained for direct characterization only.

    No supported product caller uses this class; ``WorktreeManagerFactory``
    rejects isolated mode. Managed subagents use R13 instead.
    """

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
        """Whether another worktree already holds `branch`, fail-closed.

        This is a safety check: its answer decides whether a worktree may be
        created at all. Reading `stdout` without looking at `returncode` turned
        a *failure to check* into the answer "nobody holds this branch", so a
        git error (locked index, unreadable repository, timeout) would let the
        caller create a worktree on top of a branch that is already checked
        out. Absent evidence is therefore reported as an error, never as False.
        """
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],  # noqa: S607
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,  # the verdict is inspected below; a raised error would hide its stderr
        )
        if result.returncode != 0:
            raise WorktreeProbeError(branch, result.returncode, result.stderr)
        for line in result.stdout.splitlines():
            if not line.startswith("branch "):
                continue
            existing = line.split("refs/heads/")[-1] if "refs/heads/" in line else line.replace("branch ", "", 1)
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
                check=False,  # a non-zero exit IS the answer: this candidate does not exist
            )
            if result.returncode == 0:
                return candidate
        logger.warning(f"base_branch {base_branch} not found, fallback to main")
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
            cmd, cwd=self.repo_root, capture_output=True, text=True, timeout=15, check=False
        )  # check=False: the non-zero exit is classified below, with git's own stderr

        if result.returncode != 0:
            if "already exists" in result.stderr and "branch" in result.stderr:
                cmd2 = ["git", "worktree", "add", str(worktree_path), branch]
                result2 = subprocess.run(  # noqa: S603 -- trusted binary per ADR-6
                    cmd2, cwd=self.repo_root, capture_output=True, text=True, timeout=10, check=False
                )  # check=False: reported as a refusal below, not as an exception
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
            check=False,  # reported below: a failed listing must not read as "not registered"
        )
        if list_result.returncode != 0:
            raise RuntimeError(
                f"could not verify that worktree {worktree_path} is registered: "
                f"`git worktree list --porcelain` exited {list_result.returncode}. stderr:\n{list_result.stderr}"
            )
        found = False
        for line in list_result.stdout.splitlines():
            if line.startswith("worktree "):
                wt_path = line.replace("worktree ", "", 1).strip()
                if Path(wt_path).resolve() == worktree_path.resolve():
                    found = True
                    break
        if not found:
            raise RuntimeError(f"worktree {worktree_path} not in git worktree list after add: {list_result.stdout}")

        return worktree_path

    @override
    def cleanup(self, path: Path) -> None:
        """Remove a worktree and leave git's bookkeeping consistent.

        The filesystem is the verdict — `exists()` after the attempts below is
        what decides success — but git's own status is still reported rather
        than dropped: a `worktree remove` that failed on a live worktree, or a
        `prune` that failed to run, is the state that makes the *next* creation
        fail confusingly, and it would otherwise leave no trace at all.
        """
        resolved = Path(path).resolve()
        removed = subprocess.run(  # noqa: S603 -- trusted binary per ADR-6
            ["git", "worktree", "remove", "--force", str(resolved)],  # noqa: S607
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,  # the filesystem verdict below is authoritative
        )
        if resolved.exists():
            shutil.rmtree(resolved, ignore_errors=True)
        if resolved.exists():
            raise CleanupFailedError(
                resolved,
                "after remove --force + rmtree"
                + (
                    ""
                    if removed.returncode == 0
                    else f"; `git worktree remove` exited {removed.returncode}: {removed.stderr.strip()}"
                ),
            )
        if removed.returncode != 0:
            # The bytes are gone but git's record is not: prune below is the
            # repair path, and its own failure is what an operator must see.
            logger.warning(
                "worktree remove for %s exited %s (bytes removed anyway): %s",
                resolved,
                removed.returncode,
                removed.stderr.strip(),
            )
        pruned = subprocess.run(
            ["git", "worktree", "prune"],  # noqa: S607
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,  # reported, not raised: cleanup already succeeded physically
        )
        if pruned.returncode != 0:
            logger.warning(
                "git worktree prune exited %s after cleaning %s: %s",
                pruned.returncode,
                resolved,
                pruned.stderr.strip(),
            )


class WorktreeManagerFactory:
    """Factory based on feature_flags.worktree_mode, DI via SessionState.

    v0.1: only SharedDir is used (100% stable) per reduced surface principle.
    Isolated mode deferred to branch worktree-isolated, Factory returns SharedDir with warning.
    """

    @staticmethod
    def from_flags(flags: Any | None, session_root: Path, repo_root: Path, run_id: str = "") -> WorktreeManager:
        """Return the manager for the configured mode, or refuse (V19).

        An unsupported mode raises instead of quietly returning ``SharedDir``.
        Silently downgrading is the failure mode this project's own test header
        cites as prior art (Claude Code #55708 / #47548 / #31546: an
        ``isolation:worktree`` parameter that is accepted and ignored). The
        operator asks for isolation, does not get it, and is never told — so
        they reason about a boundary that is not there.

        ``isolated`` is retired from supported product use under Q126-A.
        The historical manager remains available only for direct characterization
        tests; it is not an upgrade path or a product fallback. Refusing here says
        "not available", which is true, rather than "done", which is not.
        """
        del repo_root  # SharedDir needs only the session root; isolated mode is unsupported.
        mode = getattr(flags, "worktree_mode", "shared") if flags else "shared"
        if mode != "shared":
            raise ValueError(
                f"worktree_mode={mode!r} is not supported; only 'shared' is available in v0.1. "
                "Isolated worktrees are deferred (ADR-14/15 v3) — set worktree.mode: shared, "
                "or construct IsolatedWorktreeManager directly if you are testing that path."
            )
        return SharedDirWorktreeManager(session_root, run_id=run_id)


__all__ = [
    "SUBAGENT_ARTIFACT_DIRNAME",
    "BranchAlreadyCheckedOutError",
    "CleanupFailedError",
    "IsolatedWorktreeManager",
    "SharedDirWorktreeManager",
    "WorktreeManager",
    "WorktreeManagerFactory",
    "WorktreeProbeError",
    "_sanitize_task_id",
    "ensure_subagent_artifact_root",
    "subagent_artifact_root",
]
