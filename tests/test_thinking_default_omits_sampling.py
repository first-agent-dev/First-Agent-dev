"""Thinking-default kill-checks: FA must NOT force temperature/top_p on the wire.

S13.x — the default request shape is the thinking-model shape: reasoning models
lock temperature/top_p (they are rejected 400 or silently ignored), so FA omits
both by default and a role opts into explicit sampling via ``sampling:`` in
models.yaml (ADR-9 §Amendment 2026-07-23). The adapter already omits the fields
when they are ``None`` (openai_compat.py); these tests pin that the *call sites*
stop forcing them.

Tests are labelled per tests-writing skill:
- C0p: default-value properties (no forced default anywhere).
- C1: composition against the real chain + real adapter wire body.

**Kill-checks (must fail if the design regresses):**
- `drive_session` default request carries ``temperature is None`` → removing the
  ``None`` default in coder_loop fails.
- the real OpenAI-compat adapter body omits ``temperature``/``top_p`` when the
  request has them ``None`` → a regression forcing a value fails.
- a role that sets ``sampling.temperature/top_p`` still gets them on the wire
  (the opt-in escape hatch is preserved).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry, SandboxHook
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.tools import build_baseline_registry
from fa.providers.base import RequestInfo, ResponseInfo, TransportResponse
from fa.providers.chain import ChainConfig, ChainEntry, ProviderChain
from fa.providers.errors import ProviderTransientError
from fa.providers.openai_compat import OpenAICompatProvider

# --- helpers (reuse the test_coder_loop harness idiom) ----------------------


@dataclass
class _FakeProvider:
    script: list[ResponseInfo | Exception]
    calls: list[RequestInfo] = field(default_factory=list)
    name: str = "fake"

    def request(
        self,
        request: RequestInfo,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        transport_retries: int,
        extra_headers: Mapping[str, str],
    ) -> ResponseInfo:
        del base_url, api_key, timeout_seconds, transport_retries, extra_headers
        self.calls.append(request)
        if not self.script:
            raise ProviderTransientError("script exhausted", status=503, kind="service_unavailable")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _make_chain(provider: _FakeProvider) -> ProviderChain:
    entry = ChainEntry(
        provider="openrouter",
        model="test/model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_KEY",
        cooldown_seconds=300,
    )
    config = ChainConfig(role="coder", name="test-model", family="", chain=(entry,))
    return ProviderChain(
        config,
        provider_factory=lambda _e: provider,
        env={"TEST_KEY": "k"},
    )


def _make_state(tmp_path: Path) -> SessionState:
    log = EventLog(tmp_path / "events.jsonl", run_id="t")
    return SessionState(workspace_root=tmp_path, run_id="t", log=log)


def _resp(text: str = "done") -> ResponseInfo:
    return ResponseInfo(
        text=text,
        finish_reason="stop",
        in_tokens=10,
        out_tokens=5,
    )


class _FakeTransport:
    """Captures the exact JSON body the adapter would send to the wire."""

    def __init__(self) -> None:
        self.sent_bodies: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
        transport_retries: int,
    ) -> TransportResponse:
        self.sent_bodies.append(dict(json_body))
        return TransportResponse(
            status=200,
            body={"choices": [{"message": {"role": "assistant", "content": "ok"}}], "usage": {}},
        )


# --- C0p: drive_session default carries no forced temperature -----------------


def test_drive_session_default_request_has_temperature_none(tmp_path: Path) -> None:
    """C0p/C1 — a default ``drive_session`` builds a request with ``temperature is
    None`` (thinking-model default), not a forced 0.0/0.2."""
    provider = _FakeProvider([_resp()])
    chain = _make_chain(provider)
    registry = build_baseline_registry(workspace_root=tmp_path)
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = _make_state(tmp_path)

    drive_session(
        "do nothing",
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
    )

    assert len(provider.calls) == 1
    request = provider.calls[0]
    assert request.temperature is None
    assert request.top_p is None


# --- C1: the real adapter omits temperature/top_p from the wire body ----------


def test_openai_compat_wire_body_omits_temperature_and_top_p_when_none() -> None:
    """C1 — when a request has temperature/top_p None, the real OpenAI-compat
    adapter does NOT put them in the wire body (kill-check for the forcing)."""
    transport = _FakeTransport()
    provider = OpenAICompatProvider(transport=transport)
    provider.request(
        RequestInfo(model_slug="m", messages=({"role": "user", "content": "hi"},)),
        base_url="https://example.invalid/v1",
        api_key="k",
        timeout_seconds=10.0,
        transport_retries=1,
        extra_headers={},
    )
    body = transport.sent_bodies[-1]
    assert "temperature" not in body
    assert "top_p" not in body


def test_openai_compat_wire_body_includes_sampling_when_explicit() -> None:
    """C1 — the opt-in escape hatch is preserved: a role that sets
    sampling.temperature/top_p still gets them on the wire."""
    transport = _FakeTransport()
    provider = OpenAICompatProvider(transport=transport)
    provider.request(
        RequestInfo(
            model_slug="m",
            messages=({"role": "user", "content": "hi"},),
            temperature=0.2,
            top_p=0.9,
        ),
        base_url="https://example.invalid/v1",
        api_key="k",
        timeout_seconds=10.0,
        transport_retries=1,
        extra_headers={},
    )
    body = transport.sent_bodies[-1]
    assert body.get("temperature") == 0.2
    assert body.get("top_p") == 0.9
