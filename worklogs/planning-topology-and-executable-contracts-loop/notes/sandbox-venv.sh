#!/usr/bin/env bash
# Rebuild the sandbox venv for this planning task.
#
#   bash worklogs/planning-topology-and-executable-contracts-loop/notes/sandbox-venv.sh
#   export PATH="$PWD/.venv/bin:$PATH"
#
# `.venv` is excluded from the snapshot, so it disappears between turns and
# sometimes mid-turn. Anything kept outside the repository disappears too --
# which is why this lives here and not in /tmp or $HOME.
#
# Two things are load-bearing and easy to forget:
#  * only python3.11 exists but pyproject requires >=3.13, so fa.inner_loop
#    fails at import without a typing.override shim;
#  * PATH must carry .venv/bin or uv-dependent tests fail spuriously.
set -euo pipefail

REPO=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)
cd "$REPO"

python3 -m venv .venv
./.venv/bin/python -m pip install -q --upgrade pip

DEPS=$(./.venv/bin/python - <<'PY'
import tomllib
from pathlib import Path

data = tomllib.loads(Path("pyproject.toml").read_text())
deps = list(data["project"].get("dependencies", []))
for extra in data["project"].get("optional-dependencies", {}).values():
    deps.extend(extra)
print(" ".join(repr(d) for d in deps))
PY
)
# shellcheck disable=SC2086
eval ./.venv/bin/python -m pip install -q $DEPS \
    fastjsonschema bashlex 'pyrefly==1.1.1' 'mutmut==3.6.0' uv vulture pytest ruff mypy
./.venv/bin/python -m pip install -q --only-binary=:all: semgrep || echo "semgrep: skipped"

SITE=$(./.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
printf '%s\n' "$REPO/src" > "$SITE/_fa_src.pth"
printf '%s\n' "$REPO" > "$SITE/_fa_root.pth"

cat > "$SITE/_fa_shim.py" <<'PY'
"""Backfill typing.override for python3.11 (pyproject asks for >=3.13)."""

import typing

if not hasattr(typing, "override"):

    def override(func):  # type: ignore[no-untyped-def]
        return func

    typing.override = override  # type: ignore[attr-defined]
PY
printf '%s\n' 'import _fa_shim' > "$SITE/_fa_shim.pth"

./.venv/bin/python -c 'from fa.inner_loop.slice_verification import apply_kill; print("venv ok")'
