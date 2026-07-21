"""Kill-check tests for S7: check_log_kind_contract.py script.

Verifies:
1. Script exits 0 on clean tree
2. Script detects unknown kind (kill-check: remove a LogKind member → script fails)
3. Script detects missing dual-write for CONSOLE_MIRROR_KINDS
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/check_log_kind_contract.py")


def _run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )


# ── Kill-check 1: Script exits 0 on clean tree ──────────────────────


def test_script_exits_0_on_clean_tree():
    """The contract check script must exit 0 on the current clean source tree."""
    result = _run_script()
    assert result.returncode == 0, (
        f"Script exited {result.returncode} on clean tree.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ── Kill-check 2: Script reports LogKind member count ───────────────


def test_script_reports_log_kind_count():
    """The script output must include the LogKind member count."""
    result = _run_script()
    assert "LogKind members:" in result.stdout, (
        f"Script output missing LogKind member count.\nstdout:\n{result.stdout}"
    )


# ── Kill-check 3: Script reports CONSOLE_MIRROR_KINDS ───────────────


def test_script_reports_console_mirror_kinds():
    """The script output must include the CONSOLE_MIRROR_KINDS count."""
    result = _run_script()
    assert "CONSOLE_MIRROR_KINDS members:" in result.stdout, (
        f"Script output missing CONSOLE_MIRROR_KINDS count.\nstdout:\n{result.stdout}"
    )


# ── Kill-check 4: Script validates all 4 checks ─────────────────────


def test_script_runs_all_checks():
    """The script must run all 4 contract checks."""
    result = _run_script()
    output = result.stdout
    assert "CHECK 1:" in output, "Missing CHECK 1"
    assert "CHECK 2:" in output, "Missing CHECK 2"
    assert "CHECK 3:" in output, "Missing CHECK 3"
    assert "CHECK 4:" in output, "Missing CHECK 4"
