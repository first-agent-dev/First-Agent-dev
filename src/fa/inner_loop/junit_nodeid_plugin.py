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

from typing import Protocol

__all__ = ["JUNIT_NODEID_PROPERTY", "pytest_itemcollected"]

JUNIT_NODEID_PROPERTY = "fa_pytest_nodeid"


class _PytestItem(Protocol):
    """The small part of a pytest Item consumed by this plugin."""

    nodeid: str
    user_properties: list[tuple[str, object]]


def pytest_itemcollected(item: _PytestItem) -> None:
    """Attach pytest's exact nodeid before it creates JUnit test reports."""
    item.user_properties.append((JUNIT_NODEID_PROPERTY, item.nodeid))
