"""Anthropic ``/v1/messages`` adapter (ADR-9 §5 Category 2).

Translates between FA's canonical OpenAI-shaped
:class:`fa.providers.base.RequestInfo` and Anthropic's native shape:

* ``system`` row is hoisted out of ``messages`` into Anthropic's
  separate top-level ``system`` field.
* ``tools`` field-names: OpenAI ``{type: function, function: {name,
  description, parameters}}`` → Anthropic ``{name, description,
  input_schema}``.
* Tool-use response: Anthropic returns ``content: [{type: "tool_use",
  id, name, input}, ...]`` content blocks; the adapter re-projects
  these into OpenAI-shaped ``tool_calls: [{id, type: "function",
  function: {name, arguments}}, ...]`` so the canonical
  :class:`fa.providers.base.ResponseInfo` stays adapter-agnostic.
* ``finish_reason`` mapping: ``end_turn`` → ``stop``, ``max_tokens``
  → ``length``, ``tool_use`` → ``tool_calls``, ``stop_sequence`` →
  ``stop``.

Status-code split is identical to :mod:`fa.providers.openai_compat`
because ADR-9 §2 splits live in the chain dispatcher, not per-adapter.
Authentication uses the ``x-api-key`` header (Anthropic-specific) +
mandatory ``anthropic-version`` header.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, cast

from fa.providers.base import (
    RequestInfo,
    ResponseInfo,
    Transport,
    TransportResponse,
    parse_transport_response,
)

_ANTHROPIC_API_VERSION = "2023-06-01"

_STOP_REASON_MAP: Mapping[str, str] = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}


class AnthropicProvider:
    """``/v1/messages`` adapter (Anthropic native protocol)."""

    name = "anthropic"

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def request(
        self,
        request: RequestInfo,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        extra_headers: Mapping[str, str],
    ) -> ResponseInfo:
        url = base_url.rstrip("/") + "/v1/messages"
        body = _build_request_body(request)

        headers: dict[str, str] = {
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_API_VERSION,
            "Content-Type": "application/json",
        }
        for key, value in extra_headers.items():
            headers[key] = value

        response = self._transport.post(
            url, headers=headers, json_body=body, timeout_seconds=timeout_seconds
        )
        return _parse_response(response)


def _build_request_body(request: RequestInfo) -> dict[str, Any]:
    system_parts: list[str] = []
    msgs: list[Mapping[str, Any]] = []
    for row in request.messages:
        if row.get("role") == "system":
            content = row.get("content")
            if isinstance(content, str):
                system_parts.append(content)
            continue
        msgs.append(row)

    body: dict[str, Any] = {
        "model": request.model_slug,
        "messages": msgs,
        # Anthropic requires ``max_tokens``; the canonical default
        # matches the ``max_tokens`` default in `~/.fa/models.yaml`.
        "max_tokens": request.max_tokens if request.max_tokens is not None else 4096,
    }
    if system_parts:
        body["system"] = "\n\n".join(system_parts)
    if request.temperature is not None:
        body["temperature"] = request.temperature
    if request.tools:
        body["tools"] = [
            {
                "name": _tool_name(tool),
                "description": _tool_description(tool),
                "input_schema": _tool_schema(tool),
            }
            for tool in request.tools
        ]
    for key, value in request.extras.items():
        body.setdefault(key, value)
    return body


def _tool_name(tool: Mapping[str, Any]) -> str:
    fn = tool.get("function")
    if isinstance(fn, Mapping):
        return cast(str, fn.get("name", ""))
    return cast(str, tool.get("name", ""))


def _tool_description(tool: Mapping[str, Any]) -> str:
    fn = tool.get("function")
    if isinstance(fn, Mapping):
        return cast(str, fn.get("description", ""))
    return cast(str, tool.get("description", ""))


def _tool_schema(tool: Mapping[str, Any]) -> Mapping[str, Any]:
    fn = tool.get("function")
    if isinstance(fn, Mapping):
        return cast(Mapping[str, Any], fn.get("parameters", {}))
    return cast(Mapping[str, Any], tool.get("input_schema", {}))


def _parse_response(response: TransportResponse) -> ResponseInfo:
    # Status -> exception mapping is shared across adapters; only the 200-body
    # decode differs, supplied here as the Anthropic-specific normalizer.
    return parse_transport_response(response, _normalize_success)


def _normalize_success(body: Mapping[str, Any]) -> ResponseInfo:
    text_parts: list[str] = []
    tool_calls: list[Mapping[str, Any]] = []
    raw_content = cast(list[Mapping[str, Any]], body.get("content") or [])
    for block in raw_content:
        kind = block.get("type")
        if kind == "text":
            text_parts.append(cast(str, block.get("text", "")))
        elif kind == "tool_use":
            tool_calls.append(
                {
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": json.dumps(block.get("input") or {}),
                    },
                }
            )

    raw_stop = cast(str, body.get("stop_reason") or "")
    finish_reason = _STOP_REASON_MAP.get(raw_stop, raw_stop)

    usage = cast(Mapping[str, Any], body.get("usage") or {})
    in_tokens = int(usage.get("input_tokens") or 0)
    out_tokens = int(usage.get("output_tokens") or 0)
    cache_read_input_tokens = int(usage.get("cache_read_input_tokens") or 0)
    cache_creation_input_tokens = int(usage.get("cache_creation_input_tokens") or 0)

    extras: dict[str, Any] = {}
    for key in ("id", "model", "role", "stop_sequence", "thinking"):
        if key in body:
            extras[key] = body[key]

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
