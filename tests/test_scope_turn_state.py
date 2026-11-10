"""C1 — the six scope locals the driver used to carry separately.

They were `_expansion`, `_active_skill_name`, `_exhausted_flag`,
`_prev_calls`, `_prev_results`, `_last_observed_evidence` plus
`observation_context`: seven assignments, two write sites (session entry and
the per-turn boundary), three read sites. None of them was ever written alone —
the boundary reads all of them and the loop writes back four — which is the
definition of one value.

`ScopeState.adopt` exists instead of four assignments at the call site because
the order is load-bearing: `observation_context` is rebuilt from the render, so
it must be assigned after the render is adopted, not before.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fa.inner_loop.expansion import ExpansionState
from fa.inner_loop.observations import ObservationRender
from fa.inner_loop.scope_turn import ScopeState, ScopeTurnResult

if TYPE_CHECKING:
    from fa.inner_loop.registry import ToolCall, ToolResult


def _state() -> ScopeState:
    return ScopeState(expansion=ExpansionState(level=1))


def _result(
    *,
    level: int,
    skill: str,
    evidence: tuple[tuple[str, object], ...] | None,
    context: str,
) -> ScopeTurnResult:
    return ScopeTurnResult(
        expansion=ExpansionState(level=level),
        active_skill_name=skill,
        last_observed_evidence=evidence,
        render=ObservationRender(turn_context=context, skill_block=None),
    )


def test_defaults_match_the_drivers_previous_initialisation() -> None:
    """The driver seeds level and leaves everything else neutral."""
    state = _state()

    assert state.expansion.level == 1
    assert state.active_skill_name == ""
    assert state.exhausted_flag is False
    assert state.observation_context == ""
    assert state.previous_calls == ()
    assert state.previous_results == ()
    assert state.last_observed_evidence is None


def test_adopt_takes_all_four_boundary_fields() -> None:
    """C1: what one boundary decides must land in all four places."""
    state = _state()

    state.adopt(_result(level=3, skill="verify-first", evidence=(("k", 1),), context="L3 block"))

    assert state.expansion.level == 3
    assert state.active_skill_name == "verify-first"
    assert state.last_observed_evidence == (("k", 1),)
    assert state.observation_context == "L3 block"


def test_observation_context_is_rebuilt_not_appended() -> None:
    """The anti-staleness rule, now testable without driving a session.

    The old append-based S7 behaviour let an L2 line survive an L3 escalation.
    A rebuild is only guaranteed if adoption *replaces* the string, so that is
    what this pins.
    """
    state = _state()

    state.adopt(_result(level=2, skill="", evidence=None, context="L2 advice"))
    state.adopt(_result(level=3, skill="", evidence=None, context="L3 advice"))

    assert state.observation_context == "L3 advice"
    assert "L2" not in state.observation_context


def test_adopt_does_not_touch_fields_the_boundary_does_not_own() -> None:
    """`exhausted_flag` and the previous batch belong to the tool turn.

    A boundary that cleared them would silently break F6 (observations land in
    the NEXT request) — the previous batch must survive the boundary that
    consumed it.
    """
    state = _state()
    state.exhausted_flag = True
    sentinel_call = cast("ToolCall", object())
    sentinel_result = cast("ToolResult", object())
    state.previous_calls = (sentinel_call,)
    state.previous_results = (sentinel_result,)

    state.adopt(_result(level=2, skill="", evidence=None, context="L2"))

    assert state.exhausted_flag is True
    assert state.previous_calls == (sentinel_call,), "the previous batch must survive the boundary"
    assert state.previous_results == (sentinel_result,)
