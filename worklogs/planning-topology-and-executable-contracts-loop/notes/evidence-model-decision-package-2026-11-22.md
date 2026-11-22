# Evidence-model decision package — invoke_workflow / PLAN-V2

> **SUPERSEDED 2026-11-22 (E604).** Consolidated into the single final package:
> [evidence-model-final-decision-package-2026-11-22.md](evidence-model-final-decision-package-2026-11-22.md).
> Everything here is superseded; do not read this as the governing document.


**Date:** 2026-11-22<br>
**Status:** decision-ready context. Read-only. Not an implementation.<br>
**Scope:** the V2 evidence/admission model — `plan_v2.py`, `plan_admission.py`, `acceptance_bundle.py`, `acceptance_collection.py`, `acceptance_defect.py`, `kill_attribution.py`, `workflow_controller.py`, CLI, canonical schema, skills.<br>
**Audience:** the operator making final decisions. Every open item names its owner and the exact question.

---

## 0. Purpose of this document

This is the single read-me for the open question behind Q-V2-ACC-2 (evidence coverage) and its adjacent defects. It exists so that:

- No one re-discovers the four measured facts on the way to a decision (they are in §3).
- The plan's internal contradictions are on the table before anyone leans on them (§4).
- Every recommendation is labelled **judgment, not ratified decision** (§5).
- Implementation order is explicit and honest about what is blocking what (§6).

It does not replace the plan. It is the decision context for the plan's Q-V2-ACC-2 + SLICE3.

---

## 1. How the system works — and what is actually landed

### 1.1. The pipeline (target state, as designed)

```text
chat → invoke_workflow (CREATE_NEW)
  → slug validated (tool boundary, before any child exists)
  → planner stage: WRITE PROJECT view (worklogs/<slug>/)
       harness writes scaffold (empty documents)
       planner writes documents + acceptance/tests/** + notes
  → STOP_VIEW → SEAL → PUBLISH  (one revision)
  → metadata check (D-V2-9.3: closed table, identity/status/created)
  → parse_plan (grammar + graph cardinalities + evidence)
  → bind_dispositions (caller grant; owner/evidence/reviewed_at)
  → metadata + parse are the admission gates → coder
  → verifier (sealed closure, managed cell)
  → terminal result
```

### 1.2. What is actually landed (verified 2026-11-22)

| Layer | Landed? | Evidence |
|---|---|---|
| V2 parser `parse_plan` + `contract_evidence` + `attested_contracts` + `resolve_selectors` | **Yes** | `tests/test_ai_native_plan_v2.py` — 45 tests; 22 killed mutants (per plan §5) |
| V2 admission route (`_validate_v2_admission`, `snapshot_from_bytes(format=PLAN_V2)`) | **Yes** | `workflow_controller.py:3427-3478`, `plan_admission.py:260+` |
| Payload layer (render/install) | **Deleted** | `plan_semantics.py` is absent; `CREATE_NEW_PROJECT` dispatch exists |
| Scaffold writer + planner-as-writer + metadata cross-check (D-V2-9) | **Yes** | `test_ai_native_bootstrap.py` — 26 tests |
| `project_exists` mapping (D-V2-9.2) | **Yes** | `CT-2.7` tests |
| Repair stage (D-V2-9.8) | **Yes** — but narrow allowlist | `workflow_controller.py:3047-3057` |
| Seal mint wiring (CT-2.4) | **No** | zero `AcceptanceBundle` refs in `workflow_controller.py` (grep-verified) |
| Mode-A projection (CT-3.3) | **No** | `protected_paths` carries only `plan_ref.workspace_relative_path`; closure unprotected |
| Verifier uses sealed closure (CT-3.6) | **No** | planner `verify` fence still executes (`slice_verification.py:552`) |
| AcceptanceBundle / custody / attribution / TEST-DEFECT | **Yes, as library** | `tests/test_ai_native_acceptance_bundle.py` (45), `test_ai_native_acceptance_closure.py` (30) — zero production consumers |
| CLI `--dispositions` | **No** | `--project-action`/`--project-slug` only (`cli.py:999-1001`) |
| Canonical schema = V2 (SLICE1) | **No** | schema file still teaches `TESTS:` + `verify` fences; skills still teach `TESTS:` |
| §8 step 4 "Q-V2-ACC-1/2 are closed" | **No — false** | Q-V2-ACC-2 row is BLOCKING (§4) |

---

## 2. What the system is for — and what it is not

### 2.1. The one sentence

**An artifact produced by an AI must be checked by something other than the AI that produced it — and that check cannot be talked around.**

### 2.2. What this buys (mechanism → property)

| Mechanism | Property |
|---|---|
| Planner ≠ coder (different stages, different capabilities) | Author of the claim ≠ author of the proof |
| `INV → CT → TEST-ID → selector → one nodeid` | Every claim maps to an executable check, or it is refused |
| Seal: plan bytes + revision + closure digest | The check that ran is the check that was reviewed |
| `MUTATION` view confined to `{src, scripts}` | Coder cannot rewrite the tests it must pass |
| Managed verifier cell | The proof is produced where the author does not control the environment |
| `ToolResult.fail` on settled create failure | "Finished" and "created" are one statement |

### 2.3. The six values that make the system worth building

1. **Independence of evidence from the author of the claim.** The root property.
2. **Fail-closed, not fail-open.** No silent success; every refusal is structured and stable.
3. **Small verifiable steps.** One claim → one check, no wide routes around.
4. **Repair without losing evidence.** Repair is a bounded loop, not a silence blanket; old evidence is preserved.
5. **Audit trail.** Seal, ledger, projection — who/what/where/when, recorded.
6. **Minimalism toward new mechanisms.** New machinery only when the existing substrate is exhausted. (The STEP9A seal stack is the cautionary example: built as a library, never wired into production.)

### 2.4. The critical honesty point

Values 1 and 2 are **not currently true in production**, for the reason that CT-2.4 is absent: nothing mints a seal, nothing enforces closure custody before the coder, and nothing routes verification through the sealed closure. The system **looks** intact — seals mint in tests, verifiers run, verdicts print — while the chain that actually protects the coder has no production path. This is not a code bug; it is a wiring gap, and it is exactly the class of gap the plan calls out (§5 E564 table).

---

## 3. Measured findings (all re-measured 2026-11-22)

### 3.1. The four facts (validated by execution on this branch)

| # | Finding | Measured result | Source |
|---|---|---|---|
| 1 | `KIND` is read in exactly one place | `plan_v2.py:622` — only to decide whether to refuse. `grep -rn "invariant.kind\|item.kind" src/fa/` → 1 hit | `plan_v2.py` |
| 1 | SOFT + TEST_REQUIRED, no selector | admitted; `contract_evidence["CT-1.2"] = UNCOVERED` | execution |
| 2 | HARD + NON_EXECUTABLE + reason | admitted; after `bind_dispositions` → `ATTESTED`; enters `seal.attested` | execution |
| 3 | Seal does not carry a contract count | `mint_seal` over UNCOVERED graph mints fine; no `contract_total`/`uncovered` fields | execution + `_record()` |
| 4 | "ready CT" has no runtime meaning | 0 hits in `src/fa/`; the phrase appears in plan line 60, 233, 284, 511, 621 | grep |

### 3.2. Additional findings (this pass)

| # | Finding | Evidence |
|---|---|---|
| D1 | Plan contradicts itself: §8 step 4 says "Q-V2-ACC-1/2 are closed"; the Q-V2-ACC-2 row is BLOCKING with no resolution | `plan-v2:650` vs `:621` |
| D2 | STEP9A seal stack is a library, not a production path — `mint_seal`/`sealed_collection_argv`/`acceptance_collection`/`acceptance_defect`/`kill_attribution` all unwired; controller has zero `AcceptanceBundle` refs | grep |
| D3 | Repair allowlist is increment + open-questions only (`workflow_controller.py:3047-3057`) — a coverage gap requiring a test file **cannot be repaired** by the repair stage | code + tests `test_a_create_new_repair_may_write_only_the_documents_admission_read` |
| D4 | CT-2.4's named test is absent; CT-2.6 (prompt) is done | `plan-v2:517`, `grep tests/` |
| D5 | CLI `fa invoke-workflow` drops `dispositions` — a legal V2 plan is unreachable from the human front | `cli.py:999-1001` vs `workflow_tool.py:245` |
| D6 | Planner `verify` fence still executes on the PLAN-V2 route | `slice_verification.py:552` |
| D7 | `protected_paths` carries only the plan file; `worklogs/<slug>/acceptance/` unprotected | `workspace.py:2191-2199`, `:2810-2819` |
| D8 | **Parse refusals surface to repair as `bootstrap-invalid-metadata`** — a coverage refusal would be misdiagnosed to the planner | `workflow_controller.py` `_admit_published_project` (the `snapshot.format_error is not None` branch) |
| D9 | The two encoding tests pin the OLD policy | `test_a_soft_invariant_may_still_stay_uncovered` (line 819), `test_a_contract_with_neither_a_selector_nor_a_disposition_is_uncovered` (line 720) |
| D10 | Planner-authored `verify` fences on V2: the verifier path is currently the V1 fence path | `slice_verification.py:552` |

### 3.3. What is NOT claimed

- No production change was made in this analysis (read-only).
- No test suite was run — no Python 3.13 toolchain is available in this sandbox. All measurements were performed by executing the production modules directly (parser, admission, mint_seal) with synthetic fixtures.

---

## 4. The real question — and why it is not "where to refuse"

### 4.1. The plan contradicts itself on the exact point that matters

| Site | Statement | Reading |
|---|---|---|
| Line 60 (grammar delta) | "only HARD blocks ready/admission, and `NON_EXECUTABLE` is **forbidden for HARD/ready contracts** unless Q-V2-ACC-2 is resolved under a ratified rule" | Strict |
| Line 233 (grammar requirement) | "every hard INV/ready CT has **a test or a typed explicit evidence disposition**" | Loose |
| Line 284 (INV-05) | "Every admitted hard invariant/ready CT has **an explicit evidence disposition** and complete ID graph" | Loose |
| Line 511 (CT-3.1) | "hard invariant/ready CT must have executable evidence or **explicit reviewed disposition**" | Middle |
| Line 621 (Q-V2-ACC-2 row) | "choose either (A) every hard INV/ready CT needs an executable assertion, or (B) permit typed NON_EXECUTABLE only under an already-ratified disposition rule" | **Pending** |
| Line 650 (§8 step 4) | "Q-V2-ACC-1/2 are closed" | **False** |

Three readings coexist. No reading is derived from a resolved disposition. This is why the question appeared answerable and was not.

### 4.2. The honest reframing

The question is not "where to refuse UNCOVERED". That is a routing question with a wrong answer (a second gate instead of a first). The question is: **what does `KIND` oblige?**

The plan defines no meaning for `KIND` beyond "HARD blocks admission when the contract has no test". There is no meaning for SOFT. There is no meaning for "ready". Hence:

- The only fully mechanical rule that enforces the grammar's own promise: **a contract whose invariant declares `EVIDENCE: TEST_REQUIRED` and which has neither a selector nor a disposition must be refused at admission** — for every KIND. This is not a new policy; it is the enforcement of what the grammar already says (EVIDENCE: TEST_REQUIRED means "must be proven by a test").
- HARD + NON_EXECUTABLE: **the plan is silent/contradictory**; this is a ratification decision. My recommendation is to **allow it** (INV-05's own "explicit evidence disposition" wording is the ratified pipeline — typed, one-shot, time-boxed, grant-bound). This is a judgment, not a ratified decision — see §5.
- The seal must **record** the coverage map (covered/attested/uncovered) so coverage is auditable from bytes — even when the uncovered set is empty by construction. This is auditability, not policy.
- The repair geometry and CLI ingress are ordinary defects with bounded fixes.

### 4.3. The genuine residual open question

What `HARD` means to the coder:

- Current code: HARD = "blocks admission" only (the `_admit_evidence` exemption). No loop-side effect.
- If SOFT means "not admission-gating", the natural semantics (HARD = admission-gating, SOFT = not) gives KIND real meaning without inventing a new subsystem.
- This is the one semantic change worth ratifying explicitly. It is a one-paragraph line in the plan + one row in the schema.

---

## 5. Decision requests — what the operator must decide

These are numbered so each can be ratified independently. **My recommendation is labelled judgment; nothing here is ratified.**

### Decision 1 — admission rule for uncovered TEST_REQUIRED (any KIND)

**Question:** Is a SOFT/HARD contract that declares `EVIDENCE: TEST_REQUIRED` and carries neither an executable test nor an owner-bound disposition refused at admission?

| | TIGHT (my recommendation) | LOOSE |
|---|---|---|
| Rule | Refused at admission (`contract-uncovered`) | Admitted; `UNCOVERED` is legal and recorded as such |
| Rationale | The grammar promises a test; unfulfilled is a broken plan | The plan's literal design ("only HARD blocks") |
| Cost | Two encoding tests flip (§3.2 D9); repair must widen allowlist (D3); repair needs honest diagnostics (D8) | Zero |
| Risk option | Blocks repair loop on content gap unless D3 is fixed | Allows broken plans to ship |

**My recommendation: TIGHT.** Rationale: under the grammar's own words, `TEST_REQUIRED` is a claim the plan does not make if unfulfilled. The SOFT exemption was an implementation gap, not a ratified decision.

### Decision 2 — HARD + NON_EXECUTABLE

**Question:** Is a HARD invariant allowed to request a typed NON_EXECUTABLE disposition through the ratified pipeline?

| | ALLOW (my recommendation) | REFUSE (strict reading) |
|---|---|---|
| Plan text | Line 233/284 permits it; line 60 prohibits it | Line 60 prohibits it |
| Semantics | Host readiness / deployment identity / owner approval / power-loss are genuinely untestable in the sandbox | Only HARD contracts with tests ship |
| Risk | Any HARD invariant can be converted to human signature — the strictest class becomes the easiest to waive | Plan unsatisfiable for host-gated invariants |
| Cost | None new — the pipeline already exists | Line 60 must be deleted or amended — this is plan hygiene |

**My recommendation: ALLOW,** per INV-05's own wording. Delete the line-60 strict reading from the plan. Record D-V2-10: this is a ratified decision, not a code change.

### Decision 3 — seal coverage map

**Question:** Does the seal record the contract count + coverage map?

| | YES (my recommendation) | NO |
|---|---|---|
| Effect | A seal is auditable without the plan graph; a future regression that reintroduces `UNCOVERED` is detectable from bytes | Seal stays minimal |
| Cost | One field + schema_version bump (none needed — no production seals exist, load_seal refuses unknown versions so bump freely) | Zero |
| Risk | Cleaner contract, zero migration cost | Consumer cannot distinguish covered-from-uncovered |

**My recommendation: YES** — record `contract_total`, `covered`, `attested`, `uncovered` (uncovered always empty after Decision 1, which is the point). This is not a new mechanism; it is a field.

### Decision 4 — repair geometry for coverage refusals

**Question:** When admission refuses a coverage gap, is the refusal repairable?

| | WIDEN (my recommendation) | NON-REPAIRABLE |
|---|---|---|
| Effect | Repair writes the missing test file; admission re-validates | Run ends BLOCKED with operator-facing diagnostics |
| Cost | Repair allowlist changes by the refusal family; `_repair_stage_task` text changes; `test_a_create_new_repair_may_write_only_the_documents_admission_read` updates; D8 diagnostic mapping added | None — existing behaviour |
| Risk | New behavior is bounded (the allowlist narrows again per-family, not wider) | Repair budget silently burned on a gap it cannot fix |

**My recommendation: WIDEN** — but only for content refusals, with a diagnostic-family-scoped allowlist. This keeps repair's purpose ("the plan is incomplete, fix it") honest.

### Decision 5 — CLI `--dispositions` ingress

**Question:** Does the CLI accept `--dispositions <path-or-json>` as an unmodified pass-through?

| | YES (my recommendation) | NO (defer) |
|---|---|---|
| Effect | A legal V2 plan is reachable from the human front | Only the chat/agent path |
| Cost | Same bounded edit as `--project-action`/`--project-slug`; one test | Zero |
| Risk | Minimal — validation stays in the tool | A legal plan is unreachable from the CLI |

**My recommendation: YES.** Land it with the evidence fix.

### Decision 6 — the schema rewrite (V1→V2)

**Question:** Does the canonical schema become V2, with skills + conformance tests in the same commit?

| | YES (my recommendation) | NO |
|---|---|---|
| Effect | The grammar's source of truth matches the parser | Every new contract designs against a doc that cannot answer its own questions |
| Cost | One document + 3 skills + 4 conformance tests + plan §5/§10/§11 link fixes | Zero (documentation only) |
| Risk | Irreversible semantics — the decision commit carries it | The exact drift E601 warns about |

**My recommendation: YES as the first actual work item**, and as **one coherent change set** with the grammar fix (Decisions 1-2). Do not land the schema alone first.

### Decision 7 — the plan's internal consistency (documentation)

- Delete line 60 strict reading or align it with INV-05.
- Replace "ready CT" with a precise statement: "a contract that gates admission".
- Fix §8 step 4 ("Q-V2-ACC-1/2 are closed").
- Resolve the Q-V2-ACC-2 row in the plan with the ratified answers from Decisions 1-2.
- Record D-V2-10: the evidence rule + repair geometry + schema rewrite as one ratified change set.

**My recommendation: do this first, as documentation, before any code.**

### Q-V2-ACC-1 (test closure)

| | Budget half (512 files, 4 MiB/file, 16 MiB aggregate, 4096 chars, depth 64, symlink/hidden/nested-conftest/hardlink/uid refusals, pytest_argv pins) | Transitive-import half (sealed test imports outside `acceptance/`) |
|---|---|---|
| Status | **Closed-by-code, 30 tests** (`test_ai_native_acceptance_closure.py`) | **Named residual, not a closable gate** — on the MUTATION route the verifier imports the current candidate by design (CT-3.6); a sealed closure cannot statically bound the import graph without a hash-only sidecar the plan refuses |

**My recommendation:** record the budget half as closed in the plan's Q-V2-ACC-1 row; file the transitive half as the named residual it is. Do not present it as a blocker.

---

## 6. Implementation order — explicit dependencies

### Phase 1 — documentation + ratification (no code)

| Step | Work | Blocks |
|---|---|---|
| 1.1 | Scheme rewrite + delete "ready CT" + fix §8 step 4 + resolve Q-V2-ACC-2 row + D-V2-10 | All SLICE1/3 work |
| 1.2 | Skills + 4 conformance tests in the same commit | 1.1 |
| 1.3 | Record ACC-1 budget half as closed | §8 step 4 |

**DoD:** the plan, the schema, and the skills agree byte-for-byte; the operator has ratified Decisions 1-2.

### Phase 2 — the evidence fix (one coherent commit, or one PR)

| Step | Work |
|---|---|
| 2.1 | `_admit_evidence`: refuse any TEST_REQUIRED-covered-less contract (both KINDs); `contract-uncovered` |
| 2.2 | Seal: `contract_total` + coverage map; refuse UNCOVERED with closed rule `uncovered-contract`; schema_version bump |
| 2.3 | Rewrite the two encoding tests (D9) |
| 2.4 | Repair: family-scoped allowlist (acceptance/tests/** for content gaps); `_repair_stage_task` text; D8 diagnostic mapping |
| 2.5 | CLI: `--dispositions` (Decision 5) |
| 2.6 | `HARD`+NON_EXECUTABLE: no code path change (already admitted — refused nothing today for this); delete the strict reading from the plan (Decision 2) |

**DoD:** parse refuses the previously-admitted cases; seal refuses an uncovered graph; repair fixes a coverage gap (a test that adds an acceptance file in the repair stage); two encoding tests rewritten; no production caller of the seal yet (CT-2.4/3.6 still open).

**Do NOT test against a sealed graph with coverage already refused at admission** — write the seal-side test directly against a caller-supplied graph (the defect re-mint path), not the normal path.

### Phase 3 — SLICE2/3 wiring (dependencies, not order of preference)

| # | Work | Notes |
|---|---|---|
| 3.1 | CT-2.4 — seal mint in the controller (publish→seal, D-V2-5 on the D-V2-9 revision) | **First.** Everything else waits |
| 3.2 | CT-3.3 — mode-A projection (protected paths + acceptance closure) | D-V2-6 |
| 3.3 | CT-3.6 — verifier uses sealed closure; retire planner fence on PLAN-V2 route | D3.6 |
| 3.4 | CT-3.2 — seal materialization into the verifier path (`sealed_collection_argv` wiring) | After 3.1 |
| 3.5 | CT-3.1 — graph + nodeid edges (after Phase 1/2 ratify ACC-2) | Currently BLOCKING |
| 3.6 | CT-3.4/3.5 — attribution, TEST-DEFECT (after seal mint) |  |

### What is NOT in this package

- No code changes.
- No plan changes without operator ratification (Step 4.1 is a decision; it is documented, not shipped).
- No claim that SLICE4/5 can start. The status-tick design gate (§2 of the plan) blocks SLICE4 independently.

---

## 7. What NOT to do

1. **Do not** declare HARD+NON_EXECUTABLE a bug fix. It is a ratification. (Corrects the overstatement in the E601 audit and in this document's earlier draft.)
2. **Do not** land the schema rewrite as a separate PR from the grammar fix. Two sources of truth = the original defect.
3. **Do not** widen the repair allowlist without the diagnostic mapping. The repair stage gets the planner the wrong rule today (D8).
4. **Do not** treat the two encoding tests as "old code to delete". They are the only existing encoding of the SOFT exemption; deleting them silently removes the only statement of what SOFT was for.
5. **Do not** treat the seal-side refusal as a "two gates" annoyance. It is defense for the defect re-mint path, which mints from a graph admission never saw. Different paths, different invariants.
6. **Do not** present the transitive-import half of ACC-1 as closable. It is a named residual.
7. **Do not** claim SLICE4/5 can start before the status-tick design gate and ACC-2 ratification resolve. They cannot.
8. **Do not** expand the existing repair budget to absorb coverage failures. That is the D3 finding; budget exhaustion with a clear, actionable diagnostic is correct behavior for unfixable gaps.

---

## 8. Honest limitations of this analysis

- The test suite was not run in this pass (no Python 3.13 toolchain available). Measurements were performed by executing the production modules directly (parse, bind, mint) with synthetic fixtures; grep-verified structural facts. Those measurements are cited as "verified" with their method.
- No decision here is ratified. Decisions 1-2 and the schema rewrite are editorial ratifications the operator must make. This document exists to make that cheap.
- The plan's §8 step 4 is **false** (ACC-1/2 are not closed). It is corrected in this document; the plan's own edit is out of this document's scope.

---

## 9. Appendix — what this analysis measured, in order

1. `grep -rn "invariant.kind\|item.kind" src/fa/ --include=*.py` → 1 hit (`plan_v2.py:622`). KIND is read once, only to exempt.
2. Execution: SOFT + TEST_REQUIRED + no selector → admitted; `contract_evidence["CT-1.2"] = UNCOVERED`.
3. Execution: HARD + NON_EXECUTABLE + reason → admitted; after `bind_dispositions` → `ATTESTED`, `attested_contracts == ("CT-1.2",)`.
4. Execution: `mint_seal` over UNCOVERED graph → mints fine; no contract count in the record; shape-identical to a fully-covered seal.
5. Grep: "ready" in `src/fa/` → 0 hits (excluding `ReadyState`/`READY` status).
6. Grep: zero `AcceptanceBundle` refs in `workflow_controller.py`; zero outside the STEP9A modules.
7. Read: `_repair_allowlist` = increment + open-questions only (`workflow_controller.py:3047-3057`).
8. Read: parse refusals surface as `bootstrap-invalid-metadata` to repair (`workflow_controller.py`, `_admit_published_project`).
9. Read: two encoding tests pin the SOFT exemption (`tests/test_ai_native_plan_v2.py:720`, `:819`).
10. Read: `slice_verification.py:552` executes planner verify fence shell=True.
11. Read: `protected_paths` carries only `plan_ref.workspace_relative_path` (`workspace.py:2191-2196`, `:2810-2819`).
12. Read: CLI invoke-workflow has no `--dispositions` (`cli.py:999-1001`); tool schema has the field (`workflow_tool.py:245`).
13. Read: plan §8 step 4 says ACC-1/2 closed (false); Q-V2-ACC-2 row is BLOCKING; line 60/233/284/511/621 — five sites with three readings.
