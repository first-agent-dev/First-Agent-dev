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


def test_clean_readiness_integration_is_only_selected_in_the_explicit_host_lane() -> None:
    test_path = "tests/test_workspace_readiness_integration.py"
    node_id = f"{test_path}::test_clean_candidate_real_readiness_commit_and_local_publication"
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q", test_path]
    env = os.environ.copy()
    env.pop("FA_REQUIRE_EXECUTION_HOST", None)

    default_run = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert default_run.returncode == int(pytest.ExitCode.NO_TESTS_COLLECTED), default_run.stdout + default_run.stderr
    assert node_id not in default_run.stdout
    assert "1 deselected" in default_run.stdout

    host_env = env.copy()
    host_env["FA_REQUIRE_EXECUTION_HOST"] = "1"
    explicit_run = subprocess.run(
        [*command, "-m", "execution_host"],
        cwd=REPO_ROOT,
        env=host_env,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert explicit_run.returncode == int(pytest.ExitCode.OK), explicit_run.stdout + explicit_run.stderr
    assert node_id in explicit_run.stdout
    assert "1 test collected" in explicit_run.stdout


def test_clean_readiness_host_run_refuses_missing_opt_in_before_bootstrap() -> None:
    test_path = "tests/test_workspace_readiness_integration.py"
    env = os.environ.copy()
    env.pop("FA_REQUIRE_EXECUTION_HOST", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            test_path,
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

    output = completed.stdout + completed.stderr
    assert completed.returncode == int(pytest.ExitCode.TESTS_FAILED), output
    assert "execution_host_preflight:explicit_host_opt_in_required" in output
    assert "precommit_prewarm_failed" not in output
    assert "1 failed" in output


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


def test_current_host_substrate_collects_all_eight_nodes_without_running_them() -> None:
    """S4P4/S6P5: strict host collection is inventory, never host acceptance."""
    paths = [
        "tests/integration/test_execution_boundary.py",
        "tests/integration/test_execution_closure.py",
        "tests/integration/test_nested_workflow.py",
        "tests/integration/test_publication_recovery.py",
        "tests/integration/test_workspace_views.py",
        "tests/test_workspace_readiness_integration.py",
    ]
    env = os.environ.copy()
    env["FA_REQUIRE_EXECUTION_HOST"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--strict-markers", *paths, "-m", "execution_host"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=45,
    )
    assert completed.returncode == int(pytest.ExitCode.OK), completed.stdout + completed.stderr
    nodeids = [line for line in completed.stdout.splitlines() if line.startswith("tests/") and "::" in line]
    assert len(nodeids) == len(set(nodeids)) == 8, completed.stdout
    assert {path.split("::", 1)[0] for path in nodeids} == set(paths)
    assert sum("test_stopping_a_view_kills_its_background_descendant" in node for node in nodeids) == 1
    assert "8 tests collected" in completed.stdout
    assert "passed" not in completed.stdout


def test_preapproval_host_sheet_cannot_be_mistaken_for_an_approved_suite() -> None:
    sheet = (
        REPO_ROOT
        / "worklogs/planning-topology-and-executable-contracts-loop/notes"
        / "i03-s6p5-host-run-sheet-preapproval-2026-11-10.md"
    ).read_text(encoding="utf-8")
    assert "BLOCKED / DRAFT; NOT AUTHORIZED FOR EXECUTION" in sheet
    assert "UNKNOWN" in sheet and "W4 TO CAPTURE" in sheet
    assert "1,342,177,280" in sheet and "view_profile_id" in sheet and "read_only_profile_id" in sheet
    assert "AUTO_STASH=0 SKIP_TESTS=1 SKIP_UV_SYNC=1 PRUNE=0" in sheet
    assert "FA_REQUIRE_EXECUTION_HOST=1" in sheet and "--collect-only" in sheet
    assert "L-RCPT-2/6" in sheet and "L-ENTRY-4" in sheet
    assert "three distinct admitted `RunContext` bindings" in sheet
    assert "only the execution run has task `event_log` rows" in sheet
    assert "different, named" in sheet and "STEP7" in sheet and "STEP8" in sheet
    assert "tests/integration/live/" in sheet and "absent" in sheet
    assert "Do not run any host command from this draft" in sheet
