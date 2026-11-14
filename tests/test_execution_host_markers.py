"""The host-only pytest marker contract is explicit and fail-closed."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_pytest_registers_and_excludes_host_only_suites_by_default() -> None:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    settings = config["tool"]["pytest"]["ini_options"]
    marker_names = {entry.split(":", maxsplit=1)[0] for entry in settings["markers"]}

    assert {"execution_host", "live_e2e"} <= marker_names
    addopts = settings["addopts"]
    marker_expression = addopts[addopts.index("-m") + 1]
    assert marker_expression == "not execution_host and not live_e2e"


def test_required_host_run_refuses_empty_execution_host_selection() -> None:
    env = os.environ.copy()
    env["FA_REQUIRE_EXECUTION_HOST"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            str(Path(__file__).resolve()),
            "-m",
            "execution_host",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), completed.stdout + completed.stderr
    assert "FA_REQUIRE_EXECUTION_HOST=1" in completed.stdout + completed.stderr
    assert "no execution_host test was selected" in completed.stdout + completed.stderr
