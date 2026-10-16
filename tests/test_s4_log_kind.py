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

import ast
import typing
from pathlib import Path

from fa.output import LogKind
from scripts.check_log_kind_contract import KNOWN_DORMANT_KINDS, _AppendKindVisitor, extract_log_append_kinds
from tests._capabilities import requires_posix_paths

# ── Constants ────────────────────────────────────────────────────────

SRC_FA = Path("src/fa")


# ── Kill-check 1: LogKind is defined and has members ─────────────────


def test_log_kind_defined_and_nonempty() -> None:
    """LogKind must be a Literal with at least 30 members."""
    args = typing.get_args(LogKind)
    assert len(args) >= 30, f"LogKind has only {len(args)} members, expected >= 30"


# ── Kill-check 2: Member count matches source kind= literals ────────


@requires_posix_paths
def test_log_kind_member_count_matches_source() -> None:
    """The number of LogKind members must match the number of unique kind=
    string literals found in src/fa/ (including dynamically constructed kinds)."""
    args = set(typing.get_args(LogKind))

    # One canonical producer scanner: admission/provider ``kind`` fields are
    # different namespaces. Unresolved actual log producers still fail closed.
    producers, unresolved = extract_log_append_kinds()
    assert not unresolved, f"Unresolved log producers: {unresolved}"
    found_kinds = set(producers)

    # Every source kind must be in LogKind
    missing_from_logkind = found_kinds - args
    assert not missing_from_logkind, f"Kinds found in source but missing from LogKind: {missing_from_logkind}"

    # Every LogKind member must have a producer in source — except members
    # explicitly declared dormant in output.py (e.g. scope_tripwire, retired by
    # S10 but kept as an alias because the S8 calibration projection keys on
    # the historical name). A member is dormant only when its LogKind
    # declaration line carries the word "dormant".
    output_py = SRC_FA / "output.py"
    dormant_kinds: set[str] = set()
    import re as _re

    for line in output_py.read_text().splitlines():
        m = _re.search(r'^\s*"(scope_[a-z_]+|[a-z_]+)",\s*#.*dormant', line)
        if m:
            dormant_kinds.add(m.group(1))

    dormant_kinds.update(KNOWN_DORMANT_KINDS)
    missing_from_source = args - found_kinds
    assert not (missing_from_source - dormant_kinds), (
        f"LogKind members with no producer in source: {missing_from_source - dormant_kinds}"
    )
    assert missing_from_source <= dormant_kinds, (
        f"unproduced member not declared dormant: {missing_from_source - dormant_kinds}"
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


def test_log_kind_scanner_separates_namespaces_and_preserves_dynamic_producers() -> None:
    source = """
_record_admission_attempt(kind="EXPLICIT_INPUT")
ProviderError(kind="provider-only")
log.append(kind="real-event")
kind = "first" if condition else "second"
log.append(kind=kind)
log.append(kind=unknown_value)
"""
    visitor = _AppendKindVisitor("probe.py")
    visitor.visit(ast.parse(source))
    assert set(visitor.found) == {"real-event", "first", "second"}
    assert len(visitor.unresolved) == 1 and "unknown_value" in visitor.unresolved[0]
