# E2E handoff, plan review, and status design

**Status:** working design for the planning-topology reference project
**Recorded:** 2026-10-09
**Purpose:** preserve the agreed operating model before it is applied to the canonical artifact schema, prompts, skills, and I02 acceptance package.

This is a design record, not evidence that the schema, prompts, E2E artifacts, or controller behavior have been implemented. Confirmed choices, recommendations, and open implementation details are distinguished below so a future slice does not silently turn a proposal into policy.

## 1. Confirmed project decisions

- **Roadmap lifecycle:** `IN PROGRESS` / `DONE`.
- **Increment lifecycle:** `OUTLINED` → `IN PROGRESS` → `SHIPPED`; remove increment-level `READY`.
  - `OUTLINED`: a short roadmap outline, not yet an executable increment plan.
  - `IN PROGRESS`: the increment plan has been written in full with slices and steps and is ready to execute; implementation may also be underway.
  - `SHIPPED`: the increment's own DoD is complete, including code/tests/eval judgment and any additional requirements that increment explicitly lists.
- **Contract lifecycle:** `PLANNED` → `IMPLEMENTED` → `VERIFIED`.
  - `PLANNED`: declared as a `CT#` in an increment.
  - `IMPLEMENTED`: the code exists and its required unit/mutation proof passes.
  - `VERIFIED`: the harness's deterministic evidence passes and the eval role's contract judgment passes. Eval does not overrule a determinate blocking gate; the gate remains a floor. Stochastic verification retains the existing pass^k rule.
- **Step markers:** `[ ]` todo, `[>]` in progress, `[x]` done.
- **E2E is separate evidence, not a universal increment status and not a harness/eval verdict.** A particular increment may explicitly require live E2E in its DoD. I02 does; therefore I02 still needs live-host evidence before it is declared shipped. Other increments need not all be live-tested at the moment their code work closes.
- **Deployment path:** no separate staging/dev host. For I02, prepare the live-verification package in the branch, merge to `main`, run the normal update/rebuild, then test the deployed main image. Start in observe mode; review artifacts before any enforce-mode run.
- **E2E artifact layout:**

  ```text
  worklogs/<project>/e2e/
    README.md                    # planner-owned case index
    I02/
      live-verification.md       # planner-owned operator sheet
      implementation-handoffs.md # coder appends seam observations/proposals
      fixtures/                  # coder implements planned fixtures/helpers
  ```

The roadmap is planner-written (chat may prompt), not harness-written. Its increment list may carry a concise live-E2E summary and evidence link. The E2E result is assigned by the operator or an LLM only after the run output has been collected and evaluated.

## 2. Planner/coder/reviewer/operator handoff

The key design distinction is **acceptance oracle versus implementation seam**. The planner should not guess code-specific seams; the coder should not have unilateral authority to define what success means or to certify its own work.

1. **Planner, before coding:** record the E2E obligation for each applicable contract/producer: the behavior to observe, the negative case that must be caught, and any known live-host constraint. The observable contract is fixed before implementation; exact commands and fixture details may be refined later when the code seam is known.
2. **Coder, during/after implementation:** append an implementation handoff for new or changed producers. It supplies code-grounded facts and fixture proposals; it does not change the contract oracle, the E2E case's ownership, or its pass status.
3. **Planner:** use the handoff to write/finalize the operator run sheet. Keep the acceptance condition consistent with the original contract.
4. **Independent plan reviewer:** check the plan and E2E package before execution. The planner's own anti-theater/self-check is not this review.
5. **Coder:** may implement fixture/helper files named in the reviewed plan. A material change to the oracle requires a plan revision and re-review.
6. **Operator:** runs the copy/paste CLI/Python instructions on the deployed host and supplies outputs/run identifiers.
7. **Operator or LLM reviewer:** evaluates the supplied evidence against the stated oracle and records the live result. Neither harness nor eval-role code sets this result.

### Coder handoff fields

Keep each handoff concise and evidenced: contract/producer IDs, source references, production path, observable effect or artifact, host prerequisites, candidate fixture/command, and known limitations. Label assertions about the code as facts only when the coder can point to evidence; label suggested checks as proposals.

A handoff should answer, at minimum:

- Which declared CTs and producers does it cover?
- What source locations and production call path were verified?
- What useful observable boundary/artifact is reached on the live path?
- Which host/workspace/venv/config prerequisites matter?
- What candidate fixture and command exercise it?
- What does the in-repo proof already establish, and what remains host-only?
- What could not be verified or needs planner/reviewer disposition?

A suggested Markdown shape (field names are a proposal until the artifact schema is updated):

```markdown
## I02 / SLICE# — coder E2E handoff
- Contracts / producers:
- Verified source references:
- Production path:
- Observable effect / artifact:
- Host prerequisites:
- Candidate fixture / command: [PROPOSAL]
- Local proof:
- Host-only assumptions / limitations:
- Evidence references:
- Planner disposition: pending
```

The live E2E case should assert behavior at a **useful observable boundary**. Internal helper names may identify implementation seams in the handoff, but should not become the sole live assertion. A single host scenario may cover several producer rows if each row is explicitly mapped to the observable proof; this does not remove the standing requirement to track each producer.

## 3. E2E case index and result recording

`e2e/README.md` is the planner-owned index of required live cases. Each entry should map stable case ID(s) to increment, slice, CTs, producer(s), fixture/run-sheet paths, local-proof references, and expected live observations. The detailed I02 commands and fixtures live under `e2e/I02/`, not in the evidence ledger.

**Recommended I02 row model (the increment plan uses it; retain as a proposal until operator review):** keep local proof separate from live result. The current `unit | planned | e2e` vocabulary mixes proof level, preparation, and execution. Use `NOT RUN | PASS | FAIL | BLOCKED` for live status, with append-only attempts carrying run ID, deployed SHA, command, date, and artifact references. The enum records evidence ownership only; it must never imply that the harness assigned a live result. SLICE7's artifact-contract test checks field shape and duplicate coverage, not live status.

The roadmap should carry only a concise per-increment summary (for example, not run / partial / pass plus run/SHA reference). Full commands, fixtures, and per-case outcomes stay in `e2e/`. The append-only ledger may receive a concise provenance entry for a completed run, but it is not the fixture repository and its parser is not implemented yet (I04).

Do not check secrets, large host logs, or credentials into the E2E directory. Keep only the fixture/helper files needed to reproduce the test and the minimal evidence reference/summary.

## 4. Plan review

Plans require an independent review pass after initial creation and before fixture/helper implementation or host execution. The review checks contract coverage, test quality, producer/consumer wiring, E2E obligations, command safety, artifact paths, and whether the operator can observe the required outcomes. Do not count the planner's self-check as independent review.

**Confirmed operator choice, 2026-10-09:** record a checklist-only manual review. The sheet contains the reviewer, review date, checkboxes, and short notes; it is a human record, not a hash-bound approval marker, machine-readable `approved: true` field, or automated controller gate. Material changes to an oracle, command, or fixture require a new manual checklist entry. This review record does not assign or imply a live-E2E result.

The generic `DRAFT | READY | BLOCKED` statuses in planning skills may refer to a different plan-authoring gate. When editing prompts, audit their meaning rather than globally replacing every `READY`. The final wording must make increment lifecycle, manual plan review, CT state, and E2E result distinct.

## 5. Current implementation facts and implications

- `plan_ids.py` reads increment body grammar, not increment frontmatter lifecycle or review fields. Changing frontmatter values will not break its current parser, but the parser will not validate or update them.
- `SliceRecord.contracts` currently carries `(id, class, text)`; it has no parsed CT lifecycle status.
- No production module reads an E2E register or E2E directory. `parse_ledger()` is specified but remains I04 work.
- Therefore the E2E index/result remains planner/operator/LLM-owned unless a later slice explicitly adds a read-only coverage validator. No harness behavior may mark live E2E as passed.
- The existing I02 register's malformed-directive row is stale: it expects immediate blocking, while Q57 now requires bounded planner repair and revalidation in both linear and adaptive workflows. `validate_kill_directives` has no production caller; I02 SLICE2 CT52/CT53 prove the pure validator only. The C1 composition-root test must observe successful repair and coder/eval only after admission, plus blocked exhaustion/indeterminate cases. The register also contains duplicate `_producer_absent` and `_classify` rows that SLICE7 must merge without losing unique producers.
- I02 currently declares `slices: 8`, including the explicitly authorized local exception above the global seven-slice ceiling. This does not revise the global sizing rule.
- A 2026-10-09 direct pure-module probe confirmed both `precheck("")` and `validate_kill_directives("", extract_plan_ids(""))` return no blocking diagnostic. Empty input must block; a non-empty no-slice plan with a determinate structural near-miss (such as a misspelled slice heading) may repair through Q57, but a final no-slice parse—or one with no determinate repair diagnostic—must block rather than treat an empty parsed set as admission success.

## 6. I02 disposition and later work

Fold the following into I02 **before its main-host deployment/E2E run**:

1. Close admission wiring with one shared pre-coder helper used by linear and adaptive dispatch. The C1 test must boot `run_workflow` → `_cmd_run` → `drive_session`, mock only `ProviderChain.request`, prove deterministic diagnostics reach bounded planner repair, and assert coder/eval do not run until the revised plan passes. Cover blocked exhaustion, no planner, indeterminate input, and the empty-plan fail-open guard. Name every production producer call whose deletion makes its test fail.
2. Require explicit `--plan` for coder workflows (E137). Missing/unreadable/empty input blocks; a non-empty no-slice plan with a determinate structural diagnostic may be repaired, but no-slice input with no such diagnostic or a still-invalid final candidate blocks in direct controller calls. Capture T0 only after admission, persist attempt diagnostics/routes in `admission.json`, and preserve the write-once baseline across adaptive replan.
3. Add one I02 slice for the E2E artifacts/schema/skills: planner-owned case index, operator run sheet, coder implementation handoff, reviewed-before-fixture sequence, and manual review checklist.
4. Retain I02's live-host E2E DoD. There is no separate staging: merge to `main`, use the normal update/rebuild, verify deployed SHA/health, then test. First verify-gate run is observe; admission remains blocking independent of that mode; an operator reviews persisted evidence before enforce-mode testing. Interpret `fa update`'s test rc separately from deployment/health because it can exit nonzero after deployment.

Do **not** fold generic automated plan-review infrastructure into I02. The selected checklist is manual only; implement any future machine approval gate in later planning/tracker work, never as a live-E2E result setter.

### Resolved decision and remaining implementation details

- **Q57 — RESOLVED by operator, 2026-10-09:** determinate admission diagnostics go to the planner through bounded repair in the same invocation in both modes; revalidate each revision; no coder while diagnostics remain; exhaustion or indeterminate validation is `blocked`. No eval runs for a pre-coder rejection; Q55 applies after successful coder stages. The diagnostic and final route must be observable. Linear remains one-pass for eval outcomes. See `notes/open-questions-2026-10-07.md`.
- **Q58 — RESOLVED by operator, 2026-10-09.** The operator accepted the controller-owned candidate and exact-target planner writer, with physical promotion back to the same canonical increments file. The planner writes only `.fa/admission/<run_id>/candidate-*`; after both validators pass, the controller rechecks the source hash, stages beside the canonical file, and atomically replaces the original at the exact supplied `--plan` path under `worklogs/.../increments/`. That increments path remains the sole current plan; the `.fa` candidate is staging only and is removed after promotion, while attempt/diagnostic/target/source/candidate/promoted hashes and routes remain in `admission.json`. It is never an alternate active location; do not broaden the general planner allowlist. The hash check is concurrency protection, not a review approval. Live E2E uses a disposable copy at the same relative path and never mutates the tracked source plan. See Q58 in `notes/open-questions-2026-10-07.md`.
- SLICE7 should use distinct local-proof and live-result fields; `NOT RUN | PASS | FAIL | BLOCKED` is the current recommendation, not an operator-ratified policy. The live result remains operator/LLM-owned after evidence collection.
- Update canonical status ownership so increment lifecycle/roadmap E2E summary are not confused with harness-owned CT/STEP ticks during SLICE7.

## 7. Documents to update from this design

The I02 follow-up slice should update or create the following, rather than leaving this note as an unconnected design:

- `notes/artifact-schema-and-grammar.md` — increment/CT state semantics, optional `e2e/` artifact, and ownership rules.
- `roadmap.md` — I02 lifecycle and concise live-E2E status/evidence summary.
- `increments/increment-02-verify-gate-and-kill-checks.md` — admission integration, E2E package, explicit live-host DoD.
- `notes/e2e-live-verification-register.md` — migrate/reconcile into the new E2E index without losing any unique producer case; remove exact duplicate rows.
- `knowledge/skills/feature-planning/SKILL.md` and `INJECT.md` — planner records E2E obligations before coding and finalizes the operator sheet from the coder handoff.
- `knowledge/skills/plan-authoring/SKILL.md` — plan-review lifecycle and increment status parity.
- `knowledge/skills/tests-writing/SKILL.md` and `INJECT.md` — coder handoff facts/proposals, observable-boundary rule, and no self-assigned E2E pass.
- Add/update focused conformance tests for the prompt/schema and E2E index format. Do not make live-host E2E part of the harness's local `VERIFIED` state.

## 8. Non-goals

- Do not create a separate dev/staging host or change the main-only deployment workflow.
- Do not let the coder author or approve its own E2E oracle/result.
- Do not have the eval role claim a live-host result from mocked/local test output.
- Do not broaden the global slice ceiling because I02 received one explicit exception.
