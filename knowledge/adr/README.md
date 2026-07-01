# Architecture Decision Records (ADRs)

We record significant decisions as comperhensive ADRs.

## Index & cheat-sheet

[`DIGEST.md`](./DIGEST.md) — one-paragraph summary per accepted ADR
plus its amendments. Updated in the same PR whenever an ADR amendment
lands ([`pr-creation` skill PR Checklist rule #9](../skills/pr-creation/SKILL.md#pr-checklist)).

## ADR creation rules
- for routine code-level choices use AGENTS.md conventios.

Write an ADR when the decision:
- Locks in a trade-off that will be expensive to reverse, **or**
- Affects multiple modules or public APIs, **or**
- Picks between multiple credible options (frameworks, models, storage, orchestration).
- Use [`ADR-template.md`](./ADR-template.md) → `ADR-N-short-slug.md` for each topic.
- Commit after reviewers agree with the decisions and all gaps are covered.
