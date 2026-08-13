#!/usr/bin/env python3
"""Shared helpers for targeted CI gates (mutmut and Semgrep).

This module is part of the CI Trusted Computing Base. All Git subprocesses are
bounded, list-form, and fail open with a visible diagnostic. Callers opt into
worktree/untracked discovery; existing committed-delta behavior remains default.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

__all__ = ["_log", "changed_python_files", "resolve_tool"]

GIT_TIMEOUT_SECONDS = 30


def _log(msg: str) -> None:
    """Write ``msg`` to stderr with a stable prefix."""
    print(f"[git-diff] {msg}", file=sys.stderr, flush=True)


def resolve_tool(
    name: str,
    *,
    repo_root: Path,
    venv_bin_rel: str | None = None,
) -> str | None:
    """Resolve one executable path; never return a shell fragment."""
    found = shutil.which(name)
    if found:
        return found
    if venv_bin_rel is not None:
        candidate = repo_root / venv_bin_rel
        if candidate.is_file():
            return str(candidate)
    return None


def _run_git(git: str, argv: list[str], *, repo_root: Path) -> subprocess.CompletedProcess[bytes] | None:
    try:
        result = subprocess.run(
            [git, *argv],
            cwd=repo_root,
            capture_output=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _log(f"git {' '.join(argv[:2])} failed: {exc}; skipping (fail-open)")
        return None
    if result.returncode != 0:
        _log(f"git {' '.join(argv[:2])} returned {result.returncode}; skipping (fail-open)")
        return None
    return result


def _decode_nul_paths(payload: bytes, *, command: str) -> list[str] | None:
    try:
        return [item.decode("utf-8", errors="strict") for item in payload.split(b"\0") if item]
    except UnicodeDecodeError as exc:
        _log(f"{command} emitted a non-UTF-8 path: {exc}; skipping (fail-open)")
        return None


def _merge_base(git: str, repo_root: Path, candidates: tuple[str, ...]) -> str | None:
    for ref in candidates:
        result = _run_git(git, ["merge-base", "HEAD", ref], repo_root=repo_root)
        if result is None:
            continue
        try:
            value = result.stdout.strip().decode("ascii", errors="strict")
        except UnicodeDecodeError:
            continue
        if value:
            return value
    _log("no merge-base found; skipping (fail-open)")
    return None


def _collect_names(
    git: str,
    repo_root: Path,
    *,
    base: str,
    diff_filter: str,
    include_worktree: bool,
    include_untracked: bool,
) -> list[str] | None:
    commands: list[tuple[str, list[str]]] = [
        (
            "committed diff",
            ["diff", "--name-only", "-z", f"--diff-filter={diff_filter}", f"{base}...HEAD"],
        )
    ]
    if include_worktree:
        commands.append(("worktree diff", ["diff", "--name-only", "-z", f"--diff-filter={diff_filter}", "HEAD"]))
    if include_untracked:
        commands.append(("untracked files", ["ls-files", "--others", "--exclude-standard", "-z"]))

    names: list[str] = []
    for label, argv in commands:
        result = _run_git(git, argv, repo_root=repo_root)
        if result is None:
            return None
        decoded = _decode_nul_paths(result.stdout, command=label)
        if decoded is None:
            return None
        names.extend(decoded)
    return names


def changed_python_files(
    repo_root: Path,
    *,
    base_candidates: tuple[str, ...] = ("origin/main", "main", "HEAD~1"),
    source_prefixes: tuple[str, ...] = ("src/", "tests/"),
    allow_extensions: tuple[str, ...] = (".py",),
    max_files: int = 50,
    diff_filter: str = "ACMR",
    include_worktree: bool = False,
    include_untracked: bool = False,
) -> list[Path]:
    """Return contained changed Python files, or ``[]`` on any discovery failure.

    The committed merge-base delta is always queried. ``include_worktree`` adds
    staged and unstaged tracked files; ``include_untracked`` adds non-ignored
    untracked files. All filename-producing commands use NUL delimiters.
    """
    git = resolve_tool("git", repo_root=repo_root)
    if git is None:
        _log("git not found on PATH; skipping (fail-open)")
        return []
    base = _merge_base(git, repo_root, base_candidates)
    if base is None:
        return []
    names = _collect_names(
        git,
        repo_root,
        base=base,
        diff_filter=diff_filter,
        include_worktree=include_worktree,
        include_untracked=include_untracked,
    )
    if names is None:
        return []

    canonical_root = repo_root.resolve()
    files: set[Path] = set()
    for name in names:
        if not name.endswith(allow_extensions):
            continue
        path = (repo_root / name).resolve()
        try:
            relative = path.relative_to(canonical_root).as_posix()
        except ValueError:
            continue
        if not any(relative.startswith(prefix) for prefix in source_prefixes):
            continue
        if path.is_file():
            files.add(path)

    if len(files) > max_files:
        _log(f"{len(files)} changed files > max_files={max_files}; skipping (fail-open)")
        return []
    return sorted(files)
