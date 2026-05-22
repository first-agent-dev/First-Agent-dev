"""PROVIDERS registry + ``build_provider`` factory (ADR-9 §5)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from fa.providers.anthropic import AnthropicProvider
from fa.providers.base import TransportResponse
from fa.providers.errors import ConfigurationError
from fa.providers.openai_compat import OpenAICompatProvider
from fa.providers.registry import PROVIDERS, build_provider


class _NullTransport:
    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> TransportResponse:
        return TransportResponse(status=200, body={})


def test_openrouter_resolves_to_openai_compat_adapter() -> None:
    spec = PROVIDERS["openrouter"]
    assert spec.adapter == "openai_compat"
    instance = build_provider("openrouter", transport=_NullTransport())
    assert isinstance(instance, OpenAICompatProvider)


def test_anthropic_resolves_to_anthropic_adapter() -> None:
    spec = PROVIDERS["anthropic"]
    assert spec.adapter == "anthropic"
    instance = build_provider("anthropic", transport=_NullTransport())
    assert isinstance(instance, AnthropicProvider)


def test_unknown_provider_raises_configuration_error_with_known_list() -> None:
    with pytest.raises(ConfigurationError, match="unknown provider 'mystery'"):
        build_provider("mystery", transport=_NullTransport())


def test_every_registered_provider_builds() -> None:
    transport = _NullTransport()
    for name in PROVIDERS:
        assert build_provider(name, transport=transport) is not None
