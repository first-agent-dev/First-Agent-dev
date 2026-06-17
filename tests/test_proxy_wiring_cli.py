"""Phase E (ADR-12): fa-side proxy wiring carries NO provider key.

Proves that when proxy mode rewrites a role chain, every entry targets the
proxy (not the real provider) and carries only the fa→proxy token — never a
provider API key.
"""

from __future__ import annotations

from fa.cli import _PROXY_TIMEOUT_HEADER, _PROXY_TOKEN_HEADER, _apply_proxy_mode
from fa.providers.chain import ChainConfig, ChainEntry

_TOKEN = "fa-proxy-token-abcdef123456"


def _chain() -> ChainConfig:
    return ChainConfig(
        role="coder",
        model="llama",
        family="llama",
        chain=(
            ChainEntry(
                provider="openrouter",
                slug="meta-llama/llama-3.1-8b",
                base_url="https://openrouter.ai/api/v1",
                api_key_env="OPENROUTER_API_KEY",
            ),
            ChainEntry(
                provider="fireworks",
                slug="llama-v3p1-8b",
                base_url="https://api.fireworks.ai/inference/v1",
                api_key_env="FIREWORKS_API_KEY",
            ),
        ),
    )


def test_proxy_rewrite_targets_proxy_and_carries_token() -> None:
    rewritten = _apply_proxy_mode(
        _chain(), proxy_url="http://fa-egress-proxy:8080", proxy_token=_TOKEN
    )
    for entry in rewritten.chain:
        assert entry.base_url.startswith("http://fa-egress-proxy:8080/route/")
        assert entry.extra_headers[_PROXY_TOKEN_HEADER] == _TOKEN


def test_proxy_rewrite_advertises_per_route_timeout() -> None:
    """F-2: each rewritten entry tells the proxy its upstream timeout so a slow
    model's configured timeout_seconds is honored instead of a hardcoded cap."""
    chain = _chain()
    rewritten = _apply_proxy_mode(
        chain, proxy_url="http://fa-egress-proxy:8080", proxy_token=_TOKEN
    )
    for original, entry in zip(chain.chain, rewritten.chain, strict=True):
        assert entry.extra_headers[_PROXY_TIMEOUT_HEADER] == str(original.timeout_seconds)


def test_proxy_rewrite_places_no_provider_key_anywhere() -> None:
    rewritten = _apply_proxy_mode(
        _chain(), proxy_url="http://fa-egress-proxy:8080", proxy_token=_TOKEN
    )
    # The fa side never sees a provider key value; only the api_key_env *name*
    # (used by the proxy for routing) and the proxy token are present.
    for entry in rewritten.chain:
        for value in entry.extra_headers.values():
            assert "sk-" not in value
            assert "fw-" not in value
        # base_url no longer points at a real provider host.
        assert "openrouter.ai" not in entry.base_url
        assert "fireworks.ai" not in entry.base_url


def test_proxy_route_names_are_stable() -> None:
    a = _apply_proxy_mode(_chain(), proxy_url="http://p", proxy_token=_TOKEN)
    b = _apply_proxy_mode(_chain(), proxy_url="http://p", proxy_token=_TOKEN)
    assert [e.base_url for e in a.chain] == [e.base_url for e in b.chain]


def test_validate_proxy_mode_skips_key_presence() -> None:
    # In proxy mode the ORIGINAL models.yaml (https provider URLs) is validated
    # with require_api_keys=False BEFORE the proxy rewrite — keys are absent from
    # the fa env but validation must not raise. (The rewritten chain is not
    # re-validated; ProviderChain.__init__ does not call validate().)
    warnings = _chain().validate({}, require_api_keys=False)
    assert isinstance(warnings, list)
