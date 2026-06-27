"""LLM-driven coder loop (M-8) — the missing LLM ↔ tools bridge.

This is the v0.1 acceptance surface for ``fa run``. It bridges the
:class:`fa.providers.chain.ProviderChain` (which makes the LLM call
and handles per-provider fallback) and
:func:`fa.inner_loop.loop.run_session` (which dispatches tool calls
through the HookRegistry). Without this bridge ``run_session``
consumes only pre-built ``ToolCall`` sequences and the substrate is
undrivable by a real model — see ``release-roadmap-post-m2.md`` §M4.

Per-turn loop (one iteration === one LLM round-trip):

1. Dispatch ``BEFORE_LLM_CALL`` middleware (ObserverMiddleware in
   v0.1; LLM-using GuardMiddleware would require family-disjoint
   plumbing through the chain, deferred to M5+).
2. Build a :class:`fa.providers.base.RequestInfo` from the running
   message list plus the mechanically-projected tool spec list.
3. Call ``provider_chain.request(req)`` — the chain handles
   per-attempt fallback and cooldown bookkeeping internally,
   returning a :class:`fa.providers.base.ResponseInfo` plus per-
   attempt trace records.
4. Dispatch ``AFTER_LLM_CALL`` middleware.
5. Append the assistant turn (text + tool_calls) to the message
   list AND to events.jsonl as a ``model_msg`` row.
6. If the response carries tool_calls: parse each (closed-set JSON
   decode, no LLM judgement), build a :class:`ToolCall` per entry,
   pass the whole batch through ``run_session`` so the existing
   BEFORE/AFTER_TOOL_EXEC hooks fire. Append each tool result as
   a ``tool``-role observation message for the next LLM turn.
7. If no tool_calls AND ``finish_reason`` is terminal → exit the
   loop with ``stopped_by_llm``.
8. If turn count reaches ``max_turns`` → exit with
   ``iteration_cap``.

Provider-agnostic by design: every adapter normalises ``tool_calls``
to the canonical OpenAI ``{id, type:"function", function:{name,
arguments:str}}`` shape (see
:func:`fa.providers.openai_compat._normalize_success` +
:func:`fa.providers.anthropic._normalize_success`). The driver's
:func:`_build_tool_calls` parses that one shape only.

Determinism guards (deep-dive §3 I-5 — deterministic post-LLM
filter): malformed ``arguments`` JSON, missing ``name`` field, or
non-mapping params collapse to a synthetic ``ToolCall`` whose
registry validation produces the canonical ``invalid_params``
error row rather than the driver itself raising. The LLM sees the
error on the next turn and can correct.

References:
- knowledge/adr/ADR-9-llm-provider-client.md §2 (chain runtime),
  §4 (Tier-1 / Tier-2 observability), §5 (canonical request /
  response shapes).
- knowledge/adr/ADR-8-hook-registry.md §1 (lifecycle order),
  §3 (first-deny short-circuit + GuardMiddleware contract).
- knowledge/adr/ADR-7-inner-loop-tool-registry.md §2 (ToolSpec /
  ToolCall / ToolResult contract), §7 (events.jsonl kinds),
  §Amendment 2026-05-20 rule 2 (max_iterations from
  ~/.fa/config.yaml, never code constants).
- knowledge/research/fa-abc-synthesis-deep-dive-2026-05.md §3
  I-2 (A-bucket residue), I-4 (typed loop-state ownership),
  I-5 (deterministic post-LLM filter).
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.hooks.base import HookPayload, HookRegistry, LifecyclePoint
from fa.inner_loop.loop import run_session
from fa.inner_loop.projection import project_for_model
from fa.inner_loop.prompt import (
    build_system_message,
    render_tool_specs,
)
from fa.inner_loop.registry import ToolCall, ToolRegistry, ToolResult, ToolSpec
from fa.inner_loop.runtime_limits import RuntimeLimits
from fa.inner_loop.state import SessionState
from fa.observability.redaction import SecretRedactor
from fa.output import EventBus, OutputEvent
from fa.providers.base import RequestInfo, ResponseInfo
from fa.providers.chain import ProviderChain
from fa.providers.errors import (
    ProviderChainExhaustedError,
    ProviderRequestShapeError,
)

# Default LLM-turn cap. Distinct from :attr:`RuntimeLimits.max_iterations`
# which counts *tool calls* across one ``run_session`` invocation; one
# LLM turn may emit multiple tool calls so the two caps are
# independent. Anchored at 16 — small enough to bound runaway loops on
# a confused model, large enough that a multi-step UC1 demo
# (read → write → verify → run) completes without truncation.
DEFAULT_MAX_TURNS = 16

# ``finish_reason`` values that signal the LLM intends to end its turn
# cleanly (not via iteration cap, not via content_filter / length cap).
# Both adapters normalise into one of these per
# :data:`fa.providers.anthropic._STOP_REASON_MAP`.
_TERMINAL_FINISH_REASONS: frozenset[str] = frozenset({"stop", "end_turn"})

# Default sampling temperature. T=0.0 keeps the v0.1 loop deterministic for
# replay; ADR-7 §Amendment 2026-05-20 rule 3's T=1.0-on-retry is a *retry*
# policy, not a first-attempt policy, and only applies once the
# FailureClassifierObserver fires. The CLI overrides this per role (the coder
# role uses DEFAULT_CODER_TEMPERATURE for slightly less rigid edits).
DEFAULT_TEMPERATURE = 0.0

# Coder-role first-attempt temperature. A small amount of sampling (0.2) gives
# the coder room for non-degenerate edits while staying close to deterministic.
# Planner/eval keep T=0.0. See fa.cli._cmd_run for the per-role selection.
DEFAULT_CODER_TEMPERATURE = 0.2

# Default max output tokens per turn. Sized for modern long-context reasoning
# models (e.g. the Fireworks lineup in models.yaml.example) so multi-tool-call
# turns and long reasoning are not truncated; a runaway emission still surfaces
# via the ``abnormal_stop:length`` outcome.
DEFAULT_MAX_TOKENS = 64000


def _redact(redactor: SecretRedactor | None, text: str) -> str:
    """Mask known secret values in model-facing tool output (ADR-12 B2).

    This is the single egress chokepoint between tool results and the LLM
    message stream (pi-style input-side redaction). Even if a tool returns a
    secret value (e.g. the deploy key read via some path the gate missed), it
    is masked — in raw, base64, hex, and url-encoded forms — before it can
    reach the provider and therefore before the model can ever repeat it.
    """
    if redactor is None:
        return text
    return redactor.redact(text)


def _usage_event_content(response: ResponseInfo) -> dict[str, int]:
    return {
        "input_tokens": response.in_tokens,
        "cache_read_input_tokens": response.cache_read_input_tokens,
        "cache_creation_input_tokens": response.cache_creation_input_tokens,
        "output_tokens": response.out_tokens,
    }


def _session_summary_content(totals: Mapping[str, int], n_turns: int) -> dict[str, object]:
    cache_read = totals["cache_read_input_tokens"]
    cache_creation = totals["cache_creation_input_tokens"]
    input_tokens = totals["input_tokens"]
    uncached = max(input_tokens - cache_read - cache_creation, 0)
    denominator = cache_read + cache_creation + uncached
    cache_hit_ratio = (cache_read / denominator) if denominator else 0.0
    return {
        "n_turns": n_turns,
        "input_tokens": input_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation,
        "uncached_input_tokens": uncached,
        "output_tokens": totals["output_tokens"],
        "cache_hit_ratio": cache_hit_ratio,
    }


def _assert_tool_pairing_invariant(messages: Sequence[Mapping[str, Any]]) -> None:
    """Assert provider-visible tool call/result ids are exactly paired."""
    use_ids: set[str] = set()
    result_ids: set[str] = set()
    for message in messages:
        role = message.get("role")
        if role == "assistant":
            for call in message.get("tool_calls") or ():
                if isinstance(call, Mapping):
                    use_ids.add(str(call.get("id") or ""))
            content = message.get("content")
            if isinstance(content, Sequence) and not isinstance(content, str):
                for block in content:
                    if isinstance(block, Mapping) and block.get("type") == "tool_use":
                        use_ids.add(str(block.get("id") or ""))
        if role == "tool":
            result_ids.add(str(message.get("tool_call_id") or ""))
        if role == "user":
            content = message.get("content")
            if isinstance(content, Sequence) and not isinstance(content, str):
                for block in content:
                    if isinstance(block, Mapping) and block.get("type") == "tool_result":
                        result_ids.add(str(block.get("tool_use_id") or ""))
    if use_ids != result_ids:
        raise AssertionError(
            f"orphaned tool calls: use_only={use_ids - result_ids}, "
            f"result_only={result_ids - use_ids}"
        )


def _fallback_projection_handler(_params: Mapping[str, object]) -> ToolResult:
    return ToolResult.ok("projection fallback")


def _projection_spec_for_call(registry: ToolRegistry, call: ToolCall) -> ToolSpec:
    try:
        return registry.lookup(call.name)
    except KeyError:
        return ToolSpec(
            name=call.name,
            description="Fallback projection spec for an unregistered tool call.",
            input_schema={"type": "object"},
            permission="read",
            handler=_fallback_projection_handler,
        )


def _tool_calls_for_message(
    raw_calls: Sequence[Mapping[str, Any]], parsed_calls: Sequence[ToolCall]
) -> list[Mapping[str, Any]]:
    """Return provider-history tool calls with ids matching ``parsed_calls``.

    ``_build_tool_calls`` intentionally supplies fallback ids / names for
    malformed model emissions so the registry can return a structured
    failure instead of crashing. The assistant message sent back to the
    provider must use the same fallback ids, otherwise the next request
    would contain an orphaned ``tool`` result and fail the pairing
    invariant before the model can correct itself.
    """
    projected: list[Mapping[str, Any]] = []
    for raw, parsed in zip(raw_calls, parsed_calls, strict=True):
        raw_function = raw.get("function")
        function = raw_function if isinstance(raw_function, Mapping) else {}
        name = str(function.get("name") or parsed.name)
        arguments = function.get("arguments")
        if not isinstance(arguments, str):
            arguments = json.dumps(dict(parsed.params), ensure_ascii=False, sort_keys=True)
        projected.append(
            {
                "id": parsed.call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        )
    return projected


@dataclass(frozen=True)
class SessionOutcome:
    """Terminal state of a :func:`drive_session` invocation.

    Returned (never raised) so the CLI can render the outcome in the
    canonical OK/ERROR shape across every termination path:

    - ``exit_code == 0`` + ``stop_reason == "stopped_by_llm"``: LLM
      emitted a final message with no tool calls and a terminal
      ``finish_reason`` (the happy path).
    - ``exit_code == 1`` + ``stop_reason == "iteration_cap"``: the
      ``max_turns`` cap fired before the LLM signalled completion.
    - ``exit_code == 1`` + ``stop_reason == "abnormal_stop:<reason>"``:
      the LLM stopped on ``length`` / ``content_filter`` without a
      tool call — terminal but abnormal.
    - ``exit_code == 2`` + ``stop_reason == "chain_exhausted"``: every
      provider in the chain failed; the chain raised
      :class:`fa.providers.errors.ProviderChainExhaustedError`.
    - ``exit_code == 2`` + ``stop_reason == "request_shape"``: a
      provider returned 400/422 (FA's request construction is wrong);
      the chain raised :class:`fa.providers.errors.ProviderRequestShapeError`.
    - ``exit_code == 130`` + ``stop_reason == "abnormal_stop:interrupt"``:
      the user sent ``KeyboardInterrupt`` (Ctrl+C) during a turn.
    """

    exit_code: int
    stop_reason: str
    turns: int
    final_text: str
    tool_results: tuple[ToolResult, ...] = field(default_factory=tuple)


# C901-baseline waiver (25>15): top-level session driver; decompose per
# loop-improvement-workplan BEFORE adding more branches.
def drive_session(  # noqa: C901
    task: str,
    *,
    provider_chain: ProviderChain,
    registry: ToolRegistry,
    hooks: HookRegistry,
    state: SessionState,
    role: str = "coder",
    acting_family: str = "",
    limits: RuntimeLimits | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    system_prompt_extra: str = "",
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    redactor: SecretRedactor | None = None,
    output: EventBus | None = None,
) -> SessionOutcome:
    """Drive an LLM-driven coder session to terminal state.

    Args:
        task: The user-supplied task description; injected as the
            first ``user`` message in the conversation.
        provider_chain: Configured chain for the acting role; the
            driver calls :meth:`ProviderChain.request` once per
            turn. The chain handles per-provider fallback and
            cooldown internally — the driver only sees the final
            outcome.
        registry: Tool registry; spec list rendered into the system
            prompt's tool-list slot once at the start of the
            session.
        hooks: Hook registry; dispatched at ``BEFORE_LLM_CALL`` /
            ``AFTER_LLM_CALL`` per turn AND at ``BETWEEN_ROUNDS`` /
            ``BEFORE_TOOL_EXEC`` / ``AFTER_TOOL_EXEC`` inside
            ``run_session`` per tool call.
        state: Session state; the driver writes ``user_msg`` /
            ``model_msg`` rows for LLM I/O, and ``run_session``
            writes ``tool_call`` / ``tool_result`` / ``hook_decision``
            rows for tool dispatch.
        role: Acting role label (``coder`` / ``planner`` / ``eval``);
            passed through to every HookPayload.
        acting_family: Acting-role model family for the
            family-disjoint LLM-using-middleware check; pass the
            ``family`` field from :attr:`ProviderChain.config` to
            keep the chain and the hook registry in sync.
        limits: Per-call runtime limits; defaults to
            :meth:`RuntimeLimits.anchored_defaults` (max_iterations=6).
            One ``run_session`` invocation per LLM turn means the
            tool-call cap applies per-turn, not per-session.
        max_turns: LLM-turn cap; defaults to :data:`DEFAULT_MAX_TURNS`.
        system_prompt_extra: Optional text appended after the
            canonical system prompt body.
        temperature: Sampling temperature; default 0.0 keeps replay
            byte-deterministic against a deterministic provider stub.
        max_tokens: Per-turn output token cap.

    Returns:
        :class:`SessionOutcome` describing the terminal state.

    Raises:
        ValueError: when ``state.log`` is None (the run-wide audit
            sink is the durable replay surface; silently None-ing
            it would lose audit rows — same fence as
            :func:`fa.inner_loop.loop.run_session`).
    """
    if state.log is None:
        raise ValueError("SessionState.log must be set before drive_session")

    effective_limits = limits if limits is not None else RuntimeLimits.anchored_defaults()
    tool_payload = render_tool_specs(registry.specs())
    artifact_store = ArtifactStore.from_event_log(state.log)
    usage_totals = {
        "input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "output_tokens": 0,
    }
    usage_turns = 0
    summary_written = False
    system_message = build_system_message(system_prompt_extra, role=role)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": task},
    ]
    state.log.append(actor="user", kind="user_msg", content={"text": task})
    state.log.append(
        actor="runtime",
        kind="run_started",
        content={"role": role, "max_turns": max_turns, "temperature": temperature},
    )

    _session_start_mono = time.monotonic()

    # ── Output: session_start ──────────────────────────────────────────────
    if output is not None:
        output.emit(
            OutputEvent(
                type="session_start",
                max_turns=max_turns,
                data={"model": provider_chain.config.model, "role": role, "family": acting_family},
            )
        )

    collected_results: list[ToolResult] = []
    turn = 0

    def record_usage(response: ResponseInfo) -> None:
        nonlocal usage_turns
        # Waiver: internal invariant (log attached before loop starts).
        assert state.log is not None  # noqa: S101
        row = _usage_event_content(response)
        state.log.append(actor="runtime", kind="usage", content=row)
        for key, value in row.items():
            usage_totals[key] += value
        usage_turns += 1

    def finish(outcome: SessionOutcome) -> SessionOutcome:
        nonlocal summary_written
        # Waiver: internal invariant (log attached before loop starts).
        assert state.log is not None  # noqa: S101
        if not summary_written:
            summary = _session_summary_content(usage_totals, usage_turns)
            state.log.append(
                actor="runtime",
                kind="session_summary",
                content=summary,
            )
            summary_written = True
            # ── Output: session_end ────────────────────────────────────────
            if output is not None:
                output.emit(
                    OutputEvent(
                        type="session_end",
                        turn=outcome.turns,
                        max_turns=max_turns,
                        data={
                            "stop_reason": outcome.stop_reason,
                            "ok": outcome.exit_code == 0,
                            "turns": outcome.turns,
                            "wall_s": time.monotonic() - _session_start_mono,
                            "total_in": usage_totals.get("input_tokens", 0),
                            "total_out": usage_totals.get("output_tokens", 0),
                            "cache_hit_ratio": summary.get("cache_hit_ratio", 0.0),
                            "context_used_pct": None,
                        },
                    )
                )
        return outcome

    while turn < max_turns:
        turn += 1
        # ── Output: turn_start ─────────────────────────────────────────────
        if output is not None:
            output.emit(
                OutputEvent(
                    type="turn_start",
                    turn=turn,
                    max_turns=max_turns,
                )
            )
        try:
            hooks.dispatch(
                LifecyclePoint.BEFORE_LLM_CALL,
                HookPayload(role=role, acting_family=acting_family),
            )
        except PermissionError as exc:
            state.log.append(
                actor="runtime",
                kind="run_stopped",
                content={
                    "reason": f"hook_deny:{LifecyclePoint.BEFORE_LLM_CALL.value}",
                    "detail": str(exc),
                },
            )
            # ── Output: hook_deny ──────────────────────────────────────────
            if output is not None:
                output.emit(
                    OutputEvent(
                        type="hook_deny",
                        turn=turn,
                        max_turns=max_turns,
                        data={"hook": "BEFORE_LLM_CALL", "reason": str(exc)},
                    )
                )
            return finish(
                SessionOutcome(
                    exit_code=1,
                    stop_reason=f"hook_deny:{LifecyclePoint.BEFORE_LLM_CALL.value}",
                    turns=turn,
                    final_text="",
                    tool_results=tuple(collected_results),
                )
            )
        if __debug__:
            _assert_tool_pairing_invariant(messages)
        request = RequestInfo(
            model_slug=provider_chain.config.model,
            messages=tuple(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tool_payload,
        )
        try:
            # --- Internal Retry Loop for Chain Exhaustion ---
            max_chain_retries = 3
            attempt_count = 0
            while True:
                try:
                    response, _logical_id, _attempts = provider_chain.request(request)
                    break
                except ProviderChainExhaustedError as exc:
                    attempt_count += 1
                    if state.log is not None:
                        for attempt in exc.attempts:
                            state.log.append(
                                actor="provider",
                                kind="provider_attempt",
                                content={
                                    "provider": attempt.provider,
                                    "slug": attempt.slug,
                                    "status": attempt.status,
                                    "ms": attempt.ms,
                                    "error": attempt.error,
                                    "logical_call_id": exc.logical_call_id,
                                },
                            )
                    if attempt_count >= max_chain_retries:
                        raise  # Break the while loop, letting the outer try/except catch it as norm

                    now = time.time()
                    active_cooldowns = [
                        row.expires_at - now
                        for key, row in provider_chain.cooldowns.items()
                        if row.expires_at > now
                    ]

                    wait_s = max(1.0, min(active_cooldowns)) if active_cooldowns else 5.0

                    # Protect tests from hanging
                    import os
                    if wait_s > 60 or "PYTEST_CURRENT_TEST" in os.environ:
                        wait_s = 0.01

                    if output is not None:

                        for _att in exc.attempts:
                            output.emit(
                                OutputEvent(
                                    type="api_retry",
                                    turn=turn,
                                    max_turns=max_turns,
                                    data={
                                        "provider": _att.provider,
                                        "status": _att.status,
                                        "retry_after_s": int(wait_s),
                                        "reason": _att.error or "unknown",
                                    },
                                )
                            )
                    time.sleep(wait_s)

            if state.log is not None:
                for attempt in _attempts:
                    state.log.append(
                        actor="provider",
                        kind="provider_attempt",
                        content={
                            "provider": attempt.provider,
                            "slug": attempt.slug,
                            "status": attempt.status,
                            "ms": attempt.ms,
                            "error": attempt.error,
                            "logical_call_id": _logical_id,
                        },
                    )
            record_usage(response)
            # ── Output: llm_response ───────────────────────────────────────
            if output is not None:
                _elapsed = int(_attempts[-1].ms if _attempts else 0)
                output.emit(
                    OutputEvent(
                        type="llm_response",
                        turn=turn,
                        max_turns=max_turns,
                        data={
                            "ms": _elapsed,
                            "in_tokens": response.in_tokens,
                            "out_tokens": response.out_tokens,
                            "cache_read": response.cache_read_input_tokens,
                            "cache_creation": response.cache_creation_input_tokens,
                            "tool_call_count": len(response.tool_calls),
                            "text": response.text if response.text else None,
                        },
                    )
                )
        except KeyboardInterrupt:
            state.log.append(
                actor="runtime",
                kind="run_stopped",
                content={"reason": "abnormal_stop:interrupt"},
            )
            return finish(
                SessionOutcome(
                    exit_code=130,
                    stop_reason="abnormal_stop:interrupt",
                    turns=turn,
                    final_text="",
                    tool_results=tuple(collected_results),
                )
            )
        except ProviderChainExhaustedError as exc:
            # Log individual attempt records so events.jsonl contains
            # per-entry diagnostics (status, ms, error) even on chain
            # exhaustion — closes the observability gap where the
            # operator saw only "all N chain entries failed" with no
            # detail on which entry returned which HTTP status.
            for attempt in exc.attempts:
                state.log.append(
                    actor="provider",
                    kind="provider_attempt",
                    content={
                        "provider": attempt.provider,
                        "slug": attempt.slug,
                        "status": attempt.status,
                        "ms": attempt.ms,
                        "error": attempt.error,
                        "logical_call_id": exc.logical_call_id,
                    },
                )
            state.log.append(
                actor="runtime",
                kind="run_stopped",
                content={"reason": "chain_exhausted", "detail": str(exc)},
            )
            # ── Output: api_retry (all entries failed) ─────────────────────
            if output is not None:
                for _att in exc.attempts:
                    output.emit(
                        OutputEvent(
                            type="api_retry",
                            turn=turn,
                            max_turns=max_turns,
                            data={
                                "provider": _att.provider,
                                "status": _att.status,
                                "retry_after_s": 0,
                                "reason": _att.error or "unknown",
                            },
                        )
                    )
            return finish(
                SessionOutcome(
                    exit_code=2,
                    stop_reason="chain_exhausted",
                    turns=turn,
                    final_text="",
                    tool_results=tuple(collected_results),
                )
            )
        except ProviderRequestShapeError as exc:
            state.log.append(
                actor="runtime",
                kind="run_stopped",
                content={"reason": "request_shape", "detail": str(exc)},
            )
            return finish(
                SessionOutcome(
                    exit_code=2,
                    stop_reason="request_shape",
                    turns=turn,
                    final_text="",
                    tool_results=tuple(collected_results),
                )
            )
        try:
            hooks.dispatch(
                LifecyclePoint.AFTER_LLM_CALL,
                HookPayload(role=role, acting_family=acting_family),
            )
        except PermissionError as exc:
            state.log.append(
                actor="runtime",
                kind="run_stopped",
                content={
                    "reason": f"hook_deny:{LifecyclePoint.AFTER_LLM_CALL.value}",
                    "detail": str(exc),
                },
            )
            return finish(
                SessionOutcome(
                    exit_code=1,
                    stop_reason=f"hook_deny:{LifecyclePoint.AFTER_LLM_CALL.value}",
                    turns=turn,
                    final_text="",
                    tool_results=tuple(collected_results),
                )
            )

        tool_calls = _build_tool_calls(response.tool_calls) if response.tool_calls else ()
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": response.text or "",
        }
        if tool_calls:
            assistant_message["tool_calls"] = _tool_calls_for_message(
                response.tool_calls, tool_calls
            )
        messages.append(assistant_message)
        state.log.append(
            actor="model",
            kind="model_msg",
            content={
                "text": response.text,
                "tool_calls": [dict(c) for c in response.tool_calls],
                "finish_reason": response.finish_reason,
                "in_tokens": response.in_tokens,
                "cache_read_input_tokens": response.cache_read_input_tokens,
                "cache_creation_input_tokens": response.cache_creation_input_tokens,
                "out_tokens": response.out_tokens,
            },
        )

        if not tool_calls:
            if response.finish_reason in _TERMINAL_FINISH_REASONS or not response.finish_reason:
                return finish(
                    SessionOutcome(
                        exit_code=0,
                        stop_reason="stopped_by_llm",
                        turns=turn,
                        final_text=response.text,
                        tool_results=tuple(collected_results),
                    )
                )
            # LLM stopped for length / content_filter without a tool
            # call — terminal but ABNORMAL; surface as non-zero exit
            # so the CLI distinguishes a clean stop from a truncated
            # one. The audit trail already has the ``model_msg`` row
            # carrying the abnormal ``finish_reason`` verbatim.
            state.log.append(
                actor="runtime",
                kind="run_stopped",
                content={"reason": f"abnormal_stop:{response.finish_reason}"},
            )
            return finish(
                SessionOutcome(
                    exit_code=1,
                    stop_reason=f"abnormal_stop:{response.finish_reason}",
                    turns=turn,
                    final_text=response.text,
                    tool_results=tuple(collected_results),
                )
            )

        # Capture log length BEFORE run_session so we only inspect
        # rows appended during this invocation, not stale rows from
        # earlier turns (cross-turn contamination guard).
        log_len_before = len(state.log.read_all()) if state.log is not None else 0
        turn_results = run_session(
            tool_calls,
            registry=registry,
            hooks=hooks,
            state=state,
            role=role,
            acting_family=acting_family,
            limits=effective_limits,
        )
        # ``run_session`` enforces ``max_iterations`` per invocation.
        # If the LLM emitted more tool calls than the cap, the loop
        # breaks early and returns fewer results. We MUST pad the
        # remainder with synthetic failures so the conversation history
        # stays protocol-valid: every ``tool_call_id`` in the
        # assistant message needs a matching ``role="tool"`` message.
        missing = len(tool_calls) - len(turn_results)
        if missing > 0:
            # Determine whether run_session stopped for a real iteration
            # cap or for a guard denial (PauseGuard, LoopGuard, etc.).
            stop_reason_code = "iteration_cap"
            stop_reason_detail = (
                f"tool call skipped: per-turn iteration limit "
                f"({effective_limits.max_iterations}) exceeded"
            )
            if state.log is not None:
                new_rows = state.log.read_all()[log_len_before:]
                for row in reversed(new_rows):
                    if row.kind == "run_stopped":
                        reason = str(row.content.get("reason", ""))
                        if not reason.startswith("iteration_cap"):
                            stop_reason_code = "run_stopped"
                            stop_reason_detail = f"tool call skipped: session stopped — {reason}"
                        break

            synthetic = ToolResult.fail(
                stop_reason_code,
                stop_reason_detail,
                retryable=True,
            )
            turn_results = (*turn_results, *([synthetic] * missing))
            # Record synthetic tool results in the audit trail so
            # replay sees a complete paired ``tool_call`` / ``tool_result``
            # row set per ADR-7 §10 Acceptance criterion 8.
            start = len(turn_results) - missing
            for call, result in zip(tool_calls[start:], turn_results[start:], strict=False):
                state.record_tool_call(call)
                state.record_tool_result(call, result)
        collected_results.extend(turn_results)
        for call, result in zip(tool_calls, turn_results, strict=True):
            # ── Output: tool_call ──────────────────────────────────────────
            if output is not None:
                output.emit(
                    OutputEvent(
                        type="tool_call",
                        turn=turn,
                        max_turns=max_turns,
                        data={
                            "tool": call.name,
                            "params": dict(call.params),
                            "summary": result.summary,
                            "ok": result.error is None,
                            "error": result.error.message if result.error else None,
                        },
                    )
                )
            spec = _projection_spec_for_call(registry, call)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.call_id,
                    "content": _redact(redactor, project_for_model(spec, result, artifact_store)),
                }
            )

    state.log.append(
        actor="runtime",
        kind="run_stopped",
        content={"reason": "iteration_cap", "turns": turn},
    )
    return finish(
        SessionOutcome(
            exit_code=1,
            stop_reason="iteration_cap",
            turns=turn,
            final_text="",
            tool_results=tuple(collected_results),
        )
    )


def _build_tool_calls(raw_calls: Sequence[Mapping[str, Any]]) -> tuple[ToolCall, ...]:
    """Project canonical wire-shape tool calls into a :class:`ToolCall` tuple.

    Wire shape (canonical across every adapter)::

        {"id": "<id>", "type": "function",
         "function": {"name": "<tool>", "arguments": "<json-str>"}}

    The Anthropic adapter re-projects its native ``tool_use`` blocks
    into this shape at response-normalise time (see
    :func:`fa.providers.anthropic._normalize_success` ll. 187-196).
    OpenAI-compat providers emit this shape natively.

    Determinism guards (deep-dive §3 I-5 — deterministic post-LLM
    filter): a missing ``function`` block, missing ``name``, or
    malformed ``arguments`` JSON does NOT raise — instead the driver
    produces a synthetic call whose registry validation produces the
    canonical ``invalid_params`` error row. The LLM sees the error
    on the next turn and can correct.
    """
    parsed: list[ToolCall] = []
    for index, raw in enumerate(raw_calls):
        raw_function = raw.get("function")
        function: Mapping[str, Any] = raw_function if isinstance(raw_function, Mapping) else {}
        name = str(function.get("name") or "")
        arguments_raw = function.get("arguments")
        call_id = str(raw.get("id") or f"tc-{index:04d}")
        params: Mapping[str, Any]
        if isinstance(arguments_raw, str):
            try:
                decoded = json.loads(arguments_raw) if arguments_raw else {}
            except json.JSONDecodeError:
                decoded = {}
            params = decoded if isinstance(decoded, Mapping) else {}
        elif isinstance(arguments_raw, Mapping):
            params = arguments_raw
        else:
            params = {}
        if not name:
            # ToolCall constructor rejects empty name; surface the
            # malformed emission as a synthetic ``__invalid__`` call so
            # the registry validation path produces the canonical
            # error row instead of the driver itself raising.
            name = "__invalid__"
        parsed.append(ToolCall(name=name, params=dict(params), call_id=call_id))
    return tuple(parsed)


__all__ = [
    "DEFAULT_CODER_TEMPERATURE",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MAX_TURNS",
    "DEFAULT_TEMPERATURE",
    "SessionOutcome",
    "drive_session",
]
