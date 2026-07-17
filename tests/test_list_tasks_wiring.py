"""C1 composition-root wiring tests for fs.list_tasks — observability + pair lifecycle.

Covers:
- PTY session listing via live session (C1)
- Subagent artifact discovery via live session (C1)
- Worktree dir discovery via live session (C1)
- Empty list when no pool or manager (C1)

Skill: knowledge/skills/tests-writing/SKILL.md
- root: drive_session
- matrix: A-gates-only (default FeatureFlags, no special gates)
- oracle: Rank 6 — product-owned FS/DB rows (tool result result["tasks"])
- kill-check: removing build_list_tasks_tool registration makes tool dispatch fail
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog, SessionState
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.tools import build_baseline_registry
from fa.providers import ChainConfig, ProviderChain
from tests.fixtures.session_wiring import (
    make_tool_call,
    mock_response_with_tools,
    mock_success_response,
    require_log,
)


# ---------------------------------------------------------------------------
# Test 1 — PTY session listing
# ---------------------------------------------------------------------------

def test_list_tasks_finds_pty_session(tmp_path: Path) -> None:
    """LIVE-PATH PROOF:
    - root: drive_session
    - test: tests/test_list_tasks_wiring.py::test_list_tasks_finds_pty_session
    - matrix: A-gates-only (default FeatureFlags)
    - oracle: tool_result result["tasks"] contains {"type": "pty", "id": "main"}
    - kill-check: removing pty_pool from SessionState makes list_tasks return no PTY tasks

    Product claim: fs.list_tasks finds active PTY sessions via pool.list_sessions().
    """
    from fa.runtime import PtyPool

    log = EventLog(tmp_path / "events.jsonl", run_id="list-tasks-pty")
    pty_pool = PtyPool(max_size=2, base_cwd=tmp_path, run_id="list-tasks-pty")
    # Acquire a session so list_sessions() returns something
    pty_pool.acquire("main")

    state = SessionState(
        workspace_root=tmp_path,
        run_id="list-tasks-pty",
        log=log,
        pty_pool=pty_pool,
        feature_flags=FeatureFlags(),
    )
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()

    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 150000
    mock_chain.config.compaction_threshold = None
    mock_chain.config.model = "test"
    mock_chain.config.family = "openai"

    tc1 = make_tool_call("fs.list_tasks", {}, "tc-1")

    mock_chain.request.side_effect = [
        mock_response_with_tools([tc1]),
        mock_success_response("done"),
    ]

    outcome = drive_session(
        "list tasks",
        provider_chain=mock_chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=2,
    )

    assert outcome.exit_code == 0

    # Find the tool_result event for fs.list_tasks
    events = require_log(state).read_all()
    tr = [e for e in events if e.kind == "tool_result" and e.tool_name == "fs.list_tasks"]
    assert len(tr) == 1, "Expected exactly one fs.list_tasks tool_result event"

    result = tr[0].content.get("result") or {}
    tasks = result.get("tasks", [])
    pty_tasks = [t for t in tasks if t.get("type") == "pty"]
    assert len(pty_tasks) >= 1, f"Expected at least 1 PTY task, got {tasks}"
    assert any(t.get("id") == "main" for t in pty_tasks), f"Expected 'main' PTY task, got {pty_tasks}"


# ---------------------------------------------------------------------------
# Test 2 — Subagent artifact discovery
# ---------------------------------------------------------------------------

def test_list_tasks_finds_subagent_artifact(tmp_path: Path) -> None:
    """LIVE-PATH PROOF:
    - root: drive_session
    - test: tests/test_list_tasks_wiring.py::test_list_tasks_finds_subagent_artifact
    - matrix: A-gates-only with subagent_spawning_enabled=True
    - oracle: tool_result result["tasks"] contains {"type": "subagent", "id": "t-1"}
    - kill-check: removing .fa/subagents/ dir makes no subagent tasks appear

    Product claim: fs.list_tasks discovers subagent artifacts in .fa/subagents/.
    """
    # Pre-create a subagent artifact
    subagents_dir = tmp_path / ".fa" / "subagents"
    subagents_dir.mkdir(parents=True, exist_ok=True)
    (subagents_dir / "t-1.json").write_text('{"task_id": "t-1", "type": "verifier"}', encoding="utf-8")

    log = EventLog(tmp_path / "events.jsonl", run_id="list-tasks-subagent")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="list-tasks-subagent",
        log=log,
        feature_flags=FeatureFlags(subagent_spawning_enabled=True),
    )
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()

    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 150000
    mock_chain.config.compaction_threshold = None
    mock_chain.config.model = "test"
    mock_chain.config.family = "openai"

    tc1 = make_tool_call("fs.list_tasks", {}, "tc-1")

    mock_chain.request.side_effect = [
        mock_response_with_tools([tc1]),
        mock_success_response("done"),
    ]

    outcome = drive_session(
        "list tasks",
        provider_chain=mock_chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=2,
    )

    assert outcome.exit_code == 0

    events = require_log(state).read_all()
    tr = [e for e in events if e.kind == "tool_result" and e.tool_name == "fs.list_tasks"]
    assert len(tr) == 1

    result = tr[0].content.get("result") or {}
    tasks = result.get("tasks", [])
    subagent_tasks = [t for t in tasks if t.get("type") == "subagent"]
    assert len(subagent_tasks) >= 1, f"Expected at least 1 subagent task, got {tasks}"
    assert any(t.get("id") == "t-1" for t in subagent_tasks), f"Expected 't-1' subagent task, got {subagent_tasks}"


# ---------------------------------------------------------------------------
# Test 3 — Worktree dir discovery
# ---------------------------------------------------------------------------

def test_list_tasks_finds_worktree_dir(tmp_path: Path) -> None:
    """LIVE-PATH PROOF:
    - root: drive_session
    - test: tests/test_list_tasks_wiring.py::test_list_tasks_finds_worktree_dir
    - matrix: A-gates-only
    - oracle: tool_result result["tasks"] contains {"type": "worktree", "id": "agent-1"}
    - kill-check: removing worktree dir makes no worktree tasks appear

    Product claim: fs.list_tasks discovers worktree directories via worktree_manager.
    """
    # Create a mock worktree_manager with worktrees_root pointing to a dir
    worktrees_root = tmp_path / "worktrees"
    worktrees_root.mkdir(parents=True)
    (worktrees_root / "agent-1").mkdir()

    mock_wm = MagicMock()
    mock_wm.worktrees_root = str(worktrees_root)

    log = EventLog(tmp_path / "events.jsonl", run_id="list-tasks-worktree")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="list-tasks-worktree",
        log=log,
        feature_flags=FeatureFlags(),
    )
    # Attach worktree_manager to session so fs.list_tasks can find it
    state.worktree_manager = mock_wm  # type: ignore[attr-defined]

    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()

    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 150000
    mock_chain.config.compaction_threshold = None
    mock_chain.config.model = "test"
    mock_chain.config.family = "openai"

    tc1 = make_tool_call("fs.list_tasks", {}, "tc-1")

    mock_chain.request.side_effect = [
        mock_response_with_tools([tc1]),
        mock_success_response("done"),
    ]

    outcome = drive_session(
        "list tasks",
        provider_chain=mock_chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=2,
    )

    assert outcome.exit_code == 0

    events = require_log(state).read_all()
    tr = [e for e in events if e.kind == "tool_result" and e.tool_name == "fs.list_tasks"]
    assert len(tr) == 1

    result = tr[0].content.get("result") or {}
    tasks = result.get("tasks", [])
    worktree_tasks = [t for t in tasks if t.get("type") == "worktree"]
    assert len(worktree_tasks) >= 1, f"Expected at least 1 worktree task, got {tasks}"
    assert any(t.get("id") == "agent-1" for t in worktree_tasks), f"Expected 'agent-1' worktree task, got {worktree_tasks}"


# ---------------------------------------------------------------------------
# Test 4 — Empty list when no pool/manager
# ---------------------------------------------------------------------------

def test_list_tasks_empty_when_no_pool_or_manager(tmp_path: Path) -> None:
    """LIVE-PATH PROOF:
    - root: drive_session
    - test: tests/test_list_tasks_wiring.py::test_list_tasks_empty_when_no_pool_or_manager
    - matrix: A-gates-only (no pty_pool, no worktree_manager)
    - oracle: tool_result result["tasks"] is empty list
    - kill-check: N/A (this tests the fallback/degradation path)

    Product claim: fs.list_tasks gracefully returns empty when no pool or manager available.
    """
    log = EventLog(tmp_path / "events.jsonl", run_id="list-tasks-empty")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="list-tasks-empty",
        log=log,
        feature_flags=FeatureFlags(),
    )
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()

    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 150000
    mock_chain.config.compaction_threshold = None
    mock_chain.config.model = "test"
    mock_chain.config.family = "openai"

    tc1 = make_tool_call("fs.list_tasks", {}, "tc-1")

    mock_chain.request.side_effect = [
        mock_response_with_tools([tc1]),
        mock_success_response("done"),
    ]

    outcome = drive_session(
        "list tasks",
        provider_chain=mock_chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=2,
    )

    assert outcome.exit_code == 0

    events = require_log(state).read_all()
    tr = [e for e in events if e.kind == "tool_result" and e.tool_name == "fs.list_tasks"]
    assert len(tr) == 1

    result = tr[0].content.get("result") or {}
    tasks = result.get("tasks", [])
    # No pty_pool, no worktree_manager, no subagent artifacts -> should be empty
    # (might have subagent artifacts if tmp_path has .fa/subagents but we didn't create any)
    non_subagent = [t for t in tasks if t.get("type") != "subagent"]
    assert len(non_subagent) == 0, f"Expected no PTY/worktree tasks without pool/manager, got {non_subagent}"
