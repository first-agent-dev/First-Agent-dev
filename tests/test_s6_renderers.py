"""S6.3 — the two renderers are separate consumers and must be proven separately.

Contract under test (S6-CT3)
----------------------------
**PRE:** one event stream, two renderers.
**POST:** ``ConsoleRenderer`` and ``QuietRenderer`` are each asserted
independently; a change to one cannot mask a regression in the other.

Gap this closes (measured 2026-07-28)
-------------------------------------
``tests/test_output.py`` has 12 tests, of which 10 exercise ``ConsoleRenderer``,
one covers ``QuietRenderer`` and one covers bus fan-out. Cross-checking the
``EventType`` literal against that file: **7 of 16 types are referenced, 9 are
not** — ``api_retry``, ``compaction_end``, ``compaction_start``,
``context_warn``, ``cost_alert``, ``hook_deny``, ``loop_warn``,
``subagent_start``, ``subagent_end``.

The parametrised test below is driven **from the ``EventType`` literal itself**,
so adding a type without a renderer branch fails immediately. Enumerating
by hand is what let nine types drift out of coverage in the first place
(tests-writing skill, path-inventory law).

Quiet-mode contract (Q23, operator-resolved)
--------------------------------------------
Measured: a ``QuietRenderer`` plus a raising listener still writes ~351 bytes of
traceback to stderr via ``logger.error``. **That is correct behaviour, not a
defect**: stdout carries the final answer, diagnostics belong on stderr, and
suppressing them would hide a real fault precisely in the least verbose mode.
So quiet guarantees *silence on stdout and on the happy path* — **not**
suppression of listener failures. These tests pin that reading, so the contract
stops being an undocumented accident.

Test classes: C1 (renderer behaviour over the real bus) + C3 (failure paths).
"""

from __future__ import annotations

import io
import sys
import typing
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from fa.output import ConsoleRenderer, EventBus, EventType, OutputEvent, QuietRenderer

ALL_EVENT_TYPES: tuple[str, ...] = tuple(typing.get_args(EventType))

# Minimal, representative payloads. Handlers read specific keys; an empty dict
# would exercise only the ``.get(...)`` defaults and prove less.
_PAYLOADS: dict[str, dict[str, object]] = {
    "session_start": {"task": "demo", "model": "test/model"},
    "turn_start": {"turn": 1, "max_turns": 3},
    "llm_response": {"text": "hello", "in_tokens": 10, "out_tokens": 2},
    "tool_call": {"name": "fs_read_file", "params": {"path": "a.txt"}, "ok": True},
    "hook_deny": {"point": "after_tool_exec", "reason": "policy stop"},
    "api_retry": {"attempt": 2, "max_attempts": 3, "reason": "429"},
    "session_end": {"outcome": "done", "turns": 2},
    # pct>=80 required by output.py:380 — below that the handler is
    # intentionally silent at standard detail.
    "context_warn": {"pct": 92, "action": "stage2"},
    "compaction_warning": {"compaction_enabled": True, "threshold": 80},
    "config_warning": {"line_no": 3, "key": "worktree.mode", "detail": "bad value"},
    "compaction_start": {"stage": 2, "before_tokens": 100},
    "compaction_end": {"stage": 2, "after_tokens": 40},
    "subagent_start": {"task_id": "t1", "role": "verifier", "command_preview": "pytest"},
    # ok=False: output.py:424 prints nothing for a SUCCESSFUL subagent at
    # standard detail, by design. The failure case is the visible one.
    "subagent_end": {"task_id": "t1", "role": "verifier", "exit_code": 1, "ok": False, "error": "boom"},
    "cost_alert": {"message": "80% of budget"},
    "loop_warn": {"detector": "repeat", "message": "same call 3x"},
    "iteration_cap": {
        "point": "iteration_cap",
        "reason": "iteration_cap: per-turn iteration limit (2) exceeded — used 2 of 2",
        "profile": "coder",
    },
}


@contextmanager
def _captured_stderr() -> Iterator[io.StringIO]:
    """Capture what ConsoleRenderer writes.

    ``ConsoleRenderer._write`` calls ``sys.stderr.write`` directly
    (``output.py:265-267``) — there is no stream-injection seam — so the
    capture has to happen at ``sys.stderr``. Verified against the source rather
    than assumed: an earlier version of this file patched a ``_stream``
    attribute that does not exist, and every assertion passed vacuously
    because the renderer wrote to the real stderr instead.
    """
    buffer = io.StringIO()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(sys, "stderr", buffer)
        yield buffer


def test_payload_table_covers_every_event_type() -> None:
    """C0: the table itself must not drift from the literal.

    Without this, a new EventType could be added to ``_PAYLOADS`` *or* to
    ``EventType`` and the parametrised test below would quietly skip it.
    """
    assert set(_PAYLOADS) == set(ALL_EVENT_TYPES), (
        f"payload table out of sync: missing={set(ALL_EVENT_TYPES) - set(_PAYLOADS)}, "
        f"extra={set(_PAYLOADS) - set(ALL_EVENT_TYPES)}"
    )


# ---------------------------------------------------------------------------
# S6-P8 — console renders every event type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("event_type", ALL_EVENT_TYPES)
def test_console_renders_every_event_type(event_type: str) -> None:
    """C1 (S6-P8): every EventType produces console output.

    Driven from the ``EventType`` literal, so a new type with no renderer
    branch fails here rather than shipping invisible.

    Kill-check target: delete a ``_handle_*`` method — its parameter case fails.
    """
    renderer = ConsoleRenderer(no_color=True)

    with _captured_stderr() as buffer:
        renderer.on_event(OutputEvent(type=event_type, data=_PAYLOADS[event_type]))  # type: ignore[arg-type]

    assert buffer.getvalue().strip(), f"{event_type!r} produced no console output"


@pytest.mark.parametrize("event_type", ALL_EVENT_TYPES)
def test_console_output_is_not_a_bare_repr(event_type: str) -> None:
    """C1: the renderer formats, it does not dump the payload.

    A handler that fell back to ``str(data)`` would satisfy "produced output"
    while being unreadable, so the oracle is ranked above mere non-emptiness.
    """
    renderer = ConsoleRenderer(no_color=True)

    with _captured_stderr() as buffer:
        renderer.on_event(OutputEvent(type=event_type, data=_PAYLOADS[event_type]))  # type: ignore[arg-type]

    written = buffer.getvalue()
    assert not written.strip().startswith("{"), f"{event_type!r} dumped a raw dict: {written!r}"


# ---------------------------------------------------------------------------
# S6-P9 / S6-P10 — quiet mode, happy path and failure path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("event_type", ALL_EVENT_TYPES)
def test_quiet_emits_nothing_for_any_event_type(event_type: str) -> None:
    """C1 (S6-P9): quiet is quiet for every type, not just the sampled one.

    Kill-check target: make ``QuietRenderer.on_event`` print.
    """
    renderer = QuietRenderer()
    buffer = io.StringIO()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("sys.stdout", buffer)
        monkeypatch.setattr("sys.stderr", buffer)
        renderer.on_event(OutputEvent(type=event_type, data=_PAYLOADS[event_type]))  # type: ignore[arg-type]

    assert buffer.getvalue() == "", f"quiet mode wrote output for {event_type!r}"


def test_quiet_failure_path_keeps_diagnostics_on_stderr(caplog: pytest.LogCaptureFixture) -> None:
    """C3 (S6-P10, Q23): a raising listener still reports — by design.

    Pins the operator decision. Quiet guarantees a clean **stdout** and silence
    on the happy path; it does not suppress listener faults, because a silent
    failure in the least verbose mode is the worst place to hide one.

    Kill-check target: swallow the exception in ``EventBus.emit`` without
    logging — this fails, and so does the fan-out test below.
    """

    class _Exploding:
        def on_event(self, event: OutputEvent) -> None:
            raise RuntimeError("renderer exploded")

    bus = EventBus()
    bus.add(QuietRenderer())
    bus.add(_Exploding())

    # ``caplog``, not a captured ``sys.stderr``: ``EventBus.emit`` reports via
    # ``logger.error`` (``output.py:204``), and under pytest the logging plugin
    # owns the handlers — patching ``sys.stderr`` observes nothing and the
    # assertion would pass or fail for the wrong reason.
    with caplog.at_level("ERROR", logger="fa.output"):
        bus.emit(OutputEvent(type="session_end", data=_PAYLOADS["session_end"]))

    assert "renderer exploded" in caplog.text, (
        "a listener failure produced no diagnostic; quiet mode must not silence faults (Q23)"
    )
    assert any(record.exc_info for record in caplog.records), (
        "the diagnostic carries no traceback, so an operator cannot locate the fault"
    )


# ---------------------------------------------------------------------------
# S6-P11 — one bad listener must not starve the others
# ---------------------------------------------------------------------------


def test_listener_exception_does_not_break_fanout() -> None:
    """C3 (S6-P11): the *other* listener still receives the event.

    The existing crash-isolation test proves the loop survives. This proves the
    stronger property that actually matters: a broken renderer must not cost
    the operator the working one.

    Kill-check target: re-raise in ``EventBus.emit`` — the good listener never
    sees the event.
    """
    received: list[str] = []

    class _Exploding:
        def on_event(self, event: OutputEvent) -> None:
            raise RuntimeError("boom")

    class _Recording:
        def on_event(self, event: OutputEvent) -> None:
            received.append(event.type)

    bus = EventBus()
    bus.add(_Exploding())  # registered FIRST — order must not matter
    bus.add(_Recording())

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("sys.stderr", io.StringIO())
        bus.emit(OutputEvent(type="turn_start", data=_PAYLOADS["turn_start"]))

    assert received == ["turn_start"], "a raising listener starved the healthy one"


def test_both_renderers_consume_the_same_stream_independently() -> None:
    """C1 (S6-CT3): one stream, two consumers, neither masking the other."""
    bus = EventBus()
    bus.add(ConsoleRenderer(no_color=True))
    bus.add(QuietRenderer())

    with _captured_stderr() as buffer:
        bus.emit(OutputEvent(type="session_start", data=_PAYLOADS["session_start"]))

    assert buffer.getvalue().strip(), "console consumer produced nothing"
