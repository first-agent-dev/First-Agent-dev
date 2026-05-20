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
