"""Existing-test-protection rule (research-note R-6) — both seats.

Covers :func:`fa.hygiene.pr_intent.parse_test_edits` /
:func:`fa.hygiene.pr_intent.validate_test_edits` directly, the
IntentGuard harness seat, and the two-seat closure property for
OPAQUE_EXEC / rename evasion (the staged ``D`` row surfaces at the
``git add`` / ``git commit`` INDEX_WRITE validation even when the
tool call itself made no touched-path claims).
"""

from __future__ import annotations

from pathlib import Path

from fa.hygiene.pr_intent import (
    Intent,
    StagedPath,
    Violation,
    parse_test_edits,
    validate_test_edits,
)
from fa.inner_loop.hooks.base import HookPayload, LifecyclePoint
from fa.inner_loop.hooks.intent_guard import IntentGuard
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.registry import ToolCall

# A FIX draft that passes every shape check (citation resolves against
# the fixture repo created in _make_guard_repo below).
_VALID_FIX_DRAFT = (
    "INTENT: FIX\n"
    "CLASS: REPAIR\n"
    "INVARIANT: Affects: src/fa/x.py\n"
    "DEGREE-OF-FREEDOM CLOSED: the retry path now clamps the budget\n"
    "DETERMINISTIC MECHANISM: clamp asserted at src/fa/x.py:1\n"
)

_VALID_FIX_DRAFT_WITH_DECLARATION = (
    _VALID_FIX_DRAFT + "TEST-EDITS:\ntests/test_x.py — fixture must track the new enum member\n"
)

_VALID_IMPLEMENT_DRAFT = (
    "INTENT: IMPLEMENT\nINVARIANT: Implements: knowledge/adr/ADR-7-inner-loop-tool-registry.md §8\n"
)


# ---------------------------------------------------------------------------
# parse_test_edits
# ---------------------------------------------------------------------------


def test_parse_block_entries_and_terminators() -> None:
    text = (
        "INTENT: FIX\n"
        "TEST-EDITS:\n"
        "tests/test_a.py — reason one\n"
        "tests/test_b.py - hyphen separator also fine\n"
        "\n"
        "tests/test_after_blank.py — NOT collected (block ended)\n"
    )
    declared = parse_test_edits(text)
    assert declared == {
        "tests/test_a.py": "reason one",
        "tests/test_b.py": "hyphen separator also fine",
    }


def test_parse_same_line_entry_and_header_terminator() -> None:
    text = (
        "TEST-EDITS: tests/test_inline.py — same-line entry\n"
        "tests/test_second.py — collected\n"
        "INVARIANT: Affects: src/fa/x.py\n"
        "tests/test_after_header.py — NOT collected\n"
    )
    declared = parse_test_edits(text)
    assert set(declared) == {"tests/test_inline.py", "tests/test_second.py"}


def test_parse_malformed_entries_excluded() -> None:
    # No separator, empty reason, empty path: all fail-closed (excluded).
    text = (
        "TEST-EDITS:\n"
        "tests/test_nosep.py reason without dash\n"
        "tests/test_empty.py — \n"
        "— reason only\n"
    )
    assert parse_test_edits(text) == {}


def test_parse_no_header_returns_empty() -> None:
    assert parse_test_edits("INTENT: FIX\n") == {}


# ---------------------------------------------------------------------------
# validate_test_edits — the rule matrix
# ---------------------------------------------------------------------------


def _codes(violations: list[Violation]) -> list[str]:
    return [v.code for v in violations]


def test_fix_undeclared_modify_blocked() -> None:
    v = validate_test_edits(_VALID_FIX_DRAFT, Intent.FIX, [StagedPath("M", "tests/test_x.py")])
    assert _codes(v) == ["test_edit_undeclared"]


def test_fix_declared_modify_allowed() -> None:
    v = validate_test_edits(
        _VALID_FIX_DRAFT_WITH_DECLARATION,
        Intent.FIX,
        [StagedPath("M", "tests/test_x.py")],
    )
    assert v == []


def test_delete_blocked_under_every_intent_even_declared() -> None:
    draft = _VALID_FIX_DRAFT + "TEST-EDITS:\ntests/test_x.py — declared but D has no escape\n"
    for intent in (Intent.FIX, Intent.IMPLEMENT, Intent.CHORE):
        v = validate_test_edits(draft, intent, [StagedPath("D", "tests/test_x.py")])
        assert _codes(v) == ["test_delete_blocked"], intent


def test_rename_dest_row_blocked_like_delete() -> None:
    # `git mv tests/test_x.py archive/` shows only the destination in
    # --name-status; a dest row UNDER tests/ (R/C) is still a removal
    # of the original and is blocked.
    v = validate_test_edits(
        _VALID_FIX_DRAFT, Intent.FIX, [StagedPath("R", "tests/test_renamed.py")]
    )
    assert _codes(v) == ["test_delete_blocked"]


def test_add_always_allowed_and_implement_modify_allowed() -> None:
    rows_a = [StagedPath("A", "tests/test_new.py")]
    assert validate_test_edits(_VALID_FIX_DRAFT, Intent.FIX, rows_a) == []
    assert (
        validate_test_edits(
            _VALID_IMPLEMENT_DRAFT, Intent.IMPLEMENT, [StagedPath("M", "tests/test_x.py")]
        )
        == []
    )


def test_non_test_paths_ignored() -> None:
    rows = [StagedPath("D", "src/fa/x.py"), StagedPath("M", "docs.md")]
    assert validate_test_edits(_VALID_FIX_DRAFT, Intent.FIX, rows) == []


def test_typed_intent_cannot_disarm() -> None:
    """SECURITY INVARIANT — the rule receives the classifier intent.

    A draft that types `INTENT: IMPLEMENT` over a FIX-shaped diff must
    still be blocked: callers pass classify_intent(...) output, never
    the typed override. This test pins the *call contract* by showing
    the rule fires for Intent.FIX regardless of what the draft says.
    """

    draft = _VALID_IMPLEMENT_DRAFT  # types IMPLEMENT
    v = validate_test_edits(draft, Intent.FIX, [StagedPath("M", "tests/test_x.py")])
    assert _codes(v) == ["test_edit_undeclared"]


# ---------------------------------------------------------------------------
# IntentGuard harness seat
# ---------------------------------------------------------------------------


def _make_guard(tmp_path: Path, *, draft_text: str, git_output: str) -> IntentGuard:
    repo_root = tmp_path / "repo"
    (repo_root / "src" / "fa").mkdir(parents=True)
    (repo_root / "src" / "fa" / "x.py").write_text("line1\n", encoding="utf-8")
    (repo_root / "knowledge").mkdir()
    (repo_root / "knowledge" / "llms.txt").write_text("placeholder\n", encoding="utf-8")
    (repo_root / "tests").mkdir()
    (repo_root / "tests" / "test_x.py").write_text(
        "def test_x():\n    assert 1\n", encoding="utf-8"
    )
    draft_store = PrDraftStore(tmp_path / "pr_draft.md")
    draft_store.write_text(draft_text)
    return IntentGuard(
        repo_root=repo_root,
        draft_store=draft_store,
        git_runner=lambda: git_output,
    )


def test_guard_denies_undeclared_test_write_under_fix(tmp_path: Path) -> None:
    guard = _make_guard(
        tmp_path,
        draft_text=_VALID_FIX_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(name="fs.write_file", params={"path": "tests/test_x.py", "content": "x"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert "test_edit_undeclared" not in decision.reason  # message text, not code
    assert "TEST-EDITS" in decision.reason


def test_guard_allows_declared_test_write_under_fix(tmp_path: Path) -> None:
    guard = _make_guard(
        tmp_path,
        draft_text=_VALID_FIX_DRAFT_WITH_DECLARATION,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(name="fs.write_file", params={"path": "tests/test_x.py", "content": "x"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"


def test_guard_denies_bash_rm_of_test_under_any_intent(tmp_path: Path) -> None:
    # `rm tests/test_x.py` analyzes REPO_WRITE and projects a D row.
    guard = _make_guard(
        tmp_path,
        draft_text=_VALID_FIX_DRAFT_WITH_DECLARATION,  # declared — D still blocked
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(name="fs.run_bash", params={"command": "rm tests/test_x.py"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert "deleting/renaming an existing test is blocked" in decision.reason


def test_guard_allows_new_test_file_write(tmp_path: Path) -> None:
    guard = _make_guard(
        tmp_path,
        draft_text=_VALID_FIX_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(name="fs.write_file", params={"path": "tests/test_new.py", "content": "x"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"  # status A — adding tests is always fine


def test_guard_typed_implement_override_does_not_disarm(tmp_path: Path) -> None:
    """An agent typing `INTENT: IMPLEMENT` over a FIX-shaped diff is
    still blocked from undeclared test edits (classifier-intent keying).

    The draft must be IMPLEMENT-shape-valid so the only violation left
    is the test-protection one — proving the deny came from R-6, not
    from a shape check.
    """

    guard = _make_guard(
        tmp_path,
        draft_text=_VALID_IMPLEMENT_DRAFT,
        git_output="M\tsrc/fa/x.py\n",  # M-only diff → classifier says FIX
    )
    call = ToolCall(name="fs.write_file", params={"path": "tests/test_x.py", "content": "x"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert "TEST-EDITS" in decision.reason


def test_two_seat_closure_index_write_sees_staged_delete(tmp_path: Path) -> None:
    """OPAQUE_EXEC / rename evasion closes at the INDEX_WRITE seat.

    A `git rm`/`python -c` deletion makes no touched-path claim at
    call time — but the staged snapshot at the next `git add`/`git
    commit` carries the real `D tests/...` row, and INDEX_WRITE
    validates against exactly that snapshot.
    """

    guard = _make_guard(
        tmp_path,
        draft_text=_VALID_FIX_DRAFT_WITH_DECLARATION,
        git_output="D\ttests/test_x.py\nM\tsrc/fa/x.py\n",  # post-deletion stage
    )
    call = ToolCall(name="fs.run_bash", params={"command": "git commit -m wip"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert "deleting/renaming an existing test is blocked" in decision.reason
