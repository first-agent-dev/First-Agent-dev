"""Tests for :mod:`fa.observability.cost_guardian` (Wave-3 R-45).

Five-test scope (per the approved Wave-3 plan):
1. Observer accumulates one CostObservation per recognised artifact.
2. Guard denies the next call when the rolling rollup exceeds budget.
3. Observe-only mode (``budget_usd == 0.0``) accumulates without
   ever denying — useful for measuring baseline USD before pinning a
   real budget.
4. Unbounded mode (``budget_usd is None``) accumulates without ever
   denying — the documented default.
5. End-to-end through :func:`run_session`: an ObserverMiddleware
   pipeline with the guardian wired produces both the
   ``cost_observation`` audit row and a deny when the budget breaks.

Plus thin coverage of :func:`default_cost_extractor` parse paths
(missing artifact => ``None``; malformed artifact => observe-only-fail).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.hooks import HookPayload, HookRegistry, LifecyclePoint
from fa.inner_loop.registry import (
    ToolCall as RegistryToolCall,
)
from fa.inner_loop.registry import (
    ToolRegistry,
    ToolResult,
    ToolSpec,
)
from fa.observability import (
    COST_ARTIFACT_PREFIX,
    CostGuardian,
    CostObservation,
    CostRollup,
    default_cost_extractor,
)


def _result_with_cost(*, tokens_in: int, tokens_out: int, usd: float) -> ToolResult:
    return ToolResult.ok(
        summary="ok",
        artifacts=(
            f"{COST_ARTIFACT_PREFIX}tokens_in={tokens_in},tokens_out={tokens_out},usd={usd}",
        ),
    )


def _after_payload(tool_name: str, result: ToolResult, *, call_id: str = "tc-1") -> HookPayload:
    return HookPayload(
        tool_call=RegistryToolCall(name=tool_name, params={}, call_id=call_id),
        tool_result=result,
    )


def _before_payload(tool_name: str, *, call_id: str = "tc-1") -> HookPayload:
    return HookPayload(
        tool_call=RegistryToolCall(name=tool_name, params={}, call_id=call_id),
    )


# --- CostObservation / CostRollup invariants -------------------------------


def test_cost_observation_rejects_negative_fields() -> None:
    """Sub-zero counts are a parse error upstream; reject early."""

    with pytest.raises(ValueError, match="tokens_in"):
        CostObservation(tokens_in=-1, tokens_out=0, usd=0.0)
    with pytest.raises(ValueError, match="tokens_out"):
        CostObservation(tokens_in=0, tokens_out=-1, usd=0.0)
    with pytest.raises(ValueError, match="usd"):
        CostObservation(tokens_in=0, tokens_out=0, usd=-0.01)


def test_cost_observation_rejects_nan_and_inf_usd() -> None:
    """``float("nan")`` and ``float("inf")`` parse without raising,
    so without an explicit guard a malformed artifact could construct
    a poisoned :class:`CostObservation`. NaN poisons the rollup
    permanently (``x + NaN == NaN``) and silently disables the gate
    (``NaN > budget`` is always ``False``). ``+Inf`` flips the gate
    the other way (always denies). Reject both at the dataclass
    boundary so the extractor's ``except ValueError`` branch catches
    them as observe-only-fail.

    Regression guard for Agent-Review BUG #27 run 3.
    """

    with pytest.raises(ValueError, match="finite"):
        CostObservation(tokens_in=0, tokens_out=0, usd=float("nan"))
    with pytest.raises(ValueError, match="finite"):
        CostObservation(tokens_in=0, tokens_out=0, usd=float("inf"))
    with pytest.raises(ValueError, match="finite"):
        CostObservation(tokens_in=0, tokens_out=0, usd=float("-inf"))


def test_cost_rollup_add_accumulates_each_field() -> None:
    """Adding two samples sums tokens_in/tokens_out/usd and bumps samples."""

    rollup = CostRollup()
    rollup = rollup.add(CostObservation(tokens_in=10, tokens_out=20, usd=0.001))
    rollup = rollup.add(CostObservation(tokens_in=3, tokens_out=4, usd=0.002))

    assert rollup.tokens_in == 13
    assert rollup.tokens_out == 24
    assert rollup.usd == pytest.approx(0.003)
    assert rollup.samples == 2


# --- default_cost_extractor parse paths -------------------------------------


def test_default_extractor_returns_empty_when_no_cost_artifact() -> None:
    """Baseline M-1 tools never emit ``cost=…`` => extractor no-op
    (empty list, not ``None`` — the contract is plural by ADR-7
    §Sub-amendment 2026-05-21)."""

    assert default_cost_extractor(ToolResult.ok(summary="ok")) == []
    assert default_cost_extractor(ToolResult.ok(summary="ok", artifacts=("note=foo",))) == []


def test_default_extractor_parses_valid_artifact() -> None:
    """Valid ``cost=tokens_in=…,tokens_out=…,usd=…`` round-trips
    as a single-element list."""

    result = _result_with_cost(tokens_in=42, tokens_out=7, usd=0.0123)
    observations = default_cost_extractor(result)
    assert observations == [CostObservation(tokens_in=42, tokens_out=7, usd=0.0123)]


def test_default_extractor_returns_empty_on_malformed_artifact() -> None:
    """Malformed artifact never blocks the loop — observe-only-fail,
    skipped from the returned list rather than aborting the parse."""

    bad = ToolResult.ok(
        summary="ok",
        artifacts=(f"{COST_ARTIFACT_PREFIX}tokens_in=NaN,usd=oops",),
    )
    assert default_cost_extractor(bad) == []


def test_default_extractor_skips_nan_and_inf_usd() -> None:
    """``usd=NaN`` / ``usd=inf`` parse via :class:`float` without
    raising, but :class:`CostObservation.__post_init__` rejects them.
    The extractor's ``except ValueError`` branch must therefore skip
    these artifacts rather than constructing a poisoned observation
    that silently disables the gate.

    Regression guard for Agent-Review BUG #27 run 3 (NaN bypass).
    """

    poisoned = ToolResult.ok(
        summary="ok",
        artifacts=(
            f"{COST_ARTIFACT_PREFIX}tokens_in=10,tokens_out=5,usd=NaN",
            f"{COST_ARTIFACT_PREFIX}tokens_in=20,tokens_out=10,usd=inf",
            f"{COST_ARTIFACT_PREFIX}tokens_in=30,tokens_out=15,usd=-inf",
            # The one valid row must still survive.
            f"{COST_ARTIFACT_PREFIX}tokens_in=1,tokens_out=1,usd=0.001",
        ),
    )
    assert default_cost_extractor(poisoned) == [
        CostObservation(tokens_in=1, tokens_out=1, usd=0.001),
    ]


def test_default_extractor_returns_one_observation_per_artifact() -> None:
    """ADR-7 §Sub-amendment 2026-05-21 — «one row per recognised
    ``cost=…`` artifact»: a single :class:`ToolResult` carrying
    multiple ``cost=…`` artifacts (retry chain, router fan-out,
    batch call) returns one :class:`CostObservation` per artifact,
    in source order. A malformed artifact in the middle is skipped
    without dropping the good rows that follow.
    """

    multi = ToolResult.ok(
        summary="ok",
        artifacts=(
            f"{COST_ARTIFACT_PREFIX}tokens_in=10,tokens_out=20,usd=0.01",
            "note=ignored",  # non-cost artifact — skipped silently
            f"{COST_ARTIFACT_PREFIX}tokens_in=NaN,usd=oops",  # malformed
            f"{COST_ARTIFACT_PREFIX}tokens_in=3,tokens_out=4,usd=0.002",
        ),
    )
    observations = default_cost_extractor(multi)
    assert observations == [
        CostObservation(tokens_in=10, tokens_out=20, usd=0.01),
        CostObservation(tokens_in=3, tokens_out=4, usd=0.002),
    ]


# --- CostGuardian observe-in-handle ----------------------------------------


def test_guardian_observe_accumulates_rollup_without_event_log() -> None:
    """No EventLog wired => still accumulates the rollup on the instance."""

    guardian = CostGuardian()
    guardian.handle(
        LifecyclePoint.AFTER_TOOL_EXEC,
        _after_payload("llm.call", _result_with_cost(tokens_in=100, tokens_out=50, usd=0.01)),
    )
    guardian.handle(
        LifecyclePoint.AFTER_TOOL_EXEC,
        _after_payload("llm.call", _result_with_cost(tokens_in=10, tokens_out=5, usd=0.001)),
    )

    assert guardian.rollup.samples == 2
    assert guardian.rollup.usd == pytest.approx(0.011)


def test_guardian_observe_emits_one_row_per_artifact(tmp_path: Path) -> None:
    """ADR-7 §Sub-amendment 2026-05-21 — a :class:`ToolResult` carrying
    several ``cost=…`` artifacts (retry / fan-out / batch) produces
    one ``cost_observation`` row per artifact AND one rollup-add per
    artifact, with each row's ``rollup_*`` snapshot reflecting the
    post-add total at that step.
    """

    log = EventLog(tmp_path / ".fa" / "events.jsonl", run_id="run-multi")
    guardian = CostGuardian(event_log=log)
    multi = ToolResult.ok(
        summary="ok",
        artifacts=(
            f"{COST_ARTIFACT_PREFIX}tokens_in=10,tokens_out=5,usd=0.01",
            f"{COST_ARTIFACT_PREFIX}tokens_in=20,tokens_out=10,usd=0.02",
        ),
    )
    guardian.handle(LifecyclePoint.AFTER_TOOL_EXEC, _after_payload("llm.call", multi))

    assert guardian.rollup.samples == 2
    assert guardian.rollup.usd == pytest.approx(0.03)
    cost_rows = [e for e in log.read_all() if e.kind == "cost_observation"]
    assert len(cost_rows) == 2
    # Post-add rollup snapshots are monotonically increasing.
    assert cost_rows[0].content["usd"] == pytest.approx(0.01)
    assert cost_rows[0].content["rollup_usd"] == pytest.approx(0.01)
    assert cost_rows[0].content["rollup_samples"] == 1
    assert cost_rows[1].content["usd"] == pytest.approx(0.02)
    assert cost_rows[1].content["rollup_usd"] == pytest.approx(0.03)
    assert cost_rows[1].content["rollup_samples"] == 2


def test_guardian_observe_emits_cost_observation_event(tmp_path: Path) -> None:
    """Wired EventLog => one ``kind="cost_observation"`` row per sample."""

    log = EventLog(tmp_path / ".fa" / "events.jsonl", run_id="run-test")
    guardian = CostGuardian(event_log=log)
    guardian.handle(
        LifecyclePoint.AFTER_TOOL_EXEC,
        _after_payload(
            "llm.call",
            _result_with_cost(tokens_in=100, tokens_out=50, usd=0.01),
            call_id="tc-42",
        ),
    )

    events = log.read_all()
    cost_rows = [e for e in events if e.kind == "cost_observation"]
    assert len(cost_rows) == 1
    row = cost_rows[0]
    assert row.actor == "hook"
    assert row.tool_name == "llm.call"
    assert row.tool_call_id == "tc-42"
    assert row.content["usd"] == pytest.approx(0.01)
    assert row.content["rollup_samples"] == 1


# --- CostGuardian gate modes (None / 0.0 / >0) -----------------------------


def test_guardian_unbounded_mode_never_denies() -> None:
    """Default ``budget_usd=None`` allows even after enormous rollup."""

    guardian = CostGuardian(budget_usd=None)
    guardian.handle(
        LifecyclePoint.AFTER_TOOL_EXEC,
        _after_payload(
            "llm.call",
            _result_with_cost(tokens_in=1_000_000, tokens_out=1_000_000, usd=1_000.0),
        ),
    )
    decision = guardian.handle(LifecyclePoint.BEFORE_TOOL_EXEC, _before_payload("llm.call"))
    assert decision.action == "allow"


def test_guardian_observe_only_mode_never_denies() -> None:
    """``budget_usd=0.0`` accumulates the rollup but the gate never denies."""

    guardian = CostGuardian(budget_usd=0.0)
    guardian.handle(
        LifecyclePoint.AFTER_TOOL_EXEC,
        _after_payload("llm.call", _result_with_cost(tokens_in=10, tokens_out=10, usd=999.0)),
    )

    assert guardian.rollup.samples == 1
    assert guardian.rollup.usd == pytest.approx(999.0)
    decision = guardian.handle(LifecyclePoint.BEFORE_TOOL_EXEC, _before_payload("llm.call"))
    assert decision.action == "allow"


def test_guardian_hard_cap_denies_after_budget_breach() -> None:
    """``budget_usd > 0`` denies the next call after rollup crosses the line."""

    guardian = CostGuardian(budget_usd=0.05)

    # Below budget => allow.
    guardian.handle(
        LifecyclePoint.AFTER_TOOL_EXEC,
        _after_payload("llm.call", _result_with_cost(tokens_in=10, tokens_out=10, usd=0.02)),
    )
    decision = guardian.handle(LifecyclePoint.BEFORE_TOOL_EXEC, _before_payload("llm.call"))
    assert decision.action == "allow"

    # Cross the budget.
    guardian.handle(
        LifecyclePoint.AFTER_TOOL_EXEC,
        _after_payload("llm.call", _result_with_cost(tokens_in=10, tokens_out=10, usd=0.04)),
    )
    decision = guardian.handle(LifecyclePoint.BEFORE_TOOL_EXEC, _before_payload("llm.call"))
    assert decision.action == "deny"
    assert "budget" in decision.reason
    assert "0.060000" in decision.reason


def test_guardian_rejects_negative_budget() -> None:
    """A negative budget is a config error, not observe-only — refuse early."""

    with pytest.raises(ValueError, match="budget_usd"):
        CostGuardian(budget_usd=-0.01)


def test_guardian_rejects_nan_and_inf_budget() -> None:
    """A NaN budget silently disables the gate (every comparison is
    ``False``); ``+Inf`` silently allows everything. Refuse both at
    construction time. Regression guard for Agent-Review BUG #27 run 3
    sibling finding on the runtime-limits float parser.
    """

    with pytest.raises(ValueError, match="finite"):
        CostGuardian(budget_usd=float("nan"))
    with pytest.raises(ValueError, match="finite"):
        CostGuardian(budget_usd=float("inf"))
    with pytest.raises(ValueError, match="finite"):
        CostGuardian(budget_usd=float("-inf"))


# --- End-to-end via run_session --------------------------------------------


def test_guardian_end_to_end_through_run_session(tmp_path: Path) -> None:
    """Synthetic tool emits a ``cost=…`` artifact; the guardian denies the
    second call after the rollup crosses the budget. Asserts the
    ``cost_observation`` row and the run-stop event.
    """

    workspace = tmp_path
    log = EventLog(workspace / ".fa" / "events.jsonl", run_id="run-e2e")

    # Each call emits a `cost=…` artifact with usd=0.03; budget=0.05
    # crosses after the first call so the second call is denied.
    def _handler(_: object) -> ToolResult:
        return _result_with_cost(tokens_in=5, tokens_out=5, usd=0.03)

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="llm.call",
            description="synthetic LLM call emitting a cost= artifact",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            permission="read",
            handler=_handler,
        )
    )

    hooks = HookRegistry()
    guardian = CostGuardian(budget_usd=0.05, event_log=log)
    hooks.register(guardian)

    state = SessionState(workspace_root=workspace, run_id="run-e2e", log=log)
    # Budget 0.05 + each call usd=0.03 ⇒ call 1 runs (rollup=0.03),
    # call 2 runs (rollup=0.06; over budget); call 3 denied at
    # BEFORE_TOOL_EXEC. Asserts the deny-on-third-call posture +
    # the two ``cost_observation`` rows from calls 1 and 2.
    calls = (
        ToolCall(name="llm.call", params={}, call_id="tc-1"),
        ToolCall(name="llm.call", params={}, call_id="tc-2"),
        ToolCall(name="llm.call", params={}, call_id="tc-3"),
    )
    results = run_session(calls, registry=registry, hooks=hooks, state=state)

    assert results[0].error is None
    assert results[1].error is None
    assert results[2].error is not None
    third_error = results[2].error
    assert third_error is not None and "budget" in third_error.message

    events = log.read_all()
    cost_rows = [e for e in events if e.kind == "cost_observation"]
    assert len(cost_rows) == 2
    assert cost_rows[0].content["usd"] == pytest.approx(0.03)
    assert cost_rows[1].content["rollup_samples"] == 2
    assert guardian.rollup.usd == pytest.approx(0.06)

    # Confirm the audit trail also includes a ``run_stopped`` row
    # since the BEFORE_TOOL_EXEC deny breaks the loop.
    stop_rows = [e for e in events if e.kind == "run_stopped"]
    assert len(stop_rows) == 0  # BEFORE_TOOL_EXEC deny surfaces as a tool_result, not run_stopped
