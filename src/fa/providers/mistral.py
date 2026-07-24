# pylint: disable=duplicate-code  # Mistral/OpenAI adapters intentionally share transport-call scaffolding.
"""Mistral ``/v1/chat/completions`` adapter (Category 3 — Mistral-native).

Mistral's chat completions endpoint is OpenAI-compatible at the wire level
(``/v1/chat/completions``), but adds several provider-specific fields that
the generic :class:`fa.providers.openai_compat.OpenAICompatProvider` does
not validate or structure:

* ``prediction: {type: "content", content: "..."}`` — predicted/guided
  output. The ``content`` field should contain the *expected output* (e.g.
  the previous summary to be updated), NOT the input document. The input
  document goes in ``messages``. This adapter validates the prediction
  field and logs a warning when the content exceeds a heuristic length
  (suggesting the caller may have put the input document in the prediction
  slot instead of the expected output).
* ``reasoning_effort: "high" | "medium" | "low"`` — for models that support
  adjustable reasoning (Mistral Small 4, Mistral Medium 3.5 / 2604).
* ``prompt_cache_key: str`` — prompt caching key. Cached tokens are billed
  at 10% of standard input price. Use the same key for requests that share
  a prompt prefix (multi-turn conversations, repeated system prompts).
  Reported in ``usage.prompt_tokens_details.cached_tokens``.
* ``response_format: {type: "json_schema", json_schema: {...}}`` — structured
  output. Mistral supports both ``json_object`` (any valid JSON) and
  ``json_schema`` (schema-constrained, recommended — 100% vs 64% schema
  conformance on nested schemas). This adapter auto-adds ``strict: true``
  when ``json_schema`` is used without an explicit ``strict`` field.
* ``safe_prompt: bool`` — inject a safety prompt before all conversations.
* ``prompt_mode: "reasoning" | "default"`` — toggle reasoning mode on
  reasoning-capable models.
* ``parallel_tool_calls: bool`` — enable parallel function calling.

The adapter reuses the shared ``parse_transport_response`` error mapping
from :mod:`fa.providers.base` and only specialises the request-body
construction and the 200-body normaliser.

References:
- https://docs.mistral.ai/api/endpoint/chat — Chat Completions API
- https://docs.mistral.ai/studio-api/conversations/advanced/predicted-outputs
- https://docs.mistral.ai/studio-api/conversations/advanced/prompt-caching
- https://docs.mistral.ai/capabilities/structured-output/custom_structured_output/
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, cast

from fa.providers.base import (
    RequestInfo,
    ResponseInfo,
    Transport,
    TransportResponse,
    parse_transport_response,
)

logger = logging.getLogger(__name__)

# Heuristic: prediction content longer than this is likely an input document
# rather than expected output. 8192 characters ≈ 2000 tokens, which is a
# reasonable upper bound for "expected output" (summaries, code edits, etc.).
_PREDICTION_LENGTH_WARN_CHARS = 8192

# Mistral-specific top-level body keys this adapter recognises (module
# docstring above is the source of truth this set must track). Exported
# (not module-private) so fa.providers.routing_lint can reuse it as the
# single source of truth for the "unknown provider_params key" check
# instead of hardcoding a second, driftable copy.
#
# Historical note: this set was previously missing "response_format" and
# "prompt_cache_key" (5 of the 7 documented keys) despite being unused
# anywhere in the module at the time — found stale during the ADR-9
# §Amendment 2026-07-23 code review and corrected to match the docstring
# + _build_request_body's actual behavior (prediction/response_format get
# structural handling; the rest are generic passthrough).
MISTRAL_RECOGNIZED_PROVIDER_PARAMS_KEYS = frozenset(
    {
        "prediction",
        "response_format",
        "reasoning_effort",
        "prompt_cache_key",
        "safe_prompt",
        "prompt_mode",
        "parallel_tool_calls",
    }
)


class MistralProvider:
    """``/v1/chat/completions`` adapter for Mistral (native protocol).

    This adapter handles Mistral-specific fields (``prediction``,
    ``reasoning_effort``, ``safe_prompt``, ``prompt_mode``,
    ``parallel_tool_calls``) that are passed through ``RequestInfo.extras``
    from the chain config. Standard OpenAI fields (``model``, ``messages``,
    ``temperature``, ``max_tokens``, ``tools``, ``response_format``,
    ``prompt_cache_key``) are handled identically to the generic
    :class:`OpenAICompatProvider`.
    """

    name = "mistral"

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
        url = base_url.rstrip("/") + "/chat/completions"
        body = _build_request_body(request)

        headers: dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        for key, value in extra_headers.items():
            headers[key] = value

        response = self._transport.post(
            url,
            headers=headers,
            json_body=body,
            timeout_seconds=timeout_seconds,
            transport_retries=transport_retries,
        )
        return _parse_response(response)


def _build_request_body(request: RequestInfo) -> dict[str, Any]:
    """Build the Mistral-specific request body.

    Standard fields (model, messages, temperature, max_tokens, tools) are
    handled identically to OpenAI. Mistral-specific fields are extracted
    from ``request.extras`` and validated/structured.
    """
    body: dict[str, Any] = {
        "model": request.model_slug,
        "messages": list(request.messages),
    }
    if request.temperature is not None:
        body["temperature"] = request.temperature
    if request.top_p is not None:
        body["top_p"] = request.top_p
    if request.max_tokens is not None:
        body["max_tokens"] = request.max_tokens
    if request.tools:
        body["tools"] = list(request.tools)

    # Process extras — split into Mistral-specific and generic.
    for key, value in request.extras.items():
        if key == "prediction":
            _apply_prediction(body, value)
        elif key == "response_format":
            _apply_response_format(body, value)
        else:
            # Generic passthrough: prompt_cache_key, reasoning_effort,
            # safe_prompt, prompt_mode, parallel_tool_calls, etc.
            body.setdefault(key, value)

    return body


def _apply_prediction(body: dict[str, Any], prediction: Any) -> None:
    """Apply the ``prediction`` field with validation.

    The ``prediction`` field enables predicted/guided output: the caller
    specifies the expected completion content, and the model can skip
    re-generating the known portions. This is the Mistral equivalent of
    OpenAI's "predicted outputs" feature.

    **Correct usage**: ``prediction.content`` = the *expected output*
    (e.g. previous summary, old code to be edited), NOT the input document.

    **Incorrect usage**: Putting the 28K input document in ``prediction``.
    The input document belongs in ``messages``; the prediction should only
    contain the much shorter expected output.

    This function validates the prediction shape and warns when the content
    exceeds a heuristic length (suggesting misuse).
    """
    if prediction is None:
        return
    if not isinstance(prediction, Mapping):
        logger.warning(
            "Mistral prediction field should be a mapping {type, content}, got %s",
            type(prediction).__name__,
        )
        body["prediction"] = prediction
        return
    pred_type = prediction.get("type")
    if pred_type != "content":
        logger.warning(
            "Mistral prediction type should be 'content', got %r",
            pred_type,
        )
    content = prediction.get("content", "")
    if isinstance(content, str) and len(content) > _PREDICTION_LENGTH_WARN_CHARS:
        logger.warning(
            "Mistral prediction content is %d chars — this field should contain "
            "the EXPECTED OUTPUT (e.g. previous summary to update), NOT the input "
            "document. Put the input document in messages and only the expected "
            "output here. Long predictions may indicate misuse.",
            len(content),
        )
    body["prediction"] = dict(prediction)


def _apply_response_format(body: dict[str, Any], response_format: Any) -> None:
    """Apply the ``response_format`` field with Mistral-specific defaults.

    Mistral supports two JSON modes:

    * ``{type: "json_object"}`` — any valid JSON, no schema enforcement.
      Schema conformance is ~64% on nested schemas.
    * ``{type: "json_schema", json_schema: {name, schema, strict}}`` —
      schema-constrained output with ``strict: true``. Schema conformance
      is ~100% even on deeply nested schemas. **Recommended.**

    When ``json_schema`` is used without an explicit ``strict`` field,
    this adapter auto-adds ``strict: true`` as the safe default (matching
    Mistral's own recommendation and the evidence from pydantic-ai stress
    tests showing 100% vs 64% conformance).
    """
    if not isinstance(response_format, Mapping):
        body["response_format"] = response_format
        return
    fmt_type = response_format.get("type")
    if fmt_type == "json_schema":
        # Auto-add strict: true if not explicitly set — safe default per
        # Mistral docs and pydantic-ai stress test results.
        json_schema = response_format.get("json_schema")
        if isinstance(json_schema, Mapping) and "strict" not in json_schema:
            rf = dict(response_format)
            rf["json_schema"] = dict(json_schema)
            rf["json_schema"]["strict"] = True
            body["response_format"] = rf
            return
    body["response_format"] = dict(response_format) if isinstance(response_format, Mapping) else response_format


def _parse_response(response: TransportResponse) -> ResponseInfo:
    """Parse Mistral response — reuses shared status mapping."""
    return parse_transport_response(response, _normalize_success)


def _normalize_success(body: Mapping[str, Any]) -> ResponseInfo:
    """Normalize a Mistral 200 response into canonical ResponseInfo.

    Mistral's chat completions response follows the OpenAI shape:
    ``choices[0].message.content``, ``usage.prompt_tokens``, etc.
    Cache tokens are reported in ``usage.prompt_tokens_details.cached_tokens``.
    """
    choices = cast(list[Mapping[str, Any]], body.get("choices", []))
    first = choices[0] if choices else {}
    message = cast(Mapping[str, Any], first.get("message", {}))
    text = cast(str, message.get("content") or "")
    finish_reason = cast(str, first.get("finish_reason") or "")
    raw_tool_calls = cast(list[Mapping[str, Any]], message.get("tool_calls") or [])
    tool_calls = tuple(raw_tool_calls)

    usage = cast(Mapping[str, Any], body.get("usage") or {})
    in_tokens = int(usage.get("prompt_tokens") or 0)
    out_tokens = int(usage.get("completion_tokens") or 0)
    prompt_details = usage.get("prompt_tokens_details")
    prompt_details_map = prompt_details if isinstance(prompt_details, Mapping) else {}
    cache_read_input_tokens = int(prompt_details_map.get("cached_tokens") or usage.get("cache_read_input_tokens") or 0)
    cache_creation_input_tokens = int(usage.get("cache_creation_input_tokens") or 0)

    extras: dict[str, Any] = {}
    for key in ("id", "model", "created", "object"):
        if key in body:
            extras[key] = body[key]

    # Mistral may return prediction_tokens in usage for predicted output stats
    if "prediction_tokens" in usage:
        extras["prediction_tokens"] = int(usage["prediction_tokens"])

    message_extras = {k: v for k, v in message.items() if k not in {"content", "role", "tool_calls"}}
    if message_extras:
        extras["message_extras"] = message_extras

    return ResponseInfo(
        text=text,
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        finish_reason=finish_reason,
        tool_calls=tool_calls,
        cache_read_input_tokens=cache_read_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        extras=extras,
    )
