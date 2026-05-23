"""OpenAI-compatible adapter — shared transport for ``/chat/completions``.

Covers every OpenAI-compatible provider per ADR-9 §5 Category 1:
OpenRouter, Fireworks, NVIDIA Build, Groq, GitHub Models, Modal,
Together AI, Lambda Labs, vLLM, Ollama, ZAI, MiniMax, Cerebras,
Perplexity, xAI. Adding a new provider in this category = 1 row in
:mod:`fa.providers.registry` + 1 YAML chain entry; no new file.

The adapter parses the response into the canonical
:class:`fa.providers.base.ResponseInfo` (Postel's Law surface) and
raises typed errors from :mod:`fa.providers.errors` for each of the
ADR-9 §2 status-code splits:

* ``200`` → :class:`ResponseInfo`.
* ``401 / 403`` → :class:`ProviderAuthError` (continue chain).
* ``400 / 422`` → :class:`ProviderRequestShapeError` (fail fast).
* ``429 / 5xx`` or network error → :class:`ProviderTransientError`
  (continue chain + cool down).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from fa.providers.base import (
    RequestInfo,
    ResponseInfo,
    Transport,
    TransportResponse,
)
from fa.providers.errors import (
    ProviderAuthError,
    ProviderRequestShapeError,
    ProviderTransientError,
)


class OpenAICompatProvider:
    """Shared adapter for every OpenAI-shaped ``/chat/completions`` provider."""

    name = "openai_compat"

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
        url = base_url.rstrip("/") + "/chat/completions"
        body: dict[str, Any] = {
            "model": request.model_slug,
            "messages": list(request.messages),
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.tools:
            body["tools"] = list(request.tools)
        for key, value in request.extras.items():
            body.setdefault(key, value)

        headers: dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        for key, value in extra_headers.items():
            headers[key] = value

        response = self._transport.post(
            url, headers=headers, json_body=body, timeout_seconds=timeout_seconds
        )
        return _parse_response(response)


def _parse_response(response: TransportResponse) -> ResponseInfo:
    if response.network_error is not None:
        raise ProviderTransientError(
            f"network_error: {response.network_error}",
            status=0,
            kind="timeout",
            retry_after_seconds=0.0,
        )
    status = response.status
    if status == 200:
        return _normalize_success(response.body)
    if status in {400, 422}:
        raise ProviderRequestShapeError(
            f"request_shape_error: status={status} body={response.body!r}", status=status
        )
    if status in {401, 403}:
        raise ProviderAuthError(f"auth_error: status={status}", status=status)
    if status == 429 or 500 <= status <= 504:
        kind = "rate_limited" if status == 429 else "service_unavailable"
        raise ProviderTransientError(
            f"{kind}: status={status}",
            status=status,
            kind=kind,
            retry_after_seconds=response.retry_after_seconds or 0.0,
        )
    raise ProviderTransientError(
        f"unexpected_status: status={status}",
        status=status,
        kind="service_unavailable",
        retry_after_seconds=response.retry_after_seconds or 0.0,
    )


def _normalize_success(body: Mapping[str, Any]) -> ResponseInfo:
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

    extras: dict[str, Any] = {}
    for key in ("system_fingerprint", "provider", "id", "created", "model"):
        if key in body:
            extras[key] = body[key]

    return ResponseInfo(
        text=text,
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        finish_reason=finish_reason,
        tool_calls=tool_calls,
        extras=extras,
    )
