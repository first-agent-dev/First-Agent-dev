"""Anthropic ``/v1/messages`` adapter — offline tests with fake transport.

Covers system-row splitting into Anthropic's top-level ``system``
field, ``tools`` field-name translation, content-block →
``tool_calls`` round-trip back into the OpenAI-shaped canonical
response, stop-reason mapping, and the ADR-9 §2 status-code split.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest

from fa.providers.anthropic import AnthropicProvider
from fa.providers.base import RequestInfo, TransportResponse
from fa.providers.errors import (
    ProviderAuthError,
    ProviderRequestShapeError,
    ProviderTransientError,
)


@dataclass
class FakeTransport:
    response: TransportResponse
    last_url: str = ""
    last_headers: dict[str, str] = field(default_factory=dict)
    last_body: dict[str, Any] = field(default_factory=dict)

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
        return self.response


def _request_with_system_and_tools() -> RequestInfo:
    return RequestInfo(
        model_slug="claude-3-5-sonnet-latest",
        messages=(
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ),
        max_tokens=1024,
        tools=(
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "search the web",
                    "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
                },
            },
        ),
    )


def test_request_hoists_system_row_into_top_level_field() -> None:
    transport = FakeTransport(
        response=TransportResponse(
            status=200,
            body={
                "content": [{"type": "text", "text": "hi"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 4, "output_tokens": 1},
            },
        ),
    )
    provider = AnthropicProvider(transport=transport)
    provider.request(
        _request_with_system_and_tools(),
        base_url="https://api.anthropic.com",
        api_key="sk-ant-x",
        timeout_seconds=60.0,
        extra_headers={},
    )
    assert transport.last_url == "https://api.anthropic.com/v1/messages"
    assert transport.last_headers["x-api-key"] == "sk-ant-x"
    assert transport.last_headers["anthropic-version"]
    assert transport.last_body["system"] == "You are helpful."
    # The system row is removed from the messages list:
    assert transport.last_body["messages"] == [{"role": "user", "content": "hi"}]
    # max_tokens is mandatory:
    assert transport.last_body["max_tokens"] == 1024
    # Tools translated to Anthropic shape (input_schema / no nested ``function``):
    tool = transport.last_body["tools"][0]
    assert tool["name"] == "search"
    assert "input_schema" in tool
    assert "function" not in tool


def test_request_supplies_default_max_tokens_when_absent() -> None:
    transport = FakeTransport(
        response=TransportResponse(
            status=200,
            body={"content": [], "stop_reason": "end_turn", "usage": {}},
        ),
    )
    provider = AnthropicProvider(transport=transport)
    provider.request(
        RequestInfo(model_slug="claude-3-5-sonnet-latest", messages=()),
        base_url="https://api.anthropic.com",
        api_key="k",
        timeout_seconds=60.0,
        extra_headers={},
    )
    assert transport.last_body["max_tokens"] == 4096


def test_response_translates_tool_use_blocks_to_openai_tool_calls() -> None:
    transport = FakeTransport(
        response=TransportResponse(
            status=200,
            body={
                "content": [
                    {"type": "text", "text": "let me search"},
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "search",
                        "input": {"q": "first agent"},
                    },
                ],
                "stop_reason": "tool_use",
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 8,
                    "cache_read_input_tokens": 7,
                    "cache_creation_input_tokens": 3,
                },
                "model": "claude-3-5-sonnet-latest",
            },
        ),
    )
    provider = AnthropicProvider(transport=transport)
    response = provider.request(
        _request_with_system_and_tools(),
        base_url="https://api.anthropic.com",
        api_key="k",
        timeout_seconds=60.0,
        extra_headers={},
    )
    assert response.text == "let me search"
    assert response.finish_reason == "tool_calls"
    assert response.in_tokens == 12
    assert response.out_tokens == 8
    assert response.cache_read_input_tokens == 7
    assert response.cache_creation_input_tokens == 3
    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert call["id"] == "toolu_01"
    assert call["function"]["name"] == "search"
    # The Anthropic ``input`` dict is JSON-encoded to match the OpenAI tool-call shape:
    assert json.loads(call["function"]["arguments"]) == {"q": "first agent"}


@pytest.mark.parametrize(
    "raw_stop,expected",
    [
        ("end_turn", "stop"),
        ("stop_sequence", "stop"),
        ("max_tokens", "length"),
        ("tool_use", "tool_calls"),
        ("unknown_value", "unknown_value"),
    ],
)
def test_stop_reason_mapping(raw_stop: str, expected: str) -> None:
    transport = FakeTransport(
        response=TransportResponse(
            status=200,
            body={"content": [], "stop_reason": raw_stop, "usage": {}},
        ),
    )
    provider = AnthropicProvider(transport=transport)
    response = provider.request(
        _request_with_system_and_tools(),
        base_url="https://api.anthropic.com",
        api_key="k",
        timeout_seconds=60.0,
        extra_headers={},
    )
    assert response.finish_reason == expected


@pytest.mark.parametrize(
    "status,exc",
    [
        (400, ProviderRequestShapeError),
        (422, ProviderRequestShapeError),
        (401, ProviderAuthError),
        (403, ProviderAuthError),
        (429, ProviderTransientError),
        (503, ProviderTransientError),
    ],
)
def test_status_split_matches_adr9(status: int, exc: type[BaseException]) -> None:
    transport = FakeTransport(response=TransportResponse(status=status, body={}))
    provider = AnthropicProvider(transport=transport)
    with pytest.raises(exc):
        provider.request(
            _request_with_system_and_tools(),
            base_url="https://api.anthropic.com",
            api_key="k",
            timeout_seconds=60.0,
            extra_headers={},
        )
