"""ChainConfig + ProviderChain + cooldown bookkeeping (ADR-9 §1..§4, §Amendment 2026-07-23).

This is the dispatch core of T-2: a per-role ordered list of chain
entries, each pinning the *same* logical model identity on a different
provider platform. The chain walks entries in declared order; the
first entry not in cooldown is attempted; transient failure cools the
``(provider, model)`` tuple and the walk continues to the next entry.

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
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import urlparse

from fa.providers.base import (
    Provider,
    RequestInfo,
    ResponseInfo,
)
from fa.providers.debug_bodies import debug_body_context
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

# Lockout period after a provider exhausts retries
DEFAULT_COOLDOWN_SECONDS = 15
# Number of retry attempts on network/timeout errors
DEFAULT_TRANSPORT_RETRIES = 2
# Waiting time for HTTP response
DEFAULT_TIMEOUT_SECONDS = 300
# Waiver: allowlist for DETECTING local endpoints, not a bind address.
LOCALHOST_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0"})  # noqa: S104
RESERVED_PROVIDER_NAMES: frozenset[str] = frozenset({"__internal__", "__metadata__", "__fallback_marker__"})


def _validate_context_budget_settings(config: ChainConfig) -> None:
    if config.context_limit <= 0:
        raise ConfigurationError(
            f"role {config.role!r}: context_limit must be a positive integer, "
            f"got {config.context_limit}. Fix: set a positive context_limit under "
            f"the '{config.role}' role in ~/.fa/models.yaml."
        )
    if config.compaction_threshold is None:
        return
    if config.compaction_threshold <= 0:
        raise ConfigurationError(
            f"role {config.role!r}: compaction_threshold must be a positive integer, "
            f"got {config.compaction_threshold}. Fix: set a positive compaction_threshold "
            f"or remove it (null = disabled) under the '{config.role}' role in ~/.fa/models.yaml."
        )
    if config.compaction_threshold > config.context_limit:
        raise ConfigurationError(
            f"role {config.role!r}: compaction_threshold ({config.compaction_threshold}) "
            f"cannot exceed context_limit ({config.context_limit}). "
            f"Fix: reduce compaction_threshold or increase context_limit in ~/.fa/models.yaml."
        )


@dataclass(frozen=True)
class ChainEntry:
    """One row of a role's ``chain:`` config (ADR-9 §1, §Amendment 2026-07-23).

    ``transport_retries`` is the per-entry low-level transport retry budget.
    It is consumed by the production transport before the provider chain sees
    the final outcome. This knob is intentionally narrower than the chain-level
    fallback/cooldown logic: it applies only to transport/network failures, not
    to HTTP transient status responses such as 429/5xx, which remain owned by
    :class:`ProviderChain`.

    ``model`` is THE literal string sent as ``"model"`` in this entry's HTTP
    request body — renamed from the historical ``slug`` field name (which
    every real provider calls ``model`` in its own API; see ADR-9 §Amendment
    2026-07-23 for the rationale and the accompanying dispatch-loop fix that
    makes this field actually reach the request, where the old ``slug`` field
    never did).

    ``provider_params`` are provider-specific request-body fields sent ONLY
    to this entry (e.g. Mistral's ``reasoning_effort``, ``safe_prompt``) —
    renamed and re-scoped from the historical role-level ``ChainConfig.extras``,
    which was broadcast unconditionally to every chain entry regardless of
    whether that provider understood the field.
    """

    provider: str
    model: str
    base_url: str
    api_key_env: str
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS
    transport_retries: int = DEFAULT_TRANSPORT_RETRIES
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    extra_headers: Mapping[str, str] = field(default_factory=dict)
    provider_params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChainConfig:
    """Per-role chain config — produced by the ``~/.fa/models.yaml`` loader.

    ``name`` is a display/logging/``extract_family()``-input label ONLY —
    it is NEVER forwarded to any provider's request body (renamed from the
    historical ``model`` field name, which collided with the per-entry wire
    value; see ADR-9 §Amendment 2026-07-23).

    ``sampling`` carries role-level default request parameters
    (``temperature``, ``max_tokens``, ``top_p``) sent identically to every
    chain entry — the common denominator every registered adapter already
    understands. Per-call-site explicit overrides (e.g. ``fa probe``'s
    ``temperature=0.0, max_tokens=1``) take precedence over these defaults.
    """

    role: str
    name: str
    family: str
    chain: tuple[ChainEntry, ...]
    context_limit: int = 150000
    compaction_threshold: int | None = None
    sampling: Mapping[str, Any] = field(default_factory=dict)

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
            raise ConfigurationError(
                f"role {self.role!r}: empty chain — no providers configured for this role. "
                f"Fix: add at least one chain entry under the 'chain:' key for role "
                f"'{self.role}' in ~/.fa/models.yaml."
            )
        _validate_context_budget_settings(self)
        for index, entry in enumerate(self.chain):
            label = f"role {self.role!r} chain[{index}]"
            if entry.provider in RESERVED_PROVIDER_NAMES:
                raise ReservedProviderError(
                    f"{label}: reserved provider name {entry.provider!r}; reserved: {sorted(RESERVED_PROVIDER_NAMES)}"
                )
            if entry.provider not in PROVIDERS:
                raise ConfigurationError(
                    f"{label}: unknown provider {entry.provider!r}; known: {sorted(PROVIDERS)}. "
                    f"Fix: check the 'provider' field in ~/.fa/models.yaml for role '{self.role}'."
                )
            parsed = urlparse(entry.base_url)
            if parsed.scheme == "http":
                if parsed.hostname not in LOCALHOST_HOSTS:
                    raise ConfigurationError(
                        f"{label}: base_url {entry.base_url!r} must be https:// for non-localhost. "
                        f"Fix: change the base_url scheme to https:// in ~/.fa/models.yaml, "
                        f"or use an http://localhost gateway."
                    )
                warnings.append(f"{label}: http:// base_url permitted only for localhost gateway")
            elif parsed.scheme != "https":
                raise ConfigurationError(
                    f"{label}: base_url {entry.base_url!r} must be https:// or http://localhost. "
                    f"Fix: set a valid base_url under the 'chain:' entry in ~/.fa/models.yaml."
                )
            if not entry.api_key_env:
                raise ConfigurationError(
                    f"{label}: api_key_env must be non-empty. "
                    f"Fix: set the 'api_key_env' field to an environment variable name "
                    f"containing your API key in ~/.fa/models.yaml."
                )
            if require_api_keys and not environ.get(entry.api_key_env, "").strip():
                raise ConfigurationError(
                    f"{label}: api_key_env={entry.api_key_env!r} not set or empty in the "
                    f"configured secret store. Fix: set the {entry.api_key_env!r} environment "
                    f"variable to your API key, or update 'api_key_env' in ~/.fa/models.yaml "
                    f"to reference a different variable."
                )
            # Best-effort model-identity check (ADR-9 §1 + §7 reframed):
            # entry.model strings vary legitimately across providers, so we
            # WARN (not error) when extract_family(entry.model) disagrees
            # with the role's declared ``family:``. Model strings that defeat
            # the heuristic entirely surface as FamilyExtractionError
            # — also a warning, not a hard reject.
            try:
                inferred_family = extract_family(entry.model)
            except FamilyExtractionError:
                warnings.append(f"{label}: cannot infer family from model {entry.model!r}; verify chain entry")
            else:
                if self.family and inferred_family != self.family:
                    warnings.append(f"{label}: entry family {inferred_family!r} != role family {self.family!r}")
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
        self._cooldowns: dict[tuple[str, str], CooldownRow] = cooldowns if cooldowns is not None else {}

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
        # Role-level `sampling:` (ADR-9 §Amendment 2026-07-23) supplies
        # DEFAULTS for fields the caller did not set explicitly. A caller
        # that passes an explicit value (e.g. `fa probe`'s
        # `temperature=0.0, max_tokens=1`) always wins — matching the
        # existing chain-extras-over-prompt-composer-extras precedence
        # rule this ADR already documents for provider_params/extras.
        sampling = self._config.sampling
        effective_temperature = request.temperature if request.temperature is not None else sampling.get("temperature")
        effective_max_tokens = request.max_tokens if request.max_tokens is not None else sampling.get("max_tokens")
        effective_top_p = request.top_p if request.top_p is not None else sampling.get("top_p")
        attempts: list[ChainAttemptRecord] = []
        for attempt_index, entry in enumerate(self._config.chain):
            now = self._clock()
            key = (entry.provider, entry.model)
            row = self._cooldowns.get(key)
            if row is not None and row.expires_at > now:
                continue
            api_key = self._env.get(entry.api_key_env, "")
            provider = self._provider_factory(entry)
            start = self._clock()
            # Per-entry request (ADR-9 §Amendment 2026-07-23): each chain
            # entry gets ITS OWN `model_slug` (entry.model — the literal
            # string this provider expects, which legitimately differs
            # across platforms for "the same" logical model) and ITS OWN
            # `provider_params` merged into `extras` — never a sibling
            # entry's provider-specific fields. Role-level `sampling`
            # defaults apply uniformly (every adapter already understands
            # temperature/max_tokens/top_p).
            entry_extras: dict[str, Any] = dict(request.extras)
            entry_extras.update(entry.provider_params)
            entry_request = replace(
                request,
                model_slug=entry.model,
                temperature=effective_temperature,
                max_tokens=effective_max_tokens,
                top_p=effective_top_p,
                extras=entry_extras,
            )
            try:
                with debug_body_context(
                    logical_call_id=logical_call_id,
                    provider=entry.provider,
                    slug=entry.model,
                    attempt_index=attempt_index,
                ):
                    response = provider.request(
                        entry_request,
                        base_url=entry.base_url,
                        api_key=api_key,
                        timeout_seconds=float(entry.timeout_seconds),
                        transport_retries=int(entry.transport_retries),
                        extra_headers=entry.extra_headers,
                    )
            except ProviderRequestShapeError as exc:
                elapsed_ms = int((self._clock() - start) * 1000)
                attempts.append(
                    ChainAttemptRecord(
                        provider=entry.provider,
                        slug=entry.model,
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
                        slug=entry.model,
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
                        slug=entry.model,
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
                    slug=entry.model,
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
                    slug=entry.model,
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

    Helper used by the ``~/.fa/models.yaml`` loader; landed here (rather
    than in the loader) so the chain shape stays co-located with its
    validator.

    ADR-9 §Amendment 2026-07-23 hard cutover: the historical field names
    (role-level ``model:``, chain-entry ``slug:``, role-level ``extras:``)
    are REJECTED with an explicit migration hint, not silently accepted —
    see the amendment for the rationale (the old names were both confusing
    and, for ``slug``/``extras``, connected to nothing / broadcast
    incorrectly).
    """

    if "model" in raw:
        raise ConfigurationError(
            f"role {role!r}: 'model:' at role level is the OLD field name (ADR-9 §Amendment "
            f"2026-07-23). Fix: rename it to 'name:' in ~/.fa/models.yaml — the role-level "
            f"field is a display/logging label only and is NEVER sent to any provider; the "
            f'string actually sent as "model" in each HTTP request now comes from each '
            f"chain entry's own 'model:' field (was 'slug:')."
        )
    if "extras" in raw:
        raise ConfigurationError(
            f"role {role!r}: 'extras:' at role level is the OLD field name (ADR-9 §Amendment "
            f"2026-07-23). Fix: move these fields into a 'provider_params:' block under EACH "
            f"chain entry that should receive them in ~/.fa/models.yaml — role-level 'extras:' "
            f"used to be broadcast to every chain entry regardless of whether that provider "
            f"understood the field; 'provider_params:' is scoped to a single entry."
        )

    # ``raw.get("chain", ())`` returns the actual value when the YAML
    # contains ``chain: null`` (or bare ``chain:``) because the key
    # exists, so the subsequent ``for row in chain_rows`` would raise
    # ``TypeError: 'NoneType' object is not iterable``. ``or ()``
    # coalesces both missing-key and None-value to the empty tuple so
    # the validator surfaces the intended ``ConfigurationError("empty
    # chain — role not callable")`` instead of a confusing crash.
    chain_rows: Sequence[Mapping[str, Any]] = raw.get("chain") or ()
    # Required chain-entry fields must be non-null AND present per ADR-9 §1
    # chain-entry schema (as amended 2026-07-23: 'model', not 'slug').
    # ``str(row["provider"])`` would smuggle the literal string ``"None"``
    # into the ``ChainEntry`` on YAML ``provider: null``, and
    # ``row["provider"]`` would raise ``KeyError`` (less helpful than a
    # named ``ConfigurationError``) on a missing key. The downstream
    # validator catches the smuggled ``"None"`` indirectly («unknown
    # provider 'None'»), but the user-facing message is clearer when the
    # loader surfaces the offending field by name. Same pattern as the
    # optional-field null coercion below.
    for index, row in enumerate(chain_rows):
        if "slug" in row:
            raise ConfigurationError(
                f"role {role!r} chain[{index}]: 'slug:' is the OLD field name (ADR-9 §Amendment "
                f"2026-07-23). Fix: rename it to 'model:' in ~/.fa/models.yaml — this is the "
                f'literal string sent as "model" in this entry\'s request body (every real '
                f"provider API calls this field 'model'; the historical 'slug' name was never "
                f"actually wired to the request)."
            )
        if "extras" in row:
            raise ConfigurationError(
                f"role {role!r} chain[{index}]: 'extras:' is not a valid chain-entry field "
                f"(ADR-9 §Amendment 2026-07-23). Fix: use 'provider_params:' instead in "
                f"~/.fa/models.yaml."
            )
        for field_name in ("provider", "model", "base_url", "api_key_env"):
            if row.get(field_name) is None:
                raise ConfigurationError(
                    f"role {role!r} chain[{index}]: required field {field_name!r} is null or missing. "
                    f"Fix: set the '{field_name}' field in the chain[{index}] entry under "
                    f"role '{role}' in ~/.fa/models.yaml."
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
    # ``extra_headers`` / ``provider_params`` ``or {}`` is safe because
    # an empty dict and a missing dict are observationally equivalent.
    entries = tuple(
        ChainEntry(
            provider=str(row["provider"]),
            model=str(row["model"]),
            base_url=str(row["base_url"]),
            api_key_env=str(row["api_key_env"]),
            cooldown_seconds=int(
                row["cooldown_seconds"] if row.get("cooldown_seconds") is not None else DEFAULT_COOLDOWN_SECONDS
            ),
            transport_retries=int(
                row["transport_retries"] if row.get("transport_retries") is not None else DEFAULT_TRANSPORT_RETRIES
            ),
            timeout_seconds=int(
                row["timeout_seconds"] if row.get("timeout_seconds") is not None else DEFAULT_TIMEOUT_SECONDS
            ),
            extra_headers=dict(row.get("extra_headers") or {}),
            provider_params=dict(row.get("provider_params") or {}),
        )
        for row in chain_rows
    )
    # ``raw.get(key, "")`` returns the actual value when the YAML row
    # contains ``key: null`` (because the key exists), so ``str(None)``
    # would smuggle the literal string ``"None"`` into the config and
    # the validator would emit a confusing «entry family X != role
    # family 'None'» warning. ``raw.get(key) or ""`` coalesces both
    # missing-key and None-value to the empty string.
    #
    # ``family`` is additionally normalised via ``.strip().lower()``
    # so every downstream consumer of ``ChainConfig.family`` —
    # ``check_eval_disjoint`` (ADR-2 §Amendment 2026-05-20 rule 1,
    # case-sensitive ``==``), the validator's entry-family mismatch
    # warning (compares against ``extract_family(entry.model)`` which is
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
    context_limit_raw = raw.get("context_limit")
    compaction_threshold_raw = raw.get("compaction_threshold")
    try:
        context_limit = int(context_limit_raw) if context_limit_raw is not None else 150000
        compaction_threshold = int(compaction_threshold_raw) if compaction_threshold_raw is not None else None
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            f"role {role!r}: context_limit and compaction_threshold must be integers "
            f"(got context_limit={context_limit_raw!r}, "
            f"compaction_threshold={compaction_threshold_raw!r}). "
            f"Fix: use integer values in ~/.fa/models.yaml."
        ) from exc
    # Role-level sampling defaults (ADR-9 §Amendment 2026-07-23): sent
    # identically to every chain entry unless the caller passes an
    # explicit override (see ProviderChain.request). Values are passed
    # through verbatim; ProviderChain.request applies them as fallbacks
    # for RequestInfo.temperature / max_tokens / top_p (None means "use
    # role default"), so no type coercion happens here — a malformed
    # value surfaces as a TypeError from the provider's own transport
    # layer, same failure mode as a malformed explicit call-site value.
    sampling_raw = raw.get("sampling")
    sampling: Mapping[str, Any] = sampling_raw if isinstance(sampling_raw, Mapping) else {}
    return ChainConfig(
        role=role,
        name=str(raw.get("name") or ""),
        family=str(raw.get("family") or "").strip().lower(),
        chain=entries,
        context_limit=context_limit,
        compaction_threshold=compaction_threshold,
        sampling=sampling,
    )
