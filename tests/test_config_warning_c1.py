"""C1 config-warning persistence and delayed EventBus wiring tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fa.feature_flags import FeatureFlags, FeatureFlagsLoadResult, FeatureFlagWarning
from fa.inner_loop.state import EventLog, SessionState
from fa.output import EventBus, OutputEvent


class _Capture:
    def __init__(self) -> None:
        self.events: list[OutputEvent] = []

    def on_event(self, event: OutputEvent) -> None:
        self.events.append(event)


def test_legacy_config_warning_is_persisted_and_flushed_after_bus_wiring(tmp_path: Path) -> None:
    """C1 producer/consumer: bootstrap warning survives the no-bus window."""
    warning = FeatureFlagWarning(
        line_no=2,
        key="context_compaction_enabled",
        detail="deprecated and ignored; use models.yaml compaction_threshold presence to enable compaction",
    )
    result = FeatureFlagsLoadResult(flags=FeatureFlags(), warnings=(warning,))
    log = EventLog(tmp_path / "events.jsonl", run_id="config-warning-c1")

    with patch("fa.feature_flags.load_feature_flags_from_path", return_value=result):
        state = SessionState(
            workspace_root=tmp_path,
            run_id="config-warning-c1",
            log=log,
            feature_flags=None,
        )

    # SessionState is constructed before CLI output wiring in production.
    assert state.output_bus is None
    assert len(state._pending_output_events) == 1
    persisted = [event for event in log.read_all() if event.kind == "config_warning"]
    assert len(persisted) == 1
    assert persisted[0].content["key"] == "context_compaction_enabled"

    bus = EventBus()
    capture = _Capture()
    bus.add(capture)
    state.attach_output_bus(bus)

    visible = [event for event in capture.events if event.type == "config_warning"]
    assert len(visible) == 1
    assert visible[0].data["key"] == "context_compaction_enabled"
    assert state._pending_output_events == []
