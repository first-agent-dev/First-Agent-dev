"""Production HTTP transport for the T-2 provider chain (ADR-9).

:class:`UrllibTransport` is the single production-side implementation
of the :class:`fa.providers.base.Transport` Protocol. It uses
``urllib.request`` from the standard library so the chain has a real
HTTP client without adding a new third-party dependency to FA's
runtime surface (deferred decision: ``httpx`` migration is tracked
under ADR-9 §1's ``httpx_retries`` field — see BACKLOG row when the
need for HTTP/2 or pooled connections forces the dep).

Scope is intentionally narrow:

- POST JSON only. Adapters never GET in v0.1 (response normalisation
  is body-only); GET / PUT / DELETE are out of scope.
- Map HTTP status → :class:`fa.providers.base.TransportResponse` with
  the body JSON-decoded once. Adapters consume the decoded mapping;
  raw bytes never escape the transport.
- Parse ``Retry-After`` header per RFC 9110 seconds-form only
  (HTTP-date form is out of scope per ADR-9 §3 footnote — adapters
  fall back to the chain's configured cooldown floor when the
  header is absent or non-numeric).
- ``network_error`` surface captures URLError / socket.timeout /
  json.JSONDecodeError as a single string carried back to the
  adapter, which re-raises as
  :class:`fa.providers.errors.ProviderTransientError` per ADR-9 §2.

References:
- ``knowledge/adr/ADR-9-llm-provider-client.md`` §2 (runtime
  semantics; status-code routing in the chain dispatcher).
- ``knowledge/adr/ADR-9-llm-provider-client.md`` §3 (Retry-After
  parsing; adaptive cooldown floor).
- :class:`fa.providers.base.Transport` Protocol (the contract this
  transport implements).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

from fa.providers.base import Transport, TransportResponse

DEFAULT_USER_AGENT = "first-agent/0.1 (+https://github.com/MondayInRussian/First-Agent-fork2)"


class UrllibTransport(Transport):
    """stdlib-based :class:`Transport` implementation.

    Args:
        user_agent: Value sent as ``User-Agent``; defaults to
            :data:`DEFAULT_USER_AGENT`. Providers that fingerprint
            the agent (GitHub Models, some Anthropic endpoints) treat
            unmarked clients with stricter rate limits; surfacing a
            recognisable UA reduces unnecessary 429 noise.
    """

    def __init__(self, *, user_agent: str = DEFAULT_USER_AGENT) -> None:
        self._user_agent = user_agent

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> TransportResponse:
        body_bytes = json.dumps(json_body).encode("utf-8")
        request = urllib.request.Request(url, data=body_bytes, method="POST")
        # Defensive: urllib.request.Request does not set Content-Type
        # automatically in all Python versions when data is provided.
        # Set it here unless the caller already provided one, so a
        # generic adapter that forgets the header still sends valid JSON.
        if not any(k.lower() == "content-type" for k in headers):
            request.add_header("Content-Type", "application/json")
        request.add_header("User-Agent", self._user_agent)
        for key, value in headers.items():
            if key.lower() != "user-agent":
                request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                status = int(response.status)
                raw = response.read()
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            raw = exc.read()
            retry_after = _parse_retry_after(exc.headers.get("Retry-After"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            return TransportResponse(
                status=0,
                body={},
                retry_after_seconds=None,
                network_error=str(exc),
            )
        return TransportResponse(
            status=status,
            body=_decode_body(raw),
            retry_after_seconds=retry_after,
        )


def _decode_body(raw: bytes) -> Mapping[str, Any]:
    if not raw:
        return {}
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, Mapping) else {}


def _parse_retry_after(value: str | None) -> float | None:
    """Parse RFC 9110 ``Retry-After`` seconds-form into a float.

    Returns ``None`` for absent, blank, or non-numeric values
    (HTTP-date form is out of scope per ADR-9 §3 footnote — the chain
    falls back to its configured cooldown floor in that case).
    """
    if value is None or not value.strip():
        return None
    try:
        seconds = float(value.strip())
    except ValueError:
        return None
    return max(seconds, 0.0)


__all__ = ["DEFAULT_USER_AGENT", "UrllibTransport"]
