"""Scripted session probe: identical observable behaviour across a refactor.

Run this against two revisions and compare the JSON. It is a probe, not a test,
because its job is to compare two *revisions* — a test can only see the one it
runs on. Timings (``wall_s``) differ by machine load; scrub them before diffing
(``--scrub`` does it for you).

Scenarios cover the budget block's branches:
  1. warn rung, compaction configured   (record_budget_pressure -> warn)
  2. stage-2 rung, compaction disabled  (record_budget_pressure -> stage2)
  3. stage-2 rung, compaction enabled   (compaction_warning + start/end)
  4. stage-3 rung, compaction disabled  (hard stop, NON-compaction return)
  5. circuit breaker                    (hard stop after failed stage-3)
  6. stage-3 still over budget after compaction (hard stop, second return)
  7. no EventBus                        (rows still durable)

Usage:
    python3 -B tests/fixtures/budget_effects_probe.py            # full JSON
    python3 -B tests/fixtures/budget_effects_probe.py --scrub     # timing-free
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_SCRUB_KEYS = {"wall_s", "duration_s", "elapsed_s", "ts", "timestamp", "started_at", "finished_at"}


def _scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: ("<timing>" if k in _SCRUB_KEYS else _scrub(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


class _Capture:
    def __init__(self, sink: list[dict[str, Any]]) -> None:
        self._sink = sink

    def on_event(self, event: Any) -> None:
        self._sink.append({"type": event.type, "turn": event.turn, "max_turns": event.max_turns, "data": event.data})


def run_case(
    tokens: int,
    *,
    threshold: int | None,
    run_id: str,
    breaker: bool = False,
    tokens_after: int | None = None,
    output: bool = True,
) -> dict[str, Any]:
    """Drive one scripted session and snapshot everything observable.

    ``tokens_after`` models a compaction that reclaims some space: the first
    estimate returns ``tokens``, every later one ``tokens_after``. A constant
    fake cannot tell a stale ratio from a fresh one, which is exactly the Q#4
    blind spot.
    """
    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import EventLog, SessionState, coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry
    from fa.memory.context_budget import ContextBudget
    from fa.output import EventBus
    from tests.fixtures.session_wiring import make_mock_chain, mock_success_response

    captured: list[dict[str, Any]] = []
    tmp = Path(tempfile.mkdtemp())
    log = EventLog(tmp / f"{run_id}.jsonl", run_id=run_id)
    state = SessionState(
        workspace_root=tmp,
        run_id=run_id,
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True),
    )
    bus = EventBus() if output else None
    if bus is not None:
        bus.add(_Capture(captured))

    chain = make_mock_chain(context_limit=100_000, compaction_threshold=threshold)
    chain.request.return_value = mock_success_response("done")

    calls = {"n": 0}

    def fake_estimate(*_args: Any, **_kwargs: Any) -> int:
        calls["n"] += 1
        if tokens_after is not None and calls["n"] > 1:
            return tokens_after
        return tokens

    patches = [patch("fa.memory.context_budget.estimate_tokens", side_effect=fake_estimate)]
    if breaker:
        patches.append(patch.object(ContextBudget, "record_compaction_attempt", lambda *_a, **_k: False))
    for p in patches:
        p.start()
    try:
        outcome = coder_loop.drive_session(
            run_id,
            provider_chain=chain,
            registry=ToolRegistry(),
            hooks=HookRegistry(),
            state=state,
            max_turns=1,
            output=bus,
        )
    finally:
        for p in patches:
            p.stop()

    return {
        "outcome": {
            "exit_code": outcome.exit_code,
            "stop_reason": outcome.stop_reason,
            "final_text": outcome.final_text,
        },
        "events": captured,
        "rows": [{"kind": r.kind, "content": r.content} for r in log.read_all()],
    }


def main(argv: list[str]) -> None:
    cases = {
        "warn_rung": run_case(75_000, threshold=100_000, run_id="probe-warn"),
        "stage2_disabled": run_case(85_000, threshold=None, run_id="probe-stage2-off"),
        # compaction_threshold tunes the Stage-2 rung: 80_000 puts a 85_000-token
        # prompt over it while staying under Stage 3 (90_000).
        "stage2_enabled": run_case(85_000, threshold=80_000, run_id="probe-stage2-on"),
        "stage3_disabled": run_case(95_000, threshold=None, run_id="probe-stage3-off"),
        # 3rd failed reclaim in a row: breaker fires on the stage-3 success path.
        "circuit_breaker": run_case(95_000, threshold=80_000, run_id="probe-cb", breaker=True, tokens_after=94_000),
        # Masking and stage-3 both land on 92_000: still over the 90_000 Stage-3
        # rung, so the second stage-3 hard-stop return fires, with the Q#4
        # percentage measured after compaction.
        "stage3_after_compaction": run_case(95_000, threshold=80_000, run_id="probe-stage3-after", tokens_after=92_000),
        "no_bus": run_case(75_000, threshold=100_000, run_id="probe-nobus", output=False),
    }
    payload = _scrub(cases) if "--scrub" in argv else cases
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main(sys.argv[1:])
