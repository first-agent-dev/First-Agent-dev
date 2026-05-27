---
name: pr-creation
description: |
  Canonical PR-creation rulebook. Load before opening any PR (including
  pure-doc PRs) to derive the header lines the agent must emit on the
  PR description and the first commit message body, AND to verify the
  full PR Checklist + PR Description Style + AI-Session trailer
  discipline. Replaces the former §PR Intent Classification (2026-05-26,
  PR A'), then absorbs §PR Checklist rules 1-10 + §PR Description Style
  + AI-Session trailer rule (2026-05-26, PR A' expansion).
status: active
last-reviewed: 2026-05-26
triggers:
  - "about to open a PR"
  - "writing a commit message for a PR-bearing commit"
  - "filling in INTENT / CLASS / INVARIANT header lines"
  - "verifying PR Checklist items 1-10 before opening"
  - "composing PR description body or review reply"
  - "adding AI-Session trailer to a Devin-driven commit"
relocated_from: |
  AGENTS.md §PR Intent Classification (2026-05-26 — PR A'); AGENTS.md
  §PR Checklist rules 1-10 + §PR Description Style + AI-Session
  trailer paragraph from §Development Workflow (2026-05-26 — PR A'
  expansion).
---

# Skill — PR creation

Forward-only from **2026-05-25**. Replaces the former §Change
Classification rule (REPAIR / RELAX / WORKAROUND as a top-level
taxonomy applied to every module-touching PR). REPAIR / RELAX /
WORKAROUND is retained as a **Level-2 sub-classifier** scoped to
`INTENT: FIX` only.

## Trigger

You are about to open a PR — branch is on a non-main ref, staged
diff is non-empty, and you are composing the PR description or
the first commit message body. The skill applies to **every** PR
including pure-doc PRs.

## Reference

> The two-level classifier and the per-intent INVARIANT-content
> table below are **closed-enum lookups**. They are read by the
> agent (today) and by the `prepare-commit-msg` / `commit-msg`
> hook in `src/fa/hygiene/pr_intent.py` (planned, PR B). The
> hook treats these tables as the single source of truth; the
> agent reads them for visibility into what will be validated.

### Level 1 — INTENT (closed enum; classifier is path-shape-deterministic)

The classifier reads `git diff --cached --name-status` and emits
one of five labels. Every label has a mechanical match rule — no
LLM judgement on which bucket the PR is in.

| Label       | Path-shape that fires it                                                                                                                                  |
|-------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `RESEARCH`  | Sole adds under `knowledge/research/*.md`. No `src/`, no `tests/`, no rule files. Includes audit-style sweeps (read-only repo audits producing findings). |
| `ADR-RULE`  | ANY of the following in the diff: `knowledge/adr/ADR-*`, `AGENTS.md`, `knowledge/project-overview.md`, `knowledge/anti-patterns/AP-*`, `knowledge/MAINTENANCE.md`, `knowledge/skills/**`. |
| `IMPLEMENT` | `src/fa/**` and/or `tests/**` with status `A` (added) ONLY — first-time work realising an accepted ADR-RULE contract.                                     |
| `FIX`       | `src/fa/**` and/or `tests/**` with status `M` (modified) or mixed `A`+`M` — behaviour change interacting with a pre-existing invariant. Requires Level-2 CLASS. |
| `CHORE`     | Sole touches in `{pyproject.toml, .pre-commit-config.yaml, .github/**, knowledge/llms.txt}`. Non-semantic; no logic or rule changes.                       |

**Cross-category resolution.** When a single diff spans multiple
labels (which §No mixed PRs below forbids but a slipped PR may
still produce), the classifier picks the highest-impact label per:

```text
ADR-RULE  >  IMPLEMENT  >  FIX  >  RESEARCH  >  CHORE
```

The hook emits a WARNING «multi-intent diff detected; consider
splitting per §No mixed PRs» — see [§No mixed PRs](#no-mixed-prs)
below.

**Mirror files** (`HANDOFF.md`,
`knowledge/trace/exploration_log.md`,
`knowledge/adr/DIGEST.md`, `knowledge/llms.txt` when ride-along)
do NOT independently trigger any intent — they are updated in the
same PR per
[§PR Checklist rule #9](#pr-checklist)
(ADR PRs) or per maintenance rules, but the intent is set by the
upstream change they mirror. If the diff is mirror-only with
nothing upstream, the hook emits «mirror-only diff is unusual;
pick the dominant upstream intent or commit as `CHORE` if pure
cleanup».

### Level 2 — CLASS (only when INTENT: FIX)

| Label        | Meaning                                                                                                                                       |
|--------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| `REPAIR`     | Restore a broken invariant verbatim. No ADR amendment needed.                                                                                  |
| `RELAX`      | Weaken or change a strict invariant. MUST land an ADR amendment in the same PR per [§PR Checklist rule #9](#pr-checklist). |
| `WORKAROUND` | Temporary bypass of an invariant. MUST catalogue the pattern under [`knowledge/anti-patterns/`](../../anti-patterns/README.md) in the same PR and link the entry from the PR description; if the invariant is genuinely the wrong shape, escalate to `RELAX` instead. |

### INVARIANT line content (per intent)

| Intent       | Required INVARIANT content                                                                                                                |
|--------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| `RESEARCH`   | `n/a` — research artefacts do not bind project behaviour by themselves.                                                                  |
| `ADR-RULE`   | `Contract: <one sentence stating the introduced or modified clause>`                                                                     |
| `IMPLEMENT`  | `Implements: <ADR or rule reference, e.g. ADR-10 §2 or knowledge/skills/pr-creation/SKILL.md>`                                            |
| `FIX`        | `Affects: <pre-existing ADR or rule invariant being restored / changed / bypassed, e.g. ADR-7 §5 Input validation>`                       |
| `CHORE`      | `n/a` — non-semantic updates do not change any invariant.                                                                                |

## Decision points

These are the **judgement-bound** clauses — what the LLM must
decide when applying the skill. Not numbered orchestration steps.

### D-1 — Compose the INVARIANT line content

The intent label is mechanical (the classifier picks it). The
**content** of the `INVARIANT:` line is LLM-bound: name the right
ADR / rule clause, in one sentence, that the PR upholds (for
ADR-RULE), realises (for IMPLEMENT), or affects (for FIX). When
unsure which clause is touched, read the diff's surrounding
context and the closest binding ADR before composing.

### D-2 — Choose REPAIR vs RELAX vs WORKAROUND (FIX only)

The Level-2 CLASS sub-classifier captures **intent toward the
invariant**, not implementation shape:

- **REPAIR** — the diff restores the invariant the codebase
  already promises. No ADR change needed; the codebase had
  drifted, the diff brings it back. Most FIX PRs are REPAIR.
- **RELAX** — the diff changes (typically weakens) a strict
  invariant because the strict shape was wrong. MUST come with
  an ADR amendment in the same PR. If you are tempted to RELAX
  without changing an ADR, you are probably actually doing
  WORKAROUND.
- **WORKAROUND** — the diff bypasses an invariant without
  changing it. The invariant remains stated; the PR routes
  around it for now. MUST catalogue the pattern under
  `knowledge/anti-patterns/` and link the entry. WORKAROUND is
  the **escape hatch**, not the default — repeated WORKAROUNDs
  on the same invariant signal that RELAX is the right shape
  and the invariant is incorrectly stated.

### D-3 — Fill `DEGREE-OF-FREEDOM CLOSED:` (FIX only)

One sentence naming the spec-bearing decision the LLM previously
had a degree of freedom on, that this fix removes.

- A genuine answer names a **producer-site** decision (a schema
  field shape, a function return contract, a config validation
  rule). «The agent could accept either shape and produce
  silently-wrong output» is the canonical form.
- `n/a (reason)` is accepted when the FIX has **no agent-facing
  degree of freedom** — pure type-bugs the compiler caught,
  refactors that move code without changing behaviour, dependency
  bumps, test reshuffles that pin no new invariant. The reason
  MUST be explicit; blank or `<fill me>` is rejected.

### D-4 — Fill `DETERMINISTIC MECHANISM:` (FIX only)

One sentence ending with a `repo/file.ext:line` citation that
resolves against the staged tree — the function / type /
constant / schema / exit-code contract that closes the degree of
freedom named in D-3.

- The citation MUST resolve: the file exists in the staged blob
  (or HEAD if the file is unmodified), and the line number is
  within the file's bounds. The hook validates this; a
  non-resolving citation is a hard fail.
- `n/a (reason)` is paired with D-3's `n/a (reason)` — same
  reason; if D-3 is `n/a` because no agent surface exists, D-4
  is `n/a` for the same reason.
- A **two-token meaningless mechanism string** (`mechanism: fix`,
  `mechanism: the bug`) is structurally impossible to pass —
  the citation requirement forces a real artefact. If you cannot
  point at a producer-site artefact, the fix is shallow; see
  §Escalation.

### D-5 — Decide whether to override the classifier's INTENT

The hook is `INTENT`-suggestive but not `INTENT`-prescriptive —
the classifier output is a default the agent may override (e.g.
a NEW `src/fa/**` file is normally `IMPLEMENT`, but a contributor
may override to `FIX` if the new file is itself the fix shape
for an existing invariant). When overriding:

- Override is **logged** so the reviewer sees the shape
  mismatch.
- Write the override reason as a one-sentence rationale at the
  top of the PR description: `INTENT override: classifier
  suggested <X>; overridden to <Y> because <reason>.`
- Overrides that cannot be justified in one sentence are
  probably wrong — re-classify with the classifier's default.

## Output format

The PR description AND the first commit message body MUST open
with two or three header lines, mechanically derived from the
staged-paths shape per §Reference above:

```text
INTENT: <RESEARCH | ADR-RULE | IMPLEMENT | FIX | CHORE>
[CLASS: <REPAIR | RELAX | WORKAROUND>]   ← only when INTENT: FIX
INVARIANT: <one sentence | n/a>
```

For `INTENT: FIX` PRs, the description ALSO carries the
**anti-shallow-fix gate** clauses immediately after the
`INVARIANT:` line:

```text
DEGREE-OF-FREEDOM CLOSED: <one sentence | n/a (reason)>
DETERMINISTIC MECHANISM: <one sentence ending with `repo/file.ext:line` | n/a (reason)>
```

This output format is the **single source of truth** for the
PR B hook. The hook's regex matches against the shape above; a
snapshot test in PR B pins the hook regex to this section so the
two views cannot drift.

## PR Checklist

Verify before opening any PR. Each item has triggered wasted
review cycles in the project's recent history. Until the
`prepare-commit-msg` / `commit-msg` hook lands (PR B), the agent
is responsible for self-checking against each rule.

1. **Code fences have language tags.** No bare ` ``` ` at opening!
   Underlying style rule lives in
   [`AGENTS.md` §Working in This Repo](../../../AGENTS.md#working-in-this-repo);
   this is the PR-time gate.
2. **Frontmatter uses `compiled:`, not `date:`.** Schema:
   [`knowledge/README.md` §Conventions](../../README.md#conventions).
3. **File length within tier limits.**
   - Summaries / overviews: **<1000 lines**.
   - Deep-dive research: **<2000 lines**.
   - Readability > size.
4. **`compiled:` date ≥ all dates cited in text.** No temporal
   impossibilities.
5. *(DELETED 2026-05-25 — supersession-not-overwrite no longer
   mandated as a PR Checklist rule. Slot retained so rules
   6..10 keep their numbers; archival mechanics remain
   per-artefact in
   [`knowledge/MAINTENANCE.md`](../../MAINTENANCE.md).)*
6. **PR description lists changed / new files as clickable
   blob-URLs** (`https://github.com/<owner>/<repo>/blob/<branch>/<path>`),
   at least for non-trivial files. Plain bullet text is
   insufficient — reviewers should be able to open each file in
   one click without copy-pasting paths. Use the head branch of
   the PR, not `main`.
7. **`knowledge/llms.txt` reflects reality.** If this PR adds,
   removes, or renames a file under `docs/` or `knowledge/`,
   follow the matching checklist in
   [`knowledge/MAINTENANCE.md`](../../MAINTENANCE.md) (§When
   adding a new file / §When archiving a research note / §When
   superseding a non-research file). Pre-commit regenerator is
   planned post-Phase S
   ([`docs/workflow.md`](../../../docs/workflow.md) item 7).
8. **Research notes from the research-briefing workflow start
   with §0 Decision Briefing.** Notes under `knowledge/research/`
   produced via
   [`knowledge/prompts/research-briefing.md`](../../prompts/research-briefing.md)
   MUST place a `## 0. Decision Briefing` section as the first
   section after the frontmatter (before TL;DR / Scope). Each
   recommendation in §0 follows the eight-field format (What /
   Project-axis fit (A, B) / Goal-lens fit (C) / Cost / Verdict /
   If UNCERTAIN-ASK / Alternative-if-rejected / Concrete first
   step). Axes (A) "reduces session-start noise" and (B) "helps
   LLM find context" are stable project-axis criteria evaluated
   identically for every note; axis (C) "advances chosen
   goal_lens" is the only per-session axis and references the
   goal_lens elicited in Stage 1. §0 closes with a 7-column
   summary table (R-N / Verdict / Project-fit / Goal-fit / Cost /
   Alternative-if-rejected / User decision needed?). Frontmatter
   MUST include a `goal_lens:` field capturing the one-sentence
   research goal elicited at session start. The agent also posts
   §0 verbatim in chat after handover. This rule applies to
   **new** notes with `compiled: ≥ 2026-05-04`; older notes are
   exempted and not retro-fitted.
9. **New ADR PRs append to the exploration log and update a
   DIGEST.md row.** Any PR that introduces or amends an accepted
   ADR MUST append a block (or amendment block) to
   [`knowledge/trace/exploration_log.md`](../../trace/exploration_log.md):
   the question, the chosen option (`Chosen:`), each rejected
   option with `Reason:` (why rejected at decision time) +
   `Lesson:` (what new evidence would re-open the branch), and
   `Coupling:` cross-question coupling when applicable. Schema
   reference:
   [`knowledge/README.md` §`trace/`](../../README.md#trace--exploration-log).
   Rationale: the log is the cheap-read overlay agents use to
   understand *why* alternatives were rejected without re-reading
   every ADR end-to-end (origin: research note
   [`ara-protocol-cross-reference-2026-05.md`](../../research/ara-protocol-cross-reference-2026-05.md)
   §9 R-1). Log converted from YAML DAG to telegraphic markdown
   2026-05-10 per Tsinghua NLAH finding (code → NL migration:
   +16.8 pp accuracy, 9× faster, 97% fewer LLM calls on
   `arXiv:2603.25723`). **In the same PR**, also update
   [`knowledge/adr/DIGEST.md`](../../adr/DIGEST.md) — add a
   one-paragraph row for a new ADR or extend the **Amendments**
   bullet of the matching ADR's row. DIGEST.md is the
   agent-reading cheat-sheet (one paragraph per ADR ≈ 80 lines
   for all seven); stale rows defeat the purpose. **In the same
   PR**, also cross-check
   [`HANDOFF.md`](../../../HANDOFF.md) §Current state ADR list —
   it is the human-readable mirror of the ADR slate (per
   `HANDOFF.md` §Why this file exists) and drifts silently if
   not enforced. If the PR adds an ADR, append a bullet under
   §Current state *Architecture decisions*; if it amends one,
   extend the existing bullet with an *Amendment YYYY-MM-DD*
   clause. Same drift risk that motivates the DIGEST rule above
   applies here.
10. **Harness-component PRs cite minimalism-first evidence.** PRs
    that introduce or amend a harness component (tool,
    prompt-layer, retrieval-stage, executor, sandbox-rule) MUST
    include in the description **explicit answers** to the
    4-question minimalism-first test from
    [`knowledge/project-overview.md` §1.2](../../project-overview.md#12-enforceable-principle--minimalism-first):

    1. Research-evidence supporting the component's necessity
       under UC1+UC3 single-user scope (paper / primary-source
       post / eval-report citation).

       *Recognised anti-patterns the citation must clear*
       (forward-only from 2026-05-20):
       - **«Prompt-diversity layer» / re-asking with paraphrased
         prompts is NOT a valid harness component** — Nitarach
         P-3 §4.4 finding
         ([correlated-LLM-errors note §4.4](../../research/correlated-llm-errors-and-ensembling-2026-05.md))
         shows prompt-diversity ensembles do not yield consistent
         gains; gains are sample-by-sample noise, not signal. A
         PR that proposes «retry with a re-worded prompt» MUST
         instead cite the underlying mechanism (different
         temperature, model family, retrieval scope) it would
         actually exploit. The layer-name «prompt diversity» on
         its own is rejected as under-specified.
       - **«Spawn-recursion» sub-agent — sub-agent that can spawn
         further sub-agents — is NOT allowed.** Cap
         `SUBAGENT_MAX_STEPS ≤ 100`, sub-agent tool set MUST
         exclude any `SpawnSubAgent` tool, sub-agent invocation
         MUST use `generateText` (not streaming). Captured in
         [ADR-7 §Amendment 2026-05-20](../../adr/ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule)
         rule 5 and
         [BACKLOG.md I-2](../../BACKLOG.md#i-2--agent--sub-agents-for-context-load-reduction)
         pending the BACKLOG I-2 implementation.
    2. Open-source agent-stack precedent that **already** removed
       or did not add a similar component, and the observed
       result.
    3. Concrete capability lost if the component is omitted, and
       whether it can be replaced by an existing tool or config
       setting.
    4. **Could this step be a deterministic Python function
       instead of an LLM call?** If the step is parsing,
       formatting, aggregation, fan-out over a list, file lookup,
       or any other operation that does not require model
       judgement, a function is the correct default; an LLM call
       is justified only when the step needs reasoning that
       cannot be expressed deterministically. Subtraction
       question per user idea 4 + ADR-7 prep input — the
       inner-loop is the natural seat of step-as-function vs
       step-as-LLM-call decisions; the rule captures the
       discipline now so ADR-7 inherits it.

    After UC5 landing, KPI-delta on a reproducible benchmark
    replaces the 4-question test for harness components
    measurably evaluated. Documentation-only or non-harness PRs
    (research notes, README updates, lint fixes) are exempted.
    This rule applies to **new** PRs from the merge of this PR
    forward; older PRs are not retro-fitted.

The PR-time context-budget declaration (the «design invariant»
sub-rule of the former PR Checklist rule #11) lives in
[`AGENTS.md` §Context-budget discipline](../../../AGENTS.md#context-budget-discipline)
because it applies to every harness session, not only to
PR-creation time. This skill cross-checks that any harness-PR
description states which mitigation (a / b / c / d) the PR
adopts; the rule itself is loaded once per session via AGENTS.md,
not by this skill.

## PR Description Style

PR descriptions are the *first reading-pass* for both human
review and LLM agents loading repo context. They should be
readable end-to-end (no bullet-soup), and they should be cheap to
parse for the same agents that wrote them.

**Language split:**

- **Default to Russian** for analytical prose, rationale, scope
  discussion, retro-fit notes — this matches the convention
  already in force for research notes
  ([`knowledge/README.md` §Conventions](../../README.md#conventions))
  and keeps the human-review path natural.
- **Keep in English** any *identifier* whose precision matters
  for later grep / cross-reference: file paths, frontmatter keys
  (`compiled:`, `goal_lens:`), rule references («§PR Checklist
  rule #N» — now skill-internal), full PR titles when
  referencing other PRs (e.g. «PR #16 *docs: add
  research-briefing workflow…*»), code blocks, schema examples,
  verdict tokens (`TAKE` / `SKIP` / `DEFER` / `UNCERTAIN-ASK`).

**Recommended structure:**

One-paragraph what+why opening — Russian prose, what ships +
motivating problem. No bullets here.
Files (clickable blob-URLs) per [§PR Checklist rule
#6](#pr-checklist) above.
Design-rationale prose for any non-obvious choice — flowing
paragraphs, not bullets, when explanation > 3 lines.
Scope / ordering / retro-fit — short list (≤5 items) flagging
merge-order, deferrals, forward-only clauses.
Review & Testing Checklist for Human — GitHub PR template
block; Russian for action items, English for technical
referents.
Notes — Russian; mention follow-up PRs and any session-
continuity context. AI-Session trailer is appended automatically.

**Execution Rules:**

Develop complex lists into prose: If a sequence exceeds 5 items,
requires 2-3 lines per item, write cohesive Russian paragraphs.
Reserve bullet points strictly for short, scannable lists.
Synthesize the commit history: Write a fresh, high-level summary
and explicitly reference the commit SHA. Treat the PR body as an
independent overview rather than a verbatim copy of the commit
log.
Only reference identifiers (like PRs or issues) that already
exist and resolve perfectly at read-time.
Inline review comments / replies follow the same language split:
Russian prose for the response; keep the cited identifier (file
path / line / suggestion code-block) in English.

**Canonical examples:**

- [PR #17 *docs: add knowledge/trace/exploration_tree.yaml backfilling ADR-1..6 (R-1)*](https://github.com/GrasshopperBoy/First-Agent-fork/pull/17)
  — DAG backfill PR; description retro-rewritten in this style
  as a demonstration before this convention merged.
- [PR #18 *docs(AGENTS): add §PR Description Style — Russian
  prose + English identifiers*](https://github.com/GrasshopperBoy/First-Agent-fork/pull/18)
  — original landing PR; self-demonstrating description.

## AI-Session trailer

When a commit is driven by a Devin (or other LLM-agent) session,
add an `AI-Session: <session-id>` trailer to the commit message.
This preserves the link from a squash-merged commit back to the
originating session for audit and re-entry. Pattern lifted from
`codedna` (see
[`research/agentic-memory-supplement.md` §3](../../research/agentic-memory-supplement.md)).

Every commit within a PR-bearing branch carries the trailer
(`AI-Session:` is per-commit, not per-PR); the trailer is read by
the post-merge audit path. In this project all commits land
inside a PR (no direct push to `main`), so in practice every
LLM-driven commit gets the trailer. Example:

```text
docs: add ADR-N on <topic>

Body...

AI-Session: 2f45f66ef9ff45eab03161ecef165c0e
Co-Authored-By: <human> <email>
```

## What the hook validates

Once the `prepare-commit-msg` / `commit-msg` hook lands (PR B),
it will mechanically validate every commit on the PR's branch:

- **`prepare-commit-msg` (BEFORE the agent sees the commit-msg
  buffer)** — pre-populates the template with the
  mechanically-derived `INTENT:` line plus `<fill me>`
  placeholders for every required field per the intent's row
  above. The agent sees the placeholders before composing;
  cognitive load drops from «remember the rule» to «fill the
  placeholders».
- **`commit-msg` (AFTER the agent composes the message, BEFORE
  the commit lands)** — validates field-presence per the intent's
  required-field table; returns ALL violations in one pass (no
  short-circuit on first failure); hard-fails the commit on any
  violation.

The hook checks:

1. `INTENT:` line is present and value is in the closed enum.
2. `CLASS:` line is present iff `INTENT: FIX`, value in the
   closed enum.
3. `INVARIANT:` line is present and content matches the intent's
   required shape (see §Reference table).
4. For `INTENT: FIX`: `DEGREE-OF-FREEDOM CLOSED:` and
   `DETERMINISTIC MECHANISM:` are present and non-empty.
5. For `INTENT: FIX`: `DETERMINISTIC MECHANISM:` ends with
   `path/file.ext:line` and the citation resolves (file exists in
   staged tree or HEAD; line number within bounds), OR
   `n/a (reason)`.
6. Tautology check: `DEGREE-OF-FREEDOM CLOSED:` and
   `DETERMINISTIC MECHANISM:` are not string-identical modulo
   whitespace.

Until PR B lands, the agent is responsible for hand-emitting the
header lines per §Output format and self-checking against the
list above.

## Escalation

Inability to name either D-3 or D-4 with a meaningful answer
(non-`n/a`, non-tautological, citation resolves) **escalates**
the PR from `CLASS: REPAIR` to `CLASS: WORKAROUND` and
catalogues under
[`knowledge/anti-patterns/AP-003-shallow-fix-no-mechanism.md`](../../anti-patterns/AP-003-shallow-fix-no-mechanism.md).

The asymmetry is the wedge: a cheap-scope guard is cheap to
write but expensive to dress up convincingly with a real
`path/file.ext:line` citation that closes a *named* degree of
freedom — and a reviewer spots the tautology in two seconds.
The gate is *action-count* mitigation per
[`AP-001` §Why-the-wrong-shape-dominates](../../anti-patterns/AP-001-spec-bypassing-workaround.md),
not *rule-count* mitigation; the discipline lives in the
mechanically-verifiable citation, not in remembered prose.

## No mixed PRs

A PR that genuinely covers two intents MUST split. Cross-category
resolution above picks the dominant intent for a slipped PR;
this subsection is the canonical home of the single-concern
discipline (there is no separate numbered PR Checklist rule for
it — the rule lives here, attached to the classifier that
detects violations). The classifier's WARNING surfaces the
violation; the reviewer enforces the split.

## Worked example

See [`AP-003-shallow-fix-no-mechanism.md`](../../anti-patterns/AP-003-shallow-fix-no-mechanism.md)
§Wrong shape vs §Right shape — a `fs.move_file` schema bug
worked-history showing both the shallow `try / except FileNotFoundError`
WORKAROUND and the producer-site schema-fix REPAIR; the
DEGREE-OF-FREEDOM CLOSED / DETERMINISTIC MECHANISM clauses make
the difference reviewable in two seconds.

## Rationale (≤ 3 sentences)

The previous §Change Classification rule fired at PR-description
time — post-code, post-diff, post-commit-message — which is the
*last* gating point and the weakest; moving the gate to
`prepare-commit-msg` (pre-description, pre-commit) cuts
action-count: the agent never has the freedom to choose the
wrong-shape header, because the right-shape skeleton is already
in the buffer when they start typing. Externalising the rule —
along with §PR Checklist rules 1-10, §PR Description Style, and
the AI-Session trailer paragraph — from AGENTS.md to this skill
keeps AGENTS.md scoped to the universal session loadout (repo
navigation, style, pre-flight discipline, design invariants the
session must keep loaded at all times) and makes the PR-creation
rulebook loadable on-demand per ADR-10 §1 context-budget
invariant. The skill gives the PR B hook a single parsing target
that matches what the agent sees; the PR-time portion of the
context-budget invariant (mitigation declaration in the PR
description) is the only cross-cutting check kept dual-located
because the underlying design rule is always-loaded in
[`AGENTS.md` §Context-budget discipline](../../../AGENTS.md#context-budget-discipline).
