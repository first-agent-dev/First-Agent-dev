#!/usr/bin/env python3
"""Targeted Semgrep gate (pre-push / CI).

Runs Semgrep OSS (p/python + p/owasp-top-ten) against the Python files
changed vs merge-base. Full-repo Semgrep is slow and lives in the weekly
CI workflow (semgrep.yml); the push-time gate scopes to the diff to stay
under a couple of minutes.

Uses ``uvx semgrep`` so the semgrep binary does not need to be in the
project dev dependencies.

Fail-open: if uvx is unavailable, semgrep cannot be installed, the diff is
empty/too large, or ``FA_SKIP_TARGETED_SEMGREP=1`` is set, exit 0 with a
note. Real Semgrep findings exit non-zero.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

MAX_FILES = 50
RUN_TIMEOUT_SECONDS = 120


def _log(msg: str) -> None:
    print(f"[targeted-semgrep] {msg}", file=sys.stderr, flush=True)


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
        if p.is_file() and (rel.startswith("src/") or rel.startswith("tests/") or rel.startswith("scripts/")):
            files.append(p)
    return files


def _resolve_uvx() -> str | None:
    uvx = shutil.which("uvx")
    if uvx:
        return uvx
    uv = shutil.which("uv")
    if uv:
        return f"{uv} tool run"  # fall back; uvx is preferred
    return None


def main() -> int:
    if os.environ.get("FA_SKIP_TARGETED_SEMGREP") == "1":
        _log("skipping (FA_SKIP_TARGETED_SEMGREP=1)")
        return 0

    uvx = _resolve_uvx()
    if uvx is None:
        _log("uvx not found; skipping targeted semgrep (fail-open)")
        return 0

    changed = _changed_python_files()
    if not changed:
        _log("no changed Python files vs merge-base; nothing to scan")
        return 0
    if len(changed) > MAX_FILES:
        _log(f"{len(changed)} changed files > MAX_FILES={MAX_FILES}; skipping (weekly full-semgrep covers large diffs)")
        return 0

    _log(f"scanning {len(changed)} file(s):")
    for p in changed:
        _log(f"  - {p.relative_to(REPO_ROOT).as_posix()}")

    pos_args = [str(p) for p in changed]
    cmd = [
        "uvx",
        "semgrep",
        "scan",
        "--quiet",
        "--config=p/python",
        "--config=p/owasp-top-ten",
        *pos_args,
    ]
    # NOTE: no --no-git-ignore. That flag was tried and reverted — it causes
    # semgrep to descend into .venv, mutants, .mypy_cache, etc. The regular
    # gitignore-honouring scan is the production-default behaviour.
    start = time.monotonic()
    try:
        r = subprocess.run(cmd, cwd=REPO_ROOT, check=False, timeout=RUN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _log(f"semgrep timed out after {RUN_TIMEOUT_SECONDS}s; skipping (fail-open)")
        return 0
    _log(f"finished in {time.monotonic() - start:.1f}s (rc={r.returncode})")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
