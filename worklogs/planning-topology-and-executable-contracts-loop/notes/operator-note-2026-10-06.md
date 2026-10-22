# Operator note — plan-edit session 2026-10-06

Deliverable per `first-agent-bridge.md` §7: what changed, what was banked, what still needs a
decision. Rationale for every item: `notes/decisions-qa-2026-10-06.md` (Q0–Q30, all closed).
Evidence: `notes/findings-register-2026-10-06.md` (72 findings, groups A–H, P, S).

## What happened

Four input documents (two reviews, the bridge brief, a parallel agent's production-patterns
review) produced ~55 findings against a project whose governing principle is minimalism. I
catalogued all of them, added 17 more from the parallel agent and 5 from reading `src/`, then
walked them as 30 decisions. **Six of my own recommendations were overturned during the walk** —
four by you, two by my own re-analysis. Those are marked below, because they are the parts most
worth re-reading.

The output is deliberately small: **6 new contracts in I01, one new slice, one reordered
increment, 9 standing decisions, 21 ledger entries** — against roughly 40 explicitly banked
items.

## What changed in the plans

**`increments/increment-01-…md` — reordered and extended (4 slices → 6).**
The order now follows one principle you set during the walk (**SD-A**): *the prompt is primary;
the parser conforms to it.* So the authoring contract is written before the parser changes.

| Order | Slice | State |
|---|---|---|
| 1 | `SLICE1` | ✅ shipped `c0a8f429`; boxes ticked, `shipped:` in frontmatter, `status: IN PROGRESS` |
| 2 | **`SLICE1b`** new | the authoring contract: schema §4 + both skills + the planner prompt. CT21–CT24 |
| 3 | `SLICE2` | parser conforms: CT16 section boundary, CT17/CT18 contract declaration, CT19/CT20 accessors. `DEPS: SLICE1b` |
| 4 | `SLICE3` | pre-check: CT25 all-violations-at-once, CT26 near-miss lint, CT27 undeclared-contract WARN, drift corpus |
| 5 | `SLICE4` | reduced to end-to-end conformance + the human migration note |
| 6 | **`SLICE5`** new | pinned invariants re-injected every call. CT28–CT30. Independent, `DEPS: SLICE1` |

**`notes/artifact-schema-and-grammar.md`** — §4 gains four normative boundary rules and the
`## Grounding` block; §5 gains reflection-typing and the ledger→`Blackboard` projection; §6 gains
the interim tick rule and pass^k resettability; §7 gains a `consumer:` on every name.

**`roadmap.md`** — 9 standing decisions, 3 Deferred rows, the dead `PLANNING-TOPOLOGY-EXPLAINED.md`
reference repointed, and a pointer naming `decisions-qa-2026-10-06.md` as the *rationale-context
surface* (so no new rationale file was created, and plan bodies stay rationale-free).

**`ledger.md`** — E49–E69 appended, with `supersedes:` on the four stale entries.

**`notes/i02-handoff-verify-gate.md`** §6 and **`notes/role-prompts-conformance.md`** addendum —
the banks, merged into one each.

**Outside `worklogs/`:** the research note's eight citation errors corrected in place (your call),
and `knowledge/prompts/research-topic.md` gained the version-pinning rule that would have
prevented six of them.

## The three findings that changed the most

**1. A large part of what the reviews proposed already exists in `src/`.** `BlackboardEntry`
carries `content_hash`, `parent_id` lineage, `read_set`/`write_set`, `assumptions`,
`version_dependencies`; `detect_conflict` does full overlap detection plus assumption violation;
`TelemetryLogger` already elides secrets. **The planning loop touches none of it.** That made
redundant, before being built: a typed attempt record, a failure-signature canonicalisation spec,
hash-link provenance, the freshness stamp, stale-fact detection, and syntactic parallel-slice
safety. The gap is **integration, not design** — the same shape as the flat `.commands` field that
shipped with zero readers. Hence **SD-B**: no accessor ships without a named consumer and a wiring
step in that consumer's increment. (E60, E61, register §S.)

**2. The live blocker is not subtle.** `grep -c SLICE src/fa/inner_loop/prompt.py` → **0**. A
freshly authored plan parses to empty `.slices`, so the coverage gate silently no-ops. And the
runtime format has *no `SLICE#` tier at all* — its `S1.` items are step-sized — which is why a
runtime→increment compiler was rejected: it would have to invent the slice grouping, i.e. be a
shadow planner. ASK#-01 closes as **(b′)**. (E52, E53, E54.)

**3. The reliability "contradiction" I reported was my own misreading.** I read your 4–7 rule as a
sizing prior competing with the s^N arithmetic. It is a **complexity ceiling** — the opposite
operation, and the mathematically correct one, because hierarchy resets the exponent while finer
slicing inflates it. The whole SLO package I had proposed was withdrawn; what survives is one prose
sentence in SLICE1b and one ledger entry recording why.

## What needs a decision from you

1. **Nothing blocking.** All 30 questions are closed. The items below are flags, not blockers.
2. **`.commands` must be given a consumer or retired.** SD-B makes this explicit; it has had zero
   readers since it shipped and the new rule forbids that state continuing unnamed.
3. **Two deliberately-red doc gates** (`test_doc_links`,
   `test_historical_workspace_docs_have_top_level_superseded_banner`) may now fail differently —
   this session added three files under `notes/`. Per E19 I did not touch them. **Report only.**
4. **Verification could not be executed here.** The sandbox has Python 3.11; the project targets
   3.13 (`from typing import override` in `src/fa/inner_loop/loop.py:17`), so `pytest` cannot
   import the package. I dogfooded `plan_ids.py` standalone instead: extraction is **total over all
   15 planning documents**, and the rewritten increment parses to 6 slices with correct
   `steps_mode` and `test_paths`. **Run the real suite before trusting anything here.**
5. **The rewritten increment reproduces A3 and A4 on itself** — SLICE5 picks up `CT14`/`CT11` from
   the document tail, SLICE1 still picks up a `CONSTRAINT`-classed `CT3` from CT2's example. This
   is intentional: it is the evidence those contracts exist, and the first fixtures for the drift
   corpus in SLICE3/STEP6. It disappears when CT16–CT18 ship.

## Where I overruled myself

Worth knowing, because each one shrank the plan:

- **R5** — a distilled failure packet must be built *mechanically*, not by an LLM summariser, and
  "≤15 lines" is a magic number. A hallucinating summariser makes the coder repair a defect that
  never happened.
- **R7** — my auto-flip rider was over-engineering *and* contradicted the syntactic-first rule I
  endorse two questions later. Also, the coupling conflates scope with uncertainty.
- **Mutation testing** — you were right and my version was six mechanisms where two suffice. The
  only real objection to a gate is equivalent mutants, and the standard fix is an appeal, not a
  shadow phase.
- **Held-out tests** — I had them as a reasonable option. They are not: the eval reads *the same
  plan* and inherits the same misunderstanding.
- **D18/D20** — I proposed pre-checks for things only a runtime can know. A pre-check cannot run
  anything.
- **E25/E28b** — downgraded by my own SD-B rule (guidance for a field with no consumer).
