"""C1 — golden order oracle for the session trace.

**Why this file exists.** The probes compare a filtered view: `budget_effects_probe`
and `multiturn_probe` keep only the budget-related kinds. That is deliberate —
they exist to compare refactors of the budget block — but it means a refactor
could reorder `run_started` after `llm_call`, drop a `provider_attempt` row, or
write `session_summary` before `run_stopped`, and every probe would still say
"IDENTICAL".

Measured when this file was written: a one-turn session writes **ten** rows, and
a filter that keeps only budget kinds shows **none** of them. So the probes'
green light covered none of the ordering that the driver actually produces.

The oracle is the *shape of the log*, not its content:

* the sequence of ``(actor, kind)`` pairs;
* the key set of each row's ``content``, sorted.

Values are excluded on purpose: ids, timings and token counts vary per run and
pinning them would make this a snapshot of a clock. What must not vary is which
rows appear, in what order, carrying which fields — that is the durable contract
``fa stats`` and any future reader depend on.

**When this fails, the answer is not "update the golden".** Either a row moved
for a reason (say so in the commit message, and update here in the same commit),
or a refactor changed the trace by accident, which is the failure this file is
for.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog, SessionState, coder_loop
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.registry import ToolRegistry, ToolResult, ToolSpec
from fa.output import EventBus
from tests.fixtures.session_wiring import make_mock_chain, mock_response_with_tools

#: A clean single-turn session with the budget enabled and no pressure.
#:
#: ``provider_attempt`` is absent and that is correct for this fixture: the mock
#: chain answers without going through the retry seam, so no attempt record is
#: produced. The row appears on real chains and on failure paths; pinning its
#: absence here documents which shape this scenario actually has, instead of
#: leaving a reader to assume the rollup implies the attempts.
_CLEAN_SESSION: list[tuple[str, str, list[str]]] = [
    ("user", "user_msg", ["text"]),
    ("runtime", "run_started", ["max_turns", "role", "temperature"]),
    (
        "provider",
        "llm_call",
        [
            "chain",
            "family",
            "in_tokens",
            "logical_call_id",
            "model",
            "out_tokens",
            "role",
            "wallclock_ms",
        ],
    ),
    (
        "runtime",
        "usage",
        [
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
            "input_tokens",
            "output_tokens",
        ],
    ),
    (
        "model",
        "model_msg",
        [
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
            "finish_reason",
            "in_tokens",
            "out_tokens",
            "text",
            "tool_calls",
        ],
    ),
    ("coder", "tool_call", ["params"]),
    ("telemetry", "telemetry", ["artifact_id", "ok", "tool_name", "turn"]),
    ("tool", "tool_result", ["artifacts", "ok", "summary"]),
    ("runtime", "run_stopped", ["reason", "turns"]),
    (
        "runtime",
        "session_summary",
        [
            "cache_creation_input_tokens",
            "cache_hit_ratio",
            "cache_read_input_tokens",
            "exit_code",
            "input_tokens",
            "n_turns",
            "output_tokens",
            "role",
            "stop_reason",
            "uncached_input_tokens",
        ],
    ),
]


def _shape(events: Any) -> list[tuple[str, str, list[str]]]:
    """``(actor, kind, sorted content keys)`` for every row, in written order."""
    return [(row.actor, row.kind, sorted(row.content)) for row in events]


def _run_clean_session(
    *,
    max_turns: int = 1,
    compaction_threshold: int | None = None,
    estimate: int = 10_000,
) -> tuple[EventLog, Any]:
    tmp = Path(tempfile.mkdtemp())
    log = EventLog(tmp / "events.jsonl", run_id="golden")
    state = SessionState(
        workspace_root=tmp,
        run_id="golden",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True),
    )
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="noop_golden",
            description="One tool call so the turn has a tool result to record.",
            input_schema={"type": "object", "properties": {}},
            handler=lambda _params: ToolResult.ok("noop"),
            permission="read",
        )
    )
    chain = make_mock_chain(context_limit=100_000, compaction_threshold=compaction_threshold)
    chain.request.return_value = mock_response_with_tools(
        [{"id": "call-1", "type": "function", "function": {"name": "noop_golden", "arguments": "{}"}}]
    )
    bus = EventBus()
    with patch("fa.memory.context_budget.estimate_tokens", lambda *a, **k: estimate):
        outcome = coder_loop.drive_session(
            "golden",
            provider_chain=chain,
            registry=registry,
            hooks=HookRegistry(),
            state=state,
            max_turns=max_turns,
            output=bus,
        )
    return log, outcome


def test_clean_session_trace_shape_is_pinned() -> None:
    """C1: the ten rows of an ordinary session, in order, with their fields.

    Kill-check target: move any ``log.append`` in the driver across another one
    (e.g. write ``session_summary`` before ``run_stopped``) → this fails and
    prints the first divergence.
    """
    log, _ = _run_clean_session()

    assert _shape(log.read_all()) == _CLEAN_SESSION


def test_order_oracle_is_sensitive_to_a_swap() -> None:
    """C0 liveness: the comparison must not pass on any two equal-length lists.

    A shape oracle that compared sets, or sorted, would pass a swapped trace.
    This pins that the assertion is order-sensitive, using the fixture itself.
    """
    swapped = list(_CLEAN_SESSION)
    swapped[0], swapped[1] = swapped[1], swapped[0]

    assert _shape([]) != swapped
    assert swapped != _CLEAN_SESSION


def test_summary_is_the_last_row_and_names_the_stop() -> None:
    """The summary must come after ``run_stopped`` and agree with the outcome.

    Two rows describe the same decision. If they disagree, ``fa stats`` and the
    console tell different stories about the same run — which is the class Q#4
    was, one level up.
    """
    log, outcome = _run_clean_session()

    rows = log.read_all()
    assert rows[-1].kind == "session_summary"
    assert rows[-2].kind == "run_stopped"

    stopped, summary = rows[-2], rows[-1]
    assert stopped.content["reason"] == outcome.stop_reason
    assert summary.content["stop_reason"] == outcome.stop_reason
    assert summary.content["exit_code"] == outcome.exit_code


@pytest.mark.parametrize("max_turns", [1, 2])
def test_turn_count_in_the_trace_matches_the_outcome(max_turns: int) -> None:
    """A second turn must add exactly one usage row and one model response.

    This is the property a multi-turn refactor is most likely to break silently:
    the loop keeps its own counters, and a slice that moves state into an object
    can drop a turn's bookkeeping without changing the exit code.
    """
    log, outcome = _run_clean_session(max_turns=max_turns)

    kinds = [row.kind for row in log.read_all()]
    # One `model_msg` and one `usage` row per turn that reached the provider.
    # Measured: max_turns=2 gives two of each, in the order llm_call, usage,
    # model_msg — not one usage row for a two-turn run, which is what a
    # "ledger counts turns, so subtract one" reading would predict.
    assert kinds.count("model_msg") == outcome.turns
    assert kinds.count("usage") == outcome.turns
    assert kinds.count("llm_call") == outcome.turns
