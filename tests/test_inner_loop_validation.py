"""Schema validation + modify->revalidate + sandbox-on-path tests (ADR-7 \u00a75, \u00a78).

Covers F-1..F-3 and F-12 from the PR #24 must-fix block:

- F-1 / \u00a75: ``ToolRegistry.dispatch`` rejects malformed params with
  ``error.code = "invalid_params"`` before the handler runs.
- F-2 / \u00a78: a ``Decision.modify`` cannot bypass schema validation \u2014
  ``ToolRegistry.dispatch`` re-validates the mutated payload.
- F-3 / \u00a78: ``SandboxHook`` denies ``fs.read_file`` / ``fs.write_file``
  paths that escape the workspace root, not only ``fs.run_bash``.
- F-12 / \u00a78: a Decision.modify that mutates ``path`` to escape the
  workspace triggers the sandbox replay and is denied.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop import (
    EventLog,
    SessionState,
    ToolCall,
    ToolRegistry,
    ToolResult,
    ToolSpec,
    run_session,
)
from fa.inner_loop.hooks import (
    Decision,
    GuardMiddleware,
    HookPayload,
    HookRegistry,
    LifecyclePoint,
    SandboxHook,
)
from fa.inner_loop.tools import build_baseline_registry


def _noop_handler(_params: object) -> ToolResult:
    return ToolResult.ok("noop")


def test_dispatch_rejects_invalid_params() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="demo.echo",
            description="echo a string back",
            input_schema={
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string"}},
            },
            permission="read",
            handler=_noop_handler,
        )
    )

    # F-1: missing required field surfaces as invalid_params, retryable.
    missing = registry.dispatch(ToolCall(name="demo.echo", params={}))
    assert missing.error is not None
    assert missing.error.code == "invalid_params"
    assert missing.error.retryable is True

    # F-1: wrong type surfaces with a path so the model can correct.
    wrong_type = registry.dispatch(ToolCall(name="demo.echo", params={"text": 42}))
    assert wrong_type.error is not None
    assert wrong_type.error.code == "invalid_params"
    assert "text" in wrong_type.error.message


def test_register_rejects_malformed_schema() -> None:
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="invalid input_schema"):
        registry.register(
            ToolSpec(
                name="demo.broken",
                description="broken schema",
                input_schema={"type": "not-a-real-type"},
                permission="read",
                handler=_noop_handler,
            )
        )


def test_full_permission_is_rejected() -> None:
    # F-8: ``"full"`` is reserved by ADR-7 \u00a72; the dedicated branch in
    # ``ToolSpec.__post_init__`` surfaces the canonical error message.
    with pytest.raises(ValueError, match="reserved"):
        ToolSpec(
            name="demo.full",
            description="should fail",
            input_schema={"type": "object"},
            permission="full",  # type: ignore[arg-type]
            handler=_noop_handler,
        )


class _PathMutatorGuard(GuardMiddleware):
    """Test fixture: rewrites the ``path`` param to a fixed value once."""

    attaches_to = (LifecyclePoint.BEFORE_TOOL_EXEC,)

    def __init__(self, new_path: str, *, name: str = "path-mutator") -> None:
        self.name = name
        self.new_path = new_path

    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point
        assert payload.tool_call is not None
        call = payload.tool_call
        new_params = dict(call.params)
        new_params["path"] = self.new_path
        return Decision.modify(
            payload.with_tool_call(
                ToolCall(name=call.name, params=new_params, call_id=call.call_id)
            )
        )


def test_modify_does_not_bypass_schema_revalidation(tmp_path: Path) -> None:
    """F-2: a Decision.modify that mutates params into an invalid shape
    is caught by the registry-level re-validation on the next dispatch."""

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="demo.read",
            description="read a string from params",
            input_schema={
                "type": "object",
                "required": ["path"],
                "properties": {"path": {"type": "string", "minLength": 1}},
            },
            permission="read",
            handler=_noop_handler,
        )
    )

    class _InvalidatingGuard(GuardMiddleware):
        name = "invalidator"
        attaches_to = (LifecyclePoint.BEFORE_TOOL_EXEC,)

        def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
            del point
            assert payload.tool_call is not None
            call = payload.tool_call
            return Decision.modify(
                payload.with_tool_call(
                    ToolCall(name=call.name, params={"path": ""}, call_id=call.call_id)
                )
            )

    hooks = HookRegistry()
    hooks.register(_InvalidatingGuard())
    state = SessionState(
        workspace_root=tmp_path, run_id="t-modify", log=EventLog(tmp_path / "ev.jsonl")
    )

    results = run_session(
        (ToolCall(name="demo.read", params={"path": "valid.txt"}, call_id="tc-1"),),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert results[0].error is not None
    assert results[0].error.code == "invalid_params"


def test_sandbox_blocks_read_file_escape(tmp_path: Path) -> None:
    """F-3: SandboxHook denies an out-of-workspace fs.read_file path
    BEFORE the tool's own ``resolve_workspace_path`` runs."""

    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")

    registry = build_baseline_registry(workspace)
    hooks = HookRegistry()
    hooks.register(SandboxHook(workspace))
    state = SessionState(
        workspace_root=workspace, run_id="t-read", log=EventLog(workspace / "ev.jsonl")
    )

    results = run_session(
        (ToolCall(name="fs.read_file", params={"path": str(outside)}, call_id="tc-1"),),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert results[0].error is not None
    assert results[0].error.code == "hook_deny"
    assert "escapes" in results[0].summary


def test_sandbox_blocks_write_file_escape(tmp_path: Path) -> None:
    """F-3: SandboxHook denies an out-of-workspace fs.write_file path."""

    workspace = tmp_path / "ws"
    workspace.mkdir()
    escape_target = tmp_path / "outside.txt"

    registry = build_baseline_registry(workspace)
    hooks = HookRegistry()
    hooks.register(SandboxHook(workspace))
    state = SessionState(
        workspace_root=workspace, run_id="t-write", log=EventLog(workspace / "ev.jsonl")
    )

    results = run_session(
        (
            ToolCall(
                name="fs.write_file",
                params={"path": str(escape_target), "content": "boom"},
                call_id="tc-1",
            ),
        ),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert results[0].error is not None
    assert results[0].error.code == "hook_deny"
    assert not escape_target.exists()


def test_modify_to_escape_is_caught_by_sandbox_replay(tmp_path: Path) -> None:
    """F-12: a Decision.modify that rewrites ``path`` to an out-of-workspace
    target must be caught even when sandbox ran BEFORE the mutator (ADR-7 \u00a78
    sandbox-re-check exception via ``revalidates_after_modify``)."""

    workspace = tmp_path / "ws"
    workspace.mkdir()
    escape_target = tmp_path / "outside.txt"

    registry = build_baseline_registry(workspace)
    hooks = HookRegistry()
    # Sandbox registered FIRST (so it has already-run by the time the mutator
    # changes ``path``); the replay path is what catches the escape attempt.
    hooks.register(SandboxHook(workspace))
    hooks.register(_PathMutatorGuard(str(escape_target)))
    state = SessionState(
        workspace_root=workspace, run_id="t-replay", log=EventLog(workspace / "ev.jsonl")
    )

    results = run_session(
        (
            ToolCall(
                name="fs.write_file",
                params={"path": "in-ws.txt", "content": "ok"},
                call_id="tc-1",
            ),
        ),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert results[0].error is not None
    assert results[0].error.code == "hook_deny"
    assert "escapes" in results[0].summary
    assert not escape_target.exists()


def test_dispatch_trace_records_sandbox_replay(tmp_path: Path) -> None:
    """The dispatch trace marks replayed guards with an ``@replay`` suffix
    so an operator can tell baseline vs revalidation rows apart."""

    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = build_baseline_registry(workspace)
    hooks = HookRegistry()
    hooks.register(SandboxHook(workspace))
    hooks.register(_PathMutatorGuard("kept-in-ws.txt"))
    state = SessionState(
        workspace_root=workspace, run_id="t-trace", log=EventLog(workspace / "ev.jsonl")
    )

    results = run_session(
        (
            ToolCall(
                name="fs.write_file",
                params={"path": "original.txt", "content": "ok"},
                call_id="tc-1",
            ),
        ),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert results[0].error is None
    decisions = [record.middleware for record in hooks.dispatch_trace]
    assert "sandbox@replay" in decisions
