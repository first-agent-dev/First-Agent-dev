"""Tests for the Mistral chat completions adapter.

Verifies:
- Request body construction with Mistral-specific fields
- Prediction field validation (warn on long content)
- Response format auto-strict for json_schema
- Response normalization (cache tokens, prediction tokens)
- Error mapping (shared via parse_transport_response)
- Integration with chain config extras
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import pytest

from fa.providers.base import (
    RequestInfo,
    TransportResponse,
)
from fa.providers.errors import (
    ProviderAuthError,
    ProviderRequestShapeError,
    ProviderTransientError,
)
from fa.providers.mistral import (
    _PREDICTION_LENGTH_WARN_CHARS,
    MISTRAL_RECOGNIZED_PROVIDER_PARAMS_KEYS,
    MistralProvider,
    _apply_prediction,
    _apply_response_format,
    _build_request_body,
)

# ── Fake transport ──────────────────────────────────────────────────


class FakeTransport:
    """Deterministic transport for offline tests."""

    def __init__(self, response: TransportResponse) -> None:
        self._response = response
        self.last_url: str = ""
        self.last_headers: dict[str, str] = {}
        self.last_body: dict[str, Any] = {}

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
        return self._response


def _success_response(body: dict[str, Any] | None = None) -> TransportResponse:
    """Build a 200 TransportResponse with a typical Mistral success body."""
    if body is None:
        body = {
            "id": "cmpl-test123",
            "object": "chat.completion",
            "model": "mistral-medium-2604",
            "created": 1702256327,
            "choices": [
                {
                    "index": 0,
                    "message": {"content": "Hello!", "role": "assistant"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
                "prompt_tokens_details": {"cached_tokens": 80},
            },
        }
    return TransportResponse(status=200, body=body)


# ── Request body construction ───────────────────────────────────────


class TestBuildRequestBody:
    """Test _build_request_body with Mistral-specific fields."""

    def test_basic_fields(self) -> None:
        """Standard fields are set correctly."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
            temperature=0.3,
            max_tokens=2000,
        )
        body = _build_request_body(request)
        assert body["model"] == "mistral-medium-2604"
        assert body["messages"] == [{"role": "user", "content": "Hi"}]
        assert body["temperature"] == 0.3
        assert body["max_tokens"] == 2000

    def test_prediction_forwarded(self) -> None:
        """Prediction field is forwarded from extras."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Update summary"},),
            extras={"prediction": {"type": "content", "content": "Old summary here"}},
        )
        body = _build_request_body(request)
        assert body["prediction"] == {"type": "content", "content": "Old summary here"}

    def test_reasoning_effort_forwarded(self) -> None:
        """reasoning_effort is forwarded from extras."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Think"},),
            extras={"reasoning_effort": "high"},
        )
        body = _build_request_body(request)
        assert body["reasoning_effort"] == "high"

    def test_prompt_cache_key_forwarded(self) -> None:
        """prompt_cache_key is forwarded from extras."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
            extras={"prompt_cache_key": "session-42"},
        )
        body = _build_request_body(request)
        assert body["prompt_cache_key"] == "session-42"

    def test_safe_prompt_forwarded(self) -> None:
        """safe_prompt is forwarded from extras."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
            extras={"safe_prompt": True},
        )
        body = _build_request_body(request)
        assert body["safe_prompt"] is True

    def test_parallel_tool_calls_forwarded(self) -> None:
        """parallel_tool_calls is forwarded from extras."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
            extras={"parallel_tool_calls": True},
        )
        body = _build_request_body(request)
        assert body["parallel_tool_calls"] is True

    def test_tools_forwarded(self) -> None:
        """Function tools are forwarded."""
        tools = (
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        )
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
            tools=tools,
        )
        body = _build_request_body(request)
        assert body["tools"] == list(tools)

    def test_no_temperature_when_none(self) -> None:
        """temperature is omitted when None."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
        )
        body = _build_request_body(request)
        assert "temperature" not in body

    def test_no_max_tokens_when_none(self) -> None:
        """max_tokens is omitted when None."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
        )
        body = _build_request_body(request)
        assert "max_tokens" not in body

    def test_recognized_provider_params_keys_are_all_actually_forwarded(self) -> None:
        """Anti-drift regression: MISTRAL_RECOGNIZED_PROVIDER_PARAMS_KEYS is
        consumed by fa.providers.routing_lint as the single source of truth
        for "does this adapter recognise this provider_params key" — if the
        constant claims a key is recognised but _build_request_body actually
        drops it, routing-check would give a false "OK" for a config whose
        provider_params silently never reaches the request. Found stale
        2026-07-24: the constant previously listed only 5 of the 7 keys
        _build_request_body actually accepts (missing "response_format" and
        "prompt_cache_key") despite being unused by any code path at the
        time, so nothing caught the drift. This test is that catch.
        """
        sample_values: dict[str, object] = {
            "prediction": {"type": "content", "content": "x"},
            "response_format": {"type": "json_object"},
            "reasoning_effort": "high",
            "prompt_cache_key": "some-key",
            "safe_prompt": True,
            "prompt_mode": "reasoning",
            "parallel_tool_calls": False,
        }
        assert set(sample_values) == MISTRAL_RECOGNIZED_PROVIDER_PARAMS_KEYS, (
            "This test's sample_values must be kept in sync with the exported "
            "constant so every recognised key is exercised below."
        )
        for key, value in sample_values.items():
            request = RequestInfo(
                model_slug="mistral-medium-2604",
                messages=({"role": "user", "content": "Hi"},),
                extras={key: value},
            )
            body = _build_request_body(request)
            assert key in body, f"recognised key {key!r} was NOT forwarded into the request body"


# ── Prediction validation ───────────────────────────────────────────


class TestPredictionValidation:
    """Test _apply_prediction validation and warnings."""

    def test_valid_prediction(self) -> None:
        """Valid prediction is applied without warnings."""
        body: dict[str, Any] = {}
        _apply_prediction(body, {"type": "content", "content": "Expected output"})
        assert body["prediction"] == {"type": "content", "content": "Expected output"}

    def test_none_prediction_skipped(self) -> None:
        """None prediction is silently skipped."""
        body: dict[str, Any] = {}
        _apply_prediction(body, None)
        assert "prediction" not in body

    def test_long_prediction_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """Long prediction content triggers a warning about misuse."""
        body: dict[str, Any] = {}
        long_content = "x" * (_PREDICTION_LENGTH_WARN_CHARS + 1)
        with caplog.at_level(logging.WARNING, logger="fa.providers.mistral"):
            _apply_prediction(body, {"type": "content", "content": long_content})
        assert body["prediction"]["content"] == long_content
        assert "EXPECTED OUTPUT" in caplog.text
        assert "NOT the input document" in caplog.text

    def test_short_prediction_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Short prediction content does not trigger warnings."""
        body: dict[str, Any] = {}
        with caplog.at_level(logging.WARNING, logger="fa.providers.mistral"):
            _apply_prediction(body, {"type": "content", "content": "Short"})
        assert "prediction" in body
        assert "EXPECTED OUTPUT" not in caplog.text

    def test_non_mapping_prediction_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """Non-mapping prediction triggers a warning but is still forwarded."""
        body: dict[str, Any] = {}
        with caplog.at_level(logging.WARNING, logger="fa.providers.mistral"):
            _apply_prediction(body, "bad_prediction")
        assert body["prediction"] == "bad_prediction"
        assert "mapping" in caplog.text.lower()

    def test_wrong_type_prediction_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """prediction with wrong type field triggers a warning."""
        body: dict[str, Any] = {}
        with caplog.at_level(logging.WARNING, logger="fa.providers.mistral"):
            _apply_prediction(body, {"type": "other", "content": "x"})
        assert "content" in caplog.text.lower()


# ── Response format ─────────────────────────────────────────────────


class TestResponseFormat:
    """Test _apply_response_format with Mistral-specific defaults."""

    def test_json_schema_auto_strict(self) -> None:
        """json_schema without explicit strict gets strict=True."""
        body: dict[str, Any] = {}
        _apply_response_format(
            body,
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "summary",
                    "schema": {
                        "type": "object",
                        "properties": {"points": {"type": "array", "items": {"type": "string"}}},
                        "required": ["points"],
                    },
                },
            },
        )
        assert body["response_format"]["json_schema"]["strict"] is True

    def test_json_schema_explicit_strict_preserved(self) -> None:
        """json_schema with explicit strict=False is preserved."""
        body: dict[str, Any] = {}
        _apply_response_format(
            body,
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "summary",
                    "schema": {"type": "object", "properties": {}},
                    "strict": False,
                },
            },
        )
        assert body["response_format"]["json_schema"]["strict"] is False

    def test_json_object_passthrough(self) -> None:
        """json_object type is passed through unchanged."""
        body: dict[str, Any] = {}
        _apply_response_format(body, {"type": "json_object"})
        assert body["response_format"] == {"type": "json_object"}

    def test_text_type_passthrough(self) -> None:
        """text type is passed through unchanged."""
        body: dict[str, Any] = {}
        _apply_response_format(body, {"type": "text"})
        assert body["response_format"] == {"type": "text"}


# ── Full adapter request ────────────────────────────────────────────


class TestMistralProviderRequest:
    """Test MistralProvider.request end-to-end."""

    def test_url_and_headers(self) -> None:
        """URL is /chat/completions with Bearer auth."""
        transport = FakeTransport(_success_response())
        provider = MistralProvider(transport)
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
        )
        provider.request(
            request,
            base_url="https://api.mistral.ai/v1",
            api_key="test-key",
            timeout_seconds=30,
            transport_retries=1,
            extra_headers={},
        )
        assert transport.last_url == "https://api.mistral.ai/v1/chat/completions"
        assert transport.last_headers["Authorization"] == "Bearer test-key"

    def test_extras_in_body(self) -> None:
        """Role-level extras are forwarded in the request body."""
        transport = FakeTransport(_success_response())
        provider = MistralProvider(transport)
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
            extras={
                "prompt_cache_key": "session-42",
                "reasoning_effort": "high",
                "safe_prompt": True,
            },
        )
        provider.request(
            request,
            base_url="https://api.mistral.ai/v1",
            api_key="test-key",
            timeout_seconds=30,
            transport_retries=1,
            extra_headers={},
        )
        body = transport.last_body
        assert body["prompt_cache_key"] == "session-42"
        assert body["reasoning_effort"] == "high"
        assert body["safe_prompt"] is True


# ── Response normalization ──────────────────────────────────────────


class TestMistralResponseNormalization:
    """Test Mistral response parsing."""

    def test_basic_response(self) -> None:
        """Basic 200 response is normalized correctly."""
        transport = FakeTransport(_success_response())
        provider = MistralProvider(transport)
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
        )
        response = provider.request(
            request,
            base_url="https://api.mistral.ai/v1",
            api_key="test-key",
            timeout_seconds=30,
            transport_retries=1,
            extra_headers={},
        )
        assert response.text == "Hello!"
        assert response.in_tokens == 100
        assert response.out_tokens == 10
        assert response.finish_reason == "stop"
        assert response.cache_read_input_tokens == 80

    def test_tool_calls_response(self) -> None:
        """Response with tool calls is normalized correctly."""
        body = {
            "id": "cmpl-test",
            "model": "mistral-medium-2604",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "search", "arguments": '{"q": "test"}'},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 5},
        }
        transport = FakeTransport(TransportResponse(status=200, body=body))
        provider = MistralProvider(transport)
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Search"},),
        )
        response = provider.request(
            request,
            base_url="https://api.mistral.ai/v1",
            api_key="test-key",
            timeout_seconds=30,
            transport_retries=1,
            extra_headers={},
        )
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "search"
        assert response.finish_reason == "tool_calls"

    def test_prediction_tokens_in_extras(self) -> None:
        """prediction_tokens from usage is captured in extras."""
        body = {
            "id": "cmpl-test",
            "model": "mistral-medium-2604",
            "choices": [{"index": 0, "message": {"content": "Updated", "role": "assistant"}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "prediction_tokens": 45,
            },
        }
        transport = FakeTransport(TransportResponse(status=200, body=body))
        provider = MistralProvider(transport)
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Update"},),
        )
        response = provider.request(
            request,
            base_url="https://api.mistral.ai/v1",
            api_key="test-key",
            timeout_seconds=30,
            transport_retries=1,
            extra_headers={},
        )
        assert response.extras.get("prediction_tokens") == 45

    def test_cache_tokens_from_prompt_tokens_details(self) -> None:
        """Cache tokens from usage.prompt_tokens_details.cached_tokens."""
        body = {
            "id": "cmpl-test",
            "model": "mistral-medium-2604",
            "choices": [{"index": 0, "message": {"content": "Hi", "role": "assistant"}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 200,
                "completion_tokens": 10,
                "prompt_tokens_details": {"cached_tokens": 150},
            },
        }
        transport = FakeTransport(TransportResponse(status=200, body=body))
        provider = MistralProvider(transport)
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
        )
        response = provider.request(
            request,
            base_url="https://api.mistral.ai/v1",
            api_key="test-key",
            timeout_seconds=30,
            transport_retries=1,
            extra_headers={},
        )
        assert response.cache_read_input_tokens == 150
        assert response.in_tokens == 200


# ── Error mapping ───────────────────────────────────────────────────


class TestMistralErrorMapping:
    """Test that Mistral provider uses shared error mapping."""

    def test_auth_error(self) -> None:
        """401 raises ProviderAuthError."""
        transport = FakeTransport(TransportResponse(status=401, body={"error": "unauthorized"}))
        provider = MistralProvider(transport)
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
        )
        with pytest.raises(ProviderAuthError):
            provider.request(
                request,
                base_url="https://api.mistral.ai/v1",
                api_key="bad-key",
                timeout_seconds=30,
                transport_retries=0,
                extra_headers={},
            )

    def test_transient_error_429(self) -> None:
        """429 raises ProviderTransientError."""
        transport = FakeTransport(TransportResponse(status=429, body={"error": "rate limited"}))
        provider = MistralProvider(transport)
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
        )
        with pytest.raises(ProviderTransientError) as exc_info:
            provider.request(
                request,
                base_url="https://api.mistral.ai/v1",
                api_key="test-key",
                timeout_seconds=30,
                transport_retries=0,
                extra_headers={},
            )
        assert exc_info.value.kind == "rate_limited"

    def test_shape_error_422(self) -> None:
        """422 raises ProviderRequestShapeError."""
        transport = FakeTransport(TransportResponse(status=422, body={"error": "validation"}))
        provider = MistralProvider(transport)
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
        )
        with pytest.raises(ProviderRequestShapeError):
            provider.request(
                request,
                base_url="https://api.mistral.ai/v1",
                api_key="test-key",
                timeout_seconds=30,
                transport_retries=0,
                extra_headers={},
            )


# ── Registry integration ────────────────────────────────────────────


class TestMistralRegistry:
    """Test that mistral is registered in the provider registry."""

    def test_mistral_in_providers(self) -> None:
        """'mistral' is a registered provider."""
        from fa.providers.registry import PROVIDERS

        assert "mistral" in PROVIDERS

    def test_mistral_adapter_name(self) -> None:
        """mistral provider has adapter='mistral'."""
        from fa.providers.registry import PROVIDERS

        assert PROVIDERS["mistral"].adapter == "mistral"

    def test_mistral_agents_in_providers(self) -> None:
        """'mistral_agents' is a registered provider."""
        from fa.providers.registry import PROVIDERS

        assert "mistral_agents" in PROVIDERS

    def test_mistral_agents_adapter_name(self) -> None:
        """mistral_agents provider has adapter='mistral_agents'."""
        from fa.providers.registry import PROVIDERS

        assert PROVIDERS["mistral_agents"].adapter == "mistral_agents"

    def test_build_provider_mistral(self) -> None:
        """build_provider('mistral') returns a MistralProvider."""
        from fa.providers.mistral import MistralProvider
        from fa.providers.registry import build_provider

        class FakeTransportForBuild:
            def post(self, *args: Any, **kwargs: Any) -> Any:
                return None  # never called

        provider = build_provider("mistral", transport=FakeTransportForBuild())
        assert isinstance(provider, MistralProvider)
        assert provider.name == "mistral"


def test_unrecognized_extras_filtered_out() -> None:
    """Unrecognized extras (e.g. prompt_cache_retention) are filtered out."""
    req = RequestInfo(
        model_slug="mistral-small-2603",
        messages=({"role": "user", "content": "hi"},),
        extras={"prompt_cache_retention": "1h", "prompt_cache_key": "valid-key"},
    )
    body = _build_request_body(req)
    assert "prompt_cache_retention" not in body
    assert body["prompt_cache_key"] == "valid-key"


def test_list_content_normalization() -> None:
    """Mistral responses with list-based content blocks normalize correctly to str."""
    from fa.providers.mistral import _normalize_success

    body = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "text": "internal thought"},
                        {"type": "text", "text": "hello world"},
                    ],
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    response_info = _normalize_success(body)
    assert response_info.text == "hello world"
