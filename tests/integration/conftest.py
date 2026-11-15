"""Fixtures for explicit W4 Docker/cgroup host tests; no prerequisite is skipped."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest

from fa.execution import composition
from tests.integration._host import (
    ExecutionHostPreflightError,
    ExecutionHostReadiness,
    ExecutionHostRuntime,
    load_and_probe_execution_host,
    require_execution_host_opt_in,
    start_execution_host_runtime,
)


@pytest.fixture(scope="session")
def execution_host_readiness() -> ExecutionHostReadiness:
    """Require the explicit gate and prove actual prerequisites before cases run."""
    try:
        require_execution_host_opt_in(os.environ.get("FA_REQUIRE_EXECUTION_HOST"))
        return load_and_probe_execution_host()
    except ExecutionHostPreflightError as error:
        pytest.fail(str(error), pytrace=False)


@pytest.fixture
def host_runtime(
    execution_host_readiness: ExecutionHostReadiness,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[ExecutionHostRuntime]:
    """Run the production supervisor over the real daemon on disposable roots."""
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", config_path)
    try:
        runtime = start_execution_host_runtime(
            execution_host_readiness,
            tmp_path,
            config_yaml_path=config_path,
        )
    except ExecutionHostPreflightError as error:
        pytest.fail(str(error), pytrace=False)

    yield runtime

    try:
        runtime.close()
    except Exception as error:  # noqa: BLE001 - teardown uncertainty must fail the required host run.
        pytest.fail(f"execution_host_cleanup_failed:{type(error).__name__}", pytrace=False)
