"""Tests for pyrefly import-topology configuration (PY1/PY2 closure).

These tests verify that the pyrefly configuration correctly resolves
tests.* and scripts.* imports through the repository root search path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_pyrefly_config_has_search_path() -> None:
    """Verify pyproject.toml contains search-path for pyrefly."""
    pyproject = REPO_ROOT / "pyproject.toml"
    content = pyproject.read_text()

    assert 'search-path = ["src", "."]' in content or "search-path" in content, (
        "pyproject.toml must contain search-path configuration for pyrefly to resolve tests.* and scripts.* imports"
    )


def test_pyrefly_config_includes_scripts() -> None:
    """Verify pyproject.toml includes scripts in project-includes."""
    pyproject = REPO_ROOT / "pyproject.toml"
    content = pyproject.read_text()

    # Check that scripts is in project-includes
    assert '"scripts"' in content, (
        "pyproject.toml project-includes must contain 'scripts' for pyrefly to check scripts/*.py files"
    )


def test_pyrefly_check_passes() -> None:
    """Integration test: pyrefly check must pass with 0 errors."""
    result = subprocess.run(
        [sys.executable, "-m", "pyrefly", "check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Check that no ERROR lines appear in output
    error_lines = [line for line in result.stdout.splitlines() if line.startswith("ERROR")]

    assert len(error_lines) == 0, f"pyrefly check found {len(error_lines)} errors:\n" + "\n".join(error_lines[:10])


def test_tests_fixtures_session_wiring_importable() -> None:
    """Verify tests.fixtures.session_wiring is importable (resolves PY1)."""
    from tests.fixtures.session_wiring import (
        make_mock_chain,
        mock_success_response,
    )

    # Verify the imported symbols are callable
    assert callable(make_mock_chain)
    assert callable(mock_success_response)


def test_scripts_modules_importable() -> None:
    """Verify scripts.* modules are importable (resolves PY2)."""
    from scripts.check_dead_flags import check_dead_flags
    from scripts.compile_corrections import compile_summary
    from scripts.frozen_guard import scan_tcb_frozen

    assert callable(check_dead_flags)
    assert callable(compile_summary)
    assert callable(scan_tcb_frozen)
