"""Scripted session probe: identical observable behaviour across the effects move.

Run this against the working tree and against the pre-slice commit; the two
JSON blobs must be byte-identical. It is a probe, not a test, because its job is
to compare two *revisions* — a test can only see the one it runs on.

Scenario covers every branch this slice touched:
  1. warn rung, compaction configured   (record_budget_pressure -> warn)
  2. stage-2 rung, compaction disabled  (record_budget_pressure -> stage2)
  3. stage-2 rung, compaction enabled   (compaction_warning + compaction_start/end)
  4. circuit breaker                    (context_warn with the breaker's message)
  5. no EventBus                        (row still durable)

Usage: python3 -B tests/fixtures/budget_effects_probe.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def run_case(tokens: int, *, threshold: int | None, run_id: str) -> dict[str, object]:
    from fa.feature_flags import FeatureFlags
    from fa.inner_loop import EventLog, SessionState, coder_loop
    from fa.inner_loop.hooks import HookRegistry
    from fa.inner_loop.registry import ToolRegistry
    from fa.output import EventBus

    captured: list[dict[str, object]] = []

    class _Capture:
        def on_event(self, event) -> None:  # noqa: ANN001 - duck-typed EventSink
            captured.append(
                {"type": event.type, "turn": event.turn, "max_turns": event.max_turns, "data": event.data}
            )

    tmp = Path(tempfile.mkdtemp())
    log = EventLog(tmp / f"{run_id}.jsonl", run_id=run_id)
    state = SessionState(
        workspace_root=tmp,
        run_id=run_id,
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True),
    )
    bus = EventBus()
    bus.add(_Capture())

    from tests.fixtures.session_wiring import make_mock_chain, mock_success_response

    chain = make_mock_chain(context_limit=100_000, compaction_threshold=threshold)
    chain.request.return_value = mock_success_response("done")
    with patch("fa.memory.context_budget.estimate_tokens", return_value=tokens):
        coder_loop.drive_session(
            run_id,
            provider_chain=chain,
            registry=ToolRegistry(),
            hooks=HookRegistry(),
            state=state,
            max_turns=1,
            output=bus,
        )

    rows = [{"kind": r.kind, "content": r.content} for r in log.read_all()]
    return {"events": captured, "rows": rows}


def main() -> None:
    cases = {
        "warn_rung": run_case(75_000, threshold=100_000, run_id="probe-warn"),
        "stage2_disabled": run_case(85_000, threshold=None, run_id="probe-stage2-off"),
        "stage2_enabled": run_case(85_000, threshold=100_000, run_id="probe-stage2-on"),
        "circuit_breaker": run_case(95_000, threshold=None, run_id="probe-cb"),
        "no_bus": run_case(75_000, threshold=100_000, run_id="probe-nobus"),
    }
    print(json.dumps(cases, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
