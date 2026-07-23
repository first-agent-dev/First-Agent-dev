"""Shared utilities for providers.

This module contains common functions used by multiple provider implementations
to avoid duplication and ensure consistency in response parsing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict, cast

from fa.providers.base import Transport, TransportResponse


class TokenUsage(TypedDict):
    """Parsed token usage information."""

    in_tokens: int
    out_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


def parse_token_usage(body: Mapping[str, Any]) -> TokenUsage:
    """Parse token usage from provider response body.

    Extracts token counts from the 'usage' field, handling various
    provider-specific formats (OpenAI, Mistral, etc.).

    Args:
        body: Response body mapping containing 'usage' field

    Returns:
        TokenUsage dict with in_tokens, out_tokens, cache_read_input_tokens,
        and cache_creation_input_tokens

    Example:
        >>> body = {
        ...     "usage": {
        ...         "prompt_tokens": 100,
        ...         "completion_tokens": 50,
        ...         "prompt_tokens_details": {"cached_tokens": 80}
        ...     }
        ... }
        >>> usage = parse_token_usage(body)
        >>> print(usage)
        {'in_tokens': 100, 'out_tokens': 50, 'cache_read_input_tokens': 80, 'cache_creation_input_tokens': 0}
    """
    usage = cast(Mapping[str, Any], body.get("usage") or {})
    in_tokens = int(usage.get("prompt_tokens") or 0)
    out_tokens = int(usage.get("completion_tokens") or 0)

    # Handle cache tokens - check both nested and flat formats
    prompt_details = usage.get("prompt_tokens_details")
    prompt_details_map = prompt_details if isinstance(prompt_details, Mapping) else {}
    cache_read_input_tokens = int(prompt_details_map.get("cached_tokens") or usage.get("cache_read_input_tokens") or 0)
    cache_creation_input_tokens = int(usage.get("cache_creation_input_tokens") or 0)

    return TokenUsage(
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
    )


def make_authenticated_request(
    transport: Transport,
    url: str,
    api_key: str,
    body: Mapping[str, Any],
    extra_headers: Mapping[str, str],
    timeout_seconds: float,
    transport_retries: int,
) -> TransportResponse:
    """Make an authenticated HTTP POST request with standard headers.

    Common pattern for OpenAI-compatible providers: builds Authorization header,
    merges extra headers, and calls transport.post.

    Args:
        transport: Transport instance for HTTP calls
        url: Target URL
        api_key: API key for Bearer authentication
        body: Request body (will be JSON-encoded)
        extra_headers: Additional headers to merge
        timeout_seconds: Request timeout
        transport_retries: Number of transport-level retries

    Returns:
        TransportResponse from the transport layer

    Example:
        >>> response = make_authenticated_request(
        ...     transport=my_transport,
        ...     url="https://api.openai.com/v1/chat/completions",
        ...     api_key="sk-...",
        ...     body={"model": "gpt-4", "messages": [...]},
        ...     extra_headers={"X-Custom": "value"},
        ...     timeout_seconds=30.0,
        ...     transport_retries=3,
        ... )
    """
    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    for key, value in extra_headers.items():
        headers[key] = value

    return transport.post(
        url,
        headers=headers,
        json_body=body,
        timeout_seconds=timeout_seconds,
        transport_retries=transport_retries,
    )


__all__ = ["TokenUsage", "make_authenticated_request", "parse_token_usage"]
