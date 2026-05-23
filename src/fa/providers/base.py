"""Provider protocol + canonical request/response dataclasses (ADR-9 §5).

The provider surface is intentionally narrow: a single
:meth:`Provider.request` method that takes a canonical
:class:`RequestInfo` and returns a canonical :class:`ResponseInfo`.
Each adapter (:mod:`fa.providers.openai_compat`,
:mod:`fa.providers.anthropic`) is responsible for translating in and
out of its provider's native wire shape, so the chain dispatcher
(:mod:`fa.providers.chain`) stays adapter-agnostic.

Transport injection (`Transport` Protocol + :class:`TransportResponse`
dataclass) keeps the adapters offline-testable per ADR-7 §10 — tests
hand the adapter a fake transport that returns canned responses; no
real HTTP call ever fires from the test suite.

The canonical ``ResponseInfo`` follows Postel's-Law per ADR-9 §5:
adapters write stable canonical fields (``text`` / ``in_tokens`` /
``out_tokens`` / ``finish_reason`` / ``tool_calls``) plus a free-form
``extras`` mapping for provider-specific data that does not fit the
canonical shape (OpenRouter ``provider`` metadata block, OpenAI
``system_fingerprint``, Anthropic separate ``thinking`` blocks). The
observability Tier-1 row only reads the canonical fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class RequestInfo:
    """Canonical request shape passed to every adapter.

    ``messages`` follows the OpenAI ``role`` / ``content`` shape;
    :class:`fa.providers.anthropic.AnthropicProvider` splits the
    leading ``system`` row out into Anthropic's separate top-level
    ``system`` field at request-build time (ADR-9 §5).
    """

    model_slug: str
    messages: tuple[Mapping[str, Any], ...]
    temperature: float | None = None
    max_tokens: int | None = None
    tools: tuple[Mapping[str, Any], ...] = ()
    extras: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResponseInfo:
    """Canonical response shape returned by every adapter."""

    text: str
    in_tokens: int
    out_tokens: int
    finish_reason: str
    tool_calls: tuple[Mapping[str, Any], ...] = ()
    extras: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransportResponse:
    """Adapter-agnostic HTTP response (body already JSON-decoded).

    ``retry_after_seconds`` is the parsed RFC 9110 ``Retry-After``
    header (seconds-form) when present and parseable; ``None`` for
    absent or malformed values. The chain bookkeeper composes this
    with its configured floor per ADR-9 §3 adaptive-cooldown rule.
    """

    status: int
    body: Mapping[str, Any]
    retry_after_seconds: float | None = None
    network_error: str | None = None


@runtime_checkable
class Transport(Protocol):
    """Pluggable HTTP transport for offline tests + production swap."""

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> TransportResponse: ...


@runtime_checkable
class Provider(Protocol):
    """Adapter contract — see :mod:`fa.providers.openai_compat` / :mod:`fa.providers.anthropic`."""

    name: str

    def request(
        self,
        request: RequestInfo,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        extra_headers: Mapping[str, str],
    ) -> ResponseInfo: ...
