"""Phase D (ADR-12): egress-injection proxy unit tests (no network).

Proves the proxy injects the real key, strips caller-supplied auth, rejects a
bad/absent token, 404s unknown routes, healthchecks, and NEVER echoes a key.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
from typing import Any

import pytest

from fa.egress_proxy.routing import (
    ProxyConfigError,
    build_route_table,
    inject_headers,
    route_name_for,
)
from fa.egress_proxy.server import build_handler_class

_KEY = "fw-PROXY-REAL-KEY-0xDEADBEEF-123456"
_TOKEN = "fa-proxy-bootstrap-token-xyz"


# --- routing (pure) --------------------------------------------------------
def test_route_name_is_url_safe() -> None:
    assert route_name_for("openrouter", "meta-llama/llama-3.1-8b") == (
        "openrouter-meta-llama-llama-3-1-8b"
    )


def test_build_route_table_dedupes_and_detects_conflict() -> None:
    t = build_route_table(
        [
            ("openrouter", "x", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
            ("openrouter", "x", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
        ]
    )
    assert len(t) == 1
    with pytest.raises(ProxyConfigError):
        build_route_table(
            [
                ("p", "s", "https://a.example", "K"),
                ("p", "s", "https://b.example", "K"),
            ]
        )


def test_build_route_table_rejects_non_https_upstream() -> None:
    """R2-2: a tampered models.yaml must not redirect the key-injecting proxy to
    an http:// or attacker host. https required (http only for localhost)."""
    with pytest.raises(ProxyConfigError):
        build_route_table([("p", "s", "http://attacker.example/v1", "K")])
    with pytest.raises(ProxyConfigError):
        build_route_table([("p", "s", "ftp://x/v1", "K")])
    # localhost gateway over http is tolerated (matches provider-config policy).
    t = build_route_table([("p", "s", "http://localhost:8000/v1", "K")])
    assert len(t) == 1


def test_inject_headers_strips_caller_auth_openai() -> None:
    t = build_route_table([("openrouter", "s", "https://up.example/v1", "OPENROUTER_API_KEY")])
    route = t.get("openrouter-s")
    assert route is not None
    out = inject_headers(
        route,
        {"Authorization": "Bearer attacker", "X-FA-Proxy-Token": _TOKEN, "X-Keep": "1"},
        _KEY,
    )
    assert out["Authorization"] == f"Bearer {_KEY}"
    assert "X-FA-Proxy-Token" not in set(out)  # stripped
    assert out["X-Keep"] == "1"


def test_inject_headers_anthropic_uses_x_api_key() -> None:
    t = build_route_table(
        [("anthropic", "claude", "https://api.anthropic.com", "ANTHROPIC_API_KEY")]
    )
    route = t.get("anthropic-claude")
    assert route is not None
    out = inject_headers(route, {"x-api-key": "attacker"}, _KEY)
    assert out["x-api-key"] == _KEY
    assert out["anthropic-version"]
    assert "Authorization" not in out


# --- server (in-process, injected forwarder) -------------------------------
def _make_server() -> tuple[ThreadingHTTPServer, list[dict[str, Any]]]:
    captured: list[dict[str, Any]] = []

    def fake_forward(
        url: str, headers: Mapping[str, str], body: bytes, timeout: float
    ) -> tuple[int, dict[str, str], bytes]:
        captured.append({"url": url, "headers": headers, "body": body})
        return 200, {"Content-Type": "application/json"}, json.dumps({"ok": True}).encode()

    table = build_route_table([("openrouter", "s", "https://up.example/v1", "OPENROUTER_API_KEY")])
    handler = build_handler_class(
        route_table=table,
        secrets={"OPENROUTER_API_KEY": _KEY},
        proxy_token=_TOKEN,
        forward=fake_forward,
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd._captured = captured  # type: ignore[attr-defined]
    return httpd, captured


def _run(httpd: ThreadingHTTPServer) -> Thread:
    t = threading.Thread(target=httpd.handle_request)
    t.daemon = True
    t.start()
    return t


def _request(
    port: int,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes = b"",
) -> tuple[int, bytes]:
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, path, body=body, headers=headers or {})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, data


def test_healthz_ok() -> None:
    httpd, _ = _make_server()
    port = httpd.server_address[1]
    _run(httpd)
    status, data = _request(port, "GET", "/healthz")
    assert status == 200
    assert b"ok" in data


def test_routes_requires_proxy_token() -> None:
    httpd, _ = _make_server()
    port = httpd.server_address[1]
    _run(httpd)
    status, _ = _request(port, "GET", "/routes")
    assert status == 403


def test_routes_returns_only_safe_fields_and_has_key() -> None:
    table = build_route_table(
        [
            ("openrouter", "s", "https://up.example/v1", "OPENROUTER_API_KEY"),
            ("anthropic", "claude", "https://api.anthropic.com", "ANTHROPIC_API_KEY"),
        ]
    )
    handler = build_handler_class(
        route_table=table,
        secrets={"OPENROUTER_API_KEY": _KEY, "ANTHROPIC_API_KEY": ""},
        proxy_token=_TOKEN,
        forward=None,
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    _run(httpd)

    status, data = _request(
        port,
        "GET",
        "/routes",
        headers={"X-FA-Proxy-Token": _TOKEN},
    )

    assert status == 200
    routes = json.loads(data.decode("utf-8"))
    assert routes == [
        {"has_key": False, "name": "anthropic-claude"},
        {"has_key": True, "name": "openrouter-s"},
    ]
    assert all(set(row) == {"name", "has_key"} for row in routes)
    body = data.decode("utf-8")
    # /routes must not expand the agent's leak/use surface: no key values, no
    # env-var names (which can be sensitive operational metadata), and no
    # upstream URLs that a compromised caller could enumerate.
    assert _KEY not in body
    assert "OPENROUTER_API_KEY" not in body
    assert "ANTHROPIC_API_KEY" not in body
    assert "up.example" not in body
    assert "api.anthropic.com" not in body
    assert "api_key_env" not in body
    assert "upstream" not in body


def test_routes_treats_whitespace_secret_as_missing() -> None:
    table = build_route_table([("openrouter", "s", "https://up.example/v1", "OPENROUTER_API_KEY")])
    handler = build_handler_class(
        route_table=table,
        secrets={"OPENROUTER_API_KEY": "   "},
        proxy_token=_TOKEN,
        forward=None,
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    _run(httpd)

    status, data = _request(port, "GET", "/routes", headers={"X-FA-Proxy-Token": _TOKEN})

    assert status == 200
    assert json.loads(data.decode("utf-8")) == [{"has_key": False, "name": "openrouter-s"}]


def test_post_injects_key_and_strips_caller_auth() -> None:
    httpd, captured = _make_server()
    port = httpd.server_address[1]
    _run(httpd)
    status, data = _request(
        port,
        "POST",
        "/route/openrouter-s/chat/completions",
        headers={
            "X-FA-Proxy-Token": _TOKEN,
            "Authorization": "Bearer attacker-supplied",
            "Content-Type": "application/json",
        },
        body=b'{"model":"x","messages":[]}',
    )
    assert status == 200
    assert captured, "forwarder should have been called"
    sent = captured[0]
    assert sent["url"] == "https://up.example/v1/chat/completions"
    assert sent["headers"]["Authorization"] == f"Bearer {_KEY}"
    # The key must never be echoed back to the caller.
    assert _KEY.encode() not in data


def test_bad_token_rejected() -> None:
    httpd, _ = _make_server()
    port = httpd.server_address[1]
    _run(httpd)
    status, _ = _request(
        port,
        "POST",
        "/route/openrouter-s/chat/completions",
        headers={"X-FA-Proxy-Token": "wrong", "Content-Type": "application/json"},
        body=b"{}",
    )
    assert status == 403


def test_unknown_route_404() -> None:
    httpd, _ = _make_server()
    port = httpd.server_address[1]
    _run(httpd)
    status, _ = _request(
        port,
        "POST",
        "/route/does-not-exist/chat/completions",
        headers={"X-FA-Proxy-Token": _TOKEN, "Content-Type": "application/json"},
        body=b"{}",
    )
    assert status == 404


# --- F-2: per-route upstream timeout ---------------------------------------
def test_resolve_upstream_timeout_clamps_and_defaults() -> None:
    from fa.egress_proxy.server import (
        _DEFAULT_UPSTREAM_TIMEOUT,
        _MAX_UPSTREAM_TIMEOUT,
        _resolve_upstream_timeout,
    )

    assert _resolve_upstream_timeout(None) == _DEFAULT_UPSTREAM_TIMEOUT
    assert _resolve_upstream_timeout("") == _DEFAULT_UPSTREAM_TIMEOUT
    assert _resolve_upstream_timeout("not-a-number") == _DEFAULT_UPSTREAM_TIMEOUT
    assert _resolve_upstream_timeout("240") == 240.0
    # 0 = "no transport timeout" on the agent side → bounded to the ceiling.
    assert _resolve_upstream_timeout("0") == _MAX_UPSTREAM_TIMEOUT
    # A buggy/hostile agent cannot pin a worker open beyond the ceiling.
    assert _resolve_upstream_timeout("99999") == _MAX_UPSTREAM_TIMEOUT


def test_inject_headers_strips_x_fa_timeout() -> None:
    t = build_route_table([("openrouter", "s", "https://up.example/v1", "OPENROUTER_API_KEY")])
    route = t.get("openrouter-s")
    assert route is not None
    out = inject_headers(route, {"X-FA-Timeout": "240", "X-Keep": "1"}, _KEY)
    assert "X-FA-Timeout" not in set(out)
    assert all(k.lower() != "x-fa-timeout" for k in out)
    assert out["X-Keep"] == "1"


def _make_server_capturing_timeout() -> tuple[ThreadingHTTPServer, list[dict[str, Any]]]:
    captured: list[dict[str, Any]] = []

    def fake_forward(
        url: str, headers: Mapping[str, str], body: bytes, timeout: float
    ) -> tuple[int, dict[str, str], bytes]:
        captured.append({"url": url, "headers": headers, "timeout": timeout})
        return 200, {"Content-Type": "application/json"}, b"{}"

    table = build_route_table([("openrouter", "s", "https://up.example/v1", "OPENROUTER_API_KEY")])
    handler = build_handler_class(
        route_table=table,
        secrets={"OPENROUTER_API_KEY": _KEY},
        proxy_token=_TOKEN,
        forward=fake_forward,
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    return httpd, captured


def test_post_honors_agent_supplied_timeout() -> None:
    httpd, captured = _make_server_capturing_timeout()
    port = httpd.server_address[1]
    _run(httpd)
    status, _ = _request(
        port,
        "POST",
        "/route/openrouter-s/chat/completions",
        headers={
            "X-FA-Proxy-Token": _TOKEN,
            "X-FA-Timeout": "240",
            "Content-Type": "application/json",
        },
        body=b"{}",
    )
    assert status == 200
    assert captured and captured[0]["timeout"] == 240.0


def test_post_without_timeout_header_uses_default() -> None:
    from fa.egress_proxy.server import _DEFAULT_UPSTREAM_TIMEOUT

    httpd, captured = _make_server_capturing_timeout()
    port = httpd.server_address[1]
    _run(httpd)
    status, _ = _request(
        port,
        "POST",
        "/route/openrouter-s/chat/completions",
        headers={"X-FA-Proxy-Token": _TOKEN, "Content-Type": "application/json"},
        body=b"{}",
    )
    assert status == 200
    assert captured and captured[0]["timeout"] == _DEFAULT_UPSTREAM_TIMEOUT
