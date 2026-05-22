"""PROVIDERS registry + factory (ADR-9 §5 file layout).

The registry pins the adapter category for every named provider FA
ships out of the box. Adding a new OpenAI-compatible provider = 1
row here + 1 YAML chain entry; no new file needed. Adding a native-
shape provider = 1 new adapter file under :mod:`fa.providers` + 1
row here.

The factory function :func:`build_provider` is the single seam the
chain dispatcher uses; tests construct adapters directly with a fake
transport, so the factory only matters at production wiring time.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from fa.providers.anthropic import AnthropicProvider
from fa.providers.base import Provider, Transport
from fa.providers.errors import ConfigurationError
from fa.providers.openai_compat import OpenAICompatProvider


@dataclass(frozen=True)
class ProviderSpec:
    """Static metadata for one named provider — adapter class + category name."""

    factory: Callable[[Transport], Provider]
    adapter: str


_OPENAI_COMPAT = ProviderSpec(factory=OpenAICompatProvider, adapter="openai_compat")
_ANTHROPIC = ProviderSpec(factory=AnthropicProvider, adapter="anthropic")

PROVIDERS: Mapping[str, ProviderSpec] = {
    "openrouter": _OPENAI_COMPAT,
    "fireworks": _OPENAI_COMPAT,
    "nvidia_build": _OPENAI_COMPAT,
    "groq": _OPENAI_COMPAT,
    "github_models": _OPENAI_COMPAT,
    "modal": _OPENAI_COMPAT,
    "together_ai": _OPENAI_COMPAT,
    "lambda_labs": _OPENAI_COMPAT,
    "cerebras": _OPENAI_COMPAT,
    "perplexity": _OPENAI_COMPAT,
    "xai": _OPENAI_COMPAT,
    "anthropic": _ANTHROPIC,
}


def build_provider(name: str, *, transport: Transport) -> Provider:
    """Instantiate the registered adapter for ``name``.

    Raises :class:`ConfigurationError` for unknown provider names so
    the chain validator (:meth:`fa.providers.chain.ChainConfig.validate`)
    can surface the typo loudly at config-load time per ADR-9 §1.
    """

    try:
        spec = PROVIDERS[name]
    except KeyError as exc:
        known = sorted(PROVIDERS)
        raise ConfigurationError(f"unknown provider {name!r}; known: {known}") from exc
    return spec.factory(transport)
