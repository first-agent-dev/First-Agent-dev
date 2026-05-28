"""Snapshot + behaviour tests for the PR-intent classifier (PR B — M-6).

The first test (:func:`test_output_format_matches_hook_constants`) is
**the dual-located-rule guard**: it reads the canonical contract
([`knowledge/skills/pr-creation/SKILL.md`](../knowledge/skills/pr-creation/SKILL.md)
§Output format) at test time and asserts the constants exported by
:mod:`fa.hygiene.pr_intent` match the fenced-block shape verbatim.
Any drift between the skill and the hook fails CI per the M-6
contract.

The rest of the file exercises the classifier branches, citation
resolution edge cases, the six commit-msg validation checks (each
with a positive + negative fixture), and the prepare-commit-msg
buffer rendering.
"""

from __future__ import annotations

import dataclasses
import re
import unittest.mock as mock
from pathlib import Path

import pytest

from fa.hygiene.pr_intent import (
    CLASS_VALUES,
    HEADER_CLASS,
    HEADER_DET_MECHANISM,
    HEADER_DOF_CLOSED,
    HEADER_INTENT,
    HEADER_INVARIANT,
    INTENT_VALUES,
    FieldSpec,
    Intent,
    StagedPath,
    _cli_prepare,
    _cli_validate,
    _is_non_validating_commit_source,
    classify_intent,
    derive_required_fields,
    detect_multi_intent,
    is_mirror_only,
    parse_name_status,
    render_prepare_buffer,
    resolve_citation,
    validate_commit_msg,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "knowledge" / "skills" / "pr-creation" / "SKILL.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_text_blocks_under(heading: str, body: str) -> list[str]:
    """Return every fenced ```text block under the given §-heading.

    The skill's §Output format section contains two fenced ```text
    blocks (the base header + the FIX-specific clauses). Both are
    pinned by the snapshot test.
    """

    section_pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(?P<body>.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = section_pattern.search(body)
    if match is None:
        raise AssertionError(f"section {heading!r} not found in skill")
    section_body = match.group("body")
    fence_pattern = re.compile(
        r"^```text\s*$(?P<content>.*?)^```\s*$",
        re.MULTILINE | re.DOTALL,
    )
    return [m.group("content") for m in fence_pattern.finditer(section_body)]


# ---------------------------------------------------------------------------
# Snapshot tests — pin hook constants to skill §Output format
# ---------------------------------------------------------------------------


def test_skill_file_exists() -> None:
    """Sanity check — the contract source is on disk before we pin it."""

    assert SKILL_PATH.is_file(), (
        f"missing contract source {SKILL_PATH}; the snapshot test cannot run without the skill."
    )


def test_output_format_matches_hook_constants() -> None:
    """Pin hook constants to the skill's §Output format fenced blocks.

    This is the dual-located-rule guard mandated by M-6. The skill
    is the single source of truth; the hook hard-codes the same
    anchors. This test re-reads the skill at test time so any drift
    fails CI immediately.
    """

    body = SKILL_PATH.read_text(encoding="utf-8")
    blocks = _extract_text_blocks_under("Output format", body)
    assert len(blocks) == 2, (
        "skill §Output format must contain exactly two ```text fenced "
        "blocks (base header + FIX clauses); found "
        f"{len(blocks)}."
    )
    base_block, fix_block = blocks

    # Header anchors.
    assert HEADER_INTENT in base_block
    assert HEADER_CLASS in base_block
    assert HEADER_INVARIANT in base_block
    assert HEADER_DOF_CLOSED in fix_block
    assert HEADER_DET_MECHANISM in fix_block

    # Intent enum values pulled out of the `<RESEARCH | ADR-RULE | ...>`
    # alternatives in the skill.
    intent_alt_match = re.search(
        rf"{re.escape(HEADER_INTENT)}\s*<(?P<alts>[^>]+)>",
        base_block,
    )
    assert intent_alt_match is not None
    intent_alts = {token.strip() for token in intent_alt_match.group("alts").split("|")}
    assert intent_alts == INTENT_VALUES, (
        f"skill INTENT alternatives {intent_alts} drift from hook INTENT_VALUES {INTENT_VALUES}."
    )

    # FIX-class enum values pulled out of `[CLASS: <REPAIR | ...>]`.
    class_alt_match = re.search(
        rf"{re.escape(HEADER_CLASS)}\s*<(?P<alts>[^>]+)>",
        base_block,
    )
    assert class_alt_match is not None
    class_alts = {token.strip() for token in class_alt_match.group("alts").split("|")}
    assert class_alts == CLASS_VALUES, (
        f"skill CLASS alternatives {class_alts} drift from hook CLASS_VALUES {CLASS_VALUES}."
    )

    # Citation grammar mention — the FIX block must require a
    # `repo/file.ext:line` citation.
    assert "repo/file.ext:line" in fix_block
    assert "n/a (reason)" in fix_block


# ---------------------------------------------------------------------------
# classify_intent — one test per Level-1 branch + resolution
# ---------------------------------------------------------------------------


def _staged(rows: list[tuple[str, str]]) -> list[StagedPath]:
    return [StagedPath(status=s, path=p) for s, p in rows]


def test_classify_intent_research_only_adds() -> None:
    assert (
        classify_intent(_staged([("A", "knowledge/research/note-2026-05.md")])) == Intent.RESEARCH
    )


def test_classify_intent_adr_rule_via_adr_path() -> None:
    assert classify_intent(_staged([("M", "knowledge/adr/ADR-7-foo.md")])) == Intent.ADR_RULE


def test_classify_intent_adr_rule_via_agents_md() -> None:
    assert classify_intent(_staged([("M", "AGENTS.md")])) == Intent.ADR_RULE


def test_classify_intent_adr_rule_via_skill() -> None:
    assert (
        classify_intent(_staged([("M", "knowledge/skills/pr-creation/SKILL.md")]))
        == Intent.ADR_RULE
    )


def test_classify_intent_implement_pure_adds_under_src() -> None:
    assert (
        classify_intent(
            _staged(
                [
                    ("A", "src/fa/hygiene/pr_intent.py"),
                    ("A", "tests/test_pr_intent_snapshot.py"),
                ]
            )
        )
        == Intent.IMPLEMENT
    )


def test_classify_intent_fix_modified_src() -> None:
    assert classify_intent(_staged([("M", "src/fa/inner_loop/loop.py")])) == Intent.FIX


def test_classify_intent_fix_mixed_add_modify_src() -> None:
    assert (
        classify_intent(
            _staged(
                [
                    ("A", "src/fa/hygiene/new_helper.py"),
                    ("M", "src/fa/hygiene/__init__.py"),
                ]
            )
        )
        == Intent.FIX
    )


def test_classify_intent_chore_via_pyproject() -> None:
    assert classify_intent(_staged([("M", "pyproject.toml")])) == Intent.CHORE


def test_classify_intent_chore_via_github_workflow() -> None:
    assert classify_intent(_staged([("M", ".github/workflows/ci.yml")])) == Intent.CHORE


def test_classify_intent_resolution_adr_rule_dominates_research() -> None:
    """ADR-RULE wins over RESEARCH per cross-category resolution."""

    fired = detect_multi_intent(
        _staged(
            [
                ("A", "knowledge/research/note.md"),
                ("M", "knowledge/adr/ADR-7-foo.md"),
            ]
        )
    )
    assert Intent.ADR_RULE in fired and Intent.RESEARCH in fired
    assert (
        classify_intent(
            _staged(
                [
                    ("A", "knowledge/research/note.md"),
                    ("M", "knowledge/adr/ADR-7-foo.md"),
                ]
            )
        )
        == Intent.ADR_RULE
    )


def test_classify_intent_resolution_implement_dominates_research() -> None:
    """IMPLEMENT > RESEARCH per resolution order."""

    assert (
        classify_intent(
            _staged(
                [
                    ("A", "knowledge/research/note.md"),
                    ("A", "src/fa/hygiene/new_module.py"),
                ]
            )
        )
        == Intent.IMPLEMENT
    )


def test_classify_intent_mirror_only_returns_chore() -> None:
    """Mirror-only diffs default to CHORE; warning surface is separate."""

    staged = _staged([("M", "HANDOFF.md"), ("M", "knowledge/llms.txt")])
    assert is_mirror_only(staged)
    assert classify_intent(staged) == Intent.CHORE


def test_detect_multi_intent_surfaces_warning_set() -> None:
    """The multi-intent warning surface returns all fired buckets."""

    fired = detect_multi_intent(
        _staged(
            [
                ("M", "AGENTS.md"),
                ("M", "src/fa/inner_loop/loop.py"),
            ]
        )
    )
    assert fired == {Intent.ADR_RULE, Intent.FIX}


# ---------------------------------------------------------------------------
# derive_required_fields / render_prepare_buffer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "intent",
    [Intent.RESEARCH, Intent.ADR_RULE, Intent.IMPLEMENT, Intent.FIX, Intent.CHORE],
)
def test_derive_required_fields_includes_intent_and_invariant(intent: Intent) -> None:
    fields = derive_required_fields(intent)
    names = [f.name for f in fields]
    assert "INTENT" in names
    assert "INVARIANT" in names


def test_derive_required_fields_fix_includes_fix_only_clauses() -> None:
    fields = derive_required_fields(Intent.FIX)
    names = [f.name for f in fields]
    assert "CLASS" in names
    assert "DEGREE-OF-FREEDOM CLOSED" in names
    assert "DETERMINISTIC MECHANISM" in names


def test_render_prepare_buffer_emits_intent_line() -> None:
    buffer = render_prepare_buffer(Intent.IMPLEMENT)
    assert buffer.splitlines()[0] == "INTENT: IMPLEMENT"


def test_render_prepare_buffer_uses_placeholder_for_invariant() -> None:
    buffer = render_prepare_buffer(Intent.ADR_RULE)
    assert any(line.startswith("INVARIANT: <fill me") for line in buffer.splitlines())


# ---------------------------------------------------------------------------
# validate_commit_msg — positive + negative fixture per check
# ---------------------------------------------------------------------------


def test_validate_research_positive(tmp_path: Path) -> None:
    msg = "INTENT: RESEARCH\nINVARIANT: n/a\n\nBody…"
    violations = validate_commit_msg(msg, Intent.RESEARCH, [], tmp_path)
    assert violations == []


def test_validate_intent_missing_violation(tmp_path: Path) -> None:
    msg = "INVARIANT: n/a\n\nBody…"
    violations = validate_commit_msg(msg, Intent.RESEARCH, [], tmp_path)
    codes = [v.code for v in violations]
    assert "intent_missing" in codes


def test_validate_intent_value_invalid(tmp_path: Path) -> None:
    msg = "INTENT: NOT-A-LABEL\nINVARIANT: n/a\n"
    violations = validate_commit_msg(msg, Intent.RESEARCH, [], tmp_path)
    codes = [v.code for v in violations]
    assert "intent_value_invalid" in codes


def test_validate_class_unexpected_when_not_fix(tmp_path: Path) -> None:
    msg = "INTENT: ADR-RULE\nCLASS: REPAIR\nINVARIANT: Contract: foo\n"
    violations = validate_commit_msg(msg, Intent.ADR_RULE, [], tmp_path)
    codes = [v.code for v in violations]
    assert "class_unexpected" in codes


def test_validate_class_missing_when_fix(tmp_path: Path) -> None:
    msg = (
        "INTENT: FIX\n"
        "INVARIANT: Affects: ADR-7 §5\n"
        "DEGREE-OF-FREEDOM CLOSED: x\n"
        "DETERMINISTIC MECHANISM: y src/fa/cli.py:1\n"
    )
    violations = validate_commit_msg(msg, Intent.FIX, [], tmp_path)
    codes = [v.code for v in violations]
    assert "class_missing" in codes


def test_validate_class_value_invalid(tmp_path: Path) -> None:
    msg = (
        "INTENT: FIX\n"
        "CLASS: SOMETHING-ELSE\n"
        "INVARIANT: Affects: ADR-7\n"
        "DEGREE-OF-FREEDOM CLOSED: x\n"
        "DETERMINISTIC MECHANISM: y src/fa/cli.py:1\n"
    )
    violations = validate_commit_msg(msg, Intent.FIX, [], tmp_path)
    codes = [v.code for v in violations]
    assert "class_value_invalid" in codes


def test_validate_invariant_shape_mismatch_for_adr_rule(tmp_path: Path) -> None:
    msg = "INTENT: ADR-RULE\nINVARIANT: Random prose without prefix\n"
    violations = validate_commit_msg(msg, Intent.ADR_RULE, [], tmp_path)
    codes = [v.code for v in violations]
    assert "invariant_shape_mismatch" in codes


def test_validate_invariant_shape_mismatch_for_implement(tmp_path: Path) -> None:
    msg = "INTENT: IMPLEMENT\nINVARIANT: Affects: not-implements\n"
    violations = validate_commit_msg(msg, Intent.IMPLEMENT, [], tmp_path)
    codes = [v.code for v in violations]
    assert "invariant_shape_mismatch" in codes


def test_validate_fix_dof_missing(tmp_path: Path) -> None:
    msg = (
        "INTENT: FIX\n"
        "CLASS: REPAIR\n"
        "INVARIANT: Affects: ADR-7 §5\n"
        "DETERMINISTIC MECHANISM: y src/fa/cli.py:1\n"
    )
    violations = validate_commit_msg(msg, Intent.FIX, [], tmp_path)
    codes = [v.code for v in violations]
    assert "dof_missing" in codes


def test_validate_fix_mechanism_missing(tmp_path: Path) -> None:
    msg = (
        "INTENT: FIX\n"
        "CLASS: REPAIR\n"
        "INVARIANT: Affects: ADR-7 §5\n"
        "DEGREE-OF-FREEDOM CLOSED: closes the freedom\n"
    )
    violations = validate_commit_msg(msg, Intent.FIX, [], tmp_path)
    codes = [v.code for v in violations]
    assert "mechanism_missing" in codes


def test_validate_fix_mechanism_citation_unresolved(tmp_path: Path) -> None:
    msg = (
        "INTENT: FIX\n"
        "CLASS: REPAIR\n"
        "INVARIANT: Affects: ADR-7 §5\n"
        "DEGREE-OF-FREEDOM CLOSED: producer-site decision X\n"
        "DETERMINISTIC MECHANISM: closes via src/nope/missing.py:42\n"
    )
    violations = validate_commit_msg(msg, Intent.FIX, [], tmp_path)
    codes = [v.code for v in violations]
    assert "mechanism_citation_unresolved" in codes


def test_validate_fix_tautology_check(tmp_path: Path) -> None:
    target = tmp_path / "src" / "fa" / "cli.py"
    target.parent.mkdir(parents=True)
    target.write_text("a\nb\nc\n", encoding="utf-8")
    msg = (
        "INTENT: FIX\n"
        "CLASS: REPAIR\n"
        "INVARIANT: Affects: ADR-7 §5\n"
        "DEGREE-OF-FREEDOM CLOSED: producer-site decision X src/fa/cli.py:1\n"
        "DETERMINISTIC MECHANISM:   producer-site decision X src/fa/cli.py:1\n"
    )
    violations = validate_commit_msg(msg, Intent.FIX, [], tmp_path)
    codes = [v.code for v in violations]
    assert "fix_tautology" in codes


def test_validate_fix_positive_with_resolving_citation(tmp_path: Path) -> None:
    target = tmp_path / "src" / "fa" / "cli.py"
    target.parent.mkdir(parents=True)
    target.write_text("line1\nline2\nline3\n", encoding="utf-8")
    msg = (
        "INTENT: FIX\n"
        "CLASS: REPAIR\n"
        "INVARIANT: Affects: ADR-7 §5 Input validation\n"
        "DEGREE-OF-FREEDOM CLOSED: schema field accepts list or scalar\n"
        "DETERMINISTIC MECHANISM: list-shape enforced at src/fa/cli.py:2\n"
    )
    violations = validate_commit_msg(msg, Intent.FIX, [], tmp_path)
    assert violations == []


def test_validate_fix_accepts_na_reason(tmp_path: Path) -> None:
    msg = (
        "INTENT: FIX\n"
        "CLASS: REPAIR\n"
        "INVARIANT: Affects: ADR-7 §5\n"
        "DEGREE-OF-FREEDOM CLOSED: n/a (pure refactor)\n"
        "DETERMINISTIC MECHANISM: n/a (pure refactor)\n"
    )
    violations = validate_commit_msg(msg, Intent.FIX, [], tmp_path)
    # Tautology check still fires when both are identical n/a strings.
    codes = [v.code for v in violations]
    assert "mechanism_citation_unresolved" not in codes
    assert "fix_tautology" in codes


# ---------------------------------------------------------------------------
# resolve_citation
# ---------------------------------------------------------------------------


def test_resolve_citation_file_not_present(tmp_path: Path) -> None:
    assert not resolve_citation("foo src/fa/missing.py:1", tmp_path, [])


def test_resolve_citation_line_out_of_bounds(tmp_path: Path) -> None:
    target = tmp_path / "f.py"
    target.write_text("only one line\n", encoding="utf-8")
    assert not resolve_citation("x f.py:99", tmp_path, [])


def test_resolve_citation_line_in_bounds(tmp_path: Path) -> None:
    target = tmp_path / "f.py"
    target.write_text("a\nb\nc\n", encoding="utf-8")
    assert resolve_citation("x f.py:2", tmp_path, [])


def test_resolve_citation_accepts_backticks(tmp_path: Path) -> None:
    target = tmp_path / "f.py"
    target.write_text("a\nb\n", encoding="utf-8")
    assert resolve_citation("x `f.py:1`", tmp_path, [])


def test_resolve_citation_na_reason_accepted(tmp_path: Path) -> None:
    assert resolve_citation("n/a (pure refactor)", tmp_path, [])


def test_resolve_citation_na_without_reason_rejected(tmp_path: Path) -> None:
    assert not resolve_citation("n/a", tmp_path, [])


def test_resolve_citation_staged_only_accepted(tmp_path: Path) -> None:
    """File not yet on disk but recorded as staged → accept."""

    staged = [StagedPath(status="A", path="src/fa/new.py")]
    assert resolve_citation("via src/fa/new.py:1", tmp_path, staged)


def test_resolve_citation_rejects_path_escape(tmp_path: Path) -> None:
    """Citations may not point outside the repo root."""

    assert not resolve_citation("../../etc/passwd:1", tmp_path, [])


# ---------------------------------------------------------------------------
# parse_name_status — git diff --cached --name-status helper
# ---------------------------------------------------------------------------


def test_parse_name_status_handles_add_and_modify() -> None:
    stdout = "A\tsrc/fa/new.py\nM\tsrc/fa/old.py\n"
    rows = parse_name_status(stdout)
    assert rows == [
        StagedPath("A", "src/fa/new.py"),
        StagedPath("M", "src/fa/old.py"),
    ]


def test_parse_name_status_uses_destination_for_renames() -> None:
    stdout = "R100\tsrc/fa/old.py\tsrc/fa/new.py\n"
    rows = parse_name_status(stdout)
    assert rows == [StagedPath("R", "src/fa/new.py")]


def test_parse_name_status_ignores_blank_lines() -> None:
    stdout = "\nA\tfoo.py\n\n"
    rows = parse_name_status(stdout)
    assert rows == [StagedPath("A", "foo.py")]


# ---------------------------------------------------------------------------
# FieldSpec smoke
# ---------------------------------------------------------------------------


def test_fieldspec_is_immutable() -> None:
    """Frozen dataclass: mutation raises FrozenInstanceError at runtime."""

    spec = FieldSpec(name="INTENT", placeholder="RESEARCH")
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.name = "OTHER"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Bug-fix regression tests (added post-review)
# ---------------------------------------------------------------------------


# --- Bug #1: knowledge/llms.txt dual membership (dead CHORE entry) ----------


def test_llms_txt_not_in_chore_exact_paths() -> None:
    """knowledge/llms.txt must live in _MIRROR_PATHS only, not _CHORE_EXACT_PATHS.

    The former dual membership made the CHORE-set entry dead code: the
    mirror filter in _fired_intents runs first, so llms.txt was always
    stripped before the CHORE check could fire. Removing it from
    _CHORE_EXACT_PATHS eliminates the confusion without changing
    observable behaviour (standalone llms.txt → CHORE via fallback).
    """
    from fa.hygiene.pr_intent import _CHORE_EXACT_PATHS, _MIRROR_PATHS

    assert "knowledge/llms.txt" in _MIRROR_PATHS
    assert "knowledge/llms.txt" not in _CHORE_EXACT_PATHS


def test_llms_txt_standalone_still_gives_chore() -> None:
    """Standalone knowledge/llms.txt commit still classifies as CHORE."""
    assert classify_intent(_staged([("M", "knowledge/llms.txt")])) == Intent.CHORE


def test_llms_txt_ride_along_is_transparent() -> None:
    """knowledge/llms.txt alongside a src change does not distort the intent."""
    result = classify_intent(
        _staged([("M", "knowledge/llms.txt"), ("M", "src/fa/inner_loop/loop.py")])
    )
    assert result == Intent.FIX


# --- Bug #2: Sequence[StagedPath] contract (replaces Iterable) --------------


def test_classify_intent_accepts_list_not_generator() -> None:
    """classify_intent must accept a list (Sequence); calling twice gives same result."""
    rows: list[StagedPath] = [StagedPath("A", "src/fa/new.py")]
    assert classify_intent(rows) == Intent.IMPLEMENT
    assert classify_intent(rows) == Intent.IMPLEMENT


# --- Bug #6: blank-line separator between header and existing content --------


def test_cli_prepare_blank_line_between_header_and_existing(tmp_path: Path) -> None:
    """_cli_prepare must insert a blank line between the header block and the
    existing commit-message template text so editors render them as distinct
    paragraphs and the validator can easily locate the header.
    """
    msg_file = tmp_path / "COMMIT_EDITMSG"
    existing = "# Please enter the commit message for your changes.\n"
    msg_file.write_text(existing, encoding="utf-8")

    with mock.patch("fa.hygiene.pr_intent._run_git", return_value=""):
        _cli_prepare(msg_file, tmp_path)

    result = msg_file.read_text(encoding="utf-8")
    lines = result.splitlines()

    try:
        invariant_idx = next(i for i, line in enumerate(lines) if line.startswith("INVARIANT:"))
    except StopIteration as exc:
        raise AssertionError(f"INVARIANT: line not found in buffer:\n{result}") from exc

    assert invariant_idx + 1 < len(lines), "No line after INVARIANT: line"
    assert lines[invariant_idx + 1] == "", (
        f"Expected blank separator after INVARIANT:, got {lines[invariant_idx + 1]!r}"
    )


def test_cli_prepare_no_double_trailing_newline(tmp_path: Path) -> None:
    """_cli_prepare must not produce more than one trailing newline."""
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("# git comment\n", encoding="utf-8")

    with mock.patch("fa.hygiene.pr_intent._run_git", return_value=""):
        _cli_prepare(msg_file, tmp_path)

    result = msg_file.read_text(encoding="utf-8")
    assert result.endswith("\n"), "File must end with newline"
    assert not result.endswith("\n\n"), f"Must not end with double newline; got {result!r}"


# --- Bug #7: commit-msg hook must skip git-generated messages ---------------


def test_is_non_validating_commit_source_merge_head(tmp_path: Path) -> None:
    """MERGE_HEAD marker → _is_non_validating_commit_source returns True."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "MERGE_HEAD").write_text("abc123\n", encoding="utf-8")
    assert _is_non_validating_commit_source(tmp_path) is True


def test_is_non_validating_commit_source_cherry_pick_head(tmp_path: Path) -> None:
    """CHERRY_PICK_HEAD marker → _is_non_validating_commit_source returns True."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "CHERRY_PICK_HEAD").write_text("abc123\n", encoding="utf-8")
    assert _is_non_validating_commit_source(tmp_path) is True


def test_is_non_validating_commit_source_revert_head(tmp_path: Path) -> None:
    """REVERT_HEAD marker → _is_non_validating_commit_source returns True."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "REVERT_HEAD").write_text("abc123\n", encoding="utf-8")
    assert _is_non_validating_commit_source(tmp_path) is True


def test_is_non_validating_commit_source_amend_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GIT_REFLOG_ACTION=commit (amend) → _is_non_validating_commit_source returns True."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.setenv("GIT_REFLOG_ACTION", "commit (amend)")
    assert _is_non_validating_commit_source(tmp_path) is True


def test_is_non_validating_commit_source_merge_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GIT_REFLOG_ACTION=merge → _is_non_validating_commit_source returns True."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.setenv("GIT_REFLOG_ACTION", "merge")
    assert _is_non_validating_commit_source(tmp_path) is True


def test_is_non_validating_commit_source_normal_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normal author-written commit → _is_non_validating_commit_source returns False."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.delenv("GIT_REFLOG_ACTION", raising=False)
    assert _is_non_validating_commit_source(tmp_path) is False


def test_cli_validate_skips_merge_commit(tmp_path: Path) -> None:
    """_cli_validate returns 0 for a merge commit lacking INTENT/INVARIANT headers."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "MERGE_HEAD").write_text("abc123\n", encoding="utf-8")

    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("Merge branch 'main' into feature-x\n", encoding="utf-8")

    with mock.patch("fa.hygiene.pr_intent._run_git", return_value=""):
        rc = _cli_validate(msg_file, tmp_path)

    assert rc == 0, "merge commit must not be blocked by commit-msg validator"


def test_cli_validate_blocks_headerless_normal_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_cli_validate returns 1 for a normal commit without INTENT header."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.delenv("GIT_REFLOG_ACTION", raising=False)

    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("docs: quick fix typo\n", encoding="utf-8")

    with mock.patch("fa.hygiene.pr_intent._run_git", return_value=""):
        rc = _cli_validate(msg_file, tmp_path)

    assert rc == 1, "headerless normal commit must be blocked"
