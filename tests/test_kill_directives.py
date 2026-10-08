"""I02/SLICE2 — kill directives: strict parse, loud failure.

root=pure functions class=C0/C0p claim=CT50/CT50b/CT51/CT52/CT53/CT54 path=T3
oracle=parsed directive tuples, and the exact diagnostic rule + line.

**Why there is no C1 here.** `parse_kill_directives` and `validate_kill_directives`
have no production caller until SLICE5 assembles the verdict and SLICE6 wires it
into `_run_stage`. A composition-root test over an uncalled function would boot
the loop, assert nothing about these functions, and pass whether or not they
exist — the definition of theatre. The live proof is SLICE6's and is registered
in `notes/e2e-live-verification-register.md` against these producers.

**The thing being defended.** A kill directive is the only thing separating "the
tests are green" from "the tests are green AND they would notice if the feature
were deleted". Every failure mode below ends in a silently disabled non-vacuity
gate, so every one of them is a FAIL with a line number rather than an absence.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

import pytest

from fa.inner_loop import slice_verification
from fa.inner_loop.plan_ids import FAIL, SliceRecord, extract_plan_ids
from fa.inner_loop.slice_verification import (
    KillDirective,
    KillOperator,
    parse_kill_directives,
    validate_kill_directives,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_DIR = REPO_ROOT / "worklogs" / "planning-topology-and-executable-contracts-loop" / "increments"


def _section(*lines: str) -> str:
    """A slice section, written the way a planner writes one."""
    return textwrap.dedent("\n".join(lines)) + "\n"


def _rec(section: str) -> SliceRecord:
    """The record I01 builds for *section* — the parser's own answer.

    These tests drive `parse_kill_directives` through I01 rather than handing
    it text, because that is now the only way it can be called. The coupling
    is the point: if I01 stops recognising an entry, this test file notices,
    where previously I02 held a private opinion that could agree with nothing.
    """
    records = extract_plan_ids(section).slice_records
    return records[0] if records else SliceRecord(slice_id="SLICE1")


# ── CT50 — parse: the directive is read from the raw section ───────────────


def test_a_directive_on_the_last_line_parses() -> None:
    """§F1 case 1 — the shape that already worked, pinned so it keeps working."""
    section = _section(
        "## SLICE1: a thing",
        "CONTRACTS:",
        "  CT1 [FUNCTIONAL]: it does the thing.",
        "    kill: neutralise src/a.py::do_thing",
    )

    directives = parse_kill_directives(_rec(section))

    assert directives == {
        "CT1": KillDirective(
            operator=KillOperator.NEUTRALISE,
            path="src/a.py",
            symbol="do_thing",
            callee=None,
            line=4,
        )
    }


def test_trailing_prose_after_the_directive_is_harmless() -> None:
    """§F1 case 2 — the case that broke the contract-body reader (E123).

    Reading the directive from the joined contract body lost the line boundary,
    so an anchored regex stopped matching the moment prose followed. Four of the
    six measured cases degraded to "no kill-check found", which is
    indistinguishable from "the planner declared none".
    """
    section = _section(
        "## SLICE1: a thing",
        "CONTRACTS:",
        "  CT1 [FUNCTIONAL]: it does the thing.",
        "    kill: remove-call src/a.py::caller -> callee",
        "    Catches: the whole point of the contract, explained at length.",
    )

    directives = parse_kill_directives(_rec(section))

    assert directives["CT1"].operator is KillOperator.REMOVE_CALL
    assert directives["CT1"].callee == "callee"


def test_two_directives_on_one_contract_keep_the_first_deterministically() -> None:
    """§F1 case 3 — a mapping cannot hold both, so the choice must be stated.

    Taking the *last* silently honours the directive the planner probably
    abandoned. Taking the first is equally arbitrary in isolation, which is
    exactly why the condition is also reported — see the ambiguity oracle.
    """
    section = _section(
        "## SLICE1: a thing",
        "CONTRACTS:",
        "  CT1 [FUNCTIONAL]: it does the thing.",
        "    kill: neutralise src/a.py::first",
        "    kill: neutralise src/a.py::second",
    )

    assert parse_kill_directives(_rec(section))["CT1"].symbol == "first"


def test_a_directive_is_attributed_to_the_contract_it_sits_under() -> None:
    """Attribution, not position: the reason the raw section is the input."""
    section = _section(
        "## SLICE1: a thing",
        "CONTRACTS:",
        "  CT1 [FUNCTIONAL]: first.",
        "    kill: neutralise src/a.py::one",
        "  CT2 [FUNCTIONAL]: second.",
        "    kill: neutralise src/b.py::two",
    )

    directives = parse_kill_directives(_rec(section))

    assert directives["CT1"].symbol == "one"
    assert directives["CT2"].symbol == "two"
    assert directives["CT1"].path == "src/a.py"
    assert directives["CT2"].path == "src/b.py"


def test_a_directive_before_any_contract_is_ignored_not_misattributed() -> None:
    """A stray directive must not be charged to whichever contract comes next."""
    section = _section(
        "## SLICE1: a thing",
        "    kill: neutralise src/a.py::orphan",
        "CONTRACTS:",
        "  CT1 [FUNCTIONAL]: it does the thing.",
    )

    assert parse_kill_directives(_rec(section)) == {}


def test_an_empty_section_parses_to_nothing_without_raising() -> None:
    """Total, like I01's accessors: unknown input yields emptiness, never an error."""
    assert parse_kill_directives(_rec("")) == {}


# ── CT50b — a symbol may be a bare name or a dotted Class.method ───────────


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [("f", ("f",)), ("Class.method", ("Class", "method")), ("A.B.c", ("A", "B", "c"))],
)
def test_a_symbol_splits_into_its_dotted_parts(symbol: str, expected: tuple[str, ...]) -> None:
    """CT50b — found by auditing this plan's own directives.

    Three contracts name `_Silence.visit_Call`. Under a bare-name grammar that
    directive resolves to nothing and reports PRODUCER_ABSENT against working
    code — a false accusation shaped exactly like a true one.
    """
    assert slice_verification._split_dotted(symbol) == expected


def test_a_dotted_symbol_survives_the_strict_parse() -> None:
    """The grammar half of CT50b: the reader must accept what the plan writes."""
    section = _section(
        "## SLICE1: a thing",
        "CONTRACTS:",
        "  CT1 [FUNCTIONAL]: it does the thing.",
        "    kill: remove-call src/a.py::_Silence.visit_Call -> generic_visit",
    )

    directive = parse_kill_directives(_rec(section))["CT1"]

    assert directive.symbol == "_Silence.visit_Call"
    assert slice_verification._split_dotted(directive.symbol) == ("_Silence", "visit_Call")


# ── CT51 / CT52 / CT54 — validation ────────────────────────────────────────


def _validate(section: str) -> list[tuple[str, int]]:
    """Validate a one-slice document and return (rule, line) pairs."""
    ids = extract_plan_ids(section)
    return [(d.rule, d.line) for d in validate_kill_directives(section, ids, path="PLAN.md")]


def _plan(*contract_lines: str) -> str:
    return _section(
        "## SLICE1: a thing",
        "STEPS: prescriptive",
        "INTENT: do a thing.",
        "CONTRACTS:",
        *contract_lines,
        "TESTS: tests/test_thing.py",
    )


@pytest.mark.parametrize("typo", ["kil:", "Kill :", "kill-check:"])
def test_a_near_miss_keyword_is_reported_not_swallowed(typo: str) -> None:
    """CT51 — the three shapes the contract names, each by its own line.

    Without this rule a typo presents as "this contract declared no
    kill-check", which is a legitimate state for a CONSTRAINT. The gate would
    switch itself off for that contract and say nothing.
    """
    found = _validate(_plan("  CT1 [FUNCTIONAL]: a thing.", f"    {typo} neutralise src/a.py::f"))

    assert ("kill-directive-near-miss", 6) in found


def test_a_well_formed_directive_is_never_reported_as_a_near_miss() -> None:
    """Non-vacuity for CT51: a rule that fires on everything proves nothing."""
    found = _validate(_plan("  CT1 [FUNCTIONAL]: a thing.", "    kill: neutralise src/a.py::f"))

    assert found == []


def test_a_line_claiming_to_be_a_directive_that_does_not_parse_is_malformed() -> None:
    """CT52 — `kill:` with a missing `::` is an error, not an absence."""
    found = _validate(_plan("  CT1 [FUNCTIONAL]: a thing.", "    kill: neutralise src/a.py f"))

    assert ("kill-directive-malformed", 6) in found


def test_a_malformed_directive_is_not_also_reported_as_missing() -> None:
    """One mistake, one diagnostic. Two would send the operator in a circle."""
    found = _validate(_plan("  CT1 [FUNCTIONAL]: a thing.", "    kill: neutralise src/a.py f"))

    assert [rule for rule, _ in found] == ["kill-directive-malformed"]


def test_two_directives_on_one_contract_are_ambiguous() -> None:
    """CT52 — the condition the parser's first-wins rule deliberately hides.

    The parser must stay total, so it picks one. That choice is only safe
    because this rule refuses to let the plan ship with the ambiguity in it.
    """
    found = _validate(
        _plan(
            "  CT1 [FUNCTIONAL]: a thing.",
            "    kill: neutralise src/a.py::first",
            "    kill: neutralise src/a.py::second",
        )
    )

    assert ("kill-directive-ambiguous", 7) in found


def test_a_functional_contract_without_a_directive_is_missing() -> None:
    """CT52 — the default-deny that makes the whole gate non-optional."""
    found = _validate(_plan("  CT1 [FUNCTIONAL]: a thing with no kill-check."))

    assert found == [("kill-directive-missing", 5)]


@pytest.mark.parametrize("contract_class", ["CONSTRAINT", "PRESERVATION"])
def test_a_non_functional_contract_needs_no_directive(contract_class: str) -> None:
    """CT54 — exemption, so the gate asks for evidence and not for ceremony.

    A CONSTRAINT's proof is usually an absence and a PRESERVATION's is an
    existing test. Demanding a mutation of either manufactures a kill-check
    that cannot fail for the right reason.
    """
    found = _validate(_plan(f"  CT1 [{contract_class}]: a thing proven another way."))

    assert found == []


def test_diagnostics_are_ordered_by_line() -> None:
    """Determinism: an operator reads a report top to bottom, like the file."""
    found = _validate(
        _plan(
            "  CT1 [FUNCTIONAL]: a thing.",
            "    kil: neutralise src/a.py::f",
            "  CT2 [FUNCTIONAL]: another thing.",
            "    kill: neutralise src/b.py broken",
        )
    )

    assert [line for _, line in found] == sorted(line for _, line in found)


# ── CT53 — purity, so the gate can run at admission ────────────────────────


@pytest.mark.parametrize("function_name", ["parse_kill_directives", "validate_kill_directives", "_near_miss"])
def test_parsing_and_validation_touch_neither_disk_nor_subprocess(function_name: str) -> None:
    """CT53 — structural, because the claim is about what the code *can* do.

    A behavioural test cannot prove the absence of a filesystem read; it can
    only fail to trigger one. This walks the function's own AST instead. The
    point is scheduling: a malformed directive must be catchable before the
    coder stage starts, and anything that opens a file or spawns a process
    cannot run at admission.
    """
    source = textwrap.dedent(inspect.getsource(getattr(slice_verification, function_name)))
    forbidden = {"open", "subprocess", "run", "Popen", "read_text", "write_text", "mkdir"}

    called: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            called.add(func.id)
        elif isinstance(func, ast.Attribute):
            called.add(func.attr)

    assert not (called & forbidden), f"{function_name} reaches for {sorted(called & forbidden)}"


# ── Integration against the real plans this gate exists to read ────────────


def test_the_i02_plan_declares_a_clean_set_of_directives() -> None:
    """The strongest available oracle: the artifact the gate was written for.

    A hand-written corpus proves the parser handles what its author imagined;
    this proves it handles what the planner actually wrote.

    The count is derived, not pinned. An earlier version asserted the literal
    28 the readiness audit counted (E138), and it fired the moment the plan
    legitimately grew a slice — a tripwire that reports editing, not breakage,
    and whose only available fix is to bump the number, which teaches the
    reader to bump it next time too. What must hold is the invariant: every
    FUNCTIONAL contract carries a directive the parser can recover, and the
    validator finds nothing to say. The floor keeps it non-vacuous.
    """
    path = PLAN_DIR / "increment-02-verify-gate-and-kill-checks.md"
    text = path.read_text(encoding="utf-8")
    ids = extract_plan_ids(text)

    parsed: dict[str, KillDirective] = {}
    for record in ids.slice_records:
        parsed.update(parse_kill_directives(record))
    functional = {c for c in ids.contracts if ids.contract_class(c) == "FUNCTIONAL"}

    assert len(parsed) >= 28, "fewer directives than the readiness audit counted (E138)"
    assert functional - set(parsed) == set(), "a FUNCTIONAL contract lost its kill directive"
    assert validate_kill_directives(text, ids, path=str(path)) == []


def test_the_i01_plan_is_reported_as_predating_the_grammar() -> None:
    """Non-vacuity for the validator: it must be capable of saying no.

    I01 was written before kill directives existed, so every FUNCTIONAL
    contract in it genuinely lacks one. A validator that returned `[]` here
    too would be proving nothing on the test above.
    """
    path = PLAN_DIR / "increment-01-plan-grammar-and-extractor.md"
    text = path.read_text(encoding="utf-8")
    ids = extract_plan_ids(text)

    diagnostics = validate_kill_directives(text, ids, path=str(path))

    assert diagnostics, "the validator found nothing in a plan that predates the grammar"
    assert {d.rule for d in diagnostics} == {"kill-directive-missing"}
    assert all(d.severity == FAIL for d in diagnostics)
    assert all(d.line > 0 for d in diagnostics), "every diagnostic must locate itself"


# ── Mutation-driven oracles (C4 follow-up to the SLICE2 sweep) ─────────────


def test_an_unclassed_contract_is_still_located() -> None:
    """Regression — the defect mutation testing exposed, not a gap in coverage.

    I01 makes the class bracket optional and defaults such an entry to
    FUNCTIONAL (`plan_ids.py:82-85`). This locator required the bracket, so an
    unclassed contract was invisible: its directive went unattributed and the
    contract was reported as declaring none. A false `kill-directive-missing`
    against a correct plan is worse than a miss — it teaches the operator to
    distrust the gate.
    """
    plan = _plan("  CT1: an unclassed contract, FUNCTIONAL by default.", "    kill: neutralise src/a.py::f")

    assert _validate(plan) == []


def test_parsing_continues_past_a_directive_it_cannot_attribute() -> None:
    """A stray directive must cost that directive, never the ones after it.

    Found by mutation testing: turning the skip into a stop survived, because
    no fixture had anything worth parsing *after* an unattributable line.
    """
    section = _section(
        "## SLICE1: a thing",
        "    kill: neutralise src/a.py::orphan",
        "CONTRACTS:",
        "  CT1 [FUNCTIONAL]: first.",
        "    kill: neutralise src/a.py::one",
        "  CT2 [FUNCTIONAL]: second.",
        "    kill: neutralise src/b.py::two",
    )

    directives = parse_kill_directives(_rec(section))

    assert sorted(directives) == ["CT1", "CT2"]


def test_a_stray_directive_never_invents_a_contract() -> None:
    """Found by mutation testing: seeding the cursor with `""` instead of None.

    An empty string is not None, so every stray directive would be filed under
    a phantom contract — and two of them would raise an ambiguity diagnostic
    for a contract that does not exist.
    """
    plan = _section(
        "## SLICE1: a thing",
        "    kill: neutralise src/a.py::strayone",
        "    kill: neutralise src/a.py::straytwo",
        "CONTRACTS:",
        "  CT1 [CONSTRAINT]: proven elsewhere.",
        "TESTS: tests/t.py",
    )

    assert [rule for rule, _ in _validate(plan)] == []


def test_validation_reports_every_offender_not_merely_the_first() -> None:
    """Found by mutation testing: four `continue`s survived becoming `break`.

    Every fixture had a single defect, so stopping at the first was
    indistinguishable from skipping it. A gate that reports one problem per run
    turns a five-minute fix into five round trips.
    """
    plan = _plan(
        "  CT1 [FUNCTIONAL]: a thing.",
        "    kil: neutralise src/a.py::f",
        "  CT2 [FUNCTIONAL]: another.",
        "    kill: neutralise src/b.py broken",
        "  CT3 [FUNCTIONAL]: a third with nothing at all.",
    )

    rules = sorted(rule for rule, _ in _validate(plan))

    assert rules == [
        "kill-directive-malformed",
        "kill-directive-missing",
        "kill-directive-missing",
        "kill-directive-near-miss",
    ]


def test_an_exempt_contract_does_not_stop_the_missing_scan() -> None:
    """The sharpest of the `continue`/`break` survivors, and the most dangerous.

    The exemption loop skips CONSTRAINT and PRESERVATION entries. Turning that
    skip into a stop means the first exempt contract silently switches the
    missing-directive check off for every contract after it — a gate that
    disables itself, which is the one failure this module exists to prevent.
    """
    plan = _plan(
        "  CT1 [CONSTRAINT]: exempt, and declared first on purpose.",
        "  CT2 [FUNCTIONAL]: declares no kill directive.",
    )

    assert [rule for rule, _ in _validate(plan)] == ["kill-directive-missing"]


def test_the_ambiguity_diagnostic_names_every_offending_line() -> None:
    """The `line` field can hold one number; the operator needs both.

    Found by mutation testing: the joined line list could be corrupted without
    any test noticing, leaving a message that says "2 directives" and points
    at one of them.
    """
    plan = _plan(
        "  CT1 [FUNCTIONAL]: a thing.",
        "    kill: neutralise src/a.py::first",
        "    kill: neutralise src/a.py::second",
    )
    ids = extract_plan_ids(plan)

    (diagnostic,) = validate_kill_directives(plan, ids, path="PLAN.md")

    assert diagnostic.rule == "kill-directive-ambiguous"
    assert "6" in diagnostic.message and "7" in diagnostic.message


def test_a_contract_merely_referenced_is_not_demanded_a_kill_directive() -> None:
    """The guard that makes the missing-rule safe, pinned because it is subtle.

    `ids.contracts` is every id *mentioned*, so a plan that cites another
    increment's contract in prose has that id in the set. Only
    `contract_class` tells a declaration from a citation, returning None for
    the latter. Without this the gate would demand kill directives from
    contracts that live in a different document.
    """
    plan = _plan(
        "  CT1 [FUNCTIONAL]: a thing, in the manner of CT999 from the other increment.",
        "    kill: neutralise src/a.py::f",
    )
    ids = extract_plan_ids(plan)

    assert "CT999" in ids.contracts, "precondition: a cited id is in the mention set"
    assert ids.contract_class("CT999") is None
    assert validate_kill_directives(plan, ids, path="PLAN.md") == []


def test_a_malformed_line_does_not_stop_the_scan() -> None:
    """Found by mutation testing: the skip after a malformed line.

    The earlier multi-defect fixture put the malformed line last, so stopping
    there cost nothing. Ordering it first is what makes the oracle real.
    """
    plan = _plan(
        "  CT1 [FUNCTIONAL]: a thing.",
        "    kill: neutralise src/a.py broken",
        "  CT2 [FUNCTIONAL]: another.",
        "    kil: neutralise src/b.py::g",
    )

    rules = sorted(rule for rule, _ in _validate(plan))

    assert rules == ["kill-directive-malformed", "kill-directive-missing", "kill-directive-near-miss"]


def test_a_well_formed_contract_does_not_stop_the_ambiguity_scan() -> None:
    """Found by mutation testing: the skip over contracts with one directive.

    Turning it into a stop means a single correct contract hides every
    duplicate declared after it — the self-disabling gate again, in the one
    rule whose whole job is to refuse ambiguity.
    """
    plan = _plan(
        "  CT1 [FUNCTIONAL]: correct, and declared first on purpose.",
        "    kill: neutralise src/a.py::f",
        "  CT2 [FUNCTIONAL]: ambiguous.",
        "    kill: neutralise src/b.py::first",
        "    kill: neutralise src/b.py::second",
    )

    assert [rule for rule, _ in _validate(plan)] == ["kill-directive-ambiguous"]


def test_the_ambiguity_message_lists_the_lines_in_a_readable_form() -> None:
    """Tightened after mutation testing: 'is 6 in the message' was too weak.

    A corrupted separator still leaves both digits present. The operator reads
    a line list, so the list itself is the contract.
    """
    plan = _plan(
        "  CT1 [FUNCTIONAL]: a thing.",
        "    kill: neutralise src/a.py::first",
        "    kill: neutralise src/a.py::second",
    )
    ids = extract_plan_ids(plan)

    (diagnostic,) = validate_kill_directives(plan, ids, path="PLAN.md")

    assert "lines 6, 7" in diagnostic.message
