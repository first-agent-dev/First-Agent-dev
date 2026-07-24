"""Tier-3 opt-in raw request/response body capture (ADR-9 §4).

:class:`DebugBodyTransport` wraps any :class:`~fa.providers.base.Transport`
implementation and, only when explicitly enabled, mirrors every
``{request_body, response_body}`` pair to a separate ``llm_bodies.jsonl``
file — correlated back to the Tier-1 ``llm_call`` row (see
:mod:`fa.inner_loop.coder_loop`) via ``logical_call_id``.

Disabled by default (opt-in via ``FA_DEBUG_LLM_BODIES=1``) per ADR-9 §4:
bodies are 5-50 KB per call, may carry UC5-sensitive context, and 99% of
sessions never need them. When disabled, :func:`wrap_transport_for_debug_bodies`
returns the original transport unchanged — zero overhead, zero behavior
change, in the default path.

Design note — why a contextvar and not a constructor argument threading
through every adapter: adapters (:mod:`fa.providers.openai_compat`,
:mod:`fa.providers.mistral`, :mod:`fa.providers.anthropic`, ...) implement
the thin, provider-specific translation layer per ADR-9 §5 and must stay
unaware of observability plumbing. The chain dispatcher
(:mod:`fa.providers.chain`) is the one caller that already knows
``logical_call_id`` / the chain entry's ``provider`` and ``model`` /  the
attempt index — it sets :func:`debug_body_context` immediately before
calling into the adapter and the context flows down through the adapter's
``transport.post()`` call without changing any adapter or ``Transport``
Protocol signature.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

from fa.providers.base import Transport, TransportResponse

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fa.observability.redaction import SecretRedactor

logger = logging.getLogger(__name__)

__all__ = [
    "DebugBodyTransport",
    "debug_body_context",
    "is_debug_bodies_enabled",
    "wrap_transport_for_debug_bodies",
]

_ENV_VAR = "FA_DEBUG_LLM_BODIES"


@dataclass(frozen=True)
class _DebugBodyContext:
    logical_call_id: str
    provider: str
    slug: str
    attempt_index: int


_CONTEXT: ContextVar[_DebugBodyContext | None] = ContextVar("_fa_debug_body_context", default=None)


@contextmanager
def debug_body_context(
    *,
    logical_call_id: str,
    provider: str,
    slug: str,
    attempt_index: int,
) -> Iterator[None]:
    """Bind the current chain-entry attempt's correlation fields.

    Set by :meth:`fa.providers.chain.ProviderChain.request` around each
    per-entry ``provider.request(...)`` call; read by
    :class:`DebugBodyTransport` inside the resulting ``transport.post()``
    call. A no-op when Tier-3 capture is disabled (the context is still
    set, but :func:`wrap_transport_for_debug_bodies` never installs the
    wrapper that would read it).
    """
    token = _CONTEXT.set(_DebugBodyContext(logical_call_id, provider, slug, attempt_index))
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def _now_iso_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_debug_bodies_enabled(env: Mapping[str, str] | None = None) -> bool:
    """``True`` iff ``FA_DEBUG_LLM_BODIES=1`` (exact match; any other value is off)."""
    source: Mapping[str, str] = env if env is not None else os.environ
    return source.get(_ENV_VAR, "").strip() == "1"


class DebugBodyTransport(Transport):
    """Transparent :class:`Transport` decorator — mirrors bodies, never mutates them.

    Forwards every ``post()`` call to ``inner`` unchanged (same arguments,
    same return value, same raised exceptions) and, as a side effect,
    appends one JSON row per call to ``path``. A write failure is logged
    and swallowed — never raised — matching
    :meth:`fa.inner_loop.state.EventLog.append`'s own best-effort JSONL
    mirror policy; a debug-only convenience file must never crash a
    production session.
    """

    name = "debug_body_transport"

    def __init__(
        self,
        inner: Transport,
        *,
        path: Path,
        redactor: SecretRedactor | None = None,
    ) -> None:
        self._inner = inner
        self._path = path
        self._redactor = redactor
        self._lock = threading.Lock()

    @override
    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
        transport_retries: int,
    ) -> TransportResponse:
        response = self._inner.post(
            url,
            headers=headers,
            json_body=json_body,
            timeout_seconds=timeout_seconds,
            transport_retries=transport_retries,
        )
        self._write(json_body, response)
        return response

    def _write(self, request_body: Mapping[str, Any], response: TransportResponse) -> None:
        ctx = _CONTEXT.get()
        row: dict[str, Any] = {
            "kind": "llm_body",
            "ts": _now_iso_z(),
            "logical_call_id": ctx.logical_call_id if ctx else "",
            "attempt_index": ctx.attempt_index if ctx is not None else -1,
            "provider": ctx.provider if ctx else "",
            "slug": ctx.slug if ctx else "",
            "request_body": dict(request_body),
            "response_body": dict(response.body),
        }
        if self._redactor is not None:
            row = self._redact(row)
        try:
            with self._lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False, default=str, sort_keys=True) + "\n")
        except OSError as exc:
            logger.warning("Failed to write llm_bodies.jsonl row: %s", exc)

    def _redact(self, value: object) -> Any:
        assert self._redactor is not None  # noqa: S101 - guarded by caller
        if isinstance(value, str):
            return self._redactor.redact(value)
        if isinstance(value, Mapping):
            return {k: self._redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._redact(v) for v in value]
        if isinstance(value, tuple):
            return tuple(self._redact(v) for v in value)
        return value


def wrap_transport_for_debug_bodies(
    transport: Transport,
    *,
    run_log_dir: Path,
    redactor: SecretRedactor | None = None,
    env: Mapping[str, str] | None = None,
) -> Transport:
    """Return ``transport`` unchanged, or wrapped in :class:`DebugBodyTransport`.

    ``run_log_dir`` is the per-run session-log directory
    (``~/.fa/session-log/<run_id>/``); the sibling file
    ``llm_bodies.jsonl`` is created there, matching ``events.jsonl``'s
    location so both rows for the same run live side by side.
    """
    if not is_debug_bodies_enabled(env):
        return transport
    return DebugBodyTransport(transport, path=run_log_dir / "llm_bodies.jsonl", redactor=redactor)
