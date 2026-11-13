"""S5P1 STEP2 — the acquisition view is pinned, validated, and always stopped.

`_pinned_acquisition_substrate` is the production seam that gives the acquisition
planner a real READ view. Two things about it are worth a bank of their own:

  * it pins with `plan_ref=None`, because acquisition happens before any plan is
    admitted — and `ProtectedPlanContext` documents that as the ordinary
    no-active-plan case rather than formal evidence;
  * the view is stopped in `finally`, so a planner that raises cannot leave a
    pinned view owned by a finished run (the next run on the workspace would then
    be refused until somebody settled it).

Classes (knowledge/skills/tests-writing):
  C1 — a real pin becomes a real port plus the names that view reports.
  C0 — nothing available is `None`, and a wrong grant is a contract violation.

The transport is a real `ExecutionClient` with `request` overridden, because
`ClientWorkspacePort` refuses anything that is not one — and because a fake that
answers less than a supervisor does would prove the seam works against a fiction.
Each answer below says which real requirement it satisfies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, override

import pytest

from fa.execution.client import ExecutionClient
from fa.execution.primitives import ExecutionContractError
from fa.execution.tool_port import ClientWorkspacePort
from fa.execution.types import (
    Access,
    GrantReply,
    NamespaceRef,
    Operation,
    ViewPurpose,
    ViewRef,
)
from fa.inner_loop.plan_admission import PlanRef
from fa.inner_loop.workflow_controller import (
    WorkflowContext,
    _pinned_acquisition_substrate,
    workflow_artifact_paths,
)

from .test_plan_reference import _config

# The transport validates these ids as 32 hex digits, so the fixture uses the real
# shapes rather than readable names the product would refuse.
WORKSPACE = "ws-" + "a" * 32
VIEW = "view-" + "b" * 32
REVISION = "rev-" + "c" * 32


class _Client(ExecutionClient):
    """A real client whose transport answers with fixed replies; no socket at all."""

    def __init__(self, *, grant: Any, names: tuple[str, ...] = (), incomplete: tuple[str, ...] = ()) -> None:
        super().__init__(Path("/nonexistent/supervisor.sock"), server_uid=0, rpc_timeout_ms=1000)
        self._grant = grant
        self._names = names
        self._incomplete = incomplete
        self.pins: list[dict[str, Any]] = []
        self.stops: list[str] = []
        self.operations: list[Operation] = []

    @override
    def request(self, operation: Operation, **kwargs: Any) -> dict[str, Any]:
        self.operations.append(operation)
        if operation is Operation.HEALTH:
            # A v1-only peer makes `list_projects` unavailable rather than empty, so
            # the fixture advertises what a real v2 supervisor advertises.
            return {"ready": True, "protocol_version": 2, "features": ["list_projects"]}
        if operation is Operation.PIN_READER:
            self.pins.append(kwargs.get("payload", {}))
            # The client decodes the *wire* grant, not a `GrantReply` object, so the
            # fixture answers in the shape a supervisor actually sends.
            return {
                "view_ref": self._grant.view_ref.to_dict(),
                "capability": self._grant.capability,
                "generation": self._grant.generation,
                "revision_id": self._grant.revision_id,
            }
        if operation is Operation.LIST_PROJECTS:
            return {"projects": [{"project_slug": name} for name in self._names], "incomplete": list(self._incomplete)}
        if operation is Operation.STOP_VIEW:
            view = kwargs.get("view")
            self.stops.append("" if view is None else view.view_id)
            # The real client requires the terminality receipt and then releases a
            # READ view, so a fake replying anything less is not a working transport.
            return {"terminal": True}
        if operation is Operation.RELEASE:
            return {}
        raise AssertionError(f"unexpected operation {operation}")


class _Binding:
    """The two identity fields a binding owns; the client infers nothing else."""

    namespace = NamespaceRef(WORKSPACE, "run-1")
    workspace_id = WORKSPACE


class _Managed:
    def __init__(self, client: _Client) -> None:
        self.client = client
        self.binding = _Binding()
        self.current_revision_id = REVISION
        self.read_only_profile = object()


def _grant(
    *,
    operation: Operation = Operation.PIN_READER,
    access: Access = Access.READ,
    purpose: ViewPurpose = ViewPurpose.PROJECT,
    owner: str = "run-1",
) -> GrantReply:
    view = ViewRef(WORKSPACE, VIEW, REVISION, owner, 1, access, purpose)
    # A view grant carries neither a generation nor a revision: those belong to the
    # owner grants (`GrantReply.__post_init__`).
    return GrantReply(operation, "d" * 64, view, None, None)


def _spy_on_port_builds(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    """Record every `ClientWorkspacePort` construction the seam attempts."""
    import fa.inner_loop.workflow_controller as controller

    built: list[tuple[Any, ...]] = []
    real = controller.ClientWorkspacePort

    def _counting(*args: Any, **kwargs: Any) -> Any:
        built.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(controller, "ClientWorkspacePort", _counting)
    return built


def _ctx(tmp_path: Any, managed: Any) -> WorkflowContext:
    return WorkflowContext(
        run_id="run-1",
        base_task="t",
        per_role_task={},
        artifact_paths=workflow_artifact_paths("run-1", base_dir=tmp_path / "logs"),
        config=_config(tmp_path),
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        managed_execution=managed,
        # A genuine plan ref, so "acquisition pinned with no plan" is a fact this
        # bank can observe. With None here, passing the run's ref would be
        # indistinguishable from passing None and the check would prove nothing.
        managed_plan_ref=PlanRef("worklogs/demo-project/increments/i.md", "EXISTING_SELECTION", "e" * 64),
    )


# ── C1: a real pin becomes a real portal ────────────────────────────────────


def test_the_substrate_pins_with_no_plan_and_returns_a_port(tmp_path: Any) -> None:
    client = _Client(grant=_grant(), names=("demo-project",), incomplete=("broken-proj",))
    managed = _Managed(client)

    with _pinned_acquisition_substrate(_ctx(tmp_path, managed)) as substrate:
        assert substrate is not None
        assert isinstance(substrate.port, ClientWorkspacePort)
        assert substrate.project_names == ("demo-project",)
        assert substrate.incomplete_names == ("broken-proj",)

    assert len(client.pins) == 1
    assert client.pins[0]["plan_ref"] is None, "acquisition runs before any plan exists"
    assert client.pins[0]["revision_id"] == REVISION


def test_the_view_is_stopped_even_when_the_body_raises(tmp_path: Any) -> None:
    """A leaked pin would refuse the next run on this workspace."""
    client = _Client(grant=_grant())
    managed = _Managed(client)

    with pytest.raises(RuntimeError):
        with _pinned_acquisition_substrate(_ctx(tmp_path, managed)):
            raise RuntimeError("planner blew up")

    assert client.stops == [VIEW]


def test_the_client_labels_the_grant_with_the_operation_it_performed() -> None:
    """Why the operation clause is a backstop rather than a live branch.

    `ExecutionClient.pin_reader` stamps every reply it returns with `PIN_READER`
    (`client.py:_grant`), so a real pin cannot come back with another operation.
    The seam's operation check therefore guards against a caller that constructs a
    grant some other way -- it is real defence, but it is *unreachable through this
    client*, and a test pretending otherwise would be testing a case the product
    cannot produce.

    Measured, not assumed: a `CREATE_VIEW` grant over an otherwise-valid READ/
    PROJECT view does satisfy `GrantReply`, so nothing but the seam's own check
    stands between such a grant and a port built on a view acquired another way.
    """
    client = _Client(grant=_grant())
    grant = client.pin_reader(_Binding(), revision_id=REVISION, plan_ref=None, deadline=None)

    assert grant.operation is Operation.PIN_READER
    assert grant.view_ref is not None and grant.view_ref.access is Access.READ
    assert grant.view_ref.purpose is ViewPurpose.PROJECT


# ── C0: nothing available, and a wrong grant ────────────────────────────────


def test_no_managed_execution_yields_nothing(tmp_path: Any) -> None:
    """`None` is "no substrate", and the caller turns it into a rule, not a host run."""
    with _pinned_acquisition_substrate(_ctx(tmp_path, None)) as substrate:
        assert substrate is None


def test_a_grant_for_another_runs_view_is_a_contract_violation(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Continuing would read a view this run does not own.

    The spy matters: `ClientWorkspacePort` refuses this same grant with the same
    exception type, so an assertion on the exception alone cannot tell whether the
    seam checked anything. Counting constructions can.
    """
    built = _spy_on_port_builds(monkeypatch)
    client = _Client(grant=_grant(owner="other-run"))

    with pytest.raises(ExecutionContractError):
        with _pinned_acquisition_substrate(_ctx(tmp_path, _Managed(client))):
            pass

    assert built == [], "the seam must refuse before building a port on a foreign view"


def test_a_candidate_view_is_a_contract_violation(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The coder's CANDIDATE view is not an acquisition view; the purpose matters."""
    built = _spy_on_port_builds(monkeypatch)
    client = _Client(grant=_grant(purpose=ViewPurpose.CANDIDATE))

    with pytest.raises(ExecutionContractError):
        with _pinned_acquisition_substrate(_ctx(tmp_path, _Managed(client))):
            pass

    assert built == [], "a CANDIDATE view must be refused before any port is built"


# ── the seam's own checks, exercised through a client that misbehaves ────────


class _MisreportingClient(_Client):
    """A client that returns a grant it did not earn.

    Not a shape the shipped `ExecutionClient` can produce — it stamps every reply
    with `PIN_READER` and the transport refuses a WRITE grant on a pin. That is
    exactly why the seam re-checks instead of trusting its caller: these two
    oracles are the only way to show the check is live rather than decorative, and
    they simulate the bug the check exists to survive.
    """

    def __init__(self, *, produced: Any) -> None:
        super().__init__(grant=produced)
        self._produced = produced

    @override
    def pin_reader(self, binding: Any, revision_id: str, **kwargs: Any) -> Any:
        return self._produced


def test_a_grant_for_a_different_operation_is_refused(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    built = _spy_on_port_builds(monkeypatch)
    forged = _grant(operation=Operation.CREATE_VIEW)
    client = _MisreportingClient(produced=forged)

    with pytest.raises(ExecutionContractError):
        with _pinned_acquisition_substrate(_ctx(tmp_path, _Managed(client))):
            pass

    assert built == [], "a grant from another operation must not become a readable view"


def test_a_write_grant_is_refused(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Acquisition asks for observation; a writer grant would be a different request.

    The pair this test feeds in is one `GrantReply` refuses to construct: WRITE on
    `PIN_READER`. It is built the only way it can then arrive — as a legal grant
    whose operation is changed afterwards — which is precisely the bug the seam's
    access check exists to survive. Every other check (operation, purpose, owner)
    passes, so nothing but the access clause can reject it.
    """
    built = _spy_on_port_builds(monkeypatch)
    forged = _grant(operation=Operation.CREATE_VIEW, access=Access.WRITE)
    object.__setattr__(forged, "operation", Operation.PIN_READER)
    client = _MisreportingClient(produced=forged)

    with pytest.raises(ExecutionContractError):
        with _pinned_acquisition_substrate(_ctx(tmp_path, _Managed(client))):
            pass

    assert built == []
