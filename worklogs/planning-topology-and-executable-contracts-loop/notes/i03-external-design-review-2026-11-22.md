# I03 external design review — what the evidence model is for, and what SLICE3 should build first

**Date:** 2026-11-22<br>
**Scope:** `plan_v2.py` evidence matrix, `plan_admission.bind_dispositions`, `acceptance_bundle.mint_seal`,
`workflow_controller` create-new route, `project_scaffold`, `slice_verification`, `admission_schema`,
`prompt.AUTHORING_SYSTEM_PROMPT`, `notes/artifact-schema-and-grammar.md`.<br>
**Status:** read-only source audit + design review. **No production change.** The only additions are this note
and ledger E602.<br>
**Inputs:** plan [`i03-ai-native-workflow-refactor-plan-v2.md`](i03-ai-native-workflow-refactor-plan-v2.md),
audit [`evidence-model-audit-2026-11-21.md`](evidence-model-audit-2026-11-21.md), ledger E600/E601.<br>

Every factual claim below was reproduced against the working tree (commands and file:line given). Where I disagree
with E600/E601 I say so explicitly and give the measurement that moved me.

---

## 0. What this system is for — and which of its values are load-bearing

Read from the code rather than the prose, the system makes exactly one promise:

> **An artifact produced by a model is checked by something other than the model that produced it, and the check
> cannot be talked around — not by the plan, not by the author, not by "it finished".**

Everything else in the tree is an entailment of that promise, and each mechanism earns its place by removing a
specific way the promise could be faked:

| Value | Mechanism | Where |
|---|---|---|
| the author of a claim is not the author of the proof | separate planner/coder/verifier stages, separate capabilities | `PlannerDispatchKind`, `profiles.build_registry_for_role` |
| a claim either maps to an executable check or is refused | `INV → CT → TEST-ID → selector → one nodeid` | `plan_v2._admit`, `resolve_selectors` |
| the thing that ran is the thing that was reviewed | seal over plan bytes + revision + closure digest + exact nodeids | `acceptance_bundle.mint_seal` |
| the author cannot edit what must pass | `MUTATION` view confined to `{"src","scripts"}` | `workspace._MUTATION_ROOTS` |
| the proof is produced outside the author's control | managed no-network / read-only-rootfs cell | `profiles.py`, `slice_verification` |
| "finished" ≠ "succeeded" | `ToolResult.fail` on child exit 0 + non-`DONE` | `workflow_tool` (CT-2.5) |
| human authority is only for what physics puts out of reach | closed `DISPOSITION_REASONS` (host readiness, deployment identity, owner approval, durability/power loss), grant by caller, ≤30 days | `plan_v2`, `plan_admission.bind_dispositions` |
| uncertainty is a named state, not a retry | `DURABILITY_UNKNOWN`, no blind retry | `workspace` publish saga |
| refusals are data | closed rule vocabularies per surface; repair consumes diagnostics | `admission_schema`, `workflow_controller` |

Two of these are unusual and, in my judgement, are the actual product: the **seal** (bytes-with-revision identity)
and the **disposition pipeline** (a waiver that a model cannot mint for itself, restricted to reasons that are
outside the sandbox by nature rather than by convenience). Design decisions around them should be defended harder
than anything else in the tree; the rest — V1 legacy, the I03 parent plan, the tick machinery, the review layer —
is scaffolding.

I read three further values in how the work itself is done, and they are the project's real methodology:

1. **Claims are verified, not asserted** — "measured, not read", mutants killed, exit codes retained.
2. **A defect is a named row that can be closed**, not a paragraph that can be re-worded.
3. **One mechanism, no parallel path** — the plan applies this to code repeatedly (no second parser, no second
   runner, no second seal, no V1 fallback).

Value 3 is where the current problem lives, and it is not a code problem. It is applied to *code* but not to
*contracts*: there are today three or four descriptions of the plan grammar, and the model that writes plans reads
the wrong one (§4).

---

## 1. Measured state

Executed against this tree. "Route" means reachable from chat `invoke_workflow` → managed `run_workflow`.

| Thing | State | Evidence |
|---|---|---|
| V2 parser + admission rules | **implemented, 775 lines, on the route** | `plan_v2.parse_plan`; called once in production at `workflow_controller.py:3190` |
| Metadata cross-check, scaffold, planner-as-writer, one-revision create | **implemented** | `project_scaffold.py` (148), `_admit_published_project` `:3141`, `_run_create_new_repair` `:3081` |
| SLICE1 CT-1.1…1.5 tests | **5/5 present** | `tests/test_ai_native_plan_v2.py` |
| SLICE2 CT-2.1/2.2/2.3/2.5/2.6/2.7/2.8/2.9 tests | **8/8 present** | `test_ai_native_bootstrap.py`, `test_invoke_workflow_tool.py`, `test_prompt_registry_coherence.py` |
| CT-2.4 (seal before coder) and CT-3.1…3.6 | **absent** | 0 test hits; `grep -rn AcceptanceBundle src/fa/inner_loop/workflow_controller.py` → 0 |
| `mint_seal` | **library only** | single production caller `acceptance_defect.py:246` |
| `contract_evidence` / `UNCOVERED` | **no consumer** | only `acceptance_bundle.attested_contracts` at mint time; `UNCOVERED` read by nothing |
| `protected_paths` on the coder view | **plan file only** | `workspace.py:2194`, `:2814` pass `(plan_ref.workspace_relative_path,)`; acceptance root absent |
| planner `verify` fence on the V2 route | **still executed** | `slice_verification.py:552` |
| canonical schema vs parser | **divergent** | `artifact-schema-and-grammar.md`: `AI-NATIVE-PLAN-V2` ×0, `KIND:` ×0, `CT-` ×0, `TESTS:` ×10 |
| real V2 project documents in the repo | **zero** | `grep -rl AI-NATIVE-PLAN-V2 worklogs/` → only plan/ledger/notes, no `worklogs/<slug>/increments/*` |
| authored-repair budget | **1** | `replans_allowed = DEFAULT_MAX_REPLANS = 1` (`workflow_controller.py:157`, `:2950`) |
| repair write surface | **increment + open-questions only** | `_REPAIR_WRITABLE_SUFFIXES` `:3044` |
| `plan-v2` diagnostic namespace | **not in the closed table** | `admission_schema.ADMISSION_RULES_V2` has no `"plan-v2"` key; `"plan-v2"` × 0 |
| diagnostic `contract_id` shape | **V1 only** | `re.fullmatch(r"CT\d+[a-z]?", …)` `:169` — a V2 `CT-1.1` is unrepresentable |

Scale, for context on where the effort is going: `src` 88 747 lines, `tests` 152 181 lines (5 531 tests),
`worklogs/**/*.md` **141 555 lines**, ledger 317 entries. Documentation mass is now larger than the source it
describes. That is a signal about the process, not about the code (§7).

**One consequence worth stating plainly:** because there is not a single V2 plan in existence outside test fixtures,
**every vocabulary change recommended below has zero compatibility cost today.** This is the cheapest moment in the
whole programme to fix the grammar, and the price only rises from here.

---

## 2. Q-V2-ACC-2, re-derived

The question as filed — *"where do we refuse a plan that declared `TEST_REQUIRED` and covered nothing: at parse or
at seal?"* — cannot be answered as asked, because it assumes a two-gate architecture that this route does not have.
Three corrections, each measured.

### 2.1 There is one gate, and its refusal is the repair trigger

On the create-new route the order is:

```
authoring stage → STOP_VIEW/SEAL/PUBLISH (one revision)
  → _admit_published_project                      workflow_controller.py:3141
      → check_project_metadata → snapshot_from_bytes(... format=PLAN_V2)   :3168, :3190
          → parse_plan → _admit(graph)            plan_v2.py:648
      → bind_dispositions (caller grants)                                :3212
  → on any PlanRefError: _bind_authored_project → _may_repair_authored_project → _run_create_new_repair
                                                                          :2963–2988
```

Parsing happens **inside admission**, admission is **the** pre-coder gate, and its refusal is **the** input to the
one authored-repair stage. E600 argued that refusing at parse "lands before the repair begins, burns the budget, and
kills the repair loop". That is not what the code does: a parse refusal returns
`PlanRefError("bootstrap-invalid-metadata")` (`:3202`), which is repairable (`_may_repair_authored_project` only
excludes collision/unavailable/route-mismatch/failed-repair, `:2946–2951`). Option B feeds the repair loop; it does
not bypass it.

So the real choice is not *parse vs seal*. It is **one admission predicate** versus **two predicates to keep in
step** — and the second is exactly the "parallel mechanism" the plan forbids everywhere else.

### 2.2 `HARD + NON_EXECUTABLE` is not a bug — it is the disposition pipeline's primary case

E601 calls it "a `HARD` invariant can be waived, which the plan forbids verbatim". Three measurements say
otherwise:

1. The sentence being quoted ends differently: *"`NON_EXECUTABLE` is forbidden for HARD/ready contracts **unless
   Q-V2-ACC-2 is resolved under a ratified rule**"* (plan §2), and the ACC-2 row itself offers, as option B,
   *"permit only a typed `NON_EXECUTABLE` disposition with reason and authoritative evidence under an
   already-ratified disposition rule"*. The typed-reason + caller-grant + 30-day pipeline is that rule.
2. The plan cannot see this. The whole point of a disposition is a claim that is **critical and unobservable**. "The
   release is registered under the owner's domain", "the host is approved", "the record survives power loss" are all
   `HARD`; if `HARD` refused dispositions, dispositions would exist only for claims nobody cares about, and the
   mechanism would be dead weight. `DISPOSITION_REASONS` is a list of *physics and institutions*, not of severities.
3. The author does not choose it. `bind_dispositions` (`plan_admission.py:171`) refuses `disposition-undeclared`, and
   is the sole source of `owner` and `evidence_ref`; `contract_evidence` grades `ATTESTED` only when `owner is not
   None` (`plan_v2.py:753–757`). A plan can *request*; only a caller can *grant*.

**Therefore:** E601's proposed (A) "refuse `HARD + NON_EXECUTABLE`" is not a bug fix — it is a regression against the
feature's purpose. Do not implement it. (The narrower defect E601 measured is real but different: nothing *forces*
a requesting plan to have a grant before admission on the create-new route — see §3.2, which is where that
belongs.)

### 2.3 `SOFT` is not a policy, it is a hole — and the test that defends it asserts an unverified property

Reproduced by executing the module directly (no pytest needed; `plan_v2` is stdlib-only):

```
CT-1.2 HARD + TEST_REQUIRED, no test, no disposition  -> REFUSED  hard-contract-without-executable-evidence
CT-1.2 SOFT + TEST_REQUIRED, no test, no disposition  -> ADMITTED {'CT-1.2': UNCOVERED}
CT-1.2 HARD + NON_EXECUTABLE(reason), no grant        -> ADMITTED {'CT-1.2': UNCOVERED}
CT-1.2 SOFT + NON_EXECUTABLE(reason), no grant        -> ADMITTED {'CT-1.2': UNCOVERED}
```

The third and fourth rows are admissible **because admission has not yet bound a grant**; after
`bind_dispositions` they become `ATTESTED`, and without one `_granted_dispositions` refuses the run
(`disposition-undeclared`). That part is coherent.

The second row is not. The document says "this must be checked by a test"; the parser accepts that no test exists;
`contract_evidence` marks it `UNCOVERED`; nothing reads `UNCOVERED`; the seal cannot even represent it. The
defending test is titled `test_a_soft_invariant_may_still_stay_uncovered`
(`tests/test_ai_native_plan_v2.py:819`) and its docstring claims the gap is *"legal — and visible"*. **The
"visible" half is false**: there is no reader. A test that asserts a property no code implements is the exact
defect class this project exists to catch — it is a `GUESS` wearing a `FACT`'s clothes.

### 2.4 `"ready CT"` — strike the phrase

`grep -rni "ready ct\|ready_contract\|contract_ready" src/fa/` → 0. Contract lifecycle (`PLANNED/IMPLEMENTED/VERIFIED`)
belongs to SLICE4 and does not exist. On the V2 route every admitted contract is in force from the moment of
admission, so "ready" was an attempt to say "every contract", and it should be spelled that way.

### 2.5 The rule, stated once

A plan is admissible iff **every contract is discharged by exactly one of two modes, and the mode is total**:

| `EVIDENCE` on the contract's invariant | required | refused |
|---|---|---|
| `TEST_REQUIRED` | ≥1 acceptance row resolving to exactly one nodeid in the sealed closure | no row, no nodeid, ambiguous nodeid — **regardless of `KIND`** |
| `NON_EXECUTABLE` (+ typed reason) | a caller grant bound at admission (owner + typed evidence ref + ≤30 d) | missing grant, unratified reason, reason reused, >1 contract per grant, `PRESERVATION` class |

`PRESERVATION` stays non-dispositionable (`plan_v2.py:617`) — that check is correct and should be *stated as a rule*
rather than living as an ordering accident.

Implementation is one branch: delete `if invariant.kind != "HARD": continue` (`plan_v2.py:622`) and let the existing
`hard-contract-without-executable-evidence` rule fire for every uncovered contract whose invariant requests a test.
Two tests get rewritten (`:720`, `:819`) — they encode the hole, and their replacement asserts the property that
actually holds.

### 2.6 Behaviour on a real task, side by side

Task: *"сделай сервис экспорта отчётов"*; the planner writes `INV: export works offline`, `EVIDENCE: TEST_REQUIRED`,
`CT-1.2`, and no acceptance row.

| | A — today | B — refuse at admission (recommended) | C — refuse at seal | E601 (A′): also refuse `HARD+NON_EXECUTABLE` |
|---|---|---|---|---|
| plan admitted | yes | no | yes | as B for the soft case |
| repair stage runs | — | **yes**, one shot, narrowed allowlist | no (no refusal yet) | irrelevant |
| planner learns | nothing | the parser's rule name (once §3.1 is fixed) | nothing at refusal time | — |
| coder dispatched | yes | no | yes — until the seal is wired | no |
| what the run produces | a project whose own plan says a test is required and has none; seal (when wired) is shape-identical to a fully-covered one | a second revision that either adds the test or converts the claim to a request-for-grant; or `BLOCKED`, project present and honestly unadmitted | a second gate whose refusal has no repair path on this route; two predicates, two vocabularies | dispositions become unusable for exactly the claims they exist for |
| cost | 0 | 1 line + 2 test rewrites + the two §3 fixes | ~50 lines of wiring that must stay in step forever | — |
| verdict | hole | **correct** | correct-in-principle, worse-in-practice | regression |

**Answer to the operator question:** no — a plan that says "must be tested" and ships no test must not reach a
coder, and it must not need a waiver either. It must go back to the planner with a rule name it can act on, or end
`BLOCKED` with the project present and inspectable. The waiver path is for claims physics puts out of reach, not for
tests the planner did not get around to writing.

---

## 3. Two holes the parse/seal question hides — both bigger than the question

### 3.1 The repair loop is lossy, and the fix it may need is outside its allowlist

Two measured facts combine badly:

* the repair stage is told **one** sanitized string, and on the create-new route every grammar refusal collapses to
  `bootstrap-invalid-metadata` (`:3202` → `_authored_diagnostics` `:2953`). The parser knows the precise rule
  (`slice-1-exit-check-entry`, `acceptance-selector-invalid`, `hard-contract-without-executable-evidence`, …); the
  model is told "invalid metadata". E590 recorded the first two prompt drafts failing on exactly those two rules —
  a real model produces them.
* the repair may write only `increments/increment-01-initial-plan.md` and `open-questions.md` (`:3044`). The natural
  fix for an uncovered `TEST_REQUIRED` contract is **to write the test**, which lives in
  `acceptance/tests/` — outside the allowlist. The reachable fixes are "delete the contract" or "re-describe it as a
  grant request", i.e. exactly the two behaviours that make a model optimize the claim away rather than escalate.

With one repair in the budget, these two facts mean the loop will usually fail on the class of refusal that the
whole V2 effort is about. Both fixes are small and bounded: carry the parser's closed rule as the diagnostic rule
(the vocabulary must therefore contain grammar rules — §4), and add `acceptance/tests/` to the repair allowlist
(planner-owned bytes, sealed afterwards, coder still cannot touch them).

### 3.2 A grant request has no upward path

`ctx.dispositions` comes from the caller at invocation time. If a plan truthfully needs an out-of-sandbox
attestation and the caller did not pre-declare one, the run gets `disposition-undeclared`, spends its single repair
attempt, and the model will almost certainly remove or weaken the claim. That is the worst possible outcome for the
product: the honest plan is punished, the dishonest one is admitted.

The disposition pipeline needs a **third outcome besides "granted" and "refused": `needs_grant(reason)` as a
structured terminal result**, distinct from `workflow_failed` and retryable by re-invoking with `--dispositions` /
the tool field. The chat caller can then show the operator one line ("this plan needs OWNER_APPROVAL: <what>"),
and the operator decides. That is the human gate the design intends — reached as a *result*, not as a repair
attempt by the author.

Related: CT-1.5's documented gap (no `--dispositions` on the CLI) is not a test gap but the same capability gap from
the human side; it becomes blocking the moment §3.2 exists.

---

## 4. The canonical schema: not a rewrite, a conformance gate

The measured divergence is real (schema teaches V1 `TESTS:` + `verify`, parser requires V2 `CONTRACTS/ACCEPTANCE/…`),
and it is the root cause of every unanswerable evidence question — the document that defines invariants never
mentions `KIND`. E601's step (C) is right that this must be fixed, but "rewrite the authoritative document" is the
wrong shape of fix, because it will drift again. There are four surfaces of the same grammar:

| Surface | Who reads it | Enforced by |
|---|---|---|
| `plan_v2.py` (parser + `_admit`) | the machine | itself |
| `notes/artifact-schema-and-grammar.md` | two skills, four conformance tests, humans | nothing |
| `prompt.AUTHORING_SYSTEM_PROMPT` (`:1225`) | **the model that writes plans** | nothing |
| plan §2 "grammar delta" | reviewers | nothing |

Fix the *relationship*, not the text: one machine-readable grammar table (sections, fields, cardinalities, and the
closed rule vocabulary), from which (a) the parser's rules are drawn, (b) the document's grammar block is checked,
(c) the prompt's worked example is **parsed by the real parser in a test** (CT-2.6 already does this), and (d) the
skills' conformance test reads the same table. Then "two descriptions of the grammar" becomes a build failure rather
than an audit finding.

This is not speculative: the repository already does exactly this for the *admission record* vocabulary
(`ADMISSION_RULES`/`ADMISSION_RULES_V2`, closed tables, schema tests). Extending that pattern to the grammar closes
the root cause. Two live defects prove the gap is not academic:

* `_validate_v2_admission` emits diagnostics under validator `"plan-v2"` (`:3481`, `:3490`) — a namespace that
  `ADMISSION_RULES_V2` does not contain, so a loaded record would be **rejected as corrupt**
  (`_record_diagnostics` → `_record_enum(validator, frozenset(rules))`). Latent today, one refactor from live.
* the record's `contract_id` regex is `CT\d+[a-z]?` (`admission_schema.py:169`), while V2 ids are `CT-1.1`
  (`plan_v2.is_contract_id`). A V2 diagnostic carrying a contract id cannot be persisted.

Also worth correcting while the prompt is being brought into line: it currently states a rule the parser does not
enforce ("a `FUNCTIONAL`/`CONSTRAINT` contract with `INV` pointing at a `TEST_REQUIRED` invariant must have an
acceptance row") and a promise nothing keeps ("a false `TEST_REQUIRED` is a lie the verifier will catch later",
`prompt.py:1260–1263`, `:1319`). After §2.5 the first becomes true; the second should be deleted, or made true by
§2.5 and the seal.

---

## 5. The vocabulary: `KIND` needs a consumer or a funeral

`invariant.kind` is read in exactly one place (`plan_v2.py:622`) and only to exempt. A field whose only consumer
removes an obligation is, for a model author, an attractor: the model is trained to produce *admissible* documents,
so the cheapest admissible document is the one that uses the exemption. That is not a severity knob that is being
misused; it is a free pass.

Two honest options:

* **Delete `KIND`.** The grammar then has one evidence field with two total modes (§2.5). Smallest vocabulary that
  is fully enforced. Costs a schema/prompt/parser change, which today costs nothing (§1).
* **Keep it, but make it a second, consumed axis.** `SEVERITY: BLOCKING | ADVISORY`, consumed by verdict grading
  (a `SOFT`/advisory contract failing produces a warning and does not block `SHIPPED`) and by status promotion.
  That is a real product decision for SLICE4 and it is fine — as long as `SEVERITY` never touches *proof mode*.

What is not fine is the current state: one field doing both jobs, with the severity half unread and the exemption
half live. **Doctrine to adopt, in the project's own idiom:** *no field enters the grammar without a named consumer
and a test that fails when the consumer is removed.* This is the producer kill-check applied to the grammar itself.

---

## 6. Order inside SLICE3 — riskiest unknown first, not contract order

The plan's CT order is a *dependency* order. The value order is different: two facts gate everything else, and one
of them is a measurement nobody has taken.

**STEP 0 — the C1 probe (do this before any seal code).**
The whole design assumes the managed runner can collect and execute a project test at
`worklogs/<slug>/acceptance/tests/<file>.py::<node>` and resolve it to exactly one nodeid
(`slice_verification.capture_test_nodeids`, plan §2). That has never been measured on a fresh project. Write one
test that proves collection, one nodeid, and an ambiguous-selector refusal. If it fails, the plan's own instruction
applies: fail closed and replan — everything in SLICE3 is downstream of this.

**STEP 1 — totality + a repair that can actually repair.** §2.5, plus §3.1's two fixes, plus §3.2's
`needs_grant`. Exit: three tests — uncovered `TEST_REQUIRED` refused pre-coder; the repair writes the missing test
and the second revision admits; the diagnostic the repair stage receives is the parser's own rule name.
This is CT-3.1, and it is ~80 % already implemented: `_admit_contracts`, `_admit_acceptance`, `_admit_scenarios`,
`_admit_kill_targets`, `_admit_steps` already enforce the graph cardinalities.

**STEP 2 — mint the seal on the route.** `_admit_published_project`: collect → `resolve_selectors` → `mint_seal`
from the **bound** graph and the published revision → persist per-seal + atomic pointer (D-V2-5) → admission
refuses a missing/stale seal. Add to the seal: `contracts_total`, `uncovered` (empty by construction), `attested`.
`mint_seal` refuses `UNCOVERED` and refuses an unbound `NON_EXECUTABLE` invariant — as a *serialization invariant*,
not a second policy. Exit: CT-2.4 + CT-3.2, and a seal that is auditable without the graph.

**STEP 3 — mode A.** `protected_paths` ← every sealed semantic path (`workspace.py:2194`, `:2814`), not just the
plan file. Exit: CT-3.3 both halves (file-tool refusal; shell drift detected before any verdict).

**STEP 4 — the verifier runs the seal.** `sealed_collection_argv` on the V2 route; retire the planner `verify` fence
there (`slice_verification.py:552`); closure-digest check before any verdict. Exit: CT-3.6.

**STEP 5 — attribution and TEST-DEFECT** to the existing `kill_attribution` / `acceptance_defect` mechanisms
(CT-3.4/3.5). No new state machine.

**STEP 6 — schema + prompt conformance**, last, because the prompt can only be written truthfully once 0–5 exist
(the P0-1 lesson). §4 in one change.

Do not start with "the graph" as a new parser feature (it is largely there), and do not start with seal wiring
before STEP 0 — a seal built on an unproven collection path would be a second, more expensive audit.

---

## 7. Process observations (offered as an equal, not a junior)

1. **The review layer has outgrown the product.** 141 k lines of worklog against 89 k of source; E600–E601 plus
   four audits in three days. The audits are excellent — E600's refusal to widen admission semantics by inference is
   exactly right — but the ratio says the bottleneck has moved from "unknowns" to "decision latency". A decision that
   is measured twice and written three times is not safer than one that is measured once and ratified.
2. **The plan is three documents in one.** It carries (a) ratified decisions, (b) status, (c) the specification, and
   they contradict each other: §8 step 4 says "Q-V2-ACC-1/2 are closed" while the ACC-2 row says BLOCKING; the header
   says "PLAN ONLY, no implementation" while eight of its own contracts are implemented. That is not carelessness;
   it is what happens when one file is both a decision record and a status board. Split them: decisions immutable and
   dated; state generated or checked; spec machine-verified (§4).
3. **"Present tense" discipline cuts both ways.** The plan learned not to describe targets as existing (P0-1). The
   mirror rule is missing: a *status* claim must cite evidence or be absent. "Closed" without a citation is how the
   §8/Q contradiction appeared.
4. **The cheapest next measurement is a real run, not another audit.** There is no host witness and no live
   create-new run; the model-authored plan path has been exercised only by fixtures and by the prompt example. One
   local managed run with a real provider will teach more about the repair loop, the prompt drift and the diagnostic
   quality than several more static reviews — and the whole product claim (INV-12) is about exactly that path.
5. **Do not reopen D-V2-9.** Planner-as-writer removes an orthogonal serialization, deletes ~3 600 lines of
   renderer, and is implemented and tested. The fact that it moved the failure from "renderer refuses" to "admission
   refuses" is the intended trade, and it is the better one.

---

## 8. Proposed resolutions to ratify (ready to paste)

**Q-V2-ACC-2 — RESOLVED.** Evidence is total: every contract is discharged either by a selector resolving to exactly
one nodeid in the sealed closure, or by a caller-granted typed disposition. `KIND` is not an exemption; `"ready CT"`
is struck from the grammar (no runtime meaning). Two consequences: (a) `kind != "HARD"` no longer exempts a contract
from evidence, so `SOFT + TEST_REQUIRED` with no selector and no grant is refused at admission with
`hard-contract-without-executable-evidence` (rule name to be renamed `contract-without-executable-evidence`), and the
two tests encoding the hole are replaced; (b) `HARD + NON_EXECUTABLE` remains legal **only** with a bound caller
grant — the disposition pipeline is the ratified rule this row asked for, and refusing it for `HARD` would make the
mechanism unusable for the claims it exists for. Admission is the single gate; the seal re-checks coverage as a
serialization invariant and records `contracts_total`/`attested`/`uncovered`, never re-decides policy.

**§2 grammar delta.** Delete "`NON_EXECUTABLE` is forbidden for HARD/ready contracts unless…"; replace with:
"every contract has exactly one discharge mode; `TEST_REQUIRED` requires a resolving selector, `NON_EXECUTABLE`
requires a bound caller grant; `PRESERVATION` is never dispositionable."

**§8 step 4.** Replace "Q-V2-ACC-1/2 are closed" with: "Q-V2-ACC-1 is closed by code (budgets, 30 tests); its
transitive half is a named residual. Q-V2-ACC-2 is resolved by D-V2-10 (evidence totality)."

**D-V2-10 — evidence totality** (new ratified decision): the rule in §2.5 plus (i) the parser's rule name is the
diagnostic the repair stage receives, (ii) the repair allowlist includes `acceptance/tests/`, (iii) `needs_grant` is a
structured, retryable terminal outcome that lets the operator supply a disposition and re-invoke.

**D-V2-11 — grammar conformance** (new): one machine-readable grammar table is the source for parser rules, the
canonical document's grammar block, the skills' conformance test and the prompt example; `ADMISSION_RULES_V2` gains
the `plan-v2` namespace and V2-shaped contract ids.

**Q-V2-ACC-1 — CLOSED-BY-CODE + residual.** Agreed with E601: budgets are implemented and strict; the transitive
import closure is not provable in this design (a sealed test may import outside `acceptance/`, and the MUTATION route
imports the candidate by design). Record it as a named residual with the reason, not as an open gate.

---

## 9. What I would do on Monday

1. Ratify D-V2-10/D-V2-11 and the four one-paragraph plan edits above (30 minutes, no code).
2. Land STEP 0 as a throwaway probe (~1 hour) — the only unknown that can invalidate SLICE3.
3. Land STEP 1 + STEP 2 (evidence totality, repair fixes, seal wiring) behind the existing tests; run the suites.
4. Then do one real create-new run end-to-end and read what the model actually did, instead of auditing what it
   should do. Everything else — mode A, verifier, attribution, ticks — has a known shape and can wait for that
   measurement.
