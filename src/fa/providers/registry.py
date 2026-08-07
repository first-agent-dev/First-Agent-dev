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
from dataclasses import dataclass, field

from fa.providers.anthropic import AnthropicProvider
from fa.providers.base import Provider, Transport
from fa.providers.errors import ConfigurationError
from fa.providers.message_rules import MessageRules
from fa.providers.mistral import MistralProvider
from fa.providers.mistral_conversations import MistralConversationsProvider
from fa.providers.openai_compat import OpenAICompatProvider


@dataclass(frozen=True)
class ProviderSpec:
    """Static metadata for one named provider — adapter class + category name.

    ``rules`` is the per-provider :class:`~fa.providers.message_rules.MessageRules`
    capability record (S13.4 / D2). It defaults to the strict-safe values so an
    unspecified provider is treated as a strict validator (K6); it is the "add a
    provider = one line; add a quirk = one field" seam (CT6).
    """

    factory: Callable[[Transport], Provider]
    adapter: str
    rules: MessageRules = field(default_factory=MessageRules)


# OpenAI-shaped endpoints tolerate a trailing assistant (the shape the S13.3
# emitter no longer produces, but which OpenAI accepts); Mistral/Anthropic do
# not. All 16 OpenAI-compatible names share this rule set.
_OPENAI_COMPAT = ProviderSpec(
    factory=OpenAICompatProvider,
    adapter="openai_compat",
    rules=MessageRules(allows_trailing_assistant=True),
)
# NVIDIA build rejects the composer's prompt-cache keys (`prompt_cache_key`,
# `prompt_cache_retention`) with a 400 — a measured divergence (S13.7), not a
# silent drop. Same OpenAI-compat shape otherwise (allows a trailing assistant).
_NVIDIA_BUILD = ProviderSpec(
    factory=OpenAICompatProvider,
    adapter="openai_compat",
    rules=MessageRules(allows_trailing_assistant=True, supports_prompt_cache=False),
)
_ANTHROPIC = ProviderSpec(factory=AnthropicProvider, adapter="anthropic")
# Mistral's serving surface requires top_p=1 when greedy (temperature==0),
# otherwise it rejects the request (I-48: `top_p must be 1 when using greedy
# sampling`, code 3054). This is a platform capability, not a per-model quirk,
# so it lives on the whole `mistral` adapter. `allows_trailing_assistant`
# stays strict (Mistral rejects a trailing assistant, 3230).
_MISTRAL = ProviderSpec(
    factory=MistralProvider,
    adapter="mistral",
    rules=MessageRules(requires_top_p_one_when_greedy=True),
)
_MISTRAL_AGENTS = ProviderSpec(factory=MistralConversationsProvider, adapter="mistral_agents")

PROVIDERS: Mapping[str, ProviderSpec] = {
    "openrouter": _OPENAI_COMPAT,
    "fireworks": _OPENAI_COMPAT,
    "nvidia_build": _NVIDIA_BUILD,
    "groq": _OPENAI_COMPAT,
    "github_models": _OPENAI_COMPAT,
    "modal": _OPENAI_COMPAT,
    "together_ai": _OPENAI_COMPAT,
    "lambda_labs": _OPENAI_COMPAT,
    "cerebras": _OPENAI_COMPAT,
    "perplexity": _OPENAI_COMPAT,
    "xai": _OPENAI_COMPAT,
    "alistaitsacle": _OPENAI_COMPAT,
    "apertis": _OPENAI_COMPAT,
    "llm7": _OPENAI_COMPAT,
    "aigate": _OPENAI_COMPAT,
    "anymodel": _OPENAI_COMPAT,
    "openmodel": _ANTHROPIC,
    "anthropic": _ANTHROPIC,
    "mistral": _MISTRAL,
    "mistral_agents": _MISTRAL_AGENTS,
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
        raise ConfigurationError(
            f"unknown provider {name!r}; known: {known}. "
            f"Fix: check the 'provider' field in your ~/.fa/models.yaml chain entry."
        ) from exc
    return spec.factory(transport)
