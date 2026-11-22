# Evidence model — consolidated decision package

**Date:** 2026-11-22<br>
**Status:** decision-ready context. Read-only analysis; NO production changes in this document.<br>
**Audience:** the next agent (or operator) making the final decisions. Self-contained.<br>
**Scope:** the PLAN-V2 evidence/admission model and its wiring: `plan_v2.py`, `plan_admission.py`, `acceptance_bundle.py`, `acceptance_collection.py`, `acceptance_defect.py`, `kill_attribution.py`, `workflow_controller.py`, `cli.py`, `slice_verification.py`, the canonical schema, skills, the plan.<br>
**Supersedes:** `q-v2-acc2-expert-opinion-2026-11-22.md` (E602, with errors corrected) and `evidence-model-decision-package-2026-11-22.md` (E603, the earlier draft).<br>

---

## 0. Purpose — for this document

This is the ONE consolidated reference for the open question behind Q-V2-ACC-2 and its adjacent defects. It exists to:

- give the next agent the full picture without re-deriving it (§1–§3);
- list the problems with precise classification (§4);
- frame the real question honestly (§5);
- state the proposed paths of solution, with costs and risks (§6);
- state the expert opinion on the global problem (§7);
- give the implementation order with DoDs (§8);
- make the ratification points explicit (§9);
- record what is NOT verified (§10);
- cite every claim to a line, a test, or an execution (§11);

It makes NO decision on its own. Every recommendation is labelled as judgment; the operator ratifies.

---

## 1. What the system is — and why it exists

### 1.1. The one sentence

> An artifact produced by an AI must be checked by something other than the AI that produced it — and that check cannot be talked around.

### 1.2. How the system works (target state)

```text
chat → invoke_workflow(project_action=CREATE_NEW, project_slug=<validated slug>)
  → tool boundary validates slug before any child exists (invalid_project_slug / invalid_project_action)
  → harness opens WRITE PROJECT view (worklogs/<slug>/), writes the scaffold
  → planner authors documents: roadmap.md, increments/increment-01-initial-plan.md,
    open-questions.md, ledger.md, acceptance/tests/**, notes/, reviews/
  → STOP_VIEW → SEAL → PUBLISH  (one revision, D-V2-9)
  → metadata cross-check (D-V2-9.3: identity fields, status vocabulary, created)
  → parse_plan (grammar + graph cardinalities + evidence rules)
  → bind_dispositions (caller grant → owner/evidence/reviewed_at; R1: plan requests, caller grants)
  → admission gate → coder dispatches (mode A: closure read-only)
  → verifier executes the sealed closure in a managed cell
  → terminal result (only exit 0 + DONE + refreshed revision = ok)
```

### 1.3. The roles and authority split

| Role | Owns | Does not own |
|---|---|---|
| Planner (AI) | semantic content: roadmap/increment/acceptance content/selectors/questions | scaffold bytes, scaffold identity, seal |
| Harness/controller | scaffold, metadata cross-check, admission, seal minting, status ticks, structured outcomes | planner semantic bytes |
| Coder (AI) | implementation under admitted behavior, internal seams | sealed plan bytes, sealed acceptance closure, tests |
| Verifier/eval | evidence of the sealed closure, classification | plan or test bytes |

### 1.4. What is actually landed (verified 2026-11-22 — not assumed from the plan)

| Layer | Status | Evidence |
|---|---|---|
| V2 parser `parse_plan` + `contract_evidence` + `attested_contracts` + `resolve_selectors` | **Landed** | `tests/test_ai_native_plan_v2.py` — 45 tests |
| V2 admission route (`_validate_v2_admission`, `snapshot_from_bytes(format=PLAN_V2)`) | **Landed** | `workflow_controller.py:3427-3478`, `plan_admission.py` |
| Payload layer (render/install) — **deleted** | **Landed** | `plan_semantics.py` absent |
| Scaffold writer + planner-as-writer + metadata cross-check (D-V2-9) | **Landed** | 26 tests, `test_ai_native_bootstrap.py` |
| `project_exists` mapping (D-V2-9.2) | **Landed** | CT-2.7 tests |
| Repair stage (D-V2-9.8) | **Landed** — narrow allowlist (see §4 P4) | `workflow_controller.py:3047-3057` |
| Seal mint wiring (CT-2.4) | **NOT landed** — controller has zero `AcceptanceBundle` refs | grep-verified |
| Mode-A closure projection (CT-3.3) | **NOT landed** — `protected_paths` carries only the plan file | `workspace.py:2191-2199`, `:2810-2819` |
| Verifier sealed-closure path (CT-3.6) | **NOT landed** — planner verify fence still executes (`slice_verification.py:552`) | grep-verified |
| AcceptanceBundle / custody / attribution / TEST-DEFECT | **Landed as library** — zero production consumers | `tests/test_ai_native_acceptance_bundle.py` (45), `test_ai_native_acceptance_closure.py` (30) |
| CLI `--dispositions` | **NOT landed** | `fa invoke-workflow` forwards only task/roles/mode/project_action/project_slug |
| Canonical schema = V2 | **NOT landed** — schema still teaches `TESTS:` + verify fences; skills still teach `TESTS:` | `artifact-schema-and-grammar.md`, 2 skills, 4 conformance test files |
| §8 step 4 "Q-V2-ACC-1/2 are closed" | **False** | Q-V2-ACC-2 row is BLOCKING |

---

## 2. Why the evidence model is the load-bearing piece

### 2.1. The system is not "an AI that writes code"

The value is that a claim CANNOT be talked around. Every mechanism in the system exists to make that one property true:

| Mechanism | Property |
|---|---|
| Planner ≠ coder (different stages) | Author of the claim ≠ author of the proof |
| `INV → CT → TEST-ID → selector → one nodeid` | Claims must map to executable checks — or the plan is refused |
| Seal: plan bytes + revision + closure digest | The check that ran is the check that was reviewed |
| `MUTATION` view confined to `{src, scripts}` | Coder cannot rewrite the tests it must pass |
| Managed verifier cell | The proof is produced where the author doesn't control the environment |
| `ToolResult.fail` on settled create failure | "Finished" and "created" are one statement |

### 2.2. Six values, in order of importance

1. **Independence of evidence from the author of the claim** — the root property.
2. **Fail-closed, not fail-open** — no silent success; every refusal is structured and stable.
3. **Small verifiable steps** — one claim → one check; no wide routes around.
4. **Repair without losing evidence** — repair is a bounded loop, not a silence blanket; old evidence is preserved.
5. **Audit trail** — seal, ledger, projection; who/what/where/when, recorded.
6. **Minimalism toward new mechanisms** — new machinery only when existing substrate is exhausted. (The STEP9A seal stack is the cautionary example: built as a library, never wired into production.)

### 2.3. The critical honesty point

Values 1–2 are **not currently true in production code**, because the evidence model is not wired into the controller path. The system **looks** intact — seals mint in tests, verifiers run, verdicts print — while the chain protecting the coder has no production path. This is a wiring gap, not a bug; it is the exact class of gap the plan's E564 table names.

---

## 3. Measured facts (all re-measured 2026-11-22, not assumed from the plan)

### 3.1. KIND is read in exactly one place — and only to exempt

`grep -rn "invariant.kind\|item.kind" src/fa/` → **1 hit** (`plan_v2.py:622`, `if invariant.kind != "HARD": continue`). KIND reaches the seal, verifier, verdict and report nowhere. `SOFT` is an exemption flag, not a severity.

### 3.2. SOFT + TEST_REQUIRED with no selector and no disposition is admitted

Execution (`parse_plan` + `contract_evidence`):

```text
admitted (parse_plan returns normally)
contract_evidence(graph) = {'CT-1.1': 'executable', 'CT-1.2': 'uncovered'}
attested_contracts(graph) = ()
```

### 3.3. HARD + NON_EXECUTABLE + reason is admitted, then ATTESTED

Execution:

```text
pre-grant:  {'CT-1.1': 'executable', 'CT-1.2': 'uncovered'}  attested: ()
post-grant: {'CT-1.1': 'executable', 'CT-1.2': 'attested'}   attested: ('CT-1.2',)
```

A HARD invariant can be converted to a human signature by the planner choosing `NON_EXECUTABLE` on it. `PRESERVATION` is protected correctly only because its class check precedes the waiver branch at `:617` — ordering, not rule.

### 3.4. The seal cannot express "unverified"

`mint_seal` over an UNCOVERED graph mints fine. The record carries `selectors` + `attested` — no contract count, no uncovered set. A seal over 5 contracts / 1 test / 1 grant is **shape-identical** to 2 contracts / 1 test / 1 grant. Consumers cannot distinguish "we waived the rest" from "the rest were never mentioned".

### 3.5. "ready CT" does not exist

`grep -rn "ready" src/fa/` → 0 hits (excluding `ReadyState`/`READY` status, unrelated). Q-V2-ACC-2 and INV-05 and CT-3.1 are phrased over a category with no runtime meaning — which is exactly why "where to refuse UNCOVERED" looked answerable.

### 3.6. The STEP9A seal stack has zero production consumers

`mint_seal`/`sealed_collection_argv`/`acceptance_collection`/`acceptance_defect`/`kill_attribution` — 0 imports outside their own modules. `workflow_controller.py` has **zero** `AcceptanceBundle` references. CT-2.4's named test (`test_validation_and_seal_precede_coder...`) is absent.

### 3.7. The plan contradicts itself

| Site | Statement |
|---|---|
| Line 60 (grammar delta) | "only HARD blocks ready/admission, and `NON_EXECUTABLE` is **forbidden for HARD/ready contracts** unless Q-V2-ACC-2 is resolved under a ratified rule" — strict |
| Line 233 (production grammar) | "every hard INV/ready CT has **a test or a typed explicit evidence disposition**" — loose |
| Line 284 (INV-05) | "Every admitted hard invariant/ready CT has **an explicit evidence disposition** and complete ID graph" — loose |
| Line 511 (CT-3.1 row) | "hard invariant/ready CT must have executable evidence or **explicit reviewed disposition**" — middle |
| Line 621 (Q-V2-ACC-2 row) | BLOCKING, choices (A) executable assertion or (B) typed disposition — **pending** |
| Line 650 (§8 step 4) | "Q-V2-ACC-1/2 are closed" — **false** |

### 3.8. The repair geometry cannot fix a coverage gap

The repair stage's allowlist is increment + open-questions (`workflow_controller.py:3047-3057`, `_REPAIR_WRITABLE_SUFFIXES`). A coverage gap (a contract with no test) cannot be fixed by a repair stage that cannot write `acceptance/tests/**`. Additionally, parse refusals surface to the repair stage as `bootstrap-invalid-metadata` (the `snapshot.format_error` branch in `_admit_published_project`) — a coverage gap is misdiagnosed as a metadata problem, and the repair loop burns budget on a gap it cannot fix.

### 3.9. CLI dispositions gap

`fa invoke-workflow` forwards `task`, `roles`, `mode`, `project_action`, `project_slug` — and **not** `dispositions`. The tool schema accepts dispositions (`workflow_tool.py:245`), so a legal V2 plan is reachable from the agent path but not from the human CLI path. This is a capability gap, not a test gap (CT-1.5).

### 3.10. Two encoding tests pin the old policy

`tests/test_ai_native_plan_v2.py:720` — `test_a_contract_with_neither_a_selector_nor_a_disposition_is_uncovered`.<br>
`tests/test_ai_native_plan_v2.py:819` — `test_a_soft_invariant_may_still_stay_uncovered`.<br>
Both assert UNCOVERED is legal for SOFT. They are the only encoding of the SOFT exemption.

### 3.11. The planner verify fence still executes on the PLAN-V2 route

`slice_verification.py:552` — `subprocess.run(command, shell=True, ...)` for the planner-authored verify fence. CT-3.6 (retire on V2) has not landed.

### 3.12. `protected_paths` does not cover the closure

`workspace.py:2191-2196` and `:2810-2819` — both construction sites pass `protected_paths` only when `plan_ref is not None`, and the tuple carries `plan_ref.workspace_relative_path` only. `worklogs/<slug>/acceptance/` is unprotected — a file-tool write to the sealed closure is refused only by the authority, not by the IO layer. (CT-3.3.)

---

## 4. Problems — classified

| # | Problem | Classification | Blast radius |
|---|---|---|---|
| P1 | **Evidence model never given runtime meaning**: KIND is read once to exempt; SOFT is not a severity; "ready CT" doesn't exist | Design defect | Every contract is designed blind — the root cause |
| P2 | **Two sources of truth for the grammar**: canonical schema (V1-shaped, `TESTS:`, verify fence) vs `plan_v2.py` (V2: INVARIANTS/KIND/CT/ACCEPTANCE/selectors); skills and 4 conformance tests pin the V1 example | Root cause | Every further contract is designed against a document that cannot answer questions about its own vocabulary |
| P3 | **Plan contradicts itself** (§8 step 4 false; line 60 vs 233/284; Q-V2-ACC-2 row PENDING) | Documentation defect | The stricter reading cannot be inferred; the operator cannot decide |
| P4 | **Seal/custody/attribution/TEST-DEFECT unwired** — controller has zero `AcceptanceBundle` refs; CT-2.4 absent | Wiring defect | The whole evidence chain is inert in production; the coder is admitted without a seal |
| P5 | **Repair geometry cannot fix coverage gaps** — allowlist excludes `acceptance/tests/**`; parse refusals misdiagnosed | Geometry defect | Repair budget silently burns on a gap it cannot fix |
| P6 | **CLI `--dispositions` absent** — a legal V2 plan is unreachable from the human CLI | Capability gap | The operator path is blocked by the same policy as the agent path |
| P7 | **Planner verify fence still executes on the PLAN-V2 route** (`slice_verification.py:552`) | Unfinished migration | Planner-authored shell drives a result on a route that forbids it |
| P8 | **Canonical schema not updated** — skills still teach V1; conformance tests still pin V1 | Drift | P2 repeats forever |
| P9 | **Two encoding tests pin the SOFT exemption** | Legacy encoding | The only statement of what SOFT was for lives in tests that contradict the grammar |
| P10 | **Seal schema does not record coverage** | Missing invariant | A seal without a count or a coverage map cannot be audited without the plan graph |
| P11 | **`protected_paths` does not cover the closure** | Custody gap | File-tool writes to the closure are structurally allowed |
| P12 | **No production seals exist** | Honest fact | Migration for schema bump is free today — seals don't exist |

---

## 5. The real question — honest reframing

### 5.1. What the question is NOT

"Where to refuse UNCOVERED?" — a routing question whose answer ("at seal" vs "at admission") was never the hard part. That framing misses:

- what `KIND` obliges (currently: nothing beyond one exemption check);
- what `SOFT` means (currently: nothing distinguishable from uncovered);
- what "ready CT" means (currently: nothing);
- what `TEST_REQUIRED` means (currently: a claim the grammar makes, that nobody enforces).

### 5.2. The honest question

**What does `KIND` oblige, and is every `TEST_REQUIRED` claim discharged?**

Two sub-questions:

1. **Does the grammar's own promise (`EVIDENCE: TEST_REQUIRED`) hold?** If the plan says TEST_REQUIRED, the plan must either have a test or declare NON_EXECUTABLE and request a disposition. A claim that cannot be discharged by anything the plan can do is a broken plan.
2. **Is HARD + NON_EXECUTABLE admissible?** The plan is contradictory here. The disposition pipeline is typed, one-shot, time-boxed, grant-bound. The honest reading of INV-05 (line 284): a typed explicit evidence disposition IS acceptable evidence for a HARD invariant. The honest reading of line 60 (grammar delta): forbidden. The plan did not resolve this.

### 5.3. The honest answer (my judgment)

**Yes, TEST_REQUIRED must be discharged for every contract, for every KIND.** This makes the vocabulary tautological in the good sense: `HARD` = must execute (or be granted by the ratified pipeline); `SOFT` = not admission-gating (same discharge rule); `UNCOVERED` = never admissible. The two encoding tests pin the OLD policy and will be rewritten.

**HARD + NON_EXECUTABLE: allowed** via the ratified pipeline. The plan's line-60 strict reading should be deleted (or aligned with INV-05). The ratified alternative is executable evidence-only. This is a ratification decision, not a code fix.

**Seal must record the coverage map** — contract count + covered/attested/uncovered — so the invariant is auditable from bytes.

**The seal must be wired** (CT-2.4) before SLICE3.

### 5.4. Why not just "seal refuse UNCOVERED" (the naive fix)?

The seal-side refusal alone leaves three defects intact:

- it doesn't fix the SOFT-exemption tests or the plan contradictions;
- the defect re-mint path (`acceptance_defect.correct` → `mint_seal`) can mint a seal over an uncovered graph because it passes a caller-supplied graph;
- the repair loop still runs on garbage diagnostics (`bootstrap-invalid-metadata`) and its allowlist can't fix the gap — budget burned, BLOCKED.

The naive fix is necessary but not sufficient.

---

## 6. Proposed paths of solution — with costs and risks

### 6.1. The evidence rule (P1, P5, P9)

**Path A (my recommendation) — TIGHT admission rule.**

- Admission (`_admit_evidence`) refuses any contract whose invariant declares `EVIDENCE: TEST_REQUIRED` and which has neither a selector nor a disposition: closed rule `contract-uncovered`.
- Both KINDs. Not only HARD.
- The seal also refuses an UNCOVERED graph — the defense-in-depth for the defect re-mint path (different invariant, same rule).
- The two encoding tests are rewritten to the new rule.

**Cost:** two tests flip; repair geometry needs widening (6.2); the diagnostic map needs the new family.<br>
**Risk:** blocks the repair budget if not paired with 6.2; the two tests' semantic shift is visible in the diff (good).

**Path B — keep the SOFT exemption.** The plan never states it; the encoding tests pin it. The only honest output: the seal must record UNCOVERED (visible but legal).

**Cost:** zero. **Risk:** the grammar's own promise is unenforced; a TEST_REQUIRED claim can ship unproven.

### 6.2. Repair geometry (P5)

**Path A (my recommendation) — family-scoped allowlist.**

- The repair allowlist varies by refusal family: content refusals (grammar/graph) → increment + open-questions + acceptance/tests/**; Q-record refusals → open-questions only.
- The repair stage's task text and the diagnostic mapping are updated; the D8 misdiagnosis (`bootstrap-invalid-metadata` for a coverage gap) is fixed.
- `test_a_create_new_repair_may_write_only_the_documents_admission_read` is amended.

**Path B — coverage refusals non-repairable.** Run ends BLOCKED with an actionable diagnostic. Honest, but throws away the repair budget on a gap the planner could fix.

### 6.3. Seal self-description (P10)

**Path — record the coverage map.** Add to `AcceptanceBundle` (and the seal record): `contract_total`, `covered`, `attested`, `uncovered` (uncovered always empty after 6.1). `SCHEMA_VERSION` bump 1 → 2. **Zero migration cost — no production seals exist** (the STEP9A seal stack is unwired; `load_seal` refuses unknown versions, so old seals fail closed, which is safe).

### 6.4. HARD + NON_EXECUTABLE (P1)

**Path A (my recommendation) — allow via ratified pipeline.** Align the plan with INV-05 (line 60 strict reading deleted or aligned).

**Path B — refuse (strict reading of line 60).** Line 233/284 delete themselves.

### 6.5. CLI dispositions (P6)

Bounded: add `--dispositions <path-or-json>` to the `invoke-workflow` parser, pass through unmodified. One test. No second validation rule.

### 6.6. Schema/skills/conformance rewrite (P2, P8)

**Path A (my recommendation) — one coherent change set with the grammar fix.** The canonical schema (`artifact-schema-and-grammar.md`) becomes V2: INVARIANTS/KIND/EVIDENCE/SLICE/CT/ACCEPTANCE/selectors, with "ready CT" deleted, INV-05/grammar-delta/CT-3.1 aligned to the ratified evidence rule. Skills (`feature-planning`, `plan-authoring`, `tests-writing`) + INJECT surfaces + 4 conformance test files in the same commit.

**Path B — schema alone, grammar fix separately.** Reintroduces the drift. Not recommended.

### 6.7. Seal wiring (P4)

**Path — implement CT-2.4 (publish→seal, D-V2-5 on the D-V2-9 revision).** Emit the complete schema-declared acceptance manifest into the seal request; the authority mints a controller-minted seal bound to plan bytes + revision receipt; admission refuses a missing/stale seal before coder. Then CT-3.2/3.3/3.6 proceed.

### 6.8. Plan consistency (P3)

Documentation-only: delete or align line 60; delete "ready CT" (use "a contract that gates admission"); fix §8 step 4; record ACC-2 resolved D-V2-10 + repair geometry + schema rewrite as one ratified change set.

---

## 7. Expert opinion — the global problem

### 7.1. What the global problem is

**The system has been built twice as long as it has been wired.**

- The V2 grammar is parser-complete, controller-admission-wired, and never published as the canonical source of truth.
- The seal/custody/attribution/TEST-DEFECT stack is built, tested (45+30 tests), and never called.
- The canonical schema describes a different grammar. Skills teach it. Conformance tests pin it.
- The evidence model — the ONE place where the system records how a claim is checked — is written and then left unenforced: KIND read once to exempt, SOFT unknowable, "ready CT" unexistent.

This is the same drift the plan itself warns about ("two descriptions of the grammar is how the router and the parser drifted apart", line 60 note + P0-1). It is the global problem. The local questions (Q-V2-ACC-2, CT-3.1, CT-2.4) are all downstream of it.

### 7.2. The cause (not the symptom)

A grammar with two sources of truth. The plan mandated the fix: "Make the canonical Markdown schema the only V2 source" (§2 line 58). That step was never done. Everything else — Q-V2-ACC-2, Q-V2-ACC-1, CT-3.1, mode A — reads out of that unfilled plan.

### 7.3. The recommendation (the global fix, in order)

1. **One change set:** canonical schema rewrite (V2) + skills + conformance tests + grammar fix + repair geometry + CLI dispositions. ONE PR. The drift is the defect; fixing the pieces separately guarantees it repeats.
2. **The evidence rule:** TEST_REQUIRED must be discharged for every contract, for every KIND (Path A in 6.1). The SOFT exemption was an implementation gap, not a ratified decision. Rewrite the two encoding tests.
3. **HARD + NON_EXECUTABLE allowed via the ratified pipeline** (Path A in 6.4). Delete or align the line-60 strict reading.
4. **Seal self-describing** (Path A in 6.3). Coverage map + `contract_total`. Schema bump, free today.
5. **CT-2.4 wiring** (Path A in 6.7) before SLICE3. The seal is the only thing that makes the coder dependable.
6. **Seal record as auditable**: `uncovered` empty by construction; a future regression is detectable from bytes.
7. **Record ACC-1 budget half as closed-by-code; transitive half as a named residual** — not a closable gate.
8. **Delete "ready CT" and fix every contradiction in the plan** (§8 step 4 "are closed"). The plan is the artifact the next agent reads; it must be true.

### 7.4. What NOT to do — with reasons

1. **Do not land the schema rewrite separately from the grammar fix.** Two sources = the original defect.
2. **Do not unilaterally flip SOFT to admission-required without ratification.** It is a policy change; it must be ratified (D-V2-10) before the code changes.
3. **Do not widen the repair allowlist without the diagnostic mapping.** The repair stage misdiagnoses today.
4. **Do not delete the two encoding tests.** They are the only encoding of SOFT; deleting them silently removes the only statement of what SOFT was for. Rewrite them.
5. **Do not treat the seal-side refusal as duplication of the admission gate.** Different paths (defect re-mint vs normal admission), different invariants.
6. **Do not present the transitive-import half of ACC-1 as closable.** It is a named residual.
7. **Do not stay in "where to refuse" — the real answer is "what KIND obliges".** The first question unblocks nothing.
8. **Do not skip the schema rewrite because "the parser works".** The parser is the de-facto truth; it is not the source of truth. That is the defect.

### 7.5. The honest limits

- No test suite has been run in this sandbox (no Python 3.13 toolchain). All measurements were performed by executing production modules directly with synthetic fixtures; structural facts were grep-verified.
- The plan's STEP9B review gate (§8 step 1) is still pending. The global fix is a plan-level change: it must go through the plan's review before implementation.
- The status-tick design gate (§2 of the plan) is independent and blocking SLICE4/5 — this package does not address it and must not be mistaken for doing so.

---

## 8. Implementation order — explicit dependencies

### Phase 1 — documentation + ratification (no code; must be ratified first)

| Step | Work | DoD |
|---|---|---|
| 1.1 | Rewrite the canonical schema to V2 + delete "ready CT" + fix §8 step 4 + align line 60/233/284/511 with the ratified rule + resolve the Q-V2-ACC-2 row + record ACC-1 closed-by-code | Plan, schema, skills agree byte-for-byte; the operator has ratified (Phase 1 DoD) |
| 1.2 | Skills + conformance tests + INJECT surfaces in the same commit | Skills and schema agree; conformance tests pass |
| 1.3 | Record D-V2-10: evidence rule + repair geometry + CLI dispositions + schema rewrite = one ratified change set | Operator ratification |

### Phase 2 — the evidence fix (one coherent PR)

| Step | Work |
|---|---|
| 2.1 | `_admit_evidence`: refuse a contract whose invariant declares TEST_REQUIRED and which has neither a selector nor a disposition (`contract-uncovered`) |
| 2.2 | Seal: add `contract_total` + coverage map (`covered`/`attested`/`uncovered`); refuse UNCOVERED with closed rule `uncovered-contract`; schema_version bump |
| 2.3 | Rewrite the two encoding tests (§3.10) |
| 2.4 | Repair: family-scoped allowlist + diagnostic mapping + task text; update the geometry test |
| 2.5 | CLI: `--dispositions` pass-through |
| 2.6 | No code change for HARD + NON_EXECUTABLE (already admitted); alignment lives in the plan (1.1) |

**DoD:** parse refuses the previously-admitted cases; seal refuses an uncovered caller-supplied graph; repair fixes a coverage gap (second authoring stage writes the missing acceptance test file); two encoding tests rewritten; no production seal exists yet (CT-2.4/3.6 still open).

### Phase 3 — SLICE2/3 wiring (dependencies, not preferences)

| # | Work | Notes |
|---|---|---|
| 3.1 | **CT-2.4 — seal mint wiring** (publish → seal, D-V2-5 on the D-V2-9 revision) | **First.** Everything else waits |
| 3.2 | **CT-3.3 — mode-A projection** (protected paths + acceptance closure) | D-V2-6 |
| 3.3 | **CT-3.6 — verifier uses sealed closure; retire planner fence on PLAN-V2** | |
| 3.4 | **CT-3.2 — seal materialization into verifier path** (`sealed_collection_argv` wiring) | |
| 3.5 | **CT-3.1 — graph + nodeid edges** (after Phase 1/2 ratify ACC-2) | Currently BLOCKING |
| 3.6 | **CT-3.4/3.5 — attribution, TEST-DEFECT** (after seal mint) | |

### What is NOT in this package

- No code changes.
- No plan changes without ratification (Phase 1 is the ratification).
- No claim that SLICE4/5 can start — the status-tick design gate blocks them.

---

## 9. Ratification points — explicit, in order

| # | Decision | My recommendation |
|---|---|---|
| D1 | Admission rule for uncovered TEST_REQUIRED (any KIND) | **TIGHT** (refuse at admission + at seal; rewrite two encoding tests) |
| D2 | HARD + NON_EXECUTABLE | **Allow** via ratified pipeline; delete line-60 strict reading |
| D3 | Seal records coverage map | **Yes** (`contract_total` + covered/attested/uncovered; schema bump; zero migration) |
| D4 | Repair geometry for coverage refusals | **Widen** (family-scoped; test) |
| D5 | CLI `--dispositions` | **Yes** (bounded, one test) |
| D6 | Schema/grammar/repair/CLI rewrite = one change set | **Yes** |
| D7 | Plan internal consistency (§8 step 4, line 60, "ready CT") | **Yes** (documentation, first) |

**Ratification gate:** Phase 1 is ratified by the operator before Phase 2. Phase 2 changes admission semantics; it is not a "code fix".

---

## 10. What is NOT verified (honest limits)

1. The test suite has NOT been run in this sandbox — no Python 3.13 toolchain. Measurements were performed by executing the production modules directly (parse, bind, mint) with synthetic fixtures; structural facts were grep-verified.
2. No decision in this package is ratified. D1–D7 are recommendations.
3. The plan is REVIEW DRAFT (STEP9B). Phase 1/2/3 are blocked until STEP9B lands and the operator ratifies.
4. The status-tick design gate (§2 of the plan) is independent and blocks SLICE4/5. This package must not be mistaken for resolving it.
5. The `verify_slice` gate (legacy route) is not addressed here.
6. No host-side verification exists for V2 — SLICE5 is not started.

---

## 11. Appendix — measurement trail (every claim cited)

| # | Claim | Method | Line |
|---|---|---|---|
| 1 | KIND read once | grep | `plan_v2.py:622` |
| 2 | SOFT + TEST_REQUIRED + no selector → admitted | execution | — |
| 3 | SOFT + TEST_REQUIRED + no selector → UNCOVERED | execution | — |
| 4 | HARD + NON_EXECUTABLE + reason → admitted | execution | — |
| 5 | HARD + NON_EXECUTABLE + grant → ATTESTED | execution | — |
| 6 | Seal mints over UNCOVERED graph | execution | — |
| 7 | Seal does not record contract count | grep record fields | `acceptance_bundle.py` `_record()` |
| 8 | "ready CT" absent | grep | `src/fa/` (0 hits) |
| 9 | STEP9A seal stack has zero production consumers | grep | `workflow_controller.py` (0 `AcceptanceBundle` refs) |
| 10 | Plan contradicts itself | read | plan lines 60, 233, 284, 511, 621, 650 |
| 11 | Repair allowlist cannot fix coverage gap | read | `workflow_controller.py:3047-3057` |
| 12 | Parse refusals surface as `bootstrap-invalid-metadata` | read | `workflow_controller.py` `_admit_published_project` |
| 13 | CLI drops `dispositions` | read | `cli.py:999-1001`, `workflow_tool.py:245` |
| 14 | Two encoding tests pin the old policy | read | `test_ai_native_plan_v2.py:720`, `:819` |
| 15 | Verify fence still executes on V2 | read | `slice_verification.py:552` |
| 16 | `protected_paths` does not cover closure | read | `workspace.py:2191-2199`, `:2810-2819` |
| 17 | Metadata cross-check is identity-only | read | `project_metadata.py` |
| 18 | Repair budget is `replans_allowed` | read | `workflow_controller.py:2950` |
| 19 | CT-2.4 absent (named test nonexistent) | grep | plan line 517 |
| 20 | Bootstrap tests count (26) | grep | `test_ai_native_bootstrap.py` |
| 21 | PLAN-V2 parser test count (45) | grep | `test_ai_native_plan_v2.py` |
| 22 | Acceptance closure budgets (512/4MiB/16MiB/4096/64) | read | `acceptance_closure.py:51-55` |
| 23 | pytest_argv pins `-c`/`--rootdir` + closed `--addopts` | read | `acceptance_closure.py` |
| 24 | Bundle tests (45), closure tests (30) | grep | `tests/test_ai_native_acceptance_bundle.py`, `test_ai_native_acceptance_closure.py` |
| 25 | The two encoding tests' exact bodies | read | `test_ai_native_plan_v2.py:720-727`, `:819-826` |

---

*No production code, tests, or the plan were modified by this package.*
