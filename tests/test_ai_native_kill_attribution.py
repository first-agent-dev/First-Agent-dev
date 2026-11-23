"""C0 oracles for exact kill attribution over sealed nodeids (STEP9A item 3)."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest

from fa.inner_loop.acceptance_bundle import AcceptanceBundle, AcceptanceBundleError, load_seal, seal_bytes
from fa.inner_loop.kill_attribution import (
    ATTRIBUTION_VERDICTS,
    NODE_OUTCOMES,
    KillAttribution,
    KillAttributionError,
    KillTargetBinding,
    NodeOutcome,
    NodeRun,
    attribute,
    bindings,
    oracle_argv,
    run_node_oracle,
)
from fa.inner_loop.slice_verification import (
    JUNIT_BLOCK_END,
    JUNIT_BLOCK_START,
    KILL_CHECK_VERDICTS,
    CommandOutcome,
    CommandResult,
    SliceVerdict,
    parse_inband_kill_node_outcomes,
    parse_kill_node_outcomes,
)
from fa.inner_loop.verification_attempt import MUTATION_VERDICTS
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
from tests.test_ai_native_plan_v2 import granted_graph as admitted_graph
from tests.test_ai_native_plan_v2 import plan_document, plan_graph

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
    (binding,) = bindings(bundle, graph or admitted_graph(), plan_bytes=_PLAN_BYTES)
    return binding


def _run(outcome: NodeOutcome, *, detail: str = "") -> NodeRun:
    return NodeRun(outcome=outcome, command="python -m pytest ...", exit_code=0, detail=detail)


def _attributed(bundle: AcceptanceBundle, outcome: NodeOutcome, *, detail: str = "") -> Any:
    return attribute(_binding(bundle), baseline=_run(NodeOutcome.PASSED), mutated=_run(outcome, detail=detail))


def _seal_rule(callable_: Callable[[], object]) -> str:
    """The seal's own closed rule: drift is refused by the seal, never re-labelled."""
    with pytest.raises(AcceptanceBundleError) as refused:
        callable_()
    return refused.value.rule


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


def test_a_graph_from_a_different_plan_is_refused(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)
    graph = plan_graph(slice_body=_SLICE_UNSEALED_TARGET)

    assert _rule(lambda: bindings(bundle, graph, plan_bytes=_PLAN_BYTES)) == "kill-plan-mismatch"


def test_a_target_naming_an_unsealed_test_is_refused(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)
    graph = plan_graph(slice_body=_SLICE_UNSEALED_TARGET)
    plan_bytes = plan_document(slice_body=_SLICE_UNSEALED_TARGET).encode()
    substituted = replace(bundle, plan_sha256=hashlib.sha256(plan_bytes).hexdigest())
    internally_consistent = load_seal(seal_bytes(substituted))
    assert _rule(lambda: bindings(internally_consistent, graph, plan_bytes=plan_bytes)) == "kill-target-unsealed"


def test_binding_needs_a_bundle_and_a_graph(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)
    not_a_graph: Any = None

    assert _rule(lambda: bindings(bundle, not_a_graph, plan_bytes=_PLAN_BYTES)) == "kill-input-invalid"


def test_binding_needs_a_real_bundle_seal(tmp_path: Path) -> None:
    _, _ = _seal(tmp_path)
    not_a_bundle: Any = {"seal": 1}

    assert _rule(lambda: bindings(not_a_bundle, admitted_graph(), plan_bytes=_PLAN_BYTES)) == "kill-input-invalid"


def test_a_plan_without_kill_targets_binds_nothing(tmp_path: Path) -> None:
    graph = plan_graph(slice_body=_SLICE_NO_TARGETS)
    plan_bytes = plan_document(slice_body=_SLICE_NO_TARGETS).encode()
    bundle, _ = _seal(tmp_path, graph=graph, plan_bytes=plan_bytes)

    assert bindings(bundle, graph, plan_bytes=plan_bytes) == ()


@pytest.mark.parametrize("field", ["ct", "selector", "target", "bytes"])
def test_binding_rejects_a_foreign_graph_or_plan(tmp_path: Path, field: str) -> None:
    bundle, _ = _seal(tmp_path)
    graph = admitted_graph()
    part = graph.slices[0]
    plan_bytes = _PLAN_BYTES
    if field == "ct":
        part = replace(part, kill_targets=(replace(part.kill_targets[0], ct="CT-1.2"),))
    elif field == "selector":
        part = replace(part, acceptance=(replace(part.acceptance[0], selector=_OTHER_ENV),))
    elif field == "target":
        part = replace(part, kill_targets=(replace(part.kill_targets[0], target_id="foreign.target"),))
    else:
        plan_bytes = _PLAN_BYTES + b"\n"
    graph = replace(graph, slices=(part,))
    assert _rule(lambda: bindings(bundle, graph, plan_bytes=plan_bytes)) == "kill-plan-mismatch"


@pytest.mark.parametrize(
    "field",
    ["target_id", "contract_id", "test_id", "nodeid", "test_sha256", "seal_sha256", "revision_id", "closure_sha256"],
)
def test_oracle_rejects_foreign_binding_before_running(tmp_path: Path, field: str) -> None:
    bundle, _ = _seal(tmp_path)
    binding = _binding(bundle)
    altered = replace(binding, **{field: "foreign"})
    executor = FakeHost(report=junit_report(("tests/test_publish.py::test_publish", "passed")))
    assert (
        _rule(
            lambda: run_node_oracle(
                bundle, altered, graph=admitted_graph(), plan_bytes=_PLAN_BYTES, workspace=tmp_path, executor=executor
            )
        )
        == "kill-binding-mismatch"
    )
    assert executor.commands == []


@pytest.mark.parametrize("field", ["ct_id", "selector", "nodeid"])
def test_binding_refuses_seal_rows_that_do_not_match_the_admitted_graph(tmp_path: Path, field: str) -> None:
    bundle, _ = _seal(tmp_path)
    row = bundle.selectors[0]
    value = "CT-9.9" if field == "ct_id" else _OTHER_ENV
    altered = replace(bundle, selectors=(replace(row, **{field: value}),))
    internally_consistent = load_seal(seal_bytes(altered))
    assert _rule(lambda: bindings(internally_consistent, admitted_graph(), plan_bytes=_PLAN_BYTES)) == (
        "kill-target-mismatch"
    )


def test_a_single_parameterized_nodeid_remains_valid(tmp_path: Path) -> None:
    nodeid = _NODEID + "[one]"
    bundle, _ = _seal(tmp_path, collected={_PUBLISH: [nodeid]})
    assert _binding(bundle).nodeid == nodeid


def test_oracle_argv_rejects_a_stale_binding(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)
    binding = replace(_binding(bundle), revision_id="rev-" + "1" * 32)
    assert _rule(lambda: oracle_argv(bundle, binding, report="oracle.xml")) == "kill-binding-mismatch"


def test_a_changed_in_memory_seal_is_not_resigned(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)
    changed = replace(bundle, revision_id="rev-" + "1" * 32)
    assert _rule(lambda: bindings(changed, admitted_graph(), plan_bytes=_PLAN_BYTES)) == "kill-seal-invalid"


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


class _OracleHost(FakeHost):
    """Carry harness-issued run identity into otherwise explicit synthetic reports."""

    def run_verify_command(self, command: str, *, cwd: Path, timeout_s: float, env: dict[str, str]) -> Any:
        if self.report is not None:
            root = ElementTree.fromstring(self.report)
            for case in root.iter("testcase"):
                props = case.find("properties")
                assert props is not None
                ElementTree.SubElement(props, "property", name="fa_pytest_run_id", value=env["FA_VERIFY_JUNIT_RUN_ID"])
                kind = "assertion" if case.find("failure") is not None else "passed"
                ElementTree.SubElement(props, "property", name="fa_pytest_call_outcome", value=kind)
            self.report = ElementTree.tostring(root)
        return super().run_verify_command(command, cwd=cwd, timeout_s=timeout_s, env=env)


def _oracle(bundle: AcceptanceBundle, tmp_path: Path, report: bytes | None, **kwargs: Any) -> NodeRun:
    if report is not None and b"<failure" in report and not kwargs:
        kwargs = {"outcome": CommandOutcome.FAIL, "exit_code": 1}
    executor = _OracleHost(report=report, **kwargs)
    return run_node_oracle(
        bundle, _binding(bundle), graph=admitted_graph(), plan_bytes=_PLAN_BYTES, workspace=tmp_path, executor=executor
    )


def test_an_assertion_failure_on_the_mapped_nodeid_is_a_failed_run(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    run = _oracle(bundle, tmp_path, junit_report(("tests/test_publish.py::test_publish", "failure")))

    assert run.outcome == "FAILED"
    assert run.detail == ""
    assert run.command.startswith("python -m pytest")


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("assert False", NodeOutcome.FAILED),
        ("raise ValueError('bad')", NodeOutcome.ERROR),
        ("pass", NodeOutcome.PASSED),
    ],
)
def test_oracle_uses_real_pytest_call_phase_evidence(tmp_path: Path, body: str, expected: NodeOutcome) -> None:
    root = sealed_tree(tmp_path)
    (root / "tests" / "test_publish.py").write_text(f"def test_publish():\n    {body}\n", encoding="utf-8")
    bundle = mint_sealed(root)

    class LocalSubprocess:
        def run_verify_command(
            self, command: str, *, cwd: Path, timeout_s: float, env: dict[str, str]
        ) -> CommandResult:
            env = dict(env)
            env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}"
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
            completed = subprocess.run(
                command, shell=True, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout_s, check=False
            )
            return CommandResult(
                command=command,
                outcome=CommandOutcome.PASS if completed.returncode == 0 else CommandOutcome.FAIL,
                exit_code=completed.returncode,
                stdout_tail=completed.stdout[-4000:],
                stderr_tail=completed.stderr[-4000:],
                duration_s=0.0,
            )

    run = run_node_oracle(
        bundle,
        _binding(bundle),
        graph=admitted_graph(),
        plan_bytes=_PLAN_BYTES,
        workspace=tmp_path,
        executor=LocalSubprocess(),
    )
    assert run.outcome is expected


def test_a_failure_exit_that_contradicts_the_report_is_an_error(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)
    run = _oracle(
        bundle,
        tmp_path,
        junit_report(("tests/test_publish.py::test_publish", "failure")),
        outcome=CommandOutcome.PASS,
        exit_code=0,
    )
    assert run.outcome is NodeOutcome.ERROR
    assert run.detail == "oracle-status-mismatch"


@pytest.mark.parametrize("property_value", ["other", "", "assertion_duplicate", "missing", "wrong_nonce"])
def test_kill_parser_refuses_unproven_assertion_or_invocation(property_value: str) -> None:
    raw = junit_report(("tests/test_publish.py::test_publish", "failure"))
    root = ElementTree.fromstring(raw)
    props = root.find(".//testcase/properties")
    assert props is not None
    ElementTree.SubElement(
        props, "property", name="fa_pytest_run_id", value="bad" if property_value == "wrong_nonce" else "run"
    )
    if property_value != "missing":
        value = "assertion" if property_value in {"wrong_nonce", "assertion_duplicate"} else property_value
        ElementTree.SubElement(props, "property", name="fa_pytest_call_outcome", value=value)
    if property_value == "assertion_duplicate":
        ElementTree.SubElement(props, "property", name="fa_pytest_call_outcome", value="assertion")
    outcomes, _ = parse_kill_node_outcomes(ElementTree.tostring(root), run_id="run")
    assert outcomes is None


def test_inband_kill_report_requires_one_complete_bound_block() -> None:
    raw = junit_report(("tests/test_publish.py::test_publish", "failure"))
    root = ElementTree.fromstring(raw)
    props = root.find(".//testcase/properties")
    assert props is not None
    ElementTree.SubElement(props, "property", name="fa_pytest_run_id", value="run")
    ElementTree.SubElement(props, "property", name="fa_pytest_call_outcome", value="assertion")
    block = f"{JUNIT_BLOCK_START}\n{ElementTree.tostring(root, encoding='unicode')}\n{JUNIT_BLOCK_END}"
    parsed, _ = parse_inband_kill_node_outcomes(block, run_id="run")
    assert parsed == {"tests/test_publish.py::test_publish": "failed"}
    for unusable in (block + block, block.replace(JUNIT_BLOCK_END, ""), block[:-12]):
        parsed, _ = parse_inband_kill_node_outcomes(unusable, run_id="run")
        assert parsed is None
    stale, _ = parse_inband_kill_node_outcomes(block, run_id="other")
    assert stale is None


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("assertion", "failed"),
        ("pass", "passed"),
        ("other", None),
        ("setup", None),
        ("teardown", None),
        ("skip", "skipped"),
    ],
)
def test_real_pytest_plugin_and_kill_parser_distinguish_phases(tmp_path: Path, case: str, expected: str | None) -> None:
    source = {
        "assertion": "def test_case():\n    assert False\n",
        "pass": "def test_case():\n    pass\n",
        "other": "def test_case():\n    raise ValueError('not an assertion')\n",
        "setup": (
            "import pytest\n@pytest.fixture(autouse=True)\ndef gate():\n"
            "    raise AssertionError('setup')\ndef test_case():\n    pass\n"
        ),
        "teardown": (
            "import pytest\n@pytest.fixture(autouse=True)\ndef gate():\n    yield\n"
            "    raise AssertionError('teardown')\ndef test_case():\n    pass\n"
        ),
        "skip": "import pytest\ndef test_case():\n    pytest.skip('not executed')\n",
    }[case]
    (tmp_path / "test_case.py").write_text(source, encoding="utf-8")
    report = tmp_path / "out.xml"
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", FA_VERIFY_JUNIT_RUN_ID="actual-run")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "fa.inner_loop.junit_nodeid_plugin",
            "test_case.py",
            "--junitxml=out.xml",
            "-q",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == (0 if case in {"pass", "skip"} else 1), completed.stdout + completed.stderr
    outcomes, detail = parse_kill_node_outcomes(report.read_bytes(), run_id="actual-run")
    if expected is None:
        assert outcomes is None, detail
    else:
        assert outcomes == {"test_case.py::test_case": expected}
    stale, _ = parse_kill_node_outcomes(report.read_bytes(), run_id="other-run")
    assert stale is None


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

    assert (
        _seal_rule(
            lambda: run_node_oracle(
                bundle,
                _binding(bundle),
                graph=admitted_graph(),
                plan_bytes=_PLAN_BYTES,
                workspace=tmp_path,
                executor=executor,
            )
        )
        == "seal-byte-drift"
    )
    assert executor.commands == [], "a verdict about drifted bytes would be a verdict about nothing"


@pytest.mark.parametrize("binding", [None, {"target": 1}])
def test_the_oracle_run_needs_a_binding(tmp_path: Path, binding: Any) -> None:
    bundle, _ = _seal(tmp_path)

    assert (
        _rule(
            lambda: run_node_oracle(bundle, binding, graph=admitted_graph(), plan_bytes=_PLAN_BYTES, workspace=tmp_path)
        )
        == "kill-binding-invalid"
    )


# -- the verdict ------------------------------------------------------------


def test_the_verdict_vocabulary_is_closed() -> None:
    """Q-V2-SLICE3-3: a verdict is ``SliceVerdict``'s own member, not a second spelling."""
    assert ATTRIBUTION_VERDICTS == {SliceVerdict.PROVEN, SliceVerdict.VACUOUS, SliceVerdict.ERROR}
    assert {verdict.value for verdict in ATTRIBUTION_VERDICTS} <= {member.value for member in KILL_CHECK_VERDICTS}
    assert NODE_OUTCOMES == {
        NodeOutcome.PASSED,
        NodeOutcome.FAILED,
        NodeOutcome.SKIPPED,
        NodeOutcome.MISSING,
        NodeOutcome.ERROR,
    }
    # The wire spelling is part of the contract: these five words are what a reader of the
    # attribution record sees, and the axis is deliberately *not* the verdict axis (lowercase).
    assert {member.value for member in NODE_OUTCOMES} == {"PASSED", "FAILED", "SKIPPED", "MISSING", "ERROR"}


def test_an_attribution_verdict_is_the_verdict_the_attempt_accepts() -> None:
    """The bind the old two-vocabulary world could not state: no translation at the boundary.

    ``MutationEvidence`` refuses a spelling outside ``MUTATION_VERDICTS``, so an attribution
    verdict that is not expressible there would fail the day CT-3.4/3.5 is wired -- or, worse,
    compare unequal to ``"proven"`` and read as *not proven*. This asserts the values are the
    same strings, which is the only property the future writer needs.
    """
    assert {verdict.value for verdict in ATTRIBUTION_VERDICTS} <= MUTATION_VERDICTS
    assert SliceVerdict.PROVEN.value in MUTATION_VERDICTS


def test_a_record_cannot_name_a_verdict_the_gate_does_not_use(tmp_path: Path) -> None:
    """The constant was exported and read by nothing; now it is the rule it claimed to be."""
    bundle, _ = _seal(tmp_path)
    binding = _binding(bundle)
    good = attribute(binding, baseline=_run(NodeOutcome.PASSED), mutated=_run(NodeOutcome.FAILED))

    with pytest.raises(KillAttributionError) as refused:
        KillAttribution(
            binding=good.binding,
            verdict="PROVEN",  # type: ignore[arg-type]
            detail="",
            baseline=good.baseline,
            mutated=good.mutated,
        )
    assert refused.value.rule == "kill-attribution-invalid"

    # A member of the *slice* vocabulary that this module never measures. It carries a detail,
    # so only the membership rule can refuse it -- that is the half the membership check owns.
    with pytest.raises(KillAttributionError) as measured_elsewhere:
        KillAttribution(
            binding=good.binding,
            verdict=SliceVerdict.PRODUCER_ABSENT,
            detail="the slice gate owns this outcome",
            baseline=good.baseline,
            mutated=good.mutated,
        )
    assert measured_elsewhere.value.rule == "kill-attribution-invalid"

    with pytest.raises(KillAttributionError) as unexplained:
        KillAttribution(
            binding=good.binding,
            verdict=SliceVerdict.VACUOUS,
            detail="",
            baseline=good.baseline,
            mutated=_run(NodeOutcome.PASSED),
        )
    assert unexplained.value.rule == "kill-attribution-invalid"


def test_a_run_outcome_outside_the_five_is_refused_where_it_is_written() -> None:
    with pytest.raises(KillAttributionError) as refused:
        NodeRun(outcome="MAYBE", command="python -m pytest ...", exit_code=0)  # type: ignore[arg-type]
    assert refused.value.rule == "kill-run-invalid"


def test_a_baseline_pass_and_a_mutation_failure_is_proven(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    attribution = _attributed(bundle, NodeOutcome.FAILED)

    assert attribution.verdict is SliceVerdict.PROVEN
    assert attribution.detail == ""
    assert attribution.binding.target_id == _TARGET
    assert attribution.baseline.outcome is NodeOutcome.PASSED
    assert attribution.mutated.outcome is NodeOutcome.FAILED


def test_a_mutation_that_still_passes_is_vacuous(tmp_path: Path) -> None:
    bundle, _ = _seal(tmp_path)

    attribution = _attributed(bundle, NodeOutcome.PASSED)

    assert attribution.verdict is SliceVerdict.VACUOUS
    assert "still passes" in attribution.detail


@pytest.mark.parametrize("baseline", [NodeOutcome.FAILED, NodeOutcome.SKIPPED, NodeOutcome.MISSING, NodeOutcome.ERROR])
def test_a_baseline_that_did_not_pass_can_never_prove_a_kill(tmp_path: Path, baseline: NodeOutcome) -> None:
    bundle, _ = _seal(tmp_path)

    attribution = attribute(_binding(bundle), baseline=_run(baseline), mutated=_run(NodeOutcome.FAILED))

    assert attribution.verdict is SliceVerdict.ERROR
    assert attribution.detail == f"baseline_{baseline.value.lower()}"


@pytest.mark.parametrize("mutated", [NodeOutcome.SKIPPED, NodeOutcome.MISSING, NodeOutcome.ERROR])
def test_a_mutation_run_that_was_not_an_assertion_failure_is_an_error(tmp_path: Path, mutated: NodeOutcome) -> None:
    bundle, _ = _seal(tmp_path)

    attribution = _attributed(bundle, mutated)

    assert attribution.verdict is SliceVerdict.ERROR
    assert attribution.detail == f"mutated_{mutated.value.lower()}"


@pytest.mark.parametrize(
    ("baseline", "mutated"),
    [("MAYBE", "FAILED"), ("PASSED", "MAYBE"), (None, "FAILED")],
)
def test_something_that_is_not_a_run_cannot_be_attributed(tmp_path: Path, baseline: Any, mutated: Any) -> None:
    """A run-shaped value that is not a ``NodeRun`` (a dict, ``None``) is refused as a run.

    An *outcome* outside the five is now refused where it is written (next test), so the only
    way to hand ``attribute`` a bad value is to hand it something that is not a run at all.
    """
    bundle, _ = _seal(tmp_path)
    runs: dict[Any, Any] = {
        "PASSED": _run(NodeOutcome.PASSED),
        "FAILED": _run(NodeOutcome.FAILED),
        None: None,
        "MAYBE": {"outcome": "MAYBE"},
    }

    assert _rule(lambda: attribute(_binding(bundle), baseline=runs[baseline], mutated=runs[mutated])) == (
        "kill-run-invalid"
    )


def test_two_targets_attribute_independently(tmp_path: Path) -> None:
    root = sealed_tree(tmp_path)
    graph = plan_graph(slice_body=_SLICE_TWO_TARGETS)
    bundle = mint_sealed(
        root,
        graph=graph,
        plan_bytes=plan_document(slice_body=_SLICE_TWO_TARGETS).encode(),
        collected={_PUBLISH: [_NODEID], f"{_SEALED_ROOT}/tests/test_extra.py": [_OTHER_ENV]},
    )
    bound = bindings(bundle, graph, plan_bytes=plan_document(slice_body=_SLICE_TWO_TARGETS).encode())

    proven = attribute(bound[0], baseline=_run(NodeOutcome.PASSED), mutated=_run(NodeOutcome.FAILED))
    vacuous = attribute(bound[1], baseline=_run(NodeOutcome.PASSED), mutated=_run(NodeOutcome.PASSED))

    assert [item.target_id for item in bound] == ["publication.publish_plan", "publication.plan_immutable"]
    assert proven.verdict is SliceVerdict.PROVEN
    assert vacuous.verdict is SliceVerdict.VACUOUS


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
