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

import re
from pathlib import Path

import pytest

from fa.inner_loop.plan_ids import PlanIds, canonical_slice_id, extract_plan_ids

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


# ── SLICE2: per-slice accessors over the records ──────────────────────────
#
# root=plan_ids class=C0/C0p claim=CT3,CT4,CT4b,CT4c,CT16-CT20,CT33
# oracle=exact tuples, exact section spans, exact contract text.
# producer-kill-check: each test below names the production mechanism whose
# removal makes it fail. A parser has no `output.emit()`, so the producer is
# the parsing rule itself; "the test fails if the rule is deleted" is the
# same proof obligation in a different shape.
#
# C0 is "incomplete alone" for a product claim. The product claim for the new
# accessors is owned by I02 (CT19/CT20/CT33 name it as their consumer), which
# is not built; SD-B forbids shipping an accessor without a named consumer
# increment, and names it. What IS live today is `.slices`, read at
# workflow_controller.py:332 and :461 — so the C1 live-path proof below
# asserts that the span change does not disturb that reader.

#: Prologue block, two slices, and an increment-level tail that carries its
#: own verify block. Before CT16 the tail belonged to SLICE2.
SPAN_FIXTURE = """\
# PLAN: span

```verify
uv run ruff check .
```

## SLICE1: first
STEPS: prescriptive
INTENT: do the first thing.
CONTRACTS:
  CT1 [FUNCTIONAL]: the first rule holds.
    Catches: the rationale that must survive the join.
  CT2 [CONSTRAINT]: the second rule holds.
TESTS: tests/test_first.py  (NEW - author it; absent at 2f6b8c1)
```verify
uv run pytest tests/test_first.py -q
uv run pytest tests/test_first.py -q
```
- [ ] STEP1: cite CT9 in step prose (exit: CT1 green.)

## SLICE2: second
STEPS: outcome
INTENT: do the second thing.
CONTRACTS:
  CT3 [PRESERVATION]: the third rule holds.
SHIPPED: abc1234
  CT8 [FUNCTIONAL]: declared after a column-zero line, so not a contract.
TESTS: tests/test_second.py
```verify
uv run pytest tests/test_second.py -q
```

## Increment definition of done
```verify
uv run pytest -q
```
"""


class TestSectionSpan:
    """CT16 — a slice section ends at the next heading of depth <= its own."""

    def test_last_slice_no_longer_absorbs_the_increment_level_tail(self) -> None:
        # producer-kill-check: revert the terminator in `_slice_spans` to
        # "next slice heading only" and this fails.
        rec = extract_plan_ids(SPAN_FIXTURE).slice_records[-1]
        assert rec.slice_id == "SLICE2"
        assert "## Increment definition of done" not in rec.section
        assert rec.section.rstrip().endswith("```")

    def test_terminator_depth_is_read_from_the_matched_heading(self) -> None:
        """Kill-check for a hardcoded `^#{1,2}` terminator.

        `_SLICE_RE` admits `##`..`####`. For a `###` slice the terminator must
        be depth <= 3, so a sibling `### Notes` ends it. A fixed `^#{1,2}`
        would run straight through and swallow the sibling.
        """
        text = "### SLICE1: deep\nbody\n\n### Notes\nnot mine\n"
        rec = extract_plan_ids(text).slice_records[0]
        assert "### Notes" not in rec.section
        assert "not mine" not in rec.section

    def test_a_deeper_heading_stays_inside_the_section(self) -> None:
        """The converse kill-check: depth <= own, not "any heading".

        A `####` subsection belongs to the `###` slice that introduces it.
        A terminator of "any heading" would truncate the slice at its own
        first subsection — which is how `## Grounding`-style subsections get
        lost.
        """
        text = "### SLICE1: deep\n#### Grounding\nmine\n\n### Notes\nnot mine\n"
        rec = extract_plan_ids(text).slice_records[0]
        assert "#### Grounding" in rec.section
        assert "mine" in rec.section
        assert "not mine" not in rec.section

    def test_a_slice_heading_terminates_regardless_of_depth(self) -> None:
        """Preservation: sections never overlap.

        Depth <= own alone would let a `### SLICE2` nest inside a `## SLICE1`,
        so one command would belong to two records and the CT4c partition
        would double-count. This guarantee predates CT16 and must survive it.
        """
        text = "## SLICE1: outer\nmine\n### SLICE2: inner\nnot mine\n"
        recs = extract_plan_ids(text).slice_records
        assert [r.slice_id for r in recs] == ["SLICE1", "SLICE2"]
        assert "not mine" not in recs[0].section

    def test_the_live_increment_last_slice_is_bounded(self) -> None:
        path = (
            REPO_ROOT
            / "worklogs"
            / "planning-topology-and-executable-contracts-loop"
            / "increments"
            / "increment-01-plan-grammar-and-extractor.md"
        )
        assert path.is_file(), f"increment artifact missing: {path}"
        rec = extract_plan_ids(path.read_text(encoding="utf-8")).slice_records[-1]
        for heading in ("## Increment definition of done", "## Out of scope", "## Hand-off to I02"):
            assert heading not in rec.section, heading


class TestContractsBlock:
    """CT17/CT18 — declaration is scoped to the block, entry text is whole."""

    def test_a_contract_id_in_step_prose_is_not_a_contract(self) -> None:
        # producer-kill-check: drop the CONTRACTS:-block scoping in
        # `_section_contracts` and CT9 reappears.
        rec = extract_plan_ids(SPAN_FIXTURE).slice_records[0]
        assert [cid for cid, _, _ in rec.contracts] == ["CT1", "CT2"]

    def test_a_column_zero_line_ends_the_block_even_if_unknown(self) -> None:
        """Kill-check for a field-name allowlist.

        `SHIPPED:` is not a plan field an allowlist would have listed, and it
        was added to the grammar after the parser. Indentation is the only
        terminator precisely so that the next new field cannot silently
        extend the block.
        """
        rec = extract_plan_ids(SPAN_FIXTURE).slice_records[1]
        assert [cid for cid, _, _ in rec.contracts] == ["CT3"]

    def test_contract_text_joins_continuation_lines(self) -> None:
        # producer-kill-check: restore `line.split("]:", 1)[1]` and the
        # Catches: sentence vanishes.
        rec = extract_plan_ids(SPAN_FIXTURE).slice_records[0]
        text = {cid: body for cid, _, body in rec.contracts}["CT1"]
        assert text == "the first rule holds. Catches: the rationale that must survive the join."

    def test_class_is_read_from_the_entry_first_line_only(self) -> None:
        """A bracketed class inside a continuation must not re-class or split.

        This is CT18's first defect: an illustrative `CT3 [CONSTRAINT]` quoted
        inside CT2's explanation used to become a second, differently-classed
        contract of the slice.
        """
        text = (
            "## SLICE1: x\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: outer rule.\n"
            "    For example CT3 [CONSTRAINT]: an illustration, not a declaration.\n"
            "TESTS: tests/t.py\n"
        )
        rec = extract_plan_ids(text).slice_records[0]
        assert [(cid, cls) for cid, cls, _ in rec.contracts] == [("CT1", "FUNCTIONAL")]

    def test_unclassed_entry_still_defaults_to_functional(self) -> None:
        rec = extract_plan_ids(RECORD_FIXTURE).slice_records[0]
        assert {cid: cls for cid, cls, _ in rec.contracts} == {
            "CT1": "FUNCTIONAL",
            "CT2": "CONSTRAINT",
            "CT3": "FUNCTIONAL",
        }


class TestAccessors:
    """CT3/CT4/CT19/CT20/CT33 — the read API I02 consumes."""

    def test_commands_for_returns_only_that_slice_deduped(self) -> None:
        ids = extract_plan_ids(SPAN_FIXTURE)
        assert ids.commands_for("SLICE1") == ("uv run pytest tests/test_first.py -q",)
        assert ids.commands_for("SLICE2") == ("uv run pytest tests/test_second.py -q",)

    def test_section_returns_exactly_that_slice(self) -> None:
        ids = extract_plan_ids(SPAN_FIXTURE)
        assert ids.section("SLICE1").startswith("## SLICE1: first")
        assert "## SLICE2" not in ids.section("SLICE1")

    def test_unknown_ids_are_empty_not_raising(self) -> None:
        ids = extract_plan_ids(SPAN_FIXTURE)
        assert ids.commands_for("SLICE99") == ()
        assert ids.section("SLICE99") == ""
        assert ids.tests_for("SLICE99") == ()
        assert ids.contract_class("CT99") is None

    def test_contract_class_resolves_across_slices(self) -> None:
        ids = extract_plan_ids(SPAN_FIXTURE)
        assert ids.contract_class("CT1") == "FUNCTIONAL"
        assert ids.contract_class("CT2") == "CONSTRAINT"
        assert ids.contract_class("CT3") == "PRESERVATION"
        assert ids.contract_class("CT8") is None

    def test_duplicate_declaration_is_deterministic_first_wins(self) -> None:
        text = (
            "## SLICE1: a\nCONTRACTS:\n  CT5 [FUNCTIONAL]: first.\nTESTS: tests/a.py\n"
            "## SLICE2: b\nCONTRACTS:\n  CT5 [CONSTRAINT]: second.\nTESTS: tests/b.py\n"
        )
        assert extract_plan_ids(text).contract_class("CT5") == "FUNCTIONAL"

    def test_tests_for_returns_the_slice_paths(self) -> None:
        ids = extract_plan_ids(SPAN_FIXTURE)
        assert ids.tests_for("SLICE1") == ("tests/test_first.py",)
        assert ids.tests_for("SLICE2") == ("tests/test_second.py",)

    def test_tests_note_is_preserved_verbatim(self) -> None:
        # CT33. I02's fail-before filter keys on it and has no other source.
        recs = extract_plan_ids(SPAN_FIXTURE).slice_records
        assert recs[0].tests_note == "(NEW - author it; absent at 2f6b8c1)"
        assert recs[1].tests_note == ""


class TestCommandOwnership:
    """CT4b/CT4c + Q35 — ownership of every verify command is total."""

    def test_unowned_commands_are_reachable_from_plan_commands(self) -> None:
        ids = extract_plan_ids(SPAN_FIXTURE)
        assert ids.plan_commands == ("uv run ruff check .", "uv run pytest -q")
        assert ids.commands_for(None) == ids.plan_commands

    def test_no_sentinel_slice_is_invented_for_them(self) -> None:
        # CT4b: SliceRecord is not widened and no fake id appears.
        ids = extract_plan_ids(SPAN_FIXTURE)
        assert [r.slice_id for r in ids.slice_records] == ["SLICE1", "SLICE2"]
        assert "uv run ruff check ." not in [c for r in ids.slice_records for c in r.commands]

    def test_ownership_partitions_the_flat_field(self) -> None:
        """Q35: the exact identity, not a vacuous superset.

        A bare `flat >= concat` assertion passes when `plan_commands` is empty
        and tolerates junk in the flat field. This one fails if any command is
        dropped, duplicated into the wrong slice, or misattributed.
        """
        ids = extract_plan_ids(SPAN_FIXTURE)
        owned = {c for r in ids.slice_records for c in r.commands}
        assert set(ids.commands) == set(ids.plan_commands) | owned

    def test_flat_commands_stay_a_strict_superset_on_the_live_plan(self) -> None:
        """CT4c preservation, measured on the real artifact."""
        path = (
            REPO_ROOT
            / "worklogs"
            / "planning-topology-and-executable-contracts-loop"
            / "increments"
            / "increment-01-plan-grammar-and-extractor.md"
        )
        ids = extract_plan_ids(path.read_text(encoding="utf-8"))
        concat = [c for r in ids.slice_records for c in r.commands]
        assert set(ids.commands) >= set(concat)
        assert list(ids.commands) != concat, "flat field was re-derived from the slices"
        assert set(ids.commands) == set(ids.plan_commands) | set(concat)


class TestLivePathUndisturbed:
    """C1 — the only shipped consumer of this module must not move."""

    def test_workflow_controller_still_sees_every_declared_slice(self) -> None:
        """CT11 preservation under CT16.

        workflow_controller.py:332 returns early on an empty `.slices`, so a
        span change that dropped a slice would silently disable the per-slice
        coverage gate rather than fail loudly. `.slices` is derived from
        headings, not spans; this pins that.
        """
        ids = extract_plan_ids(SPAN_FIXTURE)
        assert ids.slices == ("SLICE1", "SLICE2")
        path = (
            REPO_ROOT
            / "worklogs"
            / "planning-topology-and-executable-contracts-loop"
            / "increments"
            / "increment-01-plan-grammar-and-extractor.md"
        )
        text = path.read_text(encoding="utf-8")
        live = extract_plan_ids(text)

        # A differential oracle, not a snapshot. An earlier version hardcoded
        # the slice list of the live increment, so it went red every time the
        # plan legitimately gained a slice -- which trains the next agent to
        # edit the expectation rather than read the failure. What the gate
        # actually needs is that `.slices` accounts for every heading in the
        # document, checked against a scan written independently of the
        # parser, plus that it is never empty (`workflow_controller.py:332`
        # returns early on empty and the coverage gate silently no-ops).
        from_headings = tuple(
            f"SLICE{m.group(1)}" for m in re.finditer(r"^#{2,4} +SLICE(\d+[a-z]?):", text, re.MULTILINE)
        )
        assert from_headings, "fixture lost: the live increment declares no slices"
        assert live.slices == from_headings


class TestMutationHardening:
    """C4 follow-up — oracles added for mutants that survived the first sweep.

    Each test names the mutation it kills. These are not implementation
    mirrors: every one asserts a behaviour a plan author can observe, and the
    sweep is what revealed the fixture gap that hid it.
    """

    def test_nested_slice_does_not_leak_into_its_parent(self) -> None:
        """Kills `matches[i + 1]` -> `matches[i - 1]` in `_slice_spans`.

        Two slices cannot distinguish the two indices: `matches[-1]` is the
        next slice. It takes three, with a *deeper* middle one, for the wrong
        index to make SLICE1 swallow SLICE2.
        """
        text = "## SLICE1: outer\nmine\n### SLICE2: nested\nnot mine\n## SLICE3: last\nalso not\n"
        recs = extract_plan_ids(text).slice_records
        assert [r.slice_id for r in recs] == ["SLICE1", "SLICE2", "SLICE3"]
        assert "### SLICE2" not in recs[0].section
        assert "not mine" not in recs[0].section

    def test_a_plan_opening_with_a_verify_fence_keeps_it(self) -> None:
        """Kills `cursor = 0` -> `cursor = 1` in `_unowned_commands`.

        Dropping one character is invisible unless the very first byte of the
        document is part of a fence.
        """
        text = "```verify\nuv run ruff check .\n```\n\n## SLICE1: x\nTESTS: tests/t.py\n"
        assert extract_plan_ids(text).plan_commands == ("uv run ruff check .",)

    def test_a_single_space_is_enough_indentation(self) -> None:
        """Kills `line[:1].isspace()` -> `line[:2].isspace()` in `_contracts_block`.

        CT17 says indentation is the terminator — any indentation. Reading two
        characters misclassifies a one-space entry as a column-zero line and
        truncates the block before it.
        """
        text = "## SLICE1: x\nCONTRACTS:\n CT1 [FUNCTIONAL]: shallow but indented.\nTESTS: tests/t.py\n"
        rec = extract_plan_ids(text).slice_records[0]
        assert [cid for cid, _, _ in rec.contracts] == ["CT1"]

    def test_a_hash_note_is_a_tests_note_too(self) -> None:
        """Kills the `"#"` literal in the TESTS:-note pattern."""
        text = "## SLICE1: x\nTESTS: tests/a.py  # run under -k slow\n"
        rec = extract_plan_ids(text).slice_records[0]
        assert rec.test_paths == ("tests/a.py",)
        assert rec.tests_note == "# run under -k slow"

    def test_absent_fields_fall_back_to_their_documented_defaults(self) -> None:
        """Kills the `""` / `"prescriptive"` fallbacks in `_build_record`.

        RECORD_FIXTURE states every field explicitly, so the `else` arms were
        never evaluated and could be changed to anything at all.
        """
        rec = extract_plan_ids("## SLICE1: bare\n- [ ] STEP1: do (exit: x)\n").slice_records[0]
        assert rec.intent == ""
        assert rec.steps_mode == "prescriptive"
        assert rec.test_paths == ()
        assert rec.tests_note == ""
        assert rec.contracts == ()

    def test_a_duplicate_id_inside_one_slice_keeps_the_first(self) -> None:
        """Kills `seen.add(cid)` -> `seen.add(None)`.

        The cross-slice duplicate test exercises `contract_class`'s scan
        order, not the per-slice de-duplication set.
        """
        text = (
            "## SLICE1: x\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: the first one.\n"
            "  CT1 [CONSTRAINT]: the second one.\n"
            "  CT2 [PRESERVATION]: a later, distinct one.\n"
            "TESTS: tests/t.py\n"
        )
        rec = extract_plan_ids(text).slice_records[0]
        # The trailing CT2 also kills `continue` -> `break`: skipping a
        # duplicate must not abandon the rest of the block.
        assert [(cid, cls) for cid, cls, _ in rec.contracts] == [
            ("CT1", "FUNCTIONAL"),
            ("CT2", "PRESERVATION"),
        ]

    def test_a_line_at_entry_indent_closes_the_entry(self) -> None:
        """Kills `<= indent` -> `< indent` and the `len(line) + len(...)` flip.

        Only a *more* indented line continues an entry. A line at the same
        indent is a sibling, and joining it would merge two contracts' text.
        """
        text = (
            "## SLICE1: x\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: the rule.\n"
            "    deeper, so part of CT1.\n"
            "  stray prose at entry indent.\n"
            "TESTS: tests/t.py\n"
        )
        rec = extract_plan_ids(text).slice_records[0]
        assert [body for _, _, body in rec.contracts] == ["the rule. deeper, so part of CT1."]

    def test_an_entry_may_start_its_text_on_the_continuation_line(self) -> None:
        """Kills the `if p` filter in the join — it would leave a leading space."""
        text = "## SLICE1: x\nCONTRACTS:\n  CT1 [FUNCTIONAL]:\n    all of it is here.\nTESTS: tests/t.py\n"
        rec = extract_plan_ids(text).slice_records[0]
        assert [body for _, _, body in rec.contracts] == ["all of it is here."]

    def test_a_deeper_entry_is_a_declaration_not_continuation_text(self) -> None:
        """Kills the four `stop` mutants in `_section_contracts`.

        An indented line that *itself* begins `CT<n> [CLASS]:` is an entry
        wherever it sits, so it must not also be folded into the previous
        entry's text. Three entries are needed: with two, `starts[-1]` and
        `starts[position + 1]` are the same element.
        """
        text = (
            "## SLICE1: x\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: first.\n"
            "    CT2 [CONSTRAINT]: deeper, still its own declaration.\n"
            "  CT3 [PRESERVATION]: third.\n"
            "    CT4 [FUNCTIONAL]: deeper, and last.\n"
            "TESTS: tests/t.py\n"
        )
        rec = extract_plan_ids(text).slice_records[0]
        # A deeper entry in the *middle* and a deeper entry at the *end*
        # exercise different arms of the stop index; the last-but-one entry
        # is the only position where an off-by-one in the guard shows up.
        assert [(cid, body) for cid, _, body in rec.contracts] == [
            ("CT1", "first."),
            ("CT2", "deeper, still its own declaration."),
            ("CT3", "third."),
            ("CT4", "deeper, and last."),
        ]

    def test_a_blank_line_does_not_truncate_an_entry(self) -> None:
        """Kills `continue` -> `break` on the blank-line skip.

        A blank line inside the block is visual spacing, not a terminator;
        only indentation terminates (CT17). Pinned because the grammar does
        not say so in words.
        """
        text = (
            "## SLICE1: x\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: opening clause.\n"
            "\n"
            "    Catches: the clause after the blank line.\n"
            "TESTS: tests/t.py\n"
        )
        rec = extract_plan_ids(text).slice_records[0]
        assert [body for _, _, body in rec.contracts] == ["opening clause. Catches: the clause after the blank line."]

    def test_accessors_accept_either_id_grammar(self) -> None:
        """`_record` canonicalises, so a legacy `S<n>` token resolves.

        The accessors are the first callers of `canonical_slice_id` inside
        this module; without this the mapping is reachable only through the
        workflow controller.
        """
        ids = extract_plan_ids(SPAN_FIXTURE)
        assert ids.commands_for("S1") == ids.commands_for("SLICE1")
        assert ids.tests_for("S2") == ("tests/test_second.py",)
        assert ids.section("S1").startswith("## SLICE1: first")
        assert ids.commands_for("SLICE1") != ()

    def test_test_path_tokens_are_stripped_of_list_punctuation(self) -> None:
        """Kills `t.strip(",;")` -> `strip(None)` / a corrupted strip set."""
        rec = extract_plan_ids("## SLICE1: x\nTESTS: tests/a.py, tests/b.py;\n").slice_records[0]
        assert rec.test_paths == ("tests/a.py", "tests/b.py")

    def test_only_list_punctuation_is_stripped_from_a_path(self) -> None:
        """The strip set is `,;` exactly — letters at a token edge survive.

        Kills a widened strip set. A path is an opaque token to this parser;
        trimming anything but the separators the grammar allows would corrupt
        a legitimate filename.
        """
        rec = extract_plan_ids("## SLICE1: x\nTESTS: tests/fooX, tests/b.py\n").slice_records[0]
        assert rec.test_paths == ("tests/fooX", "tests/b.py")


class TestCanonicalSliceId:
    """The id mapping the accessors depend on — `_record` canonicalises first.

    Reached only through the workflow controller before SLICE2, so its
    branches were never pinned. Each case names the mutation it kills.
    """

    def test_lowercase_prefix_is_canonicalised(self) -> None:
        # kills `"slice"` -> `"SLICE"` (never true against a lowered string).
        assert canonical_slice_id("slice1") == "SLICE1"
        assert canonical_slice_id("Slice2b") == "SLICE2b"

    def test_legacy_short_form_is_canonicalised(self) -> None:
        assert canonical_slice_id("S1") == "SLICE1"
        assert canonical_slice_id("S5a") == "SLICE5a"

    def test_a_non_slice_token_is_returned_unchanged(self) -> None:
        # kills the two `and` -> `or` flips: "step" must not become
        # "SLICEtep", and "X9" must not become "SLICE9".
        assert canonical_slice_id("step") == "step"
        assert canonical_slice_id("X9") == "X9"

    def test_a_bare_s_does_not_index_past_the_end(self) -> None:
        # kills `len(text) > 1` -> `>= 1`, which raises IndexError instead.
        assert canonical_slice_id("s") == "s"
        assert canonical_slice_id("") == ""
