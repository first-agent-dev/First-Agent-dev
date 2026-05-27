---
name: pr-creation
description: |
  Externalised PR intent classification and anti-shallow-fix gate.
  Load before opening any PR (including pure-doc PRs) to derive the
  header lines the agent must emit on the PR description and the
  first commit message body. Replaces the former §PR Intent
  Classification section that lived in AGENTS.md until 2026-05-26.
status: active
last-reviewed: 2026-05-26
triggers:
  - "about to open a PR"
  - "writing a commit message for a PR-bearing commit"
  - "filling in INTENT / CLASS / INVARIANT header lines"
relocated_from: AGENTS.md §PR Intent Classification (2026-05-26 — PR A')
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
[AGENTS.md PR Checklist rule #9](../../../AGENTS.md#pr-checklist)
(ADR PRs) or per maintenance rules, but the intent is set by the
upstream change they mirror. If the diff is mirror-only with
nothing upstream, the hook emits «mirror-only diff is unusual;
pick the dominant upstream intent or commit as `CHORE` if pure
cleanup».

### Level 2 — CLASS (only when INTENT: FIX)

| Label        | Meaning                                                                                                                                       |
|--------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| `REPAIR`     | Restore a broken invariant verbatim. No ADR amendment needed.                                                                                  |
| `RELAX`      | Weaken or change a strict invariant. MUST land an ADR amendment in the same PR per [AGENTS.md PR Checklist rule #9](../../../AGENTS.md#pr-checklist). |
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
*last* gating point and the weakest. Moving the gate to
`prepare-commit-msg` (pre-description, pre-commit) cuts
action-count: the agent never has the freedom to choose the
wrong-shape header, because the right-shape skeleton is already
in the buffer when they start typing. Externalising the rule
from AGENTS.md to this skill keeps AGENTS.md small (~150 lines
smaller), makes the rule loadable on-demand per ADR-10 §1
context-budget invariant, and gives the PR B hook a single
parsing target that matches what the agent sees.
