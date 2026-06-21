"""Route table + header-injection logic for the egress proxy (ADR-12).

Pure, network-free, fully unit-testable. The HTTP server (``server.py``) is a
thin shell over these functions.

Routing model
-------------
The agent's ``models.yaml`` ``base_url`` is rewritten to
``<proxy>/route/<name>`` where ``name = route_name_for(provider, slug)``. The
proxy receives e.g. ``POST /route/openrouter-llama-3-1-8b/chat/completions``,
strips the ``/route/<name>`` prefix, and forwards the remainder
(``/chat/completions``) to the route's real ``upstream_base_url`` with the real
key injected. This is path-transparent, so the existing provider adapters
(which append ``/chat/completions`` or ``/v1/messages``) need no changes.

Auth injection
--------------
``inject_headers`` strips any caller-supplied ``Authorization`` / ``x-api-key``
and sets the correct provider auth header from the route's secret value:

* OpenAI-compatible providers → ``Authorization: Bearer <key>``
* Anthropic                   → ``x-api-key: <key>`` (+ ``anthropic-version``)
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

__all__ = [
    "ANTHROPIC_API_VERSION",
    "ProxyConfigError",
    "ProxyRoute",
    "RouteTable",
    "build_route_table",
    "inject_headers",
    "route_name_for",
]

ANTHROPIC_API_VERSION = "2023-06-01"

# Providers whose auth is ``x-api-key`` rather than ``Authorization: Bearer``.
_XAPIKEY_PROVIDERS = frozenset({"anthropic"})

# Hosts for which http:// is tolerated (a local gateway), matching the provider
# config validator. Everything else MUST be https:// so the injected key is not
# sent in clear or redirected to an attacker.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0"})  # noqa: S104

_NAME_SAFE_RE = re.compile(r"[^a-z0-9]+")


class ProxyConfigError(Exception):
    """Raised when the proxy cannot build a valid route table."""


def route_name_for(provider: str, slug: str) -> str:
    """Return a URL-safe route name for a ``(provider, slug)`` pair.

    Lowercased, non-alphanumeric runs collapsed to ``-``. Deterministic so the
    fa side and the proxy compute the same name from the same models.yaml.
    """
    raw = f"{provider}-{slug}"
    name = _NAME_SAFE_RE.sub("-", raw.lower()).strip("-")
    if not name:
        raise ProxyConfigError(f"empty route name for provider={provider!r} slug={slug!r}")
    return name


@dataclass(frozen=True)
class ProxyRoute:
    """One injectable route: where to forward and which header to add."""

    name: str
    provider: str
    upstream_base_url: str
    api_key_env: str


class RouteTable:
    """Immutable name → :class:`ProxyRoute` map with safe lookup."""

    __slots__ = ("_routes",)

    def __init__(self, routes: Mapping[str, ProxyRoute]) -> None:
        self._routes: dict[str, ProxyRoute] = dict(routes)

    def get(self, name: str) -> ProxyRoute | None:
        return self._routes.get(name)

    def __len__(self) -> int:
        return len(self._routes)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._routes))

    def routes(self) -> tuple[ProxyRoute, ...]:
        """Return routes in stable, name-sorted order for safe diagnostics."""
        return tuple(self._routes[name] for name in sorted(self._routes))


def build_route_table(chain_entries: list[tuple[str, str, str, str]]) -> RouteTable:
    """Build a :class:`RouteTable` from ``(provider, slug, base_url, api_key_env)``.

    Duplicate ``(provider, slug)`` pairs collapse to one route (same upstream).
    Conflicting upstreams for the same name is a config error.
    """
    routes: dict[str, ProxyRoute] = {}
    for provider, slug, base_url, api_key_env in chain_entries:
        name = route_name_for(provider, slug)
        # Belt-and-braces (R2-2): refuse to build a route whose upstream is not
        # https (the proxy injects the real key into the request, so an http or
        # otherwise-rewritten base_url would send the key in clear / to an
        # attacker). The proxy's models.yaml is mounted from a proxy-only dir the
        # agent cannot write, but this is a second, independent guard.
        parsed = urlparse(base_url)
        _https = parsed.scheme == "https" and bool(parsed.hostname)
        _local_http = parsed.scheme == "http" and parsed.hostname in _LOCAL_HOSTS
        if not (_https or _local_http):
            raise ProxyConfigError(
                f"route {name!r}: upstream base_url must be https:// (or "
                f"http://localhost); got {base_url!r}"
            )
        existing = routes.get(name)
        candidate = ProxyRoute(
            name=name,
            provider=provider,
            upstream_base_url=base_url.rstrip("/"),
            api_key_env=api_key_env,
        )
        if existing is not None and existing != candidate:
            raise ProxyConfigError(
                f"route {name!r} maps to conflicting upstreams: "
                f"{existing.upstream_base_url} vs {candidate.upstream_base_url}"
            )
        routes[name] = candidate
    return RouteTable(routes)


def inject_headers(
    route: ProxyRoute,
    inbound_headers: Mapping[str, str],
    api_key: str,
) -> dict[str, str]:
    """Return headers to send upstream: caller auth stripped, real auth injected.

    Any inbound ``Authorization`` / ``x-api-key`` / proxy token header is
    dropped so the agent can neither supply nor influence provider auth.
    """
    drop = {
        "authorization",
        "x-api-key",
        "x-fa-proxy-token",
        "x-fa-timeout",
        "host",
        "content-length",
    }
    out: dict[str, str] = {k: v for k, v in inbound_headers.items() if k.lower() not in drop}
    if route.provider in _XAPIKEY_PROVIDERS:
        out["x-api-key"] = api_key
        out.setdefault("anthropic-version", ANTHROPIC_API_VERSION)
    else:
        out["Authorization"] = f"Bearer {api_key}"
    out.setdefault("Content-Type", "application/json")
    return out
