"""Tests for the M-8 LLM-driven coder loop (fa.inner_loop.coder_loop).

The test surface exercises each terminal state of :func:`drive_session`
against a deterministic fake provider — no real HTTP, no real LLM,
no real time. The fake `FakeProvider` records every :class:`RequestInfo`
it sees so tests can assert the message-history shape, the rendered
tool-spec payload, and the per-turn observation feedback.

Per the FA-ABC synthesis deep-dive §3 I-2, the driver's A-bucket
residue (system prompt, tool-spec projection, message-history
construction) is deterministic; tests pin that determinism by
asserting on the exact request body the FakeProvider receives.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.coder_loop import (
    DEFAULT_MAX_TURNS,
    SessionOutcome,
    drive_session,
)
from fa.inner_loop.hooks import (
    Decision,
    GuardMiddleware,
    HookPayload,
    HookRegistry,
    LifecyclePoint,
    PauseGuard,
    SandboxHook,
)
from fa.inner_loop.registry import ToolRegistry, ToolSpec
from fa.inner_loop.runtime_limits import RuntimeLimits
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.tools import build_baseline_registry
from fa.providers.base import RequestInfo, ResponseInfo
from fa.providers.chain import ChainConfig, ChainEntry, ProviderChain
from fa.providers.errors import (
    ProviderRequestShapeError,
    ProviderTransientError,
)


class FakeProvider:
    """Duck-typed :class:`fa.providers.base.Provider` for offline tests.

    ``script`` is a list of items the provider returns or raises in order:
    a :class:`ResponseInfo` is returned; an :class:`Exception` is raised.
    Records every observed :class:`RequestInfo` on ``self.calls`` so
    tests assert on message-history shape and rendered tool payload.
    """

    name = "fake"

    def __init__(self, script: list[ResponseInfo | Exception]) -> None:
        self._script = list(script)
        self.calls: list[RequestInfo] = []

    def request(
        self,
        request: RequestInfo,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        extra_headers: Mapping[str, str],
    ) -> ResponseInfo:
        self.calls.append(request)
        if not self._script:
            raise ProviderTransientError(
                "fake provider script exhausted",
                status=503,
                kind="service_unavailable",
            )
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _make_chain(provider: FakeProvider) -> ProviderChain:
    entry = ChainEntry(
        provider="openrouter",
        slug="test/model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_KEY",
    )
    config = ChainConfig(role="coder", model="test-model", family="", chain=(entry,))
    return ProviderChain(
        config,
        provider_factory=lambda _e: provider,
        env={"TEST_KEY": "k"},
    )


def _make_state(tmp_path: Path) -> SessionState:
    log = EventLog(tmp_path / "events.jsonl", run_id="t")
    return SessionState(workspace_root=tmp_path, run_id="t", log=log)


def _make_response(
    *,
    text: str = "",
    finish_reason: str = "stop",
    tool_calls: tuple[Mapping[str, Any], ...] = (),
    in_tokens: int = 10,
    out_tokens: int = 5,
) -> ResponseInfo:
    return ResponseInfo(
        text=text,
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        finish_reason=finish_reason,
        tool_calls=tool_calls,
    )


def _registry_with_dummy_tool() -> ToolRegistry:
    """Registry with a single ``echo`` tool that records params and returns them."""

    registry = ToolRegistry()

    def _echo_handler(params: Mapping[str, Any]) -> Any:
        from fa.inner_loop.registry import ToolResult

        return ToolResult(summary=f"echo {params.get('text', '')}", result=dict(params))

    spec = ToolSpec(
        name="echo",
        description="Echo back the given text.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        handler=_echo_handler,
        permission="read",
    )
    registry.register(spec)
    return registry


# -- Happy path --------------------------------------------------------------


def test_drive_session_completes_when_llm_signals_done(tmp_path: Path) -> None:
    provider = FakeProvider([_make_response(text="all done", finish_reason="stop")])
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    outcome = drive_session(
        "do nothing",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert outcome == SessionOutcome(
        exit_code=0,
        stop_reason="stopped_by_llm",
        turns=1,
        final_text="all done",
        tool_results=(),
    )
    assert len(provider.calls) == 1
    request = provider.calls[0]
    assert request.messages[0]["role"] == "system"
    assert request.messages[1]["role"] == "user"
    assert request.messages[1]["content"] == "do nothing"


# -- Tool-call dispatch ------------------------------------------------------


def test_drive_session_dispatches_tool_calls_then_completes(tmp_path: Path) -> None:
    tool_call_emit = {
        "id": "tc-1",
        "type": "function",
        "function": {"name": "echo", "arguments": '{"text": "hi"}'},
    }
    provider = FakeProvider(
        [
            _make_response(finish_reason="tool_calls", tool_calls=(tool_call_emit,)),
            _make_response(text="echoed", finish_reason="stop"),
        ]
    )
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    outcome = drive_session(
        "echo hi",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert outcome.exit_code == 0
    assert outcome.stop_reason == "stopped_by_llm"
    assert outcome.turns == 2
    assert len(outcome.tool_results) == 1
    assert outcome.tool_results[0].summary == "echo hi"
    # The follow-up request must carry the tool-role observation.
    follow_up = provider.calls[1]
    tool_messages = [m for m in follow_up.messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "tc-1"
    assert tool_messages[0]["content"] == "echo hi"


# -- Iteration cap -----------------------------------------------------------


def test_drive_session_hits_iteration_cap(tmp_path: Path) -> None:
    looping_call = {
        "id": "tc-loop",
        "type": "function",
        "function": {"name": "echo", "arguments": '{"text": "again"}'},
    }
    # Always emit the same tool call so the loop never terminates on its own.
    provider = FakeProvider(
        [_make_response(finish_reason="tool_calls", tool_calls=(looping_call,)) for _ in range(20)]
    )
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    outcome = drive_session(
        "loop forever",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=3,
    )

    assert outcome.exit_code == 1
    assert outcome.stop_reason == "iteration_cap"
    assert outcome.turns == 3
    assert len(provider.calls) == 3


# -- Provider chain failure modes -------------------------------------------


def test_drive_session_chain_exhausted_returns_exit_two(tmp_path: Path) -> None:
    provider = FakeProvider([ProviderTransientError("503", status=503, kind="service_unavailable")])
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    outcome = drive_session(
        "boom",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert outcome.exit_code == 2
    assert outcome.stop_reason == "chain_exhausted"
    assert outcome.turns == 1


def test_drive_session_request_shape_error_returns_exit_two(tmp_path: Path) -> None:
    provider = FakeProvider([ProviderRequestShapeError("bad body", status=400)])
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    outcome = drive_session(
        "boom",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert outcome.exit_code == 2
    assert outcome.stop_reason == "request_shape"


# -- Abnormal finish_reason --------------------------------------------------


def test_drive_session_abnormal_stop_surfaces_finish_reason(tmp_path: Path) -> None:
    provider = FakeProvider([_make_response(text="cut off", finish_reason="length")])
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    outcome = drive_session(
        "truncated",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert outcome.exit_code == 1
    assert outcome.stop_reason == "abnormal_stop:length"
    assert outcome.final_text == "cut off"


# -- Tool-spec rendering into the request body ------------------------------


def test_drive_session_renders_tool_specs_into_request(tmp_path: Path) -> None:
    provider = FakeProvider([_make_response(text="ok", finish_reason="stop")])
    chain = _make_chain(provider)
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    drive_session(
        "list",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    request = provider.calls[0]
    tool_names = {tool["function"]["name"] for tool in request.tools}
    assert {"fs.read_file", "fs.write_file", "fs.run_bash"}.issubset(tool_names)
    # Every projected tool keeps its schema verbatim from ToolSpec.
    for tool in request.tools:
        assert tool["type"] == "function"
        assert "parameters" in tool["function"]


# -- Malformed tool-call arguments -------------------------------------------


def test_drive_session_handles_malformed_tool_arguments(tmp_path: Path) -> None:
    malformed = {
        "id": "tc-bad",
        "type": "function",
        "function": {"name": "echo", "arguments": "{not json"},
    }
    provider = FakeProvider(
        [
            _make_response(finish_reason="tool_calls", tool_calls=(malformed,)),
            _make_response(text="recovered", finish_reason="stop"),
        ]
    )
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    outcome = drive_session(
        "echo broken",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    # Driver does not crash; registry surfaces invalid_params; LLM sees
    # the observation on the next turn and signals stop.
    assert outcome.exit_code == 0
    assert outcome.stop_reason == "stopped_by_llm"
    assert outcome.tool_results[0].error is not None


# -- events.jsonl audit trail ------------------------------------------------


def test_drive_session_writes_user_and_model_msg_rows(tmp_path: Path) -> None:
    provider = FakeProvider([_make_response(text="hello", finish_reason="stop")])
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    drive_session(
        "greet",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    events_path = tmp_path / "events.jsonl"
    rows = [line for line in events_path.read_text().splitlines() if line.strip()]
    kinds = []
    for row in rows:
        import json

        kinds.append(json.loads(row)["kind"])
    assert "user_msg" in kinds
    assert "model_msg" in kinds
    assert "run_started" in kinds


def test_drive_session_default_max_turns_constant_is_stable() -> None:
    # Snapshot guard: bumping the default silently would relax replay
    # determinism in CI; require the bump to be intentional via a
    # failing test that surfaces the diff.
    assert DEFAULT_MAX_TURNS == 16


def test_drive_session_raises_when_state_log_unset(tmp_path: Path) -> None:
    provider = FakeProvider([_make_response(text="x", finish_reason="stop")])
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    state = SessionState(workspace_root=tmp_path, run_id="t", log=None)
    state.log = None

    with pytest.raises(ValueError, match=r"SessionState\.log"):
        drive_session(
            "x",
            provider_chain=chain,
            registry=registry,
            hooks=hooks,
            state=state,
        )


def test_drive_session_respects_custom_runtime_limits(tmp_path: Path) -> None:
    provider = FakeProvider([_make_response(text="done", finish_reason="stop")])
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    custom_limits = RuntimeLimits.anchored_defaults()
    outcome = drive_session(
        "x",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
        limits=custom_limits,
    )

    assert outcome.exit_code == 0


# -- Batch truncation (run_session max_iterations < tool_calls) --------------


def test_drive_session_pads_truncated_tool_calls(tmp_path: Path) -> None:
    """If the LLM emits more tool calls than run_session's max_iterations
    allows in a single batch, the driver must pad synthetic failures so
    the OpenAI function-calling protocol stays valid (every tool_call_id
    needs a matching role="tool" message).
    """
    tool_calls = [
        {
            "id": f"tc-{i}",
            "type": "function",
            "function": {
                "name": "echo",
                "arguments": f'{{"text": "call-{i}"}}',
            },
        }
        for i in range(3)
    ]
    provider = FakeProvider(
        [
            _make_response(finish_reason="tool_calls", tool_calls=tuple(tool_calls)),
            _make_response(text="done", finish_reason="stop"),
        ]
    )
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    # max_iterations=2 means run_session stops after the 2nd call.
    limits = RuntimeLimits(max_iterations=2)
    outcome = drive_session(
        "batch",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
        limits=limits,
    )

    # Turn 1: LLM emits 3 calls, run_session only processes 2.
    # Turn 2: LLM sees the 2 real results + 1 synthetic failure.
    assert outcome.exit_code == 0
    assert outcome.turns == 2
    # The second (follow-up) request must contain exactly 3 tool
    # messages so the conversation shape is protocol-valid.
    follow_up = provider.calls[1]
    tool_messages = [m for m in follow_up.messages if m.get("role") == "tool"]
    assert len(tool_messages) == 3
    # The 3rd message must be the synthetic failure, not silently absent.
    assert "iteration limit" in tool_messages[2]["content"]

    # events.jsonl must have 3 tool_result rows (2 real + 1 synthetic).
    events_path = tmp_path / "events.jsonl"
    kinds = [
        json.loads(line)["kind"] for line in events_path.read_text().splitlines() if line.strip()
    ]
    assert kinds.count("tool_result") == 3


# -- KeyboardInterrupt terminal path -----------------------------------------


def test_drive_session_keyboard_interrupt_returns_outcome(
    tmp_path: Path,
) -> None:
    """Ctrl+C during the LLM request must not crash the process; it must
    return a typed SessionOutcome with exit_code 130 (standard Unix SIGINT).
    """

    class InterruptProvider:
        name = "interrupt"

        def request(
            self,
            request: RequestInfo,
            *,
            base_url: str,
            api_key: str,
            timeout_seconds: float,
            extra_headers: Mapping[str, str],
        ) -> ResponseInfo:
            raise KeyboardInterrupt()

    entry = ChainEntry(
        provider="openrouter",
        slug="test/model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_KEY",
    )
    config = ChainConfig(role="coder", model="test-model", family="", chain=(entry,))
    chain = ProviderChain(
        config,
        provider_factory=lambda _e: InterruptProvider(),
        env={"TEST_KEY": "k"},
    )
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    outcome = drive_session(
        "interrupt me",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert outcome.exit_code == 130
    assert outcome.stop_reason == "abnormal_stop:interrupt"
    assert outcome.turns == 1
    assert outcome.final_text == ""

    events_path = tmp_path / "events.jsonl"
    kinds = [
        json.loads(line)["kind"] for line in events_path.read_text().splitlines() if line.strip()
    ]
    assert "run_stopped" in kinds
    assert "abnormal_stop:interrupt" in events_path.read_text()


# -- BEFORE_LLM_CALL / AFTER_LLM_CALL guard denial --------------------------------


class _DenyBeforeLlmCallGuard(GuardMiddleware):
    name = "deny_before_llm_call"
    attaches_to = (LifecyclePoint.BEFORE_LLM_CALL,)

    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point, payload
        return Decision.deny("mock before_llm_call deny")


class _DenyAfterLlmCallGuard(GuardMiddleware):
    name = "deny_after_llm_call"
    attaches_to = (LifecyclePoint.AFTER_LLM_CALL,)

    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point, payload
        return Decision.deny("mock after_llm_call deny")


def test_drive_session_before_llm_call_guard_deny_returns_outcome(
    tmp_path: Path,
) -> None:
    """A GuardMiddleware denying at BEFORE_LLM_CALL must return a typed
    SessionOutcome with exit_code 1, not propagate the raw PermissionError."""
    provider = FakeProvider([_make_response(text="never reached", finish_reason="stop")])
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    hooks.register(_DenyBeforeLlmCallGuard())
    state = _make_state(tmp_path)

    outcome = drive_session(
        "do nothing",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert outcome.exit_code == 1
    assert outcome.stop_reason == "hook_deny:BEFORE_LLM_CALL"
    assert outcome.turns == 1

    events_path = tmp_path / "events.jsonl"
    kinds = [
        json.loads(line)["kind"] for line in events_path.read_text().splitlines() if line.strip()
    ]
    assert "run_stopped" in kinds
    assert "hook_deny:BEFORE_LLM_CALL" in events_path.read_text()


def test_drive_session_after_llm_call_guard_deny_returns_outcome(
    tmp_path: Path,
) -> None:
    """A GuardMiddleware denying at AFTER_LLM_CALL must return a typed
    SessionOutcome with exit_code 1. Unlike BEFORE_LLM_CALL, the model
    message has already been appended to messages and state.log."""
    provider = FakeProvider([_make_response(text="partial", finish_reason="stop")])
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    hooks.register(_DenyAfterLlmCallGuard())
    state = _make_state(tmp_path)

    outcome = drive_session(
        "do nothing",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert outcome.exit_code == 1
    assert outcome.stop_reason == "hook_deny:AFTER_LLM_CALL"
    assert outcome.turns == 1

    # AFTER_LLM_CALL fires immediately after provider_chain.request()
    # returns but BEFORE the assistant message / model_msg are appended.
    # A deny here therefore skips the model_msg (consistent with the
    # guard-deny "stop immediately" pattern).
    assert len(provider.calls) == 1
    events_path = tmp_path / "events.jsonl"
    text = events_path.read_text()
    assert "model_msg" not in text
    assert "hook_deny:AFTER_LLM_CALL" in text


# -- Synthetic padding uses real guard stop reason ---------------------------


class _DenyAfterRound2Guard(GuardMiddleware):
    """Denies at BETWEEN_ROUNDS starting from the second iteration."""

    name = "deny_after_round_2"
    attaches_to = (LifecyclePoint.BETWEEN_ROUNDS,)

    def __init__(self) -> None:
        self._count = 0

    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point, payload
        self._count += 1
        if self._count >= 2:
            return Decision.deny("mock round-2 deny")
        return Decision.allow()


def test_drive_session_synthetic_padding_uses_guard_reason(
    tmp_path: Path,
) -> None:
    """When run_session stops early because of a guard denial (not iteration
    cap), the synthetic padding message must carry the guard reason, not
    the generic 'iteration limit exceeded' text."""
    looping_call = {
        "id": "tc-loop",
        "type": "function",
        "function": {"name": "echo", "arguments": '{"text": "again"}'},
    }
    # Turn 1: tool call executes. Turn 2: guard denies at BETWEEN_ROUNDS.
    provider = FakeProvider(
        [
            _make_response(finish_reason="tool_calls", tool_calls=(looping_call,)),
            _make_response(finish_reason="tool_calls", tool_calls=(looping_call,)),
        ]
    )
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    hooks.register(_DenyAfterRound2Guard())
    state = _make_state(tmp_path)

    outcome = drive_session(
        "loop",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
        max_turns=3,
    )

    # The guard deny happened inside run_session (BETWEEN_ROUNDS);
    # drive_session itself did not terminate, so the session continued
    # until max_turns was reached or the provider script exhausted.
    # What we care about is the synthetic padding message content.

    # The synthetic padding is appended to ``messages`` AFTER the Turn 2
    # provider response. It appears in the Turn 3 request captured by
    # the fake provider (even though the provider script is exhausted).
    assert len(provider.calls) == 3
    turn3_request = provider.calls[2]
    tool_messages = [m for m in turn3_request.messages if m.get("role") == "tool"]
    # Turn 1 produced a real tool result; Turn 2 produced a synthetic one.
    assert len(tool_messages) == 2
    # The synthetic padding (last tool message) must carry the guard reason.
    assert "mock round-2 deny" in tool_messages[-1]["content"]
    assert "iteration limit" not in tool_messages[-1]["content"].lower()

    events_path = tmp_path / "events.jsonl"
    text = events_path.read_text()
    assert "run_stopped" in text
    assert "mock round-2 deny" in text
    assert "tool_result" in text


# -- Provider attempt telemetry -----------------------------------------------


def test_drive_session_logs_provider_attempts(
    tmp_path: Path,
) -> None:
    """``provider_chain.request`` returns a ``ChainAttemptRecord`` list
    in ``_attempts``; ``drive_session`` must write each record to
    ``events.jsonl`` so the audit trail is complete."""
    provider = FakeProvider([_make_response(text="done", finish_reason="stop")])
    chain = _make_chain(provider)
    registry = _registry_with_dummy_tool()
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    outcome = drive_session(
        "task",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert outcome.exit_code == 0
    assert state.log is not None
    events = state.log.read_all()
    provider_attempts = [e for e in events if e.kind == "provider_attempt"]
    assert len(provider_attempts) == 1
    assert provider_attempts[0].content["provider"] == "openrouter"
    assert provider_attempts[0].content["slug"] == "test/model"
    assert provider_attempts[0].content["status"] == 200
    assert provider_attempts[0].content.get("error") is None
