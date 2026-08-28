"""S10.1 — expansion pure core (CT1).

root=expansion-policy class=C0/C0p claim=G1/G11 path=P1-P9
oracle=decision fields (level_to/evidence/observation_key), exact, deterministic.
Producer kill-checks live in this module (it IS the producer for later slices).
"""

from __future__ import annotations

import pytest

from fa.inner_loop.expansion import (
    CHANGE_LIMIT,
    LEVEL_CEILING,
    READ_LIMIT,
    ExpansionDecision,
    ExpansionState,
    difficulty_to_level,
    next_level,
    select_l2_skill,
)
from tests.test_r1_heldout_wording import LevelEvidence


def state(level: int = 1) -> ExpansionState:
    return ExpansionState(level=level)


# ── difficulty_to_level (G11) ──────────────────────────────────────────────


def test_difficulty_to_level_maps_every_mode() -> None:
    assert difficulty_to_level("chat_direct") == 1
    assert difficulty_to_level("chat_planned") == 2
    assert difficulty_to_level("workflow_linear") == 3


def test_difficulty_to_level_is_total_on_known_union_only() -> None:
    with pytest.raises(ValueError):
        difficulty_to_level("not_a_mode")


# ── select_l2_skill (DP-7) ─────────────────────────────────────────────────


def test_select_l2_skill_warm_and_cold() -> None:
    assert select_l2_skill(plan_artifact=True) == "feature-planning"
    assert select_l2_skill(plan_artifact=False) == "plan-authoring"


# ── trigger policy (P1/P2/P5/P6/P7/P8) ─────────────────────────────────────


def test_high_tier_write_escalates_to_three() -> None:
    d = next_level(
        state(1),
        files_read=1,
        files_changed=1,
        write_tier=5,
        read_tier_high=False,
        verify_failed=False,
        assumed_linear=False,
    )
    assert d == ExpansionDecision(level_to=3, evidence="high_tier_write", observation_key="escalation")


def test_high_tier_read_without_write_arms_level_two() -> None:
    d = next_level(
        state(1),
        files_read=1,
        files_changed=0,
        write_tier=0,
        read_tier_high=True,
        verify_failed=False,
        assumed_linear=False,
    )
    assert d == ExpansionDecision(level_to=2, evidence="read_high_arm", observation_key="skill")


def test_verify_failed_escalates() -> None:
    d = next_level(
        state(2),
        files_read=2,
        files_changed=1,
        write_tier=3,
        read_tier_high=False,
        verify_failed=True,
        assumed_linear=False,
    )
    assert d is not None and d.level_to == 3 and d.evidence == "verify_failed"


def test_archive_bulk_safe_tier_stays_silent() -> None:
    # 15 files read, many changed — but safe tier and no high read: no signal.
    d = next_level(
        state(1),
        files_read=15,
        files_changed=15,
        write_tier=1,
        read_tier_high=False,
        verify_failed=False,
        assumed_linear=False,
    )
    assert d is None


def test_medium_tier_writes_do_not_change_level() -> None:
    # tests/** edit = medium: verification posture only, never a level change.
    d = next_level(
        state(1),
        files_read=4,
        files_changed=2,
        write_tier=3,
        read_tier_high=False,
        verify_failed=False,
        assumed_linear=False,
    )
    assert d is None


def test_assumed_linear_is_always_silent() -> None:
    d = next_level(
        state(1),
        files_read=50,
        files_changed=50,
        write_tier=5,
        read_tier_high=True,
        verify_failed=True,
        assumed_linear=True,  # RK-I: seeded workflow_linear never re-fires
    )
    assert d is None


def test_clean_run_no_evidence_returns_none() -> None:
    d = next_level(
        state(1),
        files_read=2,
        files_changed=1,
        write_tier=1,
        read_tier_high=False,
        verify_failed=False,
        assumed_linear=False,
    )
    assert d is None


# ── monotonicity / ceiling (I1, I2) ────────────────────────────────────────


def test_never_escalates_above_ceiling() -> None:
    kwargs_cases: tuple[LevelEvidence, ...] = (
        {
            "files_read": 99,
            "files_changed": 99,
            "write_tier": 5,
            "read_tier_high": True,
            "verify_failed": True,
            "assumed_linear": False,
        },
        {
            "files_read": 0,
            "files_changed": 0,
            "write_tier": 0,
            "read_tier_high": True,
            "verify_failed": False,
            "assumed_linear": False,
        },
    )
    for kwargs in kwargs_cases:
        assert next_level(ExpansionState(level=LEVEL_CEILING), **kwargs) is None


def test_monotone_across_sequence() -> None:
    """Property: every returned decision moves strictly up; repeated
    evaluation with the same evidence is idempotent (I3)."""
    s = state(1)
    # arm to 2 on high read
    d1 = next_level(
        s, files_read=1, files_changed=0, write_tier=0, read_tier_high=True, verify_failed=False, assumed_linear=False
    )
    assert d1 is not None and d1.level_to == 2
    # idempotent: same state+evidence again -> same answer
    d1b = next_level(
        s, files_read=1, files_changed=0, write_tier=0, read_tier_high=True, verify_failed=False, assumed_linear=False
    )
    assert d1b == d1
    s2 = ExpansionState(level=2)
    # read-high at level 2 does NOT re-arm and does not escalate
    assert (
        next_level(
            s2,
            files_read=1,
            files_changed=0,
            write_tier=0,
            read_tier_high=True,
            verify_failed=False,
            assumed_linear=False,
        )
        is None
    )
    # escalate to 3 on high write
    d3 = next_level(
        s2, files_read=3, files_changed=1, write_tier=5, read_tier_high=True, verify_failed=False, assumed_linear=False
    )
    assert d3 is not None and d3.level_to == 3
    assert d3.level_to > s2.level > s.level


# ── validation (errors are programmer errors only) ─────────────────────────


def test_state_rejects_bad_level() -> None:
    with pytest.raises(ValueError):
        ExpansionState(level=0)
    with pytest.raises(ValueError):
        ExpansionState(level=4)


def test_negative_counters_rejected() -> None:
    with pytest.raises(ValueError):
        next_level(
            state(1),
            files_read=-1,
            files_changed=0,
            write_tier=0,
            read_tier_high=False,
            verify_failed=False,
            assumed_linear=False,
        )


def test_bad_write_tier_rejected() -> None:
    with pytest.raises(ValueError):
        next_level(
            state(1),
            files_read=0,
            files_changed=0,
            write_tier=2,
            read_tier_high=False,
            verify_failed=False,
            assumed_linear=False,
        )


def test_threshold_constants_match_s7_tripwire() -> None:
    # Replacement is behaviour-compatible with routing.py tripwire thresholds.
    assert READ_LIMIT == 10
    assert CHANGE_LIMIT == 3
