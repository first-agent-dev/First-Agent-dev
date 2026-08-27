"""S7 / CT10: the mid-run scope tripwire.

Root: ``drive_session``. Provider I/O is mocked; EventLog, SessionState, the
transaction counters, and prompt composition are all real.

The oracle that matters here is **the composed request body**, not an append to
some intermediate list. An earlier revision of this design routed the
observation through ``state.observations``, which is written in seven places
and read by nothing on this path — every mock-based test would still have
passed while the model never saw a word of it. So the load-bearing test below
reaches into the actual payload handed to the provider.

Kill-checks (each verified to discriminate before this file was committed):
  - remove the ``turn_context`` append in the loop -> the request-body test fails
  - remove the latch                               -> the fires-once test fails
  - TRIPWIRE_READ_LIMIT -> 999                     -> the read-trip test fails
  - drop the transaction-is-None guard             -> the defensive test fails
  - drop the ``log.append`` producer               -> the event test fails
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from fa.inner_loop import EventLog, SessionState
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.registry import ToolCall, ToolRegistry
from fa.inner_loop.routing import (
    TRIPWIRE_CHANGE_LIMIT,
    TRIPWIRE_READ_LIMIT,
    check_scope_tripwire,
)
from tests.fixtures.session_wiring import (
    make_mock_chain,
    mock_success_response,
    mock_tool_call_response,
)

# A sentinel that appears in NO production string. Asserting on a realistic
# hint like "## Task Scope Estimate" is not enough: the tripwire text itself
# names the mode, so a mutant that REPLACES turn_context instead of appending
# to it still produced overlapping words and survived the suite.
S3_HINT_MARKER = "ZZ-PREEXISTING-TURN-CONTEXT-ZZ"


def _tripwire_events(state: SessionState) -> list[Any]:
    """Read scope_tripwire rows, narrowing ``state.log`` the way production does.

    ``SessionState.log`` is ``EventLog | None``; every producer in the loop
    narrows it before use. Mirroring that here keeps the fixture type-honest
    instead of papering over the Optional with an ignore comment.
    """
    log = state.log
    assert log is not None, "these tests always construct a real EventLog"
    return [e for e in log.read_all() if e.kind == "scope_tripwire"]


def _state_with_files(tmp_path: Path, *, reads: int = 0, changes: int = 0) -> SessionState:
    """Build a real SessionState whose transaction has already seen N files.

    Drives the counters through ``record_tool_call`` — the same production path
    the live loop uses — rather than poking ``transaction.read_set`` directly,
    so the test breaks if that wiring is ever removed.
    """
    log = EventLog(tmp_path / "events.jsonl", run_id="tripwire-c1")
    state = SessionState(workspace_root=tmp_path, run_id="tripwire-c1", log=log)
    for i in range(reads):
        state.record_tool_call(ToolCall(name="fs_read_file", params={"path": f"r{i}.py"}, call_id=""))
    for i in range(changes):
        state.record_tool_call(ToolCall(name="fs_write_file", params={"path": f"w{i}.py"}, call_id=""))
    return state


def _drive(
    state: SessionState,
    *,
    scope_mode: str,
    max_turns: int = 1,
    registry: ToolRegistry | None = None,
) -> MagicMock:
    """Run the real loop with a mocked provider; return the chain for payload reads.

    When *max_turns* > 1 the provider is scripted to emit a tool call on every
    turn but the last, because a text-only response ends the loop immediately.
    An earlier revision of this file passed ``max_turns=3`` with a text-only
    mock and silently exercised ONE turn — which made the latch kill-check
    vacuous. Multi-turn tests must prove the loop really iterated, so callers
    assert on ``chain.request.call_count``.
    """
    chain = make_mock_chain(context_limit=100_000, compaction_threshold=None)
    if max_turns > 1:
        tool_turns = [
            mock_tool_call_response(f"call-{i}", "fs_read_file", {"path": f"loop{i}.py"}) for i in range(max_turns - 1)
        ]
        chain.request.side_effect = [*tool_turns, mock_success_response("done")]
    else:
        chain.request.return_value = mock_success_response("done")
    drive_session(
        "tripwire C1",
        provider_chain=chain,
        registry=registry if registry is not None else ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        role="chat",
        max_turns=max_turns,
        turn_context=S3_HINT_MARKER,
        scope_mode=scope_mode,
    )
    return chain


def _sent_payloads(chain: MagicMock) -> list[str]:
    """Flatten every request body the loop actually handed the provider."""
    payloads: list[str] = []
    for call in chain.request.call_args_list:
        payloads.append(repr(call.args) + repr(call.kwargs))
    return payloads


# ── CT10 producer: the observation reaches the request (P35) ───────────────


def test_tripwire_text_reaches_the_composed_request(tmp_path: Path) -> None:
    """C1 (P35): the observation lands in the payload sent to the provider.

    root=drive_session class=C1 claim=CT10 path=P35 oracle=request body
    producer-kill-check=remove the turn_context append inside the turn loop
    This is the test that would have caught routing the text through
    ``state.observations``: that append succeeds and changes nothing observable.
    """
    state = _state_with_files(tmp_path, reads=TRIPWIRE_READ_LIMIT + 1)
    chain = _drive(state, scope_mode="chat_direct")

    body = "\n".join(_sent_payloads(chain))
    assert "invoke_workflow" in body, "tripwire text never reached the provider request"
    assert "Scope check" in body


def test_tripwire_preserves_the_existing_scope_hint(tmp_path: Path) -> None:
    """C1 (RK-H): the tripwire appends to turn_context, never replaces it.

    root=drive_session class=C1 claim=CT10 oracle=request body
    ``turn_context`` already carries the S3 scope hint. Overwriting it would
    silently delete a shipped feature, and no CT10 assertion would notice.
    """
    state = _state_with_files(tmp_path, reads=TRIPWIRE_READ_LIMIT + 1)
    chain = _drive(state, scope_mode="chat_direct")

    body = "\n".join(_sent_payloads(chain))
    assert S3_HINT_MARKER in body, (
        "the pre-existing turn_context was clobbered: the tripwire must APPEND "
        "to it, never replace it (RK-H). The S3 scope hint travels on this same "
        "channel, so replacing it silently deletes a shipped feature."
    )
    assert "Scope check" in body


def test_tripwire_writes_a_durable_event(tmp_path: Path) -> None:
    """C1 (P35): the tripwire is recorded in the EventLog, not just the prompt.

    root=drive_session class=C1 claim=CT10 path=P35 oracle=event kind+fields
    producer-kill-check=remove the log.append("scope_tripwire") call
    Dual-write: the prompt channel is ephemeral, so the durable row is what
    makes the S8 calibration work possible at all.
    """
    state = _state_with_files(tmp_path, reads=TRIPWIRE_READ_LIMIT + 1)
    _drive(state, scope_mode="chat_direct")

    events = _tripwire_events(state)
    assert len(events) == 1
    content = events[0].content
    assert content["files_read"] == TRIPWIRE_READ_LIMIT + 1
    assert content["recommended_mode"] == "chat_direct"


def test_tripwire_fires_at_most_once(tmp_path: Path) -> None:
    """C1 (P36): the latch holds across turns.

    root=drive_session class=C1 claim=CT10 path=P36 oracle=event count
    producer-kill-check=remove the _tripwire_fired latch -> count exceeds 1
    Repeating the same sentence every turn is context the model learns to skip,
    and it would churn the prompt cache on every single call.
    """
    from fa.inner_loop.tools import build_baseline_registry

    state = _state_with_files(tmp_path, reads=TRIPWIRE_READ_LIMIT + 1)
    (tmp_path / "loop0.py").write_text("x = 1\n")
    (tmp_path / "loop1.py").write_text("x = 2\n")
    registry = build_baseline_registry(tmp_path, bash_timeout_seconds=30)

    chain = _drive(state, scope_mode="chat_direct", max_turns=3, registry=registry)

    assert chain.request.call_count >= 2, (
        f"the loop ran {chain.request.call_count} turn(s); a single-turn run cannot prove a latch holds ACROSS turns"
    )
    events = _tripwire_events(state)
    assert len(events) == 1, f"tripwire fired {len(events)} times; the latch is not holding"


# ── Silence paths (P37) ────────────────────────────────────────────────────


def test_run_within_estimate_stays_silent(tmp_path: Path) -> None:
    """C1 (P37): at the limit exactly, nothing fires.

    root=drive_session class=C1 claim=CT10 path=P37 oracle=event count + body
    producer-kill-check=change ``>`` to ``>=`` in check_scope_tripwire
    """
    state = _state_with_files(tmp_path, reads=TRIPWIRE_READ_LIMIT)
    chain = _drive(state, scope_mode="chat_direct")

    assert not _tripwire_events(state)
    assert "Scope check" not in "\n".join(_sent_payloads(chain))


def test_workflow_scoped_run_is_never_tripped(tmp_path: Path) -> None:
    """C1 (P37): a run already estimated workflow_linear is left alone.

    root=drive_session class=C1 claim=CT10 path=P37 oracle=event count
    It was correctly scoped, so the tripwire has nothing to tell it.
    """
    state = _state_with_files(tmp_path, reads=TRIPWIRE_READ_LIMIT + 5)
    _drive(state, scope_mode="workflow_linear")

    assert not _tripwire_events(state)


def test_absent_scope_mode_disables_the_tripwire(tmp_path: Path) -> None:
    """C1 (P37): non-chat runs pass scope_mode="" and are never tripped.

    root=drive_session class=C1 claim=CT10 path=P37 oracle=event count
    """
    state = _state_with_files(tmp_path, reads=TRIPWIRE_READ_LIMIT + 5)
    _drive(state, scope_mode="")

    assert not _tripwire_events(state)


# ── Defensive path (P38) ───────────────────────────────────────────────────


def test_missing_transaction_does_not_raise(tmp_path: Path) -> None:
    """C1 (P38): telemetry must never be the reason a session dies.

    root=drive_session class=C1 claim=CT10 path=P38 oracle=no exception + no event
    producer-kill-check=drop the ``transaction is None`` guard -> AttributeError
    """
    state = _state_with_files(tmp_path, reads=0)
    state.transaction = None

    chain = _drive(state, scope_mode="chat_direct")

    assert chain.request.call_count >= 1, "the run did not proceed"
    assert not _tripwire_events(state)


# ── C0p: the predicate surface ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("reads", "changes", "mode", "fires"),
    [
        (TRIPWIRE_READ_LIMIT + 1, 0, "chat_direct", True),
        (TRIPWIRE_READ_LIMIT, 0, "chat_direct", False),
        (0, TRIPWIRE_CHANGE_LIMIT + 1, "chat_direct", True),
        (0, TRIPWIRE_CHANGE_LIMIT, "chat_direct", False),
        (TRIPWIRE_READ_LIMIT + 1, 0, "chat_planned", True),
        (TRIPWIRE_READ_LIMIT + 1, 0, "workflow_linear", False),
        (TRIPWIRE_READ_LIMIT + 1, 0, "", False),
    ],
)
def test_tripwire_predicate_matrix(reads: int, changes: int, mode: str, fires: bool) -> None:
    """C0p: the full (reads x changes x mode) decision surface.

    root=check_scope_tripwire class=C0p claim=CT10 oracle=return value
    producer-kill-check=widen either threshold -> a boundary row fails
    """
    result = check_scope_tripwire(files_read=reads, files_changed=changes, recommended_mode=mode)
    assert (result is not None) is fires


def test_tripwire_text_names_the_tool_and_the_evidence() -> None:
    """C0: the observation carries counts and the tool name.

    root=check_scope_tripwire class=C0 claim=CT10 oracle=substring
    An observation the model cannot act on is noise. It needs the tool name to
    call, and the numbers that justify calling it.
    """
    text = check_scope_tripwire(files_read=12, files_changed=5, recommended_mode="chat_direct")
    assert text is not None
    assert "invoke_workflow" in text
    assert "12" in text
    assert "5" in text
    assert "chat_direct" in text


def test_tripwire_text_interpolates_no_untrusted_input() -> None:
    """C3: the observation is built only from ints and a closed-set mode string.

    root=check_scope_tripwire class=C3 claim=CT10 oracle=absence of injection
    The text lands in a prompt. If operator- or model-supplied strings could
    reach it, this would be a prompt-injection seam. Only typed values do.
    """
    hostile = "chat_direct"  # closed set; never operator text
    text = check_scope_tripwire(files_read=99, files_changed=99, recommended_mode=hostile)
    assert text is not None
    assert "\n" not in text.strip(), "observation must stay a single block"


def test_counters_come_from_the_production_recorder(tmp_path: Path) -> None:
    """C1: distinct-path counting is the same code the telemetry uses.

    root=SessionState.record_tool_call class=C1 claim=CT10 oracle=set contents
    producer-kill-check=remove add_read/add_write from record_tool_call
    Guards against S7 growing a second counter that could disagree with the
    numbers the run reports in ``fa stats``.
    """
    state = _state_with_files(tmp_path, reads=3, changes=2)
    assert state.transaction is not None
    assert len(state.transaction.read_set) == 3
    assert len(state.transaction.write_set) == 2

    # duplicates must not inflate the count
    state.record_tool_call(ToolCall(name="fs_read_file", params={"path": "r0.py"}, call_id=""))
    assert len(state.transaction.read_set) == 3


def test_tripwire_thresholds_are_documented_constants() -> None:
    """C0: thresholds are named constants, not literals buried in the loop.

    root=fa.inner_loop.routing class=C0 claim=CT10 oracle=type + ordering
    """
    assert isinstance(TRIPWIRE_READ_LIMIT, int)
    assert isinstance(TRIPWIRE_CHANGE_LIMIT, int)
    assert TRIPWIRE_CHANGE_LIMIT < TRIPWIRE_READ_LIMIT, (
        "changing files is stronger evidence of scope growth than reading them, "
        "so its threshold must be the tighter of the two"
    )


def test_thresholds_are_pinned_to_their_measured_values() -> None:
    """C0: the calibrated values themselves, asserted as literals.

    root=fa.inner_loop.routing class=C0 claim=CT10 oracle=exact int
    producer-kill-check=change either constant -> this fails

    Every other test here derives its inputs from the constants
    (``TRIPWIRE_READ_LIMIT + 1``), which is the right way to express a boundary
    but means those tests follow the constant wherever it goes: widening the
    limit to 999 left the whole file green. This test is the anchor that makes
    a threshold change a deliberate, reviewed edit rather than a silent one.

    If you are changing these numbers on purpose, update this test and record
    the new measurement in the routing module docstring.
    """
    assert TRIPWIRE_READ_LIMIT == 10
    assert TRIPWIRE_CHANGE_LIMIT == 3
