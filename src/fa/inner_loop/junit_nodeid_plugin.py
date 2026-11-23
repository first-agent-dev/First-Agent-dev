"""Pytest plugin that preserves exact nodeids in JUnitXML (CT68/CT69).

Pytest's stock ``--junitxml`` output contains ``classname`` and ``name``, not
``Item.nodeid``. Reconstructing a nodeid from those two strings loses the path
under alternate import modes and can be ambiguous for nested/parameterized
cases. This tiny plugin copies the authoritative collector value onto each
item before reports are made; pytest serializes ``user_properties`` into the
``<testcase><properties>`` block. The harness parser must require exactly one
property named :data:`JUNIT_NODEID_PROPERTY` per executed test and treat a
missing/duplicate property as an unusable report, never synthesize an id.

Load explicitly with ``-p fa.inner_loop.junit_nodeid_plugin`` alongside the
harness-issued ``--junitxml`` run. It is not an auto-loaded plugin and does
nothing to ordinary test runs.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Protocol

import pytest

__all__ = ["JUNIT_NODEID_PROPERTY", "JUNIT_RUN_ID_ENV", "JUNIT_RUN_ID_PROPERTY", "pytest_itemcollected"]

from .junit_properties import (
    JUNIT_CALL_OUTCOME_PROPERTY,
    JUNIT_NODEID_PROPERTY,
    JUNIT_RUN_ID_ENV,
    JUNIT_RUN_ID_PROPERTY,
)


class _PytestItem(Protocol):
    """The small part of a pytest Item consumed by this plugin."""

    nodeid: str
    user_properties: list[tuple[str, object]]


def pytest_itemcollected(item: _PytestItem) -> None:
    """Attach pytest's exact nodeid before it creates JUnit test reports."""
    item.user_properties.append((JUNIT_NODEID_PROPERTY, item.nodeid))
    # Computed by the harness, never inherited through the environment scrubber.
    if run_id := os.environ.get(JUNIT_RUN_ID_ENV):
        item.user_properties.append((JUNIT_RUN_ID_PROPERTY, run_id))


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[object]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Attach the actual call-phase exception class, not JUnit's generic failure label."""
    report = yield
    if call.when == "call":
        if report.failed and call.excinfo is not None and isinstance(call.excinfo.value, AssertionError):
            kind = "assertion"
        elif report.passed:
            kind = "passed"
        elif report.skipped:
            kind = "skipped"
        else:
            kind = "other"
        item.user_properties.append((JUNIT_CALL_OUTCOME_PROPERTY, kind))
        # Report objects need not share the item list across pytest releases.
        report.user_properties = list(item.user_properties)
    return report
