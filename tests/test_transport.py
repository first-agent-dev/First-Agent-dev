"""Tests for fa.providers.transport.UrllibTransport.

The transport is exercised with monkeypatched ``urllib.request.urlopen``
so the suite runs offline. The pure helpers (``_parse_retry_after``,
``_decode_body``) are tested directly against their edge cases.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any, Self

import pytest

from fa.providers.transport import (
    DEFAULT_USER_AGENT,
    UrllibTransport,
    _decode_body,
    _parse_retry_after,
)

# -- _parse_retry_after -----------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("not-a-number", None),
        ("10", 10.0),
        ("0.5", 0.5),
        ("-5", 0.0),  # clamped to non-negative
    ],
)
def test_parse_retry_after_returns_expected(value: str | None, expected: float | None) -> None:
    assert _parse_retry_after(value) == expected


# -- _decode_body ------------------------------------------------------------


def test_decode_body_handles_empty_bytes() -> None:
    assert _decode_body(b"") == {}


def test_decode_body_handles_valid_json_object() -> None:
    assert _decode_body(b'{"k":"v"}') == {"k": "v"}


def test_decode_body_returns_empty_for_non_object_json() -> None:
    assert _decode_body(b"[1, 2, 3]") == {}
    assert _decode_body(b'"string"') == {}


def test_decode_body_returns_empty_for_malformed_json() -> None:
    assert _decode_body(b"{not json") == {}


def test_decode_body_returns_empty_for_non_utf8() -> None:
    assert _decode_body(b"\xff\xfe\xfd") == {}


# -- UrllibTransport.post ----------------------------------------------------


class _FakeResponse:
    def __init__(self, status: int, body: bytes, headers: Mapping[str, str]) -> None:
        self.status = status
        self._body = body
        self.headers = dict(headers)

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_post_returns_decoded_body_on_200(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        captured["url"] = request.full_url
        captured["body"] = request.data
        captured["headers"] = dict(request.headers)
        return _FakeResponse(200, b'{"ok":true}', {})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    transport = UrllibTransport()
    response = transport.post(
        "https://example.invalid/v1/chat/completions",
        headers={"Authorization": "Bearer key", "X-Custom": "1"},
        json_body={"model": "x"},
        timeout_seconds=10.0,
    )

    assert response.status == 200
    assert response.body == {"ok": True}
    assert response.retry_after_seconds is None
    assert response.network_error is None
    assert captured["url"] == "https://example.invalid/v1/chat/completions"
    assert captured["body"] == b'{"model": "x"}'
    # add_header normalises header keys to title-case.
    assert captured["headers"]["User-agent"] == DEFAULT_USER_AGENT
    assert captured["headers"]["Authorization"] == "Bearer key"


def test_post_returns_status_and_retry_after_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=429,
            msg="rate limited",
            hdrs={"Retry-After": "42"},  # type: ignore[arg-type]
            fp=io.BytesIO(b'{"error":{"code":"rate_limited"}}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    transport = UrllibTransport()
    response = transport.post(
        "https://example.invalid/v1",
        headers={},
        json_body={},
        timeout_seconds=5.0,
    )

    assert response.status == 429
    assert response.retry_after_seconds == 42.0
    assert response.body == {"error": {"code": "rate_limited"}}
    assert response.network_error is None


def test_post_captures_network_error_on_urlerror(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        raise urllib.error.URLError("dns resolution failed")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    transport = UrllibTransport()
    response = transport.post(
        "https://nowhere.invalid",
        headers={},
        json_body={},
        timeout_seconds=1.0,
    )

    assert response.status == 0
    assert response.body == {}
    assert response.network_error is not None
    assert "dns resolution" in response.network_error


def test_post_captures_network_error_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    transport = UrllibTransport()
    response = transport.post(
        "https://slow.invalid",
        headers={},
        json_body={},
        timeout_seconds=0.1,
    )

    assert response.status == 0
    assert response.network_error is not None


def test_post_serialises_json_body_consistently(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_bodies: list[bytes] = []

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        body = request.data
        assert isinstance(body, bytes)
        captured_bodies.append(body)
        return _FakeResponse(200, b"{}", {})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    transport = UrllibTransport()
    payload = {"messages": [{"role": "user", "content": "x"}], "model": "y"}
    transport.post("https://x.invalid", headers={}, json_body=payload, timeout_seconds=1.0)
    transport.post("https://x.invalid", headers={}, json_body=payload, timeout_seconds=1.0)

    assert captured_bodies[0] == captured_bodies[1]
    decoded = json.loads(captured_bodies[0])
    assert decoded == payload


def test_user_agent_is_overridable() -> None:
    transport = UrllibTransport(user_agent="my-fa/0.1")
    assert transport._user_agent == "my-fa/0.1"
