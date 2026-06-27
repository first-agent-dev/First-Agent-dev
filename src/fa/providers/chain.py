"""ChainConfig + ProviderChain + cooldown bookkeeping (ADR-9 §1..§4).

This is the dispatch core of T-2: a per-role ordered list of chain
entries, each pinning the *same* logical model identity on a different
provider platform. The chain walks entries in declared order; the
first entry not in cooldown is attempted; transient failure cools the
``(provider, slug)`` tuple and the walk continues to the next entry.

The dispatcher is intentionally *not* aware of observability hooks —
ADR-9 §4 lifecycle wiring lives in the inner-loop runtime. Instead,
:meth:`ProviderChain.request` returns the successful
:class:`fa.providers.base.ResponseInfo` *plus* the
:class:`ChainAttemptRecord` list collected along the way (one entry
per attempt including the successful tail) so the caller can build
the Tier-1 / Tier-2 rows. On chain exhaustion the dispatcher raises
:class:`fa.providers.errors.ProviderChainExhaustedError` carrying the
same record list.

References:
- ``knowledge/adr/ADR-9-llm-provider-client.md`` §1 (chain config),
  §2 (runtime semantics), §3 (cooldown semantics), §4 (observability
  contract — what the dispatcher must surface to the caller).
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from fa.providers.base import (
    Provider,
    RequestInfo,
    ResponseInfo,
)
from fa.providers.errors import (
    ConfigurationError,
    ProviderAuthError,
    ProviderChainExhaustedError,
    ProviderRequestShapeError,
    ProviderTransientError,
    ReservedProviderError,
)
from fa.providers.registry import PROVIDERS
from fa.providers.types import ChainAttemptRecord
from fa.roles import FamilyExtractionError, extract_family

DEFAULT_COOLDOWN_SECONDS = 90
DEFAULT_HTTPX_RETRIES = 1
DEFAULT_TIMEOUT_SECONDS = 15
# Waiver: allowlist for DETECTING local endpoints, not a bind address.
LOCALHOST_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0"})  # noqa: S104
RESERVED_PROVIDER_NAMES: frozenset[str] = frozenset(
    {"__internal__", "__metadata__", "__fallback_marker__"}
)


@dataclass(frozen=True)
class ChainEntry:
    """One row of a role's ``chain:`` config (ADR-9 §1).

    ``httpx_retries`` is a reserved transport-layer retry knob from ADR-9.
    The current production transport is :class:`fa.providers.transport.UrllibTransport`,
    which does not yet consume this field directly; the dispatcher keeps the
    field in the schema so a future transport retry implementation can use it
    without changing the ``models.yaml`` contract. The dispatcher itself never
    retries in-place per entry; it only sees the final outcome after the
    transport returns or raises.
    """

    provider: str
    slug: str
    base_url: str
    api_key_env: str
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS
    httpx_retries: int = DEFAULT_HTTPX_RETRIES
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    extra_headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ChainConfig:
    """Per-role chain config — produced by the ``~/.fa/models.yaml`` loader."""

    role: str
    model: str
    family: str
    chain: tuple[ChainEntry, ...]

    def validate(
        self,
        env: Mapping[str, str] | None = None,
        *,
        require_api_keys: bool = True,
    ) -> list[str]:
        """Enforce config-load invariants from ADR-9 §1.

        Returns a list of WARNING strings (best-effort heuristics that
        do not justify raising); raises :class:`ConfigurationError`
        (or :class:`ReservedProviderError`) for hard failures.

        ``require_api_keys`` (default True) enforces that each entry's
        ``api_key_env`` is present and non-empty in ``env``. In
        egress-proxy mode (ADR-12) the provider keys live in the proxy,
        not in the agent process, so the caller passes ``False`` and the
        presence check is skipped (the ``api_key_env`` name must still be
        declared, since the proxy uses it for routing).
        """

        warnings: list[str] = []
        environ = env if env is not None else os.environ
        if not self.chain:
            raise ConfigurationError(f"role {self.role!r}: empty chain — role not callable")
        for index, entry in enumerate(self.chain):
            label = f"role {self.role!r} chain[{index}]"
            if entry.provider in RESERVED_PROVIDER_NAMES:
                raise ReservedProviderError(
                    f"{label}: reserved provider name {entry.provider!r}; "
                    f"reserved: {sorted(RESERVED_PROVIDER_NAMES)}"
                )
            if entry.provider not in PROVIDERS:
                raise ConfigurationError(
                    f"{label}: unknown provider {entry.provider!r}; known: {sorted(PROVIDERS)}"
                )
            parsed = urlparse(entry.base_url)
            if parsed.scheme == "http":
                if parsed.hostname not in LOCALHOST_HOSTS:
                    raise ConfigurationError(
                        f"{label}: base_url {entry.base_url!r} must be https:// for non-localhost"
                    )
                warnings.append(f"{label}: http:// base_url permitted only for localhost gateway")
            elif parsed.scheme != "https":
                raise ConfigurationError(
                    f"{label}: base_url {entry.base_url!r} must be https:// or http://localhost"
                )
            if not entry.api_key_env:
                raise ConfigurationError(f"{label}: api_key_env must be non-empty")
            if require_api_keys and not environ.get(entry.api_key_env, "").strip():
                raise ConfigurationError(
                    f"{label}: api_key_env={entry.api_key_env} not set or empty "
                    f"in the configured secret store"
                )
            # Best-effort model-identity check (ADR-9 §1 + §7 reframed):
            # slug strings vary legitimately across providers, so we
            # WARN (not error) when extract_family(slug) disagrees
            # with the role's declared ``family:``. Slugs that defeat
            # the heuristic entirely surface as FamilyExtractionError
            # — also a warning, not a hard reject.
            try:
                inferred_family = extract_family(entry.slug)
            except FamilyExtractionError:
                warnings.append(
                    f"{label}: cannot infer family from slug {entry.slug!r}; verify chain entry"
                )
            else:
                if self.family and inferred_family != self.family:
                    warnings.append(
                        f"{label}: slug family {inferred_family!r} != role family {self.family!r}"
                    )
        # Best-effort adapter-homogeneity check (ADR-9 §1 + §2g):
        # mixed adapter categories (OpenAI-compat + Anthropic in one
        # chain) break the 400/422 fail-fast assumption that «the
        # next provider sends the same body». Warn, don't reject —
        # the natural shape (same model identity per chain) keeps
        # homogeneity by default.
        adapter_names = {PROVIDERS[entry.provider].adapter for entry in self.chain}
        if len(adapter_names) > 1:
            warnings.append(
                f"role {self.role!r}: chain mixes adapter categories {sorted(adapter_names)} "
                f"— fail-fast on 400/422 assumes a single adapter shape"
            )
        return warnings


@dataclass(frozen=True)
class CooldownRow:
    """In-memory cooldown ledger row (ADR-9 §3)."""

    provider: str
    slug: str
    started_at: float
    expires_at: float
    trigger_status: int
    trigger_error: str
    retry_after_hint_ms: int


class ProviderChain:
    """ADR-9 §2 ordered-fallback dispatcher with per-tuple cooldown ledger.

    ``provider_factory`` is the seam tests use: pass a callable that
    returns a fake :class:`Provider` per entry (one per chain row) so
    no real HTTP fires. Production callers pass a transport-backed
    factory (default ``build_provider`` from
    :mod:`fa.providers.registry`).

    ``cooldowns`` is the cross-role shared cooldown ledger per ADR-9
    §3 («The cooldown dict is process-global, keyed on
    ``(provider, slug)`` — NOT on ``(role, provider, slug)``. Two
    roles whose chains share the same ``(provider, slug)`` tuple
    share the cooldown state.»). Production callers pass one dict
    shared across all per-role :class:`ProviderChain` instances; tests
    omit it and get a fresh per-instance dict.
    """

    def __init__(
        self,
        config: ChainConfig,
        *,
        provider_factory: Callable[[ChainEntry], Provider],
        env: Mapping[str, str] | None = None,
        clock: Callable[[], float] = time.time,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
        cooldowns: dict[tuple[str, str], CooldownRow] | None = None,
    ) -> None:
        self._config = config
        self._provider_factory = provider_factory
        self._env: Mapping[str, str] = env if env is not None else os.environ
        self._clock = clock
        self._id_factory = id_factory
        self._cooldowns: dict[tuple[str, str], CooldownRow] = (
            cooldowns if cooldowns is not None else {}
        )

    @property
    def config(self) -> ChainConfig:
        return self._config

    @property
    def cooldowns(self) -> Mapping[tuple[str, str], CooldownRow]:
        return self._cooldowns

    def request(
        self,
        request: RequestInfo,
        *,
        logical_call_id: str | None = None,
    ) -> tuple[ResponseInfo, str, list[ChainAttemptRecord]]:
        """Dispatch ``request`` through the chain.

        Returns ``(response, logical_call_id, attempts)`` on success.
        Raises :class:`ProviderChainExhaustedError` (carrying the
        attempts list AND the ``logical_call_id``) on chain exhaustion;
        raises :class:`ProviderRequestShapeError` (carrying the
        ``logical_call_id``) immediately on 400 / 422 per ADR-9 §2g
        fail-fast rule. Per ADR-9 §4 Tier-2 schema both terminal
        rows MUST carry ``logical_call_id`` for correlation.

        ``logical_call_id`` may be passed by the caller (the inner-loop
        runtime that fires ``BEFORE_LLM_CALL`` per ADR-9 §2 step 2b
        already needs the id at hook-fire time, before this method
        returns); if omitted, the dispatcher generates one via
        ``id_factory``.
        """

        if logical_call_id is None:
            logical_call_id = self._id_factory()
        attempts: list[ChainAttemptRecord] = []
        for entry in self._config.chain:
            now = self._clock()
            key = (entry.provider, entry.slug)
            row = self._cooldowns.get(key)
            if row is not None and row.expires_at > now:
                continue
            api_key = self._env.get(entry.api_key_env, "")
            provider = self._provider_factory(entry)
            start = self._clock()
            try:
                response = provider.request(
                    request,
                    base_url=entry.base_url,
                    api_key=api_key,
                    timeout_seconds=float(entry.timeout_seconds),
                    extra_headers=entry.extra_headers,
                )
            except ProviderRequestShapeError as exc:
                elapsed_ms = int((self._clock() - start) * 1000)
                attempts.append(
                    ChainAttemptRecord(
                        provider=entry.provider,
                        slug=entry.slug,
                        status=exc.status,
                        ms=elapsed_ms,
                        error="request_shape",
                    )
                )
                # Stamp the call-scoped UUID so the Tier-2 row carries
                # the correlation id per ADR-9 §4.
                exc.logical_call_id = logical_call_id
                raise
            except ProviderAuthError as exc:
                elapsed_ms = int((self._clock() - start) * 1000)
                attempts.append(
                    ChainAttemptRecord(
                        provider=entry.provider,
                        slug=entry.slug,
                        status=exc.status,
                        ms=elapsed_ms,
                        error="auth_failed",
                    )
                )
                continue
            except ProviderTransientError as exc:
                elapsed_ms = int((self._clock() - start) * 1000)
                attempts.append(
                    ChainAttemptRecord(
                        provider=entry.provider,
                        slug=entry.slug,
                        status=exc.status,
                        ms=elapsed_ms,
                        error=exc.kind,
                    )
                )
                # Adaptive cooldown floor per ADR-9 §3:
                # ``max(now + cooldown_seconds, now + retry_after)``
                # — the configured floor is a lower bound; an explicit
                # ``Retry-After`` longer than the floor wins.
                now_after = self._clock()
                cooldown_until = max(
                    now_after + entry.cooldown_seconds,
                    now_after + exc.retry_after_seconds,
                )
                self._cooldowns[key] = CooldownRow(
                    provider=entry.provider,
                    slug=entry.slug,
                    started_at=start,
                    expires_at=cooldown_until,
                    trigger_status=exc.status,
                    trigger_error=exc.kind,
                    retry_after_hint_ms=int(exc.retry_after_seconds * 1000),
                )
                continue
            elapsed_ms = int((self._clock() - start) * 1000)
            attempts.append(
                ChainAttemptRecord(
                    provider=entry.provider,
                    slug=entry.slug,
                    status=200,
                    ms=elapsed_ms,
                    error=None,
                )
            )
            self._cooldowns.pop(key, None)
            return response, logical_call_id, attempts
        raise ProviderChainExhaustedError(
            f"role {self._config.role!r}: all {len(self._config.chain)} chain entries failed",
            attempts=list(attempts),
            logical_call_id=logical_call_id,
        )


def chain_from_mapping(role: str, raw: Mapping[str, Any]) -> ChainConfig:
    """Build a :class:`ChainConfig` from a YAML-loaded mapping.

    Helper used by the future ``~/.fa/models.yaml`` loader; landed
    here (rather than in the loader) so the chain shape stays
    co-located with its validator.
    """

    # ``raw.get("chain", ())`` returns the actual value when the YAML
    # contains ``chain: null`` (or bare ``chain:``) because the key
    # exists, so the subsequent ``for row in chain_rows`` would raise
    # ``TypeError: 'NoneType' object is not iterable``. ``or ()``
    # coalesces both missing-key and None-value to the empty tuple so
    # the validator surfaces the intended ``ConfigurationError("empty
    # chain — role not callable")`` instead of a confusing crash.
    chain_rows: Sequence[Mapping[str, Any]] = raw.get("chain") or ()
    # Required chain-entry fields must be non-null AND present per ADR-9 §1
    # chain-entry schema. ``str(row["provider"])`` would smuggle the literal
    # string ``"None"`` into the ``ChainEntry`` on YAML ``provider: null``,
    # and ``row["provider"]`` would raise ``KeyError`` (less helpful than a
    # named ``ConfigurationError``) on a missing key. The downstream
    # validator catches the smuggled ``"None"`` indirectly («unknown
    # provider 'None'»), but the user-facing message is clearer when the
    # loader surfaces the offending field by name. Same pattern as the
    # optional-field null coercion below.
    for index, row in enumerate(chain_rows):
        for field_name in ("provider", "slug", "base_url", "api_key_env"):
            if row.get(field_name) is None:
                raise ConfigurationError(
                    f"role {role!r} chain[{index}]: required field "
                    f"{field_name!r} is null or missing"
                )
    # ``row.get(key, DEFAULT)`` returns the actual value when the YAML
    # row contains ``key: null`` (because the key exists), so passing
    # ``None`` straight through to ``int(...)`` / ``dict(...)`` would
    # raise ``TypeError`` and break the entire loader on a single
    # null-valued optional field. For the numeric fields we use an
    # explicit ``is not None`` check (NOT ``or DEFAULT``) so that an
    # explicit zero — ``cooldown_seconds: 0`` to disable cooldown on
    # a localhost gateway, ``timeout_seconds: 0`` to opt out of the
    # transport timeout — is preserved instead of being silently
    # coalesced to the default (0 is falsy in Python). For
    # ``extra_headers`` ``or {}`` is safe because an empty dict and
    # a missing dict are observationally equivalent.
    entries = tuple(
        ChainEntry(
            provider=str(row["provider"]),
            slug=str(row["slug"]),
            base_url=str(row["base_url"]),
            api_key_env=str(row["api_key_env"]),
            cooldown_seconds=int(
                row["cooldown_seconds"]
                if row.get("cooldown_seconds") is not None
                else DEFAULT_COOLDOWN_SECONDS
            ),
            httpx_retries=int(
                row["httpx_retries"]
                if row.get("httpx_retries") is not None
                else DEFAULT_HTTPX_RETRIES
            ),
            timeout_seconds=int(
                row["timeout_seconds"]
                if row.get("timeout_seconds") is not None
                else DEFAULT_TIMEOUT_SECONDS
            ),
            extra_headers=dict(row.get("extra_headers") or {}),
        )
        for row in chain_rows
    )
    # ``raw.get(key, "")`` returns the actual value when the YAML row
    # contains ``key: null`` (because the key exists), so ``str(None)``
    # would smuggle the literal string ``"None"`` into the config and
    # the validator would emit a confusing «slug family X != role
    # family 'None'» warning. ``raw.get(key) or ""`` coalesces both
    # missing-key and None-value to the empty string.
    #
    # ``family`` is additionally normalised via ``.strip().lower()``
    # so every downstream consumer of ``ChainConfig.family`` —
    # ``check_eval_disjoint`` (ADR-2 §Amendment 2026-05-20 rule 1,
    # case-sensitive ``==``), the validator's slug-family mismatch
    # warning (compares against ``extract_family(slug)`` which is
    # already lowercased), cooldown logging, Tier-2 telemetry — sees
    # a canonical form. Without this normalisation a YAML
    # ``family: "DeepSeek"`` (mixed case) would bypass the
    # eval-vs-actor disjoint check via a casing typo (e.g. planner
    # ``"DeepSeek"`` vs eval ``"deepseek"``), silently violating the
    # safety-critical rule from ADR-2. The fix lives here (NOT only
    # at the loader's call site) because ``ChainConfig.family``
    # surfaces to many consumers; a loader-only guard would leak
    # mixed-case strings into the validator + telemetry surfaces.
    # ``.strip().lower()`` is used rather than routing through
    # ``fa.roles.extract_family`` because the latter raises
    # ``FamilyExtractionError`` for any override not in
    # :data:`KNOWN_FAMILIES`, which would reject custom /
    # not-yet-known family names that are legal in a v0.1 config.
    return ChainConfig(
        role=role,
        model=str(raw.get("model") or ""),
        family=str(raw.get("family") or "").strip().lower(),
        chain=entries,
    )
