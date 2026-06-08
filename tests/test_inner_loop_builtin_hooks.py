from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop import EventLog, ToolCall, ToolResult
from fa.inner_loop.hooks import (
    CapabilityGuard,
    HookPayload,
    LearningObserver,
    LifecyclePoint,
    PauseGuard,
    SecretGuard,
    VerifierObserver,
)
from fa.orchestration.pause import PauseKind, write_pause
from fa.verifier import VerifierContract


def test_pause_guard_denies_when_sentinel_exists(tmp_path: Path) -> None:
    write_pause(PauseKind.RATE_LIMIT, state_dir=tmp_path)
    guard = PauseGuard(state_dir=tmp_path)

    with pytest.raises(PermissionError, match="rate_limit"):
        from fa.inner_loop.hooks import HookRegistry

        registry = HookRegistry()
        registry.register(guard)
        registry.dispatch(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())


def test_capability_guard_denies_server_ops_command_by_default(tmp_path: Path) -> None:
    guard = CapabilityGuard(config_path=tmp_path / "missing.yaml")

    decision = guard.handle(
        LifecyclePoint.BEFORE_TOOL_EXEC,
        HookPayload(
            tool_call=ToolCall(name="fs.run_bash", params={"command": "deploy production"})
        ),
    )

    assert decision.action == "deny"
    assert decision.reason == "ENABLE_SERVER_OPS is false"


def test_verifier_observer_records_failed_contract() -> None:
    observer = VerifierObserver(
        contracts={
            "fs.write_file": VerifierContract(
                target_action="fs.write_file",
                required_trace_events=("file_write",),
                failure_conditions=("write_failed",),
            )
        }
    )

    observer.observe(
        LifecyclePoint.AFTER_TOOL_EXEC,
        HookPayload(
            tool_call=ToolCall(name="fs.write_file", params={"path": "x"}),
            tool_result=ToolResult.ok("wrote"),
        ),
    )

    assert observer.failures == [("fs.write_file", ("missing_required_event:file_write",))]


def test_verifier_observer_emits_verification_audit_row(tmp_path: Path) -> None:
    """When a contract trips and an ``EventLog`` is wired, the observer
    appends a ``kind="verification"`` row containing the override-action
    and the matched reasons. This is the audit-trail surface the
    downstream ``force_failure`` consumer (T-2 LLM driver) reads.
    """

    log_path = tmp_path / "events.jsonl"
    log = EventLog(log_path)
    contract = VerifierContract(
        target_action="fs.write_file",
        required_trace_events=(),
        failure_conditions=("write_failed",),
    )
    observer = VerifierObserver(contracts={"fs.write_file": contract}, event_log=log)

    observer.observe(
        LifecyclePoint.AFTER_TOOL_EXEC,
        HookPayload(
            tool_call=ToolCall(name="fs.write_file", params={"path": "x"}, call_id="tc-1"),
            tool_result=ToolResult.fail("write_failed", "permission denied"),
        ),
    )

    import json

    rows = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    verification_rows = [r for r in rows if r["kind"] == "verification"]
    assert len(verification_rows) == 1
    row = verification_rows[0]
    assert row["tool_name"] == "fs.write_file"
    assert row["tool_call_id"] == "tc-1"
    assert row["content"]["override_action"] == "force_failure"
    assert "failure_condition_observed:write_failed" in row["content"]["reasons"]


def test_verifier_observer_no_audit_row_on_success(tmp_path: Path) -> None:
    """Successful contracts produce no ``verification`` row — only
    failures need durable audit. The trace stays terse and a
    downstream consumer can rely on the row being a deny signal.
    """

    log_path = tmp_path / "events.jsonl"
    log = EventLog(log_path)
    contract = VerifierContract(
        target_action="fs.read_file",
        required_trace_events=(),
        failure_conditions=("read_failed",),
    )
    observer = VerifierObserver(contracts={"fs.read_file": contract}, event_log=log)

    observer.observe(
        LifecyclePoint.AFTER_TOOL_EXEC,
        HookPayload(
            tool_call=ToolCall(name="fs.read_file", params={"path": "x"}, call_id="tc-1"),
            tool_result=ToolResult.ok("read x"),
        ),
    )

    # File may not exist when the log was opened but never written to;
    # the test asserts the *absence* of a verification row either way.
    if not log_path.exists():
        return
    import json

    rows = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [r for r in rows if r["kind"] == "verification"] == []


def test_learning_observer_writes_discovery_and_gotcha(tmp_path: Path) -> None:
    observer = LearningObserver(
        codebase_map_path=tmp_path / "codebase_map.json",
        gotchas_path=tmp_path / "gotchas.md",
    )
    observer.observe(
        LifecyclePoint.AFTER_TOOL_EXEC,
        HookPayload(
            tool_call=ToolCall(name="fs.read_file", params={"path": "README.md"}),
            tool_result=ToolResult.ok("read README.md"),
        ),
    )
    observer.observe(
        LifecyclePoint.AFTER_TOOL_EXEC,
        HookPayload(
            tool_call=ToolCall(name="fs.write_file", params={"path": "x"}),
            tool_result=ToolResult.fail("write_failed", "no"),
        ),
    )

    assert (tmp_path / "codebase_map.json").exists()
    assert "fs.write_file failed" in (tmp_path / "gotchas.md").read_text(encoding="utf-8")


def test_secret_guard_denies_write_file_with_secret() -> None:
    guard = SecretGuard(secrets=frozenset({"sk-or-v1-real-key-12345"}))
    payload = HookPayload(
        tool_call=ToolCall(
            name="fs.write_file",
            params={"path": "test.txt", "content": "key is sk-or-v1-real-key-12345"},
        ),
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, payload)
    assert decision.action == "deny"
    assert "secret leak detected" in decision.reason


def test_secret_guard_allows_write_file_without_secret() -> None:
    guard = SecretGuard(secrets=frozenset({"sk-or-v1-real-key-12345"}))
    payload = HookPayload(
        tool_call=ToolCall(
            name="fs.write_file",
            params={"path": "test.txt", "content": "plain text"},
        ),
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, payload)
    assert decision.action == "allow"


def test_secret_guard_allows_bash_without_secret() -> None:
    guard = SecretGuard(secrets=frozenset({"sk-or-v1-real-key-12345"}))
    payload = HookPayload(
        tool_call=ToolCall(
            name="fs.run_bash",
            params={"command": "ls -la"},
        ),
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, payload)
    assert decision.action == "allow"


def test_secret_guard_allows_null_tool_call() -> None:
    guard = SecretGuard(secrets=frozenset({"sk-or-v1-real-key-12345"}))
    payload = HookPayload()
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, payload)
    assert decision.action == "allow"
