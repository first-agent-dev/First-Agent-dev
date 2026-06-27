# ADR-9 — LLM provider client (T-2 driver: per-role explicit provider chain)

- **Status:** proposed
- **Date:** 2026-05-22
- **Deciders:** project owner (`0oi9z7m1z8`), Agent (drafting)

## Context

T-2 (the LLM driver / provider client) is the lynchpin of every
Pillar-3 deliverable: ADR-2 «no cross-tier auto-escalation» role
routing, ADR-7 §5 retry-budget invariant, ADR-8 HookRegistry
`BEFORE_LLM_CALL` / `AFTER_LLM_CALL` lifecycle points, ADR-6 tool
sandbox boundary (LLM call ≠ tool call so not gated), and the
`CostGuardian` cost-budget enforcement from PR-4 / Wave-3 stack #1
— all of them assume a working LLM driver and currently no real
provider client exists in the repo.

The driver's surface lives at `src/fa/providers/` (does not yet
exist). The configuration surface lives at `~/.fa/models.yaml`
(today carries `{provider, model, temperature, ...}` per role; the
T-2 PR extends this with the chain shape from this ADR).

**The actual requirement (user reframe 2026-05-22).** The driver
must support **multi-step provider fallback for the SAME model
identity** — e.g. one logical `deepseek-v3` call falls through
OpenRouter → Fireworks → NVIDIA Build → Groq when the primary
provider is rate-limited, down, or daily-quota-exhausted. This is
**cross-PLATFORM transport-level fallback**, not cross-MODEL
auto-escalation (which ADR-2 forbids). The distinction matters:
family extraction stays anchored on the logical model identity
(`deepseek-v3` → `deepseek` family), not the provider platform,
so ADR-2 §Amendment 2026-05-20 + ADR-7 §Amendment 2026-05-20 rule 4
family-disjoint constraints are **untouched** by provider fallback.

**Free-tier reality.** Half of the candidate providers (NVIDIA
Build, Modal, OpenRouter free tier, Groq free tier, GitHub Models)
have low reliability, long queues, and per-day call quotas; the
chain pattern is the operational answer to «one provider's quota
got exhausted at 03:00 UTC, role still needs to work».

**The 9-source audit (cross-reference evidence).**
[`knowledge/research/provider-client-survey-2026-05.md`](../research/provider-client-survey-2026-05.md)
audits 8 OSS implementations + 1 data source + 3 rejected (Kong /
plano / coai). All 8 in-scope sources independently converge on
the same three-piece pattern: per-provider (or finer) cooldown
after failure + ordered fallback chain + isolated per-provider
state. FA's proposed Option D is the well-trodden industry pattern,
not novel design.

## Options considered

### Option A — Delegate entirely to an external gateway (GoModel / LiteLLM container)

- Pros:
  - Zero FA-resident provider code (~0 LOC); production-grade
    resilience inherited from upstream.
  - Future provider additions = config the gateway, no FA changes.
- Cons:
  - Hard dependency on Docker + a containerised gateway running
    locally; conflicts with UC1 single-user single-process scope.
  - Surfaces another stack to install / debug / version-pin —
    weaker OSS LLMs (DeepSeek 4 / Kimi 2.6, target audience per
    AGENTS.md) reason poorly over multi-process failure modes.
  - Cost accounting and family-disjoint enforcement need to be
    re-implemented at the gateway layer or lost; FA's existing
    `CostGuardian` middleware (R-45) wraps the FA-resident
    provider client, not a remote one.

### Option B1 — FA-direct without resilience; user runs gateway externally if they want fallback

- Pros: smallest LOC (~200); pure HTTP wrapper around httpx.
- Cons:
  - Free-tier rate-limit handling becomes the user's homework.
  - No FA-side test coverage for the free-tier-resilience path
    (since that path lives outside FA).
  - Misses the «cross-platform fallback for same model» requirement
    the user explicitly named.

### Option B2 — FA-direct with minimum resilience (retry + circuit-breaker, no fallback resolver)

- Pros: ~350 LOC; clean, single-provider-per-role.
- Cons: no fallback at all → role dies when its single configured
  provider is rate-limited. Same failure mode as B1.

### Option B3 — Full GoModel-style lift (Hooks Protocol + CircuitBreaker + FallbackResolver + CapabilityModel + ProviderAttempt)

- Pros: feature-complete provider resilience layer; matches
  GoModel's production-grade story.
- Cons:
  - ~500 LOC FA-resident; `CapabilityModel` + `ProviderAttempt`
    add indirection unjustified at FA's single-call-at-a-time scope.
  - `FallbackResolver` in GoModel auto-picks fallback candidates
    from `chatbot_arena_coding` rankings — this is **cross-MODEL
    auto-escalation**, conflicting with ADR-2 §Decision.
  - Future-agent reading burden: 500 LOC of resilience code that
    a weaker OSS LLM must absorb before touching the provider
    layer.

### Option C — B2 + transparent gateway delegation via `base_url` override

- Pros: ~330 LOC; power users opt into B3 features by running a
  gateway and setting `base_url` per provider config — FA does not
  reimplement resilience, the gateway does.
- Cons:
  - The default install has NO multi-provider fallback. UC1's
    free-tier resilience target requires running the gateway,
    which is the very dependency Option A was rejected for.
  - Solves «opt-in resilience» but not «native cross-platform
    fallback for same model» (the user's explicit reframe).

### Option D — Per-role explicit provider chain with cooldown (the picked option)

- Pros:
  - ~380 LOC FA-resident; lands between B2 and B3 LOC budget,
    above B2 only by the Anthropic-native adapter (~70 LOC) and
    chain-bookkeeping (~50 LOC).
  - **Native cross-platform fallback for the same model identity
    is the v0.1 default**, not an opt-in via external dependency.
  - Aligns with ADR-2: chain entries pin the same model identity,
    family-disjoint check stays grounded in the model identity
    (not the provider platform); no cross-model auto-escalation.
  - Subsumes Option C: a single chain entry can point its
    `base_url` at an external gateway (`http://localhost:8080/v1`),
    delegating resilience to the gateway, same code path.
  - All 8 audited OSS sources converge on this pattern (cooldown
    + ordered chain + isolated state); FA is adopting the
    industry-standard shape.
  - Add-OpenAI-compat-platform = 1 line in `PROVIDERS` dict + 1
    YAML row; Add-Anthropic-shape-platform = 1 new adapter file
    (~70 LOC).
- Cons:
  - ~50 LOC of chain-bookkeeping that B2 doesn't need.
  - User must explicitly enumerate the chain per role — no auto-
    discovery. Documented as a deliberate choice (auto-discovery
    is the GoModel arena-ranking pattern we rejected as cross-
    MODEL fallback).

## Decision

We will choose **Option D + α** (per-role explicit chain with
cooldown; per-role declaration shape, no shared named chains in
v0.1) because:

> **Revision 2026-05-22 (pre-PR critical pass).** §1, §2, §3, §4,
> §5, §7, §9, §10, §Consequences refined after self-critique against
> 7 P0 logic-bug and 6 P1 design-gap findings (typed errors, fail-
> fast on 4xx request-shape errors, `logical_call_id` correlation,
> response normalization / cost+token accounting source / per-
> request timeout / adaptive-cooldown-from-`Retry-After`, request
> translation for reasoning-model parameters, reframed §7 model-
> identity claim as user discipline + best-effort heuristic). No
> changes to §Decision direction; Option D + α remains the choice.

1. It is the only option that natively supports multi-step
   fallback for the SAME model across multiple providers — the
   user-stated v0.1 requirement (chat 2026-05-22).
2. It aligns with ADR-2 «no cross-tier auto-escalation» — chain
   entries pin the same model identity, only the platform varies;
   the family-disjoint constraint is preserved because family is
   extracted from the logical model identity, not the provider.
3. All 8 audited OSS sources independently converge on this
   pattern (see
   [`provider-client-survey-2026-05.md`](../research/provider-client-survey-2026-05.md)
   §4.2). FA is adopting the industry-standard shape, not novel
   design.
4. It subsumes Option C's flexibility (gateway delegation as one
   chain entry) without taking on Option A's dependency cost.
5. The ~380 LOC budget fits FA's «add-only-when-necessary»
   discipline; ~50 LOC of chain-bookkeeping is the explicit cost
   of native fallback.

**Decided in chat 2026-05-22.** §0 Decision Briefing of the
companion survey
([`provider-client-survey-2026-05.md`](../research/provider-client-survey-2026-05.md))
lays out R-1 (Option D + α verdict) and R-2..R-6 sub-decisions in
the audit-evidence format.

## §1 Chain configuration shape

`~/.fa/models.yaml` per-role chain example:

```yaml
coder:
  model:  "deepseek-v3"           # logical model identity (family anchored here)
  family: "deepseek"              # optional explicit override; default = extract_family(model)
  chain:                          # ordered transport fallback — explicit, code-tweakable
    - provider: openrouter
      slug:     "deepseek/deepseek-chat-v3"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
      cooldown_seconds: 300       # optional override; default = 300
    - provider: fireworks
      slug:     "accounts/fireworks/models/deepseek-v3"
      base_url: "https://api.fireworks.ai/inference/v1"
      api_key_env: FIREWORKS_API_KEY
    - provider: nvidia_build
      slug:     "deepseek-ai/deepseek-v3"
      base_url: "https://integrate.api.nvidia.com/v1"
      api_key_env: NVIDIA_BUILD_API_KEY
    - provider: groq
      slug:     "deepseek-v3"
      base_url: "https://api.groq.com/openai/v1"
      api_key_env: GROQ_API_KEY

planner:
  model:  "kimi-k2"
  family: "kimi"
  chain:
    - provider: openrouter
      slug:     "moonshotai/kimi-k2"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
    - provider: groq
      slug:     "kimi-k2"
      base_url: "https://api.groq.com/openai/v1"
      api_key_env: GROQ_API_KEY

eval:
  model:  "qwen-3-32b"            # different family from coder + planner — disjoint
  family: "qwen"
  chain:
    - provider: openrouter
      slug:     "qwen/qwen-3-32b-instruct"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
    - provider: nvidia_build
      slug:     "qwen/qwen-3-32b"
      base_url: "https://integrate.api.nvidia.com/v1"
      api_key_env: NVIDIA_BUILD_API_KEY
```

**Required fields per chain entry:** `provider` (string, must
match a key in `PROVIDERS` registry), `slug` (provider-specific
model identifier), `base_url` (HTTPS URL — wire-shape preserved
verbatim), `api_key_env` (environment variable name carrying the
API key for that provider).

**Optional fields per chain entry:** `cooldown_seconds` (integer,
default 300), `transport_retries` (integer, default 1 — see Q-2 in
the survey), `timeout_seconds` (integer, default 60 — per-request
httpx timeout covering connect + read; raise for queued free-tier
endpoints e.g. 300), `extra_headers` (dict<str, str> for provider-
specific request headers — e.g. OpenRouter's recommended
`HTTP-Referer` + `X-Title` для usage analytics; never used to
spoof transport identity per §8 point 2).

**Config-load validation (`src/fa/providers/chain.py::ChainConfig.validate()`).**
Validator MUST raise `ConfigurationError` at config-load time (not
at first request) for each of:

- **Empty chain** — `len(chain) == 0`. Roles without a chain are
  not callable.
- **Reserved provider name** — chain entry's `provider` ∈
  `RESERVED_PROVIDER_NAMES` (see §6) raises `ReservedProviderError`
  (typed subclass of `ConfigurationError`).
- **Unknown provider** — `provider` not in `PROVIDERS` registry
  raises `ConfigurationError("unknown provider 'X'; known:
  {sorted(PROVIDERS.keys())}")`.
- **`base_url` scheme** — must be `https://` for non-localhost
  hosts. `http://` accepted only when host ∈ {`localhost`,
  `127.0.0.1`, `0.0.0.0`} (gateway-delegation case); emits a
  warning row. Any other scheme (`ws://`, `file://`, missing
  scheme, ...) raises `ConfigurationError`.
- **`api_key_env` present and non-empty in `os.environ`** —
  `os.environ.get(api_key_env, "").strip() == ""` raises
  `ConfigurationError("chain entry api_key_env={api_key_env}
  not set or empty")`. Validator failure surfaces missing-env
  loudly at config-load rather than as a confusing 401 from the
  provider at first call.
- **Best-effort model-identity check** — see §7 reframed rule:
  emits warning (not error) if `extract_family(slug)` does not
  match the role's `family:` field, because slug strings vary
  legitimately across providers and exact-match would produce
  false positives.
- **Best-effort adapter-homogeneity check** — emits warning
  (not error) if not all chain entries resolve to the same
  adapter category in `PROVIDERS` (e.g. role's chain mixes
  `OpenAICompatProvider`-backed providers with
  `AnthropicProvider`-backed providers). Rationale: the §2
  step 2g fail-fast logic on 400/422 assumes the next chain
  entry sends the same request body shape; mixed adapters
  break that assumption (Anthropic's `/v1/messages` has
  system-as-separate-field + tool-use content blocks while
  OpenAI-compat `/chat/completions` does not). Warning, not
  error, because the natural shape (same model identity across
  chain entries) keeps homogeneity automatically; only unusual
  configs produce mixed-adapter chains. See §2 step 2g for the
  runtime implication.

## §2 Runtime semantics

```text
0. Generate logical_call_id (uuid4) for the role's call; this id
   correlates Tier-1 + Tier-2 + Tier-3 observability rows (§4).
1. Resolve chain for role from ~/.fa/models.yaml (loaded once at
   session start; config hot-reload is out of scope for v0.1).
2. For each chain entry in declared order:
   a. If entry is in cooldown (cooldown_row.expires_at > now): SKIP.
   b. Fire BEFORE_LLM_CALL hook with {role, provider, slug,
      logical_call_id, attempt_index} context.
   c. POST to <base_url> + <adapter endpoint>; receive HTTP status
      and headers. Adapter endpoint is per-adapter:
      OpenAICompatProvider → "/chat/completions";
      AnthropicProvider → "/v1/messages". transport_retries
      (default 1) are exhausted in-place BEFORE the chain
      progresses; only after all per-entry retries fail do the
      progression rules below apply.
   d. If status ∈ {200}: adapter normalizes response (§5
      response-normalization) → fire AFTER_LLM_CALL hook → return.
   e. If status ∈ {429, 500..504} or network error:
      - Compute cooldown_until = max(now + cooldown_seconds,
        parsed_retry_after) (see §3 adaptive cooldown).
      - Record CooldownRow for (provider, slug) with expires_at
        = cooldown_until.
      - Append ChainAttemptRecord to in-progress llm_call row.
      - Continue to next chain entry.
   f. If status ∈ {401, 403}: AUTH FAILURE for THIS provider only.
      - Log as terminal-for-this-entry; do NOT cool down (caller
        config error, not provider transient; cooldown would
        wrongly silence a future correct rotation).
      - Append ChainAttemptRecord; continue to next entry (auth
        on one provider does not block trying the next; common
        case: wrong api_key_env or expired token on one platform).
   g. If status ∈ {400, 422}: REQUEST-SHAPE FAILURE (FA's request
      construction is wrong; next provider will produce the same
      4xx because we send the same body). FAIL FAST:
      - Raise ProviderRequestShapeError immediately; do NOT
        progress chain (continuing wastes budget on a deterministic
        client bug).
      - Emit Tier-2 row with terminal="request_shape" so the
        FailureClassifierObserver routes to «code bug» not
        «retry the role» (ADR-7 §Amendment 2026-05-20 rule 3).
      - **Adapter-homogeneity assumption.** Fail-fast assumes
        chain entries send the same request body shape («the same
        body will fail the same way on the next provider»). Holds
        when every entry uses the same adapter category (all
        `OpenAICompatProvider` OR all `AnthropicProvider`). FA does
        NOT enforce homogeneity as a hard error — see §1 warning
        rule above — because the natural shape (same model identity
        across chain entries) keeps homogeneity by default: a
        `deepseek-v3` chain has no Anthropic entries; an Anthropic
        `claude-3.5` chain has no OpenAI-compat entries. Mixing
        adapter categories is undocumented territory; if a user
        does it and a 400 fires, the FAIL FAST is slightly over-
        eager but still better than silently treating all 400s as
        transient and wasting budget on every chain entry.
3. If all entries exhausted: raise ProviderChainExhaustedError
   carrying the full attempts list (typed; not bare RuntimeError —
   see §5 errors.py).
   - Fire AFTER_LLM_CALL hook with chain_status="exhausted".
   - Emit llm_chain_exhausted row to events.jsonl (Tier-2
     observability, §4).
4. On next call: cooled-down entries are deprioritized (skipped
   within cooldown window); on each entry, success deletes its
   CooldownRow.
```

**Multi-turn conversations.** Each round-trip's chain resolution
is independent — provider X may serve turn 1 and provider Y serve
turn 2. The conversation state (messages list) travels in the
request body, not the connection or the provider identity, so
fallback is transparent across turns. State-bearing optimizations
(Anthropic prompt caching, OpenAI session keys) are an exception:
fallback loses the optimization but never the correctness; see
§9 Q-5.

**Cooldown rows are in-memory only in v0.1** (no SQLite persistence;
see survey Q-1 — deferred). Process restart clears all cooldown
state; this is acceptable for UC1's single-user single-session
scope.

## §3 Cooldown semantics

**Cooldown unit:** `(provider, slug)` tuple. Finer than per-provider
(matches LiteLLM `CooldownCacheValue` schema in
`/tmp/research/litellm/litellm/router_utils/cooldown_cache.py`); a
single 503 on `openrouter/deepseek-v3` does not block
`openrouter/kimi-k2` for that role's chain. Justification in
[survey §0 R-2](../research/provider-client-survey-2026-05.md#r-2--cooldown-unit-must-be-per-provider-slug-tuple-not-per-provider).

**Cooldown trigger condition:** single transient failure (status ∈
{429, 500..504} or network error). FA does NOT use a percent-
threshold over a sliding window (LiteLLM's
`DEFAULT_FAILURE_THRESHOLD_PERCENT` pattern); UC1 traffic is too
low to accumulate statistically meaningful percent-failure signal.
Documented in [survey §5 Risks](../research/provider-client-survey-2026-05.md#5-risks-and-caveats).

**Cooldown duration:** 5 minutes by default (`cooldown_seconds: 300`),
configurable per chain entry. Matches kronos `PEER_REACTION_COOLDOWN
= 300` and dpc-messenger pattern.

**Adaptive cooldown from `Retry-After` (RFC 9110).** If the
response on a transient failure includes a `Retry-After` header
(seconds-form or HTTP-date-form), the cooldown row's `expires_at`
is set to `max(now + cooldown_seconds, parsed_retry_after)` —
floor at the configured default, ceiling unbounded. Prevents
cooling down for shorter than the provider explicitly asked for
(Cloudflare commonly returns `Retry-After: 60` on 429s; FA's flat
300-sec default is conservative but a 30-min provider notice
should override). Header parsing failure (malformed value) falls
back silently to the configured `cooldown_seconds`.

**Cross-role shared cooldown state.** The cooldown dict is
process-global, keyed on `(provider, slug)` — NOT on
`(role, provider, slug)`. Two roles whose chains share the same
`(provider, slug)` tuple share the cooldown state. Right call: the
upstream endpoint is the same, so its rate-limit signal applies
regardless of which role triggered it.

**Cooldown row schema** (in-memory dict keyed by `(provider, slug)`):

```python
@dataclass
class CooldownRow:
    provider: str
    slug: str
    started_at: float           # unix timestamp
    expires_at: float           # max(started_at + cooldown_seconds, retry_after_unix)
    trigger_status: int         # HTTP status that triggered cooldown; 0 for network failure
    trigger_error: str          # short kind: "rate_limited" | "service_unavailable" | "timeout"
    retry_after_hint_ms: int    # parsed Retry-After in ms; 0 if absent or malformed
```

**Cooldown lifecycle:**

- Cooldown row created on transient failure for `(provider, slug)`.
- Within `cooldown_seconds` window, that tuple is skipped on
  subsequent chain resolutions.
- After `cooldown_seconds` expire, the entry is tried again on
  the next chain call. On success → cooldown row deleted; on
  another transient failure → row's `expires_at` extended by a
  fresh `cooldown_seconds` (no exponential backoff in v0.1; flat
  fixed window per attempt).

## §4 Observability surface

Three tiers, all wiring through ADR-8 HookRegistry
`AFTER_LLM_CALL` lifecycle point:

**Tier 1 — always-on, 1 row per logical call (`kind: "llm_call"`):**

```json
{
  "kind": "llm_call",
  "ts": "2026-05-22T...",
  "logical_call_id": "<uuid4>",
  "role": "coder",
  "model": "deepseek-v3",
  "family": "deepseek",
  "chain": [
    {"provider": "openrouter", "slug": "deepseek/deepseek-chat-v3",
     "status": 429, "ms": 142, "error": "rate_limited"},
    {"provider": "fireworks", "slug": "accounts/fireworks/models/deepseek-v3",
     "status": 200, "ms": 891, "error": null}
  ],
  "in_tokens": 1247,
  "out_tokens": 322,
  "cost_usd": 0.0019,
  "wallclock_ms": 1033
}
```

→ Single row per *logical* call. Attempted-providers inline in
`chain: [...]`; lets an agent answer «which platform is unreliable
on which days» without grepping multi-row sequences. Mandatory for
Pillar-3 token/cost measurement anyway.

**Tier 2 — always-on but fires only on chain exhaustion or request-shape error (`kind: "llm_chain_exhausted"`):**

```json
{
  "kind": "llm_chain_exhausted",
  "ts": "2026-05-22T...",
  "logical_call_id": "<uuid4>",
  "role": "coder",
  "model": "deepseek-v3",
  "terminal": "all_exhausted",
  "attempts": [
    {"provider": "openrouter", "slug": "deepseek/deepseek-chat-v3",
     "status": 429, "ms": 142, "error": "rate_limited"},
    {"provider": "fireworks", "slug": "accounts/fireworks/models/deepseek-v3",
     "status": 503, "ms": 411, "error": "service_unavailable"},
    {"provider": "nvidia_build", "slug": "deepseek-ai/deepseek-v3",
     "status": 401, "ms": 87, "error": "auth_failed"},
    {"provider": "groq", "slug": "deepseek-v3",
     "status": 429, "ms": 234, "error": "rate_limited"}
  ],
  "wallclock_ms": 874
}
```

→ Emitted when the chain exhausts OR a request-shape error (400 /
422) terminates fast. The `terminal` field is `"all_exhausted"`
for exhaustion or `"request_shape"` for fast-fail. Consumed by
`FailureClassifierObserver` (R-3 Wave-2 stack #1) to decide
routing: exhaustion → retry role at T=1.0 per ADR-7 §Amendment
2026-05-20 rule 3; request-shape → escalate as code bug (do not
retry; same body will fail same way).

**Tier 3 — opt-in (`FA_DEBUG_LLM_BODIES=1` env var; separate file `llm_bodies.jsonl`):**

```json
{
  "kind": "llm_body",
  "ts": "2026-05-22T...",
  "logical_call_id": "<uuid4>",
  "attempt_index": 0,
  "provider": "openrouter",
  "slug": "deepseek/deepseek-chat-v3",
  "request_body": {...},
  "response_body": {...}
}
```

`logical_call_id` is identical to the Tier-1 and Tier-2 rows for
the same logical call → reviewers can correlate a debug body back
to the parent `llm_call` row via the uuid.

→ Disabled by default. When `FA_DEBUG_LLM_BODIES=1`, writes full
request/response bodies to a separate `llm_bodies.jsonl`
(gitignored). Useful for debugging «why did the planner produce
empty output». NOT in the default path — bodies are 5-50 KB per
call, contain context potentially sensitive in UC5 scenarios, and
99% of sessions never need them.

**Not collected at any tier:**

- Wire-level HTTP debug (headers, TLS handshake) — `httpx` handles
  via `LOGLEVEL=DEBUG` if needed; not FA's concern.
- Per-token streaming events — streaming is out of scope per ADR-7
  §1 «non-streaming only».
- OTel trace spans — deferred to UC5+; FA's `events.jsonl`
  already covers the «cheap-read trace» niche in v0.1.

**Cost + token accounting source.** Tier-1 `in_tokens` /
`out_tokens` come from the *successful* chain attempt's response
`usage` block, normalized per §5. Failed attempts contribute 0
tokens (4xx / 5xx responses almost never carry a `usage` field).
`cost_usd` is computed by `src/fa/observability/cost_table.py`:
lookup `(model_family, provider, slug) → (in_price_per_million,
out_price_per_million)` and multiply by the response's tokens.
Pricing table is seeded from public per-provider price pages and
is read-only from FA. Pricing-table-miss returns `cost_usd:
null` and emits a `cost_estimate_missing` warning row (so a
future amendment can backfill); CostGuardian (R-45) tolerates
`null` by treating it as zero plus a `cost_estimate_missing` flag
on its rolling-total tally. Pre-call `tiktoken`-style estimation
is deferred (Q-2 amendment slot) — pricing-table-miss is the
v0.1 telemetry signal that would justify the work.

## §5 Adapter pattern (R-4 from the survey)

Two-category provider split, matching Bifrost / GoModel /
LiteLLM / dpc-messenger convergent pattern (see
[survey §4.3](../research/provider-client-survey-2026-05.md#43-cross-source-convergence-on-the-adapter-split-r-4)):

**Category 1: OpenAI-compatible providers (shared `OpenAICompatProvider` adapter, ~80 LOC).**

Posts to `<base_url>/chat/completions`. Covers: OpenRouter,
Fireworks, NVIDIA Build, Groq, GitHub Models[^github-models],
Modal, Lambda Labs, Together AI, vLLM, Ollama, ZAI, MiniMax,
Cerebras, Perplexity, xAI, and any future OpenAI-compatible
platform. New addition = 1 row in `PROVIDERS` dict + 1 YAML chain
entry; no new file unless the provider needs custom auth headers
that `extra_headers` can't express (rare).

[^github-models]: GitHub Models uses Azure-hosted endpoints with
    GitHub PAT-based auth instead of OpenAI-style API keys.
    `OpenAICompatProvider` handles it via `api_key_env` pointing
    at a PAT (Bearer-injected by the adapter) and the standard
    OpenAI-shaped `/chat/completions` endpoint. No GitHub-specific
    adapter needed.

**Category 2: Native API providers (one adapter per shape).**

- `AnthropicProvider` (~70 LOC) — posts to `<base_url>/v1/messages`.
  Anthropic native protocol: `system` as a separate top-level
  field (not a `messages[0]` row), `tools: [{name, description,
  input_schema}]` (different field-names from OpenAI), tool use
  result as `content: [{type: "tool_use", id, name, input}]`
  blocks (vs OpenAI `tool_calls: [{...}]`).
- (Future amendments could add Gemini native, Bedrock, Cohere as
  separate adapters — but not in v0.1.)

**Response normalization (Postel's Law surface).** Each adapter
normalizes its provider's response into a canonical FA
`ResponseInfo` dataclass with stable fields {`text`, `in_tokens`,
`out_tokens`, `finish_reason`, `tool_calls`, `extras`}.
Provider-specific data that doesn't fit the canonical fields
(OpenRouter's `provider:` metadata block; Anthropic's separate
`thinking` blocks from extended-thinking models; OpenAI's
`system_fingerprint`) is preserved verbatim in
`ResponseInfo.extras: dict[str, Any]` so downstream consumers can
read it if needed, but is NOT part of the canonical contract.
Observability rows (§4 Tier-1) read only the canonical fields.

**Tool-calling syntax variance** (OpenAI `tools: [...]` +
`tool_calls: [...]` vs Anthropic `tools: [...]` + content blocks
`[{type: "tool_use", ...}]` vs Gemini `functionDeclarations: [...]`)
is handled INSIDE each adapter. Canonical FA representation uses
the OpenAI shape (chosen as the most widely-adopted v0.1 default);
`AnthropicProvider` transparently round-trips into Anthropic's
block-shape on request and back to OpenAI shape on response.
Future adapters carry the same translation contract.

**Request-parameter translation for reasoning models.**
Reasoning-model parameter translation (e.g. OpenAI o-series
`max_completion_tokens` reflecting FA's `max_tokens` field;
Anthropic extended-thinking `thinking: {type: "enabled",
budget_tokens: N}`) is a *per-model concern* applied in the
adapter at request-build time. The v0.1 translation table is
minimal (chat-completions only; no reasoning models in default
chains). Reasoning-model support is a future amendment slot
(§9 Q-6); when added, it lands as a per-model lookup in the
adapter rather than a new chain shape.

**File layout for T-2 PR:**

```text
src/fa/providers/
├── __init__.py          # public exports
├── base.py              # Provider Protocol + RequestInfo / ResponseInfo dataclasses (~60 LOC)
├── chain.py             # ChainConfig + ProviderChain + cooldown bookkeeping (~100 LOC)
├── openai_compat.py     # OpenAICompatProvider (~80 LOC)
├── anthropic.py         # AnthropicProvider (~70 LOC)
├── registry.py          # PROVIDERS dict + factory (~30 LOC)
└── errors.py            # 6 typed errors (~40 LOC):
                          #   ConfigurationError (base)
                          #   ReservedProviderError(ConfigurationError)
                          #   ProviderTransientError(Exception)
                          #   ProviderAuthError(Exception)
                          #   ProviderRequestShapeError(Exception)   ← fast-fail on 400 / 422
                          #   ProviderChainExhaustedError(Exception) ← all entries failed
```

FA's cost table also lives in observability (not providers):

```text
src/fa/observability/
└── cost_table.py        # static (model_family, provider, slug) → price-per-million lookup (~30 LOC; v0.1 seed; appended by amendment as new providers land)
```

**Total ~380 LOC.** Bullets land in T-2 PR; this ADR documents the
contract only.

## §6 Reserved-key semantics (R-5 from the survey)

Inspired by Bifrost's `BifrostContextKey*` reserved-namespace
pattern but with FA-specific fail-fast behavior (Bifrost silently
drops; FA raises at config-load time):

```python
RESERVED_PROVIDER_NAMES: frozenset[str] = frozenset({
    "__internal__",
    "__metadata__",
    "__fallback_marker__",
})
```

Config validator rejects chain entries with reserved `provider`
field at registration time (`src/fa/providers/chain.py::ChainConfig.validate()`):

```python
def validate(self) -> None:
    for entry in self.chain:
        if entry["provider"] in RESERVED_PROVIDER_NAMES:
            raise ReservedProviderError(
                f"chain entry uses reserved provider name {entry['provider']!r}; "
                f"reserved names: {sorted(RESERVED_PROVIDER_NAMES)}"
            )
```

Matches ADR-8 §3 `ConfigurationError` shape for duplicate hook
names — fail at config-load, not silently at runtime.

## §7 Family-disjoint constraint preservation

The chain shape does NOT change the family-disjoint check from
ADR-2 §Amendment 2026-05-20 + ADR-7 §Amendment 2026-05-20 rule 4 +
ADR-2 §Sub-amendment 2026-05-21 role-layer enforcement:

- **Family is extracted from the logical model identity** (top-level
  `model:` field of each role config), NOT from any chain entry's
  `provider` or `slug` field. `src/fa/roles.py::extract_family()`
  takes the model identity string and returns one of `KNOWN_FAMILIES`
  via regex slug-matching.
- **Provider fallback within same model identity is family-safe by
  construction** — all chain entries point at the same model
  weights, just hosted on different platforms. There is no family
  shift across chain entries; the eval-role family-disjoint check
  in `check_eval_disjoint()` operates on the per-role `family:`
  field and is invariant under provider rotation.
- **«All chain entries point at the same logical model identity»
  is a user-discipline constraint, NOT a validator-enforced one.**
  Slug strings vary legitimately across providers
  (`deepseek/deepseek-chat-v3` on OpenRouter,
  `accounts/fireworks/models/deepseek-v3` on Fireworks,
  `deepseek-v3` on Groq — all the same model weights); an exact-
  match validator would produce constant false positives. The
  config-load validator (§1) instead runs a **best-effort
  heuristic**: `extract_family(slug)` is applied to each chain
  entry's slug; if the result does not match the role's `family:`
  field, a WARNING row is emitted (not a hard error) suggesting
  the user verify the chain entry is on the same model identity.
  Honest documentation of this gap (rather than overclaiming
  validator coverage) is preferred — silently wrong validators
  hide bugs longer than honest «user discipline» rules.
- **LLM-using hook family-disjoint rule (ADR-7 §Amendment 2026-05-20
  rule 4)** is unaffected: when a future hook makes its own LLM
  call, it has its own role-config with its own chain; its
  family is extracted from its own model identity, and the
  family-disjoint check at `HookRegistry.register()` time compares
  it to the acting-role's family. Provider fallback is internal to
  one logical role and does not surface to the family check at all.

## §8 Out of scope

Documented explicitly so future PRs do not re-litigate each:

1. **Cross-MODEL auto-fallback** (e.g. `deepseek-v3` chain exhausted
   → auto-switch to `kimi-k2`). Conflicts with ADR-2 §Decision
   «no cross-tier auto-escalation»; the user must explicitly switch
   model identity if all chain entries exhausted (deliberate
   loud-failure path).
2. **TLS fingerprint stealth / JA3-JA4 spoofing** (OmniRoute pattern).
   Considered and rejected on ethical grounds — FA does not spoof
   transport identity to evade provider rate limits. Documented
   in [survey §6 R-6](../research/provider-client-survey-2026-05.md#r-6--explicit-out-of-scope-list-cost-cheap).
3. **Streaming responses** (ADR-7 §1 «non-streaming only»). Chain
   semantics for streaming are a v0.2 amendment slot — a chain
   entry that switches mid-stream is a stateful problem far beyond
   non-streaming chain semantics.
4. **OTel tracing spans** for provider calls. Deferred to UC5+; FA
   `events.jsonl` covers the «cheap-read trace» niche in v0.1.
5. **Persistent cooldown state across sessions** (survey Q-1 deferred).
   Cooldown rows are in-memory only; process restart clears state.
6. **Per-entry round-robin load balancing across non-cooled entries**
   (survey Q-3 deferred). Strict declared-order is the v0.1 default.
7. **GoModel `fallback/resolver.go` arena-ranking pattern** — auto-
   picks fallback candidates from `chatbot_arena_coding` /
   `chatbot_arena_math` preference lists. This is **cross-MODEL
   auto-escalation** (different model identities), conflicts with
   point 1 above.
8. **LiteLLM failure-percent-threshold cooldown** —
   `DEFAULT_FAILURE_THRESHOLD_PERCENT` + minimum-request count.
   Mis-fit for UC1 low-volume traffic; FA cools down on a single
   transient failure per §3.

## §9 Future amendments slot (β shape and others)

- **β shape: shared named chains referenced by role.** Top-level
  `chains:` block in `~/.fa/models.yaml` defines named chains
  (`deepseek-v3-cheap-chain: [...]`), roles reference via
  `chain_ref: deepseek-v3-cheap-chain`. Deferred YAGNI — per-role
  declaration is simpler for the weaker-OSS-LLM target audience
  and the second consumer doesn't exist yet. Slot reserved here
  so future PRs can land this as a non-breaking amendment.
- **Q-1: Persistent cooldown state (survey Q-1).** Persist cooldown
  rows to SQLite (reuse ADR-4 FTS5 backend); reduces cold-start
  re-hit-rate-limit churn on session restart. Cost ~30 LOC +
  schema migration; revisit after T-2 lands and we have telemetry
  on crash-recovery patterns.
- **Q-2: Httpx-retry-per-entry default tuning + pre-call
  `tiktoken` token estimation (survey Q-2).** Default
  v0.1 = 1 transport retry per chain entry; revisit if telemetry
  shows >5% of cooldowns are transient single-retry-fixable noise.
  Pre-call token estimation lands here when pricing-table-miss
  telemetry justifies (§4 cost+token accounting).
- **Q-3: Round-robin within non-cooled entries (survey Q-3).**
  Default v0.1 = strict declared-order; round-robin spreads load
  across non-cooled entries which extends usable hours per day
  for free-tier daily quotas. Revisit if UC1 telemetry shows
  daily-quota exhaustion patterns.
- **Q-4: Provider-wide cooldown when N≥2 slugs concurrently
  cooling.** Currently each `(provider, slug)` cools independently;
  if multiple slugs from the same provider hit transient failure
  in quick succession, signal points at the provider rather than
  individual slugs. Cooling the provider as a whole avoids
  thrashing through cooling slugs one-by-one. Defer until telemetry
  shows provider-wide-outage patterns (rare for production-tier
  providers, more common for free-tier).
- **Q-5: Anthropic prompt caching preservation across fallback.**
  Anthropic's `cache_control` blocks yield ~10x cost reduction on
  repeated context; falling through from Anthropic to a non-
  Anthropic provider loses the cache. Cost issue, not correctness;
  revisit if telemetry shows cache-eligible repeated context >30%
  of Anthropic-served calls. Possible designs: pin Anthropic-with-
  cache first; flag cache-eligible calls with a hint to never
  fall back (lose resilience, save cost).
- **Q-6: Reasoning-model request-parameter translation table.**
  When reasoning models (OpenAI o-series, Anthropic extended-
  thinking, future DeepSeek-R-like models) land in v0.1+ default
  chains, the per-adapter translation table from FA-canonical
  params (`max_tokens`, `temperature`, ...) to provider-native
  params (`max_completion_tokens`, `reasoning_effort`, `thinking`)
  needs a structured shape. v0.1 default has none; landing this is
  the «I added a reasoning model to a chain» trigger.
- **Q-7: Per-model timeout overrides.** v0.1 uses `timeout_seconds`
  per chain entry; reasoning models can legitimately need 10+ min
  on hard problems. A per-(provider, slug) timeout-override map
  may be cleaner than per-entry overrides if multiple roles share
  a slow model.
- **Streaming chain semantics** — when ADR-7 §1 «non-streaming
  only» is relaxed in v0.2. **NOTE: streaming will require a
  redesign, not just an amendment.** Mid-stream provider switching
  is impossible without buffering complete responses; the chain
  pattern as designed is fundamentally non-streaming. Likely
  v0.2 path: streaming roles bypass the chain (single provider,
  no fallback) or buffer-then-stream (defeats latency benefit
  of streaming). Decision deferred to v0.2 ADR-N.

## §10 Re-evaluation triggers

This ADR is re-opened (amended or replaced) when any of:

1. **A second consumer of named chains appears** — the moment a
   chain shape gets duplicated across two roles in
   `~/.fa/models.yaml`, β shape (top-level `chains:` block) is
   the right amendment slot.
2. **A future hook in `src/fa/inner_loop/hooks/` starts issuing its
   own LLM calls** — the family-disjoint check at
   `HookRegistry.register()` time (ADR-7 §Amendment 2026-05-20
   rule 4) becomes load-bearing for that hook; ADR-9 §7
   family-disjoint constraint preservation needs revisiting to
   confirm the hook's chain shape inherits the same invariants.
3. **Provider list expands past ~10 chain entries per role** — at
   that scale, the strict declared-order default (§9 Q-3) creates
   load-balancing inefficiency; round-robin amendment is the
   right next step.
4. **OTel becomes UC5 requirement** — tier-1 observability schema
   in §4 may need an OTel-compatible trace_id / span_id surface
   (the `logical_call_id` uuid is the right pre-amendment anchor).
5. **Mid-stream provider switching becomes a v0.2 requirement
   alongside ADR-7 §1 streaming-mode landing** — full §9 streaming
   redesign (not amendment; see §9 streaming note).
6. **awesome-free-llm-apis updates the canonical example slugs or
   base_urls** in survey Appendix A become stale — re-fetch and
   amend `~/.fa/models.yaml.example`.
7. **First reasoning model lands in a default chain** — triggers
   §9 Q-6 (per-model request-parameter translation table) and
   possibly Q-7 (per-model timeout override) as same-PR work.
8. **Pricing-table-miss telemetry shows >5% of `llm_call` rows
   carry `cost_usd: null`** — triggers §9 Q-2 second half
   (pre-call `tiktoken` estimation as fallback).

## Consequences

- **Positive:**
  - T-2 implementation has a complete, audit-evidenced contract;
    PR scope ~380 LOC.
  - Free-tier resilience is the v0.1 default, not an opt-in via
    external dependency.
  - Adding a new OpenAI-compatible provider = 1 PR row in
    `PROVIDERS` dict + user's YAML row, no FA-side new file.
  - Chain shape subsumes Option C gateway delegation (single
    chain entry pointing at `http://localhost:8080/v1`).
  - Cross-source convergence (8 OSS sources, see survey §4.2)
    means FA is adopting industry-standard shape; future-agent
    intuition matches OSS prior art.
- **Negative:**
  - ~50 LOC of chain-bookkeeping in `chain.py` that B2 doesn't
    need.
  - User must explicitly enumerate chain entries per role; no
    auto-discovery (deliberate, per §8 point 7 anti-pattern).
  - In-memory cooldown state means session restart loses
    information about which providers were rate-limited last;
    survey Q-1 amendment slot reserved.
- **Follow-up work this unlocks or requires:**
  - T-2 PR implementing `src/fa/providers/{base,chain,openai_compat,anthropic,registry,errors}.py`
    + `src/fa/observability/cost_table.py` (pricing-lookup seed).
  - `~/.fa/models.yaml.example` updated with the chain shape per
    §1.
  - `glossary.md` rows for `chain` / `cooldown row` /
    `logical call ID` / `OpenAI-compatible provider` / `Anthropic-
    native provider` / `response normalization` / `request-shape
    failure` / `transient failure`.
  - `BACKLOG.md` item `M-4` tracking the T-2 implementation PR
    with explicit back-reference to this ADR + the §1 chain shape;
    plus separate items for §9 Q-1..Q-7 amendments. (`M-2` /
    `M-3` are already taken by Wave-2 LoopGuard /
    FailureClassifier / attempt_history and Wave-2 pre-tool
    BlockerMiddleware + DSV YAML respectively; `M-4` is the next
    free milestone slot.)
  - HANDOFF.md §Current state ADR list updated with ADR-9 row.
  - DIGEST.md row added for ADR-9.

## Prior Art

Per [AGENTS.md §Cross-project anti-patterns rule
#4](../../AGENTS.md#cross-project-anti-patterns---learnt-from-precedents) (forward-only
from 2026-05-20). Each prior-art entry maps a design choice in
this ADR to an existing project / paper / FA prior decision, so
reviewers can verify FA is not re-inventing. Full audit evidence
lives in the companion
[provider-client-survey-2026-05.md](../research/provider-client-survey-2026-05.md);
this section condenses the eight per-design-choice mappings into
one readable block.

- **§1 per-role explicit chain config shape (`{model, family,
  chain: [...]}`):** dpc-messenger ADR-002 `AbstractLLMProvider`
  ABC + 5 provider files
  ([`dpc-messenger-inspiration-2026-05.md`](../research/dpc-messenger-inspiration-2026-05.md)) —
  closest Python parallel to FA's per-role chain shape; LiteLLM
  `model_list:` per-`model_name` deployment list
  ([`provider-client-survey-2026-05.md`](../research/provider-client-survey-2026-05.md) §4.1).
  α-shape (no shared named chains) inherits from the survey §0
  R-1 verdict; not lifted verbatim from any single source.
- **§2 ordered-fallback runtime semantics + 4xx split + typed
  errors:** GoModel `internal/llmclient/client.go::call()`
  (Hooks Protocol + per-attempt status handling) + LiteLLM
  `router_utils/fallback_event_handlers.py` (fallback dispatch
  pattern). The 401/403-continue-chain vs 400/422-fail-fast
  split is FA-specific (added during pre-PR critical pass; no
  audited OSS source documents the split explicitly — most
  treat all 4xx as auth-class errors). Typed errors
  (`ProviderRequestShapeError` / `ProviderChainExhaustedError`)
  follow ADR-8 §3 `ConfigurationError` pattern + AGENTS.md PR
  Checklist rule #10 «could-this-be-a-deterministic-Python-
  function» — explicit error types are the deterministic
  classification.
- **§3 per-`(provider, slug)` cooldown + adaptive Retry-After:**
  LiteLLM `router_utils/cooldown_cache.py::CooldownCacheValue`
  TypedDict (`{exception_received, status_code, timestamp,
  cooldown_time}`) is the direct Python lift target —
  per-deployment-keyed indexing matches FA's per-tuple key.
  kronos `llm.py::PEER_REACTION_COOLDOWN = 300` is the
  «5-min fixed default» anchor
  ([`kronos-agent-os-inspiration-2026-05.md`](../research/kronos-agent-os-inspiration-2026-05.md)).
  RFC 9110 `Retry-After` header parsing is web-standards prior
  art (no per-source citation needed; the `max(now +
  cooldown_seconds, parsed_retry_after)` floor-from-config
  composition rule is FA-specific).
- **§4 three-tier observability + shared `logical_call_id`:**
  GoModel `Hooks{OnRequestStart, OnRequestEnd}` Protocol maps
  1:1 to FA's existing `BEFORE_LLM_CALL` / `AFTER_LLM_CALL`
  (see survey §4.5). The `logical_call_id` UUID4 correlation
  surface is FA-specific (added during pre-PR critical pass
  closing P0 #3 finding); no audited OSS source uses a single
  ID across tier-1/2/3 trace surfaces explicitly. Tier-3
  `FA_DEBUG_LLM_BODIES=1` gating mirrors ADR-7 §1 «traces
  separate from agent state» discipline.
- **§5 two-category adapter split (`OpenAICompatProvider` +
  `AnthropicProvider`) + response normalization:** Bifrost
  `core/providers/{openai,anthropic,...}/` Category-1 /
  Category-2 split is the independent-convergence anchor
  (survey §4.6). 6 of 7 audited sources implement a shared
  OpenAI-compat handler (survey §4.3); FA matches the majority
  pattern. Canonical `ResponseInfo` with provider-specific
  `extras: dict[str, Any]` follows Postel's-Law (cited
  generically as web-protocol design rather than a single
  source).
- **§6 reserved-key collisions fail-fast as
  `ReservedProviderError`:** Bifrost
  `BlockRestrictedWrites()` reserved-context-keys pattern
  ([survey §0 R-5](../research/provider-client-survey-2026-05.md))
  — FA adapts the «reserved namespace exists» concept but
  inverts the «silent drop» mechanism to «fail at registration»,
  matching ADR-8 §3 `ConfigurationError` for duplicate hook
  names + FA AGENTS.md «default-deny + explicit failure»
  principle.
- **§7 family-disjoint preservation + best-effort
  `extract_family()` warning:** ADR-2 §Amendment 2026-05-20 +
  ADR-7 §Amendment 2026-05-20 rule 4 (family-disjoint rule is
  FA-internal prior art, not OSS-borrowed; correlated-llm-
  errors note §10 R-9 supplies the underlying paper-backed
  rationale). The §7 reframe of «exact-match validator → best-
  effort warning» is FA-specific (added during pre-PR critical
  pass closing P0 #4 finding — slug strings vary legitimately
  across providers, so exact-match infeasible). No OSS source
  audited documents the slug-variance failure mode because
  none enforces cross-platform family identity to begin with.
- **§8 out-of-scope rejections:** Cross-MODEL auto-escalation
  rejected per ADR-2 §Decision; GoModel
  `fallback/resolver.go::ArenaRanked` is the rejected anti-
  pattern. TLS-fingerprint stealth / JA3-JA4 spoofing rejected
  on ethical grounds (OmniRoute pattern; survey §0 R-6).
  Streaming chain semantics deferred until ADR-7 §1 «non-
  streaming only» relaxes in v0.2 (FA-internal prior art, not
  OSS-borrowed).

## References

- Companion survey: [`knowledge/research/provider-client-survey-2026-05.md`](../research/provider-client-survey-2026-05.md) — audit evidence for all decisions in this ADR.
- [ADR-2 — LLM tiering](./ADR-2-llm-tiering.md) — Role/tier mapping; «no cross-tier auto-escalation»; Amendment 2026-05-20 family-disjoint rule (rationale + slug-extraction; sub-amendment 2026-05-21 role-layer enforcement).
- [ADR-6 — Tool sandbox](./ADR-6-tool-sandbox-allow-list.md) — LLM call is NOT a tool call (LLM calls bypass tool sandbox; tool sandbox boundary is the chain's *upstream* concern).
- [ADR-7 — Inner-loop & tool-registry contract](./ADR-7-inner-loop-tool-registry.md) — §Amendment 2026-05-20: retry-budget invariant rule 1, intra-role T=1.0 rule 3, LLM-using-hook family-disjoint rule 4. Provider-level transport retries (httpx) MUST NOT count against the loop-level retry budget — two separate counters.
- [ADR-8 — HookRegistry middleware chain](./ADR-8-hook-registry.md) — `BEFORE_LLM_CALL` / `AFTER_LLM_CALL` lifecycle points; `GuardMiddleware` / `ObserverMiddleware` shapes; `revalidates_after_modify` carve-out (not applicable to T-2 provider client; documented for completeness).
- [Cost Guardian (R-45)](../research/borrow-roadmap-2026-05.md) §R-45 + `src/fa/observability/cost_guardian.py` — `cost=…` artifact emission contract: T-2 emits `cost=USD` rows that `CostGuardian` accumulates and gates on.
- [`correlated-llm-errors-and-ensembling-2026-05.md`](../research/correlated-llm-errors-and-ensembling-2026-05.md) §10 R-9 — LLM-using hooks satisfy `family ≠ acting-role` constraint; preserved under ADR-9 §7.
- [`kronos-agent-os-inspiration-2026-05.md`](../research/kronos-agent-os-inspiration-2026-05.md) — `kronos/llm.py` 623 LOC per-provider 5-min cooldown; the «cooldown idea» is what's portable, not the full provider chain machinery.
- [`dpc-messenger-inspiration-2026-05.md`](../research/dpc-messenger-inspiration-2026-05.md) — ADR-002 `AbstractLLMProvider` ABC; 3074-LOC monolith → 5 provider files; closest Python parallel to FA Option D adapter split.
- [GoModel](https://github.com/ENTERPILOT/GoModel) — `internal/llmclient/{client,circuit_breaker}.go`; `Hooks{OnRequestStart, OnRequestEnd}` Protocol; cited as primary architectural validator. Cross-MODEL `fallback/resolver.go` arena-ranking pattern explicitly rejected (§8 point 7).
- [LiteLLM](https://github.com/BerriAI/litellm) — `litellm/router_utils/{cooldown_cache,cooldown_handlers,fallback_event_handlers}.py`; `CooldownCacheValue` TypedDict is the direct lift target for FA's cooldown row schema (§3).
- [Bifrost](https://github.com/maximhq/bifrost) — `core/providers/{openai,anthropic,groq,...}/` Category-1/2 split; independent convergence on Option D adapter pattern. Reserved-context-keys pattern adapted with fail-fast semantics (§6).
- [9router](https://github.com/decolua/9router) — 3-tier cascade (Subscription → Cheap → Free); cross-platform fallback as a UX-visible product validates the user reframe (chat 2026-05-22).
- [Portkey gateway](https://github.com/Portkey-AI/gateway) — `src/providers/<name>/{api,chatComplete,embed}.ts`; modular per-provider directory pattern cited as MEDIUM-priority cross-reference.
- [OmniRoute](https://github.com/diegosouzapw/OmniRoute) — 14 routing strategies + `BaseExecutor`+override pattern; cited as «over-engineered comparator» showing what Option D consciously omits.
- [awesome-free-llm-apis](https://github.com/mnfst/awesome-free-llm-apis) — provider inventory (slugs, base URLs, free-tier quotas); data source for `~/.fa/models.yaml.example` chain blocks.
