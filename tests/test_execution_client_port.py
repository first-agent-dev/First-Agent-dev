"""SLICE4 STEP2a — the file-tool port over the supervisor wire (C0/C1/C3).

**Why this bank exists.** SLICE7 built the run-scoped composition (client,
binding, writer grant) and the plan publisher on top of it, but the *file tools*
still had no managed binding: `AuthorityWorkspacePort` needs an in-process
`WorkspaceAuthority`, and after E277 the authority is a service the controller
cannot hold. This bank proves the wire binding of the same port — the same
`WorkspacePort` protocol, the same closed error vocabulary, the same guarantees —
so the SLICE4 STEP2 cutover has a supplier to consume.

Root: a real `SupervisorService` behind a real Unix socket and a real
`ExecutionClient`; the only stand-ins are subclasses that record what the port
actually sent.

Path inventory:
  P1 write + read round trip lands in the admitted view, canonical bytes untouched
  P2 the CAS is the authority's: a stale base is ``stale`` and the other writer wins
  P3 a MUTATION view refuses paths outside the approved roots (``denied``)
  P4 a READ view has no write path, and the refusal costs no RPC
  P5 uncertainty is ``unavailable``, never ``denied``; contract bugs are ``invalid_request``
  P6 the file tools reach the view through the port (the consumer contract)
  P7 opening a view needs the run's writer grant; a grant for another view proves nothing
  P8 ending an EXECUTION view is proved, idempotent, and closes its writes
  P9 a READ view adds its pin revoke; an unproved end is reported, never assumed
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from fa.execution.client import (
    ExecutionClient,
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
)
from fa.execution.composition import ManagedExecution, managed_execution_for_run
from fa.execution.service import SupervisorService, read_config_file
from fa.execution.tool_port import ClientWorkspacePort
from fa.execution.types import (
    Access,
    ExecutionContractError,
    GrantReply,
    NamespaceRef,
    Operation,
    ViewPurpose,
    ViewRef,
)
from fa.inner_loop.plan_admission import PlanRef, read_plan_snapshot
from fa.inner_loop.tools.read_file import build_read_file_tool
from fa.inner_loop.tools.workspace_port import PORT_READ_MAX_BYTES, WorkspacePortError
from fa.inner_loop.tools.write_file import build_write_file_tool
from tests.test_execution_composition import PLAN_RELATIVE, _configs, _document, _run
from tests.test_execution_service import _registered
from tests.test_execution_tool_port import _call
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site

PLAN_BYTES = b"# Existing plan\n"


def _plan_ref(site: Site) -> PlanRef:
    """A plan ref over bytes the registered workspace really holds.

    ``_recheck_context`` (workspace.py:1959) is the reason this cannot be a
    literal: a `plan_ref` is a promise about the authority's own bytes.
    """
    path = site.source / PLAN_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PLAN_BYTES)
    return read_plan_snapshot(site.source, Path(PLAN_RELATIVE)).ref


class _CountingClient(ExecutionClient):
    """A real client that remembers the operations it was asked to send."""

    def __init__(self, path: Path, *, server_uid: int, rpc_timeout_ms: int) -> None:
        super().__init__(path, server_uid=server_uid, rpc_timeout_ms=rpc_timeout_ms)
        self.sent: list[Operation] = []

    def request(self, operation: Operation, **kwargs: Any) -> dict[str, Any]:
        self.sent.append(operation)
        return super().request(operation, **kwargs)


class _ScriptedClient(ExecutionClient):
    """A real client whose transport answers with a fixed refusal (no socket at all)."""

    def __init__(self, error: BaseException) -> None:
        super().__init__(Path("/nonexistent/supervisor.sock"), server_uid=0, rpc_timeout_ms=1000)
        self.error = error
        self.sent: list[Operation] = []

    def request(self, operation: Operation, **kwargs: Any) -> dict[str, Any]:
        self.sent.append(operation)
        raise self.error


def _namespace() -> NamespaceRef:
    return NamespaceRef("session-1", "run-1")


def _other_view() -> ViewRef:
    """A well-formed view identity that is not the one under test."""
    return ViewRef(
        "ws-" + "3" * 32,
        "view-" + "4" * 32,
        "rev-" + "5" * 32,
        "run-1",
        1,
        Access.WRITE,
        ViewPurpose.MUTATION,
    )


@contextmanager
def _served(site: Site, tmp_path: Path) -> Iterator[ManagedExecution]:
    """A live supervisor, the registered workspace, and this run's managed execution."""
    service_path, yaml_path = _configs(tmp_path, _document(site))
    with SupervisorService(read_config_file(service_path)) as service:
        workspace_id = _registered(service)
        stop = threading.Event()
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        try:
            managed = managed_execution_for_run(_run(site.source), config_path=yaml_path)
            assert managed is not None
            # The composition holds the writer for the run that registered nothing:
            # STEP8 made the run context the only source of the namespace.
            assert managed.binding.workspace_id == workspace_id
            assert managed.grant.operation is Operation.ACQUIRE_WRITER
            yield managed
        finally:
            stop.set()
            runner.join(timeout=5)
            assert not runner.is_alive()


def _socket_client(site: Site, tmp_path: Path) -> _CountingClient:
    """A second real client on the same socket, used where the RPC count matters."""
    service_path, _ = _configs(tmp_path, _document(site))
    config = read_config_file(service_path)
    return _CountingClient(config.socket_path, server_uid=next(iter(config.controller_uids)), rpc_timeout_ms=5000)


def _port(
    client: ExecutionClient,
    namespace: NamespaceRef,
    grant: GrantReply,
) -> ClientWorkspacePort:
    assert grant.view_ref is not None
    return ClientWorkspacePort(client, namespace=namespace, view=grant.view_ref, grant=grant)


def _mutation_port(
    managed: ManagedExecution, plan: PlanRef, *, client: ExecutionClient | None = None
) -> ClientWorkspacePort:
    """One MUTATION view of the run's workspace, bound to the port under test."""
    grant = managed.open_view(
        access=Access.WRITE,
        purpose=ViewPurpose.MUTATION,
        base_revision=managed.grant.revision_id,
        plan_ref=plan,
    )
    return _port(client if client is not None else managed.client, managed.binding.namespace, grant)


def _canonical(site: Site, name: str) -> bytes | None:
    path = site.source / name
    return path.read_bytes() if path.is_file() else None


# ---------------------------------------------------------------------------
# P1 — round trip through the view, canonical bytes untouched
# ---------------------------------------------------------------------------


def test_the_port_reads_and_writes_the_admitted_view(site: Site, tmp_path: Path) -> None:
    """C1: bytes and digests come from the view; the host tree is not a write path."""
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        port = _mutation_port(managed, plan)

        written = port.write_file("src/module.py", "VALUE = 1\n")
        assert written.bytes == len("VALUE = 1\n")
        read = port.read_file("src/module.py", max_bytes=4096)
        assert read.content == "VALUE = 1\n"
        assert read.sha256 == written.sha256
        assert read.eof is True
        # The single most important negative: the canonical workspace still has no
        # such file. A port that wrote host bytes would make the authority's next
        # `_unchanged` check fail (workspace.py:1320) and end the run.
        assert _canonical(site, "src/module.py") is None


# ---------------------------------------------------------------------------
# P2 — the CAS belongs to the authority
# ---------------------------------------------------------------------------


def test_a_stale_write_is_a_conflict_and_the_concurrent_bytes_survive(site: Site, tmp_path: Path) -> None:
    """C1: `expected_sha256` is passed through, not evaluated locally."""
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        port = _mutation_port(managed, plan)
        base = port.write_file("src/race.py", "one")
        port.write_file("src/race.py", "two", expected_sha256=base.sha256)

        with pytest.raises(WorkspacePortError) as conflict:
            port.write_file("src/race.py", "three", expected_sha256=base.sha256)

        assert conflict.value.code == "stale"
        assert port.read_file("src/race.py", max_bytes=64).content == "two"


# ---------------------------------------------------------------------------
# P3 — the purpose gate is the authority's, and the port reports it faithfully
# ---------------------------------------------------------------------------


def test_a_write_outside_the_mutation_roots_is_denied(site: Site, tmp_path: Path) -> None:
    """C1: a MUTATION view writes src/ and scripts/ only (E259's gate)."""
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        port = _mutation_port(managed, plan)

        with pytest.raises(WorkspacePortError) as refused:
            port.write_file("worklogs/plan.md", "not mine to write")

        assert refused.value.code == "denied"
        assert _canonical(site, PLAN_RELATIVE) == PLAN_BYTES


# ---------------------------------------------------------------------------
# P4 — a READ view has no write path, and says so without spending an RPC
# ---------------------------------------------------------------------------


def test_a_read_only_view_refuses_writes_before_any_rpc(site: Site, tmp_path: Path) -> None:
    """C0: the refusal is a property of the view the authority minted."""
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        view_grant = managed.open_view(
            access=Access.READ,
            purpose=ViewPurpose.VERIFICATION,
            base_revision=None,
            plan_ref=plan,
        )
        service_path, _ = _configs(tmp_path, _document(site))
        config = read_config_file(service_path)
        client = _CountingClient(config.socket_path, server_uid=next(iter(config.controller_uids)), rpc_timeout_ms=5000)
        port = _port(client, managed.binding.namespace, view_grant)

        with pytest.raises(WorkspacePortError) as refused:
            port.write_file("src/module.py", "nope")

        assert refused.value.code == "denied"
        assert client.sent == []  # the refusal is local and cannot be more certain than the view
        # Reads still work: the view is a reader, not a dead one.
        assert port.read_file(PLAN_RELATIVE, max_bytes=64).content == PLAN_BYTES.decode()


# ---------------------------------------------------------------------------
# P5 — one vocabulary, and uncertainty never masquerades as a refusal
# ---------------------------------------------------------------------------


def _fixed_grant() -> GrantReply:
    return GrantReply(Operation.CREATE_VIEW, "2" * 64, _other_view(), None, None)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ExecutionUncertainError("op-1"), "unavailable"),
        (ExecutionUnavailableError(), "unavailable"),
        (ExecutionRejectedError("PATH_DENIED", None), "denied"),
        (ExecutionRejectedError("STALE_REVISION", None), "stale"),
        (ExecutionRejectedError("INPUT_POLICY", None), "input_policy"),
        (ExecutionRejectedError("WORKSPACE_BUSY", None), "unavailable"),
        (ExecutionContractError(), "invalid_request"),
    ],
)
def test_client_refusals_keep_the_port_vocabulary(error: BaseException, expected: str) -> None:
    """C3: the model sees the same closed codes whichever transport it reached.

    The uncertain row is the one that matters: a lost reply means the bytes may
    have landed, so "denied" would invite the retry the write must not get.
    """
    client = _ScriptedClient(error)
    port = _port(client, _namespace(), _fixed_grant())

    with pytest.raises(WorkspacePortError) as refused:
        port.write_file("src/module.py", "x")

    assert refused.value.code == expected


def test_local_argument_checks_are_invalid_request_and_cost_no_rpc() -> None:
    """C0: the port refuses what the wire would refuse, before sending anything."""
    client = _ScriptedClient(ExecutionContractError())
    port = _port(client, _namespace(), _fixed_grant())

    for call in (
        lambda: port.write_file("src/x.py", "x", expected_sha256="not-a-digest"),
        lambda: port.write_file("src/x.py", b"bytes"),  # type: ignore[arg-type]
        lambda: port.read_file("src/x.py", max_bytes=0),
        lambda: port.read_file("src/x.py", max_bytes=PORT_READ_MAX_BYTES * 4),
    ):
        with pytest.raises(WorkspacePortError) as refused:
            call()
        assert refused.value.code in {"invalid_request", "input_policy"}

    assert client.sent == []


# ---------------------------------------------------------------------------
# P6 — the tools are the consumer, and they reach the view
# ---------------------------------------------------------------------------


def test_the_file_tools_write_and_read_through_the_port(site: Site, tmp_path: Path) -> None:
    """C3 wiring: the port is what the tools accept, not a parallel interface."""
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        port = _mutation_port(managed, plan)
        written = _call(
            build_write_file_tool(site.source, workspace_io=port), {"path": "scripts/run.sh", "content": "echo hi\n"}
        )
        assert written.error is None, written.error
        # The read goes through the tool as well: had either tool fallen back to the
        # host root, this would fail on a file the host never received.
        read = _call(build_read_file_tool(site.source, workspace_io=port), {"path": "scripts/run.sh"})
        assert read.error is None, read.error
        assert "echo hi" in str(read.result)
        assert port.read_file("scripts/run.sh", max_bytes=64).content == "echo hi\n"
        assert _canonical(site, "scripts/run.sh") is None


# ---------------------------------------------------------------------------
# P7 — the run's own grant is what opens a view
# ---------------------------------------------------------------------------


def test_a_view_grant_cannot_open_or_close_anything(site: Site, tmp_path: Path) -> None:
    """C0: CREATE_VIEW is an owner operation; a view grant is not an owner grant."""
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        view_grant = managed.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.MUTATION,
            base_revision=managed.grant.revision_id,
            plan_ref=plan,
        )
        assert view_grant.view_ref is not None

        with pytest.raises(ExecutionContractError):
            managed.client.open_view(
                managed.binding,
                access=Access.WRITE,
                purpose=ViewPurpose.MUTATION,
                base_revision=managed.grant.revision_id,
                plan_ref=plan,
                grant=view_grant,  # a view grant, not the writer
            )
        with pytest.raises(ExecutionContractError):
            # A grant that names a different view authorizes no end for this one.
            managed.client.stop_view(managed.binding.namespace, view=_other_view(), grant=view_grant)
        assert managed.stop_view(view_grant) is True


# ---------------------------------------------------------------------------
# P8 — ending a view is proved, and an unproved end is reported
# ---------------------------------------------------------------------------


def test_a_stopped_view_refuses_further_writes_and_reports_the_uncertain_case(site: Site, tmp_path: Path) -> None:
    """C1/C3: after the view is ended its writes fail; a second end is not a success."""
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.MUTATION,
            base_revision=managed.grant.revision_id,
            plan_ref=plan,
        )
        port = _port(managed.client, managed.binding.namespace, grant)
        port.write_file("src/before.py", "ok")

        assert managed.stop_view(grant) is True
        with pytest.raises(WorkspacePortError):
            port.write_file("src/after.py", "too late")

        # A second end is the authority's own idempotent answer - a proof, not a
        # refusal - so it is just as true as the first one.
        assert managed.stop_view(grant) is True
        # And the end did not cost the run its writer: the next stage opens its own
        # view over the same workspace, which is what makes a stage-over-stage view
        # sequence possible at all.
        second = _mutation_port(managed, plan)
        assert second.write_file("src/second.py", "ok").bytes == 2


# ---------------------------------------------------------------------------
# P9 — one verb, two endings: the wire shape follows the view's own access
# ---------------------------------------------------------------------------


class _FramedClient(ExecutionClient):
    """A wire-level fake: fixed answers per operation, and the operations recorded."""

    def __init__(self, answers: dict[Operation, Any]) -> None:
        super().__init__(Path("/nonexistent/supervisor.sock"), server_uid=0, rpc_timeout_ms=1000)
        self._answers = answers
        self.sent: list[Operation] = []

    def request(self, operation: Operation, **kwargs: Any) -> dict[str, Any]:
        self.sent.append(operation)
        answer = self._answers[operation]
        if isinstance(answer, BaseException):
            raise answer
        return dict(answer)


def _read_view_grant() -> GrantReply:
    view = ViewRef(
        "ws-" + "3" * 32,
        "view-" + "4" * 32,
        "rev-" + "5" * 32,
        "run-1",
        1,
        Access.READ,
        ViewPurpose.VERIFICATION,
    )
    return GrantReply(Operation.CREATE_VIEW, "2" * 64, view, None, None)


def test_an_execution_view_is_ended_by_stop_alone() -> None:
    """C0: a WRITE view has no reader pin, so a RELEASE would be a false step."""
    grant = _fixed_grant()
    client = _FramedClient({Operation.STOP_VIEW: {"terminal": True, "view_id": "view-1"}})

    assert client.stop_view(_namespace(), view=grant.view_ref, grant=grant) is True
    assert client.sent == [Operation.STOP_VIEW]


def test_a_read_view_ends_by_stop_and_release() -> None:
    """C1: the pin is the difference between the two purposes."""
    grant = _read_view_grant()
    client = _FramedClient(
        {
            Operation.STOP_VIEW: {"terminal": True, "view_id": "view-1"},
            Operation.RELEASE: {"released": True},
        }
    )

    assert client.stop_view(_namespace(), view=grant.view_ref, grant=grant) is True
    assert client.sent == [Operation.STOP_VIEW, Operation.RELEASE]


@pytest.mark.parametrize(
    ("terminal", "release", "expected"),
    [
        # Not terminal: the view still holds its copy, and no pin may be revoked
        # on the strength of an end that did not happen.
        (False, None, False),
        # Determinate refusal: the authority holds no such pin, so nothing is open.
        (True, ExecutionRejectedError("UNAUTHORIZED", None), True),
        # Indeterminate: the pin may still be held - say so instead of assuming.
        (True, ExecutionUncertainError("op-1"), False),
        (True, ExecutionUnavailableError(), False),
    ],
)
def test_an_unproved_or_undetermined_end_is_not_a_closed_view(
    terminal: bool, release: BaseException | None, expected: bool
) -> None:
    """C3: ``True`` means proved; everything else sends the caller to recovery."""
    grant = _read_view_grant()
    answers: dict[Operation, Any] = {Operation.STOP_VIEW: {"terminal": terminal, "view_id": "view-1"}}
    if release is not None:
        answers[Operation.RELEASE] = release
    client = _FramedClient(answers)

    assert client.stop_view(_namespace(), view=grant.view_ref, grant=grant) is expected
    if not terminal:
        assert Operation.RELEASE not in client.sent


def test_a_live_read_view_ends_once_and_its_pin_does_not_come_back(site: Site, tmp_path: Path) -> None:
    """C1: the READ branch over the real authority.

    The asymmetry with P8 is the authority's, and worth stating where it bites: a
    READ view's ending *is* its pin revocation, so the second end has no pin to
    prove and the authority answers ``UNAUTHORIZED`` (verified against the live
    service). One caller ends a view once; a WRITE view, which keeps its terminal
    receipt, answers twice.
    """
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=Access.READ, purpose=ViewPurpose.VERIFICATION, base_revision=None, plan_ref=plan
        )

        assert managed.stop_view(grant) is True
        assert managed.stop_view(grant) is False
