"""PLAN S3 / CT6 — plan ID + verify-command extraction.

root=plan_ids class=C0/C0p claim=G5 path=T3,T3b
oracle=exact PlanIds tuple contents and ordering.
producer-kill-check=removing the _SLICE_RE pattern (or the _VERIFY_BLOCK_RE
pattern) makes the corresponding test below fail.

This is C0 by construction: ``extract_plan_ids`` is a pure function with no
composition root to boot. Per the tests-writing ladder a C0 is "incomplete
alone" for a product claim — the product claim here (harness pre-fills slice
IDs and runs plan-authored commands) is proved at C1 in a later slice, where
this function has a caller. What C0 *can* prove exhaustively is the parsing
contract, including the failure modes the caller depends on to stay advisory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop.plan_ids import PlanIds, extract_plan_ids

REPO_ROOT = Path(__file__).resolve().parents[1]


# ── the grammar, as a realistic plan fragment ──────────────────────────────

PLAN_FIXTURE = """\
# PLAN: example                        Plan-ID: PLAN-example

## 5. Step-by-step

## SLICE1: first slice

Traces-to: G1 · GAP1, GAP2 · CT1

## SLICE5a: inserted later

Traces-to: G2 · GAP12 · CT10, CT7b

## 6. Verification plan

| T# | CT# | class |
|---|---|---|
| T1 | CT1 | C0 |
| T6e | CT4 | C1 |

```verify
uv run pytest tests/test_plan_ids.py -q
# a comment line is not a command

uv run mypy src/fa/inner_loop/plan_ids.py
```
"""


class TestGrammar:
    """The happy path: every ID class and the command block."""

    def test_slices_include_lettered_suffix(self) -> None:
        ids = extract_plan_ids(PLAN_FIXTURE)
        assert ids.slices == ("SLICE1", "SLICE5a")

    def test_gaps_are_prefixed_and_ordered(self) -> None:
        ids = extract_plan_ids(PLAN_FIXTURE)
        # Document order, de-duplicated. GAP12 must not also yield GAP1.
        assert ids.gaps == ("GAP1", "GAP2", "GAP12")

    def test_contracts_do_not_truncate_two_digit_ids(self) -> None:
        """Kill-check for the \\b boundary: CT10 must not read as CT1."""
        ids = extract_plan_ids(PLAN_FIXTURE)
        # CT4 comes from the verification table further down the fixture.
        assert ids.contracts == ("CT1", "CT10", "CT7b", "CT4")

    @pytest.mark.parametrize(
        "text",
        [
            "IMPACT3 was assessed",
            "the ACT10 statute",
            "REDACTED CONTRACT7 terms",
        ],
        ids=["IMPACT3", "ACT10", "CONTRACT7"],
    )
    def test_ids_embedded_in_words_are_not_matched(self, text: str) -> None:
        """Kill-check for the LEADING \\b boundary.

        Without it, 'IMPACT3' yields a phantom CT3 and the harness would
        pre-fill a contract the plan never declared.
        """
        assert extract_plan_ids(text).contracts == ()

    def test_gap_ids_embedded_in_words_are_not_matched(self) -> None:
        assert extract_plan_ids("MINDTHEGAP4 here").gaps == ()

    def test_tests_extracted(self) -> None:
        ids = extract_plan_ids(PLAN_FIXTURE)
        assert ids.tests == ("T1", "T6e")

    def test_commands_from_verify_block_only(self) -> None:
        ids = extract_plan_ids(PLAN_FIXTURE)
        assert ids.commands == (
            "uv run pytest tests/test_plan_ids.py -q",
            "uv run mypy src/fa/inner_loop/plan_ids.py",
        )

    def test_comment_and_blank_lines_are_not_commands(self) -> None:
        """A '#' line inside a verify block must never reach a shell."""
        ids = extract_plan_ids(PLAN_FIXTURE)
        assert not any(c.startswith("#") for c in ids.commands)
        assert "" not in ids.commands


class TestTotality:
    """Absence is a valid result, never an exception (G8 / the anti-F6 rule)."""

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   \n\n  ",
            "# A plan with prose only and no grammar at all.",
            "```python\nprint('not a verify block')\n```",
            "S1 CT1 GAP1 T1",  # bare tokens, no headings/fences
        ],
        ids=["empty", "whitespace", "prose", "wrong-fence", "bare-tokens"],
    )
    def test_never_raises(self, text: str) -> None:
        result = extract_plan_ids(text)
        assert isinstance(result, PlanIds)

    def test_empty_input_is_fully_empty(self) -> None:
        assert extract_plan_ids("").is_empty

    @pytest.mark.parametrize("bad", [None, 123, b"bytes", [], {}])
    def test_non_string_input_degrades(self, bad: object) -> None:
        """A degraded upstream read must not become a crash here."""
        assert extract_plan_ids(bad).is_empty  # type: ignore[arg-type]

    def test_prose_never_yields_a_command(self) -> None:
        """F-1's boundary: only a fenced verify block produces a command.

        A plan that merely *mentions* a command in prose must not cause the
        harness to execute it. This is the seam that stops model-authored or
        incidental text from reaching a shell.
        """
        text = "Run `rm -rf /` to clean up.\n\n    uv run pytest\n"
        assert extract_plan_ids(text).commands == ()

    def test_python_fence_is_not_a_verify_block(self) -> None:
        assert extract_plan_ids("```python\nrm -rf /\n```").commands == ()


class TestDeterminism:
    """Ordering and immutability the callers rely on."""

    def test_document_order_is_stable(self) -> None:
        """Not set-ordered: slices[0] must mean 'first slice in the plan'."""
        text = "## SLICE9: later\n## SLICE2: earlier\n"
        assert extract_plan_ids(text).slices == ("SLICE9", "SLICE2")

    def test_duplicates_collapse_to_first_occurrence(self) -> None:
        text = "CT3 CT3 CT1 CT3"
        assert extract_plan_ids(text).contracts == ("CT3", "CT1")

    def test_order_survives_hash_randomization(self) -> None:
        """Kill-check for dict.fromkeys vs set().

        A set() de-dupe passes with few items but reorders once there are
        enough to spread across hash buckets, and PYTHONHASHSEED varies per
        interpreter run -- so the harness would pre-fill a different 'first
        slice' on different runs. Enough IDs here to make that deterministic
        to detect.
        """
        ids = [3, 1, 4, 1, 5, 9, 2, 6, 8, 7, 10, 11]
        text = " ".join(f"CT{n}" for n in ids)
        expected = tuple(f"CT{n}" for n in dict.fromkeys(ids))
        assert extract_plan_ids(text).contracts == expected

    def test_first_slice_is_the_first_in_document_order(self) -> None:
        text = "".join(f"## SLICE{n}: x\n" for n in [7, 3, 11, 1, 5, 9, 2, 8, 4, 10, 6])
        assert extract_plan_ids(text).slices[0] == "SLICE7"

    def test_result_fields_are_tuples(self) -> None:
        ids = extract_plan_ids(PLAN_FIXTURE)
        for value in (ids.slices, ids.gaps, ids.contracts, ids.tests, ids.commands):
            assert isinstance(value, tuple)

    def test_repeated_calls_agree(self) -> None:
        assert extract_plan_ids(PLAN_FIXTURE) == extract_plan_ids(PLAN_FIXTURE)


class TestAgainstRealPlan:
    """C0p-flavoured: run the grammar over the repo's own plan artifacts.

    This is the measurement S3 requires (conformance is scoped to plans
    authored under the current skills; legacy misses are recorded, not
    gating). It asserts only that extraction is total over real files —
    never that a legacy plan conforms.
    """

    def test_extraction_is_total_over_repo_plans(self) -> None:
        plans = sorted((REPO_ROOT / "worklogs" / "implementation-plans").glob("*.md"))
        plans += sorted((REPO_ROOT / "worklogs").glob("*/increments/increment-*.md"))
        # Asserted, not skipped: these artifacts are committed, so an empty
        # glob means the corpus moved and this measurement silently stopped
        # measuring anything. A skip here would be test theater.
        assert plans, "no plan artifacts found — the corpus path moved"
        for path in plans:
            result = extract_plan_ids(path.read_text(encoding="utf-8"))
            assert isinstance(result, PlanIds), path.name

    def test_this_plan_is_conforming(self) -> None:
        """The live increment must be parseable by its own extractor."""
        path = (
            REPO_ROOT
            / "worklogs"
            / "planning-topology-and-executable-contracts-loop"
            / "increments"
            / "increment-01-plan-grammar-and-extractor.md"
        )
        assert path.is_file(), f"increment artifact missing: {path}"
        ids = extract_plan_ids(path.read_text(encoding="utf-8"))
        assert "SLICE1" in ids.slices
        assert "CT1" in ids.contracts


# ── T3c: the grammar-collision hazard (plan review, 2026-09-07) ────────────


def test_grammar_example_is_indistinguishable_from_a_real_fence() -> None:
    """C0 — pins a REAL defect found in plan review, not a hypothetical.

    ``_extract_commands`` cannot tell a command list from a fenced example
    that documents the grammar. The slice-ceremony plan documented the
    ```verify grammar inside a ````text wrapper; the extractor returned that
    example's two commands and nothing else, because §6 had no fence of its
    own. S6 ("the harness runs the plan's commands") would therefore have run
    S3's self-test, passed, and verified nothing about the slice under test.

    This is not fixed in code: nesting depth is a markdown-authoring
    convention, and teaching the extractor to skip examples would need it to
    parse nested fences -- more machinery than the risk warrants. It is fixed
    by CONVENTION plus this test, which documents the trap for the next author.
    """
    doc = "\n".join(
        [
            "Grammar, documented for plan authors:",
            "",
            "````text",
            "```verify",
            "uv run pytest tests/test_example.py -q",
            "```",
            "````",
        ]
    )
    ids = extract_plan_ids(doc)
    assert ids.commands == ("uv run pytest tests/test_example.py -q",), (
        "documented behaviour: a fenced EXAMPLE is still extracted as a real "
        "command. If this ever changes, the plan convention can be relaxed."
    )


def test_real_plan_yields_its_own_verification_commands() -> None:
    """C1 — the live plan must expose runnable commands, not just an example.

    Kill-check: delete the ```verify block from the plan's §6 and this fails,
    which is exactly the state the review found.
    """
    plan = (
        Path(__file__).resolve().parents[1]
        / "worklogs"
        / "planning-topology-and-executable-contracts-loop"
        / "increments"
        / "increment-01-plan-grammar-and-extractor.md"
    )
    if not plan.is_file():
        # The plan is an artifact of one feature branch. Absence is not an
        # extractor failure, so there is nothing to assert -- returning early
        # keeps this from becoming a tautological assertion
        # (FA-AUTHORING-V11-PLACEHOLDER-ASSERT).
        return
    ids = extract_plan_ids(plan.read_text(encoding="utf-8"))
    # The increment's verify fences ARE its real commands; there is no fenced
    # grammar example in it to strip, so no filter is needed.
    real = list(ids.commands)
    assert real, "the increment must carry a verify fence with runnable commands"
    assert any("ruff" in c for c in real), "static checks belong in the plan's command list"


# ── SLICE1: per-slice records (CT2/CT5/CT6/CT7) + reader-input (CT11) ──────

RECORD_FIXTURE = """\
# INCREMENT I9: example

## SLICE1: first
STEPS: prescriptive
INTENT: do the first thing.
CONTRACTS:
  CT1 [FUNCTIONAL]: it works
  CT2 [CONSTRAINT]: identical error shape
  CT3: unclassed defaults
TESTS: tests/test_first.py  (NEW - author it)
```verify
uv run pytest tests/test_first.py -q
```
- [ ] STEP1: edit the file (exit: green)

## SLICE2: second
STEPS: outcome
INTENT: do the second thing.
CONTRACTS:
  CT4 [PRESERVATION]: existing stays green
TESTS: tests/test_second.py
```verify
uv run pytest tests/test_second.py -q
```
"""


class TestSliceRecords:
    def test_slices_come_from_records(self) -> None:
        ids = extract_plan_ids(RECORD_FIXTURE)
        assert ids.slices == ("SLICE1", "SLICE2")
        assert [r.slice_id for r in ids.slice_records] == ["SLICE1", "SLICE2"]

    def test_contract_classes_and_default(self) -> None:
        rec = extract_plan_ids(RECORD_FIXTURE).slice_records[0]
        got = {cid: cls for cid, cls, _ in rec.contracts}
        assert got == {"CT1": "FUNCTIONAL", "CT2": "CONSTRAINT", "CT3": "FUNCTIONAL"}

    def test_test_paths_stop_at_paren_note(self) -> None:
        rec = extract_plan_ids(RECORD_FIXTURE).slice_records[0]
        assert rec.test_paths == ("tests/test_first.py",)

    def test_steps_mode_default_and_explicit(self) -> None:
        ids = extract_plan_ids(RECORD_FIXTURE)
        assert ids.slice_records[0].steps_mode == "prescriptive"
        assert ids.slice_records[1].steps_mode == "outcome"

    def test_record_commands_are_per_slice(self) -> None:
        ids = extract_plan_ids(RECORD_FIXTURE)
        assert ids.slice_records[0].commands == ("uv run pytest tests/test_first.py -q",)
        assert ids.slice_records[1].commands == ("uv run pytest tests/test_second.py -q",)

    def test_section_span_excludes_next_slice(self) -> None:
        rec = extract_plan_ids(RECORD_FIXTURE).slice_records[0]
        assert rec.section.startswith("## SLICE1:")
        assert "## SLICE2" not in rec.section

    def test_intent_captured(self) -> None:
        rec = extract_plan_ids(RECORD_FIXTURE).slice_records[0]
        assert rec.intent == "do the first thing."

    def test_flat_fields_retained(self) -> None:
        ids = extract_plan_ids(RECORD_FIXTURE)
        # CT4c: flat commands = concat of slices' commands, document order.
        assert ids.commands == (
            "uv run pytest tests/test_first.py -q",
            "uv run pytest tests/test_second.py -q",
        )
        assert ids.contracts == ("CT1", "CT2", "CT3", "CT4")

    def test_workflow_controller_reader_input_resolves(self) -> None:
        # workflow_controller.py:332 and :461 read exactly this attribute.
        assert extract_plan_ids(RECORD_FIXTURE).slices
        assert extract_plan_ids("### Step S1: legacy").slices == ()
