#!/usr/bin/env python3
"""Targeted Semgrep gate (pre-push / CI).

Runs Semgrep OSS (``p/python`` + ``p/owasp-top-ten``) against the Python
files changed vs merge-base. Full-repo Semgrep is slow and lives in the
weekly CI workflow (``semgrep.yml``); the push-time gate scopes to the
diff to stay under a couple of minutes.

Uses ``uvx`` (``uv tool run``) so the semgrep binary does not need to be
in the project dev dependencies. The semgrep version is pinned via
``[tool.ci-pins] semgrep = "<ver>"`` in ``pyproject.toml``; T3
parity-enforces the weekly workflow uses the same pin.

Fail-open: if uv/uvx is unavailable, semgrep cannot be installed, the
diff is empty/too large, or ``FA_SKIP_TARGETED_SEMGREP=1`` is set, exit 0
with a note. Real Semgrep findings exit non-zero.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts._git_diff as gd
from scripts._console import force_utf8_stdio

force_utf8_stdio()

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"

MAX_FILES = 50
RUN_TIMEOUT_SECONDS = 120


def _read_semgrep_pin() -> str | None:
    """Read ``[tool.ci-pins].semgrep`` from pyproject.toml.

    Returns ``None`` on any failure (missing section, TOML parse error,
    etc); caller falls back to unpinned ``uvx semgrep`` with a stderr
    note. A missing pin must NOT hard-fail the gate (fail-open).
    """
    import tomllib

    try:
        data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        gd._log(f"failed to read pyproject.toml: {exc}; running unpinned (fail-open)")
        return None
    pin = data.get("tool", {}).get("ci-pins", {}).get("semgrep")
    if not isinstance(pin, str) or not pin.strip():
        gd._log("no [tool.ci-pins].semgrep in pyproject.toml; running unpinned (fail-open)")
        return None
    return pin.strip()


def _build_semgrep_argv(*, pin: str | None, pos_args: list[str]) -> list[str] | None:
    """Build the argv list for invoking semgrep.

    Resolves the launcher in order:

    1. ``uvx`` on PATH → ``['uvx', '--from', f'semgrep=={pin}', 'semgrep', ...]``
       (when pin is given) or ``['uvx', 'semgrep', ...]`` (when unpinned).
    2. ``uv`` on PATH → ``[uv, 'tool', 'run', '--from', f'semgrep=={pin}', 'semgrep', ...]``.
    3. ``None`` → caller treats as fail-open.

    Return value is always a list of strings with NO shell fragments.
    This fixes a pre-refactor bug where the fallback returned
    ``f"{uv} tool run"`` as a single argv[0] containing a space, which
    raised ``FileNotFoundError`` (list-form subprocess does not split
    on spaces).
    """
    config_flags = ["--quiet", "--config=p/python", "--config=p/owasp-top-ten"]
    uvx = shutil.which("uvx")
    if uvx is not None:
        if pin is not None:
            return [uvx, "--from", f"semgrep=={pin}", "semgrep", "scan", *config_flags, *pos_args]
        return [uvx, "semgrep", "scan", *config_flags, *pos_args]
    uv = shutil.which("uv")
    if uv is not None:
        if pin is not None:
            return [uv, "tool", "run", "--from", f"semgrep=={pin}", "semgrep", "scan", *config_flags, *pos_args]
        return [uv, "tool", "run", "semgrep", "scan", *config_flags, *pos_args]
    return None


def main() -> int:
    if os.environ.get("FA_SKIP_TARGETED_SEMGREP") == "1":
        gd._log("skipping (FA_SKIP_TARGETED_SEMGREP=1)")
        return 0

    pin = _read_semgrep_pin()
    if pin is not None:
        gd._log(f"semgrep pin: {pin}")

    changed = gd.changed_python_files(
        REPO_ROOT,
        source_prefixes=("src/", "tests/", "scripts/"),
        allow_extensions=(".py",),
        max_files=MAX_FILES,
    )
    if not changed:
        gd._log("no changed Python files vs merge-base; nothing to scan")
        return 0

    gd._log(f"scanning {len(changed)} file(s):")
    for p in changed:
        gd._log(f"  - {p.relative_to(REPO_ROOT).as_posix()}")

    pos_args = [str(p) for p in changed]
    argv = _build_semgrep_argv(pin=pin, pos_args=pos_args)
    if argv is None:
        gd._log("uvx not found; skipping targeted semgrep (fail-open)")
        return 0

    # Defensive: every argv entry must be a plain string (no sublists,
    # no shell-fragment strings containing spaces outside a normal path).
    for a in argv:
        if not isinstance(a, str):  # pragma: no cover - defensive, type system enforces
            gd._log(f"internal: argv entry is not a string ({a!r}); skipping (fail-open)")
            return 0

    # NOTE: no --no-git-ignore. That flag was tried and reverted — it
    # causes semgrep to descend into .venv, mutants, .mypy_cache, etc.
    # The regular gitignore-honouring scan is the production default.
    start = time.monotonic()
    try:
        r = subprocess.run(argv, cwd=REPO_ROOT, check=False, timeout=RUN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        gd._log(f"semgrep timed out after {RUN_TIMEOUT_SECONDS}s; skipping (fail-open)")
        return 0
    except FileNotFoundError as exc:
        # Should not happen because we resolved the launcher above, but
        # if the binary disappears between resolution and exec (e.g. a
        # concurrent uninstall), fail-open rather than crash.
        gd._log(f"semgrep launcher not found ({exc}); skipping (fail-open)")
        return 0
    gd._log(f"finished in {time.monotonic() - start:.1f}s (rc={r.returncode})")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
