# Exploration log — alternatives rejected at decision time

> One block per accepted ADR. Each block lists the question, the
> chosen option (`Chosen:`), and each rejected option with
> `Reason:` (why rejected at decision time) + `Lesson:` (what new
> evidence would re-open the branch). Cross-question coupling
> noted under `Coupling:`. The ADR file is the authoritative
> source — this log is the cheap-read overlay agents use to learn
> *why* alternatives were rejected without re-reading every ADR
> end-to-end.
>
> **Maintenance rule.** When an ADR PR lands, append (or amend)
> the matching block in the same PR. Per
> [AGENTS.md PR Checklist rule #9](../../AGENTS.md#pr-checklist).
>
> Origin: research note
> [`ara-protocol-cross-reference-2026-05.md`](../research/ara-protocol-cross-reference-2026-05.md)
> §9 R-1, converted from YAML DAG to telegraphic markdown
> 2026-05-10 per Tsinghua NLAH finding (code → NL migration:
> +16.8 pp accuracy, 9× faster, 97% fewer LLM calls on
> `arXiv:2603.25723`).

## Q-1 — Which v0.1 use cases ship end-to-end? (2026-04-27)

- **Closed by:** [ADR-1](../adr/ADR-1-v01-use-case-scope.md)
- **Chosen:** Ship UC1 + UC3 in v0.1; defer UC4; UC2 best-effort.
- **Rejected:**
  - **UC1 + UC4 in v0.1.** Reason: UC4 ranked below UC1 + UC3 by
    lead; pulls Mem0-style volatile store from v0.2. Lesson:
    becomes viable once volatile-memory design (per-user
    namespacing) is independently justified — see Q-3 dead-end on
    Variant B.
  - **All four use cases in v0.1.** Reason: contradicts pragmatic
    medium-weight goal; sprawling scope. Lesson: revisit when v0.1
    ships and team / infra has grown past single-user.

### Q-1 amendment 2026-05-01 — UC5 (multi-LLM eval-harness) added to v0.1 deferred list

- **Coupling:** Q-1.
- **Rationale:** Needs multi-LLM runner + comparison template;
  closer to eval-harness than orchestration.
- **Source:** [ADR-1 §Amendment 2026-05-01](../adr/ADR-1-v01-use-case-scope.md#amendment-2026-05-01--uc5-added-to-deferred-list).

### Q-1 amendment 2026-05-06 — UC5 expanded to eval-driven harness iteration (5a-5e)

- **Coupling:** Q-1 + Q-1 amendment 2026-05-01.
- **Rationale:** UC5 expanded to benchmark suite + trace
  consumption + config-level iteration interface + leaderboard;
  base for Pillar 3 KPI verification per
  [`project-overview.md` §1.1](../project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars).
- **Source:** [ADR-1 §Amendment 2026-05-06](../adr/ADR-1-v01-use-case-scope.md#amendment-2026-05-06--uc5-expanded-to-eval-driven-harness-iteration).

## Q-2 — How are agent roles routed across LLM tiers? (2026-04-27)

- **Closed by:** [ADR-2](../adr/ADR-2-llm-tiering.md)
- **Chosen:** Static role routing — each role pinned to a tier in
  config; no auto-escalation.
- **Rejected:**
  - **Single-LLM, role differentiated only by prompt.** Reason:
    loses FA's tier-mix value proposition; cannot exploit OSS /
    elite cost asymmetry. Lesson: acceptable only when the budget
    mix collapses to one tier (e.g. fully local, fully Anthropic).
  - **Hybrid dynamic routing with a hard-task detector.** Reason:
    detector reliability is its own research problem; cost becomes
    unpredictable. Lesson: revisit after a stuck-loop /
    complexity detector exists with measurable precision/recall on
    FA's own task corpus.

### Q-2 amendment 2026-05-12 — `error.code` dual-mode `str | int` (ADR-7-driven clarification)

- **Coupling:** Q-2 + Q-7 (ADR-7 §2 ToolError defines
  `code: str` ergonomic-domain identifier; ADR-2 §1
  pseudo-schema is the JSON-RPC wire shape with numeric `code`).
- **Rationale:** ADR-7 §2 introduces ergonomic string codes
  (`"invalid_params"`, `"sandbox_deny"`, `"no_unique_match"`)
  for agent-facing handlers; JSON-RPC wire spec requires
  numeric codes. Dual-mode resolves the contradiction without
  amending the field set: §1 pseudo-schema relaxed from
  `code: int` to `code: str | int`, mapping table lives next to
  the dispatcher. No `name` / `params` / `result` / `error`
  field-set change → no breach of ADR-2 §4 inheritance rule.
- **Source:** [ADR-2 §Amendment 2026-05-01 §4 dual-mode](../adr/ADR-2-llm-tiering.md#amendment-2026-05-01--mcp-forward-compat-tool-shape-convention) (clarification appended in this PR alongside ADR-7 import).

### Q-2 amendment 2026-05-20 — Eval-role family-disjoint + primary-source citation

- **Coupling:** Q-2 + Q-7 (this rule generalises into [ADR-7
  §Amendment 2026-05-20](../adr/ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule)
  rule 4 — same family-disjoint rule applied to LLM-using hooks
  in the §8 hook pipeline).
- **Chosen (additive, no §Decision routing-table edit):** Eval-
  role MUST be provider+family disjoint from Planner and Coder;
  family extracted via regex slug pattern (`^glm-` → `glm`,
  `^qwen` → `qwen`, …); ambiguous slugs MUST be tagged with an
  explicit `family:` field in `~/.fa/models.yaml`. «No cross-
  tier auto-escalation» rule (§Amendment 2026-04-29) now cites
  Cornell P-1 (Kim, Garg, Peng, Garg — ICML 2025) + Simula P-2
  (Vallecillos-Ruiz, Hort, Moonen — 2026) as primary sources;
  `ρ̂ ≈ +0.6` same-family vs `ρ̂ ≈ −0.05` cross-family.
- **Rejected:**
  - **Pin `provider:` field in `models.yaml` schema now.**
    Reason: schema is still in flux (§Amendment 2026-05-12
    just added `tool_protocol.error_code_dual_mode`); coupling
    a schema-change PR to this amendment delays both. Lesson:
    revisit when one new tier-line-up actually exercises an
    ambiguous slug — then the schema field lands together with
    the routing rule.
  - **Trust user judgement, no automated family check.**
    Reason: weakens audit-trail for future tier swaps; weaker
    OSS LLMs (DeepSeek 4 / Kimi 2.6) will accept «yes my
    Planner=Coder=Eval=glm-* is fine» if no automation rejects
    it. Lesson: re-evaluate if FA workload narrows to a single
    family (vacuous case) or if regex slug coverage exceeds
    practical maintenance burden.
- **Re-evaluation triggers:** (1) measured `ρ̂ > 0.4` for the
  actively-routed family-pair on UC5 eval (when UC5 lands) →
  weaken rule to «MUST be family-disjoint when measured
  `ρ̂ > 0.3`»; (2) Cornell P-1 / Simula P-2 retracted by a
  higher-N replication → re-evaluate empirical anchor;
  (3) a future tier-bump puts two roles in the same family
  intentionally → document the pair as a measured exemption.
- **Source:** [ADR-2 §Amendment 2026-05-20](../adr/ADR-2-llm-tiering.md#amendment-2026-05-20--eval-role-family-disjoint--primary-source-citation)
  + [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-19 / §R-27 part 1 + [`research/correlated-llm-errors-and-ensembling-2026-05.md`](../research/correlated-llm-errors-and-ensembling-2026-05.md)
  §0 R-1 / §3 / §6.

### Q-2 sub-amendment 2026-05-21 — R-19 role-layer enforcement landed

- **Coupling:** Q-2 + Q-8 (the 2026-05-20 amendment landed the
  rule; the 2026-05-20 cross-link from this Q to Q-7 amendment
  rule 4 landed the hook-layer enforcement; this sub-amendment
  lands the role-layer enforcement — closing the «documentation-
  only» gap explicitly called out in the 2026-05-20 amendment).
- **Chosen (pure-function module, no `RoleConfig` dataclass
  yet):** `src/fa/roles.py` ships `extract_family(slug, *,
  override=None) -> str` (regex slug-to-family inference with
  default-deny on ambiguous slugs via `FamilyExtractionError`)
  and `check_eval_disjoint(*, planner_family, coder_family,
  eval_family) -> None` (raises `EvalFamilyConflictError` when
  eval shares family with planner or coder). Planner and coder
  are permitted to share a family — the §Decision routing table
  allows the same coder-tier model in both roles; only the eval-
  vs-actor disjointness is enforced. The `~/.fa/models.yaml`
  loader lands with the T-2 LLM driver and consumes these
  helpers — the pure functions ship now so the loader has a
  tested dependency.
- **Rejected:**
  - **Land the `~/.fa/models.yaml` loader + `RoleConfig`
    dataclass in this PR.** Reason: the loader is part of T-2
    (LLM driver) scope per
    [`research/fa-0.1-release-gaps-2026-05.md`](../research/fa-0.1-release-gaps-2026-05.md);
    bundling it here couples the role-layer enforcement to a
    much larger scope-shift and inflates the PR past the
    «one stack» budget. Lesson: revisit when T-2 lands — at
    that point the loader call site becomes the single place
    to consume these helpers.
  - **Inline the family-extraction logic in the loader (no
    `src/fa/roles.py` module).** Reason: the hook-layer call
    site in ADR-7 §Amendment 2026-05-20 rule 4 will need the
    same `extract_family` helper at `HookRegistry.register`
    time; inlining produces two divergent implementations of
    the regex table. Lesson: the function-as-module shape is
    the natural carrier for «the family extractor is the
    single source of truth» invariant.
- **Re-evaluation triggers:** (1) T-2 loader lands and the
  «Loader call site lands with T-2» rule becomes historical
  → drop the rule from ADR-2 sub-amendment, add a `RoleConfig`
  reference; (2) a new family is added to `KNOWN_FAMILIES`
  → add the matching regex row to `_FAMILY_PATTERNS` AND a
  parametrised happy-path case to `tests/test_roles.py` (the
  sync-invariant test will fail otherwise); (3) ambiguous slugs
  become common enough that pre-loading the `family:` override
  becomes painful → consider promoting `family:` from optional
  override to required field (re-evaluation of the 2026-05-20
  amendment, not this sub-amendment).
- **Source:** [ADR-2 §Sub-amendment 2026-05-21](../adr/ADR-2-llm-tiering.md#sub-amendment-2026-05-21--r-19-role-layer-enforcement-regex-extractor--disjoint-check)
  + [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-19.

## Q-3 — Which memory architecture variant for v0.1? (2026-04-27)

- **Closed by:** [ADR-3](../adr/ADR-3-memory-architecture-variant.md)
- **Coupling:** depends on Q-1 chosen option.
- **Chosen:** Variant A — Mechanical Wiki (filesystem-canonical
  Markdown + grep / FTS5 BM25).
- **Rejected:**
  - **Variant B — Hybrid Brain (canon + Mem0 4-op volatile store).**
    Reason: UC4 deferred (Q-1 chosen option), so the main
    beneficiary of B's design is not exercised in v0.1; UPDATE /
    DELETE classifier needs a top-tier LLM on every memory write.
    Lesson: becomes attractive once UC4 (multi-user TG) returns
    to scope or cross-session episodic memory is measured to
    underperform `hot.md`.
  - **Variant C — Layered KG (write-time typed-edge extraction +
    graph traversal).** Reason: most LoC and schema lock-in; graph
    cold-start empty until corpus density materialises; lead
    labelled overkill. Lesson: revisit only when corpus is dense
    enough that BM25 plateaus on multi-hop UC2 queries.

## Q-4 — Which storage backend hosts the disposable v0.1 index? (2026-04-27)

- **Closed by:** [ADR-4](../adr/ADR-4-storage-backend.md)
- **Coupling:** depends on Q-3 chosen option.
- **Chosen:** SQLite FTS5 (stdlib `sqlite3`, BM25 ranking via
  `MATCH` + `bm25()`).
- **Rejected:**
  - **In-memory BM25 (rank-bm25 / bm25s) persisted as a pickle.**
    Reason: pickle is brittle across Python / library versions;
    cold-rebuild O(corpus) on cache invalidation; no transaction
    story for an inbox-watcher. Lesson: acceptable only if SQLite
    FTS5 is unavailable on a target platform — e.g. an embedded
    build without the `sqlite3` stdlib's FTS5 compile-flag.
  - **External services — Postgres+pgvector / Elasticsearch /
    OpenSearch.** Reason: operational overhead inappropriate for
    single-workstation single-user v0.1; contradicts «working
    prototype faster». Lesson: revisit when FA grows past
    single-user OR when a vector layer is committed and the
    corpus exceeds SQLite's practical scale.
  - **Files-only — no index, grep at query time.** Reason: linear
    scan per query; no BM25 ranking; forces full match dumps into
    LLM context, breaking token-efficiency metric. Lesson: only
    viable for corpora small enough that grep latency stays
    sub-second AND no ranking is needed.

## Q-5 — Which chunker tool covers the v0.1 language set? (2026-04-28)

- **Closed by:** [ADR-5](../adr/ADR-5-chunker-tool.md)
- **Coupling:** depends on Q-3 chosen option.
- **Chosen:** universal-ctags (code) + markdown-it-py (prose) via
  a CompositeChunker.
- **Rejected:**
  - **tree-sitter-language-pack — 305 grammars in one wheel,
    full CST.** Reason: ~50–100 MB wheel; CHUNKER_VERSION
    management hard (305 grammars upgrade independently);
    PowerShell grammar fragmented across three upstream repos;
    Markdown weaker than markdown-it-py on corner cases. Lesson:
    becomes the right tool when intra-symbol splitting is required
    (e.g. for code-graph Variant C) or PowerShell grammar
    consolidates upstream.
  - **Per-language regex (sparks-style).** Reason: sparks needed
    >3000 lines of pure-Python `extract.py` for 6 languages — that
    is the floor; maintenance disproportionate to value vs ctags.
    Lesson: only viable when ctags and tree-sitter are both
    unavailable for a target language AND the language is small
    enough to regex by hand.

## Q-6 — How is Coder filesystem access constrained? (2026-04-29)

- **Closed by:** [ADR-6](../adr/ADR-6-tool-sandbox-allow-list.md)
- **Chosen:** Path allow-list with explicit read/write policy in
  `~/.fa/sandbox.toml`; default deny.
- **Rejected:**
  - **No sandbox — Coder reads/writes anything under user's home.**
    Reason: one hallucinated path away from corrupting
    `~/.ssh/authorized_keys`, `~/.aws/credentials`, browser
    profiles; violates `project-overview.md` §4 spirit. Lesson:
    never; only an adversarially-isolated environment (throwaway
    VM) makes this safe.
  - **OS-level sandbox (chroot, bubblewrap, Docker, macOS
    sandbox-exec).** Reason: cross-platform cost high
    (bubblewrap=Linux, sandbox-exec=macOS+deprecated,
    Docker=~250 MB + breaks `gh auth`); friction defeats use;
    educational forks would disable it. Lesson: becomes worth the
    cost when v0.2 ships `run_command` — pure-policy guard cannot
    intercept arbitrary shell.
  - **Pure prompt-level instruction («only edit files inside FA
    repo»).** Reason: hallucinating Coder will violate prompt;
    failure is silent. Lesson: useful only as a layer on top of
    the chosen option, never as a replacement.

## Q-7 — What is the v0.1 inner-loop & tool-registry contract? (2026-05-12)

- **Closed by:** [ADR-7](../adr/ADR-7-inner-loop-tool-registry.md)
  (Amendment 2026-05-12 — cross-reference bootstrap-cost-baseline
  measurement evidence; documentation-only, no shape change).
- **Coupling:** depends on Q-2 (ADR-2 amendments — `tool_protocol`
  + MCP-shape) and Q-6 (ADR-6 — sandbox provides the v0.1 `pre_tool`
  hook of record). Measurement counterpart:
  [`research/bootstrap-cost-baseline-2026-05.md`](../research/bootstrap-cost-baseline-2026-05.md)
  (added 2026-05-12 §Amendment) — six independent ADR-7-prep bootstrap
  sessions across two harnesses empirically validate §6 tier-1 + tier-2
  routing, §9 ≤100 K context-budget, §7 `harness_id` motivation, and
  re-evaluation trigger 5 (= BACKLOG I-8, FA's own harness re-test).
- **Chosen:** Formal inner-loop ADR — MCP-shaped `ToolSpec` /
  `ToolResult` registry; five-tool v0.1 catalog (`fs.read_file`,
  `fs.list_files`, `fs.edit_file`, `fs.write_file`, `fs.grep`); two
  edit-shapes (`edit_file` string-replace default + `apply_patch`
  unified-diff off by default, R-3 fixture pins the flip);
  JSON-Schema input validation; three-tier tool disclosure;
  separated trace (`events.jsonl` raw + `hot.md` summary, anti-
  summary-rot invariant); mini hook pipeline (`pre_tool` ×2 —
  Sandbox + Approval, `post_tool` ×1 — Audit); static layered
  prompt frozen at session start; 4-question subtraction-first
  acceptance block.
- **Rejected:**
  - **No formal inner-loop ADR; let each tool PR define its own
    contract (ampcode «three bare functions» baseline).**
    Reason: ampcode targets one tier (Claude); FA targets four
    + `tool_protocol: native | prompt-only` axis; without a
    formal contract each Coder model sees a different shape for
    the same tool, breaking ADR-2 §Amendment 2026-04-29 «loop
    adapts to the role's `tool_protocol`, not to the model».
    ADR-2 §Amendment 2026-05-01 MCP-shape convention has no
    concrete carrier; ADR-6 §Tool wiring stub propagates as
    inline boilerplate across each tool PR. Lesson: becomes
    viable only if FA collapses to a single tier (e.g. Claude
    only) AND the catalog stays at three tools.
  - **Formal ADR + full hook pipeline (pre-run / post-run /
    on-event) + MCP transport in v0.1.** Reason: pre-run /
    post-run / on-event hooks are v0.2 reflection / UC5
    territory (deferred per ADR-1 §Amendment 2026-05-01 + 2026-05-06);
    MCP transport adds an `mcp` package dependency that ADR-2
    §Amendment 2026-05-01 explicitly excludes; harness-research
    R-6 defers code-execution-over-MCP. Lesson: re-evaluate when
    UC5 lands (eval-driven harness iteration) AND OS-level sandbox
    is built out per ADR-6 §Re-evaluation triggers.

### Q-7 amendment 2026-05-13 — Declarative per-role tool whitelist in sandbox.toml

- **Coupling:** Q-7 + Q-6 (ADR-6 sandbox).
- **Rationale:** Soviet-Code reference impl (`Disentinel/soviet-code`
  v1.964.0, npm-published, systemd-in-prod) ships exactly this
  pattern: 9 agent profiles × declarative `allowed_tools` +
  `extra_dirs` blocks. ADR-7 §11 R-4 reserved `[tool_groups]`
  forward-compat for this; per-role is the natural finer-grained
  extension. Mechanically-verifiable role-capability boundary vs
  prompt-only instruction (the status quo). Closed R-4 as
  finer-than-groups variant.
- **Source:** ADR-7 §Amendment 2026-05-13 +
  [`research/soviet-code-inspiration-2026-05.md`](../research/soviet-code-inspiration-2026-05.md)
  §0 R-1.
- **Rejected alternatives:**
  - **Prompt-only enforcement (status quo).** Reason: not
    mechanically verifiable; relies on Planner respecting "do
    not write files" instruction. Lesson: declarative re-opens
    when a single tier-violation is observed in production
    traces.
  - **Defer to v0.2 multi-role.** Reason: cheap to land now
    (~70 LOC, 0 deps); deferral compounds cost when role count
    expands. Lesson: not on the critical path of v0.1, but
    landed now avoids a 2026-Q3 retrofit.
  - **Adopt soviet-code 9-dept profile granularity.** Reason:
    FA v0.1 ADR-2 ships 4 roles (Planner / Coder / Debug /
    Eval); 9-dept granularity is over-engineered for current
    scope. Lesson: revisit if v0.2 multi-role grows past ~6
    roles.

### Q-7 amendment 2026-05-20 — Retry-budget invariant + intra-role `T=1.0` + LLM-using-hook family-disjoint + sub-agent invocation rules

- **Coupling:** Q-7 + Q-2 (this amendment generalises [Q-2
  amendment 2026-05-20](#q-2-amendment-2026-05-20--eval-role-family-disjoint--primary-source-citation)
  rule «family-disjoint Eval-role» from the role layer to the
  §8 hook layer; both share the same correlated-LLM-errors
  mechanism).
- **Chosen (additive to §1 step 8 / §5 / §8; no shape change to
  §2 / §3 / §6 / §7):** five rules.
  1. Retry budgets read from `~/.fa/config.yaml`, never from
     code constants — dispatcher refuses to start if a required
     cap key is missing.
  2. `max_iterations` default = 6 (YT-4 empirical anchor:
     GPT-3.5 Turbo + correct DSV harness completed an HN
     upvote task in 6 iterations; without the harness, same
     model hallucinated success on step 2).
  3. Intra-role retry temperature default `T=1.0` per Nitarach
     P-3 §4.1 finding (`ρ̂≈−0.12` retry-error correlation at
     `T=1.0` vs `ρ̂≈+0.6` at `T=0.0`); applies only to the
     **retry sample**, not the first-attempt sample.
  4. LLM-using hooks MUST use family ≠ acting-role. Rule is
     vacuous in v0.1 (both `pre_tool` and `post_tool` hooks
     are deterministic Python functions) — pinned ahead of the
     first LLM-using hook so future amendments inherit the
     family-disjoint constraint by default.
  5. Sub-agent invocation (BACKLOG I-2 prep): `generateText`
     not streaming; sub-agent tool set MUST exclude any
     `SpawnSubAgent` tool (recursion); cap
     `SUBAGENT_MAX_STEPS ≤ 100`. Documented in
     [`BACKLOG.md` I-2](../BACKLOG.md#i-2--agent--sub-agents-for-context-load-reduction)
     for the read-side; this amendment is the authoritative
     copy.
- **Rejected:**
  - **Pin `max_iterations` to a hard-coded constant in hook
    code.** Reason: no audit trail; weakens §7 trace
    (`events.jsonl` cannot link the cap to a config version);
    forces every change to ship as a code PR instead of a
    config PR. Lesson: revisit only if the config-loading
    machinery proves too brittle for the first inner-loop
    scaffolding PR.
  - **Default intra-role retry `T = first-attempt T`.** Reason:
    repeats the same hypothesis-distribution peak — Nitarach
    P-3 §4.1 explicit anti-finding. Lesson: revisit if a
    FA-workload eval (post-UC5) shows `T=1.0` retry degrades
    pass-rate vs `T=0.7` for a measured task class.
  - **Defer rule 4 «LLM-using hooks family ≠ acting-role» until
    the first LLM-using hook is proposed.** Reason: deferral
    means the first proposing PR must re-derive both ADR-7 and
    ADR-2 evidence; rule 4 lands now so the v0.2
    amendment-author can cite the existing invariant. Lesson:
    revisit if no LLM-using hook materialises through v1.0 —
    the rule remains dormant but harmless.
- **Re-evaluation triggers:** (1) first LLM-using-hook PR
  lands → split rule 4 into a v0.2 amendment with concrete
  examples; (2) FA-on-FA bootstrap run hits `max_iterations =
  6` cap on an expected-completable task → re-measure (raise
  only on new measurement, not on guesswork); (3) Nitarach P-3
  retracted or contradicted by replication → re-evaluate
  rule 3's empirical anchor.
- **Source:** [ADR-7 §Amendment 2026-05-20](../adr/ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule)
  + [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-7 / §R-23 / §R-28 / §R-29 / §R-30 +
  [`research/correlated-llm-errors-and-ensembling-2026-05.md`](../research/correlated-llm-errors-and-ensembling-2026-05.md)
  §4.1 / §6 R-7 / R-8 / R-9.

### Q-7 sub-amendment 2026-05-21 — R-45 cost guardian + `cost_observation` event-kind

- **Coupling:** Q-7 + Q-8 (extends Q-7 §7 event-kind
  enumeration; reuses Q-8 `GuardMiddleware` shape — no Q-8
  contract change). Future cross-link to T-2 LLM driver once
  it lands the `cost=…` artifact emitter.
- **Chosen:** `src/fa/observability/cost_guardian.py` ships
  a single `CostGuardian(GuardMiddleware)` class that attaches
  to both `BEFORE_TOOL_EXEC` (gates when
  `RuntimeLimits.cost_budget_usd` exceeded) and
  `AFTER_TOOL_EXEC` (parses `cost=…` artifacts via
  `default_cost_extractor`, accumulates `CostRollup`, writes
  `cost_observation` rows). `cost_budget_usd` is tri-mode —
  `None` unbounded (default), `0.0` observe-only, `> 0`
  hard cap — mirroring the `*_suppression_seconds` pattern
  from PR-3 `95c392a`. Dormant on M-1 baseline tools; wakes
  when T-2 emits cost artifacts. Hook wired into the smoke
  entrypoint (`fa inner-loop-smoke`) so chain shape is stable
  across the T-2 cut-over.
- **Rejected:**
  - **Two middlewares — `CostObserver` + `CostGuard` —
    instead of one dual-attaching class.** Reason: the two
    sides share the same `CostRollup` state, so factoring
    them apart forces an external state container (extra
    module + extra wiring point in `_cmd_inner_loop_smoke`)
    and produces two registry entries for one logical
    concern. Q-8 `attaches_to: tuple[LifecyclePoint, ...]`
    is designed for exactly this case. Lesson: revisit if
    a use-case emerges where observation and gating need to
    be independently togglable.
  - **Pin `RuntimeLimits.cost_budget_usd` default to a
    concrete USD value (e.g. `5.00`).** Reason: M-1 baseline
    tools have no cost signal, so any concrete default would
    bind silently against the first T-2 sessions before
    baseline USD is even measured (worst case: first T-2
    smoke run trips the default cap before any meaningful
    work happens). Lesson: re-pin once T-2 lands and N
    baseline sessions provide a measured USD distribution.
  - **Land R-45 artifact emitter (T-2 scope) in the same
    PR to wake the cost-budget axis immediately.** Reason:
    T-2 is full LLM-driver scope per
    [`research/fa-0.1-release-gaps-2026-05.md`](../research/fa-0.1-release-gaps-2026-05.md);
    bundling it busts the «one stack» budget by an order of
    magnitude and ties cost-guardian iteration to driver
    iteration. Lesson: ship the observer first (dormant on
    M-1), wake it when T-2 lands — the chain shape change
    is then zero, only the artifact-emitter side flips on.
- **Re-evaluation triggers:** (1) T-2 LLM driver lands and
  emits `cost=…` artifacts on every LLM call → re-measure
  baseline USD per smoke run, consider pinning
  `DEFAULT_COST_BUDGET_USD` to a non-`None` value once N
  sessions establish a distribution; (2) a second
  observability middleware emerges (token meter, latency
  tracker, …) → factor `default_cost_extractor` artifact-
  parsing into a shared `fa.observability.artifacts` module
  so both middlewares share the same artifact-parsing
  contract; (3) `cost_observation` rows accumulate fast
  enough that the JSONL trace becomes the bottleneck →
  introduce a periodic rollup-only row + per-call detail-
  log opt-in.
- **Source:** [ADR-7 §Sub-amendment 2026-05-21](../adr/ADR-7-inner-loop-tool-registry.md#sub-amendment-2026-05-21--r-45-cost-guardian--cost_observation-event-kind)
  + [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-45.

### Q-7 sub-amendment 2026-05-21b — R-8 `LearningObserver` filesystem-canon artifacts

- **Coupling:** Q-7 + Q-8 (clarifies Q-7 §7 event-kind boundary;
  reuses Q-8 `ObserverMiddleware`/`AFTER_TOOL_EXEC` chain with no
  HookRegistry contract change). Pairs operationally with R-45 in
  the smoke CLI: both observe after tool execution, but R-45 writes
  optional `events.jsonl` cost rows while R-8 writes canonical
  filesystem artifacts.
- **Chosen:** Wire
  `fa.inner_loop.hooks.builtin.LearningObserver` into
  `_cmd_inner_loop_smoke` after `CostGuardian` and before
  `VerifierObserver`. Smoke and the T-2 real runtime share the
  **single canon root** `<workspace>/knowledge/trace/{codebase_map.json,gotchas.md}`
  — smoke exercises the same artifact path R-8 uses for cross-
  session memory in production. Repeated smoke runs leave the live
  repo untouched via three forcing functions, not a path bypass:
  (a) `LearningObserver.now="2026-05-21T00:00:00Z"` pins the
  `recorded_at` field, so the smoke artifact is reproducible; T-2
  omits `now` and live wall-clock timestamps are preserved for real
  provenance. (b) `record_gotcha` skips appends when the file
  already ends with this exact section (fixed clock ⇒ identical
  bytes ⇒ dedup; live clock ⇒ sections differ ⇒ append-only
  contract preserved). (c) The repo checks in a seed
  `knowledge/trace/codebase_map.json` baseline byte-equal to the
  smoke output, and
  `test_inner_loop_smoke_canon_snapshot_matches_seed_baseline`
  fails CI on any drift. On success the observer upserts a
  path-keyed discovery entry via `record_discovery`; on tool error
  it appends `gotchas.md` via `record_gotcha`. Do **not** introduce
  `kind="learning"` in `events.jsonl`; the two files are the
  durable audit trail for R-8. If a filesystem-canon write fails,
  reuse the existing `hook_decision` audit row
  (`decision="observer_error_swallowed"`, `reason=str(exc)`) rather
  than adding a new reader surface.
- **Rejected:**
  - **Leave R-8 as standalone writer functions only.** Reason:
    the R-8 Python ports and `LearningObserver` class already
    existed, but no runtime/smoke entrypoint invoked them; actual
    tool observations still produced no filesystem-canon learning.
    Lesson: revisit only if the smoke CLI is retired before the
    T-2 LLM driver lands.
  - **Duplicate every learning write as `kind="learning"` in
    `events.jsonl`.** Reason: `codebase_map.json` and
    `gotchas.md` are already the replay/audit artifacts for this
    concern; JSONL duplication increases trace size and adds a
    second source of truth without a new invariant. Lesson: add an
    event kind only if a downstream consumer needs to correlate
    learning writes with raw event order and cannot read the
    filesystem artifacts directly.
  - **Add a dedicated reader/CLI for swallowed observer errors.**
    Reason: the existing `EventLog` already records observer
    failures as `hook_decision` rows whenever `run_session` attaches
    the HookRegistry event sink; a separate reader is T-3 diagnostics
    scope, not required for R-8 wiring. Lesson: revisit when a
    general `fa events` / trace-inspection command is scoped.
  - **Move `LearningObserver` into `src/fa/observability/` before
    wiring.** Reason: extra move/rename churn for no capability
    gain; `builtin.py` already exports the class and tests cover it.
    Lesson: factor observability modules only when a second
    filesystem-canon observer forces shared code.
  - **Tool-name-only discovery key (`call.name.replace(".", "/")`)** —
    rejected 2026-05-22 in the same PR (follow-up commit). Reason:
    `record_discovery` is upsert-by-key, so every call to a given
    tool overwrote the prior entry; the smoke run's three tool calls
    produced exactly three permanent slots regardless of session
    length, defeating R-8's stated cross-session memory capability.
    Replaced by the path-keyed scheme: `"{tool/slug}/{path}"` when
    `call.params["path"]` is a non-empty string, else
    `"{tool/slug}/{call_id}"`, with sanitisation against
    `record_discovery._KEY_PATTERN`. Lesson: revisit only if R-8
    is ever intentionally reduced to a per-tool «last seen» index
    (no current use case).
  - **Smoke canon root under `<workspace>/.fa/knowledge/trace/`
    (the path-relocation workaround)** — considered and adopted in
    `5c1db0f` (2026-05-22), then rejected and reverted in the same
    PR (M0a follow-up). Reason: relocating writes to `.fa/` made
    `git status --short` clean but **broke the R-8 invariant** —
    smoke no longer exercised the canonical `knowledge/trace/`
    artifact path that the T-2 real runtime is supposed to use, so
    «smoke proves R-8» and «R-8 actually writes durable cross-
    session memory under `knowledge/trace/`» were silently
    decoupled. The fix was a spec-bypassing workaround masquerading
    as a reliability fix; the surface metric passed while the
    intended functionality regressed. Replaced by the canonical
    path plus three forcing functions (deterministic-clock
    injection, gotchas dedup, seed baseline + snapshot regression
    — see the Chosen block above) so the live repo stays clean
    *because* the canon artifact is reproducible, not because the
    canon was moved out of the tracked tree. Lesson: when a fix
    silences a symptom by changing **what** a module does instead
    of repairing **how reliably** it does it, surface the contract
    being violated explicitly — every spec-bypassing workaround
    walks past at least one invariant. This worked example is the
    seed for the R-32 anti-pattern catalog (planned M1).
  - **Wall-clock `LearningObserver.now` for the smoke CLI** —
    considered briefly 2026-05-22 (M0a). Reason: »just use the
    current machine timestamp« is *exactly* the current
    `_now_iso_z()` default and is the root cause the canonical path
    revert sets out to fix; live timestamps make the JSON diff after
    every smoke run non-empty (timestamp-only), which silently
    re-introduces `?? knowledge/trace/codebase_map.json` in `git
    status`. Replaced by a fixed ISO string anchored at the ADR-7
    §Sub-amendment 2026-05-21b date (`"2026-05-21T00:00:00Z"`).
    Lesson: smoke artifacts that ship into the tracked tree need a
    deterministic clock; only the T-2 real runtime should use live
    wall-clock timestamps, and the difference is one constructor
    keyword.
- **Re-evaluation triggers:** (1) T-2 LLM driver starts emitting
  richer `ToolResult.artifacts` and the `codebase_map.json`
  pointer shape proves insufficient → add a deterministic artifact
  normaliser; (2) multi-process FA invocation lands → add file
  locking around the R-8 writers; (3) a downstream UI requires
  strict event-order correlation for learning writes → reconsider
  a `kind="learning"` projection; (4) a new smoke tool is wired,
  the discovery-key scheme changes, or the summary string of any
  existing tool changes → update the seed baseline at
  `knowledge/trace/codebase_map.json` in the same PR (the snapshot
  regression test will otherwise fail loudly).
- **Source:** [ADR-7 §Sub-amendment 2026-05-21b](../adr/ADR-7-inner-loop-tool-registry.md#sub-amendment-2026-05-21b--r-8-learningobserver-filesystem-canon-artifacts)
  + [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-8.

## Q-8 — What is the v0.1 hook-pipeline contract for the inner-loop dispatcher? (2026-05-20)

- **Chosen:** ADR-8 "Doc-first HookRegistry middleware chain
  with explicit BACKLOG M-1 runtime deferral." Five lifecycle
  points (`BETWEEN_ROUNDS` / `BEFORE_LLM_CALL` /
  `AFTER_LLM_CALL` / `BEFORE_TOOL_EXEC` / `AFTER_TOOL_EXEC`),
  two middleware kinds (`GuardMiddleware` may deny/modify,
  `ObserverMiddleware` read-only), dispatcher ordered-chain
  first-deny short-circuit, family-disjoint rule enforced at
  `register()` time per ADR-2 / ADR-7 §Amendment 2026-05-20.
  v0.1 hooks (`SandboxHook`, `ApprovalHook`, `AuditHook`)
  migrate to subclasses without semantics change when the
  runtime lands.
- **Rejected:**
  - **Option A — Wait until Phase M runtime PR to write the
    contract.** Reason: every Wave-2 R-N (R-2 `LoopGuard`,
    R-3 failure-classifier, R-4 pre-tool blocker, R-22 PII
    walker) shares this substrate; not freezing it means each
    PR re-derives the same shape. Lesson: revisit only if
    Wave-2 work is abandoned wholesale; otherwise the
    duplicated derivation cost dwarfs the doc cost.
  - **Option B — Ship doc + runtime in one PR.** Reason:
    PR-2 already carries R-1 (this ADR), R-18 (tool-shapes
    registry), R-21 (capability flags), R-25 (pause sentinel);
    adding ~600 LoC runtime + ~800 LoC tests breaches the
    "atomic-PR" axis from `repo-audit-playbook.md` §P5.
    Lesson: revisit if BACKLOG M-1 (inner-loop scaffolding)
    proves to be ≪600 LoC after the §8 mini-pipeline is
    actually wired — the runtime delta may be the smaller
    half.
  - **Option D — Adopt DPC's hooks.py verbatim instead of
    re-deriving FA-shape contract.** Reason: DPC's chain is
    Python-async-only (FA is sync), uses string keys for
    lifecycle points (FA prefers `LifecyclePoint` enum), and
    does not enforce family-disjoint at `register()`. Verbatim
    port would silently regress those three FA-specific
    invariants. Lesson: revisit if Wave-2 R-Ns reveal that any
    of the three FA-specific invariants is dead weight in
    practice.
- **Coupling:** Same family-disjoint rule as ADR-2 §Amendment
  2026-05-20 + ADR-7 §Amendment 2026-05-20 rule 4. Enforced
  once at `register()` rather than at each dispatch — single
  source of truth.
- **Re-evaluation triggers:** (1) BACKLOG M-1 lands → ADR-8
  "Implementation Notes" section gets concrete code refs and
  ADR-7 §8 collapses to a one-row migration mapping; (2) first
  Wave-2 R-N PR (R-2 `LoopGuard`) — if the registry contract
  needs schema changes to fit, file a doc-first amendment
  before the code PR; (3) the v0.1 sync-only assumption is
  broken by any FA-roadmap item that requires async hooks → re-
  evaluate the `GuardMiddleware` return-type signature.
- **Source:** [ADR-8](../adr/ADR-8-hook-registry.md) +
  [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-1 +
  [`research/dpc-messenger-inspiration-2026-05.md`](../research/dpc-messenger-inspiration-2026-05.md)
  §3 + [`research/gortex-aperant-inspiration-2026-05.md`](../research/gortex-aperant-inspiration-2026-05.md)
  §2.
- **Amendment 2026-05-20a — sandbox re-check carve-out:**
  - **Chosen:** Add an opt-in `Middleware.revalidates_after_modify`
    flag (default `False`). Today only `SandboxHook` opts in;
    `HookRegistry.dispatch` replays opted-in guards once against the
    mutated payload after any `Decision.modify`. Codifies the
    exception to ADR-8 §3 "already-run hooks 1..N-1 do not re-run"
    so the contract no longer relies on an undocumented
    implementation carve-out.
  - **Rejected (a) — auto-replay all prior guards on every modify:**
    Reason: silently re-runs side-effectful observers and any
    expensive guard; makes dispatch quadratic in chain length;
    invites a footgun. Lesson: revisit only if ≥3 guards eventually
    declare `revalidates_after_modify = True` AND each carries
    integration tests proving the carve-out is no longer minimal.
  - **Rejected (b) — force ordering "mutators must be last":**
    Reason: brittle to PR landing order, hostile to two
    mutators that share a chain, and doesn't actually let the
    sandbox re-run on the mutated payload. Lesson: revisit if
    the registry adopts a topological-sort step (currently it
    does not).
  - **Coupling:** Pairs with ADR-7 §5 + §8 (re-validation after
    `Decision.modify`); pairs with the BUG-0001 fix at
    `loop.py` (BETWEEN_ROUNDS `PermissionError` converted to
    a `kind="run_stopped"` row rather than a raw traceback) —
    the two together close the "PR-#24 review block" cycle.
  - **Re-evaluation triggers:** (1) a second guard declares
    `revalidates_after_modify = True` → confirm the order of
    replays is deterministic and tests cover the multi-replay
    case; (2) a Wave-2 R-N introduces a new modify-emitting
    middleware → confirm the carve-out still bounds replay cost.
- **Amendment 2026-05-20b — `BETWEEN_ROUNDS` first-iteration semantics:**
  - **Chosen:** Codify that `BETWEEN_ROUNDS` fires at the start of
    every loop iteration **including iteration 1**. Session-level
    guards (`PauseGuard`, `LoopGuard`) attach here precisely so a
    pause sentinel or non-progress counter active at session
    start blocks the very first tool call, not only the second
    onward. Keep the name `BETWEEN_ROUNDS` rather than renaming
    to `BEFORE_ROUND` — verbatim alignment with DPC
    `dpc_agent/hooks.py:LIFECYCLE_POINTS` + Gortex
    `internal/hooks/dispatch.go:Dispatch` + borrow-roadmap §R-1
    is worth more than a slightly clearer name.
  - **Rejected (a) — rename to `BEFORE_ROUND`:**
    Reason: ~30 LOC mechanical refactor across code + ADR-8
    diagram + every Wave-2 middleware `attaches_to` tuple for
    a purely-cosmetic gain; breaks the verbatim cross-project
    naming map in Prior Art §1. Lesson: revisit if a future
    Wave-3 R-N introduces a *second* lifecycle point that
    also fires at iteration 1 and the pair would read more
    cleanly as `BEFORE_ROUND` + something else.
  - **Rejected (b) — leave the semantics undocumented and reply
    "intentional" in the PR-review thread:**
    Reason: weaker OSS LLMs reading the ADR without the PR
    thread cannot derive «fires on iter=1» from the name alone;
    the next agent who registers a session-level guard would
    have to grep `loop.py` to find out. Lesson: ADR amendments
    are the cheaper-read overlay for exactly this case (per
    research note Tsinghua NLAH conversion); inline doc beats
    repo-archaeology.
  - **Coupling:** Pairs with the PR-24 `loop.py` BETWEEN_ROUNDS
    dispatch (line 66-72: dispatched once per iteration starting
    at iteration=1) and the PR-25 `LoopGuard.attaches_to` tuple
    (`BEFORE_TOOL_EXEC` + `BETWEEN_ROUNDS`) — both depend on the
    iteration-1 semantics being part of the contract.
  - **Re-evaluation triggers:** (1) `session_start` / `session_end`
    hook points land (BACKLOG calls out the seat in §1 above) →
    re-examine whether `BETWEEN_ROUNDS` should still fire on
    iter=1 or whether `session_start` subsumes that case;
    (2) two consecutive Wave-3 R-Ns confuse the name in their
    docstrings → escalate to a rename in a follow-up amendment.

## Q-9 — Wave-1 R-N triplet (R-18 tool-shapes / R-21 capability flags / R-25 pause sentinel) — what shape? (2026-05-20)

- **Chosen:** Three independent doc + code artefacts landed
  in one PR (PR-2):
  - **R-18** — Per-tier tool-shape registry at
    `knowledge/prompts/tool-shapes.yaml` (read-only metadata,
    six families: anthropic / openai / qwen / deepseek / glm /
    kimi) + role-switch handoff one-liner rule in ADR-2
    §Amendment 2026-05-20 (Wave-1). No Python this round —
    consumer is the future role-prompt assembler, which lands
    with BACKLOG M-1.
  - **R-21** — Five capability flags (`ENABLE_DYNAMIC_TOOLS`,
    `REQUIRE_DYNAMIC_TOOL_SANDBOX`,
    `ENABLE_MCP_GATEWAY_MANAGEMENT`,
    `ENABLE_DYNAMIC_MCP_SERVERS`, `ENABLE_SERVER_OPS`), all
    default `False`, in ADR-6 §Amendment 2026-05-20 + Python
    skeleton at `src/fa/config.py` (frozen `Capabilities`
    dataclass + YAML parse). Layer-1 capability opt-in
    AND-ed with §Amendment 2026-05-13 Layer-2 role tool
    whitelist at the dispatcher.
  - **R-25** — Pause-file sentinel pattern (`RATE_LIMIT_PAUSE`
    / `AUTH_PAUSE` / `RESUME`) at
    `src/fa/orchestration/pause.py` (~80 LoC), with four
    timeout constants matching Kronos defaults
    (`MAX_RATE_LIMIT_WAIT_MS=7_200_000`,
    `RATE_LIMIT_CHECK_INTERVAL_MS=30_000`,
    `AUTH_RESUME_MAX_WAIT_MS=86_400_000`,
    `AUTH_RESUME_CHECK_INTERVAL_MS=10_000`).
- **Rejected:**
  - **Bundle R-18 / R-21 / R-25 into separate PRs.** Reason:
    each is independent of HookRegistry (so PR-2 is not
    blocked by Q-8 above), each is small (~50-80 LoC), and
    review cost amortises across one shared PR description.
    Lesson: revisit if any single R-N grows past ~150 LoC —
    split off then.
  - **Skip R-18 YAML registry; inline the per-family edit
    shape in role prompts directly.** Reason: cargo-cult risk
    when role prompts are copied (R-18 rule says: the
    one-liner FIRES on role-switch precisely because the
    *next* role tends to inherit the previous role's shape).
    Lesson: revisit only if a FA-workload eval shows the
    handoff one-liner has ≤2% effect — then the registry can
    collapse to a per-role inline.
  - **Make capability flags CLI flags or env vars instead of
    `config.yaml` field.** Reason: audit trail. Capability
    set is the security-sensitive surface; CLI/env leaves no
    diffable trace. Lesson: revisit only if the YAML parser
    proves slow enough to matter (impossible at this scale).
  - **Use a database lock for pause/resume instead of file
    sentinel.** Reason: sentinel pattern is
    process-/host-agnostic and survives crashes — DB lock
    requires a connection alive at pause-time. Lesson:
    revisit only if FA gains a persistent DB layer for other
    reasons.
- **Re-evaluation triggers:** (1) R-18 — UC5 eval shows
  per-family shape selection adds ≤2% accuracy over a single
  `string_replace + raw_json` baseline → drop the registry;
  (2) R-21 — ≥3 of 5 capability flags always flipped to
  `True` in practice → demote those to defaults; (3) R-25 —
  filesystem-sentinel pattern proves unable to survive
  cross-machine session migration (anticipated UC5 sub-agent
  surface) → re-evaluate against a `state.jsonl`-based
  equivalent.
- **Source:** [ADR-2 §Amendment 2026-05-20 (Wave-1)](../adr/ADR-2-llm-tiering.md#amendment-2026-05-20-wave-1--per-tier-tool-shape-registry--role-switch-handoff-one-liner)
  + [ADR-6 §Amendment 2026-05-20](../adr/ADR-6-tool-sandbox-allow-list.md#amendment-2026-05-20--five-capability-flags-deny-by-default-opt-in)
  + [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-18 / §R-21 / §R-25 +
  [`research/kronos-agent-os-inspiration-2026-05.md`](../research/kronos-agent-os-inspiration-2026-05.md)
  §0 R-3 (capability flags) / §0 R-7 (pause sentinel).

## Q-10 — Should the bash sandbox be a single denylist regex, a 3-layer pipeline, or a LLM-judged hook?

- **Chosen:** Three-layer deterministic pipeline at
  `src/fa/sandbox/{classifier,validators,path_containment,bash_gate}.py`
  (~715 LoC code + ~700 LoC tests). Lands ADR-6 §Amendment
  2026-05-20 (Wave-1). The three layers compose as:
  - **Classifier** (Gortex `bash_classify.go` port, ~225 LoC):
    coarse category in 5 buckets (`READ_ONLY`, `GIT_WRITE`,
    `PACKAGE_INSTALL`, `DANGEROUS`, `GENERAL_WRITE`).
  - **Validators** (Aperant `bash-validator.ts` port, ~245
    LoC): per-command rules for `rm` / `chmod` / `git` (5
    deny rules total — world-write chmod, `git config
    user.email/name`, `--global/--system` config, force-push
    to `main`/`master`, `rm` outside workspace).
  - **Path containment** (Aperant `path-containment.ts`
    port, ~95 LoC): symlink-resolved «target inside base?»
    check used by validators.
  - **Gate** (composer, ~150 LoC): `evaluate_bash(command, *,
    workspace_root) -> BashGateDecision { allow, category,
    reason, validator_result }`.
- **Rejected:**
  - **Single denylist regex.** Reason: opaque audit trail
    («matched pattern N» instead of «classifier said
    DANGEROUS + validator said target /etc is denied») +
    poor composition with the capability-flags layer (R-21,
    PR-2). Lesson: revisit only if the 3-layer eval shows
    ≥5% false-positive rate in real workload and a regex
    proves measurably better.
  - **LLM-judge hook.** Reason: AGENTS.md PR Checklist rule
    #10 question 4 («could this be a deterministic Python
    function?») answers YES for command shape; Gortex
    explicitly cites zero-latency / no-LLM as the design
    goal. Lesson: revisit only if an LLM-judge layer shows
    proven KPI lift; the deterministic gate remains the
    backstop.
  - **Path-only sandbox (status quo before this PR).**
    Reason: `git config --global user.email evil@x` passes
    the path check (no path argument) and rewrites the git
    identity — the canonical «looks innocent, mutates
    outside scope» trap Aperant documents. Lesson:
    irreversible — path-only is insufficient by
    construction.
  - **Bundle the bash-gate PR with R-18 / R-21 / R-25 (PR-2).**
    Reason: R-20 is the largest single Wave-1 R-N (~400 LoC
    spec, ~715 LoC actual) and security-sensitive — review
    cost benefits from isolation. Lesson: split-off worked
    as expected; revisit only if security review fatigue
    becomes the bottleneck.
- **Re-evaluation triggers:** (1) Workload eval shows ≥5% of
  legitimate commands misclassified by the deterministic
  classifier → demote `PACKAGE_INSTALL` and `GENERAL_WRITE`
  to a single «caller-opt-in-required» bucket and collapse
  to 3 categories; (2) MCP integration ships per-tool
  validators that supersede the head-token validator set
  → bash-gate collapses to 2 layers (classifier +
  path-containment); (3) ADR-8 HookRegistry runtime lands
  (BACKLOG M-1) and a LLM-judge `GuardMiddleware` at
  `BEFORE_TOOL_EXEC` shows KPI lift over the deterministic
  gate → the LLM hook becomes the primary gate, the
  deterministic three-layer stays as backstop.
- **Coupling:** Pairs with Q-8 (ADR-8 HookRegistry, R-1) at
  the runtime layer: once BACKLOG M-1 lands the
  `BEFORE_TOOL_EXEC` middleware kind, the bash gate is the
  prototype `GuardMiddleware` implementation. Pairs with R-4
  (Wave-2 pre-tool blocker hook) which subsumes the gate
  through the HookRegistry surface. Pairs with R-21 (PR-2
  capability flags) at the configuration layer: the
  `ENABLE_DYNAMIC_TOOLS` flag will eventually gate whether
  the `PACKAGE_INSTALL` category is even reachable.
- **Source:** [ADR-6 §Amendment 2026-05-20 (Wave-1)](../adr/ADR-6-tool-sandbox-allow-list.md#amendment-2026-05-20-wave-1--bash-sandbox-gate-three-layer-classifier--validators--path-containment)
  + [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-20 +
  [`research/gortex-aperant-inspiration-2026-05.md`](../research/gortex-aperant-inspiration-2026-05.md)
  Aperant items 6 + 13 (validators + path-containment) and
  Gortex Tier-1 item M (`bash_classify.go`).

## Q-11 — How do we prevent the spec-bypassing-workaround pattern (AP-001) from re-emerging in OSS-LLM operation? (2026-05-22)

- **Closed by:**
  [`knowledge/anti-patterns/AP-001-spec-bypassing-workaround.md`](../anti-patterns/AP-001-spec-bypassing-workaround.md)
  + [AGENTS.md §Change Classification](../../AGENTS.md#change-classification)
  + [`tests/test_cli.py::test_invariant_adr7_r8_canon_root_is_knowledge_trace`](../../tests/test_cli.py)
  (M1 PR; no new ADR).
- **Coupling:** Q-7 §Sub-amendment 2026-05-21b — the AP-001
  worked-history note lives in that ADR section; Q-11 generalises
  the lesson into a project-wide forcing-function model.
- **Chosen:** Three structural layers, ranked by leverage-per-token,
  optimised for **action count** rather than rule count:
  (1) **Layer 1 — Change-Classification prefix** in
  [`AGENTS.md` §Change Classification](../../AGENTS.md#change-classification).
  Module-touching PRs and the first module-touching commit on a
  branch open with `CLASS: REPAIR | RELAX | WORKAROUND` +
  `INVARIANT: <one sentence>`. One mandatory action per PR; the
  act of naming CLASS surfaces the contradiction at write-time and
  at review-time.
  (2) **Layer 2 — Named ADR-bound invariant tests.** For each ADR
  amendment's invariant, one test whose name encodes the
  assertion. Worked example:
  `test_invariant_adr7_r8_canon_root_is_knowledge_trace`. Retrofit
  is **opportunistic** (when an ADR amendment touches an
  invariant), not a campaign — zero new actions for the LLM, the
  test either exists or it does not.
  (3) **Layer 3 — Review-time prompt** in the PR review carrier
  (Devin Review prompt, PR template, self-review checklist): «Does
  this PR change *what the module does* or *how reliably it does
  it*? If the former, link the ADR amendment.» Documentary in M1;
  catches whatever Layers 1+2 missed.
  The catalog entry
  [`AP-001`](../anti-patterns/AP-001-spec-bypassing-workaround.md)
  is the durable evidence anchor; future entries land alongside it.
- **Rejected:**
  - **Add rule #N+1 to AGENTS.md («Do not bypass module
    invariants»).** Reason: weaker OSS LLMs ignore ~30+ rule-lines
    under attention load (FA's documented behaviour); adding
    another rule competes with existing rules for attention and
    loses under load. The wrong shape is action-count-dominated,
    not rule-count-dominated; more rules do not fix it. Lesson:
    revisit only if a measurement shows compliance with a specific
    new rule exceeds 50% on the target OSS LLM tier without
    crowding-out existing rules.
  - **Mechanise CLASS-prefix detection in CI.** Reason: too brittle
    too soon (regex over commit-message bodies is fragile;
    contributors will fight the regex more than the discipline).
    Lesson: revisit once Layer 1 has measurable signal that
    contributors / agents actually skip the prefix at a rate ≥10%,
    at which point a lightweight pre-commit hook is the natural
    next step.
  - **Mandate a second-LLM code review of every PR.** Reason: real
    cost (token spend, latency, queue depth) without a measured
    improvement over Layers 1+2 first. Also imports the «retry
    with paraphrase» anti-pattern explicitly rejected by
    [`AGENTS.md` PR Checklist rule #10](../../AGENTS.md#pr-checklist)
    («prompt-diversity layer is not a valid harness component»).
    Lesson: revisit only if Layers 1+2 leave a measurable
    invariant-bypass rate after one full Stage-2 cycle.
  - **Build a static linter for invariant strings.** Reason:
    invariants live in prose (ADRs / docstrings / commit
    messages); a static linter would either miss most of them or
    require enforcing structured invariant-declarations across the
    whole codebase, which is a much larger project than M1
    scopes. Lesson: revisit only if a high-precision invariant-
    extraction parser becomes available (e.g. from a future
    Stage-2 LLM-driven docs pipeline).
- **Re-evaluation triggers:** (1) Three or more `AP-NNN` entries
  exist → the R-32 «detector personas» layer (specific prompts
  that scan the codebase for each anti-pattern) becomes worth
  designing; (2) Layer-1 declarations get systematically omitted
  by Devin / DeepSeek / Kimi at a rate ≥10% over a measured
  sample → escalate to the mechanised-detection branch; (3) A new
  ADR's invariant cannot be encoded as a single named test (e.g.
  the invariant is over multiple files' joint behaviour) → revise
  the Layer-2 shape to allow named-invariant *test groups* with a
  common slug.
- **Source:**
  [`knowledge/anti-patterns/AP-001-spec-bypassing-workaround.md`](../anti-patterns/AP-001-spec-bypassing-workaround.md)
  + [AGENTS.md §Change Classification](../../AGENTS.md#change-classification)
  + [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-32.

## Q-12 — Should llms.txt rows carry size buckets, raw counts, both, or neither? (2026-05-22)

- **Closed by:**
  [`knowledge/anti-patterns/AP-002-stale-routing-index-counts.md`](../anti-patterns/AP-002-stale-routing-index-counts.md)
  + [`MAINTENANCE.md` §When adding a new file](../MAINTENANCE.md#when-adding-a-new-file-under-docs-or-knowledge)
  + sweep of all 58 rows in `knowledge/llms.txt` (M2 PR; no new ADR).
- **Coupling:** Q-11 — first **RELAX** dogfood of the
  [`AGENTS.md` §Change Classification](../../AGENTS.md#change-classification)
  discipline introduced in M1; second entry in the
  [`knowledge/anti-patterns/`](../anti-patterns/README.md) catalog.
- **Chosen:** **Hybrid 4-bucket label + raw count at boundaries
  300 / 800 / 1500 LOC.** Row format becomes
  `- [path](raw-url) (S|M|L|XL, ~N lines): description.` Bucket
  label is the semantic primary key (one of S / M / L / XL); raw
  count is preserved for token-budget additivity (an agent can
  still sum `~120 + ~170 + ~220 ≈ ~510` to compare against a
  context-window limit). Boundaries: S ≤ 300 (batch freely),
  M 301–800 (batch 2–3 on mid-tier OSS), L 801–1500 (read
  alone), XL > 1500 (chunked / sectional only). M2 measured the
  drift on 2026-05-22: 16 of 58 rows had `|actual − claimed| > 10`
  before the sweep; 3 rows shifted bucket (HANDOFF.md S→M,
  DIGEST.md S→M, exploration_log.md S→L). The bucket scheme
  widens the per-row drift tolerance ~20× (from ±10 LOC at the
  rounding edge to ±300/500/700 LOC at the boundary edge),
  making routine PRs touch fewer rows.
- **Rejected:**
  - **Pure buckets, no raw count (`(S)` / `(M)` / `(L)` / `(XL)`).**
    Reason: kills additivity. The project's existing token-budget
    math (e.g.
    [`research/bootstrap-cost-baseline-2026-05.md`](../research/bootstrap-cost-baseline-2026-05.md)
    §3 «6-file irreducible bootstrap core») depends on summing
    `~N lines` to size a batch read in advance; with only buckets,
    an agent batching three M files would know only that the sum
    is somewhere in 903–2400 LOC. Lesson: revisit only if
    a project-wide token-counter tool lands and the additivity
    math is no longer done by the reading agent.
  - **Raw counts only, status quo (`(~N lines)`).** Reason: the
    silent-drift pattern catalogued in AP-002 is the exact
    failure mode of this shape — 27 % of rows accumulated > 10
    LOC drift in ~5 months because every-edit-rebakes-the-row is
    a maintenance debt no one pays. Lesson: revisit only if a
    pre-commit script reliably updates `~N lines` on every
    underlying file edit; until then, the bucket scheme absorbs
    routine drift.
  - **Boundaries 400 / 800 / 1200 (user-proposed alternative).**
    Reason: (a) leaves an 800–1200 LOC gap — under that scheme
    files at 870 / 950 / 970 / 1000 / 1010 / 1090 / 1170 LOC have
    no label, and (b) collapses XL into L: the only XL file
    (`borrow-roadmap-2026-05.md` at ~1840 LOC) ends up in the
    same bucket as ~900-line ADRs, losing the «alarm: read
    chunked» signal. Lesson: revisit if the project's median file
    size shifts upward enough that 800–1500 becomes routine and
    > 1500 becomes common; then drop XL and use 400 / 1000 / 1500.
  - **Mechanise via CI script (compute bucket from `wc -l`, fail
    CI if row's declared bucket is wrong).** Reason: layer 2 of
    the AP-002 detection story is mechanically possible (small
    Python script) but premature — the bucket scheme widens
    tolerance enough that boundary-crossings are rare (3 of 58
    rows in 5 months). Pre-mature mechanisation is exactly the
    same anti-pattern as Q-11's «mechanise CLASS-prefix in CI»
    rejected branch. Lesson: revisit if the next sweep finds
    ≥ 5 % cross-bucket drift, or if any single PR introduces
    > 1 cross-bucket change without updating the row.
- **Re-evaluation triggers:** (1) Next periodic sweep (no fixed
  cadence yet; opportunistic — bundled with the next PR that
  touches `MAINTENANCE.md` or three+ llms.txt rows in a single
  edit) finds ≥ 5 % cross-bucket drift → escalate to the
  CI-mechanisation branch; (2) Project file distribution shifts
  toward larger files (median > 600 LOC) → re-cut boundaries to
  400 / 1000 / 1500; (3) A token-counter tool lands that makes
  the bucket label redundant with a per-call budget check →
  revisit the «raw count only» branch with the new evidence.
- **Source:**
  [`knowledge/anti-patterns/AP-002-stale-routing-index-counts.md`](../anti-patterns/AP-002-stale-routing-index-counts.md)
  + [`MAINTENANCE.md` §When adding a new file](../MAINTENANCE.md#when-adding-a-new-file-under-docs-or-knowledge)
  + [AGENTS.md §Change Classification](../../AGENTS.md#change-classification)
  + Q-11 (Layers 1 / 2 / 3 model this Q-12 inherits).

## Q-13 — How is the T-2 LLM provider client (driver) shaped? (2026-05-22)

- **Closed by:** [ADR-9](../adr/ADR-9-llm-provider-client.md) +
  companion survey
  [`provider-client-survey-2026-05.md`](../research/provider-client-survey-2026-05.md).
- **Coupling:** Q-2 (ADR-2 «no cross-tier auto-escalation» — provider
  fallback within same model identity does NOT violate ADR-2 because
  family is anchored on logical model identity, not provider platform);
  Q-7 / Q-8 (ADR-7 §Amendment 2026-05-20 retry-budget invariant +
  T=1.0 intra-role retry + LLM-using-hook family-disjoint rule;
  ADR-8 `BEFORE_LLM_CALL` / `AFTER_LLM_CALL` lifecycle points — T-2
  driver wires through both without new lifecycle points).
- **Chosen:** **Option D + α** — per-role explicit provider chain
  with cooldown; per-role declaration shape (no shared named chains
  in v0.1). Each role in `~/.fa/models.yaml` carries `model:` +
  `family:` + `chain: [{provider, slug, base_url, api_key_env}, ...]`
  ordered transport fallback. On transient failure (429 / 5xx /
  network), failed `(provider, slug)` tuple cools down for 5 min
  default and chain falls through to the next entry. Same logical
  model identity across all chain entries; provider platform varies
  (OpenRouter → Fireworks → NVIDIA Build → Groq for `deepseek-v3`).
  Three-tier observability: tier-1 always-on (1 `llm_call` row per
  logical call с attempted-providers inline) + tier-2 error-trace
  (`llm_chain_exhausted` row on full chain exhaustion) + tier-3
  opt-in (`FA_DEBUG_LLM_BODIES=1` → separate `llm_bodies.jsonl`
  with full request/response bodies, gitignored). Two-category
  adapter split: shared `OpenAICompatProvider` (~80 LOC) covers
  OpenRouter / Fireworks / NVIDIA Build / Groq / GitHub Models / +
  any future OpenAI-compatible provider; `AnthropicProvider`
  (~70 LOC) handles native `/v1/messages` shape. Total T-2
  implementation ~380 LOC across 6 files in `src/fa/providers/`.
- **Rejected:**
  - **Option A (delegate entirely to external gateway —
    GoModel/LiteLLM/Cloudflare AI Gateway container).** Reason:
    hard Docker dependency conflicts with UC1 single-user single-
    process scope; cost accounting / family-disjoint enforcement
    re-implemented at gateway layer or lost; weaker OSS LLMs reason
    poorly over multi-process failure modes. Lesson: revisit when
    UC1+UC3 stops being the load profile (multi-user UC4+ would
    benefit from gateway-side load balancing).
  - **Option B1 (FA-direct without resilience; user runs gateway
    externally if they want fallback).** Reason: free-tier rate-
    limit handling becomes user homework; no FA-side test coverage
    of resilience path; misses «cross-platform fallback for same
    model» requirement explicitly named by user. Lesson: revisit
    only if FA pivots to «assume always-available primary provider»
    deployment model (corporate dedicated-quota tier).
  - **Option B2 (FA-direct with minimum resilience: retry +
    circuit-breaker, no fallback resolver).** Reason: no fallback
    at all → role dies when its single configured provider is
    rate-limited; same failure mode as B1. Lesson: revisit if a
    single-provider deployment model emerges (e.g. user contracts
    one enterprise provider with SLA).
  - **Option B3 (full GoModel-style lift: Hooks Protocol +
    CircuitBreaker + FallbackResolver + CapabilityModel +
    ProviderAttempt, ~500 LOC).** Reason: (a) `FallbackResolver`
    auto-picks fallback candidates from `chatbot_arena_coding`
    rankings — cross-MODEL auto-escalation, conflicts with ADR-2
    §Decision; (b) `CapabilityModel` + `ProviderAttempt` add
    indirection unjustified at FA's single-call-at-a-time scope;
    (c) future-agent reading burden — 500 LOC vs Option D's 380.
    Lesson: revisit if FA grows to support arbitrary fan-out across
    candidates with auto-discovery (UC5+ benchmark-driven config),
    at which point `CapabilityModel` becomes load-bearing.
  - **Option C (B2 + transparent gateway delegation via `base_url`
    override).** Reason: default install has NO multi-provider
    fallback → free-tier resilience target requires running the
    gateway, the same dependency Option A was rejected for.
    Lesson: not really rejected — subsumed by Option D, which
    supports the gateway-delegation path as a single chain entry
    (`{base_url: "http://localhost:8080/v1", ...}`). Re-emerges
    if FA needs to ship a «one-config-line» upgrade path to a
    gateway-only deployment.
- **Re-evaluation triggers:** (1) Second consumer of named chains
  appears in `~/.fa/models.yaml` → β shape (top-level `chains:`
  block) amendment slot; (2) Future hook in `src/fa/inner_loop/hooks/`
  issues its own LLM calls → §7 family-disjoint constraint
  preservation needs revisiting for the hook's chain inheritance;
  (3) Provider list expands past ~10 chain entries per role →
  round-robin amendment over strict declared-order; (4) OTel
  becomes a UC5 requirement → tier-1 observability schema may need
  trace_id / span_id surface; (5) Mid-stream provider switching
  becomes a v0.2 requirement alongside ADR-7 §1 streaming-mode
  landing → §9 streaming amendment.
- **Re-evaluation triggers added in revision 2026-05-22:** (6)
  awesome-free-llm-apis updates the canonical slugs / base_urls →
  amend `~/.fa/models.yaml.example`; (7) First reasoning model
  (o-series / extended-thinking / DeepSeek-R-like) lands in a
  default chain → triggers Q-6 per-model request-parameter
  translation table + possibly Q-7 per-model timeout override;
  (8) Pricing-table-miss telemetry shows >5% of `llm_call` rows
  carry `cost_usd: null` → triggers Q-2 second half (pre-call
  `tiktoken` estimation as fallback).
- **Amendment 2026-05-22 (pre-PR critical pass).** ADR-9 §1, §2,
  §3, §4, §5, §7, §9, §10, §Consequences refined after self-
  critique closing 7 P0 logic-bug findings + 6 P1 design-gap
  findings: typed errors (`ProviderRequestShapeError`,
  `ProviderChainExhaustedError`); 4xx split at runtime (400/422
  fail-fast as FA-side client bug, 401/403 continue chain as
  single-provider auth issue); shared `logical_call_id` UUID4
  across all three observability tiers for correlation; adaptive
  cooldown from RFC 9110 `Retry-After` header; per-request
  `timeout_seconds`; response normalization (canonical
  `ResponseInfo` + `extras: dict[str, Any]` Postel's-Law surface);
  cost+token accounting source (provider `usage` block +
  `src/fa/observability/cost_table.py` pricing lookup;
  pricing-miss → `cost_usd: null` warning); §7 model-identity
  claim reframed as user discipline + best-effort
  `extract_family()` warning (exact-match validator infeasible
  due to legitimate slug-string variance across providers);
  config-load validation (non-empty chain, non-empty `api_key_env`,
  `https://` scheme); reasoning-model request-parameter
  translation seat (Q-6 slot); streaming flagged as v0.2
  **redesign** not amendment. §Decision direction unchanged
  (Option D + α remains chosen).
- **Source:** [ADR-9](../adr/ADR-9-llm-provider-client.md) +
  [`provider-client-survey-2026-05.md`](../research/provider-client-survey-2026-05.md)
  (8 OSS sources independently converge on the «per-provider
  cooldown + ordered fallback chain + isolated provider workers»
  pattern; see survey §4.2 convergence matrix).

## Q-14 — What deterministic-harness invariants does the ADR-10 slate carry, and where do they live? (2026-05-25)

- **Closed by:** [ADR-10](../adr/ADR-10-deterministic-harness-invariants.md)
  + companion §1.2.5 landing in
  [`project-overview.md` §1.2.5](../project-overview.md#125--compliance-by-construction-failure-observable).
- **Coupling:** Q-7 (ADR-7 inner-loop & tool-registry — I-2 binds
  AGENTS.md §Pre-flight residue + I-3 binds §8 hook pipeline's
  agent-facing messages); Q-8 (ADR-8 HookRegistry — I-1 binds
  classifier delegation + I-4 binds `LoopState` mutation contract);
  Q-6 (ADR-6 sandbox — I-5 binds outermost-layer validation, with
  the MCP-layer mirror as the re-evaluation trigger); Q-13 (ADR-9
  LLM provider client — I-3 binds CostGuardian future gating
  message format; F1 partial-disjoint WARNING surfaced via
  `ModelsConfig.warnings` is the failure-observable prior-art for
  §1.2.5 KPI candidate 4).
- **Chosen:** **Option C** — single ADR-10 with named invariants
  **I-1..I-5**, each grounded in `repo/file.ext:line` citations
  from the deep-dive note
  [`fa-abc-synthesis-deep-dive-2026-05.md`](../research/fa-abc-synthesis-deep-dive-2026-05.md)
  §3 + §3a. **I-1** single-source-of-truth classifier (hermes H3 at
  `tool_guardrails.py:189-221`); **I-2** numbered MANDATORY
  workflows are A-bucket residue (gortex GX3 — `CLAUDE.md` 11-step
  workflow co-existing with PreToolUse hook denial); **I-3** stable
  `[CODE]` prefix on every B-message (dpc D1 — five `stop_message()`
  implementations in `guards.py`); **I-4** typed loop-state
  ownership / loop OWNS, middleware READS (dpc D2 — `LoopState`
  dataclass in `hooks.py:44-66`); **I-5** layer-boundary fail-fast
  (rtk R8 `git_cmd_c_locale` at `rtk/src/cmds/git/git.rs:41-48` +
  icm IC1 `MAX_TOPIC_LEN` doc-comment at
  `icm/crates/icm-mcp/src/tools.rs:15-32`). Companion §1.2.5
  «compliance-by-construction, failure-observable» landed in the
  same PR per the deep-dive's §6b placement decision (chosen over
  Pillar-5 alternative); §1.2.5 ships five KPI candidates (exit-
  code contracts / schema-line-cited failure / harness-derived
  weights from enum labels / observable failures via WARNING
  surfaces / named-invariant tests citing ADR clauses).
- **Rejected:**
  - **Option A — Defer the invariants into ADR-7 / ADR-8
    amendments (no new ADR file).** Reason: the invariants
    cut across ADR-6 / ADR-7 / ADR-8 / future ADRs; splitting them
    five ways destroys the cross-cutting reading the deep-dive §3
    + §3a was authored to provide. Future amendments cannot point
    at a single citable URL for «the invariant slate»; DIGEST.md
    cannot summarise a five-way-split rule set in one paragraph.
    I-5 spans rtk R8 (parsing call site) + icm IC1 (MCP layer
    boundary) — no single existing ADR is the right home. Lesson:
    re-opens only if v0.2 collapses the cross-cutting reading
    (e.g. all 5 invariants ended up applying to a single layer);
    not anticipated under UC1 + UC3 single-user scope.
  - **Option B — One micro-ADR per invariant (5 new ADR files).**
    Reason: five files for five rules of identical shape is
    artefact bloat; the minimalism-first subtraction-check
    (AGENTS.md §Pre-flight Step 4) fails because one ADR already
    covers the cross-cutting scope. Lesson: re-opens if a single
    invariant grows enough internal structure (sub-rules, decision
    sub-options, per-component re-evaluation triggers) to justify
    its own §Decision / §Consequences block — at which point the
    invariant is graduated out of ADR-10 §1 into its own ADR.
  - **Option D — Inline I-1..I-5 directly into AGENTS.md as new PR
    Checklist rules.** Reason: AGENTS.md is procedural (how to
    author PRs); ADRs are architectural (what the harness MUST
    satisfy). Conflating the two erodes the existing «AGENTS.md =
    rules, knowledge/adr/ = decisions» separation. Rule #10
    already enforces the *evidence cells* for harness components;
    the invariants themselves belong in an ADR so future
    amendments follow the ADR amendment pattern, not the AGENTS.md
    amendment pattern. Lesson: re-opens if a rule needs PR-blocking
    enforcement at PR-creation time (today AGENTS.md rules are
    review-time gates, not pre-commit / pre-PR mechanical gates) —
    at which point inlining the rule into AGENTS.md is the right
    shape because the enforcement seat is the PR-author checklist.
  - **§1.2.5 placement as Pillar 5 in `project-overview.md` §1.1.**
    Reason: Pillars 1-4 declare what FA *is* (the product surface);
    compliance-by-construction is a how-axis principle that
    governs how harness components are built, not what the product
    *is*. Adding it as Pillar 5 would inflate the «what FA IS»
    surface with a «how FA is built» rule, eroding the categorical
    separation §1.2 already establishes. Lesson: re-opens if a
    product-surface deliverable emerges that is *itself* a
    compliance-by-construction artefact (e.g. UC5 ships a
    benchmark scoreboard whose existence is the principle made
    measurable); at that point the pillar count grows because a
    new product surface lands, not because the existing principle
    migrates. Source for the decision:
    [`research/fa-abc-synthesis-deep-dive-2026-05.md` §6b](../research/fa-abc-synthesis-deep-dive-2026-05.md#6b-125-placement-decision--compliance-by-construction).
- **Re-evaluation triggers:** (1) UC5 lands → KPI-delta on a
  reproducible benchmark replaces the rule #10 4-question evidence
  for measurably evaluated harness components; each I-N's
  «capability lost» clause grows a measured KPI reference;
  (2) MCP / external orchestrator surface lands → I-5's
  «outermost layer» definition expands; existing constants need
  the IC1-style cross-layer doc-comments; (3) second LLM-emitted
  numeric dimension surfaces → I-1 + I-3 + the deep-dive's A28
  («enum-label + harness-derived weight») compose into a new
  binding rule; (4) first hook in `src/fa/inner_loop/hooks/`
  needs to write back to `LoopState` → I-4 forbids; re-evaluation
  trigger is a hook that NEEDS cross-`HookRegistry.fire()` state
  (answer: instance state on the hook, not `LoopState`); (5) a
  new B-bucket entry overlaps an existing classifier without a
  genuine orthogonal scope → I-1 forces delegation; the trigger
  is a B-entry whose classification logic is genuinely orthogonal,
  at which point the invariant accepts the new entry as a separate
  canonical site.
- **Open questions parked, NOT re-litigated here.** Deep-dive §6
  ships five unresolved Q1-Q5 (research-note local numbering, NOT
  exploration_log Q-N): A16 (`fa doctor`) scoring weights, A17
  (`fa verify-state`) auto-heal scope, A18 (`fa sanitize-tool-
  schemas`) urgency, B19 (tool-call coerce-then-check) coercion
  aggressiveness, B21 (input-side shield) scope. Each carries a
  «default proposal» clause; ADR-10 accepts the defaults and does
  not re-open. Deep-dive §6a Q6-Q9 resolved in the rtk-ai
  amendment session (A24 deferred, A28 audit yes, A29 explicit
  frontmatter category, I-5 audit deferred until ADR-10 lands —
  unlocked by this PR as follow-up work); §6b Q10 resolved as
  §1.2.5 placement (this PR's companion landing). ADR-10 does
  not re-open Q6-Q10.
- **Source:** [ADR-10](../adr/ADR-10-deterministic-harness-invariants.md)
  + input note
  [`research/fa-abc-synthesis-deep-dive-2026-05.md`](../research/fa-abc-synthesis-deep-dive-2026-05.md)
  §3 + §3a (invariant authoring), §4 + §4a (bucket-entry
  cross-refs), §6 + §6a + §6b (open-question state +
  placement decision).

## Q-15 — How does FA classify the intent of a PR, and how does it enforce the anti-shallow-fix gate? (2026-05-25)

- **Closed by:** [`AGENTS.md` §PR Intent Classification](../../AGENTS.md#pr-intent-classification)
  (5-intent closed enum + Level-2 CLASS sub-classifier scoped to
  `INTENT: FIX`) + [`project-overview.md` §1.2.5 anti-shallow-fix
  gate](../project-overview.md#125--compliance-by-construction-failure-observable)
  (declarative principle) + [`AP-003-shallow-fix-no-mechanism.md`](../anti-patterns/AP-003-shallow-fix-no-mechanism.md)
  (anti-pattern catalogue with synthetic worked-history; forward-
  acting placeholder until first real escalation). Mechanisation
  lands as PR B (`src/fa/hygiene/pr_intent.py` + `prepare-commit-msg`
  + `commit-msg` git hooks; tracked in `HANDOFF.md`).
- **Coupling:** Q-14 (ADR-10 deterministic-harness invariants — I-1
  single-source-of-truth classifier is the structural principle the
  PR-intent classifier instantiates; §1.2.5 the anti-shallow-fix
  gate lives in is the same §1.2.5 ADR-10 §1.2.5-companion landed);
  Q-7 (ADR-7 inner-loop & tool-registry — PR C will land a
  harness-side `IntentGuard` GuardMiddleware on `BEFORE_TOOL_EXEC`
  after PR B's classifier module is reusable from the runtime);
  Q-8 (ADR-8 HookRegistry — same; the IntentGuard plugs into the
  GuardMiddleware seat verified landed in the audit pass at session
  start); AP-001 (cost-asymmetry-trap rationale shared verbatim
  — AP-003 is the forward-acting sibling); AP-002 (routing-index
  drift — `knowledge/llms.txt` refresh required per PR Checklist
  rule #7 because this PR adds AP-003 and rewrites two §-anchors).
- **Chosen:** **Option E** — two-level taxonomy with five Level-1
  intents (`RESEARCH / ADR-RULE / IMPLEMENT / FIX / CHORE`) and a
  Level-2 CLASS sub-classifier (`REPAIR / RELAX / WORKAROUND`)
  scoped to `INTENT: FIX` only. The anti-shallow-fix gate ships as
  a §1.2.5 operational clause (not a standalone §1.2.6) with two
  mandatory clauses for FIX PRs (`DEGREE-OF-FREEDOM CLOSED:` +
  `DETERMINISTIC MECHANISM:`), the latter requiring a
  `repo/file.ext:line` citation OR explicit `n/a (reason)`.
  Mechanisation lands in a separate PR B (`src/fa/hygiene/
  pr_intent.py` + `prepare-commit-msg` + `commit-msg` hooks) so
  PR A is doc-only (six files, no `src/` touches) and lints
  immediately. AUDIT collapses into RESEARCH (no separate
  intent label; audit-style sweeps are read-only research that
  feed downstream ADR-RULE or CHORE follow-up PRs); rationale
  recorded in Rejected (d) below.
- **Rejected:**
  - **(a) Keep `§Change Classification` (REPAIR / RELAX /
    WORKAROUND as top-level taxonomy) and add an
    `ADR-CREATE` exception clause.** Reason: the existing
    `§Change Classification` rule is a *fix-relation* taxonomy
    (how a change relates to a pre-existing invariant), not an
    *intent* taxonomy (what kind of work the PR is doing). Adding
    an `ADR-CREATE` exception compounds the category error —
    «ADR-CREATE» does not relate to any pre-existing invariant
    because the invariant is what the ADR introduces. The PRs that
    already shipped under the existing rule shipped either with
    strained reasoning (PR #15 forced `RELAX` for what was
    structurally `ADR-RULE` work) or without the header at all
    (PRs #13 / #51). Lesson: re-opens if a future taxonomy-
    clarifier proves cleaner than the two-level split (e.g. a
    single label encoding both intent and fix-relation
    deterministically) — not anticipated under UC1 + UC3
    single-user scope.
  - **(b) Land the anti-shallow-fix gate as a standalone
    `§1.2.6 anti-shallow principle`** (sibling to §1.2.5
    compliance-by-construction). Reason: the gate IS the
    operational reading of «the LLM never has a degree of
    freedom on a spec-bearing decision» — duplicating it in §1.2.6
    would create two principles saying the same thing, which is an
    I-1 single-source-of-truth violation. The gate is the
    operational *clause* of §1.2.5, not a new principle. Lesson:
    re-opens if §1.2.5 grows enough orthogonal sub-clauses (≥3
    independent operational rules with distinct decision
    procedures) that splitting them improves readability — not
    expected until UC5 measurability lands and the five KPI
    candidates each get an operational clause of their own.
  - **(c) PR-description-only enforcement (no `prepare-commit-msg`
    hook).** Reason: PR descriptions are post-hoc prose, written
    after code is complete. The action-count cost of «remember to
    write the four-line header AFTER writing the code» is the
    exact failure mode
    [`AP-001` §Why-wrong-shape-dominates](../anti-patterns/AP-001-spec-bypassing-workaround.md#why-the-wrong-shape-dominates)
    lines 116–119 catalogue: «action-count drift dominates rule-
    count drift in weaker LLMs; the structural fix must reduce
    the number of actions the LLM has to take to surface the
    contradiction, not add to it.» A pre-commit hook that pre-
    populates the buffer before the agent composes is an
    action-count cut, not a rule addition. Lesson: re-opens if
    pre-commit infrastructure becomes a maintenance burden (e.g.
    the hook itself drifts from the rule it mechanises) — at
    which point the right fix is to make the hook generate from
    the rule file's frontmatter, not to drop the hook.
  - **(d) Keep `AUDIT` as a distinct sixth intent in the enum
    (alongside RESEARCH).** Reason: the path-shape that fires
    AUDIT (additions to `knowledge/research/*.md`) is identical
    to the path-shape that fires RESEARCH — `git diff --cached
    --name-status` cannot mechanically tell them apart. Three
    sub-options were considered: (A1) introduce
    `knowledge/audit/` as a separate directory making the
    classifier path-decisive but adding a new directory
    convention; (A2) hook offers RESEARCH as default and the
    agent overrides to AUDIT when applicable — relies on agent
    override per AP-001 §Why-wrong-shape-dominates;
    (A3) drop AUDIT entirely and let audit-style sweeps live
    under RESEARCH with the semantic distinction maintained in
    the PR description prose. **User chose A3** with the framing
    «audit IS research done on current repo state for finding
    gaps, logic errors, and other bugs for fix or cleanup via
    adr-rule change intent or chore» — audit is therefore a
    *flavor* of research whose findings feed downstream
    ADR-RULE / CHORE / FIX follow-up PRs, not a distinct
    PR-intent category. Five-intent enum is the result. Lesson:
    re-opens if AUDIT-style PRs grow a distinct downstream
    workflow that the classifier should route differently from
    RESEARCH PRs (e.g. mandatory follow-up issue creation) — at
    which point AUDIT graduates back into its own intent with the
    A1 directory convention as the path-shape discriminator.
  - **(e) `DETERMINISTIC MECHANISM:` as a free-text one-sentence
    field without `repo/file.ext:line` citation requirement.**
    Reason: presence-only check accepts meaningless values like
    `mechanism: fix` or `mechanism: handle the bug`. The
    `prepare-commit-msg` hook can verify field presence but not
    field semantic meaning. The minimal-cost tightening that
    closes the loophole is the `repo/file.ext:line` citation
    requirement — the hook reads the staged blob and verifies
    the file exists and the line number is in bounds. Cheap,
    mechanical, deterministic. `n/a (reason)` remains acceptable
    for FIX PRs with no agent-facing degree of freedom (pure
    type-bugs, refactors, dependency bumps). **User chose
    Option B1** (require `path:line` OR `n/a (reason)`).
    Lesson: re-opens if real FIX PRs systematically struggle to
    cite a producer-site `path:line` (e.g. the fix is genuinely
    multi-file and no single line carries the contract) — at
    which point the rule grows a `path:line1, path:line2`
    multi-citation form, not a free-text relaxation.
  - **(f) Seven-intent taxonomy with separate `ADR-CREATE` and
    `ADR-AMEND` labels** (drafted earlier in this session before
    the user's six-intent counter-proposal). Reason: the
    distinction between «introduce a new ADR» and «amend an
    existing ADR» is captured by the AGENTS.md PR Checklist rule
    #9 (which fires identically for both shapes — append to
    exploration_log, update DIGEST row, update HANDOFF bullet).
    Two labels for one mechanical workflow is rule-count drift
    without action-count payoff. Unified `ADR-RULE` cleanly
    covers both shapes plus AGENTS.md rule changes plus
    project-overview rule changes plus AP-* catalogue
    additions. Lesson: re-opens if amendment PRs grow a
    materially different mechanical workflow from create PRs
    (e.g. amendments require linking the original ADR's
    `proposed` PR, creates do not) — at which point splitting
    the label is correct because the workflows have diverged.
  - **(g) Single-intent classifier (no Level-2 CLASS sub-
    classifier; delete REPAIR / RELAX / WORKAROUND entirely).**
    Reason: REPAIR / RELAX / WORKAROUND captures a real
    fix-relation distinction that the anti-shallow-fix gate
    needs — the gate downgrades a FIX PR from REPAIR to
    WORKAROUND when the agent cannot name a non-tautological
    mechanism. Deleting the sub-classifier destroys the
    downgrade target and forces AP-003 to grow its own escalation
    taxonomy. Lesson: re-opens only if the anti-shallow-fix gate
    is itself dropped (e.g. UC5 measurability makes the
    REPAIR-vs-WORKAROUND distinction observable from KPI data,
    obsoleting the prose taxonomy).
  - **(h) Mechanisation in the same PR as the rule (no
    separate PR B).** Reason: PR A is doc-only (six files, no
    `src/` touches) and lands immediately with no CI risk. PR B
    is code (`src/fa/hygiene/pr_intent.py` + tests + git hooks
    registration) and has its own CI surface (unit tests +
    hook integration tests). Bundling forces a single PR that
    blocks on the slowest signal; splitting lets the rule land
    first and the mechanisation follow without coupling the
    review surfaces. Lesson: re-opens if the rule and the
    mechanisation drift between PR A merge and PR B merge (e.g.
    a third PR amends the rule before B lands) — at which point
    the right fix is to compress the timeline, not bundle the
    PRs.
- **Source:** [`AGENTS.md` §PR Intent Classification](../../AGENTS.md#pr-intent-classification),
  [`project-overview.md` §1.2.5 anti-shallow-fix gate](../project-overview.md#125--compliance-by-construction-failure-observable),
  [`AP-003-shallow-fix-no-mechanism.md`](../anti-patterns/AP-003-shallow-fix-no-mechanism.md),
  [`AP-001` §Why-wrong-shape-dominates](../anti-patterns/AP-001-spec-bypassing-workaround.md#why-the-wrong-shape-dominates)
  (cost-asymmetry framing AP-003 inherits).

### Amendment 2026-05-26 — Externalise to loadable skill (PR A')

- **Question (refined):** Once Q-15 locked the 5-intent
  classifier + anti-shallow-fix gate, **where** does the rule
  *live* — inline in AGENTS.md, or as a loadable skill the
  agent picks up on demand?
- **Chosen:** Externalise the full classifier + INVARIANT-content
  table + anti-shallow-fix gate to
  [`knowledge/skills/pr-creation/SKILL.md`](../skills/pr-creation/SKILL.md);
  AGENTS.md retains only a moved-stub marker on the old section
  heading plus PR Checklist rule #12 (the load-directive). The
  decision uses the `knowledge/skills/` directory canonicalised
  by [`borrow-roadmap-2026-05.md` §R-24](../research/borrow-roadmap-2026-05.md#r-24--filesystem-canonical-skill-store--safe-community-import)
  + the four-place commit already on disk
  ([`project-overview.md`:70](../project-overview.md),
  [`BACKLOG.md`:117](../BACKLOG.md),
  [`docs/glossary.md`:62-64](../../docs/glossary.md)).
  Closes BACKLOG I-9 path (b) by moving
  `knowledge/prompts/repo-audit-playbook.md` to
  `knowledge/skills/repo-audit/SKILL.md` in the same PR.
- **Rejected:**
  - **(i) Keep the rule inline in AGENTS.md (no skill).**
    Reason: AGENTS.md grows ~158 lines per externalised rule;
    every session pays the context-budget cost even when no PR
    is being opened. Lesson: re-opens if the skill-load
    mechanism never lands (R-24 deferred indefinitely) AND the
    rule shrinks below a context-budget threshold (~50 lines)
    where the externalisation overhead exceeds the savings.
  - **(ii) Use `knowledge/playbooks/` naming (per BACKLOG I-9
    path (b) wording).** Reason: R-24 (compiled 2026-05-13,
    one day after BACKLOG I-9 was added) explicitly chose
    `knowledge/skills/` and the four-place commit on disk
    ([`project-overview.md`:70](../project-overview.md), `BACKLOG.md`
    R-22, `docs/glossary.md` «Self-evolving» / «Skill» entries)
    pre-dates this PR. Renaming to `playbooks/` would force a
    later rename when the full R-24 store lands. Lesson:
    re-opens only if industry convention shifts away from
    `skills/` filesystem-canon (KAOS / Anthropic / Devin
    `.agents/skills/`) toward `playbooks/` — none of the three
    currently signal this.
  - **(iii) Co-locate the skill at `.agents/skills/pr-creation/SKILL.md`
    (Devin-native auto-load).** Reason: `.agents/skills/` is
    a Devin-specific convention; weaker OSS LLMs (DeepSeek 4 /
    Kimi 2.6) lack the auto-load harness, so they need a
    `knowledge/` path the AGENTS.md rule explicitly points at.
    Lesson: re-opens once a second skill lands and the dual
    surface (`.agents/skills/` symlink + `knowledge/skills/`
    canonical) is worth the conventions overhead.
  - **(iv) Bundle the skill creation with the repo-audit move
    in two separate PRs.** Reason: both moves share the same
    forcing function (introduce `knowledge/skills/` directory
    with a self-declaring README + first two skills) and the
    same llms.txt sweep. Bundling closes BACKLOG I-9 path (b)
    in one PR with no additional review surface. Lesson: re-opens
    if the repo-audit move develops conflicts with the
    pr-creation skill content review (none expected: repo-audit
    body is unchanged, only frontmatter normalised).
  - **(v) Keep the operational rules in `project-overview.md`
    §1.2.5 verbatim.** Reason: §1.2.5 is declarative (states
    the *principle*), the operational rules are the *forcing
    function* — different layers. §1.2.5 retains the principle
    and a 1-paragraph forward-pointer; the operational rules
    live in the skill so they are loadable on-demand. Lesson:
    re-opens if a non-PR-creation operational rule needs to
    fire from the same §1.2.5 principle and would benefit from
    inline placement (none currently identified).
- **Coupling:**
  - Q-15 (rule shape) — this amendment supersedes Q-15's
    «AGENTS.md hosts the rule» finding to «skill hosts the rule;
    AGENTS.md hosts the load-directive». The Level-2 CLASS
    sub-classifier and the anti-shallow-fix gate clauses
    (`DEGREE-OF-FREEDOM CLOSED:` + `DETERMINISTIC MECHANISM:`)
    carried verbatim from PR A. The Level-1 INTENT classifier's
    `ADR-RULE` row gained one path-shape entry (`knowledge/skills/**`)
    on top of PR A's `{knowledge/adr/ADR-*, AGENTS.md,
    knowledge/project-overview.md, knowledge/anti-patterns/AP-*,
    knowledge/MAINTENANCE.md}` set — not «unchanged». Reason:
    skills are themselves rule-bearing artefacts (the skill is
    where the PR-creation rule now lives), so amending an
    existing skill or adding a new one is functionally
    equivalent to an ADR amendment and the classifier must
    fire on that path-shape. Without the addition, future
    skill-only PRs (e.g. amending `pr-creation/SKILL.md`
    itself, or adding a third skill) would have no match
    and fall through to the no-label residual. Mechanism:
    `path-startswith` rule on `knowledge/skills/`, identical
    in shape to the existing `knowledge/anti-patterns/AP-*`
    rule. Side-effect deliberately disclosed because PR A'
    dogfood-classifies itself ADR-RULE via the union of
    `{AGENTS.md, knowledge/project-overview.md,
    knowledge/anti-patterns/AP-003, knowledge/skills/**}`,
    and the documentation must not claim «unchanged» when
    a path-shape was added — see Devin-Review comment on
    `HANDOFF.md:289-291` at PR #17.
  - Q-11 (anti-pattern catalogue → AP-001 / AP-003) — AP-003's
    `applies_to:` and Linked-rule cross-references re-point from
    AGENTS.md §PR Intent Classification to the skill; the
    forward-acting role is unchanged.
  - Q-14 (ADR-10 invariants) — I-2 («numbered MANDATORY
    workflows are A-bucket residue») constrains the skill body
    structure: tables are framed as **§Reference** (closed-enum
    lookup the hook reads), not as numbered «§Step 1 do X»
    orchestration. Decision points are explicitly judgement-bound
    only.
  - BACKLOG I-9 path (b) — closed by this PR with
    `knowledge/skills/` naming (per R-24, not the I-9 wording's
    `playbooks/`).
- **Source:** [`knowledge/skills/pr-creation/SKILL.md`](../skills/pr-creation/SKILL.md),
  [`AGENTS.md` §PR Intent Classification (moved-stub)](../../AGENTS.md#pr-intent-classification),
  [`AGENTS.md` PR Checklist rule #12](../../AGENTS.md#pr-checklist),
  [`knowledge/skills/README.md`](../skills/README.md),
  [`borrow-roadmap-2026-05.md` §R-24](../research/borrow-roadmap-2026-05.md#r-24--filesystem-canonical-skill-store--safe-community-import),
  [`BACKLOG.md` I-9 (closed)](../BACKLOG.md).
  > **Note 2026-05-26 (PR A' expansion):** the AGENTS.md
  > §PR Intent Classification moved-stub and PR Checklist rule
  > #12 cited in this Source list were deleted later the same
  > day when PR A' was expanded to absorb the full PR-creation
  > rulebook — see the «PR A' expansion» amendment block
  > below. The references above describe the **initial** PR A'
  > shape (one stub + one load-directive rule); they no longer
  > resolve against the head of AGENTS.md.

### Amendment 2026-05-26 — PR A' expansion (absorb full PR-creation rulebook)

- **Question (refined further):** Once PR A' externalised
  §PR Intent Classification to the skill, the user observed
  that AGENTS.md still hosted **all of the situational
  PR-creation rules** — PR Checklist rules #1–#10, §PR
  Description Style, the AI-Session trailer paragraph inside
  §Development Workflow, plus the context-budget rule #11 whose
  mechanical framing («≤ 100 k tokens, p90») under-stated the
  goal-oriented working discipline it should encode. AGENTS.md
  should retain **only** rules that fire on every session
  (repo navigation, style, pre-flight, cross-project
  anti-patterns, design invariants the session keeps loaded);
  rules that fire only at PR creation belong in the skill.
  **Where do the remaining PR-creation rules live, and how is
  rule #11 reframed so the universal portion stays in AGENTS.md
  while the PR-time declaration moves to the skill?**
- **Chosen:** Move §PR Checklist rules 1-10 + §PR Description
  Style + the AI-Session trailer paragraph into the skill;
  refactor rule #11 into a new AGENTS.md section
  **§Context-budget discipline** with a goal-oriented opening
  paragraph (collect what is necessary, navigate the repo, read
  only what moves the task forward) and the design invariant +
  a..d mitigation list retained verbatim; replace rule #12
  (load-directive) with a new AGENTS.md section
  **§Loadable skills** — a two-row table mapping trigger →
  skill (`pr-creation`, `repo-audit`). No stubs at the former
  heading sites per user direction («i dont like stubs,
  considering removing all of them (noise)»). Orphan citations
  to «AGENTS.md PR Checklist rule #N», «AGENTS.md §PR
  Description Style», «AGENTS.md §PR Intent Classification»
  cleaned up in a separate cross-ref-sweep pass on a top-10
  highest-impact list provided to the user.
- **Rejected:**
  - **(i) Numbering-stability stubs at each former §PR
    Checklist rule (N1/N2 from the planning table).** Reason:
    user explicitly rejected stubs as «noise»; preferred
    paying the cross-ref-sweep cost once over carrying 10
    one-liner stubs forever. Lesson: re-opens only if a tool
    chain emerges that depends on stable AGENTS.md anchor
    fragments (none currently exists; cross-refs are read by
    humans / LLMs that resolve forward-pointers fine).
  - **(ii) Sweep all 38 cross-refs in this same PR (N3).**
    Reason: doubles the PR's review surface and couples the
    structural pivot with a bulk find-replace. User chose to
    do the sweep manually as a separate pass on the top-10
    files. Lesson: re-opens if a future skill-externalisation
    PR carries enough cross-refs (~100+) that manual cleanup
    becomes more expensive than scripted bulk-replace.
  - **(iii) Keep rule #11 in §PR Checklist inline alongside
    #12 (C2 from the planning table).** Reason: rule #11's
    universal core (collect-what-is-necessary; design invariant
    ≤ 100 k; mitigations a..d) fires on every session's
    design decisions, not only when a PR is being opened —
    keeping it inside §PR Checklist hides the always-on
    discipline behind a PR-time gate. Splitting it (universal
    → new AGENTS.md section, PR-time → skill checklist item)
    matches the universal-vs-situational classification that
    drives the whole expansion. Lesson: re-opens if the
    universal portion shrinks below a context-budget threshold
    (~20 lines) where a dedicated AGENTS.md section is
    over-shape for the content.
  - **(iv) Move §Cross-project anti-pattern #4 (Prior-Art
    mapping in every new ADR) to the skill (P2 from the
    planning table).** Reason: anti-pattern #4 is a
    forward-only architectural lesson from neighbouring
    OSS-LLM stacks, not a PR-time gate. The §Cross-project
    anti-patterns block is the canonical home of that genre;
    splitting it weakens the lesson-coupling. User confirmed
    P1 (anti-pattern #4 stays in AGENTS.md) «пока что»
    (for now). Lesson: re-opens if anti-pattern #4 acquires
    a checklist-like enforcement surface that wants to live
    next to other PR-time gates.
  - **(v) Keep §PR Description Style in AGENTS.md as universal
    style guidance (S2 from the planning table).** Reason:
    §PR Description Style is 100 % PR-body content (language
    split, recommended structure, execution rules around bullet
    discipline, canonical examples); the underlying universal
    style rule (Russian prose for analytical content, English
    for identifiers) already lives in §Working in This Repo
    language-convention and in `knowledge/README.md`
    §Conventions. §PR Description Style is the PR-time
    application of that universal rule; it belongs in the
    skill. Lesson: re-opens if the language-convention rule
    fragments across additional artefacts (research notes,
    inline review-replies, commit-message bodies) and needs a
    single PR-applicable digest in AGENTS.md.
  - **(vi) Keep AI-Session trailer rule in §Development
    Workflow (W1 from the planning table).** Reason: the
    trailer is per-commit, not per-PR — but in this project
    every commit lands inside a PR-bearing branch (no direct
    push to `main`), so «per-commit» reduces to «per-PR-commit»
    operationally. The trailer is read by the post-merge audit
    path, which is a PR-level concern. Moving the rule into
    the skill keeps §Development Workflow scoped to branch /
    commit-message style universals that fire even outside
    PR sessions. Lesson: re-opens if a workflow emerges where
    commits land outside a PR (e.g. direct push to a long-
    running integration branch) and the trailer rule needs to
    fire on those commits without loading the skill.
- **Coupling:**
  - Q-15 Amendment 2026-05-26 (initial) — this amendment
    extends, not supersedes, the initial PR A'. The Level-1
    INTENT classifier's `ADR-RULE` row keeps the
    `knowledge/skills/**` path-shape addition from the initial
    Amendment; the broader move (rules 1-10 + PR Description
    Style + AI-Session trailer) does not change the classifier
    shape, only the skill body. PR A' (expanded)
    dogfood-classifies itself ADR-RULE via
    `{AGENTS.md, knowledge/skills/pr-creation/SKILL.md,
    HANDOFF.md, knowledge/llms.txt, knowledge/trace/exploration_log.md}`
    — the AGENTS.md and skill paths fire the rule; mirror
    files (HANDOFF.md, llms.txt ride-along, exploration_log)
    do not independently change the intent.
  - Q-14 (ADR-10 invariants) — I-2 («numbered MANDATORY
    workflows are A-bucket residue») applies to the absorbed
    §PR Checklist inside the skill: the section is framed as
    a **closed-list verification gate**, not as numbered
    «§Step 1 do X» orchestration. Each rule is independently
    verifiable; the order is documentation convenience, not
    workflow sequencing. The 4-question minimalism-first test
    embedded in rule #10 retains its sub-structure because the
    questions are decision-points, not steps.
  - §Cross-project anti-patterns (anti-pattern #4 «Prior-Art
    mapping in every new ADR») — stays in AGENTS.md per
    rejected option (iv); the skill's §PR Checklist rule #9
    (ADR PR triple) references the anti-pattern via the
    underlying mechanism (PR description must surface the
    prior-art axes), not by re-stating it.
- **Source:** [`knowledge/skills/pr-creation/SKILL.md`](../skills/pr-creation/SKILL.md)
  (expanded body: §PR Checklist / §PR Description Style /
  §AI-Session trailer absorbed),
  [`AGENTS.md` §Context-budget discipline](../../AGENTS.md#context-budget-discipline),
  [`AGENTS.md` §Loadable skills](../../AGENTS.md#loadable-skills),
  [`AGENTS.md` §Development Workflow](../../AGENTS.md#development-workflow)
  (AI-Session trailer paragraph deleted; cross-link to skill
  retained),
  [`HANDOFF.md` §Process / rule changes 2026-05-26 PR A'](../../HANDOFF.md#current-state-as-of-2026-05-26)
  (expanded scope disclosure).

## Q-16 — What authoring-time guardrail architecture does FA adopt, and how is it enforced? (2026-06-01)

- **Closed by:** [ADR-11](../adr/ADR-11-authoring-guardrails.md), consuming
  the SSOT blueprint
  [`ADR-11-Authoring-Guardrails-Blueprint.md`](../research/ADR-11-Authoring-Guardrails-Blueprint.md)
  (R-1..R-18). This block is the doc-only decision landing; the code
  ships across PR 1..PR 5 per the blueprint Appendix B rollout.
- **Coupling:** Q-14 (ADR-10 deterministic-harness invariants — ADR-11
  is the authoring-time complement to ADR-10's runtime invariants and
  uses a disjoint `ADR-11-I<N>` namespace per blueprint §10.0 to avoid
  collision with ADR-10's global `I-1..I-5`; ADR-11-I3 parity reuses the
  ADR-10 I-1 one-classifier-two-consumers seed in
  `src/fa/hygiene/pr_intent.py`); Q-15 (PR-intent classifier — the
  `pr_intent.py` ↔ `pr-creation/SKILL.md` snapshot test is the live
  I-FROZEN parity seed ADR-11-I3 generalises); Q-6 (ADR-6 sandbox —
  runtime/execution boundary that ADR-11's authoring-time boundary
  complements); AP-002 (routing-index drift — `knowledge/llms.txt`
  refresh required per PR Checklist rule #7 because this PR adds the
  ADR-11 file).
- **Chosen:** **Option D** — a two-tier Trusted Computing Base (TCB): a
  frozen, stdlib-only Level-0 kernel (`tomllib` manifest, sorted path
  enumeration, SHA-256 snapshot/kernel/rule-pack hashing, static
  allowlist dispatch, deterministic sorted diagnostics, fail-closed,
  exit 0/1) plus allowlisted Level-1 rule packs. Lands the
  `ADR-11-I1..I8` invariant slate (I1 Level-0 determinism; I2 severity
  lifecycle; I3 I-FROZEN parity; I4 AST-over-regex; I5 test-decay lock;
  I6 CI-not-pre-commit authority; I7 protected-path governance +
  realpath denylist; I8 I-BOOT session seam), binds every write target
  to a named active consumer (blueprint §9.9), and fixes the
  enforcement-ceiling at PR-only agent rights + required human review +
  a protected-path CI flag (blueprint §12.7). Concepts are borrowed from
  Hermes / Archon / Grafema / NeMo; their runtimes are not (R-7).
- **Rejected:**
  - **(a) Keep authoring checks scattered across `pytest` /
    `pre-commit` / review prose (status quo).** Reason: no authoritative
    surface; `pre-commit` rules are bypassable with `--no-verify` and
    review prose is unenforced; the untrusted-compiler threat is not
    modelled at all (the author can weaken the very check that would
    catch the patch). Lesson: re-opens only if the repo abandons
    LLM-authored PRs — not anticipated under UC1 + UC3.
  - **(b) Import a heavy rule engine (Grafema Datalog + RFDB / NeMo
    runtime rails).** Reason: dependency footprint is wrong for a
    Level-0 kernel (NeMo pulls `aiohttp`/`onnxruntime`/`pydantic`/
    `jinja2`, blueprint §7.7; Grafema ships a Rust Datalog evaluator);
    bootstrapping + false-positive management dominate the first PR,
    failing minimalism-first. Lesson: re-opens if cross-file analysis
    needs outgrow stdlib `ast` AND a vendored subset proves lighter than
    a bespoke rule — concept borrowed now, runtime deferred (R-7).
  - **(c) Enforce via standalone CODEOWNERS and/or `pre-commit` only.**
    Reason: standalone CODEOWNERS without branch protection + a required
    protected-path check is a false security boundary (R-9); none of the
    four OSS stacks rely on it alone; `.github/**` path-skips let a patch
    alter enforcement itself (NeMo `pr-tests-skip.yml` is negative prior
    art). Lesson: CODEOWNERS becomes load-bearing only if branch
    protection with required review is enabled — folded into the R-12
    bundle, not used standalone (blueprint §12.7 enforcement-ceiling).
- **Source:** [ADR-11](../adr/ADR-11-authoring-guardrails.md);
  [`ADR-11-Authoring-Guardrails-Blueprint.md`](../research/ADR-11-Authoring-Guardrails-Blueprint.md)
  §0/§1/§9/§10/§12.7/Appendix B.
