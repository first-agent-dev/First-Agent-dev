"""I01/SLICE1b — the authoring contract is executable, not prose.

Schema §4 is the specification `plan_ids.py` conforms to (standing decision SD-A:
the prompt is primary, the parser conforms). A specification nobody can run drifts
from its implementation silently, so §4 carries a worked example and a
machine-readable expectation, and this module executes them.

Four of the rules §4 states were not implemented by the parser when this module
was written — CT16 section spans, CT17 declaration scope, CT18 whole-entry text.
Those assertions shipped as ``xfail(strict=True)`` rather than being omitted, so
that they encoded SLICE2's acceptance criteria while it was still unbuilt and
``strict`` turned the eventual XPASS into a failure demanding the marker come off.
It worked exactly as intended: SLICE2 landed, the four reported XPASS, and the
markers were removed here. A deleted assertion would have gone quiet instead.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.plan_ids import SliceRecord, extract_plan_ids

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (
    REPO_ROOT
    / "worklogs"
    / "planning-topology-and-executable-contracts-loop"
    / "notes"
    / "artifact-schema-and-grammar.md"
)
SKILLS = (
    REPO_ROOT / "knowledge" / "skills" / "plan-authoring" / "SKILL.md",
    REPO_ROOT / "knowledge" / "skills" / "feature-planning" / "SKILL.md",
)


def _marked_block(text: str, name: str) -> str:
    """Content between ``<!-- name:BEGIN -->`` and ``<!-- name:END -->``.

    The outer fence line (``````text`` / ```` ```json ````) and its closer are
    stripped, so the caller gets the payload exactly as an author wrote it.
    """
    pattern = re.compile(
        rf"<!--\s*{re.escape(name)}:BEGIN\s*-->\s*\n(.*?)\n\s*<!--\s*{re.escape(name)}:END\s*-->",
        re.DOTALL,
    )
    match = pattern.search(text)
    assert match, f"marker pair {name}:BEGIN/{name}:END not found — §4 renamed or lost its example"
    lines = match.group(1).splitlines()
    assert lines and lines[0].lstrip().startswith("`"), f"{name} does not open with a fence"
    assert lines[-1].lstrip().startswith("`"), f"{name} does not close with a fence"
    return "\n".join(lines[1:-1])


def _schema_text() -> str:
    assert SCHEMA.is_file(), f"schema artifact missing: {SCHEMA}"
    return SCHEMA.read_text(encoding="utf-8")


def _example() -> str:
    return _marked_block(_schema_text(), "SCHEMA4-EXAMPLE")


def _expected() -> dict[str, Any]:
    return json.loads(_marked_block(_schema_text(), "SCHEMA4-EXPECTED"))


def _records() -> dict[str, SliceRecord]:
    return {r.slice_id: r for r in extract_plan_ids(_example()).slice_records}


# ── CT21: the §4 example parses to exactly what §4 documents ──────────────


def test_schema4_example_and_expectation_both_exist() -> None:
    """Kill-check: delete either marked block and this fails immediately."""
    assert _example().strip(), "the §4 example block is empty"
    assert _expected(), "the §4 expectation block is empty"


def test_schema4_expectation_describes_every_slice_in_the_example() -> None:
    """The doc must not document a parse for slices it does not show (or vice versa)."""
    expected = _expected()
    declared = expected["slices"]
    for key in ("steps_mode", "test_paths", "commands", "contract_ids"):
        assert sorted(expected[key]) == sorted(declared), (
            f"§4's expectation key {key!r} does not cover exactly {declared} — "
            "the prose and the machine-readable block have drifted"
        )


def test_schema4_example_yields_the_documented_slice_ids() -> None:
    assert list(extract_plan_ids(_example()).slices) == _expected()["slices"]


def test_schema4_example_yields_the_documented_steps_modes() -> None:
    records = _records()
    for slice_id, mode in _expected()["steps_mode"].items():
        assert records[slice_id].steps_mode == mode, slice_id


def test_schema4_example_yields_the_documented_test_paths() -> None:
    records = _records()
    for slice_id, paths in _expected()["test_paths"].items():
        assert list(records[slice_id].test_paths) == paths, slice_id


def test_schema4_example_yields_the_documented_commands() -> None:
    records = _records()
    for slice_id, commands in _expected()["commands"].items():
        assert list(records[slice_id].commands) == commands, slice_id


def test_schema4_example_declares_contracts_only_inside_the_contracts_block() -> None:
    """CT17/CT18 — a `CT#` in step text is a reference, never a declaration.

    The example's SLICE2/STEP1 mentions SLICE1's `CT1`. Until SLICE2 lands,
    `_section_contracts` scans every line of the section and hands SLICE2 a
    contract it never declared.
    """
    records = _records()
    for slice_id, ids in _expected()["contract_ids"].items():
        assert [cid for cid, _cls, _text in records[slice_id].contracts] == ids, slice_id


def test_schema4_example_reads_contract_classes_from_the_entry_first_line() -> None:
    """CT18 — id and class come from the declaring line only."""
    records = _records()
    observed = {cid: cls for record in records.values() for cid, cls, _text in record.contracts}
    assert observed == _expected()["contract_classes"]


def test_schema4_example_keeps_the_whole_contract_entry_as_its_text() -> None:
    """CT18 — a CONSTRAINT's rationale lives on a continuation line and must survive.

    At 2f6b8c1 the text is `line.split("]:", 1)[1]`, so every rationale is
    discarded — including the one CT23 makes mandatory.
    """
    records = _records()
    observed = {cid: text for record in records.values() for cid, _cls, text in record.contracts}
    for cid, text in _expected()["contract_text"].items():
        assert observed[cid] == text, cid


def test_schema4_example_section_spans_use_relative_heading_depth() -> None:
    """CT16 — a deeper heading stays inside; a same-or-shallower one ends the slice."""
    records = _records()
    expected = _expected()
    for slice_id, absent in expected["section_excludes"].items():
        for needle in absent:
            assert needle not in records[slice_id].section, f"{slice_id} absorbed {needle!r}"
    for slice_id, present in expected["section_includes"].items():
        for needle in present:
            assert needle in records[slice_id].section, f"{slice_id} lost {needle!r}"


# ── CT21b: adding the example must not leak into the real corpus ──────────


def test_totality_corpus_glob_does_not_reach_the_notes_folder() -> None:
    """CT21b — the schema doc now parses as a plan; keep it out of plan corpora.

    `extract_plan_ids` over the schema file reports the example's slices and
    commands. That is accepted (SLICE1/CT13: a fenced example is still
    extracted). The containment is that no corpus glob reaches `notes/`.
    """
    schema_ids = extract_plan_ids(_schema_text())
    assert schema_ids.slices, "precondition: the schema file does expose the example's slices"

    corpus = sorted(REPO_ROOT.glob("worklogs/*/increments/increment-*.md"))
    corpus += sorted((REPO_ROOT / "worklogs" / "implementation-plans").glob("*.md"))
    assert corpus, "no plan artifacts found — the corpus path moved"
    assert SCHEMA not in corpus, (
        "the schema document reached a plan corpus; its example's CT1/CT2/CT3 would "
        "surface as duplicate declarations once the pre-check enforces uniqueness (CT34)"
    )
    assert not any("notes" in path.parts for path in corpus), (
        f"a corpus glob reached notes/: {[str(p) for p in corpus if 'notes' in p.parts]}"
    )


# ── CT22: each planning skill embeds a skeleton that actually parses ──────


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_skill_embeds_a_skeleton_block_that_parses(skill: Path) -> None:
    """CT22 — the skeleton an author copies must be the grammar the harness reads."""
    assert skill.is_file(), f"skill missing: {skill}"
    skeleton = _marked_block(skill.read_text(encoding="utf-8"), "PLAN-SKELETON")
    ids = extract_plan_ids(skeleton)
    assert ids.slices, f"{skill.parent.name}: skeleton yields no slices"
    for record in ids.slice_records:
        assert record.test_paths, f"{skill.parent.name}/{record.slice_id}: no TESTS: path"
        assert re.search(r"^STEPS:\s*(prescriptive|outcome)\b", record.section, re.M), (
            f"{skill.parent.name}/{record.slice_id}: no explicit STEPS: mode"
        )


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_skill_no_longer_teaches_the_removed_step_anchor(skill: Path) -> None:
    """SLICE1 deleted the `S#` pattern from the parser; the skills must not still emit it."""
    text = skill.read_text(encoding="utf-8")
    offenders = [
        line.strip() for line in text.splitlines() if re.search(r"^#{1,6}\s+(Step\s+)?S\d*#?\s*:", line.strip())
    ]
    assert not offenders, f"{skill.parent.name} still teaches an S# step heading: {offenders}"


# ── CT23: every CONSTRAINT carries its rationale ──────────────────────────


def _constraint_entries_missing_rationale(block: str) -> list[str]:
    """Entries whose `[CONSTRAINT]` line has no more-indented continuation."""
    lines = block.splitlines()
    missing: list[str] = []
    for i, line in enumerate(lines):
        match = re.match(r"^(\s+)CT\d+[a-z]?\s*\[CONSTRAINT\]\s*:", line)
        if not match:
            continue
        indent = len(match.group(1))
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        deeper = nxt.strip() and (len(nxt) - len(nxt.lstrip())) > indent
        if not deeper:
            missing.append(line.strip())
    return missing


def test_schema4_example_constraint_carries_a_rationale() -> None:
    """CT23 — enforced on the normative example, so the rule has a live instance."""
    assert not _constraint_entries_missing_rationale(_example())


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_skill_states_the_constraint_rationale_rule(skill: Path) -> None:
    """CT23 — the rule is taught where plans are authored, not only in the schema."""
    text = skill.read_text(encoding="utf-8")
    assert re.search(r"CONSTRAINT", text), f"{skill.parent.name}: no CONSTRAINT class taught"
    assert re.search(r"rationale", text, re.I), f"{skill.parent.name}: the CONSTRAINT rationale rule is not stated"
    assert not _constraint_entries_missing_rationale(_marked_block(text, "PLAN-SKELETON")), (
        f"{skill.parent.name}: its own skeleton violates the rule it teaches"
    )


# ── CT24: the rest of the ID grammar is untouched ─────────────────────────


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_skill_preserves_the_other_id_grammar(skill: Path) -> None:
    """CT24 — only the slice/step anchors and the new fields change."""
    text = skill.read_text(encoding="utf-8")
    for token in ("GAP#", "CT#", "T#", "Q#", "RK#"):
        assert token in text, f"{skill.parent.name}: lost {token} from its ID grammar"
