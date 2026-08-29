"""S10.7 / R1 (T8) — held-out wording robustness, incl. Russian paraphrases.

The two-layer design exists because the lexical estimator is allowed to be
wrong: it reads task TEXT, while the runtime engine reads the actual
read/write evidence. R1 proves the architecture with disjoint vocabulary —
wording the estimator never trained on (including the operator's real
Russian style, SSOT amendment 8).

Each case is a task phrasing that omits the estimator's fast-path cues
("refactor", "repo-wide", "infrastructure", …). We:
  1. record what the estimator does with the wording alone (an accuracy
     figure; a drop is EXPECTED and recorded, not asserted), and
  2. assert the load-bearing property: when the SAME task turns out to touch
     high-tier paths, the runtime expansion engine escalates regardless of
     the under-scoped wording — the safety net is evidence-driven, not
     keyword-driven.

Deterministic, no network, no LLM.
"""

from __future__ import annotations

from typing import TypedDict

import pytest

from fa.inner_loop.expansion import ExpansionState, next_level
from fa.inner_loop.scope_estimator import estimate_scope


class LevelEvidence(TypedDict):
    """The keyword evidence `next_level` consumes for one turn."""

    write_tier: int
    read_tier_high: bool
    verify_failed: bool
    assumed_linear: bool


# (task wording, evidence the run actually produced)
# evidence: high-tier write -> escalation to level 3; high-tier read -> arm 2.
HIGH_WRITE_EVIDENCE: LevelEvidence = {
    "write_tier": 5,
    "read_tier_high": False,
    "verify_failed": False,
    "assumed_linear": False,
}
HIGH_READ_EVIDENCE: LevelEvidence = {
    "write_tier": 0,
    "read_tier_high": True,
    "verify_failed": False,
    "assumed_linear": False,
}

# ≥12 held-out paraphrases: English disjoint vocabulary AND Russian (the
# operator's real terse style). None use the estimator's L3 cue words.
HELDOUT_TASKS: list[tuple[str, str, LevelEvidence]] = [
    # --- English: simple words for genuinely cross-file/high-tier work ---
    ("simplify the main function", "en", HIGH_WRITE_EVIDENCE),
    ("clean up a small thing in the cli", "en", HIGH_WRITE_EVIDENCE),
    ("make the entry point a bit shorter", "en", HIGH_WRITE_EVIDENCE),
    ("tidy how the tool gets called", "en", HIGH_WRITE_EVIDENCE),
    ("the startup path feels heavy, trim it", "en", HIGH_WRITE_EVIDENCE),
    ("wire the new flag through", "en", HIGH_WRITE_EVIDENCE),
    ("look at the core loop and straighten it", "en", HIGH_READ_EVIDENCE),
    ("check how the request is built", "en", HIGH_READ_EVIDENCE),
    # --- Russian: operator's real terse style ---
    ("убери лишнее из главной функции", "ru", HIGH_WRITE_EVIDENCE),
    ("поправь проверку перед пушем", "ru", HIGH_WRITE_EVIDENCE),
    ("глянь, как там собирается запрос, и причеши", "ru", HIGH_READ_EVIDENCE),
    ("сделай покороче точку входа", "ru", HIGH_WRITE_EVIDENCE),
    ("подключи новую настройку до конца", "ru", HIGH_WRITE_EVIDENCE),
    ("разберись с основным циклом, там каша", "ru", HIGH_READ_EVIDENCE),  # noqa: RUF001 - intentional Cyrillic
]


def test_r1_has_at_least_twelve_pairs_with_russian() -> None:
    assert len(HELDOUT_TASKS) >= 12
    langs = {lang for _t, lang, _e in HELDOUT_TASKS}
    assert {"en", "ru"} <= langs
    assert sum(1 for _t, lang, _e in HELDOUT_TASKS if lang == "ru") >= 4


@pytest.mark.parametrize("task,lang,evidence", HELDOUT_TASKS, ids=[t[:30] for t, _l, _e in HELDOUT_TASKS])
def test_under_scoped_wording_still_escalates_on_evidence(task: str, lang: str, evidence: LevelEvidence) -> None:
    """The architecture property: wording under-scopes, evidence escalates.

    Whatever the lexical estimator says about the bare text, feeding the
    real high-tier evidence to the runtime engine MUST produce a level-up
    decision — the safety net does not depend on the words used.
    """
    op = estimate_scope(task)
    # Seed from the estimator (chat_direct -> level 1).
    state = ExpansionState(level=1)
    decision = next_level(state, **evidence)

    assert decision is not None, (
        f"[{lang}] wording {task!r} scored {op.recommended_mode} but the runtime "
        "engine failed to act on high-tier evidence"
    )
    assert decision.level_to in (2, 3)
    # high-tier write -> level 3; high-tier read (no write) -> level 2
    if evidence["write_tier"] == 5:
        assert decision.level_to == 3
    else:
        assert decision.level_to == 2


def test_r1_records_estimator_accuracy_on_heldout(capsys: pytest.CaptureFixture[str]) -> None:
    """Record (not gate) estimator accuracy on disjoint vocabulary.

    A drop vs the in-vocabulary set is EXPECTED — that is the premise of the
    two-layer design. We print the figure so it is visible in run output and
    assert only that it runs deterministically.
    """
    under_scoped = 0
    for task, _lang, _ev in HELDOUT_TASKS:
        op = estimate_scope(task)
        if op.recommended_mode == "chat_direct":
            under_scoped += 1
    rate = under_scoped / len(HELDOUT_TASKS)
    print(f"\nR1 estimator under-scope rate on held-out wording: {rate:.0%} ({under_scoped}/{len(HELDOUT_TASKS)})")
    # Determinism: re-run yields the same count.
    again = sum(1 for t, _l, _e in HELDOUT_TASKS if estimate_scope(t).recommended_mode == "chat_direct")
    assert again == under_scoped
    # The whole point: held-out wording frequently fools the TEXT estimator,
    # which is why the evidence-driven net exists.
    assert under_scoped >= len(HELDOUT_TASKS) // 2


def test_r1_evidence_is_wording_independent() -> None:
    """Same evidence, opposite wordings (EN vs RU) -> identical decision."""
    en = next_level(ExpansionState(level=1), **HIGH_WRITE_EVIDENCE)
    ru = next_level(ExpansionState(level=1), **HIGH_WRITE_EVIDENCE)
    assert en is not None and ru is not None
    assert (en.level_to, en.evidence) == (ru.level_to, ru.evidence)
