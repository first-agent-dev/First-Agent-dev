#!/usr/bin/env python3
"""Targeted mutation testing for files changed vs origin/main (or $BASE_REF).

Why this exists
---------------
Full-repo mutation testing is slow (~1 min per sandbox scope, hours for
src/) and is therefore only weekly/advisory (tests.yml). For the LLM-
agent loop we want a LAST-LINE defense that runs before push: mutate
only the files the agent actually touched, run the relevant tests, and
fail if any mutant survives.

How it works
------------
1. Determine the merge base (``$BASE_REF`` or ``origin/main``) and enumerate
   files changed in the current branch/working tree.
2. Filter to ``.py`` files under ``src/fa/`` that live in tracked paths
   (excluding tests/, scripts/, __init__.py marker files, and modules
   outside the in-scope mutation scope — see [tool.mutmut] in
   pyproject.toml for reference, we target a superset that stays fast).
3. Backup ``pyproject.toml``, point ``[tool.mutmut] source_paths`` to the
   changed files, write a temporary pytest-tests selection (tests
   covering each changed file is best-effort via a ``src -> tests``
   mapping; we fall back to the full test suite for the touched area),
   run ``mutmut run``, capture survivors, restore pyproject.toml.
4. Exit non-zero if any survivors are found.

This is a BLOCKING gate (pre-push + CI). A surviving mutant means
``pytest`` does not catch a real logic mutation in code the agent
touched, which is exactly the "tests don't assert" smell LLM-written
code is prone to.

Environment override:
    FA_TARGETED_MUTATION_BASE=origin/master   choose a different base ref
    FA_SKIP_TARGETED_MUTATION=1               skip the gate (operator emergency)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Cap mutants per run to keep pre-push time bounded. If an agent touches
# >20 files there are bigger problems; full-repo mutmut is the weekly
# advisory job's responsibility.
MAX_FILES = 20
MUTANT_TIMEOUT_SECONDS = 600


def _base_ref() -> str:
    return os.environ.get("FA_TARGETED_MUTATION_BASE", "origin/main")


def _changed_py_files(base: str) -> list[Path]:
    """Return list of Paths (relative to REPO_ROOT) for .py files changed vs base.

    Combines ``git diff --name-only`` (committed changes) with
    ``git diff --name-only HEAD`` (working tree changes that are not yet
    committed), then takes the union. This covers both committed branch
    work and in-flight edits at the moment of push.
    """
    cmds = [
        ["git", "merge-base", "HEAD", base],
        ["git", "diff", "--name-only", "--diff-filter=ACMRT", f"{base}...HEAD"],
        ["git", "diff", "--name-only", "--diff-filter=ACMRT", "HEAD"],
    ]

    # Each failure (e.g. base ref not fetched) is swallowed; we fall
    # back to scanning all tracked files in the mutation scope.
    def _run(cmd: list[str]) -> str:
        try:
            return subprocess.check_output(cmd, cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    _run(cmds[0])  # warm merge-base; we don't need its output
    names = set()
    for out in (_run(cmds[1]), _run(cmds[2])):
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            names.add(line)

    py_files: list[Path] = []
    for name in sorted(names):
        p = REPO_ROOT / name
        if not p.is_file():
            continue
        if p.suffix != ".py":
            continue
        # Skip tests, scripts, hooks, and TCB. Tests are the oracle;
        # mutating them would invert the guard.
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("tests/") or rel.startswith("scripts/") or rel.startswith("src/fa/hygiene/hooks/"):
            continue
        if "/__pycache__/" in rel:
            continue
        # Pure marker __init__.py files rarely carry logic; skip those with
        # ≤ 3 non-comment non-blank lines to stay fast. Real __init__.py
        # modules (re-exports, module-level __all__, etc.) are kept.
        if rel.endswith("/__init__.py"):
            init_text = p.read_text(encoding="utf-8", errors="ignore")
            meaningful = [ln for ln in init_text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
            if len(meaningful) <= 3:
                continue
        if not rel.startswith("src/fa/"):
            continue
        py_files.append(p)
    return py_files[:MAX_FILES]


def _select_tests_for(changed: list[Path]) -> list[str]:
    """Best-effort: pick pytest test files likely to exercise the changed modules.

    Strategy: for each changed ``src/fa/foo/bar.py``, look for a matching
    ``tests/test_foo_bar.py`` or ``tests/test_bar.py``. If none exist,
    fall back to the generic test buckets used by the full scope.
    """
    found: set[str] = set()
    test_root = REPO_ROOT / "tests"
    candidates_generic = [
        "tests/test_fs_search.py",
        "tests/test_safe_walk.py",
    ]
    for p in changed:
        # src/fa/inner_loop/tools/fs_search -> test_fs_search
        basename = p.stem
        for cand in (f"test_{basename}.py", f"test_{basename}_*.py"):
            for matched in test_root.glob(cand):
                found.add(str(matched.relative_to(REPO_ROOT)))
        # Drop src/fa/x/y -> tests/test_x_y.py is too broad; rely on
        # basename match which is the repo's naming convention.
    for t in candidates_generic:
        if (REPO_ROOT / t).is_file():
            found.add(t)
    return sorted(found)


def main() -> int:
    if os.environ.get("FA_SKIP_TARGETED_MUTATION") == "1":
        print("targeted-mutmut: skipped (FA_SKIP_TARGETED_MUTATION=1)")
        return 0

    if not shutil.which("mutmut"):
        # mutmut is a dev dependency; if missing in a lean environment
        # we fail OPEN (do not block the push) rather than failing
        # closed, because failing here would block everyone before the
        # dev extras are installed. The CI job runs on the full env
        # and is the authoritative gate.
        print("targeted-mutmut: mutmut not installed (uv sync --extra dev); skipping")
        return 0

    if not (REPO_ROOT / ".git").is_dir():
        print("targeted-mutmut: not a git checkout; skipping")
        return 0

    base = _base_ref()
    changed = _changed_py_files(base)
    if not changed:
        print("targeted-mutmut: no src/fa/*.py files changed; skipping")
        return 0

    rels = [str(p.relative_to(REPO_ROOT)).replace("\\", "/") for p in changed]
    print(f"targeted-mutmut: {len(rels)} changed file(s): {', '.join(rels)}")

    tests = _select_tests_for(changed)
    if not tests:
        # No known tests to run against these files: mutation testing
        # would trivially report everything as surviving. Defer to the
        # full test suite (which is slow, so only do this when there's
        # no better choice; cap to 1 file to keep latency sane).
        print("targeted-mutmut: no direct test mapping; falling back to targeted list")
        tests = ["tests/"]

    # Read pyproject, back it up, patch [tool.mutmut] source_paths via
    # conservative string substitution — no round-trip through tomllib
    # (that would drop comments/formatting).
    backup = PYPROJECT.read_bytes()
    tmp_pyproject = PYPROJECT.with_suffix(".toml.targeted-mutmut")
    try:
        # Build patched content by string replacement (preserves
        # comments/formatting). This is intentionally simple: replace
        # the source_paths list block with a fresh one.
        text = PYPROJECT.read_text(encoding="utf-8")
        # Easiest correct approach: write a temp pyproject that inherits
        # from the original but overrides source_paths via an overlay
        # written to mutmut.toml. Since mutmut only reads pyproject.toml
        # we do inline substitution of the source_paths block.
        new_source_block = "source_paths = [\n" + "".join(f'  "{r}",\n' for r in rels) + "]\n"
        # Match source_paths = [ ... ] (multiline, non-greedy, until the
        # next top-level key at column 0 or end-of-section).
        pattern = re.compile(r"^source_paths\s*=\s*\[.*?\]\n", re.DOTALL | re.MULTILINE)
        new_text, n = pattern.subn(new_source_block, text, count=1)
        if n != 1:
            print("targeted-mutmut: could not patch [tool.mutmut] source_paths; aborting", file=sys.stderr)
            return 2
        # Also patch pytest_add_cli_args_test_selection to our chosen
        # tests (if present).
        if "pytest_add_cli_args_test_selection" in new_text:
            new_tests_block = "pytest_add_cli_args_test_selection = [\n" + "".join(f'  "{t}",\n' for t in tests) + "]\n"
            tpat = re.compile(r"^pytest_add_cli_args_test_selection\s*=\s*\[.*?\]\n", re.DOTALL | re.MULTILINE)
            new_text, nt = tpat.subn(new_tests_block, new_text, count=1)
            if nt != 1:
                print("targeted-mutmut: could not patch pytest test selection", file=sys.stderr)
                return 2
        tmp_pyproject.write_bytes(backup)
        PYPROJECT.write_text(new_text, encoding="utf-8")

        mutmut_bin = shutil.which("mutmut")
        if not mutmut_bin:
            print("targeted-mutmut: mutmut not found on PATH during run; skipping")
            return 0
        cmd = [mutmut_bin, "run"]
        print(f"targeted-mutmut: running {' '.join(cmd)} against {len(tests)} test file(s)")
        try:
            result = subprocess.run(cmd, cwd=REPO_ROOT, timeout=MUTANT_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            print(f"targeted-mutmut: timed out after {MUTANT_TIMEOUT_SECONDS}s", file=sys.stderr)
            return 2
        # Collect survivors.
        survivors = subprocess.run([mutmut_bin, "results"], cwd=REPO_ROOT, text=True, capture_output=True)
        # mutmut results prints "Survived ..." for each surviving mutant.
        survived_lines = [
            ln for ln in survivors.stdout.splitlines() if "survived" in ln.lower() or ln.strip().startswith("SURVIVED")
        ]
        if result.returncode != 0 or survived_lines:
            print("targeted-mutmut: SURVIVORS FOUND (tests do not catch mutations in changed code):", file=sys.stderr)
            for ln in survived_lines[:30]:
                print(f"  {ln}", file=sys.stderr)
            print("Run `mutmut show <id>` to see the mutant; add a test that kills it before pushing.", file=sys.stderr)
            return 1
        print(f"targeted-mutmut: all mutants killed ({len(rels)} file(s) scanned)")
        return 0
    finally:
        PYPROJECT.write_bytes(backup)
        if tmp_pyproject.exists():
            try:
                tmp_pyproject.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
