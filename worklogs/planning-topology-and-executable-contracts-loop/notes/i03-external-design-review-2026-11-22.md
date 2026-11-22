# I03 evidence model — decision document (v3, cross-reviewed)

**Date:** 2026-11-22. **v3** merges the independently produced package `2 (2).md` (same brief, second agent) and records what was adopted, rejected and corrected (§11). **No production code changed.**<br>
**Ledger:** E602 (v1 findings) · E603 (self-audit corrections) · E604 (cross-review).<br>
**Authority:** [`i03-ai-native-workflow-refactor-plan-v2.md`](i03-ai-native-workflow-refactor-plan-v2.md), Q-V2-ACC-2; prior audits `evidence-model-audit-2026-11-21.md`, E600, E601.

### Evidence classes

**[M]** measured by executing production code in this review · **[R]** read from source, file:line cited · **[A]** argument, explicitly not a measurement.

**Not verified:** the full pytest suite was not executed (no Python 3.13 in the review sandbox; `uv sync` could not fetch an interpreter). Test-existence claims are [R] by name. Every [M] claim was executed against the real modules with synthetic documents (Appendix A).

---

## 1. What the system promises, and who owns what

> An artifact produced by a model is checked by something other than the model that produced it, and the check cannot be talked around — not by the plan, not by the author, not by "it finished".

| Role | Owns | Does not own |
|---|---|---|
| Planner (AI) | semantic content: roadmap, increment, acceptance content, selectors, questions | scaffold identity, admission, seal |
| Harness / controller | scaffold, metadata cross-check, admission, seal minting, structured outcomes | planner semantic bytes |
| Coder (AI) | implementation and internal seams inside the admitted scope | sealed plan bytes, sealed acceptance closure, the tests it must pass |
| Verifier / eval | evidence from the sealed closure, classification | plan or test bytes |

The chain: `INV → CT → TEST-ID → selector → exactly one nodeid`, bound to exact bytes at an exact revision, executed in a cell the author does not control. Two mechanisms are the product — the **seal** and the **disposition pipeline** (a waiver a model cannot mint for itself, restricted to reasons that are outside the sandbox by nature). Everything else is scaffolding.

Target flow on the create-new route [R]:

```
chat → invoke_workflow(project_action=CREATE_NEW, project_slug)
  → slug validated before any child exists
  → harness opens WRITE PROJECT view, writes the scaffold (roadmap.md first)
  → planner authors documents + acceptance tests under worklogs/<slug>/
  → STOP_VIEW → SEAL → PUBLISH   (one revision, D-V2-9)
  → metadata cross-check → parse_plan (grammar + graph + evidence rules)
  → bind_dispositions (caller grant → owner/evidence/reviewed_at)
  → admission gate → coder → sealed verifier → terminal result
```

---

## 2. Where the code actually is

| Layer | State | Evidence |
|---|---|---|
| V2 parser + admission rules (`plan_v2.py`) | landed, one production call site | `workflow_controller.py:3190` [R] |
| create-new: scaffold → planner-writes → one revision → metadata → admission | landed (D-V2-9) | `project_scaffold.py`, `_admit_published_project:3141` [R] |
| payload/renderer layer | **deleted** | `src/fa/inner_loop/plan_semantics.py` absent [R] |
| SLICE1 tests (CT-1.1…1.5) / SLICE2 tests (CT-2.1, 2.2, 2.3, 2.5–2.9) | 5/5 and 8/8 present | three banks [R] |
| seal / closure / collection / attribution / TEST-DEFECT | **library only**, ≈210 test functions across six banks | `acceptance_bundle.py`, `acceptance_collection.py`, … [R] |
| those libraries on the controller route | **none** — 0 `AcceptanceBundle` refs in `workflow_controller.py` | [R] |
| coder gate | one choke point, admission only | `_run_stage:1634` [R] |
| `UNCOVERED` consumer | **none** | `contract_evidence` only via `attested_contracts` at mint [R] |
| coder write confinement | **nesting-dependent**, not role-dependent (§6.4) | `cli.py:2165`, `workspace.py:2844–2854` [R] |
| planner `verify` fence | still executed, no format branch | `slice_verification.py:552`; `grep plan_format` → 0 [R] |
| real V2 project documents | **zero** | `grep -rl AI-NATIVE-PLAN-V2 worklogs/` → plan/ledger/notes only [R] |
| authored-repair budget / write surface | 1 (shared with replans) / increment + `open-questions.md` | `DEFAULT_MAX_REPLANS=1`, `_REPAIR_WRITABLE_SUFFIXES:3044` [R] |

Scale: `src` 88 747 lines · `tests` 152 181 (≈5 53x test functions by source scan) · `workflows/**/*.md` 141 555 · ledger 317 `###` entries [R].

**Consequences.**

1. **Zero compatibility cost today.** No V2 plan and no production seal exists, so every vocabulary and schema change below is free now and grows monotonically more expensive [R].
2. **SLICE3 is an integration slice, not construction.** `sealed_collection_argv:101` already pins the closure's own `pytest.ini`/`rootdir`; `collect_sealed_nodeids:136` refuses a tree that drifted from the seal; `run_sealed_acceptance:181` refuses an unexecuted selector; `excluded_paths` defaults to `()` so `worklogs/` is visible through a managed view [R]. What is missing is controller wiring plus one policy predicate.
3. **The plan's own gate is already breached**: STEP9B is unticked while SLICE1/SLICE2 are implemented. Ratifying this decision set is also how that gets regularized — it is not a reason to stop now.

---

## 3. The decision: evidence must be total

### 3.1 What the code admits today [M]

| Plan shape | Outcome | Grade |
|---|---|---|
| `HARD` + `TEST_REQUIRED`, no selector | **refused** `hard-contract-without-executable-evidence` | — |
| `SOFT` + `TEST_REQUIRED`, no selector | **admitted** | `UNCOVERED` |
| `NON_EXECUTABLE` + reason, **caller supplied no grants** | **admitted** | `UNCOVERED` |
| `NON_EXECUTABLE` + reason, grant bound | admitted | `ATTESTED` |
| `PRESERVATION`, any kind, no selector | **refused** `preservation-without-executable-evidence` | — |

Row 2 is Q-V2-ACC-2. Row 3 is a second, independent hole found in this review: the controller **skips the binding step entirely** when the caller supplied no grants (§6.1).

### 3.2 Behaviour on a real task

Task *«сделай сервис экспорта отчётов»*; planner writes `INV: export works offline`, `EVIDENCE: TEST_REQUIRED`, `CT-1.2`, and no acceptance row.

| | Keep today (A) | Refuse at the seal (C) alone | **Refuse at admission (recommended)** | Also refuse `HARD+NON_EXECUTABLE` (E601-A) |
|---|---|---|---|---|
| plan admitted | yes | yes | **no** | as recommended, for the soft case |
| repair runs | — | no refusal yet to repair | **yes** — it *is* the repair trigger (§3.3) | — |
| coder starts | yes | yes until the seal is wired | no | no |
| outcome | a project whose own plan demands a test it does not have | a second gate with no repair path | second revision adds the test, or the claim becomes a grant request; else `BLOCKED`, project present and honestly unadmitted | dispositions unusable for exactly the claims they exist for |
| seal truthful | no — the contract disappears from the seal (§6.5) | no | yes | — |
| cost | 0 | two predicates kept in step forever | 5 small edits + 3 test rewrites | — |

**Answer to the operator's question.** A plan that says "must be tested" and ships no test must not reach a coder, and it does not need a waiver: it goes back to the planner with an actionable rule name, or the run ends `BLOCKED` with the project present and inspectable. A waiver is for claims outside the sandbox, not for a test the planner did not write.

### 3.3 Why "parse vs seal" is not the choice [R]

There is **one** gate on this route, and its refusal **is** the repair trigger:

```
_admit_published_project                                  workflow_controller.py:3141
  check_project_metadata → snapshot_from_bytes(PLAN_V2)   :3168, :3190 → parse_plan → _admit
  bind_dispositions (only when grants were supplied)      :3209
  any PlanRefError → _bind_authored_project               :2963 (single call site :2289)
    → _may_repair_authored_project                        :2929 (excludes collision / unavailable /
                                                            route-mismatch / failed repair, :2946–2951)
    → _run_create_new_repair (1 attempt)                  :3081 → re-admits the second revision :3138
```

A parse refusal returns `bootstrap-invalid-metadata` (`:3202`) and is repairable. E600's premise — that refusing at parse "lands before repair and burns the budget" — is not what the code does: **a parse refusal is what feeds the repair loop**. The real choice is one predicate versus two kept in step; the plan forbids the second everywhere it discusses code.

The division that holds: **structural facts (no selector exists) are decided where the document is read; caller facts (no grant exists) where the grant is bound; the seal asserts the consequence.** Neither belongs at the seal as policy.

### 3.4 The rule, and its measured blast radius

> Every contract is discharged by exactly one mode, and the mode is total. `TEST_REQUIRED` requires an acceptance row resolving to exactly one nodeid inside the sealed closure. `NON_EXECUTABLE` requires a caller-granted typed disposition. `KIND` is not an exemption. `PRESERVATION` is never dispositionable. "ready CT" is struck — it has no runtime meaning (0 hits in `src/fa/`).

**Why totality does not over-constrain the planner [A].** The unit of admission is the *increment*, and the increment is what the coder implements; verification is already slice-scoped (`slice_verifications`). So every slice's oracle must exist before the first coder byte — the property the system claims. Work not yet imagined belongs in a future increment, which is the artifact model's own answer. `SOFT` was implicitly serving "part of this plan is not real yet"; the honest form of that is "this plan is not ready", not "this claim is exempt".

**The patch is two deletions** [M, applied to a copy of `plan_v2.py`]:

| Case | today | with the `kind != "HARD"` branch removed |
|---|---|---|
| legitimate: covered contract + `HARD` disposition request | admitted | **admitted** |
| `SOFT` + `TEST_REQUIRED` uncovered | admitted | **refused** `contract-without-executable-evidence` |
| `HARD` + `TEST_REQUIRED` uncovered | refused | refused (same rule, renamed) |
| `NON_EXECUTABLE` request, no grant yet | admitted | **admitted** (a request is a document fact) |
| `PRESERVATION` uncovered | refused | refused |

Exactly one cell changes. Tests that encode the hole: **three** — `test_a_soft_invariant_may_still_stay_uncovered` (`tests/test_ai_native_plan_v2.py:819`), `test_a_contract_with_neither_a_selector_nor_a_disposition_is_uncovered` (`:720`), and the seal-level twin `test_a_plan_that_disposes_of_nothing_seals_an_empty_attestation` (`tests/test_ai_native_acceptance_bundle.py:493`). `KIND: SOFT` occurs 5 times in the whole test tree [R].

### 3.5 `KIND`: give it a consumer or delete it

`invariant.kind` is read in exactly one place (`plan_v2.py:622`), and only to exempt [R]. For a model author, a field whose sole consumer removes an obligation is an attractor: the cheapest admissible document is the one that uses it.

* **MVP: delete `KIND`.** One evidence field with two total modes; the attractor leaves the prompt and the schema.
* **If severity is wanted (SLICE4),** it is a *second* field (`SEVERITY: BLOCKING | ADVISORY`) with its own consumer (verdict grading, status promotion), never fused into proof mode.

Two findings that were suggested as answers but do not survive: `SOFT` as "not admission-gating" is a severity claim with no consumer — i.e. exactly the defect, restated; and `HARD` refusal of dispositions (§3.6) would remove the mechanism's main use.

### 3.6 `HARD + NON_EXECUTABLE` is the disposition pipeline's primary case

The whole point of a disposition is a claim that is **critical and unobservable**: host readiness, deployment identity, owner approval, durability. If `HARD` could not be dispositioned, the mechanism would exist only for claims nobody cares about. The plan's own ACC-2 row offers this as option B, and its §2 sentence carries the escape clause ("…unless Q-V2-ACC-2 is resolved under a ratified rule"); the typed-reason + caller-grant + 30-day pipeline **is** that rule. E601's proposal to refuse `HARD + NON_EXECUTABLE` would be a regression against the feature's purpose. The plan's strict line must be deleted, not enforced.

**The real residual [A, refined in v3].** The *caller* grants a **reason**, not a claim; the *planner* chooses which contract carries that reason. The cluster rule (one contract per invariant) and the one-shot reason rule bound the damage, and `owner`/`evidence_ref`/`reviewed_at` prove a human looked at something — but the pairing "this claim ↔ this attestation" is selected by the author. Mitigation, cheap: the binding is recorded where a human can review it (seal records the attested contract ids; the run report shows claim + reason + owner). Do **not** try to solve it by refusing `HARD`.

---

## 4. Where the plan contradicts itself [R]

Five sentences define the evidence rule and they do not agree. This is what makes the question feel unanswerable, and it must be fixed before the code change is ratified.

| Line | Statement | Reading |
|---|---|---|
| 60 (grammar delta) | "`NON_EXECUTABLE` is forbidden for HARD/ready contracts **unless** Q-V2-ACC-2 is resolved under a ratified rule" | strict |
| 233 (production grammar) | "every hard INV/ready CT has **a test or a typed explicit evidence disposition**" | loose |
| 284 (INV-05) | "Every admitted hard invariant/ready CT has **an explicit evidence disposition** and complete ID graph" | loose |
| 511 (CT-3.1 row) | "hard invariant/ready CT must have executable evidence or **explicit reviewed disposition**" | middle |
| 621 (Q-V2-ACC-2 row) | **BLOCKING**, choices (A) executable assertion or (B) typed disposition — pending | pending |
| 650 (§8 step 4) | "Q-V2-ACC-1/2 are closed" | **false** |

Also: the canonical schema (`notes/artifact-schema-and-grammar.md`) is V1-shaped — `AI-NATIVE-PLAN-V2` ×0, `KIND:` ×0, `CT-` ×0, `TESTS:` ×10 [R] — while two skills and four conformance tests read it and `prompt.AUTHORING_SYSTEM_PROMPT:1225` gives the model a third description (it states a rule the parser does not enforce at `:1260`, and promises a gate nothing keeps at `:1319`).

The fix is the *relationship*, not the text: **one machine-readable grammar table** (sections, fields, cardinalities, closed rule names) from which the parser's rules, the document's grammar block, the skills' conformance test and the prompt's worked example are all checked. The repository already does this for the admission-record vocabulary (`ADMISSION_RULES`/`ADMISSION_RULES_V2`). Two live defects show it is not academic:

* `_validate_v2_admission` emits diagnostics under validator `"plan-v2"` (`:3481`, `:3490`), which is **absent** from `ADMISSION_RULES_V2`; `_record_diagnostics` would reject such a record as corrupt. Latent today because the create-new route returns before a `_WorkflowAdmission` exists [R].
* the record's `contract_id` shape is `CT\d+[a-z]?` (`admission_schema.py:169`) while V2 ids are `CT-1.1` — a V2 diagnostic cannot carry a contract id [R].

---

## 5. The correction to "where to refuse"

Worth stating once, because both independent reviews started from the routing question: **the routing question is downstream of a vocabulary question.** Refusing `UNCOVERED` "at parse" and "at the seal" are the same rule applied at two points; what matters is (a) that every claim has exactly one discharge mode, (b) that the mode is checked where its facts exist, and (c) that the seal records the consequence. Fix (a) and the routing question disappears; fix only the routing and the vocabulary stays broken.

---

## 6. Defects found in these reviews (all with minimal fixes)

### 6.1 An un-granted disposition request reaches the coder [M]

`_admit_published_project:3209` reads `if snapshot.graph is not None and granted:` — and `granted` is `()` whenever the caller passed no dispositions. The binding step is skipped, no rule fires, and the graph is admitted with the request unbound (`UNCOVERED`, `attested == ()`).

The library is not at fault: `bind_dispositions(graph, ())` raises `disposition-undeclared` [M], and `test_a_request_without_a_grant_never_binds` already pins it (`tests/test_ai_native_dispositions.py:183`). **The controller bypasses a rule the library enforces and a test proves.** Fix: delete the guard. At the caller the rule is absent from `_V2_CREATE_FAILURES`, so the run currently ends as the generic non-retryable `workflow_failed` (`workflow_tool.py:879`) — unattributable, which INV-11 forbids [R].

### 6.2 The repair loop cannot repair the case it exists for [R]

| Fact | Measurement |
|---|---|
| one repair attempt, shared with the replan budget | `DEFAULT_MAX_REPLANS=1` (`:157`), `authored_repairs < replans_allowed` (`:2950`) |
| the repair may write only two files | `_REPAIR_WRITABLE_SUFFIXES:3044` — `acceptance/tests/` is **not** writable |
| every grammar refusal reaches the repair stage as one string | `format_error` → `bootstrap-invalid-metadata` (`:3202`) → `_authored_diagnostics:2953` |

The natural fix — *write the missing test* — is outside the allowlist, and the model is told "invalid metadata" instead of `acceptance-selector-invalid`. With one attempt, the reachable behaviours are "delete the claim" or "re-describe it as a grant request": exactly what an author model will choose, and both worse than the truth. The folded-rule part is already recorded as debt in `workflow_tool.py:846–850`; what this review adds is why it is not deferrable — **the diagnostic is the only feedback channel to the author.**

Minimal fix: (i) `acceptance/tests/` joins the repair allowlist (planner-owned bytes, sealed afterwards, coder still excluded); (ii) the repair **task text** carries the parser's precise rule (no record-schema change needed for this — the closed vocabulary work is §4 and can land separately); (iii) §6.3.

### 6.3 A grant request needs an upward path, not a repair attempt [A]

The caller fixes `ctx.dispositions` at invocation. If a plan truthfully needs an attestation the caller did not pre-declare, the planner **cannot** satisfy the refusal — only a human can. Spending the single repair on it guarantees the model removes or weakens the claim. Therefore:

* classify `disposition-undeclared` as **non-repairable** — add it to `_may_repair_authored_project`'s exclusion set next to collision (both are facts about the world, not about the bytes);
* map it to `disposition_required`, `retryable=True`, in `_V2_CREATE_FAILURES` (one row);
* the caller re-invokes with `--dispositions` / the tool field.

That is the human gate the design intends — reached as a *result*. It also makes CT-1.5's missing `--dispositions` CLI ingress (`cli.py:975–993`) blocking rather than deferred.

### 6.4 The coder's write confinement is a property of the launch topology, not of the role [R]

> Found while checking the parallel package's §3.12; missed by all three prior audits.

```
cli.py:2165   is_nested_coder = role == "coder" and managed.binding.namespace.parent_run_id is not None
              write_purpose   = ViewPurpose.MUTATION if is_nested_coder else ViewPurpose.PROJECT
workspace.py:2844–2854   PATH_DENIED for a MUTATION view outside {"src","scripts"}
                         PROJECT purpose → ordinary rooted-IO policy, no confinement
profiles.py:123–137      the coder holds unconfined fs_write_file / fs_edit_file
workspace.py:2194/2814   protected_paths = (plan file,) only
```

So: a **nested** coder (the V2 create-new route — chat → tool → child run) is confined to `{src, scripts}` and cannot touch `worklogs/`. A **top-level managed** coder stage opens a PROJECT view, where the purpose policy imposes no confinement and the only barrier is `protected_paths` — which carries the plan file and nothing else. On that route `worklogs/<slug>/acceptance/tests/**` is writable by `fs_write_file`.

The system's central claim ("the coder cannot edit the tests it must pass") is therefore true by *topology* on the common route, and false on another supported one. Note that making the purpose unconditionally `MUTATION` is **not** the fix — the coder legitimately writes repository tests, docs and configs outside `{src, scripts}` — which is precisely why the plan's CT-3.3 mechanism (`protected_paths` covering every sealed semantic path) is the right one and why it is urgent rather than defence-in-depth.

### 6.5 The seal cannot express "unverified", and a second producer can mint one [M]

A seal minted over a plan with one tested contract and one un-granted `NON_EXECUTABLE` contract contains **no trace of the latter**:

```
seal.attested    = ()     selector CTs = ['CT-1.1']
record keys      = attested, closure_sha256, files, identity, kind, mode, plan_sha256, revision_id,
                   schema_version, seal_sha256, sealed_root, selectors, supersedes_sha256
"CT-1.2" in seal -> False
```

And the seal is not minted only from admission: `acceptance_defect.correct(...)` passes a **caller-supplied graph** into `mint_seal` (`acceptance_defect.py:246`) [R]. A manifest that does not state cardinality cannot be audited — the reader cannot distinguish "the rest were waived" from "the rest were never mentioned". Production manifests solve this the boring way: a total count plus per-item digests.

**Seal requirements (three additions, no new policy):**

1. `mint_seal` refuses a graph whose `contract_evidence` contains `UNCOVERED`.
2. `mint_seal` refuses an `NON_EXECUTABLE` invariant with `owner is None` (an unbound request must never become a seal with a silent empty attestation).
3. The record carries `contracts_total`, `attested`, `uncovered` **and the check** `len(selectors) + len(attested) == contracts_total`, so the property is auditable from bytes without the graph.

(1)–(2) enforce the same rule as admission at every mint point — including the defect re-mint path — which is why they are a *serialization invariant of the seal*, not a second gate. After §3.4 + §6.1 they can never fire on the create-new route; that is the point.

---

## 7. SLICE3 as an integration slice — order and exit criteria

| Step | Work | Exit criterion | Why here |
|---|---|---|---|
| **S0** | Probe: run `sealed_collection_argv` through the **managed** executor against a published fresh project; one nodeid; a parametrized selector (`::test_x[p]`) resolves; an uncollected selector refuses | one C1 test; if it fails, replan before seal work | **mint needs `collected` nodeids produced by running the sealed bytes** — the one integration unknown; ~1 h, not a spike (§2.2) |
| **S1** | §3.4 (delete the `KIND` exemption, rename the rule) · §6.1 (unconditional bind) · §6.2 (repair allowlist + precise rule in the task text) · §6.3 (non-repairable + `disposition_required`) | 3 rewritten tests + 5 new: uncovered `TEST_REQUIRED` refused pre-coder; un-granted request refused; repair writes the missing test and the second revision admits; the repair prompt carries the parser rule; the caller sees `disposition_required` as retryable | closes both evidence holes at the gate that already exists; no seal needed |
| **S2** | Mint on the route: `collect_sealed_nodeids` → `resolve_selectors` → `mint_seal` (bound graph, published revision) → persist per-seal + atomic pointer (D-V2-5) → coder gate `_run_stage:1634` refuses without a valid seal; §6.5 counters; `SCHEMA_VERSION` 1→2 (free: no production seal exists and `load_seal` fails closed on unknown versions) | CT-2.4, CT-3.2 | makes INV-06 true on the product path |
| **S3** | Mode A: `protected_paths` ← every sealed semantic path (`workspace.py:2194`, `:2814`); shell half stays detection (D-V2-6) | CT-3.3 both halves: file-tool refusal on **both** coder routes (§6.4), and `seal-byte-drift` before any verdict | closes a live hole, not just an overclaim |
| **S4** | Verifier on the seal: `run_sealed_acceptance` with the existing `_VerifySubstrate`; **retire the planner `verify` fence on the V2 route** (`slice_verification.py:552`) | CT-3.6 | command text must never drive a result |
| **S5** | Attribution + TEST-DEFECT onto `kill_attribution` / `acceptance_defect` | CT-3.4, CT-3.5 | no new state machine |
| **S6** | Grammar table + record namespace (`plan-v2`, `CT-1.1`) + canonical doc + skills + prompt example | the prompt example parses (CT-2.6); every parser rule is a member of the closed table | last: only then can it be written truthfully (P0-1) |

Do not start with "the graph" as a new feature: `_admit_contracts`, `_admit_acceptance`, `_admit_scenarios`, `_admit_kill_targets`, `_admit_steps` already enforce the cardinalities and `resolve_selectors` already implements the nodeid half — it is simply not called on this route [R].

---

## 8. Remaining work

| # | Item | Depends | State |
|---|---|---|---|
| 1 | Ratify D-V2-10 (evidence totality) + D-V2-11 (grammar table); reconcile §4's five sentences, §8 step 4, strike "ready CT" | — | waiting on the operator |
| 2 | S0 probe | — | ready |
| 3 | S1 policy closure | 1 | ready; 5 small edits |
| 4 | S2 seal on the route + §6.5 | 3 | CT-2.4, CT-3.2 |
| 5 | S3 mode A (now urgent, §6.4) / S4 verifier | 4 | CT-3.3, CT-3.6 |
| 6 | S5 attribution, TEST-DEFECT | 4 | CT-3.4, CT-3.5 |
| 7 | S6 grammar table + doc/skills/prompt + record namespace | 3 | §4 debt becomes a task |
| 8 | Debt: `--dispositions` CLI ingress (blocking after §6.3); delete V1 `plan_ids` after the `SELECT_EXISTING` decision | — | partially blocking S1 |
| 9 | Q-V2-ACC-1: budgets **closed-by-code** (512 files / 4 MiB per file / 16 MiB / 4096 chars / depth 64 + refusal set, 25 tests); transitive-import half a **named residual** | — | close with a record |
| 10 | SLICE4/5 as planned; ticks stay a projection (Q-V2-STATUS-1 = A); status-producer gate unchanged | 4 | unchanged |

---

## 9. What not to do, and why

1. **Do not refuse `HARD + NON_EXECUTABLE`.** It would leave dispositions usable only for claims nobody cares about (§3.6).
2. **Do not keep `SOFT` as "not admission-gating" without a consumer.** That is the diagnosed defect restated (§3.5).
3. **Do not enforce the rule only at the seal.** The repair path would stay dead and the fix would arrive after the budget is spent (§3.3).
4. **Do not delete the three encoding tests.** They are the only statement of what `SOFT` was for; rewrite them so the diff shows the semantic shift.
5. **Do not widen the repair allowlist without the diagnostic.** The model would be told "invalid metadata" and guess (§6.2).
6. **Do not bundle documentation, parser policy, repair geometry and CLI into one PR.** Atomicity belongs to the *doc triad* (schema + skills + conformance tests must move together), not to everything (§11.2).
7. **Do not make the coder's view unconditionally `MUTATION`.** The coder legitimately writes repository tests and docs; protect the sealed paths instead (§6.4).
8. **Do not present the transitive-import half of ACC-1 as closable.** Named residual.
9. **Do not reopen D-V2-9.** It deletes an orthogonal serialization and is implemented and tested.

---

## 10. Residual uncertainty

1. Proposals are not applied; the §3.4 blast radius was measured on a copy, not against the suite. Expect the three named tests plus fixtures that mint seals over undispositionsed contracts.
2. No test suite was executed here (sandbox has no Python 3.13; `uv sync` blocked by egress). Test greens elsewhere in the ledger were not re-verified.
3. S2 persistence follows D-V2-5 as written; `q-v2-boot1-install-seal-audit` was not re-audited beyond "seal = installed bytes + plan + revision receipt".
4. §6.4 is read from three call sites, not executed; a live top-level managed coder run would confirm it (`fa run` with managed execution and `role=coder`).
5. The status-tick design gate (plan §2) is independent and still blocks SLICE4/5; this document must not be read as resolving it.

---

## 11. Cross-review of the parallel package (`2 (2).md`)

Same brief, independently produced, second agent. Verdict: **it is the better briefing, this is the better decision record.** Roughly 80 % of its content is correct and 60 % of that is additive; its two load-bearing errors change the recommendation, and it misses the two live holes in §6.1/§6.4.

### 11.1 Adopted (its contributions, now in this document)

| Its contribution | Where it landed |
|---|---|
| target flow + role/authority table (§1.2–1.3) | §1 |
| the plan's five contradictory sentences with line numbers 60/233/284/511/621/650 (§3.7) | §4 — the most actionable item either document produced |
| the seal has a **second producer** — `acceptance_defect.correct` passes a caller-supplied graph into `mint_seal` (§6.1) | §6.5 — verified; better justification than "a future caller" |
| `SCHEMA_VERSION` bump is free because no production seal exists (§6.3) | §7 S2, with the check `len(selectors)+len(attested)==contracts_total` added |
| "what not to do" hygiene list (§7.4) | §9, corrected |
| documentation-first ratification phase with a DoD (§8 Phase 1) | §7 S6 + §12 |
| "built twice as long as it has been wired" (§7.1) | §2, §5 |
| `protected_paths` phrasing (§3.12) | §6.4 — checking it produced the nesting finding |

### 11.2 Rejected, with reasons

| Its claim | Why rejected |
|---|---|
| "A `HARD` invariant can be converted to a human signature **by the planner choosing `NON_EXECUTABLE`**" (§3.3) | the grant is the caller's: `bind_dispositions` refuses `disposition-undeclared` and `contract_evidence` requires `owner is not None`. The planner selects *which claim* carries an attestation, not whether one exists. Load-bearing: it drives their P1 alarm and their §5.3 answer |
| "`SOFT` = not admission-gating (same discharge rule)" (§5.3) | a severity claim with no consumer — the P1 defect restated. The document names the disease and prescribes a milder form of it (§3.5) |
| one PR containing doc rewrite + parser policy + repair geometry + CLI (§7.3) | correct for the doc triad, wrong for the rest: unreviewable diff, unbisectable, couples documentation to three behaviour changes |
| seal records an `uncovered` field that "is always empty after 6.1" (§6.3) | a field that can only be empty is weaker than a refusal + counter: a future producer that skips the rule would write `uncovered: [..]` and every consumer would have to handle it (§6.5) |
| new rule name `contract-uncovered` (§6.1) | the closed vocabulary already has `hard-contract-without-executable-evidence`; rename one entry rather than add one |
| "two encoding tests … the only encoding of the SOFT exemption" (§3.10) | three (§6.5 twin at `test_ai_native_acceptance_bundle.py:493`); the diff would surprise the implementer |
| rule phrased as "declares `TEST_REQUIRED` and has neither a selector nor a disposition" (§6.1) | `TEST_REQUIRED` cannot carry a disposition — `_build_invariant` refuses `disposition-without-non-executable`; the clause is unreachable. State the rule per evidence mode |
| `grep "ready" src/fa/ → 0 hits` (§3.5) | false as written (`ReadyState`, `READY`); the true claim is narrower: no *contract-readiness* concept exists |
| test counts 45/30/26 (§1.4, §11) | not reproducible as stated (`def test_` scan → 44/25). A decision document should carry the method, not a number a reader cannot regenerate |
| Phase 3 puts seal wiring first without a collection probe (§8) | `mint_seal` needs `collected` nodeids from running the sealed bytes; that integration point is unproven (§7 S0) |
| "the seal refusal is a different invariant, not duplication" (§7.4.5) | better framed as *the seal's own serialization invariant, enforced at every mint* — same coverage of the defect path, without inviting "which gate is authoritative?" |

### 11.3 Corrections to this document's own v2 draft

| # | v2 said | v3 |
|---|---|---|
| 1 | "the author does not choose it" (dispositions) | the caller grants a **reason**; the planner selects **which claim** carries it — stated as a residual with a cheap mitigation (§3.6) |
| 2 | S3 mode A is "cheap, one tuple" | it is *more urgent* than that: coder confinement is topology-dependent today (§6.4) |
| 3 | "defence in depth against a future caller" (seal refusal) | there is an **existing** second producer: `acceptance_defect.correct` (§6.5) |
| 4 | plan contradictions cited only as §2/§8 | the five sentences with line numbers (§4) |

---

## 12. Ratification checklist (ready to paste)

**D-V2-10 — evidence totality.** Every contract has exactly one discharge mode: a selector resolving to exactly one nodeid in the sealed closure, or a caller-granted typed disposition. `KIND` is not an exemption and is deleted from the MVP grammar (reintroduced only as a separately consumed `SEVERITY`). `PRESERVATION` is never dispositionable. `HARD + NON_EXECUTABLE` stays legal **only** with a bound caller grant. Admission is the single gate; the seal re-asserts the consequence at every mint (refuse `UNCOVERED`, refuse an unbound request) and records `contracts_total`/`attested`/`uncovered` with `len(selectors)+len(attested)==contracts_total`. Strike "ready CT" (no runtime meaning).

**D-V2-11 — grammar conformance.** One machine-readable grammar table is the source for parser rules, the canonical document's grammar block, the skills' conformance test and the prompt's worked example; `ADMISSION_RULES_V2` gains the `plan-v2` namespace and V2-shaped contract ids (`CT-1.1`). The doc triad (schema + skills + conformance tests) changes atomically; the prompt example must parse in a test.

**Repair and escalation.** `acceptance/tests/` joins the repair allowlist; the repair task text carries the parser's precise rule; `disposition-undeclared` becomes non-repairable and maps to `disposition_required` (retryable); `--dispositions` gains a CLI ingress as part of the same ratified set.

**Plan consistency.** Delete the strict line-60 reading; align lines 233/284/511 with D-V2-10; resolve the Q-V2-ACC-2 row; correct §8 step 4; record Q-V2-ACC-1 as closed-by-code with the transitive half as a named residual.

**Q-V2-ACC-2 — RESOLVED** by D-V2-10 with the behaviour table in §3.2 as the accepted answer: a plan that declares `TEST_REQUIRED` and covers nothing does **not** reach the coder, does **not** need a waiver, and returns to the planner with an actionable rule name or ends `BLOCKED` with the project present and unadmitted.

---

## 13. Corrections landed in the plan (2026-11-22, E605)

The plan was edited where it contradicted itself, before any implementation, so the next slice follows one rule
instead of five. Documentation only; no production code changed.

- **Header** now carries a dated correction note naming every change and why, so the next reader does not have to
  diff two drafts to learn that the rule changed.
- **One evidence rule in all five places** (grammar delta, §2 "production grammar", INV-05, CT-3.1, §8 step 4):
  every CT is discharged exactly once; `KIND` is not an exemption; the phrase "ready CT" is gone.
- **`KIND` deleted from the grammar** (D-V2-10), including the grammar skeleton block; severity is deferred to a
  future `SEVERITY` field with its own consumer.
- **Q-V2-ACC-2 = RESOLVED** with the decision, the `HARD + NON_EXECUTABLE` residual and its mitigation. §8 step 4 no
  longer claims ACC-1/2 are closed, and no longer calls Q-V2-MODEA-1 open after D-V2-6 answered it.
- **D-V2-10 and D-V2-11** added to the ratified-decision table; **six defect rows P4-1…P4-6** added to §12
  (un-granted binding, seal blindness plus its second producer, repair geometry, coder-confinement topology,
  `KIND`'s sole exempting reader, the missing `--dispositions` ingress).
- **Five stale citations fixed** (`parse_plan:674`, `_admit_published_project:3141`,
  `_validate_plan_admission:3427` / `_validate_v2_admission:3476`, `_run_stage:1601` with its coder gate at `:1634`,
  the acceptance bank's 45 tests) plus the SLICE2 paragraph that still described the deleted payload route as *today*
  (P2-4), the duplicated §5 number, and the out-of-order §11/§12.

**What this edit does not ratify** — worth stating, because editing the plan is how this project ratifies policy:
nothing in S0 (whether the managed executor can collect and run a project test under `worklogs/<slug>/acceptance/`
is still unmeasured, and §8 keeps it as SLICE3's first step); nothing about severity *existing* (only that it may not
gate evidence); and none of S1/S2's code, which is the next slice rather than a consequence of this document.

## 14. Next slice, chosen

S1 policy closure → **S2** seal totality → S0 probe → S3 mode A. The exact task list lives in the plan, §8
"Next slice, decided 2026-11-22" — one source of truth, not two. The ordering rationale in one line each: S1 before
S2 because a seal must not certify a graph admission will later reject; S2 before S0 because the probe only proves
*where* the closure runs, not that its result is trustworthy; S0 before any SLICE3 wiring because a closure that
cannot be collected at the new path makes the wiring pointless; S3 next because P4-4 showed confinement currently
depends on the launch topology, so "the coder cannot edit its tests" is true on one supported route and false on
another.

## Appendix A — reproductions

```text
# 1. The evidence matrix today (plan_v2 is stdlib-only; no pytest needed)
#    load src/fa/inner_loop/plan_v2.py via importlib, build a two-contract document, then:
#    parse_plan(...)            -> SOFT+TEST_REQUIRED uncovered: admitted
#    contract_evidence(graph)   -> {'CT-1.1': EXECUTABLE, 'CT-1.2': UNCOVERED}
#    HARD+TEST_REQUIRED uncovered -> PlanV2Error('hard-contract-without-executable-evidence')

# 2. Patch blast radius: copy plan_v2.py, delete `if invariant.kind != "HARD": continue`,
#    rename the rule, run the five cases in §3.4 -> exactly one cell changes.

# 3. Un-granted request:  bind_dispositions(graph, (), today=date(2026,11,22))
#    -> PlanRefError('disposition-undeclared')      # the library refuses
#    ... and the controller never calls it when no grants were supplied (workflow_controller.py:3209).

# 4. Seal blindness: mint_seal over that graph (acceptance root needs pytest.ini + one test)
#    -> attested == (), selectors CTs == ['CT-1.1'], "CT-1.2" not in json.dumps(record)

# 5. Coder confinement: cli.py:2165 (purpose from nesting) + workspace.py:2844–2854
#    (PROJECT purpose = no confinement) + profiles.py:123–137 (coder holds fs_write_file).
```

Search anchors: `grep -rn "invariant.kind" src/fa` → 1 · `grep -rn AcceptanceBundle workflow_controller.py` → 0 ·
`grep -c -- "KIND:" artifact-schema-and-grammar.md` → 0 · `grep -rl "AI-NATIVE-PLAN-V2" worklogs/` → 0 projects.
