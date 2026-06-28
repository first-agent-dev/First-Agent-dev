"""Shared utilities for the hook installer and status checker.

Both :mod:`fa.hygiene.hooks.install` and :mod:`fa.hygiene.hooks.status`
need the same workspace-resolution, git-dir, and script-directory helpers.
Centralising them here avoids DRY violations and ensures a single
place to update if the workspace marker or hook-seat layout changes.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

HOOK_NAMES: tuple[str, ...] = (
    "pre-commit",
    "prepare-commit-msg",
    "commit-msg",
)


def scripts_dir() -> Path:
    """Return the directory holding the bash hook scripts."""

    return Path(__file__).resolve().parent


def resolve_repo_root(start: Path) -> Path:
    """Anchor-on-cwd workspace resolution per AGENTS.md (no walk-up).

    Raises :class:`SystemExit` if *start* is not a First-Agent
    workspace (identified by ``knowledge/llms.txt`` at the root).
    """

    if (start / "knowledge" / "llms.txt").is_file():
        return start
    raise SystemExit("fa.hygiene.hooks: not a First-Agent workspace (no knowledge/llms.txt at cwd)")


def resolve_git_dir(repo_root: Path) -> Path:
    """Return the effective git dir for *repo_root*.

    Supports both normal checkouts (``.git`` directory) and git worktrees
    (``.git`` file containing ``gitdir: ...``). If ``GIT_DIR`` is present,
    trust it first — Git sets it when running hooks.
    """

    env_git_dir = os.environ.get("GIT_DIR")
    if env_git_dir:
        return Path(env_git_dir)

    dotgit = repo_root / ".git"
    if dotgit.is_dir():
        return dotgit
    if dotgit.is_file():
        try:
            raw = dotgit.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SystemExit(f"fa.hygiene.hooks: could not read {dotgit}: {exc}") from exc
        prefix = "gitdir:"
        if not raw.startswith(prefix):
            raise SystemExit(
                f"fa.hygiene.hooks: unsupported {dotgit} format; expected 'gitdir: <path>'"
            )
        gitdir = Path(raw[len(prefix):].strip())
        if not gitdir.is_absolute():
            gitdir = (dotgit.parent / gitdir).resolve()
        return gitdir
    return dotgit


def resolve_hooks_dir(repo_root: Path) -> Path:
    """Return the effective hooks directory for *repo_root*.

    First asks git itself via ``git rev-parse --git-path hooks`` so
    ``core.hooksPath`` (when set) and worktree/common-dir rules are
    honored exactly the way Git will honor them at runtime. If git is
    unavailable or the command fails, falls back to pure-Python
    resolution via ``resolve_git_dir()`` and an optional ``commondir``
    file for worktree layouts.
    """

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks"],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError):
        result = None
    if result is not None:
        raw = result.stdout.strip()
        if raw:
            hooks = Path(raw)
            if not hooks.is_absolute():
                hooks = (repo_root / hooks).resolve()
            return hooks

    git_dir = resolve_git_dir(repo_root)
    commondir = git_dir / "commondir"
    if commondir.is_file():
        try:
            raw = commondir.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SystemExit(f"fa.hygiene.hooks: could not read {commondir}: {exc}") from exc
        common = Path(raw)
        if not common.is_absolute():
            common = (git_dir / common).resolve()
        return common / "hooks"
    return git_dir / "hooks"
