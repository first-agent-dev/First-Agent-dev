"""Restore a session's provider history from its event log (S13.2 / I-52).

Replay uses the latest stage-three compaction as the boundary. The event log
remains the authority; read failures retain the historical best-effort policy.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from fa.inner_loop.registry import ToolCall
from fa.inner_loop.state import EventLog
from fa.providers.base import ResponseInfo

# Preserve the established warning logger for operator log routing.
logger = logging.getLogger("fa.inner_loop.coder_loop")


def _merge_memory_summary_context(initial_summary: str, rebuilt_summary: str) -> str:
    initial = initial_summary.strip()
    rebuilt = rebuilt_summary.strip()
    if initial and rebuilt:
        return f"Resumed session context:\n{initial}\n\nPrevious compacted summary:\n{rebuilt}"
    return initial or rebuilt


def restore_conversation_history(log: EventLog, initial_memory_summary: str) -> tuple[str, list[dict[str, Any]]]:
    """Rebuild the post-compaction conversation from the authoritative event log."""
    memory_summary = initial_memory_summary.strip()
    conversation_history: list[dict[str, Any]] = []
    try:
        events = log.read_all()
        latest_comp_idx = -1
        rebuilt_summary = ""
        for idx, ev in enumerate(events):
            if ev.kind == "compaction_stage3_done":
                latest_comp_idx = idx
                rebuilt_summary = str(ev.content.get("summary") or "")

        memory_summary = _merge_memory_summary_context(initial_memory_summary, rebuilt_summary)
        relevant_events = events[latest_comp_idx + 1 :] if latest_comp_idx != -1 else events
        for ev in relevant_events:
            if ev.kind == "user_msg":
                # I-52: replay the prior instruction so a resumed stage sees
                # the user turn its inherited assistant/tool turns were
                # answering. `user_msg` rows appear chronologically before the
                # `model_msg` they provoked, so log-order replay cannot create
                # a user-after-tool transition.
                text = ev.content.get("text")
                conversation_history.append({"role": "user", "content": str(text or "")})
            elif ev.kind == "model_msg":
                text = ev.content.get("text")
                calls = ev.content.get("tool_calls")
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": text or "",
                }
                if calls:
                    assistant_msg["tool_calls"] = calls
                conversation_history.append(assistant_msg)
            elif ev.kind == "tool_result":
                # Tool response
                # Find tool_call_id and full stdout content
                res_data = ev.content.get("result") or {}
                stdout = ""
                if isinstance(res_data, dict):
                    stdout = str(res_data.get("stdout") or "")
                content_val = stdout if stdout else (ev.content.get("summary") or "")
                conversation_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": ev.tool_call_id,
                        "content": content_val,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to rebuild history from log: %s", exc)

    return memory_summary, conversation_history


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
            f"orphaned tool calls: use_only={use_ids - result_ids}, result_only={result_ids - use_ids}"
        )


def _assert_final_role_invariant(messages: Sequence[Mapping[str, Any]]) -> None:
    """Assert the final provider-visible message is a serving-valid role.

    I-50 (S13.3) production hardening: Mistral/Anthropic reject a trailing
    ``assistant`` for a non-prefix completion (400/3230). This dev-time assertion
    makes the loop fail fast if the emitter ever regresses, regardless of which
    transport or provider is in use.
    """
    if not messages:
        return
    last_role = messages[-1].get("role")
    if last_role not in ("user", "tool"):
        raise AssertionError(f"final provider-visible role must be user or tool for serving, got {last_role!r}")


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


def record_model_response(
    response: ResponseInfo, conversation_history: list[dict[str, Any]], log: EventLog
) -> tuple[ToolCall, ...]:
    """Append provider response and its raw audit row after the AFTER hook."""
    tool_calls = _build_tool_calls(response.tool_calls) if response.tool_calls else ()
    assistant_message: dict[str, Any] = {
        "role": "assistant",
        "content": response.text or "",
    }
    # Safely preserve custom API message attributes (like reasoning_details)
    if "message_extras" in response.extras:
        for k, v in response.extras["message_extras"].items():
            assistant_message[k] = v
    if tool_calls:
        assistant_message["tool_calls"] = _tool_calls_for_message(response.tool_calls, tool_calls)
    conversation_history.append(assistant_message)
    log.append(
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
    return tool_calls
