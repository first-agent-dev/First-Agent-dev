"""Runtime scope expansion — pure policy core (S10.1).

Implements the deterministic decision function behind the E3
"Estimate → Execute → Expand" pattern (arxiv 2607.13034): at every turn
boundary the loop asks *whether the observed evidence warrants a broader
scope*. This module owns that question and nothing else — no I/O, no session
state, no tool knowledge, stdlib only (Principle 1: routing is deterministic,
testable, auditable).

FA adaptation (SSOT decisions, 2026-08-28):
  * Levels are **postures**, not tool sets. ``chat_direct`` (level 1) works the
    task directly; ``chat_planned`` (level 2) gets the planner-skill injection;
    ``workflow`` (level 3) is the ``invoke_workflow`` recommendation.
  * There is no per-level expansion counter here: the escalation budget K
    (max workflow invocations per chat session) is enforced structurally in
    the ``invoke_workflow`` tool (CT6), because level 3 *is* that tool call.
    This module only knows the level ceiling.
  * Trigger policy (positional risk model, Q26 / DP-1) — tier/verify evidence
    only; the S7 bulk counters play NO policy role (S10.9 / GAP-H4):
      - a failed verification command        -> level 3
      - a write into a high-tier path        -> level 3
      - read of a high-tier path (no write)  -> arms level 2
      - a run seeded as ``workflow_linear`` is never re-escalated (RK-I)
    The counters still matter for *telemetry*: :func:`near_miss_evidence`
    uses them to decide when a policy-relevant-but-silent boundary is worth
    a durable ``expansion_observed`` event (S10.9 / CT-H2, feeding S11
    constant tuning). Escalation itself never reads them.

The module never mutates state and never directs re-reading observed paths;
the caller threads ``ExpansionState`` (carrying the observed path sets)
across turns, which is what makes expansion progressive rather than a
re-search (E3 §1.9a H-reuse invariant).
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "CHANGE_LIMIT",
    "LEVEL_CEILING",
    "READ_LIMIT",
    "TIER_HIGH",
    "TIER_MEDIUM",
    "TIER_SAFE",
    "ExpansionDecision",
    "ExpansionState",
    "difficulty_to_level",
    "near_miss_evidence",
    "next_level",
    "select_l2_skill",
]

#: Highest posture. At level 3 the escalator has nothing left to advise.
LEVEL_CEILING: int = 3

#: Risk tiers (path_risk.py supplies the mapping; constants mirrored here so
#: the pure decision needs no import of the config-loading module).
TIER_SAFE: int = 1
TIER_MEDIUM: int = 3
TIER_HIGH: int = 5

#: Bulk counters, inherited verbatim from the S7 tripwire (routing.py) so the
#: replacement is behaviour-compatible before tier-gating is applied.
READ_LIMIT: int = 10
CHANGE_LIMIT: int = 3

#: recommended_mode (OperatingPoint) -> posture level.
_MODE_TO_LEVEL: dict[str, int] = {
    "chat_direct": 1,
    "chat_planned": 2,
    "workflow_linear": 3,
}


@dataclass(frozen=True)
class ExpansionState:
    """Current scope posture of one run.

    Frozen and rebuilt by the caller each turn. The path sets are carried
    forward untouched (H-reuse); this module only reads them.
    """

    level: int = 1
    observed_read_paths: frozenset[str] = frozenset()
    observed_write_paths: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.level not in (1, 2, LEVEL_CEILING):
            raise ValueError(f"level must be in 1..{LEVEL_CEILING}, got {self.level!r}")


@dataclass(frozen=True)
class ExpansionDecision:
    """The result of one turn-boundary evaluation.

    Attributes:
        level_to: the strictly higher posture the evidence warrants.
        evidence: stable machine-readable trigger name (auditable).
        observation_key: which observation block the builder renders
            ("escalation" advises invoke_workflow; "skill" arms the L2
            planner-skill injection).
    """

    level_to: int
    evidence: str
    observation_key: str


def difficulty_to_level(mode: str) -> int:
    """Map the estimator's ``recommended_mode`` to the seed posture level.

    The paper writes the scope level from difficulty (Algorithm 1 line 2),
    identifying a difficulty estimate with a scope level *by fiat*. FA makes
    that identification an
    explicit, total, unit-tested function (spec §3.2 / GAP G11).

    Raises:
        ValueError: on an unknown mode — programmer error only; the
            estimator's ``OperatingPoint`` is a closed literal union.
    """
    try:
        return _MODE_TO_LEVEL[mode]
    except KeyError:
        raise ValueError(f"unknown recommended_mode {mode!r}; expected one of {sorted(_MODE_TO_LEVEL)}") from None


def select_l2_skill(*, plan_artifact: bool) -> str:
    """Deterministic L2 skill choice (DP-7).

    Warm (a plan/research artifact is already in context) -> the lighter,
    rich-context ``feature-planning`` skill; cold -> ``plan-authoring``.
    Pure: the caller decides ``plan_artifact`` from the observed read set /
    blackboard.
    """
    return "feature-planning" if plan_artifact else "plan-authoring"


def next_level(
    state: ExpansionState,
    *,
    write_tier: int,
    read_tier_high: bool,
    verify_failed: bool,
    assumed_linear: bool,
) -> ExpansionDecision | None:
    """Evaluate one turn's evidence; return the next posture or ``None``.

    Policy is tier/verify-gated only (S10.9 / GAP-H4): the S7 bulk counters
    were validated-but-unread inputs and are no longer accepted here. They
    live in caller telemetry and :func:`near_miss_evidence`.

    Args:
        state: current posture.
        write_tier: max tier of paths written this run (0 = no writes;
            otherwise 1/3/5).
        read_tier_high: True when a high-tier path has been read.
        verify_failed: a VERIFY_ONLY command (pytest/ruff/mypy) exited
            non-zero on the previous turn.
        assumed_linear: the run was seeded ``workflow_linear``.

    Returns:
        An :class:`ExpansionDecision` to a strictly higher level, or ``None``
        when no trigger fires / the ceiling is reached.

    Raises:
        ValueError: on an out-of-range write tier — programmer error only.
    """
    if write_tier not in (0, TIER_SAFE, TIER_MEDIUM, TIER_HIGH):
        raise ValueError(f"write_tier must be one of 0/1/3/5, got {write_tier!r}")

    # RK-I: a run the estimator already sent to workflow is never nudged
    # again — the advice would duplicate what the seed says.
    if assumed_linear:
        return None

    # Monotone ceiling: nothing left to advise at level 3.
    if state.level >= LEVEL_CEILING:
        return None

    # Strongest evidence first -> the emitted trigger name is unambiguous.
    if verify_failed:
        return ExpansionDecision(level_to=3, evidence="verify_failed", observation_key="escalation")

    if write_tier == TIER_HIGH:
        return ExpansionDecision(level_to=3, evidence="high_tier_write", observation_key="escalation")

    if read_tier_high and state.level < 2:
        return ExpansionDecision(level_to=2, evidence="read_high_arm", observation_key="skill")

    # No high-tier evidence: nothing to advise. A large but safe change
    # (archive docs, tests-only) is not evidence for workflow — the counters
    # that once described this case are telemetry inputs now (see
    # near_miss_evidence).
    return None


def near_miss_evidence(
    state: ExpansionState,
    *,
    files_read: int,
    files_changed: int,
    write_tier: int,
    read_tier_high: bool,
    verify_failed: bool,
) -> dict[str, int | bool] | None:
    """Telemetry predicate for a policy-relevant boundary that did NOT escalate.

    Called by the loop only when :func:`next_level` returned ``None`` (CT-H3:
    never on a transition turn). Returns the evidence payload when the turn
    carried a signal the S11 tuning cares about:

      * bulk counters over the inherited S7 thresholds (tier-gated silent), or
      * a medium-or-higher write (verification-posture territory), or
      * a high-tier read while already armed (no re-arm by design).

    Otherwise ``None`` — clean turns emit nothing. The caller delta-gates on
    the payload so an unchanged evidence tuple is logged once per run.
    Works for ``workflow_linear``-seeded runs too: telemetry records the
    seed-was-right case as well (the caller decides; this predicate has no
    ``assumed_linear`` opinion).

    Raises:
        ValueError: on negative counters or an out-of-range write tier.
    """
    if files_read < 0 or files_changed < 0:
        raise ValueError("file counters must be non-negative")
    if write_tier not in (0, TIER_SAFE, TIER_MEDIUM, TIER_HIGH):
        raise ValueError(f"write_tier must be one of 0/1/3/5, got {write_tier!r}")

    worthy = (
        files_read > READ_LIMIT
        or files_changed > CHANGE_LIMIT
        or write_tier >= TIER_MEDIUM
        or (read_tier_high and state.level >= 2)
    )
    if not worthy:
        return None
    return {
        "files_read": files_read,
        "files_changed": files_changed,
        "write_tier": write_tier,
        "read_tier_high": read_tier_high,
        "verify_failed": verify_failed,
        "level": state.level,
    }
