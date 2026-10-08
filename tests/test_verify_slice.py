"""Verdict assembly: the lattice, and one kill-check end to end. (I02/SLICE5)

These oracles run the real thing -- a real overlay, a real subprocess, a real
pytest -- against a throwaway workspace. A kill-check that was proven only
against mocks would prove that the mocks agree with each other, which is the
exact failure (`VACUOUS`) this module exists to report about other people's
tests.

Class: **C0** with real I/O. The composition root (`drive_session` /
`run_workflow`) does not reach this code yet; SLICE6 is the slice that wires
it, and `tests/test_verify_gate_live.py` is where the C1 proof will live.
Recorded here rather than left implicit, per SD-C.
"""

from __future__ import annotations

import os
import shlex
import sys
import textwrap
from dataclasses import FrozenInstanceError
from pathlib import Path
from xml.etree import ElementTree

import pytest

from fa.inner_loop import slice_verification
from fa.inner_loop.junit_nodeid_plugin import JUNIT_NODEID_PROPERTY
from fa.inner_loop.plan_ids import PlanIds, SliceRecord, extract_plan_ids
from fa.inner_loop.slice_verification import (
    KILL_CHECK_VERDICTS,
    CommandOutcome,
    CommandResult,
    KillCheck,
    KillDirective,
    KillOperator,
    SliceVerdict,
    SliceVerification,
    _classify,
    _compare_baseline,
    _module_name,
    _run_kill_check,
    capture_test_nodeids,
    verify_plan,
    verify_slice,
)
from scripts import check_kill_directive_ownership

# A test file that depends on the producer, and one that does not. The second
# is the whole point: it is green, honest-looking, and proves nothing.
_DEPENDENT_TEST = """
from pkg.thing import consume


def test_consume_doubles_what_the_producer_returns():
    assert consume() == 14
"""

_INDEPENDENT_TEST = """
def test_arithmetic_still_works():
    assert 2 + 2 == 4
"""

_MODULE = """
def produce():
    return 7


def consume():
    return produce() * 2
"""


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A minimal src-layout workspace: one producer, one dependent test."""
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg" / "thing.py").write_text(textwrap.dedent(_MODULE).lstrip())
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_thing.py").write_text(textwrap.dedent(_DEPENDENT_TEST).lstrip())
    return tmp_path


def _slice_record(
    test_paths: tuple[str, ...] = ("tests/test_thing.py",),
    *,
    symbol: str = "produce",
    command: bool = True,
    directive: bool = True,
    contract_kind: str = "FUNCTIONAL",
) -> SliceRecord:
    """Build the real I01 record shape consumed by verify_slice."""
    lines = [
        "## SLICE1: verify composition fixture",
        "CONTRACTS:",
        f"  CT99 [{contract_kind}]: exercise the declared contract.",
    ]
    if directive:
        lines.append(f"    kill: neutralise src/pkg/thing.py::{symbol}")
    if test_paths:
        lines.append(f"TESTS: {' '.join(test_paths)}")
    if command:
        lines.extend(("```verify", "python -c \"print('verify ok')\"", "```"))
    records = extract_plan_ids("\n".join(lines)).slice_records
    assert len(records) == 1
    return records[0]


@pytest.fixture(autouse=True)
def hermetic_test_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the inner pytest with this interpreter instead of `uv run`.

    `KILL_CHECK_COMMAND` is a module constant for exactly this reason -- the
    same seam `_PROVENANCE_PROBE` already uses. The throwaway workspace is not
    a uv project, and building one would need the network that `UV_NO_SYNC=1`
    deliberately forbids.
    """
    monkeypatch.setattr(
        slice_verification,
        "KILL_CHECK_COMMAND",
        f"{shlex.quote(sys.executable)} -m pytest {{path}} -q -p no:cacheprovider",
    )


def _directive(
    symbol: str,
    callee: str | None = None,
    *,
    operator: KillOperator = KillOperator.NEUTRALISE,
    path: str = "src/pkg/thing.py",
) -> KillDirective:
    return KillDirective(operator=operator, path=path, symbol=symbol, callee=callee, line=1)


# --------------------------------------------------------------------------
# STEP1 — the lattice
# --------------------------------------------------------------------------


def test_the_lattice_has_exactly_the_seven_members_the_design_names() -> None:
    """CT65 / design note §3.2. A member nobody can produce is a lie, and a
    missing one forces a caller to invent a synonym."""
    assert [v.value for v in SliceVerdict] == [
        "proven",
        "vacuous",
        "producer_absent",
        "failing",
        "regression",
        "error",
        "skipped",
    ]


def test_vacuous_and_producer_absent_are_distinct_members() -> None:
    """The single distinction the increment exists for.

    `VACUOUS` means the test is wrong; `PRODUCER_ABSENT` means the feature is
    wrong. Different causes, different repairs, and merging them would discard
    the dead-code-shipped-as-a-feature detector.
    """
    assert len({SliceVerdict.VACUOUS, SliceVerdict.PRODUCER_ABSENT}) == 2
    assert SliceVerdict.PRODUCER_ABSENT not in {SliceVerdict.VACUOUS, SliceVerdict.FAILING}


def test_a_kill_check_cannot_claim_a_slice_level_verdict() -> None:
    """A kill-check speaks about one contract, so three members are out of its reach."""
    assert KILL_CHECK_VERDICTS == {
        SliceVerdict.PROVEN,
        SliceVerdict.VACUOUS,
        SliceVerdict.PRODUCER_ABSENT,
        SliceVerdict.ERROR,
    }
    for verdict in (SliceVerdict.FAILING, SliceVerdict.REGRESSION, SliceVerdict.SKIPPED):
        with pytest.raises(ValueError, match="not a kill-check verdict"):
            KillCheck(directive=_directive("produce"), verdict=verdict, detail="x", duration_s=0.0)


def test_every_non_proven_verdict_must_say_what_to_look_at() -> None:
    """A verdict an operator cannot act on is an alarm that gets ignored."""
    with pytest.raises(ValueError, match="must say what went wrong"):
        KillCheck(
            directive=_directive("produce"),
            verdict=SliceVerdict.VACUOUS,
            detail="",
            duration_s=0.0,
        )


# --------------------------------------------------------------------------
# STEP2 — one kill-check, end to end
# --------------------------------------------------------------------------


def test_kill_check_proves_a_test_that_depends_on_its_producer(workspace: Path) -> None:
    """Row 1 of the design note's three-row oracle.

    Neutralising `produce` makes `consume` return `None * 2`, the dependent
    test raises, and the kill-check reports the test as bound to its producer.
    """
    check = _run_kill_check(_directive("produce"), "tests/test_thing.py", workspace)

    assert check.verdict is SliceVerdict.PROVEN, check.detail
    assert check.detail == ""
    assert check.duration_s > 0.0


def test_kill_check_is_vacuous_when_the_test_ignores_the_producer(workspace: Path) -> None:
    """Row 3, and the one worth dwelling on.

    The test is green, looks honest, and proves nothing about the producer it
    is declared to cover. Fail-before/pass-after would have passed it.
    """
    (workspace / "tests" / "test_thing.py").write_text(textwrap.dedent(_INDEPENDENT_TEST).lstrip())

    check = _run_kill_check(_directive("produce"), "tests/test_thing.py", workspace)

    assert check.verdict is SliceVerdict.VACUOUS, check.detail
    assert "still passes" in check.detail
    assert "produce" in check.detail


def test_kill_check_reports_producer_absent_not_vacuous(workspace: Path) -> None:
    """Row 2. The plan names something the code does not have."""
    check = _run_kill_check(_directive("never_written"), "tests/test_thing.py", workspace)

    assert check.verdict is SliceVerdict.PRODUCER_ABSENT
    assert "never_written" in check.detail


def test_kill_check_names_the_missing_callee(workspace: Path) -> None:
    """`remove-call` claims a call site. If it is not there, the claim is wrong."""
    check = _run_kill_check(
        _directive("produce", "emit", operator=KillOperator.REMOVE_CALL),
        "tests/test_thing.py",
        workspace,
    )

    assert check.verdict is SliceVerdict.PRODUCER_ABSENT
    assert "produce -> emit" in check.detail


def test_kill_check_is_absent_for_a_source_file_the_workspace_lacks(workspace: Path) -> None:
    check = _run_kill_check(_directive("produce", path="src/pkg/gone.py"), "tests/test_thing.py", workspace)

    assert check.verdict is SliceVerdict.PRODUCER_ABSENT
    assert "src/pkg/gone.py" in check.detail


def test_kill_check_errors_when_no_test_paths_are_supplied(workspace: Path) -> None:
    check = _run_kill_check(_directive("produce"), (), workspace)

    assert check.verdict is SliceVerdict.ERROR
    assert "TESTS paths" in check.detail


def test_kill_check_errors_on_an_ambiguous_symbol(workspace: Path) -> None:
    """`targets > 1` must never be resolved by picking one."""
    (workspace / "src" / "pkg" / "thing.py").write_text(
        textwrap.dedent(
            """
            def produce():
                return 7

            def produce():
                return 8

            def consume():
                return produce() * 2
            """
        ).lstrip()
    )

    check = _run_kill_check(_directive("produce"), "tests/test_thing.py", workspace)

    assert check.verdict is SliceVerdict.ERROR
    assert "2 definitions" in check.detail


def test_kill_check_errors_when_the_provenance_probe_fails(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CT82 / CT62: no verdict is trusted until the overlay is proven to win.

    Spies on `run_commands` to assert the test was not reached. Without that
    the oracle would pass on an implementation that runs the test first and
    discards the result -- which costs the full test budget on every broken
    environment.
    """
    monkeypatch.setattr(slice_verification, "_PROVENANCE_PROBE", "import sys; sys.exit(3)")
    ran: list[str] = []
    real = slice_verification.run_commands

    def spy(commands, **kwargs):  # type: ignore[no-untyped-def]
        ran.extend(commands)
        return real(commands, **kwargs)

    monkeypatch.setattr(slice_verification, "run_commands", spy)

    check = _run_kill_check(_directive("produce"), "tests/test_thing.py", workspace)

    assert check.verdict is SliceVerdict.ERROR
    assert "provenance probe" in check.detail
    assert ran == [], f"the test was run anyway: {ran}"


def test_the_operators_tree_is_untouched_by_a_kill_check(workspace: Path) -> None:
    """CT64, scoped to this unit: the mutation lives only in the overlay."""
    before = (workspace / "src" / "pkg" / "thing.py").read_text()
    listing_before = sorted(p.name for p in workspace.iterdir())

    _run_kill_check(_directive("produce"), "tests/test_thing.py", workspace)

    assert (workspace / "src" / "pkg" / "thing.py").read_text() == before
    assert sorted(p.name for p in workspace.iterdir()) == listing_before


# --------------------------------------------------------------------------
# the module-name derivation the probe depends on
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rel_path", "expected"),
    [
        ("src/fa/inner_loop/slice_verification.py", "fa.inner_loop.slice_verification"),
        ("src/pkg/thing.py", "pkg.thing"),
        ("src/pkg/__init__.py", "pkg"),
        ("scripts/check_thing.py", "scripts.check_thing"),
        ("src/pkg/data.json", None),
        ("src", None),
    ],
)
def test_kill_check_module_name_strips_the_prefix_the_overlay_adds(rel_path: str, expected: str | None) -> None:
    """The name derived here must equal the name the probe resolves.

    `src` is stripped because `src` is exactly what `_overlay_env` prepends to
    `PYTHONPATH` (CT61) -- the two agree by construction, not by coincidence.
    """
    assert _module_name(rel_path) == expected


# --------------------------------------------------------------------------
# the environment seam on run_commands
# --------------------------------------------------------------------------


def test_run_commands_still_builds_its_own_environment_by_default(tmp_path: Path) -> None:
    """The seam must not change what a plain verify command sees."""
    (result,) = slice_verification.run_commands(("printenv UV_NO_SYNC",), workspace=tmp_path)

    assert result.outcome is CommandOutcome.PASS
    assert result.stdout_tail.strip() == "1"


def test_run_commands_uses_an_injected_environment_when_given_one(tmp_path: Path) -> None:
    """And a kill-check's overlay environment must actually reach the subprocess."""
    env = slice_verification._build_env(tmp_path)
    env["FA_KILL_CHECK_MARKER"] = "overlay"

    (result,) = slice_verification.run_commands(("printenv FA_KILL_CHECK_MARKER",), workspace=tmp_path, env=env)

    assert result.outcome is CommandOutcome.PASS
    assert result.stdout_tail.strip() == "overlay"


# --------------------------------------------------------------------------
# STEP4 — slice composition and the Q53(c) all-path choice
# --------------------------------------------------------------------------


def test_verify_slice_composes_a_proven_kill_into_the_frozen_slice_result(workspace: Path) -> None:
    record = _slice_record()

    result = verify_slice(record, root=workspace, baseline={}, now={})

    assert isinstance(result, SliceVerification)
    assert result.slice_id == "SLICE1"
    assert result.verdict is SliceVerdict.PROVEN
    assert len(result.command_results) == 1
    assert result.command_results[0].outcome is CommandOutcome.PASS
    assert tuple(contract_id for contract_id, _ in result.kill_checks) == ("CT99",)
    assert result.kill_checks[0][1].verdict is SliceVerdict.PROVEN
    attribute = "verdict"
    with pytest.raises(FrozenInstanceError):
        setattr(result, attribute, SliceVerdict.FAILING)


def test_verify_slice_composes_producer_absent_not_vacuous(workspace: Path) -> None:
    record = _slice_record(symbol="never_written")

    result = verify_slice(record, root=workspace, baseline={}, now={})

    assert result.verdict is SliceVerdict.PRODUCER_ABSENT
    assert result.kill_checks[0][0] == "CT99"
    assert "never_written" in result.kill_checks[0][1].detail


def test_verify_slice_composes_vacuous_when_all_declared_paths_survive(workspace: Path) -> None:
    (workspace / "tests" / "test_thing.py").write_text(textwrap.dedent(_INDEPENDENT_TEST).lstrip())
    record = _slice_record()

    result = verify_slice(record, root=workspace, baseline={}, now={})

    assert result.verdict is SliceVerdict.VACUOUS
    assert result.kill_checks[0][0] == "CT99"
    assert "still pass" in result.kill_checks[0][1].detail


def test_verify_slice_runs_all_slice_paths_and_accepts_the_q53c_attribution_risk(workspace: Path) -> None:
    """A red second path proves the kill even though the first path is unrelated and green.

    This intentionally pins the operator's Q53(c) choice, including its weaker
    contract attribution: omitting the second path changes PROVEN to VACUOUS.
    """
    (workspace / "tests" / "test_thing.py").write_text(textwrap.dedent(_INDEPENDENT_TEST).lstrip())
    (workspace / "tests" / "test_unrelated.py").write_text("def test_unrelated_red():\n    assert False\n")
    paths = ("tests/test_thing.py", "tests/test_unrelated.py")
    record = _slice_record(paths)

    result = verify_slice(record, root=workspace, baseline={}, now={})

    assert record.test_paths == paths
    assert result.verdict is SliceVerdict.PROVEN
    assert result.kill_checks[0][1].verdict is SliceVerdict.PROVEN


def test_verify_slice_errors_before_commands_when_functional_kill_metadata_is_missing(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_run(*args: object, **kwargs: object) -> None:
        pytest.fail("invalid kill metadata must block before running verify commands")

    monkeypatch.setattr(slice_verification, "run_commands", unexpected_run)
    result = verify_slice(_slice_record(directive=False), root=workspace, baseline={}, now={})

    assert result.verdict is SliceVerdict.ERROR
    assert result.command_results == ()
    assert result.kill_checks == ()
    assert "CT99" in result.detail


def test_verify_slice_errors_when_functional_contract_has_no_test_paths(workspace: Path) -> None:
    result = verify_slice(_slice_record(test_paths=()), root=workspace, baseline={}, now={})

    assert result.verdict is SliceVerdict.ERROR
    assert "TESTS path" in result.detail
    assert result.command_results == ()


def test_verify_slice_keeps_legacy_no_command_slice_skipped(workspace: Path) -> None:
    result = verify_slice(
        _slice_record(test_paths=(), command=False, directive=False),
        root=workspace,
        baseline=None,
        now=None,
    )

    assert result.verdict is SliceVerdict.SKIPPED
    assert result.command_results == ()
    assert result.kill_checks == ()


def test_verify_slice_preserves_baseline_regression_nodeids(workspace: Path) -> None:
    record = _slice_record(symbol="never_written")
    baseline = {"tests/test_thing.py::test_existing": True}
    now = {"tests/test_thing.py::test_existing": False}

    result = verify_slice(record, root=workspace, baseline=baseline, now=now)

    assert result.verdict is SliceVerdict.REGRESSION
    assert result.regression_nodeids == ("tests/test_thing.py::test_existing",)
    assert result.failed_nodeids == ("tests/test_thing.py::test_existing",)


def test_capture_test_nodeids_uses_harness_junit_property(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The production adapter parses pytest's exact collector nodeid, not a reconstructed name."""
    test_path = tmp_path / "test_capture.py"
    test_path.write_text(
        "import pytest\n\n"
        "class TestCapture:\n"
        "    @pytest.mark.parametrize('value', [3, 4])\n"
        "    def test_value(self, value):\n"
        "        assert value > 0\n",
        encoding="utf-8",
    )
    repo_src = str(Path(__file__).resolve().parents[1] / "src")
    monkeypatch.setenv("PYTHONPATH", repo_src)
    monkeypatch.setattr(
        slice_verification,
        "NODEID_CAPTURE_COMMAND",
        f"{shlex.quote(sys.executable)} -m pytest {{paths}} -p fa.inner_loop.junit_nodeid_plugin "
        "--junitxml={report} -q",
    )

    captured = capture_test_nodeids((test_path.name,), root=tmp_path)

    assert captured.command_result is not None
    assert captured.command_result.outcome is CommandOutcome.PASS
    assert captured.nodeids == {
        "test_capture.py::TestCapture::test_value[3]": True,
        "test_capture.py::TestCapture::test_value[4]": True,
    }


def test_capture_test_nodeids_treats_a_not_yet_existing_path_as_empty_t0(tmp_path: Path) -> None:
    """CT86: a new file has no before-state; it is not fabricated as red."""
    captured = capture_test_nodeids(("tests/test_new_file.py",), root=tmp_path)

    assert captured.nodeids == {}
    assert captured.command_result is None
    assert "no declared TESTS path exists" in captured.detail


def _plan_for_verify_plan() -> str:
    return """```verify
python -c "print('plan-level')"
```
## SLICE1: first owner
CONTRACTS:
  CT11 [CONSTRAINT]: the first owner stays distinct.
TESTS: tests/test_first.py
```verify
python -c "print('slice-one')"
```
## SLICE2: second owner
CONTRACTS:
  CT12 [CONSTRAINT]: the second owner stays distinct.
TESTS: tests/test_second.py
```verify
python -c "print('slice-two')"
```
"""


def test_verify_plan_runs_plan_commands_once_and_keeps_slice_attribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = extract_plan_ids(_plan_for_verify_plan())
    command_batches: list[tuple[str, ...]] = []
    owners: list[str | None] = []
    original_commands_for = PlanIds.commands_for

    def commands_for_spy(self: PlanIds, slice_id: str | None) -> tuple[str, ...]:
        owners.append(slice_id)
        return original_commands_for(self, slice_id)

    def run_spy(
        commands: tuple[str, ...] | list[str],
        *,
        workspace: Path,
        timeout_s: float | None = None,
        deadline: float | None = None,
        env: dict[str, str] | None = None,
    ) -> tuple[CommandResult, ...]:
        del workspace, timeout_s, deadline, env
        batch = tuple(commands)
        command_batches.append(batch)
        return tuple(
            CommandResult(
                command=command,
                outcome=CommandOutcome.PASS,
                exit_code=0,
                stdout_tail="ok",
                stderr_tail="",
                duration_s=0.01,
            )
            for command in batch
        )

    monkeypatch.setattr(PlanIds, "commands_for", commands_for_spy)
    monkeypatch.setattr(slice_verification, "run_commands", run_spy)

    verification = verify_plan(
        plan,
        root=tmp_path,
        baseline_by_slice={"SLICE1": {}, "SLICE2": {}},
        now_by_slice={"SLICE1": {}, "SLICE2": {}},
    )

    assert owners == [None]
    assert command_batches == [
        plan.commands_for(None),
        plan.slice_records[0].commands,
        plan.slice_records[1].commands,
    ]
    assert len(verification.plan_command_results) == 1
    assert [result.slice_id for result in verification.slice_verifications] == ["SLICE1", "SLICE2"]
    assert verification.slice_verifications[0].command_results[0].command.endswith("slice-one')\"")
    assert verification.slice_verifications[1].command_results[0].command.endswith("slice-two')\"")
    assert verification.blocking is False


def test_verify_plan_treats_a_failed_plan_command_as_blocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = extract_plan_ids(_plan_for_verify_plan())

    def run_spy(
        commands: tuple[str, ...] | list[str],
        *,
        workspace: Path,
        timeout_s: float | None = None,
        deadline: float | None = None,
        env: dict[str, str] | None = None,
    ) -> tuple[CommandResult, ...]:
        del workspace, timeout_s, deadline, env
        return tuple(
            CommandResult(
                command=command,
                outcome=CommandOutcome.FAIL if "plan-level" in command else CommandOutcome.PASS,
                exit_code=1 if "plan-level" in command else 0,
                stdout_tail="",
                stderr_tail="plan command failed" if "plan-level" in command else "",
                duration_s=0.01,
            )
            for command in commands
        )

    monkeypatch.setattr(slice_verification, "run_commands", run_spy)

    verification = verify_plan(
        plan,
        root=tmp_path,
        baseline_by_slice={"SLICE1": {}, "SLICE2": {}},
        now_by_slice={"SLICE1": {}, "SLICE2": {}},
    )

    assert verification.blocking is True
    assert verification.plan_command_results[0].exit_code == 1
    assert all(item.verdict is not SliceVerdict.ERROR for item in verification.slice_verifications)


# --------------------------------------------------------------------------
# STEP6 — ownership audit waits for the slice's completion boundary
# --------------------------------------------------------------------------


def test_ownership_audit_reports_only_absent_targets_in_fully_ticked_slices(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CT83: the same missing producer is pending until its slice is complete."""
    increments = tmp_path / "worklogs" / "planning-topology-and-executable-contracts-loop" / "increments"
    increments.mkdir(parents=True)
    source = tmp_path / "src" / "pkg" / "thing.py"
    source.parent.mkdir(parents=True)
    source.write_text("def present():\n    return 1\n")
    (increments / "fixture.md").write_text(
        """## SLICE1: complete slice
STEPS: prescriptive
CONTRACTS:
  CT1 [FUNCTIONAL]: its target is absent.
    kill: neutralise src/pkg/thing.py::missing
  CT2 [FUNCTIONAL]: its target exists exactly once.
    kill: neutralise src/pkg/thing.py::present
TESTS: tests/test_owner.py
- [x] STEP1: complete
- [x] STEP2: complete

## SLICE2: work not done
STEPS: prescriptive
CONTRACTS:
  CT3 [FUNCTIONAL]: same absent target, but not complete.
    kill: neutralise src/pkg/thing.py::missing
TESTS: tests/test_owner.py
- [x] STEP1: complete
- [ ] STEP2: pending
"""
    )

    exit_code = check_kill_directive_ownership.main(repo_root=tmp_path)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1
    finding = captured.err.strip()
    assert "SLICE1" in finding
    assert "CT1" in finding
    assert "missing" in finding
    assert "0 definitions" in finding
    assert "CT2" not in finding
    assert "SLICE2" not in finding
    assert "CT3" not in finding


# --------------------------------------------------------------------------
# STEP3 — nodeid baseline comparison and single-verdict precedence
# --------------------------------------------------------------------------


def _result(outcome: CommandOutcome) -> CommandResult:
    """A typed command result; no mocks hide the state under classification."""
    return CommandResult(
        command="uv run pytest tests/test_thing.py -q",
        outcome=outcome,
        exit_code={CommandOutcome.PASS: 0, CommandOutcome.FAIL: 1, CommandOutcome.ERROR: None}[outcome],
        stdout_tail="",
        stderr_tail="",
        duration_s=0.01,
    )


def _kill(verdict: SliceVerdict) -> KillCheck:
    """A typed per-contract result for the classifier's precedence matrix."""
    return KillCheck(
        directive=_directive("produce"),
        verdict=verdict,
        detail="" if verdict is SliceVerdict.PROVEN else "operator detail",
        duration_s=0.01,
    )


def test_harness_junitxml_records_exact_pytest_nodeids(tmp_path: Path) -> None:
    """CT68/CT69: stock JUnitXML lacks nodeid; the harness plugin adds it.

    The inner run exercises real pytest collection, its real JUnitXML reporter,
    and the real plugin module imported from this checkout. Parameter IDs and
    class-qualified nodeids are the adversarial cases for reconstructing an ID
    from JUnit's `classname` + `name` fields.
    """
    test_path = tmp_path / "test_junit_sample.py"
    test_path.write_text(
        """
import pytest

class TestThing:
    @pytest.mark.parametrize('value', [1, 2])
    def test_value(self, value):
        assert value > 0

def test_plain():
    assert True
"""
    )
    xml_path = tmp_path / "results.xml"
    env = slice_verification._build_env(tmp_path)
    repo_src = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = repo_src + os.pathsep + env.get("PYTHONPATH", "")
    command = (
        f"{shlex.quote(sys.executable)} -m pytest {shlex.quote(test_path.name)} "
        f"-p fa.inner_loop.junit_nodeid_plugin --junitxml={shlex.quote(str(xml_path))} -q"
    )

    (result,) = slice_verification.run_commands((command,), workspace=tmp_path, env=env)

    assert result.outcome is CommandOutcome.PASS, result.stderr_tail
    xml = ElementTree.parse(xml_path).getroot()
    recorded = []
    for case in xml.iter("testcase"):
        values = [
            prop.get("value")
            for prop in case.findall("./properties/property")
            if prop.get("name") == JUNIT_NODEID_PROPERTY
        ]
        assert len(values) == 1, f"JUnit testcase {case.attrib!r} has {values!r}"
        recorded.append(values[0])

    assert recorded == [
        "test_junit_sample.py::TestThing::test_value[1]",
        "test_junit_sample.py::TestThing::test_value[2]",
        "test_junit_sample.py::test_plain",
    ]


def test_classify_baseline_maps_only_green_existing_nodeids_to_regressions() -> None:
    baseline = {
        "tests/test_a.py::test_went_red": True,
        "tests/test_a.py::test_was_already_red": False,
        "tests/test_a.py::test_missing_now": True,
    }
    now = {
        "tests/test_a.py::test_went_red": False,
        "tests/test_a.py::test_was_already_red": False,
        "tests/test_a.py::test_new": False,
    }

    assert _compare_baseline(baseline, now) == ("tests/test_a.py::test_went_red",)


def test_classify_nodeids_absent_at_t0_are_not_regressions() -> None:
    """A newly-added failing test has no before-state; it is not REGRESSION."""
    assert (
        _compare_baseline(
            {"tests/test_a.py::test_old": True},
            {"tests/test_a.py::test_old": True, "tests/test_a.py::test_new": False},
        )
        == ()
    )


def test_classify_missing_nodeid_rows_are_unknown_not_false() -> None:
    """An absent row on either side cannot manufacture a green-to-red edge."""
    assert (
        _compare_baseline(
            {"tests/test_a.py::test_missing_now": True},
            {},
        )
        == ()
    )
    assert (
        _compare_baseline(
            {},
            {"tests/test_a.py::test_absent_at_t0": False},
        )
        == ()
    )


def test_classify_red_to_red_is_not_a_regression() -> None:
    assert (
        _compare_baseline(
            {"tests/test_a.py::test_preexisting": False},
            {"tests/test_a.py::test_preexisting": False},
        )
        == ()
    )


def test_classify_unavailable_baseline_or_now_report_has_no_regression_row() -> None:
    assert _compare_baseline(None, {"tests/test_a.py::test_case": False}) == ()
    assert _compare_baseline({"tests/test_a.py::test_case": True}, None) == ()


def test_classify_command_failure_remains_blocking_even_with_a_regression() -> None:
    """Q52(a): verbatim command exit is authoritative and fail-closed."""
    verdict = _classify(
        (_result(CommandOutcome.FAIL),),
        (_kill(SliceVerdict.VACUOUS),),
        baseline={"tests/test_a.py::test_case": True},
        now={"tests/test_a.py::test_case": False},
    )

    assert verdict is SliceVerdict.FAILING


def test_classify_new_red_nodeid_absent_at_t0_is_failing_not_regression() -> None:
    verdict = _classify(
        (_result(CommandOutcome.PASS),),
        (_kill(SliceVerdict.PROVEN),),
        baseline={"tests/test_a.py::test_old": True},
        now={
            "tests/test_a.py::test_old": True,
            "tests/test_a.py::test_new": False,
        },
    )

    assert verdict is SliceVerdict.FAILING


def test_classify_red_to_red_is_advisory_when_verify_commands_pass() -> None:
    verdict = _classify(
        (_result(CommandOutcome.PASS),),
        (_kill(SliceVerdict.PROVEN),),
        baseline={"tests/test_a.py::test_preexisting": False},
        now={"tests/test_a.py::test_preexisting": False},
    )

    assert verdict is SliceVerdict.PROVEN


def test_classify_red_to_red_is_still_blocked_by_a_failed_command() -> None:
    """CT68's advisory comparison does not suppress the command's own exit."""
    verdict = _classify(
        (_result(CommandOutcome.FAIL),),
        (_kill(SliceVerdict.PROVEN),),
        baseline={"tests/test_a.py::test_preexisting": False},
        now={"tests/test_a.py::test_preexisting": False},
    )

    assert verdict is SliceVerdict.FAILING


def test_classify_green_commands_with_a_green_to_red_nodeid_is_regression() -> None:
    verdict = _classify(
        (_result(CommandOutcome.PASS),),
        (_kill(SliceVerdict.PROVEN),),
        baseline={"tests/test_a.py::test_case": True},
        now={"tests/test_a.py::test_case": False},
    )

    assert verdict is SliceVerdict.REGRESSION


def test_classify_command_error_dominates_every_other_phase() -> None:
    verdict = _classify(
        (_result(CommandOutcome.ERROR), _result(CommandOutcome.FAIL)),
        (_kill(SliceVerdict.PRODUCER_ABSENT),),
        baseline={"tests/test_a.py::test_case": True},
        now={"tests/test_a.py::test_case": False},
    )

    assert verdict is SliceVerdict.ERROR


def test_classify_kill_error_dominates_command_failure() -> None:
    verdict = _classify(
        (_result(CommandOutcome.FAIL),),
        (_kill(SliceVerdict.ERROR),),
        baseline={},
        now={},
    )

    assert verdict is SliceVerdict.ERROR


def test_classify_missing_junit_report_is_error_not_proven() -> None:
    """None means unavailable; an empty mapping is a valid empty report."""
    for baseline, now in ((None, {}), ({}, None)):
        assert (
            _classify(
                (_result(CommandOutcome.PASS),),
                (_kill(SliceVerdict.PROVEN),),
                baseline=baseline,
                now=now,
            )
            is SliceVerdict.ERROR
        )


def test_classify_skips_a_legacy_slice_without_verify_commands() -> None:
    """A missing verify block is advisory even if no baseline was captured."""
    assert _classify((), (), baseline=None, now=None) is SliceVerdict.SKIPPED


def test_classify_producer_absent_precedes_vacuous_when_both_occur() -> None:
    verdict = _classify(
        (_result(CommandOutcome.PASS),),
        (_kill(SliceVerdict.VACUOUS), _kill(SliceVerdict.PRODUCER_ABSENT)),
        baseline={},
        now={},
    )

    assert verdict is SliceVerdict.PRODUCER_ABSENT


def test_classify_vacuous_and_all_proven_contracts() -> None:
    assert (
        _classify(
            (_result(CommandOutcome.PASS),),
            (_kill(SliceVerdict.VACUOUS),),
            baseline={},
            now={},
        )
        is SliceVerdict.VACUOUS
    )
    assert (
        _classify(
            (_result(CommandOutcome.PASS),),
            (_kill(SliceVerdict.PROVEN), _kill(SliceVerdict.PROVEN)),
            baseline={},
            now={},
        )
        is SliceVerdict.PROVEN
    )
