# Architecture Decision Records (ADRs)

We record significant decisions as short ADRs, adapted from
[Michael Nygard's template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

## When to write one

Write an ADR when the decision:

- Locks in a trade-off that will be expensive to reverse, **or**
- Affects multiple modules or public APIs, **or**
- Picks between multiple credible options (frameworks, models, storage, orchestration).

You do **not** need an ADR for routine code-level choices.

## Process

1. Copy [`ADR-template.md`](./ADR-template.md) → `ADR-N-short-slug.md` (next integer, no padding).
2. Fill it in. Keep it under one page.
3. Open a PR titled `ADR: <short title>`.
4. Merge once reviewers agree with the decision, not just the wording.

## Index & cheat-sheet

[`DIGEST.md`](./DIGEST.md) — one-paragraph summary per accepted ADR
plus its amendments. Read this **instead of** the per-ADR files
unless your task needs schema / Consequences wording / full
Amendment text. Updated in the same PR whenever an ADR amendment
lands ([`pr-creation` skill PR Checklist rule #9](../skills/pr-creation/SKILL.md#pr-checklist)).
