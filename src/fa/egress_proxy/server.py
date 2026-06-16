"""Stdlib HTTP server for the egress-injection proxy (ADR-12).

Endpoints:

* ``GET  /healthz``                       → 200 ``ok`` (healthy even with 0 routes)
* ``POST /route/<name>/<upstream-path>``  → inject key, forward, return response

Security:

* Requires ``X-FA-Proxy-Token: <token>`` matching the configured token
  (constant-time compare). This proves the caller is the fa agent, not a stray
  actor on the network; it is NOT a provider key (leaking it only enables
  metered LLM calls through the proxy, a cost risk — not key disclosure).
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

    _forward = forward if forward is not None else _urllib_forward

    class _Handler(BaseHTTPRequestHandler):
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

        def do_GET(self) -> None:
            if self.path == "/healthz":
                self._send(200, b'{"status":"ok"}')
                return
            self._send_json_error(404, "not found")

        def do_POST(self) -> None:
            start = time.monotonic()
            # 1. Authn: fa→proxy bootstrap token (constant-time).
            supplied = self.headers.get("X-FA-Proxy-Token", "")
            if not proxy_token or not hmac.compare_digest(supplied, proxy_token):
                self._send_json_error(403, "forbidden")
                return

            # 2. Route parse: /route/<name>/<upstream-path...>
            if not self.path.startswith("/route/"):
                self._send_json_error(404, "not found")
                return
            remainder = self.path[len("/route/"):]
            name, sep, upstream_path = remainder.partition("/")
            if not sep:
                upstream_path = ""
            route = route_table.get(name)
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
            api_key = secrets.get(route.api_key_env, "")
            inbound = dict(self.headers.items())
            headers = inject_headers(route, inbound, api_key)
            url = f"{route.upstream_base_url}/{upstream_path.lstrip('/')}"
            try:
                status, _resp_headers, resp_body = _forward(url, headers, body, 60.0)
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
    handler = build_handler_class(
        route_table=route_table, secrets=secrets, proxy_token=proxy_token
    )
    httpd = ThreadingHTTPServer((host, port), handler)
    print(
        f"egress-proxy listening on {host}:{port} routes={len(route_table)}",
        flush=True,
    )
    httpd.serve_forever()
