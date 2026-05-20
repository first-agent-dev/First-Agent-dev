"""BlockerMiddleware (Wave-2 R-4) behavior tests.

These tests assert real denial behavior + suppression-window semantics
rather than "no exception" — the regression we are protecting against
is a blocker that silently allows the second call after detecting a
pattern, or denies forever after a single observation.

The dispatch order mirrors what ``run_session`` actually does: the
first call ``AFTER_TOOL_EXEC`` records an observation; the second
call's ``BEFORE_TOOL_EXEC`` consults the observation map and decides
whether to deny based on ``suppression_seconds``.
"""

from __future__ import annotations

import pytest

from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.hooks import (
    AuthExpiredBlocker,
    BlockerCategory,
    BlockerMiddleware,
    HookPayload,
    HookRegistry,
    LifecyclePoint,
    LockfileBlocker,
    RateLimitBlocker,
)
from fa.inner_loop.registry import (
    ToolCall as RegistryToolCall,
)
from fa.inner_loop.registry import (
    ToolError,
    ToolResult,
)
from fa.inner_loop.tools import build_baseline_registry


class _FakeClock:
    """Single-stepping clock: monotonically advances on every read."""

    def __init__(self, start: float = 1000.0, step: float = 0.0) -> None:
        self.now = start
        self.step = step

    def __call__(self) -> float:
        value = self.now
        self.now += self.step
        return value

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _payload(
    tool_name: str,
    *,
    error_code: str = "",
    error_message: str = "",
    call_id: str = "tc-1",
) -> HookPayload:
    """Construct an ``AFTER_TOOL_EXEC``-style payload with an optional error."""

    error = (
        ToolError(code=error_code, message=error_message, retryable=True)
        if (error_code or error_message)
        else None
    )
    return HookPayload(
        tool_call=RegistryToolCall(name=tool_name, params={}, call_id=call_id),
        tool_result=ToolResult(
            summary="ok" if error is None else (error_message or "failed"),
            error=error,
        ),
    )


# --- RateLimitBlocker -------------------------------------------------------


def test_rate_limit_blocker_detects_via_error_code() -> None:
    """Structured ``error.code`` matches one of the canonical rate-limit codes."""

    clock = _FakeClock(start=100.0)
    blocker = RateLimitBlocker(suppression_seconds=30.0, time_source=clock)

    # First call: rate-limit error response observed.
    observed = _payload("api.fetch", error_code="rate_limited", error_message="429")
    blocker.handle(LifecyclePoint.AFTER_TOOL_EXEC, observed)

    # Second call within window → deny.
    clock.advance(5.0)
    second = HookPayload(
        tool_call=RegistryToolCall(name="api.fetch", params={}, call_id="tc-2"),
    )
    decision = blocker.handle(LifecyclePoint.BEFORE_TOOL_EXEC, second)
    assert decision.action == "deny"
    assert "rate_limit" in decision.reason


def test_rate_limit_blocker_detects_via_error_message() -> None:
    """Regex on free-form message matches when ``error.code`` is generic."""

    clock = _FakeClock(start=100.0)
    blocker = RateLimitBlocker(suppression_seconds=30.0, time_source=clock)

    observed = _payload(
        "api.fetch",
        error_code="http_error",
        error_message="Too many requests, retry after 60s",
    )
    blocker.handle(LifecyclePoint.AFTER_TOOL_EXEC, observed)

    second = HookPayload(
        tool_call=RegistryToolCall(name="api.fetch", params={}, call_id="tc-2"),
    )
    decision = blocker.handle(LifecyclePoint.BEFORE_TOOL_EXEC, second)
    assert decision.action == "deny"


def test_rate_limit_blocker_allows_after_window_elapses() -> None:
    """Once ``suppression_seconds`` passes, the gate releases."""

    clock = _FakeClock(start=100.0)
    blocker = RateLimitBlocker(suppression_seconds=30.0, time_source=clock)

    blocker.handle(
        LifecyclePoint.AFTER_TOOL_EXEC,
        _payload("api.fetch", error_code="rate_limited", error_message="429"),
    )
    clock.advance(31.0)
    decision = blocker.handle(
        LifecyclePoint.BEFORE_TOOL_EXEC,
        HookPayload(tool_call=RegistryToolCall(name="api.fetch", params={}, call_id="tc-2")),
    )
    assert decision.action == "allow"


def test_rate_limit_blocker_does_not_affect_other_tools() -> None:
    """Suppression is keyed by ``tool_name`` — sibling tools stay live."""

    clock = _FakeClock(start=100.0)
    blocker = RateLimitBlocker(suppression_seconds=30.0, time_source=clock)

    blocker.handle(
        LifecyclePoint.AFTER_TOOL_EXEC,
        _payload("api.fetch", error_code="rate_limited", error_message="429"),
    )
    other = HookPayload(
        tool_call=RegistryToolCall(name="fs.read_file", params={}, call_id="tc-2"),
    )
    decision = blocker.handle(LifecyclePoint.BEFORE_TOOL_EXEC, other)
    assert decision.action == "allow"


def test_rate_limit_blocker_skips_observation_on_success() -> None:
    """Success responses never seed the suppression window."""

    clock = _FakeClock(start=100.0)
    blocker = RateLimitBlocker(suppression_seconds=30.0, time_source=clock)

    blocker.handle(LifecyclePoint.AFTER_TOOL_EXEC, _payload("api.fetch"))
    decision = blocker.handle(
        LifecyclePoint.BEFORE_TOOL_EXEC,
        HookPayload(tool_call=RegistryToolCall(name="api.fetch", params={}, call_id="tc-2")),
    )
    assert decision.action == "allow"


# --- LockfileBlocker --------------------------------------------------------


def test_lockfile_blocker_detects_apt_pattern() -> None:
    """apt-get's «E: Could not get lock» message trips the blocker."""

    clock = _FakeClock(start=100.0)
    blocker = LockfileBlocker(suppression_seconds=5.0, time_source=clock)

    observed = _payload(
        "fs.run_bash",
        error_code="command_failed",
        error_message="E: Could not get lock /var/lib/dpkg/lock-frontend",
    )
    blocker.handle(LifecyclePoint.AFTER_TOOL_EXEC, observed)
    decision = blocker.handle(
        LifecyclePoint.BEFORE_TOOL_EXEC,
        HookPayload(tool_call=RegistryToolCall(name="fs.run_bash", params={}, call_id="tc-2")),
    )
    assert decision.action == "deny"
    assert "lockfile" in decision.reason


def test_lockfile_blocker_detects_git_lockfile() -> None:
    """git's ``.lock`` suffix on the index trips the blocker."""

    clock = _FakeClock(start=100.0)
    blocker = LockfileBlocker(suppression_seconds=5.0, time_source=clock)

    observed = _payload(
        "fs.run_bash",
        error_code="command_failed",
        error_message="fatal: Unable to create '/repo/.git/index.lock': File exists",
    )
    blocker.handle(LifecyclePoint.AFTER_TOOL_EXEC, observed)
    decision = blocker.handle(
        LifecyclePoint.BEFORE_TOOL_EXEC,
        HookPayload(tool_call=RegistryToolCall(name="fs.run_bash", params={}, call_id="tc-2")),
    )
    assert decision.action == "deny"


def test_lockfile_blocker_ignores_unrelated_failures() -> None:
    """Random ``command_failed`` without a lockfile signature stays observe-only."""

    clock = _FakeClock(start=100.0)
    blocker = LockfileBlocker(suppression_seconds=5.0, time_source=clock)

    observed = _payload(
        "fs.run_bash",
        error_code="command_failed",
        error_message="bash: command not found: foo",
    )
    blocker.handle(LifecyclePoint.AFTER_TOOL_EXEC, observed)
    decision = blocker.handle(
        LifecyclePoint.BEFORE_TOOL_EXEC,
        HookPayload(tool_call=RegistryToolCall(name="fs.run_bash", params={}, call_id="tc-2")),
    )
    assert decision.action == "allow"


@pytest.mark.parametrize(
    "message",
    [
        # Plain "filename ends in .lock" mention \u2014 not a contention error.
        "No such file or directory: Cargo.lock",
        # Permission error on a lockfile filename \u2014 not contention.
        "Permission denied: package-lock.json",
        # Missing-lockfile error \u2014 not contention.
        "Cargo.lock not found",
        # File-not-found mentioning the word "lock" but not contention.
        "ls: cannot access '/repo/.git/index.lock': No such file or directory",
    ],
)
def test_lockfile_blocker_does_not_false_positive_on_lock_filenames(message: str) -> None:
    """Bare ``.lock`` filename mentions do NOT trip the blocker.

    Devin-Review finding: the old regex included a bare ``\\.lock\\b``
    alternative which matched any error message naming a lock file
    rather than only contention. The tightened regex (PR #26 follow-up)
    matches only contention-specific signatures (``could not get lock``,
    ``unable to create *.lock``, ``blocking waiting for file lock``,
    ``resource temporarily unavailable``, ``another (instance|process)
    ... (lock|running)``). These four messages would have falsely
    tripped the gate before the fix \u2014 they must not now.
    """

    clock = _FakeClock(start=100.0)
    blocker = LockfileBlocker(suppression_seconds=5.0, time_source=clock)

    observed = _payload("fs.run_bash", error_code="command_failed", error_message=message)
    blocker.handle(LifecyclePoint.AFTER_TOOL_EXEC, observed)
    decision = blocker.handle(
        LifecyclePoint.BEFORE_TOOL_EXEC,
        HookPayload(tool_call=RegistryToolCall(name="fs.run_bash", params={}, call_id="tc-2")),
    )
    assert (
        decision.action == "allow"
    ), f"Lockfile blocker false-positive on non-contention message: {message!r}"


@pytest.mark.parametrize(
    "message",
    [
        # cargo contention signature.
        "Blocking waiting for file lock on package cache",
        # npm contention signature using "another process ... lock".
        "npm WARN another process is currently running and holding the lock",
        # cargo contention via "another instance ... running".
        "error: another instance of cargo is already running",
        # Generic POSIX file-lock contention.
        "pthread_mutex_lock: Resource temporarily unavailable",
    ],
)
def test_lockfile_blocker_catches_contention_specific_signatures(message: str) -> None:
    """The new contention-specific signatures still trip the blocker.

    Counterpart to ``does_not_false_positive_on_lock_filenames`` \u2014
    verifies the tightened regex still matches every real contention
    pattern the old regex caught (apt + git are already covered by
    the two pattern-named tests above; this fills in cargo / npm /
    generic).
    """

    clock = _FakeClock(start=100.0)
    blocker = LockfileBlocker(suppression_seconds=5.0, time_source=clock)

    observed = _payload("fs.run_bash", error_code="command_failed", error_message=message)
    blocker.handle(LifecyclePoint.AFTER_TOOL_EXEC, observed)
    decision = blocker.handle(
        LifecyclePoint.BEFORE_TOOL_EXEC,
        HookPayload(tool_call=RegistryToolCall(name="fs.run_bash", params={}, call_id="tc-2")),
    )
    assert (
        decision.action == "deny"
    ), f"Lockfile blocker missed contention-specific signature: {message!r}"
    assert "lockfile" in decision.reason


# --- AuthExpiredBlocker -----------------------------------------------------


def test_auth_expired_blocker_is_observe_only_by_default() -> None:
    """Default ``suppression_seconds=0`` → never gates, just observes.

    Until the T-2 LLM driver wires synthetic re-auth, gating on auth
    would prevent the LLM from seeing the auth state on its next turn.
    M-1 contract: the blocker observes the pattern (so future audit
    projection can surface it) but always allows the next call.
    """

    clock = _FakeClock(start=100.0)
    blocker = AuthExpiredBlocker(time_source=clock)
    assert blocker.suppression_seconds == 0.0

    observed = _payload(
        "api.fetch",
        error_code="auth_expired",
        error_message="HTTP 401 token expired",
    )
    blocker.handle(LifecyclePoint.AFTER_TOOL_EXEC, observed)
    decision = blocker.handle(
        LifecyclePoint.BEFORE_TOOL_EXEC,
        HookPayload(tool_call=RegistryToolCall(name="api.fetch", params={}, call_id="tc-2")),
    )
    assert decision.action == "allow"


def test_auth_expired_blocker_gates_when_opted_in() -> None:
    """Callers (e.g. tests, future re-auth wiring) can opt into gating."""

    clock = _FakeClock(start=100.0)
    blocker = AuthExpiredBlocker(suppression_seconds=10.0, time_source=clock)

    observed = _payload(
        "api.fetch",
        error_code="unauthorized",
        error_message="invalid credentials",
    )
    blocker.handle(LifecyclePoint.AFTER_TOOL_EXEC, observed)
    decision = blocker.handle(
        LifecyclePoint.BEFORE_TOOL_EXEC,
        HookPayload(tool_call=RegistryToolCall(name="api.fetch", params={}, call_id="tc-2")),
    )
    assert decision.action == "deny"
    assert "auth_expired" in decision.reason


# --- Base-class invariants --------------------------------------------------


def test_blocker_rejects_negative_suppression() -> None:
    """A negative suppression window is nonsensical — fail fast at construction."""

    with pytest.raises(ValueError, match="suppression_seconds"):
        RateLimitBlocker(suppression_seconds=-1.0)


def test_blocker_base_class_detect_is_not_implemented() -> None:
    """The base class raises rather than silently allowing every pattern."""

    blocker = BlockerMiddleware()
    payload = _payload("api.fetch", error_code="rate_limited", error_message="429")
    with pytest.raises(NotImplementedError):
        blocker.handle(LifecyclePoint.AFTER_TOOL_EXEC, payload)


def test_blocker_categories_are_distinct() -> None:
    """Each blocker subclass declares a distinct category for audit routing."""

    assert RateLimitBlocker().category is BlockerCategory.RATE_LIMIT
    assert LockfileBlocker().category is BlockerCategory.LOCKFILE
    assert AuthExpiredBlocker().category is BlockerCategory.AUTH_EXPIRED


# --- Integration: blockers inside run_session -------------------------------


def test_blockers_are_dormant_on_baseline_smoke(tmp_path) -> None:
    """End-to-end: a clean smoke run with all three blockers wired emits
    only ``decision: observed`` rows for them — no denials, no
    spurious ``hook_decision: deny``. This is the contract that lets
    us ship the blockers in M-1 even though the baseline tools never
    trigger them.
    """

    workspace = tmp_path
    (workspace / "input.txt").write_text("hello\n", encoding="utf-8")
    log = EventLog(workspace / ".fa" / "events.jsonl")
    registry = build_baseline_registry(workspace)
    hooks = HookRegistry()
    hooks.register(RateLimitBlocker(suppression_seconds=30.0))
    hooks.register(LockfileBlocker(suppression_seconds=5.0))
    hooks.register(AuthExpiredBlocker())
    state = SessionState(workspace_root=workspace, run_id="t", log=log)
    calls = (
        ToolCall(name="fs.read_file", params={"path": "input.txt"}, call_id="tc-1"),
        ToolCall(
            name="fs.write_file",
            params={"path": "out.txt", "content": "x\n"},
            call_id="tc-2",
        ),
    )

    results = run_session(calls, registry=registry, hooks=hooks, state=state)

    assert all(r.error is None for r in results), [(r.summary, r.error) for r in results]
    # Three blocker dispatch records per call (BEFORE) + three per call
    # (AFTER) — none are denies. The trace inspection asserts both the
    # absence of denies AND the presence of observe-only records, so a
    # regression that disables the blockers (zero records) also fails.
    blocker_records = [r for r in hooks.dispatch_trace if r.middleware.startswith("blocker:")]
    assert blocker_records, "expected blocker dispatch records, found none"
    assert all(r.decision in ("allow", "observed") for r in blocker_records), [
        (r.middleware, r.decision) for r in blocker_records
    ]


def _build_baseline_registry_for_lockfile(workspace):
    """Use the real registry; the lockfile test injects a synthetic
    failing tool via the registry's dispatch handler."""

    return build_baseline_registry(workspace)


def test_lockfile_blocker_denies_second_run_after_lockfile_failure(tmp_path) -> None:
    """End-to-end: tool-call 1 fails with a lockfile message, the
    blocker observes it at AFTER_TOOL_EXEC, and tool-call 2 (same
    tool) is denied at BEFORE_TOOL_EXEC. Asserts the
    ``run_stopped`` row + the preserved tc-1 result.
    """

    workspace = tmp_path
    log = EventLog(workspace / ".fa" / "events.jsonl")
    registry = build_baseline_registry(workspace)
    # Replace the ``fs.run_bash`` handler with one that emits a
    # lockfile signature — the baseline ``apt-get update`` is hard
    # to trigger reliably inside a unit test, and the blocker
    # operates on ``ToolResult.error.message`` regardless of the
    # underlying tool body. ``dataclasses.replace`` returns a fresh
    # frozen ``ToolSpec``; the registry stores tools in
    # ``_tools`` so we swap directly (the public API has no
    # `replace_tool` and the registry is constructed-per-test).
    import dataclasses

    from fa.inner_loop.registry import ToolError as _ToolError
    from fa.inner_loop.registry import ToolResult as _ToolResult

    def _failing_handler(params):
        del params
        return _ToolResult(
            summary="lockfile contention",
            error=_ToolError(
                code="command_failed",
                message="E: Could not get lock /var/lib/dpkg/lock-frontend",
                retryable=True,
            ),
        )

    spec = registry._tools["fs.run_bash"]
    registry._tools["fs.run_bash"] = dataclasses.replace(spec, handler=_failing_handler)

    hooks = HookRegistry()
    hooks.register(LockfileBlocker(suppression_seconds=5.0))
    state = SessionState(workspace_root=workspace, run_id="t", log=log)
    calls = (
        ToolCall(name="fs.run_bash", params={"command": "apt-get update"}, call_id="tc-1"),
        ToolCall(name="fs.run_bash", params={"command": "apt-get update"}, call_id="tc-2"),
    )

    results = run_session(calls, registry=registry, hooks=hooks, state=state)

    # tc-1 ran and failed (lockfile failure); tc-2 was denied at
    # BEFORE_TOOL_EXEC. PR #24 BUG-0001 (``loop.py:98-103``)
    # converts the BEFORE-deny into a synthetic ``hook_deny`` result
    # and ``continue``s the loop — there's no ``run_stopped`` row for
    # BEFORE-deny (that's reserved for BETWEEN_ROUNDS / AFTER deny).
    assert len(results) == 2, [(r.summary, r.error and r.error.code) for r in results]
    assert results[0].error is not None and results[0].error.code == "command_failed"
    assert "Could not get lock" in results[0].error.message
    assert results[1].error is not None and results[1].error.code == "hook_deny"
    assert "lockfile" in results[1].error.message
    decisions = [
        (r.middleware, r.decision)
        for r in hooks.dispatch_trace
        if r.middleware == "blocker:lockfile"
    ]
    assert ("blocker:lockfile", "deny") in decisions, decisions
