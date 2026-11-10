"""Provider failures as a decision table — C1 for the value, C2 for the effects.

Why this file exists
--------------------
The three handlers it replaces could only be exercised by making a real chain
fail: the decision was a `return` inside the driver, and the counter that decides
retry-vs-stop was session state mutated in place. So the following had no test at
all before this slice, and each was a plausible production bug:

* the exhaustion counter's increment (its only consumer is
  ``session_meta.chain_exhaustion_events`` at session end — lose it and the
  metric silently reads zero forever);
* the boundary between "retry the turn" and "stop": ``<=`` vs ``<``, one off by
  one turn;
* the order of effects, which differs by path (``run_stopped`` before
  ``api_retry`` on stops, log line before console lines on retries).

Class per path: C1 = the returned decision, C2 = the rows and events it wrote.
The driver's delegation is C1 in `test_provider_turn.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop import provider_turn
from fa.inner_loop.provider_turn import (
    ProviderRetry,
    ProviderTurnStop,
    handle_provider_failure,
)
from fa.inner_loop.state import EventLog
from fa.output import EventBus, OutputEvent
from fa.providers.errors import ProviderChainExhaustedError, ProviderRequestShapeError
from fa.providers.types import ChainAttemptRecord


class _Capture:
    def __init__(self) -> None:
        self.events: list[OutputEvent] = []

    def on_event(self, event: OutputEvent) -> None:
        self.events.append(event)

    def types(self) -> list[str]:
        return [e.type for e in self.events]


def _log(tmp_path: Path) -> EventLog:
    return EventLog(tmp_path / "events.jsonl", run_id="failures")


def _attempt(provider: str = "openrouter", status: int = 503, error: str = "upstream 503") -> ChainAttemptRecord:
    return ChainAttemptRecord(provider=provider, slug=f"{provider}/m", status=status, ms=12, error=error)


def _exhausted(*attempts: ChainAttemptRecord) -> ProviderChainExhaustedError:
    return ProviderChainExhaustedError("all entries failed", attempts=list(attempts or [_attempt()]))


def _handle(
    exc: BaseException,
    *,
    log: EventLog,
    output: EventBus | Any = None,
    count: int = 0,
    max_retries: int = 0,
    turn: int = 1,
    max_turns: int = 3,
) -> provider_turn.ProviderFailure:
    return handle_provider_failure(
        exc,
        exhaustion_count=count,
        max_retries=max_retries,
        log=log,
        output=output,
        turn=turn,
        max_turns=max_turns,
    )


# ── KeyboardInterrupt: the user asked to stop ────────────────────────────


def test_interrupt_stops_with_130_and_writes_one_row(tmp_path: Path) -> None:
    """Ctrl+C is an exit, not an error: 130 and a single `run_stopped`."""
    log = _log(tmp_path)
    bus = EventBus()
    capture = _Capture()
    bus.add(capture)

    failure = _handle(KeyboardInterrupt(), log=log, output=bus)

    assert failure.stop == ProviderTurnStop(exit_code=130, reason="abnormal_stop:interrupt")
    assert failure.retry is None
    assert [e.kind for e in log.read_all()] == ["run_stopped"]
    # No console line: the interrupt already reached the terminal as ^C, and a
    # second banner would be noise. This is existing behaviour, pinned so a
    # refactor cannot "improve" it silently.
    assert capture.events == []


def test_interrupt_does_not_touch_the_exhaustion_counter(tmp_path: Path) -> None:
    """The counter counts chain exhaustion, not every way a session ends."""
    log = _log(tmp_path)
    failure = _handle(KeyboardInterrupt(), log=log, count=2)
    assert failure.exhaustion_count == 2
    assert log.chain_exhaustion_count == 0


# ── ProviderRequestShapeError: FA built a bad request ────────────────────


def test_shape_failure_stops_with_2_and_names_the_provider(tmp_path: Path) -> None:
    """Both the local (pre-HTTP) and the provider-returned 400 land here."""
    log = _log(tmp_path)
    bus = EventBus()
    capture = _Capture()
    bus.add(capture)
    exc = ProviderRequestShapeError("dangling tool_call", status=400, provider="openrouter")

    failure = _handle(exc, log=log, output=bus)

    assert failure.stop == ProviderTurnStop(exit_code=2, reason="request_shape")
    assert failure.retry is None
    rows = log.read_all()
    assert [r.kind for r in rows] == ["run_stopped"]
    assert rows[0].content["reason"] == "request_shape"
    assert "dangling tool_call" in str(rows[0].content["detail"])
    assert capture.events[0].data["reason"] == "request_shape_error: dangling tool_call"
    assert capture.events[0].data["status"] == 400


def test_shape_failure_without_provider_still_reports_one(tmp_path: Path) -> None:
    """A locally-raised shape error has no provider; the console must not print None."""
    log = _log(tmp_path)
    bus = EventBus()
    capture = _Capture()
    bus.add(capture)

    _handle(ProviderRequestShapeError("bad order"), log=log, output=bus)

    assert capture.events[0].data["provider"] == "unknown"


def test_shape_failure_is_not_mistaken_for_exhaustion(tmp_path: Path) -> None:
    """EDGE KILL-CHECK for the isinstance order.

    Both exceptions derive from `Exception`, so a shape error is only misrouted
    if the checks are reordered or merged — and the visible symptom would be a
    wrong exit code (2/`chain_exhausted` instead of 2/`request_shape`) with a
    plausible-looking trace. Asserting the exact reason is what catches it.
    """
    log = _log(tmp_path)
    failure = _handle(ProviderRequestShapeError("x", status=422, provider="p"), log=log, count=5, max_retries=99)
    assert failure.stop is not None
    assert failure.stop.reason == "request_shape"
    assert failure.exhaustion_count == 5  # not incremented


# ── ProviderChainExhaustedError: retry the turn, or stop ─────────────────


def test_first_exhaustion_with_retries_budget_retries_the_whole_turn(tmp_path: Path) -> None:
    """`max_retries=1`, count 0 → retry, and the counter advances to 1."""
    log = _log(tmp_path)
    failure = _handle(_exhausted(), log=log, count=0, max_retries=1)

    assert failure.stop is None
    assert failure.retry == ProviderRetry(exhaustion_count=1, max_retries=1)
    assert failure.exhaustion_count == 1


def test_retry_path_writes_no_rows_but_emits_every_attempt(tmp_path: Path) -> None:
    """The retry seam already persisted the attempts; re-logging would double-count.

    Pinned because "the retry path writes nothing" is a decision, not an
    oversight: `_request_with_cooldown_retries` logs each attempt before it
    re-raises, and `fa stats` counts them.
    """
    log = _log(tmp_path)
    bus = EventBus()
    capture = _Capture()
    bus.add(capture)

    _handle(_exhausted(_attempt("a"), _attempt("b")), log=log, output=bus, count=0, max_retries=2)

    assert [e.kind for e in log.read_all()] == []
    assert capture.types() == ["api_retry", "api_retry"]
    assert [e.data["provider"] for e in capture.events] == ["a", "b"]


def test_retries_exhausted_stops_the_session_with_chain_exhausted(tmp_path: Path) -> None:
    """One past the budget is a stop, not another retry."""
    log = _log(tmp_path)
    bus = EventBus()
    capture = _Capture()
    bus.add(capture)

    failure = _handle(_exhausted(), log=log, output=bus, count=1, max_retries=1)

    assert failure.stop == ProviderTurnStop(exit_code=2, reason="chain_exhausted")
    assert failure.retry is None
    rows = log.read_all()
    assert [r.kind for r in rows] == ["run_stopped"]
    assert rows[0].content["reason"] == "chain_exhausted"
    assert "all entries failed" in str(rows[0].content["detail"])
    assert capture.types() == ["api_retry"]


@pytest.mark.parametrize(
    ("count", "max_retries", "expected"),
    [(0, 0, "stop"), (0, 1, "retry"), (1, 1, "stop"), (2, 3, "retry")],
)
def test_retry_boundary_is_inclusive_of_the_budget(tmp_path: Path, count: int, max_retries: int, expected: str) -> None:
    """EDGE KILL-CHECK: `<=` not `<`.

    With the off-by-one, `count=1, max_retries=1` would retry forever at the
    boundary or stop one retry early; both look fine in a single-shot test.
    """
    failure = _handle(_exhausted(), log=_log(tmp_path), count=count, max_retries=max_retries)
    actual = "retry" if failure.retry is not None else "stop"
    assert actual == expected


def test_exhaustion_counter_advances_on_both_paths(tmp_path: Path) -> None:
    """LIVENESS: the counter is the metric `fa stats` reports at session end.

    Before this file, no test asserted the increment at all — `test_s22` only
    checks that `EventLog.chain_exhaustion_count` starts at zero, so dropping
    `log.chain_exhaustion_count += 1` would have passed every suite while
    `chain_exhaustion_events` read 0 forever.
    """
    retry_log = _log(tmp_path)
    stop_log = _log(tmp_path)

    _handle(_exhausted(), log=retry_log, count=0, max_retries=5)
    _handle(_exhausted(), log=stop_log, count=0, max_retries=0)

    assert retry_log.chain_exhaustion_count == 1
    assert stop_log.chain_exhaustion_count == 1


def test_stop_path_narrates_attempts_before_the_row(tmp_path: Path) -> None:
    """Order is the contract: the failed attempts, then `run_stopped`.

    The order was the other way round in the first version of this slice, and the
    S6 pairing rule caught it by a different route: `run_stopped` must be paired
    with a console mirror of *its own* row, and a row written 40+ lines from the
    nearest emit is unpaired. Putting the attempts first satisfies both the
    operator's reading order (reasons, then "the session ended") and the pairing
    rule, without weakening either.
    """
    seen: list[str] = []
    log = _log(tmp_path)
    bus = EventBus()

    class _Ordered:
        def on_event(self, event: OutputEvent) -> None:
            seen.append(f"event:{event.type}")

    bus.add(_Ordered())
    original = log.append

    def spy(**kwargs: Any) -> Any:
        seen.append(f"row:{kwargs['kind']}")
        return original(**kwargs)

    log.append = spy  # type: ignore[method-assign]
    try:
        _handle(_exhausted(), log=log, output=bus, count=0, max_retries=0)
    finally:
        del log.append

    assert seen == ["event:api_retry", "row:run_stopped"]


def test_nil_output_still_writes_rows(tmp_path: Path) -> None:
    """Headless runs have no bus; the durable trace must not depend on it."""
    log = _log(tmp_path)
    failure = _handle(_exhausted(), log=log, output=None, count=0, max_retries=0)
    assert failure.stop is not None
    assert [e.kind for e in log.read_all()] == ["run_stopped"]


def test_unknown_exception_is_loud(tmp_path: Path) -> None:
    """The driver's `except` list and this table must not silently disagree."""
    with pytest.raises(TypeError, match="ValueError"):
        _handle(ValueError("not a provider failure"), log=_log(tmp_path))
