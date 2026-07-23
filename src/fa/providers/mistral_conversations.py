"""Mistral ``/v1/conversations`` adapter (Category 4 — Mistral Agents/Conversations).

The Conversations API is Mistral's higher-level protocol that supports
server-side built-in tools (``web_search``, ``web_search_premium``,
``code_interpreter``, ``document_library``, ``image_generation``)
and persistent conversation state. It is NOT OpenAI-compatible — the
request/response shapes differ fundamentally:

**Request** — ``POST /v1/conversations``:
- ``inputs`` (not ``messages``) — list of input messages.
- ``model`` or ``agent_id`` — one is required.
- ``tools`` — list of built-in tool descriptors (e.g.
  ``{type: "web_search"}``) and/or function tools.
- ``store`` — whether to persist the conversation.
- ``completion_args`` — nested dict for temperature, top_p, max_tokens,
  response_format, etc.
- ``instructions`` — system-level instructions (replaces system message).

**Response** — ``outputs`` (not ``choices``):
- ``outputs`` — list of output items, each with a ``type``:
  - ``message.output`` — model text/tool-call response.
  - ``tool.execution`` — server-side tool execution result.
  - ``reference.output`` — citation/reference output.
- ``conversation_id`` — persistent conversation ID.
- ``usage`` — token usage.

This adapter maps between the canonical :class:`RequestInfo` /
:class:`ResponseInfo` and the Conversations API shape, so the chain
dispatcher and inner-loop runtime can use Mistral's built-in tools
transparently.

**When to use this adapter vs :class:`MistralProvider`**:

- Use :class:`MistralProvider` (``/v1/chat/completions``) for standard
  chat completions with function calling, structured output, prediction,
  and prompt caching. This covers the majority of use cases.
- Use :class:`MistralConversationsProvider` (``/v1/conversations``) when
  you need server-side built-in tools (``web_search``, ``code_interpreter``,
  ``document_library``) or persistent conversation state.

References:
- https://docs.mistral.ai/studio-api/agents/agents-api
- https://docs.mistral.ai/api/endpoint/beta/conversations
- https://docs.mistral.ai/studio-api/agents/agent-tools
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any, cast

from fa.providers._common import make_authenticated_request, parse_token_usage
from fa.providers.base import (
    RequestInfo,
    ResponseInfo,
    Transport,
    TransportResponse,
    parse_transport_response,
)

logger = logging.getLogger(__name__)

# Built-in tool types supported by the Conversations API.
# These are server-side tools that do NOT require a function definition —
# they are enabled by adding a ``{type: "<tool_type>"}`` entry to the
# ``tools`` list. Function tools use the standard OpenAI shape.
_MISTRAL_BUILTIN_TOOL_TYPES = frozenset(
    {
        "web_search",
        "web_search_premium",
        "code_interpreter",
        "document_library",
        "image_generation",
    }
)

# Mistral-specific finish reasons from the Conversations API.
_FINISH_REASON_MAP: Mapping[str, str] = {
    "stop": "stop",
    "length": "length",
    "tool_calls": "tool_calls",
    "tool_use": "tool_calls",  # Conversations API uses "tool_use"
    "end_turn": "stop",  # Agent-style end turn
}


class MistralConversationsProvider:
    """``/v1/conversations`` adapter for Mistral Agents/Conversations API.

    This adapter enables Mistral's server-side built-in tools
    (``web_search``, ``code_interpreter``, ``document_library``) which
    are NOT available via the standard ``/v1/chat/completions`` endpoint.

    The adapter translates the canonical :class:`RequestInfo` into the
    Conversations API request shape (``inputs``, ``tools``,
    ``completion_args``) and maps the response ``outputs`` back to
    canonical :class:`ResponseInfo`.

    Built-in tools are specified via ``RequestInfo.extras["mistral_tools"]``
    as a list of tool descriptors, e.g.::

        extras={
            "mistral_tools": [
                {"type": "web_search"},
                {"type": "document_library"},
            ]
        }

    Function tools from ``RequestInfo.tools`` are automatically converted
    to the Conversations API format.
    """

    name = "mistral_agents"

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

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
        url = base_url.rstrip("/") + "/v1/conversations"
        body = _build_conversations_body(request)

        response = make_authenticated_request(
            transport=self._transport,
            url=url,
            api_key=api_key,
            body=body,
            extra_headers=extra_headers,
            timeout_seconds=timeout_seconds,
            transport_retries=transport_retries,
        )
        return _parse_conversations_response(response)


def _build_mistral_tools(request: RequestInfo) -> list[dict[str, Any]]:
    """Convert function and built-in tools into Conversations API shape."""
    tools: list[dict[str, Any]] = []
    if request.tools:
        for tool in request.tools:
            # Check if this is a built-in tool descriptor
            tool_type = tool.get("type")
            if tool_type in _MISTRAL_BUILTIN_TOOL_TYPES:
                tools.append(dict(tool))
            elif tool_type == "function":
                fn = tool.get("function", {})
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": fn.get("name", ""),
                            "description": fn.get("description", ""),
                            "parameters": fn.get("parameters", {}),
                        },
                    }
                )
            else:
                # Passthrough unknown tool shapes
                tools.append(dict(tool))

    # Built-in tools from extras
    mistral_tools = request.extras.get("mistral_tools")
    if isinstance(mistral_tools, list):
        for mt in mistral_tools:
            if isinstance(mt, Mapping) and mt.get("type") in _MISTRAL_BUILTIN_TOOL_TYPES:
                tools.append(dict(mt))
            else:
                logger.warning(
                    "Skipping invalid mistral_tools entry: %r — expected mapping with type in %s",
                    mt,
                    sorted(_MISTRAL_BUILTIN_TOOL_TYPES),
                )

    return tools


def _build_completion_args(request: RequestInfo) -> dict[str, Any]:
    """Collect optional model parameters for the Conversations API."""
    completion_args: dict[str, Any] = {}
    if request.temperature is not None:
        completion_args["temperature"] = request.temperature
    if request.max_tokens is not None:
        completion_args["max_tokens"] = request.max_tokens

    # Pass through Mistral-specific extras into completion_args
    for key in (
        "response_format",
        "prediction",
        "reasoning_effort",
        "prompt_cache_key",
        "safe_prompt",
        "prompt_mode",
        "parallel_tool_calls",
    ):
        if key in request.extras:
            completion_args[key] = request.extras[key]

    return completion_args


def _build_conversations_body(request: RequestInfo) -> dict[str, Any]:
    """Build a Conversations API request body from canonical RequestInfo.

    Mapping:
    - ``messages`` → ``inputs`` (rename)
    - System messages → ``instructions`` (top-level, not in inputs)
    - ``temperature``, ``max_tokens``, ``response_format`` → ``completion_args``
    - Function tools → converted to Mistral function tool format
    - Built-in tools → from ``extras["mistral_tools"]``
    - ``prediction``, ``reasoning_effort`` → ``completion_args``
    """
    inputs: list[dict[str, Any]] = []
    instructions_parts: list[str] = []
    for msg in request.messages:
        role = msg.get("role")
        if role == "system":
            content = msg.get("content", "")
            if isinstance(content, str):
                instructions_parts.append(content)
            continue
        # Conversations API uses the same message shapes for user/assistant
        inputs.append(dict(msg))

    body: dict[str, Any] = {
        "model": request.model_slug,
        "inputs": inputs,
    }
    if instructions_parts:
        body["instructions"] = "\n\n".join(instructions_parts)

    tools = _build_mistral_tools(request)
    if tools:
        body["tools"] = tools

    completion_args = _build_completion_args(request)
    if completion_args:
        body["completion_args"] = completion_args

    # Store conversation by default (allows follow-up with append)
    if "store" not in request.extras:
        body["store"] = True
    else:
        body["store"] = bool(request.extras["store"])

    # agent_id from extras (if using a pre-created agent)
    agent_id = request.extras.get("agent_id")
    if agent_id:
        body["agent_id"] = str(agent_id)
        # When using agent_id, model should not be set
        body.pop("model", None)

    return body


def _parse_conversations_response(response: TransportResponse) -> ResponseInfo:
    """Parse Conversations API response — reuses shared status mapping."""
    return parse_transport_response(response, _normalize_conversations_success)


def _normalize_conversation_outputs(
    outputs: list[Mapping[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], str]:
    """Normalize message output text/tool calls and finish reason."""
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    finish_reason = "stop"
    for output in outputs:
        output_type = output.get("type")
        if output_type == "message.output":
            # Model text response
            content = output.get("content")
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                # Content blocks (similar to Anthropic)
                for block in content:
                    if isinstance(block, Mapping) and block.get("type") == "text":
                        text_parts.append(cast(str, block.get("text", "")))

            # Tool calls from the message output
            raw_tool_calls = output.get("tool_calls") or []
            for tc in raw_tool_calls:
                if isinstance(tc, Mapping):
                    tc_type = tc.get("type")
                    if tc_type == "function":
                        tool_calls.append(dict(tc))
                    else:
                        # Conversations API tool_call format — normalise
                        fn = tc.get("function") or {}
                        tool_calls.append(
                            {
                                "id": tc.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": tc.get("name", fn.get("name", "")),
                                    "arguments": (
                                        tc.get("arguments")
                                        if isinstance(tc.get("arguments"), str)
                                        else json.dumps(tc.get("arguments") or fn.get("arguments") or {})
                                    ),
                                },
                            }
                        )

            # Finish reason from message output
            if output.get("finish_reason"):
                mapped = _FINISH_REASON_MAP.get(
                    cast(str, output["finish_reason"]),
                    cast(str, output["finish_reason"]),
                )
                finish_reason = mapped

        elif output_type == "tool.execution":
            # Server-side tool execution — record as extra, not as a
            # standard tool call (the execution is complete, no client-
            # side tool result needed).
            pass
        elif output_type == "reference.output":
            # Citation/reference output — record as extra
            pass

    return text_parts, tool_calls, finish_reason


def _normalize_conversations_success(body: Mapping[str, Any]) -> ResponseInfo:
    """Normalize a Conversations API 200 response into canonical ResponseInfo.

    Conversations API response shape::

        {
            "conversation_id": "...",
            "outputs": [
                {
                    "type": "message.output",
                    "content": "Hello!",
                    "role": "assistant",
                    "tool_calls": [...],
                },
                {
                    "type": "tool.execution",
                    "name": "web_search",
                    "content": "...",
                },
                {
                    "type": "reference.output",
                    ...
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "prompt_tokens_details": {"cached_tokens": 80}
            }
        }
    """
    conversation_id = body.get("conversation_id")

    outputs = cast(list[Mapping[str, Any]], body.get("outputs", []))
    text_parts, tool_calls, finish_reason = _normalize_conversation_outputs(outputs)

    token_usage = parse_token_usage(body)
    in_tokens = token_usage["in_tokens"]
    out_tokens = token_usage["out_tokens"]
    cache_read_input_tokens = token_usage["cache_read_input_tokens"]
    cache_creation_input_tokens = token_usage["cache_creation_input_tokens"]

    # Extract usage dict for prediction_tokens check (Mistral-specific)
    usage = cast(Mapping[str, Any], body.get("usage") or {})

    extras: dict[str, Any] = {}
    if conversation_id:
        extras["conversation_id"] = conversation_id
    for key in ("id", "model", "created", "object"):
        if key in body:
            extras[key] = body[key]
    if "prediction_tokens" in usage:
        extras["prediction_tokens"] = int(usage["prediction_tokens"])

    # Collect tool execution and reference outputs as extras
    tool_executions = []
    references = []
    for output in outputs:
        output_type = output.get("type")
        if output_type == "tool.execution":
            tool_executions.append(dict(output))
        elif output_type == "reference.output":
            references.append(dict(output))
    if tool_executions:
        extras["tool_executions"] = tool_executions
    if references:
        extras["references"] = references

    return ResponseInfo(
        text="".join(text_parts),
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        finish_reason=finish_reason,
        tool_calls=tuple(tool_calls),
        cache_read_input_tokens=cache_read_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        extras=extras,
    )
