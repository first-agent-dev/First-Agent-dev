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
