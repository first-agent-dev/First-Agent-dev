"""Symlink-safe path containment for FA's bash sandbox.

Borrowed from Aperant ``apps/desktop/src/main/ai/security/path-containment.ts``
(147 LOC). Three-step containment check:

1. Lexical pre-pass — reject obvious ``..`` traversal components.
2. Resolution — collapse symlinks against the workspace base.
3. Containment — verify the canonical target is inside the canonical
   base.

Differences from Aperant:

- **No Windows-case-lowering.** Aperant lowercases on ``win32`` because
  NTFS is case-insensitive. FA targets Linux / macOS where the
  filesystem is case-preserving and the agent must respect case.
- **No write-access check.** Containment is orthogonal to read/write
  policy; the ADR-6 §Policy file already enforces glob-based scopes,
  and the bash gate consumes those separately.

The lexical pre-pass is partially redundant with ``Path.resolve()``
(which collapses ``..``) but produces a clearer error message and
rejects paths whose author *intended* traversal even when collapsing
happens to land inside the base.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ContainmentResult",
    "contains_traversal",
    "is_contained",
    "resolve_against",
]


@dataclass(frozen=True)
class ContainmentResult:
    """Outcome of an ``is_contained`` check.

    ``contained`` is the boolean answer; ``canonical_target`` is the
    resolved absolute path when resolution succeeded (None on failure);
    ``reason`` is a short human-readable explanation that the gate
    surfaces in its decision message.
    """

    contained: bool
    canonical_target: Path | None
    reason: str


def contains_traversal(path_str: str) -> bool:
    """Return True if ``path_str`` contains a literal ``..`` component.

    Used as a lexical pre-pass before ``resolve()`` so the gate can
    surface a clearer error than "resolved path X is outside base Y".
    """
    parts = Path(path_str).parts
    return ".." in parts


def resolve_against(target: str | Path, base: Path) -> Path | None:
    """Resolve ``target`` relative to ``base``, following symlinks.

    Returns the canonical absolute Path, or None on resolution failure
    (e.g. symlink loop, permission error). ``strict=False`` so that
    not-yet-existing files inside the workspace (e.g. files the agent
    is about to create) do not fail the check.
    """
    try:
        candidate = (base / target).expanduser()
        return candidate.resolve(strict=False)
    except (OSError, RuntimeError):
        return None


def is_contained(target: str | Path, base: Path) -> ContainmentResult:
    """Check whether ``target`` resolves inside ``base``.

    Two-pass: lexical pre-check on the raw input, then canonical check
    via ``resolve()``. Both must pass for ``contained=True``. The
    canonical base is itself resolved so that the comparison is between
    canonical absolute paths.
    """
    target_str = str(target)

    if contains_traversal(target_str):
        return ContainmentResult(
            contained=False,
            canonical_target=None,
            reason=f"path contains `..` traversal component: {target_str!r}",
        )

    canonical = resolve_against(target_str, base)
    if canonical is None:
        return ContainmentResult(
            contained=False,
            canonical_target=None,
            reason=f"could not resolve path: {target_str!r}",
        )

    canonical_base = base.resolve(strict=False)
    try:
        canonical.relative_to(canonical_base)
    except ValueError:
        return ContainmentResult(
            contained=False,
            canonical_target=canonical,
            reason=(f"resolved path {canonical!s} is outside base {canonical_base!s}"),
        )
    return ContainmentResult(
        contained=True,
        canonical_target=canonical,
        reason="ok",
    )
