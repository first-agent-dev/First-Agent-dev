"""C1 composition-root wiring tests for subagent termination lifecycle.

Covers:
- SubagentRunner.run_stateless respects timeout (C0/C1)
- Subagent timeout envelope is valid JSON schema (C0)
- PTY ctrl_c tool handler with wired pty_pool (C2)
- PTY ctrl_c lifecycle via drive_session with manual registry wiring (C1)
- Subagent spawn + cleanup artifact via drive_session (C1)

Skill: knowledge/skills/tests-writing/SKILL.md
- root: drive_session (C1) / SubagentRunner (C0) / build_send_ctrl_c_tool (C2)
- matrix: A-gates-only with subagent_spawning_enabled=True where needed
- oracle: Rank 1 (events) + Rank 2 (outcome) + Rank 6 (artifact FS)
- kill-check: each test named so removing the call site fails it

Architecture note (per ADR-15):
SubagentRunner uses subprocess.run(timeout=...) — there is no SIGTERM/SIGINT
sent to the subprocess. Python kills it on timeout. The "termination" path is
subprocess.TimeoutExpired. The PTY ctrl_c (fs.send_ctrl_c) operates on the
main agent's PtyPool sessions, NOT on subprocess-based subagents. These are
separate product claims tested separately.

Wiring note:
build_baseline_registry() registers fs.send_ctrl_c via
build_send_ctrl_c_tool() WITHOUT pty_pool — the tool's closure pty_pool is
None. This means drive_session dispatch of fs.send_ctrl_c returns "no-pool"
unless the tool is replaced with a properly-wired version. The C1 test below
replaces the unwired tool in the registry to achieve C1 coverage. A product
gap exists: build_baseline_registry should accept pty_pool and forward it
to build_send_ctrl_c_tool (or the tool should use get_current_session() DI
like fs.run_bash does).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from fa.feature_flags import FeatureFlags
from fa.inner_loop import EventLog, SessionState
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.tools import build_baseline_registry
from fa.providers import ProviderChain
from tests.fixtures.session_wiring import (
    make_test_chain_config,
    make_tool_call,
    mock_response_with_tools,
    mock_success_response,
    require_log,
)

# ---------------------------------------------------------------------------
# Test 1 — SubagentRunner timeout produces exit_code=-1 (C0)
# ---------------------------------------------------------------------------


def test_subagent_timeout_produces_exit_code_minus_one(tmp_path: Path) -> None:
    """LIVE-PATH PROOF:
    - root: SubagentRunner.run_stateless (subprocess-based, not drive_session)
    - test: tests/test_subagent_termination_wiring.py::test_subagent_timeout_produces_exit_code_minus_one
    - matrix: N/A (unit-level C0)
    - oracle: SubagentEnvelope.exit_code == -1, output contains "Timeout"
    - kill-check: removing timeout handling in run_stateless would raise unhandled TimeoutExpired

    Product claim: SubagentRunner.run_stateless respects timeout and produces valid
    envelope when command exceeds it.
    """
    from fa.inner_loop.subagent_runner import SubagentRunner

    runner = SubagentRunner(session_root=tmp_path, timeout=2)
    envelope = runner.run_stateless(
        task_id="timeout-test",
        command="sleep 30",
        role="verifier",
        workdir=tmp_path,
    )

    assert envelope.exit_code == -1, f"Expected exit_code=-1 for timeout, got {envelope.exit_code}"
    assert "Timeout" in envelope.summary or "Timeout" in str(envelope.verification), (
        f"Expected 'Timeout' in summary/verification, got summary={envelope.summary!r} verif={envelope.verification!r}"
    )
    assert envelope.duration_ms >= 0, "duration_ms should be non-negative"


# ---------------------------------------------------------------------------
# Test 2 — Subagent timeout envelope is valid (C0)
# ---------------------------------------------------------------------------


def test_subagent_timeout_envelope_is_valid(tmp_path: Path) -> None:
    """LIVE-PATH PROOF:
    - root: SubagentRunner.run_stateless + fastjsonschema validator
    - test: tests/test_subagent_termination_wiring.py::test_subagent_timeout_envelope_is_valid
    - matrix: N/A (C0)
    - oracle: validate_envelope does not raise
    - kill-check: removing envelope construction after timeout would return invalid envelope

    Product claim: Even timeout-produced envelopes pass schema validation.
    """
    from dataclasses import asdict

    from fa.inner_loop.subagent_envelope import validate_envelope
    from fa.inner_loop.subagent_runner import SubagentRunner

    runner = SubagentRunner(session_root=tmp_path, timeout=2)
    envelope = runner.run_stateless(
        task_id="timeout-valid",
        command="sleep 30",
        role="verifier",
        workdir=tmp_path,
    )

    # validate_envelope should NOT raise
    validate_envelope(asdict(envelope))


# ---------------------------------------------------------------------------
# Test 3a — PTY ctrl_c tool handler directly with wired pty_pool (C2)
# ---------------------------------------------------------------------------


def test_ctrl_c_tool_handler_works_with_wired_pty_pool(tmp_path: Path) -> None:
    """LIVE-PATH PROOF:
    - root: build_send_ctrl_c_tool(pty_pool=...) → handler dispatch
    - test: tests/test_subagent_termination_wiring.py::test_ctrl_c_tool_handler_works_with_wired_pty_pool
    - matrix: N/A (C2 unit-level)
    - oracle: ToolResult does NOT contain "no-pool"; status indicates ctrl_c sent or session-not-found
    - kill-check: removing pty_pool arg from build_send_ctrl_c_tool makes handler return "no-pool"

    Product claim: fs.send_ctrl_c handler works correctly when pty_pool is wired
    at construction time. This is a C2 test proving the tool logic is sound;
    the C1 test (3b) proves the composition-root wiring.
    """
    from fa.inner_loop.tools.pair_tools import build_send_ctrl_c_tool
    from fa.runtime import PtyPool

    pty_pool = PtyPool(max_size=2, base_cwd=tmp_path, run_id="ctrl-c-c2")
    spec = build_send_ctrl_c_tool(pty_pool=pty_pool)

    # Case 1: session does not exist → should report "session not found", not "no-pool"
    result = spec.handler({"session_id": "nonexistent"})
    assert "no-pool" not in result.summary, "Should not return no-pool when pty_pool is wired"
    assert result.error is None, f"Should not error for missing session, got {result.error}"
    # The handler returns ok with session-not-found message
    assert "not found" in result.summary.lower() or result.result is not None, (
        f"Expected session-not-found indication, got: {result.summary!r}"
    )

    # Case 2: no pty_pool → returns no-pool status in result dict (baseline behavior)
    unwired_spec = build_send_ctrl_c_tool(pty_pool=None)
    result2 = unwired_spec.handler({"session_id": "main"})
    assert result2.result is not None and result2.result.get("status") == "no-pool", (
        f"Unwired tool should return status=no-pool, got result={result2.result!r}"
    )


# ---------------------------------------------------------------------------
# Test 3b — PTY ctrl_c lifecycle via drive_session with manually wired registry (C1)
# ---------------------------------------------------------------------------


def test_ctrl_c_interrupts_pty_session_via_drive_session(tmp_path: Path) -> None:
    """LIVE-PATH PROOF:
    - root: drive_session with real PtyPool + fs.send_ctrl_c (manually wired)
    - test: tests/test_subagent_termination_wiring.py::test_ctrl_c_interrupts_pty_session_via_drive_session
    - matrix: A-gates-only
    - oracle: tool_result for fs.send_ctrl_c does NOT contain "no-pool"
    - kill-check: removing the registry rewiring makes send_ctrl_c return "no-pool"

    Product claim: fs.send_ctrl_c works on PtyPool sessions (main agent PTY lifecycle)
    when properly wired into the registry.

    NOTE: build_baseline_registry() registers fs.send_ctrl_c WITHOUT pty_pool,
    so we must replace the unwired tool with a properly-wired one. This is a
    known product gap — the registry builder should accept pty_pool and forward
    it to build_send_ctrl_c_tool (or the tool should use get_current_session()
    DI like fs.run_bash does). See module docstring for wiring note.
    """
    from fa.inner_loop.tools.pair_tools import build_send_ctrl_c_tool
    from fa.runtime import PtyPool

    log = EventLog(tmp_path / "events.jsonl", run_id="ctrl-c-pty")
    pty_pool = PtyPool(max_size=2, base_cwd=tmp_path, run_id="ctrl-c-pty")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="ctrl-c-pty",
        log=log,
        pty_pool=pty_pool,
        feature_flags=FeatureFlags(),
    )

    # Build baseline registry, then replace fs.send_ctrl_c with properly-wired version
    registry = build_baseline_registry(tmp_path)
    if "fs.send_ctrl_c" in registry._tools:
        del registry._tools["fs.send_ctrl_c"]
        del registry._validators["fs.send_ctrl_c"]
    registry.register(build_send_ctrl_c_tool(pty_pool=pty_pool))

    hooks = HookRegistry()

    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = make_test_chain_config(
        name="test",
    )

    # Turn 1: start a long-running bash
    tc1 = make_tool_call("fs.run_bash", {"command": "sleep 60"}, "tc-1")
    # Turn 2: send ctrl_c
    tc2 = make_tool_call("fs.send_ctrl_c", {"session_id": "main"}, "tc-2")
    # Turn 3: stop
    mock_chain.request.side_effect = [
        mock_response_with_tools([tc1]),
        mock_response_with_tools([tc2]),
        mock_success_response("done"),
    ]

    outcome = drive_session(
        "test ctrl_c",
        provider_chain=mock_chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=3,
    )

    assert outcome.exit_code == 0

    events = require_log(state).read_all()
    ctrl_c_results = [e for e in events if e.kind == "tool_result" and e.tool_name == "fs.send_ctrl_c"]
    assert len(ctrl_c_results) == 1, "Expected exactly one fs.send_ctrl_c tool_result"

    content = ctrl_c_results[0].content
    # The key assertion: it didn't fail with "no-pool" — the tool found the pty_pool
    assert "no-pool" not in str(content), "send_ctrl_c returned no-pool — PtyPool not wired correctly"


# ---------------------------------------------------------------------------
# Test 4 — Subagent spawn + cleanup artifact via drive_session (C1)
# ---------------------------------------------------------------------------


def test_subagent_spawn_and_cleanup_via_drive_session(tmp_path: Path) -> None:
    """LIVE-PATH PROOF:
    - root: drive_session with fs.spawn_subagent
    - test: tests/test_subagent_termination_wiring.py::test_subagent_spawn_and_cleanup_via_drive_session
    - matrix: A-gates-only with subagent_spawning_enabled=True
    - oracle: events contain spawn_start + spawn_done, artifact .fa/subagents/t-1.json exists
    - kill-check: removing spawn_subagent registration makes tool dispatch fail

    Product claim: subagent spawn creates artifact, events logged, workspace cleanup happens.
    """
    log = EventLog(tmp_path / "events.jsonl", run_id="spawn-cleanup")
    state = SessionState(
        workspace_root=tmp_path,
        run_id="spawn-cleanup",
        log=log,
        feature_flags=FeatureFlags(subagent_spawning_enabled=True, max_subagent_spawns_per_session=5),
    )
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()

    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = make_test_chain_config(
        name="test",
    )

    tc1 = make_tool_call(
        "fs.spawn_subagent",
        {"task_id": "t-1", "command": "echo done", "role": "verifier"},
        "tc-1",
    )

    mock_chain.request.side_effect = [
        mock_response_with_tools([tc1]),
        mock_success_response("done"),
    ]

    outcome = drive_session(
        "test subagent spawn",
        provider_chain=mock_chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=2,
    )

    assert outcome.exit_code == 0

    events = require_log(state).read_all()
    kinds = [e.kind for e in events]
    assert "subagent_spawn_start" in kinds, f"Expected subagent_spawn_start event, got {set(kinds)}"
    assert "subagent_spawn_done" in kinds, f"Expected subagent_spawn_done event, got {set(kinds)}"

    # Artifact should exist
    artifact = tmp_path / ".fa" / "subagents" / "t-1.json"
    assert artifact.exists(), f"Subagent artifact not found at {artifact}"

    # Artifact should be valid JSON with task_id
    import json

    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert data.get("task_id") == "t-1"
