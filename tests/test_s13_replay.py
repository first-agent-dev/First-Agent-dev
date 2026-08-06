"""S13.2 — I-52: faithful history replay of ``user_msg`` rows.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md``
§S13.2.

**Why.** The coder-loop history rebuild (``coder_loop.py:450-490``) mapped only
``model_msg``→assistant and ``tool_result``→tool, silently dropping ``user_msg``
rows. A resumed stage therefore inherited the prior stage's assistant/tool turns
**without** the instruction they were answering. This test boots the real
``drive_session`` root against a log that already contains a prior stage's
``user_msg`` + ``model_msg`` (the resume shape) and asserts the outgoing request
carries BOTH the prior instruction (replayed, CT1) and the current stage's task.

**Tests labelled per tests-writing skill:** C1 (composition root
``drive_session``, mock provider I/O, real EventLog/SessionState/HookRegistry).

**Kill-check:** K7 — revert the ``user_msg`` replay in ``coder_loop.py`` ⇒ the
prior instruction is absent from the outgoing request and this test fails.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.state import EventLog, SessionState
from fa.providers.base import RequestInfo, ResponseInfo
from fa.providers.chain import ChainConfig, ChainEntry, ProviderChain
from fa.providers.errors import ProviderTransientError


class _FakeProvider:
    """Duck-typed provider that records every RequestInfo (no real HTTP)."""

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
        transport_retries: int,
        extra_headers: Mapping[str, str],
    ) -> ResponseInfo:
        del base_url, api_key, timeout_seconds, transport_retries, extra_headers
        self.calls.append(request)
        if not self._script:
            raise ProviderTransientError("fake provider script exhausted", status=503)
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _make_chain(provider: _FakeProvider) -> ProviderChain:
    entry = ChainEntry(
        provider="openrouter",
        model="test/model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_KEY",
        cooldown_seconds=300,
    )
    config = ChainConfig(role="coder", name="test-model", family="", chain=(entry,))
    return ProviderChain(config, provider_factory=lambda _e: provider, env={"TEST_KEY": "k"})


def _make_state(tmp_path: Path) -> SessionState:
    log = EventLog(tmp_path / "events.jsonl", run_id="t")
    return SessionState(workspace_root=tmp_path, run_id="t", log=log)


def _make_response(text: str = "done") -> ResponseInfo:
    return ResponseInfo(
        text=text,
        in_tokens=10,
        out_tokens=5,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        finish_reason="stop",
        tool_calls=(),
    )


def _prepopulate_prior_stage(log: EventLog) -> None:
    """Write a prior stage's rows the way stage 1 (planner) would have.

    Chronological order matters: the ``user_msg`` precedes the ``model_msg`` it
    provoked, exactly as the planner would have persisted them.
    """
    log.append(
        actor="user",
        kind="user_msg",
        content={"text": "PRIOR_INSTRUCTION add a docstring to one small function"},
    )
    log.append(
        actor="model",
        kind="model_msg",
        content={
            "text": "# Prior plan: add docstring to iter_yaml_lines",
            "tool_calls": None,
            "finish_reason": "stop",
            "in_tokens": 1,
            "out_tokens": 1,
        },
    )


def test_resumed_transcript_replays_prior_user_msg(tmp_path: Path) -> None:
    """C1 — a resumed stage's outgoing request contains the prior user instruction.

    This is CT1: the history FA rebuilds for a resumed stage must be *faithful* —
    it must include the instruction the inherited assistant/tool turns were
    answering, not only those turns themselves.
    """
    provider = _FakeProvider([_make_response(text="all done")])
    chain = _make_chain(provider)
    registry = ToolRegistry()
    hooks = HookRegistry()
    state = _make_state(tmp_path)
    log = state.log
    assert log is not None
    _prepopulate_prior_stage(log)

    outcome = drive_session(
        "CURRENT_TASK finish the docstring",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert outcome.exit_code == 0
    assert outcome.stop_reason == "stopped_by_llm"
    request = provider.calls[0]

    user_contents = [str(m["content"]) for m in request.messages if m["role"] == "user"]

    # The prior stage's user instruction is replayed (CT1 / I-52).
    assert any("PRIOR_INSTRUCTION" in c for c in user_contents), (
        f"prior stage's user instruction was NOT replayed into the resumed transcript: {user_contents}"
    )

    # The current stage's task is also present (CT2 / I-50 path).
    assert any("Task: CURRENT_TASK" in c for c in user_contents), (
        f"current stage task missing from resumed transcript: {user_contents}"
    )

    # Sanity: prior instruction precedes the current task in the message stream
    # (chronological replay + task-last for an assistant-final history).
    prior_idx = next(i for i, c in enumerate(user_contents) if "PRIOR_INSTRUCTION" in c)
    task_idx = next(i for i, c in enumerate(user_contents) if "Task: CURRENT_TASK" in c)
    assert prior_idx < task_idx


def test_dangling_tool_resume_returns_request_shape_not_traceback(tmp_path: Path) -> None:
    """C1 — a resumed history ending on an orphaned tool-call is a graceful request_shape.

    Regression for a non-obvious failure mode: before S13.4, an interrupted prior
    stage whose last `model_msg` carried tool_calls but whose `tool_result` was never
    persisted would rebuild a history ending on an assistant-with-tool_calls. The
    composer's dangling-tool check raised, but it happened OUTSIDE the
    provider-request try block, so `_cmd_run` (which catches only RuntimeError)
    would crash with an uncaught traceback. Now it must return the graceful
    `request_shape` outcome (exit 2), the same as a provider-returned 400.
    """
    provider = _FakeProvider([_make_response(text="unused")])  # must NOT be reached
    chain = _make_chain(provider)
    state = _make_state(tmp_path)
    log = state.log
    assert log is not None
    # A prior stage that called a tool but whose result was never recorded:
    log.append(
        actor="model",
        kind="model_msg",
        content={
            "text": "",
            "tool_calls": [{"id": "tc-orphan", "function": {"name": "fs_read", "arguments": "{}"}}],
            "finish_reason": "tool_calls",
            "in_tokens": 1,
            "out_tokens": 1,
        },
    )

    outcome = drive_session(
        "finish the task",
        provider_chain=chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
    )

    # Graceful request-shape failure, NOT an uncaught traceback / crash.
    assert outcome.exit_code == 2
    assert outcome.stop_reason == "request_shape"
    # The provider was never reached (fail locally, before HTTP).
    assert provider.calls == []
