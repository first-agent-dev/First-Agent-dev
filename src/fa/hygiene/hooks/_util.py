"""Shared utilities for the hook installer and status checker.

Both :mod:`fa.hygiene.hooks.install` and :mod:`fa.hygiene.hooks.status`
need the same workspace-resolution, git-dir, and script-directory helpers.
Centralising them here avoids DRY violations and ensures a single
place to update if the workspace marker or hook-seat layout changes.
"""

from __future__ import annotations

import os
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

    For a normal checkout, this is ``<repo>/.git/hooks``. For a git
    worktree, hooks live in the *common* git dir recorded by the
    worktree gitdir's ``commondir`` file, not under the worktree-specific
    gitdir itself.
    """

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
