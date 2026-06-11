"""AuditHook -> EventLog wiring (F-13 + ADR-7 \u00a78 audit projection)."""

from __future__ import annotations

from pathlib import Path

from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.hooks import AuditHook, HookRegistry, SandboxHook
from fa.inner_loop.tools import build_baseline_registry


def test_event_log_appends_with_monotonic_ids_when_resuming(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    first = EventLog(path, run_id="resume-run")
    first.append(actor="runtime", kind="run_started")
    first.append(actor="runtime", kind="run_stopped")

    resumed = EventLog(path, run_id="resume-run")
    event = resumed.append(actor="runtime", kind="run_started")

    assert event.event_id == "ev-000003"
    assert [row.event_id for row in resumed.read_all()] == [
        "ev-000001",
        "ev-000002",
        "ev-000003",
    ]


def test_audit_hook_writes_to_event_log(tmp_path: Path) -> None:
    (tmp_path / "input.txt").write_text("hi\n", encoding="utf-8")
    log = EventLog(tmp_path / "ev.jsonl")
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    audit = AuditHook(event_log=log)
    hooks.register(audit)
    state = SessionState(workspace_root=tmp_path, run_id="t-audit", log=log)

    run_session(
        (ToolCall(name="fs.read_file", params={"path": "input.txt"}, call_id="tc-1"),),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    audit_rows = [event for event in log.read_all() if event.kind == "audit"]
    assert len(audit_rows) == 1
    assert audit_rows[0].actor == "hook"
    assert audit_rows[0].tool_name == "fs.read_file"
    assert audit_rows[0].tool_call_id == "tc-1"
    assert audit_rows[0].content.get("ok") is True
