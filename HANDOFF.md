# HANDOFF.md — for the next agent / session

> **Read this first if you are an LLM agent (Devin, Claude, ChatGPT,
> Cursor, etc.) starting a new session on this repository.**
>
> **Last updated:** 2026-05-22 by Devin session
> [`cf06efa54f3f49fb834438dac5532a0d`](https://app.devin.ai/sessions/cf06efa54f3f49fb834438dac5532a0d)
> — **M2 llms.txt size buckets (RELAX) + AP-002** stacks on `main`
> (PR #48 merged) and is the first **RELAX** dogfood of
> [`AGENTS.md` §Change Classification](./AGENTS.md#change-classification)
> introduced in M1. Replaces `(~N lines)` row format in
> `knowledge/llms.txt` with hybrid `(BUCKET, ~N lines)` where
> `BUCKET ∈ {S, M, L, XL}` at boundaries 300 / 800 / 1500 LOC. M2
> measured baseline drift: 16 of 58 rows had `|actual − claimed|
> > 10` LOC and 3 rows shifted bucket entirely (HANDOFF.md S→M,
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
> **Current update (2026-05-21, refined 2026-05-22 same PR, M0a
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
>
> **PR-4 review-fix iteration (2026-05-21).** Four follow-up
> commits on the same branch addressed Devin Review runs 1/2/3
> + a CodeQL nit, all gated and pushed:
> [`48138c2`](https://github.com/Bupitsa-ai/First-Agent-debloat/commit/48138c2)
> covered the missing YAML `_FLOAT_KEYS` parse tests;
> [`bf0ba14`](https://github.com/Bupitsa-ai/First-Agent-debloat/commit/bf0ba14)
> rewrote `CostExtractor` to return `list[CostObservation]` per
> ADR-7 §Sub-amendment 2026-05-21 «one row per artifact» mandate
> (was returning only the first artifact — silently undercounted
> USD when a tool emits multiple `cost=…` rows; will matter once
> T-2 LLM driver lands) and added the
> `_FAMILY_PATTERNS ⊆ KNOWN_FAMILIES` sync-invariant test promised
> by the `tests/test_roles.py` module docstring;
> [`48dabe3`](https://github.com/Bupitsa-ai/First-Agent-debloat/commit/48dabe3)
> rejected NaN/Inf at three layers (`CostObservation.__post_init__`,
> `CostGuardian.__init__`, `runtime_limits._FLOAT_KEYS` parser) —
> `float("nan")` and `float("inf")` parse without raising and NaN
> permanently poisons the rollup (`x + NaN == NaN`; `NaN > budget`
> always False so the gate silently stops denying);
> [`dd97972`](https://github.com/Bupitsa-ai/First-Agent-debloat/commit/dd97972)
> split three `assert x == DEFAULT is None` chained comparisons
> into explicit `is None` checks (CodeQL py/test-equals-none nit).
> Session-completion audit (out-of-tree): `/home/ubuntu/wave-3-session-audit.md`.
>
> **PR-26 deferred review threads landed in
> [`6fce6b3`](https://github.com/Bupitsa-ai/First-Agent-debloat/commit/6fce6b3)
> on `main` before this session started —** lockfile regex
> tightening (false-positive cases gone) + `BlockerMiddleware`
> AFTER trace-label docstring clarification both in. No follow-up
> needed; see §Open review threads (cleared) below.
>
> **Prior update:** 2026-05-20 by Devin session
> [`5f23505ec2a04caeb232bfe8d391010e`](https://app.devin.ai/sessions/5f23505ec2a04caeb232bfe8d391010e)
> — **PR-3 / Wave-2 stack #2** stacks on PR
> [#25](https://github.com/Bupitsa-ai/First-Agent-debloat/pull/25)
> and lands three more R-Ns from
> [`research/borrow-roadmap-2026-05.md`](./knowledge/research/borrow-roadmap-2026-05.md)
> §3: **R-4 pre-tool blockers** (`BlockerMiddleware` base + three
> subclasses — `RateLimitBlocker`, `LockfileBlocker`,
> `AuthExpiredBlocker` — observe at `AFTER_TOOL_EXEC` + gate at
> `BEFORE_TOOL_EXEC` with suppression windows from `RuntimeLimits`),
> **R-5 DSV YAML contracts** (`load_contracts_from_dir` batch loader
> + canonical `verifiers/*.yaml` for the three M-1 tools; smoke CLI
> seeds `VerifierObserver` automatically), **R-34 QA constants**
> (documented anchors `qa_max_iterations` / `qa_max_consecutive_errors`
> / `qa_recurring_issue_threshold` surfaced via `RuntimeLimits`; QA
> orchestrator itself is DEFER per roadmap §2.9). Same commit
> fixes a latent loader gap that silently discarded QA + R-4
> suppression keys from `~/.fa/config.yaml`. 411 tests passing
> (+29 over PR-2). Post-PR Devin-Review fix in `95c392a` accepts
> `0` for `*_suppression_seconds` keys (observe-only mode);
> 414 tests passing.
>
> **Two PR-26 review findings deferred to the next session** —
> see §Open review threads at the end of §Current state. Default
> first action for the next session: address both, push, then
> start Wave-3 stack #1.
>
> Two attachments produced for the next-session context (not
> committed to the repo — paste into the next session prompt):
> `wave-2-session-audit.md` (what landed) and
> `fa-wave-3-remaining-work.md` (combined borrow-roadmap + T-N
> minus done, with 7-column status table + Wave-3 grouping).
>
> **Prior-prior update:** 2026-05-20 by Devin session
> [`5f23505ec2a04caeb232bfe8d391010e`](https://app.devin.ai/sessions/5f23505ec2a04caeb232bfe8d391010e)
> — **PR-2 / Wave-2 stack #1** stacks on PR
> [#24](https://github.com/Bupitsa-ai/First-Agent-debloat/pull/24)
> and lands three R-Ns from
> [`research/borrow-roadmap-2026-05.md`](./knowledge/research/borrow-roadmap-2026-05.md)
> §3: **R-2 LoopGuard** (`GuardMiddleware` at `BEFORE_TOOL_EXEC` +
> `BETWEEN_ROUNDS` — identical-call repeat + same-path thrash
> detectors, thresholds from `RuntimeLimits`), **R-3 FailureClassifier**
> (deterministic `ToolError` → `RecoveryAction` mapping + observer
> emitting `kind="recovery_action"` rows), **R-6 attempt_history.json**
> (per-run writer + `knowledge/prompts/coder-recovery.md` reader-
> prompt fragment). 382 tests passing (+44 over M-1).
>
> **Prior update:** 2026-05-20 by Devin session
> [`5f23505ec2a04caeb232bfe8d391010e`](https://app.devin.ai/sessions/5f23505ec2a04caeb232bfe8d391010e)
> — PR
> [#24](https://github.com/Bupitsa-ai/First-Agent-debloat/pull/24)
> **M-1 inner-loop runtime scaffold** is now contract-conformant:
> JSON-Schema validation on `params` (ADR-7 §5), modify→re-validate
> + sandbox replay on every `Decision.modify` (ADR-7 §8), `SandboxHook`
> gates `fs.read_file` / `fs.write_file` paths (not only
> `fs.run_bash`), `events.jsonl` carries `ts` + `run_id` per ADR-7 §7
> schema, `hook_decision` rows persisted via `HookRegistry` event-sink,
> `RuntimeLimits` (max_iterations + bash_timeout) read from
> `~/.fa/config.yaml` (ADR-7 §Amendment 2026-05-20 rule 1 «never code
> constants»). 338 tests passing.
>
> **Prior update:** 2026-05-20 by Devin session
> [`b3ea514bc30848e9bf72b57aa8c28f6a`](https://app.devin.ai/sessions/b3ea514bc30848e9bf72b57aa8c28f6a)
> — Wave-0 + Wave-1 docs slate landed (PRs
> [#18](https://github.com/Bupitsa-ai/First-Agent-debloat/pull/18) /
> [#19](https://github.com/Bupitsa-ai/First-Agent-debloat/pull/19) /
> [#20](https://github.com/Bupitsa-ai/First-Agent-debloat/pull/20)):
> ADR-2 / ADR-6 / ADR-7 / ADR-8 amendments (2026-05-20 dated);
> three new inert Python modules (`fa.verifier`, `fa.tools`,
> `fa.hygiene`) + capability flags (`fa.config`) + pause sentinel
> (`fa.orchestration.pause`) + bash sandbox gate (`fa.sandbox`).
>
> **Prior update:** 2026-05-13 by Devin session
> [`22479f39c46f4ab7941d2fd667393aad`](https://app.devin.ai/sessions/22479f39c46f4ab7941d2fd667393aad)
> (ADR-7 §Amendment 2026-05-13 + ADR-6 §Amendment 2026-05-13:
> declarative per-role tool whitelist, B-NEW-1 from
> [`research/soviet-code-inspiration-2026-05.md`](./knowledge/research/soviet-code-inspiration-2026-05.md)).
>
> **Prior update:** 2026-05-12 (same Devin session) — port of
> upstream
> [GrasshopperBoy/First-Agent-fork PR #22](https://github.com/GrasshopperBoy/First-Agent-fork/pull/22)
> + ADR-7 §Amendment 2026-05-12 cross-referencing
> [`bootstrap-cost-baseline-2026-05.md`](./knowledge/research/bootstrap-cost-baseline-2026-05.md),
> earlier landed in main by session
> [`89c32745c44f47dea679af42ed2d2dd8`](https://app.devin.ai/sessions/89c32745c44f47dea679af42ed2d2dd8).

This file is a portable counterpart to the Devin Knowledge note
"First-Agent — current state pointer". Both contain the same
information. The Knowledge note auto-injects into Devin sessions;
this Markdown file exists for any LLM client that does not have
Devin's MCP context (Claude Code, Cursor, ChatGPT with repo
access, plain `git clone`).

If both disagree, the Devin Knowledge note is canonical (it gets
updated more often). When you finish a session that materially
changes the project state, update **both**.

## 60-second bootstrap

> The five steps below are a condensed bootstrap for agents that
> land on `HANDOFF.md` first (e.g. via plain `git clone`, no Devin
> MCP). The canonical routing surface for LLM agents is
> [`knowledge/llms.txt`](./knowledge/llms.txt) §MUST READ FIRST
> (six files, in order). If the two disagree, llms.txt is canonical
> — step 2 below reads it, which closes the gap.

1. Read [`AGENTS.md`](./AGENTS.md) — repo conventions, PR
   checklist, query routing.
2. Read [`knowledge/llms.txt`](./knowledge/llms.txt) — one-fetch
   index of every documentation file in this repo
   ([llmstxt.org](https://llmstxt.org/) convention).
3. Skim [`knowledge/project-overview.md`](./knowledge/project-overview.md)
   — what the project is, what v0.1 ships, what is non-goal.
4. Read [`knowledge/adr/DIGEST.md`](./knowledge/adr/DIGEST.md) —
   one-paragraph cheat-sheet for ADR-1..7 + amendments. Open the
   per-ADR file only when DIGEST is insufficient (exact schema,
   Consequences wording, full Amendment text).
5. Check the **Current state** section below for what is in
   flight right now.

You should now have everything you need. Do not crawl the repo
manually beyond this point.

## Current state (as of 2026-05-21)

- **Project stage:** **Stage 1** of the three-stage evolution
  (documentation + agent development через Devin). See
  [`knowledge/project-overview.md` §1.3](./knowledge/project-overview.md#13-three-stage-project-evolution)
  for the full ladder (Stage 2 — first-agent 0.1 локально + iteration
  через Devin; Stage 3 — first-agent self-improves, Devin as external
  advisor).
- **Inner-stage milestone:** Phase S scaffolding complete; design
  layer consolidating before first feature-module PR (Phase M).
  `src/fa/chunker/` exists per ADR-5 scaffolding, not yet end-to-end
  tested. No other feature module is implemented.
- **Working repos:** canonical
  [`GITcrassuskey-shop/First-Agent`](https://github.com/GITcrassuskey-shop/First-Agent);
  forks
  [`GrasshopperBoy/First-Agent-fork`](https://github.com/GrasshopperBoy/First-Agent-fork)
  and
  [`Bupitsa-ai/First-Agent-debloat`](https://github.com/Bupitsa-ai/First-Agent-debloat)
  are parallel work-trees — different agents (Devin sessions) run in
  different forks. PRs land upstream via cross-fork PR
  (`Contribute → Open pull request` on a fork page); the lead keeps
  `main` in sync across all three.
- **Architecture decisions (accepted, on `main` of both fork and upstream):**
  - [ADR-1](./knowledge/adr/ADR-1-v01-use-case-scope.md) — UC1
    (coding + PR write) and UC3 (local-docs-to-wiki) in;
    UC4 deferred; UC2 best-effort. **Amendment 2026-05-01:** UC5
    (semi-autonomous multi-LLM research/experiment) explicitly
    deferred. **Amendment 2026-05-06:** UC5 expanded to
    eval-driven harness iteration (5a benchmark suite, 5b trace
    consumption, 5c iteration interface, 5d score tracking /
    leaderboard, 5e out-of-scope exclusions) — additive,
    supersedes 2026-05-01 formulation.
  - [ADR-2](./knowledge/adr/ADR-2-llm-tiering.md) — static role
    routing (Planner / Coder / Debug / Eval) via
    `~/.fa/models.yaml`. **Amendment 2026-04-29:**
    `tool_protocol: native | prompt-only` field per role; v0.1
    inner-loop without Critic. **Amendment 2026-05-01:** MCP
    forward-compat tool-shape convention (JSON-RPC-shaped
    `name`/`params`/`result`/`error` for all tool dispatch).
    **Amendment 2026-05-12** (ADR-7-driven clarification):
    `error.code` is dual-mode `str | int` — ergonomic domain
    string internally, JSON-RPC numeric on the wire;
    implementations MUST map between the two at the transport
    boundary. **Amendment 2026-05-20:** Eval-role MUST be
    provider+family disjoint from Planner and Coder (regex slug
    extraction; ambiguous slugs MUST tag `family:` explicitly
    in `~/.fa/models.yaml`); «no cross-tier auto-escalation»
    rationale now cites Cornell P-1 (ICML 2025) + Simula P-2
    (2026) as primary sources — `ρ̂ ≈ +0.6` same-family vs
    `ρ̂ ≈ −0.05` cross-family. Cross-link to [ADR-7 §Amendment
    2026-05-20 rule 4](./knowledge/adr/ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule)
    (same family-disjoint rule applied to LLM-using hooks).
    **Sub-amendment 2026-05-21 (role layer):** the family
    extractor + `check_eval_disjoint` pure function ship as
    `src/fa/roles.py` (R-19 implementation; consumed by the
    `~/.fa/models.yaml` loader landing with the T-2 LLM driver).
    The rule now has runtime enforcement at two layers — the
    role layer (this sub-amendment, role-config load time) and
    the hook layer (the existing 2026-05-20 cross-link,
    `HookRegistry.register` time).
  - [ADR-3](./knowledge/adr/ADR-3-memory-architecture-variant.md) —
    Variant A (mechanical wiki, no embeddings, no graph,
    no Mem0).
  - [ADR-4](./knowledge/adr/ADR-4-storage-backend.md) — SQLite
    FTS5 (external-content mode); zero extra deps. **Amendment
    2026-04-29:** chunks schema extended with provenance fields
    (`parent_title`, `breadcrumb`, `byte_start/end`, `topic`).
  - [ADR-5](./knowledge/adr/ADR-5-chunker-tool.md) —
    universal-ctags + markdown-it-py. **Amendment 2026-04-29:**
    `Chunk` dataclass extended to match ADR-4 provenance fields.
  - [ADR-6](./knowledge/adr/ADR-6-tool-sandbox-allow-list.md) —
    Tool sandbox + path allow-list policy (deny-by-default,
    `~/.fa/sandbox.toml`, gitignore-style globs, audit log at
    `~/.fa/state/sandbox.jsonl`, one-shot CLI bypass).
  - [ADR-7](./knowledge/adr/ADR-7-inner-loop-tool-registry.md) —
    Inner-loop & tool-registry contract (MCP-shaped
    `ToolSpec`/`ToolResult`; five-tool `fs.*` catalog; two
    edit-shapes — `edit_file` string-replace default,
    `apply_patch` unified-diff off by default; JSON-Schema input
    validation; three-tier tool disclosure; trace separation
    `events.jsonl` ≠ `hot.md`; mini hook pipeline — `pre_tool`
    Sandbox + optional Approval, `post_tool` Audit; static
    layered prompt frozen at session start; 4-question
    subtraction-first acceptance block). **Amendment 2026-05-12** —
    cross-reference [`bootstrap-cost-baseline-2026-05.md`](./knowledge/research/bootstrap-cost-baseline-2026-05.md)
    measurement evidence (6-file irreducible core, ~80–95 K
    Devin / 70–95 K Arena context, `harness_id` motivation,
    re-evaluation trigger 5 = BACKLOG I-8, BACKLOG I-1 / I-2 /
    I-3 unblocked); documentation-only, no shape change.
    **Amendment 2026-05-13** — declarative per-role tool
    whitelist (B-NEW-1): `[roles.<name>].allowed_tools` block
    in `~/.fa/sandbox.toml`; enforced at dispatcher BEFORE
    `pre_tool` hooks; reject = `E_ROLE_WHITELIST`. Companion
    [ADR-6 §Amendment 2026-05-13](./knowledge/adr/ADR-6-tool-sandbox-allow-list.md#amendment-2026-05-13--roles-block-in-sandboxtoml)
    adds schema. Closes ADR-7 §11 R-4 forward-compat as
    finer-than-`[tool_groups]` variant. Knowledge-layer only
    (impl lands with inner-loop scaffolding PR per Next steps
    item 1). Source:
    [`research/soviet-code-inspiration-2026-05.md`](./knowledge/research/soviet-code-inspiration-2026-05.md)
    §0 R-1. **Amendment 2026-05-20:** retry-budget invariant
    (caps in `~/.fa/config.yaml`, never code constants);
    `max_iterations` default = 6 per YT-4 empirical anchor;
    intra-role retry temperature default `T=1.0` per Nitarach
    P-3 §4.1 (`ρ̂≈−0.12` vs `T=0.0` `ρ̂≈+0.6`); LLM-using
    hooks MUST use family ≠ acting-role (vacuous in v0.1,
    pinned for first LLM-using hook); BACKLOG I-2 sub-agent
    invocation rules (`generateText` not streaming, exclude
    `SpawnSubAgent`, `SUBAGENT_MAX_STEPS ≤ 100`). Knowledge-
    layer only. Source:
    [`research/borrow-roadmap-2026-05.md`](./knowledge/research/borrow-roadmap-2026-05.md)
    §R-7 / §R-23 / §R-28 / §R-29 / §R-30 +
    [`research/correlated-llm-errors-and-ensembling-2026-05.md`](./knowledge/research/correlated-llm-errors-and-ensembling-2026-05.md)
    §4.1 / §6 R-7 / R-8 / R-9. **Sub-amendment
    2026-05-21b (refined 2026-05-22 same PR, M0a follow-up
    2026-05-22):** R-8 `LearningObserver` is wired into
    `fa inner-loop-smoke`; smoke and the T-2 real runtime share
    the single canon root `<workspace>/knowledge/trace/`.
    Successful tool results upsert
    `knowledge/trace/codebase_map.json` with a path-keyed slug
    (`"{tool/slug}/{path}"` for `fs.*`, `"{tool/slug}/{call_id}"`
    fallback); failures append `knowledge/trace/gotchas.md`.
    Live-repo cleanliness comes from three forcing functions
    rather than a path bypass: deterministic-clock injection
    (`LearningObserver.now="2026-05-21T00:00:00Z"` for smoke;
    `None` for T-2 → live wall-clock), `record_gotcha`
    byte-suffix dedup, and a seed `knowledge/trace/codebase_map.json`
    baseline checked into the repo with a snapshot regression
    test. No new `EventLog.kind` is added because the
    filesystem artifacts are the audit surface; observer write
    failures (including the real `LearningObserver` →
    `record_discovery` → `OSError` chain) reuse the existing
    `hook_decision` / `observer_error_swallowed` row.
    **Worked-history cross-link (M1, 2026-05-22):** the M0a
    revert + reliability pattern is catalogued at
    [`knowledge/anti-patterns/AP-001-spec-bypassing-workaround.md`](./knowledge/anti-patterns/AP-001-spec-bypassing-workaround.md);
    Layer-1 forcing function at
    [`AGENTS.md` §Change Classification](./AGENTS.md#change-classification);
    Layer-2 named-invariant test at
    `tests/test_cli.py::test_invariant_adr7_r8_canon_root_is_knowledge_trace`.
  - [ADR-8](./knowledge/adr/ADR-8-hook-registry.md) —
    HookRegistry middleware-chain contract (doc-first; runtime
    BACKLOG M-1 — **closed by PR #24**). Five lifecycle points (`BETWEEN_ROUNDS` /
    `BEFORE_LLM_CALL` / `AFTER_LLM_CALL` / `BEFORE_TOOL_EXEC` /
    `AFTER_TOOL_EXEC`); two middleware kinds (`GuardMiddleware`
    may deny/modify, `ObserverMiddleware` read-only); dispatcher
    ordered-chain first-deny short-circuit, one mutation per
    dispatch (inherits ADR-7 §8); family-disjoint rule enforced
    at `register()` time per ADR-2 / ADR-7 §Amendment 2026-05-20;
    migration plan for v0.1 hooks (`SandboxHook` →
    `GuardMiddleware`/`BEFORE_TOOL_EXEC`; `ApprovalHook` →
    `GuardMiddleware`/`BEFORE_TOOL_EXEC`; `AuditHook` →
    `ObserverMiddleware`/`AFTER_TOOL_EXEC`). 8-project
    convergence cited. **Doc-only;** runtime tracked in
    BACKLOG M-1 (inner-loop scaffolding); each Wave-2 R-N PR
    (R-2 `LoopGuard`, R-3 failure-classifier, R-4 pre-tool
    blocker, R-22 PII walker) lands as ~100-LoC subclass of
    these base classes. Source:
    [`research/borrow-roadmap-2026-05.md`](./knowledge/research/borrow-roadmap-2026-05.md)
    §R-1 +
    [`research/dpc-messenger-inspiration-2026-05.md`](./knowledge/research/dpc-messenger-inspiration-2026-05.md)
    §3 +
    [`research/gortex-aperant-inspiration-2026-05.md`](./knowledge/research/gortex-aperant-inspiration-2026-05.md)
    §2. *Amendment 2026-05-20a* — adds an opt-in
    `Middleware.revalidates_after_modify` flag (default `False`)
    so the sandbox can re-check a `Decision.modify`-mutated payload
    without violating "already-run hooks 1..N-1 do not re-run".
    `SandboxHook` is the only opt-in today; the replay path is
    capped at one extra `handle()` per opted-in guard and one
    mutation per dispatch (regression in
    `tests/test_inner_loop_validation.py::test_modify_to_escape_is_caught_by_sandbox_replay`).
    *Amendment 2026-05-20b* — codifies that `BETWEEN_ROUNDS`
    fires at the start of every iteration **including iteration 1**.
    Session-level guards (`PauseGuard`, `LoopGuard`) attach here
    so an active pause sentinel or non-progress counter blocks the
    very first tool call. Kept the name `BETWEEN_ROUNDS` rather
    than renaming to `BEFORE_ROUND` to preserve verbatim alignment
    with DPC `dpc_agent/hooks.py:LIFECYCLE_POINTS` + Gortex
    `internal/hooks/dispatch.go` + borrow-roadmap §R-1.
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

[^github-pat]: GitHub Models uses Azure-hosted endpoints with
    GitHub PAT-based auth instead of OpenAI-style API keys;
    `OpenAICompatProvider` handles it without a dedicated adapter.
- **Wave-1 R-N triplet (PR-2 2026-05-20):**
  - **R-18** — Per-tier tool-shape registry at
    [`knowledge/prompts/tool-shapes.yaml`](./knowledge/prompts/tool-shapes.yaml)
    (anthropic / openai / qwen / deepseek / glm / kimi
    families) + role-switch handoff one-liner rule in
    [ADR-2 §Amendment 2026-05-20 (Wave-1)](./knowledge/adr/ADR-2-llm-tiering.md#amendment-2026-05-20-wave-1--per-tier-tool-shape-registry--role-switch-handoff-one-liner).
    Read-only metadata; harness injects the *previous* role's
    `handoff_one_liner` into the *next* role's prompt on every
    role-switch.
  - **R-21** — Five capability flags (deny-by-default opt-in):
    `ENABLE_DYNAMIC_TOOLS` / `REQUIRE_DYNAMIC_TOOL_SANDBOX` /
    `ENABLE_MCP_GATEWAY_MANAGEMENT` /
    `ENABLE_DYNAMIC_MCP_SERVERS` / `ENABLE_SERVER_OPS`, all
    default `False`, in
    [ADR-6 §Amendment 2026-05-20](./knowledge/adr/ADR-6-tool-sandbox-allow-list.md#amendment-2026-05-20--five-capability-flags-deny-by-default-opt-in)
    + Python skeleton at `src/fa/config.py` (frozen
    `Capabilities` dataclass + YAML parse). Layer-1 capability
    opt-in AND-ed with Layer-2 (per-role `allowed_tools`) at
    the dispatcher.
  - **R-25** — Pause-file sentinel pattern
    (`RATE_LIMIT_PAUSE` / `AUTH_PAUSE` / `RESUME`) at
    `src/fa/orchestration/pause.py`; four timeout constants
    match Kronos defaults (2h rate-limit wait / 30s poll;
    24h auth wait / 10s poll). Source:
    [`research/borrow-roadmap-2026-05.md`](./knowledge/research/borrow-roadmap-2026-05.md)
    §R-18 / §R-21 / §R-25.
  - **R-20 (Wave-1 follow-up PR-3)** — Bash sandbox gate at
    `src/fa/sandbox/{classifier,validators,path_containment,bash_gate}.py`
    (~715 LoC code + ~700 LoC tests). Three-layer pipeline:
    pattern classifier (`bash_classify.go` port — 5
    categories `READ_ONLY` / `GIT_WRITE` / `PACKAGE_INSTALL`
    / `DANGEROUS` / `GENERAL_WRITE`) + per-command validators
    (`bash-validator.ts` port — `rm` / `chmod` / `git` with
    5 deny rules) + symlink-resolved path containment
    (`path-containment.ts` port). Composer:
    `evaluate_bash(command, *, workspace_root) ->
    BashGateDecision`. Lands
    [ADR-6 §Amendment 2026-05-20 (Wave-1)](./knowledge/adr/ADR-6-tool-sandbox-allow-list.md#amendment-2026-05-20-wave-1--bash-sandbox-gate-three-layer-classifier--validators--path-containment).
    Wiring into inner-loop `run_shell` tracked in BACKLOG
    M-1. Source:
    [`research/borrow-roadmap-2026-05.md`](./knowledge/research/borrow-roadmap-2026-05.md)
    §R-20 +
    [`research/gortex-aperant-inspiration-2026-05.md`](./knowledge/research/gortex-aperant-inspiration-2026-05.md)
    Aperant items 6 + 13 / Gortex Tier-1 item M.
- **ADR slot reservation.** Closed by ADR-7 + ADR-8 above.
  History on the slot: `cross-reference-…-2026-04.md` §11
  supersession marks on Q-1 / Q-2.
- **Scaffolding:** `pyproject.toml`, Ruff, mypy, pytest,
  pre-commit, GitHub Actions CI, `Makefile`, `markdown-it-py`,
  and system dependency documentation for `universal-ctags`
  are in place. CI in fork is limited to Devin Review (GitHub
  Actions are configured upstream; in the fork they are
  effectively no-op).
- **Open PRs in fork.** Check
  <https://github.com/GrasshopperBoy/First-Agent-fork/pulls>.
- **Research notes that close design questions:**
  - [`research/memory-architecture-design-2026-04-26.md`](./knowledge/research/memory-architecture-design-2026-04-26.md)
    — three variants for memory (input to ADR-3).
  - [`research/chunker-design.md`](./knowledge/research/chunker-design.md)
    — five tool classes, coverage matrix, ten open questions
    (input to ADR-5).
- **Research notes added 2026-04-29 (no ADR yet, inputs for v0.1+
  implementation and v0.2 roadmap):**
  - [`research/how-to-build-an-agent-ampcode-2026-04.md`](./knowledge/research/how-to-build-an-agent-ampcode-2026-04.md)
    — inner-loop micro-architecture from Thorsten Ball / Amp;
    three-tool baseline (`read_file` / `list_files` / `edit_file`);
    mapping to ADR-1 / ADR-2 and UC1.
  - [`research/sliders-structured-reasoning-2026-04.md`](./knowledge/research/sliders-structured-reasoning-2026-04.md)
    — SLIDERS framework (Stanford OV AL, arXiv:2604.22294)
    for QA over long document sets; mapping to ADR-3 / ADR-4 /
    ADR-5 and v0.2 extraction-layer roadmap.
  - [`research/cross-reference-ampcode-sliders-to-adr-2026-04.md`](./knowledge/research/cross-reference-ampcode-sliders-to-adr-2026-04.md)
    — cross-reference review of the two notes above against
    ADR-1..5: gaps, tensions, 10 numbered recommendations
    (R-1..R-10) and 10 open questions answered by lead in §11.
    **Q-1 / Q-2 marked superseded 2026-05-01** (ADR-6 became
    sandbox; future inner-loop = ADR-7).
- **Research note added 2026-05-01:**
  - [`research/semi-autonomous-agents-cross-reference-2026-05.md`](./knowledge/research/semi-autonomous-agents-cross-reference-2026-05.md)
    — critical analysis of three sources on semi-autonomous LLM
    agents (deep-research-report, semi-autonomous-llm-agents
    research, `nextlevelbuilder/goclaw` repo) against ADR-1..6.
    Accept / defer / reject filtering with explicit reasoning.
    Source for ADR-2 §Amendment 2026-05-01 (MCP forward-compat)
    and ADR-1 §Amendment 2026-05-01 (UC5 deferred). Input for
    future ADR-7 inner-loop (ACI principle, hooks primitive).
- **Research notes added 2026-05-03:**
  - [`research/cutting-edge-agent-research-radar-2026-05.md`](./knowledge/research/cutting-edge-agent-research-radar-2026-05.md)
    — radar/backlog for First-Agent v0.1/v0.2 covering MCP/tool
    registry, ACI, hooks, memory, eval traces, sandbox/audit, and
    multi-agent coordination. Input for ADR-7 prep and future
    module PRs.
  - [`research/agent-ui-research-radar-v0-2-2026-05.md`](./knowledge/research/agent-ui-research-radar-v0-2-2026-05.md)
    — v0.2 UI radar covering Hermes Agent UI implementations,
    Pi surfaces/packages, OpenClaw gateway/UI forks, and
    Magentic-UI / DuetUI / AXIS research. Input for future
    UI/control-plane pre-ADR work.
- **Research note added 2026-05-07:**
  - [`research/efficient-llm-agent-harness-2026-05.md`](./knowledge/research/efficient-llm-agent-harness-2026-05.md)
    — consolidated research note for ADR-7 prep combining two
    upstream drafts (PR #37 + PR #38) into single source of
    truth. Nine resolved recommendations (R-1..R-9; 8 TAKE +
    1 DEFER, no surviving UNCERTAIN-ASK). Ships ADR-7 contract
    sketch (§10) — ToolSpec / ToolResult / Trace pseudo-schema +
    static layered prompt-assembly invariant + subtraction-first
    self-audit acceptance-block. Both upstream PR #37 and PR #38
    close without merge at cross-fork sync (lead action).
- **Measurement-evidence note added 2026-05-11, extended 2026-05-12:**
  - [`research/bootstrap-cost-baseline-2026-05.md`](./knowledge/research/bootstrap-cost-baseline-2026-05.md)
    — first persistent Pillar 4 datapoint. Initial release (PR #5,
    2026-05-11): three Devin ADR-7-prep sessions on a single-
    message prompt produced a convergent 7-file routing-compliant
    bootstrap core. Extension (PR #7, 2026-05-12): three Arena.ai
    Agent Mode sessions on the same prompt confirm the
    convergence on a different agent harness and tighten the
    finding — **6-file irreducible core** (`HANDOFF.md`,
    `knowledge/llms.txt`, `knowledge/adr/DIGEST.md`,
    `knowledge/adr/ADR-template.md`,
    `knowledge/research/efficient-llm-agent-harness-2026-05.md`,
    `knowledge/trace/exploration_log.md`) across all six
    ADR-7-prep sessions independently of model selection and
    agent harness. Bootstrap-floor across harnesses
    now 9 calls / 8 files / ~70 K (§6). Empirical structural
    evidence that 2026-05 readability refactor's routing signals
    work. Not a research-briefing note — §0 exempt per AGENTS.md
    rule #8. Re-measurement triggers in §9 (items 5-6 cross-link
    BACKLOG I-7 / I-8).

## Open review threads (cleared)

Both PR-26 Devin-Review findings carried over from the
2026-05-20 Wave-2 stack #2 session landed on `main` in
[commit `6fce6b3`](https://github.com/Bupitsa-ai/First-Agent-debloat/commit/6fce6b3)
before the 2026-05-21 Wave-3 stack #1 session started. No
follow-up needed; the section is kept as an audit trail of
what was deferred and how each was resolved.

1. **🚩 Lockfile regex `.lock\b` over-broad — LANDED in
   [`6fce6b3`](https://github.com/Bupitsa-ai/First-Agent-debloat/commit/6fce6b3).**
   Original report: comment 0002 on
   [`src/fa/inner_loop/hooks/blockers.py:185-197`](./src/fa/inner_loop/hooks/blockers.py).
   The `_LOCKFILE_MESSAGE` regex's bare `\.lock\b` / bare
   `lockfile` alternatives were dropped and replaced with
   contention-specific alternatives; matching negative-case +
   positive-case regression tests added in the same commit.

2. **📝 BlockerMiddleware AFTER_TOOL_EXEC trace-label semantic
   mismatch — LANDED in
   [`6fce6b3`](https://github.com/Bupitsa-ai/First-Agent-debloat/commit/6fce6b3).**
   Original report: comment 0001 on
   [`src/fa/inner_loop/hooks/blockers.py:162-168`](./src/fa/inner_loop/hooks/blockers.py).
   Docstring-only clarification applied per the bot's recommended
   disposition («GuardMiddleware that observes at AFTER_TOOL_EXEC»
   pattern documented); no `HookRegistry.dispatch` trace-label
   change — deferred until a second observe-while-guarding
   middleware materialises that would justify the broader change.

## Next steps (intended order)

0. **Wave-3 stack #2 status.** R-8 is landed: the
   existing `LearningObserver` now registers in `fa inner-loop-smoke`
   and writes the filesystem-canon trace artifacts at the canonical
   `<workspace>/knowledge/trace/codebase_map.json` +
   `<workspace>/knowledge/trace/gotchas.md` paths with a path-keyed
   discovery slug, a fixed-clock injection for smoke
   (`now="2026-05-21T00:00:00Z"`), `record_gotcha` byte-suffix
   dedup, and a seed `codebase_map.json` baseline + snapshot test.
   The T-2 real runtime will reuse this exact path with `now=None`
   for live wall-clock provenance once it lands. **R-32
   (anti-pattern catalog skeleton) is landed in M1** — see
   [`knowledge/anti-patterns/`](./knowledge/anti-patterns/README.md)
   and the §Current update «M1 anti-pattern catalog» block above
   for the three-layer model (Change-Classification prefix +
   named-invariant tests + review-time prompt).
   Remaining cheap-impl candidates from the 2026-05-21 7-column table:
   - **R-17 / R-16 / R-24** — need scope decisions from the
     project lead before queuing.
   - **R-31 / R-33** — need ADR-9 timing decision.
   - **T-2 LLM driver** — unblocks the R-45 cost guardian
     (artifact emitter currently dormant on baseline tools).

1. **Wave-2 stack #1 — R-2 + R-3 + R-6 (single PR).** Land
   `LoopGuard` (R-2) at `BETWEEN_ROUNDS` (`max_iterations`,
   `max_consecutive_failures`, `forbidden_action_repeats`),
   `FailureClassifier` + `RecoveryAction` (R-3) consumed by an
   `AFTER_TOOL_EXEC` observer that maps every `ToolResult.error`
   to a deterministic recovery hint, and `attempt_history.json`
   writer (R-6) used by the classifier to detect ping-pong
   patterns. Source contracts:
   [`borrow-roadmap-2026-05.md`](./knowledge/research/borrow-roadmap-2026-05.md)
   §3 R-2 / R-3 / R-6.
2. **Wave-2 stack #2 — R-4 + R-5 + R-34 (single PR).** Land the
   three concrete `BEFORE_TOOL_EXEC` blockers (R-4: workspace-root
   path check / forbidden-command list / capability-flag check)
   as `GuardMiddleware` subclasses next to the existing
   `SandboxHook`; extend `VerifierObserver` (R-5) to consume YAML
   DSV contracts from `~/.fa/verifier/*.yaml`; surface the
   HookRegistry guard constants (R-34) for the loop driver.
3. **(Alternative path)** — implementation of remaining
   release-gap items from `fa-0.1-release-gaps-2026-05.md`
   (attached by lead at session start, not committed; T-1 closed
   by PR #24, T-2 = LLM clients, T-3 = CLI surface, T-6 = SQLite
   FTS5 index). T-1 closed by PR #24; T-2 / T-3 / T-6 unblocked.
3. **Implementation PR — chunker.** Implement `src/fa/chunker/`
   with the `Chunk` dataclass and `Chunker` Protocol from
   [ADR-5 §Decision](./knowledge/adr/ADR-5-chunker-tool.md#decision)
   (now including provenance fields per 2026-04-29 amendment).
   **Hard gate:** the four sample-tests in
   [`research/chunker-design.md` §8](./knowledge/research/chunker-design.md#8-sample-test-plan-pre-implementation)
   must pass — including the PowerShell sanity-check on the
   project lead's real 1500-line `.ps1` (not synthetic). The
   project lead should provide the real `.ps1` and a
   representative Go sample before this PR is considered
   mergeable. Blocked-on item 1 (chunker indexer consumes
   `fs.read_file` from the inner-loop tool catalog).
4. **Chunker CLI surface.** Add `fa chunk <path>` for manual
   inspection of produced chunks as part of the chunker PR.
5. **R-3 edit-format fixture.** Run a 5-10 string-replace +
   5-10 unified-diff `apply_patch` test set on each
   tool-using model from ADR-2 (Qwen 3.6, Kimi 2.6, GLM 5.1,
   Claude latest, Nemotron 3 Super). Empirically verify that
   each model handles both edit-shapes; the result may flip
   the default in
   [ADR-7 §4](./knowledge/adr/ADR-7-inner-loop-tool-registry.md#4-edit-shapes-string-replace-and-apply_patch)
   via amendment (per ADR-7 §Consequences «Re-evaluation
   triggers» — HANDOFF item 5 fixture lands). Can run in
   parallel with item 1 (inner-loop scaffolding); not a
   blocker for either tool PR.
6. **Glossary** (cross-reference §10 R-8 + semi-autonomous
   note §7.8): add `MCP`, `Hook`, `ACI`,
   `Reflexion / Critic / Reflector`, `Self-evolving` terms
   to [`docs/glossary.md`](./docs/glossary.md). Most landed via
   the Wave-0 glossary expansion (2026-05-20 PR #18); audit
   remaining gaps before closing.
7. **v0.2 UI/control-plane pre-ADR** (optional after ADR-7 prep,
   or before if project lead prioritizes UI): use
   [`research/agent-ui-research-radar-v0-2-2026-05.md`](./knowledge/research/agent-ui-research-radar-v0-2-2026-05.md)
   to decide trace-viewer-first vs live-dashboard-first, local BFF
   shape, event schema, approval UI, and non-goals.

Phase-S item #7 (auto-generated `llms.txt`) is recorded in
[`docs/workflow.md`](./docs/workflow.md) as future work; not
blocking.

## Conventions worth knowing in 5 lines

- **Branch:** `devin/<unix-timestamp>-<slug>` from `main`.
- **Commit trailer:** every LLM-driven commit ends with
  `AI-Session: <session-id>` plus
  `Co-Authored-By: <human> <email>` (codedna pattern).
  Trailers must be in the squash-merge commit body — see PRs #19,
  #21, #23 for examples.
- **PR description:** every changed/new file listed as a clickable
  blob URL on the head branch (rule #6).
- **`knowledge/llms.txt`:** must be updated whenever `docs/` or
  `knowledge/` changes structure (rule #7).
- **Research note language:** notes are read by both humans and
  agents. Prefer Russian analytical prose and recommendations unless
  the project lead asks otherwise; keep protocol names, API fields,
  code, frontmatter keys, and direct quotes in their original language
  where precision matters.
- **Code fences:** always have a language tag (`python`, `yaml`,
  `text`, …); never a bare ` ``` ` opening.

## When to update this file

- After any PR merge that materially changes the project state
  (new ADR, new phase, new module, new big research note).
- Bump the **Last updated** date at the top.
- Also update the matching Devin Knowledge note (or replace it
  entirely with the body of this file — they are meant to be
  identical).

## Why this file exists

Pattern lifted from the educational angle of this project: every
convention should be discoverable via either Devin-specific
infrastructure (Knowledge note) **or** plain repo browsing
(this file). Forks of this repo as a starter template do not
necessarily use Devin; HANDOFF.md is what they get for free.
