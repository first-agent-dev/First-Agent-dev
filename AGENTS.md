# AGENTS.md

Instructions for AI agents (Devin and similar) working in this repo.

## Project Overview

**First-Agent** — research-backed implementation-first LLM agent project,
aimed at becoming the most token/tool-call efficient open-source
coding-agent harness under UC1+UC3 single-user scope. **Currently in
Stage 1** (documentation + agent development через Devin); three-stage
project evolution is defined in
[`knowledge/project-overview.md` §1.3](./knowledge/project-overview.md#13-three-stage-project-evolution).
Inner-stage milestone: Phase S scaffolding complete;
[ADR-7](./knowledge/adr/ADR-7-inner-loop-tool-registry.md) closes
the inner-loop / tool-registry contract before the first
feature-module PR (Phase M); `src/fa/chunker/` exists, not yet
end-to-end tested.
Goal-formulation in 4 pillars + minimalism-first principle:
[`knowledge/project-overview.md` §1.1](./knowledge/project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars).
README intro: [`README.md`](./README.md).

## Repository Structure

- [`README.md`](./README.md) — project overview.
- [`AGENTS.md`](./AGENTS.md) — this file.
- [`docs/`](./docs/README.md) — wiki (architecture, workflow,
  prompting, glossary). `devin-reference.md` and `agent-creation-github.md`
  are archived (in-place, 2026-05-08) — excluded from `knowledge/llms.txt`
  routing surface.
- [`knowledge/`](./knowledge/README.md) — durable memory (project-overview, ADR, prompts, research).

## Pre-flight checklist

Run BEFORE making any edits, opening a branch, or writing analysis on
non-trivial tasks. Five steps. Output is cheap; skipping is the failure
mode.

Steps 1–3 are literal shell commands; Steps 4–5 are declarations posted
in your analysis (not silently). Pattern-match the templates exactly —
weaker OSS LLMs (DeepSeek 4 / Kimi 2.6) drift when they paraphrase.

**Step 1 — Recency surface.** Run:

```bash
git log -n 5 --since="7 days" --oneline -- knowledge/ docs/ AGENTS.md
```

Expect ≤5 commit lines. For any commit touching a 2026-MM-DD research
note in `knowledge/research/`, open the note and skim only its §0
Decision Briefing. Rationale: supersessions and ADR amendments land on
`main` between sessions and silently invalidate older notes; this command
surfaces them in one read.

**Step 2 — Term expansion.** For every project-specific noun in the
prompt (axis, lens, pillar, harness, hook, ACI, UC1..UC5, NLAH, MCP,
subtraction-first, minimalism-first, R-S-M, …), run:

```bash
grep -i "^| \*\*<term>\*\*" docs/glossary.md
```

Expect exactly one matching row. If the row is missing, fall back to
[`knowledge/project-overview.md` §1.1–§1.2](./knowledge/project-overview.md);
add the term to the glossary in the same PR if it is in active use.
Rationale: weaker LLMs guess at jargon and produce confidently-wrong
analysis; the glossary is the single source of truth.

**Step 3 — Symmetric reading.** Before citing a research note as
evidence, run:

```bash
grep -ril "<key-term>" knowledge/research/
```

Expect 1..N file paths. Open every file in the output, not just the
first; cite from the most recent (`compiled:` date in frontmatter)
unless explicitly superseded. Rationale: the corpus is small enough
that reading every match is cheaper than missing one — and the OSS
agents' tendency to cite the first hit produces stale conclusions.

**Step 4 — Subtraction-check.** Before adding any artefact (file,
section, rule, frontmatter field, dependency), answer the three
questions verbatim in your analysis:

```text
- Removing what makes this redundant? <name an existing artefact
  that already covers ≥80% of this scope, or "none">
- What capability is lost if this artefact is omitted? <one
  sentence; concrete, not "reduced clarity">
- Open-source agent-stack precedent for not having it? <one URL
  or repo path; or "none found in 5-min search">
```

If the third answer is "none found", default to NOT adding. Rationale:
[`knowledge/project-overview.md` §1.2](./knowledge/project-overview.md#12-enforceable-principle--minimalism-first)
makes minimalism-first enforceable; the three questions force the proof
on adding rather than on removing. EXEMPT for documentation-only PRs
that introduce no new artefact (translations, typo fixes, link
updates) — restate the exemption explicitly in Step 5.

**Step 5 — Goal-lens declaration.** State in your analysis (not
silently), every session:

```text
- goal_lens: <one-sentence research goal; pick from
  knowledge/prompts/research-briefing.md Stage 1 (a)/(b)/(c)/(d)
  or write free-text>
- project-axes advanced: <pick ≥1 of A noise-reduction |
  B context-finding | C goal_lens-advancement>
- subtraction evaluated: <YES — answers in Step 4 | EXEMPT
  (documentation-only PR with no new artefact) — restate why>
- session-type: <new-feature | bug-fix | refactor | doc-edit |
  glossary-edit | dep-bump | research-briefing | other-explain>
```

Four named slots. Pattern-match the template exactly; do not omit
slots, do not paraphrase keys. Rationale: the four slots compel
explicit routing decisions before code lands; without them, mid-tier
LLMs default to "add" and the project drifts away from the four-pillar
goal in [`knowledge/project-overview.md` §1.1](./knowledge/project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars).
`goal_lens` is universal across sessions, not just research-briefing
ones; the elicitation in
[`knowledge/prompts/research-briefing.md`](./knowledge/prompts/research-briefing.md)
Stage 1 satisfies this step automatically.

## Working in This Repo

- **Session bootstrap.** Read [`HANDOFF.md`](./HANDOFF.md) §60-second
  bootstrap first — it is a quick-start sequence for agents that
  land on this repo without Devin MCP context. (This file is the
  rule book it references at step 1; `knowledge/llms.txt` is the
  canonical routing surface it references at step 2 — if HANDOFF
  and llms.txt disagree, llms.txt wins.) `HANDOFF.md` mirrors the
  Devin Knowledge note «First-Agent — current state pointer»;
  both are kept identical. Do not crawl the repo before completing
  the bootstrap.
- All documentation is Markdown. ATX headings (`#`, `##`), short lines ~150 chars.
- Fenced code blocks
  - ALWAYS open with a language tag:
    - Code: `python`, `yaml`, `json`, `bash`.
    - Non-code (ASCII art, directory trees, prompts, logs): `text`.
  -Close with bare ` ``` `.
- New docs go in the right folder:
  - Guides / references → `docs/`. Update [`docs/README.md`](./docs/README.md).
  - Project artifacts (decisions, research, prompts) → `knowledge/`.
- Research notes are read by both humans and agents. Prefer Russian for
  analytical prose, project recommendations. Keep protocol names, API field names, code,
  and direct quotes in their source language.
- readability > size
- Architectural decisions → ADR from [`knowledge/adr/ADR-template.md`](./knowledge/adr/ADR-template.md).
- **Workspace resolution (no walk-up).** Tools / scripts that need
  to locate the FA repository root MUST anchor on an explicit marker
  at the current working directory — never walk **up** the
  filesystem looking for a parent that happens to contain
  `AGENTS.md` or `knowledge/`. The marker is
  [`knowledge/llms.txt`](./knowledge/llms.txt) (already canonical
  per the §Session bootstrap rule above). Resolution algorithm:
  if `./knowledge/llms.txt` exists → FA root is `.`; otherwise
  abort with «`fa: not a First-Agent workspace (no
  knowledge/llms.txt at cwd)`». No walk-up is permitted even
  for «convenience» discovery. Rationale: walk-up resolution
  silently bridges nested checkouts, monorepo submodules, or a
  cloned repo inside `~/repos/First-Agent-debloat/external/` and
  drags wrong-project AGENTS.md / ADR slate into the agent's
  context — the exact «cross-workspace contamination» bug Gortex
  documented in `internal/workspace/workspace.go` (331 LOC). The
  marker rule is the single fence; the marker file is what FA
  already uses for LLM routing, so no new artefact is introduced.

## Context-budget discipline

When loading context for a task, collect what is **necessary** to
complete it — not breadth-first. Navigate the repo, identify
relevant files, read only the parts that move the task forward.
Use [`knowledge/llms.txt`](./knowledge/llms.txt) as the routing
surface and [`HANDOFF.md`](./HANDOFF.md) as the bootstrap surface;
prefer §-anchors and grep-windows over whole-file injection. The
goal is to keep the agent's working prompt focused on the task
and to leave headroom for the actual edits, traces, and
tool-output the session will accumulate.

**Design invariant** (Pillar-1, [ADR-10 §1](./knowledge/adr/ADR-10-deterministic-harness-invariants.md)).
Any single LLM call's total input — system prompt + role prompt +
tool definitions + retrieved chunks + scrollback + in-line memory
— must stay below ~100 k tokens for ≥ 9 out of 10 invocations in
the expected workload. Lower-tier OSS LLMs (Planner / Coder /
Eval tiers per [ADR-2](./knowledge/adr/ADR-2-llm-tiering.md))
degrade sharply past ~100 k. When designing or amending a harness
component whose natural shape pushes past this for a
non-edge-case workload, adopt **at least one** mitigation before
merge:

a. **Sub-agent split** — delegate the big-context work to a
   sub-agent so the parent context stays bounded.
b. **Lazy-load** — load skills / tool-specs / repo chunks on
   demand instead of injecting upfront (dispatcher pattern).
c. **Step-as-function** — replace the LLM call with a
   deterministic Python function where the step does not need
   model judgement.
d. **Explicit elite-tier escalation** — route the call to Debug
   tier (Claude) with written justification in the PR description
   (last resort, not a default).

The universal context-budget discipline above applies to **every
session**, not only to PR creation. The PR-time declaration that
a given harness PR adopted one of a..d lives in the
[`pr-creation` skill](./knowledge/skills/pr-creation/SKILL.md)
§PR Checklist (item that absorbed the former PR-time portion of
this rule). Documentation-only PRs and non-harness PRs are exempt
from the PR-time declaration.

## Cross-project anti-patterns

Forward-only from 2026-05-20. Four citations from neighbouring
open-source agent stacks (DPC, Aperant, Gortex, soviet-code) that
already paid the lesson — included here so FA does not re-derive
each one through a wasted PR cycle. The citations are *empirical
anchors* for the minimalism-first / subtraction-first principle
([`knowledge/project-overview.md` §1.2](./knowledge/project-overview.md#12-enforceable-principle--minimalism-first));
they do not replace the §Pre-flight Step 4 subtraction-check, they
strengthen it.

1. **No «evolution worker» / no self-improving subsystem (DPC
   ADR-015).** DPC built a background «evolution worker» that ran
   for 20+ sessions trying to mine its own traces for self-
   improvement proposals — `0 / 40` accepted proposals; the system
   was removed at the cost of `~400 LOC + 7 tools`. Lesson: a
   subsystem whose value depends on the host system being mature
   should NOT be built before the host system is mature; FA must
   not «let the agent improve itself» until the human-curated
   knowledge layer (Stage 2-3 per
   [`knowledge/project-overview.md` §1.3](./knowledge/project-overview.md#13-three-stage-project-evolution))
   is stable. Source: DPC ADR-015, cited in
   [`research/dpc-messenger-inspiration-2026-05.md`](./knowledge/research/dpc-messenger-inspiration-2026-05.md)
   §0 R-4.
2. **Estimate lines/files, not time (DPC ADR-005 P18).** DPC
   Session 14: Claude Code estimated `5-7h` for what took
   `11 min` — a `27-38×` over-estimate. Programmatic time
   estimation by LLMs is systematically wrong because LLMs do not
   have a clock-on-task signal. The discipline is to estimate
   what *can* be measured: LOC delta, files touched, ADR-amendments
   count, eval-pass count. Time estimate is permitted as «calendar-
   weeks for the human side», never as «task-hours predicted by
   the agent». Source: DPC ADR-005 P18 («scope-only estimation»),
   cited in
   [`research/dpc-messenger-inspiration-2026-05.md`](./knowledge/research/dpc-messenger-inspiration-2026-05.md)
   §0 R-5.
3. **Write-only subsystems are dead weight (DPC ADR-021
   Lesson 4).** DPC found multiple write-only ML subsystems —
   they emitted events, metrics, embeddings, but no production
   path consumed the output. Maintenance budget was non-zero;
   value was zero. Rule: every new write target (file, table,
   metric, event-channel) MUST have a named consumer (human or
   automated) at the same time it lands, or the write target
   does not land. This generalises §PR Checklist rule #7
   («llms.txt reflects reality») to all write artefacts.
   Source: DPC ADR-021 Lesson 4, cited in
   [`research/dpc-messenger-inspiration-2026-05.md`](./knowledge/research/dpc-messenger-inspiration-2026-05.md)
   §0 R-6.
4. **Prior-Art mapping in every new ADR (DPC AP8 →
   soviet-code B-NEW-8).** Every new FA ADR MUST include a
   §Prior Art section that maps each design choice to an
   existing tool, paper, or project. The §Prior Art section
   answers: «What did we look at? Which projects already
   solved this? Why are we not reusing them verbatim?». Without
   this section the ADR drifts toward not-invented-here re-
   implementation, and the §Pre-flight Step 4 subtraction-check
   loses the «OSS precedent» evidence it depends on. The
   existing ADR-template inherits this rule from 2026-05-20
   forward — older ADRs (1..7) are not retro-fitted but
   amendments to them MAY include Prior-Art if relevant.
   Source: DPC «We are NOT reinventing the wheel» rule (AP8 →
   soviet-code B-NEW-8), cited in
   [`research/dpc-messenger-inspiration-2026-05.md`](./knowledge/research/dpc-messenger-inspiration-2026-05.md)
   §6 AP8.

## Loadable skills

Per-task agent-loadable disciplines live in
[`knowledge/skills/`](./knowledge/skills/) — directory-per-skill,
filename always `SKILL.md` uppercase, matching the KAOS /
Anthropic Skills / Devin `.agents/skills/<name>/SKILL.md` shape
so a future runtime store (planned per
[`borrow-roadmap-2026-05.md` §R-24](./knowledge/research/borrow-roadmap-2026-05.md#r-24--filesystem-canonical-skill-store--safe-community-import))
plugs in without renaming. Skills are loaded on the trigger
condition; AGENTS.md retains only the trigger-to-skill mapping
below so the rules stay loadable on-demand per the
§Context-budget discipline above.

| Skill | Trigger and scope |
|---|---|
| [`pr-creation`](./knowledge/skills/pr-creation/SKILL.md) | **Before opening any PR (including pure-doc PRs).** Canonical PR-creation rulebook. Carries the 5-intent classifier (`RESEARCH / ADR-RULE / IMPLEMENT / FIX / CHORE`) + Level-2 `CLASS` sub-classifier (`REPAIR / RELAX / WORKAROUND`, FIX only) + anti-shallow-fix gate (`DEGREE-OF-FREEDOM CLOSED:` + `DETERMINISTIC MECHANISM:` with `repo/file.ext:line` citation or `n/a (reason)`) + PR Checklist rules 1-10 (code-fence lang tags, frontmatter `compiled:`, file-length tiers, date sanity, blob-URLs, `llms.txt` sync, research-briefing §0, ADR PR triple, harness-component minimalism-first evidence) + PR Description Style (Russian prose / English identifiers, recommended structure, execution rules) + AI-Session trailer rule. The PR description AND the first commit message body MUST open with the header lines specified by the skill's §Output format. The planned `prepare-commit-msg` / `commit-msg` hook (PR B, `src/fa/hygiene/pr_intent.py`) reads the skill's §Reference tables as single source of truth. Applies to every PR; forward-only from 2026-05-26 (PR A' externalisation, expanded same day to absorb the full PR Checklist + PR Description Style + AI-Session trailer rule). |
| [`repo-audit`](./knowledge/skills/repo-audit/SKILL.md) | **When asked to perform a critical structure / doc / skill review.** Carries the 7-phase audit workflow (orientation → inventory → cross-reference → invariants → contradiction sweep → demotion ledger → final report). Closes BACKLOG I-9 path (b). |

New skills land as `knowledge/skills/<name>/SKILL.md` with a row
added to this table.

## Development Workflow

- Branch: `devin/<timestamp>-<slug>` from `main`.
- All changes via Pull Request.
- Commit messages: descriptive, English, present tense (`docs: add architecture note`).
- Never push directly to `main`.
- **`AI-Session:` git trailer** rule (per-commit; example included)
  lives in the
  [`pr-creation` skill §AI-Session trailer](./knowledge/skills/pr-creation/SKILL.md#ai-session-trailer)
  since every commit in this project lands inside a PR-bearing
  branch and the trailer is read by the post-merge audit path.

## Query Routing

Route questions to the right folder. Do not load everything into context.

| Question type | Look first | Verify with |
|---|---|---|
| Architecture, patterns | [`docs/architecture.md`](./docs/architecture.md) | ADR |
| Decisions and rationale | [`knowledge/adr/`](./knowledge/adr/) | — |
| Workflow | [`docs/workflow.md`](./docs/workflow.md) | — |
| Research findings | [`knowledge/research/`](./knowledge/research/) | Primary sources from `source:` frontmatter |
| Specific number / date / quote | **Primary source** (URL / code / gist), not a summary note | — |
| Terms | [`docs/glossary.md`](./docs/glossary.md) | — |

**Chain-of-custody rule.** If citing a specific number, date, name,
or decision — go to the primary source and quote from there.
Summaries in `knowledge/research/` are pointers, not authoritative
sources.
Rationale: [`knowledge/research/llm-wiki-critique.md`](./knowledge/research/llm-wiki-critique.md).

**Supersession, not overwrite.** Never silently overwrite an outdated
note. Mark it `> **Status:** superseded by <link>` and keep for audit.
