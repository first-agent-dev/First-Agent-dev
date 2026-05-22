# Knowledge

Durable project knowledge for First-Agent. Everything here is:

1. **Committed** to the repo so it is versioned and reviewable.
2. **Cross-referenced** from Devin Knowledge notes where useful.
   (`docs/devin-reference.md` was archived 2026-05-08 — see header banner
   for the rationale; restored as a per-host gated entry once `llms.txt`
   learns to gate by agent host.)

## Layout

```text
knowledge/
├── README.md                 # this file
├── llms.txt                  # one-fetch URL index for LLM agents (llmstxt.org)
├── project-overview.md       # one-page product + scope snapshot
├── adr/                      # architecture decision records
│   ├── README.md
│   ├── DIGEST.md             # one-paragraph cheat-sheet per accepted ADR (rule #9)
│   └── ADR-template.md
├── anti-patterns/            # named anti-pattern catalog (AP-NNN-<slug>.md)
│   ├── README.md             # entry schema + Layer-1/2/3 detection model
│   └── AP-001-…              # worked example: spec-bypassing workaround
├── prompts/                  # reusable prompts
│   ├── README.md
│   ├── RESOLVER.md           # intent-to-template dispatcher
│   ├── research-topic.md
│   └── research-briefing.md  # goal-driven cross-reference workflow
├── research/                 # research notes
│   └── _template.md          # skeleton (frontmatter v1+v2 + §0 Decision Briefing)
└── trace/                    # exploration log — alternatives rejected at
    └── exploration_log.md    # decision time + lesson for re-opening branches
```

## Conventions

- One concept per file.
- Markdown only. **File-length tiers per
  [AGENTS.md PR Checklist rule #3](../AGENTS.md#pr-checklist):**
  - **Summaries / overviews:** <1000 lines.
  - **Deep-dive research:** <2000 lines.
  - **Readability > size.** Split topic-wise only when readability
    suffers, not because a numeric threshold has been crossed.
  - AGENTS.md rule #3 is the single source of truth for these
    limits; do not maintain a separate threshold here.
- Link to source URLs for any non-obvious claim.
- Research notes are written for two readers at once: Humans
  and LLM agents. Prefer Russian for analytical prose and
  recommendations so the human review path stays natural; keep exact
  protocol/API names, code, frontmatter keys, and direct quotes in the
  original language when precision matters.
- **Never silently overwrite.** When a file is superseded: mark the old
  file with `> **Status:** superseded by <link>` at the top, add a
  `superseded_by:` field to its frontmatter if present, and keep the old
  content for audit. See the critique-driven rationale in
  [`research/llm-wiki-critique.md`](./research/llm-wiki-critique.md).

### Provenance-frontmatter (for `research/` and any summary notes)

Any note that *synthesizes* multiple sources or contains
specific numbers/dates/names must carry a frontmatter:

```yaml
---
title: "<title>"
source:
  - "<url or repo path>"
compiled: "<YYYY-MM-DD>"
chain_of_custody: "<where to find the primary source for specific facts>"
claims_requiring_verification:
  - "<claim 1>"
superseded_by: "<path, if any>"
---
```

The minimum required fields are `source` and `compiled`. `chain_of_custody` is mandatory if
the note contains numbers, dates, quotes, or decisions that someone might
reference. The goal is not to lose the connection between the LLM-written summary and
the primary source. For more details, see
[`research/llm-wiki-critique-first-agent.md §9`](./research/llm-wiki-critique-first-agent.md#9-specific-edits-to-existing-files).

### Frontmatter v2 — optional fields (additive)

The schema above (v1) stays mandatory for new notes. The fields below
are **optional** and **additive** — existing files do not need to be
backfilled. They become useful once the agent starts maintaining a
typed index over the corpus (post-v0.1, see
[`adr/ADR-3-memory-architecture-variant.md`](./adr/ADR-3-memory-architecture-variant.md)
Volatile-store hooks).

All v1 fields above stay required. The v2 block adds only the
optional fields:

```yaml
---
# ... all v1 fields above (title, source, compiled, chain_of_custody) ...

# v2 optional fields
tier: stable          # stable | volatile
links:                # internal cross-refs (relative paths from this file)
  - "./other-note.md"
mentions:             # external entities (people, projects, papers, repos, URLs)
  - "OpenRouter"
  - "https://arxiv.org/abs/2504.19413"
confidence: extracted # extracted | inferred | ambiguous
# goal_lens: one-sentence research goal; mandatory for notes from
# prompts/research-briefing.md, optional otherwise.
goal_lens: "Reduce session-start context noise for future agents."
topic: pwsh           # corpus-grouping key for v0.2 SLIDERS-style extraction
---
```

Field semantics:

- **`tier`** — which memory tier the note belongs to. `stable` is the
  filesystem canon (PR-write); `volatile` is the v0.2 Mem0-style
  store (does not exist in v0.1). If absent, assume `stable`.
- **`links`** — explicit graph edges to other notes in this repo, as
  relative paths. Lets the future indexer build a citation graph
  without re-parsing prose.
- **`mentions`** — external entities referenced in the note. Free-form
  strings (names, URLs, repo handles). Used by the future indexer for
  external-entity recall.
- **`confidence`** — origin of the note's claims. `extracted` if
  copied verbatim from a primary source; `inferred` if synthesised by
  the author / LLM from multiple sources; `ambiguous` if the source-to-
  claim mapping is unclear and the note needs a verification pass.
- **`goal_lens`** — one-sentence research goal elicited at the start
  of a [`prompts/research-briefing.md`](./prompts/research-briefing.md)
  session (Stage 1: goal-lens elicitation). **Mandatory** for notes
  produced via that workflow; optional for older notes. Lets a future
  agent reading [`llms.txt`](./llms.txt) filter the corpus by current
  task without loading the note. Field stays additive — adding it to a
  pre-existing note does not constitute a schema bump.
- **`topic`** — corpus-grouping key. Free-form short string
  (`pwsh`, `trading`, `dotfiles`, `arxiv-rag`, …). Files that share
  a `topic` are expected to share enough structure that a v0.2
  SLIDERS-style extractor can amortize one schema-induction pass
  across the whole group (see
  [`research/sliders-structured-reasoning-2026-04.md`](./research/sliders-structured-reasoning-2026-04.md)
  §3.2 for the why; rationale for adding the field now is in
  [`research/cross-reference-ampcode-sliders-to-adr-2026-04.md`](./research/cross-reference-ampcode-sliders-to-adr-2026-04.md)
  §10 R-6). The chunker propagates the value into every `Chunk`
  produced from the file (see
  [`adr/ADR-5-chunker-tool.md`](./adr/ADR-5-chunker-tool.md)
  Amendment 2026-04-29). v0.1 retrieval ignores it; storing it
  now means v0.2 extraction does not require a full re-chunk.

None of these fields are validated by tooling yet. They exist so that
when v0.2 indexer lands, the additive backfill is mechanical, not a
schema migration.

### `notes/inbox/` — `topic:` is the cheap default

`notes/inbox/` is the v0.2 raw-capture directory (per
[`research/memory-architecture-design-2026-04-26.md`](./research/memory-architecture-design-2026-04-26.md)
§4 — "drop-in inbox watcher"). Files there are short and often
share a single subject across many entries (one PowerShell macro
folder, one trading-strategy notebook, one paper-summaries dump).
Tagging each file with `topic:` at capture time is the cheapest
possible way to keep the v0.2 SLIDERS amortization path open
without retro-tagging later. v0.1 inbox-watcher is not yet
implemented; this is documented here so that whoever ships it
adds the frontmatter pass-through from day one.

### `trace/` — exploration log

[`trace/exploration_log.md`](./trace/exploration_log.md) is a
telegraphic markdown overlay of the project's accepted ADRs. One
`## Q-N` block per ADR carries the alternatives considered: the
chosen option (`Chosen:`) and each rejected option with `Reason:`
(why rejected at decision time) + `Lesson:` (what new evidence would
make the branch attractive again). Cross-question coupling is noted
under `Coupling:`. This lets a future session read why Variant B / C
were rejected for v0.1 without re-reading every ADR end-to-end.
Origin: research note
[`ara-protocol-cross-reference-2026-05.md`](./research/ara-protocol-cross-reference-2026-05.md)
§9 R-1 (ARA `/trace/` Exploration Graph applied to FA's ADR set).
Format converted from YAML DAG to telegraphic markdown 2026-05-10
per Tsinghua NLAH finding (code → NL migration: +16.8 pp accuracy,
9× faster, 97% fewer LLM calls on `arXiv:2603.25723`).

Block shape (one per accepted ADR; amendments append a sub-section
referencing the parent `Q-N` via `Coupling:`):

```text
## Q-N — <one-line question> (YYYY-MM-DD)

- **Closed by:** [ADR-N](../adr/ADR-N-<slug>.md)
- **Coupling:** Q-M chosen option   ← omit if no coupling
- **Chosen:** <one-line statement of the accepted option>
- **Rejected:**
  - **<option name>.** Reason: <why rejected at decision time>.
    Lesson: <what new evidence would re-open the branch>.
  - **<option name>.** Reason: ... Lesson: ...
```

ADR text is the source of truth for any specific decision; this log
is a pointer overlay. New ADR PRs MUST append a block here —
see [`AGENTS.md` PR Checklist rule #9](../AGENTS.md#pr-checklist).

## What goes where

| If it is… | Put it in… |
|---|---|
| A decision we made (and why) | `knowledge/adr/` |
| Background research / literature summary | `knowledge/research/` |
| A reusable prompt | `knowledge/prompts/` |
| Exploration trail (which alternatives were rejected & why) | `knowledge/trace/exploration_log.md` |
| Project-wide context (mission, scope, users) | `knowledge/project-overview.md` |
| How-to / guide / reference | `docs/` (not here) |

## Routing — Where the agent looks for an answer

| Question type | Primary source | Secondary / verification |
|---|---|---|
| "What is our architecture for X?" | `docs/architecture.md` | ADRs in `knowledge/adr/` |
| "What decision did we make regarding Y and why?" | `knowledge/adr/` | — |
| "What did we find during the research of Z?" | `knowledge/research/<Z>.md` | Primary sources from `source:` frontmatter |
| Specific number / date / quote | **Always** the primary source (`source:` of the note), not the summary | — |
| Procedure / how-to | `docs/` | Future `SKILL.md` |

This same rule is documented in [`AGENTS.md`](../AGENTS.md#query-routing).
