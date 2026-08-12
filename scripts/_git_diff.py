#!/usr/bin/env python3
"""Shared helpers for targeted CI gates (``run_targeted_mutmut``, ``run_targeted_semgrep``).

Extracted from two near-identical inline copies to remove the R0801
duplicate-code finding (the two scripts had ~35 lines of git
merge-base/diff boilerplate each) AND to close a argv-form bug where one
copy's fallback built a shell-style string instead of an argv list.

This module is part of the CI Trusted Computing Base: weakening the
fail-open / scoping logic here would silence every targeted gate that
imports it. Treat edits as TCB changes (CODEOWNERS-locked, reviewed).

Design notes
------------
* Stdlib-only. No third-party imports; this keeps the helper importable
  in environments that have not run ``uv sync`` yet (e.g. early preflight).
* All failures are fail-open with a ``[git-diff]`` stderr note. Targeted
  gates must never block a push because their helper raised.
* Subprocess calls are always list-form, never ``shell=True``. Filenames
  with shell metacharacters (newlines, ``;``, ``$()``) are therefore
  safe.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

__all__ = ["_log", "changed_python_files", "resolve_tool"]


def _log(msg: str) -> None:
    """Write ``msg`` to stderr with a ``[git-diff]`` prefix; no flake."""
    print(f"[git-diff] {msg}", file=sys.stderr, flush=True)


def resolve_tool(
    name: str,
    *,
    repo_root: Path,
    venv_bin_rel: str | None = None,
) -> str | None:
    """Resolve a single executable by name.

    Search order:

    1. ``shutil.which(name)`` (PATH lookup; covers ``uv run`` PATH where
       ``.venv/bin`` is injected, and normal CI environments).
    2. If ``venv_bin_rel`` is given, ``repo_root / venv_bin_rel`` when
       that path ``is_file()``.

    Returns an absolute path string suitable for use as ``argv[0]`` in a
    list-form ``subprocess.run([...], shell=False)`` call. Returns
    ``None`` when neither candidate exists.

    IMPORTANT: this function returns ONLY single-binary paths. It does
    NOT return shell-style strings like ``"/usr/bin/uv tool run"``. When
    the desired invocation is a subcommand chain (e.g. ``uv tool run
    semgrep``), the caller builds the argv list explicitly:
    ``[uv_path, "tool", "run", "--from", f"semgrep=={ver}", "semgrep", ...]``.
    """
    found = shutil.which(name)
    if found:
        return found
    if venv_bin_rel is not None:
        cand = repo_root / venv_bin_rel
        if cand.is_file():
            return str(cand)
    return None


def changed_python_files(
    repo_root: Path,
    *,
    base_candidates: tuple[str, ...] = ("origin/main", "main", "HEAD~1"),
    source_prefixes: tuple[str, ...] = ("src/", "tests/"),
    allow_extensions: tuple[str, ...] = (".py",),
    max_files: int = 50,
    diff_filter: str = "ACMR",
) -> list[Path]:
    """Return files changed vs merge-base that are in-scope for a gate.

    Parameters
    ----------
    repo_root:
        Repository root (parent of ``.git/``). Not required to actually
        be a git repo — the function fails open.
    base_candidates:
        Ordered refs to try as ``git merge-base HEAD <ref>``. The first
        that succeeds wins.
    source_prefixes:
        Posix-style relative path prefixes (relative to ``repo_root``)
        that the caller is interested in. Files outside these prefixes
        are dropped. Callers pass explicit prefixes; there is no
        default that implicitly covers scripts/ or tests/.
    allow_extensions:
        File extensions (including leading dot) to keep.
    max_files:
        Hard cap on returned files. If the filtered list exceeds this,
        returns an empty list with a fail-open log — the caller should
        treat that as "skip the gate, too much changed". The cap is
        applied AFTER prefix/extension filtering so callers can reason
        about their own scope. (``run_targeted_mutmut`` applies a
        SECOND, narrower cap after post-processing; both are honored.)
    diff_filter:
        ``--diff-filter`` value passed to ``git diff``. Default ``ACMR``
        = Added/Copied/Modified/Renamed (no deletions, since deleted
        files cannot be scanned or mutated).

    Returns
    -------
    Sorted, absolute, resolved ``list[Path]`` of existing files that
    match all restrictions. Returns ``[]`` (with a stderr note) on any
    failure or when the cap is exceeded. Never raises.
    """
    git = resolve_tool("git", repo_root=repo_root)
    if git is None:
        _log("git not found on PATH; skipping (fail-open)")
        return []

    base: str | None = None
    for ref in base_candidates:
        r = subprocess.run(
            [git, "merge-base", "HEAD", ref],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            base = r.stdout.strip()
            break
    if base is None:
        _log("no merge-base found; skipping (fail-open)")
        return []

    r = subprocess.run(
        [git, "diff", "--name-only", f"--diff-filter={diff_filter}", f"{base}...HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    files: list[Path] = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if not line.endswith(tuple(allow_extensions)):
            continue
        p = (repo_root / line).resolve()
        try:
            rel = p.relative_to(repo_root).as_posix()
        except ValueError:
            continue
        if not any(rel.startswith(prefix) for prefix in source_prefixes):
            continue
        if not p.is_file():
            continue
        files.append(p)

    if len(files) > max_files:
        _log(f"{len(files)} changed files > max_files={max_files}; skipping (fail-open)")
        return []

    return sorted(files)
