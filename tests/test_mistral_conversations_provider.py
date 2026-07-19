"""Tests for the Mistral Conversations API adapter.

Verifies:
- Request body construction (inputs, instructions, completion_args, tools)
- Built-in tool handling (web_search, code_interpreter, document_library)
- Response normalization (outputs, conversation_id, usage)
- Function tool conversion
- Error mapping
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from fa.providers.base import (
    RequestInfo,
    ResponseInfo,
    TransportResponse,
)
from fa.providers.errors import ProviderAuthError, ProviderTransientError
from fa.providers.mistral_conversations import (
    MistralConversationsProvider,
    _build_conversations_body,
)


# ── Fake transport ──────────────────────────────────────────────────


class FakeTransport:
    """Deterministic transport for offline tests."""

    def __init__(self, response: TransportResponse) -> None:
        self._response = response
        self.last_url: str = ""
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
        self.last_body = dict(json_body)
        return self._response


def _conversations_success(body: dict[str, Any] | None = None) -> TransportResponse:
    """Build a 200 TransportResponse with a Conversations API success body."""
    if body is None:
        body = {
            "conversation_id": "conv-123",
            "outputs": [
                {
                    "type": "message.output",
                    "content": "The capital of France is Paris.",
                    "role": "assistant",
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
            },
        }
    return TransportResponse(status=200, body=body)


# ── Request body construction ───────────────────────────────────────


class TestBuildConversationsBody:
    """Test _build_conversations_body."""

    def test_basic_mapping(self) -> None:
        """messages → inputs, model set."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=(
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
            ),
        )
        body = _build_conversations_body(request)
        assert body["model"] == "mistral-medium-2604"
        assert body["inputs"] == [{"role": "user", "content": "Hello"}]
        assert body["instructions"] == "You are helpful"

    def test_system_messages_become_instructions(self) -> None:
        """Multiple system messages are joined into instructions."""
        request = RequestInfo(
            model_slug="mistral-small-latest",
            messages=(
                {"role": "system", "content": "Part 1"},
                {"role": "system", "content": "Part 2"},
                {"role": "user", "content": "Hi"},
            ),
        )
        body = _build_conversations_body(request)
        assert "Part 1" in body["instructions"]
        assert "Part 2" in body["instructions"]
        assert len(body["inputs"]) == 1

    def test_completion_args_from_temperature_max_tokens(self) -> None:
        """temperature and max_tokens go into completion_args."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
            temperature=0.2,
            max_tokens=2000,
        )
        body = _build_conversations_body(request)
        assert body["completion_args"]["temperature"] == 0.2
        assert body["completion_args"]["max_tokens"] == 2000

    def test_builtin_tools_from_extras(self) -> None:
        """Built-in tools from extras["mistral_tools"] are added."""
        request = RequestInfo(
            model_slug="mistral-small-latest",
            messages=({"role": "user", "content": "Search"},),
            extras={
                "mistral_tools": [
                    {"type": "web_search"},
                    {"type": "code_interpreter"},
                ],
            },
        )
        body = _build_conversations_body(request)
        assert {"type": "web_search"} in body["tools"]
        assert {"type": "code_interpreter"} in body["tools"]

    def test_function_tools_converted(self) -> None:
        """Function tools are converted to Conversations API format."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
            tools=(
                {
                    "type": "function",
                    "function": {
                        "name": "search",
                        "description": "Search the web",
                        "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
                    },
                },
            ),
        )
        body = _build_conversations_body(request)
        assert len(body["tools"]) == 1
        func_tool = body["tools"][0]
        assert func_tool["type"] == "function"
        assert func_tool["function"]["name"] == "search"

    def test_mixed_tools(self) -> None:
        """Built-in and function tools coexist."""
        request = RequestInfo(
            model_slug="mistral-small-latest",
            messages=({"role": "user", "content": "Search"},),
            tools=(
                {
                    "type": "function",
                    "function": {
                        "name": "my_tool",
                        "description": "Custom tool",
                        "parameters": {},
                    },
                },
            ),
            extras={
                "mistral_tools": [{"type": "web_search"}],
            },
        )
        body = _build_conversations_body(request)
        tool_types = [t.get("type") for t in body["tools"]]
        assert "function" in tool_types
        assert "web_search" in tool_types

    def test_extras_in_completion_args(self) -> None:
        """Mistral-specific extras go into completion_args."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
            extras={
                "response_format": {"type": "json_object"},
                "reasoning_effort": "high",
                "prompt_cache_key": "session-42",
            },
        )
        body = _build_conversations_body(request)
        ca = body["completion_args"]
        assert ca["response_format"] == {"type": "json_object"}
        assert ca["reasoning_effort"] == "high"
        assert ca["prompt_cache_key"] == "session-42"

    def test_agent_id_replaces_model(self) -> None:
        """agent_id from extras replaces model in the body."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
            extras={"agent_id": "agent-xyz"},
        )
        body = _build_conversations_body(request)
        assert body["agent_id"] == "agent-xyz"
        assert "model" not in body

    def test_store_default_true(self) -> None:
        """store defaults to True."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
        )
        body = _build_conversations_body(request)
        assert body["store"] is True

    def test_store_from_extras(self) -> None:
        """store can be overridden via extras."""
        request = RequestInfo(
            model_slug="mistral-medium-2604",
            messages=({"role": "user", "content": "Hi"},),
            extras={"store": False},
        )
        body = _build_conversations_body(request)
        assert body["store"] is False

    def test_invalid_mistral_tools_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        """Invalid mistral_tools entries are skipped with a warning."""
        import logging
        request = RequestInfo(
            model_slug="mistral-small-latest",
            messages=({"role": "user", "content": "Hi"},),
            extras={
                "mistral_tools": [
                    {"type": "invalid_tool"},
                    "not_a_dict",
                ],
            },
        )
        with caplog.at_level(logging.WARNING, logger="fa.providers.mistral_conversations"):
            body = _build_conversations_body(request)
        assert "tools" not in body or not body.get("tools")


# ── Response normalization ──────────────────────────────────────────


class TestConversationsResponseNormalization:
    """Test Conversations API response parsing."""

    def test_basic_message_output(self) -> None:
        """message.output with text content is normalized."""
        transport = FakeTransport(_conversations_success())
        provider = MistralConversationsProvider(transport)
        request = RequestInfo(
            model_slug="mistral-small-latest",
            messages=({"role": "user", "content": "Hello"},),
        )
        response = provider.request(
            request,
            base_url="https://api.mistral.ai/v1",
            api_key="test-key",
            timeout_seconds=30,
            transport_retries=1,
            extra_headers={},
        )
        assert response.text == "The capital of France is Paris."
        assert response.in_tokens == 50
        assert response.out_tokens == 10
        assert response.extras.get("conversation_id") == "conv-123"

    def test_tool_call_output(self) -> None:
        """message.output with tool_calls is normalized."""
        body = {
            "conversation_id": "conv-456",
            "outputs": [
                {
                    "type": "message.output",
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "web_search", "arguments": '{"q": "test"}'},
                        }
                    ],
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }
        transport = FakeTransport(TransportResponse(status=200, body=body))
        provider = MistralConversationsProvider(transport)
        request = RequestInfo(
            model_slug="mistral-small-latest",
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
        assert response.tool_calls[0]["function"]["name"] == "web_search"
        assert response.finish_reason == "tool_calls"

    def test_tool_execution_and_references_in_extras(self) -> None:
        """tool.execution and reference.output are captured in extras."""
        body = {
            "conversation_id": "conv-789",
            "outputs": [
                {"type": "tool.execution", "name": "web_search", "content": "Search results..."},
                {"type": "reference.output", "url": "https://example.com", "title": "Example"},
                {"type": "message.output", "content": "Based on search results...", "role": "assistant"},
            ],
            "usage": {"prompt_tokens": 80, "completion_tokens": 30},
        }
        transport = FakeTransport(TransportResponse(status=200, body=body))
        provider = MistralConversationsProvider(transport)
        request = RequestInfo(
            model_slug="mistral-small-latest",
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
        assert "tool_executions" in response.extras
        assert len(response.extras["tool_executions"]) == 1
        assert "references" in response.extras
        assert len(response.extras["references"]) == 1

    def test_cache_tokens(self) -> None:
        """Cache tokens from prompt_tokens_details are captured."""
        body = {
            "conversation_id": "conv-abc",
            "outputs": [
                {"type": "message.output", "content": "Hi", "role": "assistant"},
            ],
            "usage": {
                "prompt_tokens": 200,
                "completion_tokens": 10,
                "prompt_tokens_details": {"cached_tokens": 150},
            },
        }
        transport = FakeTransport(TransportResponse(status=200, body=body))
        provider = MistralConversationsProvider(transport)
        request = RequestInfo(
            model_slug="mistral-small-latest",
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


# ── Error mapping ───────────────────────────────────────────────────


class TestConversationsErrorMapping:
    """Test that Conversations provider uses shared error mapping."""

    def test_auth_error(self) -> None:
        """401 raises ProviderAuthError."""
        transport = FakeTransport(
            TransportResponse(status=401, body={"error": "unauthorized"})
        )
        provider = MistralConversationsProvider(transport)
        request = RequestInfo(
            model_slug="mistral-small-latest",
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

    def test_rate_limit_error(self) -> None:
        """429 raises ProviderTransientError."""
        transport = FakeTransport(
            TransportResponse(status=429, body={"error": "rate limited"})
        )
        provider = MistralConversationsProvider(transport)
        request = RequestInfo(
            model_slug="mistral-small-latest",
            messages=({"role": "user", "content": "Hi"},),
        )
        with pytest.raises(ProviderTransientError):
            provider.request(
                request,
                base_url="https://api.mistral.ai/v1",
                api_key="test-key",
                timeout_seconds=30,
                transport_retries=0,
                extra_headers={},
            )


# ── URL construction ────────────────────────────────────────────────


class TestConversationsURL:
    """Test that the Conversations provider hits the right URL."""

    def test_conversations_url(self) -> None:
        """URL is /v1/conversations."""
        transport = FakeTransport(_conversations_success())
        provider = MistralConversationsProvider(transport)
        request = RequestInfo(
            model_slug="mistral-small-latest",
            messages=({"role": "user", "content": "Hi"},),
        )
        provider.request(
            request,
            base_url="https://api.mistral.ai",
            api_key="test-key",
            timeout_seconds=30,
            transport_retries=1,
            extra_headers={},
        )
        assert transport.last_url == "https://api.mistral.ai/v1/conversations"
