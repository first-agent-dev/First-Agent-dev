from __future__ import annotations

from pathlib import Path

from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.hooks import AuditHook, HookRegistry, SandboxHook
from fa.inner_loop.tools import build_baseline_registry


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
    assert len(state.log.read_all()) == 6


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
