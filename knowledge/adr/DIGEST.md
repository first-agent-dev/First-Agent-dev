# ADR Digest — one-paragraph cheat-sheet

> **Purpose.** Cheat-sheet for agents and humans who need the gist of
> all accepted ADRs without reading the full source set. One paragraph
> per ADR + bulleted amendments. **The per-ADR file is the
> authoritative source** — this digest only paraphrases.
>
> **Maintenance rule.** When an ADR amendment lands, update the
> matching row here in the **same PR**. Per
> [`pr-creation` skill PR Checklist rule #9](../skills/pr-creation/SKILL.md#pr-checklist).
> Stale rows defeat the purpose.

## ADR-1 — v0.1 use-case scope (accepted 2026-04-27)

**Decision.** Ship UC1 (coding + PR end-to-end) and UC3 (local docs
to wiki) in v0.1; UC2 (multi-source research) best-effort via
LLM-fan-out on top-k chunks; UC4 (Telegram multi-user) deferred to
v0.2 entirely. **Rationale.** User's verbatim ranking puts UC1 + UC3
first; UC1 acceptance scenario (folder → search → edit → PR) is
mechanically verifiable, UC3 is the simpler half-step (no PR-write,
no allow-lists). UC4 needs per-user namespacing that does not exist.

**Amendments.**

- **2026-05-01** — UC5 (semi-autonomous multi-LLM research / experiment)
  added to deferred list.
- **2026-05-06** — UC5 expanded to eval-driven harness iteration
  (5a benchmark suite → 5b trace consumption → 5c iteration
  interface → 5d score tracking / leaderboard → 5e out-of-scope
  exclusions); makes Pillar 3 efficient-harness claim measurable.

**Source:** [`ADR-1`](./ADR-1-v01-use-case-scope.md).

## ADR-2 — LLM tiering & access (accepted 2026-04-27)

**Decision.** Static role routing — Planner = top-tier OSS,
Coder = mid-tier OSS, Debug = elite (Claude), Eval = top-tier OSS
pinned. Configuration in `~/.fa/models.yaml`. **No cross-tier
auto-escalation** on failure; Coder fails loudly, user retries.
**Rationale.** Predictable cost, predictable behavior, simple to
debug; cross-tier auto-escalation is a research problem unsuited
for v0.1.

**Amendments.**

- **2026-04-29** — `tool_protocol: native | prompt-only` per role;
  v0.1 inner-loop has **no Critic / Reflector** role (kept as
  `intra-role retry` only).
- **2026-05-01** — MCP forward-compat tool-shape convention: in-process
  tool dispatcher mirrors JSON-RPC `request: {name, params}` /
  `response: {result, error}`. **No `mcp` package dependency in v0.1.**
- **2026-05-12** (clarification, ADR-7-driven) — `error.code` is
  dual-mode `str | int`: ergonomic domain-string internally
  (e.g. `"invalid_params"`, `"sandbox_deny"`), JSON-RPC numeric
  on the wire. Implementations MUST map between the two at the
  transport boundary. No shape change — relaxation of the §1
  pseudo-schema; `name` / `params` / `result` / `error` field
  set unchanged.
- **2026-05-20** — Eval-role MUST be provider+family disjoint
  from Planner and Coder (regex slug extraction; vacuous on
  current Chinese-OSS workload but pinned for future tier
  bumps). «No cross-tier auto-escalation» rationale now cites
  Cornell P-1 (Kim et al., ICML 2025) + Simula P-2 (Vallecillos-
  Ruiz et al., 2026) as primary sources — `ρ̂ ≈ +0.6` for
  same-family ensembles vs `ρ̂ ≈ −0.05` cross-family. Cross-
  link to [ADR-7 §Amendment 2026-05-20](./ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule)
  rule 4 (same family-disjoint rule generalised to LLM-using
  hooks).
- **2026-05-20 (Wave-1)** — Per-tier tool-shape registry
  ([`knowledge/prompts/tool-shapes.yaml`](../prompts/tool-shapes.yaml)) +
  role-switch handoff one-liner. «Tool shape follows the
  model's training distribution» — anthropic / openai /
  qwen / deepseek / glm / kimi families each get one entry
  with `family:` / `shape.edit:` / `shape.tool_call_format:` /
  `handoff_one_liner:`. Harness injects the *previous* role's
  one-liner into the *next* role's prompt on every role-switch
  to prevent cargo-culting cross-family shapes. Read-only
  metadata; no provider translation. Source:
  [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-18.
- **2026-05-21 (Wave-3 sub-amendment)** — R-19 role-layer
  enforcement of the 2026-05-20 amendment landed: `src/fa/roles.py`
  ships `extract_family` (regex slug-to-family inference with
  default-deny on ambiguous slugs) and `check_eval_disjoint`
  (pure-function role-config check; raises
  `EvalFamilyConflictError` when eval shares family with planner
  or coder). Loader call site lands with the T-2 LLM driver; the
  hook-layer call site already lives in
  [ADR-7 §Amendment 2026-05-20](./ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule)
  rule 4. The rule now has runtime enforcement at both layers.
  Source: [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-19.

**Source:** [`ADR-2`](./ADR-2-llm-tiering.md).

## ADR-3 — Memory architecture variant for v0.1 (accepted 2026-04-27)

**Decision.** Variant A "Mechanical Wiki" — filesystem-canonical
Markdown + YAML frontmatter; deterministic Python chunker; SQLite
FTS5 BM25 read-side. **No embeddings, no graph, no Mem0-style
volatile store in v0.1.** Volatile-store hooks (`src/fa/memory/volatile/`)
scaffolded but empty — additive in v0.2. **Rationale.** Smallest
LoC + smallest dependency surface (~600 LoC + sqlite stdlib);
aligns with ADR-1 scope; v0.2 hooks are additive, not a migration.

**Amendments.** None.

**Source:** [`ADR-3`](./ADR-3-memory-architecture-variant.md).

## ADR-4 — Storage backend for v0.1 (accepted 2026-04-27)

**Decision.** SQLite FTS5 at `~/.fa/state/index.sqlite`
(config-overridable). External-content FTS5 over `chunks` table;
tokeniser `unicode61 remove_diacritics 2` + porter stemmer. **No
vector store in v0.1** (v0.2 ADR slot reserved for `sqlite-vec` or
separate `embeddings.sqlite`). **Rationale.** Zero extra runtime
deps (sqlite3 in stdlib); persistent + incremental upserts; BM25
ranking built-in; index is disposable cache.

**Amendments.**

- **2026-04-29** — `chunks` schema gains seven columns
  (`parent_title`, `breadcrumb`, `line_start/_end`, `byte_start/_end`,
  `topic`); migration `0002_provenance_columns.sql`. Mirrors ADR-5
  `Chunk` dataclass extension same date.

**Source:** [`ADR-4`](./ADR-4-storage-backend.md).

## ADR-5 — Chunker tool selection for v0.1 (accepted 2026-04-28)

**Decision.** universal-ctags (code) + markdown-it-py (prose),
combined behind a stable `Chunker.chunk_file(path) -> list[Chunk]`
interface. Pipeline per-extension: Markdown → AST split by H1/H2;
source code → ctags JSON, slice by line-range; config files →
one-file-per-chunk; catch-all → one-file. **tree-sitter is
explicit non-goal** with named re-evaluation triggers.
**Rationale.** Smallest dependency surface (~6 MB system + 1 MB
Python wheel); covers all six target languages including
PowerShell; loud failure modes.

**Amendments.**

- **2026-04-29** — `Chunk` dataclass extended with `parent_title`,
  `breadcrumb`, `byte_start/_end`, `topic`; `CHUNKER_VERSION` bumps
  invalidate cache once on first run.

**Source:** [`ADR-5`](./ADR-5-chunker-tool.md).

## ADR-6 — Tool sandbox & path allow-list policy (accepted 2026-04-29)

**Decision.** Path allow-list at `~/.fa/sandbox.toml` with separate
`[read]` / `[write]` blocks; default-deny; deny overrides allow;
`pathlib.Path.resolve(strict=False)` collapses symlinks; gitignore-style
globs via `pathspec`. Audit log to `~/.fa/state/sandbox.jsonl`.
**Single resolution per tool invocation** prevents TOCTOU. **v0.1
ships no `run_command` tool.** **Rationale.** Mid-tier Coder
hallucinates; reads are de-facto network egress for ~99% remote-API
config; path-level guard is loud, fast, stoppable; symmetric to
`~/.fa/repos.toml` PR-write allow-list.

**Amendments.**

- **2026-05-13** — `[roles.<name>]` block added to
  `sandbox.toml` schema (per-role `allowed_tools` whitelist enforced
  at ADR-7 dispatcher). Companion to ADR-7 §Amendment 2026-05-13.
  `allowed_dirs` shape-pinned but not exercised in v0.1.
- **2026-05-20** — Five capability flags (deny-by-default opt-in)
  added to `~/.fa/config.yaml` under top-level `capabilities:`:
  `ENABLE_DYNAMIC_TOOLS`, `REQUIRE_DYNAMIC_TOOL_SANDBOX`,
  `ENABLE_MCP_GATEWAY_MANAGEMENT`, `ENABLE_DYNAMIC_MCP_SERVERS`,
  `ENABLE_SERVER_OPS`. All default `False`; verbatim from Kronos
  `kronos/config.py:62-69`. Layer-1 capability opt-in is AND-ed
  with Layer-2 per-role `allowed_tools` (§Amendment 2026-05-13)
  at the dispatcher. Implementation: `src/fa/config.py` ships
  with this amendment as a frozen `Capabilities` dataclass +
  YAML parser. Source:
  [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-21.
- **2026-05-20 (Wave-1)** — Bash sandbox gate landed at
  `src/fa/sandbox/{classifier,validators,path_containment,bash_gate}.py`
  (~715 LoC code + ~700 LoC tests). Three-layer pipeline:
  pattern classifier (5 categories — `READ_ONLY` / `GIT_WRITE` /
  `PACKAGE_INSTALL` / `DANGEROUS` / `GENERAL_WRITE`) + per-command
  validators (`rm` / `chmod` / `git` — 5 deny rules) +
  symlink-resolved path containment. Ported from Aperant
  `bash-validator.ts` + `path-containment.ts` and Gortex
  `bash_classify.go`. `evaluate_bash(command, *,
  workspace_root) -> BashGateDecision` is the single entry
  point; AND-ed with the §Policy file (path scope) at the
  inner-loop dispatcher when BACKLOG M-1 lands. Source:
  [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-20.

**Source:** [`ADR-6`](./ADR-6-tool-sandbox-allow-list.md).

## ADR-7 — Inner-loop & tool-registry contract (accepted 2026-05-12)

**Decision.** Formal inner-loop boundary for v0.1 with six pinned
surfaces: (1) MCP-shaped `ToolSpec` / `ToolResult` registry inheriting
the ADR-2 §Amendment 2026-05-01 JSON-RPC convention; (2) five-tool
v0.1 catalog (`fs.read_file`, `fs.list_files`, `fs.edit_file`,
`fs.write_file`, `fs.grep`) matching ADR-6 §Tool wiring;
(3) two edit-shapes — `edit_file` string-replace default,
`apply_patch` unified-diff off by default (R-3 fixture pins the
flip); (4) JSON-Schema input validation per tool; (5) three-tier
tool disclosure (group list → one-line descriptors → schema on
demand); (6) trace separation — `events.jsonl` raw append-only +
`hot.md` summary (anti-summary-rot invariant). Mini hook pipeline:
`pre_tool` × 2 (Sandbox + optional Approval) + `post_tool` × 1
(Audit); `pre_run` / `post_run` / `on_event` deferred to v0.2.
Static layered prompt frozen at session start (R-8 prefix-cache
invariant). 4-question subtraction-first acceptance block at the
inner-loop boundary. **Rationale.** Ampcode «three bare functions»
works at one tier; FA spans four tiers + `tool_protocol` axis,
so a formal contract is the only way the ADR-2 §Amendment 2026-05-01
MCP-shape convention and the ADR-6 §Tool wiring sandbox stub get
concrete carriers; single source of truth for every tool PR.

**Amendments.**

- 2026-05-12 — cross-reference bootstrap-cost-baseline measurement
  evidence. Adds six inline cross-references (no shape change) to
  [`research/bootstrap-cost-baseline-2026-05.md`](../research/bootstrap-cost-baseline-2026-05.md):
  §6 empirical-backing for tier-3 lazy hydration (6-file irreducible
  core), §7 future-KPI-consumption (BACKLOG I-7), §9 empirical
  context-budget evidence (~80–95 K Devin / 70–95 K Arena),
  §11 R-9 motivation (agent self-report unreliable → `harness_id`),
  §Consequences re-evaluation trigger 5 (FA's own mid-tier harness
  ships = BACKLOG I-8), §Consequences follow-up work (BACKLOG I-1 /
  I-2 / I-3 = AGENTS.md rule #11 mitigations a / b / c). EXEMPT
  per AGENTS.md §Pre-flight Step 4 (documentation-only).
- **2026-05-13** — Declarative per-role tool whitelist (B-NEW-1).
  `[roles.<name>].allowed_tools` in `~/.fa/sandbox.toml`; enforced
  at dispatcher before `pre_tool` hooks; `E_ROLE_WHITELIST` error
  on reject. §11 R-4 status updated. Knowledge-layer only
  (impl lands with inner-loop scaffolding PR). Source:
  [`research/soviet-code-inspiration-2026-05.md`](../research/soviet-code-inspiration-2026-05.md)
  §0 R-1, §6.1.
- **2026-05-20** — Retry-budget invariant + intra-role `T=1.0` +
  LLM-using-hook family-disjoint rule. Five additive rules:
  (1) retry budgets read from `~/.fa/config.yaml`, not hook-code
  constants; (2) `max_iterations` default = 6 per YT-4 empirical
  anchor; (3) intra-role retry temperature default `T=1.0` per
  Nitarach P-3 §4.1 (`ρ̂≈−0.12` vs `T=0.0` `ρ̂≈+0.6`);
  (4) LLM-using hooks MUST use family ≠ acting-role
  (vacuous in v0.1, pinned ahead of first LLM-using hook to
  generalise [ADR-2 §Amendment 2026-05-20](./ADR-2-llm-tiering.md#amendment-2026-05-20--eval-role-family-disjoint--primary-source-citation));
  (5) BACKLOG I-2 sub-agent invocation rules — `generateText`
  not streaming, exclude `SpawnSubAgent`, cap
  `SUBAGENT_MAX_STEPS ≤ 100`. Knowledge-layer only.
  Source:
  [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-7 / §R-28 / §R-29 / §R-30 + §R-23.
- **2026-05-21 (Wave-3 sub-amendment)** — R-45 cost guardian +
  `cost_observation` event-kind. Adds one extension row to §7
  «`events.jsonl`» enumeration; no shape change to §1 driver,
  §5 input validation, §8 hook pipeline.
  `src/fa/observability/cost_guardian.py` ships a single
  `GuardMiddleware` that attaches to both `BEFORE_TOOL_EXEC`
  (gates when `RuntimeLimits.cost_budget_usd` exceeded) and
  `AFTER_TOOL_EXEC` (parses `cost=…` artifacts via
  `default_cost_extractor`, accumulates per-session
  `CostRollup`, writes `cost_observation` rows when an
  `EventLog` is wired). `cost_budget_usd` is tri-mode —
  `None` unbounded (default), `0.0` observe-only, `> 0`
  hard cap. Dormant on baseline M-1 tools; wakes when the
  T-2 LLM driver lands the artifact emitter. Source:
  [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-45.
- **2026-05-21b (Wave-3 sub-amendment, updated 2026-05-22 in same PR)** —
  R-8 `LearningObserver` filesystem-canon artifacts. Wires
  `fa.inner_loop.hooks.builtin.LearningObserver` into
  `fa inner-loop-smoke` after `CostGuardian`, attached at
  `AFTER_TOOL_EXEC`. Smoke and the T-2 real runtime share the
  **single canon root** `<workspace>/knowledge/trace/{codebase_map.json,gotchas.md}`
  — smoke literally exercises the artifact path R-8's cross-session
  memory writes to in production. Live-repo cleanliness across
  repeated smoke runs comes from three forcing functions, not a
  path bypass: (a) **deterministic-clock injection** — smoke pins
  `LearningObserver.now="2026-05-21T00:00:00Z"`, T-2 omits `now`
  and falls through to a live wall-clock; (b) **gotchas dedup** —
  `record_gotcha` skips appends when the file already ends with
  this exact section (fixed clock ⇒ identical bytes ⇒ dedup;
  live clock ⇒ append-only contract preserved); (c) **seed
  baseline + snapshot regression** — `knowledge/trace/codebase_map.json`
  is checked into the repo with the exact smoke output, and
  `test_inner_loop_smoke_canon_snapshot_matches_seed_baseline`
  fails CI on any drift. Discovery key is path-keyed
  (`"{tool/slug}/{path}"` for `fs.*`; `"{tool/slug}/{call_id}"`
  fallback) so two calls to the same tool against different paths
  no longer overwrite each other. No new `EventLog.kind` is added:
  the filesystem artifacts are the durable R-8 audit surface.
  Observer write failures — including the real
  `LearningObserver` → `record_discovery` → `OSError` chain —
  surface in the existing `hook_decision` rows as
  `decision="observer_error_swallowed"` (for smoke CLI:
  `.fa/smoke-events.jsonl`), so no dedicated reader is added.
  **Worked-history note (2026-05-22):** an earlier follow-up
  (`5c1db0f`) relocated the smoke canon to
  `<workspace>/.fa/knowledge/trace/` to silence the same `git
  status` symptom; that was a spec-bypassing workaround that
  decoupled «smoke proves R-8» from «R-8 writes cross-session
  memory under `knowledge/trace/`» and was reverted in M0a.
  **M1 follow-up (2026-05-22, separate PR):** the pattern is
  catalogued at
  [`knowledge/anti-patterns/AP-001-spec-bypassing-workaround.md`](../anti-patterns/AP-001-spec-bypassing-workaround.md),
  the
  [`pr-creation` skill §Reference](../skills/pr-creation/SKILL.md#reference)
  forcing function (Layer 1) is now active, and
  [`test_invariant_adr7_r8_canon_root_is_knowledge_trace`](../../tests/test_cli.py)
  is the Layer-2 worked example (named-invariant test).
  Source:
  [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-8 + §R-32.

**Source:** [`ADR-7`](./ADR-7-inner-loop-tool-registry.md).

## ADR-8 — HookRegistry middleware chain (accepted 2026-05-20; doc-first)

**Decision.** Promote the ADR-7 §8 mini hook-pipeline to a
first-class HookRegistry contract. **Five lifecycle points**
(`BETWEEN_ROUNDS` / `BEFORE_LLM_CALL` / `AFTER_LLM_CALL` /
`BEFORE_TOOL_EXEC` / `AFTER_TOOL_EXEC`). **Two middleware kinds:**
`GuardMiddleware` (may deny / modify; errors propagate) and
`ObserverMiddleware` (read-only; errors swallowed at DEBUG).
Dispatcher: ordered chain, first-deny short-circuit, one
mutation per dispatch (inherits ADR-7 §8), family-disjoint
rule enforced at `register()` time per
[ADR-2 §Amendment 2026-05-20](./ADR-2-llm-tiering.md#amendment-2026-05-20--eval-role-family-disjoint--primary-source-citation)
+ [ADR-7 §Amendment 2026-05-20](./ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule).
**Doc-only at acceptance; runtime materialised by PR #24
([M-1 closed 2026-05-20](../BACKLOG.md#m-1--inner-loop-scaffolding--hookregistry-runtime)).**
v0.1 hooks (`SandboxHook`, `ApprovalHook`, `AuditHook`) are now
`GuardMiddleware` / `ObserverMiddleware` subclasses at
`src/fa/inner_loop/hooks/`. The runtime adds `revalidates_after_modify`
on guards so a `Decision.modify` that mutates `path` / `command`
triggers a sandbox replay on the new params (closes ADR-7 §8
«modify → re-validate» edge case).

**Rationale.** 8-project convergence (DPC
`dpc_agent/hooks.py` + Gortex `internal/hooks/dispatch.go` +
6 cited in DPC ADR-007); Wave-2 work (R-2 `LoopGuard`, R-3
failure-classifier, R-4 pre-tool blocker, R-22 PII walker)
shares this exact substrate. Source:
[`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
§R-1.

**Amendments.**
- *2026-05-20a (sandbox re-check carve-out):* introduces
  `Middleware.revalidates_after_modify` (default `False`). A guard
  that opts in is replayed against the mutated payload after any
  later `Decision.modify`; the one-mutation-per-dispatch and
  first-deny rules still hold. Only `SandboxHook` opts in today.
  Closes the ADR-7 §5+§8 vs ADR-8 §3 "already-run hooks do not
  re-run" tension by codifying the exception explicitly instead
  of leaving it as an undocumented implementation carve-out.
- *2026-05-20b (`BETWEEN_ROUNDS` first-iteration semantics):*
  codifies that `BETWEEN_ROUNDS` fires at the start of every loop
  iteration **including iteration 1** (not only iterations ≥2).
  Session-level guards (`PauseGuard`, `LoopGuard`) MUST attach
  here so an active pause sentinel or a tripped non-progress
  counter blocks the very first tool call. Kept the name
  `BETWEEN_ROUNDS` (rather than renaming to `BEFORE_ROUND`) to
  preserve verbatim alignment with DPC `dpc_agent/hooks.py`
  + Gortex `internal/hooks/dispatch.go` + borrow-roadmap §R-1
  nomenclature; the rename had no other upside.

**Source:** [`ADR-8`](./ADR-8-hook-registry.md).

## ADR-9 — LLM provider client (T-2 driver) (proposed 2026-05-22; revised same day)

**Decision.** **Option D + α** — per-role explicit provider chain
with cooldown. Each role in `~/.fa/models.yaml` declares `model:`
+ `family:` + `chain: [{provider, slug, base_url, api_key_env,
cooldown_seconds?, httpx_retries?, timeout_seconds?,
extra_headers?}, ...]` ordered transport fallback. On transient
failure (429 / 5xx / network), failed `(provider, slug)` tuple
cools down 5 min default and the chain falls through to the next
entry. **Adaptive cooldown** = `max(now + cooldown_seconds,
parsed_retry_after)` honoring RFC 9110 `Retry-After` (header floor,
not ceiling). Same logical model identity across all chain entries;
provider platform varies (OpenRouter → Fireworks → NVIDIA Build
→ Groq for `deepseek-v3`). **4xx split at runtime:** 401 / 403 =
continue chain without cooldown (single-provider auth issue);
**400 / 422 = fail-fast** as `ProviderRequestShapeError` (FA-side
client bug — next provider will fail same way; do not waste chain
budget). Chain exhaustion raises typed `ProviderChainExhaustedError`
(not bare RuntimeError). **Family-disjoint check (ADR-2 + ADR-7)
is preserved** because family is extracted from the logical model
identity, NOT the provider platform — cross-platform fallback
for the same model = no family-disjoint risk by construction.
**§7 model-identity claim is reframed as user discipline +
best-effort `extract_family()` warning** — slug strings vary
legitimately per provider (`deepseek/deepseek-chat-v3` on
OpenRouter vs `accounts/fireworks/models/deepseek-v3` on
Fireworks), so an exact-match validator is infeasible; the
validator emits a warning (not error) on family-mismatch, and
user discipline carries the rest. **Config-load validation**
enforces non-empty chain + non-empty `api_key_env` (env-var
must resolve to non-empty string) + `https://` scheme (`http://`
accepted only for localhost gateway-delegation case + warning).
**Three-tier observability all keyed on shared `logical_call_id`
UUID4** for correlation: tier-1 always-on (1 `llm_call` row per
logical call with attempted-providers inline) + tier-2
(`llm_chain_exhausted` row on chain exhaustion OR request-shape
fast-fail; `terminal: "all_exhausted" | "request_shape"`) +
tier-3 opt-in (`FA_DEBUG_LLM_BODIES=1` → separate
`llm_bodies.jsonl` with full request/response bodies, gitignored;
each body row carries the same `logical_call_id`). **Cost +
token accounting source** spec'd: provider `usage` block via
response normalization + `src/fa/observability/cost_table.py`
model+provider price lookup; pricing-miss → `cost_usd: null` +
`cost_estimate_missing` warning, CostGuardian (R-45) treats null
as zero plus flag. **Two-category adapter split:** shared
`OpenAICompatProvider` (~80 LOC) posts to `<base_url>/chat/completions`
and covers OpenRouter / Fireworks / NVIDIA Build / Groq / GitHub
Models / Modal / Together AI / + any future OpenAI-compatible
platform via 1-row entry in `PROVIDERS` dict; `AnthropicProvider`
(~70 LOC) posts to `<base_url>/v1/messages` and handles
Anthropic's native protocol (system as separate field, tool use
as content blocks). Each adapter **normalizes** provider response
into canonical `ResponseInfo` (text / in_tokens / out_tokens /
finish_reason / tool_calls + provider-specific data parked in
`extras: dict[str, Any]`). Reasoning-model request-parameter
translation seat documented (Q-6 amendment slot — when first
o-series / extended-thinking lands in a default chain). **Six
typed errors** in `errors.py`: ConfigurationError,
ReservedProviderError, ProviderTransientError, ProviderAuthError,
ProviderRequestShapeError, ProviderChainExhaustedError. Total T-2
implementation ~380 LOC across 6 files in `src/fa/providers/` +
~30 LOC `src/fa/observability/cost_table.py`; tracked under
BACKLOG `M-4` (note: `M-2` / `M-3` are already taken by Wave-2
LoopGuard + FailureClassifier + attempt_history and Wave-2 pre-
tool BlockerMiddleware + DSV YAML respectively; `M-4` is the
next free milestone slot). **Rationale.** 8 OSS sources (GoModel, LiteLLM,
Bifrost, kronos, dpc-messenger, 9router, Portkey, OmniRoute)
independently converge on the same three-piece pattern (per-
provider-or-finer cooldown + ordered fallback chain + isolated
per-provider state); FA is adopting the industry-standard shape,
not novel design. Free-tier resilience (NVIDIA Build / Modal /
OpenRouter free tier / Groq free tier / GitHub Models — half low-
reliability with daily quotas) is the v0.1 default, not opt-in
via external gateway dependency. Option D subsumes Option C
(«B2 + base_url gateway delegation») as a single chain entry;
gateway dependency becomes optional, not central. **Cross-MODEL
auto-fallback (e.g. `deepseek-v3` → `kimi-k2`) is out of scope**
per ADR-2 §Decision; explicit-fail-loud is the v0.1 path when
all chain entries exhausted (user explicitly switches model
identity). **TLS-fingerprint stealth / JA3-JA4 spoofing**
rejected on ethical grounds. **Streaming chain semantics** is a
v0.2 **redesign**, not amendment (mid-stream switching requires
buffering complete responses, which defeats streaming's latency
benefit; likely v0.2 path is streaming-roles-bypass-chain). **7
Q-N amendment slots reserved:** Q-1 persistent cooldown, Q-2
httpx-retry tuning + pre-call `tiktoken` estimation, Q-3 round-
robin within non-cooled entries, Q-4 provider-wide cooldown when
≥2 slugs cooling, Q-5 Anthropic prompt-caching preservation, Q-6
reasoning-model request-parameter translation table, Q-7 per-model
timeout override. Companion survey
[`provider-client-survey-2026-05.md`](../research/provider-client-survey-2026-05.md)
carries the audit evidence + 8-source pattern matrix + 3 anti-
pattern flags (LiteLLM failure-percent threshold mis-fit для
UC1 low-volume; Bifrost silent-drop reserved-key writes re-cast
as fail-fast `ReservedProviderError`; OmniRoute TLS spoofing
rejected). **Revision 2026-05-22 (pre-PR critical pass).** §1,
§2, §3, §4, §5, §7, §9, §10, §Consequences refined after self-
critique against 7 P0 logic-bug findings + 6 P1 design-gap
findings; §Decision direction unchanged. **Amendment 2026-05-22
(T-2 driver landed).** Implementation merged in
`devin/1779480362-t2-llm-provider-client` — `src/fa/providers/`
(7 modules: `base.py`, `chain.py`, `openai_compat.py`,
`anthropic.py`, `registry.py`, `errors.py`, `__init__.py`) +
`src/fa/observability/cost_table.py`, plus six offline-only
test modules (55 tests, ADR-7 §10 fake-transport pattern). One
contract clarification surfaced during implementation: `ProviderSpec`
dataclass added to the registry to carry both adapter factory and
adapter-category name, so the chain validator's adapter-homogeneity
warning can reference an explicit category string instead of a class
identity (no Q-N amendment triggered — extends the ADR-9 §5 file
layout description, does not change a decision). Post-review fix-up
2026-05-22: (a) `ProviderChainExhaustedError` + `ProviderRequestShapeError`
now carry `logical_call_id` so both Tier-2 `llm_chain_exhausted`
terminals (`all_exhausted` + `request_shape`) preserve the §4
correlation UUID; (b) `ProviderChain` accepts an optional
`cooldowns: dict[(provider, slug), CooldownRow]` kwarg so the
process-global cooldown ledger required by §3 («two roles sharing
the same `(provider, slug)` tuple share the cooldown state») can be
injected once and shared across all per-role chains; (c)
`ProviderChain.request()` accepts an optional pre-generated
`logical_call_id` so the inner-loop runtime can supply the UUID
already used for `BEFORE_LLM_CALL` per §2 step 2b; (d)
`chain_from_mapping` now coalesces YAML `null` values for `model`
and `family` to the empty string (the prior `str(raw.get(key, ""))`
returned the literal string `"None"` when the YAML key existed with
a null value). **Implementation landing 2026-05-22 — T-4 loader.**
`~/.fa/models.yaml` loader merged in
`devin/1779515293-t4-models-yaml-loader` — `src/fa/providers/config.py`
(~150 LOC) exports `ModelsConfig` + `load_models_config(text, *,
env=None)` + `load_models_config_from_path(path=DEFAULT_MODELS_YAML_PATH,
*, env=None)`. The loader walks the §1 schema via `yaml.safe_load`,
calls `chain_from_mapping` per role, runs `ChainConfig.validate(env)`
to accumulate best-effort warnings, and enforces ADR-2 §Amendment
2026-05-20 rule 1 via `check_eval_disjoint(...)` when planner / coder
/ eval are all declared. Missing-file returns an empty `ModelsConfig`
(deny-by-default policy mirrored from `fa.config`); the caller decides
whether absence is fatal for its workflow. New runtime dep `pyyaml>=6.0`
(first YAML lib add in the repo; the hand-rolled `_yaml_subset.py`
covers only inline-comment stripping and cannot safely round-trip the
§1 nested lists-of-mappings + `extra_headers` schema; the verifier's
`verify_action.py` parser comment already anticipated the transition).
23 new offline tests cover happy-path, empty/null/scalar root, empty
chain, missing `api_key_env`, unknown provider, warnings accumulation,
all three family-disjoint paths (eval=planner / eval=coder / planner=coder
allowed / eval-missing skip / planner-missing skip), four-role
(planner+coder+eval+debug) shape, path-based variant including the
missing-file branch. **Implementation fix-up 2026-05-22 — T-4 review.**
Devin Review surfaced a case-sensitive-bypass bug on the safety-critical
eval-vs-actor family-disjoint check — a YAML `family: "DeepSeek"`
(mixed case) on planner vs `family: "deepseek"` (lowercase) on eval
would silently pass `check_eval_disjoint`'s case-sensitive `==`
comparison because `chain_from_mapping` stored the raw YAML string
verbatim. **Root fix at the producer site:** `chain_from_mapping`
in `src/fa/providers/chain.py` now normalises `family` via
`.strip().lower()` so every downstream consumer (the disjoint check,
the validator's slug-family mismatch warning, cooldown logging,
Tier-2 telemetry) sees a canonical form. `.strip().lower()` is used
rather than routing via `fa.roles.extract_family` because the latter
raises on any override not in `KNOWN_FAMILIES`, which would reject
custom / not-yet-known family names that are legal in v0.1. The
loader's `check_eval_disjoint` call site keeps explicit
`.strip().lower()` as defence-in-depth. 4 additional regression
tests (588 total pass) covering case + whitespace at both the
producer and loader sites. **Implementation follow-up 2026-05-23 —
PR-#13 review fix-up (fork2 only).** Three small landing-only changes
on top of the T-4 + 2-b commits above: (1) a named Layer-2 invariant
test `test_invariant_adr2_eval_disjoint_uncircumventable_by_family_case`
in `tests/test_providers_chain.py` pins the end-to-end *contract*
(mixed-case families must collide via `check_eval_disjoint`),
distinct from the 4 producer-site regression tests that pin the
*implementation* detail of `.strip().lower()`; (2) a partial-config
WARNING via `_partial_disjoint_warning` in `src/fa/providers/config.py`
surfaces the gap when `eval` is declared alongside *exactly one*
actor (planner XOR coder) — the loader's hard `check_eval_disjoint`
gate requires all three roles to fire, so the pairwise rule from
ADR-2 §Amendment 2026-05-20 rule 1 is otherwise silent on this shape;
caller (inner-loop runtime) reads `ModelsConfig.warnings` and decides
whether to fail or accept (ADR-2 §Sub-amendment 2026-05-21 §Decision
rule 2 «call `check_eval_disjoint` **once**» kept verbatim — no spec
change); (3) terminology reword in this DIGEST entry — earlier
«Amendment 2026-05-22» framing replaced with «Implementation landing»
/ «Implementation fix-up» wording because neither the T-4 loader (an
ADR-2 §Sub-amendment 2026-05-21 §Decision rule 2 implementation
landing) nor the 2-b case-sensitivity REPAIR (restoring the existing
ADR-2 §Amendment 2026-05-20 rule 1 invariant) constituted a new
architectural decision; AGENTS.md PR Checklist rule #9 explicitly
scopes `exploration_log.md` updates to PRs that «introduce or amend»
an ADR — neither applies here, so the «Amendment» word was a
misnomer carried over from upstream PR #52. 5 new offline tests
covering the WARNING surface; 1 new named-invariant test; 594 total
pass.

**Source:** [`ADR-9`](./ADR-9-llm-provider-client.md).

## ADR-10 — Deterministic-harness invariants I-1..I-5 (proposed 2026-05-25)

**Decision.** Land five named invariants every A-tier prompt-block,
B-bucket validator, hook, sandbox layer, and future `src/fa/`
component that runs before or after an LLM call MUST satisfy:
**I-1** single-source-of-truth classifier (hermes H3 at
`hermes-agent/agent/tool_guardrails.py:189-221`); **I-2** numbered
MANDATORY workflows are A-bucket residue (gortex GX3 — the prose
workflow is the residue of what the harness has not yet
mechanised); **I-3** stable `[CODE]` prefix on every B-message
(dpc D1 — five `stop_message()` implementations at
`dpc-messenger/.../guards.py:40-44 / 69-75 / 109-115 / 167-174 /
208-213`); **I-4** typed loop-state ownership / loop OWNS,
middleware READS (dpc D2 — `LoopState` dataclass at
`dpc-messenger/.../hooks.py:44-66` with mutation-contract
docstring); **I-5** layer-boundary fail-fast (rtk R8
`git_cmd_c_locale` at `rtk/src/cmds/git/git.rs:41-48` + icm IC1
`MAX_TOPIC_LEN` doc-comment at
`icm/crates/icm-mcp/src/tools.rs:15-32`). Each invariant carries
the AGENTS.md §PR Checklist rule #10 4-question evidence cell
inline, citing `§1.x` line ranges from the input research note
[`fa-abc-synthesis-deep-dive-2026-05.md`](../research/fa-abc-synthesis-deep-dive-2026-05.md)
verbatim. **Rationale.** §3 + §3a of the deep-dive authored the
invariants as a single slate keyed on the «verifiable hook results
+ deterministic harness to control LLM» goal lens — Option C
(single ADR-10 with named I-1..I-5) is the only shape that gives
future PRs a single citable URL per invariant (`ADR-10#i-N`) while
keeping DIGEST.md / HANDOFF.md / exploration_log.md cheap-read
overlays linear in ADR count. **Companion landing.**
[`project-overview.md` §1.2.5](../project-overview.md#125--compliance-by-construction-failure-observable)
«compliance-by-construction, failure-observable» landed in the same
PR per deep-dive §6b placement decision (chosen over Pillar-5
alternative); §1.2.5 carries five KPI candidates each grounded in a
concrete OSS pattern (rtk R1 exit-code contracts / gbrain G1 +
hermes H1 schema-line-cited failure / icm IC2 harness-derived
weights from enum labels / kronos K2 + fork2 PR #13 F1 partial-
disjoint observable WARNING / fork2 PR #13 commit `93a5ee7`
Layer-2 named-invariant test).

**Rejected:** Option A (defer into ADR-7 / ADR-8 amendments — kills
cross-cutting reading); Option B (one micro-ADR per invariant —
artefact bloat); Option D (inline into AGENTS.md PR Checklist rules
— conflates procedural rules with architectural decisions). See
[`exploration_log.md` Q-14](../trace/exploration_log.md#q-14--what-deterministic-harness-invariants-does-the-adr-10-slate-carry-and-where-do-they-live-2026-05-25) for
the full reject rationale + lessons + re-evaluation triggers.

**Follow-up work unlocked.** (1) I-5 FA-surface audit — `fa` CLI
parser / DSV YAML loader / chunker / BashGate — single focused PR
(deep-dive §6a Q4 resolved «defer until ADR-10 lands»); (2) A28
audit for «LLM emits a number» candidates (deep-dive §6a Q2
single-pass); (3) `[CODE]` namespace formalisation + A23 lint
(tiny PR, pytest hook).

**Source:** [`ADR-10`](./ADR-10-deterministic-harness-invariants.md).

## ADR-11 — Authoring Guardrails (two-tier TCB) (proposed 2026-06-01)

**Decision.** Adopt a two-tier Trusted Computing Base for authoring-time
admission control, leading with the **LLM as Untrusted Compiler** threat
model (the author can edit any file, including the guardrails, in the same
patch that introduces a violation). **Level 0** is a frozen, stdlib-only
kernel (`tomllib` manifest, sorted path enumeration, SHA-256
snapshot/kernel/rule-pack hashing, static allowlist dispatch,
deterministic sorted diagnostics, fail-closed, exit 0/1, never
network/dynamic-import/regex-for-structure); **Level 1** is allowlisted
rule packs. Lands the `ADR-11-I1..I8` slate — **I1** Level-0 determinism;
**I2** severity lifecycle (HARD-BLOCK / ADVISORY-with-expiry / INFO; CI
fails only on HARD-BLOCK); **I3 (I-FROZEN)** generated/mirrored parity
(`# I-FROZEN: source=… checker=…`, seed `pr_intent.py` ↔
`pr-creation/SKILL.md`); **I4** AST over regex; **I5** test-decay lock
(`pytest.skip`/`assert True`/`.only` → HARD-BLOCK); **I6** CI-enforced,
not pre-commit-only (always-run, no path-skip); **I7** protected-path
governance + realpath denylist (Hermes pattern; no `--yolo`); **I8
(I-BOOT)** `.fa/session.toml` seam (staged ⊆ declared) + bootstrap
addendum. Every write target lands with a named **active consumer**
(blueprint §9.9). **Enforcement-ceiling:** the agent may only *open* PRs —
the merge gate is required human review acting on a protected-path CI
flag; CODEOWNERS / branch protection are recommended, not load-bearing.
Disjoint `ADR-11-I<N>` namespace per blueprint §10.0 avoids collision with
ADR-10's global `I-1..I-5`. SSOT: the merged blueprint
[`ADR-11-Authoring-Guardrails-Blueprint.md`](../research/ADR-11-Authoring-Guardrails-Blueprint.md)
(R-1..R-18). **Rationale.** Concepts borrowed from Hermes / Archon /
Grafema / NeMo; their runtimes are not (R-7) — a frozen stdlib kernel is
the only shape that is reproducible, offline, and untamperable by the
author it polices.

**Rejected:** (a) scattered `pytest`/`pre-commit`/review-prose checks
(bypassable; threat unmodelled); (b) heavy rule engine — Grafema
Datalog / NeMo runtime rails (dependency footprint wrong for Level 0);
(c) standalone CODEOWNERS / pre-commit-only (false security boundary,
R-9). See [`exploration_log.md` Q-16](../trace/exploration_log.md#q-16--what-authoring-time-guardrail-architecture-does-fa-adopt-and-how-is-it-enforced-2026-06-01)
for full reject rationale + lessons.

**Follow-up work unlocked.** Code ships across the blueprint Appendix B
rollout: PR 1 Level-0 TCB skeleton + protected-path governance; PR 2
`exports.py` + `tests.py` teeth; PR 3 `parity.py` + `docs.py` + I-FROZEN
marker; PR 4 `seam.py` + `.fa/session.toml` + catch/FP corpora; PR 5
`messages.py` + severity tuning. Deferred (post-v0.1): save-time `--watch`
(R-16), network freshness watchdog outside Level 0 (R-17),
tool-whitelisted self-improvement that never mutates Level-0/HARD-BLOCK
rules (R-18).

**Amendment 2026-06-01 (contract freeze).** Added **§Verification**
(catch-corpus `F-1..F-10` baseline + `fp-corpus` with a fixed **< 1 %**
false-positive promotion gate); pinned the diagnostic-code namespace
`FA-AUTHORING-V<N>-<SLUG>` (append-only, mirrors the `ADR-11-I<N>` freeze);
collapsed v0.1 to a **single** `.fa/session.toml` manifest; specified
`rule_input_hash` over the exact bytes a rule consumed + a nullable
`session_hash` binding (I1); recorded that Level 0 must clear the repo's
`fail_under = 90` coverage gate + strict `pylint`; and cited the
`src/fa/chunker/` + DSV (`verifiers/`) seeds as pattern-reuse, explicitly **not**
imported into Level 0.

**Source:** [`ADR-11`](./ADR-11-authoring-guardrails.md).

## ADR-12 — API-key isolation from the agent (accepted 2026-06-16)

**Decision.** Keep LLM API keys out of every surface the agent can reach. The
**boundary is an egress-injection proxy** (Option C, brought forward to v0.1
after a blocking review found bash READ_ONLY commands bypassed path-containment
and the model channel was unredacted): LLM keys live ONLY in a separate
`fa-egress-proxy` container (ro mount `/run/secrets/fa.env`); the agent container
holds no key in any file/env/memory and reaches providers via the proxy
(`base_url → http://fa-egress-proxy:8080/route/<name>`, carrying a non-key
`X-FA-Proxy-Token`); the proxy strips caller auth and injects the real header.
Container separation (mount/PID namespaces) is the boundary, so it holds with the
agent as unprivileged `fa` (no root). A compromised agent can *use* a key but
never *read* it. Defense-in-depth + deploy-key protection (the deploy key still
lives in the agent for git push): (1) `fs.run_bash` reads of secret paths
(`/run/secrets`, `/srv/first-agent/secrets`, `~/.fa/.env`) are denied fail-closed
(`sandbox/secret_paths.py`); (2) the model-facing tool-result channel is redacted
at one chokepoint (`coder_loop._redact`: raw/base64/hex/url/reversed); (3) private
`SecretStore` (keys never in `os.environ`), env allowlist-scrub, SecretGuard.
Enforced by `tests/test_egress_proxy.py`, `tests/test_proxy_wiring_cli.py`,
`tests/test_sandbox_secret_paths.py`, `tests/test_model_egress_redaction.py`,
`tests/test_secret_exfiltration.py`, `tests/test_secret_isolation_invariants.py`.
Residual (deploy-key exotic-encoding) + proxy egress allowlist → BACKLOG I-24.

**Source:** [`ADR-12`](./ADR-12-secret-isolation.md).

## See also

- [`README.md`](./README.md) — ADR process and ordered index.
- [`../trace/exploration_log.md`](../trace/exploration_log.md) — alternatives that were rejected at decision time + lessons (per ADR).
- [`../project-overview.md` §1.1](../project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars) — four-pillar project goal that all ADR decisions advance.
