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
from typing import Any

import pytest

from fa.providers.base import RequestInfo, ResponseInfo
from fa.providers.chain import (
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
from fa.roles import EvalFamilyConflictError, check_eval_disjoint


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
        transport_retries: int,
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
    attempts = info.value.attempts
    assert len(attempts) == 2
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


# ----- ADR-9 §4 correlation: terminal errors carry logical_call_id -----


def test_chain_exhausted_error_carries_logical_call_id() -> None:
    # ADR-9 §4 Tier-2 schema: ``llm_chain_exhausted`` row with
    # ``terminal: "all_exhausted"`` MUST carry ``logical_call_id``.
    config = _config(_entry("openrouter"))
    stub = StubProvider(
        outcomes=[
            ProviderTransientError("rate_limited: status=429", status=429, kind="rate_limited"),
        ]
    )
    chain = ProviderChain(
        config,
        provider_factory=lambda _e: stub,
        env={"OPENROUTER_API_KEY": "k"},
        clock=_StubClock(),
        id_factory=ItertoolsId("call"),
    )
    with pytest.raises(ProviderChainExhaustedError) as info:
        chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    assert info.value.logical_call_id == "call-0"


def test_request_shape_error_carries_logical_call_id() -> None:
    # ADR-9 §4 Tier-2 schema: ``llm_chain_exhausted`` row with
    # ``terminal: "request_shape"`` MUST carry ``logical_call_id``
    # so the inner-loop runtime can correlate Tier-1 + Tier-2 rows
    # on a fail-fast 400/422 path.
    config = _config(_entry("openrouter"))
    stub = StubProvider(
        outcomes=[ProviderRequestShapeError("request_shape_error: status=400", status=400)]
    )
    chain = ProviderChain(
        config,
        provider_factory=lambda _e: stub,
        env={"OPENROUTER_API_KEY": "k"},
        clock=_StubClock(),
        id_factory=ItertoolsId("call"),
    )
    with pytest.raises(ProviderRequestShapeError) as info:
        chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    assert info.value.logical_call_id == "call-0"


def test_request_accepts_externally_injected_logical_call_id() -> None:
    # ADR-9 §2 step 2b: ``BEFORE_LLM_CALL`` hook fires with the
    # ``logical_call_id`` in context, so the inner-loop runtime needs
    # the id before chain.request() returns; caller pre-generates and
    # passes it in.
    config = _config(_entry())
    stub = StubProvider(outcomes=[_ok()])
    chain = ProviderChain(
        config,
        provider_factory=lambda _e: stub,
        env={"OPENROUTER_API_KEY": "k"},
        clock=_StubClock(),
        id_factory=ItertoolsId("internal"),
    )
    _, returned_id, _ = chain.request(
        RequestInfo(model_slug="deepseek-v3", messages=()),
        logical_call_id="caller-supplied-uuid",
    )
    assert returned_id == "caller-supplied-uuid"


def test_request_externally_injected_id_is_preserved_on_exhaustion() -> None:
    config = _config(_entry("openrouter"))
    stub = StubProvider(
        outcomes=[
            ProviderTransientError("rate_limited: status=429", status=429, kind="rate_limited"),
        ]
    )
    chain = ProviderChain(
        config,
        provider_factory=lambda _e: stub,
        env={"OPENROUTER_API_KEY": "k"},
        clock=_StubClock(),
        id_factory=ItertoolsId("internal"),
    )
    with pytest.raises(ProviderChainExhaustedError) as info:
        chain.request(
            RequestInfo(model_slug="deepseek-v3", messages=()),
            logical_call_id="caller-supplied-uuid",
        )
    assert info.value.logical_call_id == "caller-supplied-uuid"


# ----- ADR-9 §3 cross-role shared cooldown ledger ----------------------


def test_cooldown_ledger_is_shared_across_provider_chain_instances() -> None:
    # ADR-9 §3: «The cooldown dict is process-global, keyed on
    # (provider, slug) — NOT on (role, provider, slug). Two roles
    # whose chains share the same (provider, slug) tuple share the
    # cooldown state.»
    shared: dict[tuple[str, str], CooldownRow] = {}
    coder = ChainConfig(role="coder", model="deepseek-v3", family="deepseek", chain=(_entry(),))
    planner = ChainConfig(role="planner", model="deepseek-v3", family="deepseek", chain=(_entry(),))
    coder_stub = StubProvider(
        outcomes=[
            ProviderTransientError("rate_limited: status=429", status=429, kind="rate_limited"),
        ]
    )
    planner_stub = StubProvider(outcomes=[_ok("planner result")])
    clock = _StubClock()
    coder_chain = ProviderChain(
        coder,
        provider_factory=lambda _e: coder_stub,
        env={"OPENROUTER_API_KEY": "k"},
        clock=clock,
        id_factory=ItertoolsId("call"),
        cooldowns=shared,
    )
    planner_chain = ProviderChain(
        planner,
        provider_factory=lambda _e: planner_stub,
        env={"OPENROUTER_API_KEY": "k"},
        clock=clock,
        id_factory=ItertoolsId("call"),
        cooldowns=shared,
    )
    # Coder hits 429 on openrouter/deepseek and cools the tuple.
    with pytest.raises(ProviderChainExhaustedError):
        coder_chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    # Planner's chain shares the ledger and so MUST also see the
    # tuple as cooled — planner's stub is never asked.
    with pytest.raises(ProviderChainExhaustedError):
        planner_chain.request(RequestInfo(model_slug="deepseek-v3", messages=()))
    assert planner_stub.outcomes == [_ok("planner result")]


def test_default_cooldown_ledger_is_per_instance() -> None:
    # Without a shared ledger kwarg, ProviderChain instances stay
    # isolated — the v0.1 test-default behaviour.
    config = _config(_entry())
    chain_a = ProviderChain(
        config,
        provider_factory=lambda _e: StubProvider(outcomes=[]),
        env={"OPENROUTER_API_KEY": "k"},
        clock=_StubClock(),
        id_factory=ItertoolsId("call"),
    )
    chain_b = ProviderChain(
        config,
        provider_factory=lambda _e: StubProvider(outcomes=[]),
        env={"OPENROUTER_API_KEY": "k"},
        clock=_StubClock(),
        id_factory=ItertoolsId("call"),
    )
    assert chain_a.cooldowns is not chain_b.cooldowns


# ----- chain_from_mapping: YAML null coercion --------------------------


def test_chain_from_mapping_coalesces_yaml_null_family_to_empty_string() -> None:
    # YAML ``family: null`` (or bare ``family:``) parses to Python
    # ``None``. ``raw.get("family", "")`` returns ``None`` because
    # the key exists, so ``str(None)`` would smuggle the literal
    # string ``"None"`` into the config and the family-mismatch
    # validator would emit a confusing warning. The loader must
    # coalesce to the empty string.
    raw = {
        "model": None,
        "family": None,
        "chain": [
            {
                "provider": "openrouter",
                "slug": "deepseek/deepseek-chat-v3",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
            }
        ],
    }
    config = chain_from_mapping("coder", raw)
    assert config.model == ""
    assert config.family == ""
    # Validator must not produce a misleading «family 'None' !=» warning.
    warnings = config.validate(env={"OPENROUTER_API_KEY": "k"})
    assert all("'None'" not in w for w in warnings)


def test_chain_from_mapping_raises_on_yaml_null_required_field() -> None:
    # Each of the four required chain-entry fields (provider, slug,
    # base_url, api_key_env) must raise a clean ConfigurationError
    # naming the offending field when the YAML row contains the field
    # as ``null``. Without this guard the loader would smuggle
    # str(None) == "None" into the ChainEntry and the downstream
    # ChainConfig.validate would raise a confusing «unknown provider
    # 'None'» / «api_key_env=None not set» error instead.
    for null_field in ("provider", "slug", "base_url", "api_key_env"):
        row: dict[str, Any] = {
            "provider": "openrouter",
            "slug": "deepseek/deepseek-chat-v3",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_API_KEY",
        }
        row[null_field] = None
        raw = {"model": "deepseek-v3", "family": "deepseek", "chain": [row]}
        with pytest.raises(ConfigurationError) as info:
            chain_from_mapping("coder", raw)
        msg = str(info.value)
        assert null_field in msg, f"error must name field {null_field!r}, got: {msg}"
        assert "null or missing" in msg


def test_chain_from_mapping_raises_on_missing_required_field() -> None:
    # Same path also covers the missing-key case (KeyError would be
    # less helpful than ConfigurationError). Drop one required field
    # from a otherwise-valid row; the loader must surface a clean
    # ConfigurationError naming the missing field rather than letting
    # ``row["provider"]`` raise KeyError.
    for missing_field in ("provider", "slug", "base_url", "api_key_env"):
        row: dict[str, Any] = {
            "provider": "openrouter",
            "slug": "deepseek/deepseek-chat-v3",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_API_KEY",
        }
        del row[missing_field]
        raw = {"model": "deepseek-v3", "family": "deepseek", "chain": [row]}
        with pytest.raises(ConfigurationError) as info:
            chain_from_mapping("coder", raw)
        assert missing_field in str(info.value)


def test_chain_from_mapping_coalesces_yaml_null_chain_field_to_empty_tuple() -> None:
    # YAML ``chain: null`` (or bare ``chain:``) parses to Python
    # ``None``; ``raw.get("chain", ())`` returns the actual ``None``
    # because the key exists, and the subsequent ``for row in
    # chain_rows`` would raise ``TypeError: 'NoneType' object is not
    # iterable``. The loader must coalesce to an empty tuple so the
    # ``ChainConfig.validate`` surfaces the intended
    # ``ConfigurationError("empty chain — role not callable")``
    # rather than a confusing TypeError.
    raw_explicit_null = {"model": "x", "family": "x", "chain": None}
    # Must not raise TypeError.
    config_null = chain_from_mapping("coder", raw_explicit_null)
    assert config_null.chain == ()

    raw_missing_key = {"model": "x", "family": "x"}
    config_missing = chain_from_mapping("coder", raw_missing_key)
    assert config_missing.chain == ()


def test_chain_from_mapping_coalesces_yaml_null_on_chain_entry_numeric_fields() -> None:
    # YAML ``cooldown_seconds: null`` / ``transport_retries: null`` /
    # ``timeout_seconds: null`` parses to Python ``None``, which then
    # crashes ``int(...)`` with TypeError. ``row.get(k, DEFAULT)``
    # returns ``None`` when the key exists with a null value (the
    # default is only used when the key is absent), so the explicit
    # ``is not None`` ladder is what guarantees the defaults kick in
    # AND that an explicit zero is preserved.
    raw = {
        "model": "deepseek-v3",
        "family": "deepseek",
        "chain": [
            {
                "provider": "openrouter",
                "slug": "deepseek/deepseek-chat-v3",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
                "cooldown_seconds": None,
                "transport_retries": None,
                "timeout_seconds": None,
                "extra_headers": None,
            }
        ],
    }
    # Must not raise TypeError("int() argument must be ...").
    config = chain_from_mapping("coder", raw)
    entry = config.chain[0]
    assert entry.cooldown_seconds == 90  # DEFAULT_COOLDOWN_SECONDS
    assert entry.transport_retries == 1  # DEFAULT_TRANSPORT_RETRIES
    assert entry.timeout_seconds == 15  # DEFAULT_TIMEOUT_SECONDS
    assert entry.extra_headers == {}


def test_chain_from_mapping_preserves_explicit_zero_on_numeric_fields() -> None:
    # ``cooldown_seconds: 0`` disables cooldown on a localhost
    # gateway entry; ``timeout_seconds: 0`` opts out of the
    # transport timeout. A naive ``row.get(k) or DEFAULT``
    # coercion would silently coalesce 0 to the default because 0
    # is falsy in Python — the loader MUST preserve the explicit
    # zero.
    raw = {
        "model": "local-mock",
        "family": "local",
        "chain": [
            {
                "provider": "openrouter",
                "slug": "deepseek/deepseek-chat-v3",
                "base_url": "http://localhost:8080/v1",
                "api_key_env": "OPENROUTER_API_KEY",
                "cooldown_seconds": 0,
                "transport_retries": 0,
                "timeout_seconds": 0,
            }
        ],
    }
    config = chain_from_mapping("coder", raw)
    entry = config.chain[0]
    assert entry.cooldown_seconds == 0
    assert entry.transport_retries == 0
    assert entry.timeout_seconds == 0


def test_chain_from_mapping_omitted_optional_fields_use_defaults() -> None:
    # Sanity check that the loader's three-arm conditional still
    # uses the declared module defaults when the YAML row simply
    # omits the optional fields.
    raw = {
        "model": "deepseek-v3",
        "family": "deepseek",
        "chain": [
            {
                "provider": "openrouter",
                "slug": "deepseek/deepseek-chat-v3",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
            }
        ],
    }
    config = chain_from_mapping("coder", raw)
    entry = config.chain[0]
    assert entry.cooldown_seconds == 90
    assert entry.transport_retries == 1
    assert entry.timeout_seconds == 15
    assert entry.extra_headers == {}


def test_chain_from_mapping_preserves_string_family() -> None:
    # Positive sanity check that the ``or ""`` coercion does not
    # break the happy path.
    raw = {
        "model": "deepseek-v3",
        "family": "deepseek",
        "chain": [
            {
                "provider": "openrouter",
                "slug": "deepseek/deepseek-chat-v3",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
            }
        ],
    }
    config = chain_from_mapping("coder", raw)
    assert config.model == "deepseek-v3"
    assert config.family == "deepseek"


def test_chain_from_mapping_normalises_family_to_lowercase() -> None:
    # Regression test for the Agent Review finding on PR #52: a YAML
    # ``family: "DeepSeek"`` (mixed case) stored verbatim into
    # ``ChainConfig.family`` would bypass ``check_eval_disjoint``'s
    # case-sensitive ``==`` comparison when matched against a
    # lowercase eval-role ``family: "deepseek"``, silently violating
    # the safety-critical eval-vs-actor disjoint rule from ADR-2
    # §Amendment 2026-05-20. ``chain_from_mapping`` must normalise
    # via ``.strip().lower()`` so every downstream consumer (the
    # disjoint check, the validator's slug-family mismatch warning,
    # cooldown logging, Tier-2 telemetry) sees a canonical form.
    raw = {
        "model": "DeepSeek-V3",
        "family": "DeepSeek",
        "chain": [
            {
                "provider": "openrouter",
                "slug": "deepseek/deepseek-chat-v3",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
            }
        ],
    }
    config = chain_from_mapping("coder", raw)
    # ``model`` is NOT normalised — a provider's ``slug`` and the
    # user-facing ``model`` label may legally be mixed-case. Only
    # ``family`` participates in the safety-critical equality check.
    assert config.model == "DeepSeek-V3"
    assert config.family == "deepseek"


def test_chain_from_mapping_strips_whitespace_around_family() -> None:
    # Same regression contract as the case test, but for whitespace
    # padding (``family: "  deepseek  "``). The producer-site
    # ``.strip().lower()`` covers both axes; this test pins the
    # strip behaviour so a future refactor cannot regress only the
    # case half.
    raw = {
        "model": "deepseek-v3",
        "family": "  deepseek  ",
        "chain": [
            {
                "provider": "openrouter",
                "slug": "deepseek/deepseek-chat-v3",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
            }
        ],
    }
    config = chain_from_mapping("coder", raw)
    assert config.family == "deepseek"


def test_invariant_adr2_eval_disjoint_uncircumventable_by_family_case() -> None:
    """ADR-2 §Amendment 2026-05-20 rule 1: eval-vs-actor family disjoint is bypass-proof.

    Mixed-case family strings (planner ``family: "DeepSeek"``, eval
    ``family: "deepseek"``) MUST collide in :func:`check_eval_disjoint`
    after :func:`chain_from_mapping`. Producer-site ``.strip().lower()``
    at ``src/fa/providers/chain.py:429`` is the mechanical enforcement.

    Layer-2 named-invariant retrofit per AP-001 §Layer 2 / drift-
    analysis v2: failing this test means a refactor re-opened the
    case-sensitive bypass of the safety-critical ADR-2 contract.
    Change the ADR (and this test in the same PR) when the contract
    actually changes — do NOT patch the assertion to make a regression
    pass. The four neighbouring regression tests pin the producer-side
    normalisation as an *implementation* detail; THIS test pins the
    end-to-end *contract* (mixed-case must not bypass disjointness).
    """
    planner = chain_from_mapping("planner", {"family": "DeepSeek"})
    eval_role = chain_from_mapping("eval", {"family": "deepseek"})
    with pytest.raises(EvalFamilyConflictError):
        check_eval_disjoint(
            planner_family=planner.family,
            coder_family=planner.family,
            eval_family=eval_role.family,
        )
