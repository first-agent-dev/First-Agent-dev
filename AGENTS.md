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

## PR Checklist

Verify before opening a PR. Each item has triggered wasted review cycles.

1. **Code fences have language tags.** No bare ` ``` ` at opening! See rule above.
2. **Frontmatter uses `compiled:`, not `date:`.** Schema: [`knowledge/README.md`](./knowledge/README.md#conventions).
3. **File length within tier limits.**
   - Summaries / overviews: **<1000 lines**.
   - Deep-dive research: **<2000 lines**.
   - Readability > size
4. **`compiled:` date ≥ all dates cited in text.** No temporal impossibilities.
5. **(DELETED 2026-05-25 — supersession-not-overwrite no longer mandated as a PR Checklist rule.** Slot preserved to keep numbers 6..11 stable; orphan citations to «rule #5» cleaned up incrementally per user direction. Archival mechanics still apply on a per-artefact basis — see [`knowledge/MAINTENANCE.md`](./knowledge/MAINTENANCE.md) when archiving research notes or non-research files.)
6. **PR description lists changed/new files as clickable blob-URLs**
   (`https://github.com/<owner>/<repo>/blob/<branch>/<path>`), at
   least for non-trivial files. Plain bullet text is insufficient —
   reviewers should be able to open each file in one click without
   copy-pasting paths. Use the head branch of the PR, not `main`.
7. **`knowledge/llms.txt` reflects reality.** If this PR adds, removes, or renames a file under `docs/` or `knowledge/`, follow the matching checklist in [`knowledge/MAINTENANCE.md`](./knowledge/MAINTENANCE.md) (§When adding a new file / §When archiving a research note / §When superseding a non-research file). Pre-commit regenerator is planned post-Phase S ([`docs/workflow.md`](./docs/workflow.md) item 7).
8. **Research notes from the research-briefing workflow start with §0
   Decision Briefing.** Notes under `knowledge/research/` produced via
   [`knowledge/prompts/research-briefing.md`](./knowledge/prompts/research-briefing.md)
   MUST place a `## 0. Decision Briefing` section as the first
   section after the frontmatter (before TL;DR / Scope). Each
   recommendation in §0 follows the eight-field format (What /
   Project-axis fit (A, B) / Goal-lens fit (C) / Cost / Verdict / If
   UNCERTAIN-ASK / Alternative-if-rejected / Concrete first step).
   Axes (A) "reduces session-start noise" and (B) "helps LLM find
   context" are stable project-axis criteria evaluated identically
   for every note; axis (C) "advances chosen goal_lens" is the only
   per-session axis and references the goal_lens elicited in Stage 1.
   §0 closes with a 7-column summary table (R-N / Verdict /
   Project-fit / Goal-fit / Cost / Alternative-if-rejected / User
   decision needed?). Frontmatter MUST include a `goal_lens:` field
   capturing the one-sentence research goal elicited at session
   start. The agent also posts §0 verbatim in chat after handover.
   This rule applies to **new** notes with `compiled: ≥ 2026-05-04`;
   older notes are exempted and not retro-fitted.
9. **New ADR PRs append to the exploration log and update a
   DIGEST.md row.** Any PR that introduces or amends an accepted
   ADR MUST append a block (or amendment block) to
   [`knowledge/trace/exploration_log.md`](./knowledge/trace/exploration_log.md):
   the question, the chosen option (`Chosen:`), each rejected
   option with `Reason:` (why rejected at decision time) +
   `Lesson:` (what new evidence would re-open the branch), and
   `Coupling:` cross-question coupling when applicable. Schema
   reference: [`knowledge/README.md` §`trace/`](./knowledge/README.md#trace--exploration-log).
   Rationale: the log is the cheap-read overlay agents use to
   understand *why* alternatives were rejected without re-reading
   every ADR end-to-end (origin: research note
   [`ara-protocol-cross-reference-2026-05.md`](./knowledge/research/ara-protocol-cross-reference-2026-05.md)
   §9 R-1). Log converted from YAML DAG to telegraphic markdown
   2026-05-10 per Tsinghua NLAH finding (code → NL migration:
   +16.8 pp accuracy, 9× faster, 97% fewer LLM calls on
   `arXiv:2603.25723`). **In the same PR**, also update
   [`knowledge/adr/DIGEST.md`](./knowledge/adr/DIGEST.md) — add a
   one-paragraph row for a new ADR or extend the **Amendments**
   bullet of the matching ADR's row. DIGEST.md is the agent-reading
   cheat-sheet (one paragraph per ADR ≈ 80 lines for all seven);
   stale rows defeat the purpose. **In the same PR**, also cross-
   check [`HANDOFF.md`](./HANDOFF.md) §Current state ADR list — it
   is the human-readable mirror of the ADR slate (per `HANDOFF.md`
   §Why this file exists) and drifts silently if not enforced.
   If the PR adds an ADR, append a bullet under §Current state
   *Architecture decisions*; if it amends one, extend the existing
   bullet with an *Amendment YYYY-MM-DD* clause. Same drift risk
   that motivates the DIGEST rule above applies here.
10. **Harness-component PRs cite minimalism-first evidence.** PRs
    that introduce or amend a harness component (tool, prompt-layer,
    retrieval-stage, executor, sandbox-rule) MUST include in the
    description **explicit answers** to the 4-question minimalism-first
    test from
    [`knowledge/project-overview.md` §1.2](./knowledge/project-overview.md#12-enforceable-principle--minimalism-first):

    1. Research-evidence supporting the component's necessity under
       UC1+UC3 single-user scope (paper / primary-source post /
       eval-report citation).

       *Recognised anti-patterns the citation must clear* (forward-
       only from 2026-05-20):
       - **«Prompt-diversity layer» / re-asking with paraphrased
         prompts is NOT a valid harness component** — Nitarach P-3
         §4.4 finding ([correlated-LLM-errors note
         §4.4](./knowledge/research/correlated-llm-errors-and-ensembling-2026-05.md))
         shows prompt-diversity ensembles do not yield consistent
         gains; gains are sample-by-sample noise, not signal. A PR
         that proposes «retry with a re-worded prompt» MUST instead
         cite the underlying mechanism (different temperature, model
         family, retrieval scope) it would actually exploit. The
         layer-name «prompt diversity» on its own is rejected as
         under-specified.
       - **«Spawn-recursion» sub-agent — sub-agent that can spawn
         further sub-agents — is NOT allowed.** Cap
         `SUBAGENT_MAX_STEPS ≤ 100`, sub-agent tool set MUST exclude
         any `SpawnSubAgent` tool, sub-agent invocation MUST use
         `generateText` (not streaming). Captured in
         [ADR-7 §Amendment 2026-05-20](./knowledge/adr/ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule)
         rule 5 and
         [BACKLOG.md I-2](./knowledge/BACKLOG.md#i-2--agent--sub-agents-for-context-load-reduction)
         pending the BACKLOG I-2 implementation.
    2. Open-source agent-stack precedent that **already** removed or
       did not add a similar component, and the observed result.
    3. Concrete capability lost if the component is omitted, and
       whether it can be replaced by an existing tool or config
       setting.
    4. **Could this step be a deterministic Python function instead
       of an LLM call?** If the step is parsing, formatting,
       aggregation, fan-out over a list, file lookup, or any other
       operation that does not require model judgement, a function
       is the correct default; an LLM call is justified only when
       the step needs reasoning that cannot be expressed
       deterministically. Subtraction question per user idea 4 +
       ADR-7 prep input — the inner-loop is the natural seat of
       step-as-function vs step-as-LLM-call decisions; the rule
       captures the discipline now so ADR-7 inherits it.

    After UC5 landing, KPI-delta on a reproducible benchmark replaces
    the 4-question test for harness components measurably evaluated.
    Documentation-only or non-harness PRs (research notes, README
    updates, lint fixes) are exempted. This rule applies to **new**
    PRs from the merge of this PR forward; older PRs are not
    retro-fitted.
11. **Context budget for any single LLM call is ≤ 100 k tokens in
    ≥ 90 % of cases.** When designing or amending a harness component
    that issues an LLM call (prompt-layer, retrieval-stage, role
    invocation, sub-agent), the request shape MUST keep input context
    under ~100 k tokens for at least 9 out of 10 invocations in the
    component's expected workload. Justification: First-Agent's
    Pillar-1 target is the **lower-tier OSS LLM** (Planner / Coder /
    Eval tiers per [ADR-2](./knowledge/adr/ADR-2-llm-tiering.md)),
    whose effective context window degrades sharply past ~100 k input
    tokens — accuracy drops, latency jumps, cost grows super-linearly.
    Elite-tier Debug (Claude) is exempt, but routine calls do not run
    on Debug.
    **What «context» counts.** System prompt + role prompt + injected
    tool definitions + retrieved chunks + scrollback / conversation
    history + any in-line memory the harness paste in.
    **What this rule forces at design time.** If a component's natural
    shape pushes a single call past ~100 k for a non-edge-case
    workload, the design MUST adopt **at least one** mitigation
    before merge:
    a. **Sub-agent split** — delegate the big-context work to a
       sub-agent so the parent context stays bounded (Phase-M
       runner; rationale tracked in `BACKLOG.md` until ADR-7 lands).
    b. **Lazy-load** — load skills / tool-specs / repo chunks on
       demand instead of injecting upfront (dispatcher pattern;
       tracked in `BACKLOG.md` until ADR-7 + ADR-8 land).
    c. **Step-as-function** — replace the LLM call with a
       deterministic Python function where the step does not need an
       LLM (see rule #10 question 4).
    d. **Explicit elite-tier escalation** — route the call to elite
       tier *with* a written justification in the PR description
       (treat «route to elite» as a last resort, not a default).
    The PR description for such a component MUST state which
    mitigation it adopts and cite expected p90 input-token shape.
    Documentation-only PRs and non-harness PRs are exempt. Forward-
    only from the merge of this rule; older harness PRs not
    retro-fitted.

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

## PR Intent Classification

Forward-only from 2026-05-25 (PR opening this section). Supersedes
the former §Change Classification (REPAIR / RELAX / WORKAROUND as a
top-level taxonomy applied to every module-touching PR).
REPAIR / RELAX / WORKAROUND is retained as a **Level-2 sub-classifier**
scoped to `INTENT: FIX` only.

Every PR — including pure-doc PRs — MUST open the PR description AND
the first commit message body with two or three header lines,
mechanically derived from the staged-paths shape:

```text
INTENT: <RESEARCH | ADR-RULE | IMPLEMENT | FIX | CHORE>
[CLASS: <REPAIR | RELAX | WORKAROUND>]   ← only when INTENT: FIX
INVARIANT: <one sentence | n/a>
```

For `INTENT: FIX` PRs, the description ALSO carries the
**anti-shallow-fix gate** clauses from
[`project-overview.md` §1.2.5](./knowledge/project-overview.md#125--compliance-by-construction-failure-observable):

```text
DEGREE-OF-FREEDOM CLOSED: <one sentence | n/a (reason)>
DETERMINISTIC MECHANISM: <one sentence ending with `repo/file.ext:line` | n/a (reason)>
```

### Level 1 — INTENT (closed enum; classifier is path-shape-deterministic)

The classifier reads `git diff --cached --name-status` and emits one
of five labels. Every label has a mechanical match rule — no LLM
judgement on which bucket the PR is in.

| Label       | Path-shape that fires it                                                                                                                                  |
|-------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `RESEARCH`  | Sole adds under `knowledge/research/*.md`. No `src/`, no `tests/`, no rule files. Includes audit-style sweeps (read-only repo audits producing findings). |
| `ADR-RULE`  | ANY of the following in the diff: `knowledge/adr/ADR-*`, `AGENTS.md`, `knowledge/project-overview.md`, `knowledge/anti-patterns/AP-*`, `knowledge/MAINTENANCE.md`. |
| `IMPLEMENT` | `src/fa/**` and/or `tests/**` with status `A` (added) ONLY — first-time work realising an accepted ADR-RULE contract.                                     |
| `FIX`       | `src/fa/**` and/or `tests/**` with status `M` (modified) or mixed `A`+`M` — behaviour change interacting with a pre-existing invariant. Requires Level-2 CLASS. |
| `CHORE`     | Sole touches in `{pyproject.toml, .pre-commit-config.yaml, .github/**, knowledge/llms.txt}`. Non-semantic; no logic or rule changes.                       |

**Cross-category resolution.** When a single diff spans multiple
labels (which §No mixed PRs below forbids but a slipped PR may still
produce), the classifier picks the highest-impact label per:

```text
ADR-RULE  >  IMPLEMENT  >  FIX  >  RESEARCH  >  CHORE
```

The hook emits a WARNING «multi-intent diff detected; consider
splitting per §No mixed PRs» — see [§No mixed PRs](#no-mixed-prs)
below, which is the canonical home of the single-concern discipline.

**Mirror files** (`HANDOFF.md`, `knowledge/trace/exploration_log.md`,
`knowledge/adr/DIGEST.md`, `knowledge/llms.txt` when ride-along) do NOT
independently trigger any intent — they are updated in the same PR per
PR Checklist rule #9 (ADR PRs) or per maintenance rules, but the
intent is set by the upstream change they mirror. If the diff is
mirror-only with nothing upstream, the hook emits «mirror-only diff is
unusual; pick the dominant upstream intent or commit as `CHORE` if
pure cleanup».

### Level 2 — CLASS (only when INTENT: FIX)

| Label        | Meaning                                                                                                                                       |
|--------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| `REPAIR`     | Restore a broken invariant verbatim. No ADR amendment needed.                                                                                  |
| `RELAX`      | Weaken or change a strict invariant. MUST land an ADR amendment in the same PR per §PR Checklist rule #9.                                       |
| `WORKAROUND` | Temporary bypass of an invariant. MUST catalogue the pattern under [`knowledge/anti-patterns/`](./knowledge/anti-patterns/README.md) in the same PR and link the entry from the PR description; if the invariant is genuinely the wrong shape, escalate to `RELAX` instead. |

### INVARIANT line content (per intent)

| Intent       | Required INVARIANT content                                                                                                                |
|--------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| `RESEARCH`   | `n/a` — research artefacts do not bind project behaviour by themselves.                                                                  |
| `ADR-RULE`   | `Contract: <one sentence stating the introduced or modified clause>`                                                                     |
| `IMPLEMENT`  | `Implements: <ADR or rule reference, e.g. ADR-10 §2 or AGENTS.md §PR Intent Classification>`                                              |
| `FIX`        | `Affects: <pre-existing ADR or rule invariant being restored / changed / bypassed, e.g. ADR-7 §5 Input validation>`                       |
| `CHORE`      | `n/a` — non-semantic updates do not change any invariant.                                                                                |

### Anti-shallow-fix gate (FIX only)

For `INTENT: FIX` PRs, both `DEGREE-OF-FREEDOM CLOSED:` and
`DETERMINISTIC MECHANISM:` are MANDATORY in the PR description and
first commit body. The two clauses operationalise §1.2.5 «the LLM
never has a degree of freedom on a spec-bearing decision» as a
forward-acting forcing function on every FIX PR.

- `DETERMINISTIC MECHANISM:` MUST end with a `repo/file.ext:line`
  citation that resolves against the staged tree (or HEAD) — the
  hook reads the staged blob and verifies the file exists and the
  line number is within bounds.
- Both fields accept `n/a (reason)` when the FIX has no agent-facing
  degree of freedom — pure type-bugs, refactors, dependency bumps,
  test reshuffles that pin no new invariant. The agent MUST write an
  explicit reason; blank or `<fill me>` is rejected.

Inability to name either field, or naming a **tautological mechanism**
(string identity with `DEGREE-OF-FREEDOM CLOSED:` modulo whitespace
— e.g. citing the same call-site guard that the diff just added),
escalates the PR from `CLASS: REPAIR` to `CLASS: WORKAROUND` and
catalogues under
[`knowledge/anti-patterns/AP-003`](./knowledge/anti-patterns/AP-003-shallow-fix-no-mechanism.md).
The tautology check is visible to a reviewer in two seconds; the
file-line citation makes content-meaninglessness mechanically
detectable.

### Mechanisation

The classifier and validator land as `src/fa/hygiene/pr_intent.py`
(planned PR B; tracked in
[`HANDOFF.md`](./HANDOFF.md) §Current state). Two git hooks register
via `.pre-commit-config.yaml`:

- `prepare-commit-msg` — fires BEFORE the agent sees the commit-msg
  buffer; pre-populates the template with the mechanically-derived
  `INTENT:` line plus `<fill me>` placeholders for every required
  field per the intent's row above. The agent sees the placeholders
  before composing; cognitive load drops from «remember the rule» to
  «fill the placeholders».
- `commit-msg` — fires AFTER the agent composes the message, BEFORE
  the commit lands; validates field-presence per the intent's
  required-field table; returns ALL violations in one pass (no
  short-circuit on first failure); hard-fails the commit on any
  violation.

The hook is `INTENT`-suggestive but not `INTENT`-prescriptive — the
classifier output is a default the agent may override (e.g. a NEW
`src/fa/**` file is normally `IMPLEMENT`, but a contributor may
override to `FIX` if the new file is itself the fix shape for an
existing invariant). The override is logged so the reviewer sees the
shape mismatch.

### No mixed PRs

A PR that genuinely covers two intents MUST split. Cross-category
resolution above picks the dominant intent for a slipped PR; this
subsection is the canonical home of the single-concern discipline
(there is no separate numbered PR Checklist rule for it — the
rule lives here, attached to the classifier that detects violations).
The classifier's WARNING surfaces the violation; the reviewer
enforces the split.

### Rationale (≤ 3 sentences)

The previous §Change Classification rule fired at PR-description time
— post-code, post-diff, post-commit-message — which is the *last*
gating point and the weakest. Moving the gate to `prepare-commit-msg`
(pre-description, pre-commit) cuts action-count: the agent never has
the freedom to choose the wrong-shape header, because the right-shape
skeleton is already in the buffer when they start typing. Worked
history of the WORKAROUND-by-default pattern this rule is
forcing-against:
[`knowledge/anti-patterns/AP-001`](./knowledge/anti-patterns/AP-001-spec-bypassing-workaround.md);
forward-acting pattern catalogued in
[`knowledge/anti-patterns/AP-003`](./knowledge/anti-patterns/AP-003-shallow-fix-no-mechanism.md).

## PR Description Style

PR descriptions are the *first reading-pass* for both human review
and LLM agents loading repo context. They should be readable
end-to-end (no bullet-soup), and they should be cheap to parse for
the same agents that wrote them.

**Language split:**

- **Default to Russian** for analytical prose, rationale, scope
  discussion, retro-fit notes — this matches the convention already
  in force for research notes
  ([`knowledge/README.md` §Conventions](./knowledge/README.md#conventions))
  and keeps the human-review path natural.
- **Keep in English** any *identifier* whose precision matters for
  later grep / cross-reference: file paths, frontmatter keys
  (`compiled:`, `goal_lens:`), AGENTS.md rule references
  («PR Checklist rule #N»), full PR titles when referencing other
  PRs (e.g. «PR #16 *docs: add research-briefing workflow…*»), code
  blocks, schema examples, verdict tokens (`TAKE` / `SKIP` /
  `DEFER` / `UNCERTAIN-ASK`).

**Recommended structure:**

One-paragraph what+why opening — Russian prose, what ships +
motivating problem. No bullets here.
Files (clickable blob-URLs) per
PR Checklist rule #6.
Design-rationale prose for any non-obvious choice — flowing
paragraphs, not bullets, when explanation > 3 lines.
Scope / ordering / retro-fit — short list (≤5 items)
flagging merge-order, deferrals, forward-only clauses.
Review & Testing Checklist for Human — GitHub PR template
block; Russian for action items, English for technical referents.
Notes — Russian; mention follow-up PRs and any session-
continuity context. AI-Session trailer is appended automatically.

**Execution Rules:**

Develop complex lists into prose: If a sequence exceeds 5 items, requires 2-3 lines per item,
write cohesive Russian paragraphs.
Reserve bullet points strictly for short, scannable lists.
Synthesize the commit history: Write a fresh, high-level summary and explicitly reference the commit SHA.
Treat the PR body as an independent overview rather than a verbatim copy of the commit log.
Only reference identifiers (like PRs or issues) that already exist and resolve perfectly at read-time.
Inline review comments / replies follow the same language split:
Russian prose for the response; keep the cited identifier (file
path / line / suggestion code-block) in English.

**Canonical examples:**

- [PR #17 *docs: add knowledge/trace/exploration_tree.yaml backfilling ADR-1..6 (R-1)*](https://github.com/GrasshopperBoy/First-Agent-fork/pull/17)
  — DAG backfill PR; description retro-rewritten in this style as a
  demonstration before this convention merged.
- [PR #18 *docs(AGENTS): add §PR Description Style — Russian prose +
  English identifiers*](https://github.com/GrasshopperBoy/First-Agent-fork/pull/18)
  — this PR; self-demonstrating description.

## Development Workflow

- Branch: `devin/<timestamp>-<slug>` from `main`.
- All changes via Pull Request.
- Commit messages: descriptive, English, present tense (`docs: add architecture note`).
- Never push directly to `main`.
- **`AI-Session:` git trailer.** When a commit is driven by a Devin
  (or other LLM-agent) session, add an `AI-Session: <session-id>`
  trailer to the commit message. This preserves the link from a
  squash-merged commit back to the originating session for audit and
  re-entry. Pattern lifted from `codedna` (see
  [`research/agentic-memory-supplement.md` §3](./knowledge/research/agentic-memory-supplement.md)).
  Example:

  ```text
  docs: add ADR-N on <topic>

  Body...

  AI-Session: 2f45f66ef9ff45eab03161ecef165c0e
  Co-Authored-By: <human> <email>
  ```

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
