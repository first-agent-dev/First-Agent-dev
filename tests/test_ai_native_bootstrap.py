"""V2 bootstrap: validate the pair before the irreversible install (SLICE2).

The new-project route is where a project comes into existence, so the order of
operations is the contract: render, validate, install, read back, seal. A body
that does not parse must be refused while nothing exists yet, because the
recovery for an installed-but-refused bootstrap is forward recovery, not undo.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from fa.execution.publication import render_bundle
from fa.inner_loop import workflow_controller
from fa.inner_loop.managed_acquisition import BootstrapNewProjectChoice
from fa.inner_loop.plan_admission import PLAN_V2, snapshot_from_bytes

_ROADMAP_BODY = (
    "Plan-Format: AI-NATIVE-PLAN-V2\n\n"
    "## Intent\n\nShip the demo slice.\n\n"
    "## Out of scope\n\nEverything outside SLICE1.\n"
)

_INCREMENT_BODY = (
    "Plan-Format: AI-NATIVE-PLAN-V2\n\n"
    "## INVARIANTS\n"
    "### INV-1\n"
    "KIND: HARD\n"
    "TEXT: publication requires a sealed selection.\n"
    "EVIDENCE: TEST_REQUIRED\n\n"
    "## SLICE1: Foundation\n"
    "STEPS: prescriptive\n"
    "CONTRACTS:\n"
    "  CT-1.1 [FUNCTIONAL] INV: INV-1: publication requires a sealed selection\n"
    "ACCEPTANCE:\n"
    "  TEST-ID: TEST-1.1 | CT: CT-1.1 | SELECTOR: "
    "worklogs/demo-project/acceptance/tests/test_publish.py::test_publish\n"
    "STEP-EXIT-CHECKS:\n"
    "  CHECK-ID: CHECK-1 | STEP: STEP1 | TEST-ID[]: TEST-1.1\n"
    "- [ ] STEP1: publish through the sealed authority. EXIT-CHECK: CHECK-1\n"
)


class _AuthorityMustNotBeTouched:
    """Any authority call before validation is the defect this file guards."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"authority reached before validation: {name}")


def _v2_context() -> SimpleNamespace:
    return SimpleNamespace(
        managed_execution=SimpleNamespace(
            current_revision_id="rev-1",
            client=_AuthorityMustNotBeTouched(),
        ),
        plan_format=PLAN_V2,
        deadline_mono=None,
        run_id="run-bootstrap-v2",
    )


def _choice(increment_body: str) -> BootstrapNewProjectChoice:
    return BootstrapNewProjectChoice(
        project_slug="demo-project",
        increment_slug="foundation",
        roadmap_body=_ROADMAP_BODY,
        increment_body=increment_body,
    )


def test_v2_bootstrap_pair_is_validated_before_the_irreversible_install() -> None:
    """An unparseable V2 body is refused while nothing exists — no prepare, no install."""
    ctx, refusal, detail = workflow_controller._install_bootstrap_project_with_detail(
        _v2_context(),  # type: ignore[arg-type]
        _choice(_INCREMENT_BODY.replace("## INVARIANTS", "## NOT_INVARIANTS")),
    )

    assert refusal is not None
    assert refusal.rule == "bootstrap-invalid-body"
    assert detail is not None
    assert (detail.validator, detail.rule, detail.severity) == ("bootstrap", "invalid-body", "FAIL")
    assert detail.operation_id is None  # nothing was installed, so there is no operation
    assert ctx.run_id == "run-bootstrap-v2"  # unchanged: nothing was bound


def test_v1_route_keeps_its_existing_authority_order() -> None:
    """The pre-install V2 check is route-scoped: a V1 bootstrap still reaches prepare."""
    legacy = _v2_context()
    legacy.plan_format = "PLAN-V1"

    with pytest.raises(AssertionError, match="authority reached before validation"):
        workflow_controller._install_bootstrap_project_with_detail(
            legacy,  # type: ignore[arg-type]
            _choice("## SLICE1: Foundation\nCONTRACTS:\n  CT1 [CONSTRAINT]: holds.\nTESTS: tests/x.py\n"),
        )


def test_rendered_v2_bundle_is_the_pair_admission_parses() -> None:
    """The controller validates the bodies; this proves the *rendered* files agree."""
    files = render_bundle(
        "demo-project",
        "foundation",
        _ROADMAP_BODY,
        _INCREMENT_BODY,
        created="2026-11-20",
    )
    roadmap_path = "worklogs/demo-project/roadmap.md"
    increment_path = "worklogs/demo-project/increments/increment-01-foundation.md"

    assert b"Plan-Format: AI-NATIVE-PLAN-V2" in files[roadmap_path]
    assert b"Plan-Format: AI-NATIVE-PLAN-V2" in files[increment_path]

    snapshot = snapshot_from_bytes(
        increment_path,
        files[increment_path],
        source_kind="BOOTSTRAP",
        format=PLAN_V2,
        roadmap=files[roadmap_path].decode("utf-8"),
    )

    assert snapshot.graph is not None
    validation = workflow_controller._validate_plan_admission(snapshot)
    assert validation.outcome == "PASS", validation.diagnostics
    assert snapshot.graph.contracts()["CT-1.1"].inv == "INV-1"
