"""Kill-check tests for S5: Add CONSOLE_MIRROR_KINDS to output.py.

Verifies:
1. CONSOLE_MIRROR_KINDS has exactly 17 members (15 at S5, +2 in S10.9)
2. Every CONSOLE_MIRROR_KINDS member is also in LogKind
3. CONSOLE_MIRROR_KINDS is exported in __all__
4. Key safety-critical kinds are present
"""

from __future__ import annotations

import typing

from fa.output import CONSOLE_MIRROR_KINDS, LogKind

# ── Kill-check 1: CONSOLE_MIRROR_KINDS has exactly 17 members ──────


def test_console_mirror_kinds_count() -> None:
    """CONSOLE_MIRROR_KINDS must have exactly 17 members.

    S10.9 / CT-H4 added ``scope_expansion`` and ``expansion_exhausted``
    (operator-critical posture changes); ``expansion_observed`` is
    deliberately NOT mirrored (JSONL-only telemetry, noise policy).
    """
    assert len(CONSOLE_MIRROR_KINDS) == 17, (
        f"Expected 15 members, got {len(CONSOLE_MIRROR_KINDS)}: {sorted(CONSOLE_MIRROR_KINDS)}"
    )


# ── Kill-check 2: All members are in LogKind ────────────────────────


def test_console_mirror_kinds_subset_of_log_kind() -> None:
    """Every CONSOLE_MIRROR_KINDS member must also be a valid LogKind."""
    log_kinds = set(typing.get_args(LogKind))
    not_in_logkind = CONSOLE_MIRROR_KINDS - log_kinds
    assert not not_in_logkind, f"CONSOLE_MIRROR_KINDS members not in LogKind: {not_in_logkind}"


# ── Kill-check 3: CONSOLE_MIRROR_KINDS is in __all__ ───────────────


def test_console_mirror_kinds_in_all() -> None:
    """CONSOLE_MIRROR_KINDS must be exported in fa.output.__all__."""
    from fa.output import __all__

    assert "CONSOLE_MIRROR_KINDS" in __all__


# ── Kill-check 4: Safety-critical kinds are present ─────────────────


def test_safety_critical_kinds_present() -> None:
    """Key safety-critical kinds must be in CONSOLE_MIRROR_KINDS for
    dual-write enforcement (log.append + output.emit on same path)."""
    required = {
        "context_budget_warn",
        "context_budget_hard_stop",
        "compaction_circuit_breaker",
        "run_stopped",
        "tool_call",
    }
    missing = required - CONSOLE_MIRROR_KINDS
    assert not missing, f"Required safety-critical kinds missing from CONSOLE_MIRROR_KINDS: {missing}"


# ── Kill-check 5: Compaction stages are all present ─────────────────


def test_compaction_stages_all_present() -> None:
    """All compaction stage kinds must be in CONSOLE_MIRROR_KINDS
    for complete console visibility during compaction."""
    compaction_kinds = {
        "compaction_stage2_start",
        "compaction_stage2_done",
        "compaction_stage2_error",
        "compaction_stage3_start",
        "compaction_stage3_done",
        "compaction_stage3_error",
    }
    missing = compaction_kinds - CONSOLE_MIRROR_KINDS
    assert not missing, f"Compaction stage kinds missing from CONSOLE_MIRROR_KINDS: {missing}"
