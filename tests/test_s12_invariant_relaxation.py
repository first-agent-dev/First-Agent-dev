"""S12.5 (CT5) — INVARIANT shape relaxation for RESEARCH and CHORE.

Live-trial D11: agents burned turns rediscovering the literal ``n/a``
token for intents that bind no invariant by definition. The user's
decision: drop the shape check for CHORE (plan default Q9 extends it
to RESEARCH), keep the INVARIANT *header* required, keep every other
intent's prefix table untouched.

Three seats, two code paths (S12 plan RN7):

1. ``pr_prepare`` tool early validation —
   ``prepare_pr._validate_invariant_prefix`` (early ``return None``
   before ``any()``, the empty-tuple trap).
2. Shared validator Check 3 — ``pr_intent.validate_commit_msg``
   (``if required and not any(...)``), consumed by the IntentGuard
   middleware AND the M-6 git hook AND the tool's own belt-and-braces
   downstream pass.

Kill-checks (mutation targets):

- Remove ``if not required: return None`` in prepare_pr → the
  free-form tool tests fail (early seat).
- Drop ``required and`` from Check 3 → the free-form tool tests fail
  again via the downstream pass, and the direct validator tests fail.
- Re-add a prefix for CHORE in the table → table-shape test fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.hygiene.pr_intent import (
    INVARIANT_REQUIRED_PREFIXES,
    Intent,
    validate_commit_msg,
)
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.registry import ToolResult
from fa.inner_loop.tools import build_prepare_pr_tool


@pytest.fixture()
def draft_path(tmp_path: Path) -> Path:
    return tmp_path / ".fa" / "session-log" / "s125" / "pr_draft.md"


@pytest.fixture()
def draft_store(draft_path: Path) -> PrDraftStore:
    return PrDraftStore(draft_path)


def _invoke(draft_store: PrDraftStore, params: dict[str, object]) -> ToolResult:
    tool = build_prepare_pr_tool(draft_store)
    return tool.handler(params)


# ---------------------------------------------------------------------------
# T5e — table shape (C0: the contract every seat reads)
# ---------------------------------------------------------------------------


def test_relaxed_intents_carry_empty_prefix_tuple() -> None:
    assert INVARIANT_REQUIRED_PREFIXES[Intent.CHORE] == ()
    assert INVARIANT_REQUIRED_PREFIXES[Intent.RESEARCH] == ()


def test_other_intents_keep_their_prefixes() -> None:
    """Control: the relaxation must not leak into shape-checked intents."""
    assert INVARIANT_REQUIRED_PREFIXES[Intent.ADR_RULE] == ("Contract:",)
    assert INVARIANT_REQUIRED_PREFIXES[Intent.IMPLEMENT] == ("Implements:",)
    assert INVARIANT_REQUIRED_PREFIXES[Intent.FIX] == ("Affects:",)


# ---------------------------------------------------------------------------
# T5a/T5b — tool seat (C1: through the shipped handler, both code paths)
# ---------------------------------------------------------------------------


def test_chore_freeform_invariant_accepted(draft_store: PrDraftStore, draft_path: Path) -> None:
    result = _invoke(draft_store, {"intent": "CHORE", "invariant": "dependency bump: pytest 8.x"})
    assert result.error is None, result.error
    assert draft_path.read_text(encoding="utf-8") == ("INTENT: CHORE\nINVARIANT: dependency bump: pytest 8.x\n")


def test_research_freeform_invariant_accepted(draft_store: PrDraftStore, draft_path: Path) -> None:
    result = _invoke(draft_store, {"intent": "RESEARCH", "invariant": "notes for the l3 review round"})
    assert result.error is None, result.error
    assert "INVARIANT: notes for the l3 review round" in draft_path.read_text(encoding="utf-8")


def test_legacy_na_still_accepted(draft_store: PrDraftStore) -> None:
    """Backward compatibility: the old canonical token still passes."""
    for intent in ("CHORE", "RESEARCH"):
        result = _invoke(draft_store, {"intent": intent, "invariant": "n/a"})
        assert result.error is None, (intent, result.error)


# ---------------------------------------------------------------------------
# T5c — shared-validator seat (C1: direct validate_commit_msg, the hook path)
# ---------------------------------------------------------------------------


def test_validator_accepts_freeform_for_relaxed_intents(tmp_path: Path) -> None:
    for intent in (Intent.CHORE, Intent.RESEARCH):
        text = f"INTENT: {intent.value}\nINVARIANT: whatever the author writes\n"
        violations = validate_commit_msg(text, intent, staged=[], repo_root=tmp_path)
        assert [v.code for v in violations] == [], (intent, violations)


def test_invariant_header_still_required(tmp_path: Path) -> None:
    """The relaxation is shape-only: a missing/empty INVARIANT line is
    still a violation for CHORE and RESEARCH."""
    for intent in (Intent.CHORE, Intent.RESEARCH):
        violations = validate_commit_msg(f"INTENT: {intent.value}\n", intent, staged=[], repo_root=tmp_path)
        assert "invariant_missing" in [v.code for v in violations], (intent, violations)


# ---------------------------------------------------------------------------
# T5d — controls (C1: shape-checked intents unchanged)
# ---------------------------------------------------------------------------


def test_implement_wrong_prefix_still_rejected_by_tool(draft_store: PrDraftStore) -> None:
    result = _invoke(draft_store, {"intent": "IMPLEMENT", "invariant": "some free text"})
    assert result.error is not None
    assert result.error.code == "invariant_shape_mismatch"


def test_validator_rejects_wrong_prefix_for_implement(tmp_path: Path) -> None:
    text = "INTENT: IMPLEMENT\nINVARIANT: some free text\n"
    violations = validate_commit_msg(text, Intent.IMPLEMENT, staged=[], repo_root=tmp_path)
    assert "invariant_shape_mismatch" in [v.code for v in violations]
