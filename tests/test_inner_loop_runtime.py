from __future__ import annotations

import sys
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
    AuditHook,
    Decision,
    GuardMiddleware,
    HookPayload,
    HookRegistry,
    LearningObserver,
    LifecyclePoint,
    ObserverMiddleware,
    PauseGuard,
    SandboxHook,
)
from fa.inner_loop.state import TraceEvent
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

    # ADR-7 §7 projection: per call the actual emission order is
    # ``tool_call`` (state.record_tool_call — actor="coder")
    #   → ``hook_decision`` (sandbox at BEFORE_TOOL_EXEC — actor="hook")
    #   → ``hook_decision`` (audit at AFTER_TOOL_EXEC — actor="hook")
    #   → ``tool_result`` (state.record_tool_result — actor="tool").
    # ``record_tool_result`` runs *after* the AFTER_TOOL_EXEC dispatch
    # so observers see the result via ``payload.with_tool_result`` while
    # the row is appended last; an audit consumer that reconstructs the
    # call timeline pairs by ``tool_call_id``, not by file order.
    #
    # A bare ``count()`` assertion (e.g. ``count("hook_decision") == 6``)
    # passes for the right number even if the runtime emitted the wrong
    # middleware, wrong actor, or wrong order; we therefore project a
    # per-call signature of (kind, actor, middleware-or-"") so a regression
    # is diagnosable directly from the assertion failure message.
    def _signature(event: TraceEvent) -> tuple[str, str, str]:
        middleware = (
            str(event.content.get("middleware", "")) if event.kind == "hook_decision" else ""
        )
        return (event.kind, event.actor, middleware)

    by_call: dict[str, list[tuple[str, str, str]]] = {}
    for event in events:
        by_call.setdefault(event.tool_call_id, []).append(_signature(event))

    expected_signature = [
        ("tool_call", "coder", ""),
        ("hook_decision", "hook", "sandbox"),
        ("hook_decision", "hook", "audit"),
        ("tool_result", "tool", ""),
    ]
    assert by_call == {
        "tc-1": expected_signature,
        "tc-2": expected_signature,
        "tc-3": expected_signature,
    }

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


class _AfterExecDenyGuard(GuardMiddleware):
    """Test fixture: denies every AFTER_TOOL_EXEC dispatch.

    ADR-8 \u00a71 explicitly permits ``GuardMiddleware`` to attach to any
    lifecycle point, including ``AFTER_TOOL_EXEC``. No builtin guard
    sits there today (only observers do), but the contract supports it
    and Wave-2 R-Ns may add one \u2014 so ``run_session`` must already
    handle the deny path without losing the just-produced tool result.
    """

    name = "after-deny"
    attaches_to = (LifecyclePoint.AFTER_TOOL_EXEC,)

    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point, payload
        return Decision.deny("after-exec guard denied")


def test_run_session_handles_after_tool_exec_denial_cleanly(tmp_path: Path) -> None:
    """Devin-Review BUG-0003 (symmetric to BUG-0001): when a guard at
    ``AFTER_TOOL_EXEC`` denies after the tool has already executed, the
    runtime MUST still persist the tool's actual result (ADR-7 \u00a710
    Acceptance criterion 8 \u2014 paired ``tool_call`` / ``tool_result``
    rows for every call) and surface the deny via a ``run_stopped``
    row + clean loop break.

    Before the fix, the ``PermissionError`` from a denying AFTER guard
    propagated past ``state.record_tool_result`` and ``results.append``,
    so the result was lost from both the event log and the return value
    even though the tool had run successfully.
    """

    (tmp_path / "input.txt").write_text("hello\n", encoding="utf-8")
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    hooks.register(_AfterExecDenyGuard())
    state = SessionState(
        workspace_root=tmp_path,
        run_id="t-after-deny",
        log=EventLog(tmp_path / "ev.jsonl"),
    )

    # Two calls: only the first should run; the AFTER_TOOL_EXEC deny
    # must break the loop, leaving the second untouched.
    results = run_session(
        (
            ToolCall(name="fs.read_file", params={"path": "input.txt"}, call_id="tc-1"),
            ToolCall(name="fs.read_file", params={"path": "input.txt"}, call_id="tc-2"),
        ),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    # The just-produced result is preserved (the tool actually ran).
    assert len(results) == 1
    assert results[0].error is None
    assert results[0].summary == "read input.txt"
    result_payload = results[0].result
    assert result_payload is not None
    assert result_payload["content"] == "hello\n"

    assert state.log is not None
    events = state.log.read_all()
    kinds_by_call: dict[str, list[str]] = {}
    for event in events:
        kinds_by_call.setdefault(event.tool_call_id, []).append(event.kind)

    # ADR-7 \u00a710 AC #8 \u2014 paired tool_call + tool_result for tc-1 even
    # though AFTER_TOOL_EXEC denied. tc-2 must never appear in the log.
    assert "tc-1" in kinds_by_call
    assert kinds_by_call["tc-1"].count("tool_call") == 1
    assert kinds_by_call["tc-1"].count("tool_result") == 1
    assert "tc-2" not in kinds_by_call

    # run_stopped row scoped to AFTER_TOOL_EXEC with the deny reason.
    stopped = [event for event in events if event.kind == "run_stopped"]
    assert len(stopped) == 1
    assert stopped[0].content["point"] == "AFTER_TOOL_EXEC"
    reason = stopped[0].content["reason"]
    assert isinstance(reason, str)
    assert "after-exec guard denied" in reason


def test_run_session_requires_session_log_with_explicit_valueerror(tmp_path: Path) -> None:
    """``state.log`` is the durable replay surface (ADR-7 \u00a77). Earlier
    code used ``assert state.log is not None``, which gets stripped under
    ``python -O`` and silently None'd the event-sink so every
    ``hook_decision`` row would be lost. The runtime now raises an
    explicit ``ValueError`` instead, so the misconfiguration surfaces
    even under ``-O``.
    """

    # ``SessionState.__post_init__`` auto-populates ``log`` if ``None``,
    # so the only way to reach the guard is via post-construction
    # mutation. The point of the test is the guard, not the dataclass
    # default \u2014 we want \u00abif state.log is None then explicit ValueError,
    # not a silent ``-O``-stripped assert\u00bb.
    state = SessionState(workspace_root=tmp_path, run_id="t-no-log")
    state.log = None
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()

    with pytest.raises(ValueError, match=r"SessionState\.log"):
        run_session(
            (ToolCall(name="fs.read_file", params={"path": "input.txt"}, call_id="tc-1"),),
            registry=registry,
            hooks=hooks,
            state=state,
        )


class _BetweenRoundsCountingGuard(GuardMiddleware):
    """Records every BETWEEN_ROUNDS payload so the test can confirm the
    iteration-1 dispatch (ADR-8 \u00a7Amendment 2026-05-20b)."""

    name = "between-counter"
    attaches_to = (LifecyclePoint.BETWEEN_ROUNDS,)

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point
        self.calls.append("" if payload.tool_call is None else payload.tool_call.name)
        return Decision.allow()


class _FailingObserver(ObserverMiddleware):
    name = "failing-observer"
    attaches_to = (LifecyclePoint.AFTER_TOOL_EXEC,)

    def observe(self, point: LifecyclePoint, payload: HookPayload) -> None:
        del point, payload
        raise RuntimeError("observer write failed")


def test_run_session_records_swallowed_observer_errors(tmp_path: Path) -> None:
    """Observer side-effect failures are non-fatal but still auditable.

    This is the safety net for filesystem-canon observers such as
    ``LearningObserver``: a broken write path must not fail the tool
    result, but the existing ``hook_decision`` row is the durable place
    to diagnose the swallowed observer exception.
    """

    (tmp_path / "input.txt").write_text("hello\n", encoding="utf-8")
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    hooks.register(_FailingObserver())
    state = SessionState(
        workspace_root=tmp_path,
        run_id="t-observer-error",
        log=EventLog(tmp_path / "ev.jsonl"),
    )

    results = run_session(
        (ToolCall(name="fs.read_file", params={"path": "input.txt"}, call_id="tc-1"),),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert results[0].error is None
    assert state.log is not None
    events = state.log.read_all()
    observer_rows = [
        event
        for event in events
        if event.kind == "hook_decision" and event.content.get("middleware") == "failing-observer"
    ]
    assert len(observer_rows) == 1
    row = observer_rows[0]
    assert row.content["decision"] == "observer_error_swallowed"
    assert row.content["reason"] == "observer write failed"


@pytest.mark.skipif(sys.platform == "win32", reason="chmod permission bits are POSIX-only")
def test_learning_observer_write_failure_audited(tmp_path: Path) -> None:
    """The real ``LearningObserver`` write-failure path lands in the
    existing ``hook_decision`` / ``observer_error_swallowed`` audit row.

    ADR-7 §Sub-amendment 2026-05-21b rule 3 promises that a broken
    ``knowledge/trace/`` write path is diagnosable through the existing
    hook audit row. The generic ``_FailingObserver`` regression above
    proves the registry-level mechanism; this test proves the specific
    ``LearningObserver`` → ``record_discovery`` → ``OSError`` → audit-row
    chain end-to-end with the real observer + writer wired together
    (TEST-GAP-2 fix).
    """

    (tmp_path / "input.txt").write_text("hello\n", encoding="utf-8")
    canon = tmp_path / "canon"
    canon.mkdir()
    canon.chmod(0o500)  # read+exec but not write
    try:
        registry = build_baseline_registry(tmp_path)
        hooks = HookRegistry()
        hooks.register(SandboxHook(tmp_path))
        hooks.register(
            LearningObserver(
                codebase_map_path=canon / "codebase_map.json",
                gotchas_path=canon / "gotchas.md",
            )
        )
        state = SessionState(
            workspace_root=tmp_path,
            run_id="t-learning-write-failure",
            log=EventLog(tmp_path / "ev.jsonl"),
        )

        results = run_session(
            (ToolCall(name="fs.read_file", params={"path": "input.txt"}, call_id="tc-1"),),
            registry=registry,
            hooks=hooks,
            state=state,
        )
    finally:
        canon.chmod(0o700)

    assert results[0].error is None
    assert state.log is not None
    events = state.log.read_all()
    observer_rows = [
        event
        for event in events
        if event.kind == "hook_decision" and event.content.get("middleware") == "learning"
    ]
    assert len(observer_rows) == 1, "LearningObserver write failure did not emit audit row"
    row = observer_rows[0]
    assert row.content["decision"] == "observer_error_swallowed"
    assert "codebase_map.json" in row.content["reason"]


def test_between_rounds_fires_on_iteration_1(tmp_path: Path) -> None:
    """ADR-8 \u00a7Amendment 2026-05-20b codifies that ``BETWEEN_ROUNDS``
    fires at the start of every iteration **including iteration 1**.
    This is what lets ``PauseGuard`` / ``LoopGuard`` block the very
    first tool call when a session-level gate is active.

    Without the iteration-1 dispatch, a pause sentinel set BEFORE
    ``run_session`` starts would be ignored until the second tool
    call \u2014 a real behavioural regression for any session-level guard.
    """

    (tmp_path / "input.txt").write_text("hello\n", encoding="utf-8")
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()
    counter = _BetweenRoundsCountingGuard()
    hooks.register(SandboxHook(tmp_path))
    hooks.register(counter)
    state = SessionState(
        workspace_root=tmp_path,
        run_id="t-iter1",
        log=EventLog(tmp_path / "ev.jsonl"),
    )

    # Two calls. BETWEEN_ROUNDS must fire BEFORE each call's
    # BEFORE_TOOL_EXEC \u2014 so we observe exactly 2 BETWEEN_ROUNDS
    # dispatches, not 1 (which would be the case if iter=1 were skipped).
    run_session(
        (
            ToolCall(name="fs.read_file", params={"path": "input.txt"}, call_id="tc-1"),
            ToolCall(name="fs.read_file", params={"path": "input.txt"}, call_id="tc-2"),
        ),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    # Behavioural assertion \u2014 not just \u00abthe count is right\u00bb. The
    # first BETWEEN_ROUNDS observation must arrive WITHOUT any tool
    # call having been recorded yet (ADR-8 \u00a7Amendment 2026-05-20b:
    # \u00abblocks the very first tool call\u00bb). The payload at
    # BETWEEN_ROUNDS does not carry the upcoming ``tool_call`` \u2014
    # session-level guards see an empty payload, which is what makes
    # them session-level.
    assert len(counter.calls) == 2
    assert counter.calls == ["", ""]

    # Pair with the audit trail: the first ``hook_decision`` row must
    # come before any ``tool_call`` row, which is the operator-facing
    # proof that BETWEEN_ROUNDS ran on iter=1 before record_tool_call.
    assert state.log is not None
    events = state.log.read_all()
    kinds_in_order = [event.kind for event in events]
    first_hook_decision = kinds_in_order.index("hook_decision")
    first_tool_call = kinds_in_order.index("tool_call")
    assert first_hook_decision < first_tool_call


def test_run_session_records_tool_result_when_handler_crashes(tmp_path: Path) -> None:
    """A crashing tool handler must NOT propagate past ``run_session``
    and leave the audit trail half-written. ``registry.dispatch`` wraps
    unexpected handler exceptions as ``ToolResult.fail("internal_error",
    \u2026)`` so the runtime can still record the paired ``tool_result``
    row (ADR-7 \u00a710 Acceptance criterion 8).

    This is the integration counterpart to
    ``test_dispatch_wraps_unexpected_handler_exception_as_internal_error``
    in ``test_inner_loop_validation.py`` \u2014 the unit test covers the
    registry-level shape; this test covers the audit-trail side-effect.
    """

    def crashing_handler(_params: object) -> ToolResult:
        raise RuntimeError("boom")

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="demo.crash",
            description="crashes",
            input_schema={
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string"}},
            },
            permission="read",
            handler=crashing_handler,
        )
    )
    hooks = HookRegistry()
    state = SessionState(
        workspace_root=tmp_path,
        run_id="t-crash",
        log=EventLog(tmp_path / "ev.jsonl"),
    )

    results = run_session(
        (ToolCall(name="demo.crash", params={"text": "x"}, call_id="tc-1"),),
        registry=registry,
        hooks=hooks,
        state=state,
    )

    # The crash surfaces as a structured failure, not an exception.
    assert len(results) == 1
    assert results[0].error is not None
    assert results[0].error.code == "internal_error"

    # Audit trail: paired ``tool_call`` + ``tool_result`` rows MUST
    # still exist for tc-1, even though the handler crashed.
    assert state.log is not None
    events = state.log.read_all()
    kinds_by_call: dict[str, list[str]] = {}
    for event in events:
        kinds_by_call.setdefault(event.tool_call_id, []).append(event.kind)
    assert kinds_by_call["tc-1"].count("tool_call") == 1
    assert kinds_by_call["tc-1"].count("tool_result") == 1
