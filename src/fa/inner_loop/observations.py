"""Per-turn scope observation builder — pure core (S10.4 / CT2).

Every turn boundary the loop asks: *given the current expansion posture and
this turn's evidence, what advisory text should the next request carry?*
This module renders that text deterministically. It owns the DP-8 render
rules:

  * observations are REBUILT each turn (assignment, never appended) — a
    stale L2 line must never survive an L3 escalation;
  * keyed dict ``{skill, escalation, verification, exhausted}`` with a fixed
    eviction order under the token cap;
  * the L3 escalation key REPLACES the L2 skill key (posture, not stack);
  * the full skill body never enters this string — it travels via
    ``skills_conditional``; here the skill entry is at most a short anchor;
  * ``exhausted`` is the terminal SA-2 line and always wins space.

Pure + stdlib only. The caller (coder_loop) supplies the decision from
``expansion.next_level`` and the tiers from ``path_risk``; this module
turns them into ``(turn_context, skill_block)``.
"""

from __future__ import annotations

from dataclasses import dataclass

from fa.inner_loop.expansion import LEVEL_CEILING, ExpansionDecision
from fa.skills._inject import SkillInjectionResult, build_skill_anchor

__all__ = [
    "OBSERVATION_CAP_CHARS",
    "ObservationRender",
    "build_observation_block",
]

#: Soft cap on the rendered turn_context observation string. 500 tokens is
#: ~2000 chars; we cap characters at a deliberately conservative value so
#: the advisory never competes with real context.
OBSERVATION_CAP_CHARS = 1800

#: Eviction order under the cap (highest survives): exhausted/escalation
#: beat verification, which beats the skill anchor.
_KEY_PRIORITY: dict[str, int] = {"exhausted": 4, "escalation": 3, "verification": 2, "skill": 1}


@dataclass(frozen=True)
class ObservationRender:
    """The builder's per-turn output.

    Attributes:
        turn_context: the full advisory string (possibly "") for the
            composer's non-cacheable ``turn_context`` channel.
        skill_block: dict for ``skills_conditional`` on the L2 entry turn,
            else None.
    """

    turn_context: str
    skill_block: dict[str, str] | None


def _escalation_text() -> str:
    return (
        "Scope escalation: the evidence now warrants the invoke_workflow tool, which runs a "
        "planner/coder/eval loop built for work at this size.\n"
        "Do exactly:\n"
        "1) Call invoke_workflow with the current goal.\n"
        '2) The harness attaches a file map and handoff; start from its "Start here" list.\n'
        "3) Continue the chat task only if you finish without it."
    )


def _exhausted_text() -> str:
    return (
        "Escalation budget used: invoke_workflow cannot be called again this session. "
        "Finish the current task with the tools you have and report the state to the operator."
    )


def _skill_anchor_text(skill_name: str) -> str:
    anchor = build_skill_anchor(skill_name, f"knowledge/skills/{skill_name}/SKILL.md")
    return f"Planner skill active: {anchor}"


def _verification_text(write_tier: int, *, verification_command: str | None) -> str | None:
    """CT4 verification posture — advisory only; never changes level.

    low/no writes -> absent; medium -> targeted-test nudge; high -> a
    fact-grounded command for this repo when the caller knows one.
    """
    from fa.inner_loop.expansion import TIER_HIGH, TIER_MEDIUM

    if write_tier <= 0:
        return None
    if write_tier >= TIER_HIGH:
        command = verification_command or "the repo's test suite (pytest) plus ruff and mypy"
        return (
            f"Risk tier high for the modified paths. Verification: run {command} and confirm "
            "green before reporting done."
        )
    if write_tier >= TIER_MEDIUM:
        return "Changed files include test/knowledge/script paths; consider targeted tests for what you edited."
    # safe tier writes (docs/worklogs): no verification posture.
    return None


def build_observation_block(
    *,
    level_from: int,
    level_to: int,
    decision: ExpansionDecision | None,
    write_tier: int,
    skill_result: SkillInjectionResult | None = None,
    exhausted: bool = False,
    skill_name: str = "",
    verification_command: str | None = None,
) -> ObservationRender:
    """Render this turn's advisory block.

    Args:
        level_from: posture at the start of this boundary evaluation.
        level_to: posture after applying *decision* (equals level_from on a
            no-op turn).
        decision: the :class:`ExpansionDecision` produced this boundary, or
            None when no trigger fired.
        write_tier: max tier of paths written this run (0 = none).
        skill_result: the L2 skill read result when on the L2 ENTRY turn
            (its ``.block`` travels via skills_conditional); None on all
            other turns.
        exhausted: True when the workflow tool denied a call for budget
            (CT6 SA-2) — renders the terminal line.
        skill_name: the active L2 skill name for the anchor line.
        verification_command: optional repo-specific verification command
            for the high-tier posture line.

    Returns:
        :class:`ObservationRender`. The turn_context is "" when there is
        nothing to say (clean level-1 run), so callers can assign it
        unconditionally.

    Render policy (DP-8): the escalation/exhausted line renders on the
    transition turn (level_from < level_to / newly exhausted), not on every
    subsequent L3 turn — a repeated sentence is context the model skips.
    The L2 anchor persists while level == 2.
    """
    entries: dict[str, str] = {}

    just_escalated = decision is not None and level_to >= LEVEL_CEILING and level_from < LEVEL_CEILING

    if exhausted:
        entries["exhausted"] = _exhausted_text()
    elif just_escalated:
        entries["escalation"] = _escalation_text()
    elif level_to == 2:
        if decision is not None and decision.observation_key == "skill":
            # L2 entry turn: the full body rides skills_conditional; the
            # text carries only a short pointer.
            entries["skill"] = _skill_anchor_text(skill_name or "plan-authoring")
        elif skill_name:
            # Already at L2: keep the cheap anchor, never the body.
            entries["skill"] = _skill_anchor_text(skill_name)

    verification = _verification_text(write_tier, verification_command=verification_command)
    if verification is not None:
        entries["verification"] = verification

    skill_block = skill_result.block if skill_result is not None else None

    turn_context = _render_with_cap(entries)
    return ObservationRender(turn_context=turn_context, skill_block=skill_block)


def _render_with_cap(entries: dict[str, str]) -> str:
    """Join entries in priority order, evicting lowest-priority keys until
    the rendered string fits the cap (DP-8 priority)."""
    ordered = sorted(entries.items(), key=lambda kv: -_KEY_PRIORITY.get(kv[0], 0))
    chosen: list[str] = []
    total = 0
    for _key, text in ordered:
        if total + len(text) > OBSERVATION_CAP_CHARS and chosen:
            continue
        chosen.append(text)
        total += len(text)
    return "\n\n".join(chosen)
