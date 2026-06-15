---
purpose: >
  Drive a research note from kickoff to a goal-driven Decision Briefing
  comprehensible to mid-tier LLMs and the project lead. Goal-lens is
  elicited at session start; the deep-dive note is produced with the
  Briefing as §0 (first section after frontmatter).
inputs:
  - source: research paper URL, repo path, or doc reference
  - slug: short kebab-case stem for the note (e.g. "ara-protocol-cross-reference")
  - goal_lens: one-sentence research goal; if absent the agent MUST ask before reading any source
last-reviewed: 2026-05-04
---

[Objective]
Produce `knowledge/research/<slug>-<YYYY-MM>.md` with a Decision Briefing
at §0 that lets the project lead pick TAKE / SKIP / DEFER / UNCERTAIN-ASK
on every recommendation in under 5 minutes — and lets a future LLM agent
read the §0 alone (≈150–250 lines) to learn what was decided without
loading the deep-dive sections below.

[Context]
- Knowledge layout: [`knowledge/README.md`](../README.md). Frontmatter v1
  is mandatory; v2 fields are additive. This workflow adds one optional
  v2 field — `goal_lens:` (one-sentence research goal).
- Existing template style: [`research-topic.md`](./research-topic.md)
  (T1) covers the basic "research a topic" intent; this prompt extends
  it for cross-reference / paper-vs-architecture reviews where there
  are multiple recommendations to triage.
- Convention: Russian for analytical prose / project recommendations;
  English for protocol names, frontmatter keys, code, direct quotes
  ([`AGENTS.md`](../../AGENTS.md#working-in-this-repo)).
- AGENTS.md PR Checklist rule #8 makes the §0 Decision Briefing
  mandatory for notes produced via this workflow.

[Approach]

Five stages. Stages 1, 3, and 5 are blocking on the user; the rest run
to completion before the next blocking point.

1. Goal-lens elicitation (blocking).
   Before reading any source, post a single chat message asking the
   user to pick a goal. This stage also satisfies
   [AGENTS.md §Pre-flight Step 5 — Goal-lens declaration](../../AGENTS.md#pre-flight-checklist):
   `goal_lens` is universal across sessions, but research-briefing
   sessions make the elicitation explicit instead of inferring it.
   Default options:
   - (a) Reduce session-start context noise for future agents
   - (b) Find one immediate-improvement implementable in next PR
   - (c) Gap analysis vs accepted ADR-1..N
   - (d) Archive for future sessions; no immediate change planned
   - Other: <free text>
   Capture the chosen option verbatim into frontmatter
   `goal_lens:` of the resulting note. Do not start Stage 2 without
   a goal.

2. Source ingestion.
   Read `<source>` plus any cited prior research / ADRs that bear on
   the goal_lens. Do not exceed the model's working window. If the
   source is large, read it in chunks; do not summarise prematurely.

3. Relevance gate (soft warning, blocking only on confirmation).
   If after Stage 2 the source clearly does not address the
   goal_lens, do NOT silently produce a 1000-line note. Post a
   single chat message: «Relevance to goal_lens "<text>" looks low
   because <one-sentence reason>; options: (i) write a short
   `<slug>-not-applicable.md` stub and stop, (ii) widen scope and
   continue, (iii) other.» Wait for the user.

4. Deep-dive note + Decision Briefing.
   Write the note to `knowledge/research/<slug>-<YYYY-MM>.md` using
   [`_template.md`](../research/_template.md) as the skeleton.
   Layout, top to bottom:
   - Frontmatter (v1 + v2 + `goal_lens:`).
   - `## 0. Decision Briefing` (see format below). This is §0,
     immediately after frontmatter, BEFORE the TL;DR and Scope.
   - `## 1. TL;DR` — 5–7 bullet points summarising the deep-dive.
   - `## 2. Scope, метод` — coverage / method / limits; restate
     `goal_lens` verbatim.
   - `## 3. Key concepts` — source-language term definitions used
     downstream. One-line per term.
   - `## 4..N. Mapping / analysis` — the actual cross-reference
     content. Use tables where the structure repeats. Subsections
     as needed (4.1, 4.2, …).
   - `## N+1. Risks and caveats` — caveats, unverified claims, things
     that constrain the recommendations.
   - `## N+2. Numbered recommendations (R-1..R-K)` — the long-form
     prose for each R; the §0 Briefing references back here for
     details. R-numbering and cost-tags follow the convention in
     [`cross-reference-ampcode-sliders-to-adr-2026-04.md`](../research/cross-reference-ampcode-sliders-to-adr-2026-04.md).
   - `## N+3. Open questions (Q-1..Q-M)` — anything unresolved.
   - `## N+4. Files used` — the source list.
   - `## N+5. Out of scope` — what this note deliberately does not
     cover.

5. Chat handover (blocking on UNCERTAIN-ASK verdicts).
   Post the §0 Decision Briefing verbatim in chat as a non-blocking
   message. For every R with `Verdict: UNCERTAIN-ASK`, ask the user
   the question in the briefing using a `user_question` UI with the
   3–4 options listed. Once the user has answered each
   UNCERTAIN-ASK, update §0 in the note (TAKE / SKIP / DEFER) and
   open the PR. If `goal_lens:` was option (d) "archive", skip this
   stage entirely — open the PR with the Briefing as-is; there is
   nothing to iterate on.

[Decision Briefing format]

Every R-N in §0 follows this fixed shape (English keys, prose-language
follows the note's prevailing language):

```text
### R-N — <short title>

- **What:** 1–2 sentences, plain language, no jargon.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~X tokens saved) | NO | UNKNOWN
  - (B) helps LLM find context when needed: YES (pointer-shape) | NO | UNKNOWN
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "<verbatim from frontmatter>": YES
    (1-sentence reason) | PARTIAL (1-sentence caveat) | NO
- **Cost:** cheap (<1h) | medium (1–4h) | expensive (>4h)
- **Verdict:** TAKE | SKIP | DEFER | UNCERTAIN-ASK
- **If UNCERTAIN-ASK:** <one question, 3–4 concrete options>
- **Alternative-if-rejected:** <one sentence; the path-not-taken if
  user picks SKIP / DEFER>
- **Concrete first step (if TAKE):** <file path / command / 1-line
  action>
```

Eight top-level fields. (A) and (B) are stable project-axis criteria
(bootstrap-budget, pointer-shape) — they evaluate the same way for
every note in the corpus, so notes are cross-comparable on these axes.
(C) is per-session: it answers "does this R advance the goal_lens
the user picked in Stage 1?" and is the only place in §0 where the
chosen goal_lens reappears.

Closing: a 7-column summary table inside §0:

```text
| R-N | Verdict | Project-fit (A / B) | Goal-fit (C) | Cost | Alternative-if-rejected | User decision needed? |
```

The Goal-fit column carries a Y / PARTIAL / N indicator plus a
2–3-word tag; the full 1-sentence reason lives in the per-R block
above. Use `n/a` in any cell that does not apply, with a one-clause
reason.

[Constraints]
- Markdown only.
- File length tier: deep-dive (<2000 lines) per
  [`pr-creation` skill PR Checklist rule #3](../skills/pr-creation/SKILL.md#pr-checklist).
- Frontmatter v1 mandatory; `goal_lens:` mandatory (this workflow);
  other v2 fields optional and additive.
- No code changes inside this PR. Implementations of TAKE
  recommendations land in follow-up PRs.
- Do not use trigger phrases that require Russian-only matching;
  English-only triggers (see RESOLVER intent table).
- Do not retro-fit existing notes (`compiled: < 2026-05-04` are
  exempted by AGENTS.md rule #8).

[Acceptance]
- File `knowledge/research/<slug>-<YYYY-MM>.md` exists.
- Frontmatter contains `goal_lens:` capturing the user's chosen goal.
- §0 `## 0. Decision Briefing` is the first section after the
  frontmatter; every R-N follows the eight-field format above; a
  7-column summary table closes §0.
- For every R-N with `Verdict: UNCERTAIN-ASK`, the user has been
  asked in chat and the verdict is updated in the file before the
  PR is opened (exception: `goal_lens: archive` skips iteration).
- PR description lists changed/new files as clickable blob URLs
  (rule #6) and `knowledge/llms.txt` is updated to add a row
  pointing at the new note with the `[goal: <one-sentence>]` prefix
  (rule #7).

[Out of scope]
- Implementing any R-N (separate PRs).
- Editing existing research notes (use supersession, not overwrite).
- Modifying ADRs based on this note (separate PRs after lead approval).

## Example — Decision Briefing applied retroactively to ampcode/SLIDERS R-1

The example below applies the eight-field Decision Briefing format to
R-1 from
[`cross-reference-ampcode-sliders-to-adr-2026-04.md`](../research/cross-reference-ampcode-sliders-to-adr-2026-04.md)
§10. That note pre-dates this workflow, so the briefing here is
synthetic — reconstructed from the existing prose to anchor the
canonical shape. Use it as the structural template; do not alter the
eight-field layout.

Assume the session's `goal_lens:` was option (b) — "Find one
immediate-improvement implementable in next PR" — to make the (C)
axis evaluable.

```text
### R-1 — New ADR "Agent inner-loop and tool contract for v0.1"

- **What:** Accept a new ADR specifying the Coder ↔ tools contract:
  Tool-Protocol shape (name / description / input_schema / fn),
  inner-loop pseudocode (~50 lines), pydantic input validation,
  tool-call audit-log, Ctrl-C cancellation, and `tool_protocol:
  native | prompt` negotiation in `models.yaml`. None of ADR-1..5
  specifies how Coder LLM and tools communicate.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: NO (this is hard scope for
    v0.1, not a memory-compression fix)
  - (B) helps LLM find context when needed: YES (single ADR replaces
    Phase-M agents inventing inner-loop shape ad-hoc)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "Find one immediate-improvement
    implementable in next PR": YES (one design pass produces a
    self-contained, mergeable ADR-7; matches the goal exactly)
- **Cost:** medium (1–4h; one design pass, ~200–300 lines ADR + a
  reference implementation skeleton)
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE; v0.1 hard requirement per §10
  R-1 Horizon).
- **Alternative-if-rejected:** Phase-M PR "implement loop" either
  invents its own inner-loop shape (review burden) or stalls until
  this contract emerges; multi-PR drift in tool-call audit format
  becomes near-certain.
- **Concrete first step (if TAKE):** Copy
  `knowledge/adr/ADR-template.md` to
  `knowledge/adr/ADR-7-agent-inner-loop.md`; draft Tool-Protocol
  section using ampcode §4 as source; open PR.
```

Sample summary-table row:

```text
| R-1 | TAKE | NO / YES | YES (matches goal exactly) | medium | Phase-M agents invent inner-loop ad-hoc; tool-call audit drifts | No (TAKE) |
```
