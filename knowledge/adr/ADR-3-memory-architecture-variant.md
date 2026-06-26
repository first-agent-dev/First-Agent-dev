# ADR-3 — Memory architecture variant for v0.1

- **Status:** accepted
- **Date:** 2026-04-27
- **Deciders:** project owner (`0oi9z7m1z8`), Agent (drafting)

## Context

[`research/memory-architecture-design-2026-04-26.md`](../research/memory-architecture-design-2026-04-26.md)
proposes three memory architectures (Variant A "Mechanical Wiki",
Variant B "Hybrid Brain", Variant C "Layered KG") with a trade-off
table in §7 and a use-case mapping in §8.

User feedback in PR-#17 review (verbatim):

> почитав сравнение мне понятно, что
> Mechanical Wiki — сейчас
> Hybrid Brain — апгрейд позже
> Layered KG — overkill для этого проекта.

[ADR-1](./ADR-1-v01-use-case-scope.md) restricts v0.1 to UC1
(coding + PR end-to-end) and UC3 (local docs → wiki), with UC2
best-effort and UC4 deferred. UC4 is precisely the use case where
Variant B's per-user volatile store earns its complexity, so deferring
UC4 also deflates the v0.1 case for B.

## Options considered

### Option A — Variant A "Mechanical Wiki" for v0.1

Filesystem-canonical Markdown + frontmatter; deterministic write-
time chunker (multi-language); read-side = grep → SQLite FTS5 BM25;
no embeddings, no graph, no Mem0 pipeline. Hooks reserved for v0.2
upgrade.

- Pros:
  - Smallest LoC + smallest dependency surface (~600 LoC + sqlite
    stdlib + rank-bm25 / FTS5).
  - No LLM at write time except optional page-type classification —
    Coder-tier-friendly.
  - Aligns with user ranking and ADR-1 scope.
  - All v0.2 hooks (volatile/, embeddings/, graph/) can be added
    additively without rewriting v0.1 code.
- Cons:
  - Multi-hop reasoning weak — UC2 falls back to LLM-fan-out
    (acceptable per ADR-1).
  - No semantic NOOP (no Mem0-style cache hit-rate gain on
    repeated extractions) — fine because v0.1 has no long-running
    multi-session memory feature anyway.

### Option B — Variant B "Hybrid Brain" for v0.1

Two-tier memory: stable canon (PR-write) + Mem0 4-op volatile store
(`add/update/delete/noop`) with InformationContent gate.

- Pros:
  - Best-in-class for UC4 (deferred) and UC1 cross-session episodic.
  - Higher cache hit-rate from semantic NOOP.
- Cons:
  - ~2.5× LoC of Variant A; sentence-transformers + sqlite-vss
    dependency.
  - UPDATE / DELETE classification needs a top-tier or elite LLM,
    not Coder-tier (see ADR-2 routing) — adds Anthropic spend on
    every memory write.
  - UC4 deferred → main beneficiary of B's design isn't exercised
    in v0.1.

### Option C — Variant C "Layered KG" for v0.1

Write-time deterministic typed-edge extraction; lazy graph traversal
on multi-hop queries.

- Pros: best for UC2 (deferred) and richer UC4 (deferred).
- Cons:
  - Most LoC and most schema lock-in.
  - Graph cold-start is empty until corpus density materialises —
    poor v0.1 ROI.
  - User has explicitly labelled this overkill.

## Decision

We will choose **Option A (Variant A "Mechanical Wiki")** for v0.1.

Concrete v0.1 stack:

- **Canon:** filesystem-only (Markdown + YAML frontmatter, per
  [`knowledge/README.md`](../README.md)).
- **Chunker:** deterministic Python parsers covering Markdown /
  plain text + Python + Go + PowerShell + TypeScript / JavaScript +
  YAML / TOML / JSON. Implementation strategy left to a follow-up
  research note (likely `universal-ctags` for code + heading-aware
  chunker for Markdown + block-aware for config files).
- **Read-side:** three layers, lazily activated:
  1. `grep` over filename / title / tag.
  2. SQLite FTS5 BM25 over body chunks (built-in stdlib via
     `sqlite3`; no extra dep).
  3. Vector layer **scaffolded** (interface defined) but **not
     implemented** in v0.1 — see ADR-4.
- **No Mem0 pipeline, no graph layer, no embeddings in v0.1.**
- **`hot.md`** session summary, auto-archived to
  `notes/sessions/<date>.md` at session end (UC1 episodic-light).
- **Volatile-store hooks:** `src/fa/memory/volatile/` exists as an
  empty namespace with a documented interface contract. v0.2 fills
  it with the Mem0 4-op API.

### Explicit non-goals (for v0.1)

- No graph extraction (typed edges, PPR).
- No embeddings or vector index.
- No Mem0 4-op API.
- No automatic promotion of volatile→stable (because there is no
  volatile in v0.1).

These are not "later-maybe"; they are **explicit non-goals** for the
v0.1 milestone. v0.2 ADR will revisit each independently.

## Consequences

- **Positive:** v0.1 ships fastest; smallest surface to debug.
- **Positive:** Multi-language chunker is the highest-leverage
  module — user's UC1 acceptance scenario depends on it. Variant A
  forces us to nail it instead of distracting with vector / graph
  work.
- **Positive:** Mixed-LLM tiering (ADR-2) works cleanly because
  Variant A doesn't require Architect-tier LLM at write time.
- **Negative:** UC1 cross-session memory ("what did I think about
  this function 2 weeks ago") relies on session archive grep, not
  a queryable volatile store. Acceptable for v0.1; revisit in v0.2.
- **Negative:** UC2 (best-effort) costs more LLM tokens per
  multi-source question than B or C would. ADR-2 mitigates by
  budget-routing to Planner-tier OSS, not elite.
- **Follow-up work this unlocks:**
  - Detailed chunker design — **resolved** by
    [`research/chunker-design.md`](../research/chunker-design.md)
    plus [`ADR-5`](./ADR-5-chunker-tool.md) (universal-ctags +
    markdown-it-py for v0.1; tree-sitter explicit non-goal with
    re-evaluation triggers).
  - Storage backend ADR (`ADR-4`).
  - v0.2 ADR slot for "Volatile store + Mem0 4-op API".
  - v0.3 (or never) ADR slot for "Vector layer" / "Graph layer" with
    explicit triggers — see [`project-overview.md`](../project-overview.md) §7 OQ2 / OQ3.

## References

- [`research/memory-architecture-design-2026-04-26.md`](../research/memory-architecture-design-2026-04-26.md) §4 (Variant A), §7 (comparison), §8 (use-case mapping), §9.5 (B-with-C-hooks alternative the user rejected).
- [`research/llm-wiki-community-batch-2.md`](../research/llm-wiki-community-batch-2.md) §3.2 (llm-wiki-kit three-layer retrieval reference).
- [`research/agentic-memory-supplement.md`](../research/agentic-memory-supplement.md) §5 (sparks mechanical/semantic split — write-side reference).
- [ADR-1](./ADR-1-v01-use-case-scope.md) — what v0.1 must do.
- [ADR-2](./ADR-2-llm-tiering.md) — what LLM tier is available at each role.
- PR #17 review (`https://github.com/GITcrassuskey-shop/First-Agent/pull/17`) — user's verbatim variant ranking.
