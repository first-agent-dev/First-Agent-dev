"""Stdlib HTTP server for the egress-injection proxy (ADR-12).

Endpoints:

* ``GET  /healthz``                       → 200 ``ok`` (healthy even with 0 routes)
* ``GET  /routes``                        → safe route diagnostics (token required)
* ``POST /route/<name>/<upstream-path>``  → inject key, forward, return response

Security:

* Requires ``X-FA-Proxy-Token: <token>`` matching the configured token for
  every endpoint except ``/healthz`` (constant-time compare). This proves the
  caller is the fa agent, not a stray actor on the network; it is NOT a provider
  key (leaking it only enables metered LLM calls through the proxy, a cost risk
  — not key disclosure).
* Unknown route → 404 (no SSRF: upstreams come only from the route table).
* Never logs request/response bodies, headers, or keys. Logs only
  ``route, status, ms``.
"""

from __future__ import annotations

import hmac
import json
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, override

from fa.egress_proxy.routing import RouteTable, inject_headers

__all__ = ["build_handler_class", "serve"]

_MAX_BODY_BYTES = 8 * 1024 * 1024  # 8 MiB cap on request bodies.

# Upstream forward timeout. The agent advertises its per-route timeout via the
# ``X-FA-Timeout`` header (so a slow reasoning model configured with e.g.
# ``timeout_seconds: 240`` is honored instead of being cut at a hardcoded 60s,
# which surfaced as a spurious 502 → chain_exhausted). The value is clamped to
# ``_MAX_UPSTREAM_TIMEOUT`` so a compromised/buggy agent cannot pin a proxy
# worker thread open indefinitely. ``X-FA-Timeout: 0`` means "no transport
# timeout" on the agent side; we map it to the ceiling rather than unbounded.
_DEFAULT_UPSTREAM_TIMEOUT = 60.0
_MAX_UPSTREAM_TIMEOUT = 600.0


def _resolve_upstream_timeout(raw: str | None) -> float:
    """Parse + clamp the agent-advertised upstream timeout (seconds)."""
    if raw is None or not raw.strip():
        return _DEFAULT_UPSTREAM_TIMEOUT
    try:
        value = float(raw.strip())
    except ValueError:
        return _DEFAULT_UPSTREAM_TIMEOUT
    if value <= 0:
        # 0 = "opt out of the transport timeout" on the agent side; bound it.
        return _MAX_UPSTREAM_TIMEOUT
    return min(value, _MAX_UPSTREAM_TIMEOUT)


class _EgressProxyHandler(BaseHTTPRequestHandler):
    """Base handler; build_handler_class binds per-server class attributes."""

    route_table: RouteTable
    secrets: dict[str, str]
    proxy_token: str
    forward: Any

    # Silence default stderr access logging (could leak paths); we log our
    # own minimal line instead.
    @override
    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json_error(self, status: int, message: str) -> None:
        self._send(status, json.dumps({"error": message}).encode("utf-8"))

    def _authorized(self) -> bool:
        supplied = self.headers.get("X-FA-Proxy-Token", "")
        return bool(self.proxy_token) and hmac.compare_digest(supplied, self.proxy_token)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send(200, b'{"status":"ok"}')
            return
        if self.path == "/routes":
            self._handle_routes()
            return
        self._send_json_error(404, "not found")

    def _handle_routes(self) -> None:
        # /healthz stays open for Docker healthcheck, but /routes exposes
        # operational routing state (names + key-presence booleans). Keep it
        # behind the same fa→proxy token boundary as POST /route so a random
        # network peer cannot enumerate model routes. The payload deliberately
        # excludes api_key values, api_key_env names, and upstream_base_url values.
        if not self._authorized():
            self._send_json_error(403, "forbidden")
            return
        payload = [
            {
                "name": route.name,
                "has_key": bool(self.secrets.get(route.api_key_env, "").strip()),
            }
            for route in self.route_table.routes()
        ]
        self._send(200, json.dumps(payload, sort_keys=True).encode("utf-8"))

    def do_POST(self) -> None:
        start = time.monotonic()
        # 1. Authn: fa→proxy bootstrap token (constant-time).
        if not self._authorized():
            self._send_json_error(403, "forbidden")
            return

        # 2. Route parse: /route/<name>/<upstream-path...>
        if not self.path.startswith("/route/"):
            self._send_json_error(404, "not found")
            return
        remainder = self.path[len("/route/") :]
        name, sep, upstream_path = remainder.partition("/")
        if not sep:
            upstream_path = ""
        route = self.route_table.get(name)
        if route is None:
            self._send_json_error(404, "unknown route")
            return

        # 3. Body (size-capped).
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > _MAX_BODY_BYTES:
            self._send_json_error(413, "request too large")
            return
        body = self.rfile.read(length) if length else b""

        # 4. Inject real key, strip caller auth, forward.
        api_key = self.secrets.get(route.api_key_env, "")
        inbound = dict(self.headers.items())
        # Honor the agent's per-route timeout (clamped) before inject_headers
        # strips the X-FA-Timeout hop header.
        timeout = _resolve_upstream_timeout(self.headers.get("X-FA-Timeout"))
        headers = inject_headers(route, inbound, api_key)
        url = f"{route.upstream_base_url}/{upstream_path.lstrip('/')}"
        try:
            status, _resp_headers, resp_body = self.forward(url, headers, body, timeout)
        except Exception:  # noqa: BLE001 - never leak upstream exception text
            self._send_json_error(502, "upstream error")
            self._log(name, 502, start)
            return

        self._send(status, resp_body)
        self._log(name, status, start)

    def _log(self, route_name: str, status: int, start: float) -> None:
        ms = int((time.monotonic() - start) * 1000)
        # Minimal, secret-free operational line.
        print(f"egress-proxy route={route_name} status={status} ms={ms}", flush=True)


def build_handler_class(
    *,
    route_table: RouteTable,
    secrets: dict[str, str],
    proxy_token: str,
    forward: Any = None,
) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to a route table + secrets.

    ``forward`` is an injectable forwarder ``(url, headers, body, timeout) ->
    (status, resp_headers, resp_body)`` so tests can run without network. When
    ``None`` a urllib-based forwarder is used.
    """

    class _Handler(_EgressProxyHandler):
        pass

    _Handler.route_table = route_table
    _Handler.secrets = secrets
    _Handler.proxy_token = proxy_token
    _Handler.forward = staticmethod(forward if forward is not None else _urllib_forward)
    return _Handler


def _urllib_forward(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, data=body, method="POST")  # noqa: S310
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return int(resp.status), dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        # Forward upstream non-2xx faithfully (the chain maps status codes).
        return int(exc.code), dict(exc.headers or {}), exc.read()


def serve(
    *,
    route_table: RouteTable,
    secrets: dict[str, str],
    proxy_token: str,
    host: str,
    port: int,
) -> None:  # pragma: no cover - exercised via integration, not unit tests
    handler = build_handler_class(route_table=route_table, secrets=secrets, proxy_token=proxy_token)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(
        f"egress-proxy listening on {host}:{port} routes={len(route_table)}",
        flush=True,
    )
    httpd.serve_forever()
