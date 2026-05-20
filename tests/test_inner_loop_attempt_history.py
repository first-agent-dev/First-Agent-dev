"""AttemptHistory (Wave-2 R-6) writer behaviour + observer integration.

These tests assert real disk state, sliding-window pruning, cap
enforcement, and the prompt-facing ``attempt_count`` lookup the
coder-recovery reader will use.
"""

from __future__ import annotations

import json
from pathlib import Path

from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.hooks import (
    AttemptHistoryObserver,
    FailureClassifierObserver,
    HookPayload,
    HookRegistry,
    LifecyclePoint,
)
from fa.inner_loop.recovery import (
    AttemptHistory,
    AttemptHistoryEntry,
    canonical_params_hash,
)
from fa.inner_loop.registry import ToolError, ToolResult
from fa.inner_loop.tools import build_baseline_registry


def _entry(
    *,
    ts: float,
    tool_name: str = "fs.read_file",
    params_hash: str = "deadbeef",
    error_code: str = "read_failed",
    error_message: str = "ENOENT",
    recovery_action: str = "retry",
    recovery_category: str = "unexpected_environments",
) -> AttemptHistoryEntry:
    return AttemptHistoryEntry(
        ts=ts,
        tool_name=tool_name,
        params_hash=params_hash,
        error_code=error_code,
        error_message=error_message,
        recovery_action=recovery_action,
        recovery_category=recovery_category,
    )


def test_canonical_params_hash_is_stable_and_order_insensitive() -> None:
    """Same payload → same hash. Key order in dict does not matter."""

    a = canonical_params_hash("fs.read_file", {"path": "x", "n": 1})
    b = canonical_params_hash("fs.read_file", {"n": 1, "path": "x"})
    c = canonical_params_hash("fs.read_file", {"path": "y", "n": 1})
    assert a == b, "params hash must be order-independent"
    assert a != c, "different params must produce different hashes"


def test_attempt_history_append_writes_disk_atomically(tmp_path: Path) -> None:
    history_path = tmp_path / "attempt_history.json"
    history = AttemptHistory(path=history_path, max_entries=5, max_age_seconds=60)
    history.append(
        tool_name="fs.read_file",
        params_hash="abc",
        error_code="read_failed",
        error_message="missing",
        recovery_action="retry",
        recovery_category="unexpected_environments",
        ts=100.0,
    )
    # File exists and parses as a list with one entry.
    raw = json.loads(history_path.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) == 1
    assert raw[0]["tool_name"] == "fs.read_file"
    assert raw[0]["ts"] == 100.0
    # Round-trip via :meth:`open` recovers the entry.
    reloaded = AttemptHistory.open(history_path, max_entries=5, max_age_seconds=60)
    assert len(reloaded.entries) == 1
    assert reloaded.entries[0].params_hash == "abc"


def test_attempt_history_prunes_by_max_age(tmp_path: Path) -> None:
    """Entries older than ``max_age_seconds`` are dropped on next append."""

    history_path = tmp_path / "attempt_history.json"
    history = AttemptHistory(path=history_path, max_entries=10, max_age_seconds=60)
    # Two old entries (ts=0) + one fresh entry (ts=now). Old ones
    # should be pruned after the fresh append.
    history.entries.extend(
        [
            _entry(ts=0.0, params_hash="old1"),
            _entry(ts=0.0, params_hash="old2"),
        ]
    )
    history.append(
        tool_name="fs.read_file",
        params_hash="new",
        error_code="read_failed",
        error_message="x",
        recovery_action="retry",
        recovery_category="unexpected_environments",
        ts=1000.0,
    )
    raw = json.loads(history_path.read_text(encoding="utf-8"))
    hashes = [row["params_hash"] for row in raw]
    assert hashes == ["new"], "old entries beyond max_age must be pruned"


def test_attempt_history_enforces_cap(tmp_path: Path) -> None:
    """When cap is hit, the oldest entry is dropped before append."""

    history_path = tmp_path / "attempt_history.json"
    history = AttemptHistory(path=history_path, max_entries=3, max_age_seconds=10_000)
    base_ts = 1000.0
    for i in range(5):
        history.append(
            tool_name="fs.read_file",
            params_hash=f"h{i}",
            error_code="read_failed",
            error_message="x",
            recovery_action="retry",
            recovery_category="unexpected_environments",
            ts=base_ts + i,
        )
    raw = json.loads(history_path.read_text(encoding="utf-8"))
    hashes = [row["params_hash"] for row in raw]
    # Cap=3 keeps the most-recent 3 entries.
    assert hashes == ["h2", "h3", "h4"]


def test_attempt_history_open_tolerates_missing_file(tmp_path: Path) -> None:
    history = AttemptHistory.open(tmp_path / "missing.json")
    assert history.entries == []


def test_attempt_history_open_tolerates_corrupt_json(tmp_path: Path) -> None:
    history_path = tmp_path / "corrupt.json"
    history_path.write_text("{not valid json", encoding="utf-8")
    history = AttemptHistory.open(history_path)
    assert history.entries == []


def test_attempt_count_lookup_drives_prompt_thresholds(tmp_path: Path) -> None:
    """The reader-prompt API: count attempts by (tool, params_hash)."""

    history = AttemptHistory(path=tmp_path / "h.json", max_entries=10, max_age_seconds=10_000)
    # Three failed attempts of the SAME call.
    for i in range(3):
        history.append(
            tool_name="fs.write_file",
            params_hash="same",
            error_code="write_failed",
            error_message="EACCES",
            recovery_action="retry",
            recovery_category="unexpected_environments",
            ts=100.0 + i,
        )
    # One unrelated entry must not count.
    history.append(
        tool_name="fs.write_file",
        params_hash="other",
        error_code="write_failed",
        error_message="",
        recovery_action="retry",
        recovery_category="unexpected_environments",
        ts=200.0,
    )
    assert history.attempt_count(tool_name="fs.write_file", params_hash="same") == 3
    assert history.attempt_count(tool_name="fs.write_file", params_hash="missing") == 0


def test_attempt_history_observer_skips_successful_results(tmp_path: Path) -> None:
    history = AttemptHistory(path=tmp_path / "h.json")
    observer = AttemptHistoryObserver(history)
    observer.observe(
        LifecyclePoint.AFTER_TOOL_EXEC,
        HookPayload(
            tool_call=ToolCall(name="fs.read_file", params={"path": "x"}, call_id="tc"),
            tool_result=ToolResult.ok("ok"),
        ),
    )
    assert history.entries == [], "successful results must not be recorded"


def test_attempt_history_observer_records_failed_result(tmp_path: Path) -> None:
    history = AttemptHistory(path=tmp_path / "h.json", max_entries=10, max_age_seconds=10_000)
    observer = AttemptHistoryObserver(history, time_source=lambda: 500.0)
    failed = ToolResult(
        summary="boom",
        error=ToolError(code="invalid_params", message="missing path", retryable=True),
    )
    observer.observe(
        LifecyclePoint.AFTER_TOOL_EXEC,
        HookPayload(
            tool_call=ToolCall(name="fs.read_file", params={"path": "x.txt"}, call_id="tc-1"),
            tool_result=failed,
        ),
    )
    assert len(history.entries) == 1
    entry = history.entries[0]
    assert entry.tool_name == "fs.read_file"
    assert entry.error_code == "invalid_params"
    assert entry.recovery_action == "retry"
    assert entry.recovery_category == "invalid_arguments"
    assert entry.ts == 500.0


def test_failure_classifier_observer_emits_recovery_action_event(tmp_path: Path) -> None:
    """A failed call → exactly one ``recovery_action`` row in events.jsonl."""

    log_path = tmp_path / "events.jsonl"
    log = EventLog(log_path, run_id="t-rec")
    observer = FailureClassifierObserver(event_log=log)
    failed = ToolResult(
        summary="oops",
        error=ToolError(code="hook_deny", message="sandbox", retryable=False),
    )
    observer.observe(
        LifecyclePoint.AFTER_TOOL_EXEC,
        HookPayload(
            tool_call=ToolCall(name="fs.run_bash", params={"command": "rm -rf /"}, call_id="tc-1"),
            tool_result=failed,
        ),
    )
    events = log.read_all()
    recovery_rows = [e for e in events if e.kind == "recovery_action"]
    assert len(recovery_rows) == 1
    row = recovery_rows[0]
    assert row.content["category"] == "policy_denied"
    assert row.content["action"] == "escalate"
    assert row.content["target"] == "fs.run_bash"
    assert row.content["error_code"] == "hook_deny"
    assert row.tool_call_id == "tc-1"
    # In-memory trail mirrors the event log.
    assert len(observer.recent_actions) == 1
    assert observer.recent_actions[0].kind.value == "escalate"


def test_observers_in_run_session_record_failed_write(tmp_path: Path) -> None:
    """End-to-end: AttemptHistoryObserver + FailureClassifierObserver fire
    on a real failing tool call routed through run_session."""

    log = EventLog(tmp_path / "events.jsonl", run_id="t-int")
    history = AttemptHistory(
        path=tmp_path / "attempt_history.json", max_entries=10, max_age_seconds=10_000
    )
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()
    hooks.register(FailureClassifierObserver(event_log=log))
    hooks.register(AttemptHistoryObserver(history, time_source=lambda: 1.0))
    state = SessionState(workspace_root=tmp_path, run_id="t-int", log=log)

    # Missing required field ``content`` → invalid_params, retryable.
    results = run_session(
        (ToolCall(name="fs.write_file", params={"path": "x.txt"}, call_id="tc-1"),),
        registry=registry,
        hooks=hooks,
        state=state,
    )
    assert len(results) == 1
    assert results[0].error is not None
    assert results[0].error.code == "invalid_params"

    # AttemptHistory got one entry tied to the failed call.
    assert len(history.entries) == 1
    assert history.entries[0].error_code == "invalid_params"
    assert history.entries[0].recovery_category == "invalid_arguments"
    # events.jsonl recorded one recovery_action row alongside the
    # normal tool_call / tool_result trace.
    events = log.read_all()
    recovery_rows = [e for e in events if e.kind == "recovery_action"]
    assert len(recovery_rows) == 1
    assert recovery_rows[0].content["category"] == "invalid_arguments"
