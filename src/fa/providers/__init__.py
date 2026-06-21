"""T-2 LLM provider client (ADR-9) + T-4 ``~/.fa/models.yaml`` loader.

Public surface:

* :class:`fa.providers.base.RequestInfo` / :class:`fa.providers.base.ResponseInfo`
* :class:`fa.providers.base.Provider` / :class:`fa.providers.base.Transport`
* :class:`fa.providers.chain.ChainEntry` / :class:`fa.providers.chain.ChainConfig`
  / :class:`fa.providers.chain.ProviderChain`
* :class:`fa.providers.chain.ChainAttemptRecord` /
  :class:`fa.providers.chain.CooldownRow`
* :mod:`fa.providers.errors` typed-error hierarchy
* :func:`fa.providers.registry.build_provider`
* :class:`fa.providers.config.ModelsConfig` /
  :func:`fa.providers.config.load_models_config` /
  :func:`fa.providers.config.load_models_config_from_path` (T-4 loader)
* :class:`fa.providers.transport.UrllibTransport` (production HTTP)
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
    ChainConfig,
    ChainEntry,
    CooldownRow,
    ProviderChain,
    chain_from_mapping,
)
from fa.providers.config import (
    DEFAULT_MODELS_YAML_PATH,
    ModelsConfig,
    load_models_config,
    load_models_config_from_path,
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
from fa.providers.secret_store import SecretStore
from fa.providers.transport import DEFAULT_USER_AGENT, UrllibTransport
from fa.providers.types import ChainAttemptRecord

__all__ = [
    "DEFAULT_MODELS_YAML_PATH",
    "DEFAULT_USER_AGENT",
    "PROVIDERS",
    "ChainAttemptRecord",
    "ChainConfig",
    "ChainEntry",
    "ConfigurationError",
    "CooldownRow",
    "ModelsConfig",
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
    "SecretStore",
    "Transport",
    "TransportResponse",
    "UrllibTransport",
    "build_provider",
    "chain_from_mapping",
    "load_models_config",
    "load_models_config_from_path",
]
