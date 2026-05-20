from __future__ import annotations

from pathlib import Path

from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.hooks import AuditHook, HookRegistry, PauseGuard, SandboxHook
from fa.inner_loop.tools import build_baseline_registry
from fa.orchestration.pause import PauseKind, write_pause


def test_run_session_executes_tool_through_hooks(tmp_path: Path) -> None:
    (tmp_path / "input.txt").write_text("hello\n", encoding="utf-8")
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()
    audit = AuditHook()
    hooks.register(SandboxHook(tmp_path))
    hooks.register(audit)
    state = SessionState(
        workspace_root=tmp_path, run_id="test", log=EventLog(tmp_path / "events.jsonl")
    )

    results = run_session(
        (
            ToolCall(name="fs.read_file", params={"path": "input.txt"}, call_id="tc-1"),
            ToolCall(
                name="fs.write_file",
                params={"path": "out.txt", "content": "ok\n"},
                call_id="tc-2",
            ),
            ToolCall(name="fs.run_bash", params={"command": "test -f out.txt"}, call_id="tc-3"),
        ),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert [result.error for result in results] == [None, None, None]
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "ok\n"
    assert [event["tool"] for event in audit.events] == [
        "fs.read_file",
        "fs.write_file",
        "fs.run_bash",
    ]
    assert state.log is not None
    events = state.log.read_all()
    # ADR-7 §7 projection: per call we record tool_call + (sandbox hook_decision)
    # + tool_result + (audit hook_decision) = 4 events per call across 3 calls = 12.
    kinds_by_call = [event.kind for event in events]
    assert kinds_by_call.count("tool_call") == 3
    assert kinds_by_call.count("tool_result") == 3
    assert kinds_by_call.count("hook_decision") == 6  # 3 sandbox + 3 audit observer rows.
    # Every event carries the session run_id per ADR-7 §7 trace schema.
    assert {event.run_id for event in events} == {"test"}
    # ADR-7 §7 schema field is ``ts`` (not ``timestamp``).
    assert all(event.ts.endswith("Z") for event in events)


def test_run_session_records_hook_denial(tmp_path: Path) -> None:
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = SessionState(
        workspace_root=tmp_path, run_id="test-deny", log=EventLog(tmp_path / "deny.jsonl")
    )

    results = run_session(
        (ToolCall(name="fs.run_bash", params={"command": "sudo rm -rf /"}, call_id="tc-1"),),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert results[0].error is not None
    assert results[0].error.code == "hook_deny"
    assert "dangerous" in results[0].summary
    # ADR-7 §10 Acceptance criterion 8: failed tool calls still emit
    # both ``tool_call`` and ``tool_result`` rows.
    assert state.log is not None
    kinds = [event.kind for event in state.log.read_all()]
    assert kinds.count("tool_call") == 1
    assert kinds.count("tool_result") == 1
    assert "hook_decision" in kinds


def test_run_session_handles_pause_guard_denial_cleanly(tmp_path: Path) -> None:
    """Devin-Review BUG-0001: when a guard at ``BETWEEN_ROUNDS`` denies
    (``PauseGuard`` is the canonical case), ``run_session`` MUST stop
    cleanly instead of propagating ``PermissionError`` out of the loop.

    Before the fix, only the ``BEFORE_TOOL_EXEC`` dispatch was wrapped
    in a ``try/except PermissionError`` block; a ``BETWEEN_ROUNDS``
    denial crashed the CLI with a raw traceback. The fix wraps that
    dispatch too, emits a ``kind="run_stopped"`` audit row, and breaks
    out of the iteration loop.
    """

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    write_pause(PauseKind.AUTH, reason="test-pause", state_dir=state_dir)

    (tmp_path / "untouched.txt").write_text("should never read\n", encoding="utf-8")
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()
    hooks.register(PauseGuard(state_dir=state_dir))
    hooks.register(SandboxHook(tmp_path))
    state = SessionState(
        workspace_root=tmp_path, run_id="t-pause", log=EventLog(tmp_path / "ev.jsonl")
    )

    # Should not raise -- BUG-0001 made this propagate PermissionError.
    results = run_session(
        (ToolCall(name="fs.read_file", params={"path": "untouched.txt"}, call_id="tc-1"),),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    # Pause denial stops the loop BEFORE the tool runs -> zero tool results.
    assert results == ()
    assert state.log is not None
    events = state.log.read_all()
    kinds = [event.kind for event in events]
    # The hook_decision row from the guard chain is still emitted...
    assert "hook_decision" in kinds
    # ...and run_session itself records the run_stopped row so an
    # operator can tell the loop ended early without replaying the chain.
    stopped = [event for event in events if event.kind == "run_stopped"]
    assert len(stopped) == 1
    assert stopped[0].content["point"] == "BETWEEN_ROUNDS"
    reason = stopped[0].content["reason"]
    assert isinstance(reason, str)
    assert "pause sentinel" in reason
