"""Tests for fa.providers.debug_bodies (ADR-9 Sec4 Tier-3 opt-in body capture).

Covers:
- ``is_debug_bodies_enabled`` — exact-match ``"1"`` gate, no other truthy
  string accepted (avoids surprising "FA_DEBUG_LLM_BODIES=true" no-ops).
- ``wrap_transport_for_debug_bodies`` — returns the SAME transport object
  unchanged when disabled (zero overhead in the default path); wraps in
  :class:`DebugBodyTransport` when enabled.
- ``DebugBodyTransport`` — transparent passthrough of the inner transport's
  return value/behavior; writes exactly one JSON row per ``post()`` call to
  the configured path; correlates via :func:`debug_body_context`; redacts
  when a redactor is supplied; never raises on a write failure.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from fa.observability.redaction import SecretRedactor
from fa.providers.base import TransportResponse
from fa.providers.debug_bodies import (
    DebugBodyTransport,
    debug_body_context,
    is_debug_bodies_enabled,
    wrap_transport_for_debug_bodies,
)


class _FakeTransport:
    """Records every call it receives; returns a canned response.

    Duck-typed against the :class:`~fa.providers.base.Transport` Protocol
    (matches the convention already used by other fake transports in this
    test suite, e.g. ``tests/test_cli.py``'s fakes — no subclassing, so no
    ``@override`` obligation for a Protocol member).
    """

    name = "fake"

    def __init__(self, response: TransportResponse) -> None:
        self.response = response
        self.calls: list[Mapping[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
        transport_retries: int,
    ) -> TransportResponse:
        self.calls.append(dict(json_body))
        return self.response


# -- is_debug_bodies_enabled --------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        ("0", False),
        ("true", False),  # exact-match "1" only — no truthy-string surprises
        ("True", False),
        ("", False),
        (" 1 ", True),  # stripped
    ],
)
def test_is_debug_bodies_enabled_exact_match(value: str, expected: bool) -> None:
    assert is_debug_bodies_enabled({"FA_DEBUG_LLM_BODIES": value}) is expected


def test_is_debug_bodies_enabled_defaults_to_false_when_absent() -> None:
    assert is_debug_bodies_enabled({}) is False


# -- wrap_transport_for_debug_bodies ------------------------------------------


def test_wrap_returns_same_object_when_disabled(tmp_path: Path) -> None:
    inner = _FakeTransport(TransportResponse(status=200, body={}))
    wrapped = wrap_transport_for_debug_bodies(
        inner,
        run_log_dir=tmp_path,
        env={"FA_DEBUG_LLM_BODIES": "0"},
    )
    assert wrapped is inner


def test_wrap_returns_debug_body_transport_when_enabled(tmp_path: Path) -> None:
    inner = _FakeTransport(TransportResponse(status=200, body={}))
    wrapped = wrap_transport_for_debug_bodies(
        inner,
        run_log_dir=tmp_path,
        env={"FA_DEBUG_LLM_BODIES": "1"},
    )
    assert isinstance(wrapped, DebugBodyTransport)


# -- DebugBodyTransport --------------------------------------------------------


def test_debug_body_transport_passes_through_response_unchanged(tmp_path: Path) -> None:
    canned = TransportResponse(status=200, body={"choices": [{"text": "hi"}]})
    inner = _FakeTransport(canned)
    transport = DebugBodyTransport(inner, path=tmp_path / "llm_bodies.jsonl")

    result = transport.post(
        "https://api.example.com/v1/chat",
        headers={"Authorization": "Bearer x"},
        json_body={"model": "m", "messages": []},
        timeout_seconds=30.0,
        transport_retries=1,
    )

    assert result is canned
    assert inner.calls == [{"model": "m", "messages": []}]


def test_debug_body_transport_writes_one_row_per_call(tmp_path: Path) -> None:
    inner = _FakeTransport(TransportResponse(status=200, body={"ok": True}))
    path = tmp_path / "llm_bodies.jsonl"
    transport = DebugBodyTransport(inner, path=path)

    with debug_body_context(logical_call_id="call-1", provider="openrouter", slug="m/x", attempt_index=0):
        transport.post(
            "https://api.example.com/v1/chat",
            headers={},
            json_body={"model": "m/x"},
            timeout_seconds=30.0,
            transport_retries=0,
        )

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "llm_body"
    assert row["logical_call_id"] == "call-1"
    assert row["provider"] == "openrouter"
    assert row["slug"] == "m/x"
    assert row["attempt_index"] == 0
    assert row["request_body"] == {"model": "m/x"}
    assert row["response_body"] == {"ok": True}


def test_debug_body_transport_correlates_multiple_attempts(tmp_path: Path) -> None:
    """Two attempts of the same logical call each get their own row,
    both carrying the SAME logical_call_id (the correlation contract
    ADR-9 Sec4 requires across Tier-1/2/3 rows) but DIFFERENT attempt_index."""
    inner = _FakeTransport(TransportResponse(status=200, body={}))
    path = tmp_path / "llm_bodies.jsonl"
    transport = DebugBodyTransport(inner, path=path)

    for idx, provider in enumerate(("openrouter", "fireworks")):
        with debug_body_context(logical_call_id="call-shared", provider=provider, slug="m", attempt_index=idx):
            transport.post(
                "https://api.example.com/v1/chat",
                headers={},
                json_body={"attempt": idx},
                timeout_seconds=30.0,
                transport_retries=0,
            )

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert {row["logical_call_id"] for row in rows} == {"call-shared"}
    assert [row["attempt_index"] for row in rows] == [0, 1]
    assert [row["provider"] for row in rows] == ["openrouter", "fireworks"]


def test_debug_body_transport_without_context_still_writes_row(tmp_path: Path) -> None:
    """A caller that forgets to bind debug_body_context (e.g. a direct
    adapter unit test) must not crash — correlation fields degrade to
    empty/placeholder values instead."""
    inner = _FakeTransport(TransportResponse(status=200, body={}))
    path = tmp_path / "llm_bodies.jsonl"
    transport = DebugBodyTransport(inner, path=path)

    transport.post(
        "https://api.example.com/v1/chat",
        headers={},
        json_body={"model": "m"},
        timeout_seconds=30.0,
        transport_retries=0,
    )

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["logical_call_id"] == ""
    assert rows[0]["attempt_index"] == -1


def test_debug_body_transport_redacts_secrets_in_bodies(tmp_path: Path) -> None:
    secret = "sk-super-secret-key-value"
    redactor = SecretRedactor({"FAKE_KEY": secret}, ["FAKE_KEY"])
    inner = _FakeTransport(TransportResponse(status=200, body={"echo": secret}))
    path = tmp_path / "llm_bodies.jsonl"
    transport = DebugBodyTransport(inner, path=path, redactor=redactor)

    transport.post(
        "https://api.example.com/v1/chat",
        headers={},
        json_body={"prompt": f"the key is {secret}"},
        timeout_seconds=30.0,
        transport_retries=0,
    )

    raw_line = path.read_text(encoding="utf-8")
    assert secret not in raw_line
    row = json.loads(raw_line)
    assert "***REDACTED***" in row["request_body"]["prompt"]
    assert "***REDACTED***" in row["response_body"]["echo"]


def test_debug_body_transport_redacts_secrets_nested_in_lists_and_tuples(tmp_path: Path) -> None:
    """Request bodies routinely nest secrets inside ``messages: [...]``
    lists (a leaked API key pasted into a user turn, a tool result echoing
    a token) — the redaction walk must recurse into list/tuple values, not
    just top-level string/dict fields."""
    secret = "sk-super-secret-key-value"
    redactor = SecretRedactor({"FAKE_KEY": secret}, ["FAKE_KEY"])
    inner = _FakeTransport(TransportResponse(status=200, body={}))
    path = tmp_path / "llm_bodies.jsonl"
    transport = DebugBodyTransport(inner, path=path, redactor=redactor)

    transport.post(
        "https://api.example.com/v1/chat",
        headers={},
        json_body={
            "messages": [
                {"role": "user", "content": f"leaked: {secret}"},
                {"role": "tool", "content": (secret, "other")},
            ]
        },
        timeout_seconds=30.0,
        transport_retries=0,
    )

    raw_line = path.read_text(encoding="utf-8")
    assert secret not in raw_line
    row = json.loads(raw_line)
    messages = row["request_body"]["messages"]
    assert "***REDACTED***" in messages[0]["content"]
    assert messages[1]["content"][0] == "***REDACTED***"
    assert messages[1]["content"][1] == "other"


def test_debug_body_transport_write_failure_does_not_raise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A debug-only convenience file must never crash a production
    session (mirrors EventLog.append's JSONL-mirror degradation policy)."""
    inner = _FakeTransport(TransportResponse(status=200, body={}))
    # Point at a path whose parent cannot be created (a file, not a dir).
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("x")
    bad_path = blocker / "llm_bodies.jsonl"
    transport = DebugBodyTransport(inner, path=bad_path)

    result = transport.post(
        "https://api.example.com/v1/chat",
        headers={},
        json_body={"model": "m"},
        timeout_seconds=30.0,
        transport_retries=0,
    )

    assert result.status == 200  # call succeeded despite the write failure
