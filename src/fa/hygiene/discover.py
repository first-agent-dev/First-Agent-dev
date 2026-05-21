"""Canonical AI-agent config-file probe list (R-13).

Ports Gortex ``internal/audit/discover.go`` (83 LOC) — the small
ordered list of agent-config files an audit pass probes. The order
matches Gortex; do not shuffle without re-justifying.

Each entry is given as a repo-relative path. Callers are responsible
for joining the workspace root (per AGENTS.md §Workspace resolution).
The function returns a ``tuple[Path, ...]`` so callers can iterate
without worrying about accidental mutation.
"""

from __future__ import annotations

from pathlib import Path

_PROBE_LIST: tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
    "CONVENTIONS.md",
    "GEMINI.md",
    "CURSOR.md",
    ".cursorrules",
    ".github/copilot-instructions.md",
    ".aider.conf.yml",
    "ROO.md",
    "WINDSURF.md",
    "OPENCODE.md",
)


def default_config_paths() -> tuple[Path, ...]:
    """Return the canonical probe list as repo-relative :class:`Path`s."""

    return tuple(Path(name) for name in _PROBE_LIST)


__all__ = ["default_config_paths"]
