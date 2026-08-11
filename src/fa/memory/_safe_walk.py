"""Safe file iterator for memory-layer indexes (FTS, structural).

§I-S14b-4: Single source of truth for enumerating indexable files. Both
``fa.memory.search_index.SearchIndex`` and
``fa.memory.structural_index.StructuralIndex`` (S16) use this helper so
exclude-dirs, symlink containment, size-caps, and .gitignore handling stay
in lockstep.

Design (v2.1 G-2, G-4, G-6, G-10):

* **Fast path:** ``git ls-files --cached --others --exclude-standard``
  respects ``.gitignore`` out of the box — build artifacts, ``*.egg-info``,
  ``htmlcov/``, ``.mypy_cache/`` etc. are pruned by git itself without
  bloating our EXCLUDE_DIRS set.
* **Fallback:** raw ``os.walk`` with in-place dir prune, used when the
  workspace is not a git repo or the subprocess fails (timeout, missing
  git, permission error). Fail-degraded (BLE001 pattern): log WARNING and
  keep going — indexes are best-effort.
* **Symlink safety (INV-S14b-1):** every yielded path is
  ``fp.resolve().is_relative_to(root_resolved)``. A symlink to
  ``/etc/passwd`` or anywhere outside workspace root is silently skipped.
* **Size cap:** files larger than ``max_file_size`` bytes are skipped
  (prevents indexing giant minified bundles / generated artifacts).
* **Tests filter:** when ``include_tests=False``, files whose relpath
  starts with ``tests/`` or whose path contains ``/tests/`` are skipped.

This module imports only stdlib + ``fa.memory.fts_index.EXCLUDE_DIRS`` to
avoid circular imports with higher layers.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

from fa.memory.fts_index import EXCLUDE_DIRS as _BASE_EXCLUDE_DIRS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exclude configuration (v2.1 G-4, G-10)
# ---------------------------------------------------------------------------

#: Directory basenames excluded IN ADDITION to fts_index.EXCLUDE_DIRS.
#: Keep small; prefer .gitignore coverage whenever possible.
EXTRA_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".tox",
        ".pytest_cache",
        ".ruff_cache",
        ".nox",
        "htmlcov",
    }
)

#: Basename glob patterns for directories/files to exclude. Applied via
#: ``fnmatch.fnmatch(basename, pat)`` against each path component. Covers
#: cases like ``first_agent.egg-info/`` that can't be enumerated as a
#: literal basename.
EXCLUDE_DIR_GLOBS: frozenset[str] = frozenset(
    {
        "*.egg-info",
        "*.egg",
    }
)

#: Default file-extension patterns (matches globs in fts_index.py:115 area).
DEFAULT_PATTERNS: tuple[str, ...] = (
    "*.py",
    "*.md",
    "*.txt",
    "*.rst",
    "*.json",
    "*.yaml",
    "*.yml",
    "*.toml",
    "*.ini",
    "*.cfg",
    "*.html",
    "*.css",
    "*.js",
    "*.ts",
    "*.tsx",
    "*.jsx",
    "*.sh",
)


def _path_is_excluded(
    rel_parts: tuple[str, ...],
    extra_exclude: frozenset[str] | None = None,
) -> bool:
    """Return True if any path component matches an exclude rule.

    ``extra_exclude`` is a frozenset of additional directory basenames
    supplied by the caller (union with base excludes). This function is
    invoked for *every* git-ls-files result and for defense-in-depth in
    the os.walk path; it must stay O(depth * patterns).
    """
    effective: set[str] = set(_BASE_EXCLUDE_DIRS) | set(EXTRA_EXCLUDE_DIRS)
    if extra_exclude:
        effective = effective | set(extra_exclude)
    for part in rel_parts:
        if part in effective:
            return True
        for pat in EXCLUDE_DIR_GLOBS:
            if fnmatch.fnmatch(part, pat):
                return True
        # Dot-dirs (other than "."/"..") are pruned by os.walk already;
        # defense-in-depth for the git-ls-files path (which can return
        # dotfiles if force-added).
        if part.startswith(".") and part not in (".", "..") and part in effective:
            return True
    return False


def _matches_any_pattern(rel: str, basename: str, patterns: tuple[str, ...]) -> bool:
    """Return True if relpath or basename matches any fnmatch pattern."""
    for pat in patterns:
        if fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(rel, pat):
            return True
    return False


def _git_ls_files(root: Path, timeout: float = 5.0) -> list[str] | None:
    """Return list of relpaths from git, or None on any failure.

    Resolves ``git`` to an absolute path via ``shutil.which`` to satisfy
    bandit S607 (no partial-executable-path subprocess invocation).
    Uses ``--cached --others --exclude-standard`` which is the same flag
    set used by ``glob.py``'s ``git_ls_files`` helper in the existing
    codebase (cross-checked in preflight).
    """
    git_bin = shutil.which("git")
    if git_bin is None:
        logger.debug("git binary not found on PATH; using os.walk fallback")
        return None
    try:
        res = subprocess.run(  # noqa: S603 - argv list, git_bin resolved via shutil.which
            [
                git_bin,
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if res.returncode != 0:
            logger.warning(
                "git ls-files exited %d: %s; falling back to os.walk",
                res.returncode,
                res.stderr.strip()[:200],
            )
            return None
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("git ls-files failed (%s); falling back to os.walk", exc)
        return None


def _walk_fallback(
    root_resolved: Path,
    patterns: tuple[str, ...],
    effective_exclude: set[str],
    max_file_size: int,
) -> Iterator[tuple[Path, str, float, int]]:
    """os.walk-based fallback when git is unavailable.

    Containment invariant: every yielded ``resolved`` path satisfies
    ``resolved.is_relative_to(root_resolved)``. Symlinks that resolve
    outside the root are skipped (escape prevention). Duplicate
    resolution (e.g. an in-tree symlink pointing at another in-tree
    file) is deduplicated by the resolved path so we never yield the
    same underlying inode twice.
    """
    seen_resolved: set[Path] = set()
    for dirpath, dirnames, filenames in os.walk(root_resolved, followlinks=False):
        # In-place prune (critical — mutates dirnames to prevent descent).
        dirnames[:] = [
            d
            for d in dirnames
            if d not in effective_exclude
            and not d.startswith(".")
            and not any(fnmatch.fnmatch(d, g) for g in EXCLUDE_DIR_GLOBS)
        ]
        dp = Path(dirpath)
        for fname in filenames:
            fp = dp / fname
            try:
                resolved = fp.resolve()
                if not resolved.is_relative_to(root_resolved):
                    continue
                if resolved in seen_resolved:
                    continue
                # Use the ON-DISK relative path (through any symlink we
                # traversed via dp) for reporting/rel, but READ from
                # the resolved real path. This keeps containment checks
                # sound while reporting the path the operator navigated to.
                rel = str(fp.relative_to(root_resolved))
                if not _matches_any_pattern(rel, fname, patterns):
                    continue
                st = resolved.stat()
                if not resolved.is_file():
                    continue
                if max_file_size > 0 and st.st_size > max_file_size:
                    continue
                seen_resolved.add(resolved)
                yield (resolved, rel, st.st_mtime, st.st_size)
            except (OSError, ValueError) as exc:
                logger.warning("skipping %s during walk: %s", fp, exc)
                continue


def iter_searchable_files(
    root: Path,
    patterns: tuple[str, ...] = DEFAULT_PATTERNS,
    *,
    extra_exclude_dirs: frozenset[str] | None = None,
    include_tests: bool = True,
    max_file_size: int = 200_000,
    use_git_ls_files: bool = True,
) -> Iterator[tuple[Path, str, float, int]]:
    """Yield ``(absolute_path, relpath_str, st_mtime, st_size)`` for files
    that pass every filter.

    Parameters
    ----------
    root:
        Workspace root (resolved by the caller OR resolved here — both
        work; we always resolve internally for the is_relative_to check).
    patterns:
        fnmatch patterns for filenames/relpaths to include.
    extra_exclude_dirs:
        Additional directory basenames to exclude (union with
        ``_BASE_EXCLUDE_DIRS | EXTRA_EXCLUDE_DIRS``).
    include_tests:
        If False, any path whose relpath contains a ``tests`` directory
        component (or starts with ``tests/``) is skipped.
    max_file_size:
        Soft cap in bytes; files larger than this are skipped. ``0`` or
        negative means unlimited.
    use_git_ls_files:
        If True (default), tries ``git ls-files`` fast path first.
    """
    root_resolved = root.resolve()
    if not root_resolved.is_dir():
        raise NotADirectoryError(f"workspace root is not a directory: {root_resolved}")

    effective_exclude: set[str] = set(_BASE_EXCLUDE_DIRS) | set(EXTRA_EXCLUDE_DIRS)
    if extra_exclude_dirs:
        effective_exclude = effective_exclude | set(extra_exclude_dirs)
    if not include_tests:
        effective_exclude.add("tests")

    # --- Fast path: git ls-files -------------------------------------------
    files_from_git: list[str] | None = None
    if use_git_ls_files:
        files_from_git = _git_ls_files(root_resolved)

    if files_from_git is not None:
        for rel in files_from_git:
            # Normalize to POSIX-style relpath (git always outputs /)
            rel_norm = rel.replace("\\", "/")
            parts = tuple(rel_norm.split("/"))
            # Exclude-dir check on every component (defense in depth —
            # git already prunes via .gitignore but force-added files
            # inside .fa/, node_modules/, etc. must not be indexed).
            if _path_is_excluded(parts, extra_exclude=extra_exclude_dirs):
                continue
            # Re-implement the tests/ filter (git ls-files returns them).
            if not include_tests and "tests" in parts:
                continue
            fname = parts[-1] if parts else ""
            if not _matches_any_pattern(rel_norm, fname, patterns):
                continue
            fp = root_resolved / rel_norm
            try:
                resolved = fp.resolve()
                if not resolved.is_relative_to(root_resolved):
                    continue
                if not resolved.is_file():
                    continue
                st = resolved.stat()
                if max_file_size > 0 and st.st_size > max_file_size:
                    continue
                yield (resolved, rel_norm, st.st_mtime, st.st_size)
            except (OSError, ValueError) as exc:
                logger.warning("skipping %s from git ls-files: %s", fp, exc)
                continue
        return

    # --- Fallback: os.walk -------------------------------------------------
    yield from _walk_fallback(root_resolved, patterns, effective_exclude, max_file_size)


__all__ = [
    "DEFAULT_PATTERNS",
    "EXCLUDE_DIR_GLOBS",
    "EXTRA_EXCLUDE_DIRS",
    "iter_searchable_files",
]
