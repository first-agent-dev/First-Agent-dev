"""Kill-check tests for S4: Add LogKind = Literal[...] to output.py.

Verifies:
1. LogKind is defined and importable from fa.output
2. LogKind member count matches actual kind= string literals in src/fa/
3. Every LogKind member has at least one producer in the source
4. LogKind is exported in __all__
5. LogKind members are a superset of CONSOLE_MIRROR_KINDS (once S5 adds it)
6. Static: typo in kind= string would fail pyright (design intent, not runtime test)
"""

from __future__ import annotations

import subprocess
import typing
from pathlib import Path

from fa.output import LogKind

# ── Constants ────────────────────────────────────────────────────────

SRC_FA = Path("src/fa")


# ── Kill-check 1: LogKind is defined and has members ─────────────────


def test_log_kind_defined_and_nonempty() -> None:
    """LogKind must be a Literal with at least 30 members."""
    args = typing.get_args(LogKind)
    assert len(args) >= 30, f"LogKind has only {len(args)} members, expected >= 30"


# ── Kill-check 2: Member count matches source kind= literals ────────


def test_log_kind_member_count_matches_source() -> None:
    """The number of LogKind members must match the number of unique kind=
    string literals found in src/fa/ (including dynamically constructed kinds)."""
    args = set(typing.get_args(LogKind))

    # Grep for kind="..." in source
    result = subprocess.run(
        ["grep", "-rn", 'kind="', str(SRC_FA), "--include=*.py"],
        capture_output=True,
        text=True,
    )
    found_kinds: set[str] = set()
    for line in result.stdout.splitlines():
        import re
        m = re.search(r'kind="([^"]+)"', line)
        if m:
            found_kinds.add(m.group(1))

    # Add dynamically constructed kinds not caught by simple grep
    dyn_result = subprocess.run(
        ["grep", "-rn", "subagent_spawn_done", str(SRC_FA), "--include=*.py"],
        capture_output=True,
        text=True,
    )
    if "subagent_spawn_done" in dyn_result.stdout:
        found_kinds.add("subagent_spawn_done")

    # Every source kind must be in LogKind
    missing_from_logkind = found_kinds - args
    assert not missing_from_logkind, (
        f"Kinds found in source but missing from LogKind: {missing_from_logkind}"
    )

    # Every LogKind member must have a producer in source
    missing_from_source = args - found_kinds
    assert not missing_from_source, (
        f"LogKind members with no producer in source: {missing_from_source}"
    )


# ── Kill-check 3: All members are strings ───────────────────────────


def test_log_kind_all_members_are_strings() -> None:
    """Every LogKind member must be a string literal."""
    for member in typing.get_args(LogKind):
        assert isinstance(member, str), f"LogKind member {member!r} is not a string"


# ── Kill-check 4: No duplicate members ──────────────────────────────


def test_log_kind_no_duplicates() -> None:
    """LogKind must not have duplicate members."""
    args = typing.get_args(LogKind)
    assert len(args) == len(set(args)), "LogKind has duplicate members"


# ── Kill-check 5: LogKind is in __all__ ─────────────────────────────


def test_log_kind_in_all() -> None:
    """LogKind must be exported in fa.output.__all__."""
    from fa.output import __all__
    assert "LogKind" in __all__, "LogKind not found in fa.output.__all__"


# ── Kill-check 6: compaction_warning is present (was dead code before S6) ─


def test_compaction_warning_in_log_kind() -> None:
    """compaction_warning must be in LogKind — it's the single observation
    point for compaction-level pressure (added by S6 producer, but the
    type member must exist for the contract check to validate)."""
    args = set(typing.get_args(LogKind))
    assert "compaction_warning" in args, "compaction_warning missing from LogKind"


# ── Kill-check 7: Specific expected members present ─────────────────


def test_expected_members_present() -> None:
    """Spot-check that key safety-critical kinds are present."""
    args = set(typing.get_args(LogKind))
    expected = {
        "context_budget_warn",
        "context_budget_hard_stop",
        "compaction_circuit_breaker",
        "run_stopped",
        "subagent_spawn_done",
        "subagent_spawn_fail",
    }
    missing = expected - args
    assert not missing, f"Expected LogKind members missing: {missing}"
