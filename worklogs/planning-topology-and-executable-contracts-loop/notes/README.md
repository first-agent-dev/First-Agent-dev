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
| [`role-prompts-conformance.md`](role-prompts-conformance.md) | Exact prompt text to insert, banked by owner: planner→I01, coder→I03, eval→I04. |
| [`RESEARCH-ADOPTION-PLAN.md`](RESEARCH-ADOPTION-PLAN.md) | Which of the 18 research items are adopted vs deferred. §5 "more structure is not more success". |

## Record (what happened)

| File | What it records |
| --- | --- |
| [`decisions-qa-2026-10-06.md`](decisions-qa-2026-10-06.md) | The Q→A walk: 39 decided questions, Q0–Q39, with verdicts. |
| [`open-questions-2026-10-07.md`](open-questions-2026-10-07.md) | **Currently open questions.** Q40–Q42 (resolved, kept as record), **Q43 open**. |
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
