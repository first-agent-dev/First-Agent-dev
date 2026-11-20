"""Controller validation for the typed managed project-tool result envelope."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fa.execution.client import (
    ExecutionClient,
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
    ManagedProjectToolExecutor,
)
from fa.execution.profiles import ExecutionProfile
from fa.execution.types import Access, ExecutionContractError, GrantReply, NamespaceRef, Operation, ViewPurpose, ViewRef
from fa.inner_loop.registry import ToolResult
from fa.inner_loop.tools.managed_project_tool import dispatch_managed_project_tool


def test_project_executor_rebinds_only_to_a_fresh_view_in_the_same_workspace(tmp_path: Path) -> None:
    namespace = NamespaceRef("session-1", "run-1")
    workspace_id = "ws-" + "1" * 32
    first = ViewRef(
        workspace_id,
        "view-" + "2" * 32,
        "rev-" + "3" * 32,
        "run-1",
        1,
        Access.WRITE,
        ViewPurpose.PROJECT,
    )
    source_hash = "4" * 64
    capability = "5" * 64
    grant = GrantReply(Operation.CREATE_VIEW, capability, first, None, None, source_hash)
    profile = ExecutionProfile(
        "interactive",
        "example.invalid/fa@sha256:" + source_hash,
        1000,
        1000,
        1_000_000_000,
        512 * 1024 * 1024,
        32,
        30_000,
        True,
        "fa-test.slice",
        json.dumps({"defaultAction": "SCMP_ACT_ERRNO", "syscalls": []}),
    )
    executor = ManagedProjectToolExecutor(
        ExecutionClient(tmp_path / "unused.sock", server_uid=1000, rpc_timeout_ms=100),
        namespace=namespace,
        view=first,
        grant=grant,
        profile=profile,
        input_tree_sha256=source_hash,
        plan_sha256=None,
        original_revision_id=first.base_revision,
    )
    assert executor.is_bound_to(namespace, first, grant)
    executor.suspend()
    second = ViewRef(
        workspace_id,
        "view-" + "6" * 32,
        "rev-" + "7" * 32,
        "run-1",
        2,
        Access.WRITE,
        ViewPurpose.PROJECT,
    )
    second_grant = GrantReply(Operation.CREATE_VIEW, capability, second, None, None, source_hash)
    executor.rebind(namespace=namespace, view=second, grant=second_grant, original_revision_id=second.base_revision)
    assert executor.is_bound_to(namespace, second, second_grant)
    executor.suspend()
    with pytest.raises(ExecutionContractError):
        executor.rebind(namespace=namespace, view=second, grant=second_grant, original_revision_id=second.base_revision)
    assert not executor.is_bound_to(namespace, second, second_grant)


class _Executor:
    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, tool: str, params: dict[str, Any], *, timeout: int = 25) -> str:
        self.calls.append((tool, params))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def _envelope(*, result: Any = None, error: Any = None) -> str:
    return json.dumps(
        {"summary": "cell result", "result": result, "error": error, "artifacts": []},
        separators=(",", ":"),
    )


def test_managed_project_tool_validates_complete_success_before_returning() -> None:
    params = {"query": "alpha", "output_mode": "files"}
    executor = _Executor(_envelope(result={"mode": "files", "files": [{"path": "src/a.py"}]}))

    result = dispatch_managed_project_tool(executor, "fs_search", params)

    assert result.error is None
    assert result.result == {"mode": "files", "files": [{"path": "src/a.py"}]}
    assert executor.calls == [("fs_search", params)]


@pytest.mark.parametrize(
    "encoded",
    [
        "not-json",
        _envelope(result={"some": "partial"}).replace('"artifacts":[]', '"extra":1,"artifacts":[]'),
        _envelope(result={"partial": True}, error={"code": "bad", "message": "bad", "retryable": False}),
        _envelope(result=None),
        _envelope(result={"ok": True}, error={"code": "bad", "message": "bad", "retryable": "false"}),
        _envelope(result={"ok": True}).replace('"artifacts":[]', '"artifacts":["path"]'),
    ],
)
def test_managed_project_tool_rejects_malformed_or_partial_envelopes(encoded: str) -> None:
    result = dispatch_managed_project_tool(_Executor(encoded), "fs_reach", {"symbol": "f"})
    assert result.error is not None
    assert result.error.code == "project_tool_failed"
    assert result.result is None


def test_managed_project_tool_preserves_structured_helper_refusal() -> None:
    refusal = _envelope(error={"code": "source_budget", "message": "managed discovery refused", "retryable": False})
    result = dispatch_managed_project_tool(_Executor(refusal), "fs_search", {"query": "x"})
    assert result.error is not None
    assert (result.error.code, result.error.message, result.error.retryable) == (
        "source_budget",
        "managed discovery refused",
        False,
    )
    assert result.result is None


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (ExecutionUnavailableError(), "execution_unavailable"),
        (ExecutionUncertainError("op-1"), "execution_unknown"),
        (ExecutionRejectedError("bad_receipt", "op-1"), "execution_rejected"),
    ],
)
def test_managed_project_tool_never_retries_or_falls_back(raised: Exception, expected: str) -> None:
    executor = _Executor(raised)
    result: ToolResult = dispatch_managed_project_tool(executor, "fs_search", {"query": "x"})
    assert result.error is not None and result.error.code == expected
    assert executor.calls == [("fs_search", {"query": "x"})]
