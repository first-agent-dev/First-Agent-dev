"""OpenAI-compatible adapter contract — offline tests with fake transport.

Covers the ADR-9 §2 status-code split (200 / 400 / 401 / 429 / 5xx /
network), Postel's-Law response normalisation per ADR-9 §5 (canonical
fields + ``extras`` carrying provider-specific metadata), and the
adaptive-cooldown ``retry_after_seconds`` propagation from the
transport response into the typed transient error.
"""

from __future__ import annotations

import urllib.error
from collections.abc import Mapping
from dataclasses import dataclass, field
from email.message import Message
from types import TracebackType
from typing import Any, ClassVar, Literal, Self, override

import pytest

from fa.providers.base import RequestInfo, TransportResponse
from fa.providers.errors import (
    ProviderAuthError,
    ProviderRequestShapeError,
    ProviderTransientError,
)
from fa.providers.openai_compat import OpenAICompatProvider
from fa.providers.transport import UrllibTransport, _transport_retry_delay_s


@dataclass
class FakeTransport:
    """Test double: returns canned :class:`TransportResponse` per POST."""

    response: TransportResponse
    last_url: str = ""
    last_headers: dict[str, str] = field(default_factory=dict)
    last_body: dict[str, Any] = field(default_factory=dict)
    last_timeout: float = 0.0
    last_transport_retries: int = -1

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
        transport_retries: int,
    ) -> TransportResponse:
        self.last_url = url
        self.last_headers = dict(headers)
        self.last_body = dict(json_body)
        self.last_timeout = timeout_seconds
        self.last_transport_retries = transport_retries
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
        transport_retries=0,
        extra_headers={"HTTP-Referer": "https://example/"},
    )
    assert transport.last_url == "https://openrouter.ai/api/v1/chat/completions"
    assert transport.last_headers["Authorization"] == "Bearer sk-test"
    assert transport.last_headers["HTTP-Referer"] == "https://example/"
    assert transport.last_body["model"] == "deepseek/deepseek-chat-v3"
    assert transport.last_body["messages"] == [{"role": "user", "content": "hi"}]
    assert transport.last_body["temperature"] == 0.2
    assert transport.last_body["max_tokens"] == 512
    assert transport.last_transport_retries == 0
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
        transport_retries=0,
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
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 0,
                    "prompt_tokens_details": {"cached_tokens": 6},
                },
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
        transport_retries=0,
        extra_headers={},
    )
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["id"] == "tc-1"
    assert response.finish_reason == "tool_calls"
    assert response.cache_read_input_tokens == 6
    assert response.cache_creation_input_tokens == 0
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
            transport_retries=0,
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
            transport_retries=0,
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
            transport_retries=0,
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
            transport_retries=0,
            extra_headers={},
        )
    assert info.value.kind == "timeout"
    assert info.value.retry_after_seconds == 0.0


def test_transport_retry_delay_is_bounded() -> None:
    delay = _transport_retry_delay_s(5, base_seconds=0.25, cap_seconds=2.0, random_fn=lambda: 1.0)
    assert delay == 2.0


def test_urllib_transport_retries_network_errors_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    class _Resp:
        status = 200
        headers: ClassVar[dict[str, str]] = {}

        def read(self) -> bytes:
            return b'{"ok": true}'

        def __enter__(self) -> Self:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> Literal[False]:
            del exc_type, exc, tb
            return False

    def _fake_urlopen(request: object, timeout: float) -> _Resp:
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.URLError("temporary dns")
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    transport = UrllibTransport(sleep_fn=sleeps.append, random_fn=lambda: 1.0)
    resp = transport.post(
        "https://example.invalid/v1/chat/completions",
        headers={"Authorization": "Bearer k"},
        json_body={"x": 1},
        timeout_seconds=5.0,
        transport_retries=1,
    )
    assert len(calls) == 2
    assert sleeps == [0.25]
    assert resp.status == 200
    assert resp.network_error is None


def test_urllib_transport_does_not_retry_http_status(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    class _HttpErr(urllib.error.HTTPError):
        def __init__(self) -> None:
            super().__init__(
                "https://x.invalid",
                503,
                "svc unavailable",
                hdrs=Message(),
                fp=None,
            )

        @override
        def read(self, n: int = -1) -> bytes:
            del n
            return b"{}"

    def _fake_urlopen(request: object, timeout: float) -> object:
        calls.append(1)
        raise _HttpErr()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    transport = UrllibTransport(sleep_fn=lambda s: None, random_fn=lambda: 1.0)
    resp = transport.post(
        "https://example.invalid/v1/chat/completions",
        headers={"Authorization": "Bearer k"},
        json_body={"x": 1},
        timeout_seconds=5.0,
        transport_retries=3,
    )
    assert len(calls) == 1
    assert resp.status == 503
