"""Shared utilities for the hook installer and status checker.

Both :mod:`fa.hygiene.hooks.install` and :mod:`fa.hygiene.hooks.status`
need the same workspace-resolution and script-directory helpers.
Centralising them here avoids DRY violations and ensures a single
place to update if the workspace marker or script layout changes.
"""

from __future__ import annotations

from pathlib import Path


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
