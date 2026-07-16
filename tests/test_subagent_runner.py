"""
Unit tests for SubagentRunner (Phase 3).
Verifies spawning, spawn limits, filtered history fallback, and worklog aggregation.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest

from fa.feature_flags import FeatureFlags
from fa.inner_loop.context import set_current_session
from fa.inner_loop.state import SessionState
from fa.inner_loop.subagent_envelope import SubagentEnvelope
from fa.inner_loop.subagent_runner import SubagentRunner


@pytest.fixture
def mock_session_state(tmp_path: Path) -> Generator[SessionState]:
    state = SessionState(workspace_root=tmp_path, run_id="test-subagent-run")
    token = set_current_session(state)
    yield state
    from fa.inner_loop.context import reset_current_session

    reset_current_session(token)


def test_subagent_runner_limits_and_spawn(tmp_path: Path, mock_session_state: SessionState) -> None:
    runner = SubagentRunner(session_root=tmp_path)
    limits = runner._get_limits()
    assert limits is not None
    assert limits.max_subagent_spawns_per_session == 3

    assert mock_session_state.get_subagent_spawns() == 0

    runner._check_spawn_limit()
    assert mock_session_state.get_subagent_spawns() == 1

    runner._check_spawn_limit()
    assert mock_session_state.get_subagent_spawns() == 2

    runner._check_spawn_limit()
    assert mock_session_state.get_subagent_spawns() == 3

    with pytest.raises(RuntimeError) as exc_info:
        runner._check_spawn_limit()
    assert "Subagent spawn limit" in str(exc_info.value)


def test_subagent_runner_honors_feature_flag_spawn_limit(tmp_path: Path) -> None:
    state = SessionState(
        workspace_root=tmp_path,
        run_id="test-subagent-run-limit-1",
        feature_flags=FeatureFlags(subagent_spawning_enabled=True, max_subagent_spawns_per_session=1),
    )
    token = set_current_session(state)
    try:
        runner = SubagentRunner(session_root=tmp_path)
        runner._check_spawn_limit()
        assert state.get_subagent_spawns() == 1
        with pytest.raises(RuntimeError):
            runner._check_spawn_limit()
    finally:
        from fa.inner_loop.context import reset_current_session

        reset_current_session(token)


def test_subagent_runner_instance_counter_fallback(tmp_path: Path) -> None:
    # Ensure current session is None
    set_current_session(None)

    runner = SubagentRunner(session_root=tmp_path)
    # Check limit using instance counter
    runner._check_spawn_limit()
    assert runner._instance_spawn_count == 1

    runner._check_spawn_limit()
    assert runner._instance_spawn_count == 2

    runner._check_spawn_limit()
    assert runner._instance_spawn_count == 3

    with pytest.raises(RuntimeError) as exc_info:
        runner._check_spawn_limit()
    assert "Subagent spawn limit" in str(exc_info.value)


def test_build_filtered_history_fallback(tmp_path: Path) -> None:
    runner = SubagentRunner(session_root=tmp_path)
    # Vague task should fall back to default files
    history = runner._build_filtered_history("Read repository and tell what you found")
    assert len(history) >= 1
    assert history[0]["role"] == "user"
    assert "Task:" in history[0]["content"]


def test_append_to_worklog(tmp_path: Path) -> None:
    runner = SubagentRunner(session_root=tmp_path)
    envelope = SubagentEnvelope(
        task_id="task-123",
        type="verifier",
        goal="Test goal",
        exit_code=0,
        summary="Summary of work completed.",
        verification="exit_code=0",
        files_changed=["a.txt", "b.txt"],
        patch_diff="diff",
        risks=["none"],
        open_questions=[],
        token_usage={},
        duration_ms=150,
        next_action="none",
    )

    runner._append_to_worklog(envelope)

    # Check root/session_root worklog exists
    worklog_file = tmp_path / "worklog.md"
    assert worklog_file.exists()
    content = worklog_file.read_text(encoding="utf-8")
    assert "## task-123 verifier" in content
    assert "Goal: Test goal" in content
    assert "Evidence: a.txt, b.txt" in content

    # Check detailed worklog
    detailed_file = tmp_path / ".fa" / "worklog-detailed.md"
    assert detailed_file.exists()
    detailed_content = detailed_file.read_text(encoding="utf-8")
    assert "## task-123 verifier" in detailed_content
    assert "Full envelope:" in detailed_content


def test_run_stateless(tmp_path: Path, mock_session_state: SessionState) -> None:
    runner = SubagentRunner(session_root=tmp_path, timeout=5)
    env_extra = {"TEST_VAR": "hello-subagent"}
    envelope = runner.run_stateless(
        task_id="task-test-run",
        command='test "$TEST_VAR" = hello-subagent',
        role="verifier",
        workdir=tmp_path,
        env_extra=env_extra,
    )

    assert envelope.task_id == "task-test-run"
    assert envelope.type == "verifier"
    assert envelope.exit_code == 0
    assert envelope.summary == "PASS"

    artifact_file = tmp_path / ".fa" / "subagents" / "task-test-run.json"
    assert artifact_file.exists()
    artifact_data = json.loads(artifact_file.read_text(encoding="utf-8"))
    assert artifact_data["task_id"] == "task-test-run"
    assert artifact_data["exit_code"] == 0


def test_run_stateless_researcher_role_preserved(tmp_path: Path, mock_session_state: SessionState) -> None:
    runner = SubagentRunner(session_root=tmp_path, timeout=5)
    envelope = runner.run_stateless(
        task_id="task-research",
        command="printf 'source summary'",
        role="researcher",
        workdir=tmp_path,
    )

    assert envelope.task_id == "task-research"
    assert envelope.type == "researcher"
    assert envelope.exit_code == 0
    assert "source summary" in envelope.summary
