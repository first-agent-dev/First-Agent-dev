"""Kill-check tests for S9: Extend session_meta with guardrail metrics (G9).

Verifies:
1. EventLog has kind_counts dict, incremented on each append()
2. EventLog has chain_exhaustion_count counter
3. Session-end writes kind_counts, budget_threshold_breaches, chain_exhaustion_events
4. Session doesn't crash when session_db.set_meta fails
5. kind_counts is thread-safe (under existing _lock)
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock

from fa.inner_loop import EventLog, SessionState, ToolRegistry
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from tests.fixtures.session_wiring import (
    make_test_chain_config,
    mock_success_response,
)

# ── Kill-check 1: kind_counts incremental counting ───────────────────


def test_kind_counts_incremented_on_append() -> None:
    """EventLog.kind_counts must be incremented on each append() call."""
    with tempfile.TemporaryDirectory() as tmp:
        log = EventLog(Path(tmp) / "test.jsonl", run_id="test-kg9")

        log.append(actor="runtime", kind="run_started", content={})
        log.append(actor="runtime", kind="user_msg", content={})
        log.append(actor="runtime", kind="run_started", content={})  # duplicate

        assert log.kind_counts == {"run_started": 2, "user_msg": 1}


# ── Kill-check 2: chain_exhaustion_count exists ──────────────────────


def test_chain_exhaustion_count_exists() -> None:
    """EventLog must have chain_exhaustion_count initialized to 0."""
    with tempfile.TemporaryDirectory() as tmp:
        log = EventLog(Path(tmp) / "test.jsonl", run_id="test-kg9")
        assert hasattr(log, "chain_exhaustion_count")
        assert log.chain_exhaustion_count == 0


# ── Kill-check 3: Session-end metrics write ─────────────────────────


def test_session_end_writes_guardrail_metrics(tmp_path: Path) -> None:
    """When a session ends normally, kind_counts and budget_threshold_breaches
    must be written to session_db.set_meta()."""
    log = EventLog(tmp_path / "events.jsonl", run_id="test-metrics")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="test-metrics",
        log=log,
    )

    mock_chain = MagicMock()
    mock_chain.config = make_test_chain_config(context_limit=150000)
    mock_chain.request.return_value = mock_success_response("metrics test")

    outcome = drive_session(
        "test task",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
    )

    assert outcome.exit_code == 0

    # Verify session_db has the metrics
    if state.session_db is not None:
        kind_counts_val = state.session_db.get_meta("kind_counts")
        budget_breaches_val = state.session_db.get_meta("budget_threshold_breaches")
        chain_exhaustion_val = state.session_db.get_meta("chain_exhaustion_events")

        assert kind_counts_val is not None, "kind_counts not found in session_meta"
        assert isinstance(kind_counts_val, dict), f"kind_counts should be dict, got {type(kind_counts_val)}"
        assert "run_started" in kind_counts_val, f"Expected run_started in kind_counts, got {kind_counts_val}"

        assert budget_breaches_val is not None, "budget_threshold_breaches not found in session_meta"
        assert isinstance(budget_breaches_val, int), (
            f"budget_threshold_breaches should be int, got {type(budget_breaches_val)}"
        )

        assert chain_exhaustion_val is not None, "chain_exhaustion_events not found in session_meta"
        assert isinstance(chain_exhaustion_val, int), (
            f"chain_exhaustion_events should be int, got {type(chain_exhaustion_val)}"
        )


# ── Kill-check 4: Session doesn't crash when session_db.set_meta fails ─


def test_session_survives_db_unavailable(tmp_path: Path) -> None:
    """If session_db.set_meta raises, the session must still complete
    without crashing. Metrics are best-effort — never crash at session end."""
    log = EventLog(tmp_path / "events.jsonl", run_id="test-db-fail")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="test-db-fail",
        log=log,
    )

    # Make session_db.set_meta raise
    if state.session_db is not None:
        original_set_meta = state.session_db.set_meta

        def failing_set_meta(key: str, value: object, ts: str) -> None:
            if key == "kind_counts":
                raise RuntimeError("simulated DB failure")
            original_set_meta(key, value, ts)

        state.session_db.set_meta = failing_set_meta  # type: ignore[assignment]

    mock_chain = MagicMock()
    mock_chain.config = make_test_chain_config(context_limit=150000)
    mock_chain.request.return_value = mock_success_response("db fail test")

    # Must NOT raise
    outcome = drive_session(
        "test task",
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
    )

    assert outcome.exit_code == 0, "Session should complete successfully even if metrics write fails"


# ── Kill-check 5: kind_counts under lock (concurrent access) ─────────


def test_kind_counts_thread_safe() -> None:
    """kind_counts must be thread-safe — concurrent append() calls should
    not lose counts."""
    with tempfile.TemporaryDirectory() as tmp:
        log = EventLog(Path(tmp) / "test.jsonl", run_id="test-concurrent")

        n_threads = 10
        n_appends_per_thread = 50
        barrier = threading.Barrier(n_threads)

        def append_events() -> None:
            barrier.wait()
            for _ in range(n_appends_per_thread):
                log.append(actor="thread", kind="usage", content={})

        threads = [threading.Thread(target=append_events) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected_count = n_threads * n_appends_per_thread
        assert log.kind_counts.get("usage", 0) == expected_count, (
            f"Expected usage count {expected_count}, got {log.kind_counts.get('usage', 0)}"
        )
