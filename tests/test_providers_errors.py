"""Typed-error attribute contracts (ADR-9 §1, §2, §5).

The chain dispatcher consumes structured attributes off each error
(``status`` / ``kind`` / ``retry_after_seconds`` / ``attempts``)
rather than parsing the message; these tests pin the contract so a
future docstring tweak does not silently break the dispatcher.
"""

from __future__ import annotations

import pytest

from fa.providers.errors import (
    ConfigurationError,
    ProviderAuthError,
    ProviderChainExhaustedError,
    ProviderRequestShapeError,
    ProviderTransientError,
    ReservedProviderError,
)
from fa.providers.types import ChainAttemptRecord


def test_reserved_provider_error_is_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        raise ReservedProviderError("reserved")


def test_provider_transient_error_carries_structured_attrs() -> None:
    exc = ProviderTransientError(
        "rate_limited: status=429",
        status=429,
        kind="rate_limited",
        retry_after_seconds=12.0,
    )
    assert exc.status == 429
    assert exc.kind == "rate_limited"
    assert exc.retry_after_seconds == 12.0


def test_provider_transient_error_defaults() -> None:
    exc = ProviderTransientError("network_error: timeout")
    assert exc.status == 0
    assert exc.kind == "service_unavailable"
    assert exc.retry_after_seconds == 0.0


def test_provider_auth_error_status_attr() -> None:
    exc = ProviderAuthError("auth_error: status=403", status=403)
    assert exc.status == 403


def test_provider_request_shape_error_default_status() -> None:
    assert ProviderRequestShapeError("bad").status == 400
    assert ProviderRequestShapeError("bad", status=422).status == 422


def test_provider_request_shape_error_carries_logical_call_id() -> None:
    # ADR-9 §4 Tier-2 schema requires logical_call_id on the
    # ``terminal: "request_shape"`` observability row; the adapter
    # leaves it empty at construction time (adapter scope) and the
    # dispatcher overwrites at re-raise time.
    exc = ProviderRequestShapeError("bad")
    assert exc.logical_call_id == ""
    exc.logical_call_id = "uuid-xyz"
    assert exc.logical_call_id == "uuid-xyz"


def test_provider_chain_exhausted_carries_attempts() -> None:
    records = [
        ChainAttemptRecord(provider="fw", slug="m1", status=429, ms=100, error="rate_limited"),
        ChainAttemptRecord(
            provider="or", slug="m2", status=503, ms=50, error="service_unavailable"
        ),
    ]
    exc = ProviderChainExhaustedError("chain exhausted", attempts=records)
    assert len(exc.attempts) == 2
    assert exc.attempts[0].provider == "fw"
    assert exc.attempts[1].status == 503


def test_provider_chain_exhausted_carries_logical_call_id() -> None:
    # ADR-9 §4 Tier-2 schema requires logical_call_id on the
    # ``terminal: "all_exhausted"`` observability row.
    exc = ProviderChainExhaustedError(
        "chain exhausted",
        attempts=[],
        logical_call_id="uuid-abc",
    )
    assert exc.logical_call_id == "uuid-abc"


def test_provider_chain_exhausted_logical_call_id_defaults_empty() -> None:
    # Default empty string keeps the kwarg optional for direct
    # construction (e.g. tests that don't care about the id).
    exc = ProviderChainExhaustedError("chain exhausted", attempts=[])
    assert exc.logical_call_id == ""
