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

# Dependency manifests (supply-chain review tier). LLM authors hallucinate
# package names at a measurable rate and attackers register them
# ("slopsquatting"); `uv lock` only proves a package EXISTS and pip-audit
# only catches KNOWN CVEs — neither proves the dependency was intended.
# Flag every dependency-manifest edit so a human confirms each new/changed
# package on the PR. Same non-blocking annotation mechanism as TCB paths.
_DEPENDENCY_PATHS = frozenset({"pyproject.toml", "uv.lock"})

# Suppression markers (waiver-review tier). Every blocking gate in this
# repo can be locally neutralised by a comment: "noqa: <code>" (ruff),
# "pylint: disable=..." (incl. duplicate-code, where a disable in ONE
# copy suppresses the cross-file pair), "pragma: no cover" (coverage),
# "type: ignore[...]" (mypy). A waiver is a *reviewed design decision*
# (AGENTS.md, Judgment rules), so every ADDED marker is surfaced as a PR
# annotation for the human reviewer. Non-blocking: legitimate waivers are
# expected; silent ones are not.
# Concatenation keeps these literals from matching THIS file's own source
# when the script itself is edited in a PR.
_SUPPRESSION_MARKERS: tuple[str, ...] = (
    "# " + "noqa",
    "# " + "pylint: disable",
    "# " + "pragma: no cover",
    "# " + "type: ignore",
)


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


def dependency_hits(paths: Iterable[str]) -> list[str]:
    """Return the sorted dependency-manifest paths among ``paths``."""
    return sorted({_normalise(p) for p in paths if _normalise(p) in _DEPENDENCY_PATHS})


def added_suppressions(base_ref: str, repo_root: Path) -> list[tuple[str, str]]:
    """Return ``(file, added_line)`` pairs that introduce a suppression marker.

    Scans the unified diff (added lines only) so pre-existing waivers never
    re-flag; only NEW suppressions surface on the PR.
    """
    # Waiver: fixed argv, no shell; base_ref comes from the CI-provided ref.
    result = subprocess.run(  # noqa: S603
        ["git", "diff", "--unified=0", f"{base_ref}...HEAD"],  # noqa: S607
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    hits: list[tuple[str, str]] = []
    current_file = ""
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            continue
        # Python sources only: docs/config legitimately *mention* the
        # markers in prose; a directive only has effect in a .py file.
        # Corpus fixtures are deliberate violation samples — skip them.
        if not current_file.endswith(".py"):
            continue
        if current_file.startswith(("catch-corpus/", "fp-corpus/")):
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        added = line[1:]
        if any(marker in added for marker in _SUPPRESSION_MARKERS):
            hits.append((current_file, added.strip()))
    return hits


def changed_paths(base_ref: str, repo_root: Path) -> list[str]:
    """Return files changed between ``base_ref`` and ``HEAD`` (merge-base diff)."""
    # Waiver: fixed argv, no shell; base_ref comes from the CI-provided ref;
    # bare "git" resolved via PATH is the portable convention.
    result = subprocess.run(  # noqa: S603
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],  # noqa: S607
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _emit_dependency_flags(hits: Sequence[str]) -> None:
    """Annotate dependency-manifest edits (never blocking)."""
    for hit in hits:
        print(
            f"::warning file={hit}::dependency manifest modified — reviewer: "
            "verify each added/changed package name and version is intended "
            "(LLM-hallucinated names are a supply-chain vector / slopsquatting)"
        )


def _emit_suppression_flags(hits: Sequence[tuple[str, str]]) -> None:
    """Annotate newly added lint/coverage/type suppressions (never blocking)."""
    for path, line in hits:
        # Truncate the quoted line: annotations are pointers, not transcripts.
        snippet = line if len(line) <= 120 else line[:117] + "..."
        print(
            f"::warning file={path}::new suppression added ({snippet}) — "
            "reviewer: confirm the waiver rationale is sound, not a gate bypass"
        )


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
        msg = (
            f"::warning::check_protected_paths: could not compute diff: {exc}"
            " — manual review required"
        )
        print(msg, file=sys.stderr)
        return 0  # fail-open on diff errors: never block on missing git history
    _emit_dependency_flags(dependency_hits(paths))
    try:
        _emit_suppression_flags(added_suppressions(args.base, repo_root))
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        # Same fail-open contract as the path diff above.
        print(
            f"::warning::check_protected_paths: could not scan suppressions: {exc}",
            file=sys.stderr,
        )
    return _emit(protected_hits(paths, repo_root), fail_on_touch=args.fail_on_touch)


if __name__ == "__main__":
    raise SystemExit(main())
