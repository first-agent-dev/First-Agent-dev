"""C0 oracles for the TEST-DEFECT lifecycle (STEP9A item 2)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.acceptance_bundle import AcceptanceBundle, load_seal
from fa.inner_loop.acceptance_defect import (
    DefectDecision,
    DefectError,
    DefectReport,
    affected_scope,
    correct,
    report_defect,
    seal_path,
    uphold,
    write_revision_seal,
)
from tests.test_ai_native_acceptance_collection import (
    _NODEID,
    _PLAN_BYTES,
    _PUBLISH,
    _SEALED_ROOT,
    mint_sealed,
    sealed_tree,
)
from tests.test_ai_native_plan_v2 import plan_graph
from tests.test_ai_native_plan_v2 import plan_graph as admitted_graph

_REVISION = "rev-" + "0" * 32
_NEXT_REVISION = "rev-" + "1" * 32
_TEST = "TEST-1.1"
_CT = "CT-1.1"
_INV = "INV-1"


def _seal(tmp_path: Path, **overrides: Any) -> tuple[AcceptanceBundle, Path]:
    root = sealed_tree(tmp_path)
    arguments: dict[str, Any] = {
        "graph": admitted_graph(),
        "plan_bytes": _PLAN_BYTES,
        "revision_id": _REVISION,
        "sealed_root": _SEALED_ROOT,
        "collected": {_PUBLISH: [_NODEID]},
    }
    arguments.update(overrides)
    return mint_sealed(root, **arguments), tmp_path


def _report(bundle: AcceptanceBundle, graph: Any = None, **overrides: Any) -> DefectReport:
    arguments: dict[str, Any] = {
        "test_id": _TEST,
        "nodeid": bundle.nodeids()[_TEST],
        "assertion": "assert publish() == 'published' failed with 'silent'",
        "invariant_id": _INV,
    }
    arguments.update(overrides)
    return report_defect(bundle, graph or admitted_graph(), **arguments)


def _rule(callable_: Callable[[], object]) -> str:
    with pytest.raises(DefectError) as refused:
        callable_()
    return refused.value.rule


def _corrected_tree(tmp_path: Path) -> Path:
    """The same closure with the reported test's expectation corrected."""
    root = tmp_path / _SEALED_ROOT
    (root / "tests" / "test_publish.py").write_text(
        "def test_publish():\n    assert publish() == 'published!'\n", encoding="utf-8"
    )
    return root


# -- the coder's report -----------------------------------------------------


def test_a_report_is_pinned_to_the_seal_revision_nodeid_and_invariant(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    report = _report(bundle)

    assert report.seal_sha256 == bundle.seal_sha256
    assert report.revision_id == _REVISION
    assert report.test_id == _TEST
    assert report.nodeid == _NODEID
    assert report.invariant_id == _INV
    assert report.assertion.startswith("assert publish()")


def test_a_test_the_plan_never_declared_cannot_be_reported(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    assert _rule(lambda: _report(bundle, test_id="TEST-9.9", nodeid=f"{_PUBLISH}::test_other")) == (
        "defect-unknown-test"
    )


def test_a_test_the_seal_never_selected_cannot_be_reported(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)
    wider = plan_graph(slice_body=_SLICE_TWO_TESTS)

    assert (
        _rule(
            lambda: _report(
                bundle, graph=wider, test_id="TEST-1.2", nodeid=f"{_SEALED_ROOT}/tests/test_extra.py::test_extra"
            )
        )
        == "defect-test-not-sealed"
    )


def test_a_nodeid_that_is_not_the_sealed_one_cannot_be_reported(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    assert _rule(lambda: _report(bundle, nodeid=f"{_PUBLISH}::test_publish[x]")) == "defect-nodeid-mismatch"


def test_an_invariant_that_does_not_own_the_contract_cannot_be_reported(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    assert _rule(lambda: _report(bundle, invariant_id="INV-2")) == "defect-invariant-mismatch"


@pytest.mark.parametrize("assertion", ["", "   ", "x" * 2049, "assert\x00", None, 7])
def test_a_report_carries_a_bounded_factual_claim(tmp_path: Path, assertion: Any) -> None:
    bundle, _ = _seal(tmp_path)

    assert _rule(lambda: _report(bundle, assertion=assertion)) == "defect-text-invalid"


@pytest.mark.parametrize("bundle", [None, "seal"])
def test_reporting_needs_a_bundle_and_a_graph(tmp_path: Path, bundle: Any) -> None:
    sealed, _ = _seal(tmp_path)

    with pytest.raises(DefectError):
        report_defect(bundle, admitted_graph(), test_id=_TEST, nodeid=_NODEID, assertion="a", invariant_id=_INV)
    no_graph: Any = None
    with pytest.raises(DefectError):
        report_defect(sealed, no_graph, test_id=_TEST, nodeid=_NODEID, assertion="a", invariant_id=_INV)


# -- upheld -----------------------------------------------------------------


def test_upholding_keeps_the_bytes_and_re_opens_nothing(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    decision = uphold(_report(bundle), rationale="the assertion is the required behaviour")

    assert isinstance(decision, DefectDecision)
    assert decision.kind == "UPHELD"
    assert decision.replacement is None
    assert decision.affected_tests == ()
    assert decision.affected_kill_targets == ()
    assert decision.report.seal_sha256 == bundle.seal_sha256


@pytest.mark.parametrize("rationale", ["", " ", "x" * 2049, None])
def test_an_upheld_decision_still_needs_a_reason(tmp_path: Path, rationale: Any) -> None:
    bundle, _ = _seal(tmp_path)

    assert _rule(lambda: uphold(_report(bundle), rationale=rationale)) == "decision-rationale-invalid"


@pytest.mark.parametrize("call", ["uphold", "correct"])
def test_a_decision_needs_a_real_report(tmp_path: Path, call: str) -> None:
    bundle, workspace = _seal(tmp_path)
    report = _report(bundle)
    not_a_report: Any = {"seal": 1}

    if call == "uphold":
        assert _rule(lambda: uphold(not_a_report, rationale="r")) == "decision-report-invalid"
        return
    assert (
        _rule(
            lambda: correct(
                not_a_report,
                rationale="r",
                bundle_before=bundle,
                graph=admitted_graph(),
                plan_bytes=_PLAN_BYTES,
                revision_id=_NEXT_REVISION,
                acceptance_root=workspace / _SEALED_ROOT,
                collected={_PUBLISH: [_NODEID]},
            )
        )
        == "decision-report-invalid"
    )
    assert report.test_id == _TEST


# -- corrected --------------------------------------------------------------


def _correct(workspace: Path, bundle: AcceptanceBundle, report: DefectReport, **overrides: Any) -> DefectDecision:
    arguments: dict[str, Any] = {
        "rationale": "the expectation encoded the wrong output",
        "bundle_before": bundle,
        "graph": admitted_graph(),
        "plan_bytes": _PLAN_BYTES,
        "revision_id": _NEXT_REVISION,
        "collected": {_PUBLISH: [_NODEID]},
    }
    if "acceptance_root" not in overrides:
        arguments["acceptance_root"] = _corrected_tree(workspace)
    arguments.update(overrides)
    return correct(report, **arguments)


def test_a_correction_is_a_new_seal_that_supersedes_the_reported_one(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    report = _report(bundle)

    decision = _correct(workspace, bundle, report)

    replacement = decision.replacement
    assert replacement is not None
    assert decision.kind == "CORRECTED"
    assert replacement.supersedes_sha256 == bundle.seal_sha256
    assert replacement.seal_sha256 != bundle.seal_sha256
    assert replacement.revision_id == _NEXT_REVISION
    assert replacement.closure.digest != bundle.closure.digest
    assert replacement.plan_sha256 == bundle.plan_sha256
    assert decision.affected_tests == (_TEST,)
    assert decision.affected_kill_targets == ("publication.publish_plan",)


def test_a_correction_that_changes_the_plan_is_replan_work(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)

    assert _rule(lambda: _correct(workspace, bundle, _report(bundle), plan_bytes=_PLAN_BYTES + b"\n")) == (
        "defect-requires-replan"
    )


def test_a_correction_must_seal_a_different_revision(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)

    assert _rule(lambda: _correct(workspace, bundle, _report(bundle), revision_id=_REVISION)) == (
        "defect-revision-unchanged"
    )


def test_re_sealing_identical_bytes_is_not_a_correction(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)

    assert (
        _rule(lambda: _correct(workspace, bundle, _report(bundle), acceptance_root=workspace / _SEALED_ROOT))
        == "defect-no-change"
    )


def test_a_report_against_another_seal_cannot_be_corrected(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    other, _ = _seal(tmp_path / "second", revision_id=_NEXT_REVISION)
    stale = _report(other)

    assert other.seal_sha256 != bundle.seal_sha256

    assert _rule(lambda: _correct(workspace, bundle, stale)) == "defect-seal-superseded"


def test_the_old_revision_stays_readable_after_a_correction(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    decision = _correct(workspace, bundle, _report(bundle))
    replacement = decision.replacement
    assert replacement is not None

    old_path = write_revision_seal(bundle, workspace)
    new_path = write_revision_seal(replacement, workspace)

    assert old_path != new_path
    assert load_seal(old_path.read_bytes()) == bundle
    assert load_seal(new_path.read_bytes()) == replacement
    assert load_seal(new_path.read_bytes()).supersedes_sha256 == load_seal(old_path.read_bytes()).seal_sha256


# -- retention and addressing ----------------------------------------------


def test_a_seal_is_addressed_by_its_own_digest(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    assert seal_path(bundle) == f"worklogs/demo/seals/{bundle.seal_sha256}.json"


@pytest.mark.parametrize("bundle", [None, "seal", 7])
def test_seal_addressing_needs_a_bundle(bundle: Any) -> None:
    assert _rule(lambda: seal_path(bundle)) == "defect-seal-invalid"


def test_an_existing_revision_seal_is_never_replaced(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    path = write_revision_seal(bundle, workspace)

    assert _rule(lambda: write_revision_seal(bundle, workspace)) == "defect-seal-exists"
    assert load_seal(path.read_bytes()) == bundle


@pytest.mark.parametrize("worklogs", [None, "worklogs", 3])
def test_a_revision_seal_needs_a_directory(tmp_path: Path, worklogs: Any) -> None:
    bundle, _ = _seal(tmp_path)

    assert _rule(lambda: write_revision_seal(bundle, worklogs)) == "defect-seal-path-invalid"


def test_a_written_revision_seal_is_canonical_json(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)

    payload = json.loads(write_revision_seal(bundle, workspace).read_text(encoding="utf-8"))

    assert payload["seal_sha256"] == bundle.seal_sha256
    assert payload["kind"] == "ACCEPTANCE-BUNDLE"
    assert payload["supersedes_sha256"] is None


# -- what a correction obliges ---------------------------------------------


def test_every_test_of_the_contract_is_affected(tmp_path: Path) -> None:
    root = sealed_tree(tmp_path)
    wider = plan_graph(slice_body=_SLICE_TWO_TESTS)
    bundle = mint_sealed(
        root,
        graph=wider,
        collected={
            _PUBLISH: [_NODEID],
            f"{_SEALED_ROOT}/tests/test_extra.py": [f"{_SEALED_ROOT}/tests/test_extra.py::test_extra"],
        },
    )

    tests, targets = affected_scope(wider, "TEST-1.1")

    assert tests == ("TEST-1.1", "TEST-1.2")
    assert targets == ("publication.publish_plan",)
    assert bundle.nodeids()["TEST-1.2"].endswith("::test_extra")


def test_an_scope_question_about_an_unknown_test_is_refused(tmp_path: Path) -> None:
    assert _rule(lambda: affected_scope(admitted_graph(), "TEST-9.9")) == "defect-unknown-test"


_SLICE_TWO_TESTS = """## SLICE1: sealed acceptance
STEPS: outcome
CONTRACTS:
  CT-1.1 [FUNCTIONAL] INV: INV-1: publication requires a sealed selection
ACCEPTANCE:
  TEST-ID: TEST-1.1 | CT: CT-1.1 | SELECTOR: worklogs/demo/acceptance/tests/test_publish.py::test_publish
  TEST-ID: TEST-1.2 | CT: CT-1.1 | SELECTOR: worklogs/demo/acceptance/tests/test_extra.py::test_extra
KILL-TARGETS:
  TARGET-ID: publication.publish_plan | CT: CT-1.1 | TEST-ID: TEST-1.2
STEP-EXIT-CHECKS:
"""


def test_a_revision_seal_keeps_the_plan_the_gates_were_written_against(tmp_path: Path) -> None:
    bundle, workspace = _seal(tmp_path)
    decision = _correct(workspace, bundle, _report(bundle))
    replacement = decision.replacement
    assert replacement is not None

    written = json.loads(write_revision_seal(replacement, workspace).read_text(encoding="utf-8"))

    assert written["plan_sha256"] == bundle.plan_sha256
    assert written["sealed_root"] == _SEALED_ROOT
