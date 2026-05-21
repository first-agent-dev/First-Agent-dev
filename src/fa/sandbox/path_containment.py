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

import os
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ContainmentResult",
    "contains_traversal",
    "contains_unresolved_variable",
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


def contains_unresolved_variable(path_str: str) -> bool:
    """Return True if ``path_str`` still has a ``$`` after env expansion.

    Sibling guard to :func:`contains_traversal` for shell variable
    expansion. The classifier tokenises with ``shlex`` (no expansion);
    bash later runs the command via ``shell=True`` and **does** expand
    ``$VAR`` / ``${VAR}``. If the variable is undefined at execution
    time, bash substitutes the empty string, which silently shifts the
    path's depth. Example: ``rm $UNDEFINED/escape`` tokenises as
    ``["rm", "$UNDEFINED/escape"]`` → containment sees
    ``<base>/$UNDEFINED/escape`` (inside base, allowed); bash sees
    ``rm /escape`` (top-level system path, denied). The fix is to
    refuse the path entirely when expansion would leave residual
    ``$`` markers. (Devin Review finding 2026-05-20 on PR #23 —
    same class as the tilde bypass.)

    :func:`os.path.expandvars` expands any variables present in the
    **agent process** environment; remaining ``$`` markers therefore
    mean either (a) an undefined variable or (b) a literal ``$`` in
    a filename. Both cases are rare enough under FA's UC1+UC3 single-
    user scope that a blanket reject is the right minimalism-first
    default.
    """
    return "$" in os.path.expandvars(path_str)


def resolve_against(target: str | Path, base: Path) -> Path | None:
    """Resolve ``target`` relative to ``base``, following symlinks.

    Tilde (``~``) is expanded on the **raw target before joining** so
    that bash-style home references like ``~/secret`` resolve to
    ``$HOME/secret`` instead of being silently neutralised into
    ``<base>/~/secret`` (where the ``~`` is no longer at the start and
    :meth:`Path.expanduser` becomes a no-op). Without this, a tilde
    target would pass containment because ``<base>/~/secret`` IS inside
    ``<base>``, but bash would later expand the ``~`` at execution time
    and write outside the workspace \u2014 Devin Review finding 2026-05-20
    on PR #23.

    Environment variables (``$HOME``, ``${HOME}``, ``$WORKSPACE_ROOT``)
    are expanded next via :func:`os.path.expandvars` so the canonical
    comparison uses whatever bash will see at execution time. Any
    variable that is still **undefined** in the agent process leaves
    a literal ``$`` in the result — the sibling :func:`is_contained`
    rejects that case upstream via :func:`contains_unresolved_variable`
    so this function only ever sees fully-resolved strings.

    If the expanded target is absolute, it is used as-is and any
    containment escape is caught by the downstream
    :func:`is_contained` comparison. Otherwise the (relative) expanded
    target is joined to ``base`` and the join is resolved.

    Returns the canonical absolute Path, or None on resolution failure
    (e.g. symlink loop, permission error). ``strict=False`` so that
    not-yet-existing files inside the workspace (e.g. files the agent
    is about to create) do not fail the check.
    """
    try:
        expanded = os.path.expandvars(str(target))
        target_path = Path(expanded).expanduser()
        candidate = target_path if target_path.is_absolute() else (base / target_path)
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

    if contains_unresolved_variable(target_str):
        return ContainmentResult(
            contained=False,
            canonical_target=None,
            reason=(
                f"path contains unresolved shell variable: {target_str!r} "
                "(bash will expand `$VAR` at execution time, which can "
                "escape the workspace if the variable is undefined)"
            ),
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
