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
