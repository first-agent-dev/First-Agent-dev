---
Roadmap-ID: RM-planning-topology
slug: planning-topology-and-executable-contracts-loop
created: 2026-09-09
status: IN PROGRESS
active-increment: I01
supersedes: worklogs/implementation-plans/PLAN-slice-ceremony-harness-enforcement.md
---

# ROADMAP: Planning topology & executable-contracts loop

## Intent

Rebuild the role-based loop (planner → coder → eval, code-owned controller, chat
orchestrator) around the locked planning topology — **feature → increment → `SLICE#`
→ `STEP#`** — with **executable contracts** (the planner authors each slice's test; the
harness proves it non-vacuous), a **deterministic verify gate** (exit code = fact; eval
verdict = judgment), and an **EVIDENCE ledger** that makes each increment smarter than
the last.

This roadmap **supersedes** the 27-chapter `PLAN-slice-ceremony-harness-enforcement.md`
(198 KB), which collapsed under its own scope at the S15 eval-verification roadblock.
The still-relevant on-hold slices from that plan are **absorbed and revised** into the
increments below (see "Absorbed from the superseded plan"), not carried verbatim.

## Artifact schema

This project uses the new per-project schema (canonical spec:
[`notes/artifact-schema-and-grammar.md`](notes/artifact-schema-and-grammar.md)):

```
worklogs/planning-topology-and-executable-contracts-loop/
  roadmap.md        ← this file (the index)
  ledger.md         ← EVIDENCE ledger (append-only, provenance-tagged)
  increments/       ← one file per increment; SLICE#s are sections inside
  notes/            ← supporting specs, reviews, research for this project
```

## Increments

Rolling wave: **I01 is planned in full** (`increments/increment-01-…`); I02–I06 are
**outlines** here and get their own detailed increment file just-in-time, when reached.
The map below is expected to be refined as reality teaches.

| ID | Increment | Status | One-line intent |
|---|---|---|---|
| **I01** | Plan grammar & extractor | **IN PROGRESS** | the harness can parse and lint the new plan format |
| I02 | Executable contracts & verify gate | outlined | a slice is gated by a planner-authored, non-vacuous test the harness runs. **Context banked for its review:** `notes/verify-block-design.{svg,md}` + `notes/i02-handoff-verify-gate.md` (grounded @ 0e08ece; re-review when I01 lands) |
| I03 | Per-slice loop, tracker & eval | outlined | controller runs the per-slice loop; code ticks the tracker; three-level eval |
| I04 | Evidence ledger, pinned invariants, retry hygiene | outlined | the loop carries evidence, pins governance, retries clean, never wedges (includes the ledger **parser**, moved here from I01 — build it beside its consumers) |
| I05 | Rolling-wave, ASK#, autonomy, chat orchestration | outlined | the roadmap closes across runs; the ceremony/scope/draft work lands here, revised |
| I06 | Telemetry & distillation (parallel deferred) | outlined | runs are measured and distilled; slice-DAG parallelism deferred |

### Deferred — explicitly not scheduled (from `RESEARCH-ADOPTION-PLAN.md`)

Recorded so nothing is silently dropped. Each is a real adoption item, deferred for cause;
none is in any increment above until promoted.

| Item | Why deferred | Promote when |
|---|---|---|
| #10 Escalation ladder / N-version repair | needs the parallel runner (shared with #11); the simple budgeted retry must prove out first | after I03's loop + I04's stall counter |
| #11 Slice DAG + parallel git worktrees | most premature; sequential first; worktree + runtime isolation is real work | after I03, on evidence of a parallelism bottleneck |
| #15 Post-feature distillation ritual | pays off over many features, not one | after several increments ship (I06) |
| #16 Hash-anchored tamper-evident run record | nice audit property, not load-bearing yet | if/when telemetry must be trusted by an outsider (after #17) |
| #18 Model tiering (planner-tagged) | conditional on #17 telemetry; premature tiering corrupts the data it saves on | after I06 telemetry has a few hundred slices |

(#17 telemetry *schema* is pulled forward into I06 — "cheap now, expensive later" — even
though the attribution *loop* is later.)

## Standing decisions (ADR-level)

Tagged `decided:` (chosen) or `assumed:` (never verified — an `ASK#` candidate).

- `decided:` Four tiers — feature → increment (one run, shippable) → `SLICE#` (one
  commit, contracts + verify) → `STEP#` (one atomic action).
- `decided:` Rolling wave — full detail for the current increment, one-line outline for
  later ones; staleness is managed at the **increment** boundary.
- `decided:` The **planner does the heavy lifting** — roadmap, increment, slices, steps,
  and the `TESTS:` files. The coder executes steps within firm contracts; major drift is
  a `REPLAN`.
- `decided:` Artifact schema = `roadmap.md` + `ledger.md` + `increments/` + `notes/`;
  folder is a pure slug, `created:` lives in frontmatter; increments zero-padded.
- `decided:` Rename `S#` → `SLICE#`, steps → `STEP#` (kills the `### Step S#` ambiguity).
- `decided:` Contracts carry **classes** (`FUNCTIONAL` / `CONSTRAINT` / `PRESERVATION`);
  the planner authors the test; the harness proves non-vacuity (fail-before/pass-after)
  — landed in I02.
- `decided:` Verify exit code = **fact**; eval verdict = **judgment**; eval runs on a
  different model family, blind to authorship.
- `decided:` Tracker updates (CT# status, STEP# boxes) are **code**, not an LLM step.
- `decided:` Agent-executable text is written as **exact imperatives** — file:line targets
  and runnable `(exit: …)` checks; no citations, history, or rationale inline. Rationale
  lives in `notes/`. (Schema §1; exemplified in increment-01.)
- `assumed:` 4–7 slices per increment is the sizing prior — tuned from telemetry (I06).
- `assumed:` Per-slice eval beats one cumulative eval — confirmed by the slice-diff size,
  re-checked once I03 telemetry exists.

## Absorbed from the superseded plan

The monster plan's on-hold slices (`S6, S6a, S6b, S7, S11b, S8, S9`) are **revised** into
this roadmap, not resumed as written. Mapping (verified against the monster plan's GAP
ledger and step headers):

| Old slice | Was | Becomes | Note |
|---|---|---|---|
| S6 | harness runs verification (GAP5/GAP13) | **I02** | the verify gate; now planner-authored tests + non-vacuity |
| S9 | mirror grammar into planning skills | **I01** | skill migration is part of the grammar increment |
| S11b | reconcile claimed vs observed verdict | **I03** | folded into the three-level eval |
| S6a | persist edit packets (GAP12, PR-body source) | **I05** | revised: the slice brief / PR source under the new schema |
| S6b | harness-derived draft (IntentGuard) | **I05** | revised: re-examine against the chat-orchestrator role |
| S7 | `ScopeWarnHook` files-allowed signal | **I05** | revised: scope signal under the slice-brief model |
| S8 | remove `pr_prepare` from chat (GAP7/GAP8) | **I05** | revised: chat becomes the orchestrator |

The superseded plan and its `worklogs/reviews/*` artifacts remain as **evidence only**;
they move to `worklogs/archive/` later (operator decision, not part of any increment).

## Sources

- `PRODUCTION-NOTE-planning-big-tasks-for-ai-agents.md` — the research (F1–F12, the
  18-item backlog, the evidence appendix).
- `RESEARCH-ADOPTION-PLAN.md` — the ranked adoption set this roadmap implements.
- `PLANNING-TOPOLOGY-EXPLAINED.md` — the topology this roadmap is built on.
- `worklogs/implementation-plans/PLAN-slice-ceremony-harness-enforcement.md` — the
  superseded plan (evidence only).
