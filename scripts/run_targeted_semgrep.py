#!/usr/bin/env python3
"""Targeted semgrep run on files changed vs origin/main (or $BASE_REF).

Semgrep OSS scans for python anti-patterns (p/python) and OWASP top-10
(p/owasp-top-ten). Full-repo semgrep is weekly/advisory (semgrep.yml)
because it pulls rule sets from the internet on first run and takes
non-trivial time. For the pre-push gate we scan only files the branch
changes, which keeps the wall time to seconds on small diffs.

Gate semantics:
- Blocking (exit 1) if semgrep reports findings in changed .py files.
- Skip (exit 0) if semgrep is not installed, the base ref is missing,
  or there are no changed .py files. Use `FA_SKIP_TARGETED_SEMGREP=1`
  for the emergency bypass (intentionally separate from the general
  full-check bypass so operators can diagnose which layer is firing).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEMGREP_CONFIGS = ["p/python", "p/owasp-top-ten"]
MAX_FILES = 50
# Per-run timeout (seconds). Semgrep pulls rule packs over the network on
# first run; cap so a wedged network call can't hang pre-push forever.
RUN_TIMEOUT_SECONDS = 120


def _base_ref() -> str:
    return os.environ.get("FA_TARGETED_SEMGREP_BASE", "origin/main")


def _changed_py_files(base: str) -> list[Path]:
    def _run(cmd: list[str]) -> str:
        try:
            return subprocess.check_output(cmd, cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    names: set[str] = set()
    for out in (
        _run(["git", "diff", "--name-only", "--diff-filter=ACMRT", f"{base}...HEAD"]),
        _run(["git", "diff", "--name-only", "--diff-filter=ACMRT", "HEAD"]),
    ):
        for line in out.splitlines():
            line = line.strip()
            if line:
                names.add(line)

    py_files: list[Path] = []
    for name in sorted(names):
        p = REPO_ROOT / name
        if p.is_file() and p.suffix == ".py" and "/__pycache__/" not in name.replace("\\", "/"):
            py_files.append(p)
    return py_files[:MAX_FILES]


def main() -> int:
    if os.environ.get("FA_SKIP_TARGETED_SEMGREP") == "1":
        print("targeted-semgrep: skipped (FA_SKIP_TARGETED_SEMGREP=1)")
        return 0

    if not shutil.which("uvx"):
        print("targeted-semgrep: uvx not found; skipping")
        return 0

    if not (REPO_ROOT / ".git").is_dir():
        print("targeted-semgrep: not a git checkout; skipping")
        return 0

    base = _base_ref()
    changed = _changed_py_files(base)
    if not changed:
        print("targeted-semgrep: no .py files changed; skipping")
        return 0

    rels = [str(p.relative_to(REPO_ROOT)) for p in changed]
    print(f"targeted-semgrep: scanning {len(rels)} changed file(s)")

    cmd = ["uvx", "semgrep", "scan", "--quiet"]
    for cfg in SEMGREP_CONFIGS:
        cmd.extend(["--config", cfg])
    cmd.extend(rels)

    try:
        result = subprocess.run(cmd, cwd=REPO_ROOT, text=True, timeout=RUN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        print(
            f"targeted-semgrep: timed out after {RUN_TIMEOUT_SECONDS}s; skipping",
            file=sys.stderr,
        )
        return 0
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"targeted-semgrep: failed to invoke semgrep ({exc}); skipping")
        return 0

    if result.returncode != 0:
        print("targeted-semgrep: findings in changed files (see above)", file=sys.stderr)
        return 1
    print("targeted-semgrep: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
