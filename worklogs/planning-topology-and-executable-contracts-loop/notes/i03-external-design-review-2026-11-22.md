# I03 evidence model — decision document (external design review, v2)

**Date:** 2026-11-22 (supersedes the same-day v1 draft of this file, after adversarial self-review; corrections listed in §11)<br>
**Status:** read-only audit + recommendation. **No production code changed.** Ledger entries: E602 (v1 findings), E603 (self-review corrections).<br>
**Audience:** the operator ratifying Q-V2-ACC-2 and the SLICE3 order.<br>
**Authority:** [`i03-ai-native-workflow-refactor-plan-v2.md`](i03-ai-native-workflow-refactor-plan-v2.md), Q-V2-ACC-2, D-V2-5, D-V2-9; prior audits [evidence-model-audit-2026-11-21.md](evidence-model-audit-2026-11-21.md), E600, E601.

### Evidence classes used throughout

| Tag | Meaning |
|---|---|
| **[M]** | measured by executing the production code in this review (command in Appendix A) |
| **[R]** | read from source, file:line cited |
| **[A]** | argument / engineering judgement, explicitly not a measurement |

**Not verified here:** the full pytest suite was **not** executed (the review sandbox had no Python 3.13 and `uv sync` could not reach the interpreter download — §11.4). Test-existence claims are **[R] by name**, not by pass. Everything marked [M] was executed (stdlib-only modules, loaded directly).

---

## 1. What the system promises

Read from code, the promise is one sentence:

> An artifact produced by a model is checked by something other than the model that produced it, and the check cannot be talked around — not by the plan, not by the author, not by "it finished".

| Value | Mechanism | Where |
|---|---|---|
| the author of a claim is not the author of the proof | planner / coder / verifier stages, per-role capabilities | `PlannerDispatchKind`, `profiles.build_registry_for_role` [R] |
| a claim maps to an executable check or is refused | `INV → CT → TEST-ID → selector → one nodeid` | `plan_v2._admit`, `resolve_selectors` [R] |
| the check that ran is the check that was reviewed | seal over plan bytes + revision + closure digest + exact nodeids | `acceptance_bundle.mint_seal` [R] |
| the author cannot edit what must pass | `MUTATION` view confined to `{"src","scripts"}` | `workspace._MUTATION_ROOTS` [R] |
| the proof is produced outside the author's control | managed no-network / read-only-rootfs cell | `profiles`, `slice_verification` [R] |
| "finished" ≠ "succeeded" | `ToolResult.fail` unless exit 0 + `DONE` + revision | `workflow_tool._v2_create_failure` [R] |
| human authority only for what physics puts out of reach | closed disposition reasons, caller-supplied grant, ≤30 days | `plan_v2.DISPOSITION_REASONS`, `plan_admission.bind_dispositions` [R] |
| uncertainty is a named state, not a retry | `DURABILITY_UNKNOWN` | `workspace` publish saga [R] |

Two mechanisms are the product: the **seal** and the **disposition pipeline** (a waiver a model cannot mint for itself, restricted to reasons that are outside the sandbox by nature rather than by convenience). Everything else is scaffolding.

The methodology visible in the ledger is the same thesis applied to the work: claims are measured rather than read, defects get names and closure, and one mechanism is preferred over a parallel path.

---

## 2. Current state (what is on the route today)

| Item | State | Evidence |
|---|---|---|
| V2 parser + admission rules (`plan_v2.py`, 775 lines) | implemented, one production call site | `workflow_controller.py:3190` [R] |
| create-new: scaffold → planner writes → one revision → metadata cross-check → admission | implemented (D-V2-9) | `project_scaffold.py`, `_admit_published_project:3141` [R] |
| SLICE1 tests CT-1.1…1.5 | 5/5 present | `tests/test_ai_native_plan_v2.py` [R] |
| SLICE2 tests CT-2.1/2.2/2.3/2.5–2.9 | 8/8 present | `test_ai_native_bootstrap.py`, `test_invoke_workflow_tool.py`, `test_prompt_registry_coherence.py` [R] |
| `mint_seal`, `collect_sealed_nodeids`, `run_sealed_acceptance`, `kill_attribution`, `acceptance_defect` | implemented + unit-tested (≈210 test functions across six banks) | `acceptance_bundle.py`, `acceptance_collection.py`, tests [R] |
| any of the above on the controller route | **none** — 0 references to `AcceptanceBundle` in `workflow_controller.py` | [R] |
| coder gate | one choke point, admission only | `_run_stage:1634` [R] |
| `UNCOVERED` consumer | **none** | `contract_evidence` used only via `attested_contracts` at mint [R] |
| coder view protection | plan file only | `workspace.py:2194`, `:2814` pass `(plan_ref.workspace_relative_path,)` [R] |
| planner `verify` fence | still executed, no format branch | `slice_verification.py:552`; `grep plan_format` → 0 [R] |
| real V2 project documents | **zero** | `grep -rl AI-NATIVE-PLAN-V2 worklogs/` → plan/ledger/notes only [R] |
| authored-repair budget | 1 by default, shares the replan budget | `DEFAULT_MAX_REPLANS = 1` (`:157`), `_may_repair_authored_project:2950` [R] |
| repair write surface | increment + `open-questions.md` | `_REPAIR_WRITABLE_SUFFIXES:3044` [R] |

Scale: `src` 88 747 lines, `tests` 152 181 (≈5 53x test functions by source scan), `worklogs/**/*.md` **141 555** lines, ledger 317 `###`-headed entries [R].

**Two consequences.**

1. Because no V2 plan exists outside fixtures, every vocabulary change below has **zero compatibility cost today** [R]. This is the cheapest moment to fix the grammar; the price rises monotonically.
2. STEP9A shipped the mechanisms; **SLICE3 is an integration slice, not a construction slice.** `collect_sealed_nodeids` already runs the sealed closure's own `pytest.ini`/`rootdir` (`sealed_collection_argv:101`), refuses a tree that drifted from the seal, refuses an unexecuted selector (`run_sealed_acceptance:181`), and `excluded_paths` defaults to `()` so `worklogs/` is visible through a managed view [R]. What is missing is controller wiring plus one policy predicate.

---

## 3. The decision: evidence must be total

### 3.1 What the code admits today [M]

`plan_v2` executed directly, one contract per row:

| Plan shape | Outcome today | Grade |
|---|---|---|
| `HARD` + `TEST_REQUIRED`, no selector, no disposition | **refused** `hard-contract-without-executable-evidence` | — |
| `SOFT` + `TEST_REQUIRED`, no selector, no disposition | **admitted** | `UNCOVERED` |
| `HARD`/`SOFT` + `NON_EXECUTABLE` + reason, **caller supplied no grants** | **admitted** | `UNCOVERED` |
| `HARD`/`SOFT` + `NON_EXECUTABLE` + reason, grant bound | admitted | `ATTESTED` |
| `PRESERVATION`, any kind, no selector | **refused** `preservation-without-executable-evidence` | — |

Row 2 is the hole reported as Q-V2-ACC-2. Row 3 is a second hole that this review found and E601 did not: **the controller skips the binding step entirely when the caller supplied no grants**, so the request is never checked at all (§5.1).

### 3.2 Behaviour on a real task

Task *«сделай сервис экспорта отчётов»*; the planner writes `INV: export works offline`, `EVIDENCE: TEST_REQUIRED`, `CT-1.2`, and no acceptance row.

| | Keep today (A) | Refuse `UNCOVERED` at the seal (C, E600's pick) | Refuse at admission (recommended) | Refuse `HARD+NON_EXECUTABLE` too (E601-A) |
|---|---|---|---|---|
| plan admitted | yes | yes | **no** | as recommended, for the soft case |
| repair runs | — | no refusal yet | **yes** — it *is* the repair trigger (§3.3) | — |
| coder starts | yes | yes, until the seal is wired; unproven forever if it is never wired | no | no |
| what the run produces | a project whose own plan says a test is required and has none | second gate with no repair path on this route | a second revision that adds the test or converts the claim into a request for a grant; else `BLOCKED`, project present, unadmitted | dispositions unusable for exactly the claims they exist for |
| seal is truthful | no (contract vanishes from the seal — §6) | no | yes | — |
| cost | 0 | ~two predicates to keep in step, forever | 5 small edits, 3 test rewrites (§3.4) | — |
| verdict | hole | wrong layer | **correct** | regression |

**Answer to the operator's question.** A plan that says "must be tested" and ships no test must not reach a coder, and it does not need a waiver either: it goes back to the planner with an actionable rule name, or the run ends `BLOCKED` with the project present and inspectable. A waiver is for claims outside the sandbox, not for tests the planner did not write.

### 3.3 Why "parse vs seal" is not the real choice [R]

There is **one** gate on this route and its refusal **is** the repair trigger:

```
authoring stage → STOP_VIEW/SEAL/PUBLISH (one revision)
  _admit_published_project                                    workflow_controller.py:3141
    check_project_metadata → snapshot_from_bytes(… PLAN_V2)   :3168, :3190 → parse_plan → _admit
    bind_dispositions (only if the caller supplied grants)    :3209
    any PlanRefError → _bind_authored_project                 :2963 (single call site :2289)
      → _may_repair_authored_project                          :2929 (excludes collision / unavailable /
                                                               route-mismatch / failed repair, :2946–2951)
      → _run_create_new_repair (1 attempt)                    :3081 → admits the second revision :3138
```

A parse refusal returns `bootstrap-invalid-metadata` (`:3202`), which is repairable. E600's premise — that refusing at parse "lands before the repair begins and burns the budget" — is not the code's behaviour; **refusing at parse is what feeds the repair loop.** The real choice is *one predicate* versus *two predicates that must stay in step*, and the plan forbids the second everywhere it discusses code.

Rule of thumb this restores: **a structural fact (no selector exists) belongs where the document is read; a caller fact (no grant exists) belongs where the grant is bound. Neither belongs at the seal.** The seal asserts the consequence (§6).

### 3.4 The recommended rule, and its measured blast radius

> Every contract is discharged by exactly one mode, and the mode is total. `TEST_REQUIRED` requires an acceptance row resolving to exactly one nodeid in the sealed closure. `NON_EXECUTABLE` requires a caller-granted typed disposition. `KIND` is not an exemption; `PRESERVATION` is never dispositionable. "ready CT" is struck — it has no runtime meaning (0 hits in `src/fa/`).

**Why totality does not over-constrain the planner [A].** The unit of admission is the *increment*, and the increment is what the coder implements; verification is already slice-scoped (`slice_verifications`). So every slice's oracle must exist before the first coder byte — which is the property the whole system claims. Work that is not yet imagined belongs in a future increment, which is the artifact model's own answer. The `SOFT` flag was implicitly serving "some of this plan is not real yet"; the honest form of that statement is "this plan is not ready", not "this claim is exempt".

**The patch is two deletions** (measured on a copy of `plan_v2.py`, Appendix A):

| Case | today | with `kind != "HARD"` removed |
|---|---|---|
| legitimate: covered contract + `HARD` disposition request | admitted | **admitted** |
| `SOFT` + `TEST_REQUIRED` uncovered | admitted | **refused** `contract-without-executable-evidence` |
| `HARD` + `TEST_REQUIRED` uncovered | refused | refused (same rule, renamed) |
| `SOFT` + `NON_EXECUTABLE` request (no grant yet) | admitted | **admitted** (request is a document fact; the grant is checked at admission) |
| `PRESERVATION` uncovered | refused | refused (unchanged) |

Exactly one cell changes. Tests that encode the hole: **3 functions**, not 2 —
`test_a_soft_invariant_may_still_stay_uncovered` (`tests/test_ai_native_plan_v2.py:819`),
`test_a_contract_with_neither_a_selector_nor_a_disposition_is_uncovered` (`:720`), and
`test_a_plan_that_disposes_of_nothing_seals_an_empty_attestation` (`tests/test_ai_native_acceptance_bundle.py:493`).
The third is the seal-level twin: it mints a seal over an undispositionsed contract and asserts `attested == ()`. `KIND: SOFT` appears in 5 places in the whole test tree [R].

### 3.5 `KIND` itself

`invariant.kind` is read in exactly one place (`plan_v2.py:622`) and only to exempt [R]. For a model author, a field whose only consumer removes an obligation is an attractor: the cheapest admissible document is the one that uses it.

* **For the MVP: delete it.** One evidence field, two total modes. The §3.4 patch already does the work; deleting the field is the follow-up that removes the attractor from the prompt and the schema.
* **If severity is wanted later**, it is a *second* field (`SEVERITY: BLOCKING | ADVISORY`) with its own consumer (verdict grading, status promotion — SLICE4), never mixed into proof mode.

Doctrine worth adopting in the project's own idiom: **no field enters the grammar without a named consumer and a test that fails when the consumer is removed** — the producer kill-check applied to the vocabulary.

---

## 4. Where `KIND` came from, and why the question felt unanswerable

There are four descriptions of one grammar, and the model that writes plans reads the unchecked ones:

| Surface | Reader | Checked by |
|---|---|---|
| `plan_v2.py` | the machine | itself |
| `notes/artifact-schema-and-grammar.md` | 2 skills, 4 conformance tests, humans | **nothing** — `AI-NATIVE-PLAN-V2` ×0, `KIND:` ×0, `CT-` ×0, `TESTS:` ×10 [R] |
| `prompt.AUTHORING_SYSTEM_PROMPT:1225` | **the model** | nothing; it states a rule the parser does not enforce (`:1260`) and a promise nothing keeps (`:1319`) [R] |
| plan §2 "grammar delta" | reviewers | nothing; it contradicts §8 and its own Q table [R] |

The fix is the *relationship*, not the text: one machine-readable grammar table (sections, fields, cardinalities, closed rule names) from which the parser's rules, the document's grammar block, the skills' conformance test and the prompt's worked example are all checked. The repository already does this for the admission-record vocabulary (`ADMISSION_RULES`/`ADMISSION_RULES_V2`); extending it to the grammar closes the root cause. Two live defects prove it is not academic:

* `_validate_v2_admission` emits diagnostics under validator `"plan-v2"` (`:3481`, `:3490`), absent from `ADMISSION_RULES_V2`; `_record_diagnostics` would reject such a record as corrupt (`_record_enum(validator, frozenset(rules))`). Latent — today the create-new route returns before a `_WorkflowAdmission` exists [R].
* the record's `contract_id` shape is `CT\d+[a-z]?` (`admission_schema.py:169`), while V2 ids are `CT-1.1` (`plan_v2.is_contract_id`): a V2 diagnostic cannot carry a contract id [R].

---

## 5. Two defects this review found (fix them with the same change set)

### 5.1 An un-granted disposition request reaches the coder [M]

`_admit_published_project:3209` reads `if snapshot.graph is not None and granted:` — and `granted` is `()`
whenever the caller passed no dispositions. So the binding step is skipped, no rule fires, and the graph is
admitted with the request still unbound: `contract_evidence → UNCOVERED`, `attested_contracts → ()`.

The library is not at fault: `bind_dispositions(graph, ())` raises `disposition-undeclared` [M], and
`test_a_request_without_a_grant_never_binds` already proves it (`tests/test_ai_native_dispositions.py:183`).
**The controller bypasses a rule the library enforces and a test already pins.** One guard removed.

Consequence at the caller: the rule is absent from `_V2_CREATE_FAILURES`, so the run ends as the generic,
non-retryable `workflow_failed` (`workflow_tool.py:879`) — unattributable, which INV-11 forbids [R].

### 5.2 The repair loop cannot repair the case it exists for [R]

| Fact | Measurement |
|---|---|
| one repair attempt, shared with the replan budget | `DEFAULT_MAX_REPLANS = 1` (`:157`); `authored_repairs < replans_allowed` (`:2950`) |
| the repair may write only two files | `_REPAIR_WRITABLE_SUFFIXES` (`:3044`) — `acceptance/tests/` is **not** writable |
| every grammar refusal reaches the repair stage as one string | `format_error` → `bootstrap-invalid-metadata` (`:3202`) → `_authored_diagnostics` (`:2953`) |

So the natural fix for "the plan promised a test it does not have" — *write the test* — is outside the allowlist,
and the model is told "invalid metadata" instead of `acceptance-selector-invalid` or
`hard-contract-without-executable-evidence`. With one attempt, the reachable behaviours are "delete the claim" or
"re-describe it as a grant request": exactly the two an author model is most likely to choose, and both worse than
the truth. The tool's own comment already records the folded-rule part as debt (`workflow_tool.py:846–850`); this
review adds the reason it is not deferrable — **the diagnostic is the only feedback channel to the author.**

The minimal fix is not a new mechanism:

1. `acceptance/tests/` joins the repair allowlist (planner-owned bytes, sealed afterwards, coder still excluded).
2. The parser's closed rule becomes the diagnostic rule — which requires the `plan-v2` namespace to exist in
   `ADMISSION_RULES_V2` (§4), i.e. the same table work.
3. `disposition-undeclared` is classified **non-repairable** and mapped to `disposition_required` with
   `retryable=True`.

(3) is the important one and it is counter-intuitive, so it is spelled out in §5.3.

### 5.3 A grant request needs an upward path, not a repair attempt [A]

A caller fixes `ctx.dispositions` at invocation. If a plan truthfully needs an attestation the caller did not
pre-declare, the planner **cannot** satisfy the refusal — only a human can. Spending the single repair attempt on it
guarantees the model removes or weakens the claim. Therefore:

* the refusal is **not repairable** (add the rule to `_may_repair_authored_project`'s exclusion set, next to
  collision — both are "a fact about the world, not about the bytes");
* it maps to a **retryable** code `disposition_required` in the existing `_V2_CREATE_FAILURES` table (one row);
* the caller re-invokes with `--dispositions` / the tool field.

That is the human gate the design intends — reached as a *result*, not as an author's second guess. It is two lines
in existing tables, not a new outcome type. It also makes CT-1.5's missing `--dispositions` CLI ingress
(`cli.py:975–993`) blocking rather than deferred: the human path must be able to supply the grant.

---

## 6. What the seal must say [M]

Measured: a seal minted over a plan with one tested contract and one un-granted `NON_EXECUTABLE` contract
(`CT-1.2`) contains **no trace of `CT-1.2`** — not in `selectors`, not in `attested`, and the record has no field
where it could appear:

```
seal.attested     = ()
selector CTs      = ['CT-1.1']
record keys       = attested, closure_sha256, files, identity, kind, mode, plan_sha256,
                    revision_id, schema_version, seal_sha256, sealed_root, selectors, supersedes_sha256
CT-1.2 in seal    -> False
```

A manifest that does not state cardinality cannot be audited: the reader cannot distinguish "the rest were waived"
from "the rest were never mentioned". Production manifests solve this the boring way — a total count plus per-item
digests (lockfiles, in-toto/SLSA subjects).

**Seal requirements (three additions, no new policy):**

1. `mint_seal` refuses a graph whose `contract_evidence` contains `UNCOVERED` — as a *serialization invariant*, not a
   second admission decision (defence in depth against a future caller minting from an unadmitted graph).
2. `mint_seal` refuses an `NON_EXECUTABLE` invariant with `owner is None` — an unbound request must never become a
   seal with a silent empty attestation.
3. The record carries `contracts_total`, `attested`, `uncovered` (empty by construction), so
   `len(selectors) + len(attested) == contracts_total` becomes checkable **without the graph**.

With §3.4 + §5.1 in place, (1) and (2) can never fire on the create-new route; that is what makes them assertions
about the pipeline rather than a second gate. `attested` already exists; only the counter and the two refusals are new.

---

## 7. SLICE3 as an integration slice — order and exit criteria

The plan's CT order is a dependency order; this is a *risk and value* order. Each step is independently revertible.

| Step | Work | Exit criterion | Why here |
|---|---|---|---|
| **S0** | Probe: run `sealed_collection_argv` through the **managed** executor against a published fresh project; assert one nodeid; assert a parametrized selector (`::test_x[p]`) resolves; assert an uncollected selector refuses | one C1 test; if it fails, replan before any seal work | the only unknown that can invalidate everything else; ~1 h, not a research spike (§2.2) |
| **S1** | §3.4 (delete the `KIND` exemption, rename the rule) + §5.1 (unconditional `bind_dispositions`) + §5.2 (repair allowlist, precise diagnostic) + §5.3 (non-repairable, `disposition_required`) | 3 rewritten tests + 5 new: uncovered `TEST_REQUIRED` refused pre-coder; un-granted request refused; repair adds the missing test and the second revision admits; the diagnostic carries the parser rule; the caller sees `disposition_required` as retryable | closes both holes at the gate that already exists; no seal needed |
| **S2** | Mint on the route: after admission, `collect_sealed_nodeids` → `resolve_selectors` → `mint_seal` (bound graph, published revision) → persist per-seal + atomic pointer (D-V2-5) → coder gate `_run_stage:1634` refuses without a valid seal; §6 counters | CT-2.4, CT-3.2; a fresh project has a seal before its first coder byte; missing/stale seal blocks dispatch | makes INV-06 true on the product path |
| **S3** | Mode A: `protected_paths` ← every sealed semantic path (`workspace.py:2194`, `:2814`), not just the plan file | CT-3.3 both halves (file-tool refusal; shell drift detected as `seal-byte-drift` before any verdict) | cheap, one tuple, closes an overclaim |
| **S4** | Verifier on the seal: `run_sealed_acceptance` with the existing `_VerifySubstrate`; **retire the planner `verify` fence on the V2 route** (`slice_verification.py:552`) | CT-3.6; a drifted closure yields no verdict | command text must never drive a result |
| **S5** | Attribution + TEST-DEFECT onto `kill_attribution` / `acceptance_defect` | CT-3.4, CT-3.5 | no new state machine |
| **S6** | Diagnostic namespace + grammar table + canonical doc + skills + prompt example (§4, §5.2) | the prompt example parses (§CT-2.6); `ADMISSION_RULES_V2` contains every rule the parser can emit | last, because only then can it be written truthfully (the P0-1 lesson) |

Do **not** start with "the graph" as a new feature: `_admit_contracts`, `_admit_acceptance`, `_admit_scenarios`,
`_admit_kill_targets`, `_admit_steps` already enforce the cardinalities, and `resolve_selectors` already implements
the nodeid half — it is simply not called on this route yet [R].

---

## 8. Remaining-work track

| # | Item | Depends | State |
|---|---|---|---|
| 1 | Ratify D-V2-10 (evidence totality) and D-V2-11 (grammar table); correct plan §2, the Q-V2-ACC-2 row and §8 step 4 | — | **waiting on the operator**, no code |
| 2 | S0 collection probe | — | ready |
| 3 | S1 policy closure (§3.4, §5.1–5.3) | 1 | ready; 5 small edits |
| 4 | S2 seal on the route (+ §6) | 3 | CT-2.4, CT-3.2 |
| 5 | S3 mode A / S4 verifier | 4 | CT-3.3, CT-3.6 |
| 6 | S5 attribution, TEST-DEFECT | 4 | CT-3.4, CT-3.5 |
| 7 | S6 grammar table + doc/skills/prompt | 3 | current §4 debt becomes a task |
| 8 | Debt: `--dispositions` CLI ingress (blocking after §5.3); `plan-v2` namespace; `CT-1.1` in the record schema; delete V1 `plan_ids` after the `SELECT_EXISTING` decision | — | partially blocking S1 |
| 9 | Q-V2-ACC-1: budgets **closed-by-code** (512 files / 4 MiB per file / 16 MiB total / 4096 chars / depth 64 + refusal set, 25 tests); the transitive-import half is a **named residual**, not a gate | — | close with a record |
| 10 | SLICE4/5 as planned; ticks stay a projection (Q-V2-STATUS-1 = A); status-producer design gate unchanged | 4 | unchanged |

---

## 9. Risks and non-goals

| Risk | Mitigation |
|---|---|
| the seal gate becomes a second policy gate | §6 makes it a serialization invariant only; the create-new route can never reach it |
| totality makes the first real plan inadmissible and stalls the product | that is the intended behaviour, but it must land **with** §5.2 (repair can write the test) and §5.3 (honest escalation), or the first run will look like a regression |
| surface drift recurs after S6 | the table is the source; the conformance test fails when the doc/prompt/skills disagree |
| more audits instead of a first real run | §10 |
| **not** doing | reopening D-V2-9 (it deletes an orthogonal serialization and is implemented); changing `MUTATION_ROOTS`; blocking the shell half of mode A (D-V2-6 = detection is correct and profile identities stay untouched); inventing severity semantics before a consumer exists |

---

## 10. What I would do on Monday

1. Ratify D-V2-10/D-V2-11 and the four one-paragraph plan corrections (30 min, no code).
2. Run S0 (~1 h). It is the only measurement that can invalidate SLICE3.
3. Land S1 + S2 behind the existing banks; run the targeted suites.
4. **Then do one real create-new run end-to-end** and read what the model actually did. The whole product claim is
   about that path, and it has never been exercised outside fixtures; one live run will teach more about the repair
   loop, the prompt drift and the diagnostic quality than several more static reviews.

Workflow note, offered as an equal: the review layer has outgrown the product (141 k lines of worklog vs 89 k of
source, four audits in three days). The audits are good — E600's refusal to widen admission semantics by inference
was exactly right — but the bottleneck has moved from *unknowns* to *decision latency*. The plan carries decisions,
status and specification in one file, which is why §8 can claim a question closed while its own row says BLOCKING.
Split them: decisions immutable and dated, state generated or checked, specification machine-verified.

---

## 11. Adversarial review of this document

### 11.1 Corrections to the v1 draft (this is what self-review changed)

| # | v1 said | Correct statement | Why it matters |
|---|---|---|---|
| 1 | "without a grant `_granted_dispositions` refuses the run (`disposition-undeclared`)" | **false**: the controller skips binding entirely when no grants were supplied (`:3209`), so the request is admitted and graded `UNCOVERED`. The library would have refused, and a test proves it; the controller bypasses it | it is a second, live hole, and it is the cheapest of the whole set to close (one guard) |
| 2 | "two tests get rewritten" | **three**, named in §3.4 | the third is at the seal level, so it also proves the seal blindness |
| 3 | "the seal is shape-identical to a covered one" | stronger: the un-granted contract **disappears** from the seal entirely [M] | "shape-identical" understated it |
| 4 | CT-3.1 "~80 % implemented" | the cardinality half is implemented; the nodeid half (`resolve_selectors`) is implemented but not called on this route | avoids implying a parser feature is missing |
| 5 | S0 "the riskiest unknown" | the library path is implemented and unit-tested with a fake executor; the unknowns are the managed executor, the new path prefix and parametrized ids | a 1 h probe, not a spike — and it should not gate planning decisions |
| 6 | "`needs_grant` as a structured terminal outcome" | over-engineered: one row in `_V2_CREATE_FAILURES` + one rule in the non-repairable set + non-deferral of the CLI ingress | user's rule: simplest mechanism that fully satisfies the behaviour |
| 7 | "the diagnostic problem is a gap I found" | the folded-rule part is already recorded as debt in `workflow_tool.py:846–850` | credit accuracy; the finding is *why it is not deferrable* |
| 8 | "refuse `HARD+NON_EXECUTABLE` = regression" (kept) | confirmed and sharpened: the disposition pipeline needs `HARD` claims to exist at all | prevents a plausible-looking wrong fix |

### 11.2 Objections a reviewer should raise, and the answers

* **"Totality will refuse legitimate incremental planning."** §3.4 answers it: the unit of admission is the
  increment; unevidenced future work is a future increment. If the product genuinely needs exploratory slices, that
  is a *new* requirement and needs its own decision — it is not served by a silent exemption.
* **"Deleting `KIND` breaks the schema the plan mandates."** The schema already does not contain `KIND` (§4); there
  is nothing to break, and no V2 plan exists to migrate (§2).
* **"The repair should be allowed to rewrite tests — the model could weaken them."** Nothing executes at admission,
  and the coder cannot reach `acceptance/`; the seal binds whatever the repair wrote, and the verifier runs those
  bytes. The attack surface is unchanged; the alternative is a repair that can never fix the case it exists for.
* **"`disposition_required` retryable invites a loop."** Retryability is a *caller* hint, not an automatic retry;
  the same pattern is already used for `invalid_dispositions` (`workflow_tool.py:866`).

### 11.3 Residual uncertainty in this document

1. The proposals are not applied to the tree; the §3.4 blast radius was measured on a copy, not against the full
   suite. Expect the three named tests plus any fixture that mints a seal over an undispositionsed contract.
2. `SOFT` fixtures appear in 5 places; I read them, but a suite run is the authority.
3. S2's persistence details follow D-V2-5 as written; this review did not re-audit `q-v2-boot1-install-seal-audit`
   beyond the fact that the seal is minted from installed bytes + plan + revision.
4. **No test suite was executed** (sandbox lacks Python 3.13; `uv sync` blocked by egress). Claims about test
   greens elsewhere in the ledger were not re-verified.

---

## Appendix A — reproductions

```text
# 1. The evidence matrix, today (no pytest needed: plan_v2 is stdlib-only)
python3 - <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("plan_v2", "src/fa/inner_loop/plan_v2.py")
m = importlib.util.module_from_spec(spec); sys.modules["plan_v2"] = m; spec.loader.exec_module(m)
# ... build a two-contract document as in §3.1 and print m.contract_evidence(...)
PY
# Result: SOFT+TEST_REQUIRED uncovered -> ADMITTED, UNCOVERED; HARD -> REFUSED
#         hard-contract-without-executable-evidence

# 2. The patch blast radius: copy plan_v2.py, delete the `if invariant.kind != "HARD": continue`
#    branch, rename the rule; run the five cases in §3.4. Result: exactly one cell changes.

# 3. The un-granted request:
#    bind_dispositions(graph, (), today=date(2026,11,22))
#    -> PlanRefError: disposition-undeclared
#    ... and yet the request is admitted, because the controller skips this call (:3209).

# 4. The seal blindness: mint_seal over that graph (acceptance root needs pytest.ini + one test)
#    -> seal.attested == (), selector CTs == ['CT-1.1'], "CT-1.2" not in json.dumps(record)
```

Search anchors used: `grep -rn "invariant.kind" src/fa` → 1 hit; `grep -rn "AcceptanceBundle" workflow_controller.py`
→ 0; `grep -c -- "KIND:" artifact-schema-and-grammar.md` → 0; `grep -rl "AI-NATIVE-PLAN-V2" worklogs/` → 0 projects.
