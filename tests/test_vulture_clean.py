"""C1 test: vulture exits 0 on src/ at min-confidence 90.

This is the same invocation as ``just _deadcode``. Zero findings on src/
is a hard invariant: dead code is either deleted or annotated with an
underscore-prefixed name (per the vulture convention). Adding a
``ignore_names`` entry is a last resort; prefer the rename first.

Skill: tests-writing, C1 (subprocess runs real vulture).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_vulture_clean_src() -> None:
    vulture = shutil.which("vulture")
    if vulture is None:
        # vulture lives in .venv/bin when installed via uv sync
        vulture = str(REPO / ".venv" / "bin" / "vulture")
    r = subprocess.run(
        [vulture, "src/", "--min-confidence", "90"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, f"vulture found dead code (rc={r.returncode}):\n{r.stdout}\n{r.stderr}"
    assert r.stdout.strip() == "", f"vulture produced unexpected output:\n{r.stdout}"
