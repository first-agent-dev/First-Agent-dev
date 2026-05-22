---
title: "Provider-client survey — OSS landscape audit for ADR-9 (T-2 LLM driver)"
source:
  - "knowledge/research/kronos-agent-os-inspiration-2026-05.md"
  - "knowledge/research/dpc-messenger-inspiration-2026-05.md"
  - "knowledge/research/correlated-llm-errors-and-ensembling-2026-05.md"
  - "https://github.com/ENTERPILOT/GoModel"
  - "https://github.com/BerriAI/litellm"
  - "https://github.com/maximhq/bifrost"
  - "https://github.com/decolua/9router"
  - "https://github.com/Portkey-AI/gateway"
  - "https://github.com/diegosouzapw/OmniRoute"
  - "https://github.com/mnfst/awesome-free-llm-apis"
compiled: "2026-05-22"
goal_lens: "Audit OSS provider-client / AI-gateway landscape для ADR-9 (T-2 driver), validate proposed Option D + α (per-role explicit provider chain с cooldown) против 8 independent OSS implementations; identify pattern-convergence, anti-patterns, и LOC-budget anchors."
chain_of_custody: |
  Кросс-проверка 4 primary architectural sources (GoModel ADRs + llmclient; LiteLLM
  router_utils; Bifrost AGENTS.md + provider categories; kronos llm.py 623 LOC) +
  4 cross-reference sources (9router README + 3-tier cascade; Portkey provider
  modules; OmniRoute 14 routing strategies; dpc-messenger ADR-002 AbstractLLMProvider)
  + 1 data source (awesome-free-llm-apis для concrete provider slugs). Все
  primary sources fetched 2026-05-22; GitHub URLs указывают на live repos
  (no version pin — статус-quo at compile date). Russian primary prose per
  AGENTS.md §Conventions; English identifiers (file paths, ADR refs, LOC counts,
  function names, YAML keys) preserved as search anchors.
tier: stable
links: []
mentions: []
confidence: extracted
claims_requiring_verification:
  - "LiteLLM router.py 11750 LOC + main.py 7966 LOC — counted via `wc -l` 2026-05-22; subject to upstream drift."
  - "GoModel ~72k LOC — estimated from earlier audit, not re-counted at compile date."
  - "Bifrost «~11µs overhead at 5k RPS» — vendor claim в AGENTS.md, not independently benchmarked."
  - "9router «20-40% token savings via RTK» — vendor claim в README, not independently verified."
---

> **Status:** active. Note produced via
> [`knowledge/prompts/research-briefing.md`](../prompts/research-briefing.md)
> Stage-2 hybrid format (audit + research note, per Q1 = (C) hybrid
> decision locked in chat 2026-05-22).
>
> §0 below is the Decision Briefing intended for the project lead and
> для future LLM agents читающих ноту с топа. Mirrors the chat-handover
> the agent posted at session end. §1.. — deep-dive sections; load them
> only when §0 insufficient.
>
> **Purpose.** Input note for [ADR-9 — LLM provider
> client](../adr/ADR-9-llm-provider-client.md). Cited by ADR-9 §Context
> as the audit evidence; ADR-9 lifts the Decision Briefing's R-1
> verdict (Option D + α) into §Accepted decision.

## 0. Decision Briefing

### R-1 — Lock Option D + α (per-role explicit provider chain with cooldown)

- **What:** T-2 driver implements per-role ordered provider chain in
  `~/.fa/models.yaml`; each chain entry carries `{provider, slug,
  base_url, api_key_env}`. On transient failure (429 / 5xx / network),
  put failed entry into 5-min cooldown и try next entry. Same model
  identity across all chain entries; provider platform varies
  (OpenRouter → Fireworks → NVIDIA Build → Groq). Per-role α-shape
  (no shared named chains в v0.1).
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~380 LOC FA-resident vs ~500
    LOC B3-style full-pattern lift saves ~120 LOC of future-agent
    reading burden)
  - (B) helps LLM find context when needed: YES (chain-shape explicit
    в YAML; weaker OSS LLMs reason over visible config rather than
    inferred provider-resolver logic)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "Audit OSS provider-client / AI-gateway
    landscape для ADR-9 (T-2 driver), validate proposed Option D + α
    против 8 independent OSS implementations": YES — все 8 sources
    independently converge на «per-provider cooldown + ordered fallback
    chain + isolated provider workers» shape; FA Option D — well-trodden
    industry pattern, not novel design.
- **Cost:** medium (1–4h drafting; T-2 implementation itself ~380 LOC = M2-tier PR).
- **Verdict:** TAKE.
- **Alternative-if-rejected:** Option C (B2 + base_url gateway delegation)
  — power users run GoModel container; FA codes ~330 LOC. Rejected because
  user reframe (cross-platform fallback for same model is the actual
  requirement) makes a gateway optional, not central — Option D supports
  the gateway path as a single chain entry (`chain: [{base_url:
  http://localhost:8080/v1, ...}]`) while delivering free-tier resilience
  out-of-the-box.
- **Concrete first step (if TAKE):**
  `knowledge/adr/ADR-9-llm-provider-client.md` (this PR) — Accepted
  decision = Option D + α; T-2 implementation PR follows referencing
  ADR-9.

### R-2 — Cooldown unit MUST be per-`(provider, slug)` tuple, not per-provider

- **What:** LiteLLM cools down per-`model_id` (deployment-level: each
  `model+provider+region` is a separate cooldown row). Kronos cools down
  per-provider (coarser). FA picks per-`(provider, slug)` — finer than
  kronos/dpc-messenger, coarser than LiteLLM, defensible by analogy to
  LiteLLM's pattern. Justification: same provider may host the same
  model multiple times (e.g. OpenRouter routes to multiple upstream
  Fireworks instances); a single instance going 503 should not cool
  down the entire OpenRouter platform for that role.
- **Project-axis fit:** (A) YES (avoids spurious full-provider cooldowns
  that would force the role to skip 50+ healthy slugs); (B) YES
  (cooldown rows keyed by tuple — easy для agent to grep `cooldown` rows
  in `events.jsonl` and answer «why is openrouter:deepseek-v3 in
  cooldown but openrouter:kimi-k2 healthy?»).
- **Goal-fit:** YES (cross-source pattern: LiteLLM's `CooldownCacheValue
  {exception_received, status_code, timestamp, cooldown_time}` schema
  is the canonical Python reference shape; tuple-keyed indexing matches
  it exactly).
- **Cost:** cheap (decision documented in ADR-9 §Cooldown semantics; no
  per-source LOC cost vs simpler per-provider scheme).
- **Verdict:** TAKE.
- **Alternative-if-rejected:** Per-provider cooldown (kronos pattern).
  Rejected because real free-tier deployments multiplex multiple slugs
  через one provider; a single rate-limited slug shouldn't bench the
  entire provider for that role.
- **Concrete first step:** ADR-9 §Cooldown semantics specifies tuple
  key + 5-min default + cooldown-row schema; T-2 implementation grounds
  the spec in `src/fa/providers/chain.py`.

### R-3 — Observability tiers: always-on (1 row per logical call) + error-trace fire + debug-bodies opt-in

- **What:** Three-tier observability как proposed in chat 2026-05-22.
  Tier 1 (always-on): single `llm_call` row в `events.jsonl` с full
  chain-attempt list inline (`chain: [{provider, status, ms, error}]`)
  + in/out tokens + cost — ~80 bytes per call. Tier 2 (error-trace,
  always on but fires only on failure): `llm_chain_exhausted` row
  emitted на `RuntimeError` после full chain exhaustion; consumed by
  existing `FailureClassifierObserver` from R-3 Wave-2 stack. Tier 3
  (debug, opt-in via `FA_DEBUG_LLM_BODIES=1`): separate `llm_bodies.jsonl`
  с full request/response bodies (gitignored, 5-50 KB per call).
- **Project-axis fit:** (A) YES (default observability stays at ~80
  bytes/call — adds <1% to existing events.jsonl footprint per UC1
  session); (B) YES (chain-attempt list is the answer to «which
  platform is unreliable on which days» without grepping multi-row
  sequences).
- **Goal-fit:** YES (cross-source pattern: GoModel `Hooks{
  OnRequestStart, OnRequestEnd }` → FA's BEFORE/AFTER_LLM_CALL maps
  directly; LiteLLM's `cooldown_callbacks.py` is the same shape with
  more middleware seats; user's chat reframe explicitly named «debug
  info for each call» as over-spec'd, so tier 3 stays opt-in).
- **Cost:** cheap (single `ObserverMiddleware` attached to
  `AFTER_LLM_CALL` + retry-handler bumps `llm_chain_exhausted` row;
  ~80 LOC including bodies-export gating).
- **Verdict:** TAKE.
- **Alternative-if-rejected:** OTel spans (provider-call as one span,
  retry-attempts as child spans). Rejected because OTel is UC5+ scope
  per ADR-7 §1 «non-streaming only» + ADR-9 §Out of scope; FA's
  `events.jsonl` already covers the «cheap-read trace» niche.
- **Concrete first step:** ADR-9 §Observability defines three tiers
  + JSON schema for `llm_call` and `llm_chain_exhausted` rows; T-2
  implementation lands the observer (~80 LOC) under
  `src/fa/inner_loop/hooks/llm_observers.py`.

### R-4 — Two-category provider adapter split (OpenAI-compatible vs Anthropic-native)

- **What:** Bifrost's «Category 1: non-OpenAI-compatible (Anthropic,
  Bedrock, Gemini)» vs «Category 2: OpenAI-compatible (Groq, Cerebras,
  Ollama, Perplexity, OpenRouter, xAI)» split — Category 2 providers
  delegate to a single shared OpenAI handler. FA Option D's
  `openai_compat.py` + `anthropic.py` split is exactly this pattern,
  arrived at independently. Survey makes the convergence explicit
  rather than re-deriving it.
- **Project-axis fit:** (A) YES (one ~80-LOC adapter covers 4-5
  platforms; new OpenAI-compat platform = one row in `PROVIDERS` dict
  + one config row in `~/.fa/models.yaml`); (B) YES (split lives in
  `src/fa/providers/registry.py` as a 6-row dict — instantly readable
  by weaker OSS LLMs).
- **Goal-fit:** YES (cross-source pattern: Bifrost Category-1/Category-2,
  LiteLLM `llms/{provider}/` with shared transformation classes for
  OpenAI-compat providers, Portkey gateway `src/providers/<name>/`
  with `api.ts` + `chatComplete.ts` per provider — all three converge
  на the same modular split).
- **Cost:** cheap (already baked into Option D LOC budget; just citing
  prior art in ADR-9 §Adapter pattern).
- **Verdict:** TAKE.
- **Alternative-if-rejected:** One adapter per provider, no shared
  OpenAI-compat base. Rejected because most new platforms (Modal,
  Lambda Labs, Together AI, ...) are OpenAI-compat by design; cloning
  the same 70-LOC adapter 6 times is the maintenance burden the split
  exists to prevent.
- **Concrete first step:** ADR-9 §Adapter pattern explicitly cites
  Bifrost as the convergence anchor; T-2 implementation lands
  `src/fa/providers/openai_compat.py` (~80 LOC) + `anthropic.py`
  (~70 LOC) + `registry.py` (~30 LOC).

### R-5 — Reserved-key collisions fail fast (anti-pattern from Bifrost)

- **What:** Bifrost's `BlockRestrictedWrites()` silently drops writes
  to reserved context keys (`BifrostContextKeyNumberOfRetries`,
  `BifrostContextKeyFallbackIndex`, ...). Silent drops conflict with
  FA AGENTS.md «default-deny + explicit failure» principle. ADR-9
  specifies: any attempt to register a chain entry whose `provider`
  key collides with a reserved name (e.g. `__internal__`, `__metadata__`)
  MUST raise `ConfigurationError` at registration time — same shape
  as ADR-8 HookRegistry rejecting duplicate hook names.
- **Project-axis fit:** (A) YES (one explicit `ConfigurationError` at
  config-load time saves N debug-session messages «why does chain
  entry #3 do nothing»); (B) YES (failure-mode lives in one place —
  `src/fa/providers/chain.py::ChainConfig.validate()` — easy to grep).
- **Goal-fit:** YES (FA-specific adaptation: cross-source pattern is
  «reserved namespace exists», FA tightens it from «silently dropped»
  to «fail at registration»; matches ADR-8 §3 ConfigurationError
  pattern for duplicate hook names).
- **Cost:** cheap (5-LOC change to chain config validator; one new
  error class).
- **Verdict:** TAKE.
- **Alternative-if-rejected:** Bifrost's silent-drop pattern.
  Rejected per AGENTS.md PR Checklist rule #10 «could this be a
  deterministic Python function» — explicit fail-fast IS the
  deterministic check; silent drop is the LLM-trap that produces
  «mysterious empty chain» symptoms agents will fail to debug.
- **Concrete first step:** ADR-9 §Reserved-key semantics; T-2 lands
  `ChainConfig.validate()` + `ReservedProviderError` (subclass of
  `ConfigurationError`).

### R-6 — Explicit «out of scope» entries protect ADR-9 from scope creep

- **What:** ADR-9 §Out of scope MUST enumerate three rejected
  patterns:
  - **Cross-model auto-fallback** (B3 GoModel pattern; conflicts
    with ADR-2 «no cross-tier auto-escalation»).
  - **TLS fingerprint stealth / JA3-JA4 spoofing** (OmniRoute
    pattern; provider-ToS violation, not resilience).
  - **Streaming responses в v0.1** (ADR-7 §1 «non-streaming only»);
    chain semantics for streaming are a v0.2 amendment slot.
- **Project-axis fit:** (A) YES (explicit rejection list saves future
  PRs from re-litigating each); (B) YES (search «out of scope» in
  ADR-9 surfaces the three lines instantly).
- **Goal-fit:** YES (audit identified 2 anti-patterns + 1 deferred
  v0.2 feature explicitly; documenting them as «considered and
  rejected» mirrors the exploration_log discipline at the ADR layer).
- **Cost:** cheap (three short paragraphs in ADR-9 §Out of scope).
- **Verdict:** TAKE.
- **Alternative-if-rejected:** Leave them undocumented. Rejected
  because the «explicit-rejection» branch of the exploration_log
  exists precisely to prevent rejected alternatives from re-emerging
  in future PRs.
- **Concrete first step:** ADR-9 §Out of scope (three bullets).

### Summary

| R-N | Verdict | Project-fit (A / B) | Goal-fit (C) | Cost | Alternative-if-rejected | User decision needed? |
|-----|---------|---------------------|--------------|------|--------------------------|------------------------|
| R-1 | TAKE | YES / YES | YES (Option D locked) | medium | Option C base_url-gateway delegation | No (locked in chat 2026-05-22) |
| R-2 | TAKE | YES / YES | YES (per-tuple cooldown) | cheap | Per-provider cooldown (kronos) | No (cross-source convergence) |
| R-3 | TAKE | YES / YES | YES (3-tier observability) | cheap | OTel spans | No (locked in chat 2026-05-22) |
| R-4 | TAKE | YES / YES | YES (adapter split) | cheap | Per-provider adapter | No (cross-source convergence) |
| R-5 | TAKE | YES / YES | YES (fail-fast vs silent-drop) | cheap | Bifrost silent-drop | No (matches ADR-8 §3) |
| R-6 | TAKE | YES / YES | YES (out-of-scope explicit) | cheap | Leave undocumented | No (mirrors exploration_log) |

## 1. TL;DR

- **Option D + α — per-role explicit provider chain with cooldown — is
  the well-trodden industry pattern, not novel design.** All 8 in-scope
  sources independently converge on three pieces: per-provider (or
  finer) cooldown after failure + ordered fallback chain + isolated
  per-provider state.
- **LiteLLM is the canonical Python reference for the shape FA needs**;
  `router_utils/cooldown_cache.py` defines `CooldownCacheValue`
  TypedDict with `{exception_received, status_code, timestamp,
  cooldown_time}` — direct lift target for FA's cooldown row schema.
- **Bifrost's Category-1 / Category-2 provider split confirms FA's
  Option D `openai_compat.py` + `anthropic.py` adapter split** as
  independently-derived correct shape (not just FA whim).
- **GoModel's `Hooks{ OnRequestStart, OnRequestEnd }` Protocol maps
  1:1 to FA's existing HookRegistry BEFORE/AFTER_LLM_CALL lifecycle
  points** — Option D wires into the existing substrate cleanly, no
  new dispatcher needed.
- **9router proves the 3-tier free-tier cascade is mainstream enough
  to be a product's headline feature**, validating the user reframe
  that cross-platform fallback for the same model is the actual
  requirement (not cross-MODEL fallback that ADR-2 forbids).
- **Three anti-patterns documented and rejected:** LiteLLM's
  failure-percent-threshold cooldown (UC1 traffic too low), Bifrost's
  silent-drop reserved-key writes (conflicts with default-deny), and
  OmniRoute's TLS fingerprint stealth (provider-ToS violation).
- **FA Option D's LOC budget ~380 lands between B2 (~350) and B3
  (~500)**, mostly because the Anthropic-native adapter adds ~70 LOC
  that OpenAI-compat-only deployments would skip. Add-a-platform =
  1 line in `PROVIDERS` dict + 1 YAML row for OpenAI-compat
  platforms; 1 new adapter file (~70 LOC) for Anthropic-shape
  platforms.

## 2. Scope, метод

**In scope:** Audit 8 OSS provider-client / AI-gateway implementations
для validation of Option D + α as the T-2 driver shape. Sources span
3 languages (Python, Go, TypeScript/JavaScript) and 2 deployment models
(library-in-process vs gateway-as-container).

**Out of scope:** Streaming-response chain semantics (ADR-7 §1
non-streaming-only); OTel tracing (UC5+ deferred); cross-MODEL
auto-fallback (ADR-2 «no cross-tier auto-escalation»); TLS-fingerprint
stealth (provider-ToS violation, anti-pattern).

**Method:** Cross-reference audit с triage (HIGH = deepdive into key
files; MEDIUM = one-pass cross-ref; LOW = one-line out-of-scope entry).
Triage criteria: relevance to Option D pattern (per-role chain +
cooldown + observability). Each source contributes either pattern
confirmation, anti-pattern flag, or both.

**Goal-lens (verbatim):** «Audit OSS provider-client / AI-gateway
landscape для ADR-9 (T-2 driver), validate proposed Option D + α
(per-role explicit provider chain с cooldown) против 8 independent
OSS implementations; identify pattern-convergence, anti-patterns, и
LOC-budget anchors».

## 3. Key concepts (source-language terms)

- **Provider** — A logical inference platform (OpenRouter, Fireworks,
  NVIDIA Build, Groq, GitHub Models, Anthropic, Modal, ...). In FA
  Option D, one entry в `PROVIDERS` dict.
- **Slug** — Provider-specific model identifier (`deepseek/deepseek-chat-v3`,
  `accounts/fireworks/models/deepseek-v3`, `deepseek-v3`). One model
  identity may have N slugs across N providers.
- **Cooldown** — Per-`(provider, slug)` timeout after a transient
  failure (429, 5xx, network); failed tuple is deprioritized for
  the next chain-resolution within the cooldown window. FA default:
  5 min, configurable per chain entry. Source: kronos `llm.py`
  pattern via dpc-messenger ADR-002.
- **Chain** — Ordered list of `(provider, slug, base_url, api_key_env)`
  tuples for one role. Source: GoModel `fallback/resolver.go`
  pattern, but explicit-config in FA (no auto-resolution from arena
  rankings).
- **Logical call** — Conceptual «role made one LLM call»; corresponds
  to N transport attempts where N = chain entries tried until success
  or exhaustion. Tier-1 observability emits one `llm_call` row per
  logical call, with `chain: [...]` carrying the N transport attempts
  inline.
- **OpenAI-compatible provider** — A provider that accepts POST
  `/v1/chat/completions` with the OpenAI request envelope. Examples:
  OpenRouter, Fireworks, Groq, NVIDIA Build, Together AI, Modal,
  Lambda Labs. In FA, all share `OpenAICompatProvider` adapter
  (~80 LOC).
- **Anthropic-native provider** — A provider that uses Anthropic's
  `/v1/messages` API shape (system prompt as separate field; tool
  use as block-shaped messages). FA adapts as `AnthropicProvider`
  (~70 LOC).
- **HookRegistry** — FA ADR-8 substrate; Option D wires into
  `BEFORE_LLM_CALL` (header injection / pre-call gating) and
  `AFTER_LLM_CALL` (cost/token observation; chain-attempt
  emission). Source: existing FA implementation, see ADR-8 + ADR-7
  §8.
- **Family-disjoint check** — ADR-2 §Amendment 2026-05-20 + ADR-7
  §Amendment 2026-05-20 rule 4. Per-role family extracted from the
  logical model identity (`deepseek-v3` → `deepseek` family), NOT
  from the provider platform. Provider fallback within same model
  = no family-disjoint risk (same model weights).

## 4. Mapping / analysis

### 4.1 Source triage matrix

| Repo | Category | Lines | Lang | Pattern verdict | LOC reference |
|---|---|---|---|---|---|
| GoModel (HIGH, primary) | Gateway+lib | ~72k | Go | Hooks Protocol + circuit breaker + fallback resolver + Category-1/2 split | `internal/llmclient/{client,circuit_breaker}.go` |
| LiteLLM (HIGH, primary) | Gateway+SDK | ~250k | Python | Cooldown-cache + fallback-event-handlers + per-deployment cooldown | `litellm/router_utils/{cooldown_cache,cooldown_handlers,fallback_event_handlers}.py` |
| Bifrost (HIGH, primary) | Gateway | ~110k | Go | Category-1/2 provider split + reserved-context-keys + provider isolation | `core/providers/{openai,anthropic,groq,...}/`, `core/schemas/context.go` |
| kronos (HIGH, prior audit) | Agent | ~10k | Python | Per-provider 5-min cooldown + provider-chain resolution | `kronos/llm.py` (623 LOC) |
| dpc-messenger (HIGH, prior audit) | Agent | ~20k | Python | `AbstractLLMProvider` ABC + 5 provider files + `get_state()` | dpc-messenger ADR-002 |
| 9router (HIGH, cross-ref) | Router | ~5k | Node | 3-tier cascade (Subscription → Cheap → Free) + per-tier quota tracking | npm package |
| Portkey (MEDIUM) | Gateway | ~50k | TypeScript | Modular `src/providers/<name>/{api,chatComplete,embed}.ts` | Hono-based |
| OmniRoute (MEDIUM) | Router | ~70k | Node | 14 routing strategies + `BaseExecutor`+override pattern | Next.js + Electron |
| awesome-free-llm-apis (DATA) | List | n/a | n/a | Provider inventory: slugs + base URLs + quotas | Markdown only |
| correlated-llm-errors (HIGH, FA-internal) | Note | ~1100 | n/a | R-9: LLM-using hooks satisfy `family ≠ acting-role` | `knowledge/research/correlated-llm-errors-and-ensembling-2026-05.md` §10 |
| Kong (REJECTED) | API gateway | ~200k | LuaJIT | Out of domain (generic L7) | — |
| plano (REJECTED) | Envoy filter | ~80k | Rust+TS | Out of domain (WASM filter + native binary, gateway-vs-client mismatch) | — |
| coai (REJECTED) | Chat UI | ~50k | Go | Out of layer (chat-format adapters, not transport resilience) | — |

### 4.2 Cross-source convergence on the «cooldown + chain + isolation» pattern

| Source | Cooldown unit | Cooldown mechanism | Fallback model |
|---|---|---|---|
| GoModel | per-provider | closed/open/half-open with single-probe | `fallback/resolver.go` arena-ranked candidates |
| LiteLLM | per-deployment (model+provider+region) | `CooldownCacheValue {exception_received, status_code, timestamp, cooldown_time}` | `fallback_event_handlers.py` config-driven |
| kronos | per-provider | fixed 5-min `PEER_REACTION_COOLDOWN = 300` | ordered list in role config |
| dpc-messenger | per-provider | `get_state()` runtime introspection | `AbstractLLMProvider` ABC + 5 concrete subclasses |
| 9router | per-tier (Sub / Cheap / Free) | quota-tracked + auto-fallback | 3-tier cascade |
| Bifrost | per-provider | isolated worker pool (channel-based async) | `BifrostContextKeyFallbackIndex` reserved key |
| Portkey | per-provider | config-driven via `conf.json` | Modular handlers |
| OmniRoute | per-(provider, model) | T5 intra-family + circuit breaker | 14 combo strategies |

→ **All 8 sources converge on the same three-piece pattern.**
Cooldown unit varies (per-provider in 4 sources, per-deployment in
LiteLLM, per-(provider, model) in OmniRoute, per-tier in 9router); FA
picks **per-`(provider, slug)`** which matches LiteLLM and OmniRoute
— finer than kronos / dpc-messenger / Bifrost / Portkey / GoModel /
9router. Justification per R-2.

→ **Pattern frequency:** 8/8 sources implement ordered fallback; 7/8
have explicit cooldown mechanism (9router uses quota-tracking as the
cooldown equivalent); 8/8 have some form of per-provider state
isolation (whether via worker pool, factory dispatch, or config
namespace).

### 4.3 Cross-source convergence on the adapter split (R-4)

| Source | Adapter pattern | Shared OpenAI handler? | New-platform cost |
|---|---|---|---|
| GoModel | `internal/providers/{openai,anthropic,groq,...}/` | Yes (Category-2 providers delegate) | 1 file (~100 LOC for native) or 1 row (for OpenAI-compat) |
| Bifrost | `core/providers/{openai,anthropic,groq,...}/` two-category | Yes (Category-2 in 50-LOC subdirs) | 1 file (Category 1) or 1 stub (Category 2) |
| LiteLLM | `litellm/llms/{provider}/` with `BaseConfig` inheritance | Partial (transformation classes inherit) | 1 directory with `transformation.py` + `cost_calculator.py` |
| Portkey | `src/providers/<name>/{api,chatComplete,embed}.ts` | No (each provider duplicates) | 1 directory с 3 files |
| dpc-messenger | `providers/{ollama,openai,anthropic,zai,whisper}.py` | Yes (`AbstractLLMProvider` ABC) | 1 file (subclass ABC) |
| OmniRoute | `BaseExecutor` + provider-specific overrides | Yes (`DefaultExecutor` для OpenAI-compat) | 1 file (override 2-3 methods) |
| 9router | Provider registry с config-driven dispatch | Yes (most via `providers/openrouter.js`) | 1 row + optional handler |

→ **6/7 sources implement a shared OpenAI-compat handler** (LiteLLM
inheritance, Bifrost Category-2 delegation, dpc-messenger ABC,
OmniRoute Default executor, 9router config registry, GoModel
delegation). Only Portkey duplicates per-provider. FA Option D
matches the 6-source majority pattern: shared `OpenAICompatProvider`
+ provider-specific Anthropic adapter.

### 4.4 LiteLLM `CooldownCacheValue` schema as direct lift target

From `/tmp/research/litellm/litellm/router_utils/cooldown_cache.py`:

```python
class CooldownCacheValue(TypedDict):
    exception_received: str
    status_code: str
    timestamp: float
    cooldown_time: float
```

FA Option D adapts this как `ChainEntryState` row written to
`events.jsonl` as part of the tier-1 `llm_call` row:

```python
@dataclass
class ChainAttemptRecord:
    provider: str         # "openrouter" | "fireworks" | ...
    slug: str             # "deepseek/deepseek-chat-v3" | ...
    status: int           # HTTP status if reached upstream; 0 for network failure
    error: str | None     # short error kind; "rate_limited" | "timeout" | None for success
    ms: float             # transport wallclock
```

The cooldown-row stays at `{provider, slug, started_at, expires_at,
trigger_error}` — keyed by tuple, deletable on success.

### 4.5 GoModel `Hooks` Protocol → FA HookRegistry mapping

From `/tmp/gomodel/internal/llmclient/client.go`:

```go
if c.config.Hooks.OnRequestStart != nil {
    scope.ctx = c.config.Hooks.OnRequestStart(scope.ctx, scope.requestInfo)
}
// ... HTTP call ...
if c.config.Hooks.OnRequestEnd != nil {
    c.config.Hooks.OnRequestEnd(scope.ctx, scope.requestInfo, scope.responseInfo)
}
```

FA mapping (no new ADR-8 lifecycle point needed):

| GoModel | FA HookRegistry lifecycle | Decision/Observer kind |
|---|---|---|
| `OnRequestStart` | `BEFORE_LLM_CALL` | Both — guards can deny/mutate headers; observers log |
| `OnRequestEnd` | `AFTER_LLM_CALL` | ObserverMiddleware only (cost + tokens + chain-attempt emission) |

→ T-2 provider client fires these two existing lifecycle points per
chain attempt. Cooldown bookkeeping is internal to `chain.py`
(doesn't fire a hook); it's a deterministic Python function per
AGENTS.md PR Checklist rule #10 question 4.

### 4.6 Bifrost provider isolation as scaling validator

Bifrost AGENTS.md (`/tmp/research/bifrost/AGENTS.md` §Design
Principles): «Each provider has its own worker pool and queue. One
provider going down doesn't cascade to others».

FA scope is far smaller (single-user UC1+UC3; one request at a time
per role; no worker pool needed). But the **principle generalizes**:
chain entries are isolated state — failure of one entry must not
poison sibling entries' cooldown state, retry counters, or token
budgets. FA implementation: `ChainEntryState` per tuple, no cross-
tuple references.

→ Citable in ADR-9 §Isolation invariant as «scaling-tested precedent
(Bifrost ~5k RPS)» despite FA's much smaller scope; the same
invariant supports future scale-up.

## 5. Risks and caveats

- **GoModel's `fallback/resolver.go` arena-ranking pattern is
  attractive but out of scope.** GoModel picks fallback candidates
  from `chatbot_arena_coding` / `chatbot_arena_math` preference
  lists when the user doesn't specify a chain. This conflicts с
  ADR-2 «no cross-tier auto-escalation» because it implicitly
  selects different MODELS. FA Option D requires explicit
  user-config of the chain; ADR-9 §Out of scope flags this
  explicitly.
- **LiteLLM's failure-percent-threshold (`DEFAULT_FAILURE_THRESHOLD_PERCENT`
  + `DEFAULT_FAILURE_THRESHOLD_MINIMUM_REQUESTS`) is mis-fit for
  UC1 single-user low-volume traffic.** LiteLLM cools down only
  after N+ requests show failure_pct > threshold; FA's UC1
  workload may issue only 1-5 LLM calls per session, so percent
  thresholds never accumulate enough signal. FA Option D cooldowns
  on a single transient failure — flagged in ADR-9 §Adopted
  differently from LiteLLM.
- **OmniRoute's 14 routing strategies are over-engineered for UC1+UC3.**
  The 14 strategies (priority, weighted, cost-optimized,
  context-relay, ...) require runtime selection logic that FA's
  α-shape (per-role explicit chain) deliberately omits. Documented
  in §0 R-6 as out-of-scope; revisit only if UC5 benchmark suite
  produces evidence that one of the 14 strategies measurably beats
  α-shape on a single-user benchmark.
- **9router's «RTK token saver» (20-40% token savings via tool-output
  compression) is orthogonal to chain semantics, but interesting
  for FA Pillar 3 (token efficiency).** Not in ADR-9 scope; tracked
  as a candidate BACKLOG item for a future cost-reduction
  intervention. Flagged in §9 Out of scope so the question doesn't
  re-emerge in ADR-9 review.
- **Bifrost's «BlockRestrictedWrites silently drops»** — flagged
  as anti-pattern in R-5. FA must explicitly raise
  `ReservedProviderError` on collision with internal reserved
  names; documented in ADR-9 §Reserved-key semantics.
- **`awesome-free-llm-apis` is a curated list; URLs and quotas
  drift.** ADR-9 Appendix A's example `chain:` block uses values
  from the list as of compile date (2026-05-22); ADR-9 §Re-evaluation
  triggers explicitly notes that example slugs may stale.

## 6. Numbered recommendations (R-1..R-6)

### R-1 — Lock Option D + α (cost: medium for ADR draft; T-2 impl ~380 LOC)

Per §0 R-1 verdict (TAKE). Lock the chain shape:

```yaml
# ~/.fa/models.yaml (concrete example with current OSS slugs as of 2026-05-22)
coder:
  model:  "deepseek-v3"
  family: "deepseek"
  chain:
    - provider: openrouter
      slug:     "deepseek/deepseek-chat-v3"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
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
```

**Failure mode prevented:** Without explicit chain, a single rate-limit
on the free-tier provider stops the role for the rest of the
calendar day (free-tier OpenRouter typically resets daily). With
chain + cooldown, the role transparently falls through to the next
provider for the cooldown window.

**Concrete first step:** ADR-9 §Accepted decision adopts Option D + α
verbatim; T-2 PR follows with `src/fa/providers/{base,chain,
openai_compat,anthropic,registry,errors}.py` totalling ~380 LOC.

### R-2 — Per-(provider, slug) cooldown unit (cost: cheap)

Per §0 R-2 verdict (TAKE). Cooldown row schema (one row per cooled-
down tuple):

```python
@dataclass
class CooldownRow:
    provider: str           # "openrouter"
    slug:     str           # "deepseek/deepseek-chat-v3"
    started_at: float       # unix timestamp
    expires_at: float       # started_at + cooldown_seconds
    trigger_status: int     # 429 | 503 | 0-for-network
    trigger_error: str      # short kind: "rate_limited" | "service_unavailable" | "timeout"
```

Default cooldown = 300s (5 min, matching kronos `PEER_REACTION_COOLDOWN`).
Configurable per chain entry via optional `cooldown_seconds:` field
in YAML. On success after cooldown expires, the tuple's row is
deleted (in-memory only — no persistence across sessions in v0.1,
matching ADR-3 «no volatile state» principle).

**Failure mode prevented:** Per-provider cooldown would silently
benchmark the entire `openrouter` platform when a single slug
hits 429; with per-tuple cooldown, the role can still try other
`openrouter/...` slugs for the cooldown window.

### R-3 — Three-tier observability (cost: cheap)

Per §0 R-3 verdict (TAKE). Schema for tier-1 `llm_call` row:

```json
{
  "kind": "llm_call",
  "ts": "2026-05-22T...",
  "logical_call_id": "<uuid4>",
  "role": "coder",
  "model": "deepseek-v3",
  "family": "deepseek",
  "chain": [
    {"provider": "openrouter", "slug": "deepseek/deepseek-chat-v3", "status": 429, "ms": 142, "error": "rate_limited"},
    {"provider": "fireworks", "slug": "accounts/fireworks/models/deepseek-v3", "status": 200, "ms": 891, "error": null}
  ],
  "in_tokens": 1247,
  "out_tokens": 322,
  "cost_usd": 0.0019,
  "wallclock_ms": 1033
}
```

All three tiers carry the same `logical_call_id` UUID4 (generated
once per role-level call) so post-hoc analysis can correlate the
tier-1 row ↔ tier-2 row ↔ tier-3 body entries for the same
logical call across `events.jsonl` and `llm_bodies.jsonl`. ADR-9
§4 is the contract; per-attempt rows on a chain inherit the
parent's `logical_call_id` (no per-attempt UUID).

Schema for tier-2 `llm_chain_exhausted` row (fires only on failure):

```json
{
  "kind": "llm_chain_exhausted",
  "ts": "2026-05-22T...",
  "logical_call_id": "<uuid4>",
  "role": "coder",
  "model": "deepseek-v3",
  "terminal": "all_exhausted",
  "attempts": [
    {"provider": "openrouter", "status": 429, "ms": 142, "error": "rate_limited"},
    {"provider": "fireworks", "status": 503, "ms": 411, "error": "service_unavailable"},
    {"provider": "nvidia_build", "status": 401, "ms": 87, "error": "auth_failed"},
    {"provider": "groq", "status": 429, "ms": 234, "error": "rate_limited"}
  ],
  "wallclock_ms": 874
}
```

`terminal` is `"all_exhausted"` for chain-exhaustion failure (all
entries tried, all transient-failed) or `"request_shape"` for the
fail-fast path on 400/422 (FA-side client bug — next provider
would produce the same 4xx). The `FailureClassifierObserver`
branches on `terminal` to route the failure to «retry the role»
vs «code bug» per ADR-7 §Amendment 2026-05-20 rule 3.

Schema for tier-3 `llm_bodies.jsonl` row (gated by `FA_DEBUG_LLM_BODIES=1`):

```json
{
  "kind": "llm_body",
  "ts": "2026-05-22T...",
  "logical_call_id": "<uuid>",
  "attempt_index": 0,
  "provider": "openrouter",
  "request_body": {...},
  "response_body": {...}
}
```

**Failure mode prevented:** Without tier-1, debugging «why is the
coder failing every 4th call» requires correlating multi-line log
sequences; with chain-attempt inline, one row answers the question.

### R-4 — Two-category provider adapter split (cost: cheap; already in Option D LOC budget)

Per §0 R-4 verdict (TAKE). File layout:

```text
src/fa/providers/
├── base.py              # Provider Protocol + RequestInfo / ResponseInfo dataclasses (~60 LOC)
├── chain.py             # ChainConfig + ProviderChain + cooldown bookkeeping (~100 LOC)
├── openai_compat.py     # Shared adapter for OpenRouter/Fireworks/NVIDIA Build/Groq/etc (~80 LOC)
├── anthropic.py         # Anthropic /v1/messages adapter (~70 LOC)
├── registry.py          # PROVIDERS dict + factory (~30 LOC)
└── errors.py            # ConfigurationError + ReservedProviderError + ProviderTransientError + ProviderAuthError (~40 LOC)
```

Total ~380 LOC. Add-OpenAI-compat-platform = 1 line in `PROVIDERS`
dict + 1 row in user's `~/.fa/models.yaml`. Add-Anthropic-shape-
platform = new ~70 LOC adapter + registry row.

### R-5 — Reserved-key fail-fast (cost: cheap)

Per §0 R-5 verdict (TAKE). Reserved provider names:

```python
RESERVED_PROVIDER_NAMES: frozenset[str] = frozenset({
    "__internal__",
    "__metadata__",
    "__fallback_marker__",
})
```

Config validator rejects chain entries with reserved `provider`
field at registration time:

```python
def validate_chain(chain: list[dict[str, str]]) -> None:
    for entry in chain:
        if entry["provider"] in RESERVED_PROVIDER_NAMES:
            raise ReservedProviderError(
                f"chain entry uses reserved provider name {entry['provider']!r}; "
                f"reserved names: {sorted(RESERVED_PROVIDER_NAMES)}"
            )
```

### R-6 — Explicit «out of scope» list (cost: cheap)

Per §0 R-6 verdict (TAKE). ADR-9 §Out of scope enumerates:

1. **Cross-MODEL auto-fallback** (e.g. `deepseek-v3` → `kimi-k2`
   когда DeepSeek family rate-limited на всех providers).
   Conflicts with ADR-2; user must explicitly switch model identity
   if all chain entries exhausted.
2. **TLS fingerprint stealth / JA3-JA4 spoofing.** OmniRoute
   pattern. Considered and rejected on ethical grounds — FA does
   not spoof transport identity to evade provider rate limits.
3. **Streaming responses.** ADR-7 §1 «non-streaming only»; chain
   semantics for streaming are a v0.2 amendment slot (chain entry
   that switches mid-stream is a stateful problem far beyond
   non-streaming chain semantics).

## 7. Open questions (Q-1..Q-3)

### Q-1 — Should cooldown state persist across FA sessions?

In v0.1, cooldown state is in-memory only (ADR-3 «no volatile
state» principle; cooldown rows die with the process). This means
if a session crashes after 4-provider exhaustion at minute T, the
next session at minute T+30s will retry all 4 again, hitting the
same 429s.

The alternative is persisting cooldown rows в a SQLite table
(reuses ADR-4 FTS5 backend infra). Cost: ~30 LOC + schema migration.
Benefit: Smoother session-restart behavior on fresh-tier-quota-day-
reset scenarios.

**Why it matters:** UC1 sessions are long-lived (a coding session
can span hours); a mid-session crash is the main motivator for
persistence. Counter-argument: the cooldown window is 5 min by
default, so the cost is ≤ 5 min of failed retries on session-
restart.

**Resolution:** Defer to ADR-9 §Future amendments slot;
re-evaluate after T-2 PR lands and we have telemetry on actual
crash-recovery patterns.

### Q-2 — Should the chain support per-entry retry budgets?

ADR-7 §5 retry-budget invariant says config-bounded retries with
`max_iterations` default 6. Inside one chain attempt, transport-
level retries (httpx) MUST NOT count against the loop-level retry
budget (per chat 2026-05-22). But should each chain entry have
its own transport retry count (e.g. «retry httpx up to 2x per
entry before cooling down»)?

**Why it matters:** Some providers are flaky on first request but
healthy on retry (transient TLS issues, DNS hiccups); a single
httpx retry per entry would reduce false-positive cooldowns.

**Resolution:** Pick `httpx_retries: 1` (one retry per chain entry,
~100ms backoff) as the ADR-9 default; revisit if telemetry shows
>5% of cooldowns are transient single-retry-fixable noise.

### Q-3 — Should ADR-9 specify ordering preference when multiple non-cooled entries are available?

Option D's default behavior: try entries in declared order;
deprioritize cooled entries. But within the non-cooled set, there
are subtler questions — should the first entry always be tried
first (strict-order), or should round-robin balance load across
non-cooled entries?

**Why it matters:** Strict-order means the first entry's quota gets
exhausted first; round-robin spreads load. For free-tier providers
with daily quotas, round-robin extends usable hours per day.

**Resolution:** v0.1 defaults to strict-order (matches user's
explicit chain ordering as preference signal); round-robin is a
candidate amendment if UC1 telemetry shows daily-quota exhaustion
patterns. Documented в ADR-9 §Re-evaluation triggers.

## 8. Files used

- `/home/ubuntu/repos/First-Agent/knowledge/adr/ADR-2-llm-tiering.md`
  (rows 59–95 + §Amendment 2026-05-20)
- `/home/ubuntu/repos/First-Agent/knowledge/adr/ADR-7-inner-loop-tool-registry.md`
  (§Amendment 2026-05-20 rules 1–5)
- `/home/ubuntu/repos/First-Agent/knowledge/adr/ADR-8-hook-registry.md`
  (§Lifecycle points + §Amendment 2026-05-20a/b)
- `/home/ubuntu/repos/First-Agent/src/fa/inner_loop/hooks/base.py`
  (Middleware base classes + GuardMiddleware + ObserverMiddleware)
- `/home/ubuntu/repos/First-Agent/src/fa/roles.py`
  (family extractor + check_eval_disjoint)
- `/home/ubuntu/repos/First-Agent/knowledge/research/correlated-llm-errors-and-ensembling-2026-05.md`
  (§10 R-7 retry-budget invariant + R-9 LLM-using-hook family-disjoint rule)
- `/home/ubuntu/repos/First-Agent/knowledge/research/kronos-agent-os-inspiration-2026-05.md`
  (`kronos/llm.py` 623 LOC; per-provider 5-min cooldown)
- `/home/ubuntu/repos/First-Agent/knowledge/research/dpc-messenger-inspiration-2026-05.md`
  (ADR-002 AbstractLLMProvider; 3074 → 5 files)
- `https://github.com/ENTERPILOT/GoModel/`
  (ADR-0001 / 0004 / 0005; `internal/llmclient/{client,circuit_breaker}.go`;
  `internal/fallback/resolver.go`; AGENTS.md + CLAUDE.md)
- `https://github.com/BerriAI/litellm/`
  (`litellm/router_utils/{cooldown_cache,cooldown_handlers,fallback_event_handlers,
  add_retry_fallback_headers,pre_call_checks,health_state_cache}.py`;
  `litellm/llms/` provider directory layout)
- `https://github.com/maximhq/bifrost/`
  (AGENTS.md §Repository Layout + §Design Principles + §Reserved context keys;
  `core/providers/{openai,anthropic,groq,...}/` Category-1/2 split)
- `https://github.com/decolua/9router/` (README §3-Tier Fallback)
- `https://github.com/Portkey-AI/gateway/` (`src/providers/<name>/` layout)
- `https://github.com/diegosouzapw/OmniRoute/`
  (AGENTS.md §Provider Categories + §Executors + §Translator)
- `https://github.com/mnfst/awesome-free-llm-apis/` (provider inventory)
- `/tmp/research/kong/README.md` (rejected — generic L7 gateway)
- `/tmp/research/plano/README.md` + `/tmp/research/plano/CLAUDE.md`
  (rejected — Envoy WASM + native binary)
- `/tmp/research/coai/main.go` + `/tmp/research/coai/adapter/`
  (rejected — chat-format adapters)

## 9. Out of scope

- **Cross-MODEL auto-fallback** (e.g. `deepseek-v3` → `kimi-k2`).
  Documented в R-6 + ADR-9 §Out of scope. ADR-2 «no cross-tier
  auto-escalation» constraint.
- **TLS fingerprint stealth (JA3/JA4 spoofing).** Documented в
  R-6 + ADR-9 §Out of scope. Provider-ToS violation; not a
  resilience feature.
- **Streaming response chain semantics.** Documented в R-6 + ADR-9
  §Out of scope. ADR-7 §1 «non-streaming only» в v0.1.
- **9router RTK token-saver / tool-output compression.** Orthogonal
  to chain semantics; tracked как BACKLOG candidate для future
  Pillar 3 cost-reduction work; not in ADR-9 scope.
- **OmniRoute «14 routing strategies» (weighted, cost-optimized,
  context-relay, ...).** Over-engineered for UC1+UC3 single-user
  scope; FA Option D's α-shape (per-role explicit declared-order
  chain) is the deliberate minimum-viable scope. Revisit only if
  UC5 benchmark suite produces evidence one of the 14 measurably
  beats α-shape on a reproducible single-user metric.
- **OTel tracing spans for provider calls.** UC5+ scope; FA
  `events.jsonl` covers the «cheap-read trace» niche в v0.1.
- **Persistent cooldown state across sessions** (Q-1 deferred).
- **Per-entry round-robin load balancing** (Q-3 deferred; strict-
  order is v0.1 default).
- **Kong / plano / coai patterns** — rejected per §4.1 triage matrix.
