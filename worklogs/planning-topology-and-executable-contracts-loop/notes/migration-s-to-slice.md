# Migration note — `S#` → `SLICE#` / `STEP#` (for humans)

Status: informational. Owner: planner. Created 2026-10-07 for I01/SLICE4 STEP2.
Decisions: roadmap `decided:` "Rename `S#` → `SLICE#`" · ledger E13 (rename), E24
(extractor recognises `SLICE#` only), E106 (`S<n>` is ambiguous inside a plan).

## 1. What changed

The plan grammar renamed two id tiers:

| old form | new form | why |
| --- | --- | --- |
| `## S3: <title>` | `## SLICE3: <title>` | `S#` collided with the step tier |
| `### Step S3` | `- [ ] STEP3: … (exit: …)` | steps became checkbox lines carrying an exit check |

The collision was not cosmetic. A plan carries **both** tiers, so a bare `S3` has two
possible referents in the same document. The extractor now refuses to guess: `S<n>` is
rejected inside a plan body (E106, CT37), and only `SLICE<n>` opens a slice.

One leniency survives **on purpose**: `canonical_slice_id` still normalises legacy `S<n>`
tokens at the eval-report boundary (`src/fa/inner_loop/workflow_controller.py:336`). A
report has a single namespace, so there is nothing to confuse it with. That asymmetry is
deliberate and is pinned by
`tests/test_slice_id_validation.py::test_legacy_s_ids_normalise_to_canonical_space`.

## 2. No compatibility shim — and the three conditions that allowed it

The roadmap permits a zero-deprecation removal (delete the old form outright, no
warn-then-remove cycle) **only while three conditions hold**. All three were re-measured
at 2026-10-07 rather than taken on trust:

**(1) No live consumers of the old form.**
The authoring path — the glob the extractor is actually fed,
`worklogs/*/increments/increment-*.md` — contains **zero** documents using `## S<n>:` or
`### Step S<n>`. Verified by scan, not by assumption.

**(2) A small, mechanically-migratable archived corpus.**
Measured: **31** documents repo-wide still carry the old anchors. Feeding every one of
them to `extract_plan_ids` yields **0 documents with a non-empty `.slices`** — i.e. the
"accepted silent no-op" of E24 is real, not aspirational. Nothing silently half-parses.

⚠️ **Correction to the roadmap's wording.** The roadmap calls this corpus "archived". That
is imprecise: only **16** of the 31 sit under `worklogs/archive/`. The other **15** are
live-directory historical documents — `worklogs/implementation-plans/` (6),
`worklogs/reviews/` (4), `worklogs/pr-notes/` (2), `knowledge/research/` (2),
`worklogs/HANDOFF.md` (1). They are *inert*, not *archived*. The condition still holds,
because inertness is what it actually requires, but the next person to lean on the word
"archived" would be misled.

**(3) A migration note shipped for humans.**
This document. Condition (3) is closed by its existence.

If any of the three ever fails, the roadmap's standing rule applies: **the next removal is
warn-then-remove, not zero-deprecation.**

## 3. What you will see if you open an old plan

Old plans are **not** rewritten. Do not migrate them; they are history, and rewriting
history to satisfy a lint is exactly the theater this project rejects.

Two observable consequences, both expected:

- **Empty slices.** An old plan parses to `.slices == ()`. Measured across all 31 files.
- **Pre-check noise on one file.** Of the 32 documents in `worklogs/implementation-plans/`
  that the totality tests feed to the parser, exactly **one** emits pre-check failures:
  `PLAN-complexity-aware-execution-chat-role.md`, with **9 × `heading-near-miss`**. Its
  headings are `## S<n>: …`, which is precisely the shape CT26 exists to catch. This is the
  lint working, on a document that predates the grammar. It is **not** a regression, and it
  must not be "fixed" by editing the historical plan.

No gate currently pre-checks that directory, so nothing is red today. If a future increment
starts pre-checking historical plans, it must exclude them explicitly and say why — not
silence the rule.

## 4. Authoring a new plan

Use the skeleton in
[`knowledge/skills/plan-authoring/SKILL.md`](../../../knowledge/skills/plan-authoring/SKILL.md)
(the `PLAN-SKELETON` block). The grammar it emits is specified in
[`artifact-schema-and-grammar.md`](artifact-schema-and-grammar.md) §4, and the pre-check
rules that police it are listed in that file's rule inventory.
