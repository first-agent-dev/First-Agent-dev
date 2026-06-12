# AGENTS.md

## Project Overview

**First-Agent** — research-backed implementation-first LLM agent project,
aimed at becoming the most token/tool-call efficient open-source
coding-agent harness. 
**Currently in Stage 1** (documentation + agent development with Devin); three-stage
project evolution is defined in
[`knowledge/project-overview.md` §1.3](./knowledge/project-overview.md#13-three-stage-project-evolution).

Goal-formulation in 4 pillars + minimalism-first principle:
[`knowledge/project-overview.md` §1.1](./knowledge/project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars).

## Repository Structure

- [`README.md`](./README.md) — project overview.
- [`AGENTS.md`](./AGENTS.md) — this file.
- [`knowledge/`](./knowledge/README.md) — durable memory (project-overview, ADR, prompts, research).

## Pre-flight checklist

Run BEFORE making any edits, opening a branch, or writing analysis on
non-trivial tasks. Five steps. Output is cheap; skipping is the failure
mode.

Steps 1–3 are literal shell commands; Steps 4–5 are declarations posted
in your analysis openly. Pattern-match the templates exactly.

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
grep -i "^| \*\*<term>\*\*" knowledge/glossary.md
```

Expect exactly one matching row. If the row is missing, fall back to
[`knowledge/project-overview.md` §1.1–§1.2](./knowledge/project-overview.md);
add the term to the glossary in the same PR if it is in active use.
The glossary is the single source of truth.

**Step 3 — Symmetric reading.** Before citing a research note as
evidence, run:

```bash
grep -ril "<key-term>" knowledge/research/
```

Expect 1..N file paths. Open every file in the output!
Cite from the most recent (`compiled:` date in frontmatter)
unless explicitly superseded. 
Reading every match is cheaper than missing one.

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
on adding rather than on removing.

**Step 5 — Goal-lens declaration.** State in your analysis openly, every session:

```text
- goal_lens: <one-sentence research goal; pick from
  knowledge/prompts/research-briefing.md Stage 1,
  or write free-text>
- project-axes advanced: <pick ≥1 of A noise-reduction |
  B context-finding | C goal_lens-advancement>
- subtraction evaluated: <YES — answers in Step 4 | EXEMPT
  (documentation-only PR with no new artefact) — restate why>
- session-type: <new-feature | bug-fix | refactor | doc-edit |
  glossary-edit | dep-bump | research-briefing | other-explain>
```

Four named slots. Pattern-match the template exactly; respect four-pillar goal stated in
[`knowledge/project-overview.md` §1.1](./knowledge/project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars).
`goal_lens` is universal across sessions.

## Working in This Repo

- **Session bootstrap.** Read [`HANDOFF.md`](./HANDOFF.md) § 60-second
  bootstrap — it points to `knowledge/llms.txt` §MUST READ FIRST
  (five files, in order). If HANDOFF and llms.txt disagree, llms.txt
  wins. Do not crawl the repo before completing the bootstrap.
  
- All documentation is Markdown. ATX headings (`#`, `##`), short lines ~150 chars.
- Fenced code blocks
  - ALWAYS open with a language tag:
    - Code: `python`, `yaml`, `json`, `bash`.
    - Non-code (ASCII art, directory trees, prompts, logs): `text`.
  -Close with bare ` ``` `.
- New docs go in the right folder:
  - Guides / references → `knowledge/` (the former `docs/` folder was retired 2026-05-29). Update [`knowledge/llms.txt`](./knowledge/llms.txt) §BY-DEMAND INDEX.
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
  documented in `internal/workspace/workspace.go`. The
  marker rule is the single fence; the marker file is what FA
  already uses for LLM routing, so no new artefact is introduced.

## Context-budget discipline

When loading context for a task, collect what is **necessary** to complete it — not breadth-first.
Navigate the repo, identify relevant files, read only the parts that move the task forward.
Use [`knowledge/llms.txt`](./knowledge/llms.txt) as the routing surface and [`HANDOFF.md`](./HANDOFF.md) as the bootstrap surface.
Use §-anchors and grep-windows! Goal - keep the agent's working prompt focused on the task
and to leave headroom for the actual edits, traces, and tool-output.

**Design invariant** 
Any single LLM call's total input — system prompt + role prompt + tool definitions + retrieved chunks + scrollback + in-line memory
— must stay below ~100 k tokens for ≥ 9 out of 10 invocations in the expected workload.
When designing or amending a harness component, adopt **at least one** mitigation before merge:

a. **Sub-agent split** — delegate the big-context work to a sub-agent so the parent context stays bounded.
   
b. **Lazy-load** — load skills / tool-specs / repo chunks on demand instead of injecting upfront (dispatcher pattern).
   
c. **Step-as-function** — replace the LLM call with a deterministic Python function where the step does not need model judgement.
   
d. **Explicit elite-tier escalation** — route the call to Debug tier. Last resort.

The universal context-budget discipline above applies to **every
session**, not only to PR creation.

## Cross-project anti-patterns - learnt from precedents

These four citations from neighbouring open-source agent stacks (DPC, Aperant, Gortex, soviet-code)
serve as empirical anchors for our minimalism-first principle. 

1. **Do not build self-improving subsystems early.** 
   *Rule:* Do not write subsystems whose value depends on a mature host system. Keep the system human-curated.

2. **Estimate tasks by scale (files touched).**
   *Rule:* Measure tasks by files touched or eval-pass count. Agents must use scope-only metrics.

3. **Every write target must have an active consumer.**
   *Rule:* Every new write target (file, table, metric, event-channel) MUST land with a named automated or human consumer. 

4. **Every new ADR requires a §Prior Art section.**
   *Rule:* Every new ADR must document existing tools, papers, or projects to prove we are not reinventing the wheel. This prevents NIH (Not-Invented-Here) drift.

## Loadable skills

Per-task agent-loadable disciplines live in
[`knowledge/skills/`](./knowledge/skills/) — directory-per-skill,
shapes - `.agents/skills/<name>/SKILL.md` 
Skills are loaded on the trigger condition:

| Skill | Trigger and scope |
| :--- | :--- |
| [`pr-creation`](./knowledge/skills/pr-creation/SKILL.md) | **Trigger:** Before opening any PR (including pure-doc PRs).<br><br>Canonical PR-creation rulebook. Carries the 5-intent classifier (`RESEARCH / ADR-RULE / IMPLEMENT / FIX / CHORE`). The PR description AND the first commit message body MUST open with the header lines specified by the skill's §Output format. The planned `prepare-commit-msg` / `commit-msg` reads the skill's §Reference tables as the single source of truth. Applies to every PR. |
| [`repo-audit`](./knowledge/skills/repo-audit/SKILL.md)   | **Trigger:** When asked to perform a critical structure / doc / skill review.<br><br>Carries the 7-phase audit workflow (orientation → inventory → cross-reference → invariants → contradiction sweep → demotion ledger → final report). |

New skills land as `knowledge/skills/<name>/SKILL.md` with a row added to this table.

## Development Workflow

- Branch: `devin/<timestamp>-<slug>` from `main`.
- All changes via Pull Request.
- **Lint is autofix-first.** After editing code run `just fix`
  (ruff autofix + format) — it mechanically resolves all style findings
  (import order, `__all__` sorting, quoting, line wrapping). Never hand-fix
  or memorise style rules; they are not part of your job. Gate before push:
  `just check`.
- **Judgment rules (not autofixable).** `S` (security), `BLE001`
  (blind except), `C901` (complexity > 15), and pylint `duplicate-code`
  findings mean: fix the design, not the lint line. A waiver
  (`# noqa: <code> — <one-line reason>`) is allowed ONLY when the
  flagged pattern is the intended design (e.g. a fail-closed boundary,
  a sandboxed `shell=True`); never waive to silence a finding you do
  not understand.
- Commit messages: descriptive, English, present tense (`docs: add architecture note`).
- Never push directly to `main`.
- **`AI-Session:` git trailer** rule (per-commit; example included) lives in the [`pr-creation` skill §AI-Session trailer](./knowledge/skills/pr-creation/SKILL.md#ai-session-trailer)

## Query Routing

Route questions to the right folder. Do not load everything into context.

| Question type | Look first | Verify with |
|---|---|---|
| Architecture, patterns, Decisions and rationale | [`knowledge/adr/`](./knowledge/adr/) | ADR |
| Current task | [`HANDOFF.md`](./HANDOFF.md) | Session start |
| Research findings | [`knowledge/research/`](./knowledge/research/) | Primary sources from `source:` frontmatter |
| Specific decision / quote / number / date | **Primary source** (URL / code / gist), not a summary note | — |
| Terms | [`knowledge/glossary.md`](./knowledge/glossary.md) | — |

**Chain-of-custody rule.** If citing a specific decision / quote / number / date,
go to the primary source and quote from there.
Summaries in `knowledge/research/` are pointers, not authoritative sources.

- **Session close.** Update [`HANDOFF.md`](./HANDOFF.md) per its
  §Session Protocol (overwrite §Current state, rewrite §Next); update [`knowledge/llms.txt`](./knowledge/llms.txt) rows per
  [`MAINTENANCE.md`](./knowledge/MAINTENANCE.md) §When adding a
  new file (bucket, line count, ≤200 prose chars).
