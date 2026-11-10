"""Stage-2 masking extracted from the driver: same effects, same order, same failure.

The move is behaviour-preserving by construction, so the oracles are:

* the effect **sequence** (two durable rows and two console events, in the order
  the driver wrote them). A reordering here is invisible to "did it compact?"
  assertions but changes what an operator replaying the trace sees;
* the **re-check** after masking. `usage`, `decision` and `verdict` must describe
  the masked prompt, not the pre-mask one — the verdict is a snapshot, and a
  caller keeping the old one is exactly Q#4 (measured there: `pct=95` where the
  post-compaction number was 92);
* the **failure path**: masking raising must be swallowed, keep the run alive,
  and still report `ok=False` to the console.

Two-sided throughout: every assertion pairs a durable row with the console event
that is supposed to mirror it.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.compaction import compaction_turn
from fa.inner_loop.compaction.compaction_turn import Stage2Result, run_stage2_masking
from fa.inner_loop.state import EventLog
from fa.memory.context_budget import ContextBudget
from fa.output import EventBus, OutputEvent


class _Capture:
    def __init__(self) -> None:
        self.events: list[OutputEvent] = []

    def on_event(self, event: OutputEvent) -> None:
        self.events.append(event)

    def kinds(self) -> list[str]:
        return [e.type for e in self.events]


def _scripted(*values: int) -> Any:
    """Estimator returning ``values`` in order, then repeating the last one.

    The module under test calls it exactly once per run (the pre-mask usage
    arrives as an argument), so a single value is the normal case; scripts of
    two exist to prove the call is not cached across runs.
    """
    tail = itertools.chain(values, itertools.repeat(values[-1]))

    def estimate(*_args: Any, **_kwargs: Any) -> int:
        return next(tail)

    return estimate


class _Budget:
    """Real `ContextBudget`, scripted `estimate_tokens` values per call.

    A constant estimate cannot tell the pre-mask usage from the post-mask one,
    which is the whole point of the re-check.
    """

    def __init__(self, values: Sequence[int], *, limit: int = 100_000, stage2: int = 80_000) -> None:
        self._values = itertools.chain(values, itertools.repeat(values[-1]))
        self.budget = ContextBudget(limit_tokens=limit, configured_threshold=stage2)

    def __call__(self, *_args: Any, **_kwargs: Any) -> int:
        return next(self._values)


@pytest.fixture
def wiring(tmp_path: Path) -> tuple[EventLog, EventBus, _Capture]:
    log = EventLog(tmp_path / "events.jsonl", run_id="stage2")
    bus = EventBus()
    capture = _Capture()
    bus.add(capture)
    return log, bus, capture


def _compose(
    active_summary: str, observations: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]], Mapping[str, Any]]:
    """Stand-in for the driver's per-turn closure: payload size follows history."""
    payload = [{"role": "user", "content": f"summary={active_summary}"}]
    payload += [{"role": m["role"], "content": str(m.get("content", ""))} for m in observations]
    return {"body": True}, payload, {"prompt_cache_key": "k"}


def _run(
    wiring: tuple[EventLog, EventBus, _Capture],
    monkeypatch: pytest.MonkeyPatch,
    *,
    estimates: Sequence[int],
    history: list[dict[str, Any]] | None = None,
    masker: Any = None,
    fake_estimator: Any = None,
) -> Stage2Result:
    log, bus, _ = wiring
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    # Patch the source module, not our own binding: the point of the seam is
    # that callers inject the estimator by patching its home (eight test modules
    # do), and the module under test imports it at call time for that reason.
    monkeypatch.setattr(
        "fa.memory.context_budget.estimate_tokens",
        fake_estimator if fake_estimator is not None else _Budget(estimates),
    )
    if masker is not None:
        monkeypatch.setattr(compaction_turn, "_mask_observation_history", masker)
    return run_stage2_masking(
        turn=3,
        max_turns=8,
        history=history
        if history is not None
        else [{"role": "user", "content": "old"}, {"role": "assistant", "content": "t"}],
        memory_summary="prior summary",
        usage=85_000,
        budget=budget,
        log=log,
        output=bus,
        tool_payload=[{"name": "fs_read_file"}],
        compose_request=_compose,
        artifact_store=None,
        recent_turns_to_keep=4,
    )


# ---------------------------------------------------------------------------
# Success path — the effect sequence is the contract
# ---------------------------------------------------------------------------


def test_success_writes_start_done_and_mirrors_both(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1 two-sided: two rows, two events, interleaved start-before-done."""
    log, _, capture = wiring
    result = _run(wiring, monkeypatch, estimates=[85_000, 5_000], fake_estimator=_scripted(5_000))

    assert result.applied is True
    rows = [(r.kind, r.content) for r in log.read_all()]
    assert [k for k, _ in rows] == ["compaction_stage2_start", "compaction_stage2_done"]
    assert rows[0][1] == {"tokens_before": 85_000, "threshold": 80_000}
    assert rows[1][1] == {"tokens_before": 85_000, "tokens_after": 5_000}

    assert capture.kinds() == ["compaction_start", "compaction_end"]
    start, end = capture.events
    assert start.data == {"stage": 2, "tokens_before": 85_000}
    assert end.data == {"stage": 2, "tokens_before": 85_000, "tokens_after": 5_000, "ok": True}


def test_success_returns_the_post_mask_decision(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: the returned verdict describes the masked prompt (the Q#4 rule).

    Estimates are scripted so that before masking the verdict is `stage2` and
    after it the verdict is `warn`. A caller that kept the old verdict would
    stop or compact on pressure that no longer exists.
    """
    result = _run(wiring, monkeypatch, estimates=[85_000, 75_000], fake_estimator=_scripted(75_000))

    assert result.usage == 75_000
    assert result.decision["action"] == "warn"
    assert result.verdict.action == "warn"
    assert result.verdict.ratio == 0.75
    assert dict(result.verdict.raw) == result.decision


def test_success_replaces_history_and_request_payload(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: the caller gets the masked history, not the one it passed in."""
    original = [{"role": "user", "content": "old"}, {"role": "assistant", "content": "t"}]
    masked = [{"role": "user", "content": "masked"}]
    result = _run(
        wiring,
        monkeypatch,
        estimates=[85_000, 5_000],
        fake_estimator=_scripted(5_000),
        history=original,
        masker=lambda *_a, **_k: masked,
    )

    assert result.history == masked
    assert original[0]["content"] == "old"  # the input list is not mutated in place
    assert result.messages_payload[0]["content"] == "summary=prior summary"
    assert result.request_extras == {"prompt_cache_key": "k"}


def test_no_bus_still_writes_both_rows(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: console is optional, the trace is not."""
    log, _, _ = wiring
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    monkeypatch.setattr("fa.memory.context_budget.estimate_tokens", _scripted(5_000))
    result = run_stage2_masking(
        turn=1,
        max_turns=2,
        history=[{"role": "user", "content": "old"}],
        memory_summary="",
        usage=85_000,
        budget=budget,
        log=log,
        output=None,
        tool_payload=[],
        compose_request=_compose,
    )
    assert result.applied is True
    assert [r.kind for r in log.read_all()] == ["compaction_stage2_start", "compaction_stage2_done"]


# ---------------------------------------------------------------------------
# Failure path — the one deliberate `except`
# ---------------------------------------------------------------------------


def test_masking_failure_is_swallowed_and_reported(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: `applied=False`, an error row, an `ok=False` mirror, and no exception.

    This `except` is the only place in the loop where an exception is swallowed
    on purpose: masking is an optimisation, and losing the prompt over it would
    turn a degraded compaction into a dead session.
    """

    def boom(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        raise RuntimeError("mask exploded")

    log, _, capture = wiring
    result = _run(wiring, monkeypatch, estimates=[85_000], masker=boom)

    assert result.applied is False
    rows = [(r.kind, r.content) for r in log.read_all()]
    assert [k for k, _ in rows] == ["compaction_stage2_start", "compaction_stage2_error"]
    assert rows[1][1] == {"error": "mask exploded"}

    assert capture.kinds() == ["compaction_start", "compaction_end"]
    assert capture.events[1].data == {"stage": 2, "ok": False, "error": "mask exploded"}


def test_failure_does_not_adopt_a_re_derived_decision(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1 (negative): a failed mask must not move the caller's numbers.

    The inline version left `usage`/`decision`/`verdict` untouched when masking
    raised. Re-deriving them from the *pre-mask* prompt would double-count the
    same measurement and could flip the stage-3 trigger on a stale value.
    """

    def boom(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        raise RuntimeError("mask exploded")

    result = _run(wiring, monkeypatch, estimates=[85_000], masker=boom)

    assert result.usage == 85_000
    assert result.decision == {}
    assert result.messages_payload == []
    assert result.request_extras == {}


# ---------------------------------------------------------------------------
# The driver really calls it (delivery law)
# ---------------------------------------------------------------------------


def test_driver_routes_stage2_through_this_module(tmp_path: Path) -> None:
    """C1: `drive_session` reaches `run_stage2_masking` on the real stage-2 path.

    Measured before writing it: leaving the inline copy in place while this
    module existed was invisible to the 443-test bank, because both produce the
    same rows. The oracle therefore has to be the call, with the arguments that
    establish the seam (history, the composed payload, the budget).
    """
    from unittest.mock import patch

    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import EventLog, SessionState, coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry
    from tests.fixtures.session_wiring import make_mock_chain, mock_success_response

    calls: list[dict[str, Any]] = []
    real = compaction_turn.run_stage2_masking

    def spy(**kwargs: Any) -> Stage2Result:
        calls.append(
            {
                "usage": kwargs["usage"],
                "history_len": len(kwargs["history"]),
                "has_compose": callable(kwargs["compose_request"]),
            }
        )
        return real(**kwargs)

    log = EventLog(tmp_path / "stage2.jsonl", run_id="stage2-wired")
    # History with more assistant turns than the protected tail, or masking
    # leaves the prompt unchanged and the driver never reaches stage 2 — the
    # same "reachability" trap the probe hit (see budget_effects_probe.py).
    for i in range(1, 8):
        log.append(
            actor="model",
            kind="model_msg",
            content={
                "text": "Bulky step content " * 300,
                "tool_calls": [
                    {"id": f"tc-{i}", "type": "function", "function": {"name": "fs_read_file", "arguments": "{}"}}
                ],
            },
        )
        log.append(
            actor="tool",
            kind="tool_result",
            content={"summary": "short summary", "result": {"stdout": "A" * 150}, "ok": True},
            tool_name="fs_read_file",
            tool_call_id=f"tc-{i}",
        )
    state = SessionState(
        workspace_root=tmp_path,
        run_id="stage2-wired",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True),
    )
    chain = make_mock_chain(context_limit=100_000, compaction_threshold=80_000)
    chain.request.return_value = mock_success_response("done")

    with (
        patch.object(coder_loop, "run_stage2_masking", side_effect=spy),
        patch("fa.memory.context_budget.estimate_tokens", return_value=85_000),
    ):
        coder_loop.drive_session(
            "stage2 seeded",
            provider_chain=chain,
            registry=ToolRegistry(),
            hooks=HookRegistry(),
            state=state,
            max_turns=1,
        )

    assert len(calls) == 1, "the stage-2 path did not reach run_stage2_masking"
    assert calls[0]["usage"] == 85_000
    assert calls[0]["has_compose"] is True
    assert calls[0]["history_len"] >= 1


def test_driver_keeps_the_verbatim_prompt_when_masking_fails(tmp_path: Path) -> None:
    """C1: a failed mask leaves the run alive on the prompt it already had.

    This is the promise the driver's broad `except` existed to keep, and it is
    invisible to row-level assertions: both paths write
    `compaction_stage2_start`, but only the failure path continues with the
    unmasked request. Measured: `if stage2.applied:` replaced by `if True:`
    survived every test above, because none of them watched the request the
    provider actually received.
    """
    from unittest.mock import patch

    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import EventLog, SessionState, coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry
    from tests.fixtures.session_wiring import make_mock_chain, mock_success_response

    log = EventLog(tmp_path / "broken-mask.jsonl", run_id="broken-mask")
    for i in range(1, 8):
        log.append(
            actor="model",
            kind="model_msg",
            content={
                "text": "UNMASKED-SENTINEL " * 200,
                "tool_calls": [
                    {"id": f"tc-{i}", "type": "function", "function": {"name": "fs_read_file", "arguments": "{}"}}
                ],
            },
        )
        log.append(
            actor="tool",
            kind="tool_result",
            content={"summary": "short", "result": {"stdout": "B" * 300}, "ok": True},
            tool_name="fs_read_file",
            tool_call_id=f"tc-{i}",
        )
    state = SessionState(
        workspace_root=tmp_path,
        run_id="broken-mask",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True),
    )
    chain = make_mock_chain(context_limit=100_000, compaction_threshold=80_000)
    chain.request.return_value = mock_success_response("done")

    def boom(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        raise RuntimeError("mask exploded")

    with (
        patch.object(compaction_turn, "_mask_observation_history", side_effect=boom),
        patch("fa.memory.context_budget.estimate_tokens", return_value=85_000),
    ):
        outcome = coder_loop.drive_session(
            "bug",
            provider_chain=chain,
            registry=ToolRegistry(),
            hooks=HookRegistry(),
            state=state,
            max_turns=1,
        )

    # the session survived the failed optimisation and still asked the provider
    assert outcome.exit_code == 0 and outcome.stop_reason == "stopped_by_llm"
    assert chain.request.call_count == 1
    sent = chain.request.call_args[0][0]
    body = " ".join(str(m.get("content", "")) for m in sent.messages)
    assert "UNMASKED-SENTINEL" in body, "a failed mask must not silently drop the history it could not mask"


def test_driver_sends_the_masked_history_after_success(tmp_path: Path) -> None:
    """C1: on success the provider receives the masked prompt, not the original.

    The mirror of the failure test above, and the reason both exist: accepting
    the result is what makes masking worth doing. Measured — dropping the
    accepted values (`if stage2.applied: pass`) survived every other test,
    because they all assert on rows, and the rows are written either way.
    """
    from unittest.mock import patch

    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import EventLog, SessionState, coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry
    from tests.fixtures.session_wiring import make_mock_chain, mock_success_response

    log = EventLog(tmp_path / "masked.jsonl", run_id="masked")
    for i in range(1, 8):
        log.append(
            actor="model",
            kind="model_msg",
            content={
                "text": "MASKME-SENTINEL " * 200,
                "tool_calls": [
                    {"id": f"tc-{i}", "type": "function", "function": {"name": "fs_read_file", "arguments": "{}"}}
                ],
            },
        )
        log.append(
            actor="tool",
            kind="tool_result",
            content={"summary": "short", "result": {"stdout": "C" * 400}, "ok": True},
            tool_name="fs_read_file",
            tool_call_id=f"tc-{i}",
        )
    state = SessionState(
        workspace_root=tmp_path,
        run_id="masked",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True),
    )
    chain = make_mock_chain(context_limit=100_000, compaction_threshold=80_000)
    chain.request.return_value = mock_success_response("done")

    with patch("fa.memory.context_budget.estimate_tokens", return_value=85_000):
        outcome = coder_loop.drive_session(
            "mask me",
            provider_chain=chain,
            registry=ToolRegistry(),
            hooks=HookRegistry(),
            state=state,
            max_turns=1,
        )

    assert outcome.exit_code == 0
    sent = chain.request.call_args[0][0]
    body = " ".join(str(m.get("content", "")) for m in sent.messages)
    # Stage-2 masks the bulky tool output outside the protected tail; the
    # session keeps running, so the request must carry the reduced prompt.
    assert body.count("MASKME-SENTINEL") < 7 * 200 or "artifact" in body.lower() or "[masked" in body.lower()
