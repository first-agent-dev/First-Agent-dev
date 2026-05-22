# ADR Digest — one-paragraph cheat-sheet

> **Purpose.** Cheat-sheet for agents and humans who need the gist of
> all accepted ADRs without reading the full source set. One paragraph
> per ADR + bulleted amendments. **The per-ADR file is the
> authoritative source** — this digest only paraphrases.
>
> **Maintenance rule.** When an ADR amendment lands, update the
> matching row here in the **same PR**. Per
> [AGENTS.md PR Checklist rule #9](../../AGENTS.md#pr-checklist).
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
  `AFTER_TOOL_EXEC`. The smoke canon root is
  `<workspace>/.fa/knowledge/trace/{codebase_map.json,gotchas.md}`
  so the live repo stays untouched (`.fa/` already in
  `.gitignore`); the T-2 real runtime keeps the canonical
  `knowledge/trace/` root. Discovery key is path-keyed
  (`"{tool/slug}/{path}"` for `fs.*`; `"{tool/slug}/{call_id}"`
  fallback) so two calls to the same tool against different paths
  no longer overwrite each other. No new `EventLog.kind` is added:
  the filesystem artifacts are the durable R-8 audit surface.
  Observer write failures \u2014 including the real
  `LearningObserver` \u2192 `record_discovery` \u2192 `OSError` chain \u2014
  surface in the existing `hook_decision` rows as
  `decision="observer_error_swallowed"` (for smoke CLI:
  `.fa/smoke-events.jsonl`), so no dedicated reader is added.
  Source:
  [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-8.

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

## See also

- [`README.md`](./README.md) — ADR process and ordered index.
- [`../trace/exploration_log.md`](../trace/exploration_log.md) — alternatives that were rejected at decision time + lessons (per ADR).
- [`../project-overview.md` §1.1](../project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars) — four-pillar project goal that all ADR decisions advance.
