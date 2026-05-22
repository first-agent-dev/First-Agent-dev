"""T-2 LLM provider client (ADR-9).

Public surface:

* :class:`fa.providers.base.RequestInfo` / :class:`fa.providers.base.ResponseInfo`
* :class:`fa.providers.base.Provider` / :class:`fa.providers.base.Transport`
* :class:`fa.providers.chain.ChainEntry` / :class:`fa.providers.chain.ChainConfig`
  / :class:`fa.providers.chain.ProviderChain`
* :class:`fa.providers.chain.ChainAttemptRecord` /
  :class:`fa.providers.chain.CooldownRow`
* :mod:`fa.providers.errors` typed-error hierarchy
* :func:`fa.providers.registry.build_provider`
"""

from __future__ import annotations

from fa.providers.base import (
    Provider,
    RequestInfo,
    ResponseInfo,
    Transport,
    TransportResponse,
)
from fa.providers.chain import (
    ChainAttemptRecord,
    ChainConfig,
    ChainEntry,
    CooldownRow,
    ProviderChain,
    chain_from_mapping,
)
from fa.providers.errors import (
    ConfigurationError,
    ProviderAuthError,
    ProviderChainExhaustedError,
    ProviderRequestShapeError,
    ProviderTransientError,
    ReservedProviderError,
)
from fa.providers.registry import PROVIDERS, ProviderSpec, build_provider

__all__ = [
    "PROVIDERS",
    "ChainAttemptRecord",
    "ChainConfig",
    "ChainEntry",
    "ConfigurationError",
    "CooldownRow",
    "Provider",
    "ProviderAuthError",
    "ProviderChain",
    "ProviderChainExhaustedError",
    "ProviderRequestShapeError",
    "ProviderSpec",
    "ProviderTransientError",
    "RequestInfo",
    "ReservedProviderError",
    "ResponseInfo",
    "Transport",
    "TransportResponse",
    "build_provider",
    "chain_from_mapping",
]
