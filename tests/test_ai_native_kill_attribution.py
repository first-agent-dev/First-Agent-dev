"""C0 oracles for exact kill attribution over sealed nodeids (STEP9A item 3)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.acceptance_bundle import AcceptanceBundle, AcceptanceBundleError
from fa.inner_loop.kill_attribution import (
    ATTRIBUTION_VERDICTS,
    NODE_OUTCOMES,
    KillAttributionError,
    KillTargetBinding,
    NodeRun,
    attribute,
    bindings,
    oracle_argv,
    run_node_oracle,
)
from fa.inner_loop.slice_verification import CommandOutcome
from tests.test_ai_native_acceptance_collection import (
    _NODEID,
    _PLAN_BYTES,
    _PUBLISH,
    _SEALED_ROOT,
    FakeHost,
    junit_report,
    mint_sealed,
    sealed_tree,
)
from tests.test_ai_native_plan_v2 import granted_graph, plan_graph
from tests.test_ai_native_plan_v2 import granted_graph as admitted_graph

_REVISION = "rev-" + "0" * 32
_TARGET = "publication.publish_plan"
_OTHER_ENV = f"{_SEALED_ROOT}/tests/test_extra.py::test_extra"


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


def _binding(bundle: AcceptanceBundle, graph: Any = None) -> KillTargetBinding:
    (binding,) = bindings(bundle, graph or admitted_graph())
    return binding


def _run(outcome: str, *, detail: str = "") -> NodeRun:
    return NodeRun(outcome=outcome, command="python -m pytest ...", exit_code=0, detail=detail)


def _attributed(bundle: AcceptanceBundle, outcome: str, *, detail: str = "") -> Any:
    return attribute(_binding(bundle), baseline=_run("PASSED"), mutated=_run(outcome, detail=detail))


def _rule(callable_: Callable[[], object]) -> str:
    with pytest.raises(KillAttributionError) as refused:
        callable_()
    return refused.value.rule


# -- bindings ---------------------------------------------------------------


def test_a_target_is_bound_to_its_contract_test_nodeid_and_sealed_evidence(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    binding = _binding(bundle)

    assert binding.target_id == _TARGET
    assert binding.contract_id == "CT-1.1"
    assert binding.test_id == "TEST-1.1"
    assert binding.nodeid == _NODEID
    assert binding.seal_sha256 == bundle.seal_sha256
    assert binding.revision_id == _REVISION
    assert binding.closure_sha256 == bundle.closure.digest
    sealed = next(entry for entry in bundle.closure.files if entry.path == "tests/test_publish.py")
    assert binding.test_sha256 == sealed.sha256


def test_a_target_naming_an_unsealed_test_is_refused(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)
    graph = plan_graph(slice_body=_SLICE_UNSEALED_TARGET)

    assert _rule(lambda: bindings(bundle, graph)) == "kill-target-unsealed"


def test_binding_needs_a_bundle_and_a_graph(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)
    not_a_graph: Any = None

    assert _rule(lambda: bindings(bundle, not_a_graph)) == "kill-input-invalid"


def test_binding_needs_a_real_bundle_seal(tmp_path: Path) -> None:
    _, _ = _seal(tmp_path)
    not_a_bundle: Any = {"seal": 1}

    assert _rule(lambda: bindings(not_a_bundle, admitted_graph())) == "kill-input-invalid"


def test_a_plan_without_kill_targets_binds_nothing(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    assert bindings(bundle, plan_graph(slice_body=_SLICE_NO_TARGETS)) == ()


# -- the oracle command -----------------------------------------------------


def test_the_oracle_runs_exactly_one_nodeid_under_the_sealed_config(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    argv = oracle_argv(bundle, _binding(bundle), report="/tmp/oracle.xml")

    assert argv[3] == _NODEID
    assert argv[3:5] != (_PUBLISH,) and argv[4:6] == ("-c", f"{_SEALED_ROOT}/pytest.ini")
    assert argv[6:8] == ("--rootdir", _SEALED_ROOT)
    assert "-p" in argv and "no:cacheprovider" in argv


def test_the_oracle_needs_a_binding(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)
    not_a_binding: Any = {"target": 1}

    assert _rule(lambda: oracle_argv(bundle, not_a_binding, report="/tmp/x.xml")) == "kill-binding-invalid"


# -- one oracle run ---------------------------------------------------------


def _oracle(bundle: AcceptanceBundle, tmp_path: Path, report: bytes | None, **kwargs: Any) -> NodeRun:
    executor = FakeHost(report=report, **kwargs)
    return run_node_oracle(bundle, _binding(bundle), workspace=tmp_path, executor=executor)


def test_an_assertion_failure_on_the_mapped_nodeid_is_a_failed_run(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    run = _oracle(bundle, tmp_path, junit_report(("tests/test_publish.py::test_publish", "failure")))

    assert run.outcome == "FAILED"
    assert run.detail == ""
    assert run.command.startswith("python -m pytest")


def test_a_pass_on_the_mapped_nodeid_is_a_passed_run(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    assert _oracle(bundle, tmp_path, junit_report(("tests/test_publish.py::test_publish", "passed"))).outcome == (
        "PASSED"
    )


def test_a_skipped_row_is_not_a_kill(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    run = _oracle(bundle, tmp_path, junit_report(("tests/test_publish.py::test_publish", "skipped")))

    assert run.outcome == "SKIPPED"
    assert run.detail == "oracle-skipped"


def test_a_report_with_a_second_row_is_refused(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)
    report = junit_report(
        ("tests/test_publish.py::test_publish", "failure"), ("tests/test_extra.py::test_extra", "passed")
    )

    run = _oracle(bundle, tmp_path, report)

    assert run.outcome == "ERROR"
    assert run.detail == "oracle-report-not-exact"


def test_a_report_for_another_nodeid_is_refused(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    run = _oracle(bundle, tmp_path, junit_report(("tests/test_extra.py::test_extra", "failure")))

    assert run.outcome == "ERROR"
    assert run.detail == "oracle-report-not-exact"


def test_an_empty_report_never_proves_anything(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    run = _oracle(bundle, tmp_path, b'<testsuite tests="0" failures="0" errors="0" skipped="0"/>')

    assert run.outcome == "ERROR"
    assert run.detail == "oracle-report-not-exact"


def test_a_report_that_never_arrived_is_missing(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    run = _oracle(bundle, tmp_path, None)

    assert run.outcome == "MISSING"
    assert run.detail == "oracle-no-report"


def test_an_erroring_substrate_is_an_error(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    run = _oracle(bundle, tmp_path, None, outcome=CommandOutcome.ERROR, exit_code=None)

    assert run.outcome == "ERROR"


def test_a_drifted_acceptance_tree_never_runs_the_oracle(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)
    (tmp_path / _SEALED_ROOT / "tests" / "test_publish.py").write_text(
        "def test_publish():\n    assert False\n", encoding="utf-8"
    )
    executor = FakeHost(report=junit_report(("tests/test_publish.py::test_publish", "passed")))

    with pytest.raises(AcceptanceBundleError):
        run_node_oracle(bundle, _binding(bundle), workspace=tmp_path, executor=executor)
    assert executor.commands == []


@pytest.mark.parametrize("binding", [None, {"target": 1}])
def test_the_oracle_run_needs_a_binding(tmp_path: Path, binding: Any) -> None:
    bundle, _ = _seal(tmp_path)

    assert _rule(lambda: run_node_oracle(bundle, binding, workspace=tmp_path)) == "kill-binding-invalid"


# -- the verdict ------------------------------------------------------------


def test_the_verdict_vocabulary_is_closed() -> None:
    assert ATTRIBUTION_VERDICTS == {"PROVEN", "VACUOUS", "ERROR"}
    assert NODE_OUTCOMES == {"PASSED", "FAILED", "SKIPPED", "MISSING", "ERROR"}


def test_a_baseline_pass_and_a_mutation_failure_is_proven(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    attribution = _attributed(bundle, "FAILED")

    assert attribution.verdict == "PROVEN"
    assert attribution.detail == ""
    assert attribution.binding.target_id == _TARGET
    assert attribution.baseline.outcome == "PASSED"
    assert attribution.mutated.outcome == "FAILED"


def test_a_mutation_that_still_passes_is_vacuous(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    attribution = _attributed(bundle, "PASSED")

    assert attribution.verdict == "VACUOUS"
    assert "still passes" in attribution.detail


@pytest.mark.parametrize("baseline", ["FAILED", "SKIPPED", "MISSING", "ERROR"])
def test_a_baseline_that_did_not_pass_can_never_prove_a_kill(tmp_path: Path, baseline: str) -> None:
    bundle, _ = _seal(tmp_path)

    attribution = attribute(_binding(bundle), baseline=_run(baseline), mutated=_run("FAILED"))

    assert attribution.verdict == "ERROR"
    assert attribution.detail == f"baseline_{baseline.lower()}"


@pytest.mark.parametrize("mutated", ["SKIPPED", "MISSING", "ERROR"])
def test_a_mutation_run_that_was_not_an_assertion_failure_is_an_error(tmp_path: Path, mutated: str) -> None:
    bundle, _ = _seal(tmp_path)

    attribution = _attributed(bundle, mutated)

    assert attribution.verdict == "ERROR"
    assert attribution.detail == f"mutated_{mutated.lower()}"


@pytest.mark.parametrize(
    ("baseline", "mutated"),
    [({"outcome": "MAYBE"}, "FAILED"), ("PASSED", {"outcome": "MAYBE"}), (None, "FAILED")],
)
def test_a_run_with_an_unknown_outcome_cannot_be_attributed(tmp_path: Path, baseline: Any, mutated: Any) -> None:
    bundle, _ = _seal(tmp_path)
    unknown: Any = {"outcome": "MAYBE"}
    runs: dict[Any, Any] = {"PASSED": _run("PASSED"), "FAILED": _run("FAILED"), None: None, "MAYBE": unknown}
    base: Any = runs[baseline] if not isinstance(baseline, dict) else unknown
    final: Any = runs[mutated] if not isinstance(mutated, dict) else unknown

    assert _rule(lambda: attribute(_binding(bundle), baseline=base, mutated=final)) == "kill-run-invalid"


def test_two_targets_attribute_independently(tmp_path: Path) -> None:
    root = sealed_tree(tmp_path)
    graph = plan_graph(slice_body=_SLICE_TWO_TARGETS)
    bundle = mint_sealed(
        root,
        graph=graph,
        collected={_PUBLISH: [_NODEID], f"{_SEALED_ROOT}/tests/test_extra.py": [_OTHER_ENV]},
    )
    bound = bindings(bundle, graph)

    proven = attribute(bound[0], baseline=_run("PASSED"), mutated=_run("FAILED"))
    vacuous = attribute(bound[1], baseline=_run("PASSED"), mutated=_run("PASSED"))

    assert [item.target_id for item in bound] == ["publication.publish_plan", "publication.plan_immutable"]
    assert proven.verdict == "PROVEN"
    assert vacuous.verdict == "VACUOUS"


_SLICE_UNSEALED_TARGET = """## SLICE1: sealed acceptance
STEPS: outcome
CONTRACTS:
  CT-1.1 [FUNCTIONAL] INV: INV-1: publication requires a sealed selection
  CT-1.2 [CONSTRAINT] INV: INV-1: publication requires a sealed selection
ACCEPTANCE:
  TEST-ID: TEST-1.1 | CT: CT-1.1 | SELECTOR: worklogs/demo/acceptance/tests/test_publish.py::test_publish
  TEST-ID: TEST-1.2 | CT: CT-1.2 | SELECTOR: worklogs/demo/acceptance/tests/test_extra.py::test_extra
KILL-TARGETS:
  TARGET-ID: publication.publish_plan | CT: CT-1.2 | TEST-ID: TEST-1.2
STEP-EXIT-CHECKS:
"""

_SLICE_TWO_TARGETS = """## SLICE1: sealed acceptance
STEPS: outcome
CONTRACTS:
  CT-1.1 [FUNCTIONAL] INV: INV-1: publication requires a sealed selection
  CT-1.2 [CONSTRAINT] INV: INV-1: publication requires a sealed selection
ACCEPTANCE:
  TEST-ID: TEST-1.1 | CT: CT-1.1 | SELECTOR: worklogs/demo/acceptance/tests/test_publish.py::test_publish
  TEST-ID: TEST-1.2 | CT: CT-1.2 | SELECTOR: worklogs/demo/acceptance/tests/test_extra.py::test_extra
KILL-TARGETS:
  TARGET-ID: publication.publish_plan | CT: CT-1.1 | TEST-ID: TEST-1.1
  TARGET-ID: publication.plan_immutable | CT: CT-1.2 | TEST-ID: TEST-1.2
STEP-EXIT-CHECKS:
"""

_SLICE_NO_TARGETS = """## SLICE1: sealed acceptance
STEPS: outcome
CONTRACTS:
  CT-1.1 [FUNCTIONAL] INV: INV-1: publication requires a sealed selection
ACCEPTANCE:
  TEST-ID: TEST-1.1 | CT: CT-1.1 | SELECTOR: worklogs/demo/acceptance/tests/test_publish.py::test_publish
KILL-TARGETS:
STEP-EXIT-CHECKS:
"""
