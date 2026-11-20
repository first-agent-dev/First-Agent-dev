"""Runtime owner of chat scope evaluation at a turn boundary.

Pure transition and rendering policies remain in expansion/observations; this
module combines their evidence and advisory skill I/O with audit/output effects.
The driver owns session lifetime and threads this result into the next turn.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from fa.inner_loop.bash_intent import BashIntentEffect, analyze_bash_for_intent
from fa.inner_loop.expansion import ExpansionState, near_miss_evidence, next_level, select_l2_skill
from fa.inner_loop.observations import ObservationRender, build_observation_block
from fa.inner_loop.path_risk import ScopeRiskConfig, observed_tiers
from fa.inner_loop.registry import ToolCall, ToolResult
from fa.inner_loop.state import EventLog, SessionState
from fa.output import EventBus, OutputEvent
from fa.skills._inject import plan_artifact_present

logger = logging.getLogger("fa.inner_loop.coder_loop")


@dataclass(frozen=True)
class ScopeTurnResult:
    expansion: ExpansionState
    active_skill_name: str
    last_observed_evidence: tuple[tuple[str, object], ...] | None
    render: ObservationRender


@dataclass
class ScopeState:
    """What the chat-scope boundary carries from one turn to the next.

    Six locals in the driver, reassigned in two places (entry and the boundary)
    and read in three. They only ever move together — the boundary reads all
    six and writes back four — so they are one value, not six variables.

    Mutable on purpose: the driver's loop owns the transition, and a frozen
    dataclass here would force `replace()` on every turn for no gain. The
    *result* of a boundary is still frozen (`ScopeTurnResult`); this is the
    accumulator the loop threads.

    ``exhausted_flag`` is set by the tool batch rather than the boundary, which
    is why it is not in `ScopeTurnResult`: the observation render consumes it,
    the tool turn produces it.
    """

    expansion: ExpansionState
    active_skill_name: str = ""
    exhausted_flag: bool = False
    #: Per-turn observation block, REBUILT (never appended) at every boundary so
    #: a stale L2 line never survives L3. Composed on top of the caller's
    #: `turn_context`, which is session-constant (RK-H).
    observation_context: str = ""
    #: Pairs produced by the previous turn's tool batch, evaluated at the NEXT
    #: boundary (F6: observations land in the next request).
    previous_calls: tuple[ToolCall, ...] = ()
    previous_results: tuple[ToolResult, ...] = ()
    #: S10.9 / CT-H3: delta gate for `expansion_observed` — one event per
    #: distinct evidence tuple per run, never on a transition turn.
    last_observed_evidence: tuple[tuple[str, object], ...] | None = None

    def adopt(self, result: ScopeTurnResult) -> None:
        """Take the boundary's decision back into the loop's state.

        Ordering matters and is the reason this is a method rather than four
        assignments at the call site: `observation_context` is rebuilt from the
        render, so it must not be assigned before the render is adopted.
        """
        self.expansion = result.expansion
        self.active_skill_name = result.active_skill_name
        self.last_observed_evidence = result.last_observed_evidence
        self.observation_context = result.render.turn_context


def _verify_failed_in_pairs(
    *,
    calls: Sequence[ToolCall],
    results: Sequence[ToolResult],
    workspace_root: Path | None,
) -> bool:
    """True iff a VERIFY_ONLY bash command (pytest/ruff/mypy) exited non-zero
    among the given (call, result) pairs. Uses the bash_intent classifier —
    never free-text parsing. A command the classifier cannot parse is not a
    verify failure.
    """
    root = workspace_root or Path.cwd()
    for call, result in zip(calls, results, strict=False):
        if call.name != "fs_run_bash":
            continue
        if result.error is None:
            continue
        command = str(call.params.get("command", ""))
        if not command:
            continue
        try:
            analysis = analyze_bash_for_intent(command, repo_root=root)
        except Exception as exc:  # noqa: BLE001 - classification is advisory
            logger.debug("bash_intent analysis failed: %s", exc)
            continue
        if analysis.effect is BashIntentEffect.VERIFY_ONLY:
            return True
    return False


def evaluate_scope_turn(
    *,
    state: SessionState,
    scope_tiers: ScopeRiskConfig,
    scope_mode: str | None,
    expansion: ExpansionState,
    active_skill_name: str,
    exhausted_flag: bool,
    previous_calls: Sequence[ToolCall],
    previous_results: Sequence[ToolResult],
    last_observed_evidence: tuple[tuple[str, object], ...] | None,
    log: EventLog,
    output: EventBus | None,
    turn: int,
    max_turns: int,
) -> ScopeTurnResult:
    """Evaluate one chat boundary; caller threads all returned state explicitly."""
    transaction = state.transaction
    read_paths = frozenset(transaction.read_set) if transaction is not None else frozenset()
    write_paths = frozenset(transaction.write_set) if transaction is not None else frozenset()
    tiers = observed_tiers(read_paths, write_paths, scope_tiers)
    files_read = len(read_paths)
    files_changed = len(write_paths)
    write_tier = tiers["write_max"]
    read_high = tiers["read_max"] >= 5

    verify_failed = _verify_failed_in_pairs(
        calls=previous_calls,
        results=previous_results,
        workspace_root=state.workspace_root,
    )
    assumed_linear = scope_mode == "workflow_linear"

    expansion_decision = next_level(
        expansion,
        write_tier=write_tier,
        read_tier_high=read_high,
        verify_failed=verify_failed,
        assumed_linear=assumed_linear,
    )

    level_from = expansion.level
    level_to = expansion_decision.level_to if expansion_decision is not None else level_from

    # L2 skill injection: read the body ONLY on the entry turn.
    skill_result = None
    if expansion_decision is not None and expansion_decision.observation_key == "skill":
        # Warm signal: a PLAN-*.md in the read set. Blackboard
        # handoff keys arrive with CT6's blackboard entry; the read
        # path already covers plan artifacts produced this run.
        warm = plan_artifact_present(read_paths=read_paths)
        skill_name = select_l2_skill(plan_artifact=warm)
        active_skill_name = skill_name
        try:
            from fa.skills._inject import default_skills_root, read_skill_for_injection

            skill_result = read_skill_for_injection(skill_name, default_skills_root(state.workspace_root))
            if skill_result.warning is not None:
                logger.warning("L2 skill injection: %s", skill_result.warning)
        except Exception as exc:  # noqa: BLE001 - advisory must never crash
            logger.warning("L2 skill injection failed: %s", exc)
            skill_result = None

    render = build_observation_block(
        level_from=level_from,
        level_to=level_to,
        decision=expansion_decision,
        write_tier=write_tier,
        skill_result=skill_result,
        exhausted=exhausted_flag,
        skill_name=active_skill_name,
    )
    if level_to != level_from:
        expansion = ExpansionState(
            level=level_to,
            observed_read_paths=read_paths,
            observed_write_paths=write_paths,
        )
        log.append(
            actor="harness",
            kind="scope_expansion",
            content={
                "turn": turn,
                "level_from": level_from,
                "level_to": level_to,
                "evidence": expansion_decision.evidence if expansion_decision is not None else "",
                "files_read": files_read,
                "files_changed": files_changed,
                "write_tier": write_tier,
                "read_tier": tiers["read_max"],
            },
        )
        # S10.9 / CT-H4: console mirror (dual-write contract).
        if output is not None:
            output.emit(
                OutputEvent(
                    type="scope_expansion",
                    turn=turn,
                    max_turns=max_turns,
                    data={
                        "level_from": level_from,
                        "level_to": level_to,
                        "evidence": expansion_decision.evidence if expansion_decision is not None else "",
                    },
                )
            )
    else:
        expansion = ExpansionState(
            level=level_to,
            observed_read_paths=read_paths,
            observed_write_paths=write_paths,
        )
        # S10.9 / CT-H3: durable near-miss telemetry. Recorded when a
        # policy-relevant signal was present but (correctly) did not
        # escalate; delta-gated so an unchanged evidence tuple logs
        # once per run. Never fires on a transition turn (this else
        # branch). Includes workflow_linear-seeded runs — telemetry
        # records the seed-was-right case too.
        near_miss = near_miss_evidence(
            expansion,
            files_read=files_read,
            files_changed=files_changed,
            write_tier=write_tier,
            read_tier_high=read_high,
            verify_failed=verify_failed,
        )
        if near_miss is not None:
            evidence_key = tuple(sorted(near_miss.items()))
            if evidence_key != last_observed_evidence:
                last_observed_evidence = evidence_key
                log.append(
                    actor="harness",
                    kind="expansion_observed",
                    content={"turn": turn, **near_miss},
                )
    return ScopeTurnResult(expansion, active_skill_name, last_observed_evidence, render)
