# HANDOFF.md — for the next agent / session

> **Read this first starting a new session on this repository.**

## 60-second bootstrap

> The five steps below are a condensed bootstrap for agents that
> land on `HANDOFF.md` first e.g. via plain `git clone`.
> The canonical routing surface for LLM agents is
> [`knowledge/llms.txt`](./knowledge/llms.txt) §MUST READ FIRST
> (six files, in order). If the two disagree, llms.txt is canonical
> — step 2 below reads it, which closes the gap.

1. Read [`AGENTS.md`](./AGENTS.md) — repo conventions, PR
   checklist, query routing.
2. Read [`knowledge/llms.txt`](./knowledge/llms.txt) — one-fetch
   index of every documentation file in this repo
   ([llmstxt.org](https://llmstxt.org/) convention).
3. Read [`knowledge/project-overview.md`](./knowledge/project-overview.md)
   — what the project is, what v0.1 ships, what is non-goal.
4. Read [`knowledge/adr/DIGEST.md`](./knowledge/adr/DIGEST.md) —
   one-paragraph cheat-sheet all ADR's + amendments. Open the
   per-ADR file only when DIGEST is insufficient (exact schema,
   Consequences wording, full Amendment text).
5. Check the **Current state** section.

- Now you have everything you need.

## Current state (as of 2026-05-25)

  - [ADR-9](./knowledge/adr/ADR-9-llm-provider-client.md) —
    LLM provider client contract (T-2 driver; **proposed
    2026-05-22; revised same day** after pre-PR critical pass
    closing 7 P0 logic-bug findings + 6 P1 design-gap findings;
    **T-2 driver landed 2026-05-22** in branch
    `devin/1779480362-t2-llm-provider-client` — 7 modules under
    `src/fa/providers/` + `src/fa/observability/cost_table.py`
    + 6 offline-only test modules (55 tests, ADR-7 §10 fake-
    transport pattern); BACKLOG `M-4` closed by same PR;
    `M-2` / `M-3` are already occupied by Wave-2 LoopGuard /
    FailureClassifier / attempt_history and Wave-2 pre-tool
    BlockerMiddleware + DSV YAML respectively, so the T-2 driver
    took the next free milestone slot).
    **Post-review fix-up 2026-05-22:** `logical_call_id` now
    propagates on `ProviderChainExhaustedError` and
    `ProviderRequestShapeError` (closes the §4 Tier-2 correlation
    gap on both terminals); `ProviderChain` accepts a shared
    `cooldowns` ledger so the §3 process-global cooldown invariant
    holds across per-role chains; `ProviderChain.request()`
    accepts an optional pre-generated `logical_call_id` for the
    inner-loop runtime that fires `BEFORE_LLM_CALL`; YAML `null`
    values in the `model:` / `family:` fields now coalesce to the
    empty string (previously the loader stored the literal string
    `"None"` and the family-mismatch validator emitted a
    confusing warning).
    **T-4 loader landed 2026-05-22** in branch
    `devin/1779515293-t4-models-yaml-loader` —
    `src/fa/providers/config.py` (~150 LOC) exports
    `ModelsConfig` + `load_models_config(text, *, env=None)` +
    `load_models_config_from_path(path=DEFAULT_MODELS_YAML_PATH,
    *, env=None)`. The loader walks the §1 schema via
    `yaml.safe_load`, calls `chain_from_mapping` per role, runs
    `ChainConfig.validate(env)` to accumulate best-effort
    warnings, and enforces ADR-2 §Amendment 2026-05-20 rule 1
    via `check_eval_disjoint(...)` when planner / coder / eval
    are all declared. Missing-file returns an empty
    `ModelsConfig` (deny-by-default policy mirrored from
    `fa.config`); the caller decides whether absence is fatal
    for its workflow. New runtime dep `pyyaml>=6.0` (first YAML
    lib add in the repo; the hand-rolled `_yaml_subset.py`
    cannot safely round-trip the §1 nested lists-of-mappings).
    BACKLOG `M-5` closed by same PR; M-1/M-2/M-3/M-4 already
    occupied so the T-4 loader took the next free slot.
    23 new offline tests added (584 total pass).
    **T-4 review fix-up 2026-05-22:** Devin Review surfaced a
    case-sensitive-bypass bug на the eval-vs-actor family-disjoint
    check — a YAML `family: "DeepSeek"` (mixed case) for planner
    and `family: "deepseek"` (lowercase) for eval would silently
    pass `check_eval_disjoint`'s case-sensitive `==` comparison
    because `chain_from_mapping` stored the raw YAML string
    verbatim. **Root fix at the producer site:**
    `src/fa/providers/chain.py` `chain_from_mapping` now normalises
    `family` via `.strip().lower()` so every downstream consumer
    (the disjoint check, the validator's slug-family mismatch
    warning, cooldown logging, Tier-2 telemetry) sees a canonical
    form. `.strip().lower()` is used rather than routing через
    `fa.roles.extract_family` because the latter raises on any
    family override not в `KNOWN_FAMILIES`, which would reject
    custom / not-yet-known family names that are legal в v0.1.
    The loader's `check_eval_disjoint` call site keeps explicit
    `.strip().lower()` as defence-in-depth. 4 new regression
    tests (588 total pass) covering both case + whitespace axes,
    at both the `chain_from_mapping` producer and the loader's
    call site.
    **Option D + α** — per-role explicit provider chain with
    cooldown в `~/.fa/models.yaml` (`{model, family,
    chain: [{provider, slug, base_url, api_key_env,
    cooldown_seconds?, httpx_retries?, timeout_seconds?,
    extra_headers?}, ...]}`). Cross-PLATFORM transport-level
    fallback for the SAME logical model identity (e.g.
    OpenRouter → Fireworks → NVIDIA Build → Groq for
    `deepseek-v3`) — distinct from cross-MODEL auto-escalation
    (which ADR-2 §Decision forbids; family is extracted from the
    logical model identity, not the provider platform, so the
    family-disjoint check from ADR-2 + ADR-7 §Amendment 2026-05-20
    rule 4 is preserved by construction; §7 reframed as user-
    discipline + best-effort `extract_family()` warning because
    slug strings vary legitimately across providers and exact-
    match validator is infeasible). Per-`(provider, slug)` tuple
    cooldown rows (5-min fixed default; **adaptive from RFC 9110
    `Retry-After` header**: `expires_at = max(now +
    cooldown_seconds, parsed_retry_after)`; in-memory only в
    v0.1, process-global so two roles sharing the same `(provider,
    slug)` share cooldown state). **Runtime 4xx split:** 401 / 403
    = continue chain without cooldown (single-provider auth
    issue, next entry might have correct credentials);
    **400 / 422 = fail-fast** raising typed
    `ProviderRequestShapeError` (FA-side client bug — sending
    same body to next provider produces same 4xx, no point
    wasting chain budget). Chain exhaustion raises typed
    `ProviderChainExhaustedError` carrying the attempts list
    (not bare `RuntimeError`). **Config-load validation** enforces
    non-empty chain + non-empty `api_key_env` env-var (must
    resolve to non-empty string at config-load, NOT surface as
    confusing 401 at first call) + `https://` scheme (`http://`
    accepted only for localhost gateway-delegation case + warning).
    **Three-tier observability all keyed on shared `logical_call_id`
    UUID4** wired through ADR-8 `AFTER_LLM_CALL`: tier-1 always-
    on `llm_call` row (chain inline) + tier-2 `llm_chain_exhausted`
    row (`terminal: "all_exhausted" | "request_shape"`) + tier-3
    opt-in `FA_DEBUG_LLM_BODIES=1` → separate gitignored
    `llm_bodies.jsonl` (each body carries the same
    `logical_call_id` for correlation). **Cost + token accounting
    source** spec'd: provider `usage` block via response
    normalization + `src/fa/observability/cost_table.py` model+
    provider price lookup; pricing-miss → `cost_usd: null` +
    `cost_estimate_missing` warning (CostGuardian R-45 treats null
    as zero plus flag). **Two-category adapter split:** shared
    `OpenAICompatProvider` (~80 LOC) posts to
    `<base_url>/chat/completions` and covers OpenRouter /
    Fireworks / NVIDIA Build / Groq / GitHub Models[^github-pat] /
    Modal / Together AI / + any future OpenAI-compatible platform
    (add = 1 row в `PROVIDERS` dict + 1 YAML chain entry);
    `AnthropicProvider` (~70 LOC) posts to `<base_url>/v1/messages`
    (system-as-separate-field; tool use as content blocks). Each
    adapter normalizes provider response into canonical
    `ResponseInfo` (text / in_tokens / out_tokens / finish_reason
    / tool_calls + provider-specific data parked in
    `extras: dict[str, Any]`; observability reads only canonical
    fields). Reasoning-model request-parameter translation seat
    documented for future Q-6 amendment (per-model
    `max_completion_tokens` / `reasoning_effort` / `thinking`
    translation table inside each adapter). T-2 implementation
    budget ~380 LOC across 6 files under `src/fa/providers/` +
    ~30 LOC `src/fa/observability/cost_table.py`. **6 typed errors
    in `errors.py`** (ConfigurationError, ReservedProviderError,
    ProviderTransientError, ProviderAuthError,
    ProviderRequestShapeError, ProviderChainExhaustedError).
    Companion 9-source audit:
    [`research/provider-client-survey-2026-05.md`](./knowledge/research/provider-client-survey-2026-05.md)
    — 8 OSS sources (GoModel + LiteLLM + Bifrost + kronos +
    dpc-messenger + 9router + Portkey + OmniRoute) independently
    converge on the «per-provider-or-finer cooldown + ordered
    fallback chain + isolated state» pattern; 3 anti-patterns
    rejected (LiteLLM failure-percent threshold mis-fit for
    UC1 low-volume traffic; Bifrost silent-drop reserved-key
    re-cast as fail-fast `ReservedProviderError` at config-load;
    OmniRoute TLS-fingerprint stealth rejected on ethical
    grounds). **7 Q-N amendment slots reserved** (Q-1 persistent
    cooldown across sessions, Q-2 per-entry httpx retry tuning +
    pre-call `tiktoken` estimation, Q-3 round-robin within
    non-cooled entries, Q-4 provider-wide cooldown when ≥2 slugs
    cooling, Q-5 Anthropic prompt-caching preservation, Q-6
    reasoning-model translation table, Q-7 per-model timeout
    override). **Streaming chain semantics** flagged as v0.2
    **redesign**, not amendment (mid-stream switching requires
    buffering; defeats streaming's latency benefit; likely
    v0.2 path = streaming-roles-bypass-chain). Decided via chat
    2026-05-22 (Option A delegate-to-gateway / B1 no-resilience /
    B2 minimum-no-fallback / B3 full-GoModel-lift /
    C base_url-override-only rejected in `exploration_log.md`
    Q-13).

  - [ADR-10](./knowledge/adr/ADR-10-deterministic-harness-invariants.md)
    — Deterministic-harness invariants **I-1..I-5** (**proposed
    2026-05-25**) keyed on the «verifiable hook results +
    deterministic harness to control LLM» goal lens. Cross-cutting
    slate every A-tier prompt-block, B-bucket validator, hook,
    sandbox layer, and future `src/fa/` component that runs
    before or after an LLM call MUST satisfy: **I-1**
    single-source-of-truth classifier (hermes H3 at
    `hermes-agent/agent/tool_guardrails.py:189-221`); **I-2**
    numbered MANDATORY workflows are A-bucket residue (gortex GX3
    — `CLAUDE.md` 11-step workflow co-existing with PreToolUse
    hook denial); **I-3** stable `[CODE]` prefix on every
    B-message (dpc D1 — five `stop_message()` implementations at
    `dpc-messenger/.../guards.py:40-44 / 69-75 / 109-115 /
    167-174 / 208-213`); **I-4** typed loop-state ownership /
    loop OWNS, middleware READS (dpc D2 — `LoopState` dataclass
    at `dpc-messenger/.../hooks.py:44-66`); **I-5** layer-boundary
    fail-fast (rtk R8 `git_cmd_c_locale` at
    `rtk/src/cmds/git/git.rs:41-48` + icm IC1 `MAX_TOPIC_LEN`
    doc-comment at `icm/crates/icm-mcp/src/tools.rs:15-32`). Each
    invariant carries the AGENTS.md §PR Checklist rule #10
    4-question evidence cell inline, citing the input research
    note
    [`fa-abc-synthesis-deep-dive-2026-05.md`](./knowledge/research/fa-abc-synthesis-deep-dive-2026-05.md)
    §1.x / §3 / §3a line ranges verbatim (forcing function per
    deep-dive §0c — line citations are the evidence chain).
    **Companion landing in same PR:**
    [`project-overview.md` §1.2.5](./knowledge/project-overview.md#125--compliance-by-construction-failure-observable)
    «compliance-by-construction, failure-observable» per
    deep-dive §6b placement decision (chosen over Pillar-5
    alternative); §1.2.5 carries five KPI candidates — exit-code
    contracts (rtk R1), schema validators with line-cited failure
    (gbrain G1 + hermes H1), harness-derived weights from
    LLM-emitted labels (icm IC2), observable failures via WARNING
    surfaces (kronos K2 + the F1 partial-disjoint WARNING from
    fork2 PR #13), named-invariant tests citing ADR clauses
    (Layer-2 retrofit from fork2 PR #13 commit `93a5ee7`). Decided
    via chat 2026-05-25 (Option A defer-into-ADR-7/8-amendments /
    Option B one-micro-ADR-per-invariant / Option D
    inline-into-AGENTS.md-PR-checklist rejected in
    `exploration_log.md` Q-14; §1.2.5-vs-Pillar-5 placement
    rejected as Pillar-5 in same block per deep-dive §6b).
    **Follow-up work unlocked:** (1) I-5 FA-surface audit
    (`fa` CLI parser / DSV YAML loader / chunker / BashGate) as
    one focused PR per deep-dive §6a Q4 resolved «defer until
    ADR-10 lands»; (2) A28 «LLM emits a number» single-pass audit
    per §6a Q2; (3) `[CODE]` namespace formalisation + A23 lint
    (tiny PR, pytest hook).


- **Research note added 2026-05-25 (PR #14):**
  - [`research/fa-abc-synthesis-deep-dive-2026-05.md`](./knowledge/research/fa-abc-synthesis-deep-dive-2026-05.md)
    — ADR-10 input note: per-repo determinism-pattern deep-dive
    across nine OSS LLM-agent projects under the goal lens
    «verifiable hook results + deterministic harness to control
    LLM». §0-§7 cover six projects (pi, gbrain, hermes-agent,
    gortex, kronos-agent-os, dpc-messenger); §0a-§7a (Amendment R)
    extends with rtk-ai/{rtk, grit, icm}. Ships ADR-10 invariant
    candidates **I-1..I-5** (§3+§3a), 18 A/B-bucket entry
    proposals **A12..A29 + B14..B23** (§4+§4a).
    §0c jump-table at top constrains
    targeted-read cost to ≤ 5 k tokens out of the doc's ≈ 19 k
    total. Every finding cites `repo/file.ext:line` and quotes
    3–10 line snippets verbatim. Next-session use: ADR-10 author
    reads §0+§3+§4+§6 (action surface), drafts ADR-10 invariant
    list keyed on I-1..I-5, then opens §1.x sections only when
    a specific pattern ID is cited.
>
> **Last updated:** 2026-05-25 by Devin session
> [`a1514827169246168bfb7918c82179a7`](https://app.devin.ai/sessions/a1514827169246168bfb7918c82179a7)
> — **ADR-10 lands** (proposed 2026-05-25) at
> [`knowledge/adr/ADR-10-deterministic-harness-invariants.md`](./knowledge/adr/ADR-10-deterministic-harness-invariants.md)
> instantiating I-1..I-5 from the deep-dive's §3 + §3a as a single
> cross-cutting slate, each invariant carrying inline rule #10
> 4-question evidence with `§1.x` line ranges cited verbatim from
> [`research/fa-abc-synthesis-deep-dive-2026-05.md`](./knowledge/research/fa-abc-synthesis-deep-dive-2026-05.md).
> Companion §1.2.5 «compliance-by-construction, failure-observable»
> landed in same PR at
> [`knowledge/project-overview.md` §1.2.5](./knowledge/project-overview.md#125--compliance-by-construction-failure-observable)
> per deep-dive §6b placement decision (chosen over Pillar-5
> alternative); §1.2.5 ships five KPI candidates (rtk R1 exit-code
> contracts / gbrain G1 + hermes H1 schema validators with
> line-cited failure / icm IC2 harness-derived weights from
> LLM-emitted labels / kronos K2 + fork2 PR #13 F1 partial-disjoint
> WARNING / fork2 PR #13 commit `93a5ee7` Layer-2 named-invariant
> test). Rule-#9 trio shipped in same PR: `exploration_log.md`
> Q-14 with full Chosen / Rejected / Lesson / Coupling / Re-eval-
> trigger schema (Options A / B / D rejected); `DIGEST.md` ADR-10
> row (one paragraph); HANDOFF.md §Current state ADR-10 bullet
> (this entry's sibling above). `knowledge/llms.txt` updated with
> ADR-10 row + line counts for files changed in this PR. **Prior
> update:** 2026-05-25 by Devin session
> [`47973b356db843919d2ae536514051c8`](https://app.devin.ai/sessions/47973b356db843919d2ae536514051c8)
> — **PR #13** (T-4 `~/.fa/models.yaml` loader from ADR-9 §1 +
> ADR-2 §Amendment 2026-05-20 + 2-b family-case-sensitive bypass
> root fix at `chain.py:429` ported from `GITcrassuskey-shop/First-Agent`
> PR #52 commit `e9c865d` + Layer-2 invariant test
> `test_invariant_adr2_eval_family_disjoint_at_chainconfig_producer` +
> F1 partial-config disjoint WARNING via `ModelsConfig.warnings` +
> F2 DIGEST.md reword from «Amendment 2026-05-22» to «Implementation
> landing» / «Implementation fix-up» framing per AP-001
> REPAIR-vs-IMPLEMENTATION-LANDING; 5 commits + 1 review-fix-up
> commit `bd88051`; **594 tests pass**) merged to `main`. **PR #14**
> (this) lands
> [`research/fa-abc-synthesis-deep-dive-2026-05.md`](./knowledge/research/fa-abc-synthesis-deep-dive-2026-05.md)
> as next-session ADR-10 input: 9-repo determinism-pattern deep-dive
> (pi / gbrain / hermes-agent / gortex / kronos-agent-os /
> dpc-messenger across §0-§7; rtk / grit / icm across §0a-§7a),
> 5 ADR-10 invariant candidates (I-1..I-5), 18 A/B-bucket entry
> proposals (A12..A29 + B14..B23), 9 open questions (1..5
> unresolved per §6; 6..9 resolved per §6a), and the
> **§1.2.5 placement decision** for «compliance-by-construction,
> failure-observable» (§6b — chosen §1.2.5 over Pillar-5, see the
> decision rationale in the doc). Doc ≈ 19 k words; §0c
> navigation aid added at top for jump-table use (action surface
> §0+§3+§4+§6 reads in ≤ 5 k tokens). Companion analysis docs
> (`fa-drift-analysis-v2.md`,
> `fa-abc-synthesis-deep-dive-rtk-ai-amendment.md`) are kept
> user-side, not checked in. **Prior update:**
> [`cf06efa54f3f49fb834438dac5532a0d`](https://app.devin.ai/sessions/cf06efa54f3f49fb834438dac5532a0d)
> 2026-05-22 — **M2 llms.txt size buckets (RELAX) + AP-002** stacks on `main`
> (PR #48 merged) and is the first **RELAX** dogfood of
> [`AGENTS.md` §Change Classification](./AGENTS.md#change-classification)
> introduced in M1. Replaces `(~N lines)` row format in
> `knowledge/llms.txt` with hybrid `(BUCKET, ~N lines)` where
> `BUCKET ∈ {S, M, L, XL}` at boundaries 300 / 800 / 1500 LOC. M2
> measured baseline drift: 16 of 58 rows had `|actual − claimed|
> > 10 LOC and 3 rows shifted bucket entirely (HANDOFF.md S→M,
> DIGEST.md S→M, exploration_log.md S→L) — that drift is the
> observed cost asymmetry catalogued as
> [AP-002](./knowledge/anti-patterns/AP-002-stale-routing-index-counts.md).
> M2 sweeps all 58 rows + amends
> [`MAINTENANCE.md` §When adding a new file](./knowledge/MAINTENANCE.md#when-adding-a-new-file-under-docs-or-knowledge)
> with the new row format + the boundary table + opens the second
> catalog entry AP-002 + appends Q-12 to exploration_log with the
> 4-bucket-hybrid `Chosen` block and three `Rejected` branches
> («pure buckets, no number», «raw count only, status quo»,
> «boundaries 400 / 800 / 1200 with 800-1200 gap»). No code
> changes; docs-only RELAX. (Earlier 2026-05-21 session
> [`7d46c801db0f4ac3ab4b80ef97a664c3`](https://app.devin.ai/sessions/7d46c801db0f4ac3ab4b80ef97a664c3)
> — **PR-4 / Wave-3 stack #1** stacks on `main` (PR #26 merged)
> and lands two R-Ns from
> [`research/borrow-roadmap-2026-05.md`](./knowledge/research/borrow-roadmap-2026-05.md)
> §3: **R-45 cost guardian**
> (`src/fa/observability/cost_guardian.py` — single
> `GuardMiddleware` that observes per-call cost at
> `AFTER_TOOL_EXEC` and gates at `BEFORE_TOOL_EXEC` when the
> accumulated USD rollup exceeds `RuntimeLimits.cost_budget_usd`;
> tri-mode `None` unbounded / `0.0` observe-only / `> 0` hard cap;
> dormant on baseline tools, wakes when T-2 emits `cost=…`
> artifacts) and **R-19 eval-role family-disjoint** (role-layer
> check complement to the existing R-29 hook-layer check;
> `src/fa/roles.py` exposes a regex slug-to-family extractor +
> `check_eval_disjoint` pure function; ADR-2 §Amendment 2026-05-20
> rule 1 now has runtime enforcement). Same PR amends ADR-2 with
> a role-layer sub-amendment, mirrors it in DIGEST.md, appends an
> exploration_log block, refreshes `knowledge/llms.txt` for the
> two new files, and adds the `cost guardian` / `family extractor`
> glossary rows. 481 tests passing (+67 over PR-3; +29 from R-45 +
> R-19 + cleanup, +8 fixed pre-existing mypy strict errors in
> test files, +10 from four Devin-Review iteration commits — see
> §Current state «PR-4 review-fix iteration» bullet below).
>
> Previous notes:
> 2026-05-21, refined 2026-05-22 same PR, M0a
> follow-up 2026-05-22, M1 anti-pattern catalog 2026-05-22):** R-8
> filesystem-canon writer is
> operationally wired in the smoke CLI: `LearningObserver` registers
> after `CostGuardian` in `fa inner-loop-smoke`. Smoke and the T-2
> real runtime share the **single canon root**
> `<workspace>/knowledge/trace/{codebase_map.json,gotchas.md}` —
> smoke literally exercises the artifact path R-8 uses for cross-
> session memory in production. `fa inner-loop-smoke --workspace .`
> leaves the live repo's `git status` clean across repeated runs
> because three forcing functions make the canon artifact
> reproducible: (a) `LearningObserver.now="2026-05-21T00:00:00Z"`
> pins the smoke `recorded_at` field (T-2 omits `now` → live wall-
> clock for real provenance); (b) `record_gotcha` skips appends
> when the file already ends with this exact section (fixed clock
> ⇒ identical bytes ⇒ dedup; live clock ⇒ sections differ ⇒
> append-only contract preserved); (c) `knowledge/trace/codebase_map.json`
> is checked into the repo as a seed baseline byte-equal to the
> smoke output, and `tests/test_cli.py::test_inner_loop_smoke_canon_snapshot_matches_seed_baseline`
> fails CI on any drift. Discovery key is path-keyed
> (`"{tool/slug}/{path}"` for `fs.*` calls, `"{tool/slug}/{call_id}"`
> fallback) so repeated calls against different paths no longer
> overwrite each other. ADR-7 §Sub-amendment 2026-05-21b documents
> that no new `EventLog.kind` is added because R-8 writes
> filesystem artifacts, not `events.jsonl` rows; observer write
> failures — including the real `LearningObserver` →
> `record_discovery` → `OSError` chain — still surface through
> existing `hook_decision` rows as `observer_error_swallowed` in
> `.fa/smoke-events.jsonl` (test coverage: generic
> `_FailingObserver` regression + `LearningObserver`-specific
> chmod-0o500 regression). The earlier `.fa/knowledge/trace/`
> relocation in `5c1db0f` is reverted; it was a spec-bypassing
> workaround that silenced the `git status` symptom while
> decoupling «smoke proves R-8» from «R-8 writes cross-session
> memory under `knowledge/trace/`» — see exploration_log Q-7
> Rejected blocks.
>
> **M1 anti-pattern catalog (2026-05-22, separate PR from main).**
> `knowledge/anti-patterns/` directory opened with two files:
> `README.md` (entry schema + Layer-1/2/3 detection model) and
> `AP-001-spec-bypassing-workaround.md` (the wave-3 R-8 incident
> verbatim — wrong shape = `.fa/` path relocation in `5c1db0f`,
> right shape = M0a's three forcing functions, the cost-asymmetry
> trap that produced the workaround under any rough heuristic, and
> the three structural detection layers). Same PR adds
> [`AGENTS.md` §Change Classification](./AGENTS.md#change-classification)
> (Layer 1 — mandatory `CLASS: REPAIR | RELAX | WORKAROUND` +
> `INVARIANT:` lines in module-touching PR descriptions and the
> first module-touching commit), the named-invariant test
> `tests/test_cli.py::test_invariant_adr7_r8_canon_root_is_knowledge_trace`
> (Layer 2 — worked example, mechanical spec→test link for the R-8
> canon-root invariant), and full doc sync (ADR-7 §Sub-amendment
> 2026-05-21b worked-history note extended with the M1 cross-link,
> DIGEST.md row extended, knowledge/README.md §Layout updated,
> knowledge/llms.txt §Anti-pattern catalog added,
> `knowledge/trace/exploration_log.md` Q-11 appended capturing the
> three-layer decision with rejected alternatives «add rule
> #N+1 to AGENTS.md», «mechanise CLASS-prefix in CI», «second-LLM
> code review», «static linter for invariant strings»). Detector
> personas (R-32 §What original spec) deferred until ≥3 catalog
> entries exist. Layer 3 (review-time prompt in PR review carrier)
> documentary-only in M1.
>
> **M2 dogfood narrative (2026-05-22, this session).** The §Change
> Classification discipline introduced by M1 is being exercised
> for the first time: M2's PR opens with `CLASS: RELAX` +
> `INVARIANT: knowledge/llms.txt rows carry size-bucket metadata
> sufficient for batch-decision routing (bucket label + raw count)`,
> and the catalog grows by one entry (AP-002) that documents the
> drift the RELAX repairs. AP-002 § «Why the wrong shape
> dominates» explicitly cross-links to AP-001's cost-asymmetry-
> trap mechanism — the two entries are now the project's first
> evidence that the catalog has compounding value (the second
> entry references the first as a generic mechanism rather than
> re-deriving it).
