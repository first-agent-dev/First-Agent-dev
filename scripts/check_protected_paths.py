#!/usr/bin/env python3
"""Surface edits to ADR-11 protected / TCB paths (R-15, ADR-11-I7).

This is the **CI diff-check** half of the protected-path governance
bundle (CODEOWNERS + branch protection + this script). It does not — and
cannot — prove that a human approved a TCB change; per the ADR
enforcement-ceiling, the script's job is to make any edit to a Trusted
Computing Base path **loud and visible** so a reviewer acts on the flag.
It is therefore **non-blocking by default** (exit 0), which also lets the
ADR-11 rollout PRs that legitimately create these files merge. Pass
``--fail-on-touch`` to make it a hard gate for repos that want one.

Symlink-bypass safety (Hermes ``file_safety`` pattern): every candidate
is compared both by its normalised repo-relative POSIX string and by
``os.path.realpath`` against the repo root, so an alias/symlink pointing
at a protected path is still caught.

stdlib-only: this file is itself a protected TCB path.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

# Exact protected paths (repo-relative POSIX). Blueprint R-15 / ADR-11-I7.
_TCB_PATHS = frozenset(
    {
        "src/fa/authoring_tcb.py",
        "src/fa/authoring_rules/__init__.py",
        ".github/workflows/authoring-guardrails.yml",
        ".github/CODEOWNERS",
        "scripts/check_protected_paths.py",
    }
)
# Any path beneath these prefixes is protected (the whole rule pack).
_TCB_PREFIXES: tuple[str, ...] = ("src/fa/authoring_rules/",)


def _normalise(path: str) -> str:
    return path.strip().replace("\\", "/").removeprefix("./")


def is_protected(path: str, repo_root: Path) -> bool:
    """Return ``True`` if ``path`` is (or aliases) a protected TCB path."""
    rel = _normalise(path)
    if rel in _TCB_PATHS or any(rel.startswith(prefix) for prefix in _TCB_PREFIXES):
        return True
    candidate_real = os.path.realpath(repo_root / rel)
    for protected in _TCB_PATHS:
        target = repo_root / protected
        if target.exists() and candidate_real == os.path.realpath(target):
            return True
    # Symlink-to-prefix bypass fix: check if candidate realpath is under a protected prefix
    for prefix in _TCB_PREFIXES:
        prefix_real = os.path.realpath(repo_root / prefix)
        sep = os.sep
        if candidate_real == prefix_real or candidate_real.startswith(prefix_real + sep):
            return True
    return False


def protected_hits(paths: Iterable[str], repo_root: Path) -> list[str]:
    """Return the sorted, de-duplicated protected paths among ``paths``."""
    hits = {_normalise(p) for p in paths if is_protected(p, repo_root)}
    return sorted(hits)


def changed_paths(base_ref: str, repo_root: Path) -> list[str]:
    """Return files changed between ``base_ref`` and ``HEAD`` (merge-base diff)."""
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _emit(hits: Sequence[str], *, fail_on_touch: bool) -> int:
    if not hits:
        print("check_protected_paths: no protected/TCB paths touched.")
        return 0
    for hit in hits:
        # GitHub Actions annotation: shows inline on the PR Files tab.
        print(f"::warning file={hit}::ADR-11 protected/TCB path modified — requires human review")
    print(
        "check_protected_paths: "
        f"{len(hits)} protected/TCB path(s) modified; a CODEOWNER must review "
        "(ADR-11-I7 enforcement-ceiling):",
        file=sys.stderr,
    )
    for hit in hits:
        print(f"  - {hit}", file=sys.stderr)
    return 1 if fail_on_touch else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_protected_paths",
        description="Flag edits to ADR-11 protected / TCB paths in a PR diff.",
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Base ref to diff HEAD against (default: origin/main).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current directory).",
    )
    parser.add_argument(
        "--fail-on-touch",
        action="store_true",
        help="Exit non-zero when a protected path is touched (default: flag only).",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    try:
        paths = changed_paths(args.base, repo_root)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"::warning::check_protected_paths: could not compute diff: {exc} — manual review required", file=sys.stderr)
        return 0  # fail-open on diff errors: never block on missing git history
    return _emit(protected_hits(paths, repo_root), fail_on_touch=args.fail_on_touch)


if __name__ == "__main__":
    raise SystemExit(main())
