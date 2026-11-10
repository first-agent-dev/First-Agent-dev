"""C1 compaction enablement and dual-observability tests.

Root: ``drive_session``.
Provider/LLM I/O is mocked; EventLog, session DB, EventBus, and configuration
objects are real. The tests target the producer ``output.emit`` call and the
EventLog producer, not only a renderer or parser.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog, SessionState
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.registry import ToolRegistry
from fa.output import EventBus, OutputEvent
from fa.providers import ChainConfig
from fa.providers.errors import ConfigurationError
from tests.fixtures.session_wiring import make_mock_chain, mock_success_response


class _Capture:
    def __init__(self) -> None:
        self.events: list[OutputEvent] = []

    def on_event(self, event: OutputEvent) -> None:
        self.events.append(event)


def _run_budget_path(
    tmp_path: Path,
    *,
    threshold: int | None,
) -> tuple[SessionState, _Capture, MagicMock]:
    log = EventLog(tmp_path / "events.jsonl", run_id="compaction-c1")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="compaction-c1",
        log=log,
        feature_flags=FeatureFlags(context_budget_enabled=True),
    )
    bus = EventBus()
    capture = _Capture()
    bus.add(capture)
    chain = make_mock_chain(context_limit=100_000, compaction_threshold=threshold)
    chain.request.return_value = mock_success_response("done")

    with patch("fa.memory.context_budget.estimate_tokens", return_value=85_000):
        drive_session(
            "compaction C1",
            provider_chain=chain,
            registry=ToolRegistry(),
            hooks=HookRegistry(),
            state=state,
            max_turns=1,
            output=bus,
        )
    return state, capture, chain


def test_threshold_absent_emits_disabled_warning_and_no_compaction_start(tmp_path: Path) -> None:
    """C1 row A: absent threshold disables compaction and is observable.

    Kill-checks:
    - removing the EventLog compaction_warning producer removes the DB record;
    - removing the OutputEvent producer removes the EventBus record.
    """
    state, capture, chain = _run_budget_path(tmp_path, threshold=None)

    warnings = [event for event in capture.events if event.type == "compaction_warning"]
    assert len(warnings) == 1
    assert warnings[0].data["compaction_enabled"] is False
    assert not any(event.type == "compaction_start" for event in capture.events)
    assert chain.request.call_count == 1

    log = state.require_log()
    persisted = [event for event in log.read_all() if event.kind == "compaction_warning"]
    assert len(persisted) == 1
    assert persisted[0].content["compaction_enabled"] is False
    assert log.session_db is not None
    assert len(log.session_db.read_event_rows()) >= 1


def test_threshold_present_emits_enabled_warning_and_compaction_start(tmp_path: Path) -> None:
    """C1 row B: threshold presence enables the compaction path.

    The deterministic Stage 2 path is used here; the later LLM compactor is
    covered separately with a mocked provider in the existing edge suite.
    """
    state, capture, _chain = _run_budget_path(tmp_path, threshold=80_000)

    warnings = [event for event in capture.events if event.type == "compaction_warning"]
    assert len(warnings) == 1
    assert warnings[0].data["compaction_enabled"] is True
    assert warnings[0].data["threshold"] == 80_000
    assert any(event.type == "compaction_start" for event in capture.events)

    log = state.require_log()
    persisted = [event for event in log.read_all() if event.kind == "compaction_warning"]
    assert len(persisted) == 1
    assert persisted[0].content["compaction_enabled"] is True
    assert persisted[0].content["threshold"] == 80_000


@pytest.mark.parametrize("threshold", [0, -1, 100_001])
def test_invalid_threshold_fails_closed(threshold: int) -> None:
    """C2 config contract: invalid thresholds never silently enable compaction."""
    config = ChainConfig(
        role="coder",
        name="test-model",
        family="openai",
        chain=(),
        context_limit=100_000,
        compaction_threshold=threshold,
    )
    with pytest.raises(ConfigurationError):
        config.validate({}, require_api_keys=False)


@pytest.mark.parametrize("stage", [2, 3])
def test_compaction_recomposes_actual_provider_payload(tmp_path: Path, stage: int) -> None:
    """C1: stage-specific reconstruction reaches the real provider request."""
    log = EventLog(tmp_path / "events.jsonl", run_id=f"recompose-{stage}")
    state = SessionState(workspace_root=tmp_path, run_id=f"recompose-{stage}", log=log)
    for i in range(7):
        call = {"id": f"tc-{i}", "type": "function", "function": {"name": "fs_read_file", "arguments": "{}"}}
        text = "old-assistant-marker " * 18000 if stage == 3 and i < 2 else f"step-{i}"
        stdout = "old-tool-marker " * 22000 if stage == 2 and i == 0 else "small-output"
        log.append(actor="model", kind="model_msg", content={"text": text, "tool_calls": [call]})
        log.append(
            actor="tool",
            kind="tool_result",
            content={"summary": "tool output", "result": {"stdout": stdout}, "ok": True},
            tool_name="fs_read_file",
            tool_call_id=f"tc-{i}",
        )
    chain = make_mock_chain(context_limit=100_000, compaction_threshold=80_000, family="anthropic")
    chain.request.return_value = mock_success_response("done")
    compactor = make_mock_chain(context_limit=100_000)
    compactor.request.return_value = mock_success_response(
        "## PREVIOUSLY\ncompact-summary-marker\n\n## PARKED\nNone\n\n## CURRENT\nDoing task\n\n## NEXT ACTION\nProceed"
    )
    result = drive_session(
        "recompose task",
        provider_chain=chain,
        compactor_chain=compactor,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
    )
    assert result.exit_code == 0 and chain.request.call_count == 1
    payload = repr(chain.request.call_args.args[0].messages)
    rows = log.read_all()
    assert any(e.kind == "compaction_stage2_done" for e in rows)
    if stage == 2:
        assert compactor.request.call_count == 0
        assert "old-tool-marker " * 100 not in payload
    else:
        assert compactor.request.call_count == 1
        assert any(e.kind == "compaction_stage3_done" for e in rows)
        assert "compact-summary-marker" in payload
        assert "old-assistant-marker " * 100 not in payload


def test_hard_stop_after_stage3_reports_post_compaction_ratio(tmp_path: Path) -> None:
    """C1 (Q#4): the percentage shown describes the state the decision used.

    Measured before the fix, on this exact path: stage-2 masking brought usage
    to 99% and stage-3 compaction brought it to 92%, but the hard-stop that
    fired afterwards printed ``pct=99`` and ``session_end`` reported
    ``context_used_pct=99.0`` — the number from *before* the compaction, while
    ``budget.check()`` had decided on 92%. The run told the operator a different
    figure than the one it acted on.

    Why the numbers differ per estimate call: ``estimate_tokens`` is the only
    thing that knows how big the payload actually is, so the fake walks the real
    three-stage ladder (initial -> after masking -> after summarisation). A
    single return value cannot expose this defect: masking and summarisation
    both reassign ``usage``, so a constant fake makes the stale and the fresh
    ratio identical and the test passes either way.

    Kill-check target: drop ``last_budget_ratio = decision.get("ratio", 0.0)``
    after the stage-3 ``budget.check(usage)`` — both assertions below read 99.
    """
    log = EventLog(tmp_path / "events.jsonl", run_id="q4-ratio")
    state = SessionState(workspace_root=tmp_path, run_id="q4-ratio", log=log)
    for i in range(7):
        call = {"id": f"tc-{i}", "type": "function", "function": {"name": "fs_read_file", "arguments": "{}"}}
        text = "old-assistant-marker " * 18000 if i < 2 else f"step-{i}"
        log.append(actor="model", kind="model_msg", content={"text": text, "tool_calls": [call]})
        log.append(
            actor="tool",
            kind="tool_result",
            content={"summary": "tool output", "result": {"stdout": "small-output"}, "ok": True},
            tool_name="fs_read_file",
            tool_call_id=f"tc-{i}",
        )

    chain = make_mock_chain(context_limit=100_000, compaction_threshold=80_000, family="anthropic")
    chain.request.return_value = mock_success_response("done")
    compactor = make_mock_chain(context_limit=100_000)
    compactor.request.return_value = mock_success_response(
        "## PREVIOUSLY\nc\n\n## PARKED\nNone\n\n## CURRENT\nx\n\n## NEXT ACTION\ny"
    )

    bus = EventBus()
    capture = _Capture()
    bus.add(capture)

    # initial 95% -> stage3; after masking 99% -> still stage3; after
    # summarisation 92% -> still >= the 90% stage-3 threshold, so the hard-stop
    # fires on the post-compaction figure. Each value differs from the others on
    # purpose: equal values would hide the defect.
    estimate_values = iter([95_000, 99_000, 92_000, 92_000, 92_000])

    with patch("fa.memory.context_budget.estimate_tokens", side_effect=lambda *a, **k: next(estimate_values, 92_000)):
        result = drive_session(
            "q4 ratio",
            provider_chain=chain,
            compactor_chain=compactor,
            registry=ToolRegistry(),
            hooks=HookRegistry(),
            state=state,
            max_turns=1,
            output=bus,
        )

    assert result.exit_code == 1 and result.stop_reason == "context_budget_hard_stop"
    assert compactor.request.call_count == 1, "precondition: stage-3 compaction really ran"

    warns = [e for e in capture.events if e.type == "context_warn" and e.data.get("action") == "stage3"]
    assert warns, f"no stage3 context_warn; types={[e.type for e in capture.events]}"
    assert warns[-1].data["pct"] == 92, (
        f"hard-stop printed pct={warns[-1].data['pct']} — that is the pre-compaction figure (99), "
        "not the one the decision was taken on (92)"
    )

    ends = [e for e in capture.events if e.type == "session_end"]
    assert ends and ends[-1].data["context_used_pct"] == 92.0, (
        f"session_end reported context_used_pct={ends[-1].data.get('context_used_pct') if ends else None}, "
        "expected the post-compaction ratio"
    )
