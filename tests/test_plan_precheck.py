"""I01/SLICE3 — the plan pre-check: a static lint over an increment artifact.

root=plan_ids.precheck class=C0 claim=CT8,CT9,CT10,CT25,CT26,CT27,CT34,CT35
oracle=exact rule id, severity and line per diagnostic — never "something was
reported".
producer-kill-check: each test names the rule function whose deletion makes it
fail. A linter's producer is the rule, and a rule that no test can delete is a
rule nobody is relying on.

C0 by construction: `precheck` is pure, total and stdlib-only, with no
composition root to boot. Under SD-C that is stated, not assumed — I01 ships no
live-path test deliberately and I02 is named as the increment that adds one
(`notes/i02-handoff-verify-gate.md` §7). What C0 proves exhaustively here is
that every drift mode this project has actually observed produces a named,
located diagnostic rather than silence, which is the whole point of the gate.
"""

from __future__ import annotations

from pathlib import Path

from fa.inner_loop.plan_ids import precheck

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / "tests" / "data" / "plan-drift-corpus"

GOOD = """\
# Increment 99

## SLICE1: first
STEPS: prescriptive
DEPS: —
INTENT: do the first thing.
CONTRACTS:
  CT1 [FUNCTIONAL]: the first rule holds.
TESTS: tests/test_first.py
```verify
uv run pytest tests/test_first.py -q
```
- [ ] STEP1: edit the file (exit: tests/test_first.py passes.)

## SLICE2: second
STEPS: outcome
DEPS: SLICE1
INTENT: do the second thing.
CONTRACTS:
  CT2 [CONSTRAINT]: the second rule holds.
    Catches: the rationale.
TESTS: tests/test_second.py
```verify
uv run pytest tests/test_second.py -q
```

## Increment definition of done
- [ ] everything above is green.
"""


def _rules(text: str, **kw: object) -> list[str]:
    return [d.rule for d in precheck(text, **kw).diagnostics]  # type: ignore[arg-type]


class TestRunner:
    """STEP1 — aggregation, totality, ordering."""

    def test_a_wellformed_increment_passes_clean(self) -> None:
        report = precheck(GOOD)
        assert report.diagnostics == ()
        assert report.ok is True

    def test_an_empty_plan_passes(self) -> None:
        for text in ("", "   \n\n", "# just a title\n"):
            report = precheck(text)
            assert report.ok is True, text
            assert report.diagnostics == (), text

    def test_it_never_raises_on_garbage(self) -> None:
        """Totality must be reached through every rule, not just the cheap ones.

        An earlier draft passed a weaker version of this test while
        `contract-declaration-lost` raised TypeError, because none of the
        garbage inputs carried a parsed contract. Each case below is shaped to
        reach a different rule with hostile input.
        """
        cases = [
            "\x00\x01",
            "## SLICE: no number\n",
            "#" * 400,
            "CONTRACTS:\n" * 50,
            # reaches CT8/CT34/CT35: a real slice carrying real contracts
            "## SLICE1: a\nCONTRACTS:\n  CT1 [FUNCTIONAL]: x.\n  CT1 [CONSTRAINT]: y.\n",
            # reaches CT9: prescriptive with a malformed step
            "## SLICE1: a\nSTEPS: prescriptive\nTESTS: t.py\n- [ ] STEP1:\n",
            # reaches CT10: deps naming nonsense
            "## SLICE1: a\nDEPS: SLICE, , SLICE1, ---\nTESTS: t.py\n",
            # reaches CT26/CT27 together
            "## slice 1: x\nCT9999 and CT1a\n",
            # no trailing newline, CRLF, and a lone heading
            "## SLICE1: a\r\nCONTRACTS:\r\n  CT1 [FUNCTIONAL]: x.",
        ]
        for text in cases:
            report = precheck(text)
            assert isinstance(report.ok, bool), text
            assert report.render() is not None, text

    def test_a_trailing_increment_section_is_not_a_violation(self) -> None:
        """CT16 made this legal; the pre-check must not re-flag it.

        Before SLICE2 the last slice absorbed the increment-level sections.
        That is now correct parsing, so a plan that uses them must stay clean
        — otherwise the lint would punish the shape the grammar mandates.
        """
        assert precheck(GOOD).ok is True
        assert "## Increment definition of done" in GOOD

    def test_every_diagnostic_carries_a_located_rule(self) -> None:
        """CT25 — `file:line` and a rule id on each, not a bare message."""
        text = GOOD.replace("TESTS: tests/test_first.py\n", "")
        report = precheck(text, path="worklogs/x.md")
        assert report.diagnostics
        for d in report.diagnostics:
            assert d.rule
            assert d.severity in ("FAIL", "WARN")
            assert d.line >= 1
            assert d.location == f"worklogs/x.md:{d.line}"
            assert text.splitlines()[d.line - 1] is not None

    def test_all_violations_are_returned_in_one_pass(self) -> None:
        """CT25 — three distinct seeded violations report three rules."""
        text = (
            "## SLICE1: a\nSTEPS: prescriptive\nDEPS: SLICE9\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: rule.\n"
            "- [ ] STEP1: do a thing with no exit predicate\n"
            "\n## SLICE2: b\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n"
            "  CT2 [FUNCTIONAL]: rule.\nTESTS: tests/b.py\n"
        )
        rules = set(_rules(text))
        assert {"slice-without-tests", "step-without-exit", "deps-undefined-slice"} <= rules

    def test_diagnostics_are_ordered_by_line(self) -> None:
        text = (
            "## SLICE1: a\nSTEPS: prescriptive\nDEPS: —\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: rule.\n"
            "- [ ] STEP1: no exit here\n"
            "\n## SLICE2: b\nSTEPS: prescriptive\nDEPS: —\nCONTRACTS:\n"
            "  CT2 [FUNCTIONAL]: rule.\n"
            "- [ ] STEP1: nor here\n"
        )
        lines = [d.line for d in precheck(text).diagnostics]
        assert lines == sorted(lines)


class TestSliceRules:
    def test_contracts_without_tests_fail(self) -> None:
        """CT8. producer-kill-check: delete `_rule_slice_without_tests`."""
        text = "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n  CT1 [FUNCTIONAL]: rule.\n"
        report = precheck(text)
        hit = [d for d in report.diagnostics if d.rule == "slice-without-tests"]
        assert len(hit) == 1
        assert hit[0].severity == "FAIL"
        assert hit[0].line == 1
        assert report.ok is False

    def test_a_slice_with_no_contracts_needs_no_tests(self) -> None:
        """The rule is conditioned on declaring at least one CT#."""
        text = "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nINTENT: x.\n"
        assert "slice-without-tests" not in _rules(text)

    def test_a_prescriptive_step_without_an_exit_fails(self) -> None:
        """CT9. producer-kill-check: delete `_rule_step_without_exit`."""
        text = (
            "## SLICE1: a\nSTEPS: prescriptive\nDEPS: —\nTESTS: tests/a.py\n"
            "- [ ] STEP1: do the thing (exit: it is done.)\n"
            "- [ ] STEP2: do the other thing\n"
        )
        hit = [d for d in precheck(text).diagnostics if d.rule == "step-without-exit"]
        assert len(hit) == 1
        assert hit[0].severity == "FAIL"
        assert hit[0].line == 6

    def test_an_exit_on_a_continuation_line_counts(self) -> None:
        """CT9 — a STEP# is a BLOCK: its line plus indented continuations.

        Real steps wrap. Reading only the `- [ ]` line would fail every step
        whose predicate does not fit on one line, which is most of them.
        """
        text = (
            "## SLICE1: a\nSTEPS: prescriptive\nDEPS: —\nTESTS: tests/a.py\n"
            "- [ ] STEP1: do a thing whose predicate is long enough to wrap\n"
            "      onto the next line (exit: the predicate is here.)\n"
        )
        assert "step-without-exit" not in _rules(text)

    def test_an_outcome_slice_is_exempt(self) -> None:
        text = "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nTESTS: tests/a.py\n- [ ] STEP1: no exit predicate here\n"
        assert "step-without-exit" not in _rules(text)


class TestDepsGraph:
    def test_a_dependency_on_an_undefined_slice_fails(self) -> None:
        """CT10 (scoped to slice ids by Q38)."""
        text = "## SLICE1: a\nSTEPS: outcome\nDEPS: SLICE9\nTESTS: tests/a.py\n"
        hit = [d for d in precheck(text).diagnostics if d.rule == "deps-undefined-slice"]
        assert len(hit) == 1
        assert hit[0].severity == "FAIL"
        assert "SLICE9" in hit[0].message

    def test_a_dependency_cycle_fails(self) -> None:
        """CT10. producer-kill-check: delete `_rule_deps_cycle`."""
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: SLICE2\nTESTS: tests/a.py\n"
            "## SLICE2: b\nSTEPS: outcome\nDEPS: SLICE1\nTESTS: tests/b.py\n"
        )
        hit = [d for d in precheck(text).diagnostics if d.rule == "deps-cycle"]
        assert hit
        assert hit[0].severity == "FAIL"
        assert "SLICE1" in hit[0].message and "SLICE2" in hit[0].message

    def test_a_self_dependency_is_a_cycle(self) -> None:
        text = "## SLICE1: a\nSTEPS: outcome\nDEPS: SLICE1\nTESTS: tests/a.py\n"
        assert "deps-cycle" in _rules(text)

    def test_the_no_dependency_markers_all_resolve(self) -> None:
        """Em dash, en dash, hyphen and "none" all mean "depends on nothing".

        Four spellings because all four are in existing plans. They carry no
        meaning apart from each other, so disagreeing about them would be a
        lint that only ever reports formatting.

        The legacy `S1` spelling is deliberately NOT here: it used to resolve,
        and CT37 stopped it. See
        `TestAbbreviatedIdsAreNeverGuessed::test_a_legacy_dep_token_no_longer_resolves_silently`.
        """
        for nothing in ["\u2014", "\u2013", "-", "none", "N/A"]:
            text = (
                f"## SLICE1: a\nSTEPS: outcome\nDEPS: {nothing}\nTESTS: tests/a.py\n"
                f"## SLICE2: b\nSTEPS: outcome\nDEPS: SLICE1\nTESTS: tests/b.py\n"
            )
            rules = _rules(text)
            assert "deps-undefined-slice" not in rules, nothing
            assert "deps-cycle" not in rules, nothing


class TestContractRules:
    def test_a_near_miss_heading_is_reported(self) -> None:
        """CT26 — a heading that *almost* declares a slice loses it silently.

        `## SLICE 1:` parses as no slice at all, so the slice and every
        contract in it vanish from everything downstream. Reported as a FAIL:
        the plan the harness gates against is not the plan the author wrote.
        """
        text = "## SLICE 1: spaced\nSTEPS: outcome\nTESTS: tests/a.py\n"
        hit = [d for d in precheck(text).diagnostics if d.rule == "heading-near-miss"]
        assert len(hit) == 1
        assert hit[0].severity == "FAIL"
        assert hit[0].line == 1
        assert "## SLICE<n>:" in hit[0].message

    def test_a_valid_heading_is_not_a_near_miss(self) -> None:
        assert "heading-near-miss" not in _rules(GOOD)

    def test_an_undeclared_contract_reference_warns(self) -> None:
        """CT27 — WARN, never FAIL (Q38): a plan may cite a neighbour's CT."""
        text = (
            "## SLICE1: a\nSTEPS: prescriptive\nDEPS: —\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: rule.\nTESTS: tests/a.py\n"
            "- [ ] STEP1: honour CT77 from I02 (exit: done.)\n"
        )
        report = precheck(text)
        hit = [d for d in report.diagnostics if d.rule == "contract-reference-undeclared"]
        assert len(hit) == 1
        assert hit[0].severity == "WARN"
        assert hit[0].line == 7
        assert "CT77" in hit[0].message
        assert report.ok is True, "a WARN must not fail the plan"

    def test_a_contract_declared_twice_fails_naming_both(self) -> None:
        """CT34. producer-kill-check: delete `_rule_contract_declared_twice`."""
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: mine.\nTESTS: tests/a.py\n"
            "## SLICE2: b\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n"
            "  CT1 [CONSTRAINT]: also mine.\nTESTS: tests/b.py\n"
        )
        hit = [d for d in precheck(text, path="p.md").diagnostics if d.rule == "contract-declared-twice"]
        assert len(hit) == 1
        assert hit[0].severity == "FAIL"
        assert "p.md:5" in hit[0].message and "p.md:11" in hit[0].message

    def test_a_declaration_lost_to_a_margin_wrap_fails(self) -> None:
        """CT35 (Q36) — the silent data loss the probe found.

        A continuation wrapped back to column 0 closes the CONTRACTS: block,
        so CT2 is never declared. Without this rule the plan simply has fewer
        contracts than it reads as having.
        """
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: a rule whose sentence runs long and wraps\n"
            "back to the margin like ordinary prose.\n"
            "  CT2 [CONSTRAINT]: lost because the block already closed.\n"
            "TESTS: tests/a.py\n"
        )
        report = precheck(text)
        hit = [d for d in report.diagnostics if d.rule == "contract-declaration-lost"]
        assert len(hit) == 1
        assert hit[0].severity == "FAIL"
        assert hit[0].line == 7
        assert "CT2" in hit[0].message
        assert report.ok is False

    def test_a_declared_contract_is_not_reported_lost(self) -> None:
        assert "contract-declaration-lost" not in _rules(GOOD)

    def test_a_lost_declaration_is_not_also_warned_as_undeclared(self) -> None:
        """One defect, one diagnostic.

        A contract whose declaration was eaten by a margin wrap is trivially
        "declared nowhere" too. Emitting both rules sends the operator to a
        prose mention instead of to the broken block, so CT35 suppresses CT27
        for the ids it claims.
        """
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: a rule whose sentence wraps\n"
            "back to the margin.\n"
            "  CT2 [CONSTRAINT]: lost.\n"
            "TESTS: tests/a.py\n"
        )
        by_rule: dict[str, list[str]] = {}
        for d in precheck(text).diagnostics:
            by_rule.setdefault(d.rule, []).append(d.message)
        assert "contract-declaration-lost" in by_rule
        assert all("CT2" not in m for m in by_rule.get("contract-reference-undeclared", []))

    def test_suppression_does_not_hide_a_genuinely_undeclared_id(self) -> None:
        """The narrow fix must stay narrow: CT77 is still warned about."""
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: a rule whose sentence wraps\n"
            "back to the margin.\n"
            "  CT2 [CONSTRAINT]: lost.\n"
            "TESTS: tests/a.py — see CT77 in I02\n"
        )
        warned = {d.message.split()[0] for d in precheck(text).diagnostics if d.rule == "contract-reference-undeclared"}
        assert "CT77" in warned
        assert "CT2" not in warned


class TestDriftCorpus:
    """STEP5 — one file per drift mode actually observed in this project."""

    def test_the_corpus_exists(self) -> None:
        assert CORPUS.is_dir(), f"corpus missing: {CORPUS}"
        assert sorted(p.name for p in CORPUS.glob("*.md")), "corpus is empty"

    def test_every_corpus_file_produces_a_named_diagnostic(self) -> None:
        paths = sorted(p for p in CORPUS.glob("*.md") if p.name != "README.md")
        assert len(paths) >= 9, f"corpus shrank to {len(paths)} files"
        for path in paths:
            report = precheck(path.read_text(encoding="utf-8"), path=str(path))
            assert report.diagnostics, f"{path.name} parsed silently to no diagnostic"
            assert all(d.rule for d in report.diagnostics), path.name

    def test_the_corpus_covers_every_observed_drift_mode(self) -> None:
        """Naming a file is not covering a mode — assert the rule each fires."""
        expected = {
            "heading-space.md": "heading-near-miss",
            "heading-lowercase.md": "heading-near-miss",
            "heading-no-colon.md": "heading-near-miss",
            "contract-outside-block.md": "contract-reference-undeclared",
            "contract-declared-twice.md": "contract-declared-twice",
            "contract-margin-wrap.md": "contract-declaration-lost",
            "step-marker-unknown.md": "step-marker-unknown",
            "id-abbreviated.md": "step-near-miss",
            "grounding-ends-slice.md": "orphaned-slice-field",
        }
        for name, rule in expected.items():
            path = CORPUS / name
            assert path.is_file(), f"corpus file missing: {name}"
            rules = {d.rule for d in precheck(path.read_text(encoding="utf-8")).diagnostics}
            assert rule in rules, f"{name}: expected {rule}, got {sorted(rules)}"


class TestAgainstTheLiveIncrement:
    def test_this_increment_prechecks_clean(self) -> None:
        """The increment DoD requires it: the plan must pass its own lint."""
        path = (
            REPO_ROOT
            / "worklogs"
            / "planning-topology-and-executable-contracts-loop"
            / "increments"
            / "increment-01-plan-grammar-and-extractor.md"
        )
        assert path.is_file(), f"increment artifact missing: {path}"
        report = precheck(path.read_text(encoding="utf-8"), path=str(path))
        failures = [f"{d.location} [{d.rule}] {d.message}" for d in report.failures]
        assert not failures, "the live increment fails its own pre-check:\n" + "\n".join(failures)


class TestMutationDrivenGaps:
    """Cases a mutation sweep proved the suite above could not distinguish.

    Each one corresponds to a surviving mutant: an edit to `precheck` that
    changed behaviour while every other test stayed green. They are kept in
    their own class because that is what they are — holes found by a tool, not
    a reading of the contracts.
    """

    def test_the_scan_continues_past_an_exempt_slice(self) -> None:
        """`continue` in the steps rule, not `break`.

        An `outcome` slice is skipped. If the skip ended the loop instead, no
        slice after the first exempt one would ever be checked — and plans put
        the outcome slice first all the time.
        """
        text = (
            "## SLICE1: exempt\nSTEPS: outcome\nDEPS: —\nTESTS: tests/a.py\n"
            "- [ ] STEP1: nothing required here\n"
            "## SLICE2: checked\nSTEPS: prescriptive\nDEPS: —\nTESTS: tests/b.py\n"
            "- [ ] STEP1: this one is missing its predicate\n"
        )
        hit = [d for d in precheck(text).diagnostics if d.rule == "step-without-exit"]
        assert [d.line for d in hit] == [10]

    def test_the_scan_continues_past_a_slice_with_no_deps_line(self) -> None:
        """Same shape in the deps rule: a missing `DEPS:` must not end the walk."""
        text = (
            "## SLICE1: no deps line at all\nSTEPS: outcome\nTESTS: tests/a.py\n"
            "## SLICE2: bad deps\nSTEPS: outcome\nDEPS: SLICE9\nTESTS: tests/b.py\n"
        )
        assert "deps-undefined-slice" in _rules(text)

    def test_the_scan_continues_past_a_contract_that_is_fine(self) -> None:
        """CT27 and CT34 both filter before reporting; both must not short-circuit."""
        # Both ids sit on ONE line: the scan skips the declared one and must
        # keep reading the same line, not abandon it.
        undeclared = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: declared, so skipped by the scan.\n"
            "TESTS: tests/a.py — CT1 is fine but CT77 is not declared anywhere\n"
        )
        warned = [d.message for d in precheck(undeclared).diagnostics if d.rule == "contract-reference-undeclared"]
        assert len(warned) == 1
        assert warned[0].startswith("CT77")

        duplicated = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: unique, so skipped by the report loop.\n"
            "  CT2 [CONSTRAINT]: duplicated below.\nTESTS: tests/a.py\n"
            "## SLICE2: b\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n"
            "  CT2 [CONSTRAINT]: here it is again.\nTESTS: tests/b.py\n"
        )
        assert "contract-declared-twice" in _rules(duplicated)

    def test_a_step_continuation_indented_by_one_space_still_counts(self) -> None:
        """The continuation test is `line[:1].isspace()`, not `line[:2]`.

        One space is unusual but legal, and the same idiom guards the
        CONTRACTS: block, so the two must agree about what indentation is.
        """
        text = (
            "## SLICE1: a\nSTEPS: prescriptive\nDEPS: —\nTESTS: tests/a.py\n"
            "- [ ] STEP1: a predicate that wraps\n (exit: onto a line indented one space.)\n"
        )
        assert "step-without-exit" not in _rules(text)

    def test_line_numbers_are_right_when_the_plan_starts_with_a_blank_line(self) -> None:
        """Counting from offset 0, not 1 — a leading newline must not shift lines."""
        scanned = "\n## SLICE 1: spaced\nSTEPS: outcome\n"
        hit = [d for d in precheck(scanned).diagnostics if d.rule == "heading-near-miss"]
        assert [d.line for d in hit] == [2]
        assert scanned.splitlines()[1].startswith("## SLICE 1")

        # The line-scanning rules above enumerate lines directly; the
        # slice-anchored rules convert a character offset instead, which is a
        # second place the same off-by-one can hide. Exercise both.
        anchored = "\n## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n  CT1 [FUNCTIONAL]: x.\n"
        anchored_hit = [d for d in precheck(anchored).diagnostics if d.rule == "slice-without-tests"]
        assert [d.line for d in anchored_hit] == [2]
        assert anchored.splitlines()[1].startswith("## SLICE1:")

    def test_the_default_path_is_a_placeholder_not_a_real_file(self) -> None:
        """`<plan>` is deliberately unopenable: it cannot be mistaken for a path."""
        report = precheck("## SLICE 1: x\n")
        assert report.path == "<plan>"
        assert report.diagnostics[0].location == "<plan>:1"

    def test_the_cycle_message_spells_out_the_whole_path(self) -> None:
        """Naming the members is not enough — the operator needs the edges."""
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: SLICE3\nTESTS: tests/a.py\n"
            "## SLICE2: b\nSTEPS: outcome\nDEPS: SLICE1\nTESTS: tests/b.py\n"
            "## SLICE3: c\nSTEPS: outcome\nDEPS: SLICE2\nTESTS: tests/c.py\n"
        )
        hit = [d for d in precheck(text).diagnostics if d.rule == "deps-cycle"]
        assert len(hit) == 1
        assert hit[0].message.startswith("DEPS: cycle ")
        path = hit[0].message.split("DEPS: cycle ")[1].split(";")[0]
        nodes = path.split(" -> ")
        assert nodes[0] == nodes[-1], f"not a closed path: {path}"
        assert set(nodes) == {"SLICE1", "SLICE2", "SLICE3"}

    def test_two_independent_cycles_are_both_reported(self) -> None:
        """CT25 applies within a rule too, not only across rules."""
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: SLICE2\nTESTS: tests/a.py\n"
            "## SLICE2: b\nSTEPS: outcome\nDEPS: SLICE1\nTESTS: tests/b.py\n"
            "## SLICE3: c\nSTEPS: outcome\nDEPS: SLICE4\nTESTS: tests/c.py\n"
            "## SLICE4: d\nSTEPS: outcome\nDEPS: SLICE3\nTESTS: tests/d.py\n"
        )
        hit = [d for d in precheck(text).diagnostics if d.rule == "deps-cycle"]
        assert len(hit) == 2
        assert {n for d in hit for n in d.message.split()} >= {"SLICE1", "SLICE3"}

    def test_a_declaration_lost_from_an_empty_slice_says_none(self) -> None:
        """The `or 'none'` branch is reachable: the block can lose everything."""
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n\n"
            "CT1 [FUNCTIONAL]: written at column zero, so outside the block.\n"
            "TESTS: tests/a.py\n"
        )
        hit = [d for d in precheck(text).diagnostics if d.rule == "contract-declaration-lost"]
        assert len(hit) == 1
        assert "parsed only none" in hit[0].message

    def test_the_missing_tests_message_lists_every_contract(self) -> None:
        """An operator fixing this needs to know what is going unchecked."""
        text = "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n  CT1 [FUNCTIONAL]: one.\n  CT2 [CONSTRAINT]: two.\n"
        hit = [d for d in precheck(text).diagnostics if d.rule == "slice-without-tests"]
        assert len(hit) == 1
        assert "CT1, CT2" in hit[0].message

    def test_a_dependency_with_trailing_punctuation_still_resolves(self) -> None:
        """`DEPS: SLICE1.` is a real habit; stripping only whitespace misses it."""
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nTESTS: tests/a.py\n"
            "## SLICE2: b\nSTEPS: outcome\nDEPS: SLICE1.\nTESTS: tests/b.py\n"
        )
        assert "deps-undefined-slice" not in _rules(text)

    def test_the_duplicate_message_names_both_slices_and_both_lines(self) -> None:
        """Line arithmetic over the CONTRACTS: block, pinned at both ends."""
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nINTENT: x.\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: first.\nTESTS: tests/a.py\n"
            "\n\n## SLICE2: b\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n"
            "  CT1 [CONSTRAINT]: second.\nTESTS: tests/b.py\n"
        )
        hit = [d for d in precheck(text, path="p.md").diagnostics if d.rule == "contract-declared-twice"]
        assert len(hit) == 1
        assert "CT1 is declared 2 times — SLICE1 at p.md:6, SLICE2 at p.md:14" == hit[0].message
        lines = text.splitlines()
        assert lines[5].strip().startswith("CT1") and lines[13].strip().startswith("CT1")

    def test_the_lost_message_lists_what_did_survive(self) -> None:
        """ "parsed only CT1, CT2" tells the operator where the block stopped."""
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n"
            "  CT1 [FUNCTIONAL]: one.\n"
            "  CT2 [CONSTRAINT]: two, whose sentence wraps\n"
            "back to the margin.\n"
            "  CT3 [PRESERVATION]: lost.\nTESTS: tests/a.py\n"
        )
        hit = [d for d in precheck(text).diagnostics if d.rule == "contract-declaration-lost"]
        assert len(hit) == 1
        assert "parsed only CT1, CT2" in hit[0].message

    def test_the_cycle_diagnostic_renders_exactly(self) -> None:
        """A lint's output is its product; pin one message end to end.

        Also pins *which* line a cycle is reported on: the DEPS: line that
        declares the first edge of the printed path, which is a line the
        operator can edit to break it.
        """
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: SLICE2\nTESTS: tests/a.py\n"
            "## SLICE2: b\nSTEPS: outcome\nDEPS: SLICE1\nTESTS: tests/b.py\n"
        )
        hit = [d for d in precheck(text, path="p.md").diagnostics if d.rule == "deps-cycle"]
        assert len(hit) == 1
        assert hit[0].render() == (
            "p.md:7 [FAIL deps-cycle] DEPS: cycle SLICE1 -> SLICE2 -> SLICE1; no slice in it can be built first"
        )
        assert text.splitlines()[6] == "DEPS: SLICE1", "line 7 is SLICE2's DEPS: line"


class TestStepMarkerVocabulary:
    """CT36 — one normalised vocabulary for the `STEP#` checkbox.

    producer-kill-check: delete `_step_state`; every classification collapses.
    """

    def test_the_three_states_are_recognised(self) -> None:
        for marker, state in [
            ("", "todo"),
            (" ", "todo"),
            ("  ", "todo"),
            ("x", "done"),
            ("X", "done"),
            ("✓", "done"),
            ("✔", "done"),
            (" X ", "done"),
            (">", "in-progress"),
            (" > ", "in-progress"),
        ]:
            text = f"## SLICE1: a\nSTEPS: prescriptive\nDEPS: —\nTESTS: t.py\n- [{marker}] STEP1: do it (exit: done.)\n"
            rules = _rules(text)
            assert "step-marker-unknown" not in rules, f"[{marker}] should mean {state}"

    def test_a_step_is_seen_whatever_its_legal_marker(self) -> None:
        """The missing-exit rule must fire for every marker, not only `[ ]`.

        Before CT36 a capital `[X]` was not a step at all, so a step with no
        exit predicate escaped the lint entirely by being marked done.
        """
        for marker in ["", " ", "x", "X", ">", "✓"]:
            text = f"## SLICE1: a\nSTEPS: prescriptive\nDEPS: —\nTESTS: t.py\n- [{marker}] STEP1: no predicate here\n"
            assert "step-without-exit" in _rules(text), f"marker [{marker}] hid the step"

    def test_an_unknown_marker_fails_loudly(self) -> None:
        for marker in ["-", "~", "?", "ok", "1"]:
            text = f"## SLICE1: a\nSTEPS: prescriptive\nDEPS: —\nTESTS: t.py\n- [{marker}] STEP1: do it (exit: done.)\n"
            hit = [d for d in precheck(text).diagnostics if d.rule == "step-marker-unknown"]
            assert len(hit) == 1, f"[{marker}] should be rejected"
            assert hit[0].severity == "FAIL"
            assert hit[0].line == 5
            assert marker in hit[0].message


class TestAbbreviatedIdsAreNeverGuessed:
    """CT37 — `S1` is ambiguous between SLICE1 and STEP1 inside a plan."""

    def test_a_legacy_dep_token_no_longer_resolves_silently(self) -> None:
        """This reverses a defect SLICE3 shipped and pinned with a test.

        `DEPS: S1` used to canonicalise to SLICE1 while `## S1:` declared no
        slice at all — the same token legal in one position and invisible in
        the other, inside one document.
        """
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nTESTS: a.py\n## SLICE2: b\nSTEPS: outcome\nDEPS: S1\nTESTS: b.py\n"
        )
        hit = [d for d in precheck(text).diagnostics if d.rule == "deps-undefined-slice"]
        assert len(hit) == 1
        assert "S1" in hit[0].message

    def test_a_full_dep_token_still_resolves(self) -> None:
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nTESTS: a.py\n"
            "## SLICE2: b\nSTEPS: outcome\nDEPS: slice1\nTESTS: b.py\n"
        )
        assert "deps-undefined-slice" not in _rules(text)

    def test_an_abbreviated_slice_heading_is_a_near_miss(self) -> None:
        hit = [d for d in precheck("## S1: shortened\n").diagnostics if d.rule == "heading-near-miss"]
        assert len(hit) == 1
        assert hit[0].severity == "FAIL"

    def test_an_abbreviated_step_is_a_near_miss(self) -> None:
        text = "## SLICE1: a\nSTEPS: prescriptive\nDEPS: —\nTESTS: t.py\n- [ ] S1: shortened (exit: done.)\n"
        hit = [d for d in precheck(text).diagnostics if d.rule == "step-near-miss"]
        assert len(hit) == 1
        assert hit[0].severity == "FAIL"
        assert hit[0].line == 5
        assert "STEP" in hit[0].message

    def test_a_prose_heading_that_merely_starts_with_s_is_not_flagged(self) -> None:
        """`## S18 + I-63 CLOSED` is a real heading in this repo's worklogs.

        The bare `S<n>` form requires a colon precisely so that section
        numbering in prose documents is not dragged in.
        """
        for heading in ["## S18 + I-63 CLOSED", "## Section 2 overview", "## S3.5 execution update"]:
            assert "heading-near-miss" not in _rules(heading + "\n"), heading


class TestSliceCountCeiling:
    """CT38 — WARN at the ceiling, never FAIL (admission control, Q16)."""

    def _plan(self, n: int) -> str:
        return "".join(f"## SLICE{i}: s{i}\nSTEPS: outcome\nDEPS: —\nTESTS: t{i}.py\n" for i in range(1, n + 1))

    def test_six_slices_are_quiet_and_seven_warn(self) -> None:
        assert "slice-count-at-ceiling" not in _rules(self._plan(6))
        plan = self._plan(7)
        hit = [d for d in precheck(plan).diagnostics if d.rule == "slice-count-at-ceiling"]
        assert len(hit) == 1
        assert hit[0].severity == "WARN"
        assert "7" in hit[0].message
        # Reported at the slice that consumed the headroom, not at the first.
        assert plan.splitlines()[hit[0].line - 1] == "## SLICE7: s7"

    def test_the_ceiling_never_blocks(self) -> None:
        assert precheck(self._plan(12)).ok is True


class TestOrphanedGrammar:
    """CT39 — conservation: grammar the document contains must be accounted for."""

    def test_a_hash_hash_grounding_inside_a_slice_is_caught(self) -> None:
        """The measured S-e defect.

        `## Grounding` ends the slice under CT16's depth rule, so the TESTS:
        line after it belongs to no slice and is silently lost.
        """
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n  CT1 [FUNCTIONAL]: x.\n"
            "## Grounding\nUnderstood as: something.\nTESTS: tests/t.py\n"
        )
        hit = [d for d in precheck(text).diagnostics if d.rule == "orphaned-slice-field"]
        assert len(hit) == 1
        assert hit[0].severity == "FAIL"
        assert hit[0].line == 8
        assert "TESTS" in hit[0].message

    def test_the_same_slice_with_a_subsection_grounding_is_clean(self) -> None:
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n  CT1 [FUNCTIONAL]: x.\n"
            "### Grounding\nUnderstood as: something.\nTESTS: tests/t.py\n"
        )
        assert precheck(text).ok is True

    def test_it_catches_the_silent_case_too(self) -> None:
        """With no contracts, CT8 cannot fire — this is the one nothing caught."""
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nINTENT: x.\n"
            "## Grounding\nUnderstood as: something.\nTESTS: tests/t.py\n"
        )
        assert "orphaned-slice-field" in _rules(text)

    def test_an_orphaned_step_and_contract_are_caught_too(self) -> None:
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nTESTS: t.py\n"
            "## Notes\n- [ ] STEP1: stranded (exit: never.)\n  CT9 [FUNCTIONAL]: stranded.\n"
        )
        hit = [d for d in precheck(text).diagnostics if d.rule == "orphaned-slice-field"]
        assert {d.line for d in hit} == {6, 7}
        # The message must name *what* was stranded; "something sits outside"
        # is not actionable in a plan with forty bullets.
        said = " ".join(d.message for d in hit)
        assert "STEP1" in said and "CT9" in said

    def test_an_orphaned_tests_line_stops_ct8_from_lying(self) -> None:
        """CT8 must not say "has no TESTS: line" about a line the author wrote.

        Same principle as E97: one defect, one diagnostic, at the line the
        operator must edit. CT39 already points at the orphaned line; CT8
        adding "there is no TESTS: line" sends them looking for something that
        is visibly present four lines down.
        """
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n  CT1 [FUNCTIONAL]: x.\n"
            "## Grounding\nUnderstood as: something.\nTESTS: tests/t.py\n"
        )
        rules = _rules(text)
        assert "orphaned-slice-field" in rules
        assert "slice-without-tests" not in rules

    def test_the_suppression_does_not_hide_a_genuinely_testless_slice(self) -> None:
        """Narrow fix stays narrow: SLICE2 never wrote a TESTS: line at all."""
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n  CT1 [FUNCTIONAL]: x.\n"
            "## Grounding\nUnderstood as: something.\nTESTS: tests/t.py\n"
            "## SLICE2: b\nSTEPS: outcome\nDEPS: —\nCONTRACTS:\n  CT2 [CONSTRAINT]: y.\n"
        )
        hit = [d for d in precheck(text).diagnostics if d.rule == "slice-without-tests"]
        assert len(hit) == 1
        assert "SLICE2" in hit[0].message

    def test_a_non_tests_orphan_does_not_abort_the_attribution(self) -> None:
        """The orphan scan must keep reading past orphans it does not care about.

        Here a stranded STEP comes before the stranded TESTS: line. If the
        filter stopped at the first non-TESTS orphan, CT8 would go back to
        claiming SLICE1 "has no TESTS: line".
        """
        text = (
            "## SLICE1: a\nSTEPS: outcome\nDEPS: \u2014\nCONTRACTS:\n  CT1 [FUNCTIONAL]: x.\n"
            "## Notes\n- [ ] STEP9: stranded first (exit: never.)\n"
            "TESTS: tests/t.py\n"
        )
        rules = _rules(text)
        assert "orphaned-slice-field" in rules
        assert "slice-without-tests" not in rules

    def test_a_plan_with_no_slices_at_all_is_not_an_orphan_storm(self) -> None:
        """A pre-grammar document yields no slices; it must not produce noise.

        `extract_plan_ids` returns empty for such a file by design, and the
        module's founding rule is that absence is never an error.
        """
        text = "# Old plan\nSTEPS: prescriptive\nTESTS: t.py\nCONTRACTS:\n"
        assert "orphaned-slice-field" not in _rules(text)
