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
- [`knowledge/instructions/`](./knowledge/instructions/README.md) — deploy + operate the AIO (install / operations).
- [`knowledge/pr-notes/`](./knowledge/pr-notes/README.md) — archived PR notes/bodies (point-in-time artifacts).

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

If the third answer is "none found", keep the existing code as-is —
the burden of proof is on adding, per
[`knowledge/project-overview.md` §1.2](./knowledge/project-overview.md#12-enforceable-principle--minimalism-first)

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
  wins. Complete the bootstrap first, then navigate as needed.
  
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
- **Workspace resolution.** Locate the repo root by checking for
  `./AGENTS.md` in the current directory. If present →
  FA root is `.`; otherwise abort with «`fa: not a First-Agent
  workspace`». Always anchor on the current directory.

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

## Industry-proven rules (from prior art in OSS agent stacks)

Following rules are standard practice across multiple open-source
agent projects. Violations of any of these caused reverts in production.

1. **Keep the system human-curated.** Self-improving subsystems
   are a known anti-pattern — write them only when the host
   system is mature enough to validate their output.

2. **Estimate tasks by scale (files touched).** Measure scope
   by files touched or eval-pass count. Use scope-only metrics.

3. **Every write target must have an active consumer.** Every new
   file, table, metric, or event-channel lands with a named
   automated or human consumer in the same PR.

4. **Every new ADR requires a §Prior Art section.** Document
   existing tools, papers, or projects that solve the same problem.

5. **Build the runtime model before fixing infrastructure errors.**
   When failure occurs: state what implicit behaviors the tool has in that environment. Then read the tool's documentation. Focus on fixing the abstraction.
   Use [Anti-patterns](./knowledge/anti-patterns/) for debugging.

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
- **Lint is autofix-first.** Run `just fix` after editing code — it
  handles formatting (import order, `__all__` sorting, quoting, line
  wrapping). Let the tool do style; focus on logic. Gate before push:
  `just check`.
- **Judgment rules** (`S`, `BLE001`, `C901`, pylint `duplicate-code`):
  these signal a design problem — fix the design that caused the
  finding. Waive with `# noqa: <code> — <reason>` only when you can
  explain why the flagged pattern is intentional (e.g. a fail-closed
  boundary, a sandboxed `shell=True`).
- **Type-checker errors** (mypy strict, pyrefly): fix by writing
  code that validates data at the boundary — the type checker error
  disappears because the logic is genuinely correct, not silenced.
  Pattern from `src/fa/inner_loop/tools/base.py`:

  ```python
  def require_string(params: Mapping[str, object], key: str) -> str:
      value = params.get(key)
      if not isinstance(value, str):
          raise ValueError(f"{key} must be a string")
      return value  # type checker knows this is str
  ```

  The `isinstance` check serves two purposes: it validates untrusted
  input at runtime AND narrows the type for the checker. Both the
  code and the types are correct — no annotation shortcuts needed.
- **Existing tests are protected.** Deleting/renaming any `tests/**`
  file is blocked at the hook and harness seats; modifying one during a
  FIX-shaped diff requires a `TEST-EDITS:` declaration in the PR draft
  (see [`pr-creation` skill §Test-edit declaration](./knowledge/skills/pr-creation/SKILL.md#test-edit-declaration)).
  Fix the code to pass the test, keep the test as spec.
- Commit messages: descriptive, English, present tense (`docs: add architecture note`).
- Push to your branch; merge to `main` only via Pull Request.
- **`AI-Session:` git trailer** rule (per-commit; example included) lives in the [`pr-creation` skill §AI-Session trailer](./knowledge/skills/pr-creation/SKILL.md#ai-session-trailer)

## Query Routing

Route questions to the right folder. Load only what the task needs.

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
