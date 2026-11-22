"""S0 — the managed substrate probe: a sealed acceptance test must run in a cell.

Why this exists (Q-V2-S0-1 = **A**, decision recorded 2026-11-22). SLICE3 wires
verification to ``ManagedVerifyCommandExecutor``, which runs a command on a pinned
READ view instead of the controller host and carries the JUnit report back *in band*
(``writes_are_visible = False``). Every existing test of that path stops at a double:
``tests/test_slice_verification_runner.py`` stands in for the cell executor, and
``tests/test_managed_workflow_e2e.py`` fakes the container engine's API. Nothing in
the tree proves a **real** cell executes a sealed test and returns its nodeid. This
probe does, and it is the first thing SLICE3 needs, because every later claim about
"the verifier ran the seal" rests on it.

**Host prerequisite (measured 2026-11-22).** Real cell execution needs an approved
execution profile and a container engine the authority can reach. The development
sandbox has neither: ``docker`` and ``podman`` are absent and there is no
``/var/run/docker.sock``. So this probe is written here and must be *run* on the W4
Ubuntu/Docker host:

    FA_STATE_ROOT=$(mktemp -d) python -m pytest \\
        tests/test_ai_native_managed_substrate_probe.py -q -rX

The marker is ``xfail(strict=True)``, which the repository's V4 rule requires and
which is the only honest form here: on a host with the prerequisite the probe must
pass, and ``strict`` turns that XPASS into a failure, so the marker has to be removed
in the same change that proves the substrate. A broken probe on the host fails
loudly rather than passing quietly — the one thing a host-gated test must never do.

What the probe asserts, in order:

1. ``managed_execution_for_run`` binds a real run to a real supervisor (not ``None``).
2. A ``PIN_READER`` view pins over a revision that contains the sealed acceptance
   bytes — the substrate SLICE3 depends on.
3. ``capture_test_nodeids`` — the same function T0 capture and the slice verifier use
   — returns exactly the sealed nodeid over that pinned view, which can only happen if
   a cell ran ``python -m pytest -p fa.inner_loop.junit_nodeid_plugin`` and the JUnit
   report travelled back in band and parsed.
4. The command it ran is the harness's own in-band command, not a host shell.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from fa.execution.client import ExecutionClient, ExecutionUnavailableError, ReadOnlyManagedBashExecutor
from fa.execution.composition import ManagedExecution, managed_execution_for_run
from fa.execution.service import SupervisorService, read_config_file
from fa.execution.types import Access, Operation
from fa.inner_loop.slice_verification import ManagedVerifyCommandExecutor, capture_test_nodeids
from tests.test_execution_composition import _configs, _document, _run
from tests.test_execution_service import _registered
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site

#: One sealed acceptance test, laid out the way D-V2-9 writes it: the closure the seal
#: digests, under ``worklogs/<slug>/acceptance/``, run by the cell's own pytest.
_SLUG = "demo"
_ACCEPTANCE = f"worklogs/{_SLUG}/acceptance"
_PROBE_TEST = f"{_ACCEPTANCE}/tests/test_substrate_probe.py"
_PROBE_NODEID = f"{_PROBE_TEST}::test_the_cell_ran_the_seal"

_INI = """[pytest]
python_files = test_*.py
addopts = -q --strict-markers
testpaths = tests
"""

_PROBE_MODULE = '''"""The probe's own oracle: green only if a cell collected and ran it."""


def test_the_cell_ran_the_seal():
    assert True
'''


def _write_sealed_project(source: Path) -> None:
    """Write the minimal sealed closure, before the workspace is registered."""
    root = source / _ACCEPTANCE
    (root / "tests").mkdir(parents=True)
    (root / "pytest.ini").write_text(_INI, encoding="utf-8")
    (root / "conftest.py").write_text("import pytest\n", encoding="utf-8")
    (root / "tests" / "test_substrate_probe.py").write_text(_PROBE_MODULE, encoding="utf-8")


def _await_health(service: SupervisorService) -> None:
    """Prove the supervisor answers before asking it for a view."""
    client = ExecutionClient(service.socket_path, server_uid=os.getuid(), rpc_timeout_ms=5000)
    deadline = time.monotonic() + 5.0
    while True:
        try:
            client.request(
                Operation.HEALTH,
                request_id="7" * 32,
                namespace=None,
                view=None,
                grant=None,
                payload={},
                deadline=min(deadline, time.monotonic() + 1.0),
                protocol_version=2,
            )
            return
        except ExecutionUnavailableError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)


@contextmanager
def _substrate(site: Site, tmp_path: Path) -> Iterator[tuple[ManagedExecution, ManagedVerifyCommandExecutor]]:
    """A live supervisor, the registered workspace, a pinned READ view and its executor."""
    _write_sealed_project(site.source)
    service_path, yaml_path = _configs(tmp_path, _document(site))
    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        try:
            _await_health(service)
            managed = managed_execution_for_run(_run(site.source), config_path=yaml_path)
            assert managed is not None, "the run was not bound to managed execution"
            assert managed.binding.workspace_id == workspace_id
            read_grant = managed.client.pin_reader(managed.binding, managed.grant.revision_id)
            assert read_grant.view_ref is not None and read_grant.view_ref.access is Access.READ
            assert managed.read_only_profile is not None
            executor = ReadOnlyManagedBashExecutor(
                managed.client,
                namespace=managed.binding.namespace,
                view=read_grant.view_ref,
                grant=read_grant,
                profile=managed.read_only_profile,
                plan_ref=None,
                controller_root=site.source,
            )
            try:
                yield managed, ManagedVerifyCommandExecutor(executor, root=site.source)
            finally:
                executor.suspend()
                managed.client.stop_view(managed.binding.namespace, view=read_grant.view_ref, grant=read_grant)
                managed.close()
        finally:
            stop.set()
            runner.join(timeout=5)
            assert not runner.is_alive()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "requires the W4 Docker host: an approved execution profile plus a reachable "
        "container engine (no docker/podman in the development sandbox)"
    ),
)
def test_a_sealed_acceptance_test_runs_in_the_cell_and_returns_its_nodeid(site: Site, tmp_path: Path) -> None:
    """The one claim SLICE3 builds on: the seal executes off the controller host."""
    with _substrate(site, tmp_path) as (managed, substrate):
        assert managed.binding.workspace_id
        capture = capture_test_nodeids(
            [_PROBE_TEST],
            root=site.source,
            deadline=time.monotonic() + 120.0,
            executor=substrate,
        )

    assert capture.nodeids == {_PROBE_NODEID: True}, capture.detail
    assert capture.command_result is not None
    running = capture.command_result.command
    assert "-p fa.inner_loop.junit_nodeid_plugin" in running, "the probe must run the harness's own command"
    assert "--junitxml=" in running
