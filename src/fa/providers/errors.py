"""Typed errors raised by the T-2 provider chain (ADR-9 §1, §2, §5).

Six error classes split along the two axes ADR-9 §2 cares about:

* **Config-load time vs runtime.** :class:`ConfigurationError` (and
  its :class:`ReservedProviderError` subclass) fire at
  :meth:`fa.providers.chain.ChainConfig.validate` time so the user
  sees a missing ``api_key_env`` or a reserved-namespace collision
  loudly at startup, not as a confusing 401 from a provider on the
  first real call.
* **Continue-chain vs fail-fast at runtime.** :class:`ProviderTransientError`
  and :class:`ProviderAuthError` are *continue-chain* signals — the next
  entry might still succeed because the failure is local to one
  provider (rate-limit window, wrong key on one platform).
  :class:`ProviderRequestShapeError` is a *fail-fast* signal — FA built a
  bad body and every chain entry would reject it the same way, so
  continuing would waste budget on a deterministic client bug.
  :class:`ProviderChainExhaustedError` is the terminal exhaustion
  signal carrying the per-attempt record list for the
  ``llm_chain_exhausted`` observability row (ADR-9 §4 Tier-2).

Runtime errors carry structured attributes (``status`` /
``retry_after_seconds`` / ``kind``) so the dispatcher in
:mod:`fa.providers.chain` does not have to parse error strings to
build attempt records or compute adaptive cooldowns.

References:
- ``knowledge/adr/ADR-9-llm-provider-client.md`` §1 (validation),
  §2 (runtime semantics), §5 (errors.py file layout).
"""

from __future__ import annotations


class ConfigurationError(Exception):
    """Chain config rejected at load time (ADR-9 §1)."""


class ReservedProviderError(ConfigurationError):
    """Chain entry uses a reserved-namespace ``provider`` name (ADR-9 §6)."""


class ProviderTransientError(Exception):
    """Transient single-provider failure — continue chain + cool down (ADR-9 §2e).

    Covers HTTP status ∈ {429, 500..504} and network errors.
    ``kind`` is one of ``"rate_limited"`` / ``"service_unavailable"``
    / ``"timeout"`` for the observability row;
    ``retry_after_seconds`` is the parsed RFC 9110 hint (``0.0`` if
    absent) so :class:`fa.providers.chain.ProviderChain` can compose
    the adaptive cooldown floor per ADR-9 §3.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int = 0,
        kind: str = "service_unavailable",
        retry_after_seconds: float = 0.0,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.kind = kind
        self.retry_after_seconds = retry_after_seconds


class ProviderAuthError(Exception):
    """401 / 403 on one chain entry — continue chain WITHOUT cooldown (ADR-9 §2f)."""

    def __init__(self, message: str, *, status: int = 401) -> None:
        super().__init__(message)
        self.status = status


class ProviderRequestShapeError(Exception):
    """400 / 422 fail-fast (ADR-9 §2g) — FA-side request construction bug."""

    def __init__(self, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class ProviderChainExhaustedError(Exception):
    """All chain entries failed (ADR-9 §2 step 3).

    Carries the full per-attempt record list so the Tier-2
    ``llm_chain_exhausted`` observability row can be emitted by the
    inner-loop runtime; :class:`fa.inner_loop.recovery.FailureClassifierObserver`
    routes the role retry decision off the ``terminal`` field.
    """

    def __init__(self, message: str, *, attempts: list[object]) -> None:
        super().__init__(message)
        self.attempts = attempts
