"""C1 — the provider-call record, pinned by shape and order.

This block decides nothing, which is exactly why it needs a test that says so:
a pure-logging extraction is the easiest place to lose a field or swap two rows
and still pass every behavioural test, because nothing downstream branches on
the trace. The rows are durable — ``fa stats`` reads ``llm_call`` — so their
shape is part of the contract.

Three properties:

* **order** — attempts, then the rollup, then the console line;
* **shape** — the rollup's ``chain`` entries carry the same fields as the
  individual attempt rows (minus the logical id, which the row already has);
* **absence** — ``cost_usd`` is not invented (BACKLOG I-33: no wired cost
  source; a placeholder reads as "free").
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast, override

import pytest

from fa.inner_loop.provider_turn import record_provider_call
from fa.inner_loop.state import EventLog
from fa.providers.types import ChainAttemptRecord

if TYPE_CHECKING:
    from fa.providers.base import ResponseInfo


class _Capture:
    """Minimal EventBus stand-in: records OutputEvents the way the driver sees them."""

    def __init__(self) -> None:
        self.events: list[Any] = []

    def emit(self, event: Any) -> None:
        self.events.append(event)

    def kinds(self) -> list[str]:
        return [event.type for event in self.events]


def _attempt(**over: Any) -> ChainAttemptRecord:
    base: dict[str, Any] = {
        "provider": "anthropic",
        "slug": "claude-x",
        "status": "ok",
        "ms": 12,
        "error": None,
    }
    base.update(over)
    return ChainAttemptRecord(**base)


class _Response:
    """Only the attributes `record_provider_call` reads — a structural fake.

    Typed as `Any` at the call boundary below: `ResponseInfo` is a protocol-ish
    carrier and building a real one here would couple this test to its
    constructor rather than to the record it is checking.
    """

    in_tokens = 100
    out_tokens = 20
    cache_read_input_tokens = 7
    cache_creation_input_tokens = 3
    text = "hello"
    tool_calls: tuple[Any, ...] = ()


def _run(
    tmp_path: Path,
    *,
    attempts: list[ChainAttemptRecord] | None = None,
    output: Any = None,
) -> EventLog:
    log = EventLog(tmp_path / "events.jsonl", run_id="r1")
    record_provider_call(
        log=log,
        output=output,
        response=cast("ResponseInfo", _Response()),
        attempts=attempts if attempts is not None else [_attempt()],
        logical_call_id="call-1",
        role="coder",
        model="claude-x",
        family="anthropic",
        turn=2,
        max_turns=5,
    )
    return log


def test_rows_and_console_come_out_in_the_documented_order(tmp_path: Path) -> None:
    """C1: attempts -> rollup -> console, as ONE interleaved sequence.

    Checking the two streams separately is not enough: a mutation that emitted
    the console line before the rollup left both assertions true and survived.
    The operator and `fa stats` read the same moment, so the order between the
    durable row and the console line is what is actually pinned here.
    """
    timeline: list[str] = []

    class _Timeline(_Capture):
        @override
        def emit(self, event: Any) -> None:
            timeline.append(f"console:{event.type}")
            super().emit(event)

    bus = _Timeline()
    log = _run(tmp_path, attempts=[_attempt(), _attempt(provider="openai", ms=30)], output=bus)

    timeline[:0] = [f"row:{row.kind}" for row in log.read_all()]

    assert timeline == [
        "row:provider_attempt",
        "row:provider_attempt",
        "row:llm_call",
        "console:llm_response",
    ]


def test_rollup_chain_matches_the_attempt_rows(tmp_path: Path) -> None:
    """C1: the same fields per attempt in both places, or the rollup lies.

    The rollup embeds a compact chain; ``fa stats`` reads it as the story of what
    happened. A field present on an attempt row and missing from the rollup makes
    the two disagree about the same call.
    """
    log = _run(tmp_path, attempts=[_attempt(provider="a", ms=1), _attempt(provider="b", ms=2)])

    rows = log.read_all()
    attempt_rows = [row.content for row in rows if row.kind == "provider_attempt"]
    rollup = next(row.content for row in rows if row.kind == "llm_call")

    shared = set(attempt_rows[0]) - {"logical_call_id"}
    chain = cast("list[dict[str, Any]]", rollup["chain"])
    for entry, attempt_row in zip(chain, attempt_rows, strict=True):
        assert set(entry) == shared
        assert {k: entry[k] for k in shared} == {k: attempt_row[k] for k in shared}


def test_every_attempt_row_carries_the_logical_call_id(tmp_path: Path) -> None:
    """The join key: without it the rows cannot be attached to a call."""
    log = _run(tmp_path, attempts=[_attempt(), _attempt()])

    attempt_rows = [row.content for row in log.read_all() if row.kind == "provider_attempt"]
    assert [row["logical_call_id"] for row in attempt_rows] == ["call-1", "call-1"]


def test_rollup_reports_total_wallclock_not_the_last_attempt(tmp_path: Path) -> None:
    """Two attempts at 12 + 30 ms are 42 ms of wallclock, not 30.

    The console line, by contrast, reports the last attempt's latency — that is
    what the operator sees as "how long the successful call took". Pinning both
    keeps a future "simplification" from making them agree for the wrong reason.
    """
    bus = _Capture()
    log = _run(tmp_path, attempts=[_attempt(ms=12), _attempt(ms=30)], output=bus)

    rollup = next(row.content for row in log.read_all() if row.kind == "llm_call")
    assert rollup["wallclock_ms"] == 42
    assert bus.events[0].data["ms"] == 30


@pytest.mark.parametrize("forbidden", ["cost_usd", "cost", "cost_estimate"])
def test_cost_is_absent_not_zero(tmp_path: Path, forbidden: str) -> None:
    """BACKLOG I-33: absence is honest, 0.0 would read as "this call was free"."""
    log = _run(tmp_path)

    rollup = next(row.content for row in log.read_all() if row.kind == "llm_call")
    assert forbidden not in rollup


def test_headless_run_still_writes_rows(tmp_path: Path) -> None:
    """``output=None`` suppresses the console only; the trace is durable state."""
    log = _run(tmp_path, output=None)

    assert [row.kind for row in log.read_all()] == ["provider_attempt", "llm_call"]


def test_no_attempts_does_not_raise(tmp_path: Path) -> None:
    """A response with an empty attempt list is representable; wallclock is 0."""
    bus = _Capture()
    log = _run(tmp_path, attempts=[], output=bus)

    rollup = next(row.content for row in log.read_all() if row.kind == "llm_call")
    assert rollup["chain"] == []
    assert rollup["wallclock_ms"] == 0
    assert bus.events[0].data["ms"] == 0
