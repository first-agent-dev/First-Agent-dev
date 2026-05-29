"""Tests for the ``pr.prepare`` tool (M-7 §Q-N producer).

The tool writes the per-session PR-description draft IntentGuard reads;
ADR-10 I-1 says it must share validators with the M-6 git hook and the
M-7 middleware. These tests pin three things:

1. Happy paths for each closed-enum :class:`Intent` produce the
   canonical header block ``validate_commit_msg`` accepts back.
2. Validation refuses missing FIX clauses, wrong invariant prefixes,
   and ``fix_class`` set on non-FIX intents — mirroring Checks 2 + 3 + 4
   of :func:`fa.hygiene.pr_intent.validate_commit_msg`.
3. The draft round-trips through
   :func:`fa.hygiene.pr_intent.classify_intent` /
   :func:`fa.hygiene.pr_intent.validate_commit_msg` without surfacing
   violations the tool itself did not already deny.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.hygiene.pr_intent import (
    HEADER_CLASS,
    HEADER_DET_MECHANISM,
    HEADER_DOF_CLOSED,
    HEADER_INTENT,
    HEADER_INVARIANT,
    Intent,
    validate_commit_msg,
)
from fa.inner_loop.registry import ToolError, ToolResult
from fa.inner_loop.tools import build_prepare_pr_tool


@pytest.fixture()
def draft_path(tmp_path: Path) -> Path:
    return tmp_path / ".fa" / "state" / "runs" / "test-run" / "pr_draft.md"


def _invoke(draft_path: Path, params: dict[str, object]) -> ToolResult:
    tool = build_prepare_pr_tool(draft_path)
    return tool.handler(params)


def test_happy_path_implement_writes_canonical_headers(draft_path: Path) -> None:
    result = _invoke(
        draft_path,
        {"intent": "IMPLEMENT", "invariant": "Implements: prepare_pr tool (M-7 Q-N)"},
    )
    assert result.error is None, result.error
    assert draft_path.is_file()
    text = draft_path.read_text(encoding="utf-8")
    assert text.startswith(f"{HEADER_INTENT} IMPLEMENT\n")
    assert f"{HEADER_INVARIANT} Implements: prepare_pr tool (M-7 Q-N)" in text
    assert HEADER_CLASS not in text  # CLASS is FIX-only


def test_happy_path_research_accepts_n_a_invariant(draft_path: Path) -> None:
    result = _invoke(draft_path, {"intent": "RESEARCH", "invariant": "n/a"})
    assert result.error is None
    assert draft_path.read_text(encoding="utf-8").startswith(f"{HEADER_INTENT} RESEARCH\n")


def test_happy_path_adr_rule_requires_contract_prefix(draft_path: Path) -> None:
    result = _invoke(
        draft_path,
        {"intent": "ADR-RULE", "invariant": "Contract: amends skill §Output format"},
    )
    assert result.error is None


def test_happy_path_fix_emits_all_clauses(draft_path: Path) -> None:
    result = _invoke(
        draft_path,
        {
            "intent": "FIX",
            "invariant": "Affects: fa.cli._cmd_run when role missing",
            "fix_class": "REPAIR",
            "degree_of_freedom_closed": "role lookup is now closed-enum-validated",
            "deterministic_mechanism": (
                "raise SystemExit(2) before chain construction; src/fa/cli.py:298"
            ),
        },
    )
    assert result.error is None, result.error
    text = draft_path.read_text(encoding="utf-8")
    assert f"{HEADER_INTENT} FIX" in text
    assert f"{HEADER_CLASS} REPAIR" in text
    assert f"{HEADER_DOF_CLOSED} role lookup" in text
    assert f"{HEADER_DET_MECHANISM} raise SystemExit" in text


def test_optional_body_appended_after_blank_line(draft_path: Path) -> None:
    body = "Free-form rationale for reviewers."
    result = _invoke(
        draft_path,
        {
            "intent": "CHORE",
            "invariant": "n/a",
            "body": body,
        },
    )
    assert result.error is None
    text = draft_path.read_text(encoding="utf-8")
    assert text.endswith(f"\n\n{body}\n")


def test_unknown_intent_returns_invalid_params(draft_path: Path) -> None:
    result = _invoke(draft_path, {"intent": "BOGUS", "invariant": "n/a"})
    assert isinstance(result.error, ToolError)
    assert result.error.code == "invalid_params"
    assert not draft_path.exists()


def test_invariant_shape_mismatch_returns_violation(draft_path: Path) -> None:
    # IMPLEMENT requires ``Implements:`` prefix; ``Affects:`` is the FIX shape.
    result = _invoke(
        draft_path,
        {"intent": "IMPLEMENT", "invariant": "Affects: wrong shape on purpose"},
    )
    assert isinstance(result.error, ToolError)
    assert result.error.code == "invariant_shape_mismatch"
    assert not draft_path.exists()


def test_fix_without_fix_class_refuses_early(draft_path: Path) -> None:
    result = _invoke(
        draft_path,
        {
            "intent": "FIX",
            "invariant": "Affects: something",
            "degree_of_freedom_closed": "dof",
            "deterministic_mechanism": "mech",
        },
    )
    assert isinstance(result.error, ToolError)
    assert result.error.code == "invalid_params"
    assert "fix_class" in result.error.message
    assert not draft_path.exists()


def test_non_fix_with_fix_class_refused(draft_path: Path) -> None:
    result = _invoke(
        draft_path,
        {"intent": "IMPLEMENT", "invariant": "Implements: x", "fix_class": "REPAIR"},
    )
    assert isinstance(result.error, ToolError)
    assert result.error.code == "invalid_params"
    assert "only valid when" in result.error.message
    assert not draft_path.exists()


def test_missing_required_invariant_refused(draft_path: Path) -> None:
    result = _invoke(draft_path, {"intent": "RESEARCH"})
    assert isinstance(result.error, ToolError)
    assert result.error.code == "invalid_params"


def test_overwrite_replaces_existing_draft(draft_path: Path) -> None:
    _invoke(draft_path, {"intent": "RESEARCH", "invariant": "n/a"})
    first = draft_path.read_text(encoding="utf-8")
    result = _invoke(
        draft_path,
        {"intent": "IMPLEMENT", "invariant": "Implements: rerun"},
    )
    assert result.error is None
    second = draft_path.read_text(encoding="utf-8")
    assert first != second
    assert f"{HEADER_INTENT} IMPLEMENT" in second
    assert "RESEARCH" not in second


def test_parent_dirs_created_when_missing(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c" / "pr_draft.md"
    result = _invoke(nested, {"intent": "RESEARCH", "invariant": "n/a"})
    assert result.error is None
    assert nested.is_file()


def test_rendered_draft_round_trips_through_validator(draft_path: Path) -> None:
    """Single-source-of-truth check: validate_commit_msg accepts our output."""
    _invoke(
        draft_path,
        {
            "intent": "FIX",
            "invariant": "Affects: src/fa/cli.py role lookup",
            "fix_class": "REPAIR",
            "degree_of_freedom_closed": "role lookup closed-enum-validated",
            # ``mechanism_citation_unresolved`` is filtered by the tool;
            # ``validate_commit_msg`` will surface it here because the
            # citation does not resolve in this synthetic test repo.
            "deterministic_mechanism": "n/a (tested via tmp_path; no staged tree)",
        },
    )
    text = draft_path.read_text(encoding="utf-8")
    violations = validate_commit_msg(text, Intent.FIX, staged=[], repo_root=draft_path.parent)
    assert violations == []


def test_tool_spec_metadata_is_stable(draft_path: Path) -> None:
    """Schema / permission / tags drift would silently break the registry."""
    spec = build_prepare_pr_tool(draft_path)
    assert spec.name == "pr.prepare"
    assert spec.permission == "workspace"
    assert "draft" in spec.tags
    schema = spec.input_schema
    properties = schema["properties"]
    assert isinstance(properties, dict)
    assert sorted(properties.keys()) == [
        "body",
        "degree_of_freedom_closed",
        "deterministic_mechanism",
        "fix_class",
        "intent",
        "invariant",
    ]
    assert schema["required"] == ["intent", "invariant"]
