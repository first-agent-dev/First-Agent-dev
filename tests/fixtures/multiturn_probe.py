"""Adversarial probe: does the refactored budget block still hold up over time?

The main probe (`budget_effects_probe.py`) drives **one** turn per scenario. That
is enough to prove a single pass through the block, and it is not enough to
prove the thing the refactor actually risks: the locals the driver reassigns
(`conversation_history`, `memory_summary`, `usage`, `verdict`) survive into the
next turn, and the evaluator-compaction pair changes them mid-turn.

So this probe runs multi-turn sessions with a *scripted* estimator (usage per
call, not per session) and prints the observable trace of every turn. Compare
two revisions; identical output means the refactor did not change how a session
evolves — only where the code lives.

Usage:
    python3 -B tests/fixtures/multiturn_probe.py            # JSON
    python3 -B tests/fixtures/multiturn_probe.py --scrub     # timing-free
"""

from __future__ import annotations

import itertools
import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_SCRUB = {"wall_s", "duration_s", "elapsed_s", "ts", "timestamp", "started_at", "finished_at"}


def _scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: ("<timing>" if k in _SCRUB else _scrub(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def _scripted(values: list[int]) -> Any:
    """Estimator that walks ``values`` and then holds the last one."""
    tail = itertools.chain(values, itertools.repeat(values[-1]))

    def estimate(*_args: Any, **_kwargs: Any) -> int:
        return next(tail)

    return estimate


def _seed_history(log: Any, pairs: int) -> None:
    for i in range(1, pairs + 1):
        log.append(
            actor="model",
            kind="model_msg",
            content={
                "text": f"step {i} " * 40,
                "tool_calls": [
                    {"id": f"tc-{i}", "type": "function", "function": {"name": "fs_read_file", "arguments": "{}"}}
                ],
            },
        )
        log.append(
            actor="tool",
            kind="tool_result",
            content={"summary": f"r{i}", "result": {"stdout": "A" * 300}, "ok": True},
            tool_name="fs_read_file",
            tool_call_id=f"tc-{i}",
        )


def run_multiturn(
    estimates: list[int],
    *,
    max_turns: int,
    compaction_threshold: int | None,
    seed_pairs: int,
    run_id: str,
) -> dict[str, Any]:
    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import EventLog, SessionState, coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry, ToolResult, ToolSpec
    from fa.output import EventBus
    from tests.fixtures.session_wiring import make_mock_chain

    events: list[dict[str, Any]] = []

    class _Capture:
        def on_event(self, event: Any) -> None:
            events.append({"type": event.type, "turn": event.turn, "data": event.data})

    tmp = Path(tempfile.mkdtemp())
    log = EventLog(tmp / f"{run_id}.jsonl", run_id=run_id)
    _seed_history(log, seed_pairs)
    state = SessionState(
        workspace_root=tmp,
        run_id=run_id,
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True),
    )
    bus = EventBus()
    bus.add(_Capture())
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="noop_probe",
            description="Registers a call so the loop keeps iterating to its turn limit.",
            input_schema={"type": "object", "properties": {}},
            handler=lambda _params: ToolResult.ok("noop"),
            permission="read",
        )
    )
    chain = make_mock_chain(context_limit=100_000, compaction_threshold=compaction_threshold)
    # Each turn gets a tool call, so the loop keeps iterating until its own
    # turn limit stops it — `max_turns` is the variable under test here, and a
    # bare "done" answer would end the session after turn 1 and measure nothing.
    from tests.fixtures.session_wiring import mock_response_with_tools

    chain.request.return_value = mock_response_with_tools(
        [{"id": "call-1", "type": "function", "function": {"name": "noop_probe", "arguments": "{}"}}]
    )

    with patch("fa.memory.context_budget.estimate_tokens", _scripted(estimates)):
        outcome = coder_loop.drive_session(
            run_id,
            provider_chain=chain,
            registry=registry,
            hooks=HookRegistry(),
            state=state,
            max_turns=max_turns,
            output=bus,
        )

    return {
        "outcome": {
            "exit_code": outcome.exit_code,
            "stop_reason": outcome.stop_reason,
            "turns": outcome.turns,
        },
        "provider_calls": chain.request.call_count,
        "rows": [
            {"kind": r.kind, "content": r.content}
            for r in log.read_all()
            if r.kind
            in {
                "context_budget_warn",
                "compaction_warning",
                "compaction_stage2_start",
                "compaction_stage2_done",
                "compaction_stage2_error",
                "compaction_stage3_start",
                "compaction_stage3_done",
                "compaction_stage3_error",
                "compaction_circuit_breaker",
                "context_budget_hard_stop",
                "run_stopped",
                "session_summary",
            }
        ],
        "events": [
            e for e in events if e["type"] in {"context_warn", "compaction_start", "compaction_end", "session_end"}
        ],
    }


def main(argv: list[str]) -> None:
    cases = {
        # Two turns under pressure: masking in turn 1 must leave turn 2 on the
        # masked history, and the second turn's decision must be its own.
        "two_turns_stage2_each": run_multiturn(
            [85_000, 40_000, 85_000, 40_000],
            max_turns=2,
            compaction_threshold=80_000,
            seed_pairs=7,
            run_id="mt-stage2",
        ),
        # Compaction happens once and the summary has to survive into the next
        # turn: this is the state the refactor routes through a return value.
        "two_turns_stage3_then_ok": run_multiturn(
            [95_000, 95_000, 92_000, 50_000],
            max_turns=2,
            compaction_threshold=80_000,
            seed_pairs=7,
            run_id="mt-stage3",
        ),
        # Pressure in the last turn with nowhere to compact: must stop at once.
        "stop_on_second_turn": run_multiturn(
            [50_000, 95_000],
            max_turns=3,
            compaction_threshold=None,
            seed_pairs=2,
            run_id="mt-stop",
        ),
        # Budget disabled entirely: the block must be a no-op for every turn.
        "many_turns_clean": run_multiturn(
            [10_000, 20_000, 30_000],
            max_turns=3,
            compaction_threshold=None,
            seed_pairs=1,
            run_id="mt-clean",
        ),
    }
    payload = _scrub(cases) if "--scrub" in argv else cases
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main(sys.argv[1:])
