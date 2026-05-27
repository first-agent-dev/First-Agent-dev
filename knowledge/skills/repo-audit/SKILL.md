---
name: repo-audit
description: |
  Reusable workflow for auditing and refactoring a research-heavy
  repository so that mid-tier OSS LLM agents (DeepSeek 4, Kimi 2.6,
  ~100 k effective context) can autonomously navigate it without
  lateral-thinking or meta-reasoning fallback. Captures the seven-
  phase flow used in the First-Agent-debloat session 2026-04-22 /
  2026-05-11. Optimised for the user's working style: middleground
  prose (not ultra-terse), evidence-backed findings (not speculation),
  PR-per-finding cadence with explicit deferral via BACKLOG.md.
status: active
last-reviewed: 2026-05-26
triggers:
  - "audit the repo for agent-readability"
  - "what should we prune from llms.txt / AGENTS.md / glossary"
  - "is the structure good enough for OSS LLMs"
  - 'give honest critical review of a doc / structure'
  - any variant of "look at the repo with fresh eyes"
relocated_from: knowledge/prompts/repo-audit-playbook.md (2026-05-26)
inputs:
  - repo at a defined commit (snapshot of "current state")
  - target LLMs (audience: tier + effective context window)
  - constraints (in-flight PRs to merge into baseline? scope cap?)
outputs:
  - one structured `repo-audit-YYYY-MM-DD.md` artefact
  - one `repo-audit-YYYY-MM-DD-revised.md` after critical re-pass
  - 3-7 doc-only PRs, each tied to one KEEP finding
  - new BACKLOG.md entries for demoted findings
forbidden:
  - modifying repo files during phases P1, P2, P3, P6 (analysis only)
  - merging PRs without explicit user approval
  - silently dropping findings (must demote to LOW-ROI with rationale)
prereqs:
  - Read [`AGENTS.md`](https://github.com/Bupitsa-ai/First-Agent-debloat/blob/main/AGENTS.md)
    Pre-flight checklist before write-side actions
  - Have `git log --oneline -20 main`, `git diff --merge-base main`,
    and `grep -rn "TODO\|XXX\|FIXME"` available
---

# Workflow — Agent-Oriented Repo Audit & Refactor

> **Lineage.** Distilled from the First-Agent-debloat session
> 2026-04-22 / 2026-05-11. Specific artefacts cited throughout are
> from that session and serve as worked-example anchors; the
> phase structure is reusable.

## 0. TL;DR — the loop

```text
P1 Frame ─► P2 Analyse ─► P3 Confirm & Diverge ─► P4 Implement
                              ▲                         │
                              │                         ▼
       P7 Capture ◄── P6 Critical re-pass ◄── P5 Assess
```

Seven phases. P1 → P5 is the «forward pass» (audit → PRs → write-up).
P6 is the load-bearing step that turned **27 findings into 6 KEEPs**
in this session by filtering on *measurable* performance impact — most
of the value of the entire workflow lives in P6. P7 closes the loop
by capturing the recipe for next time.

**Five rules that govern every phase** (load-bearing, written first
because they cut across all phases):

1. **Plan for the weakest downstream agent.** The audit target is
   mid-tier OSS LLMs (DeepSeek 4, Kimi 2.6, ~100 k effective context).
   What a Devin / Sonnet-class agent shrugs off, a mid-tier model
   stalls on.
2. **Evidence > speculation.** A finding survives P6 only if it has
   empirical support — peer-reviewed paper, repo-internal research
   note, or reproducible benchmark. "Models might…" loses.
3. **Middleground over ultra-terse.** The user explicitly prefers
   rules + nearby rationale to «5-word bullets». Trim ceremony, keep
   the «why» one paragraph away.
4. **PR-per-finding, doc-only first.** Each KEEP finding → ≤ 1 PR.
   Doc-only PRs ship first; code-touching PRs only after the doc-
   substrate is stable.
5. **No silent loss.** Demoted findings → BACKLOG.md with explicit
   unblock-trigger. Never delete-without-marker.

---

## P1 — Frame

> **Trigger.** User asks for an audit / critical review / structural
> assessment of the repo.

### Inputs

- User's brief (usually a 3-7 paragraph `<system_directive>` or
  `received_chat_message`).
- Repo at HEAD (note the commit hash; the audit is bound to it).
- List of in-flight PRs (do they count as part of the baseline, or
  not?).

### Action

Three reads, then stop:

1. `git log --oneline -10` — what landed recently?
2. Read the entry-point trio: `AGENTS.md`, `knowledge/llms.txt`,
   `HANDOFF.md`. These are the «bootstrap sequence» for any agent.
3. Read the user's brief twice. **Extract** four things:
   - **Audience tier** (Devin? Sonnet? DeepSeek 4? Kimi 2.6?)
   - **Effective context budget** (~100 k for OSS mid-tier; ~200 k for
     Sonnet-class).
   - **Success criterion** (the explicit one + the unstated one).
   - **Out-of-scope** (what user says they will do manually).

### Decision gates

- **Q1: Is the brief missing the audience tier?** Block, ask. The
  whole workflow pivots on this.
- **Q2: Does the user want one artefact or staged delivery?** Default
  to one artefact in P2.
- **Q3: Are there in-flight PRs?** If yes, decide whether to treat
  the audit as «main + open PR-N content as if merged» or
  «main only». **State explicitly in P2 output.**

### Output

A two-line acknowledgement to the user stating: (a) what you're
about to do, (b) any blocking question. **No write-side actions.**

### This-session anchor

User brief: «Design an Agent-Oriented research heavy repository —
optimising structure so that weaker OSS LLM agents (DeepSeek 4, Kimi
2.6) can autonomously navigate without lateral thinking». Extracted
audience tier (mid-tier OSS), effective context (~100 k), success
criterion (autonomous navigation; no meta-reasoning), out-of-scope
(human-process improvements).

### Anti-patterns

- Starting to read research notes before the entry-point trio. Wastes
  context budget; you do not yet know what's load-bearing.
- Assuming the brief == the actual scope. User's *unstated*
  constraint in this session was «do not modify Devin-only artefacts»;
  surfaced in P3, not P1.

---

## P2 — Analyse

> **Trigger.** P1 complete; audience tier and scope known.

### Inputs

- Repo at HEAD.
- Audience tier + effective context budget from P1.
- A bounded list of criteria (the user's 7 in this session, but
  cap at ~10).

### Action — five sub-steps

#### P2.1 — Sample, don't load

Read the entry-point trio in full. For everything else, **sample**:

- `prompts/` — first 30 lines per file.
- `knowledge/research/` — frontmatter + first 50 lines per file.
- `knowledge/adr/` — full read of `DIGEST.md`, then ADR-1 + ADR-2
  + the most recent ADR.
- `docs/` — full read of files referenced from `AGENTS.md` /
  `llms.txt`; skim the rest.

#### P2.2 — Simulate the bootstrap path

Manually walk the agent's first 60 seconds:

```text
HANDOFF.md → AGENTS.md §Pre-flight → llms.txt §MUST-READ
        → project-overview.md §1.1 → DIGEST.md
        → HANDOFF.md §Current state
```

Count tokens at each hop. Note where ambiguity, dangling links, or
forward-references appear. **This is where most CRITICAL / HIGH
findings will come from.**

#### P2.3 — Apply the user's criteria + your own

For each of the user's 7 criteria, find 0-N concrete instances. For
each instance, capture:

```yaml
section: "§N.M — short description"
severity: CRITICAL | HIGH | MEDIUM | LOW
location: "path/to/file.md:line-line"
mechanism: "one sentence — what bytes do the wrong thing"
suggested_fix_direction: "one sentence — not full fix wording"
roi: "expected effect on mid-tier OSS LLM bootstrap path"
```

Don't write fix wording in P2 — that's P4 territory. P2 is diagnosis,
not prescription.

#### P2.4 — Add criteria the user didn't ask for

In this session, four criteria were added (forward-references,
anchor-slug rot, language-switch density, blockquote-type confusion).
These came from **structural patterns I noticed while reading**, not
the user's list. Surface them as `§7.x — your-own check criteria` in
the output.

#### P2.5 — Embedded self-review (the «what did I miss» pass)

Before writing the final artefact, re-read your own findings as an
adversary:

- Am I double-counting? (In this session, §3.1, §7.1, §4.1 were the
  same root cause.)
- Am I citing empirical evidence, or speculating? (Mark
  `evidence: weak | strong | none` per finding.)
- Did I confuse `process-improvement` with `LLM-performance`? (In
  this session, EXEMPT clause was process; demoted in P6.)

### Output

One `repo-audit-YYYY-MM-DD.md` artefact. Section order:

```text
0. Method + scope + commit hash + treatment of in-flight PRs
1. Bootstrap path token-count walk
2. Findings § per criterion (1 .. N)
3. Top-K highest-ROI findings (1-line each, ranked)
4. What I did NOT cover (deliberately + cite the reason)
5. Open questions blocking next phase
```

### Decision gates

- **Q1: Is any finding CRITICAL?** Cite it in your message to user.
  CRITICAL means: would mislead an agent into a wrong action, not
  just slow it down.
- **Q2: Are there ≥ 3 forward-references (rule cites file F.md when
  F.md doesn't exist yet)?** This is a leading indicator of churn;
  flag it.

### This-session anchor

Artefact: <ref_file file="/home/ubuntu/repo-audit-2026-05-10.md" />
(~600 lines, 27 findings, 1 CRITICAL + 6 HIGH).

Bootstrap token count: ~28 k of 100 k budget (rule #11). Workable
but fragile.

### Anti-patterns

- Writing the artefact as you read. Causes you to anchor on the
  first issue you find. Read fully, then write.
- Prescribing fixes in P2. The user is still selecting findings;
  fix wording wastes effort on findings that get cut in P3.
- Skipping P2.5 self-review. In this session, P6 (critical re-pass)
  found 21 / 27 findings that should have been caught in P2.5 —
  but weren't, because the «am I speculating?» pass wasn't yet a
  habit. **Make it a habit.**

---

## P3 — Confirm & Diverge

> **Trigger.** P2 artefact delivered; user reads and replies.

### Inputs

- P2 artefact.
- User's per-finding response: usually one of `accept` / `skip` /
  `do manually` / `partial` / `defer`.

### Action — three sub-steps

#### P3.1 — Map user response to a finding-status table

```text
Finding  | Status   | User rationale                  | PR / Manual
§1.3     | accept   | — (default)                     | PR-X
§4.1     | skip     | "human-review process, manual"   | manual
§5       | accept   | —                                | PR-Y
§7.1     | manual   | "I'll do this"                  | manual
§8       | defer    | "future, when X exists"          | BACKLOG.md
```

#### P3.2 — Do a self-review of the artefact, not just findings

Before opening any PR, re-read the P2 artefact and flag your own
issues:

- Internal contradictions between findings?
- Sequencing errors? (e.g., «rewrite F.md» depends on «archive G.md»
  having landed first.)
- Naming conflicts? (Glossary insertion order, archive-banner
  format, etc.)

In this session, P3.2 caught 8 issues in the v1 artefact, surfaced
in `First-Agent-debloat-refactor-revision.md`.

#### P3.3 — Ask blocking questions

Don't open PRs while ambiguity remains. Two patterns from this
session:

- «Option A vs Option B» — surface as a question, let user pick.
  Example: «Archive convention — new `/archive/` directory OR
  in-place stubs?» User picked B.
- «Confirm specific item» — when one finding has a load-bearing
  detail you're unsure of. Example: «Confirm `devin-reference.md`
  archive specifically?» User confirmed yes + asked for inbound
  link updates.

### Output

A short message to user: (a) findings map + status, (b) self-review
issues caught, (c) blocking questions. **Block on user response.**

### Decision gates

- **Q1: Are there ≥ 2 blocking questions?** Batch them into one
  message; don't ask sequentially.
- **Q2: Did the user pick a non-default option that changes the PR
  sequence?** Update the sequence plan before P4.

### This-session anchor

After user picked Option B (in-place stubs) + confirmed
`devin-reference.md` archive: opened PR-A → PR-B → PR-C → PR-D as a
stack (since PR-B / PR-C / PR-D had concrete dependencies on each
other's content).

### Anti-patterns

- Treating «skip» as «reject permanently». User's «skip» often means
  «I'll do this manually» — keep the finding visible in your TODO
  but not in the PR plan.
- Starting P4 before P3 is finished. In this session, the v1 artefact
  was almost shipped without the P3.2 self-review; caught 8 issues
  late by re-reading it as an adversary.

---

## P4 — Implement

> **Trigger.** P3 complete; user has approved a set of findings and
> answered blocking questions.

### Inputs

- Status table from P3 (findings → PR / manual / defer).
- Sequencing plan (independent vs stacked).

### Action — five sub-steps

#### P4.1 — Decide PR sequence

Build a cross-file conflict matrix:

```text
            AGENTS.md  llms.txt  HANDOFF.md  glossary.md  research/*
PR-A glossary    .         .          .          ✏️           .
PR-B archive     .         ✏️         ✏️          .          ✏️
PR-C llms-txt    .         ✏️         ✏️          .           .
PR-D pre-flight  ✏️        .          .          .           .
```

- **Independent rows** (no ✏️ overlap) → parallel PRs against `main`.
- **Overlap rows** → stack with explicit `base_branch=PR-B`.

#### P4.2 — Branch naming

Follow the user's convention if specified. Default:
`devin/$(date +%s)-{descriptive-slug}`. **One PR per finding.**

#### P4.3 — Doc-only PRs first

In this session, all 13 PRs were doc-only. Code-touching PRs would
come later, after the doc-substrate is stable. **Doc-only PRs land
without CI**; iterate fast.

#### P4.4 — Apply «middleground» prose, not ultra-terse

User's load-bearing preference (worth re-stating because it shapes
every fix-wording choice): **keep the literal rule + the rationale
one paragraph away**, not in distant cross-references. Trim ceremony
(intro paragraphs, restated context). Keep one-sentence justifications
adjacent to each rule.

Example (this session, AGENTS.md rule #11):

```diff
- (terse) #11. Context budget ≤100k tokens.
- (verbose) #11. Context budget should be kept to under approximately
-   100,000 tokens in 90% of cases. The reason for this is...
+ (middleground) #11. Context budget ≤100 k tokens in 90 % of cases.
+   Mid-tier OSS LLMs (DeepSeek 4, Kimi 2.6) show effective-context
+   degradation past this point (RULER benchmark, Hsieh et al. 2024).
+   Mitigations: (a) sub-agent split, (b) lazy-load tool specs,
+   (c) trim archived bodies, (d) ...
```

#### P4.5 — PR description format

Auto-generated descriptions are fine. Append:

- **«Review & Testing Checklist for Human»** — explicit decisions
  the human should confirm (e.g., «is `cf7db4d` the right base?»).
- **«Notes»** — sibling PRs (PR-K, PR-M, PR-N), merge-order
  observations, why the diff is bigger / smaller than expected.

### Output

- Each PR opened with `git_create_pr`.
- Final message to user lists all PR URLs in one block (not staggered).

### Decision gates

- **Q1: PR diff size > 500 LoC?** Split unless it's a deletion-heavy
  prune (in this session, PR-M was -6,715 / +821 — exempt because
  most of the diff is grep-poison removal, not new content).
- **Q2: Any PR touches code, not just docs?** Defer until doc PRs
  merge; revisit in P5.

### This-session anchor

Stage 0 (4 PRs): PR-A (glossary) → PR-B (archive 12) → PR-C
(llms.txt rewrite) → PR-D (docs trim). Stage 1 (4+1 PRs):
PR-F (exploration_log.md) + PR-G (rule #11) + PR-H (rule #10 q4)
+ PR-J (§1.3 + repo-naming) parallel against main; PR-I (MAINTENANCE
+ BACKLOG) after PR-F merge. Critical-re-pass (3 PRs): PR-K, PR-N,
PR-M.

### Anti-patterns

- Stacking PRs unnecessarily. Stacking complicates review and rebase.
  Default to parallel-against-main; stack only when there's a
  concrete cross-file conflict (matrix in P4.1).
- Prefixing all PRs with «refactor:». Use the actual conventional
  commit prefix: `docs:`, `chore:`, `feat:`, etc. (this session
  used `docs:` for almost everything.)
- Force-pushing to main. Doc PRs land via `git_create_pr` only.

---

## P5 — Assess

> **Trigger.** Wave of PRs merged (or close to merging). Time to
> write up what shipped + what's next.

### Inputs

- Merged PR URLs.
- Any open follow-up PRs.
- New entries added to `BACKLOG.md` / `HANDOFF.md` / `MAINTENANCE.md`.

### Action — three sub-steps

#### P5.1 — Write a one-shot assessment

A `stage-N-assessment.md` (or `preflight-pass-assessment.md`, in this
session). Sections:

```text
1. What changed (per PR, one paragraph)
2. Expected effects on mid-tier OSS LLM bootstrap path
3. Pending follow-ups (manual items + BACKLOG entries)
4. Open questions for the next session
```

#### P5.2 — Update HANDOFF.md

Bump «Last updated», update `§Current state` ADR list. If a deferred
idea now has an unblock-trigger met, **move** it from BACKLOG.md to
HANDOFF.md `§Current state`.

#### P5.3 — Surface what didn't ship + why

Per Rule 5 (no silent loss): every finding that was demoted to
LOW-ROI or deferred → enumerated in the assessment with the rationale.

### Output

- Attach `stage-N-assessment.md` to user message.
- PR links re-listed (so user has a single message with everything).

### Decision gates

- **Q1: Did any PR fail CI / get blocked on Devin Review?** Surface
  to user explicitly; do not let it sit silent.
- **Q2: Is there a CRITICAL finding still un-shipped?** Block on
  user; don't close the audit.

### This-session anchor

Artefact: <ref_file file="/home/ubuntu/preflight-pass-assessment.md" />
(written after PR-E landed).

### Anti-patterns

- Skipping P5 entirely. In this session, P5 was the only artefact
  that documented «PR #2 Devin Review failed status is historical;
  resolved by commit 871a156 before merge». Without P5, that
  context is lost when the next session starts.

---

## P6 — Critical re-pass

> **Trigger.** P5 complete. User asks something like «are those
> findings REALLY affecting LLM performance?» — or you self-prompt
> the question.

> This is the load-bearing phase. Without P6, the audit produces
> noise. With P6, the audit produces signal.

### Inputs

- The P2 artefact (`repo-audit-YYYY-MM-DD.md`).
- Access to in-repo research notes (`knowledge/research/*.md`).
- Web search for external peer-reviewed sources.

### Action — five sub-steps

#### P6.1 — For each finding, ask the four-part filter

```text
1. Is there empirical support? (paper, benchmark, repo-internal note)
2. Is the effect measurable? (1pp on a benchmark, 30% token reduction)
3. Does the effect apply to the target audience? (mid-tier OSS LLM
   ≠ Sonnet-class ≠ frontier; some findings are tier-specific)
4. Is the cost of fixing > the expected value? (the «ROI» check)
```

If all four are YES → KEEP.
If any are NO → DEMOTE to LOW-ROI.
If unclear → DEFER (gather evidence next session).

#### P6.2 — Cross-reference with in-repo research

Repo has its own canon. Check:

- `knowledge/research/llm-wiki-critique.md` (corpus / search / load
  patterns).
- `knowledge/research/efficient-llm-agent-harness-2026-05.md` (tool
  contracts, layered prompts).
- `knowledge/research/agent-roles.md` (role asymmetries).
- ADR-1..ADR-6 for shipped decisions.

In this session, 4 / 6 KEEP findings had in-repo research support;
2 needed external citation.

#### P6.3 — Web-search for external corroboration

For each KEEP finding, find one peer-reviewed paper or one widely-
cited benchmark. In this session:

- **§4.1 archived-body grep-poison** → Lost-in-the-Middle (Liu et al.
  2023, arXiv:2307.03172, TACL).
- **§1.4 HANDOFF / AGENTS dual-bootstrap** → Procedural execution
  failure (Anthropic 2024 blog + Plan-to-Action paper).
- **§1.3 broken anchor** → Trivial UX bug; no paper needed, but
  Lost-in-the-Middle still applies (dangling links degrade retrieval).
- **§3.2 grep placeholder** → Grep-based retrieval pattern (well-
  documented; no single canonical paper).

If you cannot find external corroboration for a finding **and** in-
repo research is silent → demote to LOW-ROI.

#### P6.4 — Catch the «I should have caught this in P2.5» errors

In this session, P6 caught:

- **Code-switching myth.** Original audit recommended standardising
  ASCII quotes. Literature shows code-switching ENHANCES reasoning
  (Li et al. 2025: +5.6pp MATH500 on DeepSeek-R1). **Recommendation
  reversed.**
- **Token-budget alarmism.** Original audit flagged 28 k bootstrap
  as «high utilisation». 28 k of 128 k = 22 % = firmly in the smart
  zone (<40 %). Demoted to LOW-ROI.
- **Same-issue double-counting.** §3.1, §7.1, §4.1 all touched the
  same root cause (archived-body cohabitation). Consolidated into
  one CRITICAL.
- **Process-improvement masquerading as LLM-perf.** EXEMPT clause
  ambiguity affects PR coordination, not runtime LLM accuracy.
  Demoted to LOW-ROI; logged to BACKLOG as I-4.

#### P6.5 — Produce the revised artefact

`repo-audit-YYYY-MM-DD-revised.md`. Sections:

```text
0. Method (the four-part filter)
1. KEEP findings (with empirical citation per finding)
2. DEFER findings (need evidence next session)
3. LOW-ROI findings (with rationale for demotion)
4. BACKLOG additions (LOW-ROI items with unblock-triggers)
5. Revised PR plan (KEEP findings → PR-K, PR-M, etc.)
```

### Output

- Attach `repo-audit-YYYY-MM-DD-revised.md` to user message.
- Block on user for «approve revised plan? open PR-K / PR-M / PR-N?»

### Decision gates

- **Q1: How many findings survived?** Healthy ratio is 20-30 % KEEP.
  In this session: 6 / 27 = 22 %. If > 50 % survive, your P6 filter
  is too lenient; re-tighten.
- **Q2: Are demoted findings + DEFERs all logged in BACKLOG.md?**
  Verify before closing P6.

### This-session anchor

Artefact: <ref_file file="/home/ubuntu/repo-audit-2026-05-10-revised.md" />
(~600 lines, 6 KEEP + 2 DEFER + 19 LOW-ROI).

### Anti-patterns

- Skipping P6 because P5 felt complete. **P5 captures what shipped;
  P6 captures whether what shipped was the right thing.** Different
  questions, different answers.
- Demoting a finding without writing the rationale. The next
  session's audit will surface the same finding again.
- Using «expert intuition» without paper citation. In this session,
  the code-switching recommendation looked obviously correct
  («mix of quote styles is sloppy»); literature reversed it.

---

## P7 — Followup + workflow capture

> **Trigger.** P6 revised plan accepted by user.

### Inputs

- Revised KEEP set from P6.
- BACKLOG additions identified in P6.
- This workflow document (recursive: P7 produces the next version
  of this very file).

### Action — three sub-steps

#### P7.1 — Implement KEEP set

Repeat P4 sub-steps with the revised PR plan. In this session:
PR-K (#11, ~15 LoC, three KEEP findings), PR-N (#12, ~30 LoC,
glossary trim), PR-M (#13, -5,900 lines, archived body trim).

#### P7.1.a — Trim operations: preserve, don't paraphrase

**Load-bearing.** Any PR whose action is «remove the body and
leave a short stub» is a trim operation. Trim operations have a
distinct failure mode that PR-style code review catches but P4
self-review usually does **not**: paraphrasing pre-existing prose
from session-memory introduces silent semantic drift.

Examples of drift seen on PR-M (#13) before the fix-up commit:

- A research note about MEMM (Rust/Tauri codebase) was paraphrased
  as a Python project, with fabricated `memm/scoring/signals.py`
  source paths.
- A `source:` frontmatter field originally listing
  `sliders-structured-reasoning-2026-04.md` was rewritten to
  `deepseek-v3-sliders-2026-04.md` — a filename that doesn't exist
  in the repo.
- A community-projects survey citing six real repositories was
  replaced with six fabricated repositories whose URLs 404.

The trim's goal was «collapse the grep surface for archived
bodies», not «produce a faithful abstract». Conflating those two
goals is the failure mode.

**Discipline for trim PRs:**

1. **Never modify frontmatter during a trim.** Read it from the
   pre-trim commit with `git show <base>:<path>` and write it out
   verbatim. The only allowed frontmatter delta is appending a
   `; body trimmed YYYY-MM-DD per PR-X` marker to an existing
   supersession banner.
2. **Never paraphrase the body from memory.** If a short abstract
   is genuinely useful, derive it line-by-line from the pre-trim
   text in a single side-by-side read — do not write it from
   recall after closing the file. This applies recursively to
   *template/boilerplate text* that replaces the body: a template
   that asserts facts about each file («the `source:` field is
   preserved», «the codebase is X») must be parameterised by what's
   actually in each file. Static strings asserting per-file facts
   are fabrications waiting to happen.
3. **Default to a pointer-only body** when in doubt. Two sections
   suffice: (a) `git show <base>:<path>` recipe with pre-trim line
   count; (b) link to the active superseder. No prose summary.
4. **Verify before push.** For each trimmed file run
   `git diff <base>...HEAD -- <path>` and visually confirm: the
   frontmatter diff is empty (or only the banner-marker append),
   and the body diff replaces prose with the pointer block.

**Decision rule.** If the agent can't faithfully reproduce the
original frontmatter without `git show`, it can't faithfully
abstract the body either. Choose the pointer-only path.

#### P7.2 — Add BACKLOG items

For each LOW-ROI / DEFER finding worth tracking, add an I-N entry
to `BACKLOG.md` with:

```markdown
## I-N — Short title

- **Status:** deferred from Stage X (proposed YYYY-MM-DD).
- **Idea:** What the deferred change is, in 2-4 lines.
- **Blocked-on:** What concrete artefact / decision must exist first.
- **Unblock-trigger:** The exact event that moves this from deferred
  to actionable.
- **First concrete step once unblocked:** One sentence so the next
  session doesn't have to re-derive it.
- **Why this is LOW ROI for Stage X.** One sentence so the demotion
  rationale survives.
```

In this session, two BACKLOG items landed in PR-K (#11):

- I-4 EXEMPT clause needs explicit scope criteria.
- I-5 RESOLVER.md T2-T5 lack standalone template files.

#### P7.3 — Capture the workflow (this document)

Re-read the session and find:

- **Steps that worked** — these stay.
- **Steps that could merge** — collapse them.
- **Steps that were skipped without harm** — drop them.
- **New steps that emerged** — add them.

This session's compressions:

- Original v1 plan had P2.5 (self-review) as a separate phase.
  Folded it into P2 because it never made sense to do P2 without
  P2.5.
- Original v1 plan had «P3.5 ask blocking questions» as a separate
  sub-step. Folded into P3 because P3 *is* the ask-and-confirm
  phase.
- Added P6.4 («catch the I-should-have-caught-this-in-P2.5
  errors») as an explicit named step, because P6 doing the work
  that P2.5 should have done is a recurring pattern worth naming.
- Added P7.1.a («trim operations: preserve, don't paraphrase»)
  after Devin Review caught 5 fabrication regressions on PR-M
  (#13). The original P7.1 was a one-liner («repeat P4»); it
  missed that trim operations have their own failure mode that
  P4 self-review does not catch. The new sub-step encodes the
  «pointer-only» default + the four-rule discipline.

### Output

- Workflow .md attached to final user message.
- Plus all PR URLs from P7.1.
- Plus BACKLOG additions enumerated.

### Decision gates

- **Q1: Is the workflow itself reusable to someone who didn't
  participate in this session?** Test by reading it as a stranger.
- **Q2: Do all artefact-paths cited in the workflow still resolve?**
  This session's workflow cites `repo-audit-2026-05-10.md` etc. —
  those are on the box but not in the repo. **Mark explicitly.**

### This-session anchor

This file: `workflow-repo-audit.md`.

### Anti-patterns

- Writing a workflow that's just a session transcript. The point is
  to **abstract** the loop, not narrate the events. (This document
  uses session events only as worked-example anchors at the end of
  each phase.)
- Over-prescribing. A workflow with «do X, then Y, then Z, then W»
  fails on the first session that legitimately needs a different
  order. Use «trigger → action → output → decision gates» — leaves
  room for adaptation.
- **Treating P7.1 (implement KEEP set) as «just do P4 again».**
  This is what produced the PR-M fabrications in this session. Some
  KEEP findings are *trim operations* (delete content); those have
  the failure mode in P7.1.a. Apply P7.1.a discipline before push.

---

## Appendix A — Artefact catalogue (this session)

| Artefact | Phase | Purpose |
|---|---|---|
| `First-Agent-debloat-refactor.md` | P2 (pre-formalised) | v1 audit — 12 trim targets + bootstrapper + glossary |
| `First-Agent-debloat-refactor-revision.md` | P3.2 | Self-review of v1 audit; caught 8 issues |
| `preflight-pass-assessment.md` | P5 | Assessment after PR-E |
| `stage1-task-assessment.md` | P5 / P1-for-next-loop | Bridge from Stage-0 to Stage-1 |
| `stage1-action-plan.md` | P2 / P4 | 5-PR plan for Stage-1 with full wording |
| `stage1-action-plan-ru.md` | P3 (user-facing) | Russian translation of above |
| `repo-audit-2026-05-10.md` | P2 | First fully-structured audit, 27 findings |
| `repo-audit-2026-05-10-revised.md` | P6 | Critical re-pass, 6 KEEP + 2 DEFER + 19 LOW-ROI |
| `workflow-repo-audit.md` | P7 | This document |

The artefacts are on the working machine, not in the repo (intentional —
they're work-product, not docs the agent should grep at runtime).

## Appendix B — PR catalogue (this session)

**Stage 0 (initial debloat, after first user brief):**

- PR #1 PR-A — docs/glossary.md +16 terms (merged).
- PR #2 PR-B — archive 10 research + 2 docs in-place stubs (merged
  with fixup 871a156).
- PR #3 PR-C — llms.txt rewrite + HANDOFF.md trim (merged).
- PR #4 PR-D — docs/{architecture, workflow}.md trim (merged).
- PR #5 PR-E — AGENTS.md Pre-flight 5-step rewrite + research-
  briefing cross-link (merged).

**Stage 1 (parallel batch + sequenced PR-I):**

- PR #6 PR-F — exploration_tree.yaml → telegraphic exploration_log.md
  (merged).
- PR #7 PR-G — AGENTS.md rule #11 «≤100 k token context budget»
  (merged).
- PR #8 PR-H — rule #10 question 4 code-functions-first (merged).
- PR #9 PR-J — §1.3 three-stage model + repo-naming + HANDOFF
  cross-link (merged).
- PR #10 PR-I — MAINTENANCE.md + BACKLOG.md (merged).

**Critical-re-pass (P6 → P7):**

- PR #11 PR-K — Stage-1 critical-re-pass KEEP findings (merged
  2026-05-12; one fix-up commit `9c85e19` addressed Devin Review
  on the bootstrap canonicality wording).
- PR #12 PR-N — glossary trim 8 duplicative rows (merged
  2026-05-12; one fix-up commit `7b59434` corrected the
  Symmetric-reading grep path and the stale R-N / Q-N row left
  over from PR-F).
- PR #13 PR-M — trim 12 archived bodies (~5,900 lines deleted)
  (merged 2026-05-12; one large fix-up commit `6622e66` reverted
  frontmatter fabrications and replaced the abstract-style bodies
  with pointer-only bodies per P7.1.a discipline, plus a second
  fix-up `923fb28` + `b36d0f9` that parameterised the pointer-block
  boilerplate per file — see the recursive-fabrication note in
  Appendix B-2 below).

## Appendix B-2 — Failure-mode catalogue (this session)

Failure modes that actually fired in this session, with the phase
that *should* have caught them. Use as a checklist for future P3.2,
P4 self-review, and P7.1.a.

| Failure mode | Where it fired | Caught by | Should have been caught at |
|---|---|---|---|
| Same finding triple-counted across audit sections | P2 of `repo-audit-2026-05-10.md` | P6 dedup | P2.5 |
| Code-switching recommendation contradicting empirical literature | P2 finding §4.3 | P6.3 web-search | P2.4 / P6.3 |
| Token-budget alarmism (28k bootstrap on 128k window framed as «risky») | P2 finding §1.6 | P6 four-part filter | P2.3 |
| Trim PR rewrote frontmatter from memory | PR-M `28eb9a9` | Devin Review | P4 self-review (now P7.1.a) |
| Trim PR fabricated source URLs in body | PR-M `28eb9a9` | Devin Review | P4 self-review (now P7.1.a) |
| Trim PR contradicted technology stack (Rust → Python) | PR-M `28eb9a9` | Devin Review | P4 self-review (now P7.1.a) |
| Trim PR claimed «portable mirror» where lists differed structurally | PR-K `5973278` | Devin Review | P4.4 «middleground» check |
| Trim PR introduced canonicality contradiction across two files | PR-K `5973278` | Devin Review | P4 cross-file consistency check |
| Trim PR misquoted authoritative source (extra grep path) | PR-N `7ed24f6` | Devin Review | P4 verification-against-source |
| Trim PR copy-pasted boilerplate stub-text across files without per-file verification | PR-M `6622e66` | Devin Review | P7.1.a per-file check |

Load-bearing observation: **all 10 failures fired in trim or
restate-from-memory operations.** Net-add PRs (PR-F exploration_log,
PR-G rule #11, PR-I MAINTENANCE+BACKLOG) had zero substantive
Devin Review findings. The signal: when the operation is *delete +
restate*, double the verification budget; when it's *add new
content*, single budget is fine.

Note on `6622e66`: the fix-up commit that resolved the first 5
fabrications introduced its own — a static boilerplate bullet
asserting frontmatter fields existed in all 12 files when they
actually existed in only 5/12. Recursive instance of the same
failure mode the fix-up was meant to close. Lesson is folded into
P7.1.a rule #2 («boilerplate text that asserts facts about each
file must be parameterised, not static»).

## Appendix C — User-style cheat-sheet

Inferred from this session's accept/skip/manual pattern. Future
session can use these as priors:

| User signal | Means |
|---|---|
| «accepted» without qualifier | Open PR with default wording |
| «skip, I'll do it manually» | Add to TODO, don't open PR |
| «be careful, too terse → middleground» | Add rationale paragraph nearby |
| «start to implement, look at the plan again» | Insert self-review step (P3.2) |
| «what do those changes affect» | Trigger P5 assessment |
| «those findings REALLY affect performance?» | Trigger P6 critical re-pass |
| «make a workflow from it» | Trigger P7 capture (this document) |
| «accepted» + «accepted» + «accepted» | User read the proposal; ship without further re-confirmation |
| Russian-language reply | Reply in Russian (or mixed); identifiers stay in English |

## Appendix D — Empirical citations referenced during P6

| Finding | Citation |
|---|---|
| Effective-context degradation past 50 % of claimed window | RULER (Hsieh et al. 2024, arXiv:2404.06654) |
| Lost-in-the-Middle / U-shaped attention | Liu et al. 2023, TACL (arXiv:2307.03172) |
| Procedural execution failure 5-step → 95-step | Plan-to-Action / Anthropic blog 2024 |
| Code-switching enhances reasoning | Li et al. 2025 (DeepSeek-R1 ablation) +5.6 pp MATH500 |
| Grep + contextual window retrieval | Anthropic engineering blog 2024 + Elastic context-poisoning post |
| Context budget <40 % utilisation as «smart zone» | AgentPatterns / contextpatterns.com (2024-2025) |

## Appendix E — When NOT to use this workflow

- Single-file changes (e.g., «fix a typo in README»). Workflow
  overhead > task cost.
- Code-only PRs touching `src/`. This workflow is doc-substrate-
  focused; code PRs have their own loop (TDD + CI).
- Sessions where the user explicitly asks for a quick assessment
  («just give me 3 bullet points»). Skip to P6 directly with a
  smaller finding set.
- When `repo-audit-*.md` artefacts from a prior session are < 30
  days old. Re-read them first; don't redo P2 from scratch.

---

## Reusable templates

### Audit finding template (P2.3)

```yaml
section: "§N.M — short description"
severity: CRITICAL | HIGH | MEDIUM | LOW
location: "path/to/file.md:line-line"
mechanism: |
  One sentence describing what bytes do the wrong thing.
suggested_fix_direction: |
  One sentence — direction only, not full wording.
roi: |
  Expected effect on mid-tier OSS LLM bootstrap path.
evidence: weak | strong | none
```

### BACKLOG item template (P7.2)

```markdown
## I-N — Short title

- **Status:** deferred from Stage X (proposed YYYY-MM-DD).
- **Idea:** ...
- **Blocked-on:** ...
- **Unblock-trigger:** ...
- **First concrete step once unblocked:** ...
- **Why this is LOW ROI for Stage X.** ...
```

### PR sequencing matrix (P4.1)

```text
            File-A   File-B   File-C   File-D
PR-X        ✏️        .        .        .
PR-Y        .        ✏️        ✏️        .
PR-Z        .        .        .        ✏️
```

Independent rows → parallel against `main`.
Overlap rows → stack with explicit `base_branch=PR-...`.

### P6 four-part filter

```text
1. Empirical support? (paper / benchmark / in-repo research)
2. Measurable effect? (1 pp, 30 % tokens, X% speedup)
3. Applies to target audience? (mid-tier OSS LLM specifically)
4. Cost(fix) < value? (the ROI check)

All YES → KEEP
Any NO → DEMOTE
Unclear → DEFER (gather evidence next session)
```
