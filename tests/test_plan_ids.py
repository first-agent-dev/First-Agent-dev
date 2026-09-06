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

### Step S1: first slice

Traces-to: G1 · GAP1, GAP2 · CT1

### Step S5a: inserted later

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
        assert ids.slices == ("S1", "S5a")

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
        text = "### Step S9: later\n### Step S2: earlier\n"
        assert extract_plan_ids(text).slices == ("S9", "S2")

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
        text = "".join(f"### Step S{n}: x\n" for n in [7, 3, 11, 1, 5, 9, 2, 8, 4, 10, 6])
        assert extract_plan_ids(text).slices[0] == "S7"

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
        if not plans:
            pytest.skip("no plan artifacts in this checkout")
        for path in plans:
            result = extract_plan_ids(path.read_text(encoding="utf-8"))
            assert isinstance(result, PlanIds), path.name

    def test_this_plan_is_conforming(self) -> None:
        """The slice-ceremony plan must be parseable by its own extractor."""
        path = REPO_ROOT / "worklogs" / "implementation-plans" / "PLAN-slice-ceremony-harness-enforcement.md"
        if not path.exists():
            pytest.skip("plan artifact not present")
        ids = extract_plan_ids(path.read_text(encoding="utf-8"))
        assert "S1" in ids.slices
        assert "CT1" in ids.contracts
        assert "GAP1" in ids.gaps
