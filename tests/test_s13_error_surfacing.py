"""S13.4a — I-51: surface the provider's error on request_shape.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md``
§S13.4a.

**Why.** When a provider rejects a request, the console used to print:
``⏳ retry in 0s (unknown/0)`` — `unknown`/`0` were hardcoded placeholders
(``coder_loop.py``) and the real reason sat in the event's ``reason`` key, which
``_handle_api_retry`` (``output.py``) never rendered. The provider's message
(e.g. ``code=3230 ... got assistant``) was therefore invisible live, which is
exactly what made I-50 hard to diagnose. This slice surfaces it.

**Mechanism (verified, three sites):**
1. ``ProviderRequestShapeError`` gained a ``provider`` field (``errors.py``);
2. ``chain.py`` stamps ``exc.provider = entry.provider`` on re-raise (both the
   local ``MessageRulesError`` path and the remote ``ProviderRequestShapeError``
   path) — the dispatcher knows the chain entry in scope;
3. ``coder_loop.py`` emits ``exc.provider``/``exc.status`` instead of
   ``"unknown"``/``0``, and ``output.py:_handle_api_retry`` renders ``reason``.

**Tests labelled per tests-writing skill:**
- **C0** — the error class carries a `provider` field; the renderer prints reason.
- **C1 (producer)** — ``drive_session`` with a rejecting provider emits an
  ``api_retry`` OutputEvent carrying the real provider/status and a reason that
  contains the provider's message (kill-check: remove the emit fields → fail).
- **C1** — ``ProviderChain`` stamps ``provider`` on both the local conformance
  path and the remote request_shape path.

**Kill-check:** K5 — revert either half (the stamp or the render) → the rendered
line / the event loses the provider message.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.state import EventLog, SessionState
from fa.output import ConsoleRenderer, EventBus, OutputEvent
from fa.providers.base import RequestInfo, ResponseInfo
from fa.providers.chain import ChainConfig, ChainEntry, ProviderChain
from fa.providers.errors import ProviderRequestShapeError
from fa.providers.message_rules import MessageRulesError

# --- C0: the error class carries a provider field ----------------------------


def test_request_shape_error_carries_provider_field() -> None:
    exc = ProviderRequestShapeError("bad", provider="mistral")
    assert exc.provider == "mistral"
    assert exc.status == 400
    # default is None (adapter does not know the chain provider)
    assert ProviderRequestShapeError("bad").provider is None


# --- C0: the renderer prints reason when present -----------------------------


def test_renderer_prints_reason() -> None:
    renderer = ConsoleRenderer(no_color=True)
    import io
    import sys

    buffer = io.StringIO()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sys, "stderr", buffer)
        renderer.on_event(
            OutputEvent(
                type="api_retry",
                data={
                    "retry_after_s": 0,
                    "provider": "mistral",
                    "status": 400,
                    "reason": "request_shape_error: code=3230 ... got assistant",
                },
            )
        )
    out = buffer.getvalue()
    assert "mistral" in out
    assert "400" in out
    assert "code=3230" in out  # the provider's message is rendered
    assert "unknown" not in out


def test_renderer_no_reason_no_suffix() -> None:
    renderer = ConsoleRenderer(no_color=True)
    import io
    import sys

    buffer = io.StringIO()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sys, "stderr", buffer)
        renderer.on_event(
            OutputEvent(
                type="api_retry",
                data={"retry_after_s": 1, "provider": "openrouter", "status": 429},
            )
        )
    assert "openrouter" in buffer.getvalue()
    assert "—" not in buffer.getvalue()  # no reason → no suffix


# --- C1: chain stamps provider on both paths ---------------------------------


class _RaisingProvider:
    """Provider that raises on request. Records whether it was invoked."""

    name = "fake"
    invoked = False
    exception: Exception

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
        del request, base_url, api_key, timeout_seconds, transport_retries, extra_headers
        self.__class__.invoked = True
        raise self.__class__.exception


def _chain_for(provider: str) -> ProviderChain:
    entry = ChainEntry(
        provider=provider,
        model="m",
        base_url="https://example.invalid/v1",
        api_key_env="K",
        cooldown_seconds=0,
    )
    config = ChainConfig(role="coder", name="m", family="", chain=(entry,))

    def _factory(_entry: ChainEntry) -> Any:
        return _RaisingProvider()

    return ProviderChain(config, provider_factory=_factory, env={"K": "k"})


def test_chain_stamps_provider_on_remote_request_shape() -> None:
    """C1 — remote 400/422 exception gets its provider stamped by the chain."""
    _RaisingProvider.invoked = False
    _RaisingProvider.exception = ProviderRequestShapeError("bad body", status=400)
    chain = _chain_for("mistral")
    req = RequestInfo(
        model_slug="m",
        messages=({"role": "user", "content": "t"}, {"role": "assistant", "content": "x"}),
    )
    with pytest.raises(ProviderRequestShapeError) as info:
        chain.request(req)
    assert info.value.provider == "mistral"
    assert info.value.status == 400


def test_chain_stamps_provider_on_local_message_rules() -> None:
    """C1 — a local conformance violation carries the entry's provider."""
    chain = _chain_for("mistral")
    req = RequestInfo(
        model_slug="m",
        messages=({"role": "user", "content": "t"}, {"role": "assistant", "content": "x"}),
    )
    with pytest.raises(MessageRulesError) as info:
        chain.request(req)
    assert info.value.provider == "mistral"


# --- C1 producer: coder_loop emits real provider/status -----------------------


class _Capture:
    def __init__(self) -> None:
        self.events: list[OutputEvent] = []

    def on_event(self, event: OutputEvent) -> None:
        self.events.append(event)


def _make_session(tmp_path: Path) -> tuple[SessionState, EventBus, _Capture]:
    log = EventLog(tmp_path / "events.jsonl", run_id="s13-4a")
    state = SessionState(workspace_root=tmp_path, run_id="s13-4a", log=log)
    bus = EventBus()
    capture = _Capture()
    bus.add(capture)
    return state, bus, capture


def test_drive_session_emits_real_provider_and_status(tmp_path: Path) -> None:
    """C1 producer — the api_retry event carries the real provider/status + reason.

    Previously this emitted ``provider="unknown"``, ``status=0``, and the reason
    was never rendered. Now it must carry ``mistral``/``400`` and a reason that
    contains the provider's message.
    """
    _RaisingProvider.invoked = False
    _RaisingProvider.exception = ProviderRequestShapeError(
        "request_shape_error: status=400 body={'message': 'code=3230 ... got assistant'}",
        status=400,
    )
    state, bus, capture = _make_session(tmp_path)

    outcome = drive_session(
        "boom",
        provider_chain=_chain_for("mistral"),
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
        output=bus,
    )

    assert outcome.exit_code == 2
    assert outcome.stop_reason == "request_shape"
    retries = [e for e in capture.events if e.type == "api_retry"]
    assert len(retries) >= 1, f"expected api_retry; got {[e.type for e in capture.events]}"
    data = retries[-1].data
    assert data["provider"] == "mistral", f"expected real provider, got {data['provider']!r}"
    assert data["status"] == 400
    assert "code=3230" in str(data["reason"])
    assert data["provider"] != "unknown"
    assert data["status"] != 0
