#!/usr/bin/env python3
"""Targeted mutation-testing gate (pre-push / CI).

Runs ``mutmut`` against the Python files changed between the working tree
and the merge-base with ``origin/main`` (with graceful fallbacks to
``main``, ``HEAD~1``). Scopes mutation to those files by temporarily
rewriting ``[tool.mutmut] source_paths`` in ``pyproject.toml`` (mutmut 3.x
removed ``--paths-to-mutate``); the file is restored in ``finally``.

Why targeted: the full sandbox+substrate scope in pyproject.toml runs for
~20+ minutes in CI and lives in the weekly ``tests.yml`` workflow. The
push-time gate needs to complete inside the pre-push budget.

Fail-open: if mutmut is not installed, git is unavailable, the diff is
empty/too large, or ``FA_SKIP_TARGETED_MUTATION=1`` is set, exit 0 with a
note so unbootstrapped shells and escape-hatches work. Real survivor
findings exit non-zero.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"

MAX_FILES = 20
MUTANT_TIMEOUT_SECONDS = 600
_BACKUP_SUFFIX = ".pre-targeted-mutmut.bak"


def _log(msg: str) -> None:
    print(f"[targeted-mutmut] {msg}", file=sys.stderr, flush=True)


def _changed_python_files() -> list[Path]:
    git = shutil.which("git")
    if git is None:
        _log("git not found on PATH; skipping (fail-open)")
        return []

    base: str | None = None
    for ref in ("origin/main", "main", "HEAD~1"):
        r = subprocess.run(
            [git, "merge-base", "HEAD", ref],
            cwd=REPO_ROOT,
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
        [git, "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    files: list[Path] = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line.endswith(".py"):
            continue
        p = (REPO_ROOT / line).resolve()
        try:
            rel = p.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            continue
        if rel.startswith(("src/", "tests/")) and p.is_file():
            files.append(p)
    return files


def _configured_source_roots() -> list[str]:
    """Return currently configured [tool.mutmut] source_paths entries (trailing-/ stripped)."""
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(
        r"source_paths\s*=\s*\[(.*?)\]",
        text,
        flags=re.DOTALL,
    )
    if not m:
        return []
    return [m.strip().strip('"').rstrip("/") for m in re.findall(r'"([^"]+)"', m.group(1))]


def _scope_to_changed(changed: list[Path]) -> list[Path]:
    """Keep only changed files that live under a configured source root or under tests/."""
    roots = _configured_source_roots()
    out: list[Path] = []
    for p in changed:
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("tests/") or any(rel == r or rel.startswith(r + "/") for r in roots):
            out.append(p)
    return out


def _rewrite_source_paths(scoped: list[Path]) -> None:
    backup = PYPROJECT.with_name(PYPROJECT.name + _BACKUP_SUFFIX)
    backup.write_text(PYPROJECT.read_text(encoding="utf-8"), encoding="utf-8")
    text = backup.read_text(encoding="utf-8")
    entries = "\n".join(f'  "{p.relative_to(REPO_ROOT).as_posix()}",' for p in scoped)
    new_block = f"source_paths = [\n{entries}\n]"
    new_text, n = re.subn(
        r"source_paths\s*=\s*\[.*?\]",
        new_block,
        text,
        count=1,
        flags=re.DOTALL,
    )
    if n != 1:
        raise RuntimeError("failed to locate source_paths block in pyproject.toml")
    PYPROJECT.write_text(new_text, encoding="utf-8")


def _restore_pyproject() -> None:
    backup = PYPROJECT.with_name(PYPROJECT.name + _BACKUP_SUFFIX)
    if backup.is_file():
        PYPROJECT.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
        backup.unlink()


def _resolve_mutmut() -> str | None:
    for cand in (shutil.which("mutmut"), str(REPO_ROOT / ".venv" / "bin" / "mutmut")):
        if cand and Path(cand).is_file():
            return cand
    return None


def main() -> int:
    if os.environ.get("FA_SKIP_TARGETED_MUTATION") == "1":
        _log("skipping (FA_SKIP_TARGETED_MUTATION=1)")
        return 0

    mutmut = _resolve_mutmut()
    if mutmut is None:
        _log("mutmut not installed; skipping (fail-open)")
        return 0

    changed = _changed_python_files()
    if not changed:
        _log("no changed Python files vs merge-base; nothing to mutate")
        return 0
    scoped = _scope_to_changed(changed)
    if not scoped:
        _log("changed files are outside mutmut source_paths; nothing to do")
        return 0
    if len(scoped) > MAX_FILES:
        _log(f"{len(scoped)} changed files > MAX_FILES={MAX_FILES}; skipping (weekly full-mutmut covers large diffs)")
        return 0

    _log(f"mutating {len(scoped)} file(s):")
    for p in scoped:
        _log(f"  - {p.relative_to(REPO_ROOT).as_posix()}")

    try:
        _rewrite_source_paths(scoped)
    except (OSError, RuntimeError, re.error) as exc:  # pragma: no cover - defensive
        _log(f"failed to patch pyproject.toml: {exc}; skipping (fail-open)")
        _restore_pyproject()
        return 0

    start = time.monotonic()
    rc = 0
    try:
        env = dict(os.environ)
        env["MUTANT_TIMEOUT_SECONDS"] = str(MUTANT_TIMEOUT_SECONDS)
        r = subprocess.run([mutmut, "run"], cwd=REPO_ROOT, check=False, env=env)
        rc = r.returncode
        subprocess.run([mutmut, "results"], cwd=REPO_ROOT, check=False)
        _log(f"finished in {time.monotonic() - start:.1f}s (rc={rc})")
    finally:
        _restore_pyproject()
    return rc


if __name__ == "__main__":
    sys.exit(main())
