"""CT114 (SLICE7 STEP1): the delivery law is *load-bearing text*, not decoration.

Six surfaces carry it — `plan-authoring`, `tests-writing` (skill + inject), `feature-planning` (skill +
inject), the planner/coder prompt, and the architect prompt. This bank reads them as artifacts and
asserts the vocabulary a planner needs is actually present, then damages a copy of each surface and
asserts the checker notices. Text that nobody verifies is text that silently rots: the failure mode
this guards is the E260-E288 shape - a plan that presents an uncalled module as done because the
surfaces stopped saying what "done" costs.

The kill directive is `remove-call ...::test_each_surface_states_the_law -> _TOKENS`: if the table stops
being consulted, the count assertion below fails before the loop can pass vacuously.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

# One entry per file. The six *surfaces* are these seven files: `feature-planning` and
# `tests-writing` each carry a skill and an inject, and both halves are read by agents.
_TOKENS: dict[str, tuple[str, ...]] = {
    # Liveness ladder (ROOT/EDGE/BODY-EDGE mutants, SUPPORT units), cutover contract, gates, I-IP-7..9.
    "knowledge/skills/plan-authoring/SKILL.md": (
        "liveness",
        "EDGE mutant",
        "SUPPORT",
        "rooted-by",
        "cutover",
        "I-IP-7",
    ),
    # Central laws, L1/L2/L3 table, I-TW-22..24.
    "knowledge/skills/tests-writing/SKILL.md": ("EDGE mutant", "L1", "L2", "L3", "I-TW-22", "supplier"),
    "knowledge/skills/tests-writing/INJECT.md": ("EDGE mutant", "supplier"),
    # Laws 10-11, contract-card SUPPLIER/ROOT/EDGE, edit-packet Delivery, anti-patterns.
    "knowledge/skills/feature-planning/SKILL.md": ("SUPPLIER", "ROOT", "EDGE", "anti-pattern", "rooted-by"),
    "knowledge/skills/feature-planning/INJECT.md": ("SUPPORT", "rooted-by", "supplier", "Delivery"),
    # PLANNER hard rules + `## Delivery` template + self-check; CODER delivery discipline and the
    # three final-message facts.
    "src/fa/inner_loop/prompt.py": ("## Delivery", "self-check", "final message", "rooted-by", "supplier"),
    "knowledge/prompts/architect-fa.md": ("## Delivery", "rooted-by", "supplier"),
}


def _missing(text: str, tokens: tuple[str, ...]) -> list[str]:
    """The tokens a surface no longer states. Case-sensitive on purpose: these are quoted labels."""
    return [token for token in tokens if token not in text]


def _read(surface: str) -> str:
    return (_ROOT / surface).read_text(encoding="utf-8")


def test_each_surface_states_the_law() -> None:
    """producer-kill-check: stop consulting `_TOKENS` (keep the loop, drop the table)."""
    assert len(_TOKENS) == 7, "the delivery law has six surfaces: seven files, never fewer"
    absent = {surface: missing for surface in _TOKENS if (missing := _missing(_read(surface), _TOKENS[surface]))}
    assert not absent, f"surfaces that stopped stating the delivery law: {absent}"


@pytest.mark.parametrize("surface", sorted(_TOKENS))
def test_a_damaged_surface_is_flagged(surface: str) -> None:
    """The checker bites: rename the mutant vocabulary, or drop the section that carries it."""
    text = _read(surface)
    tokens = _TOKENS[surface]

    # Damage 1 — the E260-E288 shape: the word an agent reads becomes a softer one.
    damaged = text.replace(tokens[0], "PRODUCER")
    assert damaged != text, f"{surface} does not state {tokens[0]!r} at all"
    assert tokens[0] in _missing(damaged, tokens)

    # Damage 2 - the statements are deleted, not merely reworded: every line that carries a
    # required token goes, which is what "the section was dropped in an edit" looks like.
    kept = "".join(line for line in text.splitlines(keepends=True) if not any(t in line for t in tokens))
    assert kept != text, f"{surface} states none of {tokens} on a line of its own"
    assert tokens[0] in _missing(kept, tokens), f"{surface}: deleting the law's lines went unnoticed"
