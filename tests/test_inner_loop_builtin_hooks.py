from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop import ToolCall, ToolResult
from fa.inner_loop.hooks import (
    CapabilityGuard,
    HookPayload,
    LearningObserver,
    LifecyclePoint,
    PauseGuard,
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
