"""``ChainConfig`` + ``ProviderChain`` contract — offline tests with fakes.

Covers ADR-9 §1 config validator (empty chain, reserved provider,
unknown provider, base_url scheme, missing api_key_env), §2 runtime
semantics (200 success returns, 401/403 continue chain without
cooldown, 429/5xx cool the tuple, 400/422 fail-fast, exhaustion
raises typed error), §3 adaptive ``Retry-After`` floor, and the
``logical_call_id`` propagation surface the inner-loop runtime uses
to correlate the three observability tiers.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import pytest

from fa.providers.base import RequestInfo, ResponseInfo
from fa.providers.chain import (
    ChainAttemptRecord,
    ChainConfig,
    ChainEntry,
    ProviderChain,
)
from fa.providers.errors import (
    ConfigurationError,
    ProviderAuthError,
    ProviderChainExhaustedError,
    ProviderRequestShapeError,
    ProviderTransientError,
    ReservedProviderError,
)


@dataclass
class StubProvider:
    """Stub :class:`fa.providers.base.Provider` returning canned outcomes per call."""

    outcomes: list[ResponseInfo | Exception]
    name: str = "stub"

    def request(
        self,
        request: RequestInfo,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        extra_headers: Mapping[str, str],
    ) -> ResponseInfo:
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _entry(provider: str = "openrouter", slug: str = "deepseek/deepseek-chat-v3") -> ChainEntry:
    return ChainEntry(
        provider=provider,
        slug=slug,
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        cooldown_seconds=300,
    )


def _ok(text: str = "ok") -> ResponseInfo:
    return ResponseInfo(text=text, in_tokens=1, out_tokens=1, finish_reason="stop")


def _config(*entries: ChainEntry) -> ChainConfig:
    return ChainConfig(role="coder", model="deepseek-v3", family="deepseek", chain=tuple(entries))


class _StubClock:
    """Monotonic clock fake with ``advance`` helper."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class ItertoolsId:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._counter = itertools.count()

    def __call__(self) -> str:
        return f"{self._prefix}-{next(self._counter)}"


# ----- validator: hard failures ----------------------------------------


def test_validate_rejects_empty_chain() -> None:
    config = _config()
    with pytest.raises(ConfigurationError, match="empty chain"):
        config.validate(env={"OPENROUTER_API_KEY": "k"})


def test_validate_rejects_reserved_provider_name() -> None:
    config = _config(
        ChainEntry(
            provider="__internal__",
            slug="x",
            base_url="https://x.example/v1",
            api_key_env="OPENROUTER_API_KEY",
        )
    )
    with pytest.raises(ReservedProviderError):
        config.validate(env={"OPENROUTER_API_KEY": "k"})


def test_validate_rejects_unknown_provider() -> None:
    config = _config(
        ChainEntry(
            provider="not_a_provider",
            slug="x",
            base_url="https://x.example/v1",
            api_key_env="OPENROUTER_API_KEY",
        )
    )
    with pytest.raises(ConfigurationError, match="unknown provider"):
        config.validate(env={"OPENROUTER_API_KEY": "k"})


def test_validate_rejects_non_https_non_localhost_base_url() -> None:
    config = _config(
        ChainEntry(
            provider="openrouter",
            slug="x",
            base_url="http://api.evil.example/v1",
            api_key_env="OPENROUTER_API_KEY",
        )
    )
    with pytest.raises(ConfigurationError, match="must be https"):
        config.validate(env={"OPENROUTER_API_KEY": "k"})


def test_validate_rejects_missing_api_key_env_value() -> None:
    config = _config(_entry())
    with pytest.raises(ConfigurationError, match="not set or empty"):
        config.validate(env={})


def test_validate_rejects_empty_api_key_env_name() -> None:
    config = _config(
        ChainEntry(
            provider="openrouter",
            slug="x",
            base_url="https://x.example/v1",
            api_key_env="",
        )
    )
    with pytest.raises(ConfigurationError, match="api_key_env must be non-empty"):
        config.validate(env={"": "k"})


# ----- validator: best-effort warnings ---------------------------------


def test_validate_permits_localhost_http_with_warning() -> None:
    config = _config(
        ChainEntry(
            provider="openrouter",
            slug="deepseek/deepseek-chat-v3",
            base_url="http://localhost:8080/v1",
            api_key_env="OPENROUTER_API_KEY",
        )
    )
    warnings = config.validate(env={"OPENROUTER_API_KEY": "k"})
    assert any("localhost" in w for w in warnings)


def test_validate_warns_when_slug_family_differs_from_role_family() -> None:
    config = ChainConfig(
        role="coder",
        model="claude-3-5-sonnet",
        family="anthropic",
        chain=(_entry(slug="deepseek/deepseek-chat-v3"),),
    )
    warnings = config.validate(env={"OPENROUTER_API_KEY": "k"})
    assert any("slug family" in w for w in warnings)


def test_validate_warns_on_mixed_adapter_categories() -> None:
    config = ChainConfig(
        role="coder",
        model="deepseek-v3",
        family="deepseek",
        chain=(
            _entry(),
            ChainEntry(
                provider="anthropic",
                slug="claude-3-5-sonnet-latest",
                base_url="https://api.anthropic.com",
                api_key_env="OPENROUTER_API_KEY",
            ),
        ),
    )
    warnings = config.validate(env={"OPENROUTER_API_KEY": "k"})
    assert any("mixes adapter categories" in w for w in warnings)


# ----- dispatch: success paths -----------------------------------------


def test_dispatch_returns_first_success_with_attempts_and_logical_call_id() -> None:
    config = _config(_entry())
    stub = StubProvider(outcomes=[_ok("from openrouter")])
    chain = ProviderChain(
        config,
        provider_factory=lambda _entry: stub,
        env={"OPENROUTER_API_KEY": "k"},
        clock=_StubClock(),
        id_factory=ItertoolsId("call"),
    )
    response, logical_call_id, attempts = chain.request(
        RequestInfo(model_slug="deepseek-v3", messages=())
    )
    assert response.text == "from openrouter"
    assert logical_call_id == "call-0"
    assert [a.provider for a in attempts] == ["openrouter"]
    assert attempts[0].status == 200
    assert attempts[0].error is None


def test_dispatch_falls_through_transient_failure_to_next_entry_and_cools_first() -> None:
    config = _config(_entry("openrouter"), _entry("fireworks"))
    stubs = {
        "openrouter": StubProvider(
            outcomes=[
                ProviderTransientError("rate_limited: status=429", status=429, kind="rate_limited")
            ]
        ),
        "fireworks": StubProvider(outcomes=[_ok("from fireworks")]),
    }
    clock = _StubClock()
    chain = ProviderChain(
        config,
        provider_factory=lambda entry: stubs[entry.provider],
        env={"OPENROUTER_API_KEY": "k"},
        clock=clock,
        id_factory=ItertoolsId("call"),
    )
    response, _, attempts = chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    assert response.text == "from fireworks"
    assert [a.provider for a in attempts] == ["openrouter", "fireworks"]
    assert attempts[0].error == "rate_limited"
    assert attempts[1].status == 200
    # The cooled tuple is in the cooldown ledger:
    cooldowns = chain.cooldowns
    assert ("openrouter", "deepseek/deepseek-chat-v3") in cooldowns


def test_cooled_tuple_is_skipped_until_cooldown_expires() -> None:
    config = _config(_entry("openrouter"), _entry("fireworks"))
    or_stub = StubProvider(
        outcomes=[
            ProviderTransientError("rate_limited: status=429", status=429, kind="rate_limited"),
            _ok("recovered"),
        ]
    )
    fw_stub = StubProvider(outcomes=[_ok("from fireworks"), _ok("from fireworks 2")])

    def factory(entry: ChainEntry) -> StubProvider:
        return or_stub if entry.provider == "openrouter" else fw_stub

    clock = _StubClock()
    chain = ProviderChain(
        config,
        provider_factory=factory,
        env={"OPENROUTER_API_KEY": "k"},
        clock=clock,
        id_factory=ItertoolsId("call"),
    )
    # First call: openrouter fails, fireworks serves
    chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    # Second call within cooldown window: openrouter MUST be skipped
    clock.advance(100.0)
    response, _, attempts = chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    assert response.text == "from fireworks 2"
    assert [a.provider for a in attempts] == ["fireworks"]
    # Third call after cooldown expires: openrouter is retried and now succeeds
    clock.advance(400.0)
    response, _, attempts = chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    assert response.text == "recovered"
    assert [a.provider for a in attempts] == ["openrouter"]
    assert chain.cooldowns == {}


def test_adaptive_cooldown_floor_uses_retry_after_when_longer() -> None:
    config = _config(_entry("openrouter"))
    stub = StubProvider(
        outcomes=[
            ProviderTransientError(
                "rate_limited: status=429",
                status=429,
                kind="rate_limited",
                retry_after_seconds=900.0,
            )
        ]
    )
    clock = _StubClock(start=1_000_000.0)
    chain = ProviderChain(
        config,
        provider_factory=lambda _e: stub,
        env={"OPENROUTER_API_KEY": "k"},
        clock=clock,
        id_factory=ItertoolsId("call"),
    )
    with pytest.raises(ProviderChainExhaustedError):
        chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    row = chain.cooldowns[("openrouter", "deepseek/deepseek-chat-v3")]
    # Retry-After (900s) exceeds the configured floor (300s) → floor lifts.
    assert row.expires_at - 1_000_000.0 >= 900.0
    assert row.retry_after_hint_ms == 900_000


def test_auth_failure_continues_chain_without_cooldown() -> None:
    config = _config(_entry("openrouter"), _entry("fireworks"))
    stubs = {
        "openrouter": StubProvider(
            outcomes=[ProviderAuthError("auth_error: status=401", status=401)]
        ),
        "fireworks": StubProvider(outcomes=[_ok("served")]),
    }
    chain = ProviderChain(
        config,
        provider_factory=lambda e: stubs[e.provider],
        env={"OPENROUTER_API_KEY": "k"},
        clock=_StubClock(),
        id_factory=ItertoolsId("call"),
    )
    response, _, attempts = chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    assert response.text == "served"
    assert attempts[0].error == "auth_failed"
    assert attempts[0].status == 401
    # No cooldown row written:
    assert chain.cooldowns == {}


def test_request_shape_error_fails_fast_without_trying_next_entry() -> None:
    config = _config(_entry("openrouter"), _entry("fireworks"))
    or_stub = StubProvider(
        outcomes=[ProviderRequestShapeError("request_shape_error: status=400", status=400)]
    )
    fw_stub = StubProvider(outcomes=[_ok("would have served")])

    def factory(entry: ChainEntry) -> StubProvider:
        return or_stub if entry.provider == "openrouter" else fw_stub

    chain = ProviderChain(
        config,
        provider_factory=factory,
        env={"OPENROUTER_API_KEY": "k"},
        clock=_StubClock(),
        id_factory=ItertoolsId("call"),
    )
    with pytest.raises(ProviderRequestShapeError):
        chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    # Fireworks must NOT have been called:
    assert fw_stub.outcomes == [_ok("would have served")]


def test_chain_exhaustion_raises_typed_error_with_attempts() -> None:
    config = _config(_entry("openrouter"), _entry("fireworks"))
    stubs = {
        "openrouter": StubProvider(
            outcomes=[
                ProviderTransientError("rate_limited: status=429", status=429, kind="rate_limited")
            ]
        ),
        "fireworks": StubProvider(
            outcomes=[
                ProviderTransientError(
                    "service_unavailable: status=503",
                    status=503,
                    kind="service_unavailable",
                )
            ]
        ),
    }
    chain = ProviderChain(
        config,
        provider_factory=lambda e: stubs[e.provider],
        env={"OPENROUTER_API_KEY": "k"},
        clock=_StubClock(),
        id_factory=ItertoolsId("call"),
    )
    with pytest.raises(ProviderChainExhaustedError) as info:
        chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    attempts = cast(list[ChainAttemptRecord], info.value.attempts)
    assert len(attempts) == 2
    assert all(isinstance(a, ChainAttemptRecord) for a in attempts)
    assert attempts[0].error == "rate_limited"
    assert attempts[1].error == "service_unavailable"


def test_logical_call_id_is_unique_per_call() -> None:
    config = _config(_entry())
    stub = StubProvider(outcomes=[_ok(), _ok()])
    chain = ProviderChain(
        config,
        provider_factory=lambda _e: stub,
        env={"OPENROUTER_API_KEY": "k"},
        clock=_StubClock(),
        id_factory=ItertoolsId("call"),
    )
    _, id_a, _ = chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    _, id_b, _ = chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    assert id_a == "call-0"
    assert id_b == "call-1"
