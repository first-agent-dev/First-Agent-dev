"""Shift-left ``models.yaml`` routing lint (ADR-12 preflight companion).

Three independent checks, all provable from ``models.yaml`` alone — no
Docker, no network, no running proxy required:

1. **Cross-role route conflicts** — re-runs
   :func:`fa.egress_proxy.routing.build_route_table` against every role's
   chain combined. This is the exact check ``fa egress-proxy`` performs at
   container-start time (:class:`fa.egress_proxy.routing.ProxyConfigError`);
   running it here surfaces the identical failure in well under a second,
   before any image build or container crash-loop.

2. **Near-miss base_url heuristic** — flags a chain entry whose ``base_url``
   is *suspicious*: same registered provider, but not an exact match for
   any known-good canonical URL for that provider, and "close" to one by
   edit distance (a likely typo) rather than "unrelated" (a deliberate
   custom gateway). This catches the case a cross-role conflict check
   cannot: a lone typo in an entry that has no sibling to disagree with.

3. **Unknown provider_params key** — flags a chain entry's ``provider_params``
   key that the entry's own adapter does not recognise (e.g.
   ``reasoning_efort`` instead of ``reasoning_effort``). Adapters that do
   unrestricted body passthrough (``openai_compat``, ``anthropic`` category
   providers) have no fixed key set to check against and are silently
   skipped — this check only fires for adapters that publish an explicit
   recognised-keys constant (currently ``mistral`` and ``mistral_agents``).
   ``body.setdefault(key, value)`` in every adapter accepts ANY key with no
   validation, so a typo'd key is otherwise silently swallowed — the
   provider never receives the field the operator intended, with no error
   anywhere.

Every check is advisory-shaped (return findings; never raise) so callers
(CLI, deploy-script preflight, tests) decide what counts as fatal.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

from fa.egress_proxy.routing import ProxyConfigError, build_route_table, route_name_for
from fa.providers.config import ModelsConfig
from fa.providers.mistral import MISTRAL_RECOGNIZED_PROVIDER_PARAMS_KEYS
from fa.providers.mistral_conversations import MISTRAL_CONVERSATIONS_RECOGNIZED_PROVIDER_PARAMS_KEYS

__all__ = [
    "CANONICAL_PROVIDER_BASE_URLS",
    "KNOWN_PROVIDER_PARAMS_KEYS",
    "RoutingFinding",
    "lint_models_config",
]


@dataclass(frozen=True)
class RoutingFinding:
    """One lint finding — always advisory; the caller decides fatality."""

    category: str  # "route_conflict" | "near_miss_base_url" | "unknown_provider_params_key"
    role: str
    message: str


# Known-good canonical base_url(s) per registered provider name (NOT per
# host — see fa.providers.mistral vs fa.providers.mistral_conversations:
# both target api.mistral.ai but the *correct* base_url shape differs
# ("https://api.mistral.ai/v1" vs bare "https://api.mistral.ai") because
# each adapter appends its own path suffix. Keying by provider name (not
# host) avoids a false positive on that legitimate pair.
#
# Deliberately NOT exhaustive over every entry in
# fa.providers.registry.PROVIDERS: providers absent here (e.g. a
# self-hosted/aggregator platform with no single fixed endpoint) are
# skipped by the heuristic below, not flagged. New entries are added
# opportunistically as they appear in shipped examples/ADRs/tests
# (single source of truth for the literal is this file; do not duplicate
# the table elsewhere).
CANONICAL_PROVIDER_BASE_URLS: Mapping[str, tuple[str, ...]] = {
    "openrouter": ("https://openrouter.ai/api/v1",),
    "fireworks": ("https://api.fireworks.ai/inference/v1",),
    "nvidia_build": ("https://integrate.api.nvidia.com/v1",),
    "groq": ("https://api.groq.com/openai/v1",),
    "anthropic": ("https://api.anthropic.com",),
    "mistral": ("https://api.mistral.ai/v1",),
    "mistral_agents": ("https://api.mistral.ai",),
}

# Provider -> the set of provider_params keys THAT provider's adapter
# recognises, imported directly from each adapter module (single source of
# truth lives in the adapter; this dict only routes provider name ->
# adapter constant, never duplicates the key list itself). Providers absent
# here (openai_compat-category, anthropic) do unrestricted
# ``body.setdefault(key, value)`` passthrough with no fixed key set to
# validate against, so they are deliberately excluded — a missing entry
# means "no check for this provider", not "this provider rejects
# provider_params".
KNOWN_PROVIDER_PARAMS_KEYS: Mapping[str, frozenset[str]] = {
    "mistral": MISTRAL_RECOGNIZED_PROVIDER_PARAMS_KEYS,
    "mistral_agents": MISTRAL_CONVERSATIONS_RECOGNIZED_PROVIDER_PARAMS_KEYS,
}

# Edit-distance ceiling for "typo of a canonical URL" vs. "an unrelated,
# deliberately different URL" (e.g. a self-hosted gateway). Chosen from the
# motivating case: "https://api.mistral.ai/v1" -> ".../vl" is distance 1.
# A ceiling of 3 catches single/double-character slips (transposition,
# substitution, one dropped/added char) without flagging genuinely
# different hosts, whose distance is typically 10+.
_NEAR_MISS_MAX_DISTANCE = 3


def _levenshtein(a: str, b: str) -> int:
    """Standard O(len(a)*len(b)) edit distance; no third-party dependency."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current[j] = min(
                previous[j] + 1,  # deletion
                current[j - 1] + 1,  # insertion
                previous[j - 1] + cost,  # substitution
            )
        previous = current
    return previous[-1]


def _normalize(url: str) -> str:
    """Strip a trailing slash so ``.../v1`` and ``.../v1/`` compare equal."""
    return url.rstrip("/")


def _near_miss_finding(role: str, chain_index: int, provider: str, model: str, base_url: str) -> RoutingFinding | None:
    canonical_urls = CANONICAL_PROVIDER_BASE_URLS.get(provider)
    if not canonical_urls:
        return None
    normalized = _normalize(base_url)
    if any(normalized == _normalize(c) for c in canonical_urls):
        return None  # exact match (mod trailing slash) — nothing to flag
    # Only compare within the same host: a chain entry pointed at a
    # deliberately different host (self-hosted gateway, regional mirror)
    # is out of scope for a typo heuristic and would otherwise produce
    # noisy false positives.
    entry_host = urlparse(base_url).hostname or ""
    best_distance: int | None = None
    best_canonical = ""
    for canonical in canonical_urls:
        if urlparse(canonical).hostname != entry_host:
            continue
        distance = _levenshtein(normalized, _normalize(canonical))
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_canonical = canonical
    if best_distance is None or best_distance == 0 or best_distance > _NEAR_MISS_MAX_DISTANCE:
        return None
    return RoutingFinding(
        category="near_miss_base_url",
        role=role,
        message=(
            f"models.yaml: role {role!r} chain[{chain_index}] (provider={provider!r}, model={model!r}): "
            f"base_url {base_url!r} is {best_distance} character(s) different from "
            f"the known-good {best_canonical!r} for provider {provider!r}. "
            "This is very likely a typo (e.g. 'v1' vs 'vl'), not a deliberate "
            "custom endpoint. Fix: correct base_url in models.yaml, or confirm "
            "this is an intentional non-canonical gateway."
        ),
    )


# Matches the leading `route 'NAME'` (or `route 'NAME':`) prefix shared by
# every fa.egress_proxy.routing.ProxyConfigError message shape, so a
# conflict's route name can be recovered without re-implementing
# build_route_table's own validation logic here (single source of truth
# for "is this a conflict" stays in build_route_table; this regex only
# recovers WHICH route it was, for citing chain-entry locations).
_ROUTE_NAME_RE = re.compile(r"^route '([^']*)'")


def _unknown_provider_params_finding(
    role: str, chain_index: int, provider: str, model: str, provider_params: Mapping[str, object]
) -> RoutingFinding | None:
    known_keys = KNOWN_PROVIDER_PARAMS_KEYS.get(provider)
    if known_keys is None or not provider_params:
        return None  # no fixed key set for this provider, or nothing to check
    unknown_keys = sorted(set(provider_params) - known_keys)
    if not unknown_keys:
        return None
    return RoutingFinding(
        category="unknown_provider_params_key",
        role=role,
        message=(
            f"models.yaml: role {role!r} chain[{chain_index}] (provider={provider!r}, model={model!r}): "
            f"provider_params key(s) {unknown_keys!r} not recognised by the {provider!r} adapter "
            f"(known keys: {sorted(known_keys)!r}). This is very likely a typo — an unrecognised key "
            "is silently accepted and forwarded verbatim in the request body by "
            "body.setdefault(key, value), so the provider never receives the field you intended and "
            "no error is raised anywhere. Fix: correct the key name in models.yaml, or confirm this "
            "is an intentional passthrough field the provider documents but this adapter does not yet."
        ),
    )


def lint_models_config(models: ModelsConfig) -> list[RoutingFinding]:
    """Run all routing lint checks against an already-loaded config.

    Never raises: :class:`fa.egress_proxy.routing.ProxyConfigError` from the
    conflict check is caught and folded into a :class:`RoutingFinding` like
    every other finding, so a single lint pass reports everything it can
    instead of stopping at the first problem.
    """

    findings: list[RoutingFinding] = []

    # (role, chain_index, provider, model, base_url, api_key_env) — the index
    # lets a route_conflict finding cite exactly which entries collided,
    # instead of forcing the operator to hunt through models.yaml for every
    # occurrence of a given provider/model pair.
    located_entries: list[tuple[str, int, str, str, str, str]] = []
    for role_name, chain_config in models.roles.items():
        for chain_index, entry in enumerate(chain_config.chain):
            located_entries.append(
                (role_name, chain_index, entry.provider, entry.model, entry.base_url, entry.api_key_env)
            )
            near_miss = _near_miss_finding(role_name, chain_index, entry.provider, entry.model, entry.base_url)
            if near_miss is not None:
                findings.append(near_miss)
            unknown_params = _unknown_provider_params_finding(
                role_name, chain_index, entry.provider, entry.model, entry.provider_params
            )
            if unknown_params is not None:
                findings.append(unknown_params)

    chain_entries = [
        (provider, model, base_url, api_key_env) for _, _, provider, model, base_url, api_key_env in located_entries
    ]
    try:
        build_route_table(chain_entries)
    except ProxyConfigError as exc:
        message = str(exc)
        match = _ROUTE_NAME_RE.search(message)
        locations: list[str] = []
        if match is not None:
            conflict_name = match.group(1)
            locations = [
                f"role {role!r} chain[{chain_index}]"
                for role, chain_index, provider, model, _base_url, _api_key_env in located_entries
                if route_name_for(provider, model) == conflict_name
            ]
        if locations:
            message = f"{message} (chain entries: {', '.join(locations)})"
        findings.append(RoutingFinding(category="route_conflict", role="<cross-role>", message=message))

    return findings
