"""OpenAI-compatible adapter contract — offline tests with fake transport.

Covers the ADR-9 §2 status-code split (200 / 400 / 401 / 429 / 5xx /
network), Postel's-Law response normalisation per ADR-9 §5 (canonical
fields + ``extras`` carrying provider-specific metadata), and the
adaptive-cooldown ``retry_after_seconds`` propagation from the
transport response into the typed transient error.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest

from fa.providers.base import RequestInfo, TransportResponse
from fa.providers.errors import (
    ProviderAuthError,
    ProviderRequestShapeError,
    ProviderTransientError,
)
from fa.providers.openai_compat import OpenAICompatProvider


@dataclass
class FakeTransport:
    """Test double: returns canned :class:`TransportResponse` per POST."""

    response: TransportResponse
    last_url: str = ""
    last_headers: dict[str, str] = field(default_factory=dict)
    last_body: dict[str, Any] = field(default_factory=dict)
    last_timeout: float = 0.0

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> TransportResponse:
        self.last_url = url
        self.last_headers = dict(headers)
        self.last_body = dict(json_body)
        self.last_timeout = timeout_seconds
        return self.response


def _request() -> RequestInfo:
    return RequestInfo(
        model_slug="deepseek/deepseek-chat-v3",
        messages=({"role": "user", "content": "hi"},),
        temperature=0.2,
        max_tokens=512,
    )


def test_request_builds_chat_completions_url_and_authorization_header() -> None:
    transport = FakeTransport(
        response=TransportResponse(
            status=200,
            body={
                "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3},
                "id": "chatcmpl-x",
                "model": "deepseek/deepseek-chat-v3",
            },
        ),
    )
    provider = OpenAICompatProvider(transport=transport)
    response = provider.request(
        _request(),
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-test",
        timeout_seconds=60.0,
        extra_headers={"HTTP-Referer": "https://example/"},
    )
    assert transport.last_url == "https://openrouter.ai/api/v1/chat/completions"
    assert transport.last_headers["Authorization"] == "Bearer sk-test"
    assert transport.last_headers["HTTP-Referer"] == "https://example/"
    assert transport.last_body["model"] == "deepseek/deepseek-chat-v3"
    assert transport.last_body["messages"] == [{"role": "user", "content": "hi"}]
    assert transport.last_body["temperature"] == 0.2
    assert transport.last_body["max_tokens"] == 512
    assert response.text == "hello"
    assert response.in_tokens == 7
    assert response.out_tokens == 3
    assert response.finish_reason == "stop"
    assert response.extras["id"] == "chatcmpl-x"


def test_request_strips_trailing_slash_on_base_url() -> None:
    transport = FakeTransport(
        response=TransportResponse(status=200, body={"choices": [], "usage": {}})
    )
    provider = OpenAICompatProvider(transport=transport)
    provider.request(
        _request(),
        base_url="https://api.fireworks.ai/inference/v1/",
        api_key="k",
        timeout_seconds=60.0,
        extra_headers={},
    )
    assert transport.last_url == "https://api.fireworks.ai/inference/v1/chat/completions"


def test_response_preserves_tool_calls_and_provider_extras() -> None:
    transport = FakeTransport(
        response=TransportResponse(
            status=200,
            body={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [{"id": "tc-1", "type": "function"}],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 0},
                "system_fingerprint": "fp-123",
                "provider": {"name": "openrouter"},
            },
        ),
    )
    provider = OpenAICompatProvider(transport=transport)
    response = provider.request(
        _request(),
        base_url="https://openrouter.ai/api/v1",
        api_key="k",
        timeout_seconds=60.0,
        extra_headers={},
    )
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["id"] == "tc-1"
    assert response.finish_reason == "tool_calls"
    assert response.extras["system_fingerprint"] == "fp-123"
    assert response.extras["provider"] == {"name": "openrouter"}


@pytest.mark.parametrize("status", [400, 422])
def test_4xx_request_shape_fail_fast(status: int) -> None:
    transport = FakeTransport(response=TransportResponse(status=status, body={"error": "bad"}))
    provider = OpenAICompatProvider(transport=transport)
    with pytest.raises(ProviderRequestShapeError) as info:
        provider.request(
            _request(),
            base_url="https://x.example/v1",
            api_key="k",
            timeout_seconds=60.0,
            extra_headers={},
        )
    assert info.value.status == status


@pytest.mark.parametrize("status", [401, 403])
def test_4xx_auth_continue_chain(status: int) -> None:
    transport = FakeTransport(response=TransportResponse(status=status, body={}))
    provider = OpenAICompatProvider(transport=transport)
    with pytest.raises(ProviderAuthError) as info:
        provider.request(
            _request(),
            base_url="https://x.example/v1",
            api_key="k",
            timeout_seconds=60.0,
            extra_headers={},
        )
    assert info.value.status == status


@pytest.mark.parametrize(
    "status,expected_kind",
    [(429, "rate_limited"), (500, "service_unavailable"), (503, "service_unavailable")],
)
def test_transient_status_codes_carry_retry_after(status: int, expected_kind: str) -> None:
    transport = FakeTransport(
        response=TransportResponse(status=status, body={}, retry_after_seconds=42.0)
    )
    provider = OpenAICompatProvider(transport=transport)
    with pytest.raises(ProviderTransientError) as info:
        provider.request(
            _request(),
            base_url="https://x.example/v1",
            api_key="k",
            timeout_seconds=60.0,
            extra_headers={},
        )
    assert info.value.status == status
    assert info.value.kind == expected_kind
    assert info.value.retry_after_seconds == 42.0


def test_network_error_is_transient_timeout() -> None:
    transport = FakeTransport(
        response=TransportResponse(status=0, body={}, network_error="connection refused")
    )
    provider = OpenAICompatProvider(transport=transport)
    with pytest.raises(ProviderTransientError) as info:
        provider.request(
            _request(),
            base_url="https://x.example/v1",
            api_key="k",
            timeout_seconds=60.0,
            extra_headers={},
        )
    assert info.value.kind == "timeout"
    assert info.value.retry_after_seconds == 0.0
