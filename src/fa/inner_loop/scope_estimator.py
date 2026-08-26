"""Deterministic scope estimator for complexity-aware execution.

Implements the E3 "Estimate → Execute → Expand" pattern (arxiv 2607.13034):
a cheap, deterministic pre-dispatch function that classifies task complexity
before committing LLM budget. The estimator is deliberately optimistic —
bias toward under-estimating complexity, because over-estimating wastes
tokens on simple tasks, and under-estimating is recovered by workflow
escalation (the safety net).

Architecture:
- Pure Python function, no LLM calls, no I/O, no imports beyond stdlib
- Keyword-based classification (regex patterns per difficulty level)
- Confidence derived from match count (0.8 if ≥2, 0.6 if 1, 0.3 if 0)
- Security signals boost difficulty by +1 (capped at 3)

Compliance-by-construction (§1.2.5): routing is deterministic, testable,
auditable. The estimator is not LLM judgment — it's a pure function.

References:
- E3: "Do AI Agents Know When a Task Is Simple?" (arxiv 2607.13034, §4.2)
- ADR-16: Complexity-Aware Execution (knowledge/adr/ADR-16-*.md)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

__all__ = ["OperatingPoint", "estimate_scope"]


@dataclass(frozen=True)
class OperatingPoint:
    """Scope estimate for a task.

    Attributes:
        difficulty: Task complexity level (1=simple, 2=medium, 3=complex).
        scope: Spatial scope of the task.
        risk: Risk level for the task.
        confidence: Confidence in the estimate (0.0 to 1.0).
        recommended_mode: Recommended execution mode.

    Invariants:
        - difficulty ∈ {1, 2, 3}
        - scope ∈ {"single-file", "cross-file", "repo"}
        - risk ∈ {"low", "medium", "high"}
        - recommended_mode ∈ {"chat_direct", "chat_planned", "workflow_linear"}
        - confidence ∈ [0.0, 1.0]
    """

    difficulty: Literal[1, 2, 3]
    scope: Literal["single-file", "cross-file", "repo"]
    risk: Literal["low", "medium", "high"]
    confidence: float
    recommended_mode: Literal["chat_direct", "chat_planned", "workflow_linear"]


# Keyword patterns for difficulty classification.
# Each pattern is a compiled regex with word boundaries to avoid false positives.
# Patterns are case-insensitive (re.IGNORECASE applied at match time).
_KEYWORD_PATTERNS: dict[str, frozenset[re.Pattern[str]]] = {
    "L3": frozenset(
        [
            re.compile(r"\brefactor\b", re.IGNORECASE),
            re.compile(r"\bredesign\b", re.IGNORECASE),
            re.compile(r"\bmigrate\b", re.IGNORECASE),
            re.compile(r"\brestructure\b", re.IGNORECASE),
            re.compile(r"\bnew subsystem\b", re.IGNORECASE),
            re.compile(r"\bprotocol\b", re.IGNORECASE),
            re.compile(r"\barchitecture\b", re.IGNORECASE),
            re.compile(r"\bacross.*codebase\b", re.IGNORECASE),
            re.compile(r"\bevery.*call.?site\b", re.IGNORECASE),
        ]
    ),
    "L2": frozenset(
        [
            re.compile(r"\badd.*function\b", re.IGNORECASE),
            re.compile(r"\bimplement\b", re.IGNORECASE),
            re.compile(r"\bnew.*command\b", re.IGNORECASE),
            re.compile(r"\bcross-file\b", re.IGNORECASE),
            re.compile(r"\b2.*files\b", re.IGNORECASE),
            re.compile(r"\b3.*files\b", re.IGNORECASE),
        ]
    ),
    "L1": frozenset(
        [
            re.compile(r"\bfix typo\b", re.IGNORECASE),
            re.compile(r"\brename\b", re.IGNORECASE),
            re.compile(r"\bupdate.*docstring\b", re.IGNORECASE),
            re.compile(r"\bsingle.*file\b", re.IGNORECASE),
            re.compile(r"\bone.*line\b", re.IGNORECASE),
        ]
    ),
    "security": frozenset(
        [
            re.compile(r"\bauth\b", re.IGNORECASE),
            re.compile(r"\bpermission\b", re.IGNORECASE),
            re.compile(r"\bsecret\b", re.IGNORECASE),
            re.compile(r"\bsandbox\b", re.IGNORECASE),
            re.compile(r"\bsecurity\b", re.IGNORECASE),
        ]
    ),
}

# File reference pattern: matches common file path formats.
# Examples: "src/fa/cli.py", "README.md", "/path/to/file.js", "./config.yaml"
_FILE_REF_PATTERN = re.compile(
    r"(?:"
    r"(?:\.{0,2}/)?(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_-]+\.[a-zA-Z0-9]+"  # relative/absolute paths
    r"|"
    r"[a-zA-Z0-9_-]+\.(?:py|js|ts|md|yaml|yml|json|toml|txt|sh)"  # common extensions
    r")",
    re.IGNORECASE,
)


def _count_file_references(task: str) -> int:
    """Count explicit file references in task text.

    Matches common file path formats:
    - "src/fa/cli.py"
    - "README.md"
    - "/path/to/file.js"
    - "./config.yaml"

    Returns the count of distinct file references found.
    """
    matches = _FILE_REF_PATTERN.findall(task)
    return len(set(matches))  # deduplicate


def estimate_scope(task: str) -> OperatingPoint:
    """Estimate task scope and difficulty from task text.

    Pure function that classifies task text into L1/L2/L3 based on keyword
    patterns. No LLM calls, no I/O, no imports beyond stdlib.

    Algorithm:
        1. Reject empty/whitespace-only tasks with ValueError.
        2. Count keyword matches per level (L3, L2, L1, security).
        3. Determine difficulty (priority: L3 > L2 > L1):
           - l3_count > 0 → difficulty=3, scope="repo", risk="high", mode="workflow_linear"
           - l2_count > 0 → difficulty=2, scope="cross-file", risk="medium", mode="chat_planned"
           - l1_count > 0 → difficulty=1, scope="single-file", risk="low", mode="chat_direct"
           - else         → difficulty=1, scope="single-file", risk="low", mode="chat_direct"
        4. Confidence: 0.8 if winning level has ≥2 matches, 0.6 if 1 match,
           0.3 if 0 matches (optimistic default per E3 principle).
        5. Security boost: if security_count > 0 and difficulty < 3, difficulty += 1.

    Args:
        task: Task description text.

    Returns:
        OperatingPoint with difficulty, scope, risk, confidence, recommended_mode.

    Raises:
        ValueError: If task is empty or whitespace-only.

    Examples:
        >>> estimate_scope("fix typo in README.md")
        OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.8, recommended_mode="chat_direct")

        >>> estimate_scope("add fs_chunk tool")
        OperatingPoint(difficulty=2, scope="cross-file", risk="medium", confidence=0.8, recommended_mode="chat_planned")

        >>> estimate_scope("refactor workflow controller for parallel execution")
        OperatingPoint(difficulty=3, scope="repo", risk="high", confidence=0.8, recommended_mode="workflow_linear")
    """
    if not task or not task.strip():
        raise ValueError("task must be non-empty")

    # Count keyword matches per level
    l3_count = sum(1 for pat in _KEYWORD_PATTERNS["L3"] if pat.search(task))
    l2_count = sum(1 for pat in _KEYWORD_PATTERNS["L2"] if pat.search(task))
    l1_count = sum(1 for pat in _KEYWORD_PATTERNS["L1"] if pat.search(task))
    security_count = sum(1 for pat in _KEYWORD_PATTERNS["security"] if pat.search(task))

    # Count explicit file references (E3 paper's primary L1 signal)
    file_refs = _count_file_references(task)

    # Determine difficulty (priority: L3 > L2 > L1 > file_refs > optimistic default)
    if l3_count > 0:
        difficulty: Literal[1, 2, 3] = 3
        scope: Literal["single-file", "cross-file", "repo"] = "repo"
        risk: Literal["low", "medium", "high"] = "high"
        confidence = 0.8 if l3_count >= 2 else 0.6
        recommended_mode: Literal["chat_direct", "chat_planned", "workflow_linear"] = "workflow_linear"
    elif l2_count > 0:
        difficulty = 2
        scope = "cross-file"
        risk = "medium"
        confidence = 0.8 if l2_count >= 2 else 0.6
        recommended_mode = "chat_planned"
    elif l1_count > 0:
        difficulty = 1
        scope = "single-file"
        risk = "low"
        confidence = 0.8 if l1_count >= 2 else 0.6
        recommended_mode = "chat_direct"
    elif file_refs == 1 and security_count == 0:
        # E3 paper: explicit file reference with no security cues → L1 with high confidence
        difficulty = 1
        scope = "single-file"
        risk = "low"
        confidence = 0.8
        recommended_mode = "chat_direct"
    else:
        # No signals: optimistic default (E3 principle)
        difficulty = 1
        scope = "single-file"
        risk = "low"
        confidence = 0.3
        recommended_mode = "chat_direct"

    # Security boost: +1 difficulty (capped at 3)
    if security_count > 0 and difficulty < 3:
        # Type narrowing: min() returns int, but we know the result is in {1,2,3}
        new_difficulty = min(difficulty + 1, 3)
        if new_difficulty == 3:
            difficulty = 3
            risk = "high"
        elif new_difficulty == 2:
            difficulty = 2
        # new_difficulty cannot be 1 here (difficulty >= 1 and we add 1)

    return OperatingPoint(
        difficulty=difficulty,
        scope=scope,
        risk=risk,
        confidence=confidence,
        recommended_mode=recommended_mode,
    )
