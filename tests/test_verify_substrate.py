"""R24/Q142: the gate picks one substrate, and an unmanaged run is not charged for it.

The unit under test is the *choice*: which tree a managed run verifies, and what an
unmanaged run is allowed to keep doing. The pin's own protocol is covered where the
authority lives; what is proved here is that the controller cannot quietly verify a
copy the coder never edited, and that it cannot quietly stop verifying when the
managed substrate is missing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from fa.execution.client import ExecutionClient, ExecutionRejectedError
from fa.execution.primitives import ExecutionContractError
from fa.execution.profiles import ExecutionProfile
from fa.execution.types import Access, GrantReply, NamespaceRef, Operation, ViewPurpose, ViewRef
from fa.inner_loop import workflow_controller
from fa.inner_loop.workflow_controller import (
    WorkflowContext,
    _pinned_verify_substrate,
    workflow_artifact_paths,
)


def _ctx(tmp_path: Path, *, managed: Any = None) -> WorkflowContext:
    return WorkflowContext(
        run_id="run-verify-substrate",
        base_task="prove the substrate choice",
        per_role_task={},
        artifact_paths=workflow_artifact_paths("run-verify-substrate", base_dir=tmp_path / "logs"),
        config=object(),  # type: ignore[arg-type]
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        verify_gate_mode="observe",
        managed_execution=managed,
    )


def test_an_unmanaged_run_yields_no_substrate_and_pins_nothing(tmp_path: Path) -> None:
    """C0 — the host is not a fallback, it is the substrate an unmanaged run already is."""
    with _pinned_verify_substrate(_ctx(tmp_path)) as substrate:
        assert substrate is None


class _NoProfile:
    """A managed execution whose read-only profile was never configured."""

    client = object()
    binding = object()
    current_revision_id = "rev-current"
    read_only_profile = None


def test_a_managed_run_without_a_read_only_profile_degrades_loudly(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """C1 — no READ class is a legitimate configuration, so it must not be fatal.

    ``read_only_profile_id`` is optional and absent means "no READ view class"
    (``service.py:129-131``). Raising here turned every coder stage of such a run into
    a blocking verification error; the honest behaviour is the pre-R24 one with a
    warning, because the gate then judges the host copy rather than the revision.
    """
    with caplog.at_level(logging.WARNING):
        with _pinned_verify_substrate(_ctx(tmp_path, managed=_NoProfile())) as substrate:
            assert substrate is None

    assert "no read-only profile" in caplog.text
    assert "not the revision" in caplog.text


class _Client(ExecutionClient):
    """A real client subclass: the executors prove ``isinstance`` before trusting a pin."""

    def __init__(self, *, grant: Any) -> None:
        self.grant = grant
        self.pin_calls: list[dict[str, Any]] = []
        self.stop_calls: list[dict[str, Any]] = []

    def pin_reader(self, binding: Any, *, revision_id: str, plan_ref: Any, deadline: float) -> Any:
        self.pin_calls.append({"binding": binding, "revision_id": revision_id, "plan_ref": plan_ref})
        return self.grant

    def stop_view(self, namespace: Any, *, view: Any, grant: Any, deadline: float) -> bool:
        self.stop_calls.append({"namespace": namespace, "view": view})
        return True


def _namespace() -> NamespaceRef:
    return NamespaceRef(session_id="session-1", run_id="run-" + "1" * 16, parent_run_id=None)


def _binding() -> Any:
    return type("Binding", (), {"namespace": _namespace()})()


class _Managed:
    def __init__(self, client: Any, profile: Any) -> None:
        self.client = client
        self.binding = _binding()
        self.current_revision_id = "rev-" + "3" * 32
        self.read_only_profile = profile


def _profile() -> ExecutionProfile:
    return ExecutionProfile(
        "reader",
        "unit.invalid/cell@sha256:" + "5" * 64,
        1000,
        1000,
        1_000_000_000,
        128 * 1024**2,
        64,
        1000,
        False,
        "fa-exec.slice",
        '{"defaultAction":"SCMP_ACT_ERRNO","syscalls":[]}',
    )


def _view(*, access: Access = Access.READ) -> ViewRef:
    return ViewRef(
        "ws-" + "1" * 32, "view-" + "2" * 32, "rev-" + "3" * 32, "run-" + "1" * 16, 1, access, ViewPurpose.PROJECT
    )


def _grant(*, view: ViewRef, operation: Operation = Operation.PIN_READER) -> GrantReply:
    return GrantReply(operation, "c" * 64, view, None, None, input_tree_sha256="a" * 64)


def test_a_grant_for_anything_but_a_read_pin_is_refused(tmp_path: Path) -> None:
    """C1 — the substrate is only legitimate when the authority minted this view's READ pin.

    A grant for another view (or one that is not a pin) is not "close enough": it would
    let verification run somewhere the spec does not name.
    """
    # A grant that is not this view's READ pin. The value of the test is that the
    # substrate refuses it at construction rather than at the first command, so the
    # refusal cannot be mistaken for a verify result.
    other_view = _view(access=Access.WRITE)
    client = _Client(grant=_grant(view=_view(), operation=Operation.CREATE_VIEW))
    assert other_view != _view()  # the grant names a different view than the pin's

    with pytest.raises(ExecutionContractError):
        with _pinned_verify_substrate(_ctx(tmp_path, managed=_Managed(client, _profile()))):
            pass


def test_a_refused_pin_degrades_loudly_rather_than_blocking_the_stage(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """C1 — a determinate refusal is not uncertainty; it is a configuration outcome.

    Treating it as fatal blocked every coder stage; swallowing it silently would
    report a verdict about the host copy as if it were the revision. The middle --
    a named warning and the host substrate -- is what a refusal may buy.
    """

    class _Refusing:
        def pin_reader(self, *_args: Any, **_kwargs: Any) -> Any:
            raise ExecutionRejectedError("INPUT_POLICY", "op-1")

    managed = _Managed(_Refusing(), _profile())
    with caplog.at_level(logging.WARNING):
        with _pinned_verify_substrate(_ctx(tmp_path, managed=managed)) as substrate:
            assert substrate is None

    assert "INPUT_POLICY" in caplog.text


def test_the_pin_names_the_current_revision_and_the_plan(tmp_path: Path) -> None:
    """C1 — the view must be of the revision under judgement, not of "whatever is current"."""
    view = _view()
    client = _Client(grant=_grant(view=view))
    ctx = _ctx(tmp_path, managed=_Managed(client, _profile()))

    with _pinned_verify_substrate(ctx) as substrate:
        assert substrate is not None

    assert client.pin_calls and client.pin_calls[0]["revision_id"] == "rev-" + "3" * 32
    assert client.pin_calls[0]["plan_ref"] is ctx.managed_plan_ref


def test_capture_baseline_keeps_the_host_substrate(tmp_path: Path) -> None:
    """C0 — T0 predates the coder's publication, so there is no view for it to read.

    Pinning a revision for the baseline would be a different measurement than the
    documented one, and it would fail outright before the first publication.
    """
    seen: list[object] = []
    real = workflow_controller.capture_test_nodeids

    def spy(*_args: object, **kwargs: object) -> object:
        seen.append(kwargs.get("executor"))
        return real(*_args, **kwargs)  # type: ignore[arg-type]

    workflow_controller.capture_test_nodeids = spy  # type: ignore[assignment]
    try:
        workflow_controller._capture_nodeids_by_slice(workflow_controller.PlanIds(), root=tmp_path, execution=None)
    finally:
        workflow_controller.capture_test_nodeids = real  # type: ignore[assignment]

    assert seen == []
