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

import shlex
import sys
import textwrap
from pathlib import Path

import pytest

from fa.inner_loop import slice_verification
from fa.inner_loop.slice_verification import (
    KILL_CHECK_VERDICTS,
    CommandOutcome,
    KillCheck,
    KillDirective,
    KillOperator,
    SliceVerdict,
    _module_name,
    _run_kill_check,
)

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
    assert SliceVerdict.VACUOUS is not SliceVerdict.PRODUCER_ABSENT
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
    (workspace / "tests" / "test_thing.py").write_text(
        textwrap.dedent(_INDEPENDENT_TEST).lstrip()
    )

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
    check = _run_kill_check(
        _directive("produce", path="src/pkg/gone.py"), "tests/test_thing.py", workspace
    )

    assert check.verdict is SliceVerdict.PRODUCER_ABSENT
    assert "src/pkg/gone.py" in check.detail


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


def test_kill_check_errors_when_the_provenance_probe_fails(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
def test_kill_check_module_name_strips_the_prefix_the_overlay_adds(
    rel_path: str, expected: str | None
) -> None:
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

    (result,) = slice_verification.run_commands(
        ("printenv FA_KILL_CHECK_MARKER",), workspace=tmp_path, env=env
    )

    assert result.outcome is CommandOutcome.PASS
    assert result.stdout_tail.strip() == "overlay"
