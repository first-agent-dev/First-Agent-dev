"""Tests for shared provider utilities (fa.providers._common).

Verifies the extracted common functions work correctly and handle edge cases.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fa.providers._common import make_authenticated_request, parse_token_usage


class TestParseTokenUsage:
    """Tests for parse_token_usage() function."""

    def test_parse_standard_usage(self) -> None:
        """parse_token_usage extracts standard token counts."""
        body = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
            }
        }
        result = parse_token_usage(body)
        assert result["in_tokens"] == 100
        assert result["out_tokens"] == 50
        assert result["cache_read_input_tokens"] == 0
        assert result["cache_creation_input_tokens"] == 0

    def test_parse_usage_with_nested_cache_tokens(self) -> None:
        """parse_token_usage extracts cache tokens from nested prompt_tokens_details."""
        body = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "prompt_tokens_details": {
                    "cached_tokens": 80,
                },
            }
        }
        result = parse_token_usage(body)
        assert result["in_tokens"] == 100
        assert result["out_tokens"] == 50
        assert result["cache_read_input_tokens"] == 80
        assert result["cache_creation_input_tokens"] == 0

    def test_parse_usage_with_flat_cache_tokens(self) -> None:
        """parse_token_usage extracts cache tokens from flat format."""
        body = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cache_read_input_tokens": 80,
                "cache_creation_input_tokens": 20,
            }
        }
        result = parse_token_usage(body)
        assert result["in_tokens"] == 100
        assert result["out_tokens"] == 50
        assert result["cache_read_input_tokens"] == 80
        assert result["cache_creation_input_tokens"] == 20

    def test_parse_usage_prefers_nested_over_flat(self) -> None:
        """parse_token_usage prefers nested cached_tokens over flat cache_read_input_tokens."""
        body = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "prompt_tokens_details": {
                    "cached_tokens": 80,
                },
                "cache_read_input_tokens": 60,  # Should be ignored
            }
        }
        result = parse_token_usage(body)
        assert result["cache_read_input_tokens"] == 80

    def test_parse_missing_usage_returns_zeros(self) -> None:
        """parse_token_usage returns zeros when usage field is missing."""
        body = {}
        result = parse_token_usage(body)
        assert result["in_tokens"] == 0
        assert result["out_tokens"] == 0
        assert result["cache_read_input_tokens"] == 0
        assert result["cache_creation_input_tokens"] == 0

    def test_parse_empty_usage_returns_zeros(self) -> None:
        """parse_token_usage returns zeros when usage field is empty."""
        body = {"usage": {}}
        result = parse_token_usage(body)
        assert result["in_tokens"] == 0
        assert result["out_tokens"] == 0
        assert result["cache_read_input_tokens"] == 0
        assert result["cache_creation_input_tokens"] == 0

    def test_parse_null_usage_returns_zeros(self) -> None:
        """parse_token_usage returns zeros when usage field is null."""
        body = {"usage": None}
        result = parse_token_usage(body)
        assert result["in_tokens"] == 0
        assert result["out_tokens"] == 0
        assert result["cache_read_input_tokens"] == 0
        assert result["cache_creation_input_tokens"] == 0

    def test_parse_partial_usage(self) -> None:
        """parse_token_usage handles partial usage information."""
        body = {
            "usage": {
                "prompt_tokens": 100,
            }
        }
        result = parse_token_usage(body)
        assert result["in_tokens"] == 100
        assert result["out_tokens"] == 0
        assert result["cache_read_input_tokens"] == 0
        assert result["cache_creation_input_tokens"] == 0

    def test_parse_string_token_values(self) -> None:
        """parse_token_usage converts string token values to int."""
        body = {
            "usage": {
                "prompt_tokens": "100",
                "completion_tokens": "50",
            }
        }
        result = parse_token_usage(body)
        assert result["in_tokens"] == 100
        assert result["out_tokens"] == 50

    def test_parse_non_mapping_prompt_details(self) -> None:
        """parse_token_usage handles non-mapping prompt_tokens_details."""
        body = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "prompt_tokens_details": "invalid",  # Not a mapping
            }
        }
        result = parse_token_usage(body)
        assert result["in_tokens"] == 100
        assert result["out_tokens"] == 50
        assert result["cache_read_input_tokens"] == 0


class TestMakeAuthenticatedRequest:
    """Tests for make_authenticated_request() function."""

    def test_builds_correct_headers(self) -> None:
        """make_authenticated_request builds Authorization and Content-Type headers."""
        transport = MagicMock()
        transport.post.return_value = MagicMock()

        make_authenticated_request(
            transport=transport,
            url="https://api.example.com/v1/chat",
            api_key="test-key-123",
            body={"model": "gpt-4"},
            extra_headers={},
            timeout_seconds=30.0,
            transport_retries=3,
        )

        # Verify transport.post was called
        assert transport.post.called
        call_kwargs = transport.post.call_args.kwargs

        # Verify headers
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-key-123"
        assert call_kwargs["headers"]["Content-Type"] == "application/json"

    def test_merges_extra_headers(self) -> None:
        """make_authenticated_request merges extra_headers into standard headers."""
        transport = MagicMock()
        transport.post.return_value = MagicMock()

        make_authenticated_request(
            transport=transport,
            url="https://api.example.com/v1/chat",
            api_key="test-key",
            body={"model": "gpt-4"},
            extra_headers={"X-Custom-Header": "custom-value", "X-Another": "another"},
            timeout_seconds=30.0,
            transport_retries=3,
        )

        call_kwargs = transport.post.call_args.kwargs
        assert call_kwargs["headers"]["X-Custom-Header"] == "custom-value"
        assert call_kwargs["headers"]["X-Another"] == "another"
        # Standard headers still present
        assert "Authorization" in call_kwargs["headers"]
        assert "Content-Type" in call_kwargs["headers"]

    def test_extra_headers_can_override_standard(self) -> None:
        """make_authenticated_request allows extra_headers to override standard headers."""
        transport = MagicMock()
        transport.post.return_value = MagicMock()

        make_authenticated_request(
            transport=transport,
            url="https://api.example.com/v1/chat",
            api_key="test-key",
            body={"model": "gpt-4"},
            extra_headers={"Content-Type": "application/xml"},  # Override
            timeout_seconds=30.0,
            transport_retries=3,
        )

        call_kwargs = transport.post.call_args.kwargs
        # Extra header should override standard
        assert call_kwargs["headers"]["Content-Type"] == "application/xml"

    def test_passes_all_parameters_to_transport(self) -> None:
        """make_authenticated_request passes all parameters to transport.post."""
        transport = MagicMock()
        transport.post.return_value = MagicMock()

        body = {"model": "gpt-4", "messages": [{"role": "user", "content": "hello"}]}
        make_authenticated_request(
            transport=transport,
            url="https://api.example.com/v1/chat",
            api_key="test-key",
            body=body,
            extra_headers={"X-Custom": "value"},
            timeout_seconds=60.0,
            transport_retries=5,
        )

        call_args = transport.post.call_args
        assert call_args.args[0] == "https://api.example.com/v1/chat"
        assert call_args.kwargs["json_body"] == body
        assert call_args.kwargs["timeout_seconds"] == 60.0
        assert call_args.kwargs["transport_retries"] == 5

    def test_returns_transport_response(self) -> None:
        """make_authenticated_request returns the response from transport.post."""
        transport = MagicMock()
        expected_response = MagicMock()
        transport.post.return_value = expected_response

        result = make_authenticated_request(
            transport=transport,
            url="https://api.example.com/v1/chat",
            api_key="test-key",
            body={"model": "gpt-4"},
            extra_headers={},
            timeout_seconds=30.0,
            transport_retries=3,
        )

        assert result is expected_response
