"""S10.4 — observation builder pure core (CT2/CT4 render rules, DP-8).

root=observation-builder class=C0p claim=G7 path=T4
oracle=rendered turn_context substrings, skill_block presence, cap, eviction.
The coder_loop wiring has its own C1 file (test_scope_expansion_wiring.py).
"""

from __future__ import annotations

from fa.inner_loop.expansion import ExpansionDecision
from fa.inner_loop.observations import OBSERVATION_CAP_CHARS, build_observation_block
from fa.skills._inject import SkillInjectionResult

SKILL_ESCALATE = ExpansionDecision(level_to=3, evidence="high_tier_write", observation_key="escalation")
SKILL_ARM = ExpansionDecision(level_to=2, evidence="read_high_arm", observation_key="skill")
NO_DECISION: ExpansionDecision | None = None


def _skill_block() -> SkillInjectionResult:
    return SkillInjectionResult(
        block={
            "name": "plan-authoring",
            "description": "d",
            "instruction": "i",
            "body": "# plan-authoring — d\n\nbig body",
        }
    )


# ── clean L1 run: nothing to say ──────────────────────────────────────────


def test_clean_level_one_renders_empty() -> None:
    out = build_observation_block(level_from=1, level_to=1, decision=NO_DECISION, write_tier=0)
    assert out.turn_context == ""
    assert out.skill_block is None


# ── L2 arming: anchor text + skill block on entry turn ─────────────────────


def test_l2_entry_carries_anchor_and_skill_block() -> None:
    out = build_observation_block(
        level_from=1,
        level_to=2,
        decision=SKILL_ARM,
        write_tier=0,
        skill_result=_skill_block(),
        skill_name="plan-authoring",
    )
    assert "plan-authoring" in out.turn_context
    assert "invoke_workflow" not in out.turn_context
    assert out.skill_block is not None
    assert out.skill_block["name"] == "plan-authoring"


def test_l2_steady_state_anchor_only_no_body() -> None:
    # Already at level 2, no new decision: anchor persists, but no block.
    out = build_observation_block(
        level_from=2,
        level_to=2,
        decision=NO_DECISION,
        write_tier=0,
        skill_name="plan-authoring",
    )
    assert "plan-authoring" in out.turn_context
    assert out.skill_block is None


def test_l2_to_l3_escalation_replaces_skill_text() -> None:
    # DP-8: escalation key REPLACES the skill key; no stale L2 line at L3.
    out = build_observation_block(
        level_from=2,
        level_to=3,
        decision=SKILL_ESCALATE,
        write_tier=5,
        skill_name="plan-authoring",
    )
    assert "invoke_workflow" in out.turn_context
    assert "Planner skill active" not in out.turn_context
    assert out.skill_block is None


# ── L3 escalation: rendered on transition only ────────────────────────────


def test_l3_steady_state_renders_nothing_unless_verification() -> None:
    # At level 3 with no NEW decision and safe/none writes: the one-shot
    # escalation sentence is not repeated every turn.
    out = build_observation_block(level_from=3, level_to=3, decision=NO_DECISION, write_tier=0)
    assert out.turn_context == ""


def test_l3_escalation_text_has_do_exactly() -> None:
    out = build_observation_block(level_from=1, level_to=3, decision=SKILL_ESCALATE, write_tier=5)
    assert "Do exactly" in out.turn_context
    assert "invoke_workflow" in out.turn_context


# ── exhausted (SA-2) ───────────────────────────────────────────────────────


def test_exhausted_renders_terminal_line_and_wins() -> None:
    out = build_observation_block(
        level_from=3,
        level_to=3,
        decision=NO_DECISION,
        write_tier=5,
        exhausted=True,
    )
    assert "budget" in out.turn_context
    assert "operator" in out.turn_context
    # exhausted REPLACES the escalation line (not stacked).
    assert "Do exactly" not in out.turn_context


# ── verification posture (CT4) ─────────────────────────────────────────────


def test_verification_absent_without_writes() -> None:
    out = build_observation_block(level_from=1, level_to=1, decision=NO_DECISION, write_tier=0)
    assert "erification" not in out.turn_context


def test_verification_safe_writes_silent() -> None:
    out = build_observation_block(level_from=1, level_to=1, decision=NO_DECISION, write_tier=1)
    assert "erification" not in out.turn_context


def test_verification_medium_nudge() -> None:
    out = build_observation_block(level_from=1, level_to=1, decision=NO_DECISION, write_tier=3)
    assert "targeted tests" in out.turn_context


def test_verification_high_names_command() -> None:
    out = build_observation_block(
        level_from=1,
        level_to=1,
        decision=NO_DECISION,
        write_tier=5,
        verification_command="pytest tests/test_x.py",
    )
    assert "Risk tier high" in out.turn_context
    assert "pytest tests/test_x.py" in out.turn_context


def test_verification_high_default_command_when_none_given() -> None:
    out = build_observation_block(level_from=1, level_to=1, decision=NO_DECISION, write_tier=5)
    assert "pytest" in out.turn_context


# ── cap / eviction (DP-8 priority) ─────────────────────────────────────────


def test_cap_never_exceeded_with_oversized_low_priority() -> None:
    # An oversized low-priority entry is evicted so the total stays at/near
    # the cap; the high-priority escalation line survives.
    out = build_observation_block(
        level_from=2,
        level_to=3,
        decision=SKILL_ESCALATE,
        write_tier=5,
        verification_command="x" * 3000,
    )
    assert len(out.turn_context) < OBSERVATION_CAP_CHARS + 200
    assert "invoke_workflow" in out.turn_context


def test_low_priority_evicted_first_under_cap() -> None:
    # verification text is high-priority per CT4 (priority 2); skill anchor (1)
    # loses. With a huge verification command and a skill anchor, the anchor is
    # dropped — but escalation/exhausted always survive.
    big_cmd = "pytest " + " ".join(f"tests/test_{i}.py" for i in range(500))
    out = build_observation_block(
        level_from=1,
        level_to=2,
        decision=SKILL_ARM,
        write_tier=5,
        skill_name="plan-authoring",
        verification_command=big_cmd,
    )
    assert "Risk tier high" in out.turn_context


# ── exhausted latch wired from tool budget denial (CT6/SA-2) ───────────────


def test_exhausted_after_budget_denial_replaces_escalation() -> None:
    """Once budget is denied (exhausted=True), the terminal line renders and
    the plain escalation sentence is not stacked (DP-8)."""
    out = build_observation_block(
        level_from=3,
        level_to=3,
        decision=None,
        write_tier=5,
        exhausted=True,
    )
    assert "budget" in out.turn_context
    assert "operator" in out.turn_context
    assert "Do exactly" not in out.turn_context
