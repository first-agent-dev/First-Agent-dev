# Anti-pattern catalog

> Single-purpose directory: one Markdown file per **named** anti-pattern
> the project has either rejected on principle or actually committed
> and reverted. Each file is the *durable* description; the
> [`exploration_log.md`](../trace/exploration_log.md) and ADR amendments
> stay focused on the decisions and chosen-vs-rejected branches, while
> the catalog entries stay focused on «what pattern, how to detect it,
> what to do instead».
>
> **Scope.** UC1 + UC3 single-user OSS-LLM harness (the rest of the
> project scope per
> [`knowledge/project-overview.md` §1.3](../project-overview.md#13-three-stage-project-evolution)).
> Entries are not generic «code smells» — they are FA-specific patterns
> with concrete repo evidence (commits, PR numbers, file paths).

## Why this lives in `knowledge/`

The project's documented behavior is that **weaker OSS LLMs (DeepSeek 4,
Kimi 2.6) ignore ~30+ rule-lines under attention load** — adding rule
#N+1 to [`AGENTS.md`](../../AGENTS.md) competes with rules 1..N for
attention and loses under load. The catalog therefore optimises for
**action count**, not rule count:

- One named, durable file per anti-pattern (cheap to grep, cheap to
  link from a PR description).
- Each entry pairs the **wrong** shape with the **right** shape and
  with the **forcing function** that detects the wrong shape — so the
  LLM does not need to remember the lesson, only to recognise the
  trigger and follow the link.
- Catalog entries are evidence-anchored: they cite the actual commit
  that produced the wrong shape (or the named open-source project that
  paid the lesson before us). No speculative anti-patterns.

This sits **alongside**, not duplicates,
[`AGENTS.md` §Cross-project anti-patterns](../../AGENTS.md#cross-project-anti-patterns),
which captures four citations from neighbouring agent stacks. The two
are complementary:

- §Cross-project anti-patterns — short, terse, in-rules-file, cites
  external evidence. Read every session at bootstrap.
- `knowledge/anti-patterns/AP-NNN-<slug>.md` — long-form, in-knowledge,
  cites our own commits and our own ADR amendments. Read on demand
  when a PR is about to commit a similar shape.

## Entry schema

Every `AP-NNN-<slug>.md` file MUST have these top-level sections, in
this order:

1. **Frontmatter** — `compiled:`, `applies_to:` (which ADR / which
   module the anti-pattern lives near), and optional
   `superseded_by:` if the entry has been re-classified.
2. **§Symptom** — the surface observation the agent would notice
   (one paragraph, ≤ 100 words). Example: «`fa inner-loop-smoke`
   pollutes `git status` with untracked files».
3. **§Wrong shape** — the pattern that was rejected, including the
   exact commit SHA (if it actually landed) or the speculative shape
   (if it was caught at review).
4. **§Right shape** — what the agent should do instead. Code-level
   if possible.
5. **§Why the wrong shape dominates** — the cost-asymmetry, attention,
   or incentive trap that explains why a reasonable LLM picks the
   wrong shape under any rough heuristic. This is the
   **mechanism**, not the outcome.
6. **§Detection** — the forcing function that catches the wrong shape
   before it lands (named test, CLASS-prefix line in PR / commit,
   review-time prompt, lint rule, …). Each layer is one bullet.
7. **§Linked-ADR** — the ADR or ADR amendment whose invariant the
   anti-pattern violates. Cross-linked from the ADR's worked-history
   note in the same PR that lands the entry.
8. **§Evidence** — commit SHAs, PR numbers, or external citations.
   No bare claims without anchor.

## How a new entry lands

1. Choose the next free `AP-NNN` (zero-padded three digits). The
   numbering is global, not per-ADR.
2. Copy the schema above. Fill every section; if a section is empty,
   the entry is not ready.
3. Cross-link from the relevant ADR's worked-history note, the
   relevant [`DIGEST.md`](../adr/DIGEST.md) row, and (if the entry
   captures a chosen-vs-rejected branch)
   [`exploration_log.md`](../trace/exploration_log.md).
4. Add a line to [`knowledge/llms.txt`](../llms.txt) §`Anti-pattern
   catalog (`knowledge/anti-patterns/`)` so future agents discover the
   entry via the routing surface, not by grep alone. The section name
   must match the heading in `knowledge/llms.txt:125` exactly so a
   `grep`-based agent finds it.
5. Include in the PR description: «Anti-pattern catalogued: `AP-NNN`
   ([link]). CLASS: <REPAIR|RELAX|WORKAROUND>. INVARIANT: <one
   sentence>.» — see
   [`AGENTS.md` §Change Classification](../../AGENTS.md#change-classification).

## Detector personas (deferred to M1+)

[R-32 in `borrow-roadmap-2026-05.md` §2.8](../research/borrow-roadmap-2026-05.md#28-group-h--agentsmd--adr-citations-cluster-r-26r-32-7-items)
spec'd «detector personas» — prompts that scan the codebase for a
specific anti-pattern on demand. The personas are **deferred** until at
least three entries exist (n=3 is the cheapest evidence that a generic
detector shape is worth designing). For now, the catalog is the
passive-read surface; detection happens through the
[`AGENTS.md` §Change Classification](../../AGENTS.md#change-classification)
forcing function + named-invariant tests
([test_invariant_adr7_r8_canon_root_is_knowledge_trace](../../tests/test_cli.py)
is the worked example).

## Index

| Entry  | Title                                                   | Linked-ADR                                                                                                                              | Status   |
| ------ | ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| AP-001 | Spec-bypassing workaround masquerading as fix           | [ADR-7 §Sub-amendment 2026-05-21b](../adr/ADR-7-inner-loop-tool-registry.md#sub-amendment-2026-05-21b--r-8-learningobserver-filesystem-canon-artifacts) | accepted |
