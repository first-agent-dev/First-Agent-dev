"""S6.2 — a stop the guard requested must reach the caller (S6-F4, S6-CT2).

Contract under test
-------------------
**PRE:** a guard denies at ``AFTER_TOOL_EXEC`` / ``BETWEEN_ROUNDS``.
**POST:** ``run_session`` writes the durable ``run_stopped`` row **and** returns
an explicit ``StopInfo``; ``drive_session`` observes it and stops the turn loop.

The defect this closes (measured at S6.0)
-----------------------------------------
``_execute_one_sequential`` preserves the tool result and signals the stop
out-of-band, so a denial returns a **full** result set::

    calls issued: 1 | results returned: 1  ->  missing = 0
    run_stopped rows written: 1

``coder_loop``'s existing log read-back is guarded by ``if missing > 0``, so it
never fires; the only ``break`` after ``run_session`` lives inside that padding
block. The guard says stop, a durable row exists, and the outer loop calls the
model again. **This is a correctness bug, not a console-output bug.**

Design note — why the return type is tuple-compatible
-----------------------------------------------------
``SessionRun`` follows CPython's ``os.stat_result`` / ``time.struct_time``
pattern: it *is* the results sequence (``len``, indexing, iteration all measure
the results) and *carries* the stop as a named attribute. A bare
``(results, stop)`` tuple was rejected because ``assert len(results) == 2`` in
an existing test would have silently kept passing while measuring the pair
instead of the results (Q24).

Q12 boundary
------------
``loop.py`` must not gain an ``EventBus``. ``StopInfo`` is plain data, so the
stop travels as a value and the display decision stays in the composition root.
``test_loop_module_holds_no_event_bus_reference`` enforces this mechanically.

Test classes: C1 (real loop, real registry, real hooks) + C0 (structural).
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import override

import pytest

from fa.inner_loop.hooks.base import Decision, GuardMiddleware, HookPayload, HookRegistry, LifecyclePoint
from fa.inner_loop.loop import SessionRun, StopInfo, run_session
from fa.inner_loop.registry import ToolCall, ToolRegistry, ToolResult, ToolSpec
from fa.inner_loop.state import SessionState


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="t.ok",
            description="always succeeds",
            input_schema={"type": "object"},
            permission="read",
            handler=lambda _params: ToolResult.ok("done"),
        )
    )
    return registry


@dataclass
class _DenyAt(GuardMiddleware):
    """Guard that denies at one lifecycle point — the real denial mechanism."""

    point: LifecyclePoint = LifecyclePoint.AFTER_TOOL_EXEC
    reason: str = "policy says stop"
    name: str = "deny-at"

    @property
    def attaches_to(self) -> tuple[LifecyclePoint, ...]:  # type: ignore[override]
        return (self.point,)

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point, payload
        return Decision.deny(self.reason)


def _state(tmp_path: Path, run_id: str) -> SessionState:
    return SessionState(workspace_root=tmp_path, run_id=run_id)


# ---------------------------------------------------------------------------
# S6-P5 — the stop signal is returned, not only logged
# ---------------------------------------------------------------------------


def test_after_tool_exec_denial_returns_stop_info(tmp_path: Path) -> None:
    """C1 (S6-F4): the denial is visible to the caller as data.

    Kill-check target: return a bare ``tuple(results)`` again — ``.stop``
    disappears and this fails.
    """
    state = _state(tmp_path, "stop-after-tool")
    hooks = HookRegistry()
    hooks.register(_DenyAt(point=LifecyclePoint.AFTER_TOOL_EXEC, reason="denied by policy"))

    run = run_session(
        (ToolCall(name="t.ok", params={}, call_id="c1"),),
        registry=_registry(),
        hooks=hooks,
        state=state,
    )

    assert run.stop is not None, "guard denied but run_session reported no stop"
    assert run.stop.point == LifecyclePoint.AFTER_TOOL_EXEC.value
    assert "denied by policy" in run.stop.reason


def test_between_rounds_denial_returns_stop_info(tmp_path: Path) -> None:
    """C1: the second stop path reports too — path inventory, not one sample.

    A single EventType/signal emitted from several code paths needs each path
    tested (tests-writing skill, path-sensitivity law).
    """
    state = _state(tmp_path, "stop-between")
    hooks = HookRegistry()
    hooks.register(_DenyAt(point=LifecyclePoint.BETWEEN_ROUNDS, reason="paused"))

    run = run_session(
        (ToolCall(name="t.ok", params={}, call_id="c1"),),
        registry=_registry(),
        hooks=hooks,
        state=state,
    )

    assert run.stop is not None
    assert run.stop.point == LifecyclePoint.BETWEEN_ROUNDS.value


def test_clean_run_reports_no_stop(tmp_path: Path) -> None:
    """C1 (positive): the fix must not report a stop that did not happen.

    Without this, "always return a StopInfo" would pass every negative test.
    """
    run = run_session(
        (ToolCall(name="t.ok", params={}, call_id="c1"),),
        registry=_registry(),
        hooks=HookRegistry(),
        state=_state(tmp_path, "clean"),
    )

    assert run.stop is None, f"clean run reported a stop: {run.stop}"
    assert len(run) == 1
    assert run[0].error is None


def test_stop_info_accompanies_the_durable_row(tmp_path: Path) -> None:
    """C1: both sides agree — the returned stop matches the logged row.

    Two-sided contract: the in-band signal and the durable audit row must
    describe the same event, or one of them is lying.
    """
    state = _state(tmp_path, "stop-dual")
    hooks = HookRegistry()
    hooks.register(_DenyAt(point=LifecyclePoint.AFTER_TOOL_EXEC, reason="both sides"))
    log = state.log
    assert log is not None
    before = len(log.read_all())

    run = run_session(
        (ToolCall(name="t.ok", params={}, call_id="c1"),),
        registry=_registry(),
        hooks=hooks,
        state=state,
    )

    rows = [e for e in log.read_all()[before:] if e.kind == "run_stopped"]
    assert len(rows) == 1, f"expected exactly one run_stopped row, got {len(rows)}"
    assert run.stop is not None
    assert run.stop.reason in str(rows[0].content.get("reason", "")), (
        "returned stop reason does not match the durable row"
    )


# ---------------------------------------------------------------------------
# Q24 — the return type must not silently change existing assertions
# ---------------------------------------------------------------------------


def test_session_run_is_sequence_compatible(tmp_path: Path) -> None:
    """C0 (Q24): `len`, indexing and iteration still measure the RESULTS.

    The regression this prevents is subtle and was measured before the design
    was chosen: with a bare ``(results, stop)`` tuple, an existing
    ``assert len(results) == 2`` in a 2-call test keeps passing while measuring
    the pair. The test stays green and stops testing what it claims to.

    Kill-check target: return `(results, stop)` instead of `SessionRun` —
    `len()` becomes 2 regardless of the call count and this fails.
    """
    calls = tuple(ToolCall(name="t.ok", params={}, call_id=f"c{i}") for i in range(3))

    run = run_session(calls, registry=_registry(), hooks=HookRegistry(), state=_state(tmp_path, "seq"))

    assert len(run) == 3, "len() must count results, not the (results, stop) pair"
    assert all(r.error is None for r in run), "iteration must yield ToolResults"
    assert run[0].summary == "done", "indexing must yield a ToolResult, not a nested tuple"
    assert tuple(run) == run.results, "tuple() conversion must equal the results"


def test_session_run_is_frozen() -> None:
    """C0: the carrier is immutable — a returned result set is a fact."""
    from dataclasses import FrozenInstanceError

    run = SessionRun(results=(), stop=None)
    with pytest.raises(FrozenInstanceError):
        run.stop = StopInfo(point="x", reason="y")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Q12 — loop.py stays display-free (structural guard)
# ---------------------------------------------------------------------------


def test_loop_module_holds_no_event_bus_reference() -> None:
    """C0 (Q12): the pure path must not acquire a display dependency.

    ``output.py:126-149`` records the Q12 decision and instructs S6 explicitly:
    *"do not close it by wiring a bus into loop.py"*. A comment cannot enforce
    itself, so this asserts on the imported **module object** — not on source
    text, which would pass on commented-out code (S6-F5).
    """
    import fa.inner_loop.loop as loop_module

    offenders = [name for name in vars(loop_module) if "EventBus" in name or name == "OutputEvent"]

    assert offenders == [], f"loop.py imported display symbols {offenders}; Q12 forbids wiring a bus here"


# ---------------------------------------------------------------------------
# S6-P4 — the outer loop must honour the stop
# ---------------------------------------------------------------------------


def test_drive_session_stops_calling_the_model_after_a_denial(tmp_path: Path) -> None:
    """C1 (S6-F4, the correctness fix): the model is not called again.

    This is the assertion that fails today. ``drive_session`` currently ignores
    the inner stop and proceeds to the next turn, so the provider receives
    another request after a guard already denied the run.

    Efficiency oracle (tests-writing §3.12): assert on ``request.call_count``,
    not on free text.

    Kill-check target: remove the ``if turn_results.stop is not None: break``
    in ``_drive_session_inner``.
    """
    from fa.inner_loop.coder_loop import drive_session
    from tests.fixtures.session_wiring import make_mock_chain, mock_tool_call_response

    workspace = Path(tempfile.mkdtemp())
    chain = make_mock_chain(context_limit=150_000)
    chain.request.side_effect = [
        mock_tool_call_response("c1", "t.ok", {}),
        mock_tool_call_response("c2", "t.ok", {}),
        mock_tool_call_response("c3", "t.ok", {}),
    ]
    hooks = HookRegistry()
    hooks.register(_DenyAt(point=LifecyclePoint.AFTER_TOOL_EXEC, reason="halt the loop"))
    state = SessionState(workspace_root=workspace, run_id="drive-stop")

    drive_session(
        "do the thing",
        provider_chain=chain,
        registry=_registry(),
        hooks=hooks,
        state=state,
        max_turns=3,
    )

    assert chain.request.call_count == 1, (
        f"model was called {chain.request.call_count}x after a guard denied the run; "
        "the outer loop ignored the stop signal"
    )


def test_between_rounds_denial_does_not_break_the_turn_loop(tmp_path: Path) -> None:
    """C1: the *scope* of the break, which is the other half of S6.2's decision.

    Added 2026-07-29 after a mutation sweep. Widening the guard at
    ``coder_loop.py:1532`` from ``stop.point == AFTER_TOOL_EXEC`` to a bare
    ``stop is not None`` survived every S6 test — the sibling test above only
    pins the positive case, so nothing in S6 recorded *why* the condition is
    narrow.

    Why narrow is correct (plan §S6.2, verified not assumed): a
    ``BETWEEN_ROUNDS`` denial already shortens the result list, so the padding
    branch fires and the session continues **by design** — ``LoopGuard``'s
    circuit breaker needs several rounds to trip. Breaking on every stop point
    silently disables that.

    Kill-check: widen the condition to ``if turn_results.stop is not None:`` —
    this test fails (the model is called once instead of continuing).
    """
    from fa.inner_loop.coder_loop import drive_session
    from tests.fixtures.session_wiring import make_mock_chain, mock_tool_call_response

    workspace = Path(tempfile.mkdtemp())
    chain = make_mock_chain(context_limit=150_000)
    chain.request.side_effect = [
        mock_tool_call_response("c1", "t.ok", {}),
        mock_tool_call_response("c2", "t.ok", {}),
        mock_tool_call_response("c3", "t.ok", {}),
    ]
    hooks = HookRegistry()
    hooks.register(_DenyAt(point=LifecyclePoint.BETWEEN_ROUNDS, reason="pause, do not halt"))
    state = SessionState(workspace_root=workspace, run_id="drive-between-rounds")

    drive_session(
        "do the thing",
        provider_chain=chain,
        registry=_registry(),
        hooks=hooks,
        state=state,
        max_turns=3,
    )

    assert chain.request.call_count > 1, (
        "a BETWEEN_ROUNDS denial halted the turn loop after one model call; "
        "that path must keep iterating so LoopGuard's circuit breaker can trip"
    )


def test_stop_reason_is_recorded_in_observations(tmp_path: Path) -> None:
    """C1: the stop must be visible to the *model*, not only to the operator.

    Added 2026-07-29 after a mutation sweep: deleting the
    ``state.observations.append(f"run stopped at ...")`` line at
    ``coder_loop.py:1541`` survived the whole 2193-test suite. The console
    ``hook_deny`` event and the durable row were both pinned; the observation —
    the only channel that tells the model *why* its turn ended — was not.
    """
    from fa.inner_loop.coder_loop import drive_session
    from tests.fixtures.session_wiring import make_mock_chain, mock_tool_call_response

    workspace = Path(tempfile.mkdtemp())
    chain = make_mock_chain(context_limit=150_000)
    chain.request.side_effect = [mock_tool_call_response("c1", "t.ok", {})]
    hooks = HookRegistry()
    hooks.register(_DenyAt(point=LifecyclePoint.AFTER_TOOL_EXEC, reason="halt with a reason"))
    state = SessionState(workspace_root=workspace, run_id="drive-observation")

    drive_session(
        "do the thing",
        provider_chain=chain,
        registry=_registry(),
        hooks=hooks,
        state=state,
        max_turns=3,
    )

    stop_notes = [obs for obs in state.observations if "run stopped at" in obs]
    assert stop_notes, f"no stop observation recorded; observations={state.observations}"
    assert "halt with a reason" in stop_notes[0]
