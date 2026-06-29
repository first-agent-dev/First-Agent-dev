# ADR-1 — v0.1 use-case scope

- **Status:** accepted
- **Date:** 2026-04-27
- **Deciders:** project owner (`0oi9z7m1z8`), Agent (drafting)

## Context

[`project-overview.md`](../project-overview.md) lists four use cases
explored in research:

1. UC1 — Persistent coding & PR management.
2. UC2 — Continuous multi-source research.
3. UC3 — Local documentation to wiki.
4. UC4 — Multi-user Telegram (10-person group).

Doing all four at once defeats the "pragmatic, medium-weight
hybrid" goal stated in
[`research/memory-architecture-design-2026-04-26.md`](../research/memory-architecture-design-2026-04-26.md)
§1. We need an explicit ranking and a deferral list before scaffolding.

User priorities (verbatim from PR-#17 review):

> 1 — coding+PR / 3 — local-docs-to-wiki (main)
> 4 — multi-user TG
> 2 — multi-source research (i can live with costly search once in a while)

Plus an end-to-end acceptance scenario (PR-#17 Q5):

> Agent делает полный цикл: ingest folder → search → edit code →
> push branch → open PR (UC1 end-to-end).

## Options considered

### Option A — Ship UC1 + UC3 in v0.1; defer UC4 and best-effort UC2

- Pros:
  - Smallest end-to-end footprint (no Telegram bot, no graph).
  - UC1 acceptance scenario is concrete and demonstrable.
  - UC3 falls out of UC1's chunker + retrieval almost for free.
  - UC2 stays available as best-effort LLM-fan-out without needing
    new infra.
- Cons:
  - UC4 multi-user namespacing, which shapes the volatile-memory
    design, is not exercised; we could miss design pressure that
    matters for v0.2.
  - "Best-effort UC2" can be brittle on token cost without measurement.

### Option B — Ship UC1 + UC4 in v0.1

- Pros:
  - Forces volatile-memory design (per-user namespacing) early.
  - Unique value vs hosted agents: Telegram-driven workflows.
- Cons:
  - Telegram bot infra + multi-user store ≈ 2× engineering cost
    of UC3.
  - User explicitly ranked UC4 below UC1 + UC3.
  - Pulls in Mem0-style volatile store from v0.2 → v0.1, against
    the architectural staging.

### Option C — Ship all four in v0.1

- Pros: complete demo.
- Cons: contradicts "pragmatic, medium-weight" goal; sprawling scope;
  uneven quality on each.

## Decision

We will choose **Option A** because the user's explicit ranking
puts UC1 + UC3 first and the end-to-end UC1 PR-creation flow is the
acceptance bar. UC2 is included as **best-effort retrieval-only**
(no new infra). UC4 is **deferred to v0.2** along with the
volatile-store work that will support it.

### Concrete v0.1 in-scope list

- UC1 end-to-end: ingest folder → search → edit code → push branch
  → open PR via `gh` CLI.
- UC3 docs-to-wiki: large-textual-file ingest into `notes/inbox/`,
  retrieval via grep + SQLite FTS5 BM25, LLM Q&A on top-k chunks.
- UC2 best-effort: LLM-fan-out on top-k chunks for cross-source
  questions; no graph layer, no special infra.

### Concrete v0.1 deferred list

- UC4 Telegram multi-user.
- Mem0-style volatile store and 4-op tool-call API.
- Embeddings / vector store.
- Binary-format extractors (PDF, DOCX) — see
  [`project-overview.md`](../project-overview.md) §4.
- YouTube / Whisper / video ingest.

## Amendment 2026-05-01 — UC5 added to deferred list

**Context.** During the cross-reference research session of
2026-05-01, the project lead added a fifth use case:

> UC5 — Semi-autonomous research/experiment across different
> LLM models on the same task, producing comparable research
> docs at the end with a comparison chart.

This is distinct from UC2 (continuous multi-source research)
and from agent-team orchestration: UC5 is a **single research
task executed by N different LLM models in parallel or
sequentially**, with a structured comparison report at the
end. Examples: «прогнать одну и ту же research-задачу через
Claude / Qwen / Kimi / GLM, получить 4 одностилевых ноты +
diff-chart».

**Decision (additive to the original Decision section).**

UC5 is **out of v0.1 scope** and added to the
`Concrete v0.1 deferred list`. Rationale:

1. UC5 requires a multi-LLM execution-runner that is not part
   of any v0.1 component (the inner-loop in ADR-7-future is
   single-LLM-per-session by design).
2. UC5 requires a templated research-doc structure beyond
   what `knowledge/README.md` §Frontmatter currently
   describes — specifically, a comparison-chart template
   covering side-by-side outputs.
3. UC5 has no overlap with UC1 acceptance scenario (PR-creation
   end-to-end); pulling it into v0.1 would force the
   "pragmatic, medium-weight hybrid" goal off-balance.
4. Architecturally, UC5 sits closer to **eval-harness** (see
   [`research/semi-autonomous-agents-cross-reference-2026-05.md`](../research/semi-autonomous-agents-cross-reference-2026-05.md)
   §6.7) than to agent orchestration. It will likely land
   as its own v0.2 ADR with a runner + comparison-template
   spec, not as an extension of the inner-loop.

**Notes.**

- The existing UC2 best-effort retrieval-only stays in v0.1
  and is **not** UC5: UC2 fans out a single LLM across
  multiple sources; UC5 fans out multiple LLMs across the
  same source. Keep these distinct.
- The `knowledge/research/` conventions (frontmatter v2,
  topic field) and `knowledge/llms.txt` indexing already
  provide the *foundation* a UC5 comparison-runner would
  need; no v0.1 work is required to keep UC5 unblocked for
  v0.2.

**Consequence.** UC5 is explicitly listed in the deferred
section so future sessions do not need to guess its status.
A v0.2 ADR (`ADR-N — UC5 multi-LLM eval-harness`) will be
drafted when v0.1 ships.

## Amendment 2026-05-06 — UC5 expanded to eval-driven harness iteration

**Context.** Project goal corrected (см.
[`project-overview.md` §1.1](../project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars)
Pillar 3 + Pillar 4) — efficient-claim verified through measurement.
UC5 must therefore extend beyond «прогнать research-задачу через 4
модели» (formulation 2026-05-01) to a closed iteration loop
benchmark → trace → modify → re-benchmark → leaderboard.

**Decision (additive, supersedes formulation in Amendment 2026-05-01).**

UC5 v0.2 expanded scope:

1. **(5a) Local benchmark suite.** Детерминированные fixtures под UC1
   + UC3, scoring без LLM-as-judge dependency где возможно. Storage:
   `eval/fixtures/<task_id>.md` (Markdown с frontmatter:
   `task_id`, `scoring_kind: exact | edit_distance | llm_judge | hybrid`,
   `expected:` блок).
2. **(5b) Trace consumption.** Eval reads
   `~/.fa/session-log/<run_id>/events.jsonl` (per ADR-7 trace-shape) и
   produces structured eval report (`eval/reports/<run_id>.md`)
   с per-task verdict + aggregate metrics: tokens/task, tool-calls/task,
   tools-in-context, API cost/task, success-rate.
3. **(5c) Iteration interface.** Предлагаемые модификации harness —
   через config files (`~/.fa/sandbox.toml`, `models.yaml`,
   `knowledge/prompts/*.md`, `~/.fa/skills/*.md`). **Не** через code
   rewrites в v0.2.
4. **(5d) Score tracking.** `eval/leaderboard.md` —
   append-only Markdown table; каждая итерация = новая строка с
   `iteration_id`, datestamp, KPI snapshot, citation на eval report
   и на изменённые config files.
5. **(5e) Out-of-scope для UC5 v0.2.** **Без** автоматического
   Meta-Harness-style proposer (это v0.3+); человек продолжает
   driving iterations на основе eval report. **Без**
   prompt-mutation-via-code (only manual / YAML edits). **Без**
   trans-model harness search (один target-model на iteration в
   v0.2).

**Связь с Pillar 4.** База Pillar 4 (skill-writing) реализуется в
v0.1 как функциональность агента — отдельный ADR-8 (TBD). UC5 v0.2
**опирается** на существующую к этому моменту skill-writing
capability как один из supported config-modification channels (5c).

**Notes.**

- KPI numbers Pillar 3 ([`project-overview.md` §3](../project-overview.md#3-success-metrics))
  фиксируются по результатам первого baseline-run UC5; до того стоят
  как `TBD`.
- Old Amendment 2026-05-01 формулировка не удаляется; expanded scope
  здесь — её superset (multi-LLM comparison остаётся подмножеством
  5a-5b при варьировании target-model).
- `eval/` directory is a **new top-level repo directory** (sibling
  to `src/`, `docs/`, `knowledge/`) created in the UC5 implementation
  PR (v0.2). Forward-references here are intentional.
- `exploration_log.md` получает блок-амендмент `Q-1 amendment 2026-05-06`.

## Consequences

- **Positive:** Clear scope for scaffolding (Phase S of the roadmap
  in `research/memory-architecture-design-2026-04-26.md` §9).
  ADR-3 can pick Variant A unambiguously. ADR-2 only needs to
  cover the three-role static routing actually used in v0.1.
- **Positive:** UC1 acceptance is mechanically verifiable (a PR
  was created in a controlled repo from an FA session).
- **Negative:** v0.2 will discover volatile-memory design pressure
  for the first time; we accept that risk in exchange for shipping
  v0.1.
- **Negative:** "Best-effort UC2" needs a token-cost guardrail to
  avoid surprise spend; partially mitigated by static role routing
  ([ADR-2](./ADR-2-llm-tiering.md)) which keeps multi-source
  fan-out on Planner-tier OSS rather than elite. Fully addressed
  only when per-role token budgets land — explicitly deferred (see
  ADR-2 §Consequences "Follow-up work").
- **Follow-up work this unlocks:**
  - PR-write allow-list config (`~/.fa/repos.toml`) — single user
    repo + FA itself for v0.1.
  - LLM-as-judge eval baseline for UC1/UC3 acceptance (gstack
    scaled-down).
  - v0.2 ADR slot reserved for "Volatile store + UC4 Telegram"
    once v0.1 is shipped.

## References

- [`project-overview.md`](../project-overview.md) §4 (in scope) and §5 (non-goals).
- [`research/memory-architecture-design-2026-04-26.md`](../research/memory-architecture-design-2026-04-26.md) §8 (use-case mapping) and §9 (roadmap).
- PR #17 review thread (`https://github.com/GITcrassuskey-shop/First-Agent/pull/17`) — user's verbatim priority ranking.
