"""Stage-3 compaction extracted from the driver: three exits, one contract.

Stage-3 has three ways to end its work, and the old inline code reached two of
them through `return finish_at(...)` while the third fell out of the bottom of
the block:

1. **the breaker** — compaction ran, three attempts reclaimed <10% again;
2. **still over budget** — compaction ran (or did not) and the prompt is still
   over the stage-3 threshold;
3. **no older history** — nothing to compact, and the prompt may *still* be over
   the threshold, so the same hard stop applies.

Exit 3 is the one this slice got wrong first: returning early skipped the
re-check, and a stage-3 session walked on to the provider instead of exiting 1.
The probe caught it; the tests below pin all three, because "the module works"
and "each exit still fires" failed independently.

The module writes the rows and events, and *reports* the stop. `finish_at` stays
in the driver: it closes over eight driver locals, and handing those over would
be a bigger seam than the one being removed.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.budget_turn import BudgetVerdict, classify_budget
from fa.inner_loop.compaction.compaction_turn import Stage3Result, run_stage3_compaction
from fa.inner_loop.state import EventLog
from fa.memory.context_budget import ContextBudget
from fa.output import EventBus, OutputEvent

_DEFAULT = {"action": "allow", "ratio": 0.5, "message": "healthy"}


class _Capture:
    def __init__(self) -> None:
        self.events: list[OutputEvent] = []

    def on_event(self, event: OutputEvent) -> None:
        self.events.append(event)

    def kinds(self) -> list[str]:
        return [e.type for e in self.events]


def _scripted(*values: int) -> Any:
    tail = itertools.chain(values, itertools.repeat(values[-1]))

    def estimate(*_args: Any, **_kwargs: Any) -> int:
        return next(tail)

    return estimate


def _compose(
    active_summary: str, observations: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    payload = [{"role": "user", "content": f"summary={active_summary}"}]
    payload += [{"role": m["role"], "content": str(m.get("content", ""))} for m in observations]
    return {"body": True}, payload, {"prompt_cache_key": "k"}


@pytest.fixture
def wiring(tmp_path: Path) -> tuple[EventLog, EventBus, _Capture]:
    log = EventLog(tmp_path / "events.jsonl", run_id="stage3")
    bus = EventBus()
    capture = _Capture()
    bus.add(capture)
    return log, bus, capture


def _history(turns: int = 6) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for i in range(turns):
        messages.append({"role": "assistant", "content": f"turn {i}"})
        messages.append({"role": "user", "content": f"next {i}"})
    return messages


def _verdict(budget: ContextBudget, tokens: int) -> BudgetVerdict:
    return classify_budget(
        budget.check(tokens),
        stage2_threshold=budget.stage2_threshold,
        stage3_threshold=budget.stage3_threshold,
    )


def _run(
    wiring: tuple[EventLog, EventBus, _Capture],
    monkeypatch: pytest.MonkeyPatch,
    *,
    usage: int = 95_000,
    post_usage: int | None = 92_000,
    history: list[dict[str, Any]] | None = None,
    breaker: bool = False,
    compactor: Any = None,
    memory_summary: str = "prior",
) -> tuple[Stage3Result, ContextBudget]:
    log, bus, _ = wiring
    budget = ContextBudget(limit_tokens=100_000, configured_threshold=80_000)
    if breaker:
        budget.record_compaction_attempt = lambda **_kwargs: False  # type: ignore[method-assign]
    monkeypatch.setattr(
        "fa.memory.context_budget.estimate_tokens",
        _scripted(post_usage if post_usage is not None else usage),
    )
    if compactor is not None:
        # Injected through the real constructor site: stage-3 builds its
        # compactor inside the module, so patching the class is what a failure
        # actually looks like from the caller's side.
        monkeypatch.setattr("fa.inner_loop.compaction.compactor.FullLLMCompactor", lambda **_kw: compactor)
    result = run_stage3_compaction(
        turn=4,
        max_turns=9,
        history=history if history is not None else _history(),
        memory_summary=memory_summary,
        usage=usage,
        budget=budget,
        log=log,
        output=bus,
        tool_payload=[{"name": "fs_read_file"}],
        compose_request=_compose,
        compactor_chain=None,
        verdict_for_console=_verdict(budget, usage),
    )
    return result, budget


# ---------------------------------------------------------------------------
# Exit 1 — the circuit breaker
# ---------------------------------------------------------------------------


def test_breaker_records_its_rows_and_reports_the_stop(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: breaker row, compaction_end(ok=False), context_warn, loop_warn, exit rows."""
    log, _, capture = wiring
    result, _ = _run(wiring, monkeypatch, breaker=True, post_usage=94_000)

    assert result.stopped is True
    assert result.stop_message == "Compaction circuit breaker triggered: anti-thrashing loop locked."

    kinds = [r.kind for r in log.read_all()]
    assert kinds == [
        "compaction_stage3_start",
        "compaction_stage3_done",
        "compaction_circuit_breaker",
        "context_budget_hard_stop",
        "run_stopped",
    ]
    assert capture.kinds() == ["compaction_start", "compaction_end", "compaction_end", "context_warn", "loop_warn"]
    loop_warn = next(e for e in capture.events if e.type == "loop_warn")
    assert loop_warn.data["detector"] == "compaction_circuit_breaker"


def test_breaker_rows_and_console_agree_on_the_percentage(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1 (Q#4 + Q#5 on the breaker path): 94% in the row *and* on the console.

    Before this slice the console printed the post-*masking* verdict while the
    durable row carried the post-*compaction* usage — one exit, two numbers
    (measured at 94 vs 70). The row is built from `post_compaction_usage` and
    the console from the verdict of that same usage.
    """
    log, _, capture = wiring
    _run(wiring, monkeypatch, breaker=True, post_usage=94_000)

    row = next(r for r in log.read_all() if r.kind == "context_budget_hard_stop")
    assert row.content["ratio"] == 0.94
    warn = next(e for e in capture.events if e.type == "context_warn")
    assert warn.data["pct"] == 94
    assert warn.data["message"] == "Compaction circuit breaker triggered: anti-thrashing loop locked."


# ---------------------------------------------------------------------------
# Exit 2 — compacted, still over budget
# ---------------------------------------------------------------------------


def test_successful_compaction_over_budget_still_stops(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: the compacted prompt is re-measured, and 92% is still a stop."""
    log, _, capture = wiring
    result, _ = _run(wiring, monkeypatch, usage=95_000, post_usage=92_000)

    assert result.stopped is True
    assert "92000 tokens" in result.stop_message
    row = next(r for r in log.read_all() if r.kind == "context_budget_hard_stop")
    assert row.content["ratio"] == 0.92, "the row must describe the post-compaction prompt"
    assert [e.data.get("pct") for e in capture.events if e.type == "context_warn"] == [92]


def test_successful_compaction_under_budget_continues(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: 70% after compaction — no stop, and the caller gets the new state."""
    log, _, capture = wiring
    result, _ = _run(wiring, monkeypatch, usage=95_000, post_usage=70_000)

    assert result.applied is True
    assert result.stopped is False
    assert result.usage == 70_000
    assert result.verdict.action == "warn"
    assert result.memory_summary != "prior"
    assert [r.kind for r in log.read_all()] == ["compaction_stage3_start", "compaction_stage3_done"]
    assert capture.kinds() == ["compaction_start", "compaction_end"]


# ---------------------------------------------------------------------------
# Exit 3 — nothing to compact (the exit this slice broke first)
# ---------------------------------------------------------------------------


def test_nothing_to_compact_still_stops_when_over_budget(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1 (regression): no older history is not a licence to continue.

    The first version returned early with `stopped=False`, skipping the
    re-check. The old inline code always ran `if decision == stage3` after the
    block, so a session whose prompt was over the threshold exited 1 even
    though compaction had nothing to do. Measured: it walked on to the provider.
    """
    log, _, capture = wiring
    # every message in the protected tail → older_history empty
    result, _ = _run(wiring, monkeypatch, usage=95_000, post_usage=None, history=[], memory_summary="")

    assert result.stopped is True
    assert "92000" not in result.stop_message  # no compaction happened; usage is unchanged
    assert [r.kind for r in log.read_all()] == [
        "compaction_stage3_start",
        "context_budget_hard_stop",
        "run_stopped",
    ]
    assert "context_warn" in capture.kinds()
    # compaction_start is emitted on entry; no compaction_end: nothing compacted
    assert capture.kinds() == ["compaction_start", "context_warn"]


def test_nothing_to_compact_and_under_budget_continues(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1 (negative): the re-check decides, so it must not stop unconditionally.

    Nothing to compact means the prompt is unchanged — if that prompt is under
    the stage-3 threshold the session continues. This pins the re-check as a
    real decision rather than "reached stage 3 → stop".
    """
    result, _ = _run(wiring, monkeypatch, usage=85_000, history=[], memory_summary="")
    assert result.stopped is False
    assert result.applied is False
    assert result.verdict.action == "stage2"


# ---------------------------------------------------------------------------
# Failure — the swallow, and the re-check that still decides
# ---------------------------------------------------------------------------


def test_compaction_failure_is_swallowed_and_rechecked(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: a raising compactor degrades, does not kill — unless pressure remains.

    Stage-3 is an optimisation; when it raises the session continues on the
    prompt it had. But the *reason* it continues must be that the prompt is
    fine, not that the failure hid the check: here the unchanged prompt is
    still at 95%, so the exit fires.
    """

    class _Boom:
        def compact(self, _text: str) -> str:
            raise RuntimeError("compactor exploded")

    log, _, capture = wiring
    result, _ = _run(wiring, monkeypatch, usage=95_000, post_usage=None, compactor=_Boom())

    assert result.stopped is True
    kinds = [r.kind for r in log.read_all()]
    assert kinds == [
        "compaction_stage3_start",
        "compaction_stage3_error",
        "context_budget_hard_stop",
        "run_stopped",
    ]
    error_row = next(r for r in log.read_all() if r.kind == "compaction_stage3_error")
    assert error_row.content == {"error": "compactor exploded"}
    assert capture.kinds() == ["compaction_start", "compaction_end", "context_warn"]
    assert capture.events[1].data["ok"] is False


def test_compaction_failure_under_budget_continues_when_pressure_is_gone(
    wiring: tuple[EventLog, EventBus, _Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: the swallow is real — no exception escapes to the caller."""
    from fa.inner_loop.compaction.compactor import FullLLMCompactor

    class _Boom:
        def compact(self, _text: str) -> str:
            raise RuntimeError("boom")

    # The prompt was unchanged by the failure, so the re-check runs on the
    # pre-call usage: give it one that is under the threshold, and the session
    # must continue on the original prompt.
    result, _ = _run(wiring, monkeypatch, usage=85_000, post_usage=None, compactor=_Boom())
    assert result.stopped is False
    assert result.applied is False  # nothing was compacted
    assert isinstance(FullLLMCompactor, type)  # guard: the real class still importable


# ---------------------------------------------------------------------------
# The driver performs the stop, and reports the right percentage
# ---------------------------------------------------------------------------


def test_driver_stops_with_the_post_compaction_percentage() -> None:
    """C1: `session_end` reports the state the stop was decided on.

    Replaces what a spy could not see: the driver must adopt `stage3.verdict`
    before `finish_at`, otherwise the summary prints the pre-compaction ratio.
    Measured before this fix: 99% where the run died at 92%.
    """
    import tempfile
    from unittest.mock import patch

    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import EventLog, SessionState, coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry
    from fa.output import EventBus
    from tests.fixtures.session_wiring import make_mock_chain, mock_success_response

    captured: list[OutputEvent] = []
    tmp = Path(tempfile.mkdtemp())
    log = EventLog(tmp / "pct.jsonl", run_id="stage3-pct")
    for i in range(1, 8):
        log.append(
            actor="model",
            kind="model_msg",
            content={
                "text": "bulk " * 400,
                "tool_calls": [
                    {"id": f"tc-{i}", "type": "function", "function": {"name": "fs_read_file", "arguments": "{}"}}
                ],
            },
        )
        log.append(
            actor="tool",
            kind="tool_result",
            content={"summary": "s", "result": {"stdout": "A" * 200}, "ok": True},
            tool_name="fs_read_file",
            tool_call_id=f"tc-{i}",
        )
    state = SessionState(
        workspace_root=tmp,
        run_id="stage3-pct",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True),
    )
    bus = EventBus()
    bus.add(type("L", (), {"on_event": lambda self, e: captured.append(e)})())
    chain = make_mock_chain(context_limit=100_000, compaction_threshold=80_000)
    chain.request.return_value = mock_success_response("done")

    # pre-mask 95k → after masking 92k → after stage-3 compaction 92k
    with patch("fa.memory.context_budget.estimate_tokens", _scripted(95_000, 92_000, 92_000)):
        outcome = coder_loop.drive_session(
            "seed",
            provider_chain=chain,
            registry=ToolRegistry(),
            hooks=HookRegistry(),
            state=state,
            max_turns=1,
            output=bus,
        )

    assert outcome.exit_code == 1 and outcome.stop_reason == "context_budget_hard_stop"
    end = next(e for e in captured if e.type == "session_end")
    assert end.data["context_used_pct"] == 92.0
    # The stop itself is the driver's job: the module only reported it. Pinning
    # the outcome here means a module that reports `stopped` while the driver
    # ignores it cannot pass — the provider must never be called.
    assert outcome.final_text.startswith("Context budget critical: 92000 tokens")
    assert chain.request.call_count == 0
