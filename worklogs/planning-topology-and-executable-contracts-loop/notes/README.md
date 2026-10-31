# `notes/` — index

Where to look, and why each file exists. The folder has two kinds of document and mixing
them up is the main source of confusion:

- **Normative** — the rules code and plans must obey. Editing these changes the project.
- **Record** — what was measured, decided or asked on a given day. Append, don't rewrite.

Read `../roadmap.md` first, then `../increments/`, then come here for detail.

---

## Normative (the rules)

| File | What it is |
| --- | --- |
| [`artifact-schema-and-grammar.md`](artifact-schema-and-grammar.md) | **The canonical grammar.** §1 artifacts + ownership table, §4 slice grammar + its executable oracle, §5 ledger grammar, §6 status vocabularies, **§7 the extractor surface I01 exposes**. |
| [`verify-block-design.md`](verify-block-design.md) + `.svg` | I02's gate design: the four-phase ritual and the seven-row truth table. |
| [`i02-handoff-verify-gate.md`](i02-handoff-verify-gate.md) | I02's context bank: grounded facts, the contract boundary, open questions **H1–H7**, what must not leak, §7 the live gate I02 owes, §8 CT10b. |
| [`role-prompts-conformance.md`](role-prompts-conformance.md) | Exact prompt text to insert: planner→I01, coder/L2→actual deferred slice-loop/tracker/eval successor, eval-ledger→I04; foundation I03 does not satisfy those consumers. |
| [`RESEARCH-ADOPTION-PLAN.md`](RESEARCH-ADOPTION-PLAN.md) | Which of the 18 research items are adopted vs deferred. §5 "more structure is not more success". |

## Record (what happened)

| File | What it records |
| --- | --- |
| [`decisions-qa-2026-10-06.md`](decisions-qa-2026-10-06.md) | The Q→A walk: 39 decided questions, Q0–Q39, with verdicts. |
| [`open-questions-2026-10-07.md`](open-questions-2026-10-07.md) | **Currently open questions.** Q40–Q42 (resolved, kept as record), **Q43 open**; E201 aligns retained I02 vs I03 readiness owners and Q66 initial/log/retry rules without ratifying exact pending choices. |
| [`q59-q66-reader-review-2026-10-14.md`](q59-q66-reader-review-2026-10-14.md) | Plain-language decision guide for Q59–Q63 and Q66's remaining propagation proof; examples, code references, production options, and operator reply template. Recommendations are not ratified decisions. |
| [`planning-model-retro-2026-10-30.md`](planning-model-retro-2026-10-30.md) | **Record:** why I03 produced god-objects (contracts named symbols; 19/20 kill directives bound to `file::Symbol`), and the adopted hybrid model — invariants horizontal (≤7), behaviour vertical by observable slice. Includes verified counts, budgets, the test-as-acceptance migration, and the open gaps. Precedent to D1–D3; not normative until promoted to `AGENTS.md`/ADR. |
| [`Q89-decision-memo-2026-10-30.md`](Q89-decision-memo-2026-10-30.md) | **Record:** verification of the seven Q89 objections against `8b1cc95` (five confirmed, one withdrawn — `_mutex` is `RLock`), plus the Q89 option-1 ruling draft with refinements R1–R6 and the implementation order. |
| [`Q90-defect-group-closure-2026-10-31.md`](Q90-defect-group-closure-2026-10-31.md) | **Record:** 20 defect positions behind Q90 (15 confirmed, 2 found beyond it, 1 mis-posed, 2 retracted), grouped by class; adds §10 why I03 ended as components without a composition (contracts name bodies, the work frontier was always internal, every seam had a double — and E288 deleted the only working plan writer, −138/+17), §11 the critical-bug list for the operator's two scenarios (`fa run chat`→`invoke_workflow` and `fa workflow`), §12 the one rule + two mutants that would have caught it, and §13 why `publish_plan_buffer` was deleted (recorded: "a retained fallback is a second writer by another name") and why restoring it would corrupt the supervisor's revision model — the restoration is the *supplier*, not the writer; §14 the plan review of the new I03 SLICE7 (trajectory, code grounding, executability, correctness, high-ROI fixes) and §15 the SLICE5↔SLICE7 coexistence audit that re-ordered the slices (I03 runs 1→2→3→7→4→5→6) and closed Q91 inside STEP8. |
| [`execution-workspace-and-i02-i03-scope-decisions-2026-10-15.md`](execution-workspace-and-i02-i03-scope-decisions-2026-10-15.md) | Latest operator directions and adopted design for execution isolation, exclusive workspace ownership, simple logged planner context, kill-error classification, and I02→I03 scope migration. Context for rewriting I02/SLICE6 and planning I03; distinguishes decisions from pending implementation/proof. See E197–E198 directions, E199 lifecycle correction and E200–E201 applied plan/owner migration (no implementation claim). |
| [`execution-foundation-scope-reduction-and-reuse-audit-2026-10-15.md`](execution-foundation-scope-reduction-and-reuse-audit-2026-10-15.md) | Separate source-grounded scope-reduction check: direct reuse, seams requiring strengthening, genuinely new mechanisms, deferrals, compact grouping proposal and bounded diagnostic evidence. Recommendations are not ratification or delivery. See ledger E199. |
| [`i02-to-i03-scope-migration-2026-10-15.md`](i02-to-i03-scope-migration-2026-10-15.md) | E200 clause/STEP/GAP ownership map for reduced I02 and foundation I03; retained shared CT92 schema, exact historical SLICE7/DoD bank, and no lost live-producer obligations. Transfer is not delivery. |
| [`findings-register-2026-10-06.md`](findings-register-2026-10-06.md) | All 55 findings from the reading pass, groups A–H, with stable ids. |
| [`adversarial-review-2026-10-06.md`](adversarial-review-2026-10-06.md) | The adversarial pass and its five suspicions, all closed by SLICE3b. |
| [`deferred-verification-register.md`](deferred-verification-register.md) | **D1–D8: every promise not yet proven live**, with the increment that owns each and the kill-check its test must satisfy. |
| [`i01-dod-walk-2026-10-07.md`](i01-dod-walk-2026-10-07.md) | I01's Definition-of-Done walk: evidence per line, 8/9 passing, the one that failed and its fix. |
| [`i02-planning-readiness-2026-10-07.md`](i02-planning-readiness-2026-10-07.md) | What I02 needs before it can be planned, and what is already banked. |
| [`migration-s-to-slice.md`](migration-s-to-slice.md) | Human migration note for the `S#` → `SLICE#` / `STEP#` rename. |
| [`state-of-play-2026-10-06.md`](state-of-play-2026-10-06.md) | Project summary + document map as of the reading pass. |
| [`operator-note-2026-10-06.md`](operator-note-2026-10-06.md) | Operator note for the 2026-10-06 session. |
| `ARCHITECTURE-REVIEW.md`, `REVIEW-planning-big-tasks-for-ai-agents.md`, `production-patterns-review-2026-10-06.md`, `first-agent-bridge.md` | Inputs from earlier review sessions; evidence, not rules. |

---

## Where a given kind of change lands

| If you want to know… | Look at |
| --- | --- |
| what the grammar *is* | `artifact-schema-and-grammar.md` |
| what the parser *exposes* | same file, **§7** |
| why a decision was taken | `../ledger.md` — search the `E#` quoted in the plan or commit |
| what is still undecided | `open-questions-2026-10-07.md` |
| what is built but unproven | `deferred-verification-register.md` |
| what a slice must do | `../increments/increment-01-…md` |

**The ledger `../ledger.md` is the spine.** Every note above is a convenience view; the
ledger is append-only, numbered `E1…`, and every commit message cites the `E#` it added.
If a note and the ledger disagree, the ledger wins.
