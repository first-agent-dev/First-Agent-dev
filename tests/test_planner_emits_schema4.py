"""I01/SLICE1c — the planner is the third emitter of schema §4.

Schema §4 defines the grammar, SLICE1b taught it to the skills, and SLICE2 will
conform the parser to it. None of that is observable in production until the
planner itself emits slices: `workflow_controller.py:332` resolves
`extract_plan_ids(plan_text).slices` and **returns early when the tuple is
empty**, so a plan written in the old `S1.` shape silently skips the per-slice
coverage gate (ledger E52).

These tests therefore parse the prompt's own templates rather than grepping for
the token `SLICE` — a comment would satisfy a grep, and the thing that matters
is that what the planner is told to emit is what the harness can read.
"""

from __future__ import annotations

import re

import pytest

from fa.inner_loop.plan_ids import extract_plan_ids
from fa.inner_loop.prompt import PLANNER_SYSTEM_PROMPT

# Sections the planner emitted before SLICE1c and must keep emitting (CT32).
_PRESERVED_SECTIONS = ("## Class", "## Goal", "## Scope", "## Constraints", "## Verification")

# Evidence/Assumptions/Risks field markers: their content moves under
# `## Grounding`, it is not deleted (CT32).
_GROUNDING_FIELDS = (
    "stack:",
    "entry_points:",
    "verify_methods:",
    "conventions:",
    "analogue:",
    "missing:",
)


def _fenced_blocks(text: str) -> list[str]:
    """Every ````text fence in *text*, payload only.

    Four backticks, not three: a plan block contains a nested ```verify fence,
    so a three-backtick wrapper would be closed by its own payload.
    """
    return re.findall(r"^````text\n(.*?)^````$", text, re.DOTALL | re.MULTILINE)


def _plan_blocks() -> list[str]:
    """The fenced blocks that are plan shapes (template and worked example)."""
    blocks = [b for b in _fenced_blocks(PLANNER_SYSTEM_PROMPT) if b.lstrip().startswith("# Plan:")]
    assert blocks, "the planner prompt no longer contains a fenced `# Plan:` block"
    return blocks


@pytest.fixture(name="plan_blocks")
def _plan_blocks_fixture() -> list[str]:
    return _plan_blocks()


# ── CT31: what the planner is told to emit is what the harness parses ────


def test_planner_prompt_has_both_a_template_and_a_worked_example(plan_blocks: list[str]) -> None:
    """Kill-check: the worked example is the one authors copy; it must be covered too."""
    assert len(plan_blocks) >= 2, (
        f"expected a plan template and a worked example, found {len(plan_blocks)} plan block(s)"
    )


def test_every_plan_block_parses_into_slices(plan_blocks: list[str]) -> None:
    """CT31 — `extract_plan_ids` must find slices, or the coverage gate no-ops."""
    for index, block in enumerate(plan_blocks):
        ids = extract_plan_ids(block)
        assert ids.slices, (
            f"plan block #{index} yields no slices; `workflow_controller.py:332` would "
            "return early and the per-slice gate would never run"
        )


def test_every_slice_in_every_plan_block_carries_tests_and_steps(plan_blocks: list[str]) -> None:
    """CT31 — a slice without `TESTS:`/`STEPS:` is rejected by the SLICE3 pre-check."""
    for index, block in enumerate(plan_blocks):
        for record in extract_plan_ids(block).slice_records:
            where = f"plan block #{index}, {record.slice_id}"
            assert record.test_paths, f"{where}: no TESTS: path"
            assert re.search(r"^STEPS:\s*(prescriptive|outcome)\b", record.section, re.M), (
                f"{where}: no explicit STEPS: mode"
            )


def test_plan_blocks_declare_contracts_with_a_class(plan_blocks: list[str]) -> None:
    """CT31 — the grammar is `CT<n> [CLASS]:`; an unclassed contract defeats CONSTRAINT ordering."""
    for index, block in enumerate(plan_blocks):
        ids = extract_plan_ids(block)
        declared = [(cid, cls) for r in ids.slice_records for cid, cls, _ in r.contracts]
        assert declared, f"plan block #{index}: no contracts declared"
        for cid, cls in declared:
            assert cls in {"FUNCTIONAL", "CONSTRAINT", "PRESERVATION"}, f"{cid} has class {cls!r}"


def test_planner_prompt_no_longer_teaches_the_retired_step_anchor() -> None:
    """SLICE1 deleted the `S#` pattern from the parser; the prompt must not still emit it."""
    offenders = [
        line.strip()
        for line in PLANNER_SYSTEM_PROMPT.splitlines()
        if re.match(r"^S\d+\.\s", line.strip()) or re.match(r"^S<n>'?\.\s", line.strip())
    ]
    assert not offenders, f"the planner prompt still emits S#-style steps: {offenders}"


# ── CT32: Evidence/Assumptions/Risks are rerouted, not dropped ───────────


def test_plan_template_has_a_grounding_section(plan_blocks: list[str]) -> None:
    """CT32 — schema §4's prose-never-parsed block is where the reasoning goes."""
    assert "## Grounding" in plan_blocks[0], "the plan template has no `## Grounding` section"


def test_grounding_states_what_was_understood_and_excluded(plan_blocks: list[str]) -> None:
    """Schema §4 makes the readback line mandatory — it is the cheap misunderstanding catch."""
    template = plan_blocks[0]
    grounding = template.split("## Grounding", 1)[1]
    head = "\n".join(line for line in grounding.splitlines()[:6]).lower()
    assert "understood" in head, "`## Grounding` does not open with what the planner understood"
    assert "exclud" in head, "`## Grounding` does not state what was deliberately excluded"


def test_evidence_assumptions_and_risks_content_survives(plan_blocks: list[str]) -> None:
    """CT32 — a reformat must not quietly drop the planner's uncertainty reporting."""
    template = plan_blocks[0]
    for field in _GROUNDING_FIELDS:
        assert field in template, f"Evidence field {field!r} was deleted rather than rerouted"
    for heading in ("Assumptions", "Risks"):
        assert heading in template, f"{heading} was deleted rather than rerouted"


def test_rerouted_content_sits_under_grounding(plan_blocks: list[str]) -> None:
    """CT32 — 'routed into `## Grounding`', not merely still present somewhere."""
    template = plan_blocks[0]
    grounding_at = template.index("## Grounding")
    for field in _GROUNDING_FIELDS:
        assert template.index(field) > grounding_at, (
            f"{field!r} appears before `## Grounding`; it was not rerouted"
        )
    for heading in ("Assumptions", "Risks"):
        assert template.index(heading) > grounding_at, f"{heading} is not under `## Grounding`"


def test_other_output_sections_are_unchanged(plan_blocks: list[str]) -> None:
    """CT32 — only Evidence/Assumptions/Risks move; the rest of the shape is preserved."""
    template = plan_blocks[0]
    for section in _PRESERVED_SECTIONS:
        assert section in template, f"{section} disappeared from the plan template"


def test_grounding_is_not_parsed_as_plan_structure(plan_blocks: list[str]) -> None:
    """Schema §4 — `## Grounding` is prose; it must contribute no slice, test or command."""
    template = plan_blocks[0]
    grounding = "## Grounding" + template.split("## Grounding", 1)[1]
    ids = extract_plan_ids(grounding)
    assert not ids.slices, f"`## Grounding` leaked slices: {ids.slices}"
    assert not ids.commands, f"`## Grounding` leaked verify commands: {ids.commands}"
