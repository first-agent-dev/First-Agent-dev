#!/usr/bin/env python3
"""Offline internal-link checker for the repo's Markdown docs.

Enforces knowledge/MAINTENANCE.md §"When moving or pruning a doc": no dangling
relative links. Dependency-free and deterministic — never touches the network.

Default mode checks that every relative *file* link (``](path)`` /
``](path#anchor)``) resolves to a file that exists. This is the class of bug a
doc move/prune introduces. Anchor (``#fragment``) validation is opt-in via
``--anchors`` because GitHub's slug algorithm differs from any local
re-implementation on complex headings and the repo carries pre-existing
anchor debt.

Pre-commit passes the changed files, so the hook only judges what a commit
touches. Run with no arguments to scan the whole repo (used by the CI test),
which skips a small set of legacy doc trees with known pre-existing breakage
(see ``_LEGACY_SKIP``); those are tracked separately, not silently blessed.

Usage:
    python scripts/check_doc_links.py                 # whole repo (CI)
    python scripts/check_doc_links.py a.md b.md       # specific files (hook)
    python scripts/check_doc_links.py --anchors a.md  # also validate anchors
    python scripts/check_doc_links.py --all a.md      # include legacy trees

Exit 0 = all good; 1 = at least one broken link (details on stderr).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Inline link: ](target) | ](target "title") | ](<target>). Captures only the
# target URL/path. The optional title (" ... " / ' ... ' / ( ... )) and optional
# angle brackets are tolerated so a broken link with a title is not missed.
_LINK_RE = re.compile(
    r"""\]\(\s*
        (?:<(?P<angle>[^>]*)>|(?P<bare>[^)\s]+))
        (?:\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?
        \s*\)""",
    re.VERBOSE,
)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
# Inline code spans (`...`, ``...``) — their contents are not live links, so we
# blank them out before scanning a line (mirrors how fenced blocks are skipped).
# Example: a doc may legitimately show `](../X)` as literal text.
_INLINE_CODE_RE = re.compile(r"(`+)(?:.+?)\1")

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Legacy doc trees with pre-existing broken links (dead research notes, retired
# docs/ paths, illustrative `../X` placeholders). Excluded from the whole-repo
# scan so the gate is green today while still catching NEW breakage in the
# actively-maintained docs. Shrinking this set is good follow-up hygiene.
_LEGACY_SKIP = (
    "For cross-reference with ADR's/",
    "knowledge/trace/",
    "knowledge/research/",
    "knowledge/prompts/prompting.md",
    "knowledge/project-overview.md",
    "knowledge/anti-patterns/README.md",
    "knowledge/glossary.md",
)


def _slug(heading: str) -> str:
    text = heading.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def _headings(path: Path) -> set[str]:
    slugs: set[str] = set()
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
        if m:
            slugs.add(_slug(m.group(2)))
    return slugs


def _iter_links(path: Path):
    in_fence = False
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # Neutralise inline code spans so example link syntax inside backticks
        # (e.g. `](../X)`) is not mistaken for a real link.
        scrub = _INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line)
        for m in _LINK_RE.finditer(scrub):
            target = m.group("angle") if m.group("angle") is not None else m.group("bare")
            yield lineno, target


def _is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "tel:", "//"))


def check_file(path: Path, *, anchors: bool) -> list[str]:
    errors: list[str] = []
    try:
        rel = path.relative_to(_REPO_ROOT)
    except ValueError:
        rel = path
    for lineno, target in _iter_links(path):
        if _is_external(target) or target.startswith("/"):
            continue

        anchor = ""
        file_part = target
        if "#" in target:
            file_part, anchor = target.split("#", 1)

        if file_part == "":
            if anchors and anchor and anchor not in _headings(path):
                errors.append(f"{rel}:{lineno}: anchor '#{anchor}' not found in this file")
            continue

        dest = (path.parent / file_part).resolve()
        if not dest.exists():
            errors.append(f"{rel}:{lineno}: broken link target '{target}' -> {dest}")
            continue

        if anchors and anchor and dest.suffix == ".md" and anchor not in _headings(dest):
            errors.append(f"{rel}:{lineno}: anchor '#{anchor}' not found in {file_part}")
    return errors


def _is_legacy(path: Path) -> bool:
    """True if ``path`` lives in a known pre-existing-debt tree (``_LEGACY_SKIP``)."""
    try:
        relstr = str(path.resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return False
    return relstr.startswith(_LEGACY_SKIP)


def _discover(include_legacy: bool) -> list[Path]:
    skip_dirs = {".git", "node_modules", ".venv", "__pycache__"}
    out: list[Path] = []
    for p in _REPO_ROOT.rglob("*.md"):
        if any(part in skip_dirs for part in p.relative_to(_REPO_ROOT).parts):
            continue
        if not include_legacy and _is_legacy(p):
            continue
        out.append(p)
    return sorted(out)


def main(argv: list[str]) -> int:
    anchors = "--anchors" in argv
    include_legacy = "--all" in argv
    files_args = [a for a in argv if not a.startswith("--")]

    if files_args:
        # Explicitly-passed files (e.g. from the pre-commit hook) are still
        # filtered against _LEGACY_SKIP unless --all is given, so that merely
        # *touching* a known-debt doc does not block an unrelated commit on
        # pre-existing breakage. --all forces a full check (e.g. when cleaning
        # up a legacy file on purpose).
        files = [Path(a).resolve() for a in files_args if a.endswith(".md")]
        if not include_legacy:
            files = [f for f in files if not _is_legacy(f)]
    else:
        files = _discover(include_legacy)

    all_errors: list[str] = []
    for f in files:
        if f.exists():
            all_errors.extend(check_file(f, anchors=anchors))

    if all_errors:
        print("Broken internal doc links found:", file=sys.stderr)
        for e in all_errors:
            print(f"  {e}", file=sys.stderr)
        print(
            f"\n{len(all_errors)} broken link(s). Fix them in this PR "
            "(see knowledge/MAINTENANCE.md §When moving or pruning a doc).",
            file=sys.stderr,
        )
        return 1
    print(f"OK: {len(files)} markdown file(s) checked, no broken internal links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
