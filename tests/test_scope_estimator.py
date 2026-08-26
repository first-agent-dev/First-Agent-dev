"""Tests for scope_estimator module (C0 + C0p).

Test class: C0 (pure unit) + C0p (property/boundary)
Oracle: exact OperatingPoint field match
Kill-check: N/A (pure function, no producer site yet; S3 will wire it)

Path inventory:
  Path 1: L1 task (single-file, simple) → difficulty=1, mode=chat_direct
  Path 2: L2 task (cross-file, medium) → difficulty=2, mode=chat_planned
  Path 3: L3 task (repo, complex) → difficulty=3, mode=workflow_linear
  Path 4: No signals (optimistic default) → difficulty=1, confidence=0.3
  Path 5: Security boost → difficulty += 1 (capped at 3)
  Path 6: Empty/whitespace → ValueError

Matrix coverage:
  M1: L1 task with 1 match → confidence=0.6
  M2: L1 task with ≥2 matches → confidence=0.8
  M3: L2 task with 1 match → confidence=0.6
  M4: L2 task with ≥2 matches → confidence=0.8
  M5: L3 task with 1 match → confidence=0.6
  M6: L3 task with ≥2 matches → confidence=0.8
  M7: No signals → confidence=0.3
  M8: Security boost (L1 + security) → difficulty=2
  M9: Security boost (L2 + security) → difficulty=3
"""

from __future__ import annotations

import pytest

from fa.inner_loop.scope_estimator import OperatingPoint, estimate_scope

# 15 explicit fixtures (5 per level) with expected OperatingPoint.
# Confidence values are derived from the actual match count:
#   0.8 if ≥2 matches at the winning level, 0.6 if 1 match, 0.3 if 0 matches.
FIXTURES: list[tuple[str, OperatingPoint]] = [
    # ── L1 tasks (single-file, simple) ──────────────────────────────────
    # "fix typo" matches L1 pattern "fix typo" → 1 match → confidence=0.6
    (
        "fix typo in README.md",
        OperatingPoint(
            difficulty=1,
            scope="single-file",
            risk="low",
            confidence=0.6,
            recommended_mode="chat_direct",
        ),
    ),
    # "rename" matches L1 pattern "rename" → 1 match → confidence=0.6
    (
        "rename variable foo to bar",
        OperatingPoint(
            difficulty=1,
            scope="single-file",
            risk="low",
            confidence=0.6,
            recommended_mode="chat_direct",
        ),
    ),
    # "update docstring" matches L1 pattern "update.*docstring" → 1 match → confidence=0.6
    (
        "update docstring in function baz",
        OperatingPoint(
            difficulty=1,
            scope="single-file",
            risk="low",
            confidence=0.6,
            recommended_mode="chat_direct",
        ),
    ),
    # No L1 pattern matches "fix single line bug" exactly → 0 matches → confidence=0.3
    (
        "fix single line bug",
        OperatingPoint(
            difficulty=1,
            scope="single-file",
            risk="low",
            confidence=0.3,
            recommended_mode="chat_direct",
        ),
    ),
    # No L1 pattern matches "add comment" → 0 matches → confidence=0.3
    (
        "add comment to clarify logic",
        OperatingPoint(
            difficulty=1,
            scope="single-file",
            risk="low",
            confidence=0.3,
            recommended_mode="chat_direct",
        ),
    ),
    # ── L2 tasks (cross-file, medium) ───────────────────────────────────
    # "implement" matches L2 pattern → 1 match → confidence=0.6
    (
        "implement error handling in fs_read_file",
        OperatingPoint(
            difficulty=2,
            scope="cross-file",
            risk="medium",
            confidence=0.6,
            recommended_mode="chat_planned",
        ),
    ),
    # "implement" + "new command" → 2 L2 matches → confidence=0.8
    (
        "implement new CLI command fa ask",
        OperatingPoint(
            difficulty=2,
            scope="cross-file",
            risk="medium",
            confidence=0.8,
            recommended_mode="chat_planned",
        ),
    ),
    # "add function" matches L2 pattern → 1 match → confidence=0.6
    (
        "add function to handle user authentication",
        OperatingPoint(
            difficulty=2,
            scope="cross-file",
            risk="medium",
            confidence=0.6,
            recommended_mode="chat_planned",
        ),
    ),
    # "2 files" matches L2 pattern → 1 match → confidence=0.6
    (
        "update 2 files to fix import cycle",
        OperatingPoint(
            difficulty=2,
            scope="cross-file",
            risk="medium",
            confidence=0.6,
            recommended_mode="chat_planned",
        ),
    ),
    # "implement" matches L2 pattern → 1 match → confidence=0.6
    (
        "implement caching layer for fs_search",
        OperatingPoint(
            difficulty=2,
            scope="cross-file",
            risk="medium",
            confidence=0.6,
            recommended_mode="chat_planned",
        ),
    ),
    # ── L3 tasks (repo, complex) ────────────────────────────────────────
    # "refactor" matches L3 pattern → 1 match → confidence=0.6
    (
        "refactor workflow controller for parallel execution",
        OperatingPoint(
            difficulty=3,
            scope="repo",
            risk="high",
            confidence=0.6,
            recommended_mode="workflow_linear",
        ),
    ),
    # "redesign" + "architecture" → 2 L3 matches → confidence=0.8
    (
        "redesign the session management architecture",
        OperatingPoint(
            difficulty=3,
            scope="repo",
            risk="high",
            confidence=0.8,
            recommended_mode="workflow_linear",
        ),
    ),
    # "migrate" + "protocol" → 2 L3 matches → confidence=0.8
    (
        "migrate all tools from legacy API to new protocol",
        OperatingPoint(
            difficulty=3,
            scope="repo",
            risk="high",
            confidence=0.8,
            recommended_mode="workflow_linear",
        ),
    ),
    # "restructure" matches L3 pattern → 1 match → confidence=0.6
    (
        "restructure the provider chain for multi-tenant support",
        OperatingPoint(
            difficulty=3,
            scope="repo",
            risk="high",
            confidence=0.6,
            recommended_mode="workflow_linear",
        ),
    ),
    # "new subsystem" + "across codebase" → 2 L3 matches → confidence=0.8
    (
        "implement new subsystem for distributed task execution across codebase",
        OperatingPoint(
            difficulty=3,
            scope="repo",
            risk="high",
            confidence=0.8,
            recommended_mode="workflow_linear",
        ),
    ),
]


@pytest.mark.parametrize("task,expected", FIXTURES, ids=[t[0][:40] for t in FIXTURES])
def test_fixture(task: str, expected: OperatingPoint) -> None:
    """C0: fixture task returns exact OperatingPoint match."""
    result = estimate_scope(task)
    assert result == expected, f"Failed for task: {task!r}"


def test_boundary_empty_string() -> None:
    """C0p: empty string raises ValueError."""
    with pytest.raises(ValueError, match="task must be non-empty"):
        estimate_scope("")


def test_boundary_whitespace_only() -> None:
    """C0p: whitespace-only raises ValueError."""
    with pytest.raises(ValueError, match="task must be non-empty"):
        estimate_scope("   \n\t  ")


def test_boundary_very_long_task() -> None:
    """C0p: very long task (10,000 chars) does not crash."""
    long_task = "refactor " * (10_000 // 9)
    result = estimate_scope(long_task)
    # Should not crash; should return valid OperatingPoint
    assert result.difficulty in {1, 2, 3}
    assert result.scope in {"single-file", "cross-file", "repo"}
    assert result.risk in {"low", "medium", "high"}
    assert 0.0 <= result.confidence <= 1.0
    assert result.recommended_mode in {"chat_direct", "chat_planned", "workflow_linear"}


def test_boundary_non_english() -> None:
    """C0p: non-English text has no keyword matches, so optimistic default."""
    # Use a task WITHOUT file references to test the pure optimistic default
    result = estimate_scope("исправить опечатку в документации")
    # No keyword matches, no file references → optimistic default
    assert result.difficulty == 1
    assert result.scope == "single-file"
    assert result.risk == "low"
    assert result.confidence == 0.3
    assert result.recommended_mode == "chat_direct"


def test_security_boost_l1() -> None:
    """C0p: security boost adds +1 difficulty to L1 task.

    NOTE: Security boost changes difficulty and risk, NOT scope.
    The scope is determined by the winning level BEFORE security boost.
    Risk is only changed to "high" if difficulty becomes 3.
    """
    # "rename" is L1, "auth" is security → difficulty=2, risk stays "low"
    result = estimate_scope("rename auth token variable")
    assert result.difficulty == 2
    assert result.scope == "single-file"  # scope NOT boosted (only difficulty/risk)
    assert result.risk == "low"  # risk only changes to "high" if difficulty==3
    assert result.recommended_mode == "chat_direct"  # mode determined before boost


def test_security_boost_l2() -> None:
    """C0p: security boost adds +1 difficulty to L2 task (capped at 3)."""
    # "implement" is L2, "auth" is security → difficulty=3
    result = estimate_scope("implement new auth command")
    assert result.difficulty == 3
    assert result.scope == "cross-file"  # scope determined by L2 match
    assert result.risk == "high"  # boosted to high at difficulty=3


def test_security_boost_l3_no_change() -> None:
    """C0p: security boost does not exceed difficulty=3."""
    # "refactor" is L3, "auth" is security → difficulty stays 3
    result = estimate_scope("refactor auth system")
    assert result.difficulty == 3
    assert result.scope == "repo"
    assert result.risk == "high"


def test_confidence_single_match() -> None:
    """C0p: single match → confidence=0.6."""
    # "rename" is L1, only 1 match
    result = estimate_scope("rename this variable")
    assert result.confidence == 0.6


def test_confidence_multiple_matches() -> None:
    """C0p: multiple matches → confidence=0.8."""
    # "fix typo" is L1, "rename" is L1 → 2 matches
    result = estimate_scope("fix typo and rename variable")
    assert result.confidence == 0.8


def test_no_non_stdlib_imports() -> None:
    """C0p: verify no imports beyond stdlib.

    Allowed imports: re, dataclasses, typing, __future__ (all stdlib).
    """
    import ast
    from pathlib import Path

    source_path = Path(__file__).parent.parent / "src" / "fa" / "inner_loop" / "scope_estimator.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    # All imports must be stdlib
    stdlib_modules = {"re", "dataclasses", "typing", "__future__"}
    non_stdlib = [imp for imp in imports if imp not in stdlib_modules and not imp.startswith("typing")]
    assert non_stdlib == [], f"Non-stdlib imports found: {non_stdlib}"


# ── File reference counting tests (E3 paper §5 primary L1 signal) ────────


def test_file_reference_single_path() -> None:
    """C0p: single file reference → L1 with high confidence (E3 paper §5)."""
    result = estimate_scope("fix the bug in src/fa/cli.py")
    assert result.difficulty == 1
    assert result.scope == "single-file"
    assert result.confidence == 0.8  # High confidence from file reference
    assert result.recommended_mode == "chat_direct"


def test_file_reference_readme() -> None:
    """C0p: README.md reference → L1 with high confidence."""
    result = estimate_scope("update README.md with new instructions")
    assert result.difficulty == 1
    assert result.scope == "single-file"
    assert result.confidence == 0.8
    assert result.recommended_mode == "chat_direct"


def test_file_reference_multiple_paths() -> None:
    """C0p: multiple file references → optimistic default (ambiguous scope)."""
    result = estimate_scope("sync changes between src/fa/cli.py and tests/test_cli.py")
    assert result.difficulty == 1
    assert result.scope == "single-file"
    assert result.confidence == 0.3  # Multiple files = ambiguous
    assert result.recommended_mode == "chat_direct"


def test_file_reference_with_security() -> None:
    """C0p: file reference + security cues → security boost applies, scope stays single-file."""
    result = estimate_scope("fix auth bug in src/fa/auth.py")
    # file_refs=1 but security_count=1, so the file_refs branch is skipped
    # Falls through to optimistic default (L1), then security boost adds +1
    assert result.difficulty == 2  # L1 + security boost
    assert result.scope == "single-file"  # scope NOT boosted (only difficulty)
    assert result.risk == "low"  # risk only changes to "high" if difficulty==3
    assert result.recommended_mode == "chat_direct"


def test_file_reference_various_formats() -> None:
    """C0p: various file path formats are recognized."""
    test_cases = [
        "fix src/fa/cli.py",
        "update ./config.yaml",
        "modify README.md",
        "change utils.py",
    ]
    for task in test_cases:
        result = estimate_scope(task)
        assert result.difficulty == 1
        assert result.confidence == 0.8, f"Failed for task: {task}"


def test_file_reference_l3_overrides() -> None:
    """C0p: L3 keywords override file reference signal."""
    result = estimate_scope("refactor the entire auth system in src/fa/auth.py")
    assert result.difficulty == 3
    assert result.scope == "repo"
    assert result.confidence == 0.6
    assert result.recommended_mode == "workflow_linear"
